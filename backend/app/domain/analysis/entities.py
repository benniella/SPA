"""Analysis runs: the unit of asynchronous video-processing work.

This module defines *what* a processing request is and which state transitions
are legal. It deliberately does not know how the work is executed — that is a
job-port concern (' 'app.application.ports.jobs' '), so SPA can move from inline
execution to Celery without touching these classes.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from app.domain.shared import (
    AnalysisRunId,
    MatchId,
    OrganizationId,
    VideoId,
    new_id,
    utcnow,
)


class AnalysisRunStatus:
    """Lifecycle of one analysis run.

    Terminal states are ' 'succeeded' ', ' 'partially_succeeded' ', ' 'failed' ' and
    ' 'cancelled' '. ' 'partially_succeeded' ' exists because a multi-stage pipeline
    (detection → tracking → metrics) can produce usable tracking data while a
    later stage fails; collapsing that into ' 'failed' ' would throw away
    expensive, valid work.
    """

    __slots__ = ("value",)

    PENDING = "pending"
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    PARTIALLY_SUCCEEDED = "partially_succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"

    ALLOWED = frozenset(
        {PENDING, QUEUED, RUNNING, SUCCEEDED, PARTIALLY_SUCCEEDED, FAILED, CANCELLED}
    )
    TERMINAL = frozenset({SUCCEEDED, PARTIALLY_SUCCEEDED, FAILED, CANCELLED})

    def __init__(self, value: str) -> None:
        if value not in self.ALLOWED:
            raise ValueError(f"Unknown analysis run status: {value!r}.")
        self.value = value

    def __str__(self) -> str:
        return self.value

    def __repr__(self) -> str:
        return f"AnalysisRunStatus({self.value!r})"

    def __eq__(self, other: object) -> bool:
        if isinstance(other, AnalysisRunStatus):
            return self.value == other.value
        if isinstance(other, str):
            return self.value == other
        return NotImplemented

    def __hash__(self) -> int:
        return hash(self.value)

    @property
    def is_terminal(self) -> bool:
        return self.value in self.TERMINAL


@dataclass(frozen=True, slots=True)
class AnalysisPipelineSpec:
    """Declarative description of the work a run should perform.

    The API stores this; a worker interprets it. New stages are added by
    extending the spec, not by adding columns or endpoints, which keeps the
    processing pipeline evolvable by the ML team without API churn.
    """

    #: Ordered stage identifiers, e.g. ["detection", "tracking", "metrics"].
    stages: tuple[str, ...] = ()
    #: Model identifiers and versions, resolved by the worker.
    model_versions: dict[str, str] = field(default_factory=dict)
    #: Stage parameters (thresholds, frame sampling, pitch calibration, ...).
    params: dict[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if len(set(self.stages)) != len(self.stages):
            raise ValueError("Pipeline stages must be unique.")

    @property
    def is_empty(self) -> bool:
        return not self.stages


@dataclass(slots=True)
class AnalysisRun:
    """One execution of the processing pipeline over one video.

    Progress is tracked here so the frontend can poll a single resource while a
    match-long video is processed asynchronously.
    """

    organization_id: OrganizationId
    video_id: VideoId
    pipeline: AnalysisPipelineSpec
    id: AnalysisRunId = field(default_factory=lambda: AnalysisRunId(new_id()))
    match_id: MatchId | None = None
    status: AnalysisRunStatus = field(
        default_factory=lambda: AnalysisRunStatus(AnalysisRunStatus.PENDING)
    )
    # Populated when a worker picks the run up — set by the job layer.
    started_at: datetime | None = None
    finished_at: datetime | None = None
    error_message: str | None = None
    # Per-stage outcome keyed by stage name. Schema-less by nature: each stage
    # reports different diagnostics, so JSONB is appropriate here.
    stage_results: dict[str, object] = field(default_factory=dict)
    progress_percent: float = 0.0
    created_at: datetime = field(default_factory=utcnow)
    updated_at: datetime = field(default_factory=utcnow)

    def __post_init__(self) -> None:
        if self.pipeline.is_empty:
            raise ValueError("An analysis run requires at least one pipeline stage.")
        if not (0.0 <= self.progress_percent <= 100.0):
            raise ValueError("progress_percent must be between 0 and 100.")

    @property
    def is_terminal(self) -> bool:
        return self.status.is_terminal

    @property
    def duration_seconds(self) -> float | None:
        if self.started_at is None or self.finished_at is None:
            return None
        return (self.finished_at - self.started_at).total_seconds()

    def queue(self) -> None:
        if self.status.value != AnalysisRunStatus.PENDING:
            raise ValueError(f"Cannot queue an analysis run in state {self.status}.")
        self.status = AnalysisRunStatus(AnalysisRunStatus.QUEUED)
        self.updated_at = utcnow()

    def start(self) -> None:
        if self.status.value not in {AnalysisRunStatus.PENDING, AnalysisRunStatus.QUEUED}:
            raise ValueError(f"Cannot start an analysis run in state {self.status}.")
        self.status = AnalysisRunStatus(AnalysisRunStatus.RUNNING)
        self.started_at = utcnow()
        self.updated_at = utcnow()

    def report_progress(self, percent: float, *, stage: str | None = None) -> None:
        if not (0.0 <= percent <= 100.0):
            raise ValueError("progress_percent must be between 0 and 100.")
        if self.is_terminal:
            raise ValueError("Cannot report progress on a finished analysis run.")
        self.progress_percent = percent
        if stage is not None:
            self.stage_results[stage] = {"completed": True}
        self.updated_at = utcnow()

    def succeed(self, *, partial: bool = False) -> None:
        self.status = AnalysisRunStatus(
            AnalysisRunStatus.PARTIALLY_SUCCEEDED if partial else AnalysisRunStatus.SUCCEEDED
        )
        self.progress_percent = 100.0
        self.finished_at = utcnow()
        self.updated_at = utcnow()

    def fail(self, message: str) -> None:
        if not message.strip():
            raise ValueError("A failure message is required.")
        self.status = AnalysisRunStatus(AnalysisRunStatus.FAILED)
        self.error_message = message
        self.finished_at = utcnow()
        self.updated_at = utcnow()

    def cancel(self) -> None:
        if self.is_terminal:
            raise ValueError(f"Cannot cancel a finished analysis run ({self.status}).")
        self.status = AnalysisRunStatus(AnalysisRunStatus.CANCELLED)
        self.finished_at = utcnow()
        self.updated_at = utcnow()


def default_pipeline() -> AnalysisPipelineSpec:
    """The baseline processing pipeline.

    Named here as domain vocabulary so the API, workers and documentation refer
    to the same stages. Implementing the stages themselves belongs to ' 'ml/' '.
    """
    return AnalysisPipelineSpec(
        stages=("ingest", "detection", "tracking", "movement", "metrics"),
    )
