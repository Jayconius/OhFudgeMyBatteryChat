"""Overlay configuration: the list of device items, overlay effects, and their
per-item settings.

Stored as JSON in a "Data" folder next to the .exe. Media files the user
picks are copied into that same folder so the config stays self-contained
even if the original files move or the app updates.
"""
import dataclasses
import json
import os
import secrets
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
    "device_charging": "Device Charging",
    "device_not_charging": "Device Not Charging",
    "tracking_lost": "Tracking Lost",
    "tracking_regained": "Tracking Regained",
    "hmd_removed": "HMD Removed (Proximity)",
    "hmd_worn": "HMD Worn (Proximity)",
    # Only offered (and only evaluated) when an Effect's target is an Audio
    # Device - see EffectItem.audio_endpoint_id.
    "audio_connected": "Mic Connected",
    "audio_disconnected": "Mic Disconnected",
    "audio_muted": "Mic Muted",
    "audio_unmuted": "Mic Unmuted",
    "audio_talking": "Mic Talking",
    "audio_silent": "Mic Silent For...",
}
AUDIO_TRIGGER_KEYS = tuple(k for k in TRIGGER_OPTIONS if k.startswith("audio_"))
TARGET_MODE_OPTIONS = {
    "specific": "Specific Device",
    "all": "All Devices",
    "audio": "Audio Device",
}
MACRO_ACTION_OPTIONS = {
    "toggle": "Toggle mute",
    "mute": "Mute",
    "unmute": "Unmute",
}
CHAT_PERMISSION_OPTIONS = {
    "everyone": "Everyone",
    "vip": "VIP or higher",
    "moderator": "Moderators or higher",
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
NUDGE_DIRECTION_OPTIONS = {
    "left": "Left",
    "right": "Right",
    "up": "Up",
    "down": "Down",
}
THEME_OPTIONS = {
    "system": "Match System",
    "light": "Light",
    "dark": "Dark",
}
DURATION_MODE_OPTIONS = {
    "always": "Stay on screen while triggered",
    "timed": "Show for a set time, then hide",
}
CLOSE_ACTION_OPTIONS = {
    "ask": "Ask me every time",  # only ever saved as a real choice below; shown in the About dropdown so it can be reset back to "ask again"
    "tray": "Minimize to the system tray",
    "exit": "Exit the app completely",
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
    normal_pic_animation: str = "none"  # see TEXT_ANIMATION_OPTIONS - idle animation on the Normal Picture
    low_pic_animation: str = "none"     # idle animation on the Low Battery Picture; "none" keeps the automatic low-battery glow
    sound: Optional[str] = None
    sound_cooldown_sec: int = 300
    show_label: bool = True
    show_percent: bool = True
    enter_animation: str = "pop_bottom"  # only used when show_mode == "low_only"
    exit_animation: str = "fade"         # only used when show_mode == "low_only"
    nudge_group_id: Optional[str] = None  # if set, position/direction/spacing come from that NudgeGroup
    text_gap_px: int = 4  # vertical gap between the picture and Label/Battery % text
    # If set, this item only shows (on top of its normal show_mode logic)
    # once every member of that SyncGroup is ready - so a rarely-used set of
    # accessories pops in together instead of trickling in one at a time as
    # each connects, each still keeping its own picture/label/animation.
    sync_group_id: Optional[str] = None

    # Charging status (independent of show_mode - applies to both Always
    # Visible and Hidden until low)
    show_charging_status: bool = False
    charging_image: Optional[str] = None
    charging_pic_animation: str = "none"
    # "Still losing battery despite being on charge" warning (e.g. a wireless
    # headset draining faster than a weak charger can replace) - detected by
    # comparing the current battery_pct against whatever it was the moment
    # charging most recently started, not a continuous trend (SteamVR's
    # battery reporting updates in bursts, not smoothly, so a fixed
    # reference point is far less jittery than comparing consecutive polls).
    # Independent of show_charging_status - fires on its own even if the
    # plain charging picture was never set up.
    warn_drain_while_charging: bool = False
    warn_drain_image: Optional[str] = None
    warn_drain_pic_animation: str = "none"
    warn_drain_sound: Optional[str] = None
    warn_drain_sound_cooldown_sec: int = 300
    # Only meaningful when show_mode == "low_only" - Always Visible items
    # have nothing to hide. When the drain warning above is currently
    # active, this is ignored (the item stays visible/alerting) even if
    # charging is reported true - re-hiding would be actively misleading.
    hide_on_charging: bool = False

    # Label text styling (only rendered when show_label is True)
    label_font_family: str = "Segoe UI"
    label_font_size_px: int = 15
    label_font_color: str = "#ffffff"
    label_text_animation: str = "none"   # see TEXT_ANIMATION_OPTIONS
    label_outline_enabled: bool = False
    label_outline_thickness_px: int = 2
    label_outline_color: str = "#000000"

    # Battery % text styling (only rendered when show_percent is True)
    percent_font_family: str = "Segoe UI"
    percent_font_size_px: int = 18
    percent_font_color: str = "#ffffff"
    percent_text_animation: str = "none"  # see TEXT_ANIMATION_OPTIONS
    percent_outline_enabled: bool = False
    percent_outline_thickness_px: int = 2
    percent_outline_color: str = "#000000"

    def to_dict(self):
        return dataclasses.asdict(self)

    @staticmethod
    def from_dict(d: dict) -> "OverlayItem":
        known = {f.name for f in dataclasses.fields(OverlayItem)}
        return OverlayItem(**{k: v for k, v in d.items() if k in known})


@dataclasses.dataclass
class NudgeGroup:
    """A named, reusable shared position for Nudge: every Device item or
    Effect assigned to a group renders at the group's position (not its
    own), and shares one direction/spacing - so moving one member moves them
    all, adding something to a group needs no manual lining-up, and Devices
    and Effects can stack into the very same slot together."""
    id: str
    name: str
    x_pct: float = 50.0
    y_pct: float = 80.0
    direction: str = "left"   # see NUDGE_DIRECTION_OPTIONS
    spacing_px: int = 20

    def to_dict(self):
        return dataclasses.asdict(self)

    @staticmethod
    def from_dict(d: dict) -> "NudgeGroup":
        known = {f.name for f in dataclasses.fields(NudgeGroup)}
        return NudgeGroup(**{k: v for k, v in d.items() if k in known})


SYNC_READY_MODE_OPTIONS = {
    "all_connected": "All Connected",
    "all_charged": "All Connected & Charged",
}


@dataclasses.dataclass
class SyncGroup:
    """A named set of Device items that should only ever appear together,
    each keeping its own picture/label/animation - for VR accessories used
    rarely (special-occasion gear), so they don't trickle in individually as
    each connects but instead pop in as a set once every member is ready.
    Independent of NudgeGroup, which shares one screen position instead -
    a Device item can belong to both at once, or neither. Like NudgeGroup,
    membership isn't stored here - it's derived from which OverlayItems
    point at this group's id via their own sync_group_id."""
    id: str
    name: str
    ready_mode: str = "all_connected"  # see SYNC_READY_MODE_OPTIONS
    ready_threshold_pct: int = 95      # only used by "all_charged"

    def to_dict(self):
        return dataclasses.asdict(self)

    @staticmethod
    def from_dict(d: dict) -> "SyncGroup":
        known = {f.name for f in dataclasses.fields(SyncGroup)}
        return SyncGroup(**{k: v for k, v in d.items() if k in known})


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
    picture_animation: str = "none"     # see TEXT_ANIMATION_OPTIONS - idle animation on the picture
    sound: Optional[str] = None
    sound_cooldown_sec: int = 300
    enter_animation: str = "pop_bottom"
    exit_animation: str = "fade"
    nudge_group_id: Optional[str] = None  # if set, position/direction/spacing come from that NudgeGroup - shared with Device items
    duration_mode: str = "always"        # see DURATION_MODE_OPTIONS
    duration_sec: float = 5.0            # only used when duration_mode == "timed"
    text: str = ""
    text_position: str = "below"        # see TEXT_POSITION_OPTIONS
    text_gap_px: int = 4                # gap between the picture and the caption text (unused for "middle")
    font_family: str = "Segoe UI"
    font_size_px: int = 22
    font_color: str = "#ffffff"
    text_animation: str = "none"        # see TEXT_ANIMATION_OPTIONS
    outline_enabled: bool = False
    outline_thickness_px: int = 2
    outline_color: str = "#000000"

    # Twitch chat command (optional, additional way to trigger this effect -
    # independent of the trigger/target above, which still work normally).
    # Firing pops the effect up for duration_sec regardless of duration_mode,
    # since a chat command is a momentary event, not an ongoing state.
    chat_command: Optional[str] = None   # e.g. "!battery" - None/empty = no chat trigger
    chat_permission: str = "everyone"    # see CHAT_PERMISSION_OPTIONS

    # Audio Device target (target_mode == "audio") - a Windows recording
    # endpoint instead of a SteamVR device. The id is Windows' own endpoint
    # id (it changes if a USB receiver moves to another port - see
    # AudioMonitor rebind); audio_name is the last-known Windows name so an
    # unplugged device still shows something readable.
    audio_endpoint_id: Optional[str] = None
    audio_name: str = ""
    audio_silent_sec: int = 30           # only used by the audio_silent trigger

    def to_dict(self):
        return dataclasses.asdict(self)

    @staticmethod
    def from_dict(d: dict) -> "EffectItem":
        known = {f.name for f in dataclasses.fields(EffectItem)}
        return EffectItem(**{k: v for k, v in d.items() if k in known})


@dataclasses.dataclass
class MacroItem:
    """One mute macro: a button on the local Macros page and/or a global
    hotkey that mutes, unmutes or toggles a Windows recording device. It
    sets the *Windows* mute flag - the same one the Mic Muted/Unmuted
    triggers read - so an Effect can show a MUTED indicator for it."""
    id: str
    label: str
    endpoint_id: Optional[str] = None
    endpoint_name: str = ""             # last-known Windows name, for display when unplugged
    action: str = "toggle"              # see MACRO_ACTION_OPTIONS
    hotkey: Optional[str] = None        # e.g. "CTRL+SHIFT+NUM5" - see hotkeys.parse_hotkey

    def to_dict(self):
        return dataclasses.asdict(self)

    @staticmethod
    def from_dict(d: dict) -> "MacroItem":
        known = {f.name for f in dataclasses.fields(MacroItem)}
        return MacroItem(**{k: v for k, v in d.items() if k in known})


@dataclasses.dataclass
class AppConfig:
    version: int = CONFIG_VERSION
    port: int = 8710
    poll_interval_sec: float = 1.0
    language: str = "en"
    dismissed_battery_notice: bool = False
    check_for_updates: bool = False
    theme: str = "system"  # "system" | "light" | "dark" - see THEME_OPTIONS
    icon_check_version: str = ""  # last APP_VERSION the new-icons prompt ran for
    close_action: str = "ask"  # see CLOSE_ACTION_OPTIONS - "ask" prompts once on the first close
    # Twitch chat-command connection (experimental/beta) - access_token is
    # refreshed in place using refresh_token as it expires; twitch_login is
    # both the display name shown in Settings and the IRC channel joined.
    twitch_connected: bool = False
    twitch_login: Optional[str] = None
    twitch_access_token: Optional[str] = None
    twitch_refresh_token: Optional[str] = None
    items: list = dataclasses.field(default_factory=list)         # list[OverlayItem]
    effects: list = dataclasses.field(default_factory=list)       # list[EffectItem]
    nudge_groups: list = dataclasses.field(default_factory=list)  # list[NudgeGroup]
    sync_groups: list = dataclasses.field(default_factory=list)   # list[SyncGroup]
    # Audio devices: user-set names keyed by Windows endpoint id (Windows
    # names are generic - "Microphone (USB Audio Device)"), shown in the
    # picker and used as the default label for anything watching the device.
    audio_nicknames: dict = dataclasses.field(default_factory=dict)
    macros: list = dataclasses.field(default_factory=list)        # list[MacroItem]
    # Random secret the Macros web page carries and must send back with each
    # button press, so a stray web page can't trigger a mute - generated on
    # first use, never shown in the GUI.
    macro_token: str = ""

    def to_dict(self):
        return {
            "version": self.version,
            "port": self.port,
            "poll_interval_sec": self.poll_interval_sec,
            "language": self.language,
            "dismissed_battery_notice": self.dismissed_battery_notice,
            "check_for_updates": self.check_for_updates,
            "theme": self.theme,
            "icon_check_version": self.icon_check_version,
            "close_action": self.close_action,
            "twitch_connected": self.twitch_connected,
            "twitch_login": self.twitch_login,
            "twitch_access_token": self.twitch_access_token,
            "twitch_refresh_token": self.twitch_refresh_token,
            "items": [it.to_dict() for it in self.items],
            "effects": [ef.to_dict() for ef in self.effects],
            "nudge_groups": [g.to_dict() for g in self.nudge_groups],
            "sync_groups": [g.to_dict() for g in self.sync_groups],
            "audio_nicknames": dict(self.audio_nicknames),
            "macros": [m.to_dict() for m in self.macros],
            "macro_token": self.macro_token,
        }

    @staticmethod
    def from_dict(d: dict) -> "AppConfig":
        cfg = AppConfig(
            version=d.get("version", CONFIG_VERSION),
            port=d.get("port", 8710),
            poll_interval_sec=d.get("poll_interval_sec", 1.0),
            language=d.get("language", "en"),
            dismissed_battery_notice=d.get("dismissed_battery_notice", False),
            check_for_updates=d.get("check_for_updates", False),
            theme=d.get("theme", "system"),
            icon_check_version=d.get("icon_check_version", ""),
            close_action=d.get("close_action", "ask"),
            twitch_connected=d.get("twitch_connected", False),
            twitch_login=d.get("twitch_login"),
            twitch_access_token=d.get("twitch_access_token"),
            twitch_refresh_token=d.get("twitch_refresh_token"),
        )
        cfg.items = [OverlayItem.from_dict(it) for it in d.get("items", [])]
        cfg.effects = [EffectItem.from_dict(ef) for ef in d.get("effects", [])]
        cfg.nudge_groups = [NudgeGroup.from_dict(g) for g in d.get("nudge_groups", [])]
        cfg.sync_groups = [SyncGroup.from_dict(g) for g in d.get("sync_groups", [])]
        cfg.audio_nicknames = {k: v for k, v in (d.get("audio_nicknames") or {}).items() if isinstance(v, str)}
        cfg.macros = [MacroItem.from_dict(m) for m in d.get("macros", [])]
        cfg.macro_token = d.get("macro_token", "") or ""
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
new_group_id = new_item_id
new_sync_group_id = new_item_id
new_macro_id = new_item_id


def new_macro_token() -> str:
    return secrets.token_urlsafe(24)


def import_media(item_id: str, source_path: str, kind: str) -> str:
    """Copy a user-picked file into this item's app-data folder.

    kind (e.g. "normal", "low", "sound", "charging", "warn_drain",
    "warn_drain_sound") is used as the base filename so re-importing
    overwrites the previous file cleanly.
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
