"""Reports: the shareable, snapshot output of an analysis.

A report captures an immutable snapshot rather than referencing live metrics,
so a report downloaded last season does not change when models are re-run.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from app.domain.shared import (
    AnalysisRunId,
    MatchId,
    OrganizationId,
    ReportId,
    TeamId,
    new_id,
    utcnow,
)
from app.domain.users.entities import UserId


class ReportStatus:
    """Generation state of a report artefact."""

    __slots__ = ("value",)

    DRAFT = "draft"
    GENERATING = "generating"
    READY = "ready"
    FAILED = "failed"

    ALLOWED = frozenset({DRAFT, GENERATING, READY, FAILED})

    def __init__(self, value: str) -> None:
        if value not in self.ALLOWED:
            raise ValueError(f"Unknown report status: {value!r}.")
        self.value = value

    def __str__(self) -> str:
        return self.value

    def __repr__(self) -> str:
        return f"ReportStatus({self.value!r})"

    def __eq__(self, other: object) -> bool:
        if isinstance(other, ReportStatus):
            return self.value == other.value
        if isinstance(other, str):
            return self.value == other
        return NotImplemented

    def __hash__(self) -> int:
        return hash(self.value)


@dataclass(frozen=True, slots=True)
class ReportScope:
    """Which data a report covers.

    Optional identifiers are used instead of a polymorphic ' 'subject_type' ' +
    ' 'subject_id' ' pair so that referential integrity is enforced by PostgreSQL
    rather than by application code.
    """

    match_id: MatchId | None = None
    team_id: TeamId | None = None
    analysis_run_ids: tuple[AnalysisRunId, ...] = ()

    def __post_init__(self) -> None:
        if self.match_id is None and self.team_id is None and not self.analysis_run_ids:
            raise ValueError("A report scope must reference a match, a team or analysis runs.")

    @property
    def analysis_run_id(self) -> AnalysisRunId | None:
        """The single run a run-scoped report covers, or None for other scopes."""
        return self.analysis_run_ids[0] if len(self.analysis_run_ids) == 1 else None


@dataclass(slots=True)
class Report:
    """A generated report document.

    ' 'content' ' holds a denormalised snapshot of the numbers rendered into the
    report. It is JSONB because a report's internal shape is presentation data
    that will change faster than a relational schema can follow — but it is a
    *snapshot*, never the source of truth for performance metrics.
    """

    organization_id: OrganizationId
    title: str
    scope: ReportScope
    id: ReportId = field(default_factory=lambda: ReportId(new_id()))
    created_by_id: UserId | None = None
    status: ReportStatus = field(default_factory=lambda: ReportStatus(ReportStatus.DRAFT))
    content: dict[str, object] = field(default_factory=dict)
    definition_version: str = "v1"
    storage_key: str | None = None
    error_message: str | None = None
    generated_at: datetime | None = None
    created_at: datetime = field(default_factory=utcnow)
    updated_at: datetime = field(default_factory=utcnow)

    def __post_init__(self) -> None:
        if not self.title.strip():
            raise ValueError("Report title must not be empty.")
        if not self.definition_version.strip():
            raise ValueError("A report must declare its definition version.")

    @property
    def analysis_run_id(self) -> AnalysisRunId | None:
        return self.scope.analysis_run_id

    def is_ready_snapshot(self) -> bool:
        """Whether this report is a finished snapshot rather than still in flight.

        The distinction the read path acts on: a ready report's content is frozen
        and must not be re-derived, while an unfinished one has no content yet.
        """
        return self.status.value == ReportStatus.READY and self.generated_at is not None

    def mark_generating(self) -> None:
        if self.status.value not in {ReportStatus.DRAFT, ReportStatus.FAILED}:
            raise ValueError(f"Cannot start generating a {self.status} report.")
        self.status = ReportStatus(ReportStatus.GENERATING)
        self.updated_at = utcnow()

    def mark_ready(self, *, storage_key: str | None = None) -> None:
        self.status = ReportStatus(ReportStatus.READY)
        if storage_key is not None:
            self.storage_key = storage_key
        self.generated_at = utcnow()
        self.error_message = None
        self.updated_at = utcnow()

    def mark_failed(self, message: str) -> None:
        if not message.strip():
            raise ValueError("A failure message is required.")
        self.status = ReportStatus(ReportStatus.FAILED)
        self.error_message = message
        self.updated_at = utcnow()
