"""Administrator MFA enrolment, verification and recovery codes."""

from __future__ import annotations

from datetime import timedelta

import pytest

from app.application.use_cases.admin_mfa import (
    CHALLENGE_MAX_ATTEMPTS,
    begin_enrollment,
    confirm_enrollment,
    generate_recovery_codes,
    satisfy_challenge_with_recovery_code,
    satisfy_challenge_with_totp,
    start_challenge,
)
from app.core.errors import ConflictError, NotFoundError
from app.domain.admin import totp
from app.domain.admin.entities import AdminIdentity, AdminStatus
from app.domain.security.entities import SecurityEventType, Session, SessionId
from app.domain.security.tokens import decrypt_secret
from app.domain.shared import UserId, new_id, utcnow
from tests.unit.application.fakes import (
    FakeAdminMfaRepository,
    FakeAdminRepository,
)
from tests.unit.application.security_fakes import (
    FakeSecurityEventRepository,
    FakeSessionRepository,
)

TOKEN_SECRET = "test-secret"
ISSUER = "SPA"
NOW = 1_700_000_000


class Harness:
    def __init__(self) -> None:
        self.admins = FakeAdminRepository()
        self.admin_mfa = FakeAdminMfaRepository()
        self.sessions = FakeSessionRepository()
        self.events = FakeSecurityEventRepository()

    async def invited_admin(self) -> AdminIdentity:
        admin = AdminIdentity(
            user_id=UserId(new_id()),
            status=AdminStatus(AdminStatus.INVITED),
        )
        await self.admins.add(admin)
        return admin

    async def enrolled_admin(self) -> tuple[AdminIdentity, str]:
        admin = await self.invited_admin()
        material = await begin_enrollment(
            admin,
            admin_mfa=self.admin_mfa,
            issuer=ISSUER,
            token_secret=TOKEN_SECRET,
        )
        activated = await confirm_enrollment(
            admin,
            totp.code_at(material.secret, timestamp=NOW),
            admins=self.admins,
            admin_mfa=self.admin_mfa,
            security_events=self.events,
            token_secret=TOKEN_SECRET,
            timestamp=NOW,
        )
        return activated, material.secret

    async def session_for(self, admin: AdminIdentity) -> SessionId:
        session = Session(
            user_id=admin.user_id,
            expires_at=utcnow() + timedelta(hours=1),
            id=SessionId(new_id()),
        )
        await self.sessions.add(session, token_hash=f"hash-{session.id}")
        return session.id


@pytest.fixture
def harness() -> Harness:
    return Harness()


class TestEnrollment:
    async def test_enrollment_returns_material_without_confirming(
        self, harness: Harness
    ) -> None:
        admin = await harness.invited_admin()

        material = await begin_enrollment(
            admin, admin_mfa=harness.admin_mfa, issuer=ISSUER, token_secret=TOKEN_SECRET
        )

        assert material.provisioning_uri.startswith("otpauth://totp/")
        assert material.secret in material.provisioning_uri
        assert not await harness.admin_mfa.is_confirmed(admin.id)

    async def test_the_secret_is_encrypted_at_rest(self, harness: Harness) -> None:
        admin = await harness.invited_admin()
        material = await begin_enrollment(
            admin, admin_mfa=harness.admin_mfa, issuer=ISSUER, token_secret=TOKEN_SECRET
        )

        stored = await harness.admin_mfa.get_secret(admin.id)
        assert stored is not None
        assert material.secret not in stored
        assert decrypt_secret(stored, secret=TOKEN_SECRET) == material.secret

    async def test_confirmation_requires_a_valid_code(self, harness: Harness) -> None:
        admin = await harness.invited_admin()
        await begin_enrollment(
            admin, admin_mfa=harness.admin_mfa, issuer=ISSUER, token_secret=TOKEN_SECRET
        )

        with pytest.raises(ConflictError):
            await confirm_enrollment(
                admin,
                "000000",
                admins=harness.admins,
                admin_mfa=harness.admin_mfa,
                security_events=harness.events,
                token_secret=TOKEN_SECRET,
                timestamp=NOW,
            )
        assert not await harness.admin_mfa.is_confirmed(admin.id)

    async def test_confirmation_activates_and_audits(self, harness: Harness) -> None:
        admin = await harness.invited_admin()
        material = await begin_enrollment(
            admin, admin_mfa=harness.admin_mfa, issuer=ISSUER, token_secret=TOKEN_SECRET
        )

        activated = await confirm_enrollment(
            admin,
            totp.code_at(material.secret, timestamp=NOW),
            admins=harness.admins,
            admin_mfa=harness.admin_mfa,
            security_events=harness.events,
            token_secret=TOKEN_SECRET,
            timestamp=NOW,
        )

        assert activated.status == AdminStatus.ACTIVE
        assert activated.is_mfa_enrolled
        assert any(
            e.event_type == SecurityEventType.ADMIN_MFA_ENROLLED for e in harness.events.events
        )

    async def test_enrolling_twice_conflicts(self, harness: Harness) -> None:
        admin, _ = await harness.enrolled_admin()
        with pytest.raises(ConflictError):
            await begin_enrollment(
                admin, admin_mfa=harness.admin_mfa, issuer=ISSUER, token_secret=TOKEN_SECRET
            )

    async def test_confirming_without_a_pending_secret_is_a_conflict(
        self, harness: Harness
    ) -> None:
        admin = await harness.invited_admin()
        with pytest.raises(ConflictError):
            await confirm_enrollment(
                admin,
                "123456",
                admins=harness.admins,
                admin_mfa=harness.admin_mfa,
                security_events=harness.events,
                token_secret=TOKEN_SECRET,
                timestamp=NOW,
            )


class TestChallenge:
    async def test_a_valid_code_satisfies_the_challenge_and_the_session(
        self, harness: Harness
    ) -> None:
        admin, secret = await harness.enrolled_admin()
        session_id = await harness.session_for(admin)
        await start_challenge(admin, session_id=session_id, admin_mfa=harness.admin_mfa)

        await satisfy_challenge_with_totp(
            admin,
            session_id=session_id,
            code=totp.code_at(secret, timestamp=NOW),
            admin_mfa=harness.admin_mfa,
            sessions=harness.sessions,
            security_events=harness.events,
            token_secret=TOKEN_SECRET,
            timestamp=NOW,
        )

        session = await harness.sessions.get_for_user(session_id, admin.user_id)
        assert session is not None and session.is_mfa_verified
        assert any(
            e.event_type == SecurityEventType.ADMIN_MFA_VERIFIED for e in harness.events.events
        )

    async def test_assurance_is_not_granted_to_another_users_session(
        self, harness: Harness
    ) -> None:
        admin, _ = await harness.enrolled_admin()
        other_admin, _ = await harness.enrolled_admin()
        other_session = await harness.session_for(other_admin)
        await start_challenge(admin, session_id=other_session, admin_mfa=harness.admin_mfa)

        with pytest.raises(NotFoundError):
            await satisfy_challenge_with_totp(
                admin,
                session_id=other_session,
                code="123456",
                admin_mfa=harness.admin_mfa,
                sessions=harness.sessions,
                security_events=harness.events,
                token_secret=TOKEN_SECRET,
                timestamp=NOW,
            )

    async def test_an_invalid_code_records_an_attempt(self, harness: Harness) -> None:
        admin, _secret = await harness.enrolled_admin()
        session_id = await harness.session_for(admin)
        await start_challenge(admin, session_id=session_id, admin_mfa=harness.admin_mfa)

        with pytest.raises(ConflictError):
            await satisfy_challenge_with_totp(
                admin,
                session_id=session_id,
                code="000000",
                admin_mfa=harness.admin_mfa,
                sessions=harness.sessions,
                security_events=harness.events,
                token_secret=TOKEN_SECRET,
                timestamp=NOW,
            )

        challenge = await harness.admin_mfa.get_challenge(admin.id, session_id)
        assert challenge is not None and challenge.attempts == 1

    async def test_an_exhausted_challenge_is_never_returned(self, harness: Harness) -> None:
        """Regression: the repository must not surface a spent challenge."""
        admin, secret = await harness.enrolled_admin()
        session_id = await harness.session_for(admin)
        await start_challenge(admin, session_id=session_id, admin_mfa=harness.admin_mfa)

        challenge = await harness.admin_mfa.get_challenge(admin.id, session_id)
        assert challenge is not None
        await harness.admin_mfa.record_challenge_attempt(
            challenge.id, attempts=CHALLENGE_MAX_ATTEMPTS
        )

        assert await harness.admin_mfa.get_challenge(admin.id, session_id) is None
        with pytest.raises(ConflictError):
            await satisfy_challenge_with_totp(
                admin,
                session_id=session_id,
                code=totp.code_at(secret, timestamp=NOW),
                admin_mfa=harness.admin_mfa,
                sessions=harness.sessions,
                security_events=harness.events,
                token_secret=TOKEN_SECRET,
                timestamp=NOW,
            )

    async def test_a_satisfied_challenge_cannot_be_reused(self, harness: Harness) -> None:
        admin, secret = await harness.enrolled_admin()
        session_id = await harness.session_for(admin)
        await start_challenge(admin, session_id=session_id, admin_mfa=harness.admin_mfa)
        await satisfy_challenge_with_totp(
            admin,
            session_id=session_id,
            code=totp.code_at(secret, timestamp=NOW),
            admin_mfa=harness.admin_mfa,
            sessions=harness.sessions,
            security_events=harness.events,
            token_secret=TOKEN_SECRET,
            timestamp=NOW,
        )

        with pytest.raises(ConflictError):
            await satisfy_challenge_with_totp(
                admin,
                session_id=session_id,
                code=totp.code_at(secret, timestamp=NOW),
                admin_mfa=harness.admin_mfa,
                sessions=harness.sessions,
                security_events=harness.events,
                token_secret=TOKEN_SECRET,
                timestamp=NOW,
            )

    async def test_an_expired_challenge_is_refused(self, harness: Harness) -> None:
        admin, secret = await harness.enrolled_admin()
        session_id = await harness.session_for(admin)
        await harness.admin_mfa.start_challenge(
            admin.id,
            session_id=session_id,
            expires_at=utcnow() - timedelta(seconds=1),
            max_attempts=CHALLENGE_MAX_ATTEMPTS,
        )

        with pytest.raises(ConflictError):
            await satisfy_challenge_with_totp(
                admin,
                session_id=session_id,
                code=totp.code_at(secret, timestamp=NOW),
                admin_mfa=harness.admin_mfa,
                sessions=harness.sessions,
                security_events=harness.events,
                token_secret=TOKEN_SECRET,
                timestamp=NOW,
            )


class TestRecoveryCodes:
    async def test_generation_returns_plaintext_once_and_stores_hashes(
        self, harness: Harness
    ) -> None:
        admin, _ = await harness.enrolled_admin()

        issued = await generate_recovery_codes(
            admin,
            admin_mfa=harness.admin_mfa,
            security_events=harness.events,
            token_secret=TOKEN_SECRET,
        )

        assert len(issued.codes) == 10
        stored = harness.admin_mfa._recovery_codes[admin.id]
        assert all(code not in str(stored) for code in issued.codes)
        assert any(
            e.event_type == SecurityEventType.ADMIN_MFA_RECOVERY_CODES_REGENERATED
            for e in harness.events.events
        )

    async def test_a_recovery_code_satisfies_a_challenge(self, harness: Harness) -> None:
        admin, _ = await harness.enrolled_admin()
        issued = await generate_recovery_codes(
            admin,
            admin_mfa=harness.admin_mfa,
            security_events=harness.events,
            token_secret=TOKEN_SECRET,
        )
        session_id = await harness.session_for(admin)
        await start_challenge(admin, session_id=session_id, admin_mfa=harness.admin_mfa)

        await satisfy_challenge_with_recovery_code(
            admin,
            session_id=session_id,
            code=issued.codes[0],
            admin_mfa=harness.admin_mfa,
            sessions=harness.sessions,
            security_events=harness.events,
            token_secret=TOKEN_SECRET,
        )

        session = await harness.sessions.get_for_user(session_id, admin.user_id)
        assert session is not None and session.is_mfa_verified
        assert any(
            e.event_type == SecurityEventType.ADMIN_MFA_RECOVERY_USED
            for e in harness.events.events
        )

    async def test_a_recovery_code_cannot_be_used_twice(self, harness: Harness) -> None:
        admin, _ = await harness.enrolled_admin()
        issued = await generate_recovery_codes(
            admin,
            admin_mfa=harness.admin_mfa,
            security_events=harness.events,
            token_secret=TOKEN_SECRET,
        )
        first = await harness.session_for(admin)
        await start_challenge(admin, session_id=first, admin_mfa=harness.admin_mfa)
        await satisfy_challenge_with_recovery_code(
            admin,
            session_id=first,
            code=issued.codes[0],
            admin_mfa=harness.admin_mfa,
            sessions=harness.sessions,
            security_events=harness.events,
            token_secret=TOKEN_SECRET,
        )
        second = await harness.session_for(admin)
        await start_challenge(admin, session_id=second, admin_mfa=harness.admin_mfa)

        with pytest.raises(ConflictError):
            await satisfy_challenge_with_recovery_code(
                admin,
                session_id=second,
                code=issued.codes[0],
                admin_mfa=harness.admin_mfa,
                sessions=harness.sessions,
                security_events=harness.events,
                token_secret=TOKEN_SECRET,
            )

    async def test_regeneration_invalidates_previous_codes(self, harness: Harness) -> None:
        admin, _ = await harness.enrolled_admin()
        first = await generate_recovery_codes(
            admin,
            admin_mfa=harness.admin_mfa,
            security_events=harness.events,
            token_secret=TOKEN_SECRET,
        )
        second = await generate_recovery_codes(
            admin,
            admin_mfa=harness.admin_mfa,
            security_events=harness.events,
            token_secret=TOKEN_SECRET,
        )
        session_id = await harness.session_for(admin)
        await start_challenge(admin, session_id=session_id, admin_mfa=harness.admin_mfa)

        with pytest.raises(ConflictError):
            await satisfy_challenge_with_recovery_code(
                admin,
                session_id=session_id,
                code=first.codes[0],
                admin_mfa=harness.admin_mfa,
                sessions=harness.sessions,
                security_events=harness.events,
                token_secret=TOKEN_SECRET,
            )

        await satisfy_challenge_with_recovery_code(
            admin,
            session_id=session_id,
            code=second.codes[0],
            admin_mfa=harness.admin_mfa,
            sessions=harness.sessions,
            security_events=harness.events,
            token_secret=TOKEN_SECRET,
        )

    async def test_codes_require_an_enrolled_second_factor(self, harness: Harness) -> None:
        admin = await harness.invited_admin()
        with pytest.raises(ConflictError):
            await generate_recovery_codes(
                admin,
                admin_mfa=harness.admin_mfa,
                security_events=harness.events,
                token_secret=TOKEN_SECRET,
            )
