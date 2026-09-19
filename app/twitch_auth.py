"""Twitch OAuth via the Device Code Grant Flow - the flow Twitch actually
restricts Public clients (no client secret, safe for a distributed desktop
exe) to. Confirmed against Twitch's own docs + a documented correction
thread after the Authorization Code + PKCE approach was tried first and
rejected by Twitch with "Invalid client credentials" - Public clients simply
cannot use that flow at all, PKCE or not.

Flow: POST for a device_code + user_code -> show the user_code and send them
to Twitch's own verification page (not anything this app hosts) -> poll the
token endpoint until they approve there, or it expires.

CLIENT_ID is a public identifier (not a secret) and is safe to keep in source.
"""
import json
import time
import urllib.error
import urllib.parse
import urllib.request

CLIENT_ID = "kbmfgt9lefqox8s09sqyodii4bnbj6"
SCOPES = "chat:read"
DEVICE_URL = "https://id.twitch.tv/oauth2/device"
TOKEN_URL = "https://id.twitch.tv/oauth2/token"
USERS_URL = "https://api.twitch.tv/helix/users"
# Twitch's own doc-corrections thread confirms this exact string - the
# published docs page has this wrong (says plain "device_code").
DEVICE_GRANT_TYPE = "urn:ietf:params:oauth:grant-type:device_code"


def _post_form(url, fields):
    data = urllib.parse.urlencode(fields).encode("ascii")
    req = urllib.request.Request(
        url, data=data, method="POST",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Twitch request to {url} failed ({exc.code}): {body}") from None


def request_device_code():
    """Returns dict with device_code, user_code, verification_uri,
    expires_in, interval."""
    return _post_form(DEVICE_URL, {"client_id": CLIENT_ID, "scopes": SCOPES})


def poll_for_token(device_code, interval_sec, expires_in_sec, on_tick=None):
    """Blocks, polling at interval_sec, until the user approves at
    verification_uri or expires_in_sec elapses. on_tick(seconds_left) is
    called once per poll if given, so a caller can show a countdown.
    Returns the token dict (with 'login' added) on success, raises
    RuntimeError on expiry or a real Twitch-side error."""
    deadline = time.monotonic() + expires_in_sec
    while time.monotonic() < deadline:
        if on_tick:
            on_tick(int(deadline - time.monotonic()))
        time.sleep(interval_sec)
        try:
            token_payload = _post_form(TOKEN_URL, {
                "client_id": CLIENT_ID,
                "scopes": SCOPES,
                "device_code": device_code,
                "grant_type": DEVICE_GRANT_TYPE,
            })
        except RuntimeError as exc:
            if "authorization_pending" in str(exc):
                continue
            raise
        token_payload["login"] = _fetch_login(token_payload["access_token"])
        return token_payload
    raise RuntimeError("Timed out waiting for you to approve on Twitch's page.")


def _fetch_login(access_token):
    req = urllib.request.Request(
        USERS_URL,
        headers={"Authorization": f"Bearer {access_token}", "Client-Id": CLIENT_ID},
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        payload = json.loads(resp.read().decode("utf-8"))
    return payload["data"][0]["login"]


def refresh_access_token(refresh_token):
    """No client_secret needed - confirmed for tokens obtained via Device
    Code Flow specifically (the published refresh-token docs wrongly mark
    it required for all flows)."""
    return _post_form(TOKEN_URL, {
        "client_id": CLIENT_ID,
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
    })
