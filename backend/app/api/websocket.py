from __future__ import annotations

import logging
import uuid

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect

from app.application.ports.unit_of_work import UnitOfWork
from app.core.config import Settings
from app.core.errors import AppError
from app.domain.organizations.entities import OrganizationMembership
from app.domain.shared import OrganizationId, UserId
from app.infrastructure.realtime.hub import InProcessEventHub

logger = logging.getLogger(__name__)

router = APIRouter()


class WebSocketAuthenticator:
    def __init__(self, settings: Settings, uow_factory: object) -> None:
        self._settings = settings
        self._uow_factory = uow_factory

    async def authorize(
        self,
        *,
        user_id_header: str | None,
        organization_id: str | None,
    ) -> tuple[UserId, OrganizationId] | None:
        ""
        if not user_id_header or not organization_id:
            return None
        # A production deployment must present a real session credential; until
        # the authentication phase lands, the development header is unavailable
        # in production, matching the HTTP dependency exactly.
        if self._settings.is_production:
            return None

        try:
            user_id = UserId(uuid.UUID(user_id_header.strip()))
            organization_id_value = OrganizationId(uuid.UUID(organization_id.strip()))
        except ValueError:
            return None

        uow: UnitOfWork = self._uow_factory()  # type: ignore[operator]
        try:
            async with uow:
                user = await uow.users.get(user_id)
                if user is None or not user.is_active:
                    return None
                membership: OrganizationMembership | None = await uow.organizations.get_membership(
                    organization_id_value, user_id
                )
        except AppError:
            return None

        if membership is None:
            return None
        return user_id, organization_id_value


def _origin_allowed(settings: Settings, origin: str | None) -> bool:
    allowed = settings.websocket_origin_list
    if not allowed:
        return True
    return origin in allowed


def register_websocket_routes(app: object, settings: Settings) -> None:
    from fastapi import FastAPI

    application: FastAPI = app  # type: ignore[assignment]

    @application.websocket("/ws/processing")
    async def processing_socket(
        websocket: WebSocket,
        organization_id: str | None = Query(default=None),
    ) -> None:
        if not _origin_allowed(settings, websocket.headers.get("origin")):
            await websocket.close(code=4403)
            return

        hub: InProcessEventHub = websocket.app.state.event_hub
        authenticator: WebSocketAuthenticator = websocket.app.state.ws_authenticator

        authorized = await authenticator.authorize(
            user_id_header=websocket.headers.get("x-spa-user-id"),
            organization_id=organization_id,
        )
        if authorized is None:
            # Closed before accepting: an unauthenticated peer never reaches the
            # application protocol.
            await websocket.close(code=4401)
            return

        _, resolved_organization = authorized
        channel = str(resolved_organization)

        await websocket.accept()

        async def deliver(payload: dict[str, object]) -> None:
            await websocket.send_json(payload)

        subscription_id = hub.subscribe(channel, deliver)
        try:
            while True:
                # The client sends nothing meaningful; reading keeps the socket
                # open and surfaces a disconnect. A closed socket raises here.
                await websocket.receive_text()
        except WebSocketDisconnect:
            pass
        finally:
            await hub.unsubscribe(channel, subscription_id)
