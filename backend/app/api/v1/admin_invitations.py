from __future__ import annotations

from fastapi import APIRouter, Request

from app.api.admin_dependencies import AdminDep
from app.api.dependencies import (
    CurrentUserDep,
    EmailSenderDep,
    RateLimiterDep,
    SettingsDep,
    UnitOfWorkDep,
)
from app.application.ports.security import RateLimiter
from app.application.use_cases import admin_invitations
from app.core.errors import RateLimitedError
from app.schemas.admin import InvitationAccepted, InvitationCreate, InvitationToken
from app.schemas.common import ErrorResponse

router = APIRouter()

# The resend cooldown the application layer deliberately leaves to the API.
RESEND_COOLDOWN_SECONDS = 300
INVITATION_RATE_LIMIT = (20, 3600)


@router.post(
    "/invitations",
    status_code=202,
    summary="Invite a platform administrator",
    responses={
        403: {"model": ErrorResponse, "description": "Not permitted."},
        409: {"model": ErrorResponse, "description": "An active invitation already exists."},
    },
)
async def create_invitation(
    payload: InvitationCreate,
    admin: AdminDep,
    uow: UnitOfWorkDep,
    limiter: RateLimiterDep,
    settings: SettingsDep,
    email_sender: EmailSenderDep,
    request: Request,
) -> dict[str, str]:
    await _limit(
        limiter,
        f"admin-invite:{admin.admin.user_id}",
        limit=INVITATION_RATE_LIMIT[0],
        window_seconds=INVITATION_RATE_LIMIT[1],
    )
    async with uow:
        issued = await admin_invitations.create_invitation(
            admin,
            email=str(payload.email),
            role_name=payload.role,
            roles=uow.admin_roles,
            invitations=uow.admin_invitations,
            security_events=uow.security_events,
            email_sender=email_sender,
            token_secret=settings.session_secret,
            app_base_url=settings.app_base_url,
            ip_prefix=_ip_prefix(request),
        )
        await uow.commit()
    return {"invitation_id": str(issued.invitation.id), "status": "pending"}


@router.post(
    "/invitations/{invitation_id}/resend",
    status_code=202,
    summary="Resend an outstanding invitation with a fresh token",
    responses={
        409: {"model": ErrorResponse, "description": "Invitation is not outstanding."},
        429: {"model": ErrorResponse, "description": "Resent too recently."},
    },
)
async def resend_invitation(
    invitation_id: str,
    admin: AdminDep,
    uow: UnitOfWorkDep,
    limiter: RateLimiterDep,
    settings: SettingsDep,
    email_sender: EmailSenderDep,
    request: Request,
) -> dict[str, str]:
    await _limit(
        limiter,
        f"admin-invite-resend:{invitation_id}",
        limit=1,
        window_seconds=RESEND_COOLDOWN_SECONDS,
    )
    async with uow:
        issued = await admin_invitations.resend_invitation(
            admin,
            invitation_id,
            invitations=uow.admin_invitations,
            security_events=uow.security_events,
            email_sender=email_sender,
            token_secret=settings.session_secret,
            app_base_url=settings.app_base_url,
            ip_prefix=_ip_prefix(request),
        )
        await uow.commit()
    return {"invitation_id": str(issued.invitation.id), "status": "pending"}


@router.post(
    "/invitations/{invitation_id}/revoke",
    summary="Revoke an invitation",
    responses={404: {"model": ErrorResponse, "description": "Not found."}},
)
async def revoke_invitation(
    invitation_id: str,
    admin: AdminDep,
    uow: UnitOfWorkDep,
    request: Request,
) -> dict[str, str]:
    async with uow:
        invitation = await admin_invitations.revoke_invitation(
            admin,
            invitation_id,
            invitations=uow.admin_invitations,
            security_events=uow.security_events,
            ip_prefix=_ip_prefix(request),
        )
        await uow.commit()
    return {"invitation_id": str(invitation.id), "status": "revoked"}


@router.post(
    "/invitations/accept",
    response_model=InvitationAccepted,
    summary="Accept an invitation (authenticated invitee)",
    responses={409: {"model": ErrorResponse, "description": "Invitation is not usable."}},
)
async def accept_invitation(
    payload: InvitationToken,
    user: CurrentUserDep,
    uow: UnitOfWorkDep,
    limiter: RateLimiterDep,
    settings: SettingsDep,
    request: Request,
) -> InvitationAccepted:
    await _limit(limiter, f"admin-invite-accept:{user.id}", limit=10, window_seconds=3600)
    async with uow:
        accepted = await admin_invitations.accept_invitation(
            token=payload.token,
            user_id=user.id,
            invitations=uow.admin_invitations,
            admins=uow.admins,
            roles=uow.admin_roles,
            users=uow.users,
            security_events=uow.security_events,
            token_secret=settings.session_secret,
            ip_prefix=_ip_prefix(request),
        )
        await uow.commit()
    return InvitationAccepted(administrator_id=accepted.admin.id, status=str(accepted.admin.status))


async def _limit(limiter: RateLimiter, key: str, *, limit: int, window_seconds: int) -> None:
    decision = await limiter.hit(key, limit=limit, window_seconds=window_seconds)
    if not decision.allowed:
        raise RateLimitedError(
            "Too many attempts. Try again shortly.",
            retry_after_seconds=decision.retry_after_seconds,
        )


def _ip_prefix(request: Request) -> str | None:
    client = request.client
    return client.host if client else None
