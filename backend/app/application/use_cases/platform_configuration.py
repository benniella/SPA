from __future__ import annotations

from dataclasses import dataclass

from app.application.admin_authz import AdminContext
from app.application.ports.configuration import PlatformSettingRepository
from app.application.ports.repositories import SecurityEventRepository
from app.core.errors import NotFoundError, PermissionDeniedError, ValidationError
from app.domain.admin.entities import AdminPrivilege
from app.domain.configuration.entities import ConfigSettingSpec
from app.domain.configuration.settings import (
    MAINTENANCE_ENABLED,
    get_spec,
    known_keys,
)
from app.domain.security.entities import SecurityEvent, SecurityEventType
from app.domain.shared import UserId


@dataclass(frozen=True, slots=True)
class SettingView:
    key: str
    type: str
    section: str
    value: object
    default: object
    description: str
    is_default: bool
    restart_required: bool
    privilege: str


@dataclass(frozen=True, slots=True)
class EffectiveConfiguration:
    values: dict[str, object]

    def bool(self, key: str) -> bool:
        return bool(self.values[key])

    def int(self, key: str) -> int:
        value = self.values[key]
        assert isinstance(value, int) and not isinstance(value, bool)
        return value

    def string(self, key: str) -> str:
        return str(self.values[key])

    def string_list(self, key: str) -> list[str]:
        value = self.values[key]
        assert isinstance(value, list)
        return [str(item) for item in value]


def _spec_or_raise(key: str) -> ConfigSettingSpec:
    spec = get_spec(key)
    if spec is None:
        raise NotFoundError(f"{key!r} is not a platform setting.")
    return spec


def _require(actor: AdminContext, privilege: str) -> None:
    if not actor.holds(privilege):
        raise PermissionDeniedError(f"Privilege {privilege} is required.")


def _view(spec: ConfigSettingSpec, stored: dict[str, object]) -> SettingView:
    present = spec.key in stored
    value = stored[spec.key] if present else spec.default
    return SettingView(
        key=spec.key,
        type=spec.type.value,
        section=spec.section.value,
        value=value,
        default=spec.default,
        description=spec.description,
        is_default=not present,
        restart_required=spec.restart_required,
        privilege=spec.privilege,
    )


async def read_configuration(
    actor: AdminContext,
    *,
    settings: PlatformSettingRepository,
    key: str | None = None,
) -> list[SettingView]:
    _require(actor, AdminPrivilege.CONFIGURATION_READ)
    stored = await settings.list()

    if key is not None:
        spec = _spec_or_raise(key)
        if not actor.holds(spec.privilege):
            raise PermissionDeniedError(f"Privilege {spec.privilege} is required.")
        return [_view(spec, stored)]

    return [
        _view(spec, stored)
        for spec in _settings_in_declaration_order()
        if actor.holds(spec.privilege)
    ]


def _settings_in_declaration_order() -> list[ConfigSettingSpec]:
    from app.domain.configuration.settings import SETTINGS

    return list(SETTINGS)


async def read_effective_configuration(
    *,
    settings: PlatformSettingRepository,
) -> EffectiveConfiguration:
    stored = await settings.list()
    values: dict[str, object] = {}
    for key in known_keys():
        spec = get_spec(key)
        assert spec is not None
        values[key] = stored.get(key, spec.default)
    return EffectiveConfiguration(values=values)


async def update_setting(
    actor: AdminContext,
    *,
    key: str,
    value: object,
    settings: PlatformSettingRepository,
    security_events: SecurityEventRepository,
    reason: str | None = None,
    ip_prefix: str | None = None,
) -> SettingView:
    spec = _spec_or_raise(key)
    _require(actor, spec.privilege)

    try:
        canonical = spec.coerce(value)
    except ValueError as exc:
        raise ValidationError(str(exc)) from exc

    stored = await settings.list()
    previous = stored.get(key, spec.default)
    if previous == canonical:
        return _view(spec, stored)

    await settings.set(key, canonical, changed_by=actor.admin.user_id)
    await security_events.add(
        _audit_event(
            _change_event_type(spec),
            actor=actor.admin.user_id,
            metadata={
                "setting": key,
                "previous": _audit_value(previous),
                "new": _audit_value(canonical),
                "reason": reason,
            },
            ip_prefix=ip_prefix,
        )
    )
    updated = dict(stored)
    updated[key] = canonical
    return _view(spec, updated)


async def reset_setting(
    actor: AdminContext,
    *,
    key: str,
    settings: PlatformSettingRepository,
    security_events: SecurityEventRepository,
    reason: str | None = None,
    ip_prefix: str | None = None,
) -> SettingView:
    spec = _spec_or_raise(key)
    _require(actor, spec.privilege)

    stored = await settings.list()
    previous = stored.get(key, spec.default)
    await settings.delete(key)
    await security_events.add(
        _audit_event(
            _reset_event_type(spec),
            actor=actor.admin.user_id,
            metadata={
                "setting": key,
                "previous": _audit_value(previous),
                "new": _audit_value(spec.default),
                "reason": reason,
            },
            ip_prefix=ip_prefix,
        )
    )
    remaining = {name: value for name, value in stored.items() if name != key}
    return _view(spec, remaining)


def _change_event_type(spec: ConfigSettingSpec) -> str:
    if spec.key == MAINTENANCE_ENABLED:
        return SecurityEventType.PLATFORM_MAINTENANCE_ENABLED
    if spec.section.value == "security":
        return SecurityEventType.PLATFORM_SECURITY_POLICY_CHANGED
    if spec.section.value == "rate_limits":
        return SecurityEventType.PLATFORM_RATE_LIMIT_POLICY_CHANGED
    return SecurityEventType.PLATFORM_CONFIGURATION_CHANGED


def _reset_event_type(spec: ConfigSettingSpec) -> str:
    if spec.key == MAINTENANCE_ENABLED:
        return SecurityEventType.PLATFORM_MAINTENANCE_DISABLED
    return SecurityEventType.PLATFORM_CONFIGURATION_RESET


def _audit_value(value: object) -> object:
    if isinstance(value, list):
        return ",".join(str(item) for item in value)
    return value


def _audit_event(
    event_type: str,
    *,
    actor: UserId | None,
    metadata: dict[str, object],
    ip_prefix: str | None,
) -> SecurityEvent:
    payload: dict[str, object] = {
        key: value
        for key, value in metadata.items()
        if value is None or isinstance(value, (str, int, float, bool))
    }
    return SecurityEvent(
        user_id=actor,
        event_type=str(SecurityEventType(event_type)),
        metadata=payload,
        ip_prefix=ip_prefix,
    )
