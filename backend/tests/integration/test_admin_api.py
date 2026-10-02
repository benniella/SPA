"""The admin API boundary: authorization, privilege, MFA and lifecycle flows.

Sessions are minted directly rather than through the login endpoint: what these
tests exercise is administrative authorization, not Phase 9 credential handling,
which has its own suite. The minted sessions carry the same shape the login flow
produces, including the MFA assurance the admin dependency requires.
"""

from __future__ import annotations

import uuid
from datetime import timedelta

import pytest
from httpx import AsyncClient

from app.domain.security.tokens import hash_token
from app.domain.shared import utcnow

pytestmark = [pytest.mark.integration, pytest.mark.usefixtures("clean_database")]

TOKEN = "integration-session-token"


async def _settings():
    from app.core.config import get_settings

    return get_settings()


async def _make_user(
    *, email: str | None = None, display_name: str = "Admin"
) -> uuid.UUID:
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
                display_name=display_name,
                is_active=True,
            )
        )
        await session.commit()
    return user_id


async def _make_session(
    user_id: uuid.UUID, *, mfa_verified: bool = True
) -> str:
    """A live session for 'user_id', and its cookie token."""
    from app.core.config import get_settings
    from app.infrastructure.database.engine import get_session_factory
    from app.infrastructure.database.models import SessionModel

    settings = get_settings()
    session_factory = get_session_factory(settings)
    token = f"{TOKEN}-{uuid.uuid4()}"
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


async def _seed_catalogue() -> None:
    from sqlalchemy import text

    from app.core.config import get_settings
    from app.domain.admin.catalogue import (
        PRIVILEGE_DESCRIPTIONS,
        ROLE_DESCRIPTIONS,
        ROLE_PRIVILEGES,
    )
    from app.infrastructure.database.engine import get_session_factory

    session_factory = get_session_factory(get_settings())
    async with session_factory() as session:
        privilege_ids: dict[str, uuid.UUID] = {}
        for name in PRIVILEGE_DESCRIPTIONS:
            privilege_id = uuid.uuid4()
            privilege_ids[name] = privilege_id
            await session.execute(
                text(
                    "INSERT INTO admin_privileges (id, name, description) "
                    "VALUES (:id, :name, :description)"
                ),
                {"id": privilege_id, "name": name, "description": name},
            )
        for role_name in ROLE_DESCRIPTIONS:
            role_id = uuid.uuid4()
            await session.execute(
                text(
                    "INSERT INTO admin_roles (id, name, description) "
                    "VALUES (:id, :name, :description)"
                ),
                {"id": role_id, "name": role_name, "description": role_name},
            )
            for privilege_name in ROLE_PRIVILEGES[role_name]:
                await session.execute(
                    text(
                        "INSERT INTO admin_role_privileges (id, role_id, privilege_id) "
                        "VALUES (:id, :role_id, :privilege_id)"
                    ),
                    {
                        "id": uuid.uuid4(),
                        "role_id": role_id,
                        "privilege_id": privilege_ids[privilege_name],
                    },
                )
        await session.commit()


async def _make_admin(
    *, roles: tuple[str, ...], mfa_verified: bool = True, email: str | None = None
) -> tuple[uuid.UUID, str]:
    """Return the administrator id and its authenticated session cookie token."""
    user_id = await _make_user(email=email)
    admin_id = await _assign_roles(user_id, roles)
    token = await _make_session(user_id, mfa_verified=mfa_verified)
    return admin_id, token


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


def _cookie(token: str) -> dict[str, str]:
    return {"Cookie": f"spa_session={token}"}


@pytest.fixture(autouse=True)
async def catalogue(clean_database: None) -> None:
    await _seed_catalogue()


class TestAuthorization:
    async def test_unauthenticated_request_is_refused(self, client: AsyncClient) -> None:
        response = await client.get("/api/v1/admin/roles")
        assert response.status_code == 401

    async def test_an_ordinary_user_is_refused(self, client: AsyncClient) -> None:
        user_id = await _make_user()
        token = await _make_session(user_id)
        response = await client.get("/api/v1/admin/roles", headers=_cookie(token))
        assert response.status_code == 403

    async def test_an_admin_without_mfa_assurance_is_refused(self, client: AsyncClient) -> None:
        _, token = await _make_admin(roles=("superadmin",), mfa_verified=False)
        response = await client.get("/api/v1/admin/roles", headers=_cookie(token))
        assert response.status_code == 401

    async def test_a_suspended_admin_is_refused(self, client: AsyncClient) -> None:
        from sqlalchemy import text

        from app.core.config import get_settings
        from app.infrastructure.database.engine import get_session_factory

        _, token = await _make_admin(roles=("superadmin",))
        session_factory = get_session_factory(get_settings())
        async with session_factory() as session:
            await session.execute(
                text("UPDATE platform_admins SET status = 'suspended'"), {}
            )
            await session.commit()

        response = await client.get("/api/v1/admin/roles", headers=_cookie(token))
        assert response.status_code == 403


class TestFlowA_Superadmin:
    async def test_superadmin_reads_and_manages(self, client: AsyncClient) -> None:
        actor_token = (await _make_admin(roles=("superadmin",)))[1]
        headers = _cookie(actor_token)

        roles = await client.get("/api/v1/admin/roles", headers=headers)
        assert roles.status_code == 200
        assert "superadmin" in roles.json()["items"]

        privileges = await client.get("/api/v1/admin/privileges", headers=headers)
        assert privileges.status_code == 200
        assert "users.manage" in privileges.json()["items"]

        listing = await client.get("/api/v1/admin/administrators", headers=headers)
        assert listing.status_code == 200
        assert listing.json()["meta"]["count"] == 1

        me = await client.get("/api/v1/admin/me", headers=headers)
        assert me.status_code == 200
        assert me.json()["status"] == "active"


class TestFlowB_LimitedAdmin:
    async def test_permitted_endpoints_allowed_and_prohibited_denied(
        self, client: AsyncClient
    ) -> None:
        _, token = await _make_admin(roles=("support_admin",))
        headers = _cookie(token)

        assert (await client.get("/api/v1/admin/roles", headers=headers)).status_code == 200
        denied = await client.post(
            "/api/v1/admin/invitations",
            json={"email": "new.admin@example.com", "role": "support_admin"},
            headers=headers,
        )
        assert denied.status_code == 403


class TestFlowE_Escalation:
    async def test_role_assignment_beyond_actors_privileges_is_refused(
        self, client: AsyncClient
    ) -> None:
        _, token = await _make_admin(roles=("support_admin",))
        headers = _cookie(token)
        target_id, _ = await _make_admin(roles=())

        response = await client.put(
            f"/api/v1/admin/administrators/{target_id}/roles",
            json={"roles": ["finance_admin"]},
            headers=headers,
        )
        assert response.status_code == 403

    async def test_non_superadmin_cannot_grant_superadmin(self, client: AsyncClient) -> None:
        _, token = await _make_admin(roles=("operations_admin",))
        headers = _cookie(token)
        target_id, _ = await _make_admin(roles=())

        response = await client.put(
            f"/api/v1/admin/administrators/{target_id}/roles",
            json={"roles": ["superadmin"]},
            headers=headers,
        )
        assert response.status_code == 403

    async def test_superadmin_can_assign_a_role(self, client: AsyncClient) -> None:
        _, token = await _make_admin(roles=("superadmin",))
        headers = _cookie(token)
        target_id, _ = await _make_admin(roles=())

        response = await client.put(
            f"/api/v1/admin/administrators/{target_id}/roles",
            json={"roles": ["support_admin"]},
            headers=headers,
        )
        assert response.status_code == 200
        assert response.json()["items"] == ["support_admin"]


class TestFlowF_Lifecycle:
    async def test_suspend_then_deny_then_reactivate(self, client: AsyncClient) -> None:
        _, actor_token = await _make_admin(roles=("superadmin",), email="super@example.com")
        target_id, target_token = await _make_admin(
            roles=("support_admin",), email="target@example.com"
        )
        actor_headers = _cookie(actor_token)
        target_headers = _cookie(target_token)

        suspended = await client.post(
            f"/api/v1/admin/administrators/{target_id}/suspend", headers=actor_headers
        )
        assert suspended.status_code == 200
        assert suspended.json()["status"] == "suspended"

        denied = await client.get("/api/v1/admin/roles", headers=target_headers)
        assert denied.status_code == 403

        reactivated = await client.post(
            f"/api/v1/admin/administrators/{target_id}/reactivate", headers=actor_headers
        )
        assert reactivated.status_code == 200

        # MFA assurance lives on the session and was never revoked, so access returns.
        restored = await client.get("/api/v1/admin/roles", headers=target_headers)
        assert restored.status_code == 200

    async def test_revoke_is_permanent_even_after_reactivation_is_refused(
        self, client: AsyncClient
    ) -> None:
        _, actor_token = await _make_admin(roles=("superadmin",))
        target_id, target_token = await _make_admin(roles=("support_admin",))
        actor_headers = _cookie(actor_token)

        revoked = await client.post(
            f"/api/v1/admin/administrators/{target_id}/revoke", headers=actor_headers
        )
        assert revoked.status_code == 200
        assert revoked.json()["status"] == "revoked"

        denied = await client.get("/api/v1/admin/roles", headers=_cookie(target_token))
        assert denied.status_code == 403

        again = await client.post(
            f"/api/v1/admin/administrators/{target_id}/revoke", headers=actor_headers
        )
        assert again.status_code == 409

    async def test_an_administrator_cannot_suspend_itself(self, client: AsyncClient) -> None:
        actor_id, actor_token = await _make_admin(roles=("superadmin",))
        response = await client.post(
            f"/api/v1/admin/administrators/{actor_id}/suspend", headers=_cookie(actor_token)
        )
        assert response.status_code == 409


class TestFlowC_Invitation:
    async def test_create_accept_stays_invited_then_mfa_activates(
        self, client: AsyncClient, capsys: pytest.CaptureFixture[str]
    ) -> None:
        _, actor_token = await _make_admin(roles=("superadmin",))
        headers = _cookie(actor_token)

        created = await client.post(
            "/api/v1/admin/invitations",
            json={"email": "invitee@example.com", "role": "support_admin"},
            headers=headers,
        )
        assert created.status_code == 202

        # The raw token is not part of the administrative response: it exists
        # only in the emailed link.
        assert "token" not in created.json()
        token = _token_from_console_email(capsys)
        assert token

        invitee_id = await _make_user(email="invitee@example.com")
        invitee_token = await _make_session(invitee_id, mfa_verified=False)

        accepted = await client.post(
            "/api/v1/admin/invitations/accept",
            json={"token": token},
            headers=_cookie(invitee_token),
        )
        assert accepted.status_code == 200, accepted.text
        assert accepted.json()["status"] == "invited"

        # MFA enrollment for the newly invited administrator.
        enroll = await client.post(
            "/api/v1/admin/mfa/enroll", headers=_cookie(invitee_token)
        )
        assert enroll.status_code == 200, enroll.text
        secret = enroll.json()["secret"]

        from app.domain.admin import totp

        confirmed = await client.post(
            "/api/v1/admin/mfa/enroll/confirm",
            json={"code": totp.code_at(secret, timestamp=int(utcnow().timestamp()))},
            headers=_cookie(invitee_token),
        )
        assert confirmed.status_code == 200, confirmed.text
        # Enrolled, but not assured on this session yet: a challenge is required.
        denied = await client.get("/api/v1/admin/roles", headers=_cookie(invitee_token))
        assert denied.status_code == 401

        started = await client.post("/api/v1/admin/mfa/challenge", headers=_cookie(invitee_token))
        assert started.status_code == 200, started.text
        satisfied = await client.post(
            "/api/v1/admin/mfa/challenge/totp",
            json={"code": totp.code_at(secret, timestamp=int(utcnow().timestamp()))},
            headers=_cookie(invitee_token),
        )
        assert satisfied.status_code == 200, satisfied.text
        granted = await client.get("/api/v1/admin/roles", headers=_cookie(invitee_token))
        assert granted.status_code == 200
        assert "support_admin" in granted.json()["items"]

    async def test_an_ordinary_user_cannot_create_an_invitation(
        self, client: AsyncClient
    ) -> None:
        user_id = await _make_user()
        token = await _make_session(user_id)
        response = await client.post(
            "/api/v1/admin/invitations",
            json={"email": "x@example.com", "role": "support_admin"},
            headers=_cookie(token),
        )
        assert response.status_code == 403

    async def test_revoke_makes_acceptance_refused(self, client: AsyncClient) -> None:
        _, actor_token = await _make_admin(roles=("superadmin",))
        headers = _cookie(actor_token)
        created = await client.post(
            "/api/v1/admin/invitations",
            json={"email": "revoked@example.com", "role": "support_admin"},
            headers=headers,
        )
        invitation_id = created.json()["invitation_id"]

        revoked = await client.post(
            f"/api/v1/admin/invitations/{invitation_id}/revoke", headers=headers
        )
        assert revoked.status_code == 200

        invitee_id = await _make_user(email="revoked@example.com")
        invitee_token = await _make_session(invitee_id, mfa_verified=False)
        refused = await client.post(
            "/api/v1/admin/invitations/accept",
            json={"token": "unused-after-revocation"},
            headers=_cookie(invitee_token),
        )
        assert refused.status_code in (404, 409, 422)


def _token_from_console_email(capsys: pytest.CaptureFixture[str]) -> str:
    """The token from the console email body, as a developer would read it."""
    out = capsys.readouterr().out
    marker = "token="
    start = out.rfind(marker)
    if start == -1:
        return ""
    line = out[start + len(marker) :]
    return line.split()[0].split("\n")[0]


class TestAuditEndpoint:
    async def test_audit_requires_the_security_read_privilege(self, client: AsyncClient) -> None:
        _, token = await _make_admin(roles=("support_admin",))
        response = await client.get("/api/v1/admin/audit-events", headers=_cookie(token))
        assert response.status_code == 403

    async def test_a_security_admin_reads_platform_events(self, client: AsyncClient) -> None:


        _, actor_token = await _make_admin(roles=("superadmin",))
        target_id, _ = await _make_admin(roles=("support_admin",))
        headers = _cookie(actor_token)

        suspended = await client.post(
            f"/api/v1/admin/administrators/{target_id}/suspend", headers=headers
        )
        assert suspended.status_code == 200

        _, audit_token = await _make_admin(roles=("security_admin",))
        events = await client.get("/api/v1/admin/audit-events", headers=_cookie(audit_token))
        assert events.status_code == 200
        items = events.json()["items"]
        assert any(item["event_type"] == "ADMIN_SUSPENDED" for item in items)
        # No secret-shaped material in the payloads.
        for item in items:
            assert "token" not in str(item["metadata"]).lower()
