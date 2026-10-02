"""The OTP and challenge services.

These cover the properties an attacker would attack: codes expire, attempts are
capped, a code works once, and the raw secret is never what gets stored.
"""

from __future__ import annotations

from datetime import timedelta

import pytest

from app.application.security import (
    consume_challenge,
    issue_challenge,
    issue_otp,
    verify_otp,
)
from app.core.config import Settings
from app.core.errors import InvalidStateError, RateLimitedError, ValidationError
from app.domain.security.entities import ChallengeKind, OtpPurpose, SecurityEventType
from app.domain.shared import UserId, new_id, utcnow
from tests.unit.application.fakes import UnitOfWorkStub

SETTINGS = Settings(
    session_secret="unit-test-session-secret-that-is-long-enough",
    otp_ttl_minutes=10,
    otp_max_attempts=3,
    otp_resend_cooldown_seconds=60,
    otp_length=6,
)


def _user_id() -> UserId:
    return UserId(new_id())


class TestOtpIssuing:
    async def test_a_code_is_six_digits(self) -> None:
        uow = UnitOfWorkStub()
        code = await issue_otp(
            uow,
            SETTINGS,
            user_id=_user_id(),
            purpose=OtpPurpose.PHONE_VERIFICATION,
            destination="+447700900123",
        )
        assert code.isdigit()
        assert len(code) == 6

    async def test_the_plaintext_code_is_not_stored(self) -> None:
        uow = UnitOfWorkStub()
        code = await issue_otp(
            uow,
            SETTINGS,
            user_id=_user_id(),
            purpose=OtpPurpose.PHONE_VERIFICATION,
            destination="+447700900123",
        )
        stored = uow.otp_challenges._challenges[0]
        assert code not in stored.code_hash

    async def test_issuing_records_a_security_event(self) -> None:
        uow = UnitOfWorkStub()
        await issue_otp(
            uow,
            SETTINGS,
            user_id=_user_id(),
            purpose=OtpPurpose.PHONE_VERIFICATION,
            destination="+447700900123",
        )
        assert uow.security_events.events[0].event_type == (
            SecurityEventType.PHONE_VERIFICATION_REQUESTED
        )

    async def test_a_second_issue_inside_the_cooldown_is_refused(self) -> None:
        uow = UnitOfWorkStub()
        user_id = _user_id()
        await issue_otp(
            uow,
            SETTINGS,
            user_id=user_id,
            purpose=OtpPurpose.PHONE_VERIFICATION,
            destination="+447700900123",
        )
        with pytest.raises(RateLimitedError):
            await issue_otp(
                uow,
                SETTINGS,
                user_id=user_id,
                purpose=OtpPurpose.PHONE_VERIFICATION,
                destination="+447700900123",
            )

    async def test_issuing_replaces_an_outstanding_code(self) -> None:
        uow = UnitOfWorkStub()
        user_id = _user_id()
        first = await issue_otp(
            uow,
            SETTINGS,
            user_id=user_id,
            purpose=OtpPurpose.PHONE_VERIFICATION,
            destination="+447700900123",
        )
        uow.otp_challenges._challenges[0].created_at = utcnow() - timedelta(minutes=5)
        await issue_otp(
            uow,
            SETTINGS,
            user_id=user_id,
            purpose=OtpPurpose.PHONE_VERIFICATION,
            destination="+447700900123",
        )
        with pytest.raises(ValidationError):
            await verify_otp(
                uow,
                SETTINGS,
                user_id=user_id,
                purpose=OtpPurpose.PHONE_VERIFICATION,
                code=first,
            )


class TestOtpVerifying:
    async def _issue(self, uow: UnitOfWorkStub, user_id: UserId) -> str:
        return await issue_otp(
            uow,
            SETTINGS,
            user_id=user_id,
            purpose=OtpPurpose.PHONE_VERIFICATION,
            destination="+447700900123",
        )

    async def test_the_correct_code_verifies(self) -> None:
        uow = UnitOfWorkStub()
        user_id = _user_id()
        code = await self._issue(uow, user_id)
        challenge = await verify_otp(
            uow,
            SETTINGS,
            user_id=user_id,
            purpose=OtpPurpose.PHONE_VERIFICATION,
            code=code,
        )
        assert challenge.is_consumed

    async def test_a_verified_code_cannot_be_used_again(self) -> None:
        uow = UnitOfWorkStub()
        user_id = _user_id()
        code = await self._issue(uow, user_id)
        await verify_otp(
            uow,
            SETTINGS,
            user_id=user_id,
            purpose=OtpPurpose.PHONE_VERIFICATION,
            code=code,
        )
        with pytest.raises(InvalidStateError):
            await verify_otp(
                uow,
                SETTINGS,
                user_id=user_id,
                purpose=OtpPurpose.PHONE_VERIFICATION,
                code=code,
            )

    async def test_a_wrong_code_is_rejected(self) -> None:
        uow = UnitOfWorkStub()
        user_id = _user_id()
        await self._issue(uow, user_id)
        with pytest.raises(ValidationError):
            await verify_otp(
                uow,
                SETTINGS,
                user_id=user_id,
                purpose=OtpPurpose.PHONE_VERIFICATION,
                code="000000",
            )

    async def test_repeated_wrong_codes_exhaust_the_attempt_limit(self) -> None:
        uow = UnitOfWorkStub()
        user_id = _user_id()
        await self._issue(uow, user_id)
        for _ in range(SETTINGS.otp_max_attempts):
            with pytest.raises((ValidationError, RateLimitedError)):
                await verify_otp(
                    uow,
                    SETTINGS,
                    user_id=user_id,
                    purpose=OtpPurpose.PHONE_VERIFICATION,
                    code="000000",
                )
        with pytest.raises(RateLimitedError):
            await verify_otp(
                uow,
                SETTINGS,
                user_id=user_id,
                purpose=OtpPurpose.PHONE_VERIFICATION,
                code="000000",
            )

    async def test_an_expired_code_is_rejected(self) -> None:
        uow = UnitOfWorkStub()
        user_id = _user_id()
        code = await self._issue(uow, user_id)
        uow.otp_challenges._challenges[0].expires_at = utcnow() - timedelta(seconds=1)
        with pytest.raises(InvalidStateError):
            await verify_otp(
                uow,
                SETTINGS,
                user_id=user_id,
                purpose=OtpPurpose.PHONE_VERIFICATION,
                code=code,
            )

    async def test_a_code_for_another_purpose_does_not_verify(self) -> None:
        uow = UnitOfWorkStub()
        user_id = _user_id()
        code = await self._issue(uow, user_id)
        with pytest.raises(InvalidStateError):
            await verify_otp(
                uow,
                SETTINGS,
                user_id=user_id,
                purpose=OtpPurpose.ACCOUNT_RECOVERY,
                code=code,
            )


class TestChallengeService:
    async def test_a_challenge_token_is_consumed_once(self) -> None:
        uow = UnitOfWorkStub()
        user_id = _user_id()
        token = await issue_challenge(
            uow,
            SETTINGS,
            user_id=user_id,
            kind=ChallengeKind.EMAIL_VERIFICATION,
        )
        await consume_challenge(
            uow, SETTINGS, token=token, kind=ChallengeKind.EMAIL_VERIFICATION
        )
        with pytest.raises(ValidationError):
            await consume_challenge(
                uow, SETTINGS, token=token, kind=ChallengeKind.EMAIL_VERIFICATION
            )

    async def test_the_raw_token_is_not_stored(self) -> None:
        uow = UnitOfWorkStub()
        token = await issue_challenge(
            uow,
            SETTINGS,
            user_id=_user_id(),
            kind=ChallengeKind.PASSWORD_RESET,
        )
        assert token != uow.challenges._challenges[0].token_hash

    async def test_a_token_of_the_wrong_kind_is_refused(self) -> None:
        uow = UnitOfWorkStub()
        token = await issue_challenge(
            uow,
            SETTINGS,
            user_id=_user_id(),
            kind=ChallengeKind.EMAIL_VERIFICATION,
        )
        with pytest.raises(ValidationError):
            await consume_challenge(uow, SETTINGS, token=token, kind=ChallengeKind.PASSWORD_RESET)

    async def test_an_unknown_token_is_refused(self) -> None:
        uow = UnitOfWorkStub()
        with pytest.raises(ValidationError):
            await consume_challenge(
                uow, SETTINGS, token="not-a-real-token", kind=ChallengeKind.EMAIL_VERIFICATION
            )
