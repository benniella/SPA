"""Administrative role assignment.

The escalation rule lives here rather than in each caller: an actor may only
confer a set of roles whose combined privileges they already hold themselves, so
a support administrator cannot mint a superadmin and a finance administrator
cannot grant security authority.
"""

from __future__ import annotations

from app.application.admin_authz import AdminContext, audit_event, role_privileges
from app.application.ports.admin import (
    AdminRepository,
    AdminRoleRepository,
)
from app.application.ports.repositories import SecurityEventRepository
from app.core.errors import ConflictError, NotFoundError, ValidationError
from app.domain.admin.entities import AdminIdentity, AdminPrivilege, AdminRole
from app.domain.security.entities import SecurityEventType


async def list_administrator_roles(
    actor: AdminContext,
    admin_id: object,
    *,
    admins: AdminRepository,
    roles: AdminRoleRepository,
) -> list[str]:
    actor.require(AdminPrivilege.ADMINS_READ)
    await _require_admin(admins, admin_id)
    return [str(role) for role in await roles.roles_for_admin(admin_id)]


async def set_administrator_roles(
    actor: AdminContext,
    admin_id: object,
    requested: list[str],
    *,
    admins: AdminRepository,
    roles: AdminRoleRepository,
    security_events: SecurityEventRepository,
    ip_prefix: str | None = None,
    user_agent: str | None = None,
) -> list[str]:
    """Replace an administrator's roles with exactly 'requested'."""
    actor.require(AdminPrivilege.ADMINS_MANAGE)
    target = await admins.get(admin_id)
    if target is None:
        raise NotFoundError(f"Administrator {admin_id} does not exist.")

    wanted = _validate_requested(requested)
    await _refuse_escalation(actor, wanted)
    await _refuse_managing_a_superadmin(actor, target, roles=roles)
    if AdminRole.SUPERADMIN in {str(role) for role in wanted} and not actor.is_superadmin:
        raise ConflictError("Only a superadmin may grant the superadmin role.")

    current = {str(role) for role in await roles.roles_for_admin(target.id)}
    for role in wanted:
        if str(role) not in current:
            await roles.assign(target.id, role, assigned_by=actor.admin.user_id)
            await security_events.add(
                audit_event(
                    SecurityEventType.ADMIN_ROLE_ASSIGNED,
                    actor=actor.admin.user_id,
                    target_admin_id=target.id,
                    metadata={"role": str(role)},
                    ip_prefix=ip_prefix,
                    user_agent=user_agent,
                )
            )
    for name in sorted(current - {str(role) for role in wanted}):
        await roles.unassign(target.id, AdminRole(name))
        await security_events.add(
            audit_event(
                SecurityEventType.ADMIN_ROLE_REMOVED,
                actor=actor.admin.user_id,
                target_admin_id=target.id,
                metadata={"role": name},
                ip_prefix=ip_prefix,
                user_agent=user_agent,
            )
        )
    return [str(role) for role in await roles.roles_for_admin(target.id)]


def _validate_requested(requested: list[str]) -> list[AdminRole]:
    seen: list[AdminRole] = []
    for name in requested:
        try:
            role = AdminRole(name)
        except ValueError as exc:
            raise ValidationError(f"Unknown administrative role: {name!r}.") from exc
        if role not in seen:
            seen.append(role)
    return seen


async def _refuse_escalation(actor: AdminContext, wanted: list[AdminRole]) -> None:
    """Refuse any role whose privileges the actor does not already hold.

    Superadmin is exempt from the subset test because it is refused separately:
    comparing it as a privilege set would let a superadmin pass and every other
    actor fail for the wrong reason.
    """
    if actor.is_superadmin:
        return
    for role in wanted:
        if str(role) == AdminRole.SUPERADMIN:
            continue
        missing = role_privileges(role) - actor.privileges
        if missing:
            raise ConflictError(
                f"Role {role} grants privileges the actor does not hold: {sorted(missing)}."
            )


async def _refuse_managing_a_superadmin(
    actor: AdminContext,
    target: AdminIdentity,
    *,
    roles: AdminRoleRepository,
) -> None:
    target_roles = {str(role) for role in await roles.roles_for_admin(target.id)}
    if AdminRole.SUPERADMIN in target_roles and not actor.is_superadmin:
        raise ConflictError("Only a superadmin may manage a superadmin.")


async def _require_admin(admins: AdminRepository, admin_id: object) -> None:
    if await admins.get(admin_id) is None:
        raise NotFoundError(f"Administrator {admin_id} does not exist.")
