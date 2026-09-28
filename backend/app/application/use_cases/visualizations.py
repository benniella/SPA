"""The visualization read layer: derive bounded, deterministic visuals for a run.

It consumes the same persisted data the metrics stage does — tracking
observations and derived metrics — and adds nothing analytical. Coordinates stay
in source-image pixels, so nothing here can be read as a physical position.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.application.ports.unit_of_work import UnitOfWork
from app.application.use_cases.metrics import get_analysis_metrics
from app.application.use_cases.organizations import require_organization_member
from app.core.config import Settings
from app.core.errors import ConflictError, NotFoundError
from app.domain.analysis.entities import AnalysisRunStatus
from app.domain.metrics.types import AnalysisMetrics, TrackObservationPoint
from app.domain.shared import AnalysisRunId, OrganizationId, UserId
from app.domain.tracking.entities import TrackRecord
from app.domain.visualization.types import (
    ActivityTimeline,
    DensityGrid,
    SourceFrame,
    TrackPath,
    build_activity_timeline,
    build_density_grid,
    build_track_paths,
)

READABLE_STATUSES = frozenset({AnalysisRunStatus.SUCCEEDED, AnalysisRunStatus.PARTIALLY_SUCCEEDED})

#: Observations read per query while deriving a visualization. The same bound the
#: metrics engine uses, so a match-long run is never materialized in one query.
_PAGE_SIZE = 2000


@dataclass(frozen=True, slots=True)
class VisualizationData:
    """Everything one visualization read returns, in source-image pixels."""

    analysis_run_id: AnalysisRunId
    organization_id: OrganizationId
    status: str
    frame: SourceFrame
    observation_count: int
    track_count: int
    paths: tuple[TrackPath, ...]
    density: DensityGrid
    timeline: ActivityTimeline
    metrics: AnalysisMetrics


async def get_run_visualization(
    uow: UnitOfWork,
    *,
    settings: Settings,
    organization_id: OrganizationId,
    user_id: UserId,
    run_id: AnalysisRunId,
) -> VisualizationData:
    """Derive the visualization for a run from its persisted observations.

    Raises:
        NotFoundError: the run does not exist in this organization.
        ConflictError: the run has not produced tracking data to visualize.
    """
    await require_organization_member(uow, organization_id=organization_id, user_id=user_id)

    async with uow:
        run = await uow.analysis_runs.get(run_id)
        if run is None or run.organization_id != organization_id:
            # A cross-tenant probe must not be able to confirm the id exists.
            raise NotFoundError(f"Analysis run {run_id} does not exist.")

        if run.status.value not in READABLE_STATUSES:
            raise ConflictError(
                f"Analysis run {run_id} is '{run.status}' and has no tracking data to visualize.",
                details={"status": str(run.status)},
            )

        observation_count = await uow.track_observations.count_for_run(run_id)
        track_ids = await uow.track_observations.track_ids(run_id)
        extent = await uow.track_observations.coordinate_extent(run_id)
        video = await uow.videos.get(run.video_id)

    frame = SourceFrame(
        width=video.spec.width if video is not None else None,
        height=video.spec.height if video is not None else None,
    )
    bounds = _bounds(frame, extent)

    observations = await _read_observations(uow, run_id, track_ids)
    metrics = await get_analysis_metrics(
        uow,
        organization_id=organization_id,
        user_id=user_id,
        run_id=run_id,
    )

    return VisualizationData(
        analysis_run_id=run.id,
        organization_id=run.organization_id,
        status=str(run.status),
        frame=frame,
        observation_count=observation_count,
        track_count=len(track_ids),
        paths=build_track_paths(
            observations,
            max_points_per_track=settings.visualization_max_points_per_track,
        ),
        density=build_density_grid(
            observations,
            columns=settings.visualization_grid_columns,
            rows=settings.visualization_grid_rows,
            bounds=bounds,
        ),
        timeline=build_activity_timeline(
            observations,
            bucket_seconds=settings.visualization_timeline_bucket_seconds,
        ),
        metrics=metrics,
    )


async def _read_observations(
    uow: UnitOfWork,
    run_id: AnalysisRunId,
    track_ids: list[int],
) -> list[TrackObservationPoint]:
    """Read the run's observations in bounded pages, one track at a time.

    Reads are paged by the same batch size the metrics engine uses, so a run with
    hundreds of thousands of rows is never materialized in one query. The
    per-track bound is applied when the paths are built, not here, because the
    grid and timeline need the full set to be correct.
    """
    points: list[TrackObservationPoint] = []
    for track_id in track_ids:
        offset = 0
        while True:
            async with uow:
                page = await uow.track_observations.list_for_track(
                    run_id, track_id, limit=_PAGE_SIZE, offset=offset
                )
            if not page:
                break
            points.extend(_to_point(record) for record in page)
            if len(page) < _PAGE_SIZE:
                break
            offset += len(page)
    return points


def _bounds(
    frame: SourceFrame,
    extent: tuple[float, float, float, float] | None,
) -> tuple[float, float, float, float] | None:
    """Prefer the source frame; fall back to the observed coordinate extent.

    The frame is what the coordinates were measured against, so it is the honest
    extent to draw. It is unknown for a run whose video never recorded a
    resolution, in which case the observed bounds are the only truthful span.
    """
    if frame.is_known:
        return (0.0, 0.0, float(frame.width or 0), float(frame.height or 0))
    return extent


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
