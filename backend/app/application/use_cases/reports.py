"""Report use cases."""

from __future__ import annotations

from app.application.ports.jobs import Job, JobDispatcher, JobKind
from app.application.ports.unit_of_work import UnitOfWork
from app.core.errors import NotFoundError
from app.domain.reports.entities import Report, ReportScope
from app.domain.shared import (
    AnalysisRunId,
    MatchId,
    OrganizationId,
    ReportId,
    TeamId,
    UserId,
)


async def request_report(
    uow: UnitOfWork,
    *,
    organization_id: OrganizationId,
    title: str,
    scope: ReportScope,
    created_by_id: UserId | None,
    dispatcher: JobDispatcher,
) -> Report:
    """Create a draft report and queue its generation.

    Rendering a PDF that embeds dozens of charts should not happen in a request,
    for the same reason video analysis does not.
    """
    async with uow:
        report = Report(
            organization_id=organization_id,
            title=title,
            scope=scope,
            created_by_id=created_by_id,
        )
        report.mark_generating()
        await uow.reports.add(report)
        await uow.commit()

    await dispatcher.dispatch(
        Job(
            kind=JobKind(JobKind.GENERATE_REPORT),
            payload={"report_id": str(report.id)},
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


def match_scope(match_id: MatchId) -> ReportScope:
    return ReportScope(match_id=match_id)


def team_scope(team_id: TeamId) -> ReportScope:
    return ReportScope(team_id=team_id)


def run_scope(*run_ids: AnalysisRunId) -> ReportScope:
    return ReportScope(analysis_run_ids=tuple(run_ids))
