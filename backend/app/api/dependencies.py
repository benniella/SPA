from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from typing import Annotated, cast

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.ports.jobs import JobDispatcher
from app.application.ports.unit_of_work import UnitOfWork
from app.application.ports.video_storage import VideoStorage
from app.core.config import Settings, get_settings
from app.core.errors import AuthenticationError, ConfigurationError
from app.domain.shared import UserId
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


def job_dispatcher_dependency(request: Request) -> JobDispatcher:
    dispatcher = getattr(request.app.state, "job_dispatcher", None)
    if dispatcher is None:  # pragma: no cover - guarded by lifespan startup
        raise ConfigurationError("Job dispatcher is not configured.")
    return dispatcher


JobDispatcherDep = Annotated[JobDispatcher, Depends(job_dispatcher_dependency)]


def video_storage_dependency(request: Request) -> VideoStorage:
    storage = getattr(request.app.state, "video_storage", None)
    if storage is None:  # pragma: no cover - guarded by lifespan startup
        raise ConfigurationError("Video storage is not configured.")
    return storage


VideoStorageDep = Annotated[VideoStorage, Depends(video_storage_dependency)]


async def current_user_dependency(
    request: Request,
    uow: UnitOfWorkDep,
) -> User:
    settings = get_settings()
    header = request.headers.get("x-spa-user-id", "").strip()
    if not header:
        raise AuthenticationError("Authentication is required.")
    if settings.is_production:
        raise AuthenticationError("Header identity is not available in production.")

    try:
        user_id = UserId(uuid.UUID(header))
    except ValueError as exc:
        raise AuthenticationError("Authentication is required.") from exc

    async with uow:
        user = await uow.users.get(user_id)
    if user is None or not user.is_active:
        raise AuthenticationError("Authentication is required.")
    return user


CurrentUserDep = Annotated[User, Depends(current_user_dependency)]
