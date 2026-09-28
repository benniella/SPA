"""Visualization response schemas.

The shapes mirror the domain visualization types. Coordinates are source-image
pixels throughout; 'space' is stated once on the response so a client cannot read
a pixel as a metre.
"""

from __future__ import annotations

import uuid
from typing import Literal

from pydantic import Field

from app.schemas.common import ApiModel
from app.schemas.metrics import AnalysisMetricsRead, MetricSpaceLiteral

VisualizationStatusLiteral = Literal[
    "pending",
    "queued",
    "running",
    "succeeded",
    "partially_succeeded",
    "failed",
    "cancelled",
]


class SourceFrameRead(ApiModel):
    """The source video frame's pixel dimensions, when they are known."""

    width: int | None = Field(default=None, ge=1)
    height: int | None = Field(default=None, ge=1)


class TrackPointRead(ApiModel):
    frame_index: int = Field(ge=0)
    timestamp_seconds: float = Field(ge=0)
    x: float
    y: float
    confidence: float = Field(ge=0, le=1)


class TrackPathRead(ApiModel):
    """One track's ordered trajectory, possibly downsampled for the response."""

    track_id: int = Field(ge=0)
    observation_count: int = Field(ge=0)
    downsampled: bool
    start_seconds: float = Field(ge=0)
    end_seconds: float = Field(ge=0)
    points: list[TrackPointRead]


class DensityGridRead(ApiModel):
    """Observation counts over a deterministic grid of the source frame.

    'counts' is row-major with 'columns' entries per row. 'max_count' is the
    largest cell, so a client can normalize without recomputing it.
    """

    columns: int = Field(ge=1)
    rows: int = Field(ge=1)
    counts: list[int]
    max_count: int = Field(ge=0)
    bounds: list[float] = Field(min_length=4, max_length=4)
    observation_count: int = Field(ge=0)
    track_count: int = Field(ge=0)


class ActivityBucketRead(ApiModel):
    index: int = Field(ge=0)
    start_seconds: float = Field(ge=0)
    end_seconds: float = Field(ge=0)
    observation_count: int = Field(ge=0)
    track_ids: list[int]


class ActivityTimelineRead(ApiModel):
    bucket_seconds: float = Field(gt=0)
    start_seconds: float = Field(ge=0)
    end_seconds: float = Field(ge=0)
    max_count: int = Field(ge=0)
    buckets: list[ActivityBucketRead]


class RunVisualizationRead(ApiModel):
    analysis_run_id: uuid.UUID
    organization_id: uuid.UUID
    status: VisualizationStatusLiteral
    space: MetricSpaceLiteral
    frame: SourceFrameRead
    observation_count: int = Field(ge=0)
    track_count: int = Field(ge=0)
    paths: list[TrackPathRead]
    density: DensityGridRead
    timeline: ActivityTimelineRead
    metrics: AnalysisMetricsRead
