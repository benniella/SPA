"""Registration, sign-in, sign-out and email verification.

These assert the security properties the API depends on: registration does not
confirm whether an address exists, a failed sign-in is indistinguishable from an
unknown account, and an account that may not authenticate cannot open a session.
"""

from __future__ import annotations

import pytest

from app.application.use_cases.authentication import (
    login,
    logout,
    register_user,
    resend_verification,
    verify_email,
)
from app.core.config import Settings
from app.core.errors import (
    AccountNotActiveError,
    AuthenticationError,
    RateLimitedError,
    ValidationError,
)
from app.domain.security.entities import SecurityEventType
from app.domain.users.entities import AccountStatus, User
from tests.unit.application.fakes import UnitOfWorkStub
from tests.unit.application.security_fakes import (
    FakePasswordHasher,
    FakeRateLimiter,
    RecordingEmailSender,
    token_from,
)

SETTINGS = Settings(
    session_secret="unit-test-session-secret-that-is-long-enough",
    password_min_length=10,
    rate_limit_login_per_minute=10,
    rate_limit_login_per_account_per_minute=5,
    rate_limit_register_per_hour=20,
    rate_limit_resend_verification_per_hour=5,
)

PASSWORD = "correct-horse-9"


def _register_kwargs(uow: UnitOfWorkStub, sender: RecordingEmailSender) -> dict[str, object]:
    return {
        "uow": uow,
        "settings": SETTINGS,
        "email": "coach@club.example",
        "password": PASSWORD,
        "display_name": "Coach",
        "organization_name": "Riverside FC",
        "organization_slug": "riverside-fc",
        "hasher": FakePasswordHasher(),
        "limiter": FakeRateLimiter(),
        "client_key": "203.0.113.0",
        "email_sender": sender,
    }


class TestRegistration:
    async def test_registration_creates_an_unverified_account_and_a_workspace(self) -> None:
        uow = UnitOfWorkStub()
        sender = RecordingEmailSender()
        result = await register_user(**_register_kwargs(uow, sender))  # type: ignore[arg-type]

        assert result.user.account_status.value == AccountStatus.PENDING_VERIFICATION
        assert not result.user.is_email_verified
        assert uow.organizations.memberships[0].role == "owner"
        assert len(sender.messages) == 1

    async def test_the_password_is_stored_hashed(self) -> None:
        uow = UnitOfWorkStub()
        await register_user(**_register_kwargs(uow, RecordingEmailSender()))  # type: ignore[arg-type]
        assert uow.users.items[0].password_hash != PASSWORD  # type: ignore[attr-defined]

    async def test_a_weak_password_is_rejected(self) -> None:
        uow = UnitOfWorkStub()
        kwargs = _register_kwargs(uow, RecordingEmailSender())
        kwargs["password"] = "short"
        with pytest.raises(ValidationError):
            await register_user(**kwargs)  # type: ignore[arg-type]

    async def test_registering_an_existing_address_is_not_revealed(self) -> None:
        uow = UnitOfWorkStub()
        sender = RecordingEmailSender()
        first = await register_user(**_register_kwargs(uow, sender))  # type: ignore[arg-type]
        second = await register_user(**_register_kwargs(uow, sender))  # type: ignore[arg-type]

        assert first.already_registered is False
        assert second.already_registered is True
        assert len(uow.users.items) == 1

    async def test_the_verification_email_does_not_contain_the_password(self) -> None:
        uow = UnitOfWorkStub()
        sender = RecordingEmailSender()
        await register_user(**_register_kwargs(uow, sender))  # type: ignore[arg-type]
        assert PASSWORD not in sender.messages[0].text


class TestEmailVerification:
    async def _registered(
        self, uow: UnitOfWorkStub, sender: RecordingEmailSender
    ) -> User:
        result = await register_user(**_register_kwargs(uow, sender))  # type: ignore[arg-type]
        return result.user

    async def test_verifying_activates_the_account(self) -> None:
        uow = UnitOfWorkStub()
        sender = RecordingEmailSender()
        user = await self._registered(uow, sender)

        verified = await verify_email(uow, SETTINGS, token=token_from(sender.messages[0]))

        assert verified.id == user.id
        assert verified.is_email_verified
        assert verified.account_status.value == AccountStatus.ACTIVE

    async def test_a_verification_token_cannot_be_reused(self) -> None:
        uow = UnitOfWorkStub()
        sender = RecordingEmailSender()
        await self._registered(uow, sender)
        token = token_from(sender.messages[0])

        await verify_email(uow, SETTINGS, token=token)
        with pytest.raises(ValidationError):
            await verify_email(uow, SETTINGS, token=token)

    async def test_an_unknown_token_is_rejected(self) -> None:
        uow = UnitOfWorkStub()
        with pytest.raises(ValidationError):
            await verify_email(uow, SETTINGS, token="not-a-real-token")

    async def test_resending_for_an_unknown_address_stays_silent(self) -> None:
        uow = UnitOfWorkStub()
        sender = RecordingEmailSender()
        await resend_verification(
            uow,
            SETTINGS,
            email="nobody@club.example",
            email_sender=sender,
            limiter=FakeRateLimiter(),
            client_key="203.0.113.0",
        )
        assert sender.messages == []


class TestLogin:
    async def _active_user(self, uow: UnitOfWorkStub) -> User:
        sender = RecordingEmailSender()
        await register_user(**_register_kwargs(uow, sender))  # type: ignore[arg-type]
        return await verify_email(uow, SETTINGS, token=token_from(sender.messages[0]))

    def _login_kwargs(self, uow: UnitOfWorkStub) -> dict[str, object]:
        return {
            "uow": uow,
            "settings": SETTINGS,
            "email": "coach@club.example",
            "password": PASSWORD,
            "hasher": FakePasswordHasher(),
            "limiter": FakeRateLimiter(),
            "client_key": "203.0.113.0",
        }

    async def test_valid_credentials_open_a_session(self) -> None:
        uow = UnitOfWorkStub()
        await self._active_user(uow)

        issued = await login(**self._login_kwargs(uow))  # type: ignore[arg-type]

        assert issued.token
        assert issued.session.user_id is not None
        events = [event.event_type for event in uow.security_events.events]
        assert SecurityEventType.LOGIN_SUCCESS in events

    async def test_a_wrong_password_is_rejected(self) -> None:
        uow = UnitOfWorkStub()
        await self._active_user(uow)
        kwargs = self._login_kwargs(uow)
        kwargs["password"] = "wrong-password-1"

        with pytest.raises(AuthenticationError):
            await login(**kwargs)  # type: ignore[arg-type]

    async def test_an_unknown_address_fails_identically_to_a_wrong_password(self) -> None:
        uow = UnitOfWorkStub()
        await self._active_user(uow)

        wrong_password = self._login_kwargs(uow)
        wrong_password["password"] = "wrong-password-1"
        with pytest.raises(AuthenticationError) as known:
            await login(**wrong_password)  # type: ignore[arg-type]

        unknown = self._login_kwargs(uow)
        unknown["email"] = "nobody@club.example"
        with pytest.raises(AuthenticationError) as absent:
            await login(**unknown)  # type: ignore[arg-type]

        assert str(known.value) == str(absent.value)

    async def test_a_pending_account_can_sign_in_but_is_not_verified(self) -> None:
        uow = UnitOfWorkStub()
        await register_user(**_register_kwargs(uow, RecordingEmailSender()))  # type: ignore[arg-type]

        issued = await login(**self._login_kwargs(uow))  # type: ignore[arg-type]

        user = await uow.users.get_by_email("coach@club.example")
        assert issued.token
        assert user is not None
        assert not user.is_email_verified

    async def test_a_suspended_account_cannot_sign_in(self) -> None:
        uow = UnitOfWorkStub()
        user = await self._active_user(uow)
        user.account_status = AccountStatus(AccountStatus.SUSPENDED)
        await uow.users.update(user)

        with pytest.raises(AccountNotActiveError):
            await login(**self._login_kwargs(uow))  # type: ignore[arg-type]

    async def test_a_deactivated_account_cannot_sign_in(self) -> None:
        uow = UnitOfWorkStub()
        user = await self._active_user(uow)
        user.account_status = AccountStatus(AccountStatus.DEACTIVATED)
        await uow.users.update(user)

        with pytest.raises(AccountNotActiveError):
            await login(**self._login_kwargs(uow))  # type: ignore[arg-type]

    async def test_the_login_rate_limit_is_enforced(self) -> None:
        uow = UnitOfWorkStub()
        await self._active_user(uow)
        limiter = FakeRateLimiter()
        for _ in range(SETTINGS.rate_limit_login_per_minute):
            await limiter.hit("spa:ratelimit:login:203.0.113.0", limit=10, window_seconds=60)

        kwargs = self._login_kwargs(uow)
        kwargs["limiter"] = limiter
        with pytest.raises(RateLimitedError):
            await login(**kwargs)  # type: ignore[arg-type]

    async def test_a_repeated_failure_is_recorded(self) -> None:
        uow = UnitOfWorkStub()
        await self._active_user(uow)
        kwargs = self._login_kwargs(uow)
        kwargs["password"] = "wrong-password-1"

        with pytest.raises(AuthenticationError):
            await login(**kwargs)  # type: ignore[arg-type]

        assert uow.security_events.events[-1].event_type == SecurityEventType.LOGIN_FAILED


class TestLogout:
    async def test_logging_out_revokes_the_session(self) -> None:
        uow = UnitOfWorkStub()
        sender = RecordingEmailSender()
        await register_user(**_register_kwargs(uow, sender))  # type: ignore[arg-type]
        user = await verify_email(uow, SETTINGS, token=token_from(sender.messages[0]))
        issued = await login(
            uow,
            SETTINGS,
            email="coach@club.example",
            password=PASSWORD,
            hasher=FakePasswordHasher(),
            limiter=FakeRateLimiter(),
            client_key="203.0.113.0",
        )

        await logout(uow, SETTINGS, session_token=issued.token, user_id=user.id)

        assert issued.session.is_revoked
        assert uow.security_events.events[-1].event_type == SecurityEventType.LOGOUT

    async def test_logging_out_twice_is_not_an_error(self) -> None:
        uow = UnitOfWorkStub()
        await logout(uow, SETTINGS, session_token="unknown-token", user_id=None)
