"""The configuration service: effective values, validation, and audit."""

from __future__ import annotations

import pytest

from app.application.admin_authz import AdminContext
from app.application.use_cases import network_policy, platform_configuration, rate_limit_admin
from app.core.errors import NotFoundError, PermissionDeniedError, ValidationError
from app.domain.admin.entities import AdminIdentity, AdminPrivilege, AdminStatus
from app.domain.configuration.settings import (
    COUNTRY_ALLOWLIST,
    COUNTRY_POLICY_MODE,
    MAINTENANCE_ENABLED,
    MAINTENANCE_MESSAGE,
    QUOTA_ORGANIZATION_MAX_TEAMS,
    RATE_LIMIT_LOGIN_PER_MINUTE,
)
from app.domain.security.entities import SecurityEventType
from app.domain.security.network import IpBlockKind
from app.domain.shared import UserId, new_id, utcnow
from tests.unit.application.fakes import (
    FakeIpBlockRepository,
    FakePlatformSettingRepository,
    FakeSecurityEventRepository,
)
from tests.unit.application.security_fakes import FakeRateLimiter


def _admin(*privileges: str) -> AdminContext:
    admin = AdminIdentity(
        user_id=UserId(new_id()),
        status=AdminStatus(AdminStatus.ACTIVE),
        mfa_enrolled_at=utcnow(),
    )
    return AdminContext(
        admin=admin,
        privileges=frozenset(privileges),
        is_superadmin=AdminPrivilege.CONFIGURATION_MANAGE in privileges
        and AdminPrivilege.SECURITY_MANAGE in privileges,
    )


def _reader() -> AdminContext:
    return _admin(
        AdminPrivilege.CONFIGURATION_READ,
        AdminPrivilege.CONFIGURATION_MANAGE,
        AdminPrivilege.SECURITY_READ,
        AdminPrivilege.SECURITY_MANAGE,
        AdminPrivilege.MAINTENANCE_READ,
        AdminPrivilege.MAINTENANCE_MANAGE,
    )


class TestReadConfiguration:
    async def test_defaults_are_returned_before_anything_is_stored(self) -> None:
        views = await platform_configuration.read_configuration(
            _reader(), settings=FakePlatformSettingRepository()
        )
        by_key = {view.key: view for view in views}
        assert by_key[MAINTENANCE_ENABLED].value is False
        assert by_key[MAINTENANCE_ENABLED].is_default is True

    async def test_only_settings_the_caller_may_read_are_returned(self) -> None:
        views = await platform_configuration.read_configuration(
            _admin(AdminPrivilege.CONFIGURATION_READ),
            settings=FakePlatformSettingRepository(),
        )
        assert all(view.privilege == AdminPrivilege.CONFIGURATION_MANAGE for view in views)

    async def test_a_caller_without_the_read_privilege_is_refused(self) -> None:
        with pytest.raises(PermissionDeniedError):
            await platform_configuration.read_configuration(
                _admin(), settings=FakePlatformSettingRepository()
            )

    async def test_reading_one_unknown_key_is_not_found(self) -> None:
        with pytest.raises(NotFoundError):
            await platform_configuration.read_configuration(
                _reader(), settings=FakePlatformSettingRepository(), key="nope"
            )

    async def test_reading_one_key_the_caller_may_not_read_is_refused(self) -> None:
        with pytest.raises(PermissionDeniedError):
            await platform_configuration.read_configuration(
                _admin(AdminPrivilege.CONFIGURATION_READ),
                settings=FakePlatformSettingRepository(),
                key=QUOTA_ORGANIZATION_MAX_TEAMS,
            )


class TestEffectiveConfiguration:
    async def test_stored_values_override_defaults(self) -> None:
        settings = FakePlatformSettingRepository()
        await settings.set(MAINTENANCE_ENABLED, True, changed_by=None)
        configuration = await platform_configuration.read_effective_configuration(settings=settings)
        assert configuration.bool(MAINTENANCE_ENABLED) is True

    async def test_every_declared_setting_resolves(self) -> None:
        configuration = await platform_configuration.read_effective_configuration(
            settings=FakePlatformSettingRepository()
        )
        assert configuration.int(RATE_LIMIT_LOGIN_PER_MINUTE) >= 1
        assert configuration.string(MAINTENANCE_MESSAGE) == ""


class TestUpdateSetting:
    async def test_a_valid_change_is_persisted_and_audited(self) -> None:
        settings = FakePlatformSettingRepository()
        events = FakeSecurityEventRepository()

        view = await platform_configuration.update_setting(
            _reader(),
            key=QUOTA_ORGANIZATION_MAX_TEAMS,
            value=250,
            settings=settings,
            security_events=events,
            reason="Raised for a large club.",
        )

        assert view.value == 250
        assert view.is_default is False
        assert await settings.get(QUOTA_ORGANIZATION_MAX_TEAMS) == 250
        assert len(events.events) == 1
        assert str(events.events[0].event_type) == SecurityEventType.PLATFORM_CONFIGURATION_CHANGED
        assert events.events[0].metadata["setting"] == QUOTA_ORGANIZATION_MAX_TEAMS
        assert events.events[0].metadata["previous"] == 100
        assert events.events[0].metadata["new"] == 250

    async def test_the_actor_is_recorded(self) -> None:
        settings = FakePlatformSettingRepository()
        events = FakeSecurityEventRepository()
        actor = _reader()

        await platform_configuration.update_setting(
            actor,
            key=QUOTA_ORGANIZATION_MAX_TEAMS,
            value=250,
            settings=settings,
            security_events=events,
        )

        assert settings.changed_by.get(QUOTA_ORGANIZATION_MAX_TEAMS) == actor.admin.user_id
        assert events.events[0].user_id == actor.admin.user_id

    async def test_an_invalid_type_is_rejected_and_not_persisted(self) -> None:
        settings = FakePlatformSettingRepository()
        events = FakeSecurityEventRepository()

        with pytest.raises(ValidationError):
            await platform_configuration.update_setting(
                _reader(),
                key=QUOTA_ORGANIZATION_MAX_TEAMS,
                value="many",
                settings=settings,
                security_events=events,
            )

        assert await settings.get(QUOTA_ORGANIZATION_MAX_TEAMS) is None
        assert events.events == []

    async def test_a_value_below_the_minimum_is_rejected(self) -> None:
        with pytest.raises(ValidationError):
            await platform_configuration.update_setting(
                _reader(),
                key=QUOTA_ORGANIZATION_MAX_TEAMS,
                value=0,
                settings=FakePlatformSettingRepository(),
                security_events=FakeSecurityEventRepository(),
            )

    async def test_an_invalid_enum_is_rejected(self) -> None:
        with pytest.raises(ValidationError):
            await platform_configuration.update_setting(
                _reader(),
                key=COUNTRY_POLICY_MODE,
                value="block-everything",
                settings=FakePlatformSettingRepository(),
                security_events=FakeSecurityEventRepository(),
            )

    async def test_an_unknown_setting_is_not_found(self) -> None:
        with pytest.raises(NotFoundError):
            await platform_configuration.update_setting(
                _reader(),
                key="database.password",
                value="hunter2",
                settings=FakePlatformSettingRepository(),
                security_events=FakeSecurityEventRepository(),
            )

    async def test_a_caller_without_the_settings_privilege_is_refused(self) -> None:
        settings = FakePlatformSettingRepository()
        with pytest.raises(PermissionDeniedError):
            await platform_configuration.update_setting(
                _admin(AdminPrivilege.CONFIGURATION_READ),
                key=QUOTA_ORGANIZATION_MAX_TEAMS,
                value=250,
                settings=settings,
                security_events=FakeSecurityEventRepository(),
            )
        assert await settings.get(QUOTA_ORGANIZATION_MAX_TEAMS) is None

    async def test_an_unchanged_value_records_no_audit_event(self) -> None:
        settings = FakePlatformSettingRepository()
        events = FakeSecurityEventRepository()

        await platform_configuration.update_setting(
            _reader(),
            key=QUOTA_ORGANIZATION_MAX_TEAMS,
            value=100,
            settings=settings,
            security_events=events,
        )

        assert events.events == []

    async def test_enabling_maintenance_uses_the_maintenance_event(self) -> None:
        events = FakeSecurityEventRepository()
        await platform_configuration.update_setting(
            _reader(),
            key=MAINTENANCE_ENABLED,
            value=True,
            settings=FakePlatformSettingRepository(),
            security_events=events,
        )
        assert str(events.events[0].event_type) == SecurityEventType.PLATFORM_MAINTENANCE_ENABLED


class TestResetSetting:
    async def test_reset_restores_the_default_and_audits(self) -> None:
        settings = FakePlatformSettingRepository()
        events = FakeSecurityEventRepository()
        await settings.set(QUOTA_ORGANIZATION_MAX_TEAMS, 250, changed_by=None)

        view = await platform_configuration.reset_setting(
            _reader(),
            key=QUOTA_ORGANIZATION_MAX_TEAMS,
            settings=settings,
            security_events=events,
        )

        assert view.value == 100
        assert view.is_default is True
        assert await settings.get(QUOTA_ORGANIZATION_MAX_TEAMS) is None
        assert str(events.events[0].event_type) == SecurityEventType.PLATFORM_CONFIGURATION_RESET

    async def test_resetting_maintenance_uses_the_disabled_event(self) -> None:
        settings = FakePlatformSettingRepository()
        events = FakeSecurityEventRepository()
        await settings.set(MAINTENANCE_ENABLED, True, changed_by=None)

        await platform_configuration.reset_setting(
            _reader(),
            key=MAINTENANCE_ENABLED,
            settings=settings,
            security_events=events,
        )

        assert str(events.events[0].event_type) == SecurityEventType.PLATFORM_MAINTENANCE_DISABLED


class TestCountryPolicy:
    def _configuration(self, **values: object) -> platform_configuration.EffectiveConfiguration:
        base = {COUNTRY_POLICY_MODE: "off", COUNTRY_ALLOWLIST: [], "security.country_denylist": []}
        base.update(values)
        return platform_configuration.EffectiveConfiguration(values=base)

    def test_off_permits_any_country(self) -> None:
        policy = network_policy.country_policy_of(self._configuration())
        assert policy.permits("GB")
        assert policy.permits(None)

    def test_allowlist_permits_only_listed_countries(self) -> None:
        policy = network_policy.country_policy_of(
            self._configuration(**{COUNTRY_POLICY_MODE: "allowlist", COUNTRY_ALLOWLIST: ["NG"]})
        )
        assert policy.permits("NG")
        assert not policy.permits("GB")

    def test_allowlist_refuses_an_unknown_country(self) -> None:
        policy = network_policy.country_policy_of(
            self._configuration(**{COUNTRY_POLICY_MODE: "allowlist", COUNTRY_ALLOWLIST: ["NG"]})
        )
        assert not policy.permits(None)

    def test_denylist_refuses_only_listed_countries(self) -> None:
        policy = network_policy.country_policy_of(
            self._configuration(
                **{COUNTRY_POLICY_MODE: "denylist", "security.country_denylist": ["KP"]}
            )
        )
        assert not policy.permits("KP")
        assert policy.permits("GB")

    def test_denylist_refuses_an_unknown_country(self) -> None:
        policy = network_policy.country_policy_of(
            self._configuration(
                **{COUNTRY_POLICY_MODE: "denylist", "security.country_denylist": ["KP"]}
            )
        )
        assert not policy.permits(None)

    async def test_setting_an_allowlist_without_countries_is_rejected(self) -> None:
        with pytest.raises(ValidationError):
            await network_policy.set_country_policy(
                _reader(),
                mode="allowlist",
                allowlist=[],
                denylist=None,
                update=FakePlatformSettingRepository(),
                security_events=FakeSecurityEventRepository(),
            )

    async def test_an_invalid_country_code_is_rejected(self) -> None:
        with pytest.raises(ValidationError):
            await network_policy.set_country_policy(
                _reader(),
                mode="allowlist",
                allowlist=["GBR"],
                denylist=None,
                update=FakePlatformSettingRepository(),
                security_events=FakeSecurityEventRepository(),
            )

    async def test_a_valid_policy_is_persisted_and_normalised(self) -> None:
        settings = FakePlatformSettingRepository()
        events = FakeSecurityEventRepository()

        await network_policy.set_country_policy(
            _reader(),
            mode="denylist",
            allowlist=None,
            denylist=["kp"],
            update=settings,
            security_events=events,
        )

        assert await settings.get(COUNTRY_POLICY_MODE) == "denylist"
        assert await settings.get("security.country_denylist") == ["KP"]
        assert len(events.events) == 2


class TestIpBlocks:
    async def test_a_valid_permanent_block_is_added_and_audited(self) -> None:
        blocks = FakeIpBlockRepository()
        events = FakeSecurityEventRepository()

        block = await network_policy.add_ip_block(
            _reader(),
            network="203.0.113.0/24",
            kind=IpBlockKind.PERMANENT,
            reason="Abuse",
            expires_at=None,
            blocks=blocks,
            security_events=events,
        )

        assert block.network == "203.0.113.0/24"
        assert block.created_by is not None
        assert len(await blocks.list_active()) == 1
        assert str(events.events[0].event_type) == SecurityEventType.PLATFORM_IP_BLOCK_ADDED

    async def test_a_temporary_block_requires_an_expiry(self) -> None:
        with pytest.raises(ValidationError):
            await network_policy.add_ip_block(
                _reader(),
                network="203.0.113.7",
                kind=IpBlockKind.TEMPORARY,
                reason="Probing",
                expires_at=None,
                blocks=FakeIpBlockRepository(),
                security_events=FakeSecurityEventRepository(),
            )

    async def test_an_invalid_network_is_rejected(self) -> None:
        with pytest.raises(ValidationError):
            await network_policy.add_ip_block(
                _reader(),
                network="999.1.1.1",
                kind=IpBlockKind.PERMANENT,
                reason="Abuse",
                expires_at=None,
                blocks=FakeIpBlockRepository(),
                security_events=FakeSecurityEventRepository(),
            )

    async def test_an_unknown_kind_is_rejected(self) -> None:
        with pytest.raises(ValidationError):
            await network_policy.add_ip_block(
                _reader(),
                network="203.0.113.7",
                kind="forever",
                reason="Abuse",
                expires_at=None,
                blocks=FakeIpBlockRepository(),
                security_events=FakeSecurityEventRepository(),
            )

    async def test_a_caller_without_the_security_privilege_is_refused(self) -> None:
        blocks = FakeIpBlockRepository()
        with pytest.raises(PermissionDeniedError):
            await network_policy.add_ip_block(
                _admin(AdminPrivilege.SECURITY_READ),
                network="203.0.113.7",
                kind=IpBlockKind.PERMANENT,
                reason="Abuse",
                expires_at=None,
                blocks=blocks,
                security_events=FakeSecurityEventRepository(),
            )
        assert await blocks.list_all() == []

    async def test_removing_a_block_audits_and_deactivates_it(self) -> None:
        blocks = FakeIpBlockRepository()
        events = FakeSecurityEventRepository()
        block = await network_policy.add_ip_block(
            _reader(),
            network="203.0.113.7",
            kind=IpBlockKind.PERMANENT,
            reason="Abuse",
            expires_at=None,
            blocks=blocks,
            security_events=events,
        )

        removed = await network_policy.remove_ip_block(
            _reader(), block_id=block.id, blocks=blocks, security_events=events
        )

        assert removed.is_removed
        assert await blocks.list_active() == []
        assert str(events.events[-1].event_type) == SecurityEventType.PLATFORM_IP_BLOCK_REMOVED

    async def test_removing_an_unknown_block_is_not_found(self) -> None:
        with pytest.raises(NotFoundError):
            await network_policy.remove_ip_block(
                _reader(),
                block_id=new_id(),
                blocks=FakeIpBlockRepository(),
                security_events=FakeSecurityEventRepository(),
            )


class TestRateLimitAdmin:
    async def test_a_reset_clears_the_key_and_audits(self) -> None:
        limiter = FakeRateLimiter()
        events = FakeSecurityEventRepository()
        await limiter.hit("ratelimit:login:203.0.113.0/24", limit=1, window_seconds=60)

        await rate_limit_admin.reset_rate_limit_state(
            _reader(),
            scope="login",
            identifier="203.0.113.0/24",
            limiter=limiter,
            security_events=events,
        )

        assert await limiter.peek("ratelimit:login:203.0.113.0/24") is None
        assert str(events.events[0].event_type) == SecurityEventType.PLATFORM_RATE_LIMIT_STATE_RESET

    async def test_an_unknown_scope_is_rejected(self) -> None:
        with pytest.raises(ValidationError):
            await rate_limit_admin.reset_rate_limit_state(
                _reader(),
                scope="everything",
                identifier="x",
                limiter=FakeRateLimiter(),
                security_events=FakeSecurityEventRepository(),
            )

    async def test_a_blank_identifier_is_rejected(self) -> None:
        with pytest.raises(ValidationError):
            await rate_limit_admin.reset_rate_limit_state(
                _reader(),
                scope="login",
                identifier="   ",
                limiter=FakeRateLimiter(),
                security_events=FakeSecurityEventRepository(),
            )

    async def test_a_caller_without_the_security_privilege_is_refused(self) -> None:
        limiter = FakeRateLimiter()
        with pytest.raises(PermissionDeniedError):
            await rate_limit_admin.reset_rate_limit_state(
                _admin(AdminPrivilege.SECURITY_READ),
                scope="login",
                identifier="x",
                limiter=limiter,
                security_events=FakeSecurityEventRepository(),
            )
        assert limiter.reset_calls == []

    async def test_reading_state_requires_only_the_read_privilege(self) -> None:
        limiter = FakeRateLimiter()
        await limiter.hit("ratelimit:login:x", limit=5, window_seconds=60)
        count = await rate_limit_admin.read_rate_limit_state(
            _admin(AdminPrivilege.SECURITY_READ),
            scope="login",
            identifier="x",
            limiter=limiter,
        )
        assert count == 1
