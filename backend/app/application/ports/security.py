"""Password hashing and short-lived counter storage.

Both are ports because both have a real second implementation: the hasher
switches algorithm without touching a use case, and the rate-limit store switches
from an in-process counter to a shared one for a multi-process deployment.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable


@dataclass(frozen=True, slots=True)
class RateLimitDecision:
    allowed: bool
    remaining: int
    retry_after_seconds: int


class RateLimitUnavailableError(Exception):
    """The shared counter store could not be reached.

    Raised rather than returned so a caller cannot silently treat an unreachable
    store as "no limit". Authentication endpoints must fail closed.
    """


@runtime_checkable
class RateLimiter(Protocol):
    async def hit(self, key: str, *, limit: int, window_seconds: int) -> RateLimitDecision:
        """Record one attempt against a key and report whether it is allowed."""

    async def peek(self, key: str) -> int | None:
        """The current count for a key, without recording an attempt."""

    async def reset(self, key: str) -> None:
        """Clear a key, for example after a successful sign-in."""
