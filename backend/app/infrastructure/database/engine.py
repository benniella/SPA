"""SQLAlchemy 2.x engine and session management.

An async engine for the API and repositories, plus a synchronous URL derived
from the same settings for Alembic. PostgreSQL is the only supported database, so
the configuration uses PostgreSQL-specific behaviour rather than pretending to
be dialect-agnostic.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import Settings

_session_factory: async_sessionmaker[AsyncSession] | None = None
_engine: AsyncEngine | None = None


def to_sync_database_url(database_url: str) -> str:
    """Convert an async SQLAlchemy URL to its synchronous driver equivalent.

    Alembic migrations and synchronous scripts use psycopg directly, while the
    application uses the async variant of the same driver.
    """
    return (
        database_url.replace("postgresql+psycopg_async://", "postgresql+psycopg://")
        .replace("postgresql+asyncpg://", "postgresql+psycopg://")
        .replace("+psycopg://", "+psycopg://")
    )


def create_engine(settings: Settings) -> AsyncEngine:
    """Build the async engine.

    ' 'pool_pre_ping' ' is enabled because the API process can outlive a database
    restart or a network blip; without it the first request after such an event
    fails with a stale connection. ' 'pool_recycle' ' guards against the
    connection being reaped by an intermediate proxy.
    """
    return create_async_engine(
        settings.database_url,
        echo=settings.db_echo,
        pool_size=settings.db_pool_size,
        max_overflow=settings.db_max_overflow,
        pool_pre_ping=settings.db_pool_pre_ping,
        pool_recycle=1800,
        # Fail fast when the database is unreachable rather than hanging the
        # whole worker pool.
        connect_args={"connect_timeout": 10},
    )


def get_engine(settings: Settings) -> AsyncEngine:
    """Return the process-wide engine, creating it on first use."""
    global _engine
    if _engine is None:
        _engine = create_engine(settings)
    return _engine


def get_session_factory(settings: Settings) -> async_sessionmaker[AsyncSession]:
    """Return the process-wide session factory."""
    global _session_factory
    if _session_factory is None:
        _session_factory = async_sessionmaker(
            bind=get_engine(settings),
            class_=AsyncSession,
            # Objects must not be silently expired on commit: use cases return
            # entities to the caller *after* committing, and implicit expiry
            # would turn that read into an extra query or a lazy-load error.
            expire_on_commit=False,
            autoflush=False,
        )
    return _session_factory


@asynccontextmanager
async def session_scope(
    session_factory: async_sessionmaker[AsyncSession],
) -> AsyncIterator[AsyncSession]:
    """Provide a transactional session, rolling back on any exception."""
    session = session_factory()
    try:
        yield session
    except Exception:
        await session.rollback()
        raise
    finally:
        await session.close()


async def dispose_engine() -> None:
    """Close the engine's pool. Called on application shutdown."""
    global _engine, _session_factory
    if _engine is not None:
        await _engine.dispose()
    _engine = None
    _session_factory = None
