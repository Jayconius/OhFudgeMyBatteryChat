"""Background thread that keeps a Twitch chat connection alive (mirrors
vr_monitor.py's start/stop/background-thread shape) and tracks which
Effects a matching chat command has temporarily activated.

Token refresh: Device Code Flow refresh tokens are one-time use (Twitch
invalidates the old one the moment a new pair is issued), so a refreshed
pair is saved to disk immediately, not just kept in memory - losing one
before it's persisted would strand the connection with no way back in
short of the user re-approving from scratch.
"""
import ssl
import threading
import time

from . import config as config_mod
from . import twitch_auth
from .twitch_chat import TwitchChatConnection, parse_privmsg, sender_meets_permission

RECONNECT_DELAY_SEC = 5
IDLE_RETRY_SEC = 2  # how often to check "are we supposed to be connected yet" when not


def _command_matches(message: str, command: str) -> bool:
    msg = message.strip().lower()
    cmd = command.strip().lower()
    if not cmd:
        return False
    return msg == cmd or msg.startswith(cmd + " ")


class TwitchMonitor:
    def __init__(self, get_config):
        self.get_config = get_config
        self._lock = threading.Lock()
        self._active = {}  # effect_id -> monotonic expiry
        self._stop = threading.Event()
        self._thread = None
        self.connected = False
        self.last_error = ""

    def start(self):
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self):
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=5)
        self.connected = False

    def active_effect_ids(self) -> set:
        now = time.monotonic()
        with self._lock:
            expired = [k for k, v in self._active.items() if v <= now]
            for k in expired:
                del self._active[k]
            return set(self._active.keys())

    def _activate(self, effect_id, duration_sec):
        with self._lock:
            self._active[effect_id] = time.monotonic() + max(1.0, duration_sec or 5.0)

    def _handle_message(self, parsed, cfg):
        for effect in cfg.effects:
            if not effect.chat_command:
                continue
            if not _command_matches(parsed["message"], effect.chat_command):
                continue
            if not sender_meets_permission(parsed["badges"], effect.chat_permission):
                continue
            self._activate(effect.id, effect.duration_sec)

    def _try_refresh(self, cfg):
        if not cfg.twitch_refresh_token:
            return False
        try:
            token_payload = twitch_auth.refresh_access_token(cfg.twitch_refresh_token)
        except RuntimeError as exc:
            self.last_error = f"Refresh failed: {exc}"
            return False
        cfg.twitch_access_token = token_payload["access_token"]
        if token_payload.get("refresh_token"):
            cfg.twitch_refresh_token = token_payload["refresh_token"]
        config_mod.save(cfg)
        return True

    def _run(self):
        while not self._stop.is_set():
            cfg = self.get_config()
            if not cfg.twitch_connected or not cfg.twitch_access_token or not cfg.twitch_login:
                self.connected = False
                self._stop.wait(IDLE_RETRY_SEC)
                continue

            conn = TwitchChatConnection(cfg.twitch_access_token, cfg.twitch_login, cfg.twitch_login)
            clean_stop = False
            try:
                conn.connect()
                self.connected = True
                self.last_error = ""
                for line in conn.read_lines():
                    if self._stop.is_set():
                        clean_stop = True
                        break
                    if line is None:
                        continue
                    parsed = parse_privmsg(line)
                    if parsed:
                        self._handle_message(parsed, self.get_config())
            except (OSError, ssl.SSLError) as exc:
                self.last_error = str(exc)
            finally:
                conn.close()
                self.connected = False

            if clean_stop or self._stop.is_set():
                return
            # Unexpected disconnect - Twitch's own auth-failure signal is
            # just closing the socket (no clean error), so always try a
            # refresh before the next attempt; a refresh of a still-valid
            # token is harmless and just returns a fresh pair.
            self._try_refresh(self.get_config())
            self._stop.wait(RECONNECT_DELAY_SEC)
