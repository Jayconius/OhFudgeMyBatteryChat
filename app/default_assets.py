"""Generates simple, license-free placeholder art/sound the first time the app runs.

These are plain geometric shapes drawn with Pillow (not Valve/Meta artwork) so
there are no trademark/copyright concerns shipping them. Users can replace any
of these per-device in the GUI.
"""
import math
import os
import struct
import wave

from PIL import Image, ImageDraw

from . import paths

ICON_SIZE = 128


def _battery_glyph(draw: ImageDraw.ImageDraw, cx: int, cy: int, fill: str, fraction: float = 0.7):
    body_w, body_h = 70, 34
    x0, y0 = cx - body_w // 2, cy - body_h // 2
    x1, y1 = x0 + body_w, y0 + body_h
    draw.rounded_rectangle([x0, y0, x1, y1], radius=6, outline=fill, width=5)
    draw.rectangle([x1, y0 + body_h * 0.3, x1 + 8, y0 + body_h * 0.7], fill=fill)
    inset = 6
    fill_w = (body_w - inset * 2) * max(0.0, min(1.0, fraction))
    draw.rectangle(
        [x0 + inset, y0 + inset, x0 + inset + fill_w, y1 - inset],
        fill=fill,
    )


def _save(img: Image.Image, name: str):
    path = os.path.join(paths.defaults_dir(), name)
    img.save(path)
    return path


def _make_class_icon(name: str, shape: str, color: str) -> str:
    img = Image.new("RGBA", (ICON_SIZE, ICON_SIZE), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    cx, cy = ICON_SIZE // 2, ICON_SIZE // 2

    if shape == "hmd":
        d.rounded_rectangle([16, 40, 112, 88], radius=20, outline=color, width=7)
        d.ellipse([34, 54, 58, 78], outline=color, width=5)
        d.ellipse([70, 54, 94, 78], outline=color, width=5)
        d.line([16, 64, 4, 58], fill=color, width=6)
        d.line([112, 64, 124, 58], fill=color, width=6)
    elif shape == "controller":
        d.rounded_rectangle([24, 44, 104, 92], radius=24, outline=color, width=7)
        d.ellipse([32, 30, 56, 54], outline=color, width=6)
        d.ellipse([72, 30, 96, 54], outline=color, width=6)
        d.ellipse([56, 62, 72, 78], outline=color, width=5)
    elif shape == "tracker":
        d.rectangle([32, 32, 96, 96], outline=color, width=7)
        d.ellipse([54, 54, 74, 74], outline=color, width=5)
    elif shape == "base_station":
        d.polygon([(cx, 20), (108, cy), (cx, 108), (20, cy)], outline=color, width=7)
        d.ellipse([cx - 10, cy - 10, cx + 10, cy + 10], outline=color, width=5)
    elif shape == "service":
        # A hexagon ("background system/service" motif, distinct from the
        # base station's diamond) with a small dot in the middle.
        radius = 46
        points = [
            (cx + radius * math.cos(math.radians(60 * i - 90)), cy + radius * math.sin(math.radians(60 * i - 90)))
            for i in range(6)
        ]
        d.polygon(points, outline=color, width=7)
        d.ellipse([cx - 9, cy - 9, cx + 9, cy + 9], outline=color, width=5)
    elif shape == "microphone":
        _microphone_glyph(d, color)
    else:  # generic
        d.ellipse([20, 20, 108, 108], outline=color, width=7)
        _battery_glyph(d, cx, cy, color, fraction=0.8)

    return _save(img, name)


def _microphone_glyph(draw: ImageDraw.ImageDraw, color: str):
    draw.rounded_rectangle([46, 14, 82, 70], radius=18, outline=color, width=7)   # capsule
    draw.arc([32, 40, 96, 100], start=0, end=180, fill=color, width=6)             # cradle
    draw.line([(64, 100), (64, 116)], fill=color, width=6)                         # stem
    draw.line([(44, 116), (84, 116)], fill=color, width=6)                         # base


def _make_mic_muted_icon(name: str, color: str) -> str:
    img = Image.new("RGBA", (ICON_SIZE, ICON_SIZE), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    _microphone_glyph(d, color)
    d.line([(24, 20), (104, 108)], fill=color, width=9)  # slash across it
    return _save(img, name)


def tray_icon_image() -> Image.Image:
    """An in-memory icon (no disk write) for the system tray - the same
    "generic" device icon shape/style used elsewhere, at the same ICON_SIZE
    (128) as everything else in this file (_battery_glyph's proportions are
    tuned for that size) - pystray/the OS scale it down to whatever the
    tray actually needs, same as any other tray icon library expects."""
    img = Image.new("RGBA", (ICON_SIZE, ICON_SIZE), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    color = "#59c2ff"
    cx, cy = ICON_SIZE // 2, ICON_SIZE // 2
    d.ellipse([20, 20, 108, 108], outline=color, width=7)
    _battery_glyph(d, cx, cy, color, fraction=0.8)
    return img


def _make_low_battery_icon(name: str, color: str) -> str:
    img = Image.new("RGBA", (ICON_SIZE, ICON_SIZE), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    cx, cy = ICON_SIZE // 2, ICON_SIZE // 2
    _battery_glyph(d, cx, cy - 8, color, fraction=0.15)
    d.polygon(
        [(cx - 6, cy + 10), (cx + 6, cy + 10), (cx - 2, cy + 34), (cx + 12, cy + 8), (cx, cy + 8)],
        fill=color,
    )
    return _save(img, name)


def _lightning_bolt(draw: ImageDraw.ImageDraw, cx: int, cy: int, fill: str, scale: float = 1.0):
    pts = [
        (cx - 6 * scale, cy - 34 * scale), (cx + 10 * scale, cy - 34 * scale), (cx - 2 * scale, cy - 2 * scale),
        (cx + 12 * scale, cy - 2 * scale), (cx - 10 * scale, cy + 34 * scale), (cx + 2 * scale, cy + 2 * scale),
        (cx - 12 * scale, cy + 2 * scale),
    ]
    draw.polygon(pts, fill=fill)


def _make_charging_icon(name: str, color: str) -> str:
    """A mostly-full battery with a lightning bolt overlay - shown while a
    device reports charging, distinct in color from the plain "normal" icon
    so it reads as its own state, not just a re-skinned default."""
    img = Image.new("RGBA", (ICON_SIZE, ICON_SIZE), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    cx, cy = ICON_SIZE // 2, ICON_SIZE // 2
    _battery_glyph(d, cx, cy, color, fraction=0.85)
    _lightning_bolt(d, cx, cy, "#ffffff", scale=0.55)
    return _save(img, name)


def _make_drain_warning_icon(name: str, color: str) -> str:
    """A low battery + lightning bolt (still charging) + warning triangle -
    the "plugged in but still losing charge" state. Deliberately combines
    the low-battery and charging motifs plus a third warning element so it
    reads as distinct from either state alone, not a variant of one of them."""
    img = Image.new("RGBA", (ICON_SIZE, ICON_SIZE), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    cx, cy = ICON_SIZE // 2, ICON_SIZE // 2
    _battery_glyph(d, cx, cy - 18, color, fraction=0.15)
    _lightning_bolt(d, cx, cy - 18, color, scale=0.4)
    # warning triangle beneath, matching the low-battery icon's exclamation placement
    d.polygon(
        [(cx, cy + 14), (cx - 22, cy + 50), (cx + 22, cy + 50)],
        outline=color, width=6,
    )
    d.line([(cx, cy + 26), (cx, cy + 38)], fill=color, width=6)
    d.ellipse([cx - 3, cy + 42, cx + 3, cy + 48], fill=color)
    return _save(img, name)


def _make_beep_wav(name: str) -> str:
    """A short two-tone alert beep, synthesized as raw PCM (no external asset)."""
    path = os.path.join(paths.defaults_dir(), name)
    if os.path.exists(path):
        return path
    framerate = 22050
    amplitude = 12000

    def tone(freq, seconds):
        n = int(framerate * seconds)
        return [int(amplitude * math.sin(2 * math.pi * freq * (i / framerate))) for i in range(n)]

    samples = tone(880, 0.15) + tone(0, 0.05) + tone(1175, 0.2)
    with wave.open(path, "w") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(framerate)
        w.writeframes(b"".join(struct.pack("<h", s) for s in samples))
    return path


DEFAULT_NORMAL_ICONS = {
    "HMD": ("hmd_normal.png", "hmd", "#59c2ff"),
    "Controller": ("controller_normal.png", "controller", "#59c2ff"),
    "GenericTracker": ("tracker_normal.png", "tracker", "#59c2ff"),
    "TrackingReference": ("base_station_normal.png", "base_station", "#59c2ff"),
    "Service": ("service_normal.png", "service", "#59c2ff"),
    "Microphone": ("microphone_normal.png", "microphone", "#59c2ff"),
    "Other": ("generic_normal.png", "generic", "#59c2ff"),
}
DEFAULT_MIC_MUTED_ICON = ("microphone_muted.png", "#ff5c5c")
DEFAULT_LOW_ICON = ("low_battery.png", "#ff5c5c")
DEFAULT_CHARGING_ICON = ("charging.png", "#4caf50")
DEFAULT_DRAIN_WARNING_ICON = ("drain_warning.png", "#ff9800")
DEFAULT_BEEP = "warning_beep.wav"


def ensure_defaults() -> dict:
    """Create the default icon set + beep on first run; safe to call every launch."""
    paths_out = {}
    for device_class, (fname, shape, color) in DEFAULT_NORMAL_ICONS.items():
        full = os.path.join(paths.defaults_dir(), fname)
        if not os.path.exists(full):
            _make_class_icon(fname, shape, color)
        paths_out[device_class] = full
    muted_name, muted_color = DEFAULT_MIC_MUTED_ICON
    muted_full = os.path.join(paths.defaults_dir(), muted_name)
    if not os.path.exists(muted_full):
        _make_mic_muted_icon(muted_name, muted_color)
    paths_out["_mic_muted"] = muted_full

    low_name, low_color = DEFAULT_LOW_ICON
    low_full = os.path.join(paths.defaults_dir(), low_name)
    if not os.path.exists(low_full):
        _make_low_battery_icon(low_name, low_color)
    paths_out["_low"] = low_full

    charging_name, charging_color = DEFAULT_CHARGING_ICON
    charging_full = os.path.join(paths.defaults_dir(), charging_name)
    if not os.path.exists(charging_full):
        _make_charging_icon(charging_name, charging_color)
    paths_out["_charging"] = charging_full

    warn_name, warn_color = DEFAULT_DRAIN_WARNING_ICON
    warn_full = os.path.join(paths.defaults_dir(), warn_name)
    if not os.path.exists(warn_full):
        _make_drain_warning_icon(warn_name, warn_color)
    paths_out["_warn_drain"] = warn_full

    paths_out["_beep"] = _make_beep_wav(DEFAULT_BEEP)
    return paths_out
