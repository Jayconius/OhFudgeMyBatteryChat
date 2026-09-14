"""Unpacks the bundled device-icon pack (illustrated brand/model art) from
the PyInstaller exe into Data/assets/device icons, and offers restoring or
adding any new icons a later update introduces.
"""
import os
import shutil

from . import paths


def _bundled_icon_filenames() -> list:
    src_dir = paths.bundled_device_icons_source()
    if not os.path.isdir(src_dir):
        return []
    return [f for f in os.listdir(src_dir) if os.path.isfile(os.path.join(src_dir, f))]


def missing_icons() -> list:
    """Bundled icon filenames not currently present in the user's Data/assets/
    device icons folder - either never unpacked yet, or added by a later
    version after the user's folder was already populated."""
    dest_dir = paths.device_icons_dir()
    existing = set(os.listdir(dest_dir))
    return [f for f in _bundled_icon_filenames() if f not in existing]


def copy_icons(filenames) -> None:
    """Copies the given bundled icon filenames into Data/assets/device icons,
    overwriting anything already there under the same name."""
    src_dir = paths.bundled_device_icons_source()
    dest_dir = paths.device_icons_dir()
    for fname in filenames:
        src = os.path.join(src_dir, fname)
        if os.path.isfile(src):
            shutil.copyfile(src, os.path.join(dest_dir, fname))


def ensure_device_icons() -> str:
    """First-run only: if Data/assets/device icons is completely empty (a
    brand-new install, nothing to lose), silently unpacks the whole bundled
    icon pack. Once anything is in there, this is a no-op - an existing
    user's missing/new icons (e.g. from a later update) are handled by the
    ask-first prompt in gui.py instead, so an update never silently
    overwrites what a user has already added, removed, or replaced."""
    dest_dir = paths.device_icons_dir()
    if os.listdir(dest_dir):
        return dest_dir
    copy_icons(_bundled_icon_filenames())
    return dest_dir


def restore_all_icons() -> int:
    """Force-copies every bundled icon into Data/assets/device icons,
    overwriting any existing file with the same name - used by the "Restore
    Icons" button in About, after the user confirms the overwrite warning.
    Returns how many files were (re)written."""
    filenames = _bundled_icon_filenames()
    copy_icons(filenames)
    return len(filenames)
