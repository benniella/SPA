"""The report flow against real PostgreSQL.

Proves what the unit tests cannot: that a report is composed from the persisted
tracking observations and track_metrics of an analysis run, persisted, and served
with the documented shape — and that organization isolation holds for every
report endpoint. Observations and metrics are written directly, so the flow under
test is 'analysis run -> metrics -> report', with no computer vision involved.
"""

from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient

from tests.integration.test_visualization_flow import (
    make_member,
    make_organization,
    seed_tracked_run,
    straight_line,
)

pytestmark = [pytest.mark.integration, pytest.mark.usefixtures("clean_database")]


async def seed_metrics(run_id: str, organization_id: str) -> None:
    from app.core.config import get_settings
    from app.domain.metrics.types import (
        MetricName,
        MetricUnit,
        MetricValue,
        TrackMetricRecord,
    )
    from app.domain.shared import AnalysisRunId
    from app.infrastructure.database.engine import get_session_factory
    from app.infrastructure.database.unit_of_work import SqlAlchemyUnitOfWorkFactory

    uow_factory = SqlAlchemyUnitOfWorkFactory(get_session_factory(get_settings()))
    run = AnalysisRunId(uuid.UUID(run_id))
    async with uow_factory() as uow:
        await uow.track_metrics.replace_for_run(
            run,
            [
                TrackMetricRecord(
                    organization_id=uuid.UUID(organization_id),
                    analysis_run_id=run,
                    track_id=1,
                    value=MetricValue.available(
                        MetricName.OBSERVATION_COUNT, MetricUnit.COUNT, 4.0, sample_count=4
                    ),
                ),
                TrackMetricRecord(
                    organization_id=uuid.UUID(organization_id),
                    analysis_run_id=run,
                    track_id=1,
                    value=MetricValue.available(
                        MetricName.DISPLACEMENT, MetricUnit.PIXELS, 60.0, sample_count=3
                    ),
                ),
                TrackMetricRecord(
                    organization_id=uuid.UUID(organization_id),
                    analysis_run_id=run,
                    track_id=2,
                    value=MetricValue.available(
                        MetricName.PEAK_SPEED,
                        MetricUnit.PIXELS_PER_SECOND,
                        51.2,
                        sample_count=3,
                    ),
                ),
                TrackMetricRecord(
                    organization_id=uuid.UUID(organization_id),
                    analysis_run_id=run,
                    track_id=2,
                    value=MetricValue.unavailable(MetricName.DISPLACEMENT, MetricUnit.PIXELS),
                ),
            ],
        )
        await uow.commit()


async def drive_report_job(run_id: str) -> None:
    """Run the real worker over the report job the API queued.

    The API only queues; the worker is what composes the report, so the test runs
    the same pipeline a deployed worker would.
    """
    from app.core.config import get_settings
    from app.domain.shared import AnalysisRunId, JobId
    from app.infrastructure.database.engine import get_session_factory
    from app.infrastructure.database.unit_of_work import SqlAlchemyUnitOfWorkFactory

    settings = get_settings()
    uow_factory = SqlAlchemyUnitOfWorkFactory(get_session_factory(settings))
    worker = _build_report_worker(settings, uow_factory)

    async with uow_factory() as uow:
        run = await uow.analysis_runs.get(AnalysisRunId(uuid.UUID(run_id)))
        assert run is not None
        job = await uow.processing_jobs.find_active(run.video_id, REPORT_JOB_TYPE)
    assert job is not None
    await worker.process(JobId(job.id))


async def generate_report(
    client: AsyncClient, run_id: str, organization_id: str, headers: dict[str, str]
) -> str:
    response = await client.post(
        f"/api/v1/analysis-runs/{run_id}/reports",
        params={"organization_id": organization_id},
        headers=headers,
    )
    assert response.status_code == 202, response.text
    report_id = response.json()["id"]
    await drive_report_job(run_id)
    return report_id


REPORT_JOB_TYPE = "generate_report"


def _build_report_worker(settings: object, uow_factory: object) -> object:
    from app.infrastructure.jobs.queue import InMemoryJobQueue
    from app.infrastructure.processing.cv_pipeline import CvProcessingPipeline
    from app.infrastructure.processing.report_pipeline import ReportPipeline
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
        report_pipeline=ReportPipeline(
            settings=settings,  # type: ignore[arg-type]
            uow_factory=uow_factory,  # type: ignore[arg-type]
        ),
    )


class TestReportEndToEnd:
    async def test_a_report_is_composed_from_persisted_analysis_data(
        self, client: AsyncClient
    ) -> None:
        organization_id = await make_organization(client, "report-fc")
        headers = await make_member(client, organization_id)
        run_id, _ = await seed_tracked_run(
            organization_id=organization_id,
            observations=straight_line(track_id=1, count=4) + straight_line(track_id=2, count=2),
        )
        await seed_metrics(run_id, organization_id)

        created = await client.post(
            f"/api/v1/analysis-runs/{run_id}/reports",
            params={"organization_id": organization_id},
            headers=headers,
        )
        assert created.status_code == 202, created.text
        report_id = created.json()["id"]
        assert created.headers["Location"] == f"/api/v1/reports/{report_id}"
        assert created.json()["analysis_run_id"] == run_id
        assert created.json()["status"] == "generating"

        await drive_report_job(run_id)

        detail = await client.get(
            f"/api/v1/reports/{report_id}",
            params={"organization_id": organization_id},
            headers=headers,
        )
        assert detail.status_code == 200, detail.text
        assert detail.json()["status"] == "ready"
        content = detail.json()["content"]
        assert content is not None

        overview = content["overview"]
        assert overview["analysis_run_id"] == run_id
        assert overview["track_count"] == 2
        assert overview["observation_count"] == 6
        assert overview["space"] == "source"
        assert overview["source_width"] == 1920
        assert overview["source_height"] == 1080

        track_ids = [track["track_id"] for track in content["tracks"]]
        assert track_ids == [1, 2]

    async def test_an_unavailable_metric_is_reported_as_unavailable(
        self, client: AsyncClient
    ) -> None:
        organization_id = await make_organization(client, "report-partial-fc")
        headers = await make_member(client, organization_id)
        run_id, _ = await seed_tracked_run(
            organization_id=organization_id,
            observations=straight_line(track_id=1, count=3) + straight_line(track_id=2, count=3),
        )
        await seed_metrics(run_id, organization_id)

        report_id = await generate_report(client, run_id, organization_id, headers)
        detail = await client.get(
            f"/api/v1/reports/{report_id}",
            params={"organization_id": organization_id},
            headers=headers,
        )

        tracks = {track["track_id"]: track for track in detail.json()["content"]["tracks"]}
        displacement = next(
            metric for metric in tracks[2]["metrics"] if metric["name"] == "displacement"
        )
        assert displacement["availability"] == "unavailable"
        assert displacement["value"] is None

    async def test_the_report_records_a_factual_observation(self, client: AsyncClient) -> None:
        organization_id = await make_organization(client, "report-observation-fc")
        headers = await make_member(client, organization_id)
        run_id, _ = await seed_tracked_run(
            organization_id=organization_id,
            observations=straight_line(track_id=1, count=3) + straight_line(track_id=2, count=3),
        )
        await seed_metrics(run_id, organization_id)

        report_id = await generate_report(client, run_id, organization_id, headers)
        detail = await client.get(
            f"/api/v1/reports/{report_id}",
            params={"organization_id": organization_id},
            headers=headers,
        )

        observations = detail.json()["content"]["observations"]
        peak = next(
            observation
            for observation in observations
            if observation["type"] == "highest_peak_speed"
        )
        assert peak["track_ids"] == [2]
        assert peak["value"] == pytest.approx(51.2)
        assert peak["space"] == "source"

    async def test_repeated_generation_returns_the_same_report(self, client: AsyncClient) -> None:
        organization_id = await make_organization(client, "report-idempotent-fc")
        headers = await make_member(client, organization_id)
        run_id, _ = await seed_tracked_run(
            organization_id=organization_id, observations=straight_line(track_id=1, count=3)
        )
        await seed_metrics(run_id, organization_id)

        first = await client.post(
            f"/api/v1/analysis-runs/{run_id}/reports",
            params={"organization_id": organization_id},
            headers=headers,
        )
        second = await client.post(
            f"/api/v1/analysis-runs/{run_id}/reports",
            params={"organization_id": organization_id},
            headers=headers,
        )

        assert first.json()["id"] == second.json()["id"]

    async def test_a_run_that_has_not_finished_cannot_be_reported_on(
        self, client: AsyncClient
    ) -> None:
        organization_id = await make_organization(client, "report-pending-fc")
        headers = await make_member(client, organization_id)

        from app.core.config import get_settings
        from app.domain.analysis.entities import AnalysisRun, default_pipeline
        from app.domain.shared import OrganizationId
        from app.domain.videos.entities import Video
        from app.infrastructure.database.engine import get_session_factory
        from app.infrastructure.database.unit_of_work import SqlAlchemyUnitOfWorkFactory

        uow_factory = SqlAlchemyUnitOfWorkFactory(get_session_factory(get_settings()))
        async with uow_factory() as uow:
            video = Video(
                organization_id=OrganizationId(uuid.UUID(organization_id)),
                original_filename="clip.mp4",
                storage_key=f"pending/{uuid.uuid4()}.mp4",
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
            await uow.commit()
            run_id = str(run.id)

        response = await client.post(
            f"/api/v1/analysis-runs/{run_id}/reports",
            params={"organization_id": organization_id},
            headers=headers,
        )

        assert response.status_code == 409
        assert response.json()["error"]["code"] == "conflict"

    async def test_reports_are_listed_for_the_organization(self, client: AsyncClient) -> None:
        organization_id = await make_organization(client, "report-list-fc")
        headers = await make_member(client, organization_id)
        run_id, _ = await seed_tracked_run(
            organization_id=organization_id, observations=straight_line(track_id=1, count=3)
        )
        await client.post(
            f"/api/v1/analysis-runs/{run_id}/reports",
            params={"organization_id": organization_id},
            headers=headers,
        )

        response = await client.get(
            "/api/v1/reports", params={"organization_id": organization_id}, headers=headers
        )

        assert response.status_code == 200, response.text
        assert len(response.json()["items"]) == 1


class TestReportSecurity:
    async def test_creating_a_report_requires_authentication(self, client: AsyncClient) -> None:
        organization_id = await make_organization(client, "report-auth-fc")
        run_id, _ = await seed_tracked_run(
            organization_id=organization_id, observations=straight_line(track_id=1, count=3)
        )

        response = await client.post(
            f"/api/v1/analysis-runs/{run_id}/reports",
            params={"organization_id": organization_id},
        )

        assert response.status_code == 401

    async def test_a_cross_organization_report_is_not_found(self, client: AsyncClient) -> None:
        owner = await make_organization(client, "report-owner-fc")
        other = await make_organization(client, "report-other-fc")
        owner_headers = await make_member(client, owner)
        other_headers = await make_member(client, other)
        run_id, _ = await seed_tracked_run(
            organization_id=owner, observations=straight_line(track_id=1, count=3)
        )
        await seed_metrics(run_id, owner)

        created = await client.post(
            f"/api/v1/analysis-runs/{run_id}/reports",
            params={"organization_id": owner},
            headers=owner_headers,
        )
        report_id = created.json()["id"]

        response = await client.get(
            f"/api/v1/reports/{report_id}",
            params={"organization_id": other},
            headers=other_headers,
        )

        assert response.status_code == 404

    async def test_a_cross_organization_run_cannot_be_reported_on(
        self, client: AsyncClient
    ) -> None:
        owner = await make_organization(client, "report-owner-2-fc")
        other = await make_organization(client, "report-other-2-fc")
        other_headers = await make_member(client, other)
        run_id, _ = await seed_tracked_run(
            organization_id=owner, observations=straight_line(track_id=1, count=3)
        )

        response = await client.post(
            f"/api/v1/analysis-runs/{run_id}/reports",
            params={"organization_id": other},
            headers=other_headers,
        )

        assert response.status_code == 404

    async def test_a_nonexistent_report_is_not_found(self, client: AsyncClient) -> None:
        organization_id = await make_organization(client, "report-missing-fc")
        headers = await make_member(client, organization_id)

        response = await client.get(
            f"/api/v1/reports/{uuid.uuid4()}",
            params={"organization_id": organization_id},
            headers=headers,
        )

        assert response.status_code == 404
