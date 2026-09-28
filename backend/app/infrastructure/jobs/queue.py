from __future__ import annotations

import asyncio
from collections import deque


class InMemoryJobQueue:
    def __init__(self) -> None:
        self._pending: deque[str] = deque()
        self._in_flight: dict[str, None] = {}
        self._lock = asyncio.Lock()

    async def enqueue(self, job_id: str) -> None:
        async with self._lock:
            if job_id in self._in_flight:
                return
            self._pending.append(job_id)

    async def dequeue(self, *, timeout_seconds: int = 5) -> str | None:
        async with self._lock:
            if self._pending:
                job_id = self._pending.popleft()
                self._in_flight[job_id] = None
                return job_id
            return None

    async def acknowledge(self, job_id: str) -> None:
        async with self._lock:
            self._in_flight.pop(job_id, None)

    async def requeue(self, job_id: str) -> None:
        async with self._lock:
            self._in_flight.pop(job_id, None)
            self._pending.append(job_id)

    async def close(self) -> None:
        return None

    @property
    def depth(self) -> int:
        return len(self._pending)
