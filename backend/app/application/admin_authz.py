"""Administrative authorization and audit.

One place resolves whether an administrator may do something, and one place
records that they did it. Routes ask this module rather than inspecting roles,
so a role name never appears in a route handler and a new privilege cannot be
honoured by some endpoints and ignored by others.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.application.ports.admin import (
    AdminPrivilegeRepository,
    AdminRepository,
    AdminRoleRepository,
)
from app.domain.admin.catalogue import ROLE_PRIVILEGES
from app.domain.admin.entities import AdminIdentity, AdminRole
from app.domain.security.entities import SecurityEvent, SecurityEventType
from app.domain.shared import UserId


class NotAnAdministrator(Exception):
    """The authenticated user holds no platform-administration record."""


class AdministratorMayNotAct(Exception):
    """The record exists but its lifecycle state forbids administrative action."""


class MissingPrivilege(Exception):
    """The administrator is active but does not hold the required privilege."""


class MfaNotSatisfied(Exception):
    """The session has not satisfied the administrative second factor."""


@dataclass(frozen=True, slots=True)
class AdminContext:
    """An administrator proven eligible to act, with their effective privileges."""

    admin: AdminIdentity
    privileges: frozenset[str]
    is_superadmin: bool

    def holds(self, privilege: str) -> bool:
        return privilege in self.privileges

    def require(self, privilege: str) -> None:
        if not self.holds(privilege):
            raise MissingPrivilege(f"Privilege {privilege} is required.")


def role_privileges(role: AdminRole) -> frozenset[str]:
    """The privileges a role grants, read from the catalogue.

    The catalogue is the single source of truth the migration seeds from, so a
    role cannot grant one thing in the database and another at authorization time.
    """
    return frozenset(ROLE_PRIVILEGES[str(role)])


async def effective_privileges(
    admin_id: object,
    *,
    roles: AdminRoleRepository,
    privileges: AdminPrivilegeRepository,
) -> frozenset[str]:
    """Every privilege an administrator holds, right now.

    Roles and direct grants are both read on each call rather than cached: a
    privilege removal has to take effect on the very next request, and an
    in-process cache is exactly how a removed privilege keeps working.
    """
    names = {str(privilege) for privilege in await privileges.privileges_for_admin(admin_id)}
    for role in await roles.roles_for_admin(admin_id):
        names |= role_privileges(role)
    return frozenset(names)


async def build_context(
    user_id: UserId,
    *,
    admins: AdminRepository,
    roles: AdminRoleRepository,
    privileges: AdminPrivilegeRepository,
    mfa_satisfied: bool,
) -> AdminContext:
    """Resolve an administrator and prove they may act.

    Raises rather than returning None so that a caller cannot forget the check and
    fall through to a handler with an unresolved identity.
    """
    admin = await admins.get_by_user(user_id)
    if admin is None:
        raise NotAnAdministrator(f"User {user_id} is not an administrator.")
    if not admin.status.can_act:
        raise AdministratorMayNotAct(f"Administrator is {admin.status}.")
    if not admin.is_mfa_enrolled:
        raise MfaNotSatisfied("Administrator has not enrolled a second factor.")
    if not mfa_satisfied:
        raise MfaNotSatisfied("This session has not satisfied the second factor.")

    held = await roles.roles_for_admin(admin.id)
    is_superadmin = any(str(role) == AdminRole.SUPERADMIN for role in held)
    privileges_now = await effective_privileges(admin.id, roles=roles, privileges=privileges)
    return AdminContext(admin=admin, privileges=privileges_now, is_superadmin=is_superadmin)


def audit_event(
    event_type: str,
    *,
    actor: UserId | None,
    target_admin_id: object | None = None,
    metadata: dict[str, object] | None = None,
    ip_prefix: str | None = None,
    user_agent: str | None = None,
) -> SecurityEvent:
    """Build an append-only administrative audit record.

    'metadata' is filtered to primitive values and the caller is expected to pass
    identifiers only. Nothing here accepts a secret because none is ever needed:
    the actor, the target, and the action are enough to reconstruct what happened.
    """
    payload: dict[str, object] = {"admin_id": str(target_admin_id)} if target_admin_id else {}
    if metadata:
        payload.update(
            {
                key: value
                for key, value in metadata.items()
                if value is None or isinstance(value, (str, int, float, bool))
            }
        )
    return SecurityEvent(
        user_id=actor,
        event_type=str(SecurityEventType(event_type)),
        metadata=payload,
        ip_prefix=ip_prefix,
        user_agent=user_agent,
    )
