"""Windows recording-device (microphone) support: listing the devices for the
pickers, watching the few an Effect or macro actually references, and
setting their Windows mute flag for the mute macros.

Design notes (all confirmed against a real wireless mic, see HANDOFF.md):
- Only devices something references are polled; everything else is ignored,
  so a dozen virtual drivers cost nothing.
- Switching a wireless transmitter off, or unplugging its receiver, shows up
  in Windows as the endpoint going ACTIVE -> NOTPRESENT, so "disconnected" is
  detectable. Moving the receiver to a *different* USB port creates a new
  endpoint id (the old one stays NOTPRESENT) - see find_rebind_candidates.
- A device's own hardware mute button usually does NOT change Windows' mute
  flag, so the Mic Muted trigger only reflects Windows-level mute. "Talking"
  / "silent for N seconds" come from the live audio level instead.
- All COM objects live on the monitor's own thread. Creating/releasing them
  from several threads (or many times a second) crashes comtypes on Release,
  so interfaces are acquired once, reused, and dropped before COM shuts down.
"""
import gc
import json
import os
import queue
import re
import threading
import time
from dataclasses import dataclass
from typing import Dict, List, Optional

from . import paths

try:
    import winreg
except ImportError:  # pragma: no cover - non-Windows dev environments
    winreg = None

try:
    import comtypes
    from comtypes import CLSCTX_ALL
    from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume, IAudioMeterInformation
    COM_AVAILABLE = True
except Exception:  # pragma: no cover - pycaw/comtypes not installed
    comtypes = None
    COM_AVAILABLE = False

CAPTURE_PREFIX = "{0.0.1.00000000}."
_MMDEVICES_CAPTURE = r"SOFTWARE\Microsoft\Windows\CurrentVersion\MMDevices\Audio\Capture"
_KEY_DESC = "{a45c254e-df1c-4efd-8020-67d146a850e0},2"       # e.g. "Microphone"
_KEY_IFACE = "{b3f8fa53-0004-438e-9003-51a46e139bfc},6"      # e.g. "Antlion Wireless Microphone"
_KEY_ENUMERATOR = "{a45c254e-df1c-4efd-8020-67d146a850e0},24"  # "USB", "HDAUDIO", "ROOT" (virtual driver)...
STATES = {1: "ACTIVE", 2: "DISABLED", 4: "NOTPRESENT", 8: "UNPLUGGED"}
VIRTUAL_ENUMERATORS = {"ROOT", "SWD"}

POLL_SEC = 0.2
TALK_ABOVE = 0.005     # peak at/above this counts as voice; a quiet idle mic sat at <= 0.002
TALK_HOLD_SEC = 1.0    # "talking" stays true this long after the last loud sample
FAKE_SIGNAL_MAX_AGE_SEC = 3.0  # same freshness rule VRMonitor uses for the Simulator's file
COMMAND_TIMEOUT_SEC = 3.0


@dataclass
class Endpoint:
    id: str
    name: str            # Windows' own name - generic, e.g. "Microphone (USB Audio Device)"
    state: str           # ACTIVE / DISABLED / NOTPRESENT / UNPLUGGED
    virtual: bool = False
    simulated: bool = False

    @property
    def connected(self) -> bool:
        return self.state == "ACTIVE"


def normalize_name(name: str) -> str:
    """Comparable form of a device name: Windows prefixes a number ("2- ") to
    the second copy of a device name, which is exactly what changes when a
    receiver moves ports - so it's stripped before matching."""
    text = re.sub(r"\b\d+-\s*", "", name or "")
    return re.sub(r"\s+", " ", text).strip().lower()


def _reg_str(key, name) -> str:
    try:
        value, _ = winreg.QueryValueEx(key, name)
        return value if isinstance(value, str) else ""
    except OSError:
        return ""


def list_registry_endpoints() -> List[Endpoint]:
    """Every recording endpoint Windows knows, including unplugged ones -
    read straight from the MMDevices registry (instant, no COM)."""
    if winreg is None:
        return []
    out: List[Endpoint] = []
    try:
        root = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, _MMDEVICES_CAPTURE)
    except OSError:
        return out
    with root:
        i = 0
        while True:
            try:
                guid = winreg.EnumKey(root, i)
            except OSError:
                break
            i += 1
            try:
                with winreg.OpenKey(root, guid) as ep:
                    raw_state, _ = winreg.QueryValueEx(ep, "DeviceState")
                    with winreg.OpenKey(ep, "Properties") as props:
                        desc = _reg_str(props, _KEY_DESC)
                        iface = _reg_str(props, _KEY_IFACE)
                        enumerator = _reg_str(props, _KEY_ENUMERATOR)
            except OSError:
                continue
            name = f"{desc} ({iface})" if desc and iface else (desc or iface or guid)
            out.append(Endpoint(
                id=CAPTURE_PREFIX + guid,
                name=name,
                state=STATES.get(raw_state & 0xF, "UNKNOWN"),
                virtual=enumerator.upper() in VIRTUAL_ENUMERATORS,
            ))
    return out


def _read_fake_audio() -> Optional[Dict[str, dict]]:
    """The Simulator's fake microphones, if its signal file is fresh."""
    path = paths.fake_signal_path()
    try:
        if time.time() - os.path.getmtime(path) > FAKE_SIGNAL_MAX_AGE_SEC:
            return None
        with open(path, "r", encoding="utf-8-sig") as f:
            raw = json.load(f)
    except (OSError, ValueError):
        return None
    audio = raw.get("audio")
    return audio if isinstance(audio, dict) else None


def list_endpoints() -> List[Endpoint]:
    """Registry endpoints plus any Simulator microphones."""
    endpoints = list_registry_endpoints()
    for eid, d in (_read_fake_audio() or {}).items():
        if isinstance(d, dict):
            endpoints.append(Endpoint(
                id=eid, name=d.get("name") or eid,
                state=d.get("state", "ACTIVE") if d.get("state") in STATES.values() else "ACTIVE",
                simulated=True,
            ))
    return endpoints


def display_name(endpoint_id: str, windows_name: str, nicknames: Dict[str, str]) -> str:
    nick = (nicknames or {}).get(endpoint_id, "").strip()
    return nick or windows_name or endpoint_id


def find_rebind_candidates(saved: Dict[str, str], endpoints: Optional[List[Endpoint]] = None):
    """saved: {endpoint_id: last-known Windows name} for everything an Effect
    or macro points at. Returns [(old_id, new_id, name)] for each saved device
    that's no longer active where exactly one *other* active device has the
    same normalized name and isn't already something saved - i.e. the
    receiver moved to another USB port and Windows gave it a new id. Ambiguous
    matches (two identical mics) are left alone rather than guessed at."""
    endpoints = endpoints if endpoints is not None else list_endpoints()
    by_id = {e.id: e for e in endpoints}
    active_free = [e for e in endpoints if e.connected and e.id not in saved]
    out = []
    claimed = set()
    for old_id, name in saved.items():
        current = by_id.get(old_id)
        if current is not None and current.connected:
            continue
        wanted = normalize_name(name or (current.name if current else ""))
        if not wanted:
            continue
        matches = [e for e in active_free if normalize_name(e.name) == wanted and e.id not in claimed]
        if len(matches) == 1:
            claimed.add(matches[0].id)
            out.append((old_id, matches[0].id, matches[0].name))
    return out


class _Handles:
    __slots__ = ("mm", "vol", "meter")

    def __init__(self):
        self.mm = self.vol = self.meter = None


class AudioMonitor:
    def __init__(self, get_config):
        self.get_config = get_config
        self._lock = threading.Lock()
        self._snap: Dict[str, dict] = {}
        self._commands: "queue.Queue" = queue.Queue()
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._handles: Dict[str, _Handles] = {}
        self._last_loud: Dict[str, float] = {}
        self._connected_since: Dict[str, float] = {}
        self._fake_mute_override: Dict[str, tuple] = {}  # id -> (muted, file value when set)
        self._enum = None

    # -- lifecycle -----------------------------------------------------
    def start(self):
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self):
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=3)
        self._thread = None

    # -- public API (any thread) ---------------------------------------
    def get_snapshot(self) -> Dict[str, dict]:
        with self._lock:
            return {k: dict(v) for k, v in self._snap.items()}

    def set_mute(self, endpoint_id: str, action: str) -> dict:
        """action: "toggle" | "mute" | "unmute". Blocks (up to a few seconds)
        while the monitor thread does the COM call. Returns
        {"ok": bool, "muted": bool|None, "error": str}."""
        result = {"ok": False, "muted": None, "error": "audio monitor isn't running"}
        if not self._thread or not self._thread.is_alive():
            return result
        done = threading.Event()
        holder = {}
        self._commands.put((endpoint_id, action, holder, done))
        if not done.wait(COMMAND_TIMEOUT_SEC):
            return {"ok": False, "muted": None, "error": "timed out"}
        return holder

    # -- monitor thread ------------------------------------------------
    def _watched_ids(self) -> set:
        cfg = self.get_config()
        ids = {e.audio_endpoint_id for e in cfg.effects
               if getattr(e, "target_mode", "") == "audio" and e.audio_endpoint_id}
        ids |= {m.endpoint_id for m in cfg.macros if m.endpoint_id}
        return ids

    def _run(self):
        if COM_AVAILABLE:
            comtypes.CoInitialize()
            try:
                self._enum = AudioUtilities.GetDeviceEnumerator()
            except Exception:
                self._enum = None
        try:
            while not self._stop.is_set():
                try:
                    self._tick()
                except Exception:
                    pass  # one bad cycle must never end monitoring
                self._stop.wait(POLL_SEC)
        finally:
            self._handles.clear()
            self._enum = None
            gc.collect()
            if COM_AVAILABLE:
                comtypes.CoUninitialize()

    def _tick(self):
        now = time.time()
        fake = _read_fake_audio() or {}
        watched = self._watched_ids()
        snap: Dict[str, dict] = {}

        self._process_commands(fake)

        for eid in watched:
            if eid in fake:
                state, muted, peak = self._read_fake(eid, fake[eid])
                name = fake[eid].get("name", eid)
            else:
                state, muted, peak = self._read_real(eid)
                name = ""
            snap[eid] = self._build_entry(eid, state, muted, peak, name, now)

        for eid in list(self._handles):
            if eid not in watched:
                del self._handles[eid]
        with self._lock:
            self._snap = snap

    def _build_entry(self, eid, state, muted, peak, name, now):
        connected = state == "ACTIVE"
        if connected:
            self._connected_since.setdefault(eid, now)
            if peak is not None and peak >= TALK_ABOVE:
                self._last_loud[eid] = now
        else:
            self._connected_since.pop(eid, None)
            self._last_loud.pop(eid, None)
        last_loud = self._last_loud.get(eid)
        # Silence is measured from the last loud sample, or from the moment
        # the device (re)connected if it hasn't made a sound since.
        since_loud = now - (last_loud if last_loud is not None else self._connected_since[eid]) if connected else 0.0
        return {
            "state": state,
            "connected": connected,
            "muted": muted,
            "peak": round(peak, 4) if peak is not None else None,
            "talking": bool(connected and last_loud is not None and now - last_loud < TALK_HOLD_SEC),
            "silent_sec": round(since_loud, 1),
            "name": name,
        }

    # -- real devices (COM) --------------------------------------------
    def _acquire(self, eid) -> _Handles:
        h = _Handles()
        if not COM_AVAILABLE or self._enum is None:
            return h
        try:
            h.mm = self._enum.GetDevice(eid)
            h.vol = h.mm.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None).QueryInterface(IAudioEndpointVolume)
            h.meter = h.mm.Activate(IAudioMeterInformation._iid_, CLSCTX_ALL, None).QueryInterface(IAudioMeterInformation)
        except Exception:
            pass
        return h

    def _handles_for(self, eid) -> _Handles:
        h = self._handles.get(eid)
        if h is None or h.mm is None:
            h = self._acquire(eid)
            self._handles[eid] = h
        return h

    def _read_real(self, eid):
        """(state, muted, peak); muted/peak None when unreadable right now."""
        h = self._handles_for(eid)
        if h.mm is None:
            return "GONE", None, None
        try:
            state = STATES.get(h.mm.GetState() & 0xF, "UNKNOWN")
        except Exception:
            h.mm = None
            return "GONE", None, None
        if state != "ACTIVE":
            h.vol = h.meter = None
            return state, None, None
        if h.vol is None or h.meter is None:
            fresh = self._acquire(eid)
            self._handles[eid] = h = fresh if fresh.mm is not None else h
        muted = peak = None
        try:
            muted = bool(h.vol.GetMute())
            peak = float(h.meter.GetPeakValue())
        except Exception:
            h.vol = h.meter = None
        return state, muted, peak

    # -- Simulator microphones -----------------------------------------
    def _read_fake(self, eid, d):
        state = d.get("state") if d.get("state") in STATES.values() else "ACTIVE"
        if state != "ACTIVE":
            return state, None, None
        file_muted = bool(d.get("muted", False))
        override = self._fake_mute_override.get(eid)
        if override is not None and override[1] != file_muted:
            del self._fake_mute_override[eid]  # the Simulator's own checkbox changed - it wins again
            override = None
        muted = override[0] if override is not None else file_muted
        return state, muted, float(d.get("peak", 0.0))

    # -- mute commands -------------------------------------------------
    def _process_commands(self, fake):
        while True:
            try:
                eid, action, holder, done = self._commands.get_nowait()
            except queue.Empty:
                return
            try:
                holder.update(self._do_mute(eid, action, fake))
            except Exception as exc:
                holder.update({"ok": False, "muted": None, "error": str(exc)})
            finally:
                done.set()

    def _do_mute(self, eid, action, fake):
        if eid in fake:
            if fake[eid].get("state", "ACTIVE") != "ACTIVE":
                return {"ok": False, "muted": None, "error": "device isn't connected"}
            file_muted = bool(fake[eid].get("muted", False))
            override = self._fake_mute_override.get(eid)
            current = override[0] if override is not None else file_muted
            target = (not current) if action == "toggle" else (action == "mute")
            self._fake_mute_override[eid] = (target, file_muted)
            return {"ok": True, "muted": target, "error": ""}

        h = self._handles_for(eid)
        if h.mm is None:
            return {"ok": False, "muted": None, "error": "device not found"}
        if STATES.get(h.mm.GetState() & 0xF) != "ACTIVE":
            return {"ok": False, "muted": None, "error": "device isn't connected"}
        if h.vol is None:
            fresh = self._acquire(eid)
            self._handles[eid] = h = fresh
            if h.vol is None:
                return {"ok": False, "muted": None, "error": "couldn't open the device's volume control"}
        current = bool(h.vol.GetMute())
        target = (not current) if action == "toggle" else (action == "mute")
        if target != current:
            h.vol.SetMute(1 if target else 0, None)
        return {"ok": True, "muted": bool(h.vol.GetMute()), "error": ""}
