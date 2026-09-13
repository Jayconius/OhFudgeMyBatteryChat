"""Optional dark-mode support: detects the Windows "dark mode" setting once
at startup and, if it's on, re-colors the whole app.

ttk widgets all read from one shared style database per process, so
apply_theme() is called ONCE (in MainWindow.__init__, or the Simulator's
own entry point) and every ttk widget in every window - including dialogs
created later - picks up the new colors automatically. Plain tk widgets
(Canvas, classic Label/Button) and each window's own title bar aren't
covered by ttk.Style, so those need a small explicit per-window call - see
apply_window_theme().

Detection only happens at launch - the app does not watch for the OS
setting changing while it's already running.
"""
import ctypes
import sys
import winreg

DARK_BG = "#1e1e1e"
DARK_PANEL_BG = "#2b2b2b"
DARK_FIELD_BG = "#333333"
DARK_FG = "#e8e8e8"
DARK_BORDER = "#4a4a4a"
DARK_SELECT_BG = "#3d6fb5"
DARK_SELECT_FG = "#ffffff"

_DWMWA_USE_IMMERSIVE_DARK_MODE = 20
_DWMWA_USE_IMMERSIVE_DARK_MODE_OLD = 19  # Windows 10 builds before 20H1


def detect_windows_dark_mode() -> bool:
    """Reads HKCU...Personalize\\AppsUseLightTheme - 0 means dark mode is
    on. Any failure (key missing, non-Windows, permissions) is treated as
    "not dark" so this can never block startup."""
    try:
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize",
        )
        value, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
        return value == 0
    except OSError:
        return False


def apply_theme(dark: bool):
    """Configures the shared ttk Style database for the whole process. Call
    once, before building any UI. Light mode leaves the native theme
    untouched (today's look, unchanged)."""
    from tkinter import ttk
    style = ttk.Style()
    if not dark:
        return

    style.theme_use("clam")
    style.configure(
        ".", background=DARK_PANEL_BG, foreground=DARK_FG,
        fieldbackground=DARK_FIELD_BG, bordercolor=DARK_BORDER,
        lightcolor=DARK_PANEL_BG, darkcolor=DARK_PANEL_BG,
        troughcolor=DARK_FIELD_BG, selectbackground=DARK_SELECT_BG, selectforeground=DARK_SELECT_FG,
    )
    style.configure("TFrame", background=DARK_PANEL_BG)
    style.configure("TLabel", background=DARK_PANEL_BG, foreground=DARK_FG)
    style.configure("TLabelframe", background=DARK_PANEL_BG, foreground=DARK_FG, bordercolor=DARK_BORDER)
    style.configure("TLabelframe.Label", background=DARK_PANEL_BG, foreground=DARK_FG)
    style.configure("TButton", background=DARK_FIELD_BG, foreground=DARK_FG, bordercolor=DARK_BORDER)
    style.map("TButton", background=[("active", DARK_BORDER)], foreground=[("disabled", "#777777")])
    style.configure("TEntry", fieldbackground=DARK_FIELD_BG, foreground=DARK_FG, insertcolor=DARK_FG, bordercolor=DARK_BORDER)
    style.configure("TSpinbox", fieldbackground=DARK_FIELD_BG, foreground=DARK_FG, background=DARK_FIELD_BG, arrowcolor=DARK_FG, bordercolor=DARK_BORDER)
    style.configure("TCombobox", fieldbackground=DARK_FIELD_BG, foreground=DARK_FG, background=DARK_FIELD_BG, arrowcolor=DARK_FG, bordercolor=DARK_BORDER)
    style.map(
        "TCombobox",
        fieldbackground=[("readonly", DARK_FIELD_BG), ("disabled", DARK_PANEL_BG)],
        foreground=[("readonly", DARK_FG), ("disabled", "#777777")],
    )
    style.configure("TCheckbutton", background=DARK_PANEL_BG, foreground=DARK_FG)
    style.map("TCheckbutton", background=[("active", DARK_PANEL_BG)])
    style.configure("TRadiobutton", background=DARK_PANEL_BG, foreground=DARK_FG)
    style.map("TRadiobutton", background=[("active", DARK_PANEL_BG)])
    style.configure("TMenubutton", background=DARK_FIELD_BG, foreground=DARK_FG, bordercolor=DARK_BORDER)
    style.configure("TPanedwindow", background=DARK_PANEL_BG)
    style.configure("TScrollbar", background=DARK_FIELD_BG, troughcolor=DARK_PANEL_BG, bordercolor=DARK_BORDER, arrowcolor=DARK_FG)
    style.map("TScrollbar", background=[("active", DARK_BORDER)])
    style.configure("TScale", background=DARK_PANEL_BG, troughcolor=DARK_FIELD_BG)
    style.configure("Treeview", background=DARK_FIELD_BG, fieldbackground=DARK_FIELD_BG, foreground=DARK_FG, bordercolor=DARK_BORDER)
    style.configure("Treeview.Heading", background=DARK_BORDER, foreground=DARK_FG, bordercolor=DARK_BORDER)
    style.map("Treeview.Heading", background=[("active", DARK_BORDER)])
    style.map("Treeview", background=[("selected", DARK_SELECT_BG)], foreground=[("selected", DARK_SELECT_FG)])

    try:
        import tkinter as tk
        root = tk._default_root
        if root is not None:
            # Classic (non-ttk) widget defaults - only affects widgets
            # created AFTER this call, so callers still need to explicitly
            # configure() any classic widget that already exists.
            root.option_add("*Background", DARK_PANEL_BG)
            root.option_add("*Foreground", DARK_FG)
            root.option_add("*Entry.background", DARK_FIELD_BG)
            root.option_add("*Listbox.background", DARK_FIELD_BG)
            root.option_add("*Listbox.foreground", DARK_FG)
    except Exception:
        pass


def apply_window_theme(window, dark: bool):
    """Per-window dark-mode touch-ups that ttk.Style doesn't cover: the
    window's own background (a plain tk attribute, not a ttk style) and its
    OS title bar (via DWM - Windows only, silently no-ops elsewhere or on
    older Windows builds without this attribute). Call once per Toplevel
    (including the main window) after it's been created."""
    if dark:
        try:
            window.configure(bg=DARK_PANEL_BG)
        except Exception:
            pass
    _apply_dark_titlebar(window, dark)


def _apply_dark_titlebar(window, dark: bool):
    """Sets the DWM dark-titlebar attribute only - does NOT force a repaint
    itself. On at least some Windows 10 builds, DwmSetWindowAttribute
    reports success (HRESULT 0) but the title bar's actual on-screen color
    doesn't change until the window goes through a real hide/show cycle -
    a SetWindowPos(SWP_FRAMECHANGED) nudge alone was not enough in testing.
    Callers are expected to keep the window withdrawn (see with_hidden_
    window()) until after this runs, then deiconify() once - that first
    reveal IS the hide/show cycle DWM needs, with no visible flicker."""
    if sys.platform != "win32":
        return
    try:
        window.update_idletasks()
        # winfo_id() returns the HWND of Tk's inner *content* window, not
        # the decorated top-level frame that actually owns the title bar -
        # DwmSetWindowAttribute needs that outer frame's HWND (its Win32
        # parent), or it silently no-ops on the wrong window.
        hwnd = ctypes.windll.user32.GetParent(window.winfo_id())
        value = ctypes.c_int(1 if dark else 0)
        for attr in (_DWMWA_USE_IMMERSIVE_DARK_MODE, _DWMWA_USE_IMMERSIVE_DARK_MODE_OLD):
            result = ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, attr, ctypes.byref(value), ctypes.sizeof(value))
            if result == 0:
                break
    except Exception:
        pass
