"""Administrative audit retrieval."""

from __future__ import annotations

from app.application.admin_authz import AdminContext
from app.application.ports.repositories import SecurityEventRepository
from app.domain.admin.entities import AdminPrivilege
from app.domain.security.entities import SecurityEvent


async def list_administrative_events(
    actor: AdminContext,
    *,
    security_events: SecurityEventRepository,
    limit: int = 50,
    offset: int = 0,
    event_type: str | None = None,
) -> list[SecurityEvent]:
    """Platform-wide administrative audit records.

    Read-only by construction: the repository port exposes no update or delete, so
    there is no application path through which audit history can be altered.
    """
    actor.require(AdminPrivilege.SECURITY_READ)
    return await security_events.list_administrative(
        limit=limit, offset=offset, event_type=event_type
    )
