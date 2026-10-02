from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request

from app.api.admin_dependencies import AdminDep, require_privilege
from app.api.dependencies import UnitOfWorkDep
from app.api.v1.presenters import administrator_payload, audit_payload
from app.application.admin_authz import AdminContext
from app.application.use_cases import admin_administrators, admin_audit, admin_roles
from app.domain.admin.entities import AdminPrivilege
from app.schemas.admin import (
    AdministratorList,
    AdministratorRead,
    AuditEventList,
    AuditEventRead,
    PrivilegeList,
    RoleList,
    RolesUpdate,
)
from app.schemas.common import ErrorResponse, PageMeta

router = APIRouter()

ManageAdmins = require_privilege(AdminPrivilege.ADMINS_MANAGE)
ReadAdmins = require_privilege(AdminPrivilege.ADMINS_READ)
ReadAudit = require_privilege(AdminPrivilege.SECURITY_READ)


@router.get(
    "/me",
    response_model=AdministratorRead,
    summary="The administrator identity behind this session",
)
async def read_self(admin: AdminDep) -> AdministratorRead:
    return AdministratorRead.model_validate(
        {
            "id": admin.admin.id,
            "user_id": admin.admin.user_id,
            "email": None,
            "status": str(admin.admin.status),
            "roles": sorted(admin.privileges),
            "privileges": sorted(admin.privileges),
            "mfa_enrolled": admin.admin.is_mfa_enrolled,
            "created_at": admin.admin.created_at,
            "updated_at": admin.admin.updated_at,
        }
    )


@router.get(
    "/administrators",
    response_model=AdministratorList,
    summary="List platform administrators",
)
async def list_administrators(
    admin: Annotated[AdminContext, Depends(ReadAdmins)],
    uow: UnitOfWorkDep,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> AdministratorList:
    async with uow:
        summaries = await admin_administrators.list_administrators(
            admin,
            admins=uow.admins,
            roles=uow.admin_roles,
            privileges=uow.admin_privileges,
            users=uow.users,
            limit=limit,
            offset=offset,
        )
        await uow.commit()
    return AdministratorList(
        items=[AdministratorRead.model_validate(administrator_payload(s)) for s in summaries],
        meta=PageMeta(limit=limit, offset=offset, count=len(summaries)),
    )


@router.get(
    "/administrators/{admin_id}",
    response_model=AdministratorRead,
    summary="Get one administrator",
    responses={404: {"model": ErrorResponse, "description": "Not found."}},
)
async def get_administrator(
    admin_id: uuid.UUID, admin: Annotated[AdminContext, Depends(ReadAdmins)], uow: UnitOfWorkDep
) -> AdministratorRead:
    async with uow:
        summary = await admin_administrators.get_administrator(
            admin,
            admin_id,
            admins=uow.admins,
            roles=uow.admin_roles,
            privileges=uow.admin_privileges,
            users=uow.users,
        )
        await uow.commit()
    return AdministratorRead.model_validate(administrator_payload(summary))


@router.post(
    "/administrators/{admin_id}/suspend",
    response_model=AdministratorRead,
    summary="Suspend an administrator",
    responses={409: {"model": ErrorResponse, "description": "Invalid state transition."}},
)
async def suspend_administrator(
    admin_id: uuid.UUID,
    admin: Annotated[AdminContext, Depends(ManageAdmins)],
    uow: UnitOfWorkDep,
    request: Request,
) -> AdministratorRead:
    await admin_administrators.require_not_self(admin, admin_id)
    async with uow:
        await admin_administrators.suspend_administrator(
            admin,
            admin_id,
            admins=uow.admins,
            roles=uow.admin_roles,
            privileges=uow.admin_privileges,
            security_events=uow.security_events,
            ip_prefix=_ip_prefix(request),
        )
        summary = await admin_administrators.get_administrator(
            admin,
            admin_id,
            admins=uow.admins,
            roles=uow.admin_roles,
            privileges=uow.admin_privileges,
            users=uow.users,
        )
        await uow.commit()
    return AdministratorRead.model_validate(administrator_payload(summary))


@router.post(
    "/administrators/{admin_id}/reactivate",
    response_model=AdministratorRead,
    summary="Reactivate a suspended administrator",
)
async def reactivate_administrator(
    admin_id: uuid.UUID,
    admin: Annotated[AdminContext, Depends(ManageAdmins)],
    uow: UnitOfWorkDep,
    request: Request,
) -> AdministratorRead:
    async with uow:
        await admin_administrators.reactivate_administrator(
            admin,
            admin_id,
            admins=uow.admins,
            roles=uow.admin_roles,
            privileges=uow.admin_privileges,
            security_events=uow.security_events,
            ip_prefix=_ip_prefix(request),
        )
        summary = await admin_administrators.get_administrator(
            admin,
            admin_id,
            admins=uow.admins,
            roles=uow.admin_roles,
            privileges=uow.admin_privileges,
            users=uow.users,
        )
        await uow.commit()
    return AdministratorRead.model_validate(administrator_payload(summary))


@router.post(
    "/administrators/{admin_id}/revoke",
    response_model=AdministratorRead,
    summary="Revoke an administrator",
)
async def revoke_administrator(
    admin_id: uuid.UUID,
    admin: Annotated[AdminContext, Depends(ManageAdmins)],
    uow: UnitOfWorkDep,
    request: Request,
) -> AdministratorRead:
    await admin_administrators.require_not_self(admin, admin_id)
    async with uow:
        await admin_administrators.revoke_administrator(
            admin,
            admin_id,
            admins=uow.admins,
            roles=uow.admin_roles,
            privileges=uow.admin_privileges,
            security_events=uow.security_events,
            ip_prefix=_ip_prefix(request),
        )
        summary = await admin_administrators.get_administrator(
            admin,
            admin_id,
            admins=uow.admins,
            roles=uow.admin_roles,
            privileges=uow.admin_privileges,
            users=uow.users,
        )
        await uow.commit()
    return AdministratorRead.model_validate(administrator_payload(summary))


@router.get(
    "/administrators/{admin_id}/roles",
    response_model=RoleList,
    summary="Roles held",
)
async def list_administrator_roles(
    admin_id: uuid.UUID,
    admin: Annotated[AdminContext, Depends(ReadAdmins)],
    uow: UnitOfWorkDep,
) -> RoleList:
    async with uow:
        names = await admin_roles.list_administrator_roles(
            admin, admin_id, admins=uow.admins, roles=uow.admin_roles
        )
        await uow.commit()
    return RoleList(items=names)


@router.put(
    "/administrators/{admin_id}/roles",
    response_model=RoleList,
    summary="Replace the roles an administrator holds",
    responses={403: {"model": ErrorResponse, "description": "Escalation refused."}},
)
async def set_administrator_roles(
    admin_id: uuid.UUID,
    payload: RolesUpdate,
    admin: Annotated[AdminContext, Depends(ManageAdmins)],
    uow: UnitOfWorkDep,
    request: Request,
) -> RoleList:
    async with uow:
        names = await admin_roles.set_administrator_roles(
            admin,
            admin_id,
            payload.roles,
            admins=uow.admins,
            roles=uow.admin_roles,
            security_events=uow.security_events,
            ip_prefix=_ip_prefix(request),
        )
        await uow.commit()
    return RoleList(items=names)


@router.get("/roles", response_model=RoleList, summary="The administrative role catalogue")
async def list_roles(admin: AdminDep, uow: UnitOfWorkDep) -> RoleList:
    async with uow:
        names = await admin_administrators.list_roles(admin, roles=uow.admin_roles)
        await uow.commit()
    return RoleList(items=names)


@router.get(
    "/privileges", response_model=PrivilegeList, summary="The administrative privilege catalogue"
)
async def list_privileges(admin: AdminDep, uow: UnitOfWorkDep) -> PrivilegeList:
    async with uow:
        names = await admin_administrators.list_privileges(admin, privileges=uow.admin_privileges)
        await uow.commit()
    return PrivilegeList(items=names)


@router.get(
    "/audit-events",
    response_model=AuditEventList,
    summary="Administrative audit history",
)
async def list_audit_events(
    admin: Annotated[AdminContext, Depends(ReadAudit)],
    uow: UnitOfWorkDep,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    event_type: str | None = Query(default=None, max_length=64),
) -> AuditEventList:
    async with uow:
        events = await admin_audit.list_administrative_events(
            admin,
            security_events=uow.security_events,
            limit=limit,
            offset=offset,
            event_type=event_type,
        )
        await uow.commit()
    return AuditEventList(
        items=[AuditEventRead.model_validate(audit_payload(event)) for event in events],
        meta=PageMeta(limit=limit, offset=offset, count=len(events)),
    )


def _ip_prefix(request: Request) -> str | None:
    client = request.client
    return client.host if client else None
