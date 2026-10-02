"""Users: identity, credentials and account lifecycle.

Credentials are held as an opaque hash produced by a 'PasswordHasher' port; the
domain never sees or records a plaintext password.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from app.domain.shared import UserId, new_id, utcnow
from app.domain.users.credentials import normalise_email

_EMAIL_MIN_PARTS = 2


@dataclass(frozen=True, slots=True)
class Email:
    """A validated email address.

    Normalised to lowercase on construction so that uniqueness checks and
    lookups cannot drift because of casing.
    """

    value: str

    def __post_init__(self) -> None:
        candidate = normalise_email(self.value)
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


class AccountStatus:
    """The lifecycle state of an account.

    A constrained string rather than an enum so the persisted vocabulary can grow
    without a database type migration. A suspended or deactivated account must
    not authenticate; sign-in and the session dependency both check this.
    """

    __slots__ = ("value",)

    PENDING_VERIFICATION = "pending_verification"
    ACTIVE = "active"
    SUSPENDED = "suspended"
    DEACTIVATED = "deactivated"

    ALLOWED = frozenset({PENDING_VERIFICATION, ACTIVE, SUSPENDED, DEACTIVATED})

    def __init__(self, value: str) -> None:
        if value not in self.ALLOWED:
            raise ValueError(f"Unknown account status: {value!r}.")
        self.value = value

    @property
    def can_authenticate(self) -> bool:
        return self.value in {self.PENDING_VERIFICATION, self.ACTIVE}

    @property
    def is_verified(self) -> bool:
        return self.value == self.ACTIVE

    def __str__(self) -> str:
        return self.value

    def __repr__(self) -> str:
        return f"AccountStatus({self.value!r})"

    def __eq__(self, other: object) -> bool:
        if isinstance(other, AccountStatus):
            return self.value == other.value
        if isinstance(other, str):
            return self.value == other
        return NotImplemented

    def __hash__(self) -> int:
        return hash(self.value)


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
    account_status: AccountStatus = field(
        default_factory=lambda: AccountStatus(AccountStatus.PENDING_VERIFICATION)
    )
    password_hash: str | None = None
    email_verified_at: datetime | None = None
    phone_number: str | None = None
    phone_verified_at: datetime | None = None
    last_login_at: datetime | None = None
    password_changed_at: datetime | None = None
    created_at: datetime = field(default_factory=utcnow)
    updated_at: datetime = field(default_factory=utcnow)

    def __post_init__(self) -> None:
        if not self.display_name.strip():
            raise ValueError("User display_name must not be empty.")

    @property
    def status(self) -> AccountStatus:
        return self.account_status

    @property
    def can_authenticate(self) -> bool:
        """Whether this account is allowed to hold or open a session."""
        return self.is_active and self.account_status.can_authenticate

    @property
    def is_email_verified(self) -> bool:
        return self.email_verified_at is not None

    @property
    def has_password(self) -> bool:
        return self.password_hash is not None

    @property
    def is_phone_verified(self) -> bool:
        return self.phone_verified_at is not None and self.phone_number is not None

    def set_password_hash(self, password_hash: str) -> None:
        self.password_hash = password_hash
        self.password_changed_at = utcnow()
        self.updated_at = utcnow()

    def mark_email_verified(self) -> None:
        self.email_verified_at = utcnow()
        if self.account_status.value == AccountStatus.PENDING_VERIFICATION:
            self.account_status = AccountStatus(AccountStatus.ACTIVE)
        self.updated_at = utcnow()

    def change_email(self, email: Email) -> None:
        """Replace the address and clear its verification.

        The new address is unverified by construction: treating it as verified
        would let someone holding a session move the account to a mailbox they
        control and then take it over through password recovery.
        """
        self.email = email
        self.email_verified_at = None
        if self.account_status.value == AccountStatus.ACTIVE:
            self.account_status = AccountStatus(AccountStatus.PENDING_VERIFICATION)
        self.updated_at = utcnow()

    def set_phone_number(self, phone_number: str) -> None:
        self.phone_number = phone_number
        self.phone_verified_at = None
        self.updated_at = utcnow()

    def mark_phone_verified(self, phone_number: str) -> None:
        self.phone_number = phone_number
        self.phone_verified_at = utcnow()
        self.updated_at = utcnow()

    def remove_phone_number(self) -> None:
        self.phone_number = None
        self.phone_verified_at = None
        self.updated_at = utcnow()

    def record_login(self) -> None:
        self.last_login_at = utcnow()
        self.updated_at = utcnow()

    def suspend(self) -> None:
        self.account_status = AccountStatus(AccountStatus.SUSPENDED)
        self.updated_at = utcnow()

    def reactivate(self) -> None:
        self.account_status = AccountStatus(
            AccountStatus.ACTIVE if self.is_email_verified else AccountStatus.PENDING_VERIFICATION
        )
        self.is_active = True
        self.updated_at = utcnow()

    def deactivate(self) -> None:
        """Disable sign-in without deleting the user's historical data."""
        self.account_status = AccountStatus(AccountStatus.DEACTIVATED)
        self.is_active = False
        self.updated_at = utcnow()

    def rename(self, display_name: str) -> None:
        if not display_name.strip():
            raise ValueError("User display_name must not be empty.")
        self.display_name = display_name
        self.updated_at = utcnow()
