"""Password hashing.

PBKDF2-HMAC-SHA256 from the standard library, chosen over a third-party binding
because it is the one established password-hashing construction that ships with
Python: no native build step, no supply-chain surface, and no version pin that
can silently change a stored hash's cost. The stored string carries its algorithm,
iteration count and salt, so a stored hash stays verifiable when the parameters
are raised later.

'hashlib.scrypt' would be preferable for memory hardness but is capped by
'OPENSSL_MAX_MEM_LIMIT' on some builds, which makes its cost parameter
deployment-dependent — an unacceptable property for a credential.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import secrets

ALGORITHM = "pbkdf2_sha256"
ITERATIONS = 600_000
SALT_BYTES = 16
_DIGEST = "sha256"


class Pbkdf2PasswordHasher:
    def __init__(self, *, iterations: int = ITERATIONS) -> None:
        self._iterations = iterations

    def hash(self, password: str) -> str:
        salt = secrets.token_bytes(SALT_BYTES)
        digest = self._derive(password, salt, self._iterations)
        return "$".join(
            (
                ALGORITHM,
                str(self._iterations),
                _b64(salt),
                _b64(digest),
            )
        )

    def verify(self, password: str, password_hash: str) -> bool:
        parts = password_hash.split("$")
        if len(parts) != 4 or parts[0] != ALGORITHM:
            return False
        try:
            iterations = int(parts[1])
            salt = _unb64(parts[2])
            expected = _unb64(parts[3])
        except (ValueError, TypeError):
            return False
        if iterations < 1:
            return False
        candidate = self._derive(password, salt, iterations)
        return hmac.compare_digest(candidate, expected)

    @staticmethod
    def _derive(password: str, salt: bytes, iterations: int) -> bytes:
        return hashlib.pbkdf2_hmac(_DIGEST, password.encode("utf-8"), salt, iterations)


def _b64(raw: bytes) -> str:
    return base64.b64encode(raw).decode("ascii").rstrip("=")


def _unb64(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.b64decode(value + padding, validate=True)
