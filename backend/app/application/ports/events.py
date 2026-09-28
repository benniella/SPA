from __future__ import annotations

from typing import Protocol, runtime_checkable

from app.application.events import ProcessingEvent


@runtime_checkable
class EventPublisher(Protocol):
    async def publish(self, organization_id: str, event: ProcessingEvent) -> None: ...


@runtime_checkable
class EventSubscriber(Protocol):
    def subscribe(self, organization_id: str, callback: object) -> str: ...

    async def unsubscribe(self, organization_id: str, subscription_id: str) -> None: ...
