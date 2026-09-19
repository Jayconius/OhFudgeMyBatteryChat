"""Filesystem locations for user data (config + copied media assets).

Stored in a "Data" folder next to the .exe (portable-app style) so it's
transparent what the app has written to your PC, and easy to find/back up/
delete. Falls back to %APPDATA% only if the exe's folder turns out to be
read-only (e.g. running from Program Files).
"""
import os
import sys

APP_DIR_NAME = "OhFudgeMyBatteryChat"  # used only for the %APPDATA% fallback


def _exe_dir() -> str:
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(sys.argv[0]))


def program_dir() -> str:
    """Folder the program itself lives in (where sibling tools are looked for)."""
    return _exe_dir()


def _appdata_fallback() -> str:
    base = os.environ.get("APPDATA") or os.path.expanduser("~")
    return os.path.join(base, APP_DIR_NAME)


_app_data_dir_cache = None


def app_data_dir() -> str:
    global _app_data_dir_cache
    if _app_data_dir_cache:
        return _app_data_dir_cache

    preferred = os.path.join(_exe_dir(), "Data")
    try:
        os.makedirs(preferred, exist_ok=True)
        probe = os.path.join(preferred, ".write_test")
        with open(probe, "w") as f:
            f.write("ok")
        os.remove(probe)
        _app_data_dir_cache = preferred
        return preferred
    except OSError:
        fallback = _appdata_fallback()
        os.makedirs(fallback, exist_ok=True)
        _app_data_dir_cache = fallback
        return fallback


def assets_dir() -> str:
    path = os.path.join(app_data_dir(), "assets")
    os.makedirs(path, exist_ok=True)
    return path


def item_assets_dir(item_id: str) -> str:
    path = os.path.join(assets_dir(), item_id)
    os.makedirs(path, exist_ok=True)
    return path


def defaults_dir() -> str:
    path = os.path.join(assets_dir(), "_defaults")
    os.makedirs(path, exist_ok=True)
    return path


def config_path() -> str:
    return os.path.join(app_data_dir(), "config.json")


def fake_signal_path() -> str:
    """A small heartbeat file an external tool (see tools/fake_vr_signal_
    simulator.py) can write fake device data to - VRMonitor uses it in place
    of real OpenVR data whenever it exists and was updated recently, so a
    separate, already-running app can feed the real app fake devices for
    demos/testing without any special launch order or extra flags, as long
    as both share this same Data folder."""
    return os.path.join(app_data_dir(), "fake_vr_signal.json")


def bundled_resource(relative_path: str) -> str:
    """Resolve a path to a resource bundled into the PyInstaller onefile exe."""
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, relative_path)


def device_icons_dir() -> str:
    """Where the bundled device-icon pack gets unpacked to on first run -
    a subfolder of the user-visible Data/assets folder, so it's easy to find
    and safe to delete/replace like any other user-facing asset."""
    path = os.path.join(assets_dir(), "device icons")
    os.makedirs(path, exist_ok=True)
    return path


def bundled_device_icons_source() -> str:
    """Where the device-icon pack ships from: inside the PyInstaller onefile
    exe's extracted temp dir when frozen ("assets;device_icons" in the build
    command), or the project's own assets/ folder when running from source."""
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        return os.path.join(meipass, "device_icons")
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(project_root, "assets")
