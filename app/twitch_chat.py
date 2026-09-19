"""Reads a Twitch channel's chat over classic IRC-over-TLS (irc.chat.twitch.tv,
port 6697) using only the standard library (socket + ssl) - no extra
dependency needed just to read chat lines.

Twitch's IRC server here is not RFC-standard IRC; it's specifically the
"Twitch IRC" dialect documented at dev.twitch.tv/docs/irc/ - notably the
`@tags` prefix on each message (requested via a CAP REQ) carrying badge/mod/
subscriber info per-message, which is how permission checks (mod/vip/
broadcaster/subscriber) work without a separate API call per message.
"""
import socket
import ssl

HOST = "irc.chat.twitch.tv"
PORT = 6697
BADGE_TIERS = ("broadcaster", "moderator", "vip", "subscriber")


def _parse_tags(tag_str):
    """'@badge-info=;badges=broadcaster/1,premium/1;mod=0;...' -> dict."""
    tags = {}
    for pair in tag_str.lstrip("@").split(";"):
        if "=" in pair:
            k, v = pair.split("=", 1)
            tags[k] = v
    return tags


def _badges_present(tags):
    """Returns the subset of BADGE_TIERS present in this message's tags,
    combining the explicit 'badges' list with the simpler dedicated 'mod'/
    'subscriber' tag fields Twitch also sends (badges= is the only place
    broadcaster/vip show up; mod=1/subscriber=1 are redundant-but-reliable
    for those two)."""
    present = set()
    badges_raw = tags.get("badges", "")
    for entry in badges_raw.split(","):
        name = entry.split("/", 1)[0]
        if name == "broadcaster":
            present.add("broadcaster")
        elif name == "vip":
            present.add("vip")
        elif name == "moderator":
            present.add("moderator")
        elif name == "subscriber" or name == "founder":
            present.add("subscriber")
    if tags.get("mod") == "1":
        present.add("moderator")
    if tags.get("subscriber") == "1":
        present.add("subscriber")
    return present


def parse_privmsg(line):
    """Parses one raw IRC line. Returns a dict with display_name, badges
    (set), message on a PRIVMSG line, or None for anything else (PING,
    other commands, etc.)."""
    tag_str = ""
    rest = line
    if line.startswith("@"):
        tag_str, _, rest = line.partition(" ")

    if " PRIVMSG #" not in rest:
        return None

    prefix, _, remainder = rest.partition(" PRIVMSG #")
    _, _, message = remainder.partition(" :")
    tags = _parse_tags(tag_str)
    return {
        "display_name": tags.get("display-name") or prefix.split("!", 1)[0].lstrip(":"),
        "badges": _badges_present(tags),
        "message": message,
    }


def sender_meets_permission(badges: set, required: str) -> bool:
    """required is one of config.CHAT_PERMISSION_OPTIONS' keys. The
    broadcaster can always use any command on their own channel regardless
    of tier; moderator satisfies a "vip" requirement too (a mod is at least
    as trusted as a VIP for this app's purposes, even though Twitch itself
    doesn't nest those roles)."""
    if required == "everyone":
        return True
    if "broadcaster" in badges:
        return True
    if required == "vip":
        return bool(badges & {"vip", "moderator"})
    if required == "moderator":
        return "moderator" in badges
    return False


class TwitchChatConnection:
    """One blocking connection to one channel's chat. Run its listen loop on
    its own thread (mirrors vr_monitor.py's background-thread pattern) - this
    class does no threading itself, callers own that."""

    def __init__(self, access_token, login, channel):
        self.access_token = access_token
        self.login = login
        self.channel = channel.lower().lstrip("#")
        self._sock = None
        self._buf = ""

    def connect(self, timeout_sec=15):
        raw = socket.create_connection((HOST, PORT), timeout=timeout_sec)
        self._sock = ssl.create_default_context().wrap_socket(raw, server_hostname=HOST)
        self._send("CAP REQ :twitch.tv/tags twitch.tv/commands")
        self._send(f"PASS oauth:{self.access_token}")
        self._send(f"NICK {self.login}")
        self._send(f"JOIN #{self.channel}")

    def _send(self, line):
        self._sock.sendall((line + "\r\n").encode("utf-8"))

    def read_lines(self, idle_timeout_sec=10):
        """Generator yielding raw IRC lines as they arrive, or None at least
        every idle_timeout_sec when chat's been quiet - so a caller (e.g. a
        background thread's `for line in conn.read_lines(): if not
        running: break`) can check its own stop condition without blocking
        for arbitrarily long stretches of silent chat. Runs forever until
        the socket closes or errors. Handles PING/PONG transparently and
        never yields those lines."""
        self._sock.settimeout(idle_timeout_sec)
        while True:
            try:
                chunk = self._sock.recv(4096)
            except socket.timeout:
                yield None
                continue
            if not chunk:
                return
            self._buf += chunk.decode("utf-8", errors="replace")
            while "\r\n" in self._buf:
                line, self._buf = self._buf.split("\r\n", 1)
                if line.startswith("PING"):
                    self._send(line.replace("PING", "PONG", 1))
                    continue
                if line:
                    yield line

    def close(self):
        if self._sock:
            try:
                self._sock.close()
            except OSError:
                pass
            self._sock = None
