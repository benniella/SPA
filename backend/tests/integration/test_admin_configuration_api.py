"""The configuration and security-control API boundary.

Sessions are minted directly, exactly as 'test_admin_api.py' does: this suite
exercises configuration authorization, validation, persistence and audit, not
Phase 9 credential handling.
"""

from __future__ import annotations

import uuid
from datetime import timedelta

import pytest
from httpx import AsyncClient

from app.domain.security.tokens import hash_token
from app.domain.shared import utcnow

pytestmark = [pytest.mark.integration, pytest.mark.usefixtures("clean_database")]

TOKEN = "configuration-session-token"


async def _settings():
    from app.core.config import get_settings

    return get_settings()


async def _make_user(*, email: str | None = None) -> uuid.UUID:
    from app.core.config import get_settings
    from app.infrastructure.database.engine import get_session_factory
    from app.infrastructure.database.models import UserModel

    user_id = uuid.uuid4()
    session_factory = get_session_factory(get_settings())
    async with session_factory() as session:
        session.add(
            UserModel(
                id=user_id,
                email=email or f"{user_id}@example.com",
                display_name="Admin",
                is_active=True,
            )
        )
        await session.commit()
    return user_id


async def _make_session(user_id: uuid.UUID, *, mfa_verified: bool = True) -> str:
    from app.core.config import get_settings
    from app.infrastructure.database.engine import get_session_factory
    from app.infrastructure.database.models import SessionModel

    settings = get_settings()
    token = f"{TOKEN}-{uuid.uuid4()}"
    session_factory = get_session_factory(settings)
    async with session_factory() as session:
        session.add(
            SessionModel(
                id=uuid.uuid4(),
                user_id=user_id,
                token_hash=hash_token(token, secret=settings.session_secret),
                expires_at=utcnow() + timedelta(hours=1),
                last_used_at=utcnow(),
                mfa_verified_at=utcnow() if mfa_verified else None,
            )
        )
        await session.commit()
    return token


async def _assign_roles(user_id: uuid.UUID, roles: tuple[str, ...]) -> uuid.UUID:
    from sqlalchemy import text

    from app.core.config import get_settings
    from app.infrastructure.database.engine import get_session_factory

    admin_id = uuid.uuid4()
    session_factory = get_session_factory(get_settings())
    async with session_factory() as session:
        await session.execute(
            text(
                "INSERT INTO platform_admins (id, user_id, status, mfa_enrolled_at) "
                "VALUES (:id, :user_id, 'active', now())"
            ),
            {"id": admin_id, "user_id": user_id},
        )
        for role in roles:
            await session.execute(
                text(
                    "INSERT INTO admin_role_assignments (id, admin_id, role_id) "
                    "SELECT :id, a.id, r.id FROM platform_admins a, admin_roles r "
                    "WHERE a.user_id = :user_id AND r.name = :role"
                ),
                {"id": uuid.uuid4(), "user_id": user_id, "role": role},
            )
        await session.commit()
    return admin_id


async def _make_admin(
    *, roles: tuple[str, ...], mfa_verified: bool = True
) -> tuple[uuid.UUID, str]:
    user_id = await _make_user()
    admin_id = await _assign_roles(user_id, roles)
    token = await _make_session(user_id, mfa_verified=mfa_verified)
    return admin_id, token


def _cookie(token: str) -> dict[str, str]:
    return {"Cookie": f"spa_session={token}"}


@pytest.fixture(autouse=True)
async def catalogue(clean_database: None) -> None:
    """The catalogue is seeded by 'clean_database' after every truncate."""


class TestAuthorization:
    async def test_unauthenticated_read_is_refused(self, client: AsyncClient) -> None:
        response = await client.get("/api/v1/admin/configuration")
        assert response.status_code == 401

    async def test_an_ordinary_user_is_refused(self, client: AsyncClient) -> None:
        user_id = await _make_user()
        token = await _make_session(user_id)
        response = await client.get("/api/v1/admin/configuration", headers=_cookie(token))
        assert response.status_code == 403

    async def test_an_admin_without_mfa_assurance_is_refused(self, client: AsyncClient) -> None:
        _, token = await _make_admin(roles=("superadmin",), mfa_verified=False)
        response = await client.get("/api/v1/admin/configuration", headers=_cookie(token))
        assert response.status_code == 401

    async def test_a_normal_admin_cannot_read_configuration(self, client: AsyncClient) -> None:
        _, token = await _make_admin(roles=("support_admin",))
        response = await client.get("/api/v1/admin/configuration", headers=_cookie(token))
        assert response.status_code == 403

    async def test_a_normal_admin_cannot_change_configuration(self, client: AsyncClient) -> None:
        _, token = await _make_admin(roles=("support_admin",))
        response = await client.put(
            "/api/v1/admin/configuration/security.country_policy_mode",
            json={"value": "denylist"},
            headers=_cookie(token),
        )
        assert response.status_code == 403

    async def test_a_maintenance_admin_cannot_change_security_settings(
        self, client: AsyncClient
    ) -> None:
        _, token = await _make_admin(roles=("maintenance_admin",))
        response = await client.put(
            "/api/v1/admin/configuration/security.country_policy_mode",
            json={"value": "denylist"},
            headers=_cookie(token),
        )
        assert response.status_code == 403


class TestConfigurationRead:
    async def test_superadmin_reads_the_effective_configuration(self, client: AsyncClient) -> None:
        _, token = await _make_admin(roles=("superadmin",))
        response = await client.get("/api/v1/admin/configuration", headers=_cookie(token))
        assert response.status_code == 200
        keys = {item["key"] for item in response.json()["items"]}
        assert "maintenance.enabled" in keys
        assert "rate_limits.login_per_minute" in keys

    async def test_defaults_are_reported_as_defaults(self, client: AsyncClient) -> None:
        _, token = await _make_admin(roles=("superadmin",))
        response = await client.get(
            "/api/v1/admin/configuration/maintenance.enabled", headers=_cookie(token)
        )
        assert response.status_code == 200
        body = response.json()
        assert body["value"] is False
        assert body["is_default"] is True

    async def test_an_unknown_setting_is_not_found(self, client: AsyncClient) -> None:
        _, token = await _make_admin(roles=("superadmin",))
        response = await client.get(
            "/api/v1/admin/configuration/database.password", headers=_cookie(token)
        )
        assert response.status_code == 404


class TestConfigurationMutation:
    async def test_a_valid_change_is_persisted_and_returned(self, client: AsyncClient) -> None:
        _, token = await _make_admin(roles=("superadmin",))
        headers = _cookie(token)

        response = await client.put(
            "/api/v1/admin/configuration/quotas.organization_max_teams",
            json={"value": 250, "reason": "Large club."},
            headers=headers,
        )

        assert response.status_code == 200
        assert response.json()["value"] == 250
        assert response.json()["is_default"] is False

        reread = await client.get(
            "/api/v1/admin/configuration/quotas.organization_max_teams", headers=headers
        )
        assert reread.json()["value"] == 250

    async def test_an_invalid_type_is_rejected(self, client: AsyncClient) -> None:
        _, token = await _make_admin(roles=("superadmin",))
        response = await client.put(
            "/api/v1/admin/configuration/quotas.organization_max_teams",
            json={"value": "many"},
            headers=_cookie(token),
        )
        assert response.status_code == 422

    async def test_an_out_of_range_value_is_rejected(self, client: AsyncClient) -> None:
        _, token = await _make_admin(roles=("superadmin",))
        response = await client.put(
            "/api/v1/admin/configuration/quotas.organization_max_teams",
            json={"value": 0},
            headers=_cookie(token),
        )
        assert response.status_code == 422

    async def test_an_invalid_enum_is_rejected(self, client: AsyncClient) -> None:
        _, token = await _make_admin(roles=("superadmin",))
        response = await client.put(
            "/api/v1/admin/configuration/security.country_policy_mode",
            json={"value": "block-everything"},
            headers=_cookie(token),
        )
        assert response.status_code == 422

    async def test_an_unknown_setting_is_not_found(self, client: AsyncClient) -> None:
        _, token = await _make_admin(roles=("superadmin",))
        response = await client.put(
            "/api/v1/admin/configuration/database.password",
            json={"value": "hunter2"},
            headers=_cookie(token),
        )
        assert response.status_code == 404

    async def test_reset_restores_the_default(self, client: AsyncClient) -> None:
        _, token = await _make_admin(roles=("superadmin",))
        headers = _cookie(token)
        await client.put(
            "/api/v1/admin/configuration/quotas.organization_max_teams",
            json={"value": 250},
            headers=headers,
        )

        response = await client.post(
            "/api/v1/admin/configuration/quotas.organization_max_teams/reset",
            headers=headers,
        )

        assert response.status_code == 200
        assert response.json()["is_default"] is True
        assert response.json()["value"] == 100


class TestMaintenance:
    async def test_maintenance_off_leaves_the_application_available(
        self, client: AsyncClient
    ) -> None:
        response = await client.get("/api/v1/health")
        assert response.status_code == 200

    async def test_maintenance_on_refuses_ordinary_traffic(self, client: AsyncClient) -> None:
        _, token = await _make_admin(roles=("superadmin",))
        enabled = await client.put(
            "/api/v1/admin/configuration/maintenance.enabled",
            json={"value": True},
            headers=_cookie(token),
        )
        assert enabled.status_code == 200

        refused = await client.get("/api/v1/videos")
        assert refused.status_code == 503
        assert refused.json()["error"]["code"] == "maintenance"

    async def test_maintenance_on_keeps_health_available(self, client: AsyncClient) -> None:
        _, token = await _make_admin(roles=("superadmin",))
        await client.put(
            "/api/v1/admin/configuration/maintenance.enabled",
            json={"value": True},
            headers=_cookie(token),
        )

        healthy = await client.get("/api/v1/health")
        ready = await client.get("/api/v1/health/ready")
        assert healthy.status_code == 200
        assert ready.status_code == 200

    async def test_maintenance_on_does_not_lock_out_the_control_plane(
        self, client: AsyncClient
    ) -> None:
        _, token = await _make_admin(roles=("superadmin",))
        headers = _cookie(token)
        await client.put(
            "/api/v1/admin/configuration/maintenance.enabled",
            json={"value": True},
            headers=headers,
        )

        status = await client.get("/api/v1/admin/configuration/maintenance", headers=headers)
        assert status.status_code == 200
        assert status.json()["enabled"] is True

        disabled = await client.put(
            "/api/v1/admin/configuration/maintenance.enabled",
            json={"value": False},
            headers=headers,
        )
        assert disabled.status_code == 200

    async def test_a_maintenance_message_is_returned(self, client: AsyncClient) -> None:
        _, token = await _make_admin(roles=("superadmin",))
        headers = _cookie(token)
        await client.put(
            "/api/v1/admin/configuration/maintenance.enabled",
            json={"value": True},
            headers=headers,
        )
        await client.put(
            "/api/v1/admin/configuration/maintenance.message",
            json={"value": "Back at 18:00 UTC."},
            headers=headers,
        )

        refused = await client.get("/api/v1/videos")
        assert refused.json()["error"]["message"] == "Back at 18:00 UTC."


class TestCountryPolicy:
    async def test_the_default_policy_is_off(self, client: AsyncClient) -> None:
        _, token = await _make_admin(roles=("superadmin",))
        response = await client.get(
            "/api/v1/admin/configuration/country-policy", headers=_cookie(token)
        )
        assert response.status_code == 200
        assert response.json()["mode"] == "off"

    async def test_an_allowlist_policy_is_persisted_and_normalised(
        self, client: AsyncClient
    ) -> None:
        _, token = await _make_admin(roles=("superadmin",))
        headers = _cookie(token)

        response = await client.put(
            "/api/v1/admin/configuration/country-policy",
            json={"mode": "allowlist", "allowlist": ["ng", "gb"]},
            headers=headers,
        )

        assert response.status_code == 200
        assert response.json()["mode"] == "allowlist"
        assert response.json()["allowlist"] == ["GB", "NG"]

    async def test_an_invalid_country_code_is_rejected(self, client: AsyncClient) -> None:
        _, token = await _make_admin(roles=("superadmin",))
        response = await client.put(
            "/api/v1/admin/configuration/country-policy",
            json={"mode": "denylist", "denylist": ["GBR"]},
            headers=_cookie(token),
        )
        assert response.status_code == 422

    async def test_an_allowlist_without_countries_is_rejected(self, client: AsyncClient) -> None:
        _, token = await _make_admin(roles=("superadmin",))
        response = await client.put(
            "/api/v1/admin/configuration/country-policy",
            json={"mode": "allowlist", "allowlist": []},
            headers=_cookie(token),
        )
        assert response.status_code == 422


class TestIpBlocks:
    async def test_a_block_can_be_added_listed_and_removed(self, client: AsyncClient) -> None:
        _, token = await _make_admin(roles=("superadmin",))
        headers = _cookie(token)

        created = await client.post(
            "/api/v1/admin/ip-blocks",
            json={"network": "203.0.113.0/24", "kind": "permanent", "reason": "Abuse"},
            headers=headers,
        )
        assert created.status_code == 201
        block = created.json()
        assert block["network"] == "203.0.113.0/24"
        assert block["active"] is True

        listing = await client.get("/api/v1/admin/ip-blocks", headers=headers)
        assert listing.status_code == 200
        assert listing.json()["meta"]["count"] == 1

        removed = await client.delete(f"/api/v1/admin/ip-blocks/{block['id']}", headers=headers)
        assert removed.status_code == 200
        assert removed.json()["active"] is False

        active = await client.get("/api/v1/admin/ip-blocks?active_only=true", headers=headers)
        assert active.json()["meta"]["count"] == 0

    async def test_a_cidr_is_canonicalised(self, client: AsyncClient) -> None:
        _, token = await _make_admin(roles=("superadmin",))
        created = await client.post(
            "/api/v1/admin/ip-blocks",
            json={"network": "10.0.0.5/24", "kind": "permanent", "reason": "Abuse"},
            headers=_cookie(token),
        )
        assert created.json()["network"] == "10.0.0.0/24"

    async def test_an_invalid_address_is_rejected(self, client: AsyncClient) -> None:
        _, token = await _make_admin(roles=("superadmin",))
        response = await client.post(
            "/api/v1/admin/ip-blocks",
            json={"network": "999.1.1.1", "kind": "permanent", "reason": "Abuse"},
            headers=_cookie(token),
        )
        assert response.status_code == 422

    async def test_a_temporary_block_requires_an_expiry(self, client: AsyncClient) -> None:
        _, token = await _make_admin(roles=("superadmin",))
        response = await client.post(
            "/api/v1/admin/ip-blocks",
            json={"network": "203.0.113.7", "kind": "temporary", "reason": "Probing"},
            headers=_cookie(token),
        )
        assert response.status_code == 422

    async def test_a_temporary_block_with_an_expiry_is_accepted(self, client: AsyncClient) -> None:
        _, token = await _make_admin(roles=("superadmin",))
        expires = (utcnow() + timedelta(hours=1)).isoformat()
        response = await client.post(
            "/api/v1/admin/ip-blocks",
            json={
                "network": "203.0.113.7",
                "kind": "temporary",
                "reason": "Probing",
                "expires_at": expires,
            },
            headers=_cookie(token),
        )
        assert response.status_code == 201
        assert response.json()["expires_at"] is not None

    async def test_a_normal_admin_cannot_add_a_block(self, client: AsyncClient) -> None:
        _, token = await _make_admin(roles=("support_admin",))
        response = await client.post(
            "/api/v1/admin/ip-blocks",
            json={"network": "203.0.113.7", "kind": "permanent", "reason": "Abuse"},
            headers=_cookie(token),
        )
        assert response.status_code == 403

    async def test_removing_an_unknown_block_is_not_found(self, client: AsyncClient) -> None:
        _, token = await _make_admin(roles=("superadmin",))
        response = await client.delete(
            f"/api/v1/admin/ip-blocks/{uuid.uuid4()}", headers=_cookie(token)
        )
        assert response.status_code == 404


class TestRateLimitAdmin:
    async def test_state_can_be_read_and_reset(self, client: AsyncClient) -> None:
        _, token = await _make_admin(roles=("superadmin",))
        headers = _cookie(token)

        state = await client.get(
            "/api/v1/admin/rate-limits/state?scope=login&identifier=203.0.113.0",
            headers=headers,
        )
        assert state.status_code == 200
        assert state.json()["scope"] == "login"

        reset = await client.post(
            "/api/v1/admin/rate-limits/reset",
            json={"scope": "login", "identifier": "203.0.113.0"},
            headers=headers,
        )
        assert reset.status_code == 200
        assert reset.json()["identifier"] == "203.0.113.0"

    async def test_an_unknown_scope_is_rejected(self, client: AsyncClient) -> None:
        _, token = await _make_admin(roles=("superadmin",))
        response = await client.post(
            "/api/v1/admin/rate-limits/reset",
            json={"scope": "everything", "identifier": "x"},
            headers=_cookie(token),
        )
        assert response.status_code == 422

    async def test_a_maintenance_admin_cannot_reset_rate_limits(
        self, client: AsyncClient
    ) -> None:
        _, token = await _make_admin(roles=("maintenance_admin",))
        response = await client.post(
            "/api/v1/admin/rate-limits/reset",
            json={"scope": "login", "identifier": "x"},
            headers=_cookie(token),
        )
        assert response.status_code == 403


class TestAudit:
    async def test_a_configuration_change_is_audited(self, client: AsyncClient) -> None:
        user_id = await _make_user()
        await _assign_roles(user_id, ("superadmin",))
        token = await _make_session(user_id)
        headers = _cookie(token)

        await client.put(
            "/api/v1/admin/configuration/quotas.organization_max_teams",
            json={"value": 250, "reason": "Large club."},
            headers=headers,
        )

        audit = await client.get("/api/v1/admin/audit-events", headers=headers)
        assert audit.status_code == 200
        events = audit.json()["items"]
        change = next(e for e in events if e["event_type"] == "PLATFORM_CONFIGURATION_CHANGED")
        assert change["actor_id"] == str(user_id)
        assert change["metadata"]["setting"] == "quotas.organization_max_teams"
        assert change["metadata"]["new"] == 250
        assert change["metadata"]["reason"] == "Large club."

    async def test_an_ip_block_is_audited(self, client: AsyncClient) -> None:
        user_id = await _make_user()
        await _assign_roles(user_id, ("superadmin",))
        headers = _cookie(await _make_session(user_id))

        await client.post(
            "/api/v1/admin/ip-blocks",
            json={"network": "203.0.113.0/24", "kind": "permanent", "reason": "Abuse"},
            headers=headers,
        )

        audit = await client.get("/api/v1/admin/audit-events", headers=headers)
        types = {event["event_type"] for event in audit.json()["items"]}
        assert "PLATFORM_IP_BLOCK_ADDED" in types

    async def test_a_reset_is_audited(self, client: AsyncClient) -> None:
        user_id = await _make_user()
        await _assign_roles(user_id, ("superadmin",))
        headers = _cookie(await _make_session(user_id))

        await client.post(
            "/api/v1/admin/configuration/quotas.organization_max_teams/reset",
            headers=headers,
        )

        audit = await client.get("/api/v1/admin/audit-events", headers=headers)
        types = {event["event_type"] for event in audit.json()["items"]}
        assert "PLATFORM_CONFIGURATION_RESET" in types

    async def test_a_maintenance_toggle_is_audited(self, client: AsyncClient) -> None:
        user_id = await _make_user()
        await _assign_roles(user_id, ("superadmin",))
        headers = _cookie(await _make_session(user_id))

        await client.put(
            "/api/v1/admin/configuration/maintenance.enabled",
            json={"value": True},
            headers=headers,
        )

        audit = await client.get("/api/v1/admin/audit-events", headers=headers)
        types = {event["event_type"] for event in audit.json()["items"]}
        assert "PLATFORM_MAINTENANCE_ENABLED" in types

    async def test_audit_metadata_carries_no_secret_material(self, client: AsyncClient) -> None:
        user_id = await _make_user()
        await _assign_roles(user_id, ("superadmin",))
        headers = _cookie(await _make_session(user_id))

        await client.put(
            "/api/v1/admin/configuration/quotas.organization_max_teams",
            json={"value": 250},
            headers=headers,
        )

        audit = await client.get("/api/v1/admin/audit-events", headers=headers)
        for event in audit.json()["items"]:
            serialised = str(event)
            for forbidden in ("password", "secret", "token", "api_key"):
                assert forbidden not in serialised.lower()
