"""Administrator MFA: enrolment, verification and recovery codes.

The TOTP algorithm and the secret encryption already exist; this module is only
the orchestration around them. Enrolment deliberately does not mark the
credential confirmed, and does not activate the administrator: a secret that has
been generated but never proven is not a second factor.
"""

from __future__ import annotations

import secrets
import string
from dataclasses import dataclass
from datetime import datetime, timedelta

from app.application.admin_authz import audit_event
from app.application.ports.admin import AdminMfaRepository, AdminRepository
from app.application.ports.repositories import SecurityEventRepository, SessionRepository
from app.core.errors import ConflictError, NotFoundError
from app.domain.admin import totp
from app.domain.admin.entities import AdminIdentity, AdminMfaChallenge, AdminStatus
from app.domain.security.entities import SecurityEventType, Session, SessionId
from app.domain.security.tokens import (
    decrypt_secret,
    encrypt_secret,
    hash_otp,
)
from app.domain.shared import UserId, utcnow

RECOVERY_CODE_COUNT = 10
RECOVERY_CODE_BYTES = 5
CHALLENGE_TTL = timedelta(minutes=5)
CHALLENGE_MAX_ATTEMPTS = 5
ACCENT_ALPHABET = string.ascii_uppercase + string.digits


@dataclass(frozen=True, slots=True)
class EnrollmentMaterial:
    """What the administrator needs once, to configure an authenticator."""

    secret: str
    provisioning_uri: str


@dataclass(frozen=True, slots=True)
class IssuedRecoveryCodes:
    """Recovery codes, returned only at the moment they are generated."""

    codes: list[str]


async def begin_enrollment(
    admin: AdminIdentity,
    *,
    admin_mfa: AdminMfaRepository,
    issuer: str,
    token_secret: str,
) -> EnrollmentMaterial:
    """Generate and store a new TOTP secret for an administrator.

    Any previously generated credential is replaced, so re-enrolling does not
    leave an old authenticator able to satisfy the second factor.
    """
    if admin.is_mfa_enrolled:
        raise ConflictError("A second factor is already enrolled for this administrator.")

    secret = totp.generate_secret()
    await admin_mfa.set_secret(
        admin.id, secret_encrypted=encrypt_secret(secret, secret=token_secret)
    )
    return EnrollmentMaterial(
        secret=secret,
        provisioning_uri=totp.provisioning_uri(
            secret=secret, account=str(admin.user_id), issuer=issuer
        ),
    )


async def confirm_enrollment(
    admin: AdminIdentity,
    code: str,
    *,
    admins: AdminRepository,
    admin_mfa: AdminMfaRepository,
    security_events: SecurityEventRepository,
    token_secret: str,
    timestamp: int,
    ip_prefix: str | None = None,
    user_agent: str | None = None,
) -> AdminIdentity:
    """Verify the first code and only then mark the second factor real.

    Confirmation is what activates an invited administrator. Until this succeeds
    the record stays INVITED and no administrative request can be authorized.
    """
    stored = await admin_mfa.get_secret(admin.id)
    if stored is None:
        raise ConflictError("No second factor is pending enrolment for this administrator.")

    secret = decrypt_secret(stored, secret=token_secret)
    if not totp.verify(secret, code, timestamp=timestamp):
        raise ConflictError("That code is not valid.")

    await admin_mfa.confirm(admin.id)
    await security_events.add(
        audit_event(
            SecurityEventType.ADMIN_MFA_ENROLLED,
            actor=admin.user_id,
            target_admin_id=admin.id,
            ip_prefix=ip_prefix,
            user_agent=user_agent,
        )
    )

    activated = AdminIdentity(
        user_id=admin.user_id,
        status=AdminStatus(AdminStatus.ACTIVE),
        id=admin.id,
        mfa_enrolled_at=utcnow(),
        created_at=admin.created_at,
        updated_at=utcnow(),
    )
    await admins.update(activated)
    return activated


async def start_challenge(
    admin: AdminIdentity,
    *,
    session_id: SessionId,
    admin_mfa: AdminMfaRepository,
    now: datetime | None = None,
) -> AdminMfaChallenge:
    started = now or utcnow()
    await admin_mfa.start_challenge(
        admin.id,
        session_id=session_id,
        expires_at=started + CHALLENGE_TTL,
        max_attempts=CHALLENGE_MAX_ATTEMPTS,
    )
    challenge = await admin_mfa.get_challenge(admin.id, session_id)
    if challenge is None:
        raise ConflictError("Could not start a second-factor challenge.")
    return challenge


async def satisfy_challenge_with_totp(
    admin: AdminIdentity,
    *,
    session_id: SessionId,
    code: str,
    admin_mfa: AdminMfaRepository,
    sessions: SessionRepository,
    security_events: SecurityEventRepository,
    token_secret: str,
    timestamp: int,
    ip_prefix: str | None = None,
    user_agent: str | None = None,
) -> None:
    """Verify a TOTP code against the live challenge and grant session assurance.

    The session is resolved and proven to belong to this administrator before the
    code is examined, so a caller cannot use this to test codes against a session
    that is not theirs.
    """
    session = await _require_own_session(sessions, admin=admin, session_id=session_id)
    secret = await _require_secret(admin, admin_mfa=admin_mfa, token_secret=token_secret)
    challenge = await _require_challenge(admin, session_id=session_id, admin_mfa=admin_mfa)

    if not totp.verify(secret, code, timestamp=timestamp):
        await admin_mfa.record_challenge_attempt(challenge.id, attempts=challenge.attempts + 1)
        raise ConflictError("That code is not valid.")

    await admin_mfa.satisfy_challenge(challenge.id)
    await _grant_session_assurance(
        admin,
        session=session,
        sessions=sessions,
        security_events=security_events,
        event_type=SecurityEventType.ADMIN_MFA_VERIFIED,
        ip_prefix=ip_prefix,
        user_agent=user_agent,
    )


async def satisfy_challenge_with_recovery_code(
    admin: AdminIdentity,
    *,
    session_id: SessionId,
    code: str,
    admin_mfa: AdminMfaRepository,
    sessions: SessionRepository,
    security_events: SecurityEventRepository,
    token_secret: str,
    ip_prefix: str | None = None,
    user_agent: str | None = None,
) -> None:
    """Consume a recovery code, which is single-use by construction."""
    session = await _require_own_session(sessions, admin=admin, session_id=session_id)
    challenge = await _require_challenge(admin, session_id=session_id, admin_mfa=admin_mfa)
    del challenge

    candidate = hash_otp(_canonical(code), secret=token_secret)
    if not await admin_mfa.consume_recovery_code(admin.id, code_hash=candidate):
        raise ConflictError("That recovery code is not valid.")

    await _grant_session_assurance(
        admin,
        session=session,
        sessions=sessions,
        security_events=security_events,
        event_type=SecurityEventType.ADMIN_MFA_RECOVERY_USED,
        ip_prefix=ip_prefix,
        user_agent=user_agent,
    )


async def generate_recovery_codes(
    admin: AdminIdentity,
    *,
    admin_mfa: AdminMfaRepository,
    security_events: SecurityEventRepository,
    token_secret: str,
    actor: UserId | None = None,
    ip_prefix: str | None = None,
    user_agent: str | None = None,
) -> IssuedRecoveryCodes:
    """Replace every recovery code with a fresh set.

    Replacing rather than appending is what makes a regenerated set invalidate the
    previous one; the repository deletes before it inserts.
    """
    if not admin.is_mfa_enrolled:
        raise ConflictError("Enroll a second factor before generating recovery codes.")

    codes = [_new_recovery_code() for _ in range(RECOVERY_CODE_COUNT)]
    await admin_mfa.replace_recovery_codes(
        admin.id,
        code_hashes=[hash_otp(_canonical(code), secret=token_secret) for code in codes],
    )
    await security_events.add(
        audit_event(
            SecurityEventType.ADMIN_MFA_RECOVERY_CODES_REGENERATED,
            actor=actor or admin.user_id,
            target_admin_id=admin.id,
            metadata={"count": RECOVERY_CODE_COUNT},
            ip_prefix=ip_prefix,
            user_agent=user_agent,
        )
    )
    return IssuedRecoveryCodes(codes=codes)


def _new_recovery_code() -> str:
    raw = "".join(secrets.choice(ACCENT_ALPHABET) for _ in range(RECOVERY_CODE_BYTES * 2))
    return f"{raw[:RECOVERY_CODE_BYTES]}-{raw[RECOVERY_CODE_BYTES:]}"


def _canonical(code: str) -> str:
    return code.strip().upper().replace("-", "")


async def _require_secret(
    admin: AdminIdentity,
    *,
    admin_mfa: AdminMfaRepository,
    token_secret: str,
) -> str:
    stored = await admin_mfa.get_secret(admin.id)
    if stored is None or not admin.is_mfa_enrolled:
        raise NotFoundError("This administrator has no enrolled second factor.")
    return decrypt_secret(stored, secret=token_secret)


async def _require_challenge(
    admin: AdminIdentity,
    *,
    session_id: SessionId,
    admin_mfa: AdminMfaRepository,
) -> AdminMfaChallenge:
    challenge = await admin_mfa.get_challenge(admin.id, session_id)
    if challenge is None:
        raise ConflictError("No usable second-factor challenge for this session.")
    return challenge


async def _require_own_session(
    sessions: SessionRepository,
    *,
    admin: AdminIdentity,
    session_id: SessionId,
) -> Session:
    """The session, proven to belong to this administrator."""
    session = await sessions.get_for_user(session_id, admin.user_id)
    if session is None:
        raise NotFoundError("The session being verified no longer exists.")
    return session


async def _grant_session_assurance(
    admin: AdminIdentity,
    *,
    session: Session,
    sessions: SessionRepository,
    security_events: SecurityEventRepository,
    event_type: str,
    ip_prefix: str | None,
    user_agent: str | None,
) -> None:
    """Attach MFA assurance to the caller's own session."""
    session.satisfy_mfa()
    await sessions.update(session)
    await security_events.add(
        audit_event(
            event_type,
            actor=admin.user_id,
            target_admin_id=admin.id,
            ip_prefix=ip_prefix,
            user_agent=user_agent,
        )
    )
