from __future__ import annotations

import asyncio
import contextlib
import json
import logging
from typing import Any

import redis.asyncio as redis

from app.application.events import ProcessingEvent
from app.infrastructure.realtime.hub import InProcessEventHub

logger = logging.getLogger(__name__)

CHANNEL_PREFIX = "spa:events:org"


def channel_for(organization_id: str) -> str:
    return f"{CHANNEL_PREFIX}:{organization_id}"


class KeyDbEventPublisher:
    def __init__(self, url: str, *, database: int = 0) -> None:
        self._client = redis.from_url(url, db=database, decode_responses=True)

    async def publish(self, organization_id: str, event: ProcessingEvent) -> None:
        await self._client.publish(channel_for(organization_id), json.dumps(event.to_payload()))

    async def close(self) -> None:
        await self._client.aclose()


class KeyDbEventBridge:
    def __init__(self, url: str, hub: InProcessEventHub, *, database: int = 0) -> None:
        self._client = redis.from_url(url, db=database, decode_responses=True)
        self._hub = hub
        self._task: asyncio.Task[None] | None = None
        self._pubsub: Any = None

    async def start(self) -> None:
        self._pubsub = self._client.pubsub()
        await self._pubsub.psubscribe(f"{CHANNEL_PREFIX}:*")
        self._task = asyncio.create_task(self._listen())

    async def _listen(self) -> None:
        assert self._pubsub is not None
        async for message in self._pubsub.listen():
            if message.get("type") != "pmessage":
                continue
            try:
                payload = json.loads(message["data"])
            except (ValueError, TypeError):
                logger.warning("discarded a malformed event")
                continue
            organization_id = str(message["channel"]).rsplit(":", 1)[-1]
            await self._hub.publish_payload(organization_id, payload)

    async def stop(self) -> None:
        if self._task is not None:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
        if self._pubsub is not None:
            await self._pubsub.aclose()
        await self._client.aclose()
