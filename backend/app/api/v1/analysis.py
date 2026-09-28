from __future__ import annotations

import uuid
from typing import cast

from fastapi import APIRouter, Depends, Query, Response, status

from app.api.dependencies import CurrentUserDep, JobDispatcherDep, SettingsDep, UnitOfWorkDep
from app.api.v1.params import Pagination, pagination
from app.api.v1.presenters import (
    analysis_metrics_payload,
    analysis_run_payload,
    run_visualization_payload,
)
from app.application.use_cases import metrics as metrics_use_cases
from app.application.use_cases import videos as use_cases
from app.application.use_cases import visualizations as visualization_use_cases
from app.domain.analysis.entities import AnalysisPipelineSpec
from app.domain.shared import AnalysisRunId, OrganizationId, VideoId
from app.schemas.analysis import AnalysisRunCreate, AnalysisRunList, AnalysisRunRead
from app.schemas.common import ErrorResponse
from app.schemas.metrics import (
    AnalysisMetricsRead,
    MetricsCalculationRead,
    ProcessingJobStatusLiteral,
)
from app.schemas.visualization import RunVisualizationRead

router = APIRouter()


@router.post(
    "",
    response_model=AnalysisRunRead,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Queue an analysis run for a video",
    description=(
        "Creates an analysis run and dispatches it to the job pipeline. Returns "
        "immediately with '202 Accepted'; the run is processed asynchronously. "
        "Poll the returned resource for progress."
    ),
    responses={
        404: {"model": ErrorResponse, "description": "Video not found."},
        409: {"model": ErrorResponse, "description": "Video is not in an analysable state."},
    },
)
async def create_analysis_run(
    payload: AnalysisRunCreate,
    uow: UnitOfWorkDep,
    dispatcher: JobDispatcherDep,
    response: Response,
) -> AnalysisRunRead:
    pipeline = None
    if payload.pipeline is not None:
        pipeline = AnalysisPipelineSpec(
            stages=tuple(payload.pipeline.stages),
            model_versions=dict(payload.pipeline.model_versions),
            params=dict(payload.pipeline.params),
        )

    run = await use_cases.request_analysis_run(
        uow,
        organization_id=OrganizationId(payload.organization_id),
        video_id=VideoId(payload.video_id),
        dispatcher=dispatcher,
        pipeline=pipeline,
    )

    # The Location header lets a client poll without constructing the URL.
    response.headers["Location"] = f"/api/v1/analysis-runs/{run.id}"
    return AnalysisRunRead.model_validate(analysis_run_payload(run))


@router.get(
    "/{run_id}",
    response_model=AnalysisRunRead,
    summary="Get an analysis run",
    description="Polled by the frontend while a match video is processed.",
    responses={404: {"model": ErrorResponse, "description": "Not found."}},
)
async def get_analysis_run(
    run_id: uuid.UUID,
    uow: UnitOfWorkDep,
    organization_id: uuid.UUID = Query(description="Owning organization."),
) -> AnalysisRunRead:
    run = await use_cases.get_analysis_run(
        uow,
        organization_id=OrganizationId(organization_id),
        run_id=str(run_id),
    )
    return AnalysisRunRead.model_validate(analysis_run_payload(run))


@router.post(
    "/{run_id}/metrics",
    response_model=MetricsCalculationRead,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Queue metric calculation for an analysis run",
    description=(
        "Derives performance metrics from the run's persisted tracking observations "
        "and returns '202 Accepted'. The work is performed by the worker; poll the "
        "run and then read 'GET /analysis-runs/{id}/metrics'. A repeated request "
        "returns the existing job rather than creating a second one."
    ),
    responses={
        404: {"model": ErrorResponse, "description": "Analysis run not found."},
        409: {
            "model": ErrorResponse,
            "description": "The run has no tracking data to derive metrics from.",
        },
    },
)
async def calculate_analysis_metrics(
    run_id: uuid.UUID,
    user: CurrentUserDep,
    uow: UnitOfWorkDep,
    dispatcher: JobDispatcherDep,
    organization_id: uuid.UUID = Query(description="Owning organization."),
) -> MetricsCalculationRead:
    request = await metrics_use_cases.request_metrics_calculation(
        uow,
        organization_id=OrganizationId(organization_id),
        user_id=user.id,
        run_id=AnalysisRunId(run_id),
        dispatcher=dispatcher,
    )
    return MetricsCalculationRead(
        analysis_run_id=request.analysis_run_id,
        job_id=request.job.id,
        status=cast(ProcessingJobStatusLiteral, request.job.status.value),
        progress=request.job.progress,
    )


@router.get(
    "/{run_id}/metrics",
    response_model=AnalysisMetricsRead,
    summary="Get the derived metrics for an analysis run",
    description=(
        "Returns one record per track with its metrics, each carrying its unit and "
        "coordinate space. Values are source-space (pixels): no pitch calibration "
        "exists yet, so no physical unit is reported."
    ),
    responses={
        404: {"model": ErrorResponse, "description": "Analysis run not found."},
        409: {"model": ErrorResponse, "description": "The run has not produced metrics."},
    },
)
async def get_analysis_metrics(
    run_id: uuid.UUID,
    user: CurrentUserDep,
    uow: UnitOfWorkDep,
    organization_id: uuid.UUID = Query(description="Owning organization."),
) -> AnalysisMetricsRead:
    metrics = await metrics_use_cases.get_analysis_metrics(
        uow,
        organization_id=OrganizationId(organization_id),
        user_id=user.id,
        run_id=AnalysisRunId(run_id),
    )
    return AnalysisMetricsRead.model_validate(analysis_metrics_payload(metrics))


@router.get(
    "/{run_id}/visualization",
    response_model=RunVisualizationRead,
    summary="Get the visualization data for an analysis run",
    description=(
        "Returns bounded, deterministic visualization data derived from the run's "
        "persisted tracking observations and metrics: per-track paths, a spatial "
        "density grid, an activity timeline and the derived metrics. Coordinates "
        "are source-video pixels; no physical unit is implied. The response is "
        "bounded by server-side downsampling and aggregation, so it never carries "
        "a run's full observation set."
    ),
    responses={
        404: {"model": ErrorResponse, "description": "Analysis run not found."},
        409: {
            "model": ErrorResponse,
            "description": "The run has not produced tracking data to visualize.",
        },
    },
)
async def get_run_visualization(
    run_id: uuid.UUID,
    user: CurrentUserDep,
    uow: UnitOfWorkDep,
    settings: SettingsDep,
    organization_id: uuid.UUID = Query(description="Owning organization."),
) -> RunVisualizationRead:
    data = await visualization_use_cases.get_run_visualization(
        uow,
        settings=settings,
        organization_id=OrganizationId(organization_id),
        user_id=user.id,
        run_id=AnalysisRunId(run_id),
    )
    return RunVisualizationRead.model_validate(run_visualization_payload(data))


@router.get(
    "",
    response_model=AnalysisRunList,
    summary="List analysis runs for a video",
)
async def list_analysis_runs(
    uow: UnitOfWorkDep,
    video_id: uuid.UUID = Query(description="Video whose runs should be listed."),
    page: Pagination = Depends(pagination),
) -> AnalysisRunList:
    async with uow:
        runs = await uow.analysis_runs.list_for_video(VideoId(video_id))
    page_items = runs[page.offset : page.offset + page.limit]
    return AnalysisRunList(
        items=[AnalysisRunRead.model_validate(analysis_run_payload(run)) for run in page_items],
        meta=page.meta(len(page_items)),
    )


@router.post(
    "/{run_id}/cancel",
    response_model=AnalysisRunRead,
    summary="Cancel an in-flight analysis run",
    responses={
        404: {"model": ErrorResponse, "description": "Not found."},
        409: {"model": ErrorResponse, "description": "The run has already finished."},
    },
)
async def cancel_analysis_run(
    run_id: uuid.UUID,
    uow: UnitOfWorkDep,
    organization_id: uuid.UUID = Query(description="Owning organization."),
) -> AnalysisRunRead:
    async with uow:
        run = await uow.analysis_runs.get(AnalysisRunId(run_id))
        if run is None or run.organization_id != OrganizationId(organization_id):
            from app.core.errors import NotFoundError

            raise NotFoundError(f"Analysis run {run_id} does not exist.")
        run.cancel()
        await uow.analysis_runs.update(run)
        await uow.commit()

    return AnalysisRunRead.model_validate(analysis_run_payload(run))
