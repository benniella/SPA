from __future__ import annotations

from dataclasses import dataclass

from app.application.ports.jobs import Job, JobDispatcher, JobKind
from app.application.ports.unit_of_work import UnitOfWork
from app.application.ports.video_storage import VideoStorage
from app.application.use_cases.organizations import (
    require_organization_member,
    require_organization_writer,
)
from app.core.errors import ConflictError, NotFoundError
from app.domain.analysis.entities import AnalysisRun, AnalysisRunStatus
from app.domain.reports.content import content_from_dict
from app.domain.reports.entities import Report, ReportScope, ReportStatus
from app.domain.reports.export import render_report_html
from app.domain.shared import AnalysisRunId, OrganizationId, ReportId, UserId

REPORT_JOB_TYPE = str(JobKind.GENERATE_REPORT)

#: The media type of an exported report and the object name it is stored under.
EXPORT_CONTENT_TYPE = "text/html; charset=utf-8"
EXPORT_FILENAME = "report.html"

#: A report reads a run's persisted tracking observations and metrics, so it can
#: only be generated from a run that produced usable output. A partial run
#: qualifies: its missing information is already explicit in the run's status and
#: in the unavailable metrics, which the report carries through rather than hides.
GENERATABLE_STATUSES = frozenset(
    {AnalysisRunStatus.SUCCEEDED, AnalysisRunStatus.PARTIALLY_SUCCEEDED}
)


async def request_run_report(
    uow: UnitOfWork,
    *,
    organization_id: OrganizationId,
    user_id: UserId,
    run_id: AnalysisRunId,
    dispatcher: JobDispatcher,
) -> Report:
    """Create a report for an analysis run and queue its generation.

    Raises:
        NotFoundError: the run does not exist in this organization.
        ConflictError: the run has not produced data a report could describe.
    """
    await require_organization_writer(uow, organization_id=organization_id, user_id=user_id)

    async with uow:
        run = await uow.analysis_runs.get(run_id)
        if run is None or run.organization_id != organization_id:
            # A cross-tenant probe must not be able to confirm that the id exists.
            raise NotFoundError(f"Analysis run {run_id} does not exist.")

        if run.status.value not in GENERATABLE_STATUSES:
            raise ConflictError(
                f"Analysis run {run_id} is '{run.status}'. Complete the analysis before "
                "generating a report.",
                details={"status": str(run.status)},
            )

        # A repeated request returns the report already covering this run rather
        # than piling up a second snapshot from every button press — whether that
        # report is still generating or already ready. Only a failed attempt is
        # restarted, in place, so a transient failure is not a dead end.
        report = await find_report_for_run(uow, organization_id, run_id)
        if report is not None and report.status.value != ReportStatus.FAILED:
            return report
        if report is not None:
            report.content = {}
            report.mark_generating()
            await uow.reports.update(report)
        else:
            report = Report(
                organization_id=organization_id,
                title=_title(run),
                scope=ReportScope(analysis_run_ids=(run_id,)),
                created_by_id=user_id,
            )
            report.mark_generating()
            await uow.reports.add(report)
        await uow.commit()
        video_id = run.video_id

    await dispatcher.dispatch(
        Job(
            kind=JobKind(JobKind.GENERATE_REPORT),
            payload={
                "report_id": str(report.id),
                "analysis_run_id": str(run_id),
                "video_id": str(video_id),
            },
            organization_id=str(organization_id),
            idempotency_key=f"report:{report.id}",
        )
    )

    return report


async def get_report(
    uow: UnitOfWork,
    *,
    organization_id: OrganizationId,
    report_id: ReportId,
) -> Report:
    async with uow:
        report = await uow.reports.get(report_id)
        if report is None or report.organization_id != organization_id:
            raise NotFoundError(f"Report {report_id} does not exist.")
        return report


async def list_reports(
    uow: UnitOfWork,
    *,
    organization_id: OrganizationId,
    limit: int = 50,
    offset: int = 0,
) -> list[Report]:
    async with uow:
        return await uow.reports.list_for_organization(organization_id, limit=limit, offset=offset)


async def find_report_for_run(
    uow: UnitOfWork,
    organization_id: OrganizationId,
    run_id: AnalysisRunId,
) -> Report | None:
    """The run-scoped report for a run, if one exists.

    Resolved by a direct lookup on the run, not by scanning the organization's
    reports, so the request path does not grow with report volume. Only a report
    scoped to the run alone is treated as its report; a match- or team-scoped
    report may also list this run.
    """
    return await uow.reports.find_for_run(organization_id, run_id)


def _title(run: AnalysisRun) -> str:
    return f"Analysis report — run {str(run.id)[:8]}"


@dataclass(frozen=True, slots=True)
class ReportExport:
    """A stored export of a report, ready to be served to its owner."""

    report_id: ReportId
    storage_key: str
    content_type: str
    filename: str


async def export_report(
    uow: UnitOfWork,
    *,
    storage: VideoStorage,
    organization_id: OrganizationId,
    user_id: UserId,
    report_id: ReportId,
) -> ReportExport:
    """Render a ready report's snapshot to a stored document.

    Rendering happens in the request because a report's content is already
    persisted: this composes one small document from data on hand, not an
    analysis over a video. The object is written under the organization's own
    prefix, so tenancy holds at the storage layer as well as in SQL.

    Raises:
        NotFoundError: the report does not exist in this organization.
        ConflictError: the report has not been generated yet.
    """
    await require_organization_writer(uow, organization_id=organization_id, user_id=user_id)

    async with uow:
        report = await uow.reports.get(report_id)
        if report is None or report.organization_id != organization_id:
            raise NotFoundError(f"Report {report_id} does not exist.")
        if not report.is_ready_snapshot():
            raise ConflictError(
                f"Report {report_id} is '{report.status}' and has no contents to export.",
                details={"status": str(report.status)},
            )
        title = report.title
        payload = dict(report.content)
        generated_at = report.generated_at

    document = render_report_html(
        content_from_dict(payload),
        title=title,
        generated_at=generated_at.isoformat() if generated_at is not None else "",
    )
    key = storage.build_key(
        str(organization_id),
        category="reports",
        owner_id=str(report_id),
        filename=EXPORT_FILENAME,
    )
    await _write_object(storage, key, document)

    async with uow:
        stored = await uow.reports.get(report_id)
        if stored is not None:
            stored.storage_key = key
            await uow.reports.update(stored)
            await uow.commit()

    return ReportExport(
        report_id=report_id,
        storage_key=key,
        content_type=EXPORT_CONTENT_TYPE,
        filename=EXPORT_FILENAME,
    )


async def get_report_export(
    uow: UnitOfWork,
    *,
    organization_id: OrganizationId,
    user_id: UserId,
    report_id: ReportId,
) -> ReportExport:
    """Resolve a report's stored export, checking membership and ownership first.

    Raises:
        NotFoundError: the report, or its export, does not exist in this organization.
    """
    await require_organization_member(uow, organization_id=organization_id, user_id=user_id)

    async with uow:
        report = await uow.reports.get(report_id)
        if report is None or report.organization_id != organization_id or not report.storage_key:
            raise NotFoundError(f"Report {report_id} has no export.")

    filename = report.storage_key.rsplit("/", 1)[-1] or EXPORT_FILENAME
    return ReportExport(
        report_id=report_id,
        storage_key=report.storage_key,
        content_type=EXPORT_CONTENT_TYPE,
        filename=filename,
    )


async def read_export_bytes(storage: VideoStorage, export: ReportExport) -> bytes:
    return await storage.open(export.storage_key)


async def _write_object(storage: VideoStorage, key: str, document: str) -> None:
    await storage.write_bytes(key, document.encode("utf-8"))
