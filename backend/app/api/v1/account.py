from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Request, Response, status

from app.api.dependencies import (
    CallerKeyDep,
    CurrentUserDep,
    EmailSenderDep,
    PasswordHasherDep,
    RateLimiterDep,
    SecurityContextDep,
    SettingsDep,
    SmsSenderDep,
    UnitOfWorkDep,
)
from app.api.v1.account_presenters import (
    security_event_payload,
    session_payload,
)
from app.api.v1.params import Pagination, pagination
from app.application.ports.notifications import DeliveryError
from app.application.sessions import resolve_session, revoke_all_sessions, revoke_session
from app.application.use_cases import account_security as security_use_cases
from app.application.use_cases import phone as phone_use_cases
from app.application.use_cases.authentication import change_email, verify_email_change
from app.application.use_cases.security_events import list_security_events
from app.core.errors import EmailDeliveryError
from app.schemas.auth import (
    EmailChangeRequest,
    MessageAccepted,
    PhoneRequest,
    PhoneVerifyRequest,
    RecoveryCompleteRequest,
    RecoveryStartRequest,
    SecurityEventList,
    SecurityEventRead,
    SessionList,
    SessionSummary,
    TokenRequest,
)
from app.schemas.common import ErrorResponse

router = APIRouter()


@router.get(
    "/sessions",
    response_model=SessionList,
    summary="Active sessions for this account",
)
async def list_sessions(
    uow: UnitOfWorkDep,
    user: CurrentUserDep,
    request: Request,
    settings: SettingsDep,
    page: Pagination = Depends(pagination),
) -> SessionList:
    token = request.cookies.get(settings.session_cookie_name)
    async with uow:
        current = await resolve_session(uow, settings, token=token) if token else None
        sessions = await uow.sessions.list_for_user(user.id)

    current_id = current.id if current else None
    page_items = sessions[page.offset : page.offset + page.limit]
    return SessionList(
        items=[
            SessionSummary.model_validate(session_payload(item, current_session_id=current_id))
            for item in page_items
        ],
        meta=page.meta(len(page_items)),
    )


@router.delete(
    "/sessions/{session_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Revoke one of your sessions",
    responses={404: {"model": ErrorResponse, "description": "Session not found."}},
)
async def delete_session(
    session_id: uuid.UUID,
    uow: UnitOfWorkDep,
    user: CurrentUserDep,
    context: SecurityContextDep,
) -> Response:
    async with uow:
        await revoke_session(uow, session_id=session_id, user_id=user.id, context=context)
        await uow.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/sessions/revoke-all",
    response_model=MessageAccepted,
    summary="Revoke every session except this one",
)
async def revoke_all(
    uow: UnitOfWorkDep,
    user: CurrentUserDep,
    request: Request,
    settings: SettingsDep,
    context: SecurityContextDep,
) -> MessageAccepted:
    token = request.cookies.get(settings.session_cookie_name)
    async with uow:
        current = await resolve_session(uow, settings, token=token) if token else None
        await revoke_all_sessions(
            uow,
            user_id=user.id,
            except_session_id=current.id if current else None,
            context=context,
        )
        await uow.commit()
    return MessageAccepted()


@router.post(
    "/email/request-change",
    response_model=MessageAccepted,
    summary="Ask to move the account to a new email address",
)
async def request_email_change(
    payload: EmailChangeRequest,
    uow: UnitOfWorkDep,
    settings: SettingsDep,
    user: CurrentUserDep,
    hasher: PasswordHasherDep,
    email_sender: EmailSenderDep,
    context: SecurityContextDep,
) -> MessageAccepted:
    try:
        await change_email(
            uow,
            settings,
            user=user,
            new_email=str(payload.new_email),
            current_password=payload.current_password,
            hasher=hasher,
            email_sender=email_sender,
            context=context,
        )
    except DeliveryError as exc:
        raise EmailDeliveryError("The confirmation email could not be sent.") from exc
    return MessageAccepted()


@router.post(
    "/email/verify-change",
    response_model=MessageAccepted,
    summary="Confirm a new email address",
    responses={422: {"model": ErrorResponse, "description": "Invalid or expired token."}},
)
async def verify_email_change_route(
    payload: TokenRequest,
    uow: UnitOfWorkDep,
    settings: SettingsDep,
    context: SecurityContextDep,
) -> MessageAccepted:
    await verify_email_change(uow, settings, token=payload.token, context=context)
    return MessageAccepted()


@router.post(
    "/phone/request-verification",
    response_model=MessageAccepted,
    summary="Send a verification code to a phone number",
    responses={503: {"model": ErrorResponse, "description": "No SMS provider configured."}},
)
async def request_phone_verification(
    payload: PhoneRequest,
    uow: UnitOfWorkDep,
    settings: SettingsDep,
    user: CurrentUserDep,
    sms_sender: SmsSenderDep,
    limiter: RateLimiterDep,
    caller: CallerKeyDep,
    context: SecurityContextDep,
) -> MessageAccepted:
    await phone_use_cases.request_phone_verification(
        uow,
        settings,
        user=user,
        phone_number=payload.phone_number,
        sms_sender=sms_sender,
        limiter=limiter,
        client_key=caller,
        context=context,
    )
    return MessageAccepted()


@router.post(
    "/phone/verify",
    response_model=MessageAccepted,
    summary="Confirm a phone verification code",
)
async def verify_phone(
    payload: PhoneVerifyRequest,
    uow: UnitOfWorkDep,
    settings: SettingsDep,
    user: CurrentUserDep,
    limiter: RateLimiterDep,
    caller: CallerKeyDep,
    context: SecurityContextDep,
) -> MessageAccepted:
    await phone_use_cases.verify_phone(
        uow,
        settings,
        user=user,
        code=payload.code,
        limiter=limiter,
        client_key=caller,
        context=context,
    )
    return MessageAccepted()


@router.delete(
    "/phone",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove the verified phone number",
)
async def remove_phone(
    uow: UnitOfWorkDep,
    user: CurrentUserDep,
    context: SecurityContextDep,
) -> Response:
    async with uow:
        await phone_use_cases.remove_phone(uow, user=user, context=context)
        await uow.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    "/security-events",
    response_model=SecurityEventList,
    summary="Security activity for this account",
)
async def security_events(
    uow: UnitOfWorkDep,
    user: CurrentUserDep,
    page: Pagination = Depends(pagination),
) -> SecurityEventList:
    events = await list_security_events(
        uow, user_id=user.id, limit=page.limit, offset=page.offset
    )
    return SecurityEventList(
        items=[SecurityEventRead.model_validate(security_event_payload(event)) for event in events],
        meta=page.meta(len(events)),
    )


@router.post(
    "/recovery/start",
    response_model=MessageAccepted,
    summary="Start account recovery through a verified phone number",
    responses={503: {"model": ErrorResponse, "description": "No SMS provider configured."}},
)
async def start_recovery(
    payload: RecoveryStartRequest,
    uow: UnitOfWorkDep,
    settings: SettingsDep,
    limiter: RateLimiterDep,
    caller: CallerKeyDep,
    context: SecurityContextDep,
) -> MessageAccepted:
    try:
        await security_use_cases.start_recovery(
            uow,
            settings,
            email=str(payload.email),
            limiter=limiter,
            client_key=caller,
            context=context,
        )
    except DeliveryError as exc:
        raise EmailDeliveryError("The recovery code could not be sent.") from exc
    return MessageAccepted()


@router.post(
    "/recovery/complete",
    response_model=MessageAccepted,
    summary="Finish account recovery with a code and a new password",
)
async def complete_recovery(
    payload: RecoveryCompleteRequest,
    uow: UnitOfWorkDep,
    settings: SettingsDep,
    hasher: PasswordHasherDep,
    limiter: RateLimiterDep,
    caller: CallerKeyDep,
    context: SecurityContextDep,
) -> MessageAccepted:
    await security_use_cases.complete_recovery(
        uow,
        settings,
        email=str(payload.email),
        code=payload.code,
        new_password=payload.new_password,
        hasher=hasher,
        limiter=limiter,
        client_key=caller,
        context=context,
    )
    return MessageAccepted()
