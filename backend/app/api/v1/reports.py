from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query, Response, status

from app.api.dependencies import (
    CurrentUserDep,
    JobDispatcherDep,
    UnitOfWorkDep,
    VideoStorageDep,
)
from app.api.v1.params import Pagination, pagination
from app.api.v1.presenters import export_payload, report_detail_payload, report_payload
from app.application.use_cases import reports as use_cases
from app.domain.shared import AnalysisRunId, OrganizationId, ReportId
from app.schemas.common import ErrorResponse
from app.schemas.reports import (
    ReportDetailRead,
    ReportExportRead,
    ReportList,
    ReportRead,
)

router = APIRouter()


@router.post(
    "/analysis-runs/{run_id}/reports",
    response_model=ReportRead,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Request a report for an analysis run",
    description=(
        "Creates a report for an analysis run and queues its generation. Returns "
        "'202 Accepted'; poll the returned report for 'status: \"ready\"'. A run "
        "that has not completed its analysis cannot be reported on. A repeated "
        "request returns the report already covering the run rather than creating "
        "a second snapshot."
    ),
    responses={
        404: {"model": ErrorResponse, "description": "Analysis run not found."},
        409: {
            "model": ErrorResponse,
            "description": "The run has not produced a complete analysis to report on.",
        },
    },
)
async def create_run_report(
    run_id: uuid.UUID,
    user: CurrentUserDep,
    uow: UnitOfWorkDep,
    dispatcher: JobDispatcherDep,
    response: Response,
    organization_id: uuid.UUID = Query(description="Owning organization."),
) -> ReportRead:
    report = await use_cases.request_run_report(
        uow,
        organization_id=OrganizationId(organization_id),
        user_id=user.id,
        run_id=AnalysisRunId(run_id),
        dispatcher=dispatcher,
    )

    response.headers["Location"] = f"/api/v1/reports/{report.id}"
    return ReportRead.model_validate(report_payload(report))


@router.get("/reports", response_model=ReportList, summary="List reports in an organization")
async def list_reports(
    user: CurrentUserDep,
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
    "/reports/{report_id}",
    response_model=ReportDetailRead,
    summary="Get a report",
    description=(
        "Returns a report and, once it is ready, the snapshot body it was "
        "generated with: the run overview, per-track metrics, deterministic data "
        "observations and the report's stated limitations. Measurements are in "
        "source-video pixels; no physical unit is implied."
    ),
    responses={404: {"model": ErrorResponse, "description": "Not found."}},
)
async def get_report(
    report_id: uuid.UUID,
    user: CurrentUserDep,
    uow: UnitOfWorkDep,
    organization_id: uuid.UUID = Query(description="Owning organization."),
) -> ReportDetailRead:
    report = await use_cases.get_report(
        uow,
        organization_id=OrganizationId(organization_id),
        report_id=ReportId(report_id),
    )
    return ReportDetailRead.model_validate(report_detail_payload(report))


@router.post(
    "/reports/{report_id}/export",
    response_model=ReportExportRead,
    status_code=status.HTTP_201_CREATED,
    summary="Render a report to a downloadable document",
    description=(
        "Renders a ready report's stored snapshot to a self-contained HTML "
        "document and stores it privately under the organization's own prefix. "
        "The document contains only the report's own data: no scripts, no "
        "external assets and no interface controls. Returns the object's size and "
        "a download URL scoped to this report."
    ),
    responses={
        404: {"model": ErrorResponse, "description": "Report not found."},
        409: {"model": ErrorResponse, "description": "The report has no contents to export."},
    },
)
async def export_report(
    report_id: uuid.UUID,
    user: CurrentUserDep,
    uow: UnitOfWorkDep,
    storage: VideoStorageDep,
    organization_id: uuid.UUID = Query(description="Owning organization."),
) -> ReportExportRead:
    export = await use_cases.export_report(
        uow,
        storage=storage,
        organization_id=OrganizationId(organization_id),
        user_id=user.id,
        report_id=ReportId(report_id),
    )
    return ReportExportRead.model_validate(export_payload(export))


@router.get(
    "/reports/{report_id}/export",
    summary="Download a report's exported document",
    description=(
        "Streams the stored export of a report to a member of its organization. "
        "The storage key is never exposed to the client: the report is resolved "
        "and authorized first, then its object is read."
    ),
    responses={404: {"model": ErrorResponse, "description": "No export exists for this report."}},
)
async def download_report_export(
    report_id: uuid.UUID,
    user: CurrentUserDep,
    uow: UnitOfWorkDep,
    storage: VideoStorageDep,
    organization_id: uuid.UUID = Query(description="Owning organization."),
) -> Response:
    export = await use_cases.get_report_export(
        uow,
        organization_id=OrganizationId(organization_id),
        user_id=user.id,
        report_id=ReportId(report_id),
    )
    body = await use_cases.read_export_bytes(storage, export)
    return Response(
        content=body,
        media_type=export.content_type,
        headers={"Content-Disposition": f'attachment; filename="{export.filename}"'},
    )
