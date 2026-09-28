"""The metrics stage: derived quantities over a run's persisted tracking data.

Implements the existing 'ProcessingPipeline' port unchanged, so the worker, the
job lifecycle and the WebSocket events are untouched. It reads observations one
page at a time, groups them by track as it goes, and never holds a match's
tracking set in memory.
"""

from __future__ import annotations

import logging
import uuid
from collections.abc import Iterable

from app.application.ports.processing import (
    ProcessingContext,
    ProcessingOutcome,
    ProgressReporter,
)
from app.application.ports.unit_of_work import UnitOfWorkFactory
from app.core.config import Settings
from app.core.errors import ProcessingFailedError
from app.domain.analysis.entities import AnalysisRun
from app.domain.metrics.calculators import MetricCalculator
from app.domain.metrics.registry import SENTINEL_METRIC
from app.domain.metrics.types import (
    MetricSpace,
    TrackMetricRecord,
    TrackMetrics,
    TrackObservationPoint,
)
from app.domain.shared import AnalysisRunId, OrganizationId, TrackMetricId, new_id
from app.domain.tracking.entities import TrackRecord

logger = logging.getLogger(__name__)


class MetricsPipeline:
    """Calculate and persist the metrics a tracking run implies.

    It consumes 'tracking_observations' ' and nothing else. No detector, tracker,
    decoder or model is referenced, so replacing any of them leaves this stage
    untouched.
    """

    def __init__(self, *, settings: Settings, uow_factory: UnitOfWorkFactory) -> None:
        self._settings = settings
        self._uow_factory = uow_factory
        self._calculator = MetricCalculator(
            max_gap_seconds=settings.metrics_max_observation_gap_seconds
        )

    async def run(
        self, context: ProcessingContext, reporter: ProgressReporter
    ) -> ProcessingOutcome:
        await reporter.report(5.0)

        if context.analysis_run_id is None:
            raise ProcessingFailedError(
                "A metrics job requires an analysis run.",
                details={"video_id": context.video_id},
            )

        run = await self._load_run(context)
        try:
            track_metrics = await self._calculate(run.id, reporter)
        except Exception as exc:
            await self._mark_failed(run, exc)
            raise

        await self._persist(run, track_metrics)
        await self._complete(run, track_metrics)
        await reporter.report(100.0)
        logger.info(
            "metrics stage completed",
            extra={"analysis_run_id": str(run.id), "tracks": len(track_metrics)},
        )
        return ProcessingOutcome(progress_percent=100.0)

    async def _load_run(self, context: ProcessingContext) -> AnalysisRun:
        if context.analysis_run_id is None:  # pragma: no cover - guarded by the caller
            raise ProcessingFailedError("A metrics job requires an analysis run.")
        uow = self._uow_factory()
        async with uow:
            run = await uow.analysis_runs.get(AnalysisRunId(_uuid(context.analysis_run_id)))
            if run is None or run.organization_id != OrganizationId(_uuid(context.organization_id)):
                raise ProcessingFailedError(
                    "The analysis run for this video does not exist.",
                    details={"video_id": context.video_id},
                )
            if not run.is_terminal:
                run.start()
                await uow.analysis_runs.update(run)
                await uow.commit()
            return run

    async def _calculate(
        self,
        run_id: AnalysisRunId,
        reporter: ProgressReporter,
    ) -> list[TrackMetrics]:
        batch_size = self._settings.metrics_batch_size
        observations = await self._count_observations(run_id)
        if observations == 0:
            raise ProcessingFailedError(
                "This analysis run has no tracking observations to derive metrics from.",
                details={"analysis_run_id": str(run_id)},
            )

        grouped: dict[int, list[TrackObservationPoint]] = {}
        offset = 0
        while offset < observations:
            page = await self._read_page(run_id, limit=batch_size, offset=offset)
            if not page:
                break
            for record in page:
                grouped.setdefault(record.observation.track_id, []).append(_to_point(record))
            offset += len(page)
            await reporter.report(5.0 + 85.0 * min(1.0, offset / observations))

        return [
            self._calculator.calculate(track_id, points)
            for track_id, points in sorted(grouped.items())
        ]

    async def _count_observations(self, run_id: AnalysisRunId) -> int:
        uow = self._uow_factory()
        async with uow:
            return await uow.track_observations.count_for_run(run_id)

    async def _read_page(
        self, run_id: AnalysisRunId, *, limit: int, offset: int
    ) -> list[TrackRecord]:
        uow = self._uow_factory()
        async with uow:
            return await uow.track_observations.list_for_run(run_id, limit=limit, offset=offset)

    async def _persist(self, run: AnalysisRun, track_metrics: list[TrackMetrics]) -> None:
        if not track_metrics:
            raise ProcessingFailedError(
                "No track produced a usable metric for this run.",
                details={"analysis_run_id": str(run.id)},
            )
        records = _to_records(run, track_metrics)
        uow = self._uow_factory()
        async with uow:
            await uow.track_metrics.replace_for_run(run.id, records)
            await uow.commit()

    async def _complete(self, run: AnalysisRun, track_metrics: list[TrackMetrics]) -> None:
        available = sum(
            1 for metrics in track_metrics for value in metrics.values if value.is_available
        )
        partial = not _has_sentinel(track_metrics)
        uow = self._uow_factory()
        async with uow:
            stored = await uow.analysis_runs.get(run.id)
            if stored is None or stored.is_terminal:
                return
            stored.stage_results["metrics"] = {
                "tracks": len(track_metrics),
                "metrics": available,
                "space": MetricSpace.SOURCE.value,
            }
            stored.succeed(partial=partial)
            await uow.analysis_runs.update(stored)
            await uow.commit()

    async def _mark_failed(self, run: AnalysisRun, exc: Exception) -> None:
        message = (
            exc.message if isinstance(exc, ProcessingFailedError) else "Metric calculation failed."
        )
        uow = self._uow_factory()
        async with uow:
            stored = await uow.analysis_runs.get(run.id)
            if stored is None or stored.is_terminal:
                return
            stored.fail(message)
            await uow.analysis_runs.update(stored)
            await uow.commit()


def _has_sentinel(track_metrics: Iterable[TrackMetrics]) -> bool:
    return all(
        (value := metrics.value_for(SENTINEL_METRIC)) is not None and value.is_available
        for metrics in track_metrics
    )


def _to_point(record: TrackRecord) -> TrackObservationPoint:
    observation = record.observation
    return TrackObservationPoint(
        track_id=observation.track_id,
        frame_index=observation.frame_index,
        timestamp_seconds=observation.timestamp_seconds,
        x1=observation.x1,
        y1=observation.y1,
        x2=observation.x2,
        y2=observation.y2,
        confidence=observation.confidence,
    )


def _to_records(run: AnalysisRun, track_metrics: list[TrackMetrics]) -> list[TrackMetricRecord]:
    return [
        TrackMetricRecord(
            id=TrackMetricId(new_id()),
            organization_id=run.organization_id,
            analysis_run_id=run.id,
            track_id=metrics.track_id,
            value=value,
            space=metrics.space,
        )
        for metrics in track_metrics
        for value in metrics.values
    ]


def _uuid(value: str) -> uuid.UUID:
    return uuid.UUID(value)
