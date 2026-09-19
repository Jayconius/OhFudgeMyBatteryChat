"""Global hotkeys for the mute macros (Windows RegisterHotKey) plus the
helpers that turn a combo into a readable, storable string like
"CTRL+SHIFT+NUM5" and back.

RegisterHotKey fires whichever program has focus (a game, SteamVR, the
desktop) and works while this app sits in the tray. Two caveats worth
knowing: another program that already claimed the same combo wins (the
manager reports it in .failed instead of failing silently), and a few
games/anti-cheat layers swallow keystrokes before Windows sees them.
"""
import ctypes
import threading
from ctypes import wintypes

MOD_ALT, MOD_CONTROL, MOD_SHIFT, MOD_WIN = 0x1, 0x2, 0x4, 0x8
MOD_NOREPEAT = 0x4000
WM_HOTKEY = 0x0312
WM_QUIT = 0x0012

# (modifier bit, display name) in the fixed order they're written out.
_MOD_ORDER = ((MOD_CONTROL, "CTRL"), (MOD_ALT, "ALT"), (MOD_SHIFT, "SHIFT"), (MOD_WIN, "WIN"))
MODIFIER_VKS = {0x10, 0x11, 0x12, 0x5B, 0x5C, 0xA0, 0xA1, 0xA2, 0xA3, 0xA4, 0xA5}

_VK_TO_NAME = {}
_NAME_TO_VK = {}


def _add(vk, name):
    _VK_TO_NAME[vk] = name
    _NAME_TO_VK[name] = vk


for _c in range(ord("A"), ord("Z") + 1):
    _add(_c, chr(_c))
for _d in range(10):
    _add(0x30 + _d, str(_d))
    _add(0x60 + _d, f"NUM{_d}")
for _f in range(1, 25):
    _add(0x6F + _f, f"F{_f}")
for _vk, _n in (
    (0x6A, "NUM*"), (0x6B, "NUM+"), (0x6D, "NUM-"), (0x6E, "NUM."), (0x6F, "NUM/"),
    (0x0C, "CLEAR"), (0x20, "SPACE"), (0x0D, "ENTER"), (0x09, "TAB"), (0x08, "BACKSPACE"),
    (0x2D, "INSERT"), (0x2E, "DELETE"), (0x24, "HOME"), (0x23, "END"),
    (0x21, "PAGEUP"), (0x22, "PAGEDOWN"), (0x25, "LEFT"), (0x26, "UP"), (0x27, "RIGHT"), (0x28, "DOWN"),
    (0x13, "PAUSE"), (0x91, "SCROLLLOCK"),
    (0xBA, ";"), (0xBB, "="), (0xBC, ","), (0xBD, "-"), (0xBE, "."), (0xBF, "/"),
    (0xC0, "`"), (0xDB, "["), (0xDC, "\\"), (0xDD, "]"), (0xDE, "'"),
):
    _add(_vk, _n)


def format_hotkey(mods, vk):
    """(MOD_CONTROL|MOD_SHIFT, 0x65) -> "CTRL+SHIFT+NUM5"; None if vk unknown."""
    key = _VK_TO_NAME.get(vk)
    if key is None:
        return None
    parts = [name for bit, name in _MOD_ORDER if mods & bit]
    return "+".join(parts + [key])


def parse_hotkey(text):
    """"ctrl+shift+num5" -> (mods, vk), or None if it isn't a valid combo.
    The key name is the last token, so a literal "+" key can't be used
    (use NUM+ instead) - "CTRL++" is rejected rather than guessed at."""
    if not text or not isinstance(text, str):
        return None
    tokens = [t.strip().upper() for t in text.strip().split("+")]
    if len(tokens) < 1 or not tokens[-1]:
        return None
    mods = 0
    by_name = {name: bit for bit, name in _MOD_ORDER}
    for token in tokens[:-1]:
        bit = by_name.get(token)
        if bit is None:
            return None
        mods |= bit
    vk = _NAME_TO_VK.get(tokens[-1])
    if vk is None:
        return None
    return mods, vk


def allows_bare(vk):
    """Whether a key may be a hotkey with no modifier held. Function keys
    (F1-F24, the usual target for macro pads and controller-to-keystroke
    tools) and numpad keys are fine alone; anything typed - letters, digits,
    Space, Enter, arrows - would fire while the user types, so those need a
    Ctrl/Alt/Shift/Win as well."""
    return 0x70 <= vk <= 0x87 or 0x60 <= vk <= 0x6F or vk == 0x0C


def current_modifiers():
    """Modifier bits currently held, read straight from the keyboard state -
    more reliable than the Tk event's state bits, which differ per platform."""
    user32 = ctypes.windll.user32
    mods = 0
    for vk, bit in ((0x11, MOD_CONTROL), (0x12, MOD_ALT), (0x10, MOD_SHIFT)):
        if user32.GetAsyncKeyState(vk) & 0x8000:
            mods |= bit
    if (user32.GetAsyncKeyState(0x5B) & 0x8000) or (user32.GetAsyncKeyState(0x5C) & 0x8000):
        mods |= MOD_WIN
    return mods


class HotkeyManager:
    """Owns one background thread running the Win32 message loop that
    RegisterHotKey needs. set_bindings() replaces every registration (the
    thread is restarted - registrations are per-thread), and on_hotkey(key)
    is called on that thread with whatever key the binding was set under, so
    keep it quick (hand off to a queue)."""

    def __init__(self, on_hotkey):
        self.on_hotkey = on_hotkey
        self.failed = {}  # key -> reason, for the last set_bindings()
        self._thread = None
        self._thread_id = None

    def set_bindings(self, bindings):
        """bindings: {key: "CTRL+SHIFT+NUM5"} - blank/None combos are skipped."""
        self.stop()
        wanted = {k: v for k, v in bindings.items() if v}
        self.failed = {}
        if not wanted:
            return
        ready = threading.Event()
        self._thread = threading.Thread(target=self._run, args=(wanted, ready), daemon=True)
        self._thread.start()
        ready.wait(timeout=3)

    def stop(self):
        if self._thread is not None and self._thread.is_alive() and self._thread_id:
            ctypes.windll.user32.PostThreadMessageW(self._thread_id, WM_QUIT, 0, 0)
            self._thread.join(timeout=2)
        self._thread = None
        self._thread_id = None

    def _run(self, bindings, ready):
        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32
        user32.RegisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int, wintypes.UINT, wintypes.UINT]
        user32.GetMessageW.argtypes = [ctypes.POINTER(wintypes.MSG), wintypes.HWND, wintypes.UINT, wintypes.UINT]
        user32.PeekMessageW.argtypes = [ctypes.POINTER(wintypes.MSG), wintypes.HWND, wintypes.UINT, wintypes.UINT, wintypes.UINT]

        msg = wintypes.MSG()
        user32.PeekMessageW(ctypes.byref(msg), None, 0, 0, 0)  # forces this thread's message queue to exist
        self._thread_id = kernel32.GetCurrentThreadId()

        id_to_key = {}
        for i, (key, text) in enumerate(bindings.items(), start=1):
            parsed = parse_hotkey(text)
            if parsed is None:
                self.failed[key] = "not a valid key combination"
                continue
            mods, vk = parsed
            if user32.RegisterHotKey(None, i, mods | MOD_NOREPEAT, vk):
                id_to_key[i] = key
            else:
                self.failed[key] = "already in use by another program"
        ready.set()

        while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
            if msg.message == WM_HOTKEY:
                key = id_to_key.get(msg.wParam)
                if key is not None:
                    try:
                        self.on_hotkey(key)
                    except Exception:
                        pass  # never let a callback bug kill the message loop
        for i in id_to_key:
            user32.UnregisterHotKey(None, i)
