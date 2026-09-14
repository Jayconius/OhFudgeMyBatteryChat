"""Standalone fake-SteamVR signal emitter for demo recordings/testing.

This is a genuinely separate, lightweight tool - it does NOT launch a copy
of the main app. It just writes a small heartbeat file that a REAL, already-
running OhFudgeMyBatteryChat.exe (v1.2.0+) reads instead of real OpenVR
data, whenever that file exists and was updated within the last few
seconds - see vr_monitor.py's _read_fake_signal(). Close this tool (or let
it stop updating) and the real app falls back to actual SteamVR on its own,
no restart needed.

Run this ALONGSIDE the real app - drop this exe in the same folder as
OhFudgeMyBatteryChat.exe so both share one Data folder automatically, then
just start both. Or run from source:

    python tools/fake_vr_signal_simulator.py [--data-dir PATH]

Always shows the same generic placeholder rig - a Headset, two Controllers,
five Trackers (hip, both feet, both knees - a typical 5-point full body
tracking setup), and three Lighthouses/base stations (connect/disconnect
only, no battery - matching real hardware) - regardless of what's configured
in the real app, so they're always there to demo/test against instead of
disappearing once you remove the last Device/Effect that referenced them.
Point real Device/Effect items at DEMO-HMD-01/DEMO-CTRL-L/DEMO-CTRL-R/
DEMO-TRACKER-01..05/DEMO-LIGHTHOUSE-01..03 from the app's own Add screens to
drive those.
"""
import argparse
import json
import os
import sys
import time
import tkinter as tk
from tkinter import ttk

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from app import paths as paths_mod
from app import theme as theme_mod

APP_TITLE = "Oh Fudge - Fake SteamVR Signal Simulator"
HEARTBEAT_MS = 1000  # must be well under vr_monitor.FAKE_SIGNAL_MAX_AGE_SEC

PLACEHOLDER_DEVICES = [
    # (serial, device_class, model, role)
    ("DEMO-HMD-01", "HMD", "Demo Headset", ""),
    ("DEMO-CTRL-L", "Controller", "Demo Controller", "Left"),
    ("DEMO-CTRL-R", "Controller", "Demo Controller", "Right"),
    # 5-point full body tracking: hip + 2 feet + 2 knees
    ("DEMO-TRACKER-01", "GenericTracker", "Demo Tracker (Hip)", ""),
    ("DEMO-TRACKER-02", "GenericTracker", "Demo Tracker (Left Foot)", ""),
    ("DEMO-TRACKER-03", "GenericTracker", "Demo Tracker (Right Foot)", ""),
    ("DEMO-TRACKER-04", "GenericTracker", "Demo Tracker (Left Knee)", ""),
    ("DEMO-TRACKER-05", "GenericTracker", "Demo Tracker (Right Knee)", ""),
    # Base stations/lighthouses are mains-powered - no battery to report,
    # just connect/disconnect, matching real hardware.
    ("DEMO-LIGHTHOUSE-01", "TrackingReference", "Demo Lighthouse 1", ""),
    ("DEMO-LIGHTHOUSE-02", "TrackingReference", "Demo Lighthouse 2", ""),
    ("DEMO-LIGHTHOUSE-03", "TrackingReference", "Demo Lighthouse 3", ""),
]


class SimulatorApp(tk.Tk):
    """One slider + a Connected checkbox per fake device. Every tick (and on
    every change), writes the current state to the shared signal file - the
    real app's own polling loop picks it up on its next cycle."""

    def __init__(self, signal_path, devices):
        super().__init__()
        self.withdraw()
        self.title(APP_TITLE)
        self.resizable(False, False)
        dark_mode = theme_mod.detect_windows_dark_mode()
        theme_mod.apply_theme(dark_mode)
        theme_mod.apply_window_theme(self, dark_mode)
        self.signal_path = signal_path
        self.device_meta = {}    # serial -> (device_class, model, role, manufacturer)
        self.battery_vars = {}   # serial -> IntVar
        self.connected_vars = {}  # serial -> BooleanVar

        ttk.Label(self, text="Fake SteamVR Signal Simulator", font=("Segoe UI", 11, "bold")).grid(
            row=0, column=0, columnspan=4, padx=10, pady=(10, 2), sticky="w"
        )
        ttk.Label(
            self,
            text="The real app (v1.2.0+) picks this up automatically while both are running.\n"
                 "Close this window to hand control back to real SteamVR.",
            foreground=("#aaaaaa" if dark_mode else "#555555"), justify="left",
        ).grid(row=1, column=0, columnspan=4, padx=10, pady=(0, 8), sticky="w")

        for i, (serial, device_class, model, role, label) in enumerate(devices, start=2):
            self.device_meta[serial] = (device_class, model, role, "Simulated")
            display = f"{label} ({device_class}{' ' + role if role else ''})"
            ttk.Label(self, text=display, width=32).grid(row=i, column=0, padx=(10, 4), pady=4, sticky="w")

            has_battery = device_class != "TrackingReference"
            if has_battery:
                var = tk.IntVar(value=80)
                self.battery_vars[serial] = var
                ttk.Scale(self, from_=0, to=100, orient="horizontal", length=180, variable=var).grid(
                    row=i, column=1, padx=4, pady=4
                )

                pct_lbl = ttk.Label(self, text="80%", width=5)
                pct_lbl.grid(row=i, column=2, padx=4, pady=4)
                var.trace_add("write", lambda *a, var=var, lbl=pct_lbl: lbl.configure(text=f"{int(var.get())}%"))
            else:
                # Base stations/lighthouses are mains-powered in real life -
                # no battery slider, just the Connected toggle.
                ttk.Label(self, text="No battery", width=8, foreground="#888888").grid(
                    row=i, column=1, columnspan=2, padx=4, pady=4, sticky="w"
                )

            conn_var = tk.BooleanVar(value=True)
            self.connected_vars[serial] = conn_var
            ttk.Checkbutton(self, text="Connected", variable=conn_var).grid(
                row=i, column=3, padx=(4, 10), pady=4
            )

        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self._tick()
        self.deiconify()

    def _tick(self):
        self._write_signal()
        self.after(HEARTBEAT_MS, self._tick)

    def _write_signal(self):
        devices = {}
        for serial, (device_class, model, role, manufacturer) in self.device_meta.items():
            if not self.connected_vars[serial].get():
                continue
            battery_var = self.battery_vars.get(serial)
            devices[serial] = {
                "device_class": device_class,
                "model": model,
                "battery_pct": battery_var.get() if battery_var is not None else None,
                "charging": False,
                "role": role,
                "manufacturer": manufacturer,
            }
        payload = {"timestamp": time.time(), "devices": devices}
        tmp = self.signal_path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(payload, f)
        os.replace(tmp, self.signal_path)

    def _on_close(self):
        try:
            os.remove(self.signal_path)
        except OSError:
            pass
        self.destroy()


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "--data-dir", default=None,
        help="Data folder the real app uses (default: a Data folder next to this program - "
             "drop it in the same folder as OhFudgeMyBatteryChat.exe to share one automatically)",
    )
    args = parser.parse_args()

    if args.data_dir:
        os.makedirs(args.data_dir, exist_ok=True)
        paths_mod._app_data_dir_cache = args.data_dir

    signal_path = paths_mod.fake_signal_path()
    print(f"Writing fake signal to: {signal_path}")
    print("Make sure OhFudgeMyBatteryChat.exe (v1.2.0+) is running from the SAME Data folder to see it.")

    # Always the full placeholder rig, regardless of what's configured in the
    # real app - these devices need to keep existing across every launch so
    # they're always available for demoing/testing, not just while some
    # Device/Effect item still references their serial.
    devices = [(serial, device_class, model, role, model) for serial, device_class, model, role in PLACEHOLDER_DEVICES]

    app = SimulatorApp(signal_path, devices)
    app.mainloop()


if __name__ == "__main__":
    main()
