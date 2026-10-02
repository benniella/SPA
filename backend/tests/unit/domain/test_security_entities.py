"""Session and challenge lifecycle.

The rules these assert are what make a server-controlled session authoritative:
expiry is absolute, revocation is immediate, and a consumed challenge cannot be
used twice.
"""

from __future__ import annotations

from datetime import timedelta

from app.domain.security.entities import (
    Challenge,
    ChallengeKind,
    OtpChallenge,
    OtpPurpose,
    Session,
    expiry_from,
)
from app.domain.shared import UserId, new_id, utcnow


def _user_id() -> UserId:
    return UserId(new_id())


class TestSession:
    def test_a_new_session_is_valid(self) -> None:
        session = Session(user_id=_user_id(), expires_at=expiry_from(timedelta(hours=1)))
        assert session.is_valid()

    def test_an_expired_session_is_not_valid(self) -> None:
        session = Session(user_id=_user_id(), expires_at=utcnow() - timedelta(seconds=1))
        assert not session.is_valid()
        assert session.is_expired()

    def test_a_revoked_session_is_not_valid(self) -> None:
        session = Session(user_id=_user_id(), expires_at=expiry_from(timedelta(hours=1)))
        session.revoke()
        assert not session.is_valid()
        assert session.is_revoked

    def test_revoking_twice_keeps_the_first_timestamp(self) -> None:
        session = Session(user_id=_user_id(), expires_at=expiry_from(timedelta(hours=1)))
        session.revoke()
        first = session.revoked_at
        session.revoke()
        assert session.revoked_at == first

    def test_touch_records_use(self) -> None:
        session = Session(user_id=_user_id(), expires_at=expiry_from(timedelta(hours=1)))
        before = session.last_used_at
        session.touch(at=before + timedelta(minutes=5))
        assert session.last_used_at > before

    def test_a_long_user_agent_is_truncated(self) -> None:
        session = Session(
            user_id=_user_id(),
            expires_at=expiry_from(timedelta(hours=1)),
            user_agent="x" * 1000,
        )
        assert session.user_agent is not None
        assert len(session.user_agent) == 300


class TestChallenge:
    def _challenge(self, **overrides: object) -> Challenge:
        defaults: dict[str, object] = {
            "user_id": _user_id(),
            "kind": ChallengeKind.EMAIL_VERIFICATION,
            "token_hash": "hash",
            "expires_at": expiry_from(timedelta(hours=1)),
        }
        defaults.update(overrides)
        return Challenge(**defaults)  # type: ignore[arg-type]

    def test_a_fresh_challenge_is_usable(self) -> None:
        assert self._challenge().is_usable()

    def test_a_consumed_challenge_is_not_usable(self) -> None:
        challenge = self._challenge()
        challenge.consume()
        assert not challenge.is_usable()
        assert challenge.is_consumed

    def test_an_expired_challenge_is_not_usable(self) -> None:
        challenge = self._challenge(expires_at=utcnow() - timedelta(seconds=1))
        assert not challenge.is_usable()


class TestOtpChallenge:
    def _otp(self, **overrides: object) -> OtpChallenge:
        defaults: dict[str, object] = {
            "user_id": _user_id(),
            "purpose": OtpPurpose.PHONE_VERIFICATION,
            "code_hash": "hash",
            "destination": "+447700900123",
            "expires_at": expiry_from(timedelta(minutes=10)),
            "max_attempts": 3,
        }
        defaults.update(overrides)
        return OtpChallenge(**defaults)  # type: ignore[arg-type]

    def test_a_fresh_code_is_usable(self) -> None:
        assert self._otp().is_usable()

    def test_attempts_exhaust_the_code(self) -> None:
        challenge = self._otp()
        for _ in range(3):
            challenge.register_attempt()
        assert challenge.attempts_exhausted
        assert not challenge.is_usable()

    def test_a_consumed_code_is_not_usable(self) -> None:
        challenge = self._otp()
        challenge.consume()
        assert not challenge.is_usable()

    def test_an_expired_code_is_not_usable(self) -> None:
        challenge = self._otp(expires_at=utcnow() - timedelta(seconds=1))
        assert not challenge.is_usable()
