"""WebSocket authorization and delivery tests.

The boundary that matters: a connection is authorized against an organization
server-side, and an event published to one organization reaches only that
organization's connections.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app.application.events import ProcessingEvent
from app.core.config import Settings
from app.domain.organizations.entities import MembershipRole, Organization, OrganizationMembership
from app.domain.shared import OrganizationId, Slug, UserId, new_id
from app.domain.users.entities import Email, User
from app.infrastructure.realtime.hub import InProcessEventHub


def make_settings(**overrides: object) -> Settings:
    return Settings(
        database_url="postgresql+psycopg://spa:spa@localhost:5432/spa_test",
        session_secret="x" * 32,
        websocket_allowed_origins="http://localhost:3000",
        **overrides,  # type: ignore[arg-type]
    )


class StubAuthenticator:
    """A deterministic authenticator for the transport-level tests.

    The real authorization rule is exercised in the use-case tests; here it is
    stubbed so the socket behaviour (reject, deliver, isolate) can be tested
    without a database.
    """

    def __init__(self, allowed: set[str]) -> None:
        self._allowed = allowed

    async def authorize(
        self, *, user_id_header: str | None, organization_id: str | None
    ) -> tuple[UserId, OrganizationId] | None:
        if user_id_header is None or organization_id is None:
            return None
        if organization_id not in self._allowed:
            return None
        import uuid

        return UserId(uuid.UUID(user_id_header)), OrganizationId(uuid.UUID(organization_id))


def event_for(organization_id: str, video_id: str) -> ProcessingEvent:
    return ProcessingEvent(
        event="processing.completed",
        job_id=str(new_id()),
        video_id=video_id,
        status="completed",
        progress=100.0,
        timestamp=datetime.now(UTC),
    )


ALLOWED_ORIGIN = "http://localhost:3000"


def build_client(allowed: set[str], hub: InProcessEventHub) -> TestClient:
    from app.main import create_app

    app = create_app(make_settings())
    app.state.event_hub = hub
    app.state.ws_authenticator = StubAuthenticator(allowed)
    return TestClient(app)


def authorized_headers() -> dict[str, str]:
    return {"x-spa-user-id": str(new_id()), "origin": ALLOWED_ORIGIN}


class TestUnauthenticatedRejection:
    def test_a_connection_without_identity_is_rejected(self) -> None:
        hub = InProcessEventHub()
        client = build_client(set(), hub)
        organization_id = str(new_id())

        with (
            pytest.raises(WebSocketDisconnect),
            client.websocket_connect(f"/ws/processing?organization_id={organization_id}"),
        ):
            pass

    def test_a_connection_for_a_non_member_organization_is_rejected(self) -> None:
        hub = InProcessEventHub()
        client = build_client(set(), hub)

        with (
            pytest.raises(WebSocketDisconnect),
            client.websocket_connect(f"/ws/processing?organization_id={new_id()}") as socket,
        ):
            socket.send_text("hello")


class TestAuthorizedDelivery:
    async def test_an_authorized_subscriber_receives_its_organizations_event(self) -> None:
        hub = InProcessEventHub()
        organization_id = str(new_id())
        video_id = str(new_id())
        received: list[dict[str, object]] = []

        hub.subscribe(organization_id, lambda payload: _record(received, payload))
        await hub.publish(organization_id, event_for(organization_id, video_id))

        assert received[0]["video_id"] == video_id
        assert received[0]["event"] == "processing.completed"

    def test_an_authorized_connection_is_accepted(self) -> None:
        hub = InProcessEventHub()
        organization_id = str(new_id())
        client = build_client({organization_id}, hub)

        # The handshake completing is the assertion: an unauthorized peer is
        # closed before it gets here.
        with client.websocket_connect(
            f"/ws/processing?organization_id={organization_id}",
            headers=authorized_headers(),
        ):
            pass


class TestOrganizationIsolation:
    async def test_an_event_for_another_organization_is_not_delivered(self) -> None:
        hub = InProcessEventHub()
        subscriber_org = str(new_id())
        other_org = str(new_id())
        received: list[dict[str, object]] = []

        hub.subscribe(subscriber_org, lambda payload: _record(received, payload))
        await hub.publish(other_org, event_for(other_org, str(new_id())))

        assert received == []

    def test_a_subscription_is_removed_when_the_connection_closes(self) -> None:
        hub = InProcessEventHub()
        organization_id = str(new_id())
        client = build_client({organization_id}, hub)

        with client.websocket_connect(
            f"/ws/processing?organization_id={organization_id}",
            headers=authorized_headers(),
        ):
            assert hub.subscriber_count == 1

        assert hub.subscriber_count == 0


async def _record(sink: list[dict[str, object]], payload: dict[str, object]) -> None:
    sink.append(payload)


class TestOriginPolicy:
    def test_a_disallowed_origin_is_rejected(self) -> None:
        hub = InProcessEventHub()
        organization_id = str(new_id())
        client = build_client({organization_id}, hub)

        with (
            pytest.raises(WebSocketDisconnect),
            client.websocket_connect(
                f"/ws/processing?organization_id={organization_id}",
                headers={"x-spa-user-id": str(new_id()), "origin": "https://evil.example"},
            ) as socket,
        ):
            socket.send_text("hello")


class TestRealAuthenticator:
    async def test_authorize_requires_both_identity_and_organization(self) -> None:
        from app.api.websocket import WebSocketAuthenticator

        settings = make_settings()
        authenticator = WebSocketAuthenticator(settings, lambda: None)
        assert await authenticator.authorize(user_id_header=None, organization_id=None) is None
        assert await authenticator.authorize(user_id_header="x", organization_id=None) is None

    async def test_authorize_rejects_a_non_member(self) -> None:
        from app.api.websocket import WebSocketAuthenticator
        from tests.unit.application.fakes import UnitOfWorkStub

        uow = UnitOfWorkStub()
        organization_id = OrganizationId(new_id())
        user = User(email=Email("member@example.com"), display_name="Member")
        await uow.users.add(user)
        # A user in a different organization must not be authorized for this one.
        uow.organizations.memberships.append(
            OrganizationMembership(
                organization_id=OrganizationId(new_id()),
                user_id=user.id,
                role=MembershipRole.VIEWER,
            )
        )

        authenticator = WebSocketAuthenticator(make_settings(), lambda: uow)
        result = await authenticator.authorize(
            user_id_header=str(user.id), organization_id=str(organization_id)
        )
        assert result is None

    async def test_authorize_accepts_a_member(self) -> None:
        from app.api.websocket import WebSocketAuthenticator
        from tests.unit.application.fakes import UnitOfWorkStub

        uow = UnitOfWorkStub()
        organization = Organization(name="Org", slug=Slug("org"))
        await uow.organizations.add(organization)
        user = User(email=Email("member@example.com"), display_name="Member")
        await uow.users.add(user)
        uow.organizations.memberships.append(
            OrganizationMembership(
                organization_id=organization.id,
                user_id=user.id,
                role=MembershipRole.VIEWER,
            )
        )

        authenticator = WebSocketAuthenticator(make_settings(), lambda: uow)
        result = await authenticator.authorize(
            user_id_header=str(user.id), organization_id=str(organization.id)
        )
        assert result is not None
        assert result[1] == organization.id

    async def test_authorize_is_unavailable_in_production(self) -> None:
        from app.api.websocket import WebSocketAuthenticator
        from tests.unit.application.fakes import UnitOfWorkStub

        authenticator = WebSocketAuthenticator(
            make_settings(environment="production"), lambda: UnitOfWorkStub()
        )
        result = await authenticator.authorize(
            user_id_header=str(new_id()), organization_id=str(new_id())
        )
        assert result is None
