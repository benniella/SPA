"""Performance metrics: the numbers coaches actually read.

Heatmaps, movement summaries, workload/intensity profiles and team shape
descriptions all ultimately reduce to named metric records. Modelling them as
one typed entity — rather than as JSON blobs inside an analysis run — is what
makes them queryable, comparable across matches and safely versionable.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from app.domain.analysis.entities import AnalysisRunStatus
from app.domain.analysis.ids import HeatmapGridId, PerformanceMetricId
from app.domain.shared import (
    AnalysisRunId,
    MatchId,
    MetricValue,
    OrganizationId,
    Percentage,
    PitchCoordinate,
    PlayerId,
    TeamId,
    TrackingDatasetId,
    new_id,
    utcnow,
)


class MetricScope:
    """What a metric is attributed to.

    A constrained string so that new subjects (a unit, a possession interval) can
    be added without a database enum migration.
    """

    __slots__ = ("value",)

    PLAYER = "player"
    TEAM = "team"
    MATCH = "match"

    ALLOWED = frozenset({PLAYER, TEAM, MATCH})

    def __init__(self, value: str) -> None:
        if value not in self.ALLOWED:
            raise ValueError(f"Unknown metric scope: {value!r}.")
        self.value = value

    def __str__(self) -> str:
        return self.value

    def __repr__(self) -> str:
        return f"MetricScope({self.value!r})"

    def __eq__(self, other: object) -> bool:
        # Comparable with both the constrained type and the raw string, so
        # 'scope == MetricScope.MATCH' and 'scope == "match"' agree. Every
        # constrained-string type in the domain behaves this way.
        if isinstance(other, MetricScope):
            return self.value == other.value
        if isinstance(other, str):
            return self.value == other
        return NotImplemented

    def __hash__(self) -> int:
        return hash(self.value)


class MetricCategory:
    """The analytical family a metric belongs to.

    This is the vocabulary that keeps the metric model coherent and that the
    frontend uses to group results into views.
    """

    __slots__ = ("value",)

    MOVEMENT = "movement"
    WORKLOAD = "workload"
    INTENSITY = "intensity"
    TEAM_SHAPE = "team_shape"
    POSSESSION = "possession"
    PHYSICAL = "physical"

    ALLOWED = frozenset({MOVEMENT, WORKLOAD, INTENSITY, TEAM_SHAPE, POSSESSION, PHYSICAL})

    def __init__(self, value: str) -> None:
        if value not in self.ALLOWED:
            raise ValueError(f"Unknown metric category: {value!r}.")
        self.value = value

    def __str__(self) -> str:
        return self.value

    def __repr__(self) -> str:
        return f"MetricCategory({self.value!r})"

    def __eq__(self, other: object) -> bool:
        if isinstance(other, MetricCategory):
            return self.value == other.value
        if isinstance(other, str):
            return self.value == other
        return NotImplemented

    def __hash__(self) -> int:
        return hash(self.value)


@dataclass(slots=True)
class PerformanceMetric:
    """One measured value, attributed to a subject, derived from one run.

    Every metric is traceable back to the analysis run that produced it. Without
    that link, a metric that looks wrong cannot be investigated, and re-running
    a pipeline cannot be compared against the previous output.
    """

    organization_id: OrganizationId
    analysis_run_id: AnalysisRunId
    scope: MetricScope
    category: MetricCategory
    metric: MetricValue
    id: PerformanceMetricId = field(default_factory=lambda: PerformanceMetricId(new_id()))
    match_id: MatchId | None = None
    player_id: PlayerId | None = None
    team_id: TeamId | None = None
    #: Optional window the metric was computed over (e.g. first half).
    period_label: str | None = None
    created_at: datetime = field(default_factory=utcnow)

    def __post_init__(self) -> None:
        if self.scope.value == MetricScope.PLAYER and self.player_id is None:
            raise ValueError("A player-scoped metric requires a player_id.")
        if self.scope.value == MetricScope.TEAM and self.team_id is None:
            raise ValueError("A team-scoped metric requires a team_id.")

    @property
    def name(self) -> str:
        return self.metric.name

    @property
    def value(self) -> float:
        return self.metric.value


@dataclass(slots=True)
class HeatmapGrid:
    """A spatial density surface over the pitch.

    Modelled as a coarse grid rather than as a rendered image: the grid is the
    data, and the picture is a rendering concern for the frontend. Storing the
    grid keeps heatmaps comparable, re-stylable and small.
    """

    organization_id: OrganizationId
    analysis_run_id: AnalysisRunId
    tracking_dataset_id: TrackingDatasetId
    #: Number of cells along each pitch axis.
    rows: int
    cols: int
    #: Row-major density values, length == rows * cols.
    cells: list[float] = field(default_factory=list)
    id: HeatmapGridId = field(default_factory=lambda: HeatmapGridId(new_id()))
    match_id: MatchId | None = None
    player_id: PlayerId | None = None
    team_id: TeamId | None = None
    period_label: str | None = None
    #: Pitch extent the grid covers, in metres.
    pitch_extent: tuple[float, float, float, float] | None = None
    created_at: datetime = field(default_factory=utcnow)

    def __post_init__(self) -> None:
        if self.rows < 1 or self.cols < 1:
            raise ValueError("Heatmap grid dimensions must be positive.")
        if len(self.cells) != self.rows * self.cols:
            raise ValueError("Heatmap cells length must equal rows * cols.")

    def value_at(self, row: int, col: int) -> float:
        if not (0 <= row < self.rows and 0 <= col < self.cols):
            raise IndexError("Heatmap cell coordinates out of range.")
        return self.cells[row * self.cols + col]


@dataclass(frozen=True, slots=True)
class TeamShapeSample:
    """A team's shape at one instant.

    The derived quantities a coach cares about (width, depth, compactness,
    centroid) are computed here rather than stored as raw positions, so shape
    analysis is queryable without loading trajectories.
    """

    timestamp_seconds: float
    team_id: TeamId
    centroid: PitchCoordinate
    width_metres: float
    depth_metres: float
    compactness: float
    player_count: int

    def __post_init__(self) -> None:
        if self.timestamp_seconds < 0:
            raise ValueError("timestamp_seconds cannot be negative.")
        if self.player_count < 0:
            raise ValueError("player_count cannot be negative.")
        if self.width_metres < 0 or self.depth_metres < 0:
            raise ValueError("Team shape dimensions cannot be negative.")
        if not (0.0 <= self.compactness <= 1.0):
            raise ValueError("compactness must be between 0 and 1.")


@dataclass(frozen=True, slots=True)
class IntensityZoneBreakdown:
    """Time spent in each speed/intensity zone, as percentages.

    The zone thresholds are supplied by the caller: they are sport-, age- and
    even squad-specific, so hard-coding them in the domain would bake a
    coaching opinion into the schema.
    """

    thresholds: tuple[float, ...]
    share_by_zone: tuple[Percentage, ...]

    def __post_init__(self) -> None:
        # N speed thresholds partition the match into N+1 zones.
        if len(self.share_by_zone) != len(self.thresholds) + 1:
            raise ValueError(
                f"Expected {len(self.thresholds) + 1} zone shares for "
                f"{len(self.thresholds)} thresholds, got {len(self.share_by_zone)}."
            )
        if any(
            later <= earlier
            for earlier, later in zip(self.thresholds, self.thresholds[1:], strict=False)
        ):
            raise ValueError("Zone thresholds must be strictly ascending.")

    @property
    def total_share(self) -> float:
        """Sum of the zone shares.

        Not enforced to equal 100 in the constructor: rounding across zones is
        legitimate, and a hard invariant there would reject valid real data. The
        value is exposed so callers that need exactness can check it.
        """
        return sum(share.value for share in self.share_by_zone)


@dataclass(frozen=True, slots=True)
class AnalysisReadiness:
    """Whether an analysis run's output can be consumed yet.

    A small read model so the API can answer "is this match analysable?" without
    the route handler re-deriving pipeline semantics from status codes.
    """

    run_id: AnalysisRunId
    status: AnalysisRunStatus

    @property
    def has_usable_results(self) -> bool:
        return self.status.value in {
            AnalysisRunStatus.SUCCEEDED,
            AnalysisRunStatus.PARTIALLY_SUCCEEDED,
        }

    @property
    def is_in_flight(self) -> bool:
        return self.status.value in {
            AnalysisRunStatus.PENDING,
            AnalysisRunStatus.QUEUED,
            AnalysisRunStatus.RUNNING,
        }
