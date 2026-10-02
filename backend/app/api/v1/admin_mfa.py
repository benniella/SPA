from __future__ import annotations

from fastapi import APIRouter, Request

from app.api.dependencies import (
    CurrentSessionDep,
    RateLimiterDep,
    SettingsDep,
    UnitOfWorkDep,
)
from app.application.admin_authz import AdminContext, effective_privileges
from app.application.ports.security import RateLimiter
from app.application.ports.unit_of_work import UnitOfWork
from app.application.use_cases import admin_mfa
from app.core.errors import AuthenticationError, PermissionDeniedError, RateLimitedError
from app.domain.admin.entities import AdminRole, AdminStatus
from app.domain.security.entities import Session, SessionId
from app.domain.shared import UserId, utcnow
from app.schemas.admin import (
    MfaChallengeStarted,
    MfaCodeSubmit,
    MfaEnrollment,
    MfaRecoveryCodes,
)
from app.schemas.common import ErrorResponse

router = APIRouter()

TOTP_ATTEMPT_LIMIT = (10, 900)
ENROLLMENT_LIMIT = (5, 3600)


async def _acting_admin(
    uow: UnitOfWork,
    user_id: UserId,
    session: Session | None,
) -> AdminContext:
    """The administrator performing the MFA operation, without MFA assurance.

    Invitation acceptance leaves an admin in the INVITED state, and that is the
    exact point where the MFA flow is expected to begin. We therefore allow the
    invited record through this boundary while still rejecting suspended and
    revoked administrators.
    """
    admin = await uow.admins.get_by_user(user_id)
    if admin is None:
        raise PermissionDeniedError("Platform administration is not available.")
    if admin.status in (AdminStatus.SUSPENDED, AdminStatus.REVOKED):
        raise PermissionDeniedError("This administrator account cannot act right now.")
    if admin.status not in (AdminStatus.ACTIVE, AdminStatus.INVITED):
        raise PermissionDeniedError("This administrator account cannot act right now.")

    roles = await uow.admin_roles.roles_for_admin(admin.id)
    is_superadmin = any(role == AdminRole.SUPERADMIN for role in roles)
    privileges = await effective_privileges(
        admin.id,
        roles=uow.admin_roles,
        privileges=uow.admin_privileges,
    )
    return AdminContext(admin=admin, privileges=privileges, is_superadmin=is_superadmin)


@router.post(
    "/mfa/enroll",
    response_model=MfaEnrollment,
    summary="Begin second-factor enrolment",
    responses={409: {"model": ErrorResponse, "description": "Already enrolled."}},
)
async def begin_enrollment(
    uow: UnitOfWorkDep,
    session: CurrentSessionDep,
    limiter: RateLimiterDep,
    settings: SettingsDep,
) -> MfaEnrollment:
    await _limit(
        limiter,
        "admin-mfa-enroll",
        limit=ENROLLMENT_LIMIT[0],
        window_seconds=ENROLLMENT_LIMIT[1],
    )
    async with uow:
        context = await _acting_admin(uow, _user_id(session), session)
        material = await admin_mfa.begin_enrollment(
            context.admin,
            admin_mfa=uow.admin_mfa,
            issuer=settings.project_name,
            token_secret=settings.session_secret,
        )
        await uow.commit()
    return MfaEnrollment(secret=material.secret, provisioning_uri=material.provisioning_uri)


@router.post(
    "/mfa/enroll/confirm",
    response_model=MfaChallengeStarted,
    summary="Confirm enrolment with the first valid code",
    responses={409: {"model": ErrorResponse, "description": "Invalid code."}},
)
async def confirm_enrollment(
    payload: MfaCodeSubmit,
    uow: UnitOfWorkDep,
    session: CurrentSessionDep,
    limiter: RateLimiterDep,
    settings: SettingsDep,
    request: Request,
) -> MfaChallengeStarted:
    await _limit(
        limiter,
        f"admin-mfa-confirm:{_key(session)}",
        limit=TOTP_ATTEMPT_LIMIT[0],
        window_seconds=TOTP_ATTEMPT_LIMIT[1],
    )
    async with uow:
        context = await _acting_admin(uow, _user_id(session), session)
        activated = await admin_mfa.confirm_enrollment(
            context.admin,
            payload.code,
            admins=uow.admins,
            admin_mfa=uow.admin_mfa,
            security_events=uow.security_events,
            token_secret=settings.session_secret,
            timestamp=_now_epoch(),
            ip_prefix=_ip_prefix(request),
        )
        await uow.commit()
    del activated
    return MfaChallengeStarted(expires_at=utcnow(), max_attempts=admin_mfa.CHALLENGE_MAX_ATTEMPTS)


@router.post(
    "/mfa/challenge",
    summary="Start a second-factor challenge for this session",
)
async def start_challenge(
    uow: UnitOfWorkDep, session: CurrentSessionDep, settings: SettingsDep
) -> dict[str, str]:
    async with uow:
        context = await _acting_admin(uow, _user_id(session), session)
        challenge = await admin_mfa.start_challenge(
            context.admin,
            session_id=_session_id(session),
            admin_mfa=uow.admin_mfa,
        )
        await uow.commit()
    return {"challenge_id": str(challenge.id), "expires_at": challenge.expires_at.isoformat()}


@router.post(
    "/mfa/challenge/totp",
    summary="Satisfy the challenge with a TOTP code",
    responses={403: {"model": ErrorResponse, "description": "Invalid or spent challenge."}},
)
async def satisfy_with_totp(
    payload: MfaCodeSubmit,
    uow: UnitOfWorkDep,
    session: CurrentSessionDep,
    limiter: RateLimiterDep,
    settings: SettingsDep,
    request: Request,
) -> dict[str, str]:
    await _limit(
        limiter,
        f"admin-mfa-totp:{_key(session)}",
        limit=TOTP_ATTEMPT_LIMIT[0],
        window_seconds=TOTP_ATTEMPT_LIMIT[1],
    )
    async with uow:
        context = await _acting_admin(uow, _user_id(session), session)
        await admin_mfa.satisfy_challenge_with_totp(
            context.admin,
            session_id=_session_id(session),
            code=payload.code,
            admin_mfa=uow.admin_mfa,
            sessions=uow.sessions,
            security_events=uow.security_events,
            token_secret=settings.session_secret,
            timestamp=_now_epoch(),
            ip_prefix=_ip_prefix(request),
        )
        await uow.commit()
    return {"status": "verified"}


@router.post(
    "/mfa/challenge/recovery-code",
    summary="Satisfy the challenge with a recovery code",
    responses={403: {"model": ErrorResponse, "description": "Invalid recovery code."}},
)
async def satisfy_with_recovery_code(
    payload: MfaCodeSubmit,
    uow: UnitOfWorkDep,
    session: CurrentSessionDep,
    limiter: RateLimiterDep,
    settings: SettingsDep,
    request: Request,
) -> dict[str, str]:
    await _limit(
        limiter,
        f"admin-mfa-recovery:{_key(session)}",
        limit=TOTP_ATTEMPT_LIMIT[0],
        window_seconds=TOTP_ATTEMPT_LIMIT[1],
    )
    async with uow:
        context = await _acting_admin(uow, _user_id(session), session)
        await admin_mfa.satisfy_challenge_with_recovery_code(
            context.admin,
            session_id=_session_id(session),
            code=payload.code,
            admin_mfa=uow.admin_mfa,
            sessions=uow.sessions,
            security_events=uow.security_events,
            token_secret=settings.session_secret,
            ip_prefix=_ip_prefix(request),
        )
        await uow.commit()
    return {"status": "verified"}


@router.post(
    "/mfa/recovery-codes",
    response_model=MfaRecoveryCodes,
    summary="Generate or rotate recovery codes",
)
async def generate_recovery_codes(
    uow: UnitOfWorkDep, session: CurrentSessionDep, settings: SettingsDep, request: Request
) -> MfaRecoveryCodes:
    async with uow:
        context = await _acting_admin(uow, _user_id(session), session)
        issued = await admin_mfa.generate_recovery_codes(
            context.admin,
            admin_mfa=uow.admin_mfa,
            security_events=uow.security_events,
            token_secret=settings.session_secret,
            ip_prefix=_ip_prefix(request),
        )
        await uow.commit()
    return MfaRecoveryCodes(codes=issued.codes)


async def _limit(limiter: RateLimiter, key: str, *, limit: int, window_seconds: int) -> None:
    decision = await limiter.hit(key, limit=limit, window_seconds=window_seconds)
    if not decision.allowed:
        raise RateLimitedError(
            "Too many attempts. Try again shortly.",
            retry_after_seconds=decision.retry_after_seconds,
        )


def _user_id(session: Session | None) -> UserId:
    if session is None:
        raise AuthenticationError("An authenticated session is required.")
    return session.user_id


def _session_id(session: Session | None) -> SessionId:
    if session is None:
        raise AuthenticationError("An authenticated session is required.")
    return session.id


def _key(session: Session | None) -> str:
    return "anonymous" if session is None else str(session.id)


def _now_epoch() -> int:
    return int(utcnow().timestamp())


def _ip_prefix(request: Request) -> str | None:
    client = request.client
    return client.host if client else None
