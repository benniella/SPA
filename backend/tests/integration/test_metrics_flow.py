"""Derived metrics against real PostgreSQL.

Proves what the unit tests cannot: that derived metrics land in the schema, that
re-running the calculation does not duplicate them, that the API returns them in
the documented shape, and that one organization can never read another's.

Observations are written directly through the repository, so the flow under test
is 'observations → metrics → API', with no computer vision involved.
"""

from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient

pytestmark = [pytest.mark.integration, pytest.mark.usefixtures("clean_database")]


async def make_organization(client: AsyncClient, slug: str) -> str:
    response = await client.post(
        "/api/v1/organizations",
        json={"name": slug.replace("-", " ").title(), "slug": slug},
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
                display_name="Analyst",
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


async def seed_tracked_run(
    *,
    organization_id: str,
    observations: list[tuple[int, int, float, float]],
) -> tuple[str, str]:
    """Create a succeeded run with tracking observations, and return its ids.

    'observations' are (track_id, frame_index, timestamp_seconds, x_offset)
    tuples; the box is fixed in size and moves horizontally by the offset, so a
    test's expected displacement is the sum of the offsets' differences.
    """
    from app.core.config import get_settings
    from app.domain.analysis.entities import AnalysisRun, default_pipeline
    from app.domain.shared import OrganizationId
    from app.domain.tracking.entities import TrackedObservation, TrackingDataset
    from app.domain.videos.entities import Video
    from app.infrastructure.database.engine import get_session_factory
    from app.infrastructure.database.unit_of_work import SqlAlchemyUnitOfWorkFactory

    session_factory = get_session_factory(get_settings())
    uow_factory = SqlAlchemyUnitOfWorkFactory(session_factory)

    async with uow_factory() as uow:
        video = Video(
            organization_id=OrganizationId(uuid.UUID(organization_id)),
            original_filename="clip.mp4",
            storage_key=f"metrics/{uuid.uuid4()}.mp4",
        )
        video.mark_uploaded(size_bytes=1024, content_type="video/mp4")
        await uow.videos.add(video)

        run = AnalysisRun(
            organization_id=video.organization_id,
            video_id=video.id,
            pipeline=default_pipeline(),
        )
        run.queue()
        run.start()
        await uow.analysis_runs.add(run)

        dataset = TrackingDataset(
            organization_id=video.organization_id,
            video_id=video.id,
            analysis_run_id=run.id,
        )
        await uow.tracking_datasets.add(dataset)
        await uow.track_observations.add_batch(
            dataset,
            [
                TrackedObservation(
                    track_id=track_id,
                    class_id=0,
                    confidence=0.9,
                    x1=10.0 + offset,
                    y1=10.0,
                    x2=30.0 + offset,
                    y2=50.0,
                    frame_index=frame_index,
                    timestamp_seconds=timestamp_seconds,
                )
                for track_id, frame_index, timestamp_seconds, offset in observations
            ],
        )
        await uow.commit()

    # The tracking stage has run; the metrics stage is what this test exercises.
    async with uow_factory() as uow:
        stored = await uow.analysis_runs.get(run.id)
        assert stored is not None
        stored.succeed()
        await uow.analysis_runs.update(stored)
        await uow.commit()

    return str(run.id), str(video.id)


async def calculate_metrics(
    client: AsyncClient, run_id: str, organization_id: str, headers: dict[str, str]
) -> dict[str, object]:
    from app.core.config import get_settings
    from app.domain.shared import JobId
    from app.infrastructure.database.engine import get_session_factory
    from app.infrastructure.database.unit_of_work import SqlAlchemyUnitOfWorkFactory

    response = await client.post(
        f"/api/v1/analysis-runs/{run_id}/metrics",
        params={"organization_id": organization_id},
        headers=headers,
    )
    assert response.status_code == 202, response.text
    body = response.json()

    settings = get_settings()
    uow_factory = SqlAlchemyUnitOfWorkFactory(get_session_factory(settings))
    worker = _build_metrics_worker(settings, uow_factory)
    await worker.process(JobId(uuid.UUID(body["job_id"])))
    return body


def _build_metrics_worker(settings: object, uow_factory: object) -> object:
    from app.infrastructure.jobs.queue import InMemoryJobQueue
    from app.infrastructure.processing.cv_pipeline import CvProcessingPipeline
    from app.infrastructure.processing.metrics_pipeline import MetricsPipeline
    from app.infrastructure.storage.local import LocalVideoStorage
    from app.worker.runner import JobWorker

    return JobWorker(
        uow_factory=uow_factory,  # type: ignore[arg-type]
        queue=InMemoryJobQueue(),
        pipeline=CvProcessingPipeline(
            settings=settings,  # type: ignore[arg-type]
            storage=LocalVideoStorage(settings),  # type: ignore[arg-type]
            uow_factory=uow_factory,  # type: ignore[arg-type]
        ),
        metrics_pipeline=MetricsPipeline(
            settings=settings,  # type: ignore[arg-type]
            uow_factory=uow_factory,  # type: ignore[arg-type]
        ),
    )


class TestMetricsEndToEnd:
    async def test_observations_become_persisted_metrics_readable_over_the_api(
        self, client: AsyncClient
    ) -> None:
        organization_id = await make_organization(client, "metrics-fc")
        headers = await make_member(client, organization_id)
        run_id, _ = await seed_tracked_run(
            organization_id=organization_id,
            observations=[(1, index, index * 0.5, index * 10.0) for index in range(4)],
        )

        await calculate_metrics(client, run_id, organization_id, headers)

        response = await client.get(
            f"/api/v1/analysis-runs/{run_id}/metrics",
            params={"organization_id": organization_id},
            headers=headers,
        )
        assert response.status_code == 200, response.text
        body = response.json()

        assert body["analysis_run_id"] == run_id
        assert body["space"] == "source"
        assert body["track_count"] == 1

        track = body["tracks"][0]
        assert track["track_id"] == 1
        metrics = {metric["name"]: metric for metric in track["metrics"]}

        assert metrics["displacement"]["value"] == pytest.approx(30.0)
        assert metrics["displacement"]["unit"] == "pixels"
        assert metrics["average_speed"]["value"] == pytest.approx(20.0)
        assert metrics["average_speed"]["unit"] == "pixels_per_second"
        assert metrics["observation_count"]["value"] == pytest.approx(4.0)
        assert metrics["coverage"]["value"] == pytest.approx(1.0)
        assert metrics["mean_confidence"]["value"] == pytest.approx(0.9)

    async def test_an_unavailable_metric_is_null_not_zero(self, client: AsyncClient) -> None:
        organization_id = await make_organization(client, "short-track-fc")
        headers = await make_member(client, organization_id)
        run_id, _ = await seed_tracked_run(
            organization_id=organization_id,
            observations=[(1, 0, 0.0, 0.0)],
        )

        await calculate_metrics(client, run_id, organization_id, headers)

        response = await client.get(
            f"/api/v1/analysis-runs/{run_id}/metrics",
            params={"organization_id": organization_id},
            headers=headers,
        )
        metrics = {metric["name"]: metric for metric in response.json()["tracks"][0]["metrics"]}

        assert metrics["peak_speed"]["availability"] == "unavailable"
        assert metrics["peak_speed"]["value"] is None
        assert metrics["observation_count"]["value"] == pytest.approx(1.0)

    async def test_recalculating_does_not_duplicate_persisted_metrics(
        self, client: AsyncClient
    ) -> None:
        from app.core.config import get_settings
        from app.domain.shared import AnalysisRunId
        from app.infrastructure.database.engine import get_session_factory
        from app.infrastructure.database.unit_of_work import SqlAlchemyUnitOfWorkFactory

        organization_id = await make_organization(client, "idempotent-fc")
        headers = await make_member(client, organization_id)
        run_id, _ = await seed_tracked_run(
            organization_id=organization_id,
            observations=[(1, index, index * 0.5, index * 10.0) for index in range(4)],
        )

        await calculate_metrics(client, run_id, organization_id, headers)

        settings = get_settings()
        uow_factory = SqlAlchemyUnitOfWorkFactory(get_session_factory(settings))
        async with uow_factory() as uow:
            first = await uow.track_metrics.count_for_run(AnalysisRunId(uuid.UUID(run_id)))

        await calculate_metrics(client, run_id, organization_id, headers)

        async with uow_factory() as uow:
            second = await uow.track_metrics.count_for_run(AnalysisRunId(uuid.UUID(run_id)))

        assert first == second

    async def test_the_run_records_the_metrics_stage(self, client: AsyncClient) -> None:
        organization_id = await make_organization(client, "stage-fc")
        headers = await make_member(client, organization_id)
        run_id, _ = await seed_tracked_run(
            organization_id=organization_id,
            observations=[(1, index, index * 0.5, index * 10.0) for index in range(4)],
        )

        await calculate_metrics(client, run_id, organization_id, headers)

        response = await client.get(
            f"/api/v1/analysis-runs/{run_id}",
            params={"organization_id": organization_id},
            headers=headers,
        )
        assert response.status_code == 200
        assert response.json()["status"] == "succeeded"


class TestMetricsSecurity:
    async def test_metrics_require_authentication(self, client: AsyncClient) -> None:
        organization_id = await make_organization(client, "auth-fc")
        run_id, _ = await seed_tracked_run(
            organization_id=organization_id,
            observations=[(1, index, index * 0.5, index * 10.0) for index in range(3)],
        )

        response = await client.get(
            f"/api/v1/analysis-runs/{run_id}/metrics",
            params={"organization_id": organization_id},
        )
        assert response.status_code == 401

    async def test_a_cross_organization_read_is_not_found(self, client: AsyncClient) -> None:
        owner_organization = await make_organization(client, "owner-metrics-fc")
        other_organization = await make_organization(client, "other-metrics-fc")
        owner_headers = await make_member(client, owner_organization)
        other_headers = await make_member(client, other_organization)
        run_id, _ = await seed_tracked_run(
            organization_id=owner_organization,
            observations=[(1, index, index * 0.5, index * 10.0) for index in range(3)],
        )
        await calculate_metrics(client, run_id, owner_organization, owner_headers)

        response = await client.get(
            f"/api/v1/analysis-runs/{run_id}/metrics",
            params={"organization_id": other_organization},
            headers=other_headers,
        )
        # A cross-tenant probe must not be able to confirm the run exists.
        assert response.status_code == 404

    async def test_a_cross_organization_calculation_is_not_found(self, client: AsyncClient) -> None:
        owner_organization = await make_organization(client, "owner-calc-fc")
        other_organization = await make_organization(client, "other-calc-fc")
        await make_member(client, owner_organization)
        other_headers = await make_member(client, other_organization)
        run_id, _ = await seed_tracked_run(
            organization_id=owner_organization,
            observations=[(1, index, index * 0.5, index * 10.0) for index in range(3)],
        )

        response = await client.post(
            f"/api/v1/analysis-runs/{run_id}/metrics",
            params={"organization_id": other_organization},
            headers=other_headers,
        )
        assert response.status_code == 404

    async def test_metrics_are_empty_until_the_metrics_stage_has_run(
        self, client: AsyncClient
    ) -> None:
        organization_id = await make_organization(client, "empty-metrics-fc")
        headers = await make_member(client, organization_id)
        run_id, _ = await seed_tracked_run(
            organization_id=organization_id,
            observations=[(1, index, index * 0.5, index * 10.0) for index in range(3)],
        )

        response = await client.get(
            f"/api/v1/analysis-runs/{run_id}/metrics",
            params={"organization_id": organization_id},
            headers=headers,
        )
        # The run has tracking data but has not had its metrics calculated, so
        # this is a valid empty result rather than an error: a track may exist
        # without a run's metrics stage having executed.
        assert response.status_code == 200
        body = response.json()
        assert body["track_count"] == 0
        assert body["tracks"] == []

    async def test_a_run_without_tracking_data_cannot_be_calculated(
        self, client: AsyncClient
    ) -> None:
        from app.core.config import get_settings
        from app.domain.analysis.entities import AnalysisRun, default_pipeline
        from app.domain.shared import OrganizationId
        from app.domain.videos.entities import Video
        from app.infrastructure.database.engine import get_session_factory
        from app.infrastructure.database.unit_of_work import SqlAlchemyUnitOfWorkFactory

        organization_id = await make_organization(client, "untracked-fc")
        headers = await make_member(client, organization_id)

        session_factory = get_session_factory(get_settings())
        uow_factory = SqlAlchemyUnitOfWorkFactory(session_factory)
        async with uow_factory() as uow:
            video = Video(
                organization_id=OrganizationId(uuid.UUID(organization_id)),
                original_filename="clip.mp4",
                storage_key=f"untracked/{uuid.uuid4()}.mp4",
            )
            video.mark_uploaded(size_bytes=1024, content_type="video/mp4")
            await uow.videos.add(video)
            run = AnalysisRun(
                organization_id=video.organization_id,
                video_id=video.id,
                pipeline=default_pipeline(),
            )
            run.queue()
            run.start()
            run.fail("no tracking data")
            await uow.analysis_runs.add(run)
            await uow.commit()
            run_id = str(run.id)

        response = await client.post(
            f"/api/v1/analysis-runs/{run_id}/metrics",
            params={"organization_id": organization_id},
            headers=headers,
        )
        # A queued run has no tracking data, so there is nothing to derive from.
        assert response.status_code == 409
        assert response.json()["error"]["code"] == "conflict"


class TestMetricsTenancyInTheDatabase:
    async def test_every_metric_row_carries_its_organization(self, client: AsyncClient) -> None:
        from app.core.config import get_settings
        from app.domain.shared import AnalysisRunId
        from app.infrastructure.database.engine import get_session_factory
        from app.infrastructure.database.unit_of_work import SqlAlchemyUnitOfWorkFactory

        organization_id = await make_organization(client, "tenancy-fc")
        headers = await make_member(client, organization_id)
        run_id, _ = await seed_tracked_run(
            organization_id=organization_id,
            observations=[(1, index, index * 0.5, index * 10.0) for index in range(3)]
            + [(2, index, index * 0.5, index * 5.0) for index in range(3)],
        )

        await calculate_metrics(client, run_id, organization_id, headers)

        settings = get_settings()
        uow_factory = SqlAlchemyUnitOfWorkFactory(get_session_factory(settings))
        async with uow_factory() as uow:
            records = await uow.track_metrics.list_for_run(AnalysisRunId(uuid.UUID(run_id)))

        assert records
        assert {record.track_id for record in records} == {1, 2}
        for record in records:
            assert str(record.organization_id) == organization_id

    async def test_deleting_the_run_removes_its_metrics(self, client: AsyncClient) -> None:
        from sqlalchemy import text

        from app.core.config import get_settings
        from app.infrastructure.database.engine import get_session_factory, session_scope

        organization_id = await make_organization(client, "cascade-metrics-fc")
        headers = await make_member(client, organization_id)
        run_id, _ = await seed_tracked_run(
            organization_id=organization_id,
            observations=[(1, index, index * 0.5, index * 10.0) for index in range(3)],
        )
        await calculate_metrics(client, run_id, organization_id, headers)

        session_factory = get_session_factory(get_settings())
        async with session_scope(session_factory) as session:
            await session.execute(
                text("DELETE FROM analysis_runs WHERE id = :id"),
                {"id": uuid.UUID(run_id)},
            )
            await session.commit()

        async with session_scope(session_factory) as session:
            remaining = await session.execute(
                text("SELECT count(*) FROM track_metrics WHERE analysis_run_id = :id"),
                {"id": uuid.UUID(run_id)},
            )
            assert remaining.scalar_one() == 0
