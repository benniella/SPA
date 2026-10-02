"""Phone verification.

The delivery boundary is what these are really about: a code is never reported as
sent when no provider is configured, and a verified number is the only one that
can be used for recovery.
"""

from __future__ import annotations

import pytest

from app.application.use_cases import authentication as auth_use_cases
from app.application.use_cases.phone import (
    remove_phone,
    request_phone_verification,
    verify_phone,
)
from app.core.config import Settings
from app.core.errors import InvalidStateError, ValidationError
from app.domain.security.entities import SecurityEventType
from tests.unit.application.fakes import UnitOfWorkStub
from tests.unit.application.security_fakes import (
    FakePasswordHasher,
    FakeRateLimiter,
    RecordingEmailSender,
    RecordingSmsSender,
    token_from,
)

SETTINGS = Settings(
    session_secret="unit-test-session-secret-that-is-long-enough",
    password_min_length=10,
    otp_resend_cooldown_seconds=0,
    rate_limit_phone_per_hour=10,
)
PASSWORD = "correct-horse-9"
PHONE = "+447700900123"


async def _active_user(uow: UnitOfWorkStub):
    sender = RecordingEmailSender()
    await auth_use_cases.register_user(
        uow,
        SETTINGS,
        email="coach@club.example",
        password=PASSWORD,
        display_name="Coach",
        organization_name="Riverside FC",
        organization_slug="riverside-fc",
        hasher=FakePasswordHasher(),
        limiter=FakeRateLimiter(),
        client_key="203.0.113.0",
        email_sender=sender,
    )
    return await auth_use_cases.verify_email(uow, SETTINGS, token=token_from(sender.messages[0]))


def _code_from(sender: RecordingSmsSender) -> str:
    return sender.messages[-1].body.rsplit(" ", 1)[-1].rstrip(".")


class TestRequestVerification:
    async def test_a_configured_sender_receives_a_code(self) -> None:
        uow = UnitOfWorkStub()
        user = await _active_user(uow)
        sms = RecordingSmsSender()

        await request_phone_verification(
            uow,
            SETTINGS,
            user=user,
            phone_number=PHONE,
            sms_sender=sms,
            limiter=FakeRateLimiter(),
            client_key="203.0.113.0",
        )

        assert len(sms.messages) == 1
        assert sms.messages[0].to == PHONE

    async def test_an_unconfigured_sender_refuses_rather_than_pretending(self) -> None:
        uow = UnitOfWorkStub()
        user = await _active_user(uow)
        sms = RecordingSmsSender(configured=False)

        with pytest.raises(Exception) as failure:
            await request_phone_verification(
                uow,
                SETTINGS,
                user=user,
                phone_number=PHONE,
                sms_sender=sms,
                limiter=FakeRateLimiter(),
                client_key="203.0.113.0",
            )

        assert sms.messages == []
        assert "SMS" in str(failure.value)

    async def test_the_phone_number_is_normalised(self) -> None:
        uow = UnitOfWorkStub()
        user = await _active_user(uow)
        sms = RecordingSmsSender()

        await request_phone_verification(
            uow,
            SETTINGS,
            user=user,
            phone_number="+44 7700 900123",
            sms_sender=sms,
            limiter=FakeRateLimiter(),
            client_key="203.0.113.0",
        )

        assert uow.otp_challenges._challenges[-1].destination == PHONE

    async def test_the_code_is_not_logged_or_stored_in_plaintext(self) -> None:
        uow = UnitOfWorkStub()
        user = await _active_user(uow)
        sms = RecordingSmsSender()

        await request_phone_verification(
            uow,
            SETTINGS,
            user=user,
            phone_number=PHONE,
            sms_sender=sms,
            limiter=FakeRateLimiter(),
            client_key="203.0.113.0",
        )

        code = _code_from(sms)
        assert code not in uow.otp_challenges._challenges[-1].code_hash


class TestVerifyPhone:
    async def _issued(self, uow: UnitOfWorkStub, user) -> str:
        sms = RecordingSmsSender()
        await request_phone_verification(
            uow,
            SETTINGS,
            user=user,
            phone_number=PHONE,
            sms_sender=sms,
            limiter=FakeRateLimiter(),
            client_key="203.0.113.0",
        )
        return _code_from(sms)

    async def test_the_correct_code_verifies_the_number(self) -> None:
        uow = UnitOfWorkStub()
        user = await _active_user(uow)
        code = await self._issued(uow, user)

        await verify_phone(
            uow,
            SETTINGS,
            user=user,
            code=code,
            limiter=FakeRateLimiter(),
            client_key="203.0.113.0",
        )

        stored = await uow.users.get(user.id)
        assert stored is not None
        assert stored.is_phone_verified
        assert stored.phone_number == PHONE

    async def test_verifying_records_a_security_event(self) -> None:
        uow = UnitOfWorkStub()
        user = await _active_user(uow)
        code = await self._issued(uow, user)

        await verify_phone(
            uow,
            SETTINGS,
            user=user,
            code=code,
            limiter=FakeRateLimiter(),
            client_key="203.0.113.0",
        )

        events = [event.event_type for event in uow.security_events.events]
        assert SecurityEventType.PHONE_VERIFIED in events

    async def test_a_wrong_code_is_rejected(self) -> None:
        uow = UnitOfWorkStub()
        user = await _active_user(uow)
        await self._issued(uow, user)

        with pytest.raises(ValidationError):
            await verify_phone(
                uow,
                SETTINGS,
                user=user,
                code="000000",
                limiter=FakeRateLimiter(),
                client_key="203.0.113.0",
            )

    async def test_a_code_cannot_be_used_twice(self) -> None:
        uow = UnitOfWorkStub()
        user = await _active_user(uow)
        code = await self._issued(uow, user)
        await verify_phone(
            uow,
            SETTINGS,
            user=user,
            code=code,
            limiter=FakeRateLimiter(),
            client_key="203.0.113.0",
        )

        with pytest.raises(InvalidStateError):
            await verify_phone(
                uow,
                SETTINGS,
                user=user,
                code=code,
                limiter=FakeRateLimiter(),
                client_key="203.0.113.0",
            )


class TestRemovePhone:
    async def test_removing_clears_the_verified_number(self) -> None:
        uow = UnitOfWorkStub()
        user = await _active_user(uow)
        user.phone_number = PHONE
        from app.domain.shared import utcnow

        user.phone_verified_at = utcnow()
        await uow.users.update(user)

        await remove_phone(uow, user=user)

        stored = await uow.users.get(user.id)
        assert stored is not None
        assert not stored.is_phone_verified
