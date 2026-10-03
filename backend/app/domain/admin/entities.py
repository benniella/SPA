"""Platform administration: identity, roles, privileges and invitations.

Organization roles are a tenancy concern and live in the organizations domain.
These are platform-wide and are deliberately a separate security domain: an
organization owner is not an administrator, and becoming one must never be a
side effect of creating a workspace.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import NewType

from app.domain.shared import UserId, new_id, utcnow

AdminId = NewType("AdminId", uuid.UUID)
AdminInvitationId = NewType("AdminInvitationId", uuid.UUID)


class AdminStatus:
    """The lifecycle state of a platform administrator.

    A constrained string rather than an enum so the vocabulary can grow without a
    database type migration, matching the convention the rest of the domain uses.
    """

    __slots__ = ("value",)

    INVITED = "invited"
    ACTIVE = "active"
    SUSPENDED = "suspended"
    REVOKED = "revoked"

    ALLOWED = frozenset({INVITED, ACTIVE, SUSPENDED, REVOKED})

    def __init__(self, value: str) -> None:
        if value not in self.ALLOWED:
            raise ValueError(f"Unknown administrator status: {value!r}.")
        self.value = value

    def __str__(self) -> str:
        return self.value

    def __repr__(self) -> str:
        return f"AdminStatus({self.value!r})"

    def __eq__(self, other: object) -> bool:
        if isinstance(other, AdminStatus):
            return self.value == other.value
        if isinstance(other, str):
            return self.value == other
        return NotImplemented

    def __hash__(self) -> int:
        return hash(self.value)

    @property
    def can_act(self) -> bool:
        """Whether this administrator may reach administrative endpoints."""
        return self.value == self.ACTIVE


class AdminRole:
    """The administrative job a person holds. Roles grant privileges."""

    __slots__ = ("value",)

    FINANCE_ADMIN = "finance_admin"
    MAINTENANCE_ADMIN = "maintenance_admin"
    SUPPORT_ADMIN = "support_admin"
    ACCOUNT_REVIEW_ADMIN = "account_review_admin"
    COMMUNICATIONS_ADMIN = "communications_admin"
    SECURITY_ADMIN = "security_admin"
    OPERATIONS_ADMIN = "operations_admin"
    SUPERADMIN = "superadmin"

    ALLOWED = frozenset(
        {
            FINANCE_ADMIN,
            MAINTENANCE_ADMIN,
            SUPPORT_ADMIN,
            ACCOUNT_REVIEW_ADMIN,
            COMMUNICATIONS_ADMIN,
            SECURITY_ADMIN,
            OPERATIONS_ADMIN,
            SUPERADMIN,
        }
    )

    def __init__(self, value: str) -> None:
        if value not in self.ALLOWED:
            raise ValueError(f"Unknown administrator role: {value!r}.")
        self.value = value

    def __str__(self) -> str:
        return self.value

    def __repr__(self) -> str:
        return f"AdminRole({self.value!r})"

    def __eq__(self, other: object) -> bool:
        if isinstance(other, AdminRole):
            return self.value == other.value
        if isinstance(other, str):
            return self.value == other
        return NotImplemented

    def __hash__(self) -> int:
        return hash(self.value)


class AdminPrivilege:
    """A single platform capability.

    Authorization is expressed in privileges, never in role names: a route asks
    for 'users.manage', not for 'the finance role', so adding a role does not
    require touching routes and removing one cannot silently widen access.
    """

    __slots__ = ("value",)

    USERS_READ = "users.read"
    USERS_MANAGE = "users.manage"
    USERS_SUSPEND = "users.suspend"
    USERS_REACTIVATE = "users.reactivate"

    ORGANIZATIONS_READ = "organizations.read"
    ORGANIZATIONS_MANAGE = "organizations.manage"

    BILLING_READ = "billing.read"
    BILLING_MANAGE = "billing.manage"

    SUPPORT_READ = "support.read"
    SUPPORT_MANAGE = "support.manage"

    COMMUNICATIONS_READ = "communications.read"
    COMMUNICATIONS_SEND = "communications.send"

    SYSTEM_READ = "system.read"
    SYSTEM_MANAGE = "system.manage"

    MAINTENANCE_READ = "maintenance.read"
    MAINTENANCE_MANAGE = "maintenance.manage"

    SECURITY_READ = "security.read"
    SECURITY_MANAGE = "security.manage"

    JOBS_READ = "jobs.read"
    JOBS_MANAGE = "jobs.manage"

    REPORTS_READ = "reports.read"

    CONFIGURATION_READ = "configuration.read"
    CONFIGURATION_MANAGE = "configuration.manage"

    # Administration of the administrator directory itself. Kept separate from
    # 'users.manage' so that managing platform customers never implies the ability
    # to create or revoke administrators.
    ADMINS_READ = "admins.read"
    ADMINS_MANAGE = "admins.manage"

    ALLOWED = frozenset(
        {
            USERS_READ,
            USERS_MANAGE,
            USERS_SUSPEND,
            USERS_REACTIVATE,
            ORGANIZATIONS_READ,
            ORGANIZATIONS_MANAGE,
            BILLING_READ,
            BILLING_MANAGE,
            SUPPORT_READ,
            SUPPORT_MANAGE,
            COMMUNICATIONS_READ,
            COMMUNICATIONS_SEND,
            SYSTEM_READ,
            SYSTEM_MANAGE,
            MAINTENANCE_READ,
            MAINTENANCE_MANAGE,
            SECURITY_READ,
            SECURITY_MANAGE,
            JOBS_READ,
            JOBS_MANAGE,
            REPORTS_READ,
            CONFIGURATION_READ,
            CONFIGURATION_MANAGE,
            ADMINS_READ,
            ADMINS_MANAGE,
        }
    )

    def __init__(self, value: str) -> None:
        if value not in self.ALLOWED:
            raise ValueError(f"Unknown administrator privilege: {value!r}.")
        self.value = value

    def __str__(self) -> str:
        return self.value

    def __repr__(self) -> str:
        return f"AdminPrivilege({self.value!r})"

    def __eq__(self, other: object) -> bool:
        if isinstance(other, AdminPrivilege):
            return self.value == other.value
        if isinstance(other, str):
            return self.value == other
        return NotImplemented

    def __hash__(self) -> int:
        return hash(self.value)


@dataclass(frozen=True, slots=True)
class AdminIdentity:
    """A user's platform-administration record."""

    user_id: UserId
    status: AdminStatus
    id: AdminId = field(default_factory=lambda: AdminId(new_id()))
    mfa_enrolled_at: datetime | None = None
    created_at: datetime = field(default_factory=utcnow)
    updated_at: datetime = field(default_factory=utcnow)

    @property
    def is_mfa_enrolled(self) -> bool:
        return self.mfa_enrolled_at is not None

    def can_act(self, *, mfa_satisfied: bool) -> bool:
        """Whether this administrator may reach administrative endpoints now.

        Status and MFA are both required. A suspended or revoked administrator
        fails on status; an active one who has not enrolled fails on MFA, so an
        invitation cannot be turned into access by skipping enrollment.
        """
        return self.status.can_act and self.is_mfa_enrolled and mfa_satisfied


@dataclass(slots=True)
class AdminInvitation:
    """A single-use, expiring offer of administrative access."""

    email: str
    role: AdminRole
    token_hash: str
    expires_at: datetime
    invited_by: UserId | None
    id: AdminInvitationId = field(default_factory=lambda: AdminInvitationId(new_id()))
    created_at: datetime = field(default_factory=utcnow)
    accepted_at: datetime | None = None
    revoked_at: datetime | None = None

    @property
    def is_accepted(self) -> bool:
        return self.accepted_at is not None

    @property
    def is_revoked(self) -> bool:
        return self.revoked_at is not None

    def is_expired(self, *, at: datetime | None = None) -> bool:
        return (at or utcnow()) >= self.expires_at

    def is_usable(self, *, at: datetime | None = None) -> bool:
        return not self.is_accepted and not self.is_revoked and not self.is_expired(at=at)

    def accept(self, *, at: datetime | None = None) -> None:
        self.accepted_at = at or utcnow()

    def revoke(self, *, at: datetime | None = None) -> None:
        if self.revoked_at is None:
            self.revoked_at = at or utcnow()


class AdminInvitationStatus:
    """The derived lifecycle state of an invitation.

    Never stored: acceptance, revocation and expiry are recorded as separate
    timestamps, and the status shown to an operator is a reading of those.
    """

    __slots__ = ("value",)

    OUTSTANDING = "outstanding"
    ACCEPTED = "accepted"
    REVOKED = "revoked"
    EXPIRED = "expired"

    ALLOWED = frozenset({OUTSTANDING, ACCEPTED, REVOKED, EXPIRED})

    @classmethod
    def of(cls, invitation: AdminInvitation, *, at: datetime | None = None) -> str:
        if invitation.is_accepted:
            return cls.ACCEPTED
        if invitation.is_revoked:
            return cls.REVOKED
        if invitation.is_expired(at=at):
            return cls.EXPIRED
        return cls.OUTSTANDING


@dataclass(slots=True)
class AdminMfaChallenge:
    """A short-lived step-up challenge bound to one administrative session.

    Binding to the session is what makes it a step-up rather than a second login:
    satisfying it proves the person at the keyboard now is the person who opened
    the session, and it cannot be replayed onto a different session.
    """

    admin_id: AdminId
    session_id: object
    expires_at: datetime
    id: object = field(default_factory=lambda: new_id())
    attempts: int = 0
    max_attempts: int = 5
    created_at: datetime = field(default_factory=utcnow)
    satisfied_at: datetime | None = None

    @property
    def is_satisfied(self) -> bool:
        return self.satisfied_at is not None

    @property
    def attempts_exhausted(self) -> bool:
        return self.attempts >= self.max_attempts

    def is_expired(self, *, at: datetime | None = None) -> bool:
        return (at or utcnow()) >= self.expires_at

    def register_attempt(self) -> None:
        self.attempts += 1

    def satisfy(self, *, at: datetime | None = None) -> None:
        self.satisfied_at = at or utcnow()


__all__ = [
    "AdminId",
    "AdminIdentity",
    "AdminInvitation",
    "AdminInvitationId",
    "AdminMfaChallenge",
    "AdminPrivilege",
    "AdminRole",
    "AdminStatus",
]
