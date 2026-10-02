"""Opaque security tokens, one-time codes and encryptable secrets.

Generation and verification are separate from delivery: a challenge is created
and hashed here, then handed to an 'EmailSender' or 'SmsSender' port. Nothing in
this module logs a token or a code.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import secrets
import string

TOKEN_BYTES = 32
OTP_DIGITS = 6
_OTP_ALPHABET = string.digits


def generate_token() -> str:
    """A URL-safe, cryptographically random token.

    'secrets.token_urlsafe' rather than 'uuid4': a token must be unguessable, and
    a UUID carries only 122 bits of entropy in a format that invites clients to
    treat it as an identifier.
    """
    return secrets.token_urlsafe(TOKEN_BYTES)


def hash_token(token: str, *, secret: str) -> str:
    """Hash a token for storage.

    Keyed by the application secret and compared with 'compare_digest', so a
    database read alone cannot be used to confirm a guessed token, and a
    comparison cannot leak the stored value through timing.
    """
    return hmac.new(secret.encode("utf-8"), token.encode("utf-8"), hashlib.sha256).hexdigest()


def tokens_match(candidate_hash: str, stored_hash: str) -> bool:
    return hmac.compare_digest(candidate_hash, stored_hash)


def generate_otp(*, digits: int = OTP_DIGITS) -> str:
    """A numeric one-time code.

    'secrets.choice' per digit rather than 'randint': this is a credential, and
    the module-level random generator is seeded predictably.
    """
    return "".join(secrets.choice(_OTP_ALPHABET) for _ in range(digits))


def hash_otp(code: str, *, secret: str) -> str:
    return hmac.new(secret.encode("utf-8"), code.encode("utf-8"), hashlib.sha256).hexdigest()


def encrypt_secret(value: str, *, secret: str) -> str:
    """Encrypt a shared secret for storage, keyed by the application secret.

    A TOTP seed is a long-lived credential: unlike a token it cannot be rotated
    without breaking the administrator's authenticator, so it must not sit in the
    database in plaintext. A keyed stream derived from the application secret keeps
    a database read alone from yielding a working second factor, without pulling in
    a cipher dependency the project does not otherwise need.
    """
    raw = value.encode("utf-8")
    keystream = _keystream(secret, len(raw))
    ciphertext = bytes(a ^ b for a, b in zip(raw, keystream, strict=True))
    tag = hmac.new(secret.encode("utf-8"), ciphertext, hashlib.sha256).digest()[:16]
    return base64.urlsafe_b64encode(tag + ciphertext).decode("ascii")


def decrypt_secret(value: str, *, secret: str) -> str:
    """Reverse 'encrypt_secret'. Raises on a wrong key or a tampered value."""
    try:
        payload = base64.urlsafe_b64decode(value)
    except (binascii.Error, ValueError) as exc:
        raise ValueError("Encrypted value is not valid base64.") from exc
    tag, ciphertext = payload[:16], payload[16:]
    expected = hmac.new(secret.encode("utf-8"), ciphertext, hashlib.sha256).digest()[:16]
    if not hmac.compare_digest(tag, expected):
        raise ValueError("Encrypted value failed its integrity check.")
    keystream = _keystream(secret, len(ciphertext))
    return bytes(a ^ b for a, b in zip(ciphertext, keystream, strict=True)).decode("utf-8")


def _keystream(secret: str, length: int) -> bytes:
    blocks: list[bytes] = []
    counter = 0
    emitted = 0
    while emitted < length:
        block = hmac.new(
            secret.encode("utf-8"),
            f"spa-totp:{counter}".encode(),
            hashlib.sha256,
        ).digest()
        blocks.append(block)
        emitted += len(block)
        counter += 1
    return b"".join(blocks)[:length]
