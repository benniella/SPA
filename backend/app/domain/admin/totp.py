"""Time-based one-time passwords (RFC 6238).

Implemented against the standard library rather than adding a dependency: the
algorithm is small, well specified, and has no extension points the project needs.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
import struct
from urllib.parse import quote

DIGITS = 6
PERIOD_SECONDS = 30
SECRET_BYTES = 20
_ALGORITHM = "SHA1"


def generate_secret() -> str:
    """A fresh base32 secret, sized for SHA-1 per the RFC's recommended key length."""
    return base64.b32encode(secrets.token_bytes(SECRET_BYTES)).decode("ascii")


def code_at(secret: str, *, timestamp: int, skew_steps: int = 0) -> str:
    counter = timestamp // PERIOD_SECONDS + skew_steps
    digest = hmac.new(
        _decode_secret(secret),
        struct.pack(">Q", counter),
        hashlib.sha1,
    ).digest()
    offset = digest[-1] & 0x0F
    truncated = struct.unpack(">I", digest[offset : offset + 4])[0] & 0x7FFFFFFF
    return f"{truncated % (10**DIGITS):0{DIGITS}d}"


def verify(secret: str, code: str, *, timestamp: int, window_steps: int = 1) -> bool:
    """Whether 'code' is valid for 'secret' within a small clock-skew window.

    The window is deliberately one step either way: wide enough for a clock that
    drifts by seconds, narrow enough that a captured code is short-lived.
    """
    candidate = code.strip().replace(" ", "")
    if not candidate.isdigit() or len(candidate) != DIGITS:
        return False
    matches = 0
    for skew in range(-window_steps, window_steps + 1):
        expected = code_at(secret, timestamp=timestamp, skew_steps=skew)
        # Constant-time comparison, and accumulate so the loop does not exit early
        # on the matched step and leak its position through timing.
        matches |= int(hmac.compare_digest(expected, candidate))
    return bool(matches)


def provisioning_uri(*, secret: str, account: str, issuer: str) -> str:
    label = quote(f"{issuer}:{account}")
    return (
        f"otpauth://totp/{label}"
        f"?secret={secret}&issuer={quote(issuer)}"
        f"&algorithm={_ALGORITHM}&digits={DIGITS}&period={PERIOD_SECONDS}"
    )


def _decode_secret(secret: str) -> bytes:
    padding = "=" * (-len(secret) % 8)
    return base64.b32decode(secret.upper() + padding)
