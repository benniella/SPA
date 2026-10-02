"""The report pipeline against the in-memory unit of work.

These prove orchestration and persistence behaviour: a report is composed from a
run's persisted metrics and observations, the same run always yields the same
content, an unavailable metric stays unavailable, and a finished report is not
recomposed. Numeric correctness belongs to the domain tests.
"""

from __future__ import annotations

import pytest
from tests.unit.application.fakes import UnitOfWorkStub
from tests.unit.infrastructure.test_cv_pipeline import make_settings

from app.application.ports.processing import ProcessingContext
from app.core.errors import ProcessingFailedError
from app.domain.analysis.entities import AnalysisRun, default_pipeline
from app.domain.metrics.types import (
    MetricName,
    MetricUnit,
    MetricValue,
    TrackMetricRecord,
)
from app.domain.reports.entities import Report, ReportScope, ReportStatus
from app.domain.shared import AnalysisRunId, OrganizationId, VideoId, new_id
from app.domain.videos.entities import Video
from app.infrastructure.processing.report_pipeline import ReportPipeline


class RecordingReporter:
    def __init__(self) -> None:
        self.reports: list[float] = []

    async def report(self, percent: float) -> None:
        self.reports.append(percent)


async def seed_report_for_run(
    uow: UnitOfWorkStub,
    *,
    metrics: list[tuple[MetricName, float | None, MetricUnit]] | None = None,
) -> tuple[Report, AnalysisRun]:
    organization_id = OrganizationId(new_id())
    video = Video(
        organization_id=organization_id,
        original_filename="match.mp4",
        storage_key=f"reports/{new_id()}.mp4",
    )
    video.mark_uploaded(size_bytes=1024, content_type="video/mp4")
    await uow.videos.add(video)

    run = AnalysisRun(
        organization_id=organization_id,
        video_id=video.id,
        pipeline=default_pipeline(),
    )
    run.queue()
    run.start()
    run.succeed()
    await uow.analysis_runs.add(run)

    report = Report(
        organization_id=organization_id,
        title="Analysis report",
        scope=ReportScope(analysis_run_ids=(run.id,)),
    )
    report.mark_generating()
    await uow.reports.add(report)

    records = [
        TrackMetricRecord(
            organization_id=organization_id,
            analysis_run_id=run.id,
            track_id=1,
            value=(
                MetricValue.available(name, unit, value, sample_count=4)
                if value is not None
                else MetricValue.unavailable(name, unit)
            ),
        )
        for name, value, unit in (default_metrics() if metrics is None else metrics)
    ]
    await uow.track_metrics.replace_for_run(run.id, records)
    return report, run


def default_metrics() -> list[tuple[MetricName, float | None, MetricUnit]]:
    return [
        (MetricName.OBSERVATION_COUNT, 120.0, MetricUnit.COUNT),
        (MetricName.DURATION, 47.0, MetricUnit.SECONDS),
        (MetricName.COVERAGE, 0.91, MetricUnit.COUNT),
        (MetricName.DISPLACEMENT, 1240.0, MetricUnit.PIXELS),
        (MetricName.AVERAGE_SPEED, 26.4, MetricUnit.PIXELS_PER_SECOND),
        (MetricName.PEAK_SPEED, 51.2, MetricUnit.PIXELS_PER_SECOND),
        (MetricName.AVERAGE_ACCELERATION, 4.1, MetricUnit.PIXELS_PER_SECOND_SQUARED),
        (MetricName.PEAK_ACCELERATION, 9.7, MetricUnit.PIXELS_PER_SECOND_SQUARED),
        (MetricName.MEAN_CONFIDENCE, 0.88, MetricUnit.COUNT),
    ]


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


def build_pipeline(uow: UnitOfWorkStub, **overrides: object) -> ReportPipeline:
    return ReportPipeline(
        settings=make_settings(**overrides),
        uow_factory=lambda: uow,  # type: ignore[arg-type,return-value]
    )


class TestReportGeneration:
    async def test_composes_a_snapshot_from_persisted_metrics(self) -> None:
        uow = UnitOfWorkStub()
        report, run = await seed_report_for_run(uow)

        await build_pipeline(uow).run(
            context(run.id, run.organization_id, run.video_id), RecordingReporter()
        )

        stored = await uow.reports.get(report.id)
        assert stored is not None
        assert stored.status == ReportStatus.READY
        assert stored.generated_at is not None
        overview = stored.content["overview"]  # type: ignore[index]
        assert overview["analysis_run_id"] == str(run.id)  # type: ignore[index]
        assert overview["track_count"] == 1  # type: ignore[index]
        assert overview["space"] == "source"  # type: ignore[index]
        assert stored.content["tracks"][0]["track_id"] == 1  # type: ignore[index]

    async def test_the_same_data_produces_the_same_content(self) -> None:
        first = UnitOfWorkStub()
        report_a, run_a = await seed_report_for_run(first)
        await build_pipeline(first).run(
            context(run_a.id, run_a.organization_id, run_a.video_id), RecordingReporter()
        )
        stored_a = await first.reports.get(report_a.id)

        second = UnitOfWorkStub()
        report_b, run_b = await seed_report_for_run(second)
        await build_pipeline(second).run(
            context(run_b.id, run_b.organization_id, run_b.video_id), RecordingReporter()
        )
        stored_b = await second.reports.get(report_b.id)

        assert stored_a is not None and stored_b is not None
        assert stored_a.content["tracks"] == stored_b.content["tracks"]
        assert stored_a.content["observations"] == stored_b.content["observations"]
        assert stored_a.content["limitations"] == stored_b.content["limitations"]

    async def test_an_unavailable_metric_stays_unavailable(self) -> None:
        uow = UnitOfWorkStub()
        report, run = await seed_report_for_run(
            uow,
            metrics=[
                (MetricName.OBSERVATION_COUNT, 1.0, MetricUnit.COUNT),
                (MetricName.PEAK_SPEED, None, MetricUnit.PIXELS_PER_SECOND),
            ],
        )

        await build_pipeline(uow).run(
            context(run.id, run.organization_id, run.video_id), RecordingReporter()
        )

        stored = await uow.reports.get(report.id)
        assert stored is not None
        peak = next(
            metric
            for metric in stored.content["tracks"][0]["metrics"]  # type: ignore[index]
            if metric["name"] == "peak_speed"
        )
        assert peak["availability"] == "unavailable"
        assert peak["value"] is None

    async def test_a_run_with_no_metrics_composes_an_empty_track_list(self) -> None:
        uow = UnitOfWorkStub()
        report, run = await seed_report_for_run(uow, metrics=[])

        await build_pipeline(uow).run(
            context(run.id, run.organization_id, run.video_id), RecordingReporter()
        )

        stored = await uow.reports.get(report.id)
        assert stored is not None
        assert stored.status == ReportStatus.READY
        assert stored.content["tracks"] == []  # type: ignore[index]
        assert stored.content["observations"] == []  # type: ignore[index]

    async def test_an_already_ready_report_is_not_recomposed(self) -> None:
        uow = UnitOfWorkStub()
        report, run = await seed_report_for_run(uow)
        report.mark_ready()
        await uow.reports.update(report)

        with pytest.raises(ProcessingFailedError):
            await build_pipeline(uow).run(
                context(run.id, run.organization_id, run.video_id), RecordingReporter()
            )
