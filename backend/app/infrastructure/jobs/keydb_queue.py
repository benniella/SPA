from __future__ import annotations

import logging
import time

import redis.asyncio as redis

logger = logging.getLogger(__name__)

PENDING_KEY = "spa:jobs:pending"
PROCESSING_KEY = "spa:jobs:processing"
DEDUPE_KEY = "spa:jobs:seen"


class KeyDbJobQueue:
    def __init__(
        self,
        url: str,
        *,
        database: int = 0,
        visibility_timeout_seconds: int = 300,
        dedupe_ttl_seconds: int = 3600,
    ) -> None:
        self._client = redis.from_url(url, db=database, decode_responses=True)
        self._visibility_timeout = visibility_timeout_seconds
        self._dedupe_ttl = dedupe_ttl_seconds

    async def enqueue(self, job_id: str) -> None:
        # 'SET NX' collapses a duplicate enqueue of the same identifier: a second
        # dispatch of a job already waiting must not create a second delivery.
        first_delivery = await self._client.set(
            f"{DEDUPE_KEY}:{job_id}", "1", nx=True, ex=self._dedupe_ttl
        )
        if first_delivery is None:
            logger.debug("job already enqueued", extra={"job_id": job_id})
            return
        await self._client.lpush(PENDING_KEY, job_id)

    async def dequeue(self, *, timeout_seconds: int = 5) -> str | None:
        await self._reclaim_stale()
        raw = await self._client.brpoplpush(PENDING_KEY, PROCESSING_KEY, timeout=timeout_seconds)
        if raw is None:
            return None
        job_id = raw.decode() if isinstance(raw, bytes) else str(raw)
        await self._client.zadd(PROCESSING_KEY + ":claimed", {job_id: time.time()})
        return job_id

    async def acknowledge(self, job_id: str) -> None:
        await self._client.lrem(PROCESSING_KEY, 0, job_id)
        await self._client.zrem(PROCESSING_KEY + ":claimed", job_id)
        await self._client.delete(f"{DEDUPE_KEY}:{job_id}")

    async def requeue(self, job_id: str) -> None:
        await self._client.lrem(PROCESSING_KEY, 0, job_id)
        await self._client.zrem(PROCESSING_KEY + ":claimed", job_id)
        # The dedupe marker is dropped so the re-delivery is not suppressed.
        await self._client.delete(f"{DEDUPE_KEY}:{job_id}")
        await self._client.lpush(PENDING_KEY, job_id)

    async def _reclaim_stale(self) -> None:
        cutoff = time.time() - self._visibility_timeout
        stale = await self._client.zrangebyscore(PROCESSING_KEY + ":claimed", 0, cutoff)
        for raw in stale:
            job_id = raw.decode() if isinstance(raw, bytes) else str(raw)
            await self._client.lrem(PROCESSING_KEY, 0, job_id)
            await self._client.zrem(PROCESSING_KEY + ":claimed", job_id)
            await self._client.lpush(PENDING_KEY, job_id)
            logger.warning("reclaimed a job from a stale worker", extra={"job_id": job_id})

    async def flush(self) -> None:
        await self._client.delete(PENDING_KEY, PROCESSING_KEY, PROCESSING_KEY + ":claimed")
        async for key in self._client.scan_iter(match=f"{DEDUPE_KEY}:*"):
            await self._client.delete(key)

    async def ping(self) -> bool:
        try:
            return bool(await self._client.ping())
        except Exception:
            return False

    async def close(self) -> None:
        await self._client.aclose()
