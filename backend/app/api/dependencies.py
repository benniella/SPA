from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from typing import Annotated, cast

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.ports.jobs import JobDispatcher
from app.application.ports.notifications import EmailSender, SmsSender
from app.application.ports.security import RateLimiter
from app.application.ports.unit_of_work import UnitOfWork
from app.application.ports.video_storage import VideoStorage
from app.application.security import RequestContext
from app.application.sessions import resolve_session, touch_session
from app.application.use_cases.security_events import client_key, read_security_context
from app.core.config import Settings, get_settings
from app.core.errors import AuthenticationError, ConfigurationError, SessionExpiredError
from app.domain.security.entities import Session
from app.domain.shared import UserId
from app.domain.users.credentials import PasswordHasher
from app.domain.users.entities import User
from app.infrastructure.database.engine import get_session_factory


def settings_dependency() -> Settings:
    return get_settings()


SettingsDep = Annotated[Settings, Depends(settings_dependency)]


async def session_dependency(request: Request) -> AsyncIterator[AsyncSession]:
    settings = get_settings()
    session_factory = get_session_factory(settings)
    session = session_factory()
    try:
        yield session
    finally:
        await session.close()


SessionDep = Annotated[AsyncSession, Depends(session_dependency)]


def unit_of_work_dependency() -> UnitOfWork:
    from app.infrastructure.database.unit_of_work import SqlAlchemyUnitOfWorkFactory

    settings = get_settings()
    factory = SqlAlchemyUnitOfWorkFactory(get_session_factory(settings))
    # The implementation satisfies the UnitOfWork protocol structurally, but mypy
    # cannot prove it across the application/infrastructure split, so the cast
    # documents the invariant the integration tests exercise.
    return cast(UnitOfWork, factory())


UnitOfWorkDep = Annotated[UnitOfWork, Depends(unit_of_work_dependency)]


def _adapter(request: Request, name: str) -> object:
    value = getattr(request.app.state, name, None)
    if value is None:  # pragma: no cover - guarded by lifespan startup
        raise ConfigurationError(f"The {name} adapter is not configured.")
    return value


def job_dispatcher_dependency(request: Request) -> JobDispatcher:
    return cast(JobDispatcher, _adapter(request, "job_dispatcher"))


JobDispatcherDep = Annotated[JobDispatcher, Depends(job_dispatcher_dependency)]


def video_storage_dependency(request: Request) -> VideoStorage:
    return cast(VideoStorage, _adapter(request, "video_storage"))


VideoStorageDep = Annotated[VideoStorage, Depends(video_storage_dependency)]


def password_hasher_dependency(request: Request) -> PasswordHasher:
    return cast(PasswordHasher, _adapter(request, "password_hasher"))


PasswordHasherDep = Annotated[PasswordHasher, Depends(password_hasher_dependency)]


def rate_limiter_dependency(request: Request) -> RateLimiter:
    return cast(RateLimiter, _adapter(request, "rate_limiter"))


RateLimiterDep = Annotated[RateLimiter, Depends(rate_limiter_dependency)]


def email_sender_dependency(request: Request) -> EmailSender:
    return cast(EmailSender, _adapter(request, "email_sender"))


EmailSenderDep = Annotated[EmailSender, Depends(email_sender_dependency)]


def sms_sender_dependency(request: Request) -> SmsSender:
    return cast(SmsSender, _adapter(request, "sms_sender"))


SmsSenderDep = Annotated[SmsSender, Depends(sms_sender_dependency)]


def security_context_dependency(request: Request) -> RequestContext:
    return read_security_context(
        client_host=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )


SecurityContextDep = Annotated[RequestContext, Depends(security_context_dependency)]


def caller_key_dependency(request: Request) -> str:
    return client_key(
        client_host=request.client.host if request.client else None,
        fallback="unknown",
    )


CallerKeyDep = Annotated[str, Depends(caller_key_dependency)]


def session_cookie_dependency(request: Request) -> str | None:
    settings = get_settings()
    return request.cookies.get(settings.session_cookie_name)


SessionCookieDep = Annotated[str | None, Depends(session_cookie_dependency)]


async def current_user_dependency(
    request: Request,
    uow: UnitOfWorkDep,
    token: SessionCookieDep,
    settings: SettingsDep,
) -> User:
    """Resolve the authenticated identity from the session.

    In production this is always the session cookie: the cookie is an opaque
    token, its hash is looked up server-side, and the account's own state is
    re-checked on every request. A revoked session and a suspended account both
    therefore stop working immediately rather than when the cookie expires.

    Outside production a development identity header may be enabled, so the
    Phase 0-8 test architecture keeps working. That path can never be selected in
    production: 'is_local' is checked here as well as at selection time.
    """
    settings_ = settings
    if settings_.dev_identity_header and not settings_.is_production:
        header = request.headers.get("x-spa-user-id", "").strip()
        if header:
            return await _dev_identity(uow, header)

    if not token:
        raise AuthenticationError("Authentication is required.")

    async with uow:
        session = await touch_session(uow, settings_, token=token)
        if session is None:
            await uow.commit()
            raise SessionExpiredError("Your session has expired. Sign in again.")
        user = await uow.users.get(session.user_id)
        await uow.commit()

    if user is None:
        raise SessionExpiredError("Your session has expired. Sign in again.")
    if not user.can_authenticate:
        raise AuthenticationError("This account cannot sign in right now.")
    return user


CurrentUserDep = Annotated[User, Depends(current_user_dependency)]


async def current_session_dependency(
    uow: UnitOfWorkDep,
    token: SessionCookieDep,
    settings: SettingsDep,
) -> Session | None:
    """The authenticated session, or None when the request used a dev identity.

    Administrative authorization needs the session itself, not just the user: the
    second-factor assurance lives on the session and must not be inferred from the
    account alone.
    """
    if not token:
        return None
    async with uow:
        session = await resolve_session(uow, settings, token=token)
        await uow.commit()
    return session


CurrentSessionDep = Annotated[Session | None, Depends(current_session_dependency)]


async def _dev_identity(uow: UnitOfWork, header: str) -> User:
    try:
        user_id = UserId(uuid.UUID(header))
    except ValueError as exc:
        raise AuthenticationError("Authentication is required.") from exc

    async with uow:
        user = await uow.users.get(user_id)
    if user is None or not user.is_active or not user.can_authenticate:
        raise AuthenticationError("Authentication is required.")
    return user
