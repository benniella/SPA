"""Users: identity and profile.

Credentials, tokens and sessions are not modelled: authentication is unresolved
(see 'docs/architecture/overview.md'). Only the identity other domains reference.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from app.domain.shared import UserId, new_id, utcnow

_EMAIL_MIN_PARTS = 2


@dataclass(frozen=True, slots=True)
class Email:
    """A validated email address.

    Normalised to lowercase on construction so that uniqueness checks and
    lookups cannot drift because of casing.
    """

    value: str

    def __post_init__(self) -> None:
        candidate = self.value.strip().lower()
        local, _, domain = candidate.partition("@")
        if (
            not local
            or not domain
            or "." not in domain
            or candidate.count("@") != 1
            or len(candidate.split("@")) != _EMAIL_MIN_PARTS
        ):
            raise ValueError(f"Invalid email address: {self.value!r}.")
        object.__setattr__(self, "value", candidate)

    def __str__(self) -> str:
        return self.value


@dataclass(slots=True)
class User:
    """A person who signs in to SPA.

    Users are organization-independent: the same person can belong to several
    organizations with different roles.
    """

    email: Email
    display_name: str
    id: UserId = field(default_factory=lambda: UserId(new_id()))
    is_active: bool = True
    created_at: datetime = field(default_factory=utcnow)
    updated_at: datetime = field(default_factory=utcnow)

    def __post_init__(self) -> None:
        if not self.display_name.strip():
            raise ValueError("User display_name must not be empty.")

    def deactivate(self) -> None:
        """Disable sign-in without deleting the user's historical data."""
        self.is_active = False
        self.updated_at = utcnow()

    def rename(self, display_name: str) -> None:
        if not display_name.strip():
            raise ValueError("User display_name must not be empty.")
        self.display_name = display_name
        self.updated_at = utcnow()
