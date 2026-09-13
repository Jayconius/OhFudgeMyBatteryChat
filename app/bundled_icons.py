"""Unpacks the bundled device-icon pack (illustrated brand/model art) from
the PyInstaller exe into Data/assets/device icons on first run, so users can
pick from real device art in the file-choose dialog instead of only the
plain generated placeholders in default_assets.py.
"""
import os
import shutil

from . import paths


def ensure_device_icons() -> str:
    """Copies the bundled icon pack out to Data/assets/device icons the first
    time the app runs; safe to call every launch. Never overwrites - once the
    folder has anything in it (unpacked pack, or the user's own additions),
    this is a no-op."""
    dest_dir = paths.device_icons_dir()
    if os.listdir(dest_dir):
        return dest_dir

    src_dir = paths.bundled_device_icons_source()
    if not os.path.isdir(src_dir):
        return dest_dir

    for fname in os.listdir(src_dir):
        src = os.path.join(src_dir, fname)
        if os.path.isfile(src):
            shutil.copyfile(src, os.path.join(dest_dir, fname))
    return dest_dir
