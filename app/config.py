"""Overlay configuration: the list of device items, overlay effects, and their
per-item settings.

Stored as JSON in a "Data" folder next to the .exe. Media files the user
picks are copied into that same folder so the config stays self-contained
even if the original files move or the app updates.
"""
import dataclasses
import json
import os
import shutil
import uuid
from typing import Optional

from . import paths

CONFIG_VERSION = 1

VALID_SHOW_MODES = ("always", "low_only")

# Animations for "Hidden until low" items. Keys are stored in config/JSON and
# also referenced (as literal strings) by the keyframe lookup tables in the
# overlay page's JS in server.py - keep the two in sync if you add more.
ENTER_ANIMATIONS = {
    "pop_bottom": "Pop in from Bottom",
    "pop_top": "Pop in from Top",
    "pop_left": "Pop in from Left",
    "pop_right": "Pop in from Right",
    "fade": "Fade in",
    "fade_shake": "Fade in + Shake",
}
EXIT_ANIMATIONS = {
    "fade": "Fade out",
    "slide_left": "Slide out Left",
    "slide_right": "Slide out Right",
    "slide_top": "Slide out Up",
    "slide_bottom": "Slide out Down",
}

# Overlay Effect vocabulary.
TRIGGER_OPTIONS = {
    "battery_low": "Battery Low",
    "battery_normal": "Battery Normal (not low)",
    "device_disconnected": "Device Disconnected",
    "device_connected": "Device Connected",
}
TARGET_MODE_OPTIONS = {
    "specific": "Specific Device",
    "all": "All Devices",
}
TEXT_POSITION_OPTIONS = {
    "above": "Above Picture",
    "below": "Below Picture",
    "middle": "Middle of Picture",
}
TEXT_ANIMATION_OPTIONS = {
    "none": "None",
    "wobble": "Wobble",
    "shake": "Shake",
    "pulse": "Pulse",
}


@dataclasses.dataclass
class OverlayItem:
    id: str
    label: str
    device_serial: str
    device_class_hint: str = "Other"
    x_pct: float = 5.0
    y_pct: float = 80.0
    width_px: int = 160
    show_mode: str = "always"          # "always" | "low_only"
    low_threshold_pct: int = 20
    normal_image: Optional[str] = None  # path, relative to app-data dir, or None -> use default
    low_image: Optional[str] = None
    sound: Optional[str] = None
    sound_cooldown_sec: int = 300
    show_label: bool = True
    show_percent: bool = True
    enter_animation: str = "pop_bottom"  # only used when show_mode == "low_only"
    exit_animation: str = "fade"         # only used when show_mode == "low_only"

    def to_dict(self):
        return dataclasses.asdict(self)

    @staticmethod
    def from_dict(d: dict) -> "OverlayItem":
        known = {f.name for f in dataclasses.fields(OverlayItem)}
        return OverlayItem(**{k: v for k, v in d.items() if k in known})


@dataclasses.dataclass
class EffectItem:
    """A standalone popup effect (picture + optional caption + sound) bound
    to a device and a trigger condition - independent of any OverlayItem, so
    you can layer several different alerts on the same device."""
    id: str
    label: str
    device_serial: str
    device_class_hint: str = "Other"
    target_mode: str = "specific"       # see TARGET_MODE_OPTIONS - "specific" uses device_serial
    ignore_device_serials: list = dataclasses.field(default_factory=list)  # excluded from "all" matching
    x_pct: float = 5.0
    y_pct: float = 80.0
    width_px: int = 200
    trigger: str = "battery_low"        # see TRIGGER_OPTIONS
    low_threshold_pct: int = 20         # used by battery_low / battery_normal triggers
    picture: Optional[str] = None       # None -> default icon for device_class_hint
    sound: Optional[str] = None
    sound_cooldown_sec: int = 300
    enter_animation: str = "pop_bottom"
    exit_animation: str = "fade"
    text: str = ""
    text_position: str = "below"        # see TEXT_POSITION_OPTIONS
    font_family: str = "Segoe UI"
    font_size_px: int = 22
    font_color: str = "#ffffff"
    text_animation: str = "none"        # see TEXT_ANIMATION_OPTIONS
    outline_enabled: bool = False
    outline_thickness_px: int = 2
    outline_color: str = "#000000"

    def to_dict(self):
        return dataclasses.asdict(self)

    @staticmethod
    def from_dict(d: dict) -> "EffectItem":
        known = {f.name for f in dataclasses.fields(EffectItem)}
        return EffectItem(**{k: v for k, v in d.items() if k in known})


@dataclasses.dataclass
class AppConfig:
    version: int = CONFIG_VERSION
    port: int = 8710
    poll_interval_sec: float = 1.0
    language: str = "en"
    dismissed_battery_notice: bool = False
    items: list = dataclasses.field(default_factory=list)     # list[OverlayItem]
    effects: list = dataclasses.field(default_factory=list)   # list[EffectItem]

    def to_dict(self):
        return {
            "version": self.version,
            "port": self.port,
            "poll_interval_sec": self.poll_interval_sec,
            "language": self.language,
            "dismissed_battery_notice": self.dismissed_battery_notice,
            "items": [it.to_dict() for it in self.items],
            "effects": [ef.to_dict() for ef in self.effects],
        }

    @staticmethod
    def from_dict(d: dict) -> "AppConfig":
        cfg = AppConfig(
            version=d.get("version", CONFIG_VERSION),
            port=d.get("port", 8710),
            poll_interval_sec=d.get("poll_interval_sec", 1.0),
            language=d.get("language", "en"),
            dismissed_battery_notice=d.get("dismissed_battery_notice", False),
        )
        cfg.items = [OverlayItem.from_dict(it) for it in d.get("items", [])]
        cfg.effects = [EffectItem.from_dict(ef) for ef in d.get("effects", [])]
        return cfg


def load() -> AppConfig:
    path = paths.config_path()
    if not os.path.exists(path):
        return AppConfig()
    try:
        with open(path, "r", encoding="utf-8") as f:
            return AppConfig.from_dict(json.load(f))
    except (json.JSONDecodeError, OSError):
        return AppConfig()


def save(cfg: AppConfig) -> None:
    path = paths.config_path()
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(cfg.to_dict(), f, indent=2)
    os.replace(tmp, path)


def new_item_id() -> str:
    return uuid.uuid4().hex[:12]


new_effect_id = new_item_id  # same scheme; separate name for readability at call sites


def import_media(item_id: str, source_path: str, kind: str) -> str:
    """Copy a user-picked file into this item's app-data folder.

    kind is "normal", "low", or "sound" and is used as the base filename so
    re-importing overwrites the previous file cleanly.
    Returns a path relative to the app-data root (portable, stored in config).
    """
    if not source_path:
        return None
    ext = os.path.splitext(source_path)[1].lower()
    dest_dir = paths.item_assets_dir(item_id)
    dest_name = f"{kind}{ext}"
    dest_path = os.path.join(dest_dir, dest_name)
    shutil.copyfile(source_path, dest_path)
    return os.path.relpath(dest_path, paths.app_data_dir())


def resolve_media(relative_path: Optional[str]) -> Optional[str]:
    if not relative_path:
        return None
    full = os.path.join(paths.app_data_dir(), relative_path)
    return full if os.path.exists(full) else None
