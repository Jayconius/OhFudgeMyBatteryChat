"""Keeps a single copy of an app running per Windows session.

The first copy creates a named mutex (the kernel removes it automatically if
that copy crashes, so there's never a stale lock to clean up) and a named
event. A later copy sees the mutex already exists, sets the event - which the
first copy is listening for - and exits; the first copy then brings its own
window to the front (including out of the system tray). If the event can't be
signalled the caller is told, so it can show a plain "already running"
message instead of exiting silently.
"""
import ctypes
import threading
from ctypes import wintypes

ERROR_ALREADY_EXISTS = 183
EVENT_MODIFY_STATE = 0x0002
WAIT_OBJECT_0 = 0
ASFW_ANY = 0xFFFFFFFF

_k32 = ctypes.WinDLL("kernel32", use_last_error=True)
_u32 = ctypes.WinDLL("user32", use_last_error=True)
_k32.CreateMutexW.argtypes = [ctypes.c_void_p, wintypes.BOOL, wintypes.LPCWSTR]
_k32.CreateMutexW.restype = wintypes.HANDLE
_k32.CreateEventW.argtypes = [ctypes.c_void_p, wintypes.BOOL, wintypes.BOOL, wintypes.LPCWSTR]
_k32.CreateEventW.restype = wintypes.HANDLE
_k32.OpenEventW.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.LPCWSTR]
_k32.OpenEventW.restype = wintypes.HANDLE
_k32.SetEvent.argtypes = [wintypes.HANDLE]
_k32.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
_k32.WaitForSingleObject.restype = wintypes.DWORD
_k32.CloseHandle.argtypes = [wintypes.HANDLE]
_u32.AllowSetForegroundWindow.argtypes = [wintypes.DWORD]


class SingleInstance:
    def __init__(self, name="OhFudgeMyBatteryChat"):
        self._mutex_name = f"Local\\{name}.SingleInstance"
        self._event_name = f"Local\\{name}.ShowWindow"
        self._mutex = None
        self._event = None
        self._stop = threading.Event()
        self._thread = None
        self.signalled = False  # after a failed acquire(): did the running copy get told?

    def acquire(self) -> bool:
        """True if this is the only copy (keep going); False if another copy
        is already running - it has been asked to come to the front, and
        the caller should exit."""
        ctypes.set_last_error(0)
        self._mutex = _k32.CreateMutexW(None, False, self._mutex_name)
        already = ctypes.get_last_error() == ERROR_ALREADY_EXISTS
        if not self._mutex:
            return True  # couldn't create the lock at all - never block the app over that
        if not already:
            # Created up front (auto-reset) so a second launch that arrives
            # before this copy's window even exists isn't lost - the signal
            # simply waits until start_listening() picks it up.
            self._event = _k32.CreateEventW(None, False, False, self._event_name)
            return True
        _k32.CloseHandle(self._mutex)
        self._mutex = None
        self.signalled = self._signal_existing()
        return False

    def _signal_existing(self) -> bool:
        # This process was just launched by the user, so it may hand its
        # right to take the foreground to the copy that's about to raise
        # itself - without it Windows only flashes the taskbar button.
        _u32.AllowSetForegroundWindow(ASFW_ANY)
        handle = _k32.OpenEventW(EVENT_MODIFY_STATE, False, self._event_name)
        if not handle:
            return False
        try:
            return bool(_k32.SetEvent(handle))
        finally:
            _k32.CloseHandle(handle)

    def start_listening(self, callback):
        """Calls callback() (on a background thread - hop to your UI thread
        yourself) each time another copy asks this one to come forward."""
        if not self._event or self._thread is not None:
            return

        def run():
            while not self._stop.is_set():
                if _k32.WaitForSingleObject(self._event, 400) == WAIT_OBJECT_0:
                    try:
                        callback()
                    except Exception:
                        pass

        self._thread = threading.Thread(target=run, daemon=True)
        self._thread.start()

    def release(self):
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=1)
        for h in (self._event, self._mutex):
            if h:
                _k32.CloseHandle(h)
        self._event = self._mutex = None
