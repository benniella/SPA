"""Authentication endpoints.

Every response that could reveal whether an address has an account is
deliberately identical for both outcomes, and no endpoint returns a token: the
session token travels in an HttpOnly cookie, and verification, reset and OTP
codes travel only through their delivery channel.
"""

from __future__ import annotations

from fastapi import APIRouter, Response, status

from app.api.cookies import (
    clear_csrf_cookie,
    clear_session_cookie,
    set_csrf_cookie,
    set_session_cookie,
)
from app.api.dependencies import (
    CallerKeyDep,
    CurrentUserDep,
    EmailSenderDep,
    PasswordHasherDep,
    RateLimiterDep,
    SecurityContextDep,
    SessionCookieDep,
    SettingsDep,
    UnitOfWorkDep,
)
from app.api.v1.account_presenters import resolve_memberships, user_payload
from app.application.use_cases import authentication as use_cases
from app.core.errors import NotFoundError
from app.domain.security.tokens import generate_token
from app.schemas.auth import (
    AuthenticatedUser,
    EmailRequest,
    LoginRequest,
    MessageAccepted,
    PasswordChangeRequest,
    PasswordResetRequest,
    RegisterRequest,
    RegistrationAccepted,
    TokenRequest,
)
from app.schemas.common import ErrorResponse

router = APIRouter()

RESEND_RESPONSE = {
    "description": (
        "Always accepted, whether or not the address belongs to an account, so "
        "the endpoint cannot be used to enumerate registered users."
    )
}


@router.post(
    "/register",
    response_model=RegistrationAccepted,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Register an account and its first workspace",
    responses={429: {"model": ErrorResponse, "description": "Too many attempts."}},
)
async def register(
    payload: RegisterRequest,
    uow: UnitOfWorkDep,
    settings: SettingsDep,
    hasher: PasswordHasherDep,
    limiter: RateLimiterDep,
    caller: CallerKeyDep,
    context: SecurityContextDep,
    email_sender: EmailSenderDep,
    response: Response,
) -> RegistrationAccepted:
    result = await use_cases.register_user(
        uow,
        settings,
        email=str(payload.email),
        password=payload.password,
        display_name=payload.display_name,
        organization_name=payload.organization_name,
        organization_slug=payload.organization_slug,
        hasher=hasher,
        limiter=limiter,
        client_key=caller,
        email_sender=email_sender,
        context=context,
    )
    del result

    set_csrf_cookie(response, settings, token=generate_token())
    return RegistrationAccepted()


@router.post(
    "/login",
    response_model=AuthenticatedUser,
    summary="Sign in",
    responses={
        401: {"model": ErrorResponse, "description": "Credentials rejected."},
        403: {"model": ErrorResponse, "description": "Account cannot sign in."},
        429: {"model": ErrorResponse, "description": "Too many attempts."},
    },
)
async def login(
    payload: LoginRequest,
    response: Response,
    uow: UnitOfWorkDep,
    settings: SettingsDep,
    hasher: PasswordHasherDep,
    limiter: RateLimiterDep,
    caller: CallerKeyDep,
    context: SecurityContextDep,
    email_sender: EmailSenderDep,
) -> AuthenticatedUser:
    issued = await use_cases.login(
        uow,
        settings,
        email=str(payload.email),
        password=payload.password,
        hasher=hasher,
        limiter=limiter,
        client_key=caller,
        email_sender=email_sender,
        context=context,
    )
    set_session_cookie(response, settings, token=issued.token)
    set_csrf_cookie(response, settings, token=generate_token())

    async with uow:
        user = await uow.users.get(issued.session.user_id)
        organizations = await resolve_memberships(uow, issued.session.user_id)
    if user is None:  # pragma: no cover - the session proves the user exists
        raise NotFoundError("The account no longer exists.")
    return AuthenticatedUser.model_validate(user_payload(user, organizations))


@router.post(
    "/logout",
    response_model=MessageAccepted,
    summary="Sign out and revoke the current session",
)
async def logout(
    response: Response,
    uow: UnitOfWorkDep,
    settings: SettingsDep,
    token: SessionCookieDep,
    user: CurrentUserDep,
    context: SecurityContextDep,
) -> MessageAccepted:
    await use_cases.logout(
        uow, settings, session_token=token, user_id=user.id, context=context
    )
    clear_session_cookie(response, settings)
    clear_csrf_cookie(response, settings)
    return MessageAccepted()


@router.get(
    "/me",
    response_model=AuthenticatedUser,
    summary="The authenticated user",
    responses={401: {"model": ErrorResponse, "description": "Not authenticated."}},
)
async def me(user: CurrentUserDep, uow: UnitOfWorkDep) -> AuthenticatedUser:
    async with uow:
        organizations = await resolve_memberships(uow, user.id)
    return AuthenticatedUser.model_validate(user_payload(user, organizations))


@router.post(
    "/verify-email",
    response_model=AuthenticatedUser,
    summary="Verify an email address",
    responses={422: {"model": ErrorResponse, "description": "Invalid or expired token."}},
)
async def verify_email(
    payload: TokenRequest,
    uow: UnitOfWorkDep,
    settings: SettingsDep,
    context: SecurityContextDep,
) -> AuthenticatedUser:
    user = await use_cases.verify_email(uow, settings, token=payload.token, context=context)
    async with uow:
        organizations = await resolve_memberships(uow, user.id)
    return AuthenticatedUser.model_validate(user_payload(user, organizations))


@router.post(
    "/resend-verification",
    response_model=MessageAccepted,
    responses={429: {"model": ErrorResponse, "description": "Too many attempts."}},
)
async def resend_verification(
    payload: EmailRequest,
    uow: UnitOfWorkDep,
    settings: SettingsDep,
    email_sender: EmailSenderDep,
    limiter: RateLimiterDep,
    caller: CallerKeyDep,
    context: SecurityContextDep,
) -> MessageAccepted:
    await use_cases.resend_verification(
        uow,
        settings,
        email=str(payload.email),
        email_sender=email_sender,
        limiter=limiter,
        client_key=caller,
        context=context,
    )
    return MessageAccepted()


@router.post(
    "/forgot-password",
    response_model=MessageAccepted,
    responses={429: {"model": ErrorResponse, "description": "Too many attempts."}},
)
async def forgot_password(
    payload: EmailRequest,
    uow: UnitOfWorkDep,
    settings: SettingsDep,
    email_sender: EmailSenderDep,
    limiter: RateLimiterDep,
    caller: CallerKeyDep,
    context: SecurityContextDep,
) -> MessageAccepted:
    from app.application.ports.notifications import DeliveryError
    from app.application.use_cases.account_security import request_password_reset
    from app.core.errors import EmailDeliveryError

    try:
        await request_password_reset(
            uow,
            settings,
            email=str(payload.email),
            email_sender=email_sender,
            limiter=limiter,
            client_key=caller,
            context=context,
        )
    except DeliveryError as exc:
        raise EmailDeliveryError("The reset email could not be sent.") from exc
    return MessageAccepted()


@router.post(
    "/reset-password",
    response_model=MessageAccepted,
    summary="Complete a password reset",
    responses={422: {"model": ErrorResponse, "description": "Invalid or expired token."}},
)
async def reset_password(
    payload: PasswordResetRequest,
    response: Response,
    uow: UnitOfWorkDep,
    settings: SettingsDep,
    hasher: PasswordHasherDep,
    limiter: RateLimiterDep,
    caller: CallerKeyDep,
    context: SecurityContextDep,
) -> MessageAccepted:
    from app.application.use_cases.account_security import reset_password as reset

    await reset(
        uow,
        settings,
        token=payload.token,
        new_password=payload.new_password,
        hasher=hasher,
        limiter=limiter,
        client_key=caller,
        context=context,
    )
    # Every session was revoked by the reset, so the caller's own cookie is dead.
    clear_session_cookie(response, settings)
    clear_csrf_cookie(response, settings)
    return MessageAccepted()


@router.post(
    "/change-password",
    response_model=MessageAccepted,
    summary="Change the password of the signed-in account",
    responses={401: {"model": ErrorResponse, "description": "Wrong current password."}},
)
async def change_password(
    payload: PasswordChangeRequest,
    uow: UnitOfWorkDep,
    settings: SettingsDep,
    hasher: PasswordHasherDep,
    email_sender: EmailSenderDep,
    user: CurrentUserDep,
    context: SecurityContextDep,
) -> MessageAccepted:
    from app.application.use_cases.account_security import change_password as change

    await change(
        uow,
        settings,
        user=user,
        current_password=payload.current_password,
        new_password=payload.new_password,
        hasher=hasher,
        email_sender=email_sender,
        context=context,
    )
    return MessageAccepted()


__all__ = ["router"]
