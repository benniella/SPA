"""Session issue, resolution and revocation.

The token is the only secret: it is hashed into the database with the application
secret, so a leaked backup does not let anyone resume a session.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

from app.application.ports.unit_of_work import UnitOfWork
from app.application.security import RequestContext, record_event
from app.core.config import Settings
from app.domain.security.entities import (
    SecurityEventType,
    Session,
    expiry_from,
)
from app.domain.security.tokens import generate_token, hash_token
from app.domain.shared import UserId


@dataclass(frozen=True, slots=True)
class IssuedSession:
    session: Session
    token: str


async def issue_session(
    uow: UnitOfWork,
    settings: Settings,
    *,
    user_id: UserId,
    context: RequestContext | None = None,
    ttl_hours: int | None = None,
) -> IssuedSession:
    token = generate_token()
    session = Session(
        user_id=user_id,
        expires_at=expiry_from(timedelta(hours=ttl_hours or settings.session_ttl_hours)),
        user_agent=context.user_agent if context else None,
        ip_prefix=context.ip_prefix if context else None,
    )
    await uow.sessions.add(session, token_hash=hash_token(token, secret=settings.session_secret))
    await record_event(
        uow,
        event_type=SecurityEventType.SESSION_CREATED,
        user_id=user_id,
        context=context,
        metadata={"session_id": str(session.id)},
    )
    return IssuedSession(session=session, token=token)


async def resolve_session(
    uow: UnitOfWork,
    settings: Settings,
    *,
    token: str,
) -> Session | None:
    """Look up a live session, or 'None'.

    An expired session is returned as 'None' rather than repaired: silently
    extending a session the user was never told about would make the advertised
    expiry untrue.
    """
    session = await uow.sessions.get_by_token_hash(
        hash_token(token, secret=settings.session_secret)
    )
    if session is None or not session.is_valid():
        return None
    return session


async def touch_session(
    uow: UnitOfWork,
    settings: Settings,
    *,
    token: str,
) -> Session | None:
    """Resolve a session and record that it was used.

    Also enforces the idle timeout: a session that has not been used within the
    idle window is revoked, so a token stolen from a dormant browser stops
    working without waiting for the absolute expiry.
    """
    session = await resolve_session(uow, settings, token=token)
    if session is None:
        return None

    idle_deadline = session.last_used_at + timedelta(hours=settings.session_idle_timeout_hours)
    now = expiry_from(timedelta(0))
    if now >= idle_deadline:
        session.revoke()
        await uow.sessions.update(session)
        await record_event(
            uow,
            event_type=SecurityEventType.SESSION_REVOKED,
            user_id=session.user_id,
            metadata={"reason": "idle_timeout", "session_id": str(session.id)},
        )
        return None

    session.touch()
    await uow.sessions.update(session)
    return session


async def revoke_session(
    uow: UnitOfWork,
    *,
    session_id: object,
    user_id: UserId,
    context: RequestContext | None = None,
) -> Session:
    """Revoke one of the caller's own sessions.

    The lookup is scoped to the user, so a session identifier belonging to
    somebody else is indistinguishable from one that does not exist.
    """
    from app.core.errors import NotFoundError

    session = await uow.sessions.get_for_user(session_id, user_id)
    if session is None:
        raise NotFoundError("That session does not exist.")
    session.revoke()
    await uow.sessions.update(session)
    await record_event(
        uow,
        event_type=SecurityEventType.SESSION_REVOKED,
        user_id=user_id,
        context=context,
        metadata={"session_id": str(session.id)},
    )
    return session


async def revoke_all_sessions(
    uow: UnitOfWork,
    *,
    user_id: UserId,
    except_session_id: object = None,
    context: RequestContext | None = None,
) -> int:
    revoked = await uow.sessions.revoke_all_for_user(user_id, except_session_id=except_session_id)
    if revoked:
        await record_event(
            uow,
            event_type=SecurityEventType.SESSIONS_REVOKED,
            user_id=user_id,
            context=context,
            metadata={"count": revoked},
        )
    return revoked
