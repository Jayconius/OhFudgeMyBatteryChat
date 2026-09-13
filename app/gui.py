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
import tkinter as tk
import webbrowser
from tkinter import colorchooser, filedialog, messagebox, ttk

from . import config as config_mod
from . import default_assets
from . import i18n
from . import piqad
from .server import ServerController
from .vr_monitor import VRMonitor

APP_TITLE = "Oh Fudge, My Battery Chat!"  # the pun stays the same in every language
APP_VERSION = "1.0.0"
APP_AUTHOR = "Your Name Here"  # TODO: replace with your name/handle
APP_GITHUB_URL = "https://github.com/yourusername/oh-fudge-my-battery-chat"  # TODO: replace with your real repo

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
    """Base stations are mains/USB-powered - no battery to report, ever.
    Say so plainly instead of showing the same 'n/a' a real read failure would."""
    if dev.device_class == "TrackingReference":
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


def _device_display(serial, dev):
    cls = i18n.t(f"devclass_{dev.device_class}")
    role = f" {dev.role}" if dev.role else ""
    batt = _battery_display(dev)
    brand_model = _brand_model_text(dev)
    model = f" ({brand_model})" if brand_model else ""
    return f"{cls}{role}{model} - {batt} - {serial}"


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
        self.title(i18n.t("about_title"))
        self.resizable(False, False)

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

        ttk.Button(frm, text=i18n.t_piqad("about_close"), command=self.destroy).pack(anchor="e", pady=(14, 0))

        self.grab_set()
        self.transient(parent)


class FirstRunNoticeDialog(tk.Toplevel):
    """Shown once (unless dismissed) to explain that some devices report
    battery in bursts rather than continuously - not a bug in this app.

    Includes its own language switcher: this can appear before the user has
    ever touched the main window, so they shouldn't be stuck reading it in
    the wrong language until they close it."""

    def __init__(self, parent, on_dismiss):
        super().__init__(parent)
        self.main_window = parent
        self.on_dismiss = on_dismiss
        self._lang_changed = False
        self.resizable(False, False)

        lang_row = ttk.Frame(self)
        lang_row.pack(fill="x", padx=18, pady=(14, 0))
        self.lang_combo, self._lang_keys = _build_language_combo(lang_row, self._on_language_change)

        self.body_frame = ttk.Frame(self)
        self.body_frame.pack(padx=18, pady=16)
        self._dont_show_state = False
        self._build_body()

        self.protocol("WM_DELETE_WINDOW", self._on_ok)
        self.grab_set()
        self.transient(parent)

    def _build_body(self):
        self.title(i18n.t_piqad("notice_title"))
        for w in self.body_frame.winfo_children():
            w.destroy()
        frm = self.body_frame
        ttk.Label(frm, text=i18n.t_piqad("notice_title"), font=(_chrome_font_family(), 12, "bold")).pack(anchor="w")
        ttk.Label(frm, text=i18n.t_piqad("notice_battery_chunks_body"), wraplength=440, justify="left").pack(anchor="w", pady=(10, 12))

        self.dont_show_var = tk.BooleanVar(value=self._dont_show_state)
        ttk.Checkbutton(frm, text=i18n.t_piqad("chk_dont_show_again"), variable=self.dont_show_var).pack(anchor="w")

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
        self._build_body()

    def _on_ok(self):
        self.on_dismiss(self.dont_show_var.get())
        self.destroy()
        if self._lang_changed:
            self.main_window._rebuild_ui()


class DeviceSelectorMixin:
    """Shared 'pick a live SteamVR device, or type a serial manually' UI."""

    def _build_device_selector(self, parent, current_serial):
        device_frame = ttk.LabelFrame(parent, text=i18n.t_piqad("frame_device"))

        self.manual_var = tk.BooleanVar(value=False)
        snapshot = self.vr_monitor.get_snapshot()
        self._live_devices = snapshot.devices
        self._device_values = [_device_display(s, d) for s, d in snapshot.devices.items()]
        self._device_serials = list(snapshot.devices.keys())

        self.device_combo = ttk.Combobox(device_frame, values=self._device_values, width=55, state="readonly")
        self.device_combo.grid(row=0, column=0, padx=6, pady=4, sticky="ew")
        if current_serial in self._device_serials:
            self.device_combo.current(self._device_serials.index(current_serial))

        ttk.Button(device_frame, text=i18n.t_piqad("btn_refresh"), command=self._refresh_devices).grid(row=0, column=1, padx=4)

        ttk.Checkbutton(
            device_frame, text=i18n.t_piqad("chk_manual_serial"),
            variable=self.manual_var, command=self._toggle_manual,
        ).grid(row=1, column=0, columnspan=2, sticky="w", padx=6)

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

    def _refresh_devices(self):
        snapshot = self.vr_monitor.get_snapshot()
        self._live_devices = snapshot.devices
        self._device_values = [_device_display(s, d) for s, d in snapshot.devices.items()]
        self._device_serials = list(snapshot.devices.keys())
        self.device_combo.configure(values=self._device_values)

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
        return serial, self._live_devices[serial].device_class


class MediaPickerMixin:
    """Shared 'choose a file, show its name, test sounds' row builder.
    Requires self._pending_media (dict kind -> chosen path or None)."""

    def _media_row(self, parent, row, text, kind, current_rel, sound=False):
        ttk.Label(parent, text=text).grid(row=row, column=0, sticky="w", padx=6, pady=3)
        current_full = config_mod.resolve_media(current_rel)
        display = os.path.basename(current_full) if current_full else "(default)"
        lbl = ttk.Label(parent, text=display, width=28)
        lbl.grid(row=row, column=1, sticky="w", padx=6)
        ttk.Button(parent, text=i18n.t_piqad("btn_choose"), command=lambda: self._choose_media(kind, lbl, sound)).grid(row=row, column=2, padx=4)
        if sound:
            ttk.Button(parent, text=i18n.t_piqad("btn_test"), command=lambda: self._test_sound(kind, current_rel)).grid(row=row, column=3, padx=4)
        return lbl

    def _choose_media(self, kind, label_widget, sound):
        types = SOUND_FILETYPES if sound else IMAGE_FILETYPES
        path = filedialog.askopenfilename(title=i18n.t("btn_choose"), filetypes=types, parent=self)
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


class ItemEditorDialog(DeviceSelectorMixin, MediaPickerMixin, AnimationPickerMixin, PositionCanvasMixin, PreviewMixin, tk.Toplevel):
    def __init__(self, parent, vr_monitor: VRMonitor, item: config_mod.OverlayItem, other_items, preview_state=None):
        super().__init__(parent)
        self.title(i18n.t("dlg_title_device"))
        self.resizable(False, False)
        self.vr_monitor = vr_monitor
        self.item = item
        self.other_items = other_items
        self.result = None
        self._init_preview(preview_state)
        self._pending_media = {"normal": None, "low": None, "sound": None}

        self._build()
        self.protocol("WM_DELETE_WINDOW", self._on_cancel)
        self.grab_set()
        self.transient(parent)

    def _build(self):
        pad = {"padx": 8, "pady": 4}

        device_frame = self._build_device_selector(self, self.item.device_serial)
        device_frame.grid(row=0, column=0, columnspan=2, sticky="ew", **pad)

        basics = ttk.LabelFrame(self, text=i18n.t_piqad("frame_basics"))
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

        self.show_label_var = tk.BooleanVar(value=self.item.show_label)
        self.show_percent_var = tk.BooleanVar(value=self.item.show_percent)
        ttk.Checkbutton(basics, text=i18n.t_piqad("chk_show_label"), variable=self.show_label_var).grid(row=4, column=0, sticky="w", padx=6)
        ttk.Checkbutton(basics, text=i18n.t_piqad("chk_show_percent"), variable=self.show_percent_var).grid(row=4, column=1, sticky="w", padx=6)

        self.anim_frame = self._build_animation_frame(self, i18n.t_piqad("frame_pop_animation_device"), self.item.enter_animation, self.item.exit_animation)
        self.anim_frame.grid(row=2, column=0, columnspan=2, sticky="ew", **pad)

        for var in (self.show_label_var, self.show_percent_var):
            var.trace_add("write", lambda *a: self._push_preview_if_active())
        self.label_entry.bind("<KeyRelease>", lambda e: self._push_preview_if_active())

        media = ttk.LabelFrame(self, text=i18n.t_piqad("frame_media"))
        media.grid(row=3, column=0, columnspan=2, sticky="ew", **pad)
        self._media_row(media, 0, i18n.t_piqad("lbl_normal_pic"), "normal", self.item.normal_image)
        self._media_row(media, 1, i18n.t_piqad("lbl_low_pic"), "low", self.item.low_image)
        self._media_row(media, 2, i18n.t_piqad("lbl_warning_sound"), "sound", self.item.sound, sound=True)

        pos_frame = self._build_position_frame(self, self.item.id, self.item.x_pct, self.item.y_pct, self.item.width_px)
        pos_frame.grid(row=4, column=0, columnspan=2, sticky="ew", **pad)

        btns = ttk.Frame(self)
        btns.grid(row=5, column=0, columnspan=2, sticky="e", padx=8, pady=10)
        ttk.Button(btns, text=i18n.t_piqad("btn_cancel"), command=self._on_cancel).pack(side="right", padx=4)
        ttk.Button(btns, text=i18n.t_piqad("btn_save"), command=self._on_save).pack(side="right", padx=4)

        self._update_anim_frame_visibility()

    def _on_media_changed(self, kind):
        if kind == "low":
            self._push_preview_if_active()

    def _update_anim_frame_visibility(self):
        if self.mode_var.get() == "low_only":
            self.anim_frame.grid()
        else:
            self.anim_frame.grid_remove()
            self._stop_preview()

    def _current_preview_payload(self):
        low_path = self._pending_media.get("low") or config_mod.resolve_media(self.item.low_image)
        return {
            "active": True,
            "mode": "device",
            "x_pct": self.x_pct,
            "y_pct": self.y_pct,
            "width_px": self.width_var.get(),
            "enter": self.enter_keys[self.enter_combo.current()],
            "exit": self.exit_keys[self.exit_combo.current()],
            "label": self.label_entry.get().strip() or "Preview",
            "show_label": self.show_label_var.get(),
            "show_percent": self.show_percent_var.get(),
            "low_path": low_path,
            "device_class_hint": self.item.device_class_hint or "Other",
        }

    def _on_cancel(self):
        self._stop_preview()
        self.destroy()

    def _on_save(self):
        resolved = self._resolve_device_selection(self.item.device_class_hint or "Other")
        if resolved is None:
            return
        serial, device_class_hint = resolved
        label = self.label_entry.get().strip() or serial

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
            sound=self.item.sound,
            sound_cooldown_sec=self.item.sound_cooldown_sec,
            show_label=self.show_label_var.get(),
            show_percent=self.show_percent_var.get(),
            enter_animation=self.enter_keys[self.enter_combo.current()],
            exit_animation=self.exit_keys[self.exit_combo.current()],
        )

        for kind, attr in (("normal", "normal_image"), ("low", "low_image"), ("sound", "sound")):
            picked = self._pending_media.get(kind)
            if picked:
                rel = config_mod.import_media(item.id, picked, kind)
                setattr(item, attr, rel)

        self.result = item
        self._stop_preview()
        self.destroy()


class EffectEditorDialog(DeviceSelectorMixin, MediaPickerMixin, AnimationPickerMixin, PositionCanvasMixin, PreviewMixin, tk.Toplevel):
    def __init__(self, parent, vr_monitor: VRMonitor, effect: config_mod.EffectItem, other_items, preview_state=None):
        super().__init__(parent)
        self.title(i18n.t("dlg_title_effect"))
        self.resizable(False, False)
        self.vr_monitor = vr_monitor
        self.effect = effect
        self.other_items = other_items
        self.result = None
        self._init_preview(preview_state)
        self._pending_media = {"picture": None, "sound": None}

        self._build()
        self.protocol("WM_DELETE_WINDOW", self._on_cancel)
        self.grab_set()
        self.transient(parent)

    def _build(self):
        pad = {"padx": 8, "pady": 4}

        target_frame = self._build_target_frame(self)
        target_frame.grid(row=0, column=0, columnspan=2, sticky="ew", **pad)

        basics = ttk.LabelFrame(self, text=i18n.t_piqad("frame_basics"))
        basics.grid(row=1, column=0, columnspan=2, sticky="ew", **pad)
        ttk.Label(basics, text=i18n.t_piqad("lbl_label")).grid(row=0, column=0, sticky="w", padx=6)
        self.label_entry = ttk.Entry(basics, width=30)
        self.label_entry.insert(0, self.effect.label)
        self.label_entry.grid(row=0, column=1, sticky="w", padx=6, pady=4)

        ttk.Label(basics, text=i18n.t_piqad("lbl_trigger")).grid(row=1, column=0, sticky="w", padx=6)
        self.trigger_keys = list(config_mod.TRIGGER_OPTIONS.keys())
        self.trigger_combo = ttk.Combobox(basics, values=[i18n.t(f"trigger_{k}") for k in self.trigger_keys], state="readonly", width=26)
        self.trigger_combo.grid(row=1, column=1, sticky="w", padx=6)
        self.trigger_combo.current(self.trigger_keys.index(self.effect.trigger) if self.effect.trigger in self.trigger_keys else 0)

        ttk.Label(basics, text=i18n.t_piqad("lbl_battery_threshold")).grid(row=2, column=0, sticky="w", padx=6)
        self.threshold_var = tk.IntVar(value=self.effect.low_threshold_pct)
        ttk.Spinbox(basics, from_=1, to=99, textvariable=self.threshold_var, width=6).grid(row=2, column=1, sticky="w", padx=6)
        ttk.Label(basics, text=i18n.t_piqad("hint_threshold_effect"), foreground="#666").grid(row=2, column=2, sticky="w")

        self.anim_frame = self._build_animation_frame(self, i18n.t_piqad("frame_pop_animation_effect"), self.effect.enter_animation, self.effect.exit_animation)
        self.anim_frame.grid(row=2, column=0, columnspan=2, sticky="ew", **pad)

        self.label_entry.bind("<KeyRelease>", lambda e: self._push_preview_if_active())

        media = ttk.LabelFrame(self, text=i18n.t_piqad("frame_media"))
        media.grid(row=3, column=0, columnspan=2, sticky="ew", **pad)
        self._media_row(media, 0, i18n.t_piqad("lbl_picture"), "picture", self.effect.picture)
        self._media_row(media, 1, i18n.t_piqad("lbl_warning_sound"), "sound", self.effect.sound, sound=True)

        text_frame = ttk.LabelFrame(self, text=i18n.t_piqad("frame_caption"))
        text_frame.grid(row=4, column=0, columnspan=2, sticky="ew", **pad)

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

        ttk.Label(text_frame, text=i18n.t_piqad("lbl_font")).grid(row=2, column=0, sticky="w", padx=6, pady=3)
        self.font_combo = ttk.Combobox(text_frame, values=FONT_CHOICES, state="normal", width=18)
        self.font_combo.set(self.effect.font_family)
        self.font_combo.grid(row=2, column=1, sticky="w", padx=6)
        self.font_combo.bind("<<ComboboxSelected>>", lambda e: self._push_preview_if_active())
        self.font_combo.bind("<KeyRelease>", lambda e: self._push_preview_if_active())

        ttk.Label(text_frame, text=i18n.t_piqad("lbl_size")).grid(row=2, column=2, sticky="w", padx=6)
        self.font_size_var = tk.IntVar(value=self.effect.font_size_px)
        ttk.Spinbox(text_frame, from_=8, to=96, textvariable=self.font_size_var, width=5, command=self._push_preview_if_active).grid(row=2, column=3, sticky="w", padx=6)

        ttk.Label(text_frame, text=i18n.t_piqad("lbl_font_color")).grid(row=3, column=0, sticky="w", padx=6, pady=3)
        self.font_color_btn, self.font_color_var = _make_color_button(text_frame, self.effect.font_color, self._push_preview_if_active)
        self.font_color_btn.grid(row=3, column=1, sticky="w", padx=6)

        self.outline_var = tk.BooleanVar(value=self.effect.outline_enabled)
        ttk.Checkbutton(text_frame, text=i18n.t_piqad("chk_outline"), variable=self.outline_var, command=self._push_preview_if_active).grid(row=3, column=2, sticky="w", padx=6)

        ttk.Label(text_frame, text=i18n.t_piqad("lbl_thickness")).grid(row=4, column=0, sticky="w", padx=6, pady=3)
        self.outline_thickness_var = tk.IntVar(value=self.effect.outline_thickness_px)
        ttk.Spinbox(text_frame, from_=1, to=10, textvariable=self.outline_thickness_var, width=5, command=self._push_preview_if_active).grid(row=4, column=1, sticky="w", padx=6)

        ttk.Label(text_frame, text=i18n.t_piqad("lbl_outline_color")).grid(row=4, column=2, sticky="w", padx=6)
        self.outline_color_btn, self.outline_color_var = _make_color_button(text_frame, self.effect.outline_color, self._push_preview_if_active)
        self.outline_color_btn.grid(row=4, column=3, sticky="w", padx=6)

        pos_frame = self._build_position_frame(self, self.effect.id, self.effect.x_pct, self.effect.y_pct, self.effect.width_px)
        pos_frame.grid(row=5, column=0, columnspan=2, sticky="ew", **pad)

        btns = ttk.Frame(self)
        btns.grid(row=6, column=0, columnspan=2, sticky="e", padx=8, pady=10)
        ttk.Button(btns, text=i18n.t_piqad("btn_cancel"), command=self._on_cancel).pack(side="right", padx=4)
        ttk.Button(btns, text=i18n.t_piqad("btn_save"), command=self._on_save).pack(side="right", padx=4)

        self._update_target_mode_visibility()

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

        self.device_frame = self._build_device_selector(frame, self.effect.device_serial)
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
        if mode == "specific":
            self.device_frame.grid()
            self.ignore_frame.grid_remove()
        else:
            self.device_frame.grid_remove()
            self.ignore_frame.grid()
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
            "device_class_hint": self.effect.device_class_hint or "Other",
            "text": self.text_entry.get(),
            "text_position": self.text_pos_keys[self.text_pos_combo.current()],
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
        else:
            serial = ""
            device_class_hint = self.effect.device_class_hint or "Other"
            ignore_serials = self._resolve_ignore_selections()

        default_label = serial if mode == "specific" else i18n.t(f"targetmode_{mode}")
        label = self.label_entry.get().strip() or default_label

        effect = config_mod.EffectItem(
            id=self.effect.id,
            label=label,
            device_serial=serial,
            device_class_hint=device_class_hint,
            target_mode=mode,
            ignore_device_serials=ignore_serials,
            x_pct=self.x_pct,
            y_pct=self.y_pct,
            width_px=self.width_var.get(),
            trigger=self.trigger_keys[self.trigger_combo.current()],
            low_threshold_pct=self.threshold_var.get(),
            picture=self.effect.picture,
            sound=self.effect.sound,
            sound_cooldown_sec=self.effect.sound_cooldown_sec,
            enter_animation=self.enter_keys[self.enter_combo.current()],
            exit_animation=self.exit_keys[self.exit_combo.current()],
            text=self.text_entry.get(),
            text_position=self.text_pos_keys[self.text_pos_combo.current()],
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

        self.result = effect
        self._stop_preview()
        self.destroy()


class MainWindow(tk.Tk):
    def __init__(self):
        super().__init__()
        self.cfg = config_mod.load()
        i18n.set_language(self.cfg.language)
        apply_language_style()
        default_assets.ensure_defaults()
        self.vr_monitor = VRMonitor(poll_interval_sec=self.cfg.poll_interval_sec)
        self.vr_monitor.start()
        self.server = ServerController(get_config=lambda: self.cfg, vr_monitor=self.vr_monitor)
        self.server.start()

        self.title(APP_TITLE)
        self.geometry("860x560")
        self.minsize(740, 480)

        self._build()
        self._tick()
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self._refresh_url()

        if not self.cfg.dismissed_battery_notice:
            self.after(200, self._show_battery_notice)

    def _show_battery_notice(self):
        FirstRunNoticeDialog(self, self._on_battery_notice_dismissed)

    def _on_battery_notice_dismissed(self, dont_show_again):
        if dont_show_again:
            self.cfg.dismissed_battery_notice = True
            config_mod.save(self.cfg)

    # -- UI -----------------------------------------------------------
    def _build(self):
        top = ttk.Frame(self)
        top.pack(fill="x", padx=10, pady=8)

        self.steamvr_status_var = tk.StringVar(value=i18n.t("steamvr_checking"))
        ttk.Label(top, textvariable=self.steamvr_status_var, font=("Segoe UI", 10, "bold")).pack(side="left")

        right_box = ttk.Frame(top)
        right_box.pack(side="right")
        self.lang_combo, self._lang_keys = _build_language_combo(right_box, self._on_language_change)
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

    def _on_language_change(self, event=None):
        idx = self.lang_combo.current()
        new_lang = self._lang_keys[idx]
        i18n.set_language(new_lang)
        apply_language_style()
        self.cfg.language = new_lang
        config_mod.save(self.cfg)
        self._rebuild_ui()

    def _rebuild_ui(self):
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
        else:
            self.server.start()
            self.server_btn.configure(text=i18n.t_piqad("btn_stop_server"))
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
            device_display = ef.device_serial if ef.target_mode == "specific" else i18n.t(f"targetmode_{ef.target_mode}")
            thresh = f"{ef.low_threshold_pct}%" if ef.trigger in ("battery_low", "battery_normal") else "-"
            self.item_tree.insert("", "end", iid=f"fx:{ef.id}", values=(i18n.t("type_effect"), ef.label, device_display, trig, thresh))

    def _all_positionables(self):
        """Every placed thing (devices + effects), for canvas snapping/display."""
        return list(self.cfg.items) + list(self.cfg.effects)

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

    def _add_item(self):
        new_item = config_mod.OverlayItem(id=config_mod.new_item_id(), label="", device_serial="")
        dlg = ItemEditorDialog(self, self.vr_monitor, new_item, self._all_positionables(), preview_state=self.server.preview_state)
        self.wait_window(dlg)
        if dlg.result:
            self.cfg.items.append(dlg.result)
            config_mod.save(self.cfg)
            self._refresh_item_tree()

    def _add_effect(self):
        new_effect = config_mod.EffectItem(id=config_mod.new_effect_id(), label="", device_serial="")
        dlg = EffectEditorDialog(self, self.vr_monitor, new_effect, self._all_positionables(), preview_state=self.server.preview_state)
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
        if kind == "device":
            dlg = ItemEditorDialog(self, self.vr_monitor, obj, others, preview_state=self.server.preview_state)
            self.wait_window(dlg)
            if dlg.result:
                idx = next(i for i, it in enumerate(self.cfg.items) if it.id == obj.id)
                self.cfg.items[idx] = dlg.result
                config_mod.save(self.cfg)
                self._refresh_item_tree()
        else:
            dlg = EffectEditorDialog(self, self.vr_monitor, obj, others, preview_state=self.server.preview_state)
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
        if snapshot.steamvr_connected:
            self.steamvr_status_var.set(i18n.t("steamvr_connected_fmt").format(n=len(snapshot.devices)))
        else:
            msg = snapshot.error or i18n.t("steamvr_not_detected")
            self.steamvr_status_var.set(f"{i18n.t('steamvr_prefix')} {msg}")

        self.device_tree.delete(*self.device_tree.get_children())
        for serial, dev in snapshot.devices.items():
            cls = i18n.t(f"devclass_{dev.device_class}")
            if dev.role:
                cls += f" {dev.role}"
            batt = _battery_display(dev)
            self.device_tree.insert("", "end", values=(cls, _display_brand(dev.manufacturer) or "-", batt, serial))

        self.after(1500, self._tick)

    def _on_close(self):
        self.server.stop()
        self.vr_monitor.stop()
        self.destroy()


def main():
    app = MainWindow()
    app.mainloop()
