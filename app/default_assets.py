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
    else:  # generic
        d.ellipse([20, 20, 108, 108], outline=color, width=7)
        _battery_glyph(d, cx, cy, color, fraction=0.8)

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
    "Other": ("generic_normal.png", "generic", "#59c2ff"),
}
DEFAULT_LOW_ICON = ("low_battery.png", "#ff5c5c")
DEFAULT_BEEP = "warning_beep.wav"


def ensure_defaults() -> dict:
    """Create the default icon set + beep on first run; safe to call every launch."""
    paths_out = {}
    for device_class, (fname, shape, color) in DEFAULT_NORMAL_ICONS.items():
        full = os.path.join(paths.defaults_dir(), fname)
        if not os.path.exists(full):
            _make_class_icon(fname, shape, color)
        paths_out[device_class] = full
    low_name, low_color = DEFAULT_LOW_ICON
    low_full = os.path.join(paths.defaults_dir(), low_name)
    if not os.path.exists(low_full):
        _make_low_battery_icon(low_name, low_color)
    paths_out["_low"] = low_full
    paths_out["_beep"] = _make_beep_wav(DEFAULT_BEEP)
    return paths_out
