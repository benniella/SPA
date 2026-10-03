from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Annotated

from fastapi import Depends

from app.api.dependencies import CurrentSessionDep, CurrentUserDep, UnitOfWorkDep
from app.application.admin_authz import (
    AdminContext,
    AdministratorMayNotAct,
    MfaNotSatisfied,
    MissingPrivilege,
    NotAnAdministrator,
    build_context,
)
from app.core.errors import AuthenticationError, PermissionDeniedError


async def require_admin(
    user: CurrentUserDep,
    session: CurrentSessionDep,
    uow: UnitOfWorkDep,
) -> AdminContext:
    """Resolve the caller as an administrator who may act on this request.

    Lifecycle state, roles and privileges are read from the database on every
    request, so a suspension, revocation or role change applies immediately.
    """
    mfa_satisfied = session is not None and session.is_mfa_verified
    try:
        async with uow:
            context = await build_context(
                user.id,
                admins=uow.admins,
                roles=uow.admin_roles,
                privileges=uow.admin_privileges,
                mfa_satisfied=mfa_satisfied,
            )
            await uow.commit()
            return context
    except NotAnAdministrator as exc:
        raise PermissionDeniedError(
            "Platform administration is not available to this account."
        ) from exc
    except AdministratorMayNotAct as exc:
        raise PermissionDeniedError("This administrator account cannot act right now.") from exc
    except MfaNotSatisfied as exc:
        raise AuthenticationError("A second factor is required.") from exc


AdminDep = Annotated[AdminContext, Depends(require_admin)]


def require_privilege(privilege: str) -> Callable[..., Awaitable[AdminContext]]:
    async def dependency(admin: AdminDep) -> AdminContext:
        try:
            admin.require(privilege)
        except MissingPrivilege as exc:
            raise PermissionDeniedError(f"Privilege {privilege} is required.") from exc
        return admin

    return dependency


__all__ = ["AdminDep", "require_admin", "require_privilege"]
