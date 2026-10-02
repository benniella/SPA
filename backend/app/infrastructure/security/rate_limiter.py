"""Rate-limit counters.

The in-process counter is correct for a single-process development deployment
and is documented as insufficient for a multi-process one, where the same account
could spread its attempts across workers. The KeyDB-backed counter is the shared
implementation; the API selects between them from configuration.
"""

from __future__ import annotations

import time

import redis.asyncio as redis

from app.application.ports.security import RateLimitDecision, RateLimitUnavailableError


class ProcessRateLimiter:
    """A fixed-window counter held in this process.

    Bounded by pruning on read rather than by a background task, so a long-lived
    process cannot accumulate keys for clients that never return.
    """

    def __init__(self) -> None:
        self._windows: dict[str, tuple[int, int]] = {}

    async def hit(self, key: str, *, limit: int, window_seconds: int) -> RateLimitDecision:
        now = int(time.time())
        window_start, count = self._windows.get(key, (now, 0))
        if now - window_start >= window_seconds:
            window_start, count = now, 0
        count += 1
        self._windows[key] = (window_start, count)

        reset_in = max(1, window_seconds - (now - window_start))
        return RateLimitDecision(
            allowed=count <= limit,
            remaining=max(0, limit - count),
            retry_after_seconds=reset_in if count > limit else 0,
        )

    async def peek(self, key: str) -> int | None:
        entry = self._windows.get(key)
        return entry[1] if entry else None

    async def reset(self, key: str) -> None:
        self._windows.pop(key, None)


class KeyDbRateLimiter:
    """A fixed-window counter shared through KeyDB.

    'INCR' plus an expiry set on the first increment of a window is atomic enough
    for a counter whose only job is to bound abuse. A store that cannot be
    reached raises rather than returning "allowed": failing open on a login
    endpoint turns a cache outage into an unlimited credential-stuffing window.
    """

    def __init__(self, url: str, *, database: int = 0) -> None:
        self._client = redis.from_url(url, db=database, decode_responses=True)

    async def hit(self, key: str, *, limit: int, window_seconds: int) -> RateLimitDecision:
        try:
            count = await self._client.incr(key)
            if count == 1:
                await self._client.expire(key, window_seconds)
            ttl = await self._client.ttl(key)
        except Exception as exc:
            raise RateLimitUnavailableError("The rate-limit store is unavailable.") from exc

        reset_in = ttl if isinstance(ttl, int) and ttl > 0 else window_seconds
        return RateLimitDecision(
            allowed=int(count) <= limit,
            remaining=max(0, limit - int(count)),
            retry_after_seconds=reset_in if int(count) > limit else 0,
        )

    async def peek(self, key: str) -> int | None:
        try:
            value = await self._client.get(key)
        except Exception:
            return None
        return int(value) if value is not None else None

    async def reset(self, key: str) -> None:
        try:
            await self._client.delete(key)
        except Exception:
            return

    async def close(self) -> None:
        await self._client.aclose()
