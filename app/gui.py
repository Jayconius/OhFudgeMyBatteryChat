"""Tkinter configurator GUI.

Lets you see currently-connected SteamVR devices, and add two kinds of
overlay objects:

- a Device item: shows a device's live battery (image swap or pop-in/out)
- an Overlay Effect: a standalone alert (picture + optional styled caption +
  sound) that pops in/out on a trigger (battery low/normal, connect/
  disconnect), targeting a specific device, any device, or all devices

Both support drag-to-position with alignment snapping against everything
else already placed, and a live "Test Animation" preview on the real overlay
page while their editor dialog is open. The UI itself can be switched between
several languages from the top bar.
"""
import os
import threading
import tkinter as tk
import webbrowser
from tkinter import colorchooser, filedialog, messagebox, ttk
from types import SimpleNamespace

from . import audio_monitor as audio_mod
from . import bundled_icons
from . import config as config_mod
from . import default_assets
from . import hotkeys
from . import i18n
from . import paths
from . import piqad
from . import theme
from . import twitch_auth
from . import update_check
from .audio_monitor import AudioMonitor
from .hotkeys import HotkeyManager
from .server import ServerController
from .twitch_monitor import TwitchMonitor
from .vr_monitor import VRMonitor

APP_TITLE = "Oh Fudge, My Battery Chat!"  # the pun stays the same in every language
APP_VERSION = "1.3.0"
APP_AUTHOR = "Jayconius"
APP_GITHUB_URL = "https://github.com/Jayconius/OhFudgeMyBatteryChat"
APP_CONTACT_URL = "https://jayconius.com"

DEFAULT_FONT_FAMILY = "Segoe UI"

# Widget classes whose text is *always* pure translated chrome in this app
# (no serial numbers, free-typed text, or other Latin-only data ever ends up
# in them) - safe to blanket-switch to the pIqaD font. Comboboxes, Entries,
# and Treeview body rows are deliberately excluded: they mix in real device
# data that the (Latin-glyph-free) pIqaD font would render as blank boxes.
_CHROME_STYLES = (
    "TLabel", "TButton", "TCheckbutton", "TRadiobutton", "TMenubutton", "TLabelframe.Label",
    "Treeview.Heading",
)


def _chrome_font_family() -> str:
    if i18n.get_language() == "tlh" and piqad.ensure_font_loaded():
        return piqad.FONT_FAMILY
    return DEFAULT_FONT_FAMILY


def _default_font(size=9, bold=False):
    return (DEFAULT_FONT_FAMILY, size, "bold") if bold else (DEFAULT_FONT_FAMILY, size)


def _chrome_font(size=10, bold=False):
    family = _chrome_font_family()
    return (family, size, "bold") if bold else (family, size)


def apply_language_style():
    """Re-points the shared ttk Style (and re-usable font tuples) at the
    pIqaD font when Klingon is active, or back to the default otherwise.
    Call this once whenever the language changes - it's global to the Tk
    interpreter, so it takes effect for the main window and any dialog."""
    family = _chrome_font_family()
    style = ttk.Style()
    for style_name in _CHROME_STYLES:
        try:
            style.configure(style_name, font=(family, 10))
        except tk.TclError:
            pass

CANVAS_W, CANVAS_H = 480, 270  # preview scale of a 1920x1080 OBS canvas
IMAGE_FILETYPES = [("Images/GIF/WebM", "*.png *.jpg *.jpeg *.bmp *.gif *.webm"), ("All files", "*.*")]
SOUND_FILETYPES = [("Audio", "*.wav *.mp3 *.ogg"), ("All files", "*.*")]
FONT_CHOICES = ["Segoe UI", "Arial", "Impact", "Comic Sans MS", "Verdana", "Georgia", "Courier New", "Trebuchet MS"]


def _battery_display(dev):
    """Base stations are mains/USB-powered, and the SteamVR Service pseudo-
    device isn't hardware at all - neither has a battery to report, ever.
    Say so plainly instead of showing the same 'n/a' a real read failure would."""
    if dev.device_class in ("TrackingReference", "Service"):
        return i18n.t("battery_no_battery")
    return f"{dev.battery_pct:.0f}%" if dev.battery_pct is not None else "n/a"


# SteamVR/OpenVR still reports the pre-rebrand company name for these devices.
# Oculus became Meta in 2021, and plenty of older Oculus-branded headsets are
# still in daily use - show the current name regardless of what the driver says.
_BRAND_RENAMES = {
    "oculus": "Meta",
    "oculus vr": "Meta",
    "oculus vr, llc": "Meta",
}


def _display_brand(manufacturer):
    name = (manufacturer or "").strip()
    return _BRAND_RENAMES.get(name.lower(), name)


def _brand_model_text(dev):
    """Combines manufacturer + model without repeating the brand name when
    the model string already starts with it (e.g. "Valve SR Imp", "Meta Quest Pro")."""
    manufacturer = _display_brand(dev.manufacturer)
    model = (dev.model or "").strip()
    if not manufacturer:
        return model
    if not model:
        return manufacturer
    if model.lower().startswith(manufacturer.lower()) or model.lower().startswith("oculus"):
        return model
    return f"{manufacturer} {model}"


def _device_display(serial, dev, offline=False):
    cls = i18n.t(f"devclass_{dev.device_class}")
    role = f" {dev.role}" if dev.role else ""
    batt = _battery_display(dev)
    brand_model = _brand_model_text(dev)
    model = f" ({brand_model})" if brand_model else ""
    suffix = f" ({i18n.t('device_offline_suffix')})" if offline else ""
    return f"{cls}{role}{model} - {batt} - {serial}{suffix}"


def _build_language_combo(parent, on_change):
    """Builds a 'Language: [English v]' pair packed into `parent`. Returns
    (combo, lang_keys) so the caller can read the selected language back via
    lang_keys[combo.current()]. Shared by the main window and the first-run
    notice, since that notice can pop up before the main window is usable."""
    ttk.Label(parent, text=i18n.t_piqad("lang_label")).pack(side="left", padx=(0, 4))
    lang_keys = list(i18n.LANGUAGES.keys())
    piqad_ok = piqad.ensure_font_loaded()
    lang_values = [
        piqad.transliterate(name) if (key == "tlh" and piqad_ok) else name
        for key, name in i18n.LANGUAGES.items()
    ]
    # A font with pIqaD glyphs is required to show Klingon's own name in
    # script; Windows' font-linking fills in the other languages' Latin/
    # Japanese text from the system font, so one widget can show both.
    lang_font = (piqad.FONT_FAMILY, 10) if piqad_ok else (DEFAULT_FONT_FAMILY, 10)
    combo = ttk.Combobox(parent, values=lang_values, state="readonly", width=13, font=lang_font)
    current_lang = i18n.get_language()
    combo.current(lang_keys.index(current_lang) if current_lang in lang_keys else 0)
    combo.pack(side="left", padx=(0, 10))
    combo.bind("<<ComboboxSelected>>", on_change)
    return combo, lang_keys


def _make_color_button(parent, initial_hex, on_change):
    """A small color-swatch button; clicking opens the system color picker.
    Returns (button, state_dict) where state_dict['hex'] holds the current value."""
    state = {"hex": initial_hex or "#ffffff"}
    btn = tk.Button(parent, width=4, bg=state["hex"], relief="ridge")

    def pick():
        result = colorchooser.askcolor(color=state["hex"], parent=parent)
        if result and result[1]:
            state["hex"] = result[1]
            btn.configure(bg=result[1])
            on_change()

    btn.configure(command=pick)
    return btn, state


class AboutDialog(tk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.withdraw()
        self.main_window = parent
        self.title(i18n.t("about_title"))
        self.resizable(False, False)
        theme.apply_window_theme(self, getattr(parent, "dark_mode", False))

        frm = ttk.Frame(self)
        frm.pack(padx=18, pady=16)

        ttk.Label(frm, text=APP_TITLE, font=("Segoe UI", 13, "bold")).pack(anchor="w")

        info = ttk.Frame(frm)
        info.pack(anchor="w", pady=(10, 0))
        ttk.Label(info, text=i18n.t_piqad("about_version_label")).grid(row=0, column=0, sticky="w", padx=(0, 6))
        ttk.Label(info, text=APP_VERSION, font=_default_font()).grid(row=0, column=1, sticky="w")
        ttk.Label(info, text=i18n.t_piqad("about_author_label")).grid(row=1, column=0, sticky="w", padx=(0, 6))
        ttk.Label(info, text=APP_AUTHOR, font=_default_font()).grid(row=1, column=1, sticky="w")
        ttk.Label(info, text=i18n.t_piqad("about_github_label")).grid(row=2, column=0, sticky="w", padx=(0, 6))
        link = ttk.Label(info, text=APP_GITHUB_URL, foreground="#3d8bff", cursor="hand2", font=_default_font())
        link.grid(row=2, column=1, sticky="w")
        link.bind("<Button-1>", lambda e: webbrowser.open(APP_GITHUB_URL))
        ttk.Label(info, text=i18n.t_piqad("about_contact_label")).grid(row=3, column=0, sticky="w", padx=(0, 6))
        contact_link = ttk.Label(info, text=APP_CONTACT_URL, foreground="#3d8bff", cursor="hand2", font=_default_font())
        contact_link.grid(row=3, column=1, sticky="w")
        contact_link.bind("<Button-1>", lambda e: webbrowser.open(APP_CONTACT_URL))

        self.check_updates_var = tk.BooleanVar(value=parent.cfg.check_for_updates)
        ttk.Checkbutton(
            frm, text=i18n.t_piqad("chk_check_updates"),
            variable=self.check_updates_var, command=self._toggle_check_updates,
        ).pack(anchor="w", pady=(12, 0))

        theme_row = ttk.Frame(frm)
        theme_row.pack(anchor="w", pady=(10, 0), fill="x")
        ttk.Label(theme_row, text=i18n.t_piqad("about_theme_label")).pack(side="left", padx=(0, 6))
        self.theme_keys = list(config_mod.THEME_OPTIONS.keys())
        self.theme_combo = ttk.Combobox(
            theme_row, values=[i18n.t_piqad(f"theme_{k}") for k in self.theme_keys],
            state="readonly", width=14,
        )
        self.theme_combo.current(self.theme_keys.index(parent.cfg.theme if parent.cfg.theme in self.theme_keys else "system"))
        self.theme_combo.pack(side="left")
        self.theme_combo.bind("<<ComboboxSelected>>", self._on_theme_change)

        close_row = ttk.Frame(frm)
        close_row.pack(anchor="w", pady=(10, 0), fill="x")
        ttk.Label(close_row, text=i18n.t_piqad("about_close_action_label")).pack(side="left", padx=(0, 6))
        self.close_action_keys = list(config_mod.CLOSE_ACTION_OPTIONS.keys())
        self.close_action_combo = ttk.Combobox(
            close_row, values=[i18n.t_piqad(f"closeaction_{k}") for k in self.close_action_keys],
            state="readonly", width=20,
        )
        start_close_action = parent.cfg.close_action if parent.cfg.close_action in self.close_action_keys else "ask"
        self.close_action_combo.current(self.close_action_keys.index(start_close_action))
        self.close_action_combo.pack(side="left")
        self.close_action_combo.bind("<<ComboboxSelected>>", self._on_close_action_change)

        ttk.Button(frm, text=i18n.t_piqad("btn_restore_icons"), command=self._on_restore_icons).pack(anchor="w", pady=(12, 0))

        ttk.Button(frm, text=i18n.t_piqad("about_close"), command=self.destroy).pack(anchor="e", pady=(14, 0))

        self.grab_set()
        self.transient(parent)
        # transient() re-parents the window at the Win32 level (makes this
        # dialog "owned" by parent) - that resets the DWM dark-titlebar
        # attribute applied earlier, so it must be re-applied after this,
        # not just once at the top.
        theme.apply_window_theme(self, getattr(parent, "dark_mode", False))
        self.deiconify()

    def _toggle_check_updates(self):
        self.main_window.cfg.check_for_updates = self.check_updates_var.get()
        config_mod.save(self.main_window.cfg)
        self.main_window._maybe_check_for_updates()

    def _on_theme_change(self, event=None):
        new_theme = self.theme_keys[self.theme_combo.current()]
        self.main_window.cfg.theme = new_theme
        config_mod.save(self.main_window.cfg)
        messagebox.showinfo(i18n.t("about_theme_label"), i18n.t("msg_theme_restart"), parent=self)

    def _on_close_action_change(self, event=None):
        new_action = self.close_action_keys[self.close_action_combo.current()]
        self.main_window.cfg.close_action = new_action
        config_mod.save(self.main_window.cfg)

    def _on_restore_icons(self):
        confirmed = messagebox.askyesno(
            i18n.t("restore_icons_confirm_title"),
            i18n.t("restore_icons_confirm_body"),
            icon="warning",
            parent=self,
        )
        if not confirmed:
            return
        count = bundled_icons.restore_all_icons()
        messagebox.showinfo(
            i18n.t("restore_icons_confirm_title"),
            i18n.t("restore_icons_done_fmt").format(n=count),
            parent=self,
        )


class FirstRunNoticeDialog(tk.Toplevel):
    """Shown once (unless dismissed) to explain that some devices report
    battery in bursts rather than continuously - not a bug in this app.

    Includes its own language switcher: this can appear before the user has
    ever touched the main window, so they shouldn't be stuck reading it in
    the wrong language until they close it."""

    def __init__(self, parent, on_dismiss):
        super().__init__(parent)
        self.withdraw()
        self.main_window = parent
        self.on_dismiss = on_dismiss
        self._lang_changed = False
        self.resizable(False, False)
        theme.apply_window_theme(self, getattr(parent, "dark_mode", False))

        lang_row = ttk.Frame(self)
        lang_row.pack(fill="x", padx=18, pady=(14, 0))
        self.lang_combo, self._lang_keys = _build_language_combo(lang_row, self._on_language_change)

        self.body_frame = ttk.Frame(self)
        self.body_frame.pack(padx=18, pady=16)
        self._dont_show_state = False
        self._check_updates_state = self.main_window.cfg.check_for_updates
        self._build_body()

        self.protocol("WM_DELETE_WINDOW", self._on_ok)
        self.grab_set()
        self.transient(parent)
        # transient() re-parents the window at the Win32 level, which resets
        # the DWM dark-titlebar attribute applied earlier - reapply after.
        theme.apply_window_theme(self, getattr(parent, "dark_mode", False))
        self.deiconify()

    def _build_body(self):
        self.title(i18n.t_piqad("notice_title"))
        for w in self.body_frame.winfo_children():
            w.destroy()
        frm = self.body_frame
        ttk.Label(frm, text=i18n.t_piqad("notice_title"), font=(_chrome_font_family(), 12, "bold")).pack(anchor="w")
        ttk.Label(frm, text=i18n.t_piqad("notice_battery_chunks_body"), wraplength=440, justify="left").pack(anchor="w", pady=(10, 12))

        self.dont_show_var = tk.BooleanVar(value=self._dont_show_state)
        ttk.Checkbutton(frm, text=i18n.t_piqad("chk_dont_show_again"), variable=self.dont_show_var).pack(anchor="w")

        self.check_updates_var = tk.BooleanVar(value=self._check_updates_state)
        ttk.Checkbutton(frm, text=i18n.t_piqad("chk_check_updates"), variable=self.check_updates_var).pack(anchor="w", pady=(4, 0))

        ttk.Button(frm, text=i18n.t_piqad("btn_ok"), command=self._on_ok).pack(anchor="e", pady=(14, 0))

    def _on_language_change(self, event=None):
        idx = self.lang_combo.current()
        new_lang = self._lang_keys[idx]
        if new_lang == i18n.get_language():
            return
        i18n.set_language(new_lang)
        apply_language_style()
        self.main_window.cfg.language = new_lang
        config_mod.save(self.main_window.cfg)
        self._lang_changed = True
        self._dont_show_state = self.dont_show_var.get()
        self._check_updates_state = self.check_updates_var.get()
        self._build_body()

    def _on_ok(self):
        self.on_dismiss(self.dont_show_var.get(), self.check_updates_var.get())
        self.destroy()
        if self._lang_changed:
            self.main_window._rebuild_ui()


class CloseActionDialog(tk.Toplevel):
    """Shown once, the first time the window's close (X) button is used -
    asks whether closing should minimize to the system tray (keep running
    in the background, still serving the OBS overlay) or exit completely.
    The choice is saved to cfg.close_action and applied immediately for
    this close too, not just remembered for next time."""

    def __init__(self, parent, on_choice):
        super().__init__(parent)
        self.withdraw()
        self.on_choice = on_choice
        self.title(i18n.t_piqad("close_action_title"))
        self.resizable(False, False)
        theme.apply_window_theme(self, getattr(parent, "dark_mode", False))

        frm = ttk.Frame(self)
        frm.pack(padx=18, pady=16)
        ttk.Label(frm, text=i18n.t_piqad("close_action_title"), font=(_chrome_font_family(), 12, "bold")).pack(anchor="w")
        ttk.Label(frm, text=i18n.t_piqad("close_action_body"), wraplength=440, justify="left").pack(anchor="w", pady=(10, 14))

        btns = ttk.Frame(frm)
        btns.pack(anchor="e")
        ttk.Button(btns, text=i18n.t_piqad("close_action_exit_btn"), command=lambda: self._choose("exit")).pack(side="right", padx=(8, 0))
        ttk.Button(btns, text=i18n.t_piqad("close_action_tray_btn"), command=lambda: self._choose("tray")).pack(side="right")

        ttk.Label(frm, text=i18n.t_piqad("close_action_hint"), foreground="#666", wraplength=440, justify="left").pack(anchor="w", pady=(10, 0))

        self.protocol("WM_DELETE_WINDOW", lambda: self._choose("exit"))
        self.grab_set()
        self.transient(parent)
        # transient() re-parents the window at the Win32 level, which resets
        # the DWM dark-titlebar attribute applied earlier - reapply after.
        theme.apply_window_theme(self, getattr(parent, "dark_mode", False))
        self.deiconify()

    def _choose(self, action):
        self.destroy()
        self.on_choice(action)


class TwitchConnectDialog(tk.Toplevel):
    """Runs the Device Code flow (app/twitch_auth.py): requests a code,
    shows it plus a link to Twitch's own approval page (never anything
    hosted by this app), and polls in the background until the user
    approves there or it times out. on_success(login, access_token,
    refresh_token) is called once, back on the Tk main thread."""

    def __init__(self, parent, on_success):
        super().__init__(parent)
        self.withdraw()
        self.on_success = on_success
        self._closed = False
        self.title(i18n.t_piqad("dlg_title_twitch_connect"))
        self.resizable(False, False)
        theme.apply_window_theme(self, getattr(parent, "dark_mode", False))

        self.frm = ttk.Frame(self)
        self.frm.pack(padx=20, pady=18)
        self.status_var = tk.StringVar(value=i18n.t_piqad("twitch_requesting_code"))
        ttk.Label(self.frm, textvariable=self.status_var, font=(_chrome_font_family(), 11, "bold")).pack(anchor="w")

        self.body_frame = ttk.Frame(self.frm)
        self.body_frame.pack(fill="x", pady=(10, 0))

        btns = ttk.Frame(self.frm)
        btns.pack(anchor="e", pady=(14, 0))
        ttk.Button(btns, text=i18n.t_piqad("btn_cancel"), command=self._on_cancel).pack(side="right")

        self.protocol("WM_DELETE_WINDOW", self._on_cancel)
        self.grab_set()
        self.transient(parent)
        theme.apply_window_theme(self, getattr(parent, "dark_mode", False))
        self.deiconify()

        threading.Thread(target=self._worker, daemon=True).start()

    def _on_cancel(self):
        self._closed = True
        self.destroy()

    def _worker(self):
        try:
            device = twitch_auth.request_device_code()
        except RuntimeError as exc:
            self.after(0, lambda: self._show_error(str(exc)))
            return
        self.after(0, lambda: self._show_code(device))
        try:
            result = twitch_auth.poll_for_token(
                device["device_code"], device["interval"], device["expires_in"],
            )
        except RuntimeError as exc:
            self.after(0, lambda: self._show_error(str(exc)))
            return
        self.after(0, lambda: self._finish(result))

    def _show_code(self, device):
        if self._closed:
            return
        self.status_var.set(i18n.t_piqad("twitch_waiting_approval"))
        for w in self.body_frame.winfo_children():
            w.destroy()
        link = ttk.Label(self.body_frame, text=device["verification_uri"], foreground="#3d8bff", cursor="hand2", font=_default_font())
        link.pack(anchor="w")
        link.bind("<Button-1>", lambda e: webbrowser.open(device["verification_uri"]))
        code_row = ttk.Frame(self.body_frame)
        code_row.pack(anchor="w", pady=(8, 0))
        ttk.Label(code_row, text=i18n.t_piqad("lbl_twitch_code")).pack(side="left")
        ttk.Label(code_row, text=device["user_code"], font=(_chrome_font_family(), 16, "bold")).pack(side="left", padx=(8, 0))
        webbrowser.open(device["verification_uri"])

    def _show_error(self, message):
        if self._closed:
            return
        self.status_var.set(i18n.t_piqad("twitch_connect_failed"))
        for w in self.body_frame.winfo_children():
            w.destroy()
        ttk.Label(self.body_frame, text=message, foreground="#cc4444", wraplength=380, justify="left").pack(anchor="w")

    def _finish(self, result):
        if self._closed:
            return
        self._closed = True
        self.destroy()
        self.on_success(result["login"], result["access_token"], result.get("refresh_token"))


class AudioPickerFrame(ttk.Frame):
    """Microphone chooser shared by Audio Device Effects and the mute macros:
    a search box, a list of Windows recording devices (real hardware first;
    virtual drivers and unplugged devices stay hidden unless asked for), and
    a Device name box that starts out as Windows' generic name and saves as a
    nickname when changed. Nothing is written to `nicknames` until the owner
    calls commit_nickname() on Save."""

    def __init__(self, parent, nicknames, current_id=None, current_name="", on_change=None):
        super().__init__(parent)
        self.nicknames = nicknames
        self._current_id = current_id
        self._current_name = current_name or ""
        self._selected_id = current_id
        self._on_change = on_change
        self._all = []
        self._by_id = {}
        self._row_ids = []
        self._rebind = None          # (old_id, new_id, name): a same-named device replaced the saved one
        self._rebound_from = None
        self._build()
        self.refresh()

    def _build(self):
        top = ttk.Frame(self)
        top.pack(fill="x")
        ttk.Label(top, text=i18n.t_piqad("lbl_audio_search")).pack(side="left")
        self.search_var = tk.StringVar()
        ttk.Entry(top, textvariable=self.search_var, width=28).pack(side="left", padx=6)
        self.search_var.trace_add("write", lambda *a: self._refill())
        ttk.Button(top, text=i18n.t_piqad("btn_refresh"), command=self.refresh).pack(side="left")

        opts = ttk.Frame(self)
        opts.pack(fill="x", pady=(4, 0))
        self.show_virtual_var = tk.BooleanVar(value=False)
        self.show_unplugged_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(opts, text=i18n.t_piqad("chk_show_virtual_audio"), variable=self.show_virtual_var, command=self._refill).pack(side="left")
        ttk.Checkbutton(opts, text=i18n.t_piqad("chk_show_unplugged_audio"), variable=self.show_unplugged_var, command=self._refill).pack(side="left", padx=(12, 0))

        list_row = ttk.Frame(self)
        list_row.pack(fill="x", pady=(4, 0))
        self.listbox = tk.Listbox(list_row, height=6, exportselection=False, activestyle="none")
        scroll = ttk.Scrollbar(list_row, orient="vertical", command=self.listbox.yview)
        self.listbox.configure(yscrollcommand=scroll.set)
        self.listbox.pack(side="left", fill="x", expand=True)
        scroll.pack(side="left", fill="y")
        self.listbox.bind("<<ListboxSelect>>", self._on_pick)

        self._rebind_row = ttk.Frame(self)
        ttk.Label(self._rebind_row, text=i18n.t_piqad("hint_audio_rebind"), foreground="#cc8800", wraplength=420, justify="left").pack(side="left")
        ttk.Button(self._rebind_row, text=i18n.t_piqad("btn_use_it"), command=self._use_rebind).pack(side="left", padx=(8, 0))

        name_row = ttk.Frame(self)
        name_row.pack(fill="x", pady=(8, 0))
        ttk.Label(name_row, text=i18n.t_piqad("lbl_audio_device_name")).pack(side="left")
        self.name_var = tk.StringVar()
        ttk.Entry(name_row, textvariable=self.name_var, width=36).pack(side="left", padx=6)
        self.win_name_lbl = ttk.Label(self, text="", foreground="#666")
        self.win_name_lbl.pack(anchor="w")

    # -- data ----------------------------------------------------------
    def refresh(self):
        self._all = audio_mod.list_endpoints()
        self._by_id = {e.id: e for e in self._all}
        self._update_rebind()
        self._refill()
        if self._selected_id:
            self._fill_name_from(self._selected_id, keep_typed=True)

    def _windows_name(self, eid):
        e = self._by_id.get(eid)
        if e:
            return e.name
        return self._current_name if eid == self._current_id else ""

    def _update_rebind(self):
        self._rebind = None
        if self._current_id and self._selected_id == self._current_id and not self._rebound_from:
            cur = self._by_id.get(self._current_id)
            if cur is None or not cur.connected:
                saved = {self._current_id: self._current_name or (cur.name if cur else "")}
                found = audio_mod.find_rebind_candidates(saved, self._all)
                if found:
                    self._rebind = found[0]
        if self._rebind:
            self._rebind_row.pack(fill="x", pady=(4, 0), after=self.listbox.master)
        else:
            self._rebind_row.pack_forget()

    def _refill(self):
        query = self.search_var.get().strip().lower()
        rows = []
        for e in self._all:
            keep = e.id == self._selected_id
            if not keep:
                if e.virtual and not self.show_virtual_var.get():
                    continue
                if not e.connected and not self.show_unplugged_var.get():
                    continue
                nick = self.nicknames.get(e.id, "")
                if query and query not in f"{nick} {e.name}".lower():
                    continue
            rows.append(e)
        if self._selected_id and self._selected_id not in {e.id for e in rows}:
            rows.append(audio_mod.Endpoint(id=self._selected_id, name=self._current_name or self._selected_id, state="NOTPRESENT"))
        rows.sort(key=lambda e: (not e.connected, e.virtual, e.name.lower()))

        base = {e.id: self._base_text(e) for e in rows}
        counts = {}
        for text in base.values():
            counts[text] = counts.get(text, 0) + 1

        self.listbox.delete(0, tk.END)
        self._row_ids = []
        for e in rows:
            text = base[e.id]
            if counts[text] > 1:
                text += f"  [{e.id[-5:-1]}]"
            tags = []
            if e.simulated:
                tags.append(i18n.t("audio_tag_simulated"))
            elif e.virtual:
                tags.append(i18n.t("audio_tag_virtual"))
            if not e.connected:
                tags.append(i18n.t("audio_tag_not_connected"))
            if tags:
                text += "  - " + ", ".join(tags)
            self.listbox.insert(tk.END, text)
            self._row_ids.append(e.id)
        if self._selected_id in self._row_ids:
            idx = self._row_ids.index(self._selected_id)
            self.listbox.selection_set(idx)
            self.listbox.see(idx)

    def _base_text(self, e):
        nick = self.nicknames.get(e.id, "").strip()
        return f"{nick}  ({e.name})" if nick and nick != e.name else e.name

    def _fill_name_from(self, eid, keep_typed=False):
        windows_name = self._windows_name(eid)
        if not (keep_typed and self.name_var.get().strip()):
            self.name_var.set(self.nicknames.get(eid, "").strip() or windows_name)
        self.win_name_lbl.configure(text=i18n.t("lbl_audio_windows_name_fmt").format(name=windows_name) if windows_name else "")

    # -- interaction ---------------------------------------------------
    def _on_pick(self, event=None):
        sel = self.listbox.curselection()
        if not sel:
            return
        self._selected_id = self._row_ids[sel[0]]
        self._rebound_from = None
        self._fill_name_from(self._selected_id)
        self._update_rebind()
        if self._on_change:
            self._on_change()

    def _use_rebind(self):
        if not self._rebind:
            return
        old_id, new_id, _name = self._rebind
        old_nick = self.nicknames.get(old_id, "").strip() or self.name_var.get().strip()
        self._rebound_from = old_id
        self._selected_id = new_id
        self._rebind = None
        self._rebind_row.pack_forget()
        self._refill()
        windows_name = self._windows_name(new_id)
        self.name_var.set(old_nick or windows_name)
        self.win_name_lbl.configure(text=i18n.t("lbl_audio_windows_name_fmt").format(name=windows_name))
        if self._on_change:
            self._on_change()

    # -- results -------------------------------------------------------
    def selected(self):
        """(endpoint_id or None, that device's Windows name)."""
        if not self._selected_id:
            return None, ""
        return self._selected_id, self._windows_name(self._selected_id)

    def name_text(self):
        return self.name_var.get().strip()

    def commit_nickname(self, nicknames, endpoint_id, windows_name):
        """Save the Device name box as this device's nickname - or forget any
        nickname if it was left blank or matches Windows' own name. A device
        adopted through "Use it" also takes over its old id's nickname."""
        if self._rebound_from and self._rebound_from != endpoint_id:
            nicknames.pop(self._rebound_from, None)
        text = self.name_text()
        if text and text != windows_name:
            nicknames[endpoint_id] = text
        else:
            nicknames.pop(endpoint_id, None)


class MacroEditorDialog(tk.Toplevel):
    """One mute macro: which microphone, what it does, and an optional global
    hotkey (recorded by pressing the keys - see app/hotkeys.py)."""

    def __init__(self, parent, macro, audio_nicknames):
        super().__init__(parent)
        self.withdraw()
        self.macro = macro
        self.audio_nicknames = audio_nicknames
        self.result = None
        self.title(i18n.t_piqad("dlg_title_macro"))
        self.resizable(False, False)
        theme.apply_window_theme(self, getattr(parent, "dark_mode", False))

        frm = ttk.Frame(self)
        frm.pack(padx=14, pady=12, fill="both")

        label_row = ttk.Frame(frm)
        label_row.pack(fill="x")
        ttk.Label(label_row, text=i18n.t_piqad("lbl_label")).pack(side="left")
        self.label_entry = ttk.Entry(label_row, width=30)
        self.label_entry.insert(0, macro.label)
        self.label_entry.pack(side="left", padx=6)

        self.picker = AudioPickerFrame(frm, audio_nicknames, macro.endpoint_id, macro.endpoint_name)
        self.picker.pack(fill="x", pady=(10, 0))

        action_row = ttk.Frame(frm)
        action_row.pack(fill="x", pady=(10, 0))
        ttk.Label(action_row, text=i18n.t_piqad("lbl_macro_action")).pack(side="left")
        self.action_keys = list(config_mod.MACRO_ACTION_OPTIONS.keys())
        self.action_combo = ttk.Combobox(action_row, values=[i18n.t_piqad(f"macroaction_{k}") for k in self.action_keys], state="readonly", width=24)
        self.action_combo.current(self.action_keys.index(macro.action) if macro.action in self.action_keys else 0)
        self.action_combo.pack(side="left", padx=6)

        hotkey_row = ttk.Frame(frm)
        hotkey_row.pack(fill="x", pady=(10, 0))
        ttk.Label(hotkey_row, text=i18n.t_piqad("lbl_macro_hotkey")).pack(side="left")
        self.hotkey_var = tk.StringVar(value=macro.hotkey or "")
        self.hotkey_entry = ttk.Entry(hotkey_row, textvariable=self.hotkey_var, state="readonly", width=28)
        self.hotkey_entry.pack(side="left", padx=6)
        self.hotkey_entry.bind("<KeyPress>", self._on_hotkey_key)
        ttk.Button(hotkey_row, text=i18n.t_piqad("btn_clear"), command=lambda: self.hotkey_var.set("")).pack(side="left")
        self.hotkey_status = tk.StringVar(value="")
        ttk.Label(frm, text=i18n.t_piqad("hint_hotkey_record"), foreground="#666", wraplength=460, justify="left").pack(anchor="w", pady=(2, 0))
        ttk.Label(frm, textvariable=self.hotkey_status, foreground="#cc4444").pack(anchor="w")

        btns = ttk.Frame(frm)
        btns.pack(anchor="e", pady=(12, 0))
        ttk.Button(btns, text=i18n.t_piqad("btn_cancel"), command=self.destroy).pack(side="right", padx=(6, 0))
        ttk.Button(btns, text=i18n.t_piqad("btn_save"), command=self._on_save).pack(side="right")

        self.grab_set()
        self.transient(parent)
        theme.apply_window_theme(self, getattr(parent, "dark_mode", False))
        place_dialog(self)
        self.deiconify()

    def _on_hotkey_key(self, event):
        vk = event.keycode  # on Windows, Tk's keycode is the virtual-key code
        if vk in hotkeys.MODIFIER_VKS:
            return "break"
        mods = hotkeys.current_modifiers()
        if event.keysym in ("Tab", "Escape") and not mods:
            return None  # let normal focus movement / dialog behaviour through
        text = hotkeys.format_hotkey(mods, vk)
        if text is None:
            self.hotkey_status.set(i18n.t("err_hotkey_key"))
        elif not mods and not hotkeys.allows_bare(vk):
            self.hotkey_status.set(i18n.t("err_hotkey_bare"))
        else:
            self.hotkey_var.set(text)
            self.hotkey_status.set("")
        return "break"

    def _on_save(self):
        endpoint_id, windows_name = self.picker.selected()
        if not endpoint_id:
            messagebox.showerror(i18n.t("err_pick_audio_title"), i18n.t("msg_macro_needs_device"), parent=self)
            return
        label = self.label_entry.get().strip() or self.picker.name_text() or windows_name
        macro = config_mod.MacroItem(
            id=self.macro.id, label=label, endpoint_id=endpoint_id, endpoint_name=windows_name,
            action=self.action_keys[self.action_combo.current()],
            hotkey=self.hotkey_var.get().strip() or None,
        )
        self.picker.commit_nickname(self.audio_nicknames, endpoint_id, windows_name)
        self.result = macro
        self.destroy()


class MacrosDialog(tk.Toplevel):
    """The list of mute macros plus the address of the big-button page. Every
    change is saved immediately and the global hotkeys are re-registered."""

    _HOTKEY_REASONS = {
        "already in use by another program": "hotkey_reason_in_use",
        "not a valid key combination": "hotkey_reason_invalid",
    }

    def __init__(self, main):
        super().__init__(main)
        self.withdraw()
        self.main = main
        self.title(i18n.t_piqad("dlg_title_macros"))
        self.resizable(False, False)
        theme.apply_window_theme(self, getattr(main, "dark_mode", False))

        frm = ttk.Frame(self)
        frm.pack(padx=14, pady=12, fill="both")

        self.tree = ttk.Treeview(frm, columns=("label", "device", "action", "hotkey"), show="headings", height=6)
        for col, key, width in (("label", "col_macro_label", 130), ("device", "col_macro_device", 200), ("action", "col_macro_action", 120), ("hotkey", "col_macro_hotkey", 150)):
            self.tree.heading(col, text=i18n.t_piqad(key))
            self.tree.column(col, width=width)
        self.tree.pack(fill="x")
        self.tree.bind("<Double-1>", lambda e: self._edit())

        btns = ttk.Frame(frm)
        btns.pack(fill="x", pady=(6, 0))
        ttk.Button(btns, text=i18n.t_piqad("add_btn"), command=self._add).pack(side="left")
        ttk.Button(btns, text=i18n.t_piqad("btn_edit"), command=self._edit).pack(side="left", padx=4)
        ttk.Button(btns, text=i18n.t_piqad("btn_remove"), command=self._remove).pack(side="left")
        ttk.Button(btns, text=i18n.t_piqad("btn_test"), command=self._test).pack(side="left", padx=(12, 0))

        self.conflict_var = tk.StringVar(value="")
        ttk.Label(frm, textvariable=self.conflict_var, foreground="#cc4444", wraplength=560, justify="left").pack(anchor="w", pady=(8, 0))

        ttk.Separator(frm, orient="horizontal").pack(fill="x", pady=10)
        url_row = ttk.Frame(frm)
        url_row.pack(fill="x")
        ttk.Label(url_row, text=i18n.t_piqad("lbl_macro_page")).pack(side="left")
        self.url_var = tk.StringVar(value=f"http://127.0.0.1:{main.server.port or main.cfg.port}/macros")
        ttk.Entry(url_row, textvariable=self.url_var, state="readonly", width=38).pack(side="left", padx=6)
        ttk.Button(url_row, text=i18n.t_piqad("btn_copy_url"), command=self._copy_url).pack(side="left")
        ttk.Button(url_row, text=i18n.t_piqad("btn_open_browser"), command=lambda: webbrowser.open(self.url_var.get())).pack(side="left", padx=4)
        ttk.Label(frm, text=i18n.t_piqad("hint_macro_page"), foreground="#666", wraplength=560, justify="left").pack(anchor="w", pady=(6, 0))

        ttk.Button(frm, text=i18n.t_piqad("about_close"), command=self.destroy).pack(anchor="e", pady=(10, 0))

        self._refresh()
        self.protocol("WM_DELETE_WINDOW", self.destroy)
        self.grab_set()
        self.transient(main)
        theme.apply_window_theme(self, getattr(main, "dark_mode", False))
        place_dialog(self)
        self.deiconify()

    def _device_text(self, m):
        return audio_mod.display_name(m.endpoint_id or "", m.endpoint_name, self.main.cfg.audio_nicknames)

    def _refresh(self):
        self.tree.delete(*self.tree.get_children())
        for m in self.main.cfg.macros:
            self.tree.insert("", "end", iid=m.id, values=(
                m.label, self._device_text(m), i18n.t(f"macroaction_{m.action}"), m.hotkey or "-",
            ))
        lines = []
        labels = {m.id: m.label for m in self.main.cfg.macros}
        for mid, reason in self.main.hotkey_manager.failed.items():
            hk = next((m.hotkey for m in self.main.cfg.macros if m.id == mid), "")
            lines.append(i18n.t("msg_hotkey_conflict_fmt").format(
                label=labels.get(mid, mid), hotkey=hk, reason=i18n.t(self._HOTKEY_REASONS.get(reason, "hotkey_reason_invalid")),
            ))
        self.conflict_var.set("\n".join(lines))

    def _changed(self):
        config_mod.save(self.main.cfg)
        self.main._rebind_hotkeys()
        self._refresh()

    def _selected(self):
        sel = self.tree.selection()
        return next((m for m in self.main.cfg.macros if m.id == sel[0]), None) if sel else None

    def _add(self):
        dlg = MacroEditorDialog(self, config_mod.MacroItem(id=config_mod.new_macro_id(), label=""), self.main.cfg.audio_nicknames)
        self.wait_window(dlg)
        if dlg.result:
            self.main.cfg.macros.append(dlg.result)
            self._changed()

    def _edit(self):
        macro = self._selected()
        if macro is None:
            return
        dlg = MacroEditorDialog(self, macro, self.main.cfg.audio_nicknames)
        self.wait_window(dlg)
        if dlg.result:
            idx = next(i for i, m in enumerate(self.main.cfg.macros) if m.id == macro.id)
            self.main.cfg.macros[idx] = dlg.result
            self._changed()

    def _remove(self):
        macro = self._selected()
        if macro is None:
            return
        if messagebox.askyesno(i18n.t("dlg_title_macros"), i18n.t("msg_remove_body_fmt").format(label=macro.label), parent=self):
            self.main.cfg.macros = [m for m in self.main.cfg.macros if m.id != macro.id]
            self._changed()

    def _test(self):
        macro = self._selected()
        if macro is None or not macro.endpoint_id:
            return
        result = self.main.audio_monitor.set_mute(macro.endpoint_id, macro.action)
        if not result.get("ok"):
            messagebox.showwarning(i18n.t("dlg_title_macros"), i18n.t("msg_macro_press_failed_fmt").format(error=result.get("error", "")), parent=self)

    def _copy_url(self):
        self.clipboard_clear()
        self.clipboard_append(self.url_var.get())


class DeviceSelectorMixin:
    """Shared 'pick a live SteamVR device, or type a serial manually' UI.

    A device can appear in the picker three ways, in priority order:
    1. Currently connected (live).
    2. Seen earlier this run but disconnected now (known_devices) - shown
       when "Show offline devices" is checked, or unconditionally if it's
       the item/effect's own already-saved device (so editing something
       whose device just went offline never shows a bare "no device"
       error).
    3. Neither (e.g. a fresh launch with everything powered off, so nothing
       has connected yet this run) - the item/effect's own saved serial and
       class hint are synthesized into a placeholder entry, so it's still
       representable and Save still works.
    None of this is a separate persistent registry - it all comes from
    whatever the item/effect itself already has saved, or from what's
    actually connected/known this run."""

    def _build_device_selector(self, parent, current_serial, current_class_hint=None, exclude_serials=None):
        device_frame = ttk.LabelFrame(parent, text=i18n.t_piqad("frame_device"))

        self._selector_current_serial = current_serial
        self._selector_current_class_hint = current_class_hint
        self._exclude_serials = set(exclude_serials or ())
        self.manual_var = tk.BooleanVar(value=False)
        self.show_used_var = tk.BooleanVar(value=False)
        self.show_offline_var = tk.BooleanVar(value=False)
        self._compute_device_lists()

        self.device_combo = ttk.Combobox(device_frame, values=self._device_values, width=55, state="readonly")
        self.device_combo.grid(row=0, column=0, padx=6, pady=4, sticky="ew")
        if current_serial in self._device_serials:
            self.device_combo.current(self._device_serials.index(current_serial))

        ttk.Button(device_frame, text=i18n.t_piqad("btn_refresh"), command=self._refresh_devices).grid(row=0, column=1, padx=4)

        ttk.Checkbutton(
            device_frame, text=i18n.t_piqad("chk_manual_serial"),
            variable=self.manual_var, command=self._toggle_manual,
        ).grid(row=1, column=0, columnspan=2, sticky="w", padx=6)

        if self._exclude_serials:
            ttk.Checkbutton(
                device_frame, text=i18n.t_piqad("chk_show_used_devices"),
                variable=self.show_used_var, command=self._refresh_devices,
            ).grid(row=3, column=0, columnspan=2, sticky="w", padx=6)

        ttk.Checkbutton(
            device_frame, text=i18n.t_piqad("chk_show_offline_devices"),
            variable=self.show_offline_var, command=self._refresh_devices,
        ).grid(row=4, column=0, columnspan=2, sticky="w", padx=6)

        self.manual_serial_entry = ttk.Entry(device_frame, width=40)
        self.manual_serial_entry.insert(0, current_serial)
        self._toggle_manual()
        return device_frame

    def _toggle_manual(self):
        self.device_combo.configure(state="disabled" if self.manual_var.get() else "readonly")
        if self.manual_var.get():
            self.manual_serial_entry.grid(row=2, column=0, columnspan=2, sticky="ew", padx=6, pady=2)
        else:
            self.manual_serial_entry.grid_remove()

    def _compute_device_lists(self):
        snapshot = self.vr_monitor.get_snapshot()
        live = snapshot.devices
        current = self._selector_current_serial

        # known_devices is always a superset of devices (updated with the
        # latest live set every poll, see vr_monitor._apply_devices), so
        # starting from it already covers tiers 1 and 2 in one dict.
        selectable = dict(snapshot.known_devices)
        if current and current not in selectable:
            # Tier 3: nothing has connected yet this run at all (e.g. a
            # fresh launch with everything powered off) - fall back to
            # what this item/effect already has saved, so it's still
            # representable and Save still works.
            selectable[current] = SimpleNamespace(
                device_class=self._selector_current_class_hint or "Other",
                model="", role="", manufacturer="", battery_pct=None, charging=None,
            )

        hide_used = set() if self.show_used_var.get() else self._exclude_serials
        show_offline = self.show_offline_var.get()
        visible = {}
        for s, d in selectable.items():
            if s != current and s in hide_used:
                continue
            if s != current and s not in live and not show_offline:
                continue
            visible[s] = d

        self._selectable_devices = selectable
        self._device_values = [_device_display(s, d, offline=(s not in live)) for s, d in visible.items()]
        self._device_serials = list(visible.keys())

    def _refresh_devices(self):
        self._compute_device_lists()
        self.device_combo.configure(values=self._device_values)
        if self._selector_current_serial in self._device_serials:
            self.device_combo.current(self._device_serials.index(self._selector_current_serial))

    def _resolve_device_selection(self, fallback_class_hint="Other"):
        """Returns (serial, device_class_hint), or None (after showing an error)."""
        if self.manual_var.get():
            serial = self.manual_serial_entry.get().strip()
            if not serial:
                messagebox.showerror(i18n.t("err_no_device_title"), i18n.t("err_enter_serial"), parent=self)
                return None
            return serial, fallback_class_hint
        if not self._device_values:
            messagebox.showerror(i18n.t("err_no_device_title"), i18n.t("err_no_devices_detected"), parent=self)
            return None
        idx = self.device_combo.current()
        if idx < 0:
            messagebox.showerror(i18n.t("err_no_device_title"), i18n.t("err_pick_device"), parent=self)
            return None
        serial = self._device_serials[idx]
        return serial, self._selectable_devices[serial].device_class


class MediaPickerMixin:
    """Shared 'choose a file, show its name, test sounds' row builder.
    Requires self._pending_media (dict kind -> chosen path or None)."""

    def _media_row(self, parent, row, text, kind, current_rel, sound=False, anim_default=None, anim_change_cb=None):
        """Returns (label_widget, anim_combo, anim_keys, control_widgets) -
        control_widgets is [choose_btn] or [choose_btn, test_btn], for
        callers that need to enable/disable this row as a group (e.g. gating
        the Charging section on its own checkbox)."""
        ttk.Label(parent, text=text).grid(row=row, column=0, sticky="w", padx=6, pady=3)
        current_full = config_mod.resolve_media(current_rel)
        display = os.path.basename(current_full) if current_full else "(default)"
        lbl = ttk.Label(parent, text=display, width=28)
        lbl.grid(row=row, column=1, sticky="w", padx=6)
        choose_btn = ttk.Button(parent, text=i18n.t_piqad("btn_choose"), command=lambda: self._choose_media(kind, lbl, sound))
        choose_btn.grid(row=row, column=2, padx=4)
        control_widgets = [choose_btn]
        if sound:
            test_btn = ttk.Button(parent, text=i18n.t_piqad("btn_test"), command=lambda: self._test_sound(kind, current_rel))
            test_btn.grid(row=row, column=3, padx=4)
            control_widgets.append(test_btn)

        anim_combo = anim_keys = None
        if anim_default is not None:
            anim_keys = list(config_mod.TEXT_ANIMATION_OPTIONS.keys())
            ttk.Label(parent, text=i18n.t_piqad("lbl_animation")).grid(row=row, column=4, sticky="w", padx=(14, 4))
            anim_combo = ttk.Combobox(parent, values=[i18n.t_piqad(f"textanim_{k}") for k in anim_keys], state="readonly", width=10)
            start = anim_default if anim_default in anim_keys else "none"
            anim_combo.current(anim_keys.index(start))
            anim_combo.grid(row=row, column=5, padx=4)
            if anim_change_cb:
                anim_combo.bind("<<ComboboxSelected>>", lambda e: anim_change_cb())

        return lbl, anim_combo, anim_keys, control_widgets

    def _choose_media(self, kind, label_widget, sound):
        types = SOUND_FILETYPES if sound else IMAGE_FILETYPES
        kwargs = {}
        if kind in ("normal", "low"):
            kwargs["initialdir"] = paths.device_icons_dir()
        path = filedialog.askopenfilename(title=i18n.t("btn_choose"), filetypes=types, parent=self, **kwargs)
        if not path:
            return
        self._pending_media[kind] = path
        label_widget.configure(text=os.path.basename(path))
        self._on_media_changed(kind)

    def _on_media_changed(self, kind):
        pass  # subclasses override to refresh a live preview when relevant

    def _test_sound(self, kind, current_rel):
        path = self._pending_media.get(kind) or config_mod.resolve_media(current_rel) or default_assets.ensure_defaults().get("_beep")
        if not path or not os.path.exists(path):
            return
        try:
            if path.lower().endswith(".wav"):
                import winsound
                winsound.PlaySound(path, winsound.SND_FILENAME | winsound.SND_ASYNC)
            else:
                os.startfile(path)  # best-effort preview using the default player
        except Exception as exc:
            messagebox.showwarning(i18n.t("warn_sound_title"), str(exc), parent=self)


class AnimationPickerMixin:
    """Shared 'Appear / Disappear animation + Test Animation button' builder."""

    def _build_animation_frame(self, parent, title, initial_enter, initial_exit):
        frame = ttk.LabelFrame(parent, text=title)
        ttk.Label(frame, text=i18n.t_piqad("lbl_appear")).grid(row=0, column=0, sticky="w", padx=6, pady=3)
        self.enter_keys = list(config_mod.ENTER_ANIMATIONS.keys())
        self.enter_combo = ttk.Combobox(frame, values=[i18n.t(f"enter_{k}") for k in self.enter_keys], state="readonly", width=24)
        self.enter_combo.grid(row=0, column=1, sticky="w", padx=6)
        self.enter_combo.current(self.enter_keys.index(initial_enter) if initial_enter in self.enter_keys else 0)
        self.enter_combo.bind("<<ComboboxSelected>>", lambda e: self._push_preview_if_active())

        ttk.Label(frame, text=i18n.t_piqad("lbl_disappear")).grid(row=1, column=0, sticky="w", padx=6, pady=3)
        self.exit_keys = list(config_mod.EXIT_ANIMATIONS.keys())
        self.exit_combo = ttk.Combobox(frame, values=[i18n.t(f"exit_{k}") for k in self.exit_keys], state="readonly", width=24)
        self.exit_combo.grid(row=1, column=1, sticky="w", padx=6)
        self.exit_combo.current(self.exit_keys.index(initial_exit) if initial_exit in self.exit_keys else 0)
        self.exit_combo.bind("<<ComboboxSelected>>", lambda e: self._push_preview_if_active())

        self.test_btn = ttk.Button(frame, text=i18n.t_piqad("btn_test_animation"), command=self._toggle_test_animation)
        self.test_btn.grid(row=0, column=2, rowspan=2, padx=10)
        ttk.Label(frame, text=i18n.t_piqad("hint_loops"), foreground="#666").grid(row=2, column=0, columnspan=3, sticky="w", padx=6)
        return frame


class PositionCanvasMixin:
    """Shared drag-to-position canvas with alignment snapping against every
    other Device item / Effect already placed."""

    SNAP_PX = 6

    def _build_position_frame(self, parent, owner_id, initial_x_pct, initial_y_pct, initial_width_px):
        self._position_owner_id = owner_id
        self.x_pct = initial_x_pct
        self.y_pct = initial_y_pct
        self._active_guides = {"x": None, "y": None}
        self._drag_offset = (0, 0)

        pos_frame = ttk.LabelFrame(parent, text=i18n.t_piqad("frame_position"))
        self.canvas = tk.Canvas(pos_frame, width=CANVAS_W, height=CANVAS_H, bg="#222", highlightthickness=1, highlightbackground="#555")
        self.canvas.grid(row=0, column=0, rowspan=2, padx=6, pady=6)

        size_col = ttk.Frame(pos_frame)
        size_col.grid(row=0, column=1, sticky="n", padx=6)
        ttk.Label(size_col, text=i18n.t_piqad("lbl_icon_width")).pack(anchor="w")
        self.width_var = tk.IntVar(value=initial_width_px)
        ttk.Spinbox(size_col, from_=32, to=600, textvariable=self.width_var, width=6, command=self._on_width_change).pack(anchor="w")

        self.snap_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(size_col, text=i18n.t_piqad("chk_snap"), variable=self.snap_var).pack(anchor="w", pady=(10, 0))
        ttk.Label(size_col, text=i18n.t_piqad("hint_snap"), foreground="#666", justify="left").pack(anchor="w")

        self.canvas.bind("<Button-1>", self._canvas_click)
        self.canvas.bind("<B1-Motion>", self._canvas_drag)
        self.canvas.bind("<ButtonRelease-1>", self._canvas_release)
        self._redraw_canvas()
        return pos_frame

    def _redraw_canvas(self):
        self.canvas.delete("all")
        for other in self.other_items:
            if other.id == self._position_owner_id:
                continue
            ox = other.x_pct / 100 * CANVAS_W
            oy = other.y_pct / 100 * CANVAS_H
            ow = other.width_px / 1920 * CANVAS_W
            self.canvas.create_rectangle(ox, oy, ox + ow, oy + ow, outline="#666", dash=(2, 2))
            self.canvas.create_text(ox + ow / 2, oy + ow / 2, text=other.label, fill="#888", font=("Segoe UI", 7))

        guides = self._active_guides
        if guides.get("x") is not None:
            self.canvas.create_line(guides["x"], 0, guides["x"], CANVAS_H, fill="#ffcc00", dash=(4, 2))
        if guides.get("y") is not None:
            self.canvas.create_line(0, guides["y"], CANVAS_W, guides["y"], fill="#ffcc00", dash=(4, 2))

        w = self.width_var.get() / 1920 * CANVAS_W
        x = self.x_pct / 100 * CANVAS_W
        y = self.y_pct / 100 * CANVAS_H
        self.canvas.create_rectangle(x, y, x + w, y + w, outline="#59c2ff", width=2, fill="#2a3f4d")
        self.canvas.create_text(x + w / 2, y + w / 2, text=i18n.t_piqad("canvas_drag_me"), fill="#59c2ff", font=_chrome_font(8))

    def _canvas_click(self, event):
        self._drag_offset = (event.x, event.y)

    def _compute_snap(self, raw_x, raw_y, w):
        """Snap the dragged box's edges/center to align with other items on
        either axis independently, so you can line things up in a row or
        column. Returns (x, y, guides)."""
        if not self.snap_var.get():
            return raw_x, raw_y, {"x": None, "y": None}

        my_left, my_cx, my_right = raw_x, raw_x + w / 2, raw_x + w
        my_top, my_cy, my_bottom = raw_y, raw_y + w / 2, raw_y + w

        best_x, best_x_dist, guide_x = None, self.SNAP_PX + 1, None
        best_y, best_y_dist, guide_y = None, self.SNAP_PX + 1, None

        for other in self.other_items:
            if other.id == self._position_owner_id:
                continue
            ow = other.width_px / 1920 * CANVAS_W
            ox = other.x_pct / 100 * CANVAS_W
            oy = other.y_pct / 100 * CANVAS_H
            o_left, o_cx, o_right = ox, ox + ow / 2, ox + ow
            o_top, o_cy, o_bottom = oy, oy + ow / 2, oy + ow

            for mine, other_val, new_x in (
                (my_left, o_left, o_left), (my_cx, o_cx, o_cx - w / 2), (my_right, o_right, o_right - w),
            ):
                d = abs(mine - other_val)
                if d <= self.SNAP_PX and d < best_x_dist:
                    best_x_dist, best_x, guide_x = d, new_x, other_val
            for mine, other_val, new_y in (
                (my_top, o_top, o_top), (my_cy, o_cy, o_cy - w / 2), (my_bottom, o_bottom, o_bottom - w),
            ):
                d = abs(mine - other_val)
                if d <= self.SNAP_PX and d < best_y_dist:
                    best_y_dist, best_y, guide_y = d, new_y, other_val

        return (
            best_x if best_x is not None else raw_x,
            best_y if best_y is not None else raw_y,
            {"x": guide_x, "y": guide_y},
        )

    def _canvas_drag(self, event):
        w = self.width_var.get() / 1920 * CANVAS_W
        raw_x = max(0, min(CANVAS_W - w, event.x - w / 2))
        raw_y = max(0, min(CANVAS_H - w, event.y - w / 2))
        x, y, guides = self._compute_snap(raw_x, raw_y, w)
        x = max(0, min(CANVAS_W - w, x))
        y = max(0, min(CANVAS_H - w, y))
        self.x_pct = x / CANVAS_W * 100
        self.y_pct = y / CANVAS_H * 100
        self._active_guides = guides
        self._redraw_canvas()
        self._push_preview_if_active()

    def _canvas_release(self, event):
        self._active_guides = {"x": None, "y": None}
        self._redraw_canvas()

    def _on_width_change(self):
        self._redraw_canvas()
        self._push_preview_if_active()


class PreviewMixin:
    """Shared 'Test Animation' live-preview channel to the running overlay."""

    def _init_preview(self, preview_state):
        self.preview_state = preview_state
        self._preview_active = False

    def _toggle_test_animation(self):
        if self._preview_active:
            self._stop_preview()
        else:
            self._preview_active = True
            self.test_btn.configure(text=i18n.t_piqad("btn_stop_test"))
            self._push_preview()

    def _push_preview(self):
        if self.preview_state is not None:
            self.preview_state.set(self._current_preview_payload())

    def _push_preview_if_active(self):
        if getattr(self, "_preview_active", False):
            self._push_preview()

    def _stop_preview(self):
        self._preview_active = False
        if hasattr(self, "test_btn"):
            self.test_btn.configure(text=i18n.t_piqad("btn_test_animation"))
        if getattr(self, "preview_state", None) is not None:
            self.preview_state.clear()


def _work_area(widget):
    """(left, top, right, bottom) of the usable screen area - taskbar
    excluded - on whichever monitor `widget` is on."""
    try:
        import ctypes
        from ctypes import wintypes

        class MONITORINFO(ctypes.Structure):
            _fields_ = [("cbSize", wintypes.DWORD), ("rcMonitor", wintypes.RECT),
                        ("rcWork", wintypes.RECT), ("dwFlags", wintypes.DWORD)]

        user32 = ctypes.windll.user32
        user32.MonitorFromWindow.argtypes = [wintypes.HWND, wintypes.DWORD]
        user32.MonitorFromWindow.restype = ctypes.c_void_p
        user32.GetMonitorInfoW.argtypes = [ctypes.c_void_p, ctypes.POINTER(MONITORINFO)]
        hmon = user32.MonitorFromWindow(widget.winfo_toplevel().winfo_id(), 2)  # MONITOR_DEFAULTTONEAREST
        info = MONITORINFO()
        info.cbSize = ctypes.sizeof(MONITORINFO)
        if hmon and user32.GetMonitorInfoW(hmon, ctypes.byref(info)):
            r = info.rcWork
            return r.left, r.top, r.right, r.bottom
    except Exception:
        pass
    return 0, 0, widget.winfo_screenwidth(), widget.winfo_screenheight() - 60


def _decoration_height():
    """Title bar plus top and bottom window borders - geometry()'s position
    is for the outer frame while its size is for the inside."""
    try:
        import ctypes
        gm = ctypes.windll.user32.GetSystemMetrics
        return gm(4) + 2 * (gm(33) + gm(92))  # SM_CYCAPTION + 2 * (SM_CYSIZEFRAME + SM_CXPADDEDBORDER)
    except Exception:
        return 40


def max_dialog_height(win):
    """Tallest a dialog can be and still fit on screen, title bar included."""
    _, top, _, bottom = _work_area(win.master)
    return max(300, bottom - top - _decoration_height() - 12)


def place_dialog(win, width=None, height=None):
    """Centers a dialog over its parent window, then nudges it so the whole
    window - title bar and Save/Cancel - stays inside the usable screen area.
    Without this Windows drops a tall dialog wherever it likes, typically low
    enough that the bottom runs off the screen. Pass width/height to size it
    too; leave them out to position only and let it keep its natural size."""
    parent = win.master
    left, top, right, bottom = _work_area(parent)
    deco = _decoration_height()
    size_it = width is not None
    if not size_it:
        win.update_idletasks()
        width, height = win.winfo_reqwidth(), win.winfo_reqheight()
    height = min(height, max_dialog_height(win))
    if parent.winfo_viewable():
        px, py, pw, ph = parent.winfo_rootx(), parent.winfo_rooty(), parent.winfo_width(), parent.winfo_height()
    else:
        px, py, pw, ph = left, top, right - left, bottom - top
    x = px + (pw - width) // 2
    y = py + (ph - height - deco) // 2
    x = max(left, min(x, right - width - 8))
    y = max(top, min(y, bottom - height - deco - 4))
    win.geometry(f"{width}x{height}+{x}+{y}" if size_it else f"+{x}+{y}")
    return height


class ScrollableDialogMixin:
    """A dialog body that scrolls internally and caps its own height to the
    screen, so Save/Cancel stay reachable no matter how many customization
    sections are visible or how small the screen is. Shared by ItemEditorDialog
    and EffectEditorDialog since both can grow taller than a small screen once
    every optional section (Nudge/Duration/Pop Animation/Caption/Media/Position)
    is showing at once."""

    def _build_scroll_container(self):
        container = ttk.Frame(self)
        container.pack(side="top", fill="both", expand=True)
        canvas = tk.Canvas(container, highlightthickness=0, bg=self.cget("bg"))
        vsb = ttk.Scrollbar(container, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)
        inner = ttk.Frame(canvas)
        inner_window = canvas.create_window((0, 0), window=inner, anchor="nw")
        self._body_canvas, self._body_inner, self._body_vsb = canvas, inner, vsb

        def _sync_scrollregion(event=None):
            canvas.configure(scrollregion=canvas.bbox("all"))
        inner.bind("<Configure>", _sync_scrollregion)
        canvas.bind("<Configure>", lambda e: canvas.itemconfig(inner_window, width=e.width))

        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        canvas.bind("<Enter>", lambda e: canvas.bind_all("<MouseWheel>", _on_mousewheel))
        canvas.bind("<Leave>", lambda e: canvas.unbind_all("<MouseWheel>"))
        return inner, vsb

    def _cap_dialog_height(self, inner, vsb):
        """Caps the dialog's total height to fit the screen (leaving room
        for the taskbar/title bar) - the canvas scrolls internally for
        whatever doesn't fit, so Save/Cancel stay reachable regardless of
        how many customization sections are visible or how small the
        screen is.

        Measures the button bar directly rather than deriving it from
        self.winfo_reqheight() - a Canvas's own requested size defaults to a
        small fixed value regardless of what's embedded in it via
        create_window(), so it doesn't propagate inner's real height
        upward; subtracting from the Toplevel's total would badly
        underestimate the button bar's share."""
        self.update_idletasks()
        content_w = inner.winfo_reqwidth()
        scrollbar_w = vsb.winfo_reqwidth()
        width = content_w + scrollbar_w + 20
        content_h = inner.winfo_reqheight()
        chrome_h = self._body_btns.winfo_reqheight() + 20  # pady top+bottom on the button bar
        total_h = min(content_h + chrome_h, max_dialog_height(self))
        # A plain geometry() call isn't enough here: since the dialog is
        # resizable(False, False), Tk keeps re-snapping it back to its
        # natural pack-computed request size (dominated by the Canvas's tiny
        # built-in default, since a Canvas never propagates the size of
        # whatever's embedded in it via create_window()) on the next layout
        # pass, silently discarding the explicit size below. Pinning
        # min/maxsize to the same value locks it for real.
        self.minsize(width, total_h)
        self.maxsize(width, total_h)
        place_dialog(self, width, total_h)


class SyncGroupMixin:
    """Shared 'Sync Group' UI (Device items only) - a named set of items that
    should only ever appear together, each keeping its own picture/label/
    animation, gated on every member being "ready" (all connected, or all
    connected and charged past a threshold). For VR accessories only used
    for special occasions, so they pop in as a set instead of trickling in
    individually as each happens to connect. Callers must set self.item and
    self.sync_groups (the shared list[SyncGroup]) before calling
    _build_sync_frame - mirrors NudgeGroupMixin's create/join-by-name UI."""

    def _find_sync_group(self, group_id):
        if not group_id:
            return None
        return next((g for g in self.sync_groups if g.id == group_id), None)

    def _build_sync_frame(self, parent):
        frame = ttk.LabelFrame(parent, text=i18n.t_piqad("frame_sync_group"))

        current_group = self._find_sync_group(self.item.sync_group_id)

        self.sync_enabled_var = tk.BooleanVar(value=current_group is not None)
        ttk.Checkbutton(
            frame, text=i18n.t_piqad("chk_sync_enabled"), variable=self.sync_enabled_var,
            command=self._update_sync_controls_state,
        ).grid(row=0, column=0, columnspan=4, sticky="w", padx=6, pady=(6, 0))

        ttk.Label(frame, text=i18n.t_piqad("lbl_sync_group")).grid(row=1, column=0, sticky="w", padx=6, pady=3)
        group_names = [g.name for g in self.sync_groups]
        self.sync_group_combo = ttk.Combobox(frame, values=group_names, width=22)
        self.sync_group_combo.set(current_group.name if current_group else "")
        self.sync_group_combo.grid(row=1, column=1, columnspan=3, sticky="w", padx=6, pady=3)
        self.sync_group_combo.bind("<<ComboboxSelected>>", self._on_sync_group_picked)

        ttk.Label(frame, text=i18n.t_piqad("hint_sync_group"), foreground="#666", wraplength=460, justify="left").grid(
            row=2, column=0, columnspan=4, sticky="w", padx=6
        )

        ttk.Label(frame, text=i18n.t_piqad("lbl_sync_ready_mode")).grid(row=3, column=0, sticky="w", padx=6, pady=(3, 6))
        self.sync_ready_mode_keys = list(config_mod.SYNC_READY_MODE_OPTIONS.keys())
        self.sync_ready_mode_combo = ttk.Combobox(
            frame, values=[i18n.t_piqad(f"syncready_{k}") for k in self.sync_ready_mode_keys], state="readonly", width=24,
        )
        start_mode = current_group.ready_mode if current_group else "all_connected"
        start_mode = start_mode if start_mode in self.sync_ready_mode_keys else "all_connected"
        self.sync_ready_mode_combo.current(self.sync_ready_mode_keys.index(start_mode))
        self.sync_ready_mode_combo.grid(row=3, column=1, sticky="w", padx=6, pady=(3, 6))

        ttk.Label(frame, text=i18n.t_piqad("lbl_sync_ready_threshold")).grid(row=3, column=2, sticky="w", padx=6)
        self.sync_ready_threshold_var = tk.IntVar(value=current_group.ready_threshold_pct if current_group else 95)
        self.sync_ready_threshold_spin = ttk.Spinbox(frame, from_=1, to=100, textvariable=self.sync_ready_threshold_var, width=5)
        self.sync_ready_threshold_spin.grid(row=3, column=3, sticky="w", padx=6)

        self._update_sync_controls_state()
        return frame

    def _update_sync_controls_state(self):
        on = self.sync_enabled_var.get()
        self.sync_group_combo.configure(state="normal" if on else "disabled")
        self.sync_ready_mode_combo.configure(state="readonly" if on else "disabled")
        self.sync_ready_threshold_spin.configure(state="normal" if on else "disabled")

    def _on_sync_group_picked(self, event=None):
        """Picking an *existing* group from the dropdown jumps this item's
        ready mode/threshold fields to match it - no manual re-entry."""
        name = self.sync_group_combo.get().strip()
        group = next((g for g in self.sync_groups if g.name == name), None)
        if not group:
            return
        self.sync_enabled_var.set(True)
        self._update_sync_controls_state()
        if group.ready_mode in self.sync_ready_mode_keys:
            self.sync_ready_mode_combo.current(self.sync_ready_mode_keys.index(group.ready_mode))
        self.sync_ready_threshold_var.set(group.ready_threshold_pct)

    def _resolve_sync_group(self):
        """Type a new name -> creates a group. Pick/type an existing name ->
        updates that shared group's ready mode/threshold, affecting every
        other item using it too. Checkbox unchecked -> no group, regardless
        of what's typed in the field."""
        if not self.sync_enabled_var.get():
            return None
        name = self.sync_group_combo.get().strip()
        if not name:
            return None
        ready_mode = self.sync_ready_mode_keys[self.sync_ready_mode_combo.current()]
        threshold = self.sync_ready_threshold_var.get()
        existing = next((g for g in self.sync_groups if g.name == name), None)
        if existing:
            existing.ready_mode = ready_mode
            existing.ready_threshold_pct = threshold
            return existing.id
        new_group = config_mod.SyncGroup(
            id=config_mod.new_sync_group_id(), name=name,
            ready_mode=ready_mode, ready_threshold_pct=threshold,
        )
        self.sync_groups.append(new_group)
        return new_group.id


class NudgeGroupMixin:
    """Shared 'Nudge Group' UI (assign a name/direction/spacing so several
    Device items and Effects share one drag-adjusted position and stack
    into it in arrival order) - used by both ItemEditorDialog and
    EffectEditorDialog so, e.g., a Lighthouse-disconnect Effect can nudge
    into the very same slot as a stack of low-battery Device alerts.
    Callers must set self._nudge_owner (the OverlayItem or EffectItem being
    edited) and self.nudge_groups (the shared list[NudgeGroup]) before
    calling _build_nudge_frame."""

    def _find_group(self, group_id):
        if not group_id:
            return None
        return next((g for g in self.nudge_groups if g.id == group_id), None)

    def _build_nudge_frame(self, parent):
        frame = ttk.LabelFrame(parent, text=i18n.t_piqad("frame_nudge"))

        current_group = self._find_group(self._nudge_owner.nudge_group_id)

        self.nudge_enabled_var = tk.BooleanVar(value=current_group is not None)
        ttk.Checkbutton(
            frame, text=i18n.t_piqad("chk_nudge_enabled"), variable=self.nudge_enabled_var,
            command=self._update_nudge_controls_state,
        ).grid(row=0, column=0, columnspan=4, sticky="w", padx=6, pady=(3, 0))

        ttk.Label(frame, text=i18n.t_piqad("lbl_nudge_group")).grid(row=1, column=0, sticky="w", padx=6, pady=3)
        group_names = [g.name for g in self.nudge_groups]
        self.nudge_group_combo = ttk.Combobox(frame, values=group_names, width=22)
        self.nudge_group_combo.set(current_group.name if current_group else "")
        self.nudge_group_combo.grid(row=1, column=1, columnspan=3, sticky="w", padx=6, pady=3)
        self.nudge_group_combo.bind("<<ComboboxSelected>>", self._on_nudge_group_picked)

        ttk.Label(frame, text=i18n.t_piqad("hint_nudge"), foreground="#666", wraplength=460, justify="left").grid(row=2, column=0, columnspan=4, sticky="w", padx=6)

        ttk.Label(frame, text=i18n.t_piqad("lbl_nudge_direction")).grid(row=3, column=0, sticky="w", padx=6, pady=3)
        self.nudge_direction_keys = list(config_mod.NUDGE_DIRECTION_OPTIONS.keys())
        self.nudge_direction_combo = ttk.Combobox(frame, values=[i18n.t_piqad(f"nudgedir_{k}") for k in self.nudge_direction_keys], state="readonly", width=10)
        start = (current_group.direction if current_group else "left")
        start = start if start in self.nudge_direction_keys else "left"
        self.nudge_direction_combo.current(self.nudge_direction_keys.index(start))
        self.nudge_direction_combo.grid(row=3, column=1, sticky="w", padx=6)

        ttk.Label(frame, text=i18n.t_piqad("lbl_nudge_spacing")).grid(row=3, column=2, sticky="w", padx=6)
        self.nudge_spacing_var = tk.IntVar(value=current_group.spacing_px if current_group else 20)
        self.nudge_spacing_spin = ttk.Spinbox(frame, from_=0, to=500, textvariable=self.nudge_spacing_var, width=6)
        self.nudge_spacing_spin.grid(row=3, column=3, sticky="w", padx=6)

        self._update_nudge_controls_state()
        return frame

    def _update_nudge_controls_state(self):
        on = self.nudge_enabled_var.get()
        self.nudge_group_combo.configure(state="normal" if on else "disabled")
        self.nudge_direction_combo.configure(state="readonly" if on else "disabled")
        self.nudge_spacing_spin.configure(state="normal" if on else "disabled")
        self._push_preview_if_active()

    def _on_nudge_group_picked(self, event=None):
        """Picking an *existing* group from the dropdown jumps this item's
        position/direction/spacing to match it - no manual lining-up needed."""
        name = self.nudge_group_combo.get().strip()
        group = next((g for g in self.nudge_groups if g.name == name), None)
        if not group:
            return
        self.nudge_enabled_var.set(True)
        self._update_nudge_controls_state()
        self.x_pct = group.x_pct
        self.y_pct = group.y_pct
        if group.direction in self.nudge_direction_keys:
            self.nudge_direction_combo.current(self.nudge_direction_keys.index(group.direction))
        self.nudge_spacing_var.set(group.spacing_px)
        self._redraw_canvas()
        self._push_preview_if_active()

    def _resolve_nudge_group(self):
        """Type a new name -> creates a group (using this dialog's current
        position/direction/spacing). Pick/type an existing name -> updates
        that shared group's position/direction/spacing from this dialog,
        moving every other device/effect using it too. Checkbox unchecked ->
        no group at all, regardless of what's typed in the field."""
        if not self.nudge_enabled_var.get():
            return None
        name = self.nudge_group_combo.get().strip()
        if not name:
            return None
        direction = self.nudge_direction_keys[self.nudge_direction_combo.current()]
        spacing = self.nudge_spacing_var.get()
        existing = next((g for g in self.nudge_groups if g.name == name), None)
        if existing:
            existing.x_pct = self.x_pct
            existing.y_pct = self.y_pct
            existing.direction = direction
            existing.spacing_px = spacing
            return existing.id
        new_group = config_mod.NudgeGroup(
            id=config_mod.new_group_id(), name=name,
            x_pct=self.x_pct, y_pct=self.y_pct,
            direction=direction, spacing_px=spacing,
        )
        self.nudge_groups.append(new_group)
        return new_group.id


class ItemEditorDialog(ScrollableDialogMixin, NudgeGroupMixin, SyncGroupMixin, DeviceSelectorMixin, MediaPickerMixin, AnimationPickerMixin, PositionCanvasMixin, PreviewMixin, tk.Toplevel):
    def __init__(self, parent, vr_monitor: VRMonitor, item: config_mod.OverlayItem, other_items, preview_state=None, nudge_groups=None, exclude_serials=None, sync_groups=None):
        super().__init__(parent)
        self.withdraw()
        self.title(i18n.t("dlg_title_device"))
        self.resizable(False, False)
        theme.apply_window_theme(self, getattr(parent, "dark_mode", False))
        self.vr_monitor = vr_monitor
        self.item = item
        self._nudge_owner = item
        self.other_items = other_items
        self.nudge_groups = nudge_groups if nudge_groups is not None else []
        self.sync_groups = sync_groups if sync_groups is not None else []
        self.exclude_serials = exclude_serials
        self.result = None
        self._init_preview(preview_state)
        self._pending_media = {
            "normal": None, "low": None, "sound": None,
            "charging": None, "warn_drain": None, "warn_drain_sound": None,
        }

        self._build()
        self.protocol("WM_DELETE_WINDOW", self._on_cancel)
        self.grab_set()
        self.transient(parent)
        # transient() re-parents the window at the Win32 level, which resets
        # the DWM dark-titlebar attribute applied earlier - reapply after.
        theme.apply_window_theme(self, getattr(parent, "dark_mode", False))
        self.deiconify()

    def _build(self):
        pad = {"padx": 8, "pady": 4}

        # Save/Cancel are pinned outside the scroll area (packed first, so
        # they claim their space at the bottom before the scrollable body
        # below expands to fill the rest) - this dialog can grow tall enough
        # (Nudge + Pop Animation + Caption Text + Media + Position all
        # visible at once) to outgrow a smaller screen, and with
        # resizable(False, False) there'd otherwise be no way to reach Save.
        btns = ttk.Frame(self)
        btns.pack(side="bottom", fill="x", padx=8, pady=10)
        ttk.Button(btns, text=i18n.t_piqad("btn_cancel"), command=self._on_cancel).pack(side="right", padx=4)
        ttk.Button(btns, text=i18n.t_piqad("btn_save"), command=self._on_save).pack(side="right", padx=4)
        self._body_btns = btns

        inner, vsb = self._build_scroll_container()

        device_frame = self._build_device_selector(inner, self.item.device_serial, current_class_hint=self.item.device_class_hint, exclude_serials=self.exclude_serials)
        device_frame.grid(row=0, column=0, columnspan=2, sticky="ew", **pad)

        basics = ttk.LabelFrame(inner, text=i18n.t_piqad("frame_basics"))
        basics.grid(row=1, column=0, columnspan=2, sticky="ew", **pad)
        ttk.Label(basics, text=i18n.t_piqad("lbl_label")).grid(row=0, column=0, sticky="w", padx=6)
        self.label_entry = ttk.Entry(basics, width=30)
        self.label_entry.insert(0, self.item.label)
        self.label_entry.grid(row=0, column=1, sticky="w", padx=6, pady=4)

        ttk.Label(basics, text=i18n.t_piqad("lbl_threshold")).grid(row=1, column=0, sticky="w", padx=6)
        self.threshold_var = tk.IntVar(value=self.item.low_threshold_pct)
        ttk.Spinbox(basics, from_=1, to=99, textvariable=self.threshold_var, width=6).grid(row=1, column=1, sticky="w", padx=6)
        ttk.Label(basics, text="%", font=_default_font()).grid(row=1, column=2, sticky="w")

        self.mode_var = tk.StringVar(value=self.item.show_mode)
        ttk.Radiobutton(basics, text=i18n.t_piqad("radio_always"), variable=self.mode_var, value="always", command=self._update_anim_frame_visibility).grid(row=2, column=0, columnspan=3, sticky="w", padx=6)
        ttk.Radiobutton(basics, text=i18n.t_piqad("radio_low_only"), variable=self.mode_var, value="low_only", command=self._update_anim_frame_visibility).grid(row=3, column=0, columnspan=3, sticky="w", padx=6)

        self.anim_frame = self._build_animation_frame(inner, i18n.t_piqad("frame_pop_animation_device"), self.item.enter_animation, self.item.exit_animation)
        self.anim_frame.grid(row=2, column=0, columnspan=2, sticky="ew", **pad)

        self.nudge_frame = self._build_nudge_frame(inner)
        self.nudge_frame.grid(row=3, column=0, columnspan=2, sticky="ew", **pad)

        sync_frame = self._build_sync_frame(inner)
        sync_frame.grid(row=4, column=0, columnspan=2, sticky="ew", **pad)

        self.label_entry.bind("<KeyRelease>", lambda e: self._push_preview_if_active())

        charging_frame = self._build_charging_frame(inner)
        charging_frame.grid(row=5, column=0, columnspan=2, sticky="ew", **pad)

        caption_frame = ttk.LabelFrame(inner, text=i18n.t_piqad("frame_caption"))
        caption_frame.grid(row=6, column=0, columnspan=2, sticky="ew", **pad)

        gap_row = ttk.Frame(caption_frame)
        gap_row.grid(row=0, column=0, columnspan=6, sticky="w", padx=6, pady=(6, 0))
        ttk.Label(gap_row, text=i18n.t_piqad("lbl_text_distance")).pack(side="left")
        self.text_gap_var = tk.IntVar(value=self.item.text_gap_px)
        ttk.Spinbox(
            gap_row, from_=0, to=200, textvariable=self.text_gap_var, width=6,
            command=self._push_preview_if_active,
        ).pack(side="left", padx=(6, 6))
        ttk.Label(gap_row, text=i18n.t_piqad("hint_text_distance"), foreground="#666").pack(side="left")

        self.label_style = self._build_text_style_block(
            caption_frame, row=1, title_key="frame_label_style", show_key="chk_show_label",
            show_default=self.item.show_label, prefix_defaults=dict(
                font_family=self.item.label_font_family, font_size_px=self.item.label_font_size_px,
                font_color=self.item.label_font_color, text_animation=self.item.label_text_animation,
                outline_enabled=self.item.label_outline_enabled, outline_thickness_px=self.item.label_outline_thickness_px,
                outline_color=self.item.label_outline_color,
            ),
        )
        self.percent_style = self._build_text_style_block(
            caption_frame, row=6, title_key="frame_percent_style", show_key="chk_show_percent",
            show_default=self.item.show_percent, prefix_defaults=dict(
                font_family=self.item.percent_font_family, font_size_px=self.item.percent_font_size_px,
                font_color=self.item.percent_font_color, text_animation=self.item.percent_text_animation,
                outline_enabled=self.item.percent_outline_enabled, outline_thickness_px=self.item.percent_outline_thickness_px,
                outline_color=self.item.percent_outline_color,
            ),
        )

        media = ttk.LabelFrame(inner, text=i18n.t_piqad("frame_media"))
        media.grid(row=7, column=0, columnspan=2, sticky="ew", **pad)
        _, self.normal_anim_combo, self.normal_anim_keys, _ = self._media_row(
            media, 0, i18n.t_piqad("lbl_normal_pic"), "normal", self.item.normal_image,
            anim_default=self.item.normal_pic_animation, anim_change_cb=self._push_preview_if_active,
        )
        _, self.low_anim_combo, self.low_anim_keys, _ = self._media_row(
            media, 1, i18n.t_piqad("lbl_low_pic"), "low", self.item.low_image,
            anim_default=self.item.low_pic_animation, anim_change_cb=self._push_preview_if_active,
        )
        self._media_row(media, 2, i18n.t_piqad("lbl_warning_sound"), "sound", self.item.sound, sound=True)

        start_group = self._find_group(self.item.nudge_group_id)
        start_x = start_group.x_pct if start_group else self.item.x_pct
        start_y = start_group.y_pct if start_group else self.item.y_pct
        pos_frame = self._build_position_frame(inner, self.item.id, start_x, start_y, self.item.width_px)
        pos_frame.grid(row=8, column=0, columnspan=2, sticky="ew", **pad)

        self._update_anim_frame_visibility()
        self._cap_dialog_height(inner, vsb)

    def _build_text_style_block(self, parent, row, title_key, show_key, show_default, prefix_defaults):
        """One customizable text element (Label or Battery %): show toggle,
        font, size, color, animation, and outline. Returns a dict of the
        widgets/vars needed to read values back on save."""
        ttk.Label(parent, text=i18n.t_piqad(title_key), font=(_chrome_font_family(), 9, "bold")).grid(row=row, column=0, columnspan=6, sticky="w", padx=6, pady=(8, 0))

        show_var = tk.BooleanVar(value=show_default)
        show_chk = ttk.Checkbutton(parent, text=i18n.t_piqad(show_key), variable=show_var)
        show_chk.grid(row=row + 1, column=0, columnspan=2, sticky="w", padx=6)

        ttk.Label(parent, text=i18n.t_piqad("lbl_font")).grid(row=row + 2, column=0, sticky="w", padx=6, pady=2)
        font_combo = ttk.Combobox(parent, values=FONT_CHOICES, state="normal", width=14)
        font_combo.set(prefix_defaults["font_family"])
        font_combo.grid(row=row + 2, column=1, sticky="w", padx=6)

        ttk.Label(parent, text=i18n.t_piqad("lbl_size")).grid(row=row + 2, column=2, sticky="w", padx=6)
        size_var = tk.IntVar(value=prefix_defaults["font_size_px"])
        ttk.Spinbox(parent, from_=6, to=96, textvariable=size_var, width=5).grid(row=row + 2, column=3, sticky="w", padx=6)

        ttk.Label(parent, text=i18n.t_piqad("lbl_font_color")).grid(row=row + 2, column=4, sticky="w", padx=6)
        color_btn, color_state = _make_color_button(parent, prefix_defaults["font_color"], self._push_preview_if_active)
        color_btn.grid(row=row + 2, column=5, sticky="w", padx=6)

        ttk.Label(parent, text=i18n.t_piqad("lbl_animation")).grid(row=row + 3, column=0, sticky="w", padx=6, pady=2)
        anim_keys = list(config_mod.TEXT_ANIMATION_OPTIONS.keys())
        anim_combo = ttk.Combobox(parent, values=[i18n.t_piqad(f"textanim_{k}") for k in anim_keys], state="readonly", width=12)
        start_anim = prefix_defaults["text_animation"] if prefix_defaults["text_animation"] in anim_keys else "none"
        anim_combo.current(anim_keys.index(start_anim))
        anim_combo.grid(row=row + 3, column=1, sticky="w", padx=6)

        outline_var = tk.BooleanVar(value=prefix_defaults["outline_enabled"])
        ttk.Checkbutton(parent, text=i18n.t_piqad("chk_outline"), variable=outline_var).grid(row=row + 3, column=2, sticky="w", padx=6)

        ttk.Label(parent, text=i18n.t_piqad("lbl_thickness")).grid(row=row + 3, column=3, sticky="w", padx=6)
        thickness_var = tk.IntVar(value=prefix_defaults["outline_thickness_px"])
        ttk.Spinbox(parent, from_=1, to=10, textvariable=thickness_var, width=4).grid(row=row + 3, column=4, sticky="w", padx=6)

        outline_color_btn, outline_color_state = _make_color_button(parent, prefix_defaults["outline_color"], self._push_preview_if_active)
        outline_color_btn.grid(row=row + 3, column=5, sticky="w", padx=6)

        show_var.trace_add("write", lambda *a: self._push_preview_if_active())
        font_combo.bind("<<ComboboxSelected>>", lambda e: self._push_preview_if_active())
        font_combo.bind("<KeyRelease>", lambda e: self._push_preview_if_active())
        anim_combo.bind("<<ComboboxSelected>>", lambda e: self._push_preview_if_active())

        return {
            "show_var": show_var, "font_combo": font_combo, "size_var": size_var, "color_state": color_state,
            "anim_combo": anim_combo, "anim_keys": anim_keys, "outline_var": outline_var,
            "thickness_var": thickness_var, "outline_color_state": outline_color_state,
        }

    @staticmethod
    def _read_text_style(style):
        return dict(
            font_family=style["font_combo"].get() or "Segoe UI",
            font_size_px=style["size_var"].get(),
            font_color=style["color_state"]["hex"],
            text_animation=style["anim_keys"][style["anim_combo"].current()],
            outline_enabled=style["outline_var"].get(),
            outline_thickness_px=style["thickness_var"].get(),
            outline_color=style["outline_color_state"]["hex"],
        )

    def _on_media_changed(self, kind):
        if kind == "low":
            self._push_preview_if_active()

    def _build_charging_frame(self, parent):
        """Always visible above Caption Text regardless of Always Visible /
        Hidden until low, since charging can happen in either mode. Only the
        "Hide when charging starts" row is mode-specific (Always Visible
        items have nothing to hide) - shown/hidden by _update_anim_frame_visibility."""
        frame = ttk.LabelFrame(parent, text=i18n.t_piqad("frame_charging"))

        self.show_charging_var = tk.BooleanVar(value=self.item.show_charging_status)
        ttk.Checkbutton(
            frame, text=i18n.t_piqad("chk_show_charging"), variable=self.show_charging_var,
            command=self._update_charging_lock,
        ).grid(row=0, column=0, columnspan=6, sticky="w", padx=6, pady=(6, 0))
        _, self.charging_anim_combo, self.charging_anim_keys, charging_controls = self._media_row(
            frame, 1, i18n.t_piqad("lbl_charging_pic"), "charging", self.item.charging_image,
            anim_default=self.item.charging_pic_animation,
        )
        self._charging_lockable = charging_controls + [self.charging_anim_combo]

        ttk.Separator(frame, orient="horizontal").grid(row=2, column=0, columnspan=6, sticky="ew", padx=6, pady=6)

        self.warn_drain_var = tk.BooleanVar(value=self.item.warn_drain_while_charging)
        ttk.Checkbutton(
            frame, text=i18n.t_piqad("chk_warn_drain"), variable=self.warn_drain_var,
            command=self._update_charging_lock,
        ).grid(row=3, column=0, columnspan=6, sticky="w", padx=6)
        _, self.warn_drain_anim_combo, self.warn_drain_anim_keys, warn_pic_controls = self._media_row(
            frame, 4, i18n.t_piqad("lbl_warn_drain_pic"), "warn_drain", self.item.warn_drain_image,
            anim_default=self.item.warn_drain_pic_animation,
        )
        _, _, _, warn_sound_controls = self._media_row(
            frame, 5, i18n.t_piqad("lbl_warn_drain_sound"), "warn_drain_sound", self.item.warn_drain_sound, sound=True,
        )

        cooldown_row = ttk.Frame(frame)
        cooldown_row.grid(row=6, column=0, columnspan=6, sticky="w", padx=6, pady=(2, 6))
        ttk.Label(cooldown_row, text=i18n.t_piqad("lbl_warn_drain_cooldown")).pack(side="left")
        self.warn_drain_cooldown_var = tk.IntVar(value=self.item.warn_drain_sound_cooldown_sec)
        self.warn_drain_cooldown_spinbox = ttk.Spinbox(cooldown_row, from_=5, to=3600, textvariable=self.warn_drain_cooldown_var, width=6)
        self.warn_drain_cooldown_spinbox.pack(side="left", padx=(6, 4))
        ttk.Label(cooldown_row, text=i18n.t_piqad("lbl_duration_seconds")).pack(side="left")

        self._warn_drain_lockable = (
            warn_pic_controls + [self.warn_drain_anim_combo] + warn_sound_controls + [self.warn_drain_cooldown_spinbox]
        )

        ttk.Separator(frame, orient="horizontal").grid(row=7, column=0, columnspan=6, sticky="ew", padx=6, pady=6)

        self.hide_on_charging_var = tk.BooleanVar(value=self.item.hide_on_charging)
        self.hide_on_charging_chk = ttk.Checkbutton(
            frame, text=i18n.t_piqad("chk_hide_on_charging"), variable=self.hide_on_charging_var
        )
        self.hide_on_charging_chk.grid(row=8, column=0, columnspan=6, sticky="w", padx=6, pady=(0, 6))

        self._update_charging_lock()
        return frame

    def _update_charging_lock(self):
        """Greys out each sub-section's controls until its own checkbox is
        ticked, so a first-time user isn't left wondering whether the
        Charging picture/animation/sound fields need setting up even when
        they've left the feature off."""
        charging_on = self.show_charging_var.get()
        for w in self._charging_lockable:
            state = "readonly" if isinstance(w, ttk.Combobox) else "normal"
            w.configure(state=state if charging_on else "disabled")

        warn_on = self.warn_drain_var.get()
        for w in self._warn_drain_lockable:
            state = "readonly" if isinstance(w, ttk.Combobox) else "normal"
            w.configure(state=state if warn_on else "disabled")

    def _update_anim_frame_visibility(self):
        if self.mode_var.get() == "low_only":
            self.anim_frame.grid()
            self.nudge_frame.grid()
            self.hide_on_charging_chk.grid()
        else:
            self.anim_frame.grid_remove()
            self.nudge_frame.grid_remove()
            self.hide_on_charging_chk.grid_remove()
            self._stop_preview()

    def _current_preview_payload(self):
        low_path = self._pending_media.get("low") or config_mod.resolve_media(self.item.low_image)
        label_style = self._read_text_style(self.label_style)
        percent_style = self._read_text_style(self.percent_style)
        return {
            "active": True,
            "mode": "device",
            "x_pct": self.x_pct,
            "y_pct": self.y_pct,
            "width_px": self.width_var.get(),
            "enter": self.enter_keys[self.enter_combo.current()],
            "exit": self.exit_keys[self.exit_combo.current()],
            "label": self.label_entry.get().strip() or "Preview",
            "show_label": self.label_style["show_var"].get(),
            "show_percent": self.percent_style["show_var"].get(),
            "text_gap_px": self.text_gap_var.get(),
            "label_style": label_style,
            "percent_style": percent_style,
            "low_path": low_path,
            "device_class_hint": self.item.device_class_hint or "Other",
            "normal_pic_animation": self.normal_anim_keys[self.normal_anim_combo.current()],
            "low_pic_animation": self.low_anim_keys[self.low_anim_combo.current()],
        }

    def _on_cancel(self):
        self._stop_preview()
        self.destroy()

    def _resolve_nudge_group(self):
        """Type a new name -> creates a group (using this dialog's current
        position/direction/spacing). Pick/type an existing name -> updates
        that shared group's position/direction/spacing from this dialog,
        moving every other device using it too. Checkbox unchecked -> no
        group at all, regardless of what's typed in the field."""
        if not self.nudge_enabled_var.get():
            return None
        name = self.nudge_group_combo.get().strip()
        if not name:
            return None
        direction = self.nudge_direction_keys[self.nudge_direction_combo.current()]
        spacing = self.nudge_spacing_var.get()
        existing = next((g for g in self.nudge_groups if g.name == name), None)
        if existing:
            existing.x_pct = self.x_pct
            existing.y_pct = self.y_pct
            existing.direction = direction
            existing.spacing_px = spacing
            return existing.id
        new_group = config_mod.NudgeGroup(
            id=config_mod.new_group_id(), name=name,
            x_pct=self.x_pct, y_pct=self.y_pct,
            direction=direction, spacing_px=spacing,
        )
        self.nudge_groups.append(new_group)
        return new_group.id

    def _on_save(self):
        resolved = self._resolve_device_selection(self.item.device_class_hint or "Other")
        if resolved is None:
            return
        serial, device_class_hint = resolved
        label = self.label_entry.get().strip() or serial
        nudge_group_id = self._resolve_nudge_group()
        sync_group_id = self._resolve_sync_group()

        item = config_mod.OverlayItem(
            id=self.item.id,
            label=label,
            device_serial=serial,
            device_class_hint=device_class_hint,
            x_pct=self.x_pct,
            y_pct=self.y_pct,
            width_px=self.width_var.get(),
            show_mode=self.mode_var.get(),
            low_threshold_pct=self.threshold_var.get(),
            normal_image=self.item.normal_image,
            low_image=self.item.low_image,
            normal_pic_animation=self.normal_anim_keys[self.normal_anim_combo.current()],
            low_pic_animation=self.low_anim_keys[self.low_anim_combo.current()],
            sound=self.item.sound,
            sound_cooldown_sec=self.item.sound_cooldown_sec,
            show_label=self.label_style["show_var"].get(),
            show_percent=self.percent_style["show_var"].get(),
            text_gap_px=self.text_gap_var.get(),
            enter_animation=self.enter_keys[self.enter_combo.current()],
            exit_animation=self.exit_keys[self.exit_combo.current()],
            nudge_group_id=nudge_group_id,
            sync_group_id=sync_group_id,
            show_charging_status=self.show_charging_var.get(),
            charging_image=self.item.charging_image,
            charging_pic_animation=self.charging_anim_keys[self.charging_anim_combo.current()],
            warn_drain_while_charging=self.warn_drain_var.get(),
            warn_drain_image=self.item.warn_drain_image,
            warn_drain_pic_animation=self.warn_drain_anim_keys[self.warn_drain_anim_combo.current()],
            warn_drain_sound=self.item.warn_drain_sound,
            warn_drain_sound_cooldown_sec=self.warn_drain_cooldown_var.get(),
            hide_on_charging=self.hide_on_charging_var.get(),
            **{f"label_{k}": v for k, v in self._read_text_style(self.label_style).items()},
            **{f"percent_{k}": v for k, v in self._read_text_style(self.percent_style).items()},
        )

        for kind, attr in (
            ("normal", "normal_image"), ("low", "low_image"), ("sound", "sound"),
            ("charging", "charging_image"), ("warn_drain", "warn_drain_image"), ("warn_drain_sound", "warn_drain_sound"),
        ):
            picked = self._pending_media.get(kind)
            if picked:
                rel = config_mod.import_media(item.id, picked, kind)
                setattr(item, attr, rel)

        self.result = item
        self._stop_preview()
        self.destroy()


class EffectEditorDialog(ScrollableDialogMixin, NudgeGroupMixin, DeviceSelectorMixin, MediaPickerMixin, AnimationPickerMixin, PositionCanvasMixin, PreviewMixin, tk.Toplevel):
    def __init__(self, parent, vr_monitor: VRMonitor, effect: config_mod.EffectItem, other_items, preview_state=None, nudge_groups=None, exclude_serials=None, twitch_connected=False, audio_nicknames=None):
        super().__init__(parent)
        self.withdraw()
        self.title(i18n.t("dlg_title_effect"))
        self.resizable(False, False)
        theme.apply_window_theme(self, getattr(parent, "dark_mode", False))
        self.vr_monitor = vr_monitor
        self.effect = effect
        self._nudge_owner = effect
        self.other_items = other_items
        self.nudge_groups = nudge_groups if nudge_groups is not None else []
        self.exclude_serials = exclude_serials
        self.twitch_connected = twitch_connected
        self.audio_nicknames = audio_nicknames if audio_nicknames is not None else {}
        self.result = None
        self._init_preview(preview_state)
        self._pending_media = {"picture": None, "sound": None}

        self._build()
        self.protocol("WM_DELETE_WINDOW", self._on_cancel)
        self.grab_set()
        self.transient(parent)
        # transient() re-parents the window at the Win32 level, which resets
        # the DWM dark-titlebar attribute applied earlier - reapply after.
        theme.apply_window_theme(self, getattr(parent, "dark_mode", False))
        self.deiconify()

    def _build(self):
        pad = {"padx": 8, "pady": 4}

        # Save/Cancel are pinned outside the scroll area (packed first, so
        # they claim their space at the bottom before the scrollable body
        # below expands to fill the rest) - this dialog can grow tall enough
        # (Target + Pop Animation + Duration + Media + Caption Text +
        # Position all visible at once) to outgrow a smaller screen, and
        # with resizable(False, False) there'd otherwise be no way to reach
        # Save.
        btns = ttk.Frame(self)
        btns.pack(side="bottom", fill="x", padx=8, pady=10)
        ttk.Button(btns, text=i18n.t_piqad("btn_cancel"), command=self._on_cancel).pack(side="right", padx=4)
        ttk.Button(btns, text=i18n.t_piqad("btn_save"), command=self._on_save).pack(side="right", padx=4)
        self._body_btns = btns

        inner, vsb = self._build_scroll_container()

        target_frame = self._build_target_frame(inner)
        target_frame.grid(row=0, column=0, columnspan=2, sticky="ew", **pad)

        basics = ttk.LabelFrame(inner, text=i18n.t_piqad("frame_basics"))
        basics.grid(row=1, column=0, columnspan=2, sticky="ew", **pad)
        ttk.Label(basics, text=i18n.t_piqad("lbl_label")).grid(row=0, column=0, sticky="w", padx=6)
        self.label_entry = ttk.Entry(basics, width=30)
        self.label_entry.insert(0, self.effect.label)
        self.label_entry.grid(row=0, column=1, sticky="w", padx=6, pady=4)

        ttk.Label(basics, text=i18n.t_piqad("lbl_trigger")).grid(row=1, column=0, sticky="w", padx=6)
        self.trigger_keys = []
        self.trigger_combo = ttk.Combobox(basics, values=[], state="readonly", width=26)
        self.trigger_combo.grid(row=1, column=1, sticky="w", padx=6)
        self.trigger_combo.bind("<<ComboboxSelected>>", lambda e: self._update_trigger_extras())

        self._threshold_widgets = [ttk.Label(basics, text=i18n.t_piqad("lbl_battery_threshold"))]
        self._threshold_widgets[0].grid(row=2, column=0, sticky="w", padx=6)
        self.threshold_var = tk.IntVar(value=self.effect.low_threshold_pct)
        threshold_spin = ttk.Spinbox(basics, from_=1, to=99, textvariable=self.threshold_var, width=6)
        threshold_spin.grid(row=2, column=1, sticky="w", padx=6)
        threshold_hint = ttk.Label(basics, text=i18n.t_piqad("hint_threshold_effect"), foreground="#666")
        threshold_hint.grid(row=2, column=2, sticky="w")
        self._threshold_widgets += [threshold_spin, threshold_hint]

        self._silent_widgets = [ttk.Label(basics, text=i18n.t_piqad("lbl_audio_silent_for"))]
        self._silent_widgets[0].grid(row=3, column=0, sticky="w", padx=6)
        self.audio_silent_var = tk.IntVar(value=self.effect.audio_silent_sec)
        silent_spin = ttk.Spinbox(basics, from_=3, to=3600, textvariable=self.audio_silent_var, width=6)
        silent_spin.grid(row=3, column=1, sticky="w", padx=6)
        self._silent_widgets.append(silent_spin)

        self.anim_frame = self._build_animation_frame(inner, i18n.t_piqad("frame_pop_animation_effect"), self.effect.enter_animation, self.effect.exit_animation)
        self.anim_frame.grid(row=2, column=0, columnspan=2, sticky="ew", **pad)

        self.label_entry.bind("<KeyRelease>", lambda e: self._push_preview_if_active())

        self.nudge_frame = self._build_nudge_frame(inner)
        self.nudge_frame.grid(row=3, column=0, columnspan=2, sticky="ew", **pad)

        duration_frame = ttk.LabelFrame(inner, text=i18n.t_piqad("frame_duration"))
        duration_frame.grid(row=4, column=0, columnspan=2, sticky="ew", **pad)
        self.duration_mode_keys = list(config_mod.DURATION_MODE_OPTIONS.keys())
        self.duration_mode_var = tk.StringVar(
            value=self.effect.duration_mode if self.effect.duration_mode in self.duration_mode_keys else "always"
        )
        for i, key in enumerate(self.duration_mode_keys):
            ttk.Radiobutton(
                duration_frame, text=i18n.t_piqad(f"durationmode_{key}"), variable=self.duration_mode_var, value=key,
                command=self._update_duration_visibility,
            ).grid(row=i, column=0, columnspan=2, sticky="w", padx=6, pady=(3, 0))
        self.duration_sec_row = ttk.Frame(duration_frame)
        self.duration_sec_row.grid(row=len(self.duration_mode_keys), column=0, columnspan=2, sticky="w", padx=6, pady=(0, 4))
        ttk.Label(self.duration_sec_row, text=i18n.t_piqad("lbl_duration_seconds")).pack(side="left")
        self.duration_sec_var = tk.DoubleVar(value=self.effect.duration_sec)
        ttk.Spinbox(
            self.duration_sec_row, from_=0.5, to=300, increment=0.5, textvariable=self.duration_sec_var, width=6,
            command=self._push_preview_if_active,
        ).pack(side="left", padx=(6, 0))
        self._update_duration_visibility()

        chat_frame = ttk.LabelFrame(inner, text=i18n.t_piqad("frame_chat_command"))
        chat_frame.grid(row=5, column=0, columnspan=2, sticky="ew", **pad)
        ttk.Label(chat_frame, text=i18n.t_piqad("lbl_chat_command")).grid(row=0, column=0, sticky="w", padx=6, pady=(6, 3))
        self.chat_command_entry = ttk.Entry(chat_frame, width=20)
        self.chat_command_entry.insert(0, self.effect.chat_command or "")
        self.chat_command_entry.grid(row=0, column=1, sticky="w", padx=6, pady=(6, 3))
        ttk.Label(chat_frame, text=i18n.t_piqad("hint_chat_command"), foreground="#666").grid(row=1, column=0, columnspan=2, sticky="w", padx=6)
        ttk.Label(chat_frame, text=i18n.t_piqad("lbl_chat_permission")).grid(row=2, column=0, sticky="w", padx=6, pady=(4, 6))
        self.chat_permission_keys = list(config_mod.CHAT_PERMISSION_OPTIONS.keys())
        self.chat_permission_combo = ttk.Combobox(
            chat_frame, values=[i18n.t_piqad(f"chatperm_{k}") for k in self.chat_permission_keys], state="readonly", width=20,
        )
        self.chat_permission_combo.grid(row=2, column=1, sticky="w", padx=6, pady=(4, 6))
        self.chat_permission_combo.current(
            self.chat_permission_keys.index(self.effect.chat_permission) if self.effect.chat_permission in self.chat_permission_keys else 0
        )
        if not self.twitch_connected:
            self.chat_command_entry.configure(state="disabled")
            self.chat_permission_combo.configure(state="disabled")
            ttk.Label(chat_frame, text=i18n.t_piqad("hint_chat_needs_connect"), foreground="#cc8800").grid(
                row=3, column=0, columnspan=2, sticky="w", padx=6, pady=(0, 6)
            )

        media = ttk.LabelFrame(inner, text=i18n.t_piqad("frame_media"))
        media.grid(row=6, column=0, columnspan=2, sticky="ew", **pad)
        _, self.picture_anim_combo, self.picture_anim_keys, _ = self._media_row(
            media, 0, i18n.t_piqad("lbl_picture"), "picture", self.effect.picture,
            anim_default=self.effect.picture_animation, anim_change_cb=self._push_preview_if_active,
        )
        self._media_row(media, 1, i18n.t_piqad("lbl_warning_sound"), "sound", self.effect.sound, sound=True)

        text_frame = ttk.LabelFrame(inner, text=i18n.t_piqad("frame_caption"))
        text_frame.grid(row=7, column=0, columnspan=2, sticky="ew", **pad)

        ttk.Label(text_frame, text=i18n.t_piqad("lbl_text")).grid(row=0, column=0, sticky="w", padx=6, pady=3)
        self.text_entry = ttk.Entry(text_frame, width=30)
        self.text_entry.insert(0, self.effect.text)
        self.text_entry.grid(row=0, column=1, columnspan=3, sticky="ew", padx=6)
        self.text_entry.bind("<KeyRelease>", lambda e: self._push_preview_if_active())

        ttk.Label(text_frame, text=i18n.t_piqad("lbl_position")).grid(row=1, column=0, sticky="w", padx=6, pady=3)
        self.text_pos_keys = list(config_mod.TEXT_POSITION_OPTIONS.keys())
        self.text_pos_combo = ttk.Combobox(text_frame, values=[i18n.t(f"textpos_{k}") for k in self.text_pos_keys], state="readonly", width=18)
        self.text_pos_combo.grid(row=1, column=1, sticky="w", padx=6)
        self.text_pos_combo.current(self.text_pos_keys.index(self.effect.text_position) if self.effect.text_position in self.text_pos_keys else 1)
        self.text_pos_combo.bind("<<ComboboxSelected>>", lambda e: self._push_preview_if_active())

        ttk.Label(text_frame, text=i18n.t_piqad("lbl_animation")).grid(row=1, column=2, sticky="w", padx=6)
        self.text_anim_keys = list(config_mod.TEXT_ANIMATION_OPTIONS.keys())
        self.text_anim_combo = ttk.Combobox(text_frame, values=[i18n.t(f"textanim_{k}") for k in self.text_anim_keys], state="readonly", width=14)
        self.text_anim_combo.grid(row=1, column=3, sticky="w", padx=6)
        self.text_anim_combo.current(self.text_anim_keys.index(self.effect.text_animation) if self.effect.text_animation in self.text_anim_keys else 0)
        self.text_anim_combo.bind("<<ComboboxSelected>>", lambda e: self._push_preview_if_active())

        ttk.Label(text_frame, text=i18n.t_piqad("lbl_text_distance")).grid(row=2, column=0, sticky="w", padx=6, pady=3)
        self.text_gap_var = tk.IntVar(value=self.effect.text_gap_px)
        ttk.Spinbox(
            text_frame, from_=0, to=200, textvariable=self.text_gap_var, width=6,
            command=self._push_preview_if_active,
        ).grid(row=2, column=1, sticky="w", padx=6)
        ttk.Label(text_frame, text=i18n.t_piqad("hint_text_distance"), foreground="#666").grid(row=2, column=2, columnspan=2, sticky="w", padx=6)

        ttk.Label(text_frame, text=i18n.t_piqad("lbl_font")).grid(row=3, column=0, sticky="w", padx=6, pady=3)
        self.font_combo = ttk.Combobox(text_frame, values=FONT_CHOICES, state="normal", width=18)
        self.font_combo.set(self.effect.font_family)
        self.font_combo.grid(row=3, column=1, sticky="w", padx=6)
        self.font_combo.bind("<<ComboboxSelected>>", lambda e: self._push_preview_if_active())
        self.font_combo.bind("<KeyRelease>", lambda e: self._push_preview_if_active())

        ttk.Label(text_frame, text=i18n.t_piqad("lbl_size")).grid(row=3, column=2, sticky="w", padx=6)
        self.font_size_var = tk.IntVar(value=self.effect.font_size_px)
        ttk.Spinbox(text_frame, from_=8, to=96, textvariable=self.font_size_var, width=5, command=self._push_preview_if_active).grid(row=3, column=3, sticky="w", padx=6)

        ttk.Label(text_frame, text=i18n.t_piqad("lbl_font_color")).grid(row=4, column=0, sticky="w", padx=6, pady=3)
        self.font_color_btn, self.font_color_var = _make_color_button(text_frame, self.effect.font_color, self._push_preview_if_active)
        self.font_color_btn.grid(row=4, column=1, sticky="w", padx=6)

        self.outline_var = tk.BooleanVar(value=self.effect.outline_enabled)
        ttk.Checkbutton(text_frame, text=i18n.t_piqad("chk_outline"), variable=self.outline_var, command=self._push_preview_if_active).grid(row=4, column=2, sticky="w", padx=6)

        ttk.Label(text_frame, text=i18n.t_piqad("lbl_thickness")).grid(row=5, column=0, sticky="w", padx=6, pady=3)
        self.outline_thickness_var = tk.IntVar(value=self.effect.outline_thickness_px)
        ttk.Spinbox(text_frame, from_=1, to=10, textvariable=self.outline_thickness_var, width=5, command=self._push_preview_if_active).grid(row=5, column=1, sticky="w", padx=6)

        ttk.Label(text_frame, text=i18n.t_piqad("lbl_outline_color")).grid(row=5, column=2, sticky="w", padx=6)
        self.outline_color_btn, self.outline_color_var = _make_color_button(text_frame, self.effect.outline_color, self._push_preview_if_active)
        self.outline_color_btn.grid(row=5, column=3, sticky="w", padx=6)

        pos_frame = self._build_position_frame(inner, self.effect.id, self.effect.x_pct, self.effect.y_pct, self.effect.width_px)
        pos_frame.grid(row=8, column=0, columnspan=2, sticky="ew", **pad)

        self._update_target_mode_visibility()
        self._cap_dialog_height(inner, vsb)

    def _update_duration_visibility(self):
        if self.duration_mode_var.get() == "timed":
            self.duration_sec_row.grid()
        else:
            self.duration_sec_row.grid_remove()

    # -- device targeting: Specific / Any / All + Ignore Device -----------
    def _build_target_frame(self, parent):
        frame = ttk.LabelFrame(parent, text=i18n.t_piqad("frame_target"))

        self.target_mode_keys = list(config_mod.TARGET_MODE_OPTIONS.keys())
        initial_mode = self.effect.target_mode if self.effect.target_mode in self.target_mode_keys else "specific"
        self.target_mode_var = tk.StringVar(value=initial_mode)
        mode_row = ttk.Frame(frame)
        mode_row.grid(row=0, column=0, columnspan=2, sticky="w", padx=6, pady=3)
        for key in self.target_mode_keys:
            ttk.Radiobutton(
                mode_row, text=i18n.t_piqad(f"targetmode_{key}"), variable=self.target_mode_var, value=key,
                command=self._update_target_mode_visibility,
            ).pack(side="left", padx=(0, 10))

        self.device_frame = self._build_device_selector(frame, self.effect.device_serial, current_class_hint=self.effect.device_class_hint, exclude_serials=self.exclude_serials)
        self.device_frame.grid(row=1, column=0, columnspan=2, sticky="ew", padx=6, pady=3)

        self.ignore_frame = ttk.Frame(frame)
        self.ignore_frame.grid(row=2, column=0, columnspan=2, sticky="ew", padx=6, pady=3)
        ttk.Label(self.ignore_frame, text=i18n.t_piqad("lbl_ignore_devices")).pack(anchor="w")
        ttk.Label(self.ignore_frame, text=i18n.t_piqad("hint_ignore_devices"), foreground="#666").pack(anchor="w")

        list_row = ttk.Frame(self.ignore_frame)
        list_row.pack(fill="x", pady=(2, 0))
        self.ignore_listbox = tk.Listbox(list_row, selectmode=tk.MULTIPLE, height=4, exportselection=False)
        scroll = ttk.Scrollbar(list_row, orient="vertical", command=self.ignore_listbox.yview)
        self.ignore_listbox.configure(yscrollcommand=scroll.set)
        self.ignore_listbox.pack(side="left", fill="x", expand=True)
        scroll.pack(side="left", fill="y")
        self.ignore_listbox.bind("<<ListboxSelect>>", lambda e: self._push_preview_if_active())
        self._populate_ignore_listbox(preselect=self.effect.ignore_device_serials)

        self.audio_frame = AudioPickerFrame(
            frame, self.audio_nicknames, self.effect.audio_endpoint_id, self.effect.audio_name, on_change=self._push_preview_if_active,
        )
        self.audio_frame.grid(row=3, column=0, columnspan=2, sticky="ew", padx=6, pady=3)

        return frame

    def _populate_ignore_listbox(self, preselect):
        self.ignore_listbox.delete(0, tk.END)
        for val in self._device_values:
            self.ignore_listbox.insert(tk.END, val)
        for idx, serial in enumerate(self._device_serials):
            if serial in preselect:
                self.ignore_listbox.selection_set(idx)

    def _refresh_devices(self):
        prev_ignored = self._resolve_ignore_selections() if hasattr(self, "ignore_listbox") else []
        super()._refresh_devices()
        if hasattr(self, "ignore_listbox"):
            self._populate_ignore_listbox(preselect=prev_ignored)

    def _resolve_ignore_selections(self):
        return [self._device_serials[i] for i in self.ignore_listbox.curselection()]

    def _update_target_mode_visibility(self):
        mode = self.target_mode_var.get()
        self.device_frame.grid() if mode == "specific" else self.device_frame.grid_remove()
        self.ignore_frame.grid() if mode == "all" else self.ignore_frame.grid_remove()
        self.audio_frame.grid() if mode == "audio" else self.audio_frame.grid_remove()
        self._refresh_trigger_choices()
        self._push_preview_if_active()

    def _refresh_trigger_choices(self):
        """Audio Device targets only offer the microphone triggers, everything
        else only the SteamVR ones - the two sets don't mix. Keeps the current
        pick when it's still valid, otherwise falls back to the first option."""
        audio = self.target_mode_var.get() == "audio"
        keys = [k for k in config_mod.TRIGGER_OPTIONS if (k in config_mod.AUDIO_TRIGGER_KEYS) == audio]
        previous = self.trigger_keys[self.trigger_combo.current()] if self.trigger_keys and self.trigger_combo.current() >= 0 else self.effect.trigger
        self.trigger_keys = keys
        self.trigger_combo.configure(values=[i18n.t(f"trigger_{k}") for k in keys])
        self.trigger_combo.current(keys.index(previous) if previous in keys else 0)
        self._update_trigger_extras()

    def _update_trigger_extras(self):
        """Show only the settings the chosen trigger actually uses: the
        battery threshold for battery triggers, the silence length for
        "Mic Silent For..."."""
        trigger = self.trigger_keys[self.trigger_combo.current()] if self.trigger_keys else ""
        show_threshold = trigger in ("battery_low", "battery_normal")
        for w in self._threshold_widgets:
            w.grid() if show_threshold else w.grid_remove()
        for w in self._silent_widgets:
            w.grid() if trigger == "audio_silent" else w.grid_remove()
        self._push_preview_if_active()

    def _on_media_changed(self, kind):
        if kind == "picture":
            self._push_preview_if_active()

    def _current_preview_payload(self):
        picture_path = self._pending_media.get("picture") or config_mod.resolve_media(self.effect.picture)
        return {
            "active": True,
            "mode": "effect",
            "x_pct": self.x_pct,
            "y_pct": self.y_pct,
            "width_px": self.width_var.get(),
            "enter": self.enter_keys[self.enter_combo.current()],
            "exit": self.exit_keys[self.exit_combo.current()],
            "low_path": picture_path,
            "picture_animation": self.picture_anim_keys[self.picture_anim_combo.current()],
            "device_class_hint": "Microphone" if self.target_mode_var.get() == "audio" else (self.effect.device_class_hint or "Other"),
            "text": self.text_entry.get(),
            "text_position": self.text_pos_keys[self.text_pos_combo.current()],
            "text_gap_px": self.text_gap_var.get(),
            "font_family": self.font_combo.get() or "Segoe UI",
            "font_size_px": self.font_size_var.get(),
            "font_color": self.font_color_var["hex"],
            "text_animation": self.text_anim_keys[self.text_anim_combo.current()],
            "outline_enabled": self.outline_var.get(),
            "outline_thickness_px": self.outline_thickness_var.get(),
            "outline_color": self.outline_color_var["hex"],
        }

    def _on_cancel(self):
        self._stop_preview()
        self.destroy()

    def _on_save(self):
        mode = self.target_mode_var.get()
        if mode == "specific":
            resolved = self._resolve_device_selection(self.effect.device_class_hint or "Other")
            if resolved is None:
                return
            serial, device_class_hint = resolved
            ignore_serials = []
        elif mode == "audio":
            audio_id, audio_windows_name = self.audio_frame.selected()
            if not audio_id:
                messagebox.showerror(i18n.t("err_pick_audio_title"), i18n.t("err_pick_audio_body"), parent=self)
                return
            serial = ""
            device_class_hint = "Microphone"
            ignore_serials = []
        else:
            serial = ""
            device_class_hint = self.effect.device_class_hint or "Other"
            ignore_serials = self._resolve_ignore_selections()

        if mode == "audio":
            default_label = self.audio_frame.name_text() or audio_windows_name
        else:
            default_label = serial if mode == "specific" else i18n.t(f"targetmode_{mode}")
        label = self.label_entry.get().strip() or default_label
        nudge_group_id = self._resolve_nudge_group()

        effect = config_mod.EffectItem(
            id=self.effect.id,
            label=label,
            device_serial=serial,
            device_class_hint=device_class_hint,
            target_mode=mode,
            audio_endpoint_id=audio_id if mode == "audio" else None,
            audio_name=audio_windows_name if mode == "audio" else "",
            audio_silent_sec=self.audio_silent_var.get(),
            ignore_device_serials=ignore_serials,
            x_pct=self.x_pct,
            y_pct=self.y_pct,
            width_px=self.width_var.get(),
            trigger=self.trigger_keys[self.trigger_combo.current()],
            low_threshold_pct=self.threshold_var.get(),
            picture=self.effect.picture,
            picture_animation=self.picture_anim_keys[self.picture_anim_combo.current()],
            sound=self.effect.sound,
            sound_cooldown_sec=self.effect.sound_cooldown_sec,
            enter_animation=self.enter_keys[self.enter_combo.current()],
            exit_animation=self.exit_keys[self.exit_combo.current()],
            nudge_group_id=nudge_group_id,
            duration_mode=self.duration_mode_var.get(),
            duration_sec=self.duration_sec_var.get(),
            chat_command=self.chat_command_entry.get().strip() or None,
            chat_permission=self.chat_permission_keys[self.chat_permission_combo.current()],
            text=self.text_entry.get(),
            text_position=self.text_pos_keys[self.text_pos_combo.current()],
            text_gap_px=self.text_gap_var.get(),
            font_family=self.font_combo.get() or "Segoe UI",
            font_size_px=self.font_size_var.get(),
            font_color=self.font_color_var["hex"],
            text_animation=self.text_anim_keys[self.text_anim_combo.current()],
            outline_enabled=self.outline_var.get(),
            outline_thickness_px=self.outline_thickness_var.get(),
            outline_color=self.outline_color_var["hex"],
        )

        for kind, attr in (("picture", "picture"), ("sound", "sound")):
            picked = self._pending_media.get(kind)
            if picked:
                rel = config_mod.import_media(effect.id, picked, kind)
                setattr(effect, attr, rel)

        if mode == "audio":
            self.audio_frame.commit_nickname(self.audio_nicknames, audio_id, audio_windows_name)

        self.result = effect
        self._stop_preview()
        self.destroy()


class MainWindow(tk.Tk):
    def __init__(self):
        super().__init__()
        # Stays withdrawn until fully built and themed - deiconify() at the
        # end of __init__ is itself the hide/show cycle the dark title bar
        # needs to actually render (see theme._apply_dark_titlebar's
        # docstring), so the window's first visible frame is already
        # correct instead of flashing light-then-dark.
        self.withdraw()
        self.cfg = config_mod.load()
        i18n.set_language(self.cfg.language)
        apply_language_style()
        self.dark_mode = self._resolve_dark_mode()
        theme.apply_theme(self.dark_mode)
        default_assets.ensure_defaults()
        bundled_icons.ensure_device_icons()
        self.vr_monitor = VRMonitor(poll_interval_sec=self.cfg.poll_interval_sec)
        self.vr_monitor.start()
        self.twitch_monitor = TwitchMonitor(get_config=lambda: self.cfg)
        self.twitch_monitor.start()
        self.audio_monitor = AudioMonitor(get_config=lambda: self.cfg)
        self.audio_monitor.start()
        self.hotkey_manager = HotkeyManager(self._on_hotkey)
        self._rebind_asked = set()
        self.server = ServerController(get_config=lambda: self.cfg, vr_monitor=self.vr_monitor, twitch_monitor=self.twitch_monitor, audio_monitor=self.audio_monitor)
        self._port_conflict = not self.server.start()
        self._port_flash_job = None
        self._port_tooltip = None
        self._tray_icon = None

        self.title(APP_TITLE)
        self.geometry("860x560")
        self.minsize(740, 480)
        theme.apply_window_theme(self, self.dark_mode)

        self._build()
        self._tick()
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self._refresh_url()
        self.deiconify()
        self._rebind_hotkeys()
        self.after(5000, self._check_audio_rebind)

        if not self.cfg.dismissed_battery_notice:
            self.after(200, self._show_battery_notice)
        else:
            self.after(200, self._maybe_check_new_icons)

    def _show_battery_notice(self):
        FirstRunNoticeDialog(self, self._on_battery_notice_dismissed)

    def _on_battery_notice_dismissed(self, dont_show_again, check_for_updates):
        changed = False
        if dont_show_again:
            self.cfg.dismissed_battery_notice = True
            changed = True
        if check_for_updates != self.cfg.check_for_updates:
            self.cfg.check_for_updates = check_for_updates
            changed = True
        if changed:
            config_mod.save(self.cfg)
        self._maybe_check_new_icons()

    def _maybe_check_new_icons(self):
        # Only re-scans once per APP_VERSION (persisted in cfg) so this never
        # nags again on every launch of the same build - but an update that
        # bundles further new icons always gets a fresh chance to ask, even
        # if the user said no (or yes) to a previous version's prompt.
        if self.cfg.icon_check_version == APP_VERSION:
            self._maybe_check_for_updates()
            return
        missing = bundled_icons.missing_icons()
        if missing:
            self._show_new_icons_prompt(missing)
        else:
            self.cfg.icon_check_version = APP_VERSION
            config_mod.save(self.cfg)
            self._maybe_check_for_updates()

    def _show_new_icons_prompt(self, missing):
        add_now = messagebox.askyesno(
            i18n.t("new_icons_prompt_title"),
            i18n.t("new_icons_prompt_body_fmt").format(n=len(missing)),
            parent=self,
        )
        if add_now:
            bundled_icons.copy_icons(missing)
        self.cfg.icon_check_version = APP_VERSION
        config_mod.save(self.cfg)
        self._maybe_check_for_updates()

    def _maybe_check_for_updates(self):
        if not self.cfg.check_for_updates:
            return
        threading.Thread(target=self._update_check_worker, daemon=True).start()

    def _update_check_worker(self):
        result = update_check.check_latest(APP_VERSION)
        if result:
            tag, url = result
            self.after(0, lambda: self._show_update_notice(tag, url))

    def _show_update_notice(self, tag, url):
        dlg = tk.Toplevel(self)
        dlg.withdraw()
        dlg.title(i18n.t_piqad("update_notice_title"))
        dlg.resizable(False, False)
        theme.apply_window_theme(dlg, self.dark_mode)
        frm = ttk.Frame(dlg)
        frm.pack(padx=18, pady=16)
        ttk.Label(frm, text=i18n.t("update_notice_body_fmt").format(version=tag), font=_default_font()).pack(anchor="w")
        link = ttk.Label(frm, text=url, foreground="#3d8bff", cursor="hand2", font=_default_font())
        link.pack(anchor="w", pady=(8, 0))
        link.bind("<Button-1>", lambda e: webbrowser.open(url))
        ttk.Button(frm, text=i18n.t_piqad("about_close"), command=dlg.destroy).pack(anchor="e", pady=(14, 0))
        dlg.transient(self)
        # transient() re-parents the window at the Win32 level, which resets
        # the DWM dark-titlebar attribute applied earlier - reapply after.
        theme.apply_window_theme(dlg, self.dark_mode)
        dlg.deiconify()

    # -- UI -----------------------------------------------------------
    def _build(self):
        top = ttk.Frame(self)
        top.pack(fill="x", padx=10, pady=8)

        self.steamvr_status_var = tk.StringVar(value=i18n.t("steamvr_checking"))
        ttk.Label(top, textvariable=self.steamvr_status_var, font=("Segoe UI", 10, "bold")).pack(side="left")

        right_box = ttk.Frame(top)
        right_box.pack(side="right")
        self.lang_combo, self._lang_keys = _build_language_combo(right_box, self._on_language_change)
        ttk.Button(right_box, text=i18n.t_piqad("btn_macros"), command=self._open_macros).pack(side="left", padx=(0, 4))
        self.twitch_btn = ttk.Button(right_box, command=self._on_twitch_button)
        self.twitch_btn.pack(side="left", padx=(0, 4))
        self._refresh_twitch_button()
        ttk.Button(right_box, text=i18n.t_piqad("about_btn"), command=self._show_about).pack(side="left")

        server_frame = ttk.Frame(self)
        server_frame.pack(fill="x", padx=10, pady=(0, 8))
        server_label = i18n.t_piqad("btn_stop_server") if self.server.running else i18n.t_piqad("btn_start_server")
        self.server_btn = ttk.Button(server_frame, text=server_label, command=self._toggle_server)
        self.server_btn.pack(side="left")
        self.url_var = tk.StringVar()
        entry = ttk.Entry(server_frame, textvariable=self.url_var, state="readonly", width=45)
        entry.pack(side="left", padx=8)
        ttk.Button(server_frame, text=i18n.t_piqad("btn_copy_url"), command=self._copy_url).pack(side="left")
        ttk.Button(server_frame, text=i18n.t_piqad("btn_open_browser"), command=self._open_url).pack(side="left", padx=4)

        self.port_warning_frame = ttk.Frame(self)
        self.port_warning_frame.pack(fill="x", padx=10, pady=(0, 4))
        self.port_warning_lbl = tk.Label(self.port_warning_frame, fg="#cc0000", font=("Segoe UI", 9, "bold"))
        self.use_free_port_btn = ttk.Button(self.port_warning_frame, text=i18n.t_piqad("btn_use_free_port"), command=self._use_free_port)
        self.use_free_port_btn.bind("<Enter>", self._show_port_tooltip)
        self.use_free_port_btn.bind("<Leave>", self._hide_port_tooltip)
        if self._port_conflict:
            self._show_port_warning()

        body = ttk.PanedWindow(self, orient="horizontal")
        body.pack(fill="both", expand=True, padx=10, pady=4)

        left = ttk.LabelFrame(body, text=i18n.t_piqad("panel_devices"))
        body.add(left, weight=1)
        self.device_tree = ttk.Treeview(left, columns=("class", "brand", "battery", "serial"), show="headings", height=10)
        self.device_tree.heading("class", text=i18n.t_piqad("col_class"))
        self.device_tree.heading("brand", text=i18n.t_piqad("col_brand"))
        self.device_tree.heading("battery", text=i18n.t_piqad("col_battery"))
        self.device_tree.heading("serial", text=i18n.t_piqad("col_serial"))
        for col, w in (("class", 120), ("brand", 90), ("battery", 90), ("serial", 150)):
            self.device_tree.column(col, width=w)
        self.device_tree.pack(fill="both", expand=True, padx=6, pady=6)

        right = ttk.LabelFrame(body, text=i18n.t_piqad("panel_items"))
        body.add(right, weight=2)
        self.item_tree = ttk.Treeview(right, columns=("type", "label", "device", "mode", "threshold"), show="headings", height=10)
        self.item_tree.heading("type", text=i18n.t_piqad("col_type"))
        self.item_tree.heading("label", text=i18n.t_piqad("col_label"))
        self.item_tree.heading("device", text=i18n.t_piqad("col_device"))
        self.item_tree.heading("mode", text=i18n.t_piqad("col_mode"))
        self.item_tree.heading("threshold", text=i18n.t_piqad("col_threshold"))
        for col, w in (("type", 60), ("label", 130), ("device", 140), ("mode", 110), ("threshold", 70)):
            self.item_tree.column(col, width=w)
        self.item_tree.pack(fill="both", expand=True, padx=6, pady=6)
        self.item_tree.bind("<Double-1>", lambda e: self._edit_selected())

        item_btns = ttk.Frame(right)
        item_btns.pack(fill="x", padx=6, pady=(0, 6))

        add_menu = tk.Menu(self, tearoff=0, font=_chrome_font())
        add_menu.add_command(label=i18n.t_piqad("menu_add_device"), command=self._add_item)
        add_menu.add_command(label=i18n.t_piqad("menu_add_effect"), command=self._add_effect)
        add_btn = ttk.Menubutton(item_btns, text=i18n.t_piqad("add_btn") + " ▾", menu=add_menu)
        add_btn.pack(side="left")

        ttk.Button(item_btns, text=i18n.t_piqad("btn_edit"), command=self._edit_selected).pack(side="left", padx=4)
        ttk.Button(item_btns, text=i18n.t_piqad("btn_remove"), command=self._remove_selected).pack(side="left")

        footer = ttk.Label(
            self, text=i18n.t_piqad("footer_hint"),
            wraplength=820, foreground="#666",
        )
        footer.pack(fill="x", padx=10, pady=(0, 8))

        self._refresh_item_tree()

    def _show_about(self):
        AboutDialog(self)

    # -- mute macros, hotkeys, moved-microphone detection ---------------
    def _open_macros(self):
        if not self.cfg.macro_token:
            self.cfg.macro_token = config_mod.new_macro_token()
            config_mod.save(self.cfg)
        MacrosDialog(self)

    def _rebind_hotkeys(self):
        self.hotkey_manager.set_bindings({m.id: m.hotkey for m in self.cfg.macros if m.hotkey and m.endpoint_id})

    def _on_hotkey(self, macro_id):
        """Runs on the hotkey thread; set_mute waits for the audio monitor."""
        macro = next((m for m in self.cfg.macros if m.id == macro_id), None)
        if macro is not None and macro.endpoint_id:
            self.audio_monitor.set_mute(macro.endpoint_id, macro.action)

    def _check_audio_rebind(self):
        """Every few seconds: if a saved microphone is gone but exactly one
        same-named one just appeared, the receiver was moved to another USB
        port (Windows issues a new device id) - offer to switch every Effect
        and macro over, once per pair per session."""
        try:
            if self.state() != "withdrawn" and self.grab_current() is None:
                saved = {}
                for ef in self.cfg.effects:
                    if ef.target_mode == "audio" and ef.audio_endpoint_id:
                        saved[ef.audio_endpoint_id] = ef.audio_name
                for m in self.cfg.macros:
                    if m.endpoint_id:
                        saved.setdefault(m.endpoint_id, m.endpoint_name)
                for old_id, new_id, name in audio_mod.find_rebind_candidates(saved) if saved else []:
                    if (old_id, new_id) in self._rebind_asked:
                        continue
                    self._rebind_asked.add((old_id, new_id))
                    shown = self.cfg.audio_nicknames.get(old_id, "").strip() or name
                    if messagebox.askyesno(i18n.t("dlg_title_audio_rebind"), i18n.t("msg_audio_rebind_fmt").format(name=shown), parent=self):
                        self._apply_audio_rebind(old_id, new_id, name)
        finally:
            self.after(5000, self._check_audio_rebind)

    def _apply_audio_rebind(self, old_id, new_id, windows_name):
        for ef in self.cfg.effects:
            if ef.audio_endpoint_id == old_id:
                ef.audio_endpoint_id = new_id
                ef.audio_name = windows_name
        for m in self.cfg.macros:
            if m.endpoint_id == old_id:
                m.endpoint_id = new_id
                m.endpoint_name = windows_name
        nick = self.cfg.audio_nicknames.pop(old_id, None)
        if nick and new_id not in self.cfg.audio_nicknames:
            self.cfg.audio_nicknames[new_id] = nick
        config_mod.save(self.cfg)
        self._refresh_item_tree()
        self._rebind_hotkeys()

    def _refresh_twitch_button(self):
        if self.cfg.twitch_connected and self.cfg.twitch_login:
            self.twitch_btn.configure(text=i18n.t_piqad("btn_twitch_connected_fmt").format(login=self.cfg.twitch_login))
        else:
            self.twitch_btn.configure(text=i18n.t_piqad("btn_twitch_connect"))

    def _on_twitch_button(self):
        if self.cfg.twitch_connected:
            if messagebox.askyesno(i18n.t_piqad("dlg_title_twitch_disconnect"), i18n.t_piqad("confirm_twitch_disconnect"), parent=self):
                self.cfg.twitch_connected = False
                self.cfg.twitch_login = None
                self.cfg.twitch_access_token = None
                self.cfg.twitch_refresh_token = None
                config_mod.save(self.cfg)
                self._refresh_twitch_button()
            return
        TwitchConnectDialog(self, self._on_twitch_connected)

    def _on_twitch_connected(self, login, access_token, refresh_token):
        self.cfg.twitch_connected = True
        self.cfg.twitch_login = login
        self.cfg.twitch_access_token = access_token
        self.cfg.twitch_refresh_token = refresh_token
        config_mod.save(self.cfg)
        self._refresh_twitch_button()

    def _resolve_dark_mode(self) -> bool:
        """cfg.theme "light"/"dark" is an explicit user override; "system"
        (the default) follows the OS setting, detected once at startup."""
        if self.cfg.theme == "dark":
            return True
        if self.cfg.theme == "light":
            return False
        return theme.detect_windows_dark_mode()

    def _on_language_change(self, event=None):
        idx = self.lang_combo.current()
        new_lang = self._lang_keys[idx]
        i18n.set_language(new_lang)
        apply_language_style()
        self.cfg.language = new_lang
        config_mod.save(self.cfg)
        self._rebuild_ui()

    def _rebuild_ui(self):
        if self._port_flash_job:
            self.after_cancel(self._port_flash_job)
            self._port_flash_job = None
        self._hide_port_tooltip()
        for child in list(self.winfo_children()):
            child.destroy()
        self._build()
        self._refresh_url()

    def _refresh_url(self):
        port = self.server.port or self.cfg.port
        self.url_var.set(f"http://127.0.0.1:{port}/overlay")

    def _toggle_server(self):
        if self.server.running:
            self.server.stop()
            self.server_btn.configure(text=i18n.t_piqad("btn_start_server"))
            self._port_conflict = False
            self._hide_port_warning()
        else:
            started = self.server.start()
            self._port_conflict = not started
            if started:
                self.server_btn.configure(text=i18n.t_piqad("btn_stop_server"))
                self._hide_port_warning()
            else:
                self._show_port_warning()
        self._refresh_url()

    def _show_port_warning(self):
        self.port_warning_lbl.pack(side="left")
        self.use_free_port_btn.pack(side="left", padx=8)
        self._flash_port_warning()

    def _hide_port_warning(self):
        if self._port_flash_job:
            self.after_cancel(self._port_flash_job)
            self._port_flash_job = None
        self.port_warning_lbl.pack_forget()
        self.use_free_port_btn.pack_forget()

    def _flash_port_warning(self):
        current = self.port_warning_lbl.cget("fg")
        next_color = "#ff6b6b" if current == "#cc0000" else "#cc0000"
        self.port_warning_lbl.configure(fg=next_color, text=i18n.t("warn_port_in_use"))
        self._port_flash_job = self.after(600, self._flash_port_warning)

    def _show_port_tooltip(self, event=None):
        if self._port_tooltip:
            return
        x = self.use_free_port_btn.winfo_rootx()
        y = self.use_free_port_btn.winfo_rooty() + self.use_free_port_btn.winfo_height() + 4
        tip = tk.Toplevel(self)
        tip.wm_overrideredirect(True)
        tip.wm_geometry(f"+{x}+{y}")
        tk.Label(
            tip, text=i18n.t("tooltip_use_free_port"), background="#ffffe0",
            relief="solid", borderwidth=1, font=("Segoe UI", 8),
            wraplength=260, justify="left", padx=6, pady=4,
        ).pack()
        self._port_tooltip = tip

    def _hide_port_tooltip(self, event=None):
        if self._port_tooltip:
            self._port_tooltip.destroy()
            self._port_tooltip = None

    def _use_free_port(self):
        from . import server as server_mod
        self._hide_port_tooltip()
        self.cfg.port = server_mod.find_free_port()
        config_mod.save(self.cfg)
        started = self.server.start()
        self._port_conflict = not started
        if started:
            self.server_btn.configure(text=i18n.t_piqad("btn_stop_server"))
            self._hide_port_warning()
        self._refresh_url()

    def _copy_url(self):
        self.clipboard_clear()
        self.clipboard_append(self.url_var.get())

    def _open_url(self):
        webbrowser.open(self.url_var.get())

    def _refresh_item_tree(self):
        self.item_tree.delete(*self.item_tree.get_children())
        for it in self.cfg.items:
            mode = i18n.t("mode_always") if it.show_mode == "always" else i18n.t("mode_low_only")
            self.item_tree.insert("", "end", iid=f"dev:{it.id}", values=(i18n.t("type_device"), it.label, it.device_serial, mode, f"{it.low_threshold_pct}%"))
        for ef in self.cfg.effects:
            trig = i18n.t(f"trigger_{ef.trigger}")
            if ef.target_mode == "audio":
                device_display = audio_mod.display_name(ef.audio_endpoint_id or "", ef.audio_name, self.cfg.audio_nicknames)
            else:
                device_display = ef.device_serial if ef.target_mode == "specific" else i18n.t(f"targetmode_{ef.target_mode}")
            if ef.trigger in ("battery_low", "battery_normal"):
                thresh = f"{ef.low_threshold_pct}%"
            elif ef.trigger == "audio_silent":
                thresh = f"{ef.audio_silent_sec}s"
            else:
                thresh = "-"
            self.item_tree.insert("", "end", iid=f"fx:{ef.id}", values=(i18n.t("type_effect"), ef.label, device_display, trig, thresh))

    def _all_positionables(self):
        """Every placed thing (devices + effects), for canvas snapping/display.
        Anything in a Nudge group (Device items and Effects alike) is
        resolved to the group's shared position, so the preview/snapping
        reflects where they actually render."""
        groups_by_id = {g.id: g for g in self.cfg.nudge_groups}
        result = []
        for it in self.cfg.items:
            group = groups_by_id.get(it.nudge_group_id) if it.nudge_group_id else None
            x_pct = group.x_pct if group else it.x_pct
            y_pct = group.y_pct if group else it.y_pct
            result.append(SimpleNamespace(id=it.id, label=it.label, x_pct=x_pct, y_pct=y_pct, width_px=it.width_px))
        for ef in self.cfg.effects:
            group = groups_by_id.get(ef.nudge_group_id) if ef.nudge_group_id else None
            x_pct = group.x_pct if group else ef.x_pct
            y_pct = group.y_pct if group else ef.y_pct
            result.append(SimpleNamespace(id=ef.id, label=ef.label, x_pct=x_pct, y_pct=y_pct, width_px=ef.width_px))
        return result

    def _selected_entry(self):
        sel = self.item_tree.selection()
        if not sel:
            return None, None
        iid = sel[0]
        if iid.startswith("dev:"):
            item_id = iid[4:]
            return "device", next((it for it in self.cfg.items if it.id == item_id), None)
        if iid.startswith("fx:"):
            effect_id = iid[3:]
            return "effect", next((ef for ef in self.cfg.effects if ef.id == effect_id), None)
        return None, None

    def _used_device_serials(self, exclude_id=None):
        """Serials already tied to an existing Device item or a specific-
        target Effect, so the Add dialogs can hide them by default (a
        device already used elsewhere is usually not what you want to
        double-book) - excluding the item currently being edited, if any."""
        used = set()
        for it in self.cfg.items:
            if it.id != exclude_id and it.device_serial:
                used.add(it.device_serial)
        for ef in self.cfg.effects:
            if ef.id != exclude_id and ef.target_mode == "specific" and ef.device_serial:
                used.add(ef.device_serial)
        return used

    def _add_item(self):
        new_item = config_mod.OverlayItem(id=config_mod.new_item_id(), label="", device_serial="")
        dlg = ItemEditorDialog(self, self.vr_monitor, new_item, self._all_positionables(), preview_state=self.server.preview_state, nudge_groups=self.cfg.nudge_groups, exclude_serials=self._used_device_serials(), sync_groups=self.cfg.sync_groups)
        self.wait_window(dlg)
        if dlg.result:
            self.cfg.items.append(dlg.result)
            config_mod.save(self.cfg)
            self._refresh_item_tree()

    def _add_effect(self):
        new_effect = config_mod.EffectItem(id=config_mod.new_effect_id(), label="", device_serial="")
        dlg = EffectEditorDialog(self, self.vr_monitor, new_effect, self._all_positionables(), preview_state=self.server.preview_state, nudge_groups=self.cfg.nudge_groups, exclude_serials=self._used_device_serials(), twitch_connected=self.cfg.twitch_connected, audio_nicknames=self.cfg.audio_nicknames)
        self.wait_window(dlg)
        if dlg.result:
            self.cfg.effects.append(dlg.result)
            config_mod.save(self.cfg)
            self._refresh_item_tree()

    def _edit_selected(self):
        kind, obj = self._selected_entry()
        if not obj:
            messagebox.showinfo(i18n.t("msg_select_item_title"), i18n.t("msg_select_item_body"))
            return
        others = [p for p in self._all_positionables() if p.id != obj.id]
        exclude_serials = self._used_device_serials(exclude_id=obj.id)
        if kind == "device":
            dlg = ItemEditorDialog(self, self.vr_monitor, obj, others, preview_state=self.server.preview_state, nudge_groups=self.cfg.nudge_groups, exclude_serials=exclude_serials, sync_groups=self.cfg.sync_groups)
            self.wait_window(dlg)
            if dlg.result:
                idx = next(i for i, it in enumerate(self.cfg.items) if it.id == obj.id)
                self.cfg.items[idx] = dlg.result
                config_mod.save(self.cfg)
                self._refresh_item_tree()
        else:
            dlg = EffectEditorDialog(self, self.vr_monitor, obj, others, preview_state=self.server.preview_state, nudge_groups=self.cfg.nudge_groups, exclude_serials=exclude_serials, twitch_connected=self.cfg.twitch_connected, audio_nicknames=self.cfg.audio_nicknames)
            self.wait_window(dlg)
            if dlg.result:
                idx = next(i for i, ef in enumerate(self.cfg.effects) if ef.id == obj.id)
                self.cfg.effects[idx] = dlg.result
                config_mod.save(self.cfg)
                self._refresh_item_tree()

    def _remove_selected(self):
        kind, obj = self._selected_entry()
        if not obj:
            return
        title = i18n.t("msg_remove_device_title") if kind == "device" else i18n.t("msg_remove_effect_title")
        if not messagebox.askyesno(title, i18n.t("msg_remove_body_fmt").format(label=obj.label)):
            return
        if kind == "device":
            self.cfg.items = [it for it in self.cfg.items if it.id != obj.id]
        else:
            self.cfg.effects = [ef for ef in self.cfg.effects if ef.id != obj.id]
        config_mod.save(self.cfg)
        self._refresh_item_tree()

    # -- polling loop ---------------------------------------------------
    def _tick(self):
        snapshot = self.vr_monitor.get_snapshot()
        # The SteamVR Service pseudo-device (for a Disconnected/Connected
        # Effect trigger on SteamVR itself) isn't a piece of hardware - keep
        # it out of the visible device count/list, which is about what's
        # actually plugged in.
        real_devices = {s: d for s, d in snapshot.devices.items() if d.device_class != "Service"}
        if snapshot.steamvr_connected:
            self.steamvr_status_var.set(i18n.t("steamvr_connected_fmt").format(n=len(real_devices)))
        else:
            msg = snapshot.error or i18n.t("steamvr_not_detected")
            self.steamvr_status_var.set(f"{i18n.t('steamvr_prefix')} {msg}")

        self.device_tree.delete(*self.device_tree.get_children())
        for serial, dev in real_devices.items():
            cls = i18n.t(f"devclass_{dev.device_class}")
            if dev.role:
                cls += f" {dev.role}"
            batt = _battery_display(dev)
            self.device_tree.insert("", "end", values=(cls, _display_brand(dev.manufacturer) or "-", batt, serial))

        self.after(1500, self._tick)

    def _on_close(self):
        if self.cfg.close_action == "ask":
            CloseActionDialog(self, self._on_close_action_chosen)
            return
        if self.cfg.close_action == "tray":
            self._minimize_to_tray()
            return
        self._exit_app()

    def _on_close_action_chosen(self, action):
        self.cfg.close_action = action
        config_mod.save(self.cfg)
        if action == "tray":
            self._minimize_to_tray()
        else:
            self._exit_app()

    def _minimize_to_tray(self):
        self.withdraw()
        if self._tray_icon is None:
            self._start_tray_icon()

    def _start_tray_icon(self):
        import pystray
        menu = pystray.Menu(
            pystray.MenuItem(i18n.t_piqad("tray_show"), self._on_tray_show, default=True),
            pystray.MenuItem(i18n.t_piqad("tray_exit"), self._on_tray_exit),
        )
        self._tray_icon = pystray.Icon("OhFudgeMyBatteryChat", default_assets.tray_icon_image(), APP_TITLE, menu)
        threading.Thread(target=self._tray_icon.run, daemon=True).start()

    def _on_tray_show(self, icon=None, item=None):
        # pystray invokes menu actions on its own thread - Tkinter widgets
        # must only be touched from the main thread, so hop back via after().
        self.after(0, self._show_from_tray)

    def _show_from_tray(self):
        self.deiconify()
        self.lift()
        self.focus_force()

    def _on_tray_exit(self, icon=None, item=None):
        self.after(0, self._exit_app)

    def _exit_app(self):
        if self._tray_icon is not None:
            self._tray_icon.stop()
            self._tray_icon = None
        self.server.stop()
        self.vr_monitor.stop()
        self.twitch_monitor.stop()
        self.hotkey_manager.stop()
        self.audio_monitor.stop()
        self.destroy()


def main():
    app = MainWindow()
    app.mainloop()
