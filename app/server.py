"""Local HTTP server that serves the OBS browser-source overlay page plus a
small JSON status API it polls, and the media files (icons/gifs/webm/sounds)
each overlay item/effect references.

Bound to 127.0.0.1 only - this is a local OBS integration, not a public service.
"""
import json
import mimetypes
import os
import posixpath
import socket
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit

from . import config as config_mod
from . import paths
from .vr_monitor import VRMonitor

mimetypes.add_type("video/webm", ".webm")

APP_TITLE = "Oh Fudge, My Battery Chat!"

DEFAULTS_BY_CLASS = {
    "HMD": "/defaults/hmd_normal.png",
    "Controller": "/defaults/controller_normal.png",
    "GenericTracker": "/defaults/tracker_normal.png",
    "TrackingReference": "/defaults/base_station_normal.png",
    "Other": "/defaults/generic_normal.png",
    "_generic": "/defaults/generic_normal.png",
    "_low": "/defaults/low_battery.png",
    "_beep": "/defaults/warning_beep.wav",
}


class PreviewState:
    """Lets the GUI's item/effect editor push a live "test this animation"
    request that the overlay page picks up on its next poll and loops until
    the GUI clears it (dialog closed). Shared in-process between GUI and
    server - no HTTP round trip needed for the GUI -> server direction.
    """

    def __init__(self):
        self._lock = threading.Lock()
        self._data = None
        self._nonce = 0

    def set(self, payload: dict):
        with self._lock:
            self._nonce += 1
            self._data = dict(payload)
            self._data["nonce"] = self._nonce

    def clear(self):
        with self._lock:
            self._data = None

    def get(self):
        with self._lock:
            return dict(self._data) if self._data else None


def _config_version():
    """A cheap 'has anything changed' signal for the overlay page: the
    config file's own mtime. The client bakes in the version from page load
    and compares it against every poll response - a mismatch means a Device/
    Effect was added/edited/removed since this page loaded, so it reloads
    itself instead of silently going stale (see OVERLAY_PAGE_TEMPLATE's
    poll())."""
    try:
        return os.path.getmtime(paths.config_path())
    except OSError:
        return 0


def _device_dict(devices):
    return {
        serial: {
            "battery_pct": d.battery_pct,
            "charging": d.charging,
            "device_class": d.device_class,
            "model": d.model,
            "role": d.role,
        }
        for serial, d in devices.items()
    }


def _device_payload(snapshot):
    return {
        "connected": snapshot.steamvr_connected,
        "error": snapshot.error,
        "devices": _device_dict(snapshot.devices),
        "known_devices": _device_dict(snapshot.known_devices),
    }


_DEFAULT_LABEL_STYLE = dict(
    font_family="Segoe UI", font_size_px=15, font_color="#ffffff", text_animation="none",
    outline_enabled=False, outline_thickness_px=2, outline_color="#000000",
)
_DEFAULT_PERCENT_STYLE = dict(
    font_family="Segoe UI", font_size_px=18, font_color="#ffffff", text_animation="none",
    outline_enabled=False, outline_thickness_px=2, outline_color="#000000",
)


def _preview_payload(preview_state: PreviewState):
    p = preview_state.get()
    if not p or not p.get("active"):
        return {"active": False}
    low_path = p.get("low_path")
    if low_path and os.path.isfile(low_path):
        pic_src = "/media/_preview/low"
    else:
        pic_src = DEFAULTS_BY_CLASS.get(p.get("device_class_hint", "Other"), DEFAULTS_BY_CLASS["_generic"]) if p.get("mode") == "effect" else DEFAULTS_BY_CLASS.get("_low")
    return {
        "active": True,
        "nonce": p.get("nonce"),
        "mode": p.get("mode", "device"),
        "x_pct": p.get("x_pct", 5.0),
        "y_pct": p.get("y_pct", 5.0),
        "width_px": p.get("width_px", 160),
        "enter": p.get("enter", "pop_bottom"),
        "exit": p.get("exit", "fade"),
        "label": p.get("label", "Preview"),
        "show_label": p.get("show_label", True),
        "show_percent": p.get("show_percent", True),
        "label_style": {**_DEFAULT_LABEL_STYLE, **p.get("label_style", {})},
        "percent_style": {**_DEFAULT_PERCENT_STYLE, **p.get("percent_style", {})},
        "low_pic_animation": p.get("low_pic_animation", "none"),
        "low_src": pic_src,
        "text": p.get("text", ""),
        "text_position": p.get("text_position", "below"),
        "font_family": p.get("font_family", "Segoe UI"),
        "font_size_px": p.get("font_size_px", 22),
        "font_color": p.get("font_color", "#ffffff"),
        "text_animation": p.get("text_animation", "none"),
        "outline_enabled": p.get("outline_enabled", False),
        "outline_thickness_px": p.get("outline_thickness_px", 2),
        "outline_color": p.get("outline_color", "#000000"),
    }


def _item_payload(item, defaults_by_class: dict, nudge_groups_by_id: dict):
    normal = config_mod.resolve_media(item.normal_image)
    low = config_mod.resolve_media(item.low_image)
    sound = config_mod.resolve_media(item.sound)
    group = nudge_groups_by_id.get(item.nudge_group_id) if item.nudge_group_id else None
    x_pct = group.x_pct if group else item.x_pct
    y_pct = group.y_pct if group else item.y_pct
    return {
        "id": item.id,
        "label": item.label,
        "device_serial": item.device_serial,
        "x_pct": x_pct,
        "y_pct": y_pct,
        "width_px": item.width_px,
        "show_mode": item.show_mode,
        "low_threshold_pct": item.low_threshold_pct,
        "sound_cooldown_sec": item.sound_cooldown_sec,
        "show_label": item.show_label,
        "show_percent": item.show_percent,
        "label_style": {
            "font_family": item.label_font_family,
            "font_size_px": item.label_font_size_px,
            "font_color": item.label_font_color,
            "text_animation": item.label_text_animation,
            "outline_enabled": item.label_outline_enabled,
            "outline_thickness_px": item.label_outline_thickness_px,
            "outline_color": item.label_outline_color,
        },
        "percent_style": {
            "font_family": item.percent_font_family,
            "font_size_px": item.percent_font_size_px,
            "font_color": item.percent_font_color,
            "text_animation": item.percent_text_animation,
            "outline_enabled": item.percent_outline_enabled,
            "outline_thickness_px": item.percent_outline_thickness_px,
            "outline_color": item.percent_outline_color,
        },
        "normal_pic_animation": item.normal_pic_animation,
        "low_pic_animation": item.low_pic_animation,
        "enter_animation": item.enter_animation,
        "exit_animation": item.exit_animation,
        "nudge_enabled": group is not None,
        "nudge_group_id": item.nudge_group_id or "",
        "nudge_direction": group.direction if group else "left",
        "nudge_spacing_px": group.spacing_px if group else 0,
        "normal_src": f"/media/{item.id}/normal" if normal else defaults_by_class.get(item.device_class_hint, defaults_by_class.get("_generic", "")),
        "low_src": f"/media/{item.id}/low" if low else defaults_by_class.get("_low", ""),
        "sound_src": f"/media/{item.id}/sound" if sound else defaults_by_class.get("_beep", ""),
    }


def _effect_payload(effect, defaults_by_class: dict):
    pic = config_mod.resolve_media(effect.picture)
    sound = config_mod.resolve_media(effect.sound)
    return {
        "id": effect.id,
        "label": effect.label,
        "device_serial": effect.device_serial,
        "target_mode": effect.target_mode,
        "ignore_device_serials": list(effect.ignore_device_serials),
        "x_pct": effect.x_pct,
        "y_pct": effect.y_pct,
        "width_px": effect.width_px,
        "trigger": effect.trigger,
        "low_threshold_pct": effect.low_threshold_pct,
        "sound_cooldown_sec": effect.sound_cooldown_sec,
        "enter_animation": effect.enter_animation,
        "exit_animation": effect.exit_animation,
        "text": effect.text,
        "text_position": effect.text_position,
        "font_family": effect.font_family,
        "font_size_px": effect.font_size_px,
        "font_color": effect.font_color,
        "text_animation": effect.text_animation,
        "outline_enabled": effect.outline_enabled,
        "outline_thickness_px": effect.outline_thickness_px,
        "outline_color": effect.outline_color,
        "pic_src": f"/media/effect/{effect.id}/picture" if pic else defaults_by_class.get(effect.device_class_hint, defaults_by_class.get("_generic", "")),
        "sound_src": f"/media/effect/{effect.id}/sound" if sound else defaults_by_class.get("_beep", ""),
    }


OVERLAY_PAGE_TEMPLATE = r"""<!doctype html>
<html>
<head>
<meta charset="utf-8">
<title>__APP_TITLE__</title>
<style>
  html, body { margin: 0; padding: 0; background: transparent; overflow: hidden; }
  .item {
    position: absolute;
    display: flex;
    flex-direction: column;
    align-items: center;
    font-family: "Segoe UI", Arial, sans-serif;
    text-align: center;
    filter: drop-shadow(0 2px 6px rgba(0,0,0,0.6));
  }
  /* "Always visible" device items: simple cross-fade, no directional animation. */
  .item.always-mode { opacity: 0; transform: scale(0.85); transition: opacity 0.35s ease, transform 0.35s ease; }
  .item.always-mode.visible { opacity: 1; transform: scale(1); }
  /* "Hidden until low" device items and Effects: driven by JS-assigned keyframe animations. */
  .item.kf-driven { opacity: 0; }
  /* Nudge-enabled items smoothly slide between slots instead of jumping. */
  .item.nudge-enabled { transition: left 0.35s ease, top 0.35s ease; }

  .item.low img.pic, .item.low video.pic { animation: pulse 1s ease-in-out infinite; }
  .item img.pic, .item video.pic { width: 100%; height: auto; display: block; }
  .item .label, .item .pct { text-shadow: 0 1px 3px #000; margin-top: 4px; }
  @keyframes pulse {
    0%, 100% { filter: drop-shadow(0 0 0 rgba(255,60,60,0)); }
    50% { filter: drop-shadow(0 0 10px rgba(255,60,60,0.9)); }
  }

  @keyframes anim-pop-bottom { from { opacity: 0; transform: translateY(60%) scale(0.7); } to { opacity: 1; transform: translateY(0) scale(1); } }
  @keyframes anim-pop-top    { from { opacity: 0; transform: translateY(-60%) scale(0.7); } to { opacity: 1; transform: translateY(0) scale(1); } }
  @keyframes anim-pop-left   { from { opacity: 0; transform: translateX(-60%) scale(0.7); } to { opacity: 1; transform: translateX(0) scale(1); } }
  @keyframes anim-pop-right  { from { opacity: 0; transform: translateX(60%) scale(0.7); } to { opacity: 1; transform: translateX(0) scale(1); } }
  @keyframes anim-fade-in    { from { opacity: 0; } to { opacity: 1; } }
  @keyframes anim-fade-in-shake {
    0%   { opacity: 0; transform: translateX(0); }
    30%  { opacity: 1; transform: translateX(-10px); }
    45%  { transform: translateX(9px); }
    60%  { transform: translateX(-7px); }
    75%  { transform: translateX(5px); }
    90%  { transform: translateX(-2px); }
    100% { opacity: 1; transform: translateX(0); }
  }
  @keyframes anim-fade-out        { from { opacity: 1; } to { opacity: 0; } }
  @keyframes anim-slide-out-left  { from { opacity: 1; transform: translateX(0); } to { opacity: 0; transform: translateX(-120%); } }
  @keyframes anim-slide-out-right { from { opacity: 1; transform: translateX(0); } to { opacity: 0; transform: translateX(120%); } }
  @keyframes anim-slide-out-top   { from { opacity: 1; transform: translateY(0); } to { opacity: 0; transform: translateY(-120%); } }
  @keyframes anim-slide-out-bottom{ from { opacity: 1; transform: translateY(0); } to { opacity: 0; transform: translateY(120%); } }

  /* Effect text captions */
  .effect-item .pic-wrap { position: relative; width: 100%; }
  .effect-item .pic-wrap .pic { width: 100%; height: auto; display: block; }
  .effect-text { margin: 4px 0; text-shadow: 0 1px 3px rgba(0,0,0,0.7); white-space: nowrap; }
  .effect-text.pos-middle { position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%); margin: 0; }
  .text-inner { display: inline-block; }
  @keyframes text-wobble { 0%, 100% { transform: rotate(0deg); } 25% { transform: rotate(-6deg); } 75% { transform: rotate(6deg); } }
  @keyframes text-shake  { 0%, 100% { transform: translateX(0); } 25% { transform: translateX(-4px); } 75% { transform: translateX(4px); } }
  @keyframes text-pulse  { 0%, 100% { transform: scale(1); } 50% { transform: scale(1.12); } }
  .text-inner.anim-wobble { animation: text-wobble 0.6s ease-in-out infinite; }
  .text-inner.anim-shake  { animation: text-shake 0.4s ease-in-out infinite; }
  .text-inner.anim-pulse  { animation: text-pulse 0.8s ease-in-out infinite; }
</style>
</head>
<body>
<div id="root"></div>
<script>
const ITEMS = __ITEMS_JSON__;
const EFFECTS = __EFFECTS_JSON__;
const PAGE_CONFIG_VERSION = __CONFIG_VERSION__;
const root = document.getElementById('root');
const state = {};       // devices:  id -> { lastLow, shown, lastSoundTs, el, audio, pic, pct }
const effectState = {}; // effects:  id -> { lastShown, shown, lastSoundTs, el, audio }

let missedPolls = 0;
const STALE_AFTER_MISSES = 3; // ~3 poll intervals of silence -> assume the app/Simulator closed

// Called once the server's gone quiet for a while, so a closed app (or a
// crash) doesn't leave stale content stuck on screen forever - hides
// everything currently shown; a later successful poll naturally re-shows
// whatever's actually true again.
function hideAllStale() {
  for (const item of ITEMS) {
    const s = state[item.id];
    if (!s) continue;
    if (item.show_mode === 'always') { s.el.classList.remove('visible'); }
    else { s.el.style.display = 'none'; s.shown = false; }
  }
  for (const effect of EFFECTS) {
    const s = effectState[effect.id];
    if (!s) continue;
    s.el.style.display = 'none';
    s.shown = false;
  }
}

const ENTER_KEYFRAMES = {
  pop_bottom: 'anim-pop-bottom',
  pop_top: 'anim-pop-top',
  pop_left: 'anim-pop-left',
  pop_right: 'anim-pop-right',
  fade: 'anim-fade-in',
  fade_shake: 'anim-fade-in-shake',
};
const EXIT_KEYFRAMES = {
  fade: 'anim-fade-out',
  slide_left: 'anim-slide-out-left',
  slide_right: 'anim-slide-out-right',
  slide_top: 'anim-slide-out-top',
  slide_bottom: 'anim-slide-out-bottom',
};
const ENTER_DUR_MS = 500;
const EXIT_DUR_MS = 450;

function isVideoSrc(src) { return /\.webm($|\?)/i.test(src || ''); }

// Idle animations a user can pick for a Device's Normal/Low picture, so a
// custom static image isn't stuck looking boring. Reuses the same wobble/
// shake/pulse keyframes as text styling. "none" clears any inline animation,
// letting the automatic low-battery glow (.item.low .pic, in CSS) show
// through undisturbed - picking a real animation for the Low picture
// intentionally replaces that glow with the user's own choice instead.
const PIC_ANIM_CSS = {
  none: '',
  wobble: 'text-wobble 0.6s ease-in-out infinite',
  shake: 'text-shake 0.4s ease-in-out infinite',
  pulse: 'text-pulse 0.8s ease-in-out infinite',
};
function applyPicAnimation(el, key) {
  if (el) el.style.animation = PIC_ANIM_CSS[key] || '';
}

// Applies font/color/animation/outline styling to a text span. Shared by
// Effect captions and Device Label/Battery % text so both get identical
// customization behavior.
function applyTextStyle(span, style) {
  style = style || {};
  span.className = 'text-inner anim-' + (style.text_animation || 'none');
  span.style.fontFamily = style.font_family || 'Segoe UI';
  span.style.fontSize = (style.font_size_px || 16) + 'px';
  span.style.color = style.font_color || '#ffffff';
  if (style.outline_enabled) {
    span.style.webkitTextStroke = (style.outline_thickness_px || 2) + 'px ' + (style.outline_color || '#000000');
    span.style.paintOrder = 'stroke fill';
  } else {
    span.style.webkitTextStroke = '';
    span.style.paintOrder = '';
  }
}

// Builds the DOM for one Effect (picture + optional styled caption). Reused
// for real configured effects and for the GUI's live "Test Animation" preview.
function buildEffectElement(cfg) {
  const el = document.createElement('div');
  el.className = 'item kf-driven effect-item';

  const picWrap = document.createElement('div');
  picWrap.className = 'pic-wrap';
  const video = isVideoSrc(cfg.pic_src);
  const pic = document.createElement(video ? 'video' : 'img');
  pic.className = 'pic';
  pic.src = cfg.pic_src;
  if (video) { pic.autoplay = true; pic.loop = true; pic.muted = true; pic.playsInline = true; }
  picWrap.appendChild(pic);

  let textEl = null;
  if (cfg.text) {
    textEl = document.createElement('div');
    textEl.className = 'effect-text pos-' + (cfg.text_position || 'below');
    const span = document.createElement('span');
    span.textContent = cfg.text;
    applyTextStyle(span, {
      font_family: cfg.font_family, font_size_px: cfg.font_size_px, font_color: cfg.font_color,
      text_animation: cfg.text_animation, outline_enabled: cfg.outline_enabled,
      outline_thickness_px: cfg.outline_thickness_px, outline_color: cfg.outline_color,
    });
    textEl.appendChild(span);
  }

  if (textEl && cfg.text_position === 'middle') {
    picWrap.appendChild(textEl);
    el.appendChild(picWrap);
  } else if (textEl && cfg.text_position === 'above') {
    el.appendChild(textEl);
    el.appendChild(picWrap);
  } else {
    el.appendChild(picWrap);
    if (textEl) el.appendChild(textEl);
  }

  return { el, pic };
}

let nudgeArrivalCounter = 0;

for (const item of ITEMS) {
  const el = document.createElement('div');
  el.className = 'item ' + (item.show_mode === 'always' ? 'always-mode' : 'kf-driven');
  if (item.nudge_enabled) el.classList.add('nudge-enabled');
  el.style.left = item.x_pct + '%';
  el.style.top = item.y_pct + '%';
  el.style.width = item.width_px + 'px';
  if (item.show_mode !== 'always') el.style.display = 'none';

  const isVideo = isVideoSrc(item.normal_src) || isVideoSrc(item.low_src);
  const pic = document.createElement(isVideo ? 'video' : 'img');
  pic.className = 'pic';
  pic.src = item.normal_src;
  if (isVideo) { pic.autoplay = true; pic.loop = true; pic.muted = true; pic.playsInline = true; }
  applyPicAnimation(pic, item.normal_pic_animation);
  el.appendChild(pic);

  let pctSpan = null;
  if (item.show_percent) {
    const pctDiv = document.createElement('div');
    pctDiv.className = 'pct';
    pctSpan = document.createElement('span');
    pctSpan.textContent = '--%';
    applyTextStyle(pctSpan, item.percent_style);
    pctDiv.appendChild(pctSpan);
    el.appendChild(pctDiv);
  }
  if (item.show_label) {
    const labelDiv = document.createElement('div');
    labelDiv.className = 'label';
    const labelSpan = document.createElement('span');
    labelSpan.textContent = item.label;
    applyTextStyle(labelSpan, item.label_style);
    labelDiv.appendChild(labelSpan);
    el.appendChild(labelDiv);
  }
  root.appendChild(el);

  const audio = item.sound_src ? new Audio(item.sound_src) : null;
  state[item.id] = { lastLow: false, shown: false, nudgeArrival: 0, lastSoundTs: 0, el, audio, pic, pct: pctSpan };
}

for (const effect of EFFECTS) {
  const { el, pic } = buildEffectElement(effect);
  el.style.left = effect.x_pct + '%';
  el.style.top = effect.y_pct + '%';
  el.style.width = effect.width_px + 'px';
  el.style.display = 'none';
  root.appendChild(el);

  const audio = effect.sound_src ? new Audio(effect.sound_src) : null;
  effectState[effect.id] = { lastShown: false, shown: false, lastSoundTs: 0, el, audio };
}

// Evaluates the trigger against a single device's live state ('dev' is
// undefined if that device isn't currently connected).
function effectTriggerMatches(effect, dev) {
  if (effect.trigger === 'device_disconnected') return !dev;
  if (effect.trigger === 'device_connected') return !!dev;
  if (!dev) return false;
  const battery = dev.battery_pct;
  if (battery === null || battery === undefined) return false;
  const isLow = battery <= effect.low_threshold_pct;
  if (effect.trigger === 'battery_low') return isLow;
  if (effect.trigger === 'battery_normal') return !isLow;
  return false;
}

// Resolves an effect's target (Specific device, or All devices minus any
// Ignore list) against the current status payload.
function effectShouldShow(effect, data) {
  if (effect.target_mode === 'all') {
    const ignore = new Set(effect.ignore_device_serials || []);
    const serials = Object.keys(data.known_devices || {}).filter((s) => !ignore.has(s));
    if (serials.length === 0) return false;
    const results = serials.map((s) => effectTriggerMatches(effect, data.devices[s]));
    return results.every(Boolean);
  }
  return effectTriggerMatches(effect, data.devices[effect.device_serial]);
}

// -- GUI "Test Animation" live preview (not a real configured item/effect) --
let previewEl = null;
let previewTimer = null;
let previewLastNonce = null;

function stopPreviewLoop() {
  if (previewTimer) { clearTimeout(previewTimer); previewTimer = null; }
  if (previewEl) { previewEl.remove(); previewEl = null; }
}

function ensurePreviewEl(p) {
  if (previewEl) previewEl.remove();
  if (p.mode === 'effect') {
    const built = buildEffectElement({
      pic_src: p.low_src, text: p.text, text_position: p.text_position,
      font_family: p.font_family, font_size_px: p.font_size_px, font_color: p.font_color,
      text_animation: p.text_animation, outline_enabled: p.outline_enabled,
      outline_thickness_px: p.outline_thickness_px, outline_color: p.outline_color,
    });
    previewEl = built.el;
  } else {
    previewEl = document.createElement('div');
    previewEl.className = 'item kf-driven low';
    const isVideo = isVideoSrc(p.low_src);
    const pic = document.createElement(isVideo ? 'video' : 'img');
    pic.className = 'pic low';
    pic.src = p.low_src;
    if (isVideo) { pic.autoplay = true; pic.loop = true; pic.muted = true; pic.playsInline = true; }
    applyPicAnimation(pic, p.low_pic_animation);
    previewEl.appendChild(pic);
    if (p.show_percent) {
      const pctDiv = document.createElement('div');
      pctDiv.className = 'pct';
      const pctSpan = document.createElement('span');
      pctSpan.textContent = 'low%';
      applyTextStyle(pctSpan, p.percent_style);
      pctDiv.appendChild(pctSpan);
      previewEl.appendChild(pctDiv);
    }
    if (p.show_label) {
      const labelDiv = document.createElement('div');
      labelDiv.className = 'label';
      const labelSpan = document.createElement('span');
      labelSpan.textContent = p.label;
      applyTextStyle(labelSpan, p.label_style);
      labelDiv.appendChild(labelSpan);
      previewEl.appendChild(labelDiv);
    }
  }
  previewEl.style.left = p.x_pct + '%';
  previewEl.style.top = p.y_pct + '%';
  previewEl.style.width = p.width_px + 'px';
  previewEl.style.display = 'none';
  document.body.appendChild(previewEl);
}

function runPreviewLoop(p) {
  ensurePreviewEl(p);
  const enterKey = ENTER_KEYFRAMES[p.enter] || ENTER_KEYFRAMES.fade;
  const exitKey = EXIT_KEYFRAMES[p.exit] || EXIT_KEYFRAMES.fade;
  const holdMs = 1200, gapMs = 500;

  function cycle() {
    if (!previewEl) return;
    previewEl.style.display = 'flex';
    void previewEl.offsetWidth; // force reflow so the animation restarts
    previewEl.style.animation = `${enterKey} ${ENTER_DUR_MS}ms cubic-bezier(0.34,1.56,0.64,1) forwards`;
    previewTimer = setTimeout(() => {
      if (!previewEl) return;
      previewEl.style.animation = `${exitKey} ${EXIT_DUR_MS}ms ease forwards`;
      previewTimer = setTimeout(() => {
        if (!previewEl) return;
        previewEl.style.display = 'none';
        previewTimer = setTimeout(cycle, gapMs);
      }, EXIT_DUR_MS);
    }, ENTER_DUR_MS + holdMs);
  }
  cycle();
}

// Groups currently-visible Nudge-enabled Device items by anchor position +
// direction, then lines them up in arrival order (newest = original spot,
// older ones pushed back) - recomputed fresh every poll tick, so both new
// arrivals and departures (re-compacting the line) fall out naturally.
function applyNudgeLayout() {
  const groups = {};
  for (const item of ITEMS) {
    if (!item.nudge_enabled || !item.nudge_group_id) continue;
    const s = state[item.id];
    if (!s.shown) continue;
    const key = item.nudge_group_id;
    (groups[key] = groups[key] || []).push({ item, s });
  }
  for (const key in groups) {
    const members = groups[key];
    members.sort((a, b) => b.s.nudgeArrival - a.s.nudgeArrival); // newest first = slot 0
    members.forEach((m, slot) => {
      const pitchPx = m.item.width_px + m.item.nudge_spacing_px;
      let dxPx = 0, dyPx = 0;
      if (m.item.nudge_direction === 'left') dxPx = -slot * pitchPx;
      else if (m.item.nudge_direction === 'right') dxPx = slot * pitchPx;
      else if (m.item.nudge_direction === 'up') dyPx = -slot * pitchPx;
      else if (m.item.nudge_direction === 'down') dyPx = slot * pitchPx;
      m.s.el.style.left = (m.item.x_pct + dxPx / 1920 * 100) + '%';
      m.s.el.style.top = (m.item.y_pct + dyPx / 1080 * 100) + '%';
    });
  }
}

async function poll() {
  try {
    const res = await fetch('/api/status', { cache: 'no-store' });
    const data = await res.json();
    missedPolls = 0;

    if (data.config_version !== undefined && data.config_version !== PAGE_CONFIG_VERSION) {
      // A Device/Effect was added/edited/removed since this page loaded -
      // reload to pick up the new ITEMS/EFFECTS instead of going stale
      // (OBS's Browser Source never re-fetches this page on its own).
      location.reload();
      return;
    }

    for (const item of ITEMS) {
      const s = state[item.id];
      const dev = data.devices[item.device_serial];
      if (!dev) {
        if (item.show_mode === 'always') { s.el.classList.remove('visible'); }
        else { s.el.style.display = 'none'; s.shown = false; }
        continue;
      }

      const battery = dev.battery_pct;
      const isLow = battery !== null && battery !== undefined && battery <= item.low_threshold_pct;

      const wantSrc = isLow ? item.low_src : item.normal_src;
      if (s.pic && s.pic.getAttribute('src') !== wantSrc) s.pic.setAttribute('src', wantSrc);
      applyPicAnimation(s.pic, isLow ? item.low_pic_animation : item.normal_pic_animation);
      if (s.pct) s.pct.textContent = (battery === null || battery === undefined) ? '--%' : Math.round(battery) + '%';
      s.el.classList.toggle('low', isLow);

      if (item.show_mode === 'always') {
        s.el.classList.add('visible');
      } else {
        if (isLow && !s.shown) {
          s.el.style.display = 'flex';
          void s.el.offsetWidth;
          const enterKey = ENTER_KEYFRAMES[item.enter_animation] || ENTER_KEYFRAMES.pop_bottom;
          s.el.style.animation = `${enterKey} ${ENTER_DUR_MS}ms cubic-bezier(0.34,1.56,0.64,1) forwards`;
          s.shown = true;
          s.nudgeArrival = ++nudgeArrivalCounter;
        } else if (!isLow && s.shown) {
          const exitKey = EXIT_KEYFRAMES[item.exit_animation] || EXIT_KEYFRAMES.fade;
          s.el.style.animation = `${exitKey} ${EXIT_DUR_MS}ms ease forwards`;
          s.shown = false;
          const elRef = s.el;
          setTimeout(() => { if (!s.shown) elRef.style.display = 'none'; }, EXIT_DUR_MS + 20);
        }
      }

      const now = Date.now();
      if (isLow && s.audio && (!s.lastLow || now - s.lastSoundTs > item.sound_cooldown_sec * 1000)) {
        s.audio.currentTime = 0;
        s.audio.play().catch(() => {});
        s.lastSoundTs = now;
      }
      s.lastLow = isLow;
    }

    applyNudgeLayout();

    for (const effect of EFFECTS) {
      const s = effectState[effect.id];
      const shouldShow = effectShouldShow(effect, data);

      if (shouldShow && !s.shown) {
        s.el.style.display = 'flex';
        void s.el.offsetWidth;
        const enterKey = ENTER_KEYFRAMES[effect.enter_animation] || ENTER_KEYFRAMES.pop_bottom;
        s.el.style.animation = `${enterKey} ${ENTER_DUR_MS}ms cubic-bezier(0.34,1.56,0.64,1) forwards`;
        s.shown = true;
      } else if (!shouldShow && s.shown) {
        const exitKey = EXIT_KEYFRAMES[effect.exit_animation] || EXIT_KEYFRAMES.fade;
        s.el.style.animation = `${exitKey} ${EXIT_DUR_MS}ms ease forwards`;
        s.shown = false;
        const elRef = s.el;
        setTimeout(() => { if (!s.shown) elRef.style.display = 'none'; }, EXIT_DUR_MS + 20);
      }

      const now = Date.now();
      if (shouldShow && s.audio && (!s.lastShown || now - s.lastSoundTs > effect.sound_cooldown_sec * 1000)) {
        s.audio.currentTime = 0;
        s.audio.play().catch(() => {});
        s.lastSoundTs = now;
      }
      s.lastShown = shouldShow;
    }

    if (data.preview && data.preview.active) {
      if (data.preview.nonce !== previewLastNonce) {
        previewLastNonce = data.preview.nonce;
        stopPreviewLoop();
        runPreviewLoop(data.preview);
      }
    } else if (previewLastNonce !== null) {
      previewLastNonce = null;
      stopPreviewLoop();
    }
  } catch (e) {
    // Could be a momentary hiccup, or the app (or Simulator) has actually
    // closed - after a few consecutive misses, assume the latter and clear
    // the overlay instead of leaving stale content stuck on screen forever.
    missedPolls++;
    if (missedPolls === STALE_AFTER_MISSES) hideAllStale();
  }
  setTimeout(poll, __POLL_MS__);
}
poll();
</script>
</body>
</html>
"""

INDEX_PAGE = """<!doctype html>
<html><head><meta charset="utf-8"><title>__APP_TITLE__</title></head>
<body style="font-family: sans-serif; max-width: 640px; margin: 40px auto;">
<h2>__APP_TITLE__</h2>
<p>Overlay server is running. In OBS, add a <b>Browser Source</b> pointed at:</p>
<pre>{overlay_url}</pre>
<p>Recommended size: 1920x1080 (matches your canvas). Leave "Shutdown source when not visible" unchecked if you want low-battery sounds to keep working while the scene isn't active.</p>
</body></html>
""".replace("__APP_TITLE__", APP_TITLE)


class _Handler(BaseHTTPRequestHandler):
    server_version = "OhFudgeMyBatteryChat/1.0"

    def log_message(self, fmt, *args):
        pass  # keep the console quiet; the GUI shows its own status

    def _send_json(self, payload, status=200):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _send_html(self, html, status=200):
        body = html.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _send_file(self, full_path):
        if not os.path.isfile(full_path):
            self.send_error(404, "Not found")
            return
        ctype, _ = mimetypes.guess_type(full_path)
        with open(full_path, "rb") as f:
            data = f.read()
        self.send_response(200)
        self.send_header("Content-Type", ctype or "application/octet-stream")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        path = urlsplit(self.path).path
        path = posixpath.normpath(path)

        if path == "/":
            cfg = self.server.get_config()
            url = f"http://127.0.0.1:{cfg.port}/overlay"
            self._send_html(INDEX_PAGE.format(overlay_url=url))
            return

        if path == "/overlay":
            self._handle_overlay()
            return

        if path == "/api/status":
            snapshot = self.server.vr_monitor.get_snapshot()
            payload = _device_payload(snapshot)
            payload["preview"] = _preview_payload(self.server.preview_state)
            payload["config_version"] = _config_version()
            self._send_json(payload)
            return

        if path == "/media/_preview/low":
            p = self.server.preview_state.get()
            low_path = p.get("low_path") if p else None
            if not low_path or not os.path.isfile(low_path):
                self.send_error(404, "No preview media")
                return
            self._send_file(low_path)
            return

        if path.startswith("/media/"):
            self._handle_media(path)
            return

        if path.startswith("/defaults/"):
            fname = os.path.basename(path)
            self._send_file(os.path.join(paths.defaults_dir(), fname))
            return

        self.send_error(404, "Not found")

    def _handle_overlay(self):
        cfg = self.server.get_config()
        from . import default_assets
        default_assets.ensure_defaults()
        nudge_groups_by_id = {g.id: g for g in cfg.nudge_groups}
        items_json = json.dumps([_item_payload(it, DEFAULTS_BY_CLASS, nudge_groups_by_id) for it in cfg.items])
        effects_json = json.dumps([_effect_payload(ef, DEFAULTS_BY_CLASS) for ef in cfg.effects])
        html = OVERLAY_PAGE_TEMPLATE.replace("__APP_TITLE__", APP_TITLE)
        html = html.replace("__ITEMS_JSON__", items_json)
        html = html.replace("__EFFECTS_JSON__", effects_json)
        html = html.replace("__POLL_MS__", str(int(max(0.25, cfg.poll_interval_sec) * 1000)))
        html = html.replace("__CONFIG_VERSION__", json.dumps(_config_version()))
        self._send_html(html)

    def _handle_media(self, path):
        parts = path.split("/")
        cfg = self.server.get_config()

        if len(parts) == 5 and parts[2] == "effect":
            # /media/effect/<effect_id>/<kind>   kind in picture|sound
            _, _, _, effect_id, kind = parts
            effect = next((e for e in cfg.effects if e.id == effect_id), None)
            if effect is None:
                self.send_error(404, "Unknown effect")
                return
            rel = {"picture": effect.picture, "sound": effect.sound}.get(kind)
            full = config_mod.resolve_media(rel)
            if not full:
                self.send_error(404, "No media set")
                return
            self._send_file(full)
            return

        if len(parts) == 4:
            # /media/<item_id>/<kind>   kind in normal|low|sound
            _, _, item_id, kind = parts
            item = next((it for it in cfg.items if it.id == item_id), None)
            if item is None:
                self.send_error(404, "Unknown item")
                return
            rel = {"normal": item.normal_image, "low": item.low_image, "sound": item.sound}.get(kind)
            full = config_mod.resolve_media(rel)
            if not full:
                self.send_error(404, "No media set")
                return
            self._send_file(full)
            return

        self.send_error(404, "Not found")


def find_free_port() -> int:
    """Asks the OS for a currently-unused TCP port on 127.0.0.1."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class OverlayHTTPServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, port: int, get_config, vr_monitor: VRMonitor, preview_state: PreviewState):
        super().__init__(("127.0.0.1", port), _Handler)
        self.get_config = get_config
        self.vr_monitor = vr_monitor
        self.preview_state = preview_state


class ServerController:
    """Starts/stops the overlay HTTP server on a background thread from the GUI."""

    def __init__(self, get_config, vr_monitor: VRMonitor):
        self.get_config = get_config
        self.vr_monitor = vr_monitor
        self.preview_state = PreviewState()
        self._server: OverlayHTTPServer = None
        self._thread: threading.Thread = None

    @property
    def running(self) -> bool:
        return self._server is not None

    @property
    def port(self):
        return self._server.server_address[1] if self._server else None

    def start(self) -> bool:
        """Returns True if the server actually started, False if the
        configured port was already in use (self._server stays None) -
        callers decide how to surface that (e.g. a port-in-use warning)
        instead of letting the bind error crash the app."""
        if self.running:
            return True
        port = self.get_config().port
        try:
            self._server = OverlayHTTPServer(port, self.get_config, self.vr_monitor, self.preview_state)
        except OSError:
            self._server = None
            return False
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()
        return True

    def stop(self):
        if not self.running:
            return
        self._server.shutdown()
        self._server.server_close()
        self._server = None
        self._thread = None
