from __future__ import annotations

import logging
import uuid

from app.application.ports.processing import (
    ProcessingContext,
    ProcessingOutcome,
    ProgressReporter,
)
from app.application.ports.unit_of_work import UnitOfWorkFactory
from app.application.use_cases.metrics import group_track_metrics
from app.application.use_cases.reports import find_report_for_run
from app.core.config import Settings
from app.core.errors import ProcessingFailedError
from app.domain.analysis.entities import AnalysisRun
from app.domain.reports.builder import build_report_content
from app.domain.reports.content import content_to_dict
from app.domain.reports.entities import Report, ReportStatus
from app.domain.shared import AnalysisRunId, OrganizationId

logger = logging.getLogger(__name__)


class ReportPipeline:
    """Compose a report from an analysis run's persisted output.

    Like the metrics stage, this implements the existing 'ProcessingPipeline'
    port, so it runs inside the same worker, job lifecycle and event stream. It
    reads the run's stored metrics and observation counts; it derives nothing new
    and never opens the video.
    """

    def __init__(self, *, settings: Settings, uow_factory: UnitOfWorkFactory) -> None:
        self._settings = settings
        self._uow_factory = uow_factory

    async def run(
        self, context: ProcessingContext, reporter: ProgressReporter
    ) -> ProcessingOutcome:
        if context.analysis_run_id is None:
            raise ProcessingFailedError("A report job requires an analysis run.")

        await reporter.report(10.0)
        run_id = AnalysisRunId(_uuid(context.analysis_run_id))
        organization_id = OrganizationId(_uuid(context.organization_id))

        report, run = await self._load(run_id, organization_id)
        try:
            content = await self._compose(run, reporter)
        except Exception as exc:
            await self._mark_failed(report, exc)
            raise

        await self._mark_ready(report, content)
        await reporter.report(100.0)
        logger.info("report stage completed", extra={"report_id": str(report.id)})
        return ProcessingOutcome(progress_percent=100.0)

    async def _load(
        self, run_id: AnalysisRunId, organization_id: OrganizationId
    ) -> tuple[Report, AnalysisRun]:
        uow = self._uow_factory()
        async with uow:
            run = await uow.analysis_runs.get(run_id)
            if run is None or run.organization_id != organization_id:
                raise ProcessingFailedError("The analysis run for this report does not exist.")
            report = await find_report_for_run(uow, organization_id, run_id)
            if report is None:
                raise ProcessingFailedError("No report is awaiting generation for this run.")
            if report.status.value == ReportStatus.READY:
                raise ProcessingFailedError("This report has already been generated.")
            return report, run

    async def _compose(self, run: AnalysisRun, reporter: ProgressReporter) -> dict[str, object]:
        uow = self._uow_factory()
        async with uow:
            video = await uow.videos.get(run.video_id)
            observation_count = await uow.track_observations.count_for_run(run.id)
            records = await uow.track_metrics.list_for_run(run.id)

        await reporter.report(60.0)
        metrics = group_track_metrics(run, records)

        content = build_report_content(
            run=run,
            video=video,
            observation_count=observation_count,
            track_count=len(metrics.tracks),
            metrics=metrics,
        )
        return content_to_dict(content)

    async def _mark_ready(self, report: Report, content: dict[str, object]) -> None:
        uow = self._uow_factory()
        async with uow:
            stored = await uow.reports.get(report.id)
            if stored is None:
                return
            stored.content = content
            stored.mark_ready()
            await uow.reports.update(stored)
            await uow.commit()

    async def _mark_failed(self, report: Report, exc: Exception) -> None:
        message = (
            exc.message if isinstance(exc, ProcessingFailedError) else "Report generation failed."
        )
        uow = self._uow_factory()
        async with uow:
            stored = await uow.reports.get(report.id)
            if stored is None:
                return
            stored.mark_failed(message)
            await uow.reports.update(stored)
            await uow.commit()


def _uuid(value: str) -> uuid.UUID:
    return uuid.UUID(value)
