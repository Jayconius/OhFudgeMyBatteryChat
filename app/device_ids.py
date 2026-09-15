"""Well-known device-serial constants shared across modules that must NOT
pull in heavy/optional dependencies (notably openvr) just to see a plain
string - vr_monitor.py imports openvr, and tools/fake_vr_signal_simulator.py
is packaged into its own separate, lightweight exe that never bundles
openvr's native binaries, so importing vr_monitor from there would crash it
at startup.
"""

# A synthetic pseudo-device representing SteamVR itself (not any piece of
# hardware) - lets an Effect use a Device Disconnected/Connected trigger for
# "SteamVR crashed/closed" the same way it already would for a real device
# going offline. See vr_monitor.VRMonitor.get_snapshot() for how this gets
# injected, and the Simulator's own PLACEHOLDER_DEVICES for how it can be
# driven manually during testing/demos.
STEAMVR_SERVICE_SERIAL = "__steamvr_service__"
