"""Real Klingon pIqaD script rendering.

Uses the bundled "pIqaD qolqoS" font (Daniel Dadap, SIL Open Font License -
see fonts/LICENSE-pIqaD-qolqoS.txt) and the Klingon-to-Private-Use-Area
mapping originally defined in the Linux kernel's Documentation/unicode.txt
and later adopted by the ConScript Unicode Registry (U+F8D0-U+F8FF). Since
pIqaD has no official Unicode block, this mapping only round-trips correctly
with a font that implements this exact same de facto standard.

IMPORTANT: this font has *no* Latin-alphabet glyphs at all (only the 39
Klingon symbols + space) - so transliterated text only renders correctly in
widgets that ALSO use this font. Never apply it to anything that mixes in
real data (serial numbers, version numbers, free-typed text): it'll show as
blank boxes. See the curated call sites in gui.py.
"""
import ctypes
import os
import sys
import threading

from . import paths

FONT_FAMILY = "pIqaD qolqoS"
FONT_RELATIVE_PATH = os.path.join("fonts", "pIqaD-qolqoS.ttf")

# Exact letters, in greedy longest-match order (try 3-char, then 2-char, then
# 1-char tokens) - Klingon romanization is case-sensitive (q != Q, etc).
LETTER_TO_CODEPOINT = {
    "tlh": 0xF8E4,
    "ch": 0xF8D2, "gh": 0xF8D5, "ng": 0xF8DC,
    "a": 0xF8D0, "b": 0xF8D1, "D": 0xF8D3, "e": 0xF8D4, "H": 0xF8D6,
    "I": 0xF8D7, "j": 0xF8D8, "l": 0xF8D9, "m": 0xF8DA, "n": 0xF8DB,
    "o": 0xF8DD, "p": 0xF8DE, "q": 0xF8DF, "Q": 0xF8E0, "r": 0xF8E1,
    "S": 0xF8E2, "t": 0xF8E3, "u": 0xF8E5, "v": 0xF8E6, "w": 0xF8E7,
    "y": 0xF8E8, "'": 0xF8E9,
    "0": 0xF8F0, "1": 0xF8F1, "2": 0xF8F2, "3": 0xF8F3, "4": 0xF8F4,
    "5": 0xF8F5, "6": 0xF8F6, "7": 0xF8F7, "8": 0xF8F8, "9": 0xF8F9,
    ",": 0xF8FD, ".": 0xF8FE,
}
_TOKEN_LENGTHS = (3, 2, 1)

_lock = threading.Lock()
_load_attempted = False
_load_succeeded = False


def transliterate(text: str) -> str:
    """Converts Latin-letter Klingon text to pIqaD codepoints. Any character
    that isn't part of the 26-letter Klingon alphabet (spaces, punctuation,
    stray non-Klingon text) passes through unchanged."""
    out = []
    i, n = 0, len(text)
    while i < n:
        for length in _TOKEN_LENGTHS:
            if i + length <= n:
                cp = LETTER_TO_CODEPOINT.get(text[i:i + length])
                if cp is not None:
                    out.append(chr(cp))
                    i += length
                    break
        else:
            out.append(text[i])
            i += 1
    return "".join(out)


def ensure_font_loaded() -> bool:
    """Loads the bundled font privately for this process only (no system-wide
    install, no registry changes - removed automatically when the app exits).
    Safe to call repeatedly; only does the actual work once."""
    global _load_attempted, _load_succeeded
    with _lock:
        if _load_attempted:
            return _load_succeeded
        _load_attempted = True
        if sys.platform != "win32":
            return False
        font_path = paths.bundled_resource(FONT_RELATIVE_PATH)
        if not os.path.isfile(font_path):
            return False
        try:
            FR_PRIVATE = 0x10
            added = ctypes.windll.gdi32.AddFontResourceExW(ctypes.c_wchar_p(font_path), FR_PRIVATE, None)
            _load_succeeded = bool(added)
        except Exception:
            _load_succeeded = False
        return _load_succeeded
