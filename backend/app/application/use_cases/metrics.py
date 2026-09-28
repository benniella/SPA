"""The analysis engine: calculate metrics for a run, and read them back.

The engine consumes an existing analysis run's tracking observations. It never
re-derives tracking, never touches a detector or a decoder, and never bypasses
the job pipeline — a metric calculation is dispatched as a 'ProcessingJob' and
executed by the metrics pipeline, exactly as detection and tracking are.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from app.application.ports.jobs import Job, JobDispatcher, JobKind
from app.application.ports.unit_of_work import UnitOfWork
from app.application.use_cases.organizations import require_organization_member
from app.core.errors import ConflictError, NotFoundError
from app.domain.analysis.entities import AnalysisRun, AnalysisRunStatus
from app.domain.jobs.entities import ProcessingJob
from app.domain.metrics.registry import METRIC_CATALOGUE
from app.domain.metrics.types import AnalysisMetrics, MetricSpace, TrackMetricRecord, TrackMetrics
from app.domain.shared import AnalysisRunId, JobId, OrganizationId, UserId

METRICS_JOB_TYPE = str(JobKind.RUN_ANALYSIS)

#: A run's metrics can only be calculated from data that already exists, and can
#: only be read from a run that has produced usable output.
CALCULABLE_STATUSES = frozenset({AnalysisRunStatus.SUCCEEDED})
READABLE_STATUSES = frozenset({AnalysisRunStatus.SUCCEEDED, AnalysisRunStatus.PARTIALLY_SUCCEEDED})


@dataclass(frozen=True, slots=True)
class MetricsRequest:
    """What the API returns after queueing a metric calculation."""

    analysis_run_id: AnalysisRunId
    job: ProcessingJob


async def request_metrics_calculation(
    uow: UnitOfWork,
    *,
    organization_id: OrganizationId,
    user_id: UserId,
    run_id: AnalysisRunId,
    dispatcher: JobDispatcher,
) -> MetricsRequest:
    """Queue the metrics stage for an analysis run.

    Raises:
        NotFoundError: the run does not exist in this organization.
        ConflictError: the run has not produced tracking data yet, or a metric
            calculation is already queued for it.
    """
    await require_organization_member(uow, organization_id=organization_id, user_id=user_id)

    async with uow:
        run = await uow.analysis_runs.get(run_id)
        if run is None or run.organization_id != organization_id:
            # A cross-tenant probe must not be able to confirm that the id exists.
            raise NotFoundError(f"Analysis run {run_id} does not exist.")

        if run.status.value not in CALCULABLE_STATUSES:
            raise ConflictError(
                f"Analysis run {run_id} is '{run.status}' and has no tracking data to "
                "derive metrics from.",
                details={"status": str(run.status)},
            )

        # A repeated request returns the existing job rather than creating a
        # second one, mirroring the video-processing path: two workers calculating
        # the same run would double the compute for one result.
        active = await uow.processing_jobs.find_active(run.video_id, METRICS_JOB_TYPE)
        if active is not None:
            return MetricsRequest(analysis_run_id=run_id, job=active)

    result = await dispatcher.dispatch(
        Job(
            kind=JobKind(JobKind.RUN_ANALYSIS),
            payload={"analysis_run_id": str(run_id), "video_id": str(run.video_id)},
            organization_id=str(organization_id),
            idempotency_key=f"metrics:{run_id}",
        )
    )

    if not result.accepted or result.job_id is None:
        raise ConflictError("Metric calculation could not be queued for this run.")

    async with uow:
        job = await uow.processing_jobs.get(JobId(uuid.UUID(result.job_id)))
        if job is None:  # pragma: no cover - the dispatcher just persisted it
            raise ConflictError("Metric calculation could not be queued for this run.")
        return MetricsRequest(analysis_run_id=run_id, job=job)


async def get_analysis_metrics(
    uow: UnitOfWork,
    *,
    organization_id: OrganizationId,
    user_id: UserId,
    run_id: AnalysisRunId,
) -> AnalysisMetrics:
    """Read a run's derived metrics.

    Raises:
        NotFoundError: the run does not exist in this organization.
        ConflictError: the run has not produced usable metrics.
    """
    await require_organization_member(uow, organization_id=organization_id, user_id=user_id)

    async with uow:
        run = await uow.analysis_runs.get(run_id)
        if run is None or run.organization_id != organization_id:
            raise NotFoundError(f"Analysis run {run_id} does not exist.")

        records = await uow.track_metrics.list_for_run(run_id)

    if run.status.value not in READABLE_STATUSES:
        raise ConflictError(
            f"Analysis run {run_id} is '{run.status}' and has no metrics.",
            details={"status": str(run.status)},
        )

    return _group(run, records)


def _group(run: AnalysisRun, records: list[TrackMetricRecord]) -> AnalysisMetrics:
    by_track: dict[int, list[TrackMetricRecord]] = {}
    for record in records:
        by_track.setdefault(record.track_id, []).append(record)

    tracks = tuple(
        TrackMetrics(
            track_id=track_id,
            space=MetricSpace.SOURCE,
            values=tuple(record.value for record in sorted(rows, key=_metric_order)),
        )
        for track_id, rows in sorted(by_track.items())
    )
    return AnalysisMetrics(
        analysis_run_id=run.id,
        organization_id=run.organization_id,
        space=MetricSpace.SOURCE,
        tracks=tracks,
        definition_version=records[0].definition_version if records else "v1",
    )


def _metric_order(record: TrackMetricRecord) -> int:
    names = list(METRIC_CATALOGUE)
    try:
        return names.index(record.value.name)
    except ValueError:  # pragma: no cover - every persisted name is in the catalogue
        return len(names)
