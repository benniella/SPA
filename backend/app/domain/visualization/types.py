"""Visualization primitives derived from persisted tracking observations.

Everything here is pure and deterministic: the same observations always produce
the same paths, the same grid and the same activity buckets. Coordinates are
source-image pixels, never a physical space, so a rendered position is exactly
the position the tracker recorded.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.domain.metrics.types import TrackObservationPoint


@dataclass(frozen=True, slots=True)
class SourceFrame:
    """The pixel dimensions of the source video frame.

    Both values are optional: a run can have observations without a recorded
    video resolution, in which case the visualization scales to the observed
    coordinate bounds instead of claiming a frame size it does not know.
    """

    width: int | None = None
    height: int | None = None

    @property
    def is_known(self) -> bool:
        return self.width is not None and self.height is not None


@dataclass(frozen=True, slots=True)
class TrackPoint:
    """One observation rendered as a point in source-image pixel space."""

    frame_index: int
    timestamp_seconds: float
    x: float
    y: float
    confidence: float


@dataclass(frozen=True, slots=True)
class TrackPath:
    """One track's ordered trajectory through source-video space.

    'observation_count' is the track's true observation total; 'points' may hold
    fewer entries when the path was downsampled for the response.
    """

    track_id: int
    points: tuple[TrackPoint, ...]
    observation_count: int

    @property
    def downsampled(self) -> bool:
        return self.observation_count > len(self.points)

    @property
    def start_seconds(self) -> float:
        return self.points[0].timestamp_seconds

    @property
    def end_seconds(self) -> float:
        return self.points[-1].timestamp_seconds


@dataclass(frozen=True, slots=True)
class DensityGrid:
    """Observation counts over a deterministic grid of the source frame.

    'counts' is row-major with 'columns' entries per row. 'max_count' is the
    largest cell so a renderer can normalize without recomputing the maximum.
    """

    columns: int
    rows: int
    counts: tuple[int, ...]
    max_count: int
    bounds: tuple[float, float, float, float]
    observation_count: int
    track_count: int

    def intensity(self, index: int) -> float:
        if self.max_count <= 0:
            return 0.0
        return self.counts[index] / self.max_count


@dataclass(frozen=True, slots=True)
class ActivityBucket:
    """The number of observations that fall in one interval of the run."""

    index: int
    start_seconds: float
    end_seconds: float
    observation_count: int
    track_ids: tuple[int, ...]


@dataclass(frozen=True, slots=True)
class ActivityTimeline:
    """Observation activity over the run's time span, in equal buckets."""

    bucket_seconds: float
    start_seconds: float
    end_seconds: float
    buckets: tuple[ActivityBucket, ...]

    @property
    def max_count(self) -> int:
        return max((bucket.observation_count for bucket in self.buckets), default=0)


def canonical_points(
    observations: tuple[TrackObservationPoint, ...] | list[TrackObservationPoint],
) -> list[TrackObservationPoint]:
    """Order observations deterministically by frame, then timestamp.

    The same ordering the metrics engine uses, so a path and the metrics derived
    from it describe the observations in the same sequence.
    """
    return sorted(observations, key=lambda point: (point.frame_index, point.timestamp_seconds))


def build_track_paths(
    observations: list[TrackObservationPoint],
    *,
    track_ids: frozenset[int] | None = None,
    max_points_per_track: int,
) -> tuple[TrackPath, ...]:
    """Group observations into ordered per-track paths, bounded per track.

    A track with more observations than 'max_points_per_track' is downsampled by
    taking every Nth point in canonical order, always keeping the first and last
    so the path's extent is preserved. The transformation is a pure function of
    the track's length, so the same data always yields the same path.
    """
    if max_points_per_track < 2:
        raise ValueError("max_points_per_track must be at least 2.")

    grouped: dict[int, list[TrackObservationPoint]] = {}
    for point in observations:
        if track_ids is not None and point.track_id not in track_ids:
            continue
        grouped.setdefault(point.track_id, []).append(point)

    return tuple(
        TrackPath(
            track_id=track_id,
            points=tuple(_to_points(kept)),
            observation_count=len(points),
        )
        for track_id, points in sorted(grouped.items())
        for kept in (_thin(points, max_points_per_track),)
    )


def build_density_grid(
    observations: list[TrackObservationPoint],
    *,
    columns: int,
    rows: int,
    track_ids: frozenset[int] | None = None,
    bounds: tuple[float, float, float, float] | None = None,
) -> DensityGrid:
    """Bin observations into a 'columns' x 'rows' grid over the source frame.

    The grid spans the source frame when its dimensions are known and the
    observed coordinate bounds otherwise. A position on the far edge belongs to
    the final cell rather than falling outside the grid, which is what keeps a
    point at x == width counted.
    """
    if columns < 1 or rows < 1:
        raise ValueError("A density grid requires at least one column and one row.")

    selected = [point for point in observations if track_ids is None or point.track_id in track_ids]
    left, top, right, bottom = bounds if bounds is not None else coordinate_bounds(selected)

    span_x = right - left
    span_y = bottom - top

    counts = [0] * (columns * rows)
    for point in selected:
        column = _cell(point.center_x, left, span_x, columns)
        row = _cell(point.center_y, top, span_y, rows)
        counts[row * columns + column] += 1

    return DensityGrid(
        columns=columns,
        rows=rows,
        counts=tuple(counts),
        max_count=max(counts, default=0),
        bounds=(left, top, right, bottom),
        observation_count=len(selected),
        track_count=len({point.track_id for point in selected}),
    )


def build_activity_timeline(
    observations: list[TrackObservationPoint],
    *,
    bucket_seconds: float,
) -> ActivityTimeline:
    """Bucket observations over the run's time span, so activity has a shape."""
    if bucket_seconds <= 0:
        raise ValueError("bucket_seconds must be positive.")

    if not observations:
        return ActivityTimeline(
            bucket_seconds=bucket_seconds,
            start_seconds=0.0,
            end_seconds=0.0,
            buckets=(),
        )

    start = min(point.timestamp_seconds for point in observations)
    end = max(point.timestamp_seconds for point in observations)
    bucket_count = max(1, int((end - start) / bucket_seconds) + 1)

    counts = [0] * bucket_count
    tracks: list[set[int]] = [set() for _ in range(bucket_count)]
    for point in observations:
        index = min(bucket_count - 1, int((point.timestamp_seconds - start) / bucket_seconds))
        counts[index] += 1
        tracks[index].add(point.track_id)

    buckets = tuple(
        ActivityBucket(
            index=index,
            start_seconds=start + index * bucket_seconds,
            end_seconds=start + (index + 1) * bucket_seconds,
            observation_count=counts[index],
            track_ids=tuple(sorted(tracks[index])),
        )
        for index in range(bucket_count)
    )

    return ActivityTimeline(
        bucket_seconds=bucket_seconds,
        start_seconds=start,
        end_seconds=end,
        buckets=buckets,
    )


def coordinate_bounds(
    observations: list[TrackObservationPoint],
) -> tuple[float, float, float, float]:
    """The observed (left, top, right, bottom) extent, in source pixels.

    A single observation or an empty set yields a one-pixel span so the grid and
    the renderer never divide by zero.
    """
    if not observations:
        return (0.0, 0.0, 1.0, 1.0)

    xs = [point.center_x for point in observations]
    ys = [point.center_y for point in observations]
    left, right = min(xs), max(xs)
    top, bottom = min(ys), max(ys)
    return (left, top, right if right > left else left + 1.0, bottom if bottom > top else top + 1.0)


def _cell(value: float, origin: float, span: float, cells: int) -> int:
    if span <= 0:
        return 0
    index = int((value - origin) / span * cells)
    return max(0, min(cells - 1, index))


def _to_points(points: list[TrackObservationPoint]) -> list[TrackPoint]:
    return [
        TrackPoint(
            frame_index=point.frame_index,
            timestamp_seconds=point.timestamp_seconds,
            x=point.center_x,
            y=point.center_y,
            confidence=point.confidence,
        )
        for point in points
    ]


def _thin(points: list[TrackObservationPoint], limit: int) -> list[TrackObservationPoint]:
    ordered = canonical_points(points)
    if len(ordered) <= limit:
        return ordered

    stride = len(ordered) / (limit - 1)
    kept = [ordered[int(index * stride)] for index in range(limit - 1)]
    kept.append(ordered[-1])
    return kept
