from __future__ import annotations

from app.domain.analysis.entities import AnalysisRun
from app.domain.metrics.types import AnalysisMetrics
from app.domain.reports.content import (
    REPORT_DEFINITION_VERSION,
    ReportContent,
    ReportOverview,
    build_track_summaries,
)
from app.domain.reports.observations import derive_observations
from app.domain.videos.entities import Video

LIMITATIONS: tuple[str, ...] = (
    "Measurements are reported in source-video space (pixels), not physical distance or speed.",
    "Pitch calibration is not available, so no metres, m/s or km/h are reported.",
    "Track identifiers are anonymous: player, team and jersey identity are not inferred.",
    "No sport-specific interpretation is applied; every value is a measurement over positions.",
    "A metric that could not be measured is reported as unavailable rather than as zero.",
)


def build_report_content(
    *,
    run: AnalysisRun,
    video: Video | None,
    observation_count: int,
    track_count: int,
    metrics: AnalysisMetrics,
) -> ReportContent:
    """Assemble a report body from an analysis run's already-persisted output.

    Deterministic: the same run, observations and metrics always yield the same
    content. Nothing is sampled, randomised or inferred, and no new metric is
    computed here.
    """
    return ReportContent(
        definition_version=REPORT_DEFINITION_VERSION,
        overview=ReportOverview(
            analysis_run_id=run.id,
            analysis_status=str(run.status),
            video_id=str(run.video_id),
            video_filename=video.original_filename if video is not None else "Unavailable",
            match_id=str(run.match_id) if run.match_id else None,
            analysis_created_at=run.created_at,
            analysis_finished_at=run.finished_at,
            source_width=video.spec.width if video is not None else None,
            source_height=video.spec.height if video is not None else None,
            observation_count=observation_count,
            track_count=track_count,
            metric_definition_version=metrics.definition_version,
            space=metrics.space,
        ),
        tracks=build_track_summaries(metrics),
        observations=derive_observations(metrics.tracks),
        limitations=LIMITATIONS,
    )
