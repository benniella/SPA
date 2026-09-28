from __future__ import annotations

from app.application.use_cases.visualizations import VisualizationData
from app.domain.analysis.entities import AnalysisRun
from app.domain.jobs.entities import ProcessingJob
from app.domain.matches.entities import Match
from app.domain.metrics.types import AnalysisMetrics
from app.domain.organizations.entities import Organization
from app.domain.players.entities import Player
from app.domain.reports.entities import Report
from app.domain.teams.entities import Team
from app.domain.users.entities import User
from app.domain.videos.entities import Video


def organization_payload(organization: Organization) -> dict[str, object]:
    return {
        "id": organization.id,
        "name": organization.name,
        "slug": organization.slug.value,
        "created_at": organization.created_at,
        "updated_at": organization.updated_at,
    }


def user_payload(user: User) -> dict[str, object]:
    return {
        "id": user.id,
        "email": user.email.value,
        "display_name": user.display_name,
        "is_active": user.is_active,
        "created_at": user.created_at,
        "updated_at": user.updated_at,
    }


def team_payload(team: Team) -> dict[str, object]:
    return {
        "id": team.id,
        "organization_id": team.organization_id,
        "name": team.name,
        "slug": team.slug.value,
        "sport": team.sport,
        "season": team.season,
        "created_at": team.created_at,
        "updated_at": team.updated_at,
    }


def player_payload(player: Player) -> dict[str, object]:
    return {
        "id": player.id,
        "organization_id": player.organization_id,
        "display_name": player.display_name,
        "date_of_birth": player.date_of_birth,
        "external_ref": player.external_ref,
        "created_at": player.created_at,
        "updated_at": player.updated_at,
    }


def match_payload(match: Match) -> dict[str, object]:
    return {
        "id": match.id,
        "organization_id": match.organization_id,
        "played_on": match.played_on,
        "home_team_id": match.home_team_id,
        "away_team_id": match.away_team_id,
        "home_team_name": match.home_team_name,
        "away_team_name": match.away_team_name,
        "competition": match.competition,
        "is_home": match.venue.is_home,
        "venue_name": match.venue.venue_name,
        "created_at": match.created_at,
        "updated_at": match.updated_at,
    }


def video_payload(video: Video) -> dict[str, object]:
    return {
        "id": video.id,
        "organization_id": video.organization_id,
        "match_id": video.match_id,
        "original_filename": video.original_filename,
        "status": str(video.status),
        "content_type": video.content_type,
        "size_bytes": video.size_bytes,
        "duration_seconds": video.spec.duration_seconds,
        "frame_rate": video.spec.frame_rate,
        "width": video.spec.width,
        "height": video.spec.height,
        "codec": video.spec.codec,
        "failure_reason": video.failure_reason,
        "created_at": video.created_at,
        "updated_at": video.updated_at,
    }


def processing_job_payload(job: ProcessingJob) -> dict[str, object]:
    return {
        "id": job.id,
        "organization_id": job.organization_id,
        "video_id": job.video_id,
        "job_type": job.job_type,
        "status": str(job.status),
        "attempt": job.attempt,
        "max_attempts": job.max_attempts,
        "progress": job.progress,
        "error": job.error,
        "started_at": job.started_at,
        "completed_at": job.completed_at,
        "created_at": job.created_at,
        "updated_at": job.updated_at,
    }


def report_payload(report: Report) -> dict[str, object]:
    return {
        "id": report.id,
        "organization_id": report.organization_id,
        "created_by_id": report.created_by_id,
        "title": report.title,
        "status": str(report.status),
        "match_id": report.scope.match_id,
        "team_id": report.scope.team_id,
        "storage_key": report.storage_key,
        "error_message": report.error_message,
        "generated_at": report.generated_at,
        "created_at": report.created_at,
        "updated_at": report.updated_at,
    }


def analysis_metrics_payload(metrics: AnalysisMetrics) -> dict[str, object]:
    return {
        "analysis_run_id": metrics.analysis_run_id,
        "organization_id": metrics.organization_id,
        "space": str(metrics.space),
        "definition_version": metrics.definition_version,
        "track_count": len(metrics.tracks),
        "tracks": [
            {
                "track_id": track.track_id,
                "space": str(track.space),
                "metrics": [
                    {
                        "name": str(value.name),
                        "unit": str(value.unit),
                        "space": str(track.space),
                        "availability": str(value.availability),
                        "value": value.value,
                        "sample_count": value.sample_count,
                    }
                    for value in track.values
                ],
            }
            for track in metrics.tracks
        ],
        "generated_at": metrics.generated_at,
    }


def analysis_run_payload(run: AnalysisRun) -> dict[str, object]:
        return {
        "id": run.id,
        "organization_id": run.organization_id,
        "video_id": run.video_id,
        "match_id": run.match_id,
        "status": str(run.status),
        "progress_percent": run.progress_percent,
        "error_message": run.error_message,
        "started_at": run.started_at,
        "finished_at": run.finished_at,
        "created_at": run.created_at,
        "updated_at": run.updated_at,
    }


def run_visualization_payload(data: VisualizationData) -> dict[str, object]:
    return {
        "analysis_run_id": data.analysis_run_id,
        "organization_id": data.organization_id,
        "status": data.status,
        "space": "source",
        "frame": {"width": data.frame.width, "height": data.frame.height},
        "observation_count": data.observation_count,
        "track_count": data.track_count,
        "paths": [
            {
                "track_id": path.track_id,
                "observation_count": path.observation_count,
                "downsampled": path.downsampled,
                "start_seconds": path.start_seconds,
                "end_seconds": path.end_seconds,
                "points": [
                    {
                        "frame_index": point.frame_index,
                        "timestamp_seconds": point.timestamp_seconds,
                        "x": point.x,
                        "y": point.y,
                        "confidence": point.confidence,
                    }
                    for point in path.points
                ],
            }
            for path in data.paths
        ],
        "density": {
            "columns": data.density.columns,
            "rows": data.density.rows,
            "counts": list(data.density.counts),
            "max_count": data.density.max_count,
            "bounds": list(data.density.bounds),
            "observation_count": data.density.observation_count,
            "track_count": data.density.track_count,
        },
        "timeline": {
            "bucket_seconds": data.timeline.bucket_seconds,
            "start_seconds": data.timeline.start_seconds,
            "end_seconds": data.timeline.end_seconds,
            "max_count": data.timeline.max_count,
            "buckets": [
                {
                    "index": bucket.index,
                    "start_seconds": bucket.start_seconds,
                    "end_seconds": bucket.end_seconds,
                    "observation_count": bucket.observation_count,
                    "track_ids": list(bucket.track_ids),
                }
                for bucket in data.timeline.buckets
            ],
        },
        "metrics": analysis_metrics_payload(data.metrics),
    }
