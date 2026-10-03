"""Account-security domain: sessions, verification challenges, OTP and events.

Every one of these is an *account* concern, not an organization one, and each is
keyed by the user it protects. Nothing here is organization-scoped.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import NewType

from app.domain.shared import UserId, new_id, utcnow

SessionId = NewType("SessionId", uuid.UUID)
SecurityEventId = NewType("SecurityEventId", uuid.UUID)


class SecurityEventType:
    """The stable vocabulary of security-relevant events.

    A constrained string rather than an enum so the vocabulary can grow without a
    database type migration. Events are append-only: nothing in the application
    mutates or deletes one.
    """

    __slots__ = ("value",)

    LOGIN_SUCCESS = "LOGIN_SUCCESS"
    LOGIN_FAILED = "LOGIN_FAILED"
    LOGOUT = "LOGOUT"
    PASSWORD_CHANGED = "PASSWORD_CHANGED"
    PASSWORD_RESET_REQUESTED = "PASSWORD_RESET_REQUESTED"
    PASSWORD_RESET_COMPLETED = "PASSWORD_RESET_COMPLETED"
    EMAIL_VERIFICATION_REQUESTED = "EMAIL_VERIFICATION_REQUESTED"
    EMAIL_VERIFIED = "EMAIL_VERIFIED"
    EMAIL_CHANGE_REQUESTED = "EMAIL_CHANGE_REQUESTED"
    EMAIL_CHANGED = "EMAIL_CHANGED"
    PHONE_VERIFICATION_REQUESTED = "PHONE_VERIFICATION_REQUESTED"
    PHONE_VERIFIED = "PHONE_VERIFIED"
    PHONE_REMOVED = "PHONE_REMOVED"
    SESSION_CREATED = "SESSION_CREATED"
    SESSION_REVOKED = "SESSION_REVOKED"
    SESSIONS_REVOKED = "SESSIONS_REVOKED"
    ACCOUNT_SUSPENDED = "ACCOUNT_SUSPENDED"
    ACCOUNT_REACTIVATED = "ACCOUNT_REACTIVATED"
    RECOVERY_STARTED = "RECOVERY_STARTED"
    RECOVERY_COMPLETED = "RECOVERY_COMPLETED"
    SUSPICIOUS_ACTIVITY = "SUSPICIOUS_ACTIVITY"

    ADMIN_INVITATION_CREATED = "ADMIN_INVITATION_CREATED"
    ADMIN_INVITATION_RESENT = "ADMIN_INVITATION_RESENT"
    ADMIN_INVITATION_REVOKED = "ADMIN_INVITATION_REVOKED"
    ADMIN_INVITATION_ACCEPTED = "ADMIN_INVITATION_ACCEPTED"
    ADMIN_ROLE_ASSIGNED = "ADMIN_ROLE_ASSIGNED"
    ADMIN_ROLE_REMOVED = "ADMIN_ROLE_REMOVED"
    ADMIN_PRIVILEGE_GRANTED = "ADMIN_PRIVILEGE_GRANTED"
    ADMIN_PRIVILEGE_REVOKED = "ADMIN_PRIVILEGE_REVOKED"
    ADMIN_SUSPENDED = "ADMIN_SUSPENDED"
    ADMIN_REACTIVATED = "ADMIN_REACTIVATED"
    ADMIN_REVOKED = "ADMIN_REVOKED"
    ADMIN_MFA_ENROLLED = "ADMIN_MFA_ENROLLED"
    ADMIN_MFA_VERIFIED = "ADMIN_MFA_VERIFIED"
    ADMIN_MFA_RESET = "ADMIN_MFA_RESET"
    ADMIN_MFA_RECOVERY_USED = "ADMIN_MFA_RECOVERY_USED"
    ADMIN_MFA_RECOVERY_CODES_REGENERATED = "ADMIN_MFA_RECOVERY_CODES_REGENERATED"

    PLATFORM_CONFIGURATION_CHANGED = "PLATFORM_CONFIGURATION_CHANGED"
    PLATFORM_CONFIGURATION_RESET = "PLATFORM_CONFIGURATION_RESET"
    PLATFORM_MAINTENANCE_ENABLED = "PLATFORM_MAINTENANCE_ENABLED"
    PLATFORM_MAINTENANCE_DISABLED = "PLATFORM_MAINTENANCE_DISABLED"
    PLATFORM_RATE_LIMIT_POLICY_CHANGED = "PLATFORM_RATE_LIMIT_POLICY_CHANGED"
    PLATFORM_RATE_LIMIT_STATE_RESET = "PLATFORM_RATE_LIMIT_STATE_RESET"
    PLATFORM_IP_BLOCK_ADDED = "PLATFORM_IP_BLOCK_ADDED"
    PLATFORM_IP_BLOCK_REMOVED = "PLATFORM_IP_BLOCK_REMOVED"
    PLATFORM_COUNTRY_POLICY_CHANGED = "PLATFORM_COUNTRY_POLICY_CHANGED"
    PLATFORM_SECURITY_POLICY_CHANGED = "PLATFORM_SECURITY_POLICY_CHANGED"

    ADMIN_EVENT_PREFIX = "ADMIN_"
    PLATFORM_EVENT_PREFIX = "PLATFORM_"

    ALLOWED = frozenset(
        {
            LOGIN_SUCCESS,
            LOGIN_FAILED,
            LOGOUT,
            PASSWORD_CHANGED,
            PASSWORD_RESET_REQUESTED,
            PASSWORD_RESET_COMPLETED,
            EMAIL_VERIFICATION_REQUESTED,
            EMAIL_VERIFIED,
            EMAIL_CHANGE_REQUESTED,
            EMAIL_CHANGED,
            PHONE_VERIFICATION_REQUESTED,
            PHONE_VERIFIED,
            PHONE_REMOVED,
            SESSION_CREATED,
            SESSION_REVOKED,
            SESSIONS_REVOKED,
            ACCOUNT_SUSPENDED,
            ACCOUNT_REACTIVATED,
            RECOVERY_STARTED,
            RECOVERY_COMPLETED,
            SUSPICIOUS_ACTIVITY,
            ADMIN_INVITATION_CREATED,
            ADMIN_INVITATION_RESENT,
            ADMIN_INVITATION_REVOKED,
            ADMIN_INVITATION_ACCEPTED,
            ADMIN_ROLE_ASSIGNED,
            ADMIN_ROLE_REMOVED,
            ADMIN_PRIVILEGE_GRANTED,
            ADMIN_PRIVILEGE_REVOKED,
            ADMIN_SUSPENDED,
            ADMIN_REACTIVATED,
            ADMIN_REVOKED,
            ADMIN_MFA_ENROLLED,
            ADMIN_MFA_VERIFIED,
            ADMIN_MFA_RESET,
            ADMIN_MFA_RECOVERY_USED,
            ADMIN_MFA_RECOVERY_CODES_REGENERATED,
            PLATFORM_CONFIGURATION_CHANGED,
            PLATFORM_CONFIGURATION_RESET,
            PLATFORM_MAINTENANCE_ENABLED,
            PLATFORM_MAINTENANCE_DISABLED,
            PLATFORM_RATE_LIMIT_POLICY_CHANGED,
            PLATFORM_RATE_LIMIT_STATE_RESET,
            PLATFORM_IP_BLOCK_ADDED,
            PLATFORM_IP_BLOCK_REMOVED,
            PLATFORM_COUNTRY_POLICY_CHANGED,
            PLATFORM_SECURITY_POLICY_CHANGED,
        }
    )

    def __init__(self, value: str) -> None:
        if value not in self.ALLOWED:
            raise ValueError(f"Unknown security event type: {value!r}.")
        self.value = value

    def __str__(self) -> str:
        return self.value

    def __repr__(self) -> str:
        return f"SecurityEventType({self.value!r})"

    def __eq__(self, other: object) -> bool:
        if isinstance(other, SecurityEventType):
            return self.value == other.value
        if isinstance(other, str):
            return self.value == other
        return NotImplemented

    def __hash__(self) -> int:
        return hash(self.value)


class OtpPurpose:
    """What an OTP challenge authorises."""

    __slots__ = ("value",)

    PHONE_VERIFICATION = "phone_verification"
    PHONE_REMOVAL = "phone_removal"
    EMAIL_VERIFICATION = "email_verification"
    ACCOUNT_RECOVERY = "account_recovery"
    SENSITIVE_ACTION = "sensitive_action"

    ALLOWED = frozenset(
        {
            PHONE_VERIFICATION,
            PHONE_REMOVAL,
            EMAIL_VERIFICATION,
            ACCOUNT_RECOVERY,
            SENSITIVE_ACTION,
        }
    )

    def __init__(self, value: str) -> None:
        if value not in self.ALLOWED:
            raise ValueError(f"Unknown OTP purpose: {value!r}.")
        self.value = value

    def __str__(self) -> str:
        return self.value

    def __repr__(self) -> str:
        return f"OtpPurpose({self.value!r})"

    def __eq__(self, other: object) -> bool:
        if isinstance(other, OtpPurpose):
            return self.value == other.value
        if isinstance(other, str):
            return self.value == other
        return NotImplemented

    def __hash__(self) -> int:
        return hash(self.value)


class ChallengeKind:
    """A single-use, expiring security challenge."""

    __slots__ = ("value",)

    EMAIL_VERIFICATION = "email_verification"
    EMAIL_CHANGE = "email_change"
    PASSWORD_RESET = "password_reset"
    RECOVERY = "recovery"

    ALLOWED = frozenset({EMAIL_VERIFICATION, EMAIL_CHANGE, PASSWORD_RESET, RECOVERY})

    def __init__(self, value: str) -> None:
        if value not in self.ALLOWED:
            raise ValueError(f"Unknown challenge kind: {value!r}.")
        self.value = value

    def __str__(self) -> str:
        return self.value

    def __repr__(self) -> str:
        return f"ChallengeKind({self.value!r})"

    def __eq__(self, other: object) -> bool:
        if isinstance(other, ChallengeKind):
            return self.value == other.value
        if isinstance(other, str):
            return self.value == other
        return NotImplemented

    def __hash__(self) -> int:
        return hash(self.value)


@dataclass(slots=True)
class SecurityEvent:
    """An append-only record of something security-relevant that happened.

    Deliberately carries no secret material: a record that a password was reset
    is useful, the token that reset it is not.
    """

    user_id: UserId | None
    event_type: str
    id: SecurityEventId = field(default_factory=lambda: SecurityEventId(new_id()))
    # Truncated to the network prefix by the caller; a full address is personal
    # data that the security log does not need.
    ip_prefix: str | None = None
    user_agent: str | None = None
    metadata: dict[str, object] = field(default_factory=dict)
    created_at: datetime = field(default_factory=utcnow)

    @property
    def event(self) -> str:
        return str(self.event_type)

    def __post_init__(self) -> None:
        if self.user_agent is not None:
            self.user_agent = self.user_agent[:300]


@dataclass(slots=True)
class Session:
    """A server-controlled authenticated session.

    The browser only ever holds an opaque token; this row is the authority on
    whether that token still identifies anyone. Revocation is therefore a
    database write, not a cookie the client can choose to keep.
    """

    user_id: UserId
    expires_at: datetime
    id: SessionId = field(default_factory=lambda: SessionId(new_id()))
    created_at: datetime = field(default_factory=utcnow)
    last_used_at: datetime = field(default_factory=utcnow)
    revoked_at: datetime | None = None
    user_agent: str | None = None
    ip_prefix: str | None = None
    # When the second factor was last satisfied on this session. Administrative
    # authorization requires it, so an ordinary session leaves it None.
    mfa_verified_at: datetime | None = None

    @property
    def is_mfa_verified(self) -> bool:
        return self.mfa_verified_at is not None

    def satisfy_mfa(self, *, at: datetime | None = None) -> None:
        self.mfa_verified_at = at or utcnow()

    def __post_init__(self) -> None:
        if self.user_agent is not None:
            self.user_agent = self.user_agent[:300]

    @property
    def is_revoked(self) -> bool:
        return self.revoked_at is not None

    def is_expired(self, *, at: datetime | None = None) -> bool:
        return (at or utcnow()) >= self.expires_at

    def is_valid(self, *, at: datetime | None = None) -> bool:
        moment = at or utcnow()
        return not self.is_revoked and moment < self.expires_at

    def touch(self, *, at: datetime | None = None) -> None:
        self.last_used_at = at or utcnow()

    def revoke(self, *, at: datetime | None = None) -> None:
        if self.revoked_at is None:
            self.revoked_at = at or utcnow()


@dataclass(slots=True)
class Challenge:
    """A single-use, expiring challenge.

    Used for email verification, email change, password reset and account
    recovery. Only the hash of the token is stored, so a database read cannot be
    turned into a valid link.
    """

    user_id: UserId
    kind: str
    token_hash: str
    expires_at: datetime
    id: object = field(default_factory=lambda: new_id())
    # The address being verified for an email change; the current address
    # otherwise.
    destination: str | None = None
    created_at: datetime = field(default_factory=utcnow)
    consumed_at: datetime | None = None

    @property
    def is_consumed(self) -> bool:
        return self.consumed_at is not None

    def is_expired(self, *, at: datetime | None = None) -> bool:
        return (at or utcnow()) >= self.expires_at

    def is_usable(self, *, at: datetime | None = None) -> bool:
        return not self.is_consumed and not self.is_expired(at=at)

    def consume(self, *, at: datetime | None = None) -> None:
        self.consumed_at = at or utcnow()


@dataclass(slots=True)
class OtpChallenge:
    """A one-time code delivered to a phone number or an email address.

    The code itself is never stored: only its hash, so a database dump does not
    hand an attacker every pending verification code. Attempts are counted on the
    row, which is what makes the attempt limit enforceable rather than advisory.
    """

    user_id: UserId
    purpose: str
    code_hash: str
    destination: str
    expires_at: datetime
    id: object = field(default_factory=lambda: new_id())
    attempts: int = 0
    max_attempts: int = 5
    created_at: datetime = field(default_factory=utcnow)
    consumed_at: datetime | None = None

    @property
    def is_consumed(self) -> bool:
        return self.consumed_at is not None

    @property
    def attempts_exhausted(self) -> bool:
        return self.attempts >= self.max_attempts

    def is_expired(self, *, at: datetime | None = None) -> bool:
        return (at or utcnow()) >= self.expires_at

    def is_usable(self, *, at: datetime | None = None) -> bool:
        return not self.is_consumed and not self.is_expired(at=at) and not self.attempts_exhausted

    def register_attempt(self) -> None:
        self.attempts += 1

    def consume(self, *, at: datetime | None = None) -> None:
        self.consumed_at = at or utcnow()


def expiry_from(ttl: timedelta, *, now: datetime | None = None) -> datetime:
    return (now or utcnow()) + ttl
