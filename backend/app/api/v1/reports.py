from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query, Response, status

from app.api.dependencies import JobDispatcherDep, UnitOfWorkDep
from app.api.v1.params import Pagination, pagination
from app.api.v1.presenters import report_payload
from app.application.use_cases import reports as use_cases
from app.domain.reports.entities import ReportScope
from app.domain.shared import (
    AnalysisRunId,
    MatchId,
    OrganizationId,
    ReportId,
    TeamId,
)
from app.schemas.common import ErrorResponse
from app.schemas.reports import ReportCreate, ReportList, ReportRead

router = APIRouter()


@router.post(
    "",
    response_model=ReportRead,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Request a report",
    description=(
        "Creates a report in 'generating' state and queues its rendering. "
        "Composing charts for a whole season in a request would time out; the "
        "same asynchronous contract as video analysis applies."
    ),
)
async def create_report(
    payload: ReportCreate,
    uow: UnitOfWorkDep,
    dispatcher: JobDispatcherDep,
    response: Response,
) -> ReportRead:
    scope = ReportScope(
        match_id=MatchId(payload.match_id) if payload.match_id else None,
        team_id=TeamId(payload.team_id) if payload.team_id else None,
        analysis_run_ids=tuple(AnalysisRunId(run_id) for run_id in payload.analysis_run_ids),
    )

    report = await use_cases.request_report(
        uow,
        organization_id=OrganizationId(payload.organization_id),
        title=payload.title,
        scope=scope,
        created_by_id=None,  # Populated once authentication lands.
        dispatcher=dispatcher,
    )

    response.headers["Location"] = f"/api/v1/reports/{report.id}"
    return ReportRead.model_validate(report_payload(report))


@router.get("", response_model=ReportList, summary="List reports in an organization")
async def list_reports(
    uow: UnitOfWorkDep,
    organization_id: uuid.UUID = Query(description="Owning organization."),
    page: Pagination = Depends(pagination),
) -> ReportList:
    reports = await use_cases.list_reports(
        uow,
        organization_id=OrganizationId(organization_id),
        limit=page.limit,
        offset=page.offset,
    )
    return ReportList(
        items=[ReportRead.model_validate(report_payload(report)) for report in reports],
        meta=page.meta(len(reports)),
    )


@router.get(
    "/{report_id}",
    response_model=ReportRead,
    summary="Get a report",
    responses={404: {"model": ErrorResponse, "description": "Not found."}},
)
async def get_report(
    report_id: uuid.UUID,
    uow: UnitOfWorkDep,
    organization_id: uuid.UUID = Query(description="Owning organization."),
) -> ReportRead:
    report = await use_cases.get_report(
        uow,
        organization_id=OrganizationId(organization_id),
        report_id=ReportId(report_id),
    )
    return ReportRead.model_validate(report_payload(report))
