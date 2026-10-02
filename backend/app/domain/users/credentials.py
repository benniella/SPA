"""Password policy and password hashing.

The hashing algorithm lives behind a port so the domain never depends on a
library, and so a future algorithm change is an adapter swap rather than a
domain change.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

MIN_LENGTH = 10
MAX_LENGTH = 200


@dataclass(frozen=True, slots=True)
class PasswordPolicy:
    min_length: int = MIN_LENGTH
    max_length: int = MAX_LENGTH

    def violations(self, password: str) -> list[str]:
        """Every rule the password breaks, in a stable order.

        Returns all violations rather than the first so a registration form can
        show the user what is actually wrong instead of one rule at a time.
        """
        failures: list[str] = []
        if len(password) < self.min_length:
            failures.append(f"at least {self.min_length} characters")
        if len(password) > self.max_length:
            failures.append(f"at most {self.max_length} characters")
        if not any(character.isalpha() for character in password):
            failures.append("a letter")
        if not any(character.isdigit() for character in password):
            failures.append("a number")
        return failures

    def is_satisfied_by(self, password: str) -> bool:
        return not self.violations(password)


@runtime_checkable
class PasswordHasher(Protocol):
    """Hash and verify passwords without ever handling plaintext at rest."""

    def hash(self, password: str) -> str: ...

    def verify(self, password: str, password_hash: str) -> bool: ...


_WHITESPACE = re.compile(r"\s+")


def normalise_email(value: str) -> str:
    """Normalise an email address for storage and lookup.

    Lower-cased and trimmed so that uniqueness, sign-in and reset lookups cannot
    disagree about casing. Deliberately does not strip dots or '+tags': those are
    meaningful to the mailbox owner, and rewriting them silently changes which
    address a user actually controls.
    """
    return _WHITESPACE.sub("", value).lower()


def normalise_phone(value: str) -> str:
    """Normalise a phone number to an E.164-shaped string.

    A light normalisation on purpose. Full E.164 parsing needs a region and a
    numbering-plan library, and guessing a region would silently mis-normalise a
    number. Stripping formatting keeps the stored value comparable without
    inventing a country.
    """
    stripped = _WHITESPACE.sub("", value).strip()
    if stripped.startswith("+"):
        return "+" + "".join(character for character in stripped[1:] if character.isdigit())
    return "".join(character for character in stripped if character.isdigit() or character == "+")
