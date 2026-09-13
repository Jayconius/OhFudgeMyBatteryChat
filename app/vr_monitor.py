"""Background thread that polls SteamVR (via OpenVR) for connected devices
and their battery state.

Devices are keyed by serial number (stable across reboots/reconnects) rather
than tracked-device index (which SteamVR can reassign), so a saved overlay
item keeps pointing at "your right controller" even if SteamVR renumbers it.

Each poll also checks for a small external "fake signal" file (see
paths.fake_signal_path() / tools/fake_vr_signal_simulator.py) before touching
real OpenVR at all - if it exists and was written recently, its devices are
used for that cycle instead of real hardware, so a separate standalone tool
can feed this app fake devices for demos/testing. No file, or a stale one
(the simulator closed/crashed) -> falls straight back to real SteamVR, same
as always.
"""
import json
import os
import threading
import time
from dataclasses import dataclass, field
from typing import Dict, Optional

from . import paths

try:
    import openvr
except ImportError:  # pragma: no cover - dev environments without the package yet
    openvr = None

FAKE_SIGNAL_MAX_AGE_SEC = 3.0  # simulator heartbeats faster than this; older -> treated as gone

CLASS_NAMES = {
    getattr(openvr, "TrackedDeviceClass_HMD", 1): "HMD",
    getattr(openvr, "TrackedDeviceClass_Controller", 2): "Controller",
    getattr(openvr, "TrackedDeviceClass_GenericTracker", 3): "GenericTracker",
    getattr(openvr, "TrackedDeviceClass_TrackingReference", 4): "TrackingReference",
} if openvr else {}


@dataclass
class DeviceState:
    serial: str
    device_class: str
    model: str
    index: int
    battery_pct: Optional[float]  # 0-100, or None if the device doesn't report one
    charging: Optional[bool]
    role: str = ""
    manufacturer: str = ""


@dataclass
class Snapshot:
    steamvr_connected: bool
    devices: Dict[str, DeviceState] = field(default_factory=dict)  # currently connected only
    known_devices: Dict[str, DeviceState] = field(default_factory=dict)  # every serial ever seen this run, incl. now-disconnected ones (last-known state)
    error: str = ""


class VRMonitor:
    def __init__(self, poll_interval_sec: float = 1.0):
        self.poll_interval_sec = poll_interval_sec
        self._lock = threading.Lock()
        self._snapshot = Snapshot(steamvr_connected=False)
        self._known: Dict[str, DeviceState] = {}
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._vr_system = None

    def start(self):
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self):
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=2)
        self._shutdown_openvr()

    def get_snapshot(self) -> Snapshot:
        with self._lock:
            return Snapshot(
                steamvr_connected=self._snapshot.steamvr_connected,
                devices=dict(self._snapshot.devices),
                known_devices=dict(self._snapshot.known_devices),
                error=self._snapshot.error,
            )

    def _shutdown_openvr(self):
        if self._vr_system is not None and openvr is not None:
            try:
                openvr.shutdown()
            except Exception:
                pass
            self._vr_system = None

    def _try_init(self) -> bool:
        if openvr is None:
            with self._lock:
                self._snapshot.error = "The 'openvr' package is not installed."
            return False
        try:
            self._vr_system = openvr.init(openvr.VRApplication_Background)
            return True
        except Exception as exc:
            self._vr_system = None
            with self._lock:
                self._snapshot.steamvr_connected = False
                self._snapshot.error = f"SteamVR not found ({exc})"
            return False

    def _apply_devices(self, devices: Dict[str, DeviceState], connected: bool, error: str = ""):
        self._known.update(devices)  # remember every serial seen, even after it disconnects
        with self._lock:
            self._snapshot.steamvr_connected = connected
            self._snapshot.devices = devices
            self._snapshot.known_devices = dict(self._known)
            self._snapshot.error = error

    def _read_fake_signal(self) -> Optional[Dict[str, DeviceState]]:
        """Returns a devices dict from the fake-signal file if it exists and
        is fresh, else None (meaning: no simulator running, use real OpenVR)."""
        path = paths.fake_signal_path()
        try:
            mtime = os.path.getmtime(path)
        except OSError:
            return None
        if time.time() - mtime > FAKE_SIGNAL_MAX_AGE_SEC:
            return None
        try:
            with open(path, "r", encoding="utf-8-sig") as f:
                raw = json.load(f)
        except (OSError, ValueError):
            return None

        devices: Dict[str, DeviceState] = {}
        for serial, d in raw.get("devices", {}).items():
            if not isinstance(d, dict):
                continue
            devices[serial] = DeviceState(
                serial=serial,
                device_class=d.get("device_class", "Other"),
                model=d.get("model", ""),
                index=-1,
                battery_pct=d.get("battery_pct"),
                charging=d.get("charging"),
                role=d.get("role", ""),
                manufacturer=d.get("manufacturer", ""),
            )
        return devices

    def _poll_once(self):
        devices: Dict[str, DeviceState] = {}
        vr = self._vr_system
        for i in range(openvr.k_unMaxTrackedDeviceCount):
            try:
                if not vr.isTrackedDeviceConnected(i):
                    continue
            except Exception:
                continue

            try:
                raw_class = vr.getTrackedDeviceClass(i)
                device_class = CLASS_NAMES.get(raw_class, "Other")
            except Exception:
                device_class = "Other"

            try:
                serial = vr.getStringTrackedDeviceProperty(i, openvr.Prop_SerialNumber_String)
            except Exception:
                continue  # no stable identity, skip
            if not serial:
                continue

            try:
                model = vr.getStringTrackedDeviceProperty(i, openvr.Prop_ModelNumber_String)
            except Exception:
                model = ""

            try:
                manufacturer = vr.getStringTrackedDeviceProperty(i, openvr.Prop_ManufacturerName_String)
            except Exception:
                manufacturer = ""

            battery_pct = None
            try:
                raw = vr.getFloatTrackedDeviceProperty(i, openvr.Prop_DeviceBatteryPercentage_Float)
                battery_pct = round(raw * 100, 1)
            except Exception:
                battery_pct = None

            charging = None
            try:
                charging = bool(vr.getBoolTrackedDeviceProperty(i, openvr.Prop_DeviceIsCharging_Bool))
            except Exception:
                charging = None

            role = ""
            if device_class == "Controller":
                try:
                    raw_role = vr.getControllerRoleForTrackedDeviceIndex(i)
                    role = {
                        getattr(openvr, "TrackedControllerRole_LeftHand", 1): "Left",
                        getattr(openvr, "TrackedControllerRole_RightHand", 2): "Right",
                    }.get(raw_role, "")
                except Exception:
                    role = ""

            devices[serial] = DeviceState(
                serial=serial,
                device_class=device_class,
                model=model,
                index=i,
                battery_pct=battery_pct,
                charging=charging,
                role=role,
                manufacturer=manufacturer,
            )

        self._apply_devices(devices, connected=True)

    def _run(self):
        while not self._stop.is_set():
            fake_devices = self._read_fake_signal()
            if fake_devices is not None:
                self._apply_devices(fake_devices, connected=True)
                self._stop.wait(self.poll_interval_sec)
                continue

            if self._vr_system is None:
                if not self._try_init():
                    self._stop.wait(3.0)
                    continue
            try:
                self._poll_once()
            except Exception as exc:
                with self._lock:
                    self._snapshot.steamvr_connected = False
                    self._snapshot.error = f"Lost connection to SteamVR ({exc})"
                self._shutdown_openvr()
            self._stop.wait(self.poll_interval_sec)
