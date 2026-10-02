"""Password reset, password change, email change and account recovery.

These assert the recovery paths cannot be turned into an account-takeover
primitive: a reset ends every session, a change proves the current password, and
a new email is not adopted until it is confirmed.
"""

from __future__ import annotations

from datetime import timedelta

import pytest

from app.application.use_cases import authentication as auth_use_cases
from app.application.use_cases.account_security import (
    change_password,
    complete_recovery,
    request_password_reset,
    reset_password,
    start_recovery,
)
from app.core.config import Settings
from app.core.errors import AuthenticationError, RateLimitedError, ValidationError
from app.domain.security.entities import SecurityEventType
from app.domain.shared import utcnow
from app.domain.users.entities import AccountStatus
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
    rate_limit_password_reset_per_hour=10,
    otp_resend_cooldown_seconds=0,
)
PASSWORD = "correct-horse-9"
NEW_PASSWORD = "a-different-9"


async def _active_user(uow: UnitOfWorkStub, sender: RecordingEmailSender):
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


async def _open_session(uow: UnitOfWorkStub):
    return await auth_use_cases.login(
        uow,
        SETTINGS,
        email="coach@club.example",
        password=PASSWORD,
        hasher=FakePasswordHasher(),
        limiter=FakeRateLimiter(),
        client_key="203.0.113.0",
    )


class TestPasswordReset:
    async def test_a_known_address_receives_a_reset_link(self) -> None:
        uow = UnitOfWorkStub()
        sender = RecordingEmailSender()
        await _active_user(uow, sender)
        sender.messages.clear()

        await request_password_reset(
            uow,
            SETTINGS,
            email="coach@club.example",
            email_sender=sender,
            limiter=FakeRateLimiter(),
            client_key="203.0.113.0",
        )

        assert len(sender.messages) == 1
        assert "reset" in sender.messages[0].text.lower()

    async def test_an_unknown_address_produces_no_message(self) -> None:
        uow = UnitOfWorkStub()
        sender = RecordingEmailSender()

        await request_password_reset(
            uow,
            SETTINGS,
            email="nobody@club.example",
            email_sender=sender,
            limiter=FakeRateLimiter(),
            client_key="203.0.113.0",
        )

        assert sender.messages == []

    async def test_resetting_changes_the_password_and_revokes_sessions(self) -> None:
        uow = UnitOfWorkStub()
        sender = RecordingEmailSender()
        await _active_user(uow, sender)
        session = await _open_session(uow)
        sender.messages.clear()

        await request_password_reset(
            uow,
            SETTINGS,
            email="coach@club.example",
            email_sender=sender,
            limiter=FakeRateLimiter(),
            client_key="203.0.113.0",
        )
        await reset_password(
            uow,
            SETTINGS,
            token=token_from(sender.messages[0]),
            new_password=NEW_PASSWORD,
            hasher=FakePasswordHasher(),
            limiter=FakeRateLimiter(),
            client_key="203.0.113.0",
        )

        assert session.session.is_revoked
        user = await uow.users.get_by_email("coach@club.example")
        assert user is not None
        assert FakePasswordHasher().verify(NEW_PASSWORD, user.password_hash or "")

    async def test_the_old_password_no_longer_works(self) -> None:
        uow = UnitOfWorkStub()
        sender = RecordingEmailSender()
        await _active_user(uow, sender)
        sender.messages.clear()
        await request_password_reset(
            uow,
            SETTINGS,
            email="coach@club.example",
            email_sender=sender,
            limiter=FakeRateLimiter(),
            client_key="203.0.113.0",
        )
        await reset_password(
            uow,
            SETTINGS,
            token=token_from(sender.messages[0]),
            new_password=NEW_PASSWORD,
            hasher=FakePasswordHasher(),
            limiter=FakeRateLimiter(),
            client_key="203.0.113.0",
        )

        with pytest.raises(AuthenticationError):
            await _open_session(uow)

    async def test_a_reset_token_cannot_be_reused(self) -> None:
        uow = UnitOfWorkStub()
        sender = RecordingEmailSender()
        await _active_user(uow, sender)
        sender.messages.clear()
        await request_password_reset(
            uow,
            SETTINGS,
            email="coach@club.example",
            email_sender=sender,
            limiter=FakeRateLimiter(),
            client_key="203.0.113.0",
        )
        token = token_from(sender.messages[0])
        await reset_password(
            uow,
            SETTINGS,
            token=token,
            new_password=NEW_PASSWORD,
            hasher=FakePasswordHasher(),
            limiter=FakeRateLimiter(),
            client_key="203.0.113.0",
        )

        with pytest.raises(ValidationError):
            await reset_password(
                uow,
                SETTINGS,
                token=token,
                new_password="another-one-9",
                hasher=FakePasswordHasher(),
                limiter=FakeRateLimiter(),
                client_key="203.0.113.0",
            )

    async def test_an_expired_reset_token_is_rejected(self) -> None:
        uow = UnitOfWorkStub()
        sender = RecordingEmailSender()
        await _active_user(uow, sender)
        sender.messages.clear()
        await request_password_reset(
            uow,
            SETTINGS,
            email="coach@club.example",
            email_sender=sender,
            limiter=FakeRateLimiter(),
            client_key="203.0.113.0",
        )
        uow.challenges._challenges[-1].expires_at = utcnow() - timedelta(seconds=1)

        with pytest.raises(ValidationError):
            await reset_password(
                uow,
                SETTINGS,
                token=token_from(sender.messages[0]),
                new_password=NEW_PASSWORD,
                hasher=FakePasswordHasher(),
                limiter=FakeRateLimiter(),
                client_key="203.0.113.0",
            )

    async def test_reset_records_a_security_event(self) -> None:
        uow = UnitOfWorkStub()
        sender = RecordingEmailSender()
        await _active_user(uow, sender)
        sender.messages.clear()
        await request_password_reset(
            uow,
            SETTINGS,
            email="coach@club.example",
            email_sender=sender,
            limiter=FakeRateLimiter(),
            client_key="203.0.113.0",
        )
        await reset_password(
            uow,
            SETTINGS,
            token=token_from(sender.messages[0]),
            new_password=NEW_PASSWORD,
            hasher=FakePasswordHasher(),
            limiter=FakeRateLimiter(),
            client_key="203.0.113.0",
        )

        events = [event.event_type for event in uow.security_events.events]
        assert SecurityEventType.PASSWORD_RESET_COMPLETED in events


class TestPasswordChange:
    async def test_changing_requires_the_current_password(self) -> None:
        uow = UnitOfWorkStub()
        user = await _active_user(uow, RecordingEmailSender())

        with pytest.raises(AuthenticationError):
            await change_password(
                uow,
                SETTINGS,
                user=user,
                current_password="not-the-password-1",
                new_password=NEW_PASSWORD,
                hasher=FakePasswordHasher(),
            )

    async def test_changing_revokes_other_sessions_but_keeps_the_caller(self) -> None:
        uow = UnitOfWorkStub()
        user = await _active_user(uow, RecordingEmailSender())
        first = await _open_session(uow)
        second = await _open_session(uow)

        revoked = await change_password(
            uow,
            SETTINGS,
            user=user,
            current_password=PASSWORD,
            new_password=NEW_PASSWORD,
            hasher=FakePasswordHasher(),
            keep_session_id=second.session.id,
        )

        assert revoked == 1
        assert first.session.is_revoked
        assert not second.session.is_revoked

    async def test_reusing_the_same_password_is_refused(self) -> None:
        uow = UnitOfWorkStub()
        user = await _active_user(uow, RecordingEmailSender())

        with pytest.raises(ValidationError):
            await change_password(
                uow,
                SETTINGS,
                user=user,
                current_password=PASSWORD,
                new_password=PASSWORD,
                hasher=FakePasswordHasher(),
            )

    async def test_changing_records_a_security_event(self) -> None:
        uow = UnitOfWorkStub()
        user = await _active_user(uow, RecordingEmailSender())

        await change_password(
            uow,
            SETTINGS,
            user=user,
            current_password=PASSWORD,
            new_password=NEW_PASSWORD,
            hasher=FakePasswordHasher(),
        )

        events = [event.event_type for event in uow.security_events.events]
        assert SecurityEventType.PASSWORD_CHANGED in events


class TestEmailChange:
    async def test_the_new_address_is_not_adopted_until_confirmed(self) -> None:
        uow = UnitOfWorkStub()
        sender = RecordingEmailSender()
        user = await _active_user(uow, sender)
        sender.messages.clear()

        await auth_use_cases.change_email(
            uow,
            SETTINGS,
            user=user,
            new_email="new@club.example",
            current_password=PASSWORD,
            hasher=FakePasswordHasher(),
            email_sender=sender,
        )

        stored = await uow.users.get(user.id)
        assert stored is not None
        assert stored.email.value == "coach@club.example"

    async def test_changing_requires_the_current_password(self) -> None:
        uow = UnitOfWorkStub()
        user = await _active_user(uow, RecordingEmailSender())

        with pytest.raises(AuthenticationError):
            await auth_use_cases.change_email(
                uow,
                SETTINGS,
                user=user,
                new_email="new@club.example",
                current_password="not-the-password-1",
                hasher=FakePasswordHasher(),
                email_sender=RecordingEmailSender(),
            )

    async def test_confirming_adopts_the_new_address(self) -> None:
        uow = UnitOfWorkStub()
        sender = RecordingEmailSender()
        user = await _active_user(uow, sender)
        sender.messages.clear()
        await auth_use_cases.change_email(
            uow,
            SETTINGS,
            user=user,
            new_email="new@club.example",
            current_password=PASSWORD,
            hasher=FakePasswordHasher(),
            email_sender=sender,
        )

        confirmation = next(m for m in sender.messages if m.to == "new@club.example")
        updated = await auth_use_cases.verify_email_change(
            uow, SETTINGS, token=token_from(confirmation)
        )

        assert updated.email.value == "new@club.example"
        assert updated.is_email_verified

    async def test_the_old_address_is_warned(self) -> None:
        uow = UnitOfWorkStub()
        sender = RecordingEmailSender()
        user = await _active_user(uow, sender)
        sender.messages.clear()

        await auth_use_cases.change_email(
            uow,
            SETTINGS,
            user=user,
            new_email="new@club.example",
            current_password=PASSWORD,
            hasher=FakePasswordHasher(),
            email_sender=sender,
        )

        assert any(message.to == "coach@club.example" for message in sender.messages)


class TestRecovery:
    async def test_recovery_needs_a_verified_phone(self) -> None:
        uow = UnitOfWorkStub()
        await _active_user(uow, RecordingEmailSender())

        issued = await start_recovery(
            uow,
            SETTINGS,
            email="coach@club.example",
            limiter=FakeRateLimiter(),
            client_key="203.0.113.0",
        )

        assert issued is False

    async def test_recovery_ends_every_session(self) -> None:
        uow = UnitOfWorkStub()
        sender = RecordingEmailSender()
        user = await _active_user(uow, sender)
        user.phone_number = "+447700900123"
        user.phone_verified_at = utcnow()
        await uow.users.update(user)
        session = await _open_session(uow)
        uow.otp_challenges._challenges.clear()

        from app.application.security import issue_otp
        from app.domain.security.entities import OtpPurpose

        code = await issue_otp(
            uow,
            SETTINGS,
            user_id=user.id,
            purpose=OtpPurpose.ACCOUNT_RECOVERY,
            destination=user.phone_number,
        )

        await complete_recovery(
            uow,
            SETTINGS,
            email="coach@club.example",
            code=code,
            new_password=NEW_PASSWORD,
            hasher=FakePasswordHasher(),
            limiter=FakeRateLimiter(),
            client_key="203.0.113.0",
        )

        assert session.session.is_revoked

    async def test_a_wrong_recovery_code_is_rejected(self) -> None:
        uow = UnitOfWorkStub()
        sender = RecordingEmailSender()
        user = await _active_user(uow, sender)
        user.phone_number = "+447700900123"
        user.phone_verified_at = utcnow()
        await uow.users.update(user)

        from app.application.security import issue_otp
        from app.domain.security.entities import OtpPurpose

        await issue_otp(
            uow,
            SETTINGS,
            user_id=user.id,
            purpose=OtpPurpose.ACCOUNT_RECOVERY,
            destination=user.phone_number,
        )

        with pytest.raises(ValidationError):
            await complete_recovery(
                uow,
                SETTINGS,
                email="coach@club.example",
                code="000000",
                new_password=NEW_PASSWORD,
                hasher=FakePasswordHasher(),
                limiter=FakeRateLimiter(),
                client_key="203.0.113.0",
            )

    async def test_a_suspended_account_cannot_be_recovered(self) -> None:
        uow = UnitOfWorkStub()
        sender = RecordingEmailSender()
        user = await _active_user(uow, sender)
        user.phone_number = "+447700900123"
        user.phone_verified_at = utcnow()
        user.account_status = AccountStatus(AccountStatus.SUSPENDED)
        await uow.users.update(user)

        from app.application.security import issue_otp
        from app.domain.security.entities import OtpPurpose

        code = await issue_otp(
            uow,
            SETTINGS,
            user_id=user.id,
            purpose=OtpPurpose.ACCOUNT_RECOVERY,
            destination=user.phone_number,
        )

        from app.core.errors import InvalidStateError

        with pytest.raises(InvalidStateError):
            await complete_recovery(
                uow,
                SETTINGS,
                email="coach@club.example",
                code=code,
                new_password=NEW_PASSWORD,
                hasher=FakePasswordHasher(),
                limiter=FakeRateLimiter(),
                client_key="203.0.113.0",
            )

    async def test_recovery_is_rate_limited(self) -> None:
        uow = UnitOfWorkStub()
        limiter = FakeRateLimiter()
        for _ in range(SETTINGS.rate_limit_password_reset_per_hour):
            await limiter.hit("spa:ratelimit:recovery:203.0.113.0", limit=10, window_seconds=3600)

        with pytest.raises(RateLimitedError):
            await start_recovery(
                uow,
                SETTINGS,
                email="coach@club.example",
                limiter=limiter,
                client_key="203.0.113.0",
            )
