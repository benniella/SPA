"""Security-event reads and the request context the API layer supplies."""

from __future__ import annotations

from app.application.ports.unit_of_work import UnitOfWork
from app.application.security import RequestContext, request_context
from app.domain.security.entities import SecurityEvent
from app.domain.shared import UserId


def read_security_context(
    *,
    client_host: str | None,
    user_agent: str | None,
) -> RequestContext:
    return request_context(client_host=client_host, user_agent=user_agent)


def client_key(*, client_host: str | None, fallback: str) -> str:
    """The key an unauthenticated rate limit is charged against.

    The network prefix rather than the full address: it is the granularity a
    limiter can act on without storing a person's address, and it still groups an
    attempt that moves between ports.
    """
    context = request_context(client_host=client_host, user_agent=None)
    return context.ip_prefix or fallback


async def list_security_events(
    uow: UnitOfWork,
    *,
    user_id: UserId,
    limit: int = 50,
    offset: int = 0,
    event_type: str | None = None,
) -> list[SecurityEvent]:
    async with uow:
        return await uow.security_events.list_for_user(
            user_id, limit=limit, offset=offset, event_type=event_type
        )
