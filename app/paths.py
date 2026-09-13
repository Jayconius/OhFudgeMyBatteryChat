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


def bundled_resource(relative_path: str) -> str:
    """Resolve a path to a resource bundled into the PyInstaller onefile exe."""
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, relative_path)
