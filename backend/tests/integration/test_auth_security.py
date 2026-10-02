"""Security-boundary tests.

Each of these asserts a guarantee the phase claims, rather than a happy path:
production authentication cannot be bypassed, a used token stays used, and one
account cannot reach another's sessions.
"""

from __future__ import annotations

from typing import ClassVar

import pytest
from httpx import AsyncClient

from app.core.config import Settings
from app.core.errors import AuthenticationError, SessionExpiredError

pytestmark = [pytest.mark.integration, pytest.mark.usefixtures("clean_database")]

PASSWORD = "correct-horse-9"
EMAIL = "coach@club.example"


async def _register_and_sign_in(client: AsyncClient, email: str = EMAIL) -> None:
    await client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": PASSWORD,
            "display_name": "Coach",
            "organization_name": f"Club {email}",
            "organization_slug": email.split("@")[0].replace("_", "-"),
        },
    )
    response = await client.post(
        "/api/v1/auth/login", json={"email": email, "password": PASSWORD}
    )
    assert response.status_code == 200, response.text


class TestProductionCannotUseTheDevelopmentHeader:
    async def test_the_header_does_not_authenticate_in_production(self) -> None:
        """The dependency refuses the header whenever the environment is production.

        The check is asserted at the dependency boundary, where it is enforced,
        rather than through an HTTP call: the app under test runs in the local
        environment, and the guarantee is that no value of the setting can enable
        the header in production.
        """
        from app.api.dependencies import current_user_dependency

        production = Settings(
            environment="production",
            session_secret="production-session-secret-that-is-long-enough",
            database_url="postgresql+psycopg://spa:spa@localhost:5442/spa_test",
            dev_identity_header=True,
        )
        assert production.is_production
        assert production.dev_identity_header

        class _Request:
            headers: ClassVar[dict[str, str]] = {
                "x-spa-user-id": "11111111-1111-1111-1111-111111111111"
            }
            cookies: ClassVar[dict[str, str]] = {}
            client = None

        with pytest.raises((AuthenticationError, SessionExpiredError)):
            await current_user_dependency(
                _Request(),  # type: ignore[arg-type]
                uow=None,  # type: ignore[arg-type]
                token=None,
                settings=production,
            )


class TestSessionIsolation:
    async def test_one_account_cannot_revoke_anothers_session(self, client: AsyncClient) -> None:
        await _register_and_sign_in(client, "first@club.example")
        first_sessions = (await client.get("/api/v1/account/sessions")).json()["items"]

        await _register_and_sign_in(client, "second@club.example")

        response = await client.delete(f"/api/v1/account/sessions/{first_sessions[0]['id']}")
        assert response.status_code == 404

    async def test_sessions_are_listed_only_for_the_caller(self, client: AsyncClient) -> None:
        await _register_and_sign_in(client, "first@club.example")
        await _register_and_sign_in(client, "second@club.example")

        listed = (await client.get("/api/v1/account/sessions")).json()["items"]

        assert len(listed) == 1

    async def test_the_account_cannot_read_another_accounts_security_events(
        self, client: AsyncClient
    ) -> None:
        await _register_and_sign_in(client, "first@club.example")
        await client.post("/api/v1/auth/logout")

        await _register_and_sign_in(client, "second@club.example")
        events = (await client.get("/api/v1/account/security-events")).json()["items"]

        assert all(event["event_type"] != "LOGOUT" for event in events)


class TestTokensAndCredentialsAreNeverExposed:
    async def test_no_response_contains_a_raw_session_token(self, client: AsyncClient) -> None:
        await _register_and_sign_in(client)

        for path in ("/api/v1/auth/me", "/api/v1/account/sessions"):
            body = (await client.get(path)).text.lower()
            assert "spa_session" not in body
            assert "token" not in body

    async def test_no_response_contains_a_password_hash(self, client: AsyncClient) -> None:
        await _register_and_sign_in(client)

        body = (await client.get("/api/v1/auth/me")).text

        assert "pbkdf2" not in body.lower()
        assert PASSWORD not in body

    async def test_the_login_response_does_not_echo_the_password(self, client: AsyncClient) -> None:
        await _register_and_sign_in(client)

        response = await client.post(
            "/api/v1/auth/login", json={"email": EMAIL, "password": PASSWORD}
        )

        assert PASSWORD not in response.text

    async def test_the_forgot_password_response_is_identical_for_unknown_addresses(
        self, client: AsyncClient
    ) -> None:
        await _register_and_sign_in(client)

        known = await client.post("/api/v1/auth/forgot-password", json={"email": EMAIL})
        unknown = await client.post(
            "/api/v1/auth/forgot-password", json={"email": "absent@club.example"}
        )

        assert known.status_code == unknown.status_code
        assert known.json() == unknown.json()


class TestOrganizationIsolationStillHolds:
    async def test_a_session_does_not_grant_access_to_another_organization(
        self, client: AsyncClient
    ) -> None:
        await _register_and_sign_in(client, "first@club.example")
        own_organizations = (await client.get("/api/v1/auth/me")).json()["organizations"]
        own_id = own_organizations[0]["id"]

        foreign = (
            await client.post(
                "/api/v1/organizations",
                json={"name": "Other FC", "slug": "other-fc"},
            )
        ).json()

        created = await client.post(
            "/api/v1/teams",
            json={"organization_id": own_id, "name": "First Team", "slug": "first-team"},
        )
        assert created.status_code == 201

        listed = await client.get("/api/v1/teams", params={"organization_id": foreign["id"]})
        assert listed.json()["items"] == []

    async def test_the_catalog_routes_now_require_authentication(self, client: AsyncClient) -> None:
        """Phase 10 closed the gap Phase 9 documented here.

        The organization, team, player and match routes previously carried no
        current-user dependency, so an anonymous caller could reach them. They are
        now scoped to the caller's memberships.
        """
        for path, params in (
            ("/api/v1/organizations", None),
            ("/api/v1/teams", {"organization_id": "11111111-1111-1111-1111-111111111111"}),
            ("/api/v1/players", {"organization_id": "11111111-1111-1111-1111-111111111111"}),
            ("/api/v1/matches", {"organization_id": "11111111-1111-1111-1111-111111111111"}),
            ("/api/v1/users/me", None),
        ):
            response = await client.get(path, params=params)
            assert response.status_code == 401, f"{path} was reachable anonymously"


class TestExpiryAndRevocation:
    async def test_an_expired_session_is_refused(self, client: AsyncClient) -> None:
        from sqlalchemy import update

        from app.core.config import get_settings
        from app.infrastructure.database.engine import get_session_factory, session_scope
        from app.infrastructure.database.models import SessionModel

        await _register_and_sign_in(client)
        assert (await client.get("/api/v1/auth/me")).status_code == 200

        session_factory = get_session_factory(get_settings())
        async with session_scope(session_factory) as session:
            await session.execute(
                update(SessionModel).values(expires_at=SessionModel.created_at)
            )
            await session.commit()

        assert (await client.get("/api/v1/auth/me")).status_code == 401

    async def test_a_revoked_session_cannot_reach_the_account_endpoints(
        self, client: AsyncClient
    ) -> None:
        await _register_and_sign_in(client)
        cookie = client.cookies.get("spa_session")
        await client.post("/api/v1/auth/logout")
        client.cookies.set("spa_session", cookie)

        for path in ("/api/v1/auth/me", "/api/v1/account/sessions"):
            assert (await client.get(path)).status_code == 401
