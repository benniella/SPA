from __future__ import annotations

from dataclasses import dataclass

from app.application.admin_authz import AdminContext
from app.application.ports.repositories import SecurityEventRepository
from app.application.ports.security import RateLimiter
from app.core.errors import PermissionDeniedError, ValidationError
from app.domain.admin.entities import AdminPrivilege
from app.domain.security.entities import SecurityEvent, SecurityEventType

RATE_LIMIT_SCOPES = frozenset(
    {"login", "register", "password-reset", "resend-verification", "admin"}
)


@dataclass(frozen=True, slots=True)
class RateLimitReset:
    scope: str
    identifier: str
    key: str


def _require(actor: AdminContext, privilege: str) -> None:
    if not actor.holds(privilege):
        raise PermissionDeniedError(f"Privilege {privilege} is required.")


async def reset_rate_limit_state(
    actor: AdminContext,
    *,
    scope: str,
    identifier: str,
    limiter: RateLimiter,
    security_events: SecurityEventRepository,
    ip_prefix: str | None = None,
) -> RateLimitReset:
    _require(actor, AdminPrivilege.SECURITY_MANAGE)

    if scope not in RATE_LIMIT_SCOPES:
        raise ValidationError(f"Unknown rate-limit scope: {scope!r}.")
    value = identifier.strip()
    if not value:
        raise ValidationError("An identifier is required to reset a rate limit.")

    key = f"ratelimit:{scope}:{value}"
    await limiter.reset(key)
    await security_events.add(
        SecurityEvent(
            user_id=actor.admin.user_id,
            event_type=str(SecurityEventType.PLATFORM_RATE_LIMIT_STATE_RESET),
            metadata={"scope": scope, "identifier": value},
            ip_prefix=ip_prefix,
        )
    )
    return RateLimitReset(scope=scope, identifier=value, key=key)


async def read_rate_limit_state(
    actor: AdminContext,
    *,
    scope: str,
    identifier: str,
    limiter: RateLimiter,
) -> int | None:
    _require(actor, AdminPrivilege.SECURITY_READ)
    if scope not in RATE_LIMIT_SCOPES:
        raise ValidationError(f"Unknown rate-limit scope: {scope!r}.")
    value = identifier.strip()
    if not value:
        raise ValidationError("An identifier is required to read a rate limit.")
    return await limiter.peek(f"ratelimit:{scope}:{value}")
