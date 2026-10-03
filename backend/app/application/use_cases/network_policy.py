from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from app.application.admin_authz import AdminContext
from app.application.ports.configuration import IpBlockRepository, PlatformSettingRepository
from app.application.ports.repositories import SecurityEventRepository
from app.application.use_cases.platform_configuration import EffectiveConfiguration
from app.core.errors import NotFoundError, PermissionDeniedError, ValidationError
from app.domain.admin.entities import AdminPrivilege
from app.domain.configuration.settings import (
    COUNTRY_ALLOWLIST,
    COUNTRY_DENYLIST,
    COUNTRY_POLICY_MODE,
)
from app.domain.security.entities import SecurityEvent, SecurityEventType
from app.domain.security.network import (
    IpBlock,
    IpBlockKind,
    normalise_country_code,
    parse_network,
)


@dataclass(frozen=True, slots=True)
class CountryPolicy:
    mode: str
    allowlist: frozenset[str]
    denylist: frozenset[str]

    @property
    def enforced(self) -> bool:
        return self.mode != "off"

    def permits(self, country: str | None) -> bool:
        if self.mode == "off":
            return True
        if country is None:
            return False
        code = country.strip().upper()
        if self.mode == "allowlist":
            return code in self.allowlist
        if self.mode == "denylist":
            return code not in self.denylist
        return True


def country_policy_of(configuration: EffectiveConfiguration) -> CountryPolicy:
    return CountryPolicy(
        mode=configuration.string(COUNTRY_POLICY_MODE),
        allowlist=frozenset(configuration.string_list(COUNTRY_ALLOWLIST)),
        denylist=frozenset(configuration.string_list(COUNTRY_DENYLIST)),
    )


def _require(actor: AdminContext, privilege: str) -> None:
    if not actor.holds(privilege):
        raise PermissionDeniedError(f"Privilege {privilege} is required.")


async def list_ip_blocks(
    actor: AdminContext,
    *,
    blocks: IpBlockRepository,
    active_only: bool = False,
) -> list[IpBlock]:
    _require(actor, AdminPrivilege.SECURITY_READ)
    return await blocks.list_active() if active_only else await blocks.list_all()


async def add_ip_block(
    actor: AdminContext,
    *,
    network: str,
    kind: str,
    reason: str,
    expires_at: datetime | None,
    blocks: IpBlockRepository,
    security_events: SecurityEventRepository,
    ip_prefix: str | None = None,
) -> IpBlock:
    _require(actor, AdminPrivilege.SECURITY_MANAGE)

    try:
        canonical = parse_network(network)
    except ValueError as exc:
        raise ValidationError(str(exc)) from exc

    if kind not in IpBlockKind.ALLOWED:
        raise ValidationError(f"Unknown IP block kind: {kind!r}.")

    try:
        block = IpBlock(
            network=canonical,
            kind=kind,
            reason=reason,
            created_by=actor.admin.user_id,
            expires_at=expires_at,
        )
    except ValueError as exc:
        raise ValidationError(str(exc)) from exc

    await blocks.add(block)
    await security_events.add(
        _event(
            SecurityEventType.PLATFORM_IP_BLOCK_ADDED,
            actor=actor,
            metadata={
                "network": block.network,
                "kind": block.kind,
                "expires_at": block.expires_at.isoformat() if block.expires_at else None,
                "reason": block.reason,
            },
            ip_prefix=ip_prefix,
        )
    )
    return block


async def remove_ip_block(
    actor: AdminContext,
    *,
    block_id: object,
    blocks: IpBlockRepository,
    security_events: SecurityEventRepository,
    ip_prefix: str | None = None,
) -> IpBlock:
    _require(actor, AdminPrivilege.SECURITY_MANAGE)

    block = await blocks.get(block_id)
    if block is None:
        raise NotFoundError("That IP block does not exist.")

    block.remove()
    await blocks.update(block)
    await security_events.add(
        _event(
            SecurityEventType.PLATFORM_IP_BLOCK_REMOVED,
            actor=actor,
            metadata={"network": block.network},
            ip_prefix=ip_prefix,
        )
    )
    return block


async def set_country_policy(
    actor: AdminContext,
    *,
    mode: str,
    allowlist: list[str] | None,
    denylist: list[str] | None,
    update: PlatformSettingRepository,
    security_events: SecurityEventRepository,
    ip_prefix: str | None = None,
) -> None:
    _require(actor, AdminPrivilege.SECURITY_MANAGE)

    try:
        normalised_allow = [normalise_country_code(code) for code in (allowlist or [])]
        normalised_deny = [normalise_country_code(code) for code in (denylist or [])]
    except ValueError as exc:
        raise ValidationError(str(exc)) from exc

    if mode not in {"off", "allowlist", "denylist"}:
        raise ValidationError(f"Unknown country policy mode: {mode!r}.")
    if mode == "allowlist" and not normalised_allow:
        raise ValidationError("An allowlist policy requires at least one country.")
    if mode == "denylist" and not normalised_deny:
        raise ValidationError("A denylist policy requires at least one country.")

    from app.application.use_cases import platform_configuration

    await platform_configuration.update_setting(
        actor,
        key=COUNTRY_POLICY_MODE,
        value=mode,
        settings=update,
        security_events=security_events,
        ip_prefix=ip_prefix,
    )
    if allowlist is not None:
        await platform_configuration.update_setting(
            actor,
            key=COUNTRY_ALLOWLIST,
            value=normalised_allow,
            settings=update,
            security_events=security_events,
            ip_prefix=ip_prefix,
        )
    if denylist is not None:
        await platform_configuration.update_setting(
            actor,
            key=COUNTRY_DENYLIST,
            value=normalised_deny,
            settings=update,
            security_events=security_events,
            ip_prefix=ip_prefix,
        )


def _event(
    event_type: str,
    *,
    actor: AdminContext,
    metadata: dict[str, object],
    ip_prefix: str | None,
) -> SecurityEvent:
    payload: dict[str, object] = {
        key: value
        for key, value in metadata.items()
        if value is None or isinstance(value, (str, int, float, bool))
    }
    return SecurityEvent(
        user_id=actor.admin.user_id,
        event_type=str(SecurityEventType(event_type)),
        metadata=payload,
        ip_prefix=ip_prefix,
    )
