"""The metrics pipeline against the in-memory unit of work.

These prove orchestration and persistence behaviour — bounded reads, idempotent
writes, run lifecycle — rather than numeric correctness, which the domain tests
cover directly.
"""

from __future__ import annotations

import pytest
from tests.unit.application.fakes import UnitOfWorkStub
from tests.unit.infrastructure.test_cv_pipeline import make_settings

from app.application.ports.processing import ProcessingContext
from app.core.errors import ProcessingFailedError
from app.domain.analysis.entities import AnalysisRun, default_pipeline
from app.domain.metrics.registry import SENTINEL_METRIC
from app.domain.metrics.types import MetricName
from app.domain.shared import AnalysisRunId, OrganizationId, VideoId, new_id
from app.domain.tracking.entities import TrackedObservation, TrackingDataset
from app.infrastructure.processing.metrics_pipeline import MetricsPipeline


class RecordingReporter:
    def __init__(self) -> None:
        self.reports: list[float] = []

    async def report(self, percent: float) -> None:
        self.reports.append(percent)


async def seed_run_with_observations(
    uow: UnitOfWorkStub,
    *,
    organization_id: OrganizationId,
    video_id: VideoId,
    observations: list[TrackedObservation],
) -> AnalysisRun:
    dataset = TrackingDataset(
        organization_id=organization_id,
        video_id=video_id,
        analysis_run_id=AnalysisRunId(new_id()),
    )
    run = AnalysisRun(
        organization_id=organization_id,
        video_id=video_id,
        pipeline=default_pipeline(),
    )
    dataset.analysis_run_id = run.id
    run.queue()
    await uow.analysis_runs.add(run)
    await uow.tracking_datasets.add(dataset)
    await uow.track_observations.add_batch(dataset, observations)
    return run


def observation(
    *,
    track_id: int,
    frame_index: int,
    timestamp_seconds: float,
    offset: float,
    confidence: float = 0.9,
) -> TrackedObservation:
    return TrackedObservation(
        track_id=track_id,
        class_id=0,
        confidence=confidence,
        x1=10.0 + offset,
        y1=10.0,
        x2=30.0 + offset,
        y2=50.0,
        frame_index=frame_index,
        timestamp_seconds=timestamp_seconds,
    )


def context(
    run_id: AnalysisRunId, organization_id: OrganizationId, video_id: VideoId
) -> ProcessingContext:
    return ProcessingContext(
        job_id=str(new_id()),
        organization_id=str(organization_id),
        video_id=str(video_id),
        storage_key="org/videos/clip.mp4",
        content_type="video/mp4",
        size_bytes=None,
        analysis_run_id=str(run_id),
    )


def build_pipeline(uow: UnitOfWorkStub, **overrides: object) -> MetricsPipeline:
    return MetricsPipeline(
        settings=make_settings(**overrides),
        uow_factory=lambda: uow,  # type: ignore[arg-type,return-value]
    )


class TestSuccessfulCalculation:
    async def test_persists_metrics_and_records_the_stage(self) -> None:
        uow = UnitOfWorkStub()
        organization_id = OrganizationId(new_id())
        video_id = VideoId(new_id())
        observations = [
            observation(
                track_id=1, frame_index=index, timestamp_seconds=index * 0.5, offset=index * 10.0
            )
            for index in range(4)
        ]
        run = await seed_run_with_observations(
            uow, organization_id=organization_id, video_id=video_id, observations=observations
        )

        reporter = RecordingReporter()
        outcome = await build_pipeline(uow).run(
            context(run.id, organization_id, video_id), reporter
        )

        assert outcome.progress_percent == 100.0
        assert reporter.reports[-1] == 100.0

        stored = await uow.analysis_runs.get(run.id)
        assert stored is not None
        assert stored.stage_results["metrics"]["tracks"] == 1

        metrics = await uow.track_metrics.list_for_run(run.id)
        assert metrics
        displacement = next(m for m in metrics if m.value.name is MetricName.DISPLACEMENT)
        assert displacement.value.value == pytest.approx(30.0)
        assert displacement.organization_id == organization_id

    async def test_observations_are_read_in_bounded_pages(self) -> None:
        uow = UnitOfWorkStub()
        organization_id = OrganizationId(new_id())
        video_id = VideoId(new_id())
        observations = [
            observation(track_id=1, frame_index=index, timestamp_seconds=index * 0.5, offset=0.0)
            for index in range(10)
        ]
        run = await seed_run_with_observations(
            uow, organization_id=organization_id, video_id=video_id, observations=observations
        )

        # A page size of 3 means the whole set is never materialised at once.
        await build_pipeline(uow, metrics_batch_size=3).run(
            context(run.id, organization_id, video_id), RecordingReporter()
        )

        count = await uow.track_metrics.count_for_run(run.id)
        assert count > 0

    async def test_multiple_tracks_are_kept_apart(self) -> None:
        uow = UnitOfWorkStub()
        organization_id = OrganizationId(new_id())
        video_id = VideoId(new_id())
        observations = [
            observation(track_id=1, frame_index=index, timestamp_seconds=index * 0.5, offset=0.0)
            for index in range(3)
        ] + [
            observation(
                track_id=2, frame_index=index, timestamp_seconds=index * 0.5, offset=index * 25.0
            )
            for index in range(3)
        ]
        run = await seed_run_with_observations(
            uow, organization_id=organization_id, video_id=video_id, observations=observations
        )

        await build_pipeline(uow).run(
            context(run.id, organization_id, video_id), RecordingReporter()
        )

        metrics = await uow.track_metrics.list_for_run(run.id)
        first = next(
            m for m in metrics if m.track_id == 1 and m.value.name is MetricName.DISPLACEMENT
        )
        second = next(
            m for m in metrics if m.track_id == 2 and m.value.name is MetricName.DISPLACEMENT
        )
        assert first.value.value == pytest.approx(0.0)
        assert second.value.value == pytest.approx(50.0)

    async def test_every_track_reports_the_sentinel_count(self) -> None:
        uow = UnitOfWorkStub()
        organization_id = OrganizationId(new_id())
        video_id = VideoId(new_id())
        observations = [
            observation(track_id=1, frame_index=index, timestamp_seconds=index * 0.5, offset=0.0)
            for index in range(3)
        ]
        run = await seed_run_with_observations(
            uow, organization_id=organization_id, video_id=video_id, observations=observations
        )

        await build_pipeline(uow).run(
            context(run.id, organization_id, video_id), RecordingReporter()
        )

        metrics = await uow.track_metrics.list_for_run(run.id)
        sentinel = next(m for m in metrics if m.value.name is SENTINEL_METRIC)
        assert sentinel.value.is_available


class TestIdempotency:
    async def test_running_twice_does_not_duplicate_metrics(self) -> None:
        uow = UnitOfWorkStub()
        organization_id = OrganizationId(new_id())
        video_id = VideoId(new_id())
        observations = [
            observation(
                track_id=1, frame_index=index, timestamp_seconds=index * 0.5, offset=index * 10.0
            )
            for index in range(4)
        ]
        run = await seed_run_with_observations(
            uow, organization_id=organization_id, video_id=video_id, observations=observations
        )
        pipeline = build_pipeline(uow)

        # A retry over an already-succeeded run recalculates the same rows rather
        # than appending a second set.
        await pipeline.run(context(run.id, organization_id, video_id), RecordingReporter())
        first = await uow.track_metrics.count_for_run(run.id)

        await pipeline.run(context(run.id, organization_id, video_id), RecordingReporter())
        second = await uow.track_metrics.count_for_run(run.id)

        assert first == second

    async def test_running_twice_keeps_the_same_values(self) -> None:
        uow = UnitOfWorkStub()
        organization_id = OrganizationId(new_id())
        video_id = VideoId(new_id())
        observations = [
            observation(
                track_id=1, frame_index=index, timestamp_seconds=index * 0.5, offset=index * 10.0
            )
            for index in range(4)
        ]
        run = await seed_run_with_observations(
            uow, organization_id=organization_id, video_id=video_id, observations=observations
        )
        pipeline = build_pipeline(uow)

        await pipeline.run(context(run.id, organization_id, video_id), RecordingReporter())
        first = _displacement(await uow.track_metrics.list_for_run(run.id))

        await pipeline.run(context(run.id, organization_id, video_id), RecordingReporter())
        second = _displacement(await uow.track_metrics.list_for_run(run.id))

        assert first == pytest.approx(second)


def _displacement(records: list[object]) -> float:
    from app.domain.metrics.types import MetricName

    for record in records:
        if record.value.name is MetricName.DISPLACEMENT:  # type: ignore[attr-defined]
            return float(record.value.value)  # type: ignore[attr-defined]
    raise AssertionError("no displacement metric was persisted")


class TestFailureHandling:
    async def test_a_run_with_no_observations_fails_explicitly(self) -> None:
        uow = UnitOfWorkStub()
        organization_id = OrganizationId(new_id())
        video_id = VideoId(new_id())
        run = await seed_run_with_observations(
            uow, organization_id=organization_id, video_id=video_id, observations=[]
        )

        with pytest.raises(ProcessingFailedError):
            await build_pipeline(uow).run(
                context(run.id, organization_id, video_id), RecordingReporter()
            )

        stored = await uow.analysis_runs.get(run.id)
        assert stored is not None
        assert stored.error_message

    async def test_a_missing_run_fails(self) -> None:
        uow = UnitOfWorkStub()
        organization_id = OrganizationId(new_id())
        video_id = VideoId(new_id())

        with pytest.raises(ProcessingFailedError):
            await build_pipeline(uow).run(
                context(AnalysisRunId(new_id()), organization_id, video_id), RecordingReporter()
            )

    async def test_a_run_from_another_organization_is_refused(self) -> None:
        uow = UnitOfWorkStub()
        owner = OrganizationId(new_id())
        video_id = VideoId(new_id())
        run = await seed_run_with_observations(
            uow,
            organization_id=owner,
            video_id=video_id,
            observations=[
                observation(track_id=1, frame_index=0, timestamp_seconds=0.0, offset=0.0)
            ],
        )

        with pytest.raises(ProcessingFailedError):
            await build_pipeline(uow).run(
                context(run.id, OrganizationId(new_id()), video_id), RecordingReporter()
            )

    async def test_a_job_without_a_run_is_refused(self) -> None:
        uow = UnitOfWorkStub()

        with pytest.raises(ProcessingFailedError):
            await build_pipeline(uow).run(
                ProcessingContext(
                    job_id=str(new_id()),
                    organization_id=str(new_id()),
                    video_id=str(new_id()),
                    storage_key="key",
                    content_type="video/mp4",
                    size_bytes=None,
                    analysis_run_id=None,
                ),
                RecordingReporter(),
            )
