"""The visualization read use case against in-memory fakes.

These assert the properties the API depends on: a run's visualization is derived
from its observations, the output is bounded, and access is organization-scoped.
"""

from __future__ import annotations

import uuid

import pytest

from app.application.use_cases import visualizations as use_cases
from app.core.config import Settings
from app.core.errors import ConflictError, NotFoundError
from app.domain.analysis.entities import AnalysisRun, default_pipeline
from app.domain.organizations.entities import MembershipRole, Organization, OrganizationMembership
from app.domain.shared import OrganizationId, Slug, UserId, VideoSpec, new_id
from app.domain.tracking.entities import TrackedObservation, TrackingDataset
from app.domain.users.entities import Email, User
from app.domain.videos.entities import Video
from tests.unit.application.fakes import UnitOfWorkStub

SETTINGS = Settings(
    session_secret="unit-test-session-secret-that-is-long-enough",
    visualization_grid_columns=4,
    visualization_grid_rows=4,
    visualization_max_points_per_track=3,
    visualization_timeline_bucket_seconds=1.0,
)


async def seed_member(
    uow: UnitOfWorkStub,
    *,
    organization_id: OrganizationId,
    role: str = MembershipRole.COACH,
) -> UserId:
    user = User(email=Email(f"{new_id()}@example.com"), display_name="Analyst")
    await uow.users.add(user)
    await uow.organizations.add(
        Organization(
            name="Visualization FC", slug=Slug(f"viz-{new_id().hex[:8]}"), id=organization_id
        )
    )
    uow.organizations.memberships.append(
        OrganizationMembership(
            organization_id=organization_id,
            user_id=user.id,
            role=MembershipRole(role),
        )
    )
    return user.id


async def seed_run_with_observations(
    uow: UnitOfWorkStub,
    *,
    organization_id: OrganizationId,
    status: str = "succeeded",
    observation_count: int = 4,
    tracks: int = 1,
    width: int | None = 1920,
    height: int | None = 1080,
) -> AnalysisRun:
    video = Video(
        organization_id=organization_id,
        original_filename="clip.mp4",
        storage_key=f"viz/{uuid.uuid4()}.mp4",
    )
    video.mark_uploaded(size_bytes=1024, content_type="video/mp4")
    if width is not None and height is not None:
        video.record_probe(
            VideoSpec(
                duration_seconds=10.0,
                frame_rate=25.0,
                width=width,
                height=height,
                codec="h264",
            )
        )
    await uow.videos.add(video)

    run = AnalysisRun(
        organization_id=organization_id,
        video_id=video.id,
        pipeline=default_pipeline(),
    )
    if status in {"queued", "running", "succeeded", "partially_succeeded"}:
        run.queue()
        run.start()
    if status == "succeeded":
        run.succeed()
    elif status == "partially_succeeded":
        run.succeed(partial=True)
    elif status == "failed":
        run.fail("decode failed")
    await uow.analysis_runs.add(run)

    if observation_count > 0:
        dataset = TrackingDataset(
            organization_id=organization_id,
            video_id=video.id,
            analysis_run_id=run.id,
        )
        await uow.tracking_datasets.add(dataset)
        await uow.track_observations.add_batch(
            dataset,
            [
                TrackedObservation(
                    track_id=track,
                    class_id=0,
                    confidence=0.9,
                    x1=float(index * 20),
                    y1=float(index * 10),
                    x2=float(index * 20) + 10.0,
                    y2=float(index * 10) + 20.0,
                    frame_index=index,
                    timestamp_seconds=index * 0.5,
                )
                for track in range(1, tracks + 1)
                for index in range(observation_count)
            ],
        )
    return run


async def read(
    uow: UnitOfWorkStub,
    *,
    organization_id: OrganizationId,
    user_id: UserId,
    run_id: object,
):
    return await use_cases.get_run_visualization(
        uow,
        settings=SETTINGS,
        organization_id=organization_id,
        user_id=user_id,
        run_id=run_id,  # type: ignore[arg-type]
    )


class TestGetRunVisualization:
    async def test_paths_come_from_the_persisted_observations(self) -> None:
        uow = UnitOfWorkStub()
        organization_id = OrganizationId(new_id())
        user_id = await seed_member(uow, organization_id=organization_id)
        run = await seed_run_with_observations(uow, organization_id=organization_id)

        data = await read(uow, organization_id=organization_id, user_id=user_id, run_id=run.id)

        assert len(data.paths) == 1
        path = data.paths[0]
        assert path.track_id == 1
        # Bounded to the configured limit, with the first point preserved.
        assert len(path.points) == 3
        assert path.points[0].frame_index == 0
        assert path.points[0].x == 5.0
        assert data.observation_count == 4

    async def test_the_frame_dimensions_come_from_the_video(self) -> None:
        uow = UnitOfWorkStub()
        organization_id = OrganizationId(new_id())
        user_id = await seed_member(uow, organization_id=organization_id)
        run = await seed_run_with_observations(uow, organization_id=organization_id)

        data = await read(uow, organization_id=organization_id, user_id=user_id, run_id=run.id)

        assert data.frame.width == 1920
        assert data.frame.height == 1080
        assert data.density.bounds == (0.0, 0.0, 1920.0, 1080.0)

    async def test_the_density_grid_reflects_observation_density(self) -> None:
        uow = UnitOfWorkStub()
        organization_id = OrganizationId(new_id())
        user_id = await seed_member(uow, organization_id=organization_id)
        run = await seed_run_with_observations(
            uow, organization_id=organization_id, observation_count=6, tracks=2
        )

        data = await read(uow, organization_id=organization_id, user_id=user_id, run_id=run.id)

        assert data.density.columns == 4
        assert data.density.rows == 4
        assert sum(data.density.counts) == 12
        assert data.density.track_count == 2

    async def test_the_timeline_buckets_activity(self) -> None:
        uow = UnitOfWorkStub()
        organization_id = OrganizationId(new_id())
        user_id = await seed_member(uow, organization_id=organization_id)
        run = await seed_run_with_observations(
            uow, organization_id=organization_id, observation_count=4
        )

        data = await read(uow, organization_id=organization_id, user_id=user_id, run_id=run.id)

        assert data.timeline.bucket_seconds == 1.0
        assert data.timeline.start_seconds == 0.0
        assert data.timeline.end_seconds == 1.5
        assert len(data.timeline.buckets) == 2
        assert sum(bucket.observation_count for bucket in data.timeline.buckets) == 4

    async def test_metrics_are_read_alongside_the_visualization(self) -> None:
        uow = UnitOfWorkStub()
        organization_id = OrganizationId(new_id())
        user_id = await seed_member(uow, organization_id=organization_id)
        run = await seed_run_with_observations(uow, organization_id=organization_id)

        data = await read(uow, organization_id=organization_id, user_id=user_id, run_id=run.id)

        # The metrics stage has not run, so the metrics are an empty, valid result.
        assert data.metrics.analysis_run_id == run.id
        assert data.metrics.tracks == ()

    async def test_a_run_with_no_observations_yields_an_empty_visualization(self) -> None:
        uow = UnitOfWorkStub()
        organization_id = OrganizationId(new_id())
        user_id = await seed_member(uow, organization_id=organization_id)
        run = await seed_run_with_observations(
            uow, organization_id=organization_id, observation_count=0
        )

        data = await read(uow, organization_id=organization_id, user_id=user_id, run_id=run.id)

        assert data.paths == ()
        assert data.observation_count == 0
        assert data.track_count == 0
        assert data.density.max_count == 0
        assert data.timeline.buckets == ()

    async def test_a_partial_run_is_still_readable(self) -> None:
        uow = UnitOfWorkStub()
        organization_id = OrganizationId(new_id())
        user_id = await seed_member(uow, organization_id=organization_id)
        run = await seed_run_with_observations(
            uow, organization_id=organization_id, status="partially_succeeded"
        )

        data = await read(uow, organization_id=organization_id, user_id=user_id, run_id=run.id)

        assert data.status == "partially_succeeded"
        assert data.observation_count == 4

    async def test_a_run_that_has_not_finished_is_refused(self) -> None:
        uow = UnitOfWorkStub()
        organization_id = OrganizationId(new_id())
        user_id = await seed_member(uow, organization_id=organization_id)
        run = await seed_run_with_observations(
            uow, organization_id=organization_id, status="running"
        )

        with pytest.raises(ConflictError):
            await read(uow, organization_id=organization_id, user_id=user_id, run_id=run.id)

    async def test_a_failed_run_is_refused(self) -> None:
        uow = UnitOfWorkStub()
        organization_id = OrganizationId(new_id())
        user_id = await seed_member(uow, organization_id=organization_id)
        run = await seed_run_with_observations(
            uow, organization_id=organization_id, status="failed"
        )

        with pytest.raises(ConflictError):
            await read(uow, organization_id=organization_id, user_id=user_id, run_id=run.id)


class TestVisualizationAuthorization:
    async def test_a_missing_run_is_not_found(self) -> None:
        uow = UnitOfWorkStub()
        organization_id = OrganizationId(new_id())
        user_id = await seed_member(uow, organization_id=organization_id)

        with pytest.raises(NotFoundError):
            await read(uow, organization_id=organization_id, user_id=user_id, run_id=new_id())

    async def test_a_cross_organization_run_is_not_found(self) -> None:
        uow = UnitOfWorkStub()
        owner = OrganizationId(new_id())
        other = OrganizationId(new_id())
        user_id = await seed_member(uow, organization_id=other)
        run = await seed_run_with_observations(uow, organization_id=owner)

        with pytest.raises(NotFoundError):
            await read(uow, organization_id=other, user_id=user_id, run_id=run.id)

    async def test_a_non_member_is_refused(self) -> None:
        uow = UnitOfWorkStub()
        organization_id = OrganizationId(new_id())
        run = await seed_run_with_observations(uow, organization_id=organization_id)

        with pytest.raises(NotFoundError):
            await read(
                uow,
                organization_id=organization_id,
                user_id=UserId(new_id()),
                run_id=run.id,
            )
