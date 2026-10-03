"""Administrative audit retrieval."""

from __future__ import annotations

from datetime import datetime

from app.application.admin_authz import AdminContext
from app.application.ports.repositories import SecurityEventRepository
from app.core.errors import ValidationError
from app.domain.admin.entities import AdminPrivilege
from app.domain.security.entities import SecurityEvent, SecurityEventType


def _require_known_event_type(event_type: str | None) -> None:
    if event_type is None or event_type == "":
        return
    if event_type not in SecurityEventType.ALLOWED:
        raise ValidationError(f"Unknown security event type: {event_type!r}.")


def _require_ordered_range(since: datetime | None, until: datetime | None) -> None:
    if since is not None and until is not None and since > until:
        raise ValidationError("The start of the range must not be after its end.")


async def list_administrative_events(
    actor: AdminContext,
    *,
    security_events: SecurityEventRepository,
    limit: int = 50,
    offset: int = 0,
    event_type: str | None = None,
    actor_id: object | None = None,
    since: datetime | None = None,
    until: datetime | None = None,
) -> list[SecurityEvent]:
    """Platform-wide administrative audit records.

    Read-only by construction: the repository port exposes no update or delete, so
    there is no application path through which audit history can be altered.
    """
    actor.require(AdminPrivilege.SECURITY_READ)
    _require_known_event_type(event_type)
    _require_ordered_range(since, until)
    return await security_events.list_administrative(
        limit=limit,
        offset=offset,
        event_type=event_type or None,
        actor_id=actor_id,
        since=since,
        until=until,
    )


async def count_administrative_events(
    actor: AdminContext,
    *,
    security_events: SecurityEventRepository,
    event_type: str | None = None,
    actor_id: object | None = None,
    since: datetime | None = None,
    until: datetime | None = None,
) -> int:
    actor.require(AdminPrivilege.SECURITY_READ)
    _require_known_event_type(event_type)
    _require_ordered_range(since, until)
    return await security_events.count_administrative(
        event_type=event_type or None, actor_id=actor_id, since=since, until=until
    )
