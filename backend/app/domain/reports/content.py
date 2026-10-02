from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from app.domain.metrics.types import AnalysisMetrics, MetricName, MetricSpace, MetricUnit
from app.domain.shared import AnalysisRunId

REPORT_DEFINITION_VERSION = "v1"


class ObservationType(StrEnum):
    HIGHEST_OBSERVATION_COUNT = "highest_observation_count"
    HIGHEST_COVERAGE = "highest_coverage"
    HIGHEST_DISPLACEMENT = "highest_displacement"
    HIGHEST_AVERAGE_SPEED = "highest_average_speed"
    HIGHEST_PEAK_SPEED = "highest_peak_speed"
    HIGHEST_PEAK_ACCELERATION = "highest_peak_acceleration"
    LONGEST_DURATION = "longest_duration"


@dataclass(frozen=True, slots=True)
class MetricSummary:
    """One measured value for one track, exactly as the metrics stage stored it.

    'value' is None when the metric is unavailable, which is a different statement
    from a metric whose value is genuinely zero.
    """

    name: MetricName
    unit: MetricUnit
    value: float | None
    sample_count: int

    @property
    def is_available(self) -> bool:
        return self.value is not None


@dataclass(frozen=True, slots=True)
class TrackSummary:
    track_id: int
    space: MetricSpace
    metrics: tuple[MetricSummary, ...]

    def metric(self, name: MetricName) -> MetricSummary | None:
        for summary in self.metrics:
            if summary.name is name:
                return summary
        return None


@dataclass(frozen=True, slots=True)
class DataObservation:
    """A factual statement about one measured value, derived mechanically.

    It names the metric and the value it came from, so a reader can trace the
    sentence back to 'track_metrics' rather than trusting prose.
    """

    type: ObservationType
    track_ids: tuple[int, ...]
    metric_name: MetricName
    unit: MetricUnit
    space: MetricSpace
    value: float
    message: str


@dataclass(frozen=True, slots=True)
class ReportOverview:
    analysis_run_id: AnalysisRunId
    analysis_status: str
    video_id: str
    video_filename: str
    match_id: str | None
    analysis_created_at: datetime
    analysis_finished_at: datetime | None
    source_width: int | None
    source_height: int | None
    observation_count: int
    track_count: int
    metric_definition_version: str
    space: MetricSpace


@dataclass(frozen=True, slots=True)
class ReportContent:
    """The structured body of a generated report.

    A snapshot: it is written once when the report is generated and never
    re-derived from live metrics, so a report read a season later states what the
    analysis said at the time, not what it says now.
    """

    definition_version: str
    overview: ReportOverview
    tracks: tuple[TrackSummary, ...]
    observations: tuple[DataObservation, ...]
    limitations: tuple[str, ...]


def build_track_summaries(metrics: AnalysisMetrics) -> tuple[TrackSummary, ...]:
    """Project each track's metrics into a stable, ordered summary."""
    return tuple(
        TrackSummary(
            track_id=track.track_id,
            space=track.space,
            metrics=tuple(
                MetricSummary(
                    name=value.name,
                    unit=value.unit,
                    value=value.value if value.is_available else None,
                    sample_count=value.sample_count,
                )
                for value in track.values
            ),
        )
        for track in metrics.tracks
    )


def content_from_dict(payload: dict[str, object]) -> ReportContent:
    """Rebuild a report body from its stored JSONB snapshot.

    The inverse of 'content_to_dict', so an export renders the snapshot that was
    persisted rather than re-deriving anything from live metrics.
    """
    overview = payload["overview"]
    assert isinstance(overview, dict)
    tracks = payload["tracks"]
    observations = payload["observations"]
    limitations = payload["limitations"]
    assert isinstance(tracks, list)
    assert isinstance(observations, list)
    assert isinstance(limitations, list)

    return ReportContent(
        definition_version=str(payload["definition_version"]),
        overview=ReportOverview(
            analysis_run_id=AnalysisRunId(uuid.UUID(str(overview["analysis_run_id"]))),
            analysis_status=str(overview["analysis_status"]),
            video_id=str(overview["video_id"]),
            video_filename=str(overview["video_filename"]),
            match_id=str(overview["match_id"]) if overview["match_id"] else None,
            analysis_created_at=datetime.fromisoformat(str(overview["analysis_created_at"])),
            analysis_finished_at=(
                datetime.fromisoformat(str(overview["analysis_finished_at"]))
                if overview["analysis_finished_at"]
                else None
            ),
            source_width=_optional_int(overview["source_width"]),
            source_height=_optional_int(overview["source_height"]),
            observation_count=int(str(overview["observation_count"])),
            track_count=int(str(overview["track_count"])),
            metric_definition_version=str(overview["metric_definition_version"]),
            space=MetricSpace(str(overview["space"])),
        ),
        tracks=tuple(
            TrackSummary(
                track_id=int(str(track["track_id"])),
                space=MetricSpace(str(track["space"])),
                metrics=tuple(
                    MetricSummary(
                        name=MetricName(str(metric["name"])),
                        unit=MetricUnit(str(metric["unit"])),
                        value=(float(metric["value"]) if metric["value"] is not None else None),
                        sample_count=int(str(metric["sample_count"])),
                    )
                    for metric in track["metrics"]
                ),
            )
            for track in tracks
        ),
        observations=tuple(
            DataObservation(
                type=ObservationType(str(observation["type"])),
                track_ids=tuple(int(str(track_id)) for track_id in observation["track_ids"]),
                metric_name=MetricName(str(observation["metric_name"])),
                unit=MetricUnit(str(observation["unit"])),
                space=MetricSpace(str(observation["space"])),
                value=float(observation["value"]),
                message=str(observation["message"]),
            )
            for observation in observations
        ),
        limitations=tuple(str(item) for item in limitations),
    )


def _optional_int(value: object) -> int | None:
    return None if value is None else int(str(value))


def content_to_dict(content: ReportContent) -> dict[str, object]:
    """Serialise a report body for JSONB persistence.

    Keys mirror the API schema so a stored snapshot and a served response cannot
    describe the same report differently.
    """
    overview = content.overview
    return {
        "definition_version": content.definition_version,
        "overview": {
            "analysis_run_id": str(overview.analysis_run_id),
            "analysis_status": overview.analysis_status,
            "video_id": overview.video_id,
            "video_filename": overview.video_filename,
            "match_id": overview.match_id,
            "analysis_created_at": overview.analysis_created_at.isoformat(),
            "analysis_finished_at": (
                overview.analysis_finished_at.isoformat()
                if overview.analysis_finished_at is not None
                else None
            ),
            "source_width": overview.source_width,
            "source_height": overview.source_height,
            "observation_count": overview.observation_count,
            "track_count": overview.track_count,
            "metric_definition_version": overview.metric_definition_version,
            "space": str(overview.space),
        },
        "tracks": [
            {
                "track_id": track.track_id,
                "space": str(track.space),
                "metrics": [
                    {
                        "name": str(metric.name),
                        "unit": str(metric.unit),
                        "availability": "available" if metric.is_available else "unavailable",
                        "value": metric.value,
                        "sample_count": metric.sample_count,
                    }
                    for metric in track.metrics
                ],
            }
            for track in content.tracks
        ],
        "observations": [
            {
                "type": str(observation.type),
                "track_ids": list(observation.track_ids),
                "metric_name": str(observation.metric_name),
                "unit": str(observation.unit),
                "space": str(observation.space),
                "value": observation.value,
                "message": observation.message,
            }
            for observation in content.observations
        ],
        "limitations": list(content.limitations),
    }
