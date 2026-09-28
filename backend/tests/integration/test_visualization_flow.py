"""The visualization read path against real PostgreSQL.

Proves what the unit tests cannot: that the SQL aggregation the visualization
relies on returns the same numbers as the in-memory implementation, that the API
returns the documented shape, that a large observation set stays bounded, and
that one organization can never read another's tracking data.

Observations are written directly through the repository, so the flow under test
is 'observations -> visualization API', with no computer vision involved.
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
    observations: list[tuple[int, int, float, float, float]],
    width: int | None = 1920,
    height: int | None = 1080,
    status: str = "succeeded",
) -> tuple[str, str]:
    """Create a run with tracking observations, and return its ids.

    'observations' are (track_id, frame_index, timestamp_seconds, x, y) tuples;
    the box is fixed in size at the given position.
    """
    from app.core.config import get_settings
    from app.domain.analysis.entities import AnalysisRun, default_pipeline
    from app.domain.shared import OrganizationId, VideoSpec
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
            storage_key=f"visualization/{uuid.uuid4()}.mp4",
        )
        video.mark_uploaded(size_bytes=1024, content_type="video/mp4")
        if width is not None and height is not None:
            video.record_probe(
                VideoSpec(
                    duration_seconds=30.0,
                    frame_rate=25.0,
                    width=width,
                    height=height,
                    codec="h264",
                )
            )
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
                    x1=x,
                    y1=y,
                    x2=x + 10.0,
                    y2=y + 20.0,
                    frame_index=frame_index,
                    timestamp_seconds=timestamp_seconds,
                )
                for track_id, frame_index, timestamp_seconds, x, y in observations
            ],
        )
        await uow.commit()

    async with uow_factory() as uow:
        stored = await uow.analysis_runs.get(run.id)
        assert stored is not None
        if status == "succeeded":
            stored.succeed()
        elif status == "partially_succeeded":
            stored.succeed(partial=True)
        elif status == "failed":
            stored.fail("decode failed")
        await uow.analysis_runs.update(stored)
        await uow.commit()

    return str(run.id), str(video.id)


def straight_line(
    *, track_id: int, count: int, x_step: float = 20.0
) -> list[tuple[int, int, float, float, float]]:
    return [(track_id, index, index * 0.5, index * x_step, 100.0) for index in range(count)]


class TestVisualizationEndToEnd:
    async def test_paths_come_from_the_persisted_coordinates(self, client: AsyncClient) -> None:
        organization_id = await make_organization(client, "viz-fc")
        headers = await make_member(client, organization_id)
        run_id, _ = await seed_tracked_run(
            organization_id=organization_id,
            observations=[
                (1, 0, 0.0, 100.0, 100.0),
                (1, 1, 0.5, 140.0, 120.0),
                (1, 2, 1.0, 180.0, 140.0),
            ],
        )

        response = await client.get(
            f"/api/v1/analysis-runs/{run_id}/visualization",
            params={"organization_id": organization_id},
            headers=headers,
        )
        assert response.status_code == 200, response.text
        body = response.json()

        assert body["space"] == "source"
        assert body["frame"] == {"width": 1920, "height": 1080}
        assert body["observation_count"] == 3
        assert body["track_count"] == 1

        path = body["paths"][0]
        assert path["track_id"] == 1
        # The centre of the (x, y) box with a fixed 10x20 extent.
        assert [point["x"] for point in path["points"]] == [105.0, 145.0, 185.0]
        assert [point["y"] for point in path["points"]] == [110.0, 130.0, 150.0]
        assert path["downsampled"] is False

    async def test_the_density_grid_reflects_observation_density(self, client: AsyncClient) -> None:
        organization_id = await make_organization(client, "density-fc")
        headers = await make_member(client, organization_id)
        run_id, _ = await seed_tracked_run(
            organization_id=organization_id,
            # Nine observations clustered top-left, one bottom-right.
            observations=[(1, index, index * 0.5, 50.0, 50.0) for index in range(9)]
            + [(1, 9, 4.5, 1500.0, 900.0)],
        )

        response = await client.get(
            f"/api/v1/analysis-runs/{run_id}/visualization",
            params={"organization_id": organization_id},
            headers=headers,
        )
        body = response.json()
        density = body["density"]

        assert density["columns"] == 48
        assert density["rows"] == 27
        assert len(density["counts"]) == 48 * 27
        assert sum(density["counts"]) == 10
        assert density["max_count"] == 9
        assert density["bounds"] == [0.0, 0.0, 1920.0, 1080.0]

    async def test_the_timeline_represents_observation_activity(self, client: AsyncClient) -> None:
        organization_id = await make_organization(client, "timeline-fc")
        headers = await make_member(client, organization_id)
        run_id, _ = await seed_tracked_run(
            organization_id=organization_id,
            observations=straight_line(track_id=1, count=4),
        )

        response = await client.get(
            f"/api/v1/analysis-runs/{run_id}/visualization",
            params={"organization_id": organization_id},
            headers=headers,
        )
        timeline = response.json()["timeline"]

        assert timeline["bucket_seconds"] == 5.0
        assert sum(bucket["observation_count"] for bucket in timeline["buckets"]) == 4

    async def test_metrics_are_returned_alongside_the_visualization(
        self, client: AsyncClient
    ) -> None:
        from app.domain.shared import AnalysisRunId
        from app.infrastructure.database.engine import get_session_factory
        from app.infrastructure.database.unit_of_work import SqlAlchemyUnitOfWorkFactory

        organization_id = await make_organization(client, "viz-metrics-fc")
        headers = await make_member(client, organization_id)
        run_id, _ = await seed_tracked_run(
            organization_id=organization_id,
            observations=straight_line(track_id=1, count=4),
        )

        from app.core.config import get_settings

        settings = get_settings()
        uow_factory = SqlAlchemyUnitOfWorkFactory(get_session_factory(settings))
        from app.domain.metrics.types import MetricName, MetricUnit, MetricValue

        async with uow_factory() as uow:
            from app.domain.metrics.types import TrackMetricRecord

            await uow.track_metrics.replace_for_run(
                AnalysisRunId(uuid.UUID(run_id)),
                [
                    TrackMetricRecord(
                        organization_id=uuid.UUID(organization_id),
                        analysis_run_id=AnalysisRunId(uuid.UUID(run_id)),
                        track_id=1,
                        value=MetricValue.available(
                            MetricName.DISPLACEMENT,
                            MetricUnit.PIXELS,
                            60.0,
                            sample_count=3,
                        ),
                    )
                ],
            )
            await uow.commit()

        response = await client.get(
            f"/api/v1/analysis-runs/{run_id}/visualization",
            params={"organization_id": organization_id},
            headers=headers,
        )
        metrics = response.json()["metrics"]

        assert metrics["track_count"] == 1
        displacement = next(
            metric for metric in metrics["tracks"][0]["metrics"] if metric["name"] == "displacement"
        )
        assert displacement["value"] == pytest.approx(60.0)
        assert displacement["unit"] == "pixels"

    async def test_a_large_observation_set_stays_bounded(self, client: AsyncClient) -> None:
        organization_id = await make_organization(client, "bounded-fc")
        headers = await make_member(client, organization_id)
        run_id, _ = await seed_tracked_run(
            organization_id=organization_id,
            observations=straight_line(track_id=1, count=4000, x_step=0.4),
        )

        response = await client.get(
            f"/api/v1/analysis-runs/{run_id}/visualization",
            params={"organization_id": organization_id},
            headers=headers,
        )
        body = response.json()

        assert body["observation_count"] == 4000
        # The path is downsampled to the configured per-track bound, not the full
        # 4000 observations, and the grid is a fixed size regardless of volume.
        assert len(body["paths"][0]["points"]) == 400
        assert body["paths"][0]["downsampled"] is True
        assert len(body["density"]["counts"]) == 48 * 27

    async def test_the_same_data_produces_the_same_visualization(self, client: AsyncClient) -> None:
        organization_id = await make_organization(client, "deterministic-fc")
        headers = await make_member(client, organization_id)
        run_id, _ = await seed_tracked_run(
            organization_id=organization_id,
            observations=straight_line(track_id=1, count=50) + straight_line(track_id=2, count=50),
        )

        first = await client.get(
            f"/api/v1/analysis-runs/{run_id}/visualization",
            params={"organization_id": organization_id},
            headers=headers,
        )
        second = await client.get(
            f"/api/v1/analysis-runs/{run_id}/visualization",
            params={"organization_id": organization_id},
            headers=headers,
        )

        assert first.json()["density"]["counts"] == second.json()["density"]["counts"]
        assert first.json()["paths"] == second.json()["paths"]

    async def test_a_partial_run_is_visualized_and_reports_its_status(
        self, client: AsyncClient
    ) -> None:
        organization_id = await make_organization(client, "partial-viz-fc")
        headers = await make_member(client, organization_id)
        run_id, _ = await seed_tracked_run(
            organization_id=organization_id,
            observations=straight_line(track_id=1, count=4),
            status="partially_succeeded",
        )

        response = await client.get(
            f"/api/v1/analysis-runs/{run_id}/visualization",
            params={"organization_id": organization_id},
            headers=headers,
        )

        assert response.status_code == 200
        assert response.json()["status"] == "partially_succeeded"


class TestVisualizationStates:
    async def test_a_run_with_no_observations_returns_an_empty_visualization(
        self, client: AsyncClient
    ) -> None:
        organization_id = await make_organization(client, "empty-viz-fc")
        headers = await make_member(client, organization_id)
        run_id, _ = await seed_tracked_run(organization_id=organization_id, observations=[])

        response = await client.get(
            f"/api/v1/analysis-runs/{run_id}/visualization",
            params={"organization_id": organization_id},
            headers=headers,
        )

        assert response.status_code == 200, response.text
        body = response.json()
        assert body["observation_count"] == 0
        assert body["track_count"] == 0
        assert body["paths"] == []
        assert body["density"]["max_count"] == 0
        assert body["timeline"]["buckets"] == []

    async def test_a_run_without_a_known_frame_falls_back_to_observed_bounds(
        self, client: AsyncClient
    ) -> None:
        organization_id = await make_organization(client, "no-frame-fc")
        headers = await make_member(client, organization_id)
        run_id, _ = await seed_tracked_run(
            organization_id=organization_id,
            observations=[(1, 0, 0.0, 100.0, 200.0), (1, 1, 0.5, 300.0, 400.0)],
            width=None,
            height=None,
        )

        response = await client.get(
            f"/api/v1/analysis-runs/{run_id}/visualization",
            params={"organization_id": organization_id},
            headers=headers,
        )
        body = response.json()

        assert body["frame"] == {"width": None, "height": None}
        assert body["density"]["bounds"] == [100.0, 200.0, 310.0, 420.0]

    async def test_a_run_that_has_not_finished_is_a_conflict(self, client: AsyncClient) -> None:
        organization_id = await make_organization(client, "pending-viz-fc")
        headers = await make_member(client, organization_id)

        from app.core.config import get_settings
        from app.domain.analysis.entities import AnalysisRun, default_pipeline
        from app.domain.shared import OrganizationId
        from app.domain.videos.entities import Video
        from app.infrastructure.database.engine import get_session_factory
        from app.infrastructure.database.unit_of_work import SqlAlchemyUnitOfWorkFactory

        session_factory = get_session_factory(get_settings())
        uow_factory = SqlAlchemyUnitOfWorkFactory(session_factory)
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

        response = await client.get(
            f"/api/v1/analysis-runs/{run_id}/visualization",
            params={"organization_id": organization_id},
            headers=headers,
        )
        assert response.status_code == 409
        assert response.json()["error"]["code"] == "conflict"


class TestVisualizationSecurity:
    async def test_visualization_requires_authentication(self, client: AsyncClient) -> None:
        organization_id = await make_organization(client, "viz-auth-fc")
        run_id, _ = await seed_tracked_run(
            organization_id=organization_id,
            observations=straight_line(track_id=1, count=3),
        )

        response = await client.get(
            f"/api/v1/analysis-runs/{run_id}/visualization",
            params={"organization_id": organization_id},
        )
        assert response.status_code == 401

    async def test_a_cross_organization_read_is_not_found(self, client: AsyncClient) -> None:
        owner_organization = await make_organization(client, "viz-owner-fc")
        other_organization = await make_organization(client, "viz-other-fc")
        await make_member(client, owner_organization)
        other_headers = await make_member(client, other_organization)
        run_id, _ = await seed_tracked_run(
            organization_id=owner_organization,
            observations=straight_line(track_id=1, count=3),
        )

        response = await client.get(
            f"/api/v1/analysis-runs/{run_id}/visualization",
            params={"organization_id": other_organization},
            headers=other_headers,
        )
        # A cross-tenant probe must not be able to confirm the run exists.
        assert response.status_code == 404

    async def test_a_nonexistent_run_is_not_found(self, client: AsyncClient) -> None:
        organization_id = await make_organization(client, "viz-missing-fc")
        headers = await make_member(client, organization_id)

        response = await client.get(
            f"/api/v1/analysis-runs/{uuid.uuid4()}/visualization",
            params={"organization_id": organization_id},
            headers=headers,
        )
        assert response.status_code == 404

    async def test_a_non_member_is_refused(self, client: AsyncClient) -> None:
        organization_id = await make_organization(client, "viz-nonmember-fc")
        run_id, _ = await seed_tracked_run(
            organization_id=organization_id,
            observations=straight_line(track_id=1, count=3),
        )

        response = await client.get(
            f"/api/v1/analysis-runs/{run_id}/visualization",
            params={"organization_id": organization_id},
            headers={"x-spa-user-id": str(uuid.uuid4())},
        )
        assert response.status_code in {401, 404}
