"""Realtime infrastructure: the event hub behind the WebSocket boundary."""

from app.infrastructure.realtime.hub import InProcessEventHub

__all__ = ["InProcessEventHub"]
