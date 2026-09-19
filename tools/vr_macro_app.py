"""Oh Fudge VR Macro App.

A small borderless window that shows the main app's mute macros as big
buttons - the same buttons as http://127.0.0.1:8710/macros, but as its own
window instead of a whole browser, so it is easy to pin in VR with a desktop
overlay tool such as XSOverlay, OVR Toolkit or Desktop+.

It talks to the main app over its existing local macro API (the same one the
button page uses), so the main app must be running. Nothing about the
microphones is duplicated here - which macros exist, what they do, and whether
each mic is live or muted all come from the main app.

Two modes:
  User mode (default)  - locked. Only the buttons, nothing else to click by
                         accident. Right-click for a small menu.
  Edit mode            - drag buttons to move them, drag a button's corner to
                         resize it, double-click (or right-click) one to
                         change its colors, size, position or hide it. Drag the
                         empty background to move the window and its corner
                         grip to resize it. Click "Done" to lock it again.

The layout is saved next to the program in Data/vr_macro_app.json.

Usage:
    python tools/vr_macro_app.py [--data-dir PATH] [--port N] [--edit]
"""
import argparse
import ctypes
import hashlib
import http.client
import json
import os
import queue
import re
import sys
import threading
import time
import tkinter as tk
from tkinter import colorchooser, messagebox, ttk
from tkinter import font as tkfont
from ctypes import wintypes
from urllib.parse import quote

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from app import paths as paths_mod
from app.single_instance import SingleInstance

VR_MACRO_APP_VERSION = "1.0.0"  # its own version line (release tags are macros-vX.Y.Z), independent of the main app's
APP_TITLE = "Oh Fudge, My Battery Chat!"
WINDOW_TITLE = "Oh Fudge VR Macro App"

DEFAULT_COLORS = {"live": "#1f7a4d", "muted": "#b3362f", "offline": "#454b57", "text": "#ffffff"}
DEFAULT_BACKGROUND = "#15171c"
POLL_SEC = 0.5
TILE_W, TILE_H, GAP, MARGIN = 190, 100, 10, 10  # at 100% display scaling; scaled up on high-DPI screens
MIN_TILE_W, MIN_TILE_H = 60, 40
MIN_WIN_W, MIN_WIN_H = 260, 90
SNAP = 10

# -- Win32 window flags ------------------------------------------------------
GWL_EXSTYLE = -20
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_APPWINDOW = 0x00040000
WS_EX_NOACTIVATE = 0x08000000
GA_ROOT = 2
SWP_NOSIZE, SWP_NOMOVE, SWP_NOZORDER, SWP_NOACTIVATE, SWP_FRAMECHANGED = 0x1, 0x2, 0x4, 0x10, 0x20
SW_HIDE, SW_SHOWNA = 0, 8

_u32 = ctypes.WinDLL("user32", use_last_error=True)
_u32.GetAncestor.argtypes = [wintypes.HWND, wintypes.UINT]
_u32.GetAncestor.restype = wintypes.HWND
_u32.GetWindowLongPtrW.argtypes = [wintypes.HWND, ctypes.c_int]
_u32.GetWindowLongPtrW.restype = ctypes.c_ssize_t
_u32.SetWindowLongPtrW.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_ssize_t]
_u32.SetWindowLongPtrW.restype = ctypes.c_ssize_t
_u32.SetWindowPos.argtypes = [wintypes.HWND, wintypes.HWND, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, wintypes.UINT]
_u32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
_u32.GetSystemMetrics.argtypes = [ctypes.c_int]
_u32.SystemParametersInfoW.argtypes = [wintypes.UINT, wintypes.UINT, ctypes.c_void_p, wintypes.UINT]


def enable_dpi_awareness():
    """Without this Windows stretches the window as a blurry bitmap on
    scaled displays - not nice for something that gets pinned in VR."""
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass


def virtual_screen():
    return (_u32.GetSystemMetrics(76), _u32.GetSystemMetrics(77), _u32.GetSystemMetrics(78), _u32.GetSystemMetrics(79))


def primary_work_area():
    """(left, top, right, bottom) of the main monitor minus the taskbar."""
    r = wintypes.RECT()
    if _u32.SystemParametersInfoW(0x0030, 0, ctypes.byref(r), 0):  # SPI_GETWORKAREA
        return r.left, r.top, r.right, r.bottom
    return 0, 0, _u32.GetSystemMetrics(0), _u32.GetSystemMetrics(1)


def shade(hex_color, factor):
    """Multiplies each channel - factor < 1 darkens, > 1 lightens."""
    try:
        r, g, b = (int(hex_color[i:i + 2], 16) for i in (1, 3, 5))
    except (ValueError, IndexError):
        return hex_color
    return "#%02x%02x%02x" % tuple(max(0, min(255, int(c * factor))) for c in (r, g, b))


def clamp(v, lo, hi):
    return max(lo, min(hi, v))


# -- Talking to the main app ------------------------------------------------
class Backend:
    """Polls the main app's macro state on a background thread and sends
    presses. Never touches Tk - the UI reads .snapshot() and drains .events."""

    TOKEN_RE = re.compile(r'const TOKEN = ("(?:[^"\\]|\\.)*");')

    def __init__(self, data_dir, port_override=None):
        self.data_dir = data_dir
        self.port_override = port_override
        self.events = queue.Queue()  # ("toast", text)
        self.wake = threading.Event()
        self._stop = threading.Event()
        self._lock = threading.Lock()
        self._state = {"ok": False, "macros": [], "error": "starting"}
        self._token = None
        self._port = port_override or 8710
        self._port_read_at = 0.0
        self._busy = set()

    def start(self):
        threading.Thread(target=self._poll_loop, daemon=True).start()

    def stop(self):
        self._stop.set()
        self.wake.set()

    def snapshot(self):
        with self._lock:
            return dict(self._state)

    def port(self):
        if self.port_override:
            return self.port_override
        if time.time() - self._port_read_at > 3:
            self._port_read_at = time.time()
            try:
                with open(os.path.join(self.data_dir, "config.json"), "r", encoding="utf-8") as f:
                    port = int(json.load(f).get("port", 8710))
                if port != self._port:
                    self._port = port
                    self._token = None
            except (OSError, ValueError, TypeError):
                pass
        return self._port

    def _request(self, method, path, headers=None):
        conn = http.client.HTTPConnection("127.0.0.1", self.port(), timeout=2.5)
        try:
            conn.request(method, path, headers=headers or {})
            resp = conn.getresponse()
            return resp.status, resp.read()
        finally:
            conn.close()

    def _poll_loop(self):
        while not self._stop.is_set():
            try:
                status, body = self._request("GET", "/api/macros/state")
                if status != 200:
                    raise OSError(f"app answered {status}")
                state = {"ok": True, "macros": json.loads(body).get("macros", []), "error": None}
            except (OSError, ValueError, http.client.HTTPException) as e:
                state = {"ok": False, "macros": [], "error": str(e)}
            with self._lock:
                self._state = state
            self.wake.wait(POLL_SEC)
            self.wake.clear()

    def _get_token(self, force=False):
        if self._token and not force:
            return self._token
        status, body = self._request("GET", "/macros")
        if status != 200:
            return None
        m = self.TOKEN_RE.search(body.decode("utf-8", "replace"))
        self._token = json.loads(m.group(1)) if m else None
        return self._token

    def press(self, macro_id):
        if macro_id in self._busy:
            return
        self._busy.add(macro_id)
        threading.Thread(target=self._press_worker, args=(macro_id,), daemon=True).start()

    def _press_worker(self, macro_id):
        try:
            status, body = None, b""
            for attempt in (0, 1):
                token = self._get_token(force=(attempt == 1))
                if not token:
                    self.events.put(("toast", "Couldn't get the macro key from the app"))
                    return
                status, body = self._request("POST", "/api/macro/" + quote(macro_id, safe=""), {"X-Macro-Token": token})
                if status != 403:
                    break  # a 403 on the first try means the key changed - fetch it again once
            if status != 200:
                why = ""
                try:
                    why = json.loads(body).get("error", "")
                except (ValueError, AttributeError):
                    pass
                self.events.put(("toast", (why or f"The app refused that ({status})").capitalize()))
        except (OSError, ValueError, http.client.HTTPException):
            self.events.put(("toast", "Can't reach the app"))
        finally:
            self._busy.discard(macro_id)
            self.wake.set()  # show the new state right away


# -- Saved layout ------------------------------------------------------------
class Layout:
    def __init__(self, path):
        self.path = path
        self.data = {}
        self.load()

    def load(self):
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, dict):
                data = {}
        except (OSError, ValueError):
            data = {}
        data.setdefault("window", {})
        data.setdefault("buttons", {})
        data.setdefault("background", DEFAULT_BACKGROUND)
        data.setdefault("snap", True)
        data.setdefault("opacity", 1.0)
        data.setdefault("topmost", True)
        data.setdefault("taskbar", True)
        self.data = data

    def save(self):
        tmp = self.path + ".tmp"
        try:
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(self.data, f, indent=2)
            os.replace(tmp, self.path)
        except OSError:
            pass

    def button(self, macro_id):
        b = self.data["buttons"].get(macro_id)
        return b if isinstance(b, dict) and all(k in b for k in ("x", "y", "w", "h")) else None

    def set_button(self, macro_id, b):
        self.data["buttons"][macro_id] = b


# -- The window --------------------------------------------------------------
class MacroApp(tk.Tk):
    def __init__(self, data_dir, layout, backend, start_in_edit=False):
        super().__init__()
        self.layout = layout
        self.backend = backend
        self.title(WINDOW_TITLE)
        self.overrideredirect(True)
        self.withdraw()  # stay hidden until the window flags are in place
        self.s = max(1.0, self.winfo_fpixels("1i") / 96.0)
        self.editing = False
        self.macros = []  # last state rows from the app
        self.app_ok = False
        self._last_drawn = None
        self.selected = None
        self.drag = None
        self.pressed = None
        self.toast_text, self.toast_until = "", 0.0
        self.dialog = None
        self._fonts = {}
        self._save_job = None
        self.strip = None
        self._menu_vars = {}

        w = self.layout.data["window"]
        self.content_w = int(w.get("w") or (2 * self._sc(TILE_W) + self._sc(GAP) + 2 * self._sc(MARGIN)))
        self.content_h = int(w.get("h") or 0)
        self._needs_fit = not self.content_h  # first run: size the window to its buttons once they're known
        self.win_x, self.win_y = w.get("x"), w.get("y")

        self.canvas = tk.Canvas(self, highlightthickness=0, bd=0, bg=self.layout.data["background"])
        self.canvas.pack(fill="both", expand=True)
        self.canvas.bind("<ButtonPress-1>", self._on_down)
        self.canvas.bind("<B1-Motion>", self._on_motion)
        self.canvas.bind("<ButtonRelease-1>", self._on_up)
        self.canvas.bind("<Double-Button-1>", self._on_double)
        self.canvas.bind("<ButtonPress-3>", self._on_right)

        self._build_strip()
        self.attributes("-alpha", 0.0)  # invisible while the window flags are put in place below
        self._apply_geometry()
        self.deiconify()
        self.update()  # Tk only creates the real window on first show, and would reset any flags set before that
        self._apply_flags()
        self.attributes("-alpha", clamp(float(self.layout.data["opacity"]), 0.3, 1.0))
        if start_in_edit:
            self.set_editing(True)
        self.after(100, self._tick)
        self.protocol("WM_DELETE_WINDOW", self.quit_app)

    # -- helpers --------------------------------------------------------
    def _sc(self, v):
        return int(round(v * self.s))

    def _font(self, px, weight):
        key = (px, weight)
        if key not in self._fonts:
            self._fonts[key] = tkfont.Font(family="Segoe UI", size=-px, weight=weight)
        return self._fonts[key]

    def _fit(self, text, max_px, min_px, max_w, weight):
        """Largest font (up to max_px) that fits max_w, and the text
        shortened with an ellipsis if even the smallest doesn't."""
        px = max(min_px, int(max_px))
        while True:
            f = self._font(px, weight)
            if f.measure(text) <= max_w or px <= min_px:
                break
            px -= 1
        if f.measure(text) > max_w:
            while len(text) > 1 and f.measure(text + "…") > max_w:
                text = text[:-1]
            text += "…"
        return f, text

    # -- window flags / geometry ---------------------------------------------
    def _hwnd(self):
        return _u32.GetAncestor(self.winfo_id(), GA_ROOT) or self.winfo_id()

    def _apply_flags(self):
        """Never takes focus from the game (WS_EX_NOACTIVATE) and - by
        default - still appears in window lists so a VR desktop overlay
        can find it (a "tool window" is hidden from most of those)."""
        self.update_idletasks()
        hwnd = self._hwnd()
        ex = _u32.GetWindowLongPtrW(hwnd, GWL_EXSTYLE) | WS_EX_NOACTIVATE
        if self.layout.data["taskbar"]:
            ex = (ex | WS_EX_APPWINDOW) & ~WS_EX_TOOLWINDOW
        else:
            ex = (ex | WS_EX_TOOLWINDOW) & ~WS_EX_APPWINDOW
        visible = bool(self.winfo_viewable())
        if visible:
            _u32.ShowWindow(hwnd, SW_HIDE)  # style changes to tool/app window only take effect across a hide/show
        _u32.SetWindowLongPtrW(hwnd, GWL_EXSTYLE, ex)
        _u32.SetWindowPos(hwnd, None, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE | SWP_NOZORDER | SWP_NOACTIVATE | SWP_FRAMECHANGED)
        if visible:
            _u32.ShowWindow(hwnd, SW_SHOWNA)
        self.attributes("-topmost", bool(self.layout.data["topmost"]))

    def _strip_h(self):
        if not self.editing:
            return 0
        self.strip.update_idletasks()
        return max(self._sc(36), self.strip.winfo_reqheight())

    def _apply_geometry(self):
        w = max(self._sc(MIN_WIN_W), self.content_w)
        h = max(self._sc(MIN_WIN_H), self.content_h or self._sc(MIN_WIN_H))
        self.content_w, self.content_h = w, h
        vx, vy, vw, vh = virtual_screen()
        x, y = self.win_x, self.win_y
        if x is None or y is None:
            left, top, right, _ = primary_work_area()  # first run: top-right of the main monitor
            x, y = right - w - self._sc(40), top + self._sc(80)
        x = clamp(int(x), vx - w + self._sc(60), vx + vw - self._sc(60))
        y = clamp(int(y), vy, vy + vh - self._sc(40))
        self.win_x, self.win_y = x, y
        self.geometry(f"{w}x{h + self._strip_h()}+{x}+{y}")
        self.canvas.configure(width=w, height=h)

    def bring_forward(self):
        self.deiconify()
        self.lift()
        self.attributes("-topmost", True)  # (re-)raise above other always-on-top windows
        self.attributes("-topmost", bool(self.layout.data["topmost"]))

    # -- layout of buttons ------------------------------------------------
    def _btn(self, mid):
        b = self.layout.button(mid)
        if b is None:
            b = self._place_new(mid)
        for k, v in DEFAULT_COLORS.items():
            b.setdefault(k, v)
        b.setdefault("hidden", False)
        return b

    def _place_new(self, mid):
        tw, th, gap, mg = self._sc(TILE_W), self._sc(TILE_H), self._sc(GAP), self._sc(MARGIN)
        cols = max(1, (self.content_w - mg + gap) // (tw + gap))
        placed = [b for b in self.layout.data["buttons"].values() if isinstance(b, dict) and "x" in b]
        i = 0
        while True:
            x, y = mg + (i % cols) * (tw + gap), mg + (i // cols) * (th + gap)
            if not any(x < p["x"] + p["w"] and p["x"] < x + tw and y < p["y"] + p["h"] and p["y"] < y + th for p in placed):
                break
            i += 1
        b = {"x": x, "y": y, "w": tw, "h": th}
        b.update(DEFAULT_COLORS)
        b["hidden"] = False
        self.layout.set_button(mid, b)
        return b

    def _fit_window_to_buttons(self, grow_only=False):
        """Sizes the window to its buttons. grow_only keeps whatever extra
        room the user already gave it and just makes sure nothing is cut off."""
        mg = self._sc(MARGIN)
        bs = [self._btn(m["id"]) for m in self.macros if not self._btn(m["id"])["hidden"] or self.editing]
        if not bs:
            return
        need_h = max(b["y"] + b["h"] for b in bs) + mg
        need_w = max(b["x"] + b["w"] for b in bs) + mg
        self.content_h = max(self.content_h, need_h) if grow_only else need_h
        self.content_w = max(self.content_w, need_w)
        self._apply_geometry()
        self.redraw()

    def auto_arrange(self):
        tw, th, gap, mg = self._sc(TILE_W), self._sc(TILE_H), self._sc(GAP), self._sc(MARGIN)
        cols = max(1, (self.content_w - mg + gap) // (tw + gap))
        for i, m in enumerate(self.macros):
            b = self._btn(m["id"])
            b.update(x=mg + (i % cols) * (tw + gap), y=mg + (i // cols) * (th + gap), w=tw, h=th)
        rows = (len(self.macros) + cols - 1) // cols
        self.content_h = mg * 2 + max(1, rows) * (th + gap) - gap
        self._apply_geometry()
        self.redraw()
        self._changed()

    def reset_all(self):
        if not messagebox.askyesno(WINDOW_TITLE, "Put every button back to its default size, position and colors?", parent=self.dialog or self):
            return
        self.layout.data["buttons"].clear()
        self.layout.data["background"] = DEFAULT_BACKGROUND
        self.canvas.configure(bg=DEFAULT_BACKGROUND)
        for m in self.macros:
            self._btn(m["id"])
        self.auto_arrange()

    # -- state / redraw -------------------------------------------------------
    def _tick(self):
        try:
            while True:
                kind, text = self.backend.events.get_nowait()
                if kind == "toast":
                    self.toast(text)
        except queue.Empty:
            pass
        snap = self.backend.snapshot()
        self.macros, self.app_ok = snap["macros"], snap["ok"]
        if self.macros:
            known = len(self.layout.data["buttons"])
            for m in self.macros:
                self._btn(m["id"])  # a macro added in the main app gets placed in the next free slot
            if self._needs_fit:
                self._needs_fit = False
                self._fit_window_to_buttons()
                self._changed()
            elif len(self.layout.data["buttons"]) != known:
                self._fit_window_to_buttons(grow_only=True)  # ...and the window grows so it isn't cut off
                self._changed()
        stamp = (json.dumps(self.macros, sort_keys=True), self.app_ok, self.toast_text if time.time() < self.toast_until else "")
        if stamp != self._last_drawn:
            self.redraw()
        self.after(150, self._tick)

    def toast(self, text):
        self.toast_text, self.toast_until = text, time.time() + 3.5
        self.redraw()
        self.after(3600, self.redraw)

    def _state_of(self, m):
        if not self.app_ok or not m.get("connected"):
            return "offline", "OFFLINE"
        return ("muted", "MUTED") if m.get("muted") else ("live", "LIVE")

    def _rounded(self, x1, y1, x2, y2, r, **kw):
        r = max(1, min(r, (x2 - x1) // 2, (y2 - y1) // 2))
        pts = [x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r, x2, y2 - r, x2, y2, x2 - r, y2,
               x1 + r, y2, x1, y2, x1, y2 - r, x1, y1 + r, x1, y1]
        return self.canvas.create_polygon(pts, smooth=True, **kw)

    def redraw(self):
        c = self.canvas
        c.delete("all")
        self._last_drawn = (json.dumps(self.macros, sort_keys=True), self.app_ok,
                            self.toast_text if time.time() < self.toast_until else "")
        cw, ch = self.content_w, self.content_h
        if not self.app_ok:
            c.create_text(cw // 2, ch // 2, text=f"Waiting for {APP_TITLE}\nto be running…", fill="#8f99ad",
                          font=self._font(self._sc(14), "normal"), justify="center", width=cw - self._sc(30))
        elif not self.macros:
            c.create_text(cw // 2, ch // 2, text="No macros yet.\nAdd some with the Macros button in the app.",
                          fill="#8f99ad", font=self._font(self._sc(14), "normal"), justify="center", width=cw - self._sc(30))
        pad = self._sc(10)
        for m in self.macros:
            b = self._btn(m["id"])
            if b["hidden"] and not self.editing:
                continue
            x, y, w, h = b["x"], b["y"], b["w"], b["h"]
            cls, word = self._state_of(m)
            fill = b[cls]
            if b["hidden"]:
                self._rounded(x, y, x + w, y + h, self._sc(14), fill="", outline="#5a6172", dash=(4, 4), width=1)
                c.create_text(x + w // 2, y + h // 2, text=f"{m.get('label', '')} (hidden)", fill="#8f99ad",
                              font=self._font(self._sc(11), "normal"), width=max(20, w - pad))
                continue
            if self.pressed == m["id"]:
                fill = shade(fill, 0.75)
            outline = "#ffffff" if (self.editing and self.selected == m["id"]) else ""
            self._rounded(x, y, x + w, y + h, self._sc(14), fill=fill, outline=outline, width=2)
            inner = max(20, w - 2 * pad)
            f, name = self._fit(m.get("label", ""), clamp(h * 0.17, 9, self._sc(26)), 8, inner, "bold")
            c.create_text(x + pad, y + pad, text=name, anchor="nw", fill=b["text"], font=f)
            f, word_t = self._fit(word, clamp(h * 0.34, 11, self._sc(44)), 9, inner, "bold")
            c.create_text(x + pad, y + h - pad, text=word_t, anchor="sw", fill=b["text"], font=f)
            if self.editing and self.selected == m["id"]:
                hs = self._sc(14)
                c.create_rectangle(x + w - hs, y + h - hs, x + w - 2, y + h - 2, fill="#ffffff", outline="")
        if self.editing:
            g = self._sc(18)
            for i in (4, 9, 14):
                d = self._sc(i)
                c.create_line(cw - d, ch - 2, cw - 2, ch - d, fill="#8f99ad", width=2)
            c.create_rectangle(0, 0, cw - 1, ch - 1, outline="#3d6fb5", width=2)
        if time.time() < self.toast_until and self.toast_text:
            f = self._font(self._sc(13), "bold")
            tw = min(cw - self._sc(20), f.measure(self.toast_text) + self._sc(24))
            cx, cy = cw // 2, ch - self._sc(24)
            self._rounded(cx - tw // 2, cy - self._sc(15), cx + tw // 2, cy + self._sc(15), self._sc(15), fill="#5a2320", outline="")
            c.create_text(cx, cy, text=self.toast_text, fill="#ffffff", font=f, width=tw - self._sc(12))

    # -- hit testing ----------------------------------------------------------
    def _hit(self, x, y):
        """(macro id, 'body'|'handle') of the topmost button at x, y, or (None, None)."""
        for m in reversed(self.macros):
            b = self._btn(m["id"])
            if b["hidden"] and not self.editing:
                continue
            if b["x"] <= x < b["x"] + b["w"] and b["y"] <= y < b["y"] + b["h"]:
                hs = self._sc(16)
                if self.editing and x >= b["x"] + b["w"] - hs and y >= b["y"] + b["h"] - hs:
                    return m["id"], "handle"
                return m["id"], "body"
        return None, None

    def _in_grip(self, x, y):
        g = self._sc(20)
        return x >= self.content_w - g and y >= self.content_h - g

    def _snap(self, v):
        if not self.layout.data["snap"]:
            return int(v)
        g = self._sc(SNAP)
        return int(round(v / g) * g)

    # -- mouse ----------------------------------------------------------------
    def _on_down(self, e):
        if not self.editing:
            mid, _ = self._hit(e.x, e.y)
            self.pressed = mid
            if mid:
                self.redraw()
            return
        if self._in_grip(e.x, e.y):
            self.drag = {"kind": "window-size", "sx": e.x_root, "sy": e.y_root, "w": self.content_w, "h": self.content_h}
            return
        mid, part = self._hit(e.x, e.y)
        if mid:
            self.selected = mid
            b = self._btn(mid)
            self.drag = {"kind": "resize" if part == "handle" else "move", "mid": mid, "sx": e.x_root, "sy": e.y_root,
                         "x": b["x"], "y": b["y"], "w": b["w"], "h": b["h"]}
            self.redraw()
            if self.dialog is not None and self.dialog.mid != mid:
                self.open_customize(mid)
        else:
            self.selected = None
            self.drag = {"kind": "window-move", "sx": e.x_root, "sy": e.y_root, "x": self.win_x, "y": self.win_y}
            self.redraw()

    def _on_motion(self, e):
        d = self.drag
        if not self.editing or not d:
            return
        dx, dy = e.x_root - d["sx"], e.y_root - d["sy"]
        if d["kind"] == "window-move":
            self.win_x, self.win_y = d["x"] + dx, d["y"] + dy
            self.geometry(f"+{self.win_x}+{self.win_y}")
            return
        if d["kind"] == "window-size":
            self.content_w = max(self._sc(MIN_WIN_W), d["w"] + dx)
            self.content_h = max(self._sc(MIN_WIN_H), d["h"] + dy)
            self._apply_geometry()
            self.redraw()
            return
        b = self._btn(d["mid"])
        if d["kind"] == "move":
            b["x"], b["y"] = max(0, self._snap(d["x"] + dx)), max(0, self._snap(d["y"] + dy))
        else:
            b["w"] = max(self._sc(MIN_TILE_W), self._snap(d["w"] + dx))
            b["h"] = max(self._sc(MIN_TILE_H), self._snap(d["h"] + dy))
        self.redraw()
        if self.dialog is not None:
            self.dialog.sync()

    def _on_up(self, e):
        d, self.drag = self.drag, None
        if not self.editing:
            mid, self.pressed = self.pressed, None
            hit, _ = self._hit(e.x, e.y)
            self.redraw()
            if mid and hit == mid:  # released on the same button it was pressed on
                self.backend.press(mid)
            return
        if d:
            self._changed()

    def _on_double(self, e):
        if self.editing:
            mid, _ = self._hit(e.x, e.y)
            if mid:
                self.open_customize(mid)

    def _on_right(self, e):
        menu = tk.Menu(self, tearoff=0)
        mid, _ = self._hit(e.x, e.y) if self.editing else (None, None)
        if self.editing and mid:
            self.selected = mid
            self.redraw()
            b = self._btn(mid)
            menu.add_command(label="Customize…", command=lambda: self.open_customize(mid))
            menu.add_command(label="Show button" if b["hidden"] else "Hide button", command=lambda: self.toggle_hidden(mid))
            menu.add_command(label="Reset this button", command=lambda: self.reset_button(mid))
            menu.add_separator()
        if self.editing:
            menu.add_command(label="Background color…", command=self.pick_background)
            menu.add_command(label="Done editing", command=lambda: self.set_editing(False))
        else:
            menu.add_command(label=f"{WINDOW_TITLE} v{VR_MACRO_APP_VERSION}", state="disabled")
            menu.add_command(label="Edit layout", command=lambda: self.set_editing(True))
            menu.add_separator()
            self._menu_vars = {k: self._var(k) for k in ("topmost", "taskbar")}
            menu.add_checkbutton(label="Always on top", variable=self._menu_vars["topmost"], command=self._flags_changed)
            menu.add_checkbutton(label="Show in taskbar / window lists", variable=self._menu_vars["taskbar"], command=self._flags_changed)
        menu.add_separator()
        menu.add_command(label="Close", command=self.quit_app)
        try:
            menu.tk_popup(e.x_root, e.y_root)
        finally:
            menu.grab_release()

    def _var(self, key):
        v = tk.BooleanVar(value=bool(self.layout.data[key]))
        v.trace_add("write", lambda *a: self.layout.data.__setitem__(key, bool(v.get())))
        return v

    def _flags_changed(self):
        self.after(10, self._apply_flags_and_save)

    def _apply_flags_and_save(self):
        self._apply_flags()
        self._changed()

    # -- per-button actions -----------------------------------------------------
    def toggle_hidden(self, mid):
        b = self._btn(mid)
        b["hidden"] = not b["hidden"]
        self.redraw()
        self._changed()

    def reset_button(self, mid):
        old = self._btn(mid)
        self.layout.data["buttons"].pop(mid, None)
        b = self._btn(mid)  # placed again as if new... then put it back where it was, at the default size
        b["x"], b["y"] = old["x"], old["y"]
        self.redraw()
        if self.dialog is not None:
            self.dialog.sync()
        self._changed()

    def pick_background(self):
        res = colorchooser.askcolor(color=self.layout.data["background"], parent=self, title="Background color")
        if res and res[1]:
            self.layout.data["background"] = res[1]
            self.canvas.configure(bg=res[1])
            self._changed()

    def open_customize(self, mid):
        if self.dialog is not None:
            self.dialog.destroy()
        self.selected = mid
        self.dialog = CustomizeDialog(self, mid)
        self.redraw()

    def dialog_closed(self):
        self.dialog = None

    # -- edit mode ----------------------------------------------------------------
    def _build_strip(self):
        bg = "#232833"
        self.strip = tk.Frame(self, bg=bg)
        done = tk.Button(self.strip, text="Done", command=lambda: self.set_editing(False), bg="#3d6fb5", fg="white",
                         activebackground="#4f83cf", activeforeground="white", relief="flat", padx=12, bd=0)
        done.pack(side="right", padx=6, pady=4)
        tk.Label(self.strip, text="EDIT MODE", bg=bg, fg="#8fb4ff", font=("Segoe UI", 8, "bold")).pack(side="left", padx=(8, 4))
        self.snap_var = tk.BooleanVar(value=bool(self.layout.data["snap"]))
        self.snap_var.trace_add("write", lambda *a: (self.layout.data.__setitem__("snap", bool(self.snap_var.get())), self._changed()))
        tk.Checkbutton(self.strip, text="Snap", variable=self.snap_var, bg=bg, fg="#e8e8e8", selectcolor="#232833",
                       activebackground=bg, activeforeground="white", bd=0).pack(side="left")
        for text, cmd in (("Auto-arrange", self.auto_arrange), ("Reset all", self.reset_all)):
            tk.Button(self.strip, text=text, command=cmd, bg="#39404f", fg="#e8e8e8", activebackground="#4a5266",
                      activeforeground="white", relief="flat", padx=6, bd=0).pack(side="left", padx=2, pady=4)
        self.opacity_var = tk.DoubleVar(value=float(self.layout.data["opacity"]))
        tk.Scale(self.strip, from_=0.3, to=1.0, resolution=0.05, orient="horizontal", showvalue=False, length=70,
                 variable=self.opacity_var, command=self._on_opacity, bg=bg, troughcolor="#39404f", bd=0,
                 highlightthickness=0).pack(side="left", padx=(6, 0))
        tk.Label(self.strip, text="opacity", bg=bg, fg="#8f99ad", font=("Segoe UI", 8)).pack(side="left")

    def _on_opacity(self, value):
        v = clamp(float(value), 0.3, 1.0)
        self.layout.data["opacity"] = v
        self.attributes("-alpha", v)
        self._changed()

    def set_editing(self, on):
        if on == self.editing:
            return
        self.editing = on
        self.drag = None
        self.pressed = None
        if on:
            self.strip.pack(side="bottom", fill="x", before=self.canvas)
        else:
            self.strip.pack_forget()
            self.selected = None
            if self.dialog is not None:
                self.dialog.destroy()
                self.dialog = None
        self._apply_geometry()  # the strip grows the window downward, so buttons never move
        self.redraw()
        self._save_now()

    # -- saving ---------------------------------------------------------------------
    def _changed(self):
        if self._save_job is not None:
            self.after_cancel(self._save_job)
        self._save_job = self.after(300, self._save_now)

    def _save_now(self):
        self._save_job = None
        self.layout.data["window"] = {"x": self.win_x, "y": self.win_y, "w": self.content_w, "h": self.content_h}
        self.layout.save()

    def quit_app(self):
        if self._save_job is not None:
            self.after_cancel(self._save_job)
        self._save_now()
        self.backend.stop()
        self.destroy()


class CustomizeDialog(tk.Toplevel):
    """Colors, size, position and visibility of one button. Every change
    applies to the window straight away."""

    COLOR_ROWS = (("live", "Live (mic on)"), ("muted", "Muted"), ("offline", "Offline / not connected"), ("text", "Text"))

    def __init__(self, app, mid):
        super().__init__(app)
        self.app, self.mid = app, mid
        self._syncing = False
        label = next((m.get("label", "") for m in app.macros if m["id"] == mid), mid)
        self.title(f"Customize - {label}")
        self.resizable(False, False)
        self.attributes("-topmost", True)
        self.protocol("WM_DELETE_WINDOW", self.close)

        frm = ttk.Frame(self, padding=12)
        frm.pack(fill="both", expand=True)
        ttk.Label(frm, text=label, font=("Segoe UI", 11, "bold")).grid(row=0, column=0, columnspan=4, sticky="w", pady=(0, 8))

        self.vars = {k: tk.StringVar() for k in ("x", "y", "w", "h")}
        for row, (a, b, la, lb) in enumerate((("w", "h", "Width", "Height"), ("x", "y", "Position X", "Position Y")), start=1):
            for col, (key, text) in enumerate(((a, la), (b, lb))):
                ttk.Label(frm, text=text).grid(row=row, column=col * 2, sticky="w", padx=(0 if col == 0 else 12, 6), pady=2)
                sp = ttk.Spinbox(frm, from_=0, to=6000, increment=self.app._sc(SNAP), width=6, textvariable=self.vars[key],
                                 command=self.apply_size_pos)
                sp.grid(row=row, column=col * 2 + 1, sticky="w", pady=2)
                sp.bind("<KeyRelease>", lambda e: self.apply_size_pos())
                sp.bind("<FocusOut>", lambda e: self.sync())

        self.swatches = {}
        for i, (key, text) in enumerate(self.COLOR_ROWS, start=3):
            ttk.Label(frm, text=text).grid(row=i, column=0, columnspan=2, sticky="w", pady=(8 if i == 3 else 2, 2))
            sw = tk.Button(frm, width=10, relief="solid", bd=1, command=lambda k=key: self.pick(k))
            sw.grid(row=i, column=2, columnspan=2, sticky="w", padx=(12, 0), pady=(8 if i == 3 else 2, 2))
            self.swatches[key] = sw

        self.hidden_var = tk.BooleanVar()
        ttk.Checkbutton(frm, text="Hide this button", variable=self.hidden_var, command=self.apply_hidden).grid(
            row=8, column=0, columnspan=4, sticky="w", pady=(10, 0))
        btns = ttk.Frame(frm)
        btns.grid(row=9, column=0, columnspan=4, sticky="e", pady=(12, 0))
        ttk.Button(btns, text="Reset this button", command=lambda: self.app.reset_button(self.mid)).pack(side="left", padx=(0, 8))
        ttk.Button(btns, text="Close", command=self.close).pack(side="left")

        self.sync()
        self.update_idletasks()
        vx, vy, vw, vh = virtual_screen()
        dw, dh = self.winfo_reqwidth(), self.winfo_reqheight()
        x = app.win_x + app.content_w + 12
        if x + dw > vx + vw:
            x = app.win_x - dw - 12
        self.geometry(f"+{clamp(x, vx, vx + vw - dw)}+{clamp(app.win_y, vy, vy + vh - dh)}")

    def sync(self):
        """Refresh the fields from the button (it may have just been dragged)."""
        if self._syncing:
            return
        self._syncing = True
        try:
            b = self.app._btn(self.mid)
            for k in ("x", "y", "w", "h"):
                self.vars[k].set(str(b[k]))
            for k, sw in self.swatches.items():
                light = sum(int(b[k][i:i + 2], 16) for i in (1, 3, 5)) > 382  # readable label on any swatch color
                sw.configure(bg=b[k], activebackground=b[k], text=b[k], fg="#000000" if light else "#ffffff")
            self.hidden_var.set(bool(b["hidden"]))
        finally:
            self._syncing = False

    def apply_size_pos(self):
        if self._syncing:
            return
        b = self.app._btn(self.mid)
        try:
            vals = {k: int(self.vars[k].get()) for k in ("x", "y", "w", "h")}
        except ValueError:
            return  # half-typed number - wait for the next keystroke
        b["x"], b["y"] = max(0, vals["x"]), max(0, vals["y"])
        b["w"], b["h"] = max(self.app._sc(MIN_TILE_W), vals["w"]), max(self.app._sc(MIN_TILE_H), vals["h"])
        self.app.redraw()
        self.app._changed()

    def pick(self, key):
        b = self.app._btn(self.mid)
        res = colorchooser.askcolor(color=b[key], parent=self, title="Choose a color")
        if res and res[1]:
            b[key] = res[1]
            self.sync()
            self.app.redraw()
            self.app._changed()

    def apply_hidden(self):
        if self._syncing:
            return
        self.app._btn(self.mid)["hidden"] = bool(self.hidden_var.get())
        self.app.redraw()
        self.app._changed()

    def close(self):
        self.app.dialog_closed()
        self.destroy()


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--data-dir", default=None,
                        help="Data folder of the main app (default: a Data folder next to this program - "
                             "keep it in the same folder as OhFudgeMyBatteryChat.exe to share one automatically)")
    parser.add_argument("--port", type=int, default=None, help="Main app's port (default: read from its config, else 8710)")
    parser.add_argument("--edit", action="store_true", help="Start in edit mode")
    args = parser.parse_args()

    if args.data_dir:
        os.makedirs(args.data_dir, exist_ok=True)
        paths_mod._app_data_dir_cache = args.data_dir
    data_dir = paths_mod.app_data_dir()

    # One copy per Data folder - a second launch just raises the first.
    instance = SingleInstance("OhFudgeVRMacroApp." + hashlib.md5(os.path.abspath(data_dir).lower().encode()).hexdigest()[:8])
    if not instance.acquire():
        if not instance.signalled:
            ctypes.windll.user32.MessageBoxW(None, f"{WINDOW_TITLE} is already running.", WINDOW_TITLE, 0x40)
        return

    enable_dpi_awareness()
    layout = Layout(os.path.join(data_dir, "vr_macro_app.json"))
    backend = Backend(data_dir, args.port)
    backend.start()
    app = MacroApp(data_dir, layout, backend, start_in_edit=args.edit)
    instance.start_listening(lambda: app.after(0, app.bring_forward))
    app.mainloop()
    backend.stop()
    instance.release()


if __name__ == "__main__":
    main()
