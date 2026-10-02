"""Repository ports for platform administration.

Kept beside the resource repository ports but in their own module: administration
is a separate security domain, and a reader looking for how an administrator is
resolved should not have to scan the video and analysis ports to find it.
"""

from __future__ import annotations

import builtins
from typing import Protocol, runtime_checkable

from app.domain.admin.entities import (
    AdminIdentity,
    AdminInvitation,
    AdminMfaChallenge,
    AdminPrivilege,
    AdminRole,
)
from app.domain.shared import UserId


@runtime_checkable
class AdminRepository(Protocol):
    async def add(self, admin: AdminIdentity) -> None: ...

    async def get(self, admin_id: object) -> AdminIdentity | None: ...

    async def get_by_user(self, user_id: UserId) -> AdminIdentity | None: ...

    async def update(self, admin: AdminIdentity) -> None: ...

    async def list(self, *, limit: int = 50, offset: int = 0) -> list[AdminIdentity]: ...


@runtime_checkable
class AdminRoleRepository(Protocol):
    async def get_by_name(self, name: str) -> AdminRole | None: ...
    async def id_for_role(self, role: AdminRole) -> object | None:
        """The catalogue row id for a role, for tables that reference it."""

    async def list(self) -> builtins.list[AdminRole]: ...

    async def roles_for_admin(self, admin_id: object) -> builtins.list[AdminRole]: ...

    async def assign(
        self, admin_id: object, role: AdminRole, *, assigned_by: UserId | None
    ) -> None: ...

    async def unassign(self, admin_id: object, role: AdminRole) -> None: ...


@runtime_checkable
class AdminPrivilegeRepository(Protocol):
    async def list(self) -> builtins.list[AdminPrivilege]: ...

    async def privileges_for_admin(self, admin_id: object) -> builtins.list[AdminPrivilege]: ...

    async def grant(
        self, admin_id: object, privilege: AdminPrivilege, *, granted_by: UserId | None
    ) -> None: ...

    async def revoke(self, admin_id: object, privilege: AdminPrivilege) -> None: ...


@runtime_checkable
class AdminInvitationRepository(Protocol):
    async def add(self, invitation: AdminInvitation, *, role_id: object) -> None: ...

    async def get(self, invitation_id: object) -> tuple[AdminInvitation, object] | None:
        """The invitation together with the role id it offers."""

    async def get_by_token_hash(self, token_hash: str) -> tuple[AdminInvitation, object] | None: ...

    async def latest_for_email(self, email: str) -> AdminInvitation | None:
        """The most recent invitation for an address, for the resend cooldown."""

    async def list(self, *, limit: int = 50, offset: int = 0) -> list[AdminInvitation]: ...

    async def update(self, invitation: AdminInvitation) -> None: ...

    async def invalidate_for_email(self, email: str) -> int:
        """Revoke every outstanding invitation for an address."""


@runtime_checkable
class AdminMfaRepository(Protocol):
    async def set_secret(self, admin_id: object, *, secret_encrypted: str) -> None: ...

    async def get_secret(self, admin_id: object) -> str | None: ...

    async def confirm(self, admin_id: object) -> None: ...

    async def is_confirmed(self, admin_id: object) -> bool: ...

    async def replace_recovery_codes(self, admin_id: object, *, code_hashes: list[str]) -> None: ...

    async def consume_recovery_code(self, admin_id: object, *, code_hash: str) -> bool: ...

    async def clear(self, admin_id: object) -> None:
        """Remove the credential and every recovery code, for a reset."""

    async def start_challenge(
        self, admin_id: object, *, session_id: object, expires_at: object, max_attempts: int
    ) -> None: ...

    async def get_challenge(
        self, admin_id: object, session_id: object
    ) -> AdminMfaChallenge | None: ...

    async def record_challenge_attempt(self, challenge_id: object, *, attempts: int) -> None: ...

    async def satisfy_challenge(self, challenge_id: object) -> None: ...


__all__ = [
    "AdminInvitationRepository",
    "AdminMfaRepository",
    "AdminPrivilegeRepository",
    "AdminRepository",
    "AdminRoleRepository",
]
