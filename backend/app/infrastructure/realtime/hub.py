from __future__ import annotations

import asyncio
import logging
import uuid
from collections.abc import Awaitable, Callable
from typing import Any

from app.application.events import ProcessingEvent

logger = logging.getLogger(__name__)

DeliveryCallback = Callable[[dict[str, Any]], Awaitable[None]]


class InProcessEventHub:
    def __init__(self) -> None:
        self._subscribers: dict[str, dict[str, DeliveryCallback]] = {}

    def subscribe(self, organization_id: str, callback: DeliveryCallback) -> str:
        subscription_id = uuid.uuid4().hex
        self._subscribers.setdefault(organization_id, {})[subscription_id] = callback
        return subscription_id

    async def unsubscribe(self, organization_id: str, subscription_id: str) -> None:
        channel = self._subscribers.get(organization_id)
        if channel is None:
            return
        channel.pop(subscription_id, None)
        if not channel:
            self._subscribers.pop(organization_id, None)

    async def publish(self, organization_id: str, event: ProcessingEvent) -> None:
        await self.publish_payload(organization_id, event.to_payload())

    async def publish_payload(self, organization_id: str, payload: dict[str, Any]) -> None:
        channel = self._subscribers.get(organization_id)
        if not channel:
            return
        results = await asyncio.gather(
            *(callback(payload) for callback in list(channel.values())),
            return_exceptions=True,
        )
        for result in results:
            if isinstance(result, Exception):
                logger.warning("event delivery failed")

    @property
    def subscriber_count(self) -> int:
        return sum(len(channel) for channel in self._subscribers.values())
