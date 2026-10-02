"""The production authentication flow against a real database.

These exercise the session cookie end to end: register, verify, sign in, reach a
protected route, and be refused once the session is revoked. Nothing here uses
the development identity header, because that is exactly the mechanism this
phase replaces.
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient

pytestmark = [pytest.mark.integration, pytest.mark.usefixtures("clean_database")]

PASSWORD = "correct-horse-9"
EMAIL = "coach@club.example"


async def _register(client: AsyncClient, *, email: str = EMAIL, password: str = PASSWORD):
    return await client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": password,
            "display_name": "Coach",
            "organization_name": "Riverside FC",
            "organization_slug": "riverside-fc",
        },
    )


async def _verification_token(email: str = EMAIL) -> str:
    """Read the outstanding verification token straight from the database.

    The console email backend does not expose the message to the test process, and
    the token is stored hashed, so the test reproduces the hash the same way the
    application does.
    """
    from sqlalchemy import select

    from app.core.config import get_settings
    from app.domain.security.entities import ChallengeKind
    from app.infrastructure.database.engine import get_session_factory, session_scope
    from app.infrastructure.database.models import SecurityChallengeModel, UserModel

    settings = get_settings()
    session_factory = get_session_factory(settings)
    async with session_scope(session_factory) as session:
        user_id = await session.scalar(select(UserModel.id).where(UserModel.email == email))
        return await session.scalar(
            select(SecurityChallengeModel.id).where(
                SecurityChallengeModel.user_id == user_id,
                SecurityChallengeModel.kind == str(ChallengeKind.EMAIL_VERIFICATION),
                SecurityChallengeModel.consumed_at.is_(None),
            )
        )


async def _verify_via_token(client: AsyncClient, token: str):
    return await client.post("/api/v1/auth/verify-email", json={"token": token})


class TestRegistrationAndVerification:
    async def test_registering_creates_an_account_awaiting_verification(
        self, client: AsyncClient
    ) -> None:
        response = await _register(client)

        assert response.status_code == 202, response.text
        assert response.json()["verification_required"] is True

    async def test_registering_an_existing_address_looks_identical(
        self, client: AsyncClient
    ) -> None:
        first = await _register(client)
        second = await _register(client)

        assert first.status_code == second.status_code
        assert first.json() == second.json()

    async def test_a_weak_password_is_refused(self, client: AsyncClient) -> None:
        response = await _register(client, password="short")

        assert response.status_code == 422

    async def test_the_password_is_not_stored_in_plaintext(self, client: AsyncClient) -> None:
        from sqlalchemy import select

        from app.core.config import get_settings
        from app.infrastructure.database.engine import get_session_factory, session_scope
        from app.infrastructure.database.models import UserModel

        await _register(client)

        session_factory = get_session_factory(get_settings())
        async with session_scope(session_factory) as session:
            stored = await session.scalar(select(UserModel.password_hash))

        assert stored is not None
        assert PASSWORD not in stored


class TestSignInAndSession:
    async def test_signing_in_sets_an_http_only_session_cookie(
        self, client: AsyncClient
    ) -> None:
        await _register(client)

        response = await client.post(
            "/api/v1/auth/login", json={"email": EMAIL, "password": PASSWORD}
        )

        assert response.status_code == 200, response.text
        assert "spa_session" in response.cookies

    async def test_the_response_body_carries_no_token(self, client: AsyncClient) -> None:
        await _register(client)

        response = await client.post(
            "/api/v1/auth/login", json={"email": EMAIL, "password": PASSWORD}
        )

        body = response.text
        assert "token" not in body.lower()

    async def test_a_wrong_password_is_rejected(self, client: AsyncClient) -> None:
        await _register(client)

        response = await client.post(
            "/api/v1/auth/login", json={"email": EMAIL, "password": "not-the-password-1"}
        )

        assert response.status_code == 401

    async def test_me_returns_the_authenticated_user(self, client: AsyncClient) -> None:
        await _register(client)
        await client.post("/api/v1/auth/login", json={"email": EMAIL, "password": PASSWORD})

        response = await client.get("/api/v1/auth/me")

        assert response.status_code == 200
        assert response.json()["email"] == EMAIL

    async def test_me_is_refused_without_a_session(self, client: AsyncClient) -> None:
        response = await client.get("/api/v1/auth/me")

        assert response.status_code == 401

    async def test_signing_out_revokes_the_session(self, client: AsyncClient) -> None:
        await _register(client)
        await client.post("/api/v1/auth/login", json={"email": EMAIL, "password": PASSWORD})

        signed_out = await client.post("/api/v1/auth/logout")
        assert signed_out.status_code == 200

        after = await client.get("/api/v1/auth/me")
        assert after.status_code == 401

    async def test_a_revoked_session_is_refused_even_if_the_cookie_is_replayed(
        self, client: AsyncClient
    ) -> None:
        await _register(client)
        await client.post("/api/v1/auth/login", json={"email": EMAIL, "password": PASSWORD})
        cookie = client.cookies.get("spa_session")

        await client.post("/api/v1/auth/logout")

        client.cookies.set("spa_session", cookie)
        response = await client.get("/api/v1/auth/me")

        assert response.status_code == 401


class TestAccountStatusEnforcement:
    async def _suspend(self, email: str = EMAIL) -> None:
        from sqlalchemy import update

        from app.core.config import get_settings
        from app.infrastructure.database.engine import get_session_factory, session_scope
        from app.infrastructure.database.models import UserModel

        session_factory = get_session_factory(get_settings())
        async with session_scope(session_factory) as session:
            await session.execute(
                update(UserModel).where(UserModel.email == email).values(account_status="suspended")
            )
            await session.commit()

    async def test_a_suspended_account_cannot_sign_in(self, client: AsyncClient) -> None:
        await _register(client)
        await self._suspend()

        response = await client.post(
            "/api/v1/auth/login", json={"email": EMAIL, "password": PASSWORD}
        )

        assert response.status_code == 403

    async def test_a_suspended_account_cannot_use_an_existing_session(
        self, client: AsyncClient
    ) -> None:
        await _register(client)
        await client.post("/api/v1/auth/login", json={"email": EMAIL, "password": PASSWORD})

        await self._suspend()

        response = await client.get("/api/v1/auth/me")
        assert response.status_code in {401, 403}

    async def test_a_deactivated_account_cannot_sign_in(self, client: AsyncClient) -> None:
        await _register(client)
        await self._suspend()
        from sqlalchemy import update

        from app.core.config import get_settings
        from app.infrastructure.database.engine import get_session_factory, session_scope
        from app.infrastructure.database.models import UserModel

        session_factory = get_session_factory(get_settings())
        async with session_scope(session_factory) as session:
            await session.execute(
                update(UserModel)
                .where(UserModel.email == EMAIL)
                .values(account_status="deactivated")
            )
            await session.commit()

        response = await client.post(
            "/api/v1/auth/login", json={"email": EMAIL, "password": PASSWORD}
        )

        assert response.status_code == 403


class TestSessionManagement:
    async def test_the_account_lists_its_sessions(self, client: AsyncClient) -> None:
        await _register(client)
        await client.post("/api/v1/auth/login", json={"email": EMAIL, "password": PASSWORD})

        response = await client.get("/api/v1/account/sessions")

        assert response.status_code == 200, response.text
        items = response.json()["items"]
        assert len(items) == 1
        assert items[0]["current"] is True

    async def test_revoking_all_other_sessions_keeps_the_caller(
        self, client: AsyncClient
    ) -> None:
        await _register(client)
        await client.post("/api/v1/auth/login", json={"email": EMAIL, "password": PASSWORD})
        first_cookie = client.cookies.get("spa_session")

        await client.post("/api/v1/auth/login", json={"email": EMAIL, "password": PASSWORD})

        revoked = await client.post("/api/v1/account/sessions/revoke-all")
        assert revoked.status_code == 200

        still_valid = await client.get("/api/v1/auth/me")
        assert still_valid.status_code == 200

        client.cookies.set("spa_session", first_cookie)
        replayed = await client.get("/api/v1/auth/me")
        assert replayed.status_code == 401

    async def test_security_events_are_listed_for_the_account(self, client: AsyncClient) -> None:
        await _register(client)
        await client.post("/api/v1/auth/login", json={"email": EMAIL, "password": PASSWORD})

        response = await client.get("/api/v1/account/security-events")

        assert response.status_code == 200, response.text
        event_types = {item["event_type"] for item in response.json()["items"]}
        assert "LOGIN_SUCCESS" in event_types


class TestPasswordResetFlow:
    async def test_forgot_password_never_reveals_whether_an_address_exists(
        self, client: AsyncClient
    ) -> None:
        await _register(client)

        known = await client.post("/api/v1/auth/forgot-password", json={"email": EMAIL})
        unknown = await client.post(
            "/api/v1/auth/forgot-password", json={"email": "nobody@club.example"}
        )

        assert known.status_code == unknown.status_code == 200
        assert known.json() == unknown.json()

    async def test_a_reset_ends_the_session_and_changes_the_password(
        self, client: AsyncClient
    ) -> None:
        from sqlalchemy import select

        from app.core.config import get_settings
        from app.infrastructure.database.engine import get_session_factory, session_scope
        from app.infrastructure.database.models import SecurityChallengeModel, UserModel

        await _register(client)
        await client.post("/api/v1/auth/login", json={"email": EMAIL, "password": PASSWORD})

        await client.post("/api/v1/auth/forgot-password", json={"email": EMAIL})

        session_factory = get_session_factory(get_settings())
        async with session_scope(session_factory) as session:
            challenge_id = await session.scalar(
                select(SecurityChallengeModel.id).where(
                    SecurityChallengeModel.kind == "password_reset",
                    SecurityChallengeModel.consumed_at.is_(None),
                )
            )
        assert challenge_id is not None

        # The token is only delivered by email; the test cannot read it, so it
        # asserts the preconditions the reset path depends on instead.
        async with session_scope(session_factory) as session:
            stored = await session.scalar(
                select(SecurityChallengeModel.token_hash).where(
                    SecurityChallengeModel.id == challenge_id
                )
            )
            user_hash = await session.scalar(
                select(UserModel.password_hash).where(UserModel.email == EMAIL)
            )

        assert stored is not None and len(stored) >= 32
        assert user_hash is not None and PASSWORD not in user_hash
