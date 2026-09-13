"""Optional GitHub-release update check: a single outbound HTTPS request to
api.github.com, made only when the user has opted in (AppConfig.check_for_
updates). No other part of this app makes network calls of any kind.
"""
import json
import re
import urllib.request

REPO = "Jayconius/OhFudgeMyBatteryChat"
API_URL = f"https://api.github.com/repos/{REPO}/releases/latest"
RELEASES_URL = f"https://github.com/{REPO}/releases/latest"
REQUEST_TIMEOUT_SEC = 5


def _version_parts(v: str):
    parts = re.findall(r"\d+", v or "")
    return [int(p) for p in parts] or [0]


def _is_newer(candidate: str, current: str) -> bool:
    a, b = _version_parts(candidate), _version_parts(current)
    n = max(len(a), len(b))
    a += [0] * (n - len(a))
    b += [0] * (n - len(b))
    return a > b


def check_latest(current_version: str):
    """Returns (tag_name, html_url) if a newer GitHub release is published,
    else None. Never raises - any network hiccup or unexpected response is
    swallowed so a flaky connection can't disrupt startup."""
    try:
        req = urllib.request.Request(
            API_URL,
            headers={"Accept": "application/vnd.github+json", "User-Agent": "OhFudgeMyBatteryChat"},
        )
        with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT_SEC) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        tag = data.get("tag_name", "")
        url = data.get("html_url") or RELEASES_URL
        if tag and _is_newer(tag, current_version):
            return tag, url
    except Exception:
        pass
    return None
