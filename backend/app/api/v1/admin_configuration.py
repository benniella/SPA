from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request

from app.api.admin_dependencies import AdminDep, require_privilege
from app.api.dependencies import RateLimiterDep, UnitOfWorkDep
from app.application.admin_authz import AdminContext
from app.application.use_cases import (
    network_policy,
    platform_configuration,
    rate_limit_admin,
)
from app.application.use_cases.platform_configuration import EffectiveConfiguration, SettingView
from app.domain.admin.entities import AdminPrivilege
from app.domain.configuration.settings import (
    MAINTENANCE_ENABLED,
    MAINTENANCE_MESSAGE,
    SUSPICIOUS_IP_FAILURE_THRESHOLD,
    SUSPICIOUS_IP_TRACKING_ENABLED,
    SUSPICIOUS_IP_WINDOW_MINUTES,
)
from app.domain.security.network import IpBlock
from app.schemas.common import ErrorResponse, PageMeta
from app.schemas.configuration import (
    CountryPolicyRead,
    CountryPolicyUpdate,
    IpBlockCreate,
    IpBlockList,
    IpBlockRead,
    MaintenanceStatus,
    RateLimitResetRequest,
    RateLimitResetResult,
    RateLimitStateRead,
    SettingList,
    SettingRead,
    SettingUpdate,
    SuspiciousIpPolicyRead,
)

router = APIRouter()

ReadConfiguration = require_privilege(AdminPrivilege.CONFIGURATION_READ)
ReadSecurity = require_privilege(AdminPrivilege.SECURITY_READ)


def _setting_payload(view: SettingView) -> dict[str, object]:
    return {
        "key": view.key,
        "type": view.type,
        "section": view.section,
        "value": view.value,
        "default": view.default,
        "description": view.description,
        "is_default": view.is_default,
        "restart_required": view.restart_required,
        "privilege": view.privilege,
    }


def _ip_block_payload(block: IpBlock) -> dict[str, object]:
    return {
        "id": block.id,
        "network": block.network,
        "kind": block.kind,
        "reason": block.reason,
        "created_by": block.created_by,
        "expires_at": block.expires_at,
        "removed_at": block.removed_at,
        "active": block.is_active(),
        "created_at": block.created_at,
    }


def _ip_prefix(request: Request) -> str | None:
    client = request.client
    return client.host if client else None


@router.get(
    "/configuration",
    response_model=SettingList,
    summary="Effective platform configuration",
)
async def read_configuration(
    admin: Annotated[AdminContext, Depends(ReadConfiguration)],
    uow: UnitOfWorkDep,
) -> SettingList:
    async with uow:
        views = await platform_configuration.read_configuration(
            admin, settings=uow.platform_settings
        )
        await uow.commit()
    return SettingList(items=[SettingRead.model_validate(_setting_payload(view)) for view in views])


@router.get(
    "/configuration/maintenance",
    response_model=MaintenanceStatus,
    summary="Current maintenance state",
)
async def read_maintenance(
    admin: Annotated[AdminContext, Depends(ReadConfiguration)],
    uow: UnitOfWorkDep,
) -> MaintenanceStatus:
    async with uow:
        configuration = await platform_configuration.read_effective_configuration(
            settings=uow.platform_settings
        )
        await uow.commit()
    return _maintenance_payload(configuration)


@router.get(
    "/configuration/country-policy",
    response_model=CountryPolicyRead,
    summary="Current country policy",
)
async def read_country_policy(
    admin: Annotated[AdminContext, Depends(ReadSecurity)],
    uow: UnitOfWorkDep,
) -> CountryPolicyRead:
    async with uow:
        configuration = await platform_configuration.read_effective_configuration(
            settings=uow.platform_settings
        )
        await uow.commit()
    policy = network_policy.country_policy_of(configuration)
    return CountryPolicyRead(
        mode=policy.mode, allowlist=sorted(policy.allowlist), denylist=sorted(policy.denylist)
    )


@router.put(
    "/configuration/country-policy",
    response_model=CountryPolicyRead,
    summary="Replace the country policy",
    responses={422: {"model": ErrorResponse, "description": "Invalid policy."}},
)
async def update_country_policy(
    payload: CountryPolicyUpdate,
    admin: Annotated[AdminContext, Depends(ReadSecurity)],
    uow: UnitOfWorkDep,
    request: Request,
) -> CountryPolicyRead:
    async with uow:
        await network_policy.set_country_policy(
            admin,
            mode=payload.mode,
            allowlist=payload.allowlist,
            denylist=payload.denylist,
            update=uow.platform_settings,
            security_events=uow.security_events,
            ip_prefix=_ip_prefix(request),
        )
        configuration = await platform_configuration.read_effective_configuration(
            settings=uow.platform_settings
        )
        await uow.commit()
    policy = network_policy.country_policy_of(configuration)
    return CountryPolicyRead(
        mode=policy.mode, allowlist=sorted(policy.allowlist), denylist=sorted(policy.denylist)
    )


@router.get(
    "/configuration/suspicious-policy",
    response_model=SuspiciousIpPolicyRead,
    summary="Suspicious-IP policy",
)
async def read_suspicious_policy(
    admin: Annotated[AdminContext, Depends(ReadSecurity)],
    uow: UnitOfWorkDep,
) -> SuspiciousIpPolicyRead:
    async with uow:
        configuration = await platform_configuration.read_effective_configuration(
            settings=uow.platform_settings
        )
        await uow.commit()
    return SuspiciousIpPolicyRead(
        enabled=configuration.bool(SUSPICIOUS_IP_TRACKING_ENABLED),
        failure_threshold=configuration.int(SUSPICIOUS_IP_FAILURE_THRESHOLD),
        window_minutes=configuration.int(SUSPICIOUS_IP_WINDOW_MINUTES),
    )


@router.get(
    "/configuration/{key}",
    response_model=SettingRead,
    summary="One platform setting",
    responses={404: {"model": ErrorResponse, "description": "Unknown setting."}},
)
async def read_setting(
    key: str,
    admin: Annotated[AdminContext, Depends(ReadConfiguration)],
    uow: UnitOfWorkDep,
) -> SettingRead:
    async with uow:
        views = await platform_configuration.read_configuration(
            admin, settings=uow.platform_settings, key=key
        )
        await uow.commit()
    return SettingRead.model_validate(_setting_payload(views[0]))


@router.put(
    "/configuration/{key}",
    response_model=SettingRead,
    summary="Change a platform setting",
    responses={
        404: {"model": ErrorResponse, "description": "Unknown setting."},
        422: {"model": ErrorResponse, "description": "Invalid value for this setting."},
    },
)
async def update_setting(
    key: str,
    payload: SettingUpdate,
    admin: AdminDep,
    uow: UnitOfWorkDep,
    request: Request,
) -> SettingRead:
    async with uow:
        view = await platform_configuration.update_setting(
            admin,
            key=key,
            value=payload.value,
            settings=uow.platform_settings,
            security_events=uow.security_events,
            reason=payload.reason,
            ip_prefix=_ip_prefix(request),
        )
        await uow.commit()
    return SettingRead.model_validate(_setting_payload(view))


@router.post(
    "/configuration/{key}/reset",
    response_model=SettingRead,
    summary="Reset a platform setting to its default",
    responses={404: {"model": ErrorResponse, "description": "Unknown setting."}},
)
async def reset_setting(
    key: str,
    admin: AdminDep,
    uow: UnitOfWorkDep,
    request: Request,
    reason: str | None = Query(default=None, max_length=500),
) -> SettingRead:
    async with uow:
        view = await platform_configuration.reset_setting(
            admin,
            key=key,
            settings=uow.platform_settings,
            security_events=uow.security_events,
            reason=reason,
            ip_prefix=_ip_prefix(request),
        )
        await uow.commit()
    return SettingRead.model_validate(_setting_payload(view))


@router.get(
    "/ip-blocks",
    response_model=IpBlockList,
    summary="List IP blocks",
)
async def list_ip_blocks(
    admin: Annotated[AdminContext, Depends(ReadSecurity)],
    uow: UnitOfWorkDep,
    active_only: bool = Query(default=False),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> IpBlockList:
    async with uow:
        blocks = await network_policy.list_ip_blocks(
            admin, blocks=uow.ip_blocks, active_only=active_only
        )
        await uow.commit()
    page = blocks[offset : offset + limit]
    return IpBlockList(
        items=[IpBlockRead.model_validate(_ip_block_payload(block)) for block in page],
        meta=PageMeta(limit=limit, offset=offset, count=len(blocks)),
    )


@router.post(
    "/ip-blocks",
    response_model=IpBlockRead,
    status_code=201,
    summary="Add an IP block",
    responses={422: {"model": ErrorResponse, "description": "Invalid address or expiry."}},
)
async def add_ip_block(
    payload: IpBlockCreate,
    admin: Annotated[AdminContext, Depends(ReadSecurity)],
    uow: UnitOfWorkDep,
    request: Request,
) -> IpBlockRead:
    async with uow:
        block = await network_policy.add_ip_block(
            admin,
            network=payload.network,
            kind=payload.kind,
            reason=payload.reason,
            expires_at=payload.expires_at,
            blocks=uow.ip_blocks,
            security_events=uow.security_events,
            ip_prefix=_ip_prefix(request),
        )
        await uow.commit()
    return IpBlockRead.model_validate(_ip_block_payload(block))


@router.delete(
    "/ip-blocks/{block_id}",
    response_model=IpBlockRead,
    summary="Remove an IP block",
    responses={404: {"model": ErrorResponse, "description": "Unknown block."}},
)
async def remove_ip_block(
    block_id: uuid.UUID,
    admin: Annotated[AdminContext, Depends(ReadSecurity)],
    uow: UnitOfWorkDep,
    request: Request,
) -> IpBlockRead:
    async with uow:
        block = await network_policy.remove_ip_block(
            admin,
            block_id=block_id,
            blocks=uow.ip_blocks,
            security_events=uow.security_events,
            ip_prefix=_ip_prefix(request),
        )
        await uow.commit()
    return IpBlockRead.model_validate(_ip_block_payload(block))


@router.get(
    "/rate-limits/state",
    response_model=RateLimitStateRead,
    summary="Current count for a rate-limit key",
)
async def read_rate_limit_state(
    admin: Annotated[AdminContext, Depends(ReadSecurity)],
    limiter: RateLimiterDep,
    scope: str = Query(min_length=1, max_length=64),
    identifier: str = Query(min_length=1, max_length=320),
) -> RateLimitStateRead:
    count = await rate_limit_admin.read_rate_limit_state(
        admin, scope=scope, identifier=identifier, limiter=limiter
    )
    return RateLimitStateRead(scope=scope, identifier=identifier.strip(), count=count)


@router.post(
    "/rate-limits/reset",
    response_model=RateLimitResetResult,
    summary="Reset a rate-limit key",
    responses={422: {"model": ErrorResponse, "description": "Unknown scope."}},
)
async def reset_rate_limit(
    payload: RateLimitResetRequest,
    admin: Annotated[AdminContext, Depends(ReadSecurity)],
    uow: UnitOfWorkDep,
    limiter: RateLimiterDep,
    request: Request,
) -> RateLimitResetResult:
    async with uow:
        reset = await rate_limit_admin.reset_rate_limit_state(
            admin,
            scope=payload.scope,
            identifier=payload.identifier,
            limiter=limiter,
            security_events=uow.security_events,
            ip_prefix=_ip_prefix(request),
        )
        await uow.commit()
    return RateLimitResetResult(scope=reset.scope, identifier=reset.identifier)


def _maintenance_payload(configuration: EffectiveConfiguration) -> MaintenanceStatus:
    return MaintenanceStatus(
        enabled=configuration.bool(MAINTENANCE_ENABLED),
        message=configuration.string(MAINTENANCE_MESSAGE),
    )
