"""End-to-end processing flow against real PostgreSQL.

Exercises API → job row → worker → database, and the polling fallback the
frontend uses after a WebSocket reconnect. KeyDB is not required here: the inline
job backend writes the same durable row the queued backend does, and the worker
is invoked directly against it, which is the part that must be proven against a
real database.
"""

from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient

pytestmark = [pytest.mark.integration, pytest.mark.usefixtures("clean_database")]


async def make_organization(client: AsyncClient, slug: str) -> str:
    """Create a workspace as an authenticated owner.

    Organization routes require an authenticated member, so the test creates the
    identity that will own the workspace and then acts as it.
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
                display_name="Owner",
                is_active=True,
            )
        )
        await session.commit()

    response = await client.post(
        "/api/v1/organizations",
        json={"name": slug.replace("-", " ").title(), "slug": slug},
        headers={"x-spa-user-id": str(user_id)},
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


async def make_member(
    client: AsyncClient, organization_id: str, *, role: str = "coach"
) -> dict[str, str]:
    from app.core.config import get_settings
    from app.infrastructure.database.engine import get_session_factory
    from app.infrastructure.database.models import OrganizationMembershipModel, UserModel

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


def _clip_bytes() -> bytes:
    """A small, real, decodable MP4.

    The worker now runs a real CV pipeline, so the uploaded object must be a
    video the decoder can open; arbitrary bytes would fail the job rather than
    exercise the success path.
    """
    import tempfile
    from pathlib import Path

    import cv2
    import numpy as np

    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "clip.mp4"
        writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), 10.0, (320, 240))
        assert writer.isOpened()
        for index in range(10):
            frame = np.full((240, 320, 3), 30, dtype=np.uint8)
            left = 10 + index * 5
            cv2.rectangle(frame, (left, 60), (left + 40, 200), (200, 200, 200), -1)
            writer.write(frame)
        writer.release()
        return path.read_bytes()


async def upload_video(
    client: AsyncClient, organization_id: str, headers: dict[str, str], *, name: str = "match.mp4"
) -> str:
    reserved = await client.post(
        "/api/v1/videos",
        json={
            "organization_id": organization_id,
            "filename": name,
            "content_type": "video/mp4",
        },
        headers=headers,
    )
    assert reserved.status_code == 201, reserved.text
    ticket = reserved.json()

    payload = _clip_bytes()
    uploaded = await client.put(
        ticket["upload_url"].replace("http://localhost:8000", ""),
        content=payload,
        headers={"content-type": "video/mp4"},
    )
    assert uploaded.status_code == 204, uploaded.text

    completed = await client.post(
        f"/api/v1/videos/{ticket['video_id']}/complete",
        json={"organization_id": organization_id, "size_bytes": len(payload)},
        headers=headers,
    )
    assert completed.status_code == 202, completed.text
    return ticket["video_id"]


def build_worker() -> object:
    """A worker bound to the same database the API uses, with local storage."""
    from app.core.config import get_settings
    from app.infrastructure.database.engine import get_session_factory
    from app.infrastructure.database.unit_of_work import SqlAlchemyUnitOfWorkFactory
    from app.infrastructure.jobs.queue import InMemoryJobQueue
    from app.infrastructure.processing.cv_pipeline import CvProcessingPipeline
    from app.infrastructure.storage.local import LocalVideoStorage
    from app.worker.runner import JobWorker

    resolved = get_settings()
    uow_factory = SqlAlchemyUnitOfWorkFactory(get_session_factory(resolved))
    return JobWorker(
        uow_factory=uow_factory,  # type: ignore[arg-type]
        queue=InMemoryJobQueue(),
        pipeline=CvProcessingPipeline(
            settings=resolved,
            storage=LocalVideoStorage(resolved),
            uow_factory=uow_factory,  # type: ignore[arg-type]
        ),
    )


class TestProcessingRequest:
    async def test_an_uploaded_video_can_be_queued_for_processing(
        self, client: AsyncClient
    ) -> None:
        organization_id = await make_organization(client, "process-fc")
        headers = await make_member(client, organization_id)
        video_id = await upload_video(client, organization_id, headers)

        response = await client.post(
            f"/api/v1/videos/{video_id}/process",
            json={"organization_id": organization_id},
            headers=headers,
        )

        assert response.status_code == 202, response.text
        job = response.json()
        assert job["status"] == "queued"
        assert job["video_id"] == video_id

    async def test_queueing_does_not_mark_the_video_processed(self, client: AsyncClient) -> None:
        organization_id = await make_organization(client, "process-fc")
        headers = await make_member(client, organization_id)
        video_id = await upload_video(client, organization_id, headers)

        await client.post(
            f"/api/v1/videos/{video_id}/process",
            json={"organization_id": organization_id},
            headers=headers,
        )

        processing = await client.get(
            f"/api/v1/videos/{video_id}/processing",
            params={"organization_id": organization_id},
            headers=headers,
        )
        assert processing.status_code == 200, processing.text
        assert processing.json()["video_status"] == "uploaded"

    async def test_a_repeated_request_does_not_create_a_second_job(
        self, client: AsyncClient
    ) -> None:
        organization_id = await make_organization(client, "process-fc")
        headers = await make_member(client, organization_id)
        video_id = await upload_video(client, organization_id, headers)

        first = await client.post(
            f"/api/v1/videos/{video_id}/process",
            json={"organization_id": organization_id},
            headers=headers,
        )
        second = await client.post(
            f"/api/v1/videos/{video_id}/process",
            json={"organization_id": organization_id},
            headers=headers,
        )

        assert first.json()["id"] == second.json()["id"]

        jobs = await client.get(
            f"/api/v1/videos/{video_id}/processing/jobs",
            params={"organization_id": organization_id},
            headers=headers,
        )
        assert len(jobs.json()) == 1

    async def test_an_incomplete_upload_cannot_be_processed(self, client: AsyncClient) -> None:
        organization_id = await make_organization(client, "process-fc")
        headers = await make_member(client, organization_id)

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

        response = await client.post(
            f"/api/v1/videos/{video_id}/process",
            json={"organization_id": organization_id},
            headers=headers,
        )
        assert response.status_code == 409
        assert response.json()["error"]["code"] == "conflict"

    async def test_processing_requires_authentication(self, client: AsyncClient) -> None:
        organization_id = await make_organization(client, "process-fc")
        headers = await make_member(client, organization_id)
        video_id = await upload_video(client, organization_id, headers)

        response = await client.post(
            f"/api/v1/videos/{video_id}/process",
            json={"organization_id": organization_id},
        )
        assert response.status_code == 401

    async def test_cross_organization_processing_is_not_found(self, client: AsyncClient) -> None:
        owner_organization = await make_organization(client, "owner-fc")
        other_organization = await make_organization(client, "other-fc")
        owner_headers = await make_member(client, owner_organization)
        other_headers = await make_member(client, other_organization)
        video_id = await upload_video(client, owner_organization, owner_headers)

        response = await client.post(
            f"/api/v1/videos/{video_id}/process",
            json={"organization_id": other_organization},
            headers=other_headers,
        )
        assert response.status_code == 404

    async def test_cross_organization_job_access_is_not_found(self, client: AsyncClient) -> None:
        owner_organization = await make_organization(client, "owner-fc")
        other_organization = await make_organization(client, "other-fc")
        owner_headers = await make_member(client, owner_organization)
        other_headers = await make_member(client, other_organization)
        video_id = await upload_video(client, owner_organization, owner_headers)

        queued = await client.post(
            f"/api/v1/videos/{video_id}/process",
            json={"organization_id": owner_organization},
            headers=owner_headers,
        )
        job_id = queued.json()["id"]

        response = await client.get(
            f"/api/v1/processing-jobs/{job_id}",
            params={"organization_id": other_organization},
            headers=other_headers,
        )
        assert response.status_code == 404


class TestWorkerAgainstTheDatabase:
    async def test_the_worker_completes_the_job_and_marks_the_video_processed(
        self, client: AsyncClient
    ) -> None:
        from app.domain.shared import JobId

        organization_id = await make_organization(client, "worker-fc")
        headers = await make_member(client, organization_id)
        video_id = await upload_video(client, organization_id, headers)

        # The ingest job runs first and marks the video 'stored', which is what
        # makes it analysable. This mirrors the product flow: upload → ingest →
        # analysis run → processing.
        ingest = await client.post(
            f"/api/v1/videos/{video_id}/process",
            json={"organization_id": organization_id},
            headers=headers,
        )
        ingest_job_id = ingest.json()["id"]

        worker = build_worker()
        ingest_result = await worker.process(JobId(uuid.UUID(ingest_job_id)))  # type: ignore[attr-defined]
        assert ingest_result is not None
        assert str(ingest_result.status) == "completed"

        # The CV pipeline attributes its output to an analysis run, so one must
        # exist before the job runs; otherwise the run is created by a separate
        # API call, as it is in the product flow.
        run = await client.post(
            "/api/v1/analysis-runs",
            json={"video_id": video_id, "organization_id": organization_id},
            headers=headers,
        )
        assert run.status_code == 202, run.text

        # A second processing request creates a new job now that the first is
        # complete, and the worker resolves the newest run for the video.
        queued = await client.post(
            f"/api/v1/videos/{video_id}/process",
            json={"organization_id": organization_id},
            headers=headers,
        )
        job_id = queued.json()["id"]

        result = await worker.process(JobId(uuid.UUID(job_id)))  # type: ignore[attr-defined]

        assert result is not None
        assert str(result.status) == "completed"

        processing = await client.get(
            f"/api/v1/videos/{video_id}/processing",
            params={"organization_id": organization_id},
            headers=headers,
        )
        body = processing.json()
        assert body["video_status"] == "ready"
        assert body["job"]["status"] == "completed"
        assert body["analysis_run_id"] is not None
        assert body["frames_processed"] == 2

        # Confirm the run itself completed and its tracking data is reachable.
        stored_run = await client.get(
            f"/api/v1/analysis-runs/{body['analysis_run_id']}",
            params={"organization_id": organization_id},
            headers=headers,
        )
        assert stored_run.status_code == 200, stored_run.text
        assert stored_run.json()["status"] == "succeeded"

    async def test_the_worker_records_a_failure_for_a_missing_object(
        self, client: AsyncClient
    ) -> None:
        from app.domain.shared import JobId

        organization_id = await make_organization(client, "worker-fc")
        headers = await make_member(client, organization_id)
        video_id = await upload_video(client, organization_id, headers)

        queued = await client.post(
            f"/api/v1/videos/{video_id}/process",
            json={"organization_id": organization_id},
            headers=headers,
        )
        job_id = queued.json()["id"]
        max_attempts = queued.json()["max_attempts"]

        # Remove the stored object behind the API's back: the pipeline must
        # notice and the failure must be persisted, not swallowed.
        from app.core.config import get_settings
        from app.infrastructure.database.engine import get_session_factory, session_scope
        from app.infrastructure.database.models import VideoModel
        from app.infrastructure.storage.local import LocalVideoStorage

        session_factory = get_session_factory(get_settings())
        async with session_scope(session_factory) as session:
            model = await session.get(VideoModel, uuid.UUID(video_id))
            assert model is not None
            storage_key = model.storage_key
        await LocalVideoStorage(get_settings()).delete(storage_key)

        worker = build_worker()
        # The first failure is retried, so the job returns to the queue rather
        # than terminating; the budget is exhausted before it is left failed.
        for _ in range(max_attempts):
            await worker.process(JobId(uuid.UUID(job_id)))  # type: ignore[attr-defined]

        processing = await client.get(
            f"/api/v1/videos/{video_id}/processing",
            params={"organization_id": organization_id},
            headers=headers,
        )
        body = processing.json()
        assert body["job"]["status"] == "failed"
        assert body["job"]["error"]
        assert body["job"]["attempt"] == max_attempts
        assert body["video_status"] == "failed"
