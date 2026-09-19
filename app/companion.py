"""Finding, launching and - only when the user asks - downloading the small
separate programs that live beside this app: the Oh Fudge VR Macro App
(OhFudgeVRMacroApp.exe, a borderless window of big mute buttons) and the Demo
Simulator (OhFudgeMyBatteryChatSimulator.exe).

A download is the app's only file download and happens only after the user
clicks Yes on a prompt. It reads GitHub's public release list
(api.github.com), takes the newest release whose tag starts with the tool's
prefix, downloads that release's exe over HTTPS from github.com, and refuses
to keep it unless its SHA-256 matches the checksum GitHub published for that
file. It is saved next to this program, so the tool finds the same Data
folder without any setup.
"""
import hashlib
import json
import os
import re
import subprocess
import sys
import urllib.parse
import urllib.request
from dataclasses import dataclass

from . import paths

REPO = "Jayconius/OhFudgeMyBatteryChat"
RELEASES_API = f"https://api.github.com/repos/{REPO}/releases?per_page=50"
RELEASES_PAGE = f"https://github.com/{REPO}/releases"
ALLOWED_DOWNLOAD_HOSTS = ("github.com", "githubusercontent.com")  # the host itself or any subdomain of these
MAX_BYTES = 200 * 1024 * 1024
REQUEST_TIMEOUT_SEC = 20
CHUNK = 64 * 1024


@dataclass(frozen=True)
class Tool:
    product: str       # name shown to the user
    exe_name: str      # asset name on the GitHub release, and the file looked for beside this program
    tag_prefix: str    # its own release line, e.g. "simulator-v"
    source_script: str  # path (relative to the project root) used when running from source
    approx_mb: int


VR_MACRO_APP = Tool("Oh Fudge VR Macro App", "OhFudgeVRMacroApp.exe", "macros-v", "tools/vr_macro_app.py", 11)
SIMULATOR = Tool("Demo Simulator", "OhFudgeMyBatteryChatSimulator.exe", "simulator-v", "tools/fake_vr_signal_simulator.py", 10)


class CompanionError(Exception):
    """code is an i18n suffix (companion_err_<code>); detail is shown after it."""

    def __init__(self, code, detail=""):
        super().__init__(f"{code}: {detail}")
        self.code = code
        self.detail = detail


def exe_path(tool: Tool) -> str:
    return os.path.join(paths.program_dir(), tool.exe_name)


def source_script(tool: Tool) -> str:
    """When running from source (no exe built), the tool's script."""
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(root, *tool.source_script.split("/"))


def is_available(tool: Tool) -> bool:
    if os.path.isfile(exe_path(tool)):
        return True
    return not getattr(sys, "frozen", False) and os.path.isfile(source_script(tool))


def launch(tool: Tool) -> None:
    """Starts the tool pointed at this app's Data folder, detached so it
    outlives this window. Raises OSError if it can't be started."""
    data_dir = paths.app_data_dir()
    if os.path.isfile(exe_path(tool)):
        cmd = [exe_path(tool), "--data-dir", data_dir]
        cwd = os.path.dirname(exe_path(tool))
    else:
        cmd = [sys.executable, source_script(tool), "--data-dir", data_dir]
        cwd = os.path.dirname(source_script(tool))
    env = dict(os.environ)
    # A PyInstaller program starting another PyInstaller program would
    # otherwise hand it this one's extraction folder.
    env["PYINSTALLER_RESET_ENVIRONMENT"] = "1"
    flags = 0x00000008 | 0x00000200 | 0x08000000  # DETACHED_PROCESS | NEW_PROCESS_GROUP | NO_WINDOW
    subprocess.Popen(cmd, cwd=cwd, env=env, creationflags=flags, close_fds=True,
                     stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


# -- download ---------------------------------------------------------------
def _version_parts(tag: str):
    return [int(p) for p in re.findall(r"\d+", tag or "")] or [0]


def _get_json(url):
    req = urllib.request.Request(url, headers={"Accept": "application/vnd.github+json", "User-Agent": "OhFudgeMyBatteryChat"})
    try:
        with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT_SEC) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        raise CompanionError("network", str(e))


def _host_allowed(url) -> bool:
    parts = urllib.parse.urlsplit(url)
    host = (parts.hostname or "").lower()
    return parts.scheme == "https" and any(host == h or host.endswith("." + h) for h in ALLOWED_DOWNLOAD_HOSTS)


def find_release(tool: Tool):
    """The newest published release of the tool as {tag, url, size, sha256}."""
    data = _get_json(RELEASES_API)
    best = None
    for rel in data if isinstance(data, list) else []:
        tag = rel.get("tag_name", "")
        if not tag.startswith(tool.tag_prefix) or rel.get("draft") or rel.get("prerelease"):
            continue
        asset = next((a for a in rel.get("assets", []) if a.get("name") == tool.exe_name), None)
        if asset and (best is None or _version_parts(tag) > _version_parts(best["tag"])):
            digest = str(asset.get("digest") or "")
            best = {
                "tag": tag,
                "url": asset.get("browser_download_url", ""),
                "size": int(asset.get("size") or 0),
                "sha256": digest.split(":", 1)[1].lower() if digest.lower().startswith("sha256:") else "",
            }
    if best is None:
        raise CompanionError("no_release")
    if not best["sha256"]:
        raise CompanionError("no_checksum")  # never keep a program we can't verify
    if not _host_allowed(best["url"]):
        raise CompanionError("bad_source", best["url"])
    return best


def download_and_install(tool: Tool, progress=None, cancelled=None):
    """Downloads the tool next to this program, verifying it against
    GitHub's checksum. progress(done_bytes, total_bytes) is called as it goes;
    cancelled() -> True stops it. Returns the installed path. Raises
    CompanionError (nothing is left behind on failure)."""
    release = find_release(tool)
    dest = exe_path(tool)
    part = dest + ".part"
    total = release["size"]
    sha = hashlib.sha256()
    done = 0
    try:
        req = urllib.request.Request(release["url"], headers={"User-Agent": "OhFudgeMyBatteryChat"})
        try:
            resp = urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT_SEC)
        except Exception as e:
            raise CompanionError("network", str(e))
        with resp:
            if not _host_allowed(resp.geturl()):  # after any redirects
                raise CompanionError("bad_source", resp.geturl())
            total = int(resp.headers.get("Content-Length") or total or 0)
            try:
                out = open(part, "wb")
            except OSError as e:
                raise CompanionError("write", str(e))
            with out:
                while True:
                    if cancelled and cancelled():
                        raise CompanionError("cancelled")
                    try:
                        chunk = resp.read(CHUNK)
                    except Exception as e:
                        raise CompanionError("network", str(e))
                    if not chunk:
                        break
                    done += len(chunk)
                    if done > MAX_BYTES:
                        raise CompanionError("bad_file")
                    sha.update(chunk)
                    try:
                        out.write(chunk)
                    except OSError as e:
                        raise CompanionError("write", str(e))
                    if progress:
                        progress(done, total)
        if sha.hexdigest() != release["sha256"]:
            raise CompanionError("checksum")
        with open(part, "rb") as f:
            if f.read(2) != b"MZ":
                raise CompanionError("bad_file")
        try:
            os.replace(part, dest)
        except OSError as e:
            raise CompanionError("write", str(e))
        return dest
    finally:
        if os.path.exists(part):
            try:
                os.remove(part)
            except OSError:
                pass
