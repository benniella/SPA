"""Integration tests against a real PostgreSQL database.

Marked ' 'integration' ' and run with ' 'pytest -m integration' '. They verify the
things a substitute database cannot: JSONB round-trips, check constraints,
' 'ON DELETE' ' cascade behaviour, and the tenancy scoping the repositories apply.

' 'make integration-test' ' points ' 'DATABASE_URL' ' at a disposable database and
runs migrations first. If the database is unreachable the tests fail with a
clear message rather than silently passing.
"""

from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient

# Every test in this module runs against a freshly truncated database, so it does
# not depend on what a previous test or a previous run left behind.
pytestmark = [pytest.mark.integration, pytest.mark.usefixtures("clean_database")]


async def _owner_headers(display_name: str = "Owner") -> dict[str, str]:
    """Create an identity to act as, and return its header.

    Organization routes require an authenticated member, so every test that
    creates a workspace needs an identity to create it with.
    """
    from app.core.config import get_settings
    from app.infrastructure.database.engine import get_session_factory
    from app.infrastructure.database.models import UserModel

    user_id = uuid.uuid4()
    session_factory = get_session_factory(get_settings())
    async with session_factory() as session:
        session.add(
            UserModel(
                id=user_id,
                email=f"{user_id}@example.com",
                display_name=display_name,
                is_active=True,
            )
        )
        await session.commit()
    return {"x-spa-user-id": str(user_id)}


async def create_organization(
    client: AsyncClient, *, name: str, slug: str
) -> tuple[dict[str, object], dict[str, str]]:
    """Create a workspace as a new authenticated owner, and return it with the caller."""
    headers = await _owner_headers()
    response = await client.post(
        "/api/v1/organizations",
        json={"name": name, "slug": slug},
        headers=headers,
    )
    assert response.status_code == 201, response.text
    return response.json(), headers


class TestOrganizationRoundTrip:
    async def test_create_then_read(self, client: AsyncClient) -> None:
        organization, headers = await create_organization(
            client, name="Acme FC", slug="acme-fc"
        )

        fetched = await client.get(f"/api/v1/organizations/{organization['id']}", headers=headers)
        assert fetched.status_code == 200
        assert fetched.json()["slug"] == "acme-fc"

    async def test_duplicate_slug_conflicts(self, client: AsyncClient) -> None:
        _, headers = await create_organization(client, name="Duplicate FC", slug="duplicate-fc")

        response = await client.post(
            "/api/v1/organizations",
            json={"name": "Duplicate FC", "slug": "duplicate-fc"},
            headers=headers,
        )
        assert response.status_code == 409
        assert response.json()["error"]["code"] == "conflict"

    async def test_creating_an_organization_requires_authentication(
        self, client: AsyncClient
    ) -> None:
        response = await client.post(
            "/api/v1/organizations", json={"name": "Acme FC", "slug": "acme-fc"}
        )
        assert response.status_code == 401

    async def test_a_workspace_the_caller_does_not_belong_to_is_not_found(
        self, client: AsyncClient
    ) -> None:
        organization, _ = await create_organization(client, name="Private FC", slug="private-fc")
        stranger = await _owner_headers("Stranger")

        response = await client.get(
            f"/api/v1/organizations/{organization['id']}", headers=stranger
        )
        assert response.status_code == 404


class TestTenancyScoping:
    async def test_cross_organization_read_is_not_found(self, client: AsyncClient) -> None:
        first, owner_headers = await create_organization(client, name="Org One", slug="org-one")
        second, _ = await create_organization(client, name="Org Two", slug="org-two")

        team = (
            await client.post(
                "/api/v1/teams",
                json={
                    "organization_id": first["id"],
                    "name": "First Team",
                    "slug": "first-team",
                },
                headers=owner_headers,
            )
        ).json()

        # A member of the other organization, not of the first one.
        stranger = await _owner_headers("Stranger")

        listed = await client.get(
            "/api/v1/teams", params={"organization_id": first["id"]}, headers=stranger
        )
        assert listed.status_code == 404

        # ...and fetching by id must not confirm that it exists.
        fetched = await client.get(
            f"/api/v1/teams/{team['id']}",
            params={"organization_id": first["id"]},
            headers=stranger,
        )
        assert fetched.status_code == 404

        # The owner can still see their own team.
        own = await client.get(
            f"/api/v1/teams/{team['id']}",
            params={"organization_id": first["id"]},
            headers=owner_headers,
        )
        assert own.status_code == 200
        assert second["id"] != first["id"]


class TestVideoWorkflow:
    async def _organization(self, client: AsyncClient, *, slug: str = "video-fc") -> str:
        organization, _ = await create_organization(client, name="Video FC", slug=slug)
        return str(organization["id"])

    async def _member(
        self,
        client: AsyncClient,
        organization_id: str,
        *,
        role: str = "coach",
    ) -> dict[str, str]:
        """Create a user and a membership, and return the identity header.

        The header stands in for the credential exchange the authentication phase
        will introduce; the API resolves it to a real user record and authorizes
        from the membership, which is what these tests exercise.
        """
        from app.core.config import get_settings
        from app.infrastructure.database.engine import get_session_factory
        from app.infrastructure.database.models import (
            OrganizationMembershipModel,
            UserModel,
        )

        user_id = uuid.uuid4()
        session_factory = get_session_factory(get_settings())
        async with session_factory() as session:
            session.add(
                UserModel(
                    id=user_id,
                    email=f"{user_id}@example.com",
                    display_name="Coach",
                    is_active=True,
                )
            )
            session.add(
                OrganizationMembershipModel(
                    organization_id=uuid.UUID(organization_id),
                    user_id=user_id,
                    role=role,
                )
            )
            await session.commit()
        return {"x-spa-user-id": str(user_id)}

    async def test_upload_is_two_step_and_async(self, client: AsyncClient) -> None:
        organization_id = await self._organization(client)
        headers = await self._member(client, organization_id)

        # Step 1: reserve a slot. No bytes, no processing.
        reserved = await client.post(
            "/api/v1/videos",
            json={
                "organization_id": organization_id,
                "filename": "match.mp4",
                "content_type": "video/mp4",
            },
            headers=headers,
        )
        assert reserved.status_code == 201, reserved.text
        ticket = reserved.json()
        assert ticket["upload_url"]
        assert ticket["video_id"]

        # Step 2: push the bytes straight to storage (local adapter → the API's
        # own upload endpoint, standing in for S3).
        payload = b"not really a video, but bytes are bytes"
        uploaded = await client.put(
            ticket["upload_url"].replace("http://localhost:8000", ""),
            content=payload,
            headers={"content-type": "video/mp4"},
        )
        assert uploaded.status_code == 204, uploaded.text

        # Step 3: confirm. Returns 202 because ingestion is asynchronous.
        completed = await client.post(
            f"/api/v1/videos/{ticket['video_id']}/complete",
            json={"organization_id": organization_id, "size_bytes": len(payload)},
            headers=headers,
        )
        assert completed.status_code == 202, completed.text
        assert completed.json()["status"] == "uploaded"

        # Completion is idempotent: a retry returns the same recorded state.
        repeated = await client.post(
            f"/api/v1/videos/{ticket['video_id']}/complete",
            json={"organization_id": organization_id, "size_bytes": len(payload)},
            headers=headers,
        )
        assert repeated.status_code == 202
        assert repeated.json()["status"] == "uploaded"

    async def test_upload_requires_authentication(self, client: AsyncClient) -> None:
        organization_id = await self._organization(client)

        response = await client.post(
            "/api/v1/videos",
            json={
                "organization_id": organization_id,
                "filename": "match.mp4",
                "content_type": "video/mp4",
            },
        )
        assert response.status_code == 401

    async def test_cannot_upload_into_another_organization(self, client: AsyncClient) -> None:
        owner_organization = await self._organization(client, slug="owner-fc")
        other_organization = await self._organization(client, slug="other-fc")
        headers = await self._member(client, other_organization)

        response = await client.post(
            "/api/v1/videos",
            json={
                "organization_id": owner_organization,
                "filename": "match.mp4",
                "content_type": "video/mp4",
            },
            headers=headers,
        )
        # A non-member must not be able to confirm the workspace exists.
        assert response.status_code == 404

    async def test_completion_rejects_a_missing_object(self, client: AsyncClient) -> None:
        organization_id = await self._organization(client)
        headers = await self._member(client, organization_id)

        reserved = await client.post(
            "/api/v1/videos",
            json={
                "organization_id": organization_id,
                "filename": "never-uploaded.mp4",
                "content_type": "video/mp4",
            },
            headers=headers,
        )
        video_id = reserved.json()["video_id"]

        completed = await client.post(
            f"/api/v1/videos/{video_id}/complete",
            json={"organization_id": organization_id},
            headers=headers,
        )
        assert completed.status_code == 409

    async def test_delete_removes_the_video_and_is_org_scoped(self, client: AsyncClient) -> None:
        organization_id = await self._organization(client)
        headers = await self._member(client, organization_id)

        reserved = await client.post(
            "/api/v1/videos",
            json={
                "organization_id": organization_id,
                "filename": "delete-me.mp4",
                "content_type": "video/mp4",
            },
            headers=headers,
        )
        video_id = reserved.json()["video_id"]

        deleted = await client.delete(
            f"/api/v1/videos/{video_id}",
            params={"organization_id": organization_id},
            headers=headers,
        )
        assert deleted.status_code == 204, deleted.text

        fetched = await client.get(
            f"/api/v1/videos/{video_id}",
            params={"organization_id": organization_id},
            headers=headers,
        )
        assert fetched.status_code == 404

    async def test_analysis_run_returns_202_with_a_location(self, client: AsyncClient) -> None:
        organization_id = await self._organization(client)
        headers = await self._member(client, organization_id)

        reserved = await client.post(
            "/api/v1/videos",
            json={
                "organization_id": organization_id,
                "filename": "run.mp4",
                "content_type": "video/mp4",
            },
            headers=headers,
        )
        ticket = reserved.json()
        await client.put(
            ticket["upload_url"].replace("http://localhost:8000", ""),
            content=b"bytes",
            headers={"content-type": "video/mp4"},
        )
        await client.post(
            f"/api/v1/videos/{ticket['video_id']}/complete",
            json={"organization_id": organization_id},
            headers=headers,
        )

        # A completed upload is 'uploaded', not analysable: probing promotes it to
        # 'stored', and that is worker work which does not exist yet. Promote it
        # directly here so the analysis contract itself can be exercised.
        await self._mark_stored(ticket["video_id"])

        queued = await client.post(
            "/api/v1/analysis-runs",
            json={"video_id": ticket["video_id"], "organization_id": organization_id},
        )

        # 202 + Location is the entire contract for asynchronous work.
        assert queued.status_code == 202, queued.text
        assert queued.headers["location"].startswith("/api/v1/analysis-runs/")
        run = queued.json()
        assert run["status"] == "queued"
        assert run["progress_percent"] == 0.0

        polled = await client.get(
            queued.headers["location"],
            params={"organization_id": organization_id},
        )
        assert polled.status_code == 200
        assert polled.json()["id"] == run["id"]

    async def _mark_stored(self, video_id: str) -> None:
        """Apply the probe transition the ingestion worker will perform."""
        from sqlalchemy import update

        from app.core.config import get_settings
        from app.infrastructure.database.engine import get_session_factory
        from app.infrastructure.database.models import VideoModel

        session_factory = get_session_factory(get_settings())
        async with session_factory() as session:
            await session.execute(
                update(VideoModel)
                .where(VideoModel.id == uuid.UUID(video_id))
                .values(status="stored")
            )
            await session.commit()

    async def test_analysis_refuses_an_unuploaded_video(self, client: AsyncClient) -> None:
        organization_id = await self._organization(client)
        headers = await self._member(client, organization_id)

        reserved = await client.post(
            "/api/v1/videos",
            json={
                "organization_id": organization_id,
                "filename": "never-uploaded.mp4",
                "content_type": "video/mp4",
            },
            headers=headers,
        )
        video_id = reserved.json()["video_id"]

        # The upload never happened, so the video is not analysable.
        queued = await client.post(
            "/api/v1/analysis-runs",
            json={"video_id": video_id, "organization_id": organization_id},
        )
        assert queued.status_code == 409


class TestPlayerSquadResolution:
    async def test_listing_players_accepts_a_historical_date(self, client: AsyncClient) -> None:
        organization, headers = await create_organization(
            client, name="Squad FC", slug="squad-fc"
        )
        team = (
            await client.post(
                "/api/v1/teams",
                json={
                    "organization_id": organization["id"],
                    "name": "Under 18",
                    "slug": "under-18",
                },
                headers=headers,
            )
        ).json()
        await client.post(
            "/api/v1/players",
            json={"organization_id": organization["id"], "display_name": "A Player"},
            headers=headers,
        )

        response = await client.get(
            "/api/v1/players",
            params={
                "organization_id": organization["id"],
                "team_id": team["id"],
                "on_date": "2025-09-01",
            },
            headers=headers,
        )

        # Resolving a squad for a past date is a supported query shape from day
        # one, because historical matches must not be rewritten by transfers.
        assert response.status_code == 200
        assert "items" in response.json()
