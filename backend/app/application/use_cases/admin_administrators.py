"""Administrator read and lifecycle use cases.

Authorization is a parameter of every call rather than something the caller is
trusted to have done: a use case that could be reached without an
'AdminContext' would be an authorization hole waiting for a route to forget.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.application.admin_authz import AdminContext, audit_event
from app.application.ports.admin import (
    AdminPrivilegeRepository,
    AdminRepository,
    AdminRoleRepository,
)
from app.application.ports.repositories import SecurityEventRepository, UserRepository
from app.core.errors import ConflictError, NotFoundError
from app.domain.admin.entities import AdminIdentity, AdminPrivilege, AdminStatus
from app.domain.security.entities import SecurityEventType
from app.domain.shared import utcnow


@dataclass(frozen=True, slots=True)
class AdministratorSummary:
    admin: AdminIdentity
    roles: list[str]
    privileges: list[str]
    email: str | None
    mfa_enrolled: bool


async def list_administrators(
    actor: AdminContext,
    *,
    admins: AdminRepository,
    roles: AdminRoleRepository,
    privileges: AdminPrivilegeRepository,
    users: UserRepository,
    limit: int = 50,
    offset: int = 0,
) -> list[AdministratorSummary]:
    actor.require(AdminPrivilege.ADMINS_READ)
    summaries = []
    for admin in await admins.list(limit=limit, offset=offset):
        summaries.append(await _summarize(admin, roles=roles, privileges=privileges, users=users))
    return summaries


async def get_administrator(
    actor: AdminContext,
    admin_id: object,
    *,
    admins: AdminRepository,
    roles: AdminRoleRepository,
    privileges: AdminPrivilegeRepository,
    users: UserRepository,
) -> AdministratorSummary:
    actor.require(AdminPrivilege.ADMINS_READ)
    return await _summarize(
        await _require_admin(admins, admin_id),
        roles=roles,
        privileges=privileges,
        users=users,
    )


async def list_roles(
    actor: AdminContext,
    *,
    roles: AdminRoleRepository,
) -> list[str]:
    del actor
    return [str(role) for role in await roles.list()]


async def list_privileges(
    actor: AdminContext,
    *,
    privileges: AdminPrivilegeRepository,
) -> list[str]:
    del actor
    return [str(privilege) for privilege in await privileges.list()]


async def suspend_administrator(
    actor: AdminContext,
    admin_id: object,
    *,
    admins: AdminRepository,
    roles: AdminRoleRepository,
    privileges: AdminPrivilegeRepository,
    security_events: SecurityEventRepository,
    ip_prefix: str | None = None,
    user_agent: str | None = None,
) -> AdminIdentity:
    return await _transition(
        actor,
        admin_id,
        target_status=AdminStatus.SUSPENDED,
        allowed_from=(AdminStatus.ACTIVE,),
        event_type=SecurityEventType.ADMIN_SUSPENDED,
        admins=admins,
        roles=roles,
        privileges=privileges,
        security_events=security_events,
        ip_prefix=ip_prefix,
        user_agent=user_agent,
    )


async def reactivate_administrator(
    actor: AdminContext,
    admin_id: object,
    *,
    admins: AdminRepository,
    roles: AdminRoleRepository,
    privileges: AdminPrivilegeRepository,
    security_events: SecurityEventRepository,
    ip_prefix: str | None = None,
    user_agent: str | None = None,
) -> AdminIdentity:
    return await _transition(
        actor,
        admin_id,
        target_status=AdminStatus.ACTIVE,
        allowed_from=(AdminStatus.SUSPENDED,),
        event_type=SecurityEventType.ADMIN_REACTIVATED,
        admins=admins,
        roles=roles,
        privileges=privileges,
        security_events=security_events,
        ip_prefix=ip_prefix,
        user_agent=user_agent,
    )


async def revoke_administrator(
    actor: AdminContext,
    admin_id: object,
    *,
    admins: AdminRepository,
    roles: AdminRoleRepository,
    privileges: AdminPrivilegeRepository,
    security_events: SecurityEventRepository,
    ip_prefix: str | None = None,
    user_agent: str | None = None,
) -> AdminIdentity:
    return await _transition(
        actor,
        admin_id,
        target_status=AdminStatus.REVOKED,
        allowed_from=(AdminStatus.ACTIVE, AdminStatus.SUSPENDED, AdminStatus.INVITED),
        event_type=SecurityEventType.ADMIN_REVOKED,
        admins=admins,
        roles=roles,
        privileges=privileges,
        security_events=security_events,
        ip_prefix=ip_prefix,
        user_agent=user_agent,
    )


async def _transition(
    actor: AdminContext,
    admin_id: object,
    *,
    target_status: str,
    allowed_from: tuple[str, ...],
    event_type: str,
    admins: AdminRepository,
    roles: AdminRoleRepository,
    privileges: AdminPrivilegeRepository,
    security_events: SecurityEventRepository,
    ip_prefix: str | None,
    user_agent: str | None,
) -> AdminIdentity:
    actor.require(AdminPrivilege.ADMINS_MANAGE)
    target = await _require_admin(admins, admin_id)
    await _refuse_managing_a_superadmin(actor, target, roles=roles)

    current = str(target.status)
    if current not in allowed_from:
        raise ConflictError(f"Administrator is {current}, not one of {allowed_from}.")

    updated = AdminIdentity(
        user_id=target.user_id,
        status=AdminStatus(target_status),
        id=target.id,
        mfa_enrolled_at=target.mfa_enrolled_at,
        created_at=target.created_at,
        updated_at=utcnow(),
    )
    await admins.update(updated)
    await security_events.add(
        audit_event(
            event_type,
            actor=actor.admin.user_id,
            target_admin_id=target.id,
            metadata={"from": current, "to": target_status},
            ip_prefix=ip_prefix,
            user_agent=user_agent,
        )
    )
    return updated


async def require_not_self(actor: AdminContext, admin_id: object) -> None:
    """Refuse an administrator acting on their own record.

    Suspending or revoking yourself is never a recovery path and is a common way
    to lock a platform out of its last administrator.
    """
    if str(actor.admin.id) == str(admin_id):
        raise ConflictError("An administrator cannot change their own lifecycle state.")


async def _refuse_managing_a_superadmin(
    actor: AdminContext,
    target: AdminIdentity,
    *,
    roles: AdminRoleRepository,
) -> None:
    from app.domain.admin.entities import AdminRole

    target_roles = await roles.roles_for_admin(target.id)
    if any(str(role) == AdminRole.SUPERADMIN for role in target_roles) and not actor.is_superadmin:
        raise ConflictError("Only a superadmin may manage a superadmin.")


async def _require_admin(admins: AdminRepository, admin_id: object) -> AdminIdentity:
    admin = await admins.get(admin_id)
    if admin is None:
        raise NotFoundError(f"Administrator {admin_id} does not exist.")
    return admin


async def _summarize(
    admin: AdminIdentity,
    *,
    roles: AdminRoleRepository,
    privileges: AdminPrivilegeRepository,
    users: UserRepository,
) -> AdministratorSummary:
    from app.application.admin_authz import effective_privileges

    owner = await users.get(admin.user_id)
    return AdministratorSummary(
        admin=admin,
        roles=[str(role) for role in await roles.roles_for_admin(admin.id)],
        privileges=sorted(await effective_privileges(admin.id, roles=roles, privileges=privileges)),
        email=owner.email.value if owner is not None else None,
        mfa_enrolled=admin.is_mfa_enrolled,
    )


__all__ = [
    "AdministratorSummary",
    "get_administrator",
    "list_administrators",
    "list_privileges",
    "list_roles",
    "reactivate_administrator",
    "require_not_self",
    "revoke_administrator",
    "suspend_administrator",
]
