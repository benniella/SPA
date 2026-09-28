"""Derived metric schemas.

Every value carries its unit and its coordinate space, and an unavailable metric
is reported as such rather than as a zero. A client can therefore never render
'0 pixels/second' where the truth is 'this track was too short to measure'.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import Field

from app.schemas.common import ApiModel

MetricNameLiteral = Literal[
    "observation_count",
    "duration",
    "coverage",
    "displacement",
    "average_speed",
    "peak_speed",
    "average_acceleration",
    "peak_acceleration",
    "mean_confidence",
    "min_confidence",
    "max_confidence",
]

MetricUnitLiteral = Literal[
    "count",
    "seconds",
    "pixels",
    "pixels_per_second",
    "pixels_per_second_squared",
]

MetricSpaceLiteral = Literal["source", "calibrated"]

ProcessingJobStatusLiteral = Literal["queued", "running", "completed", "failed"]


class MetricValueRead(ApiModel):
    """One derived metric.

    'value' is null when 'availability' is 'unavailable', which is a different
    statement from a metric whose value is genuinely zero.
    """

    name: MetricNameLiteral
    unit: MetricUnitLiteral
    space: MetricSpaceLiteral
    availability: Literal["available", "unavailable"]
    value: float | None = None
    sample_count: int = Field(ge=0)


class TrackMetricsRead(ApiModel):
    track_id: int = Field(ge=0)
    space: MetricSpaceLiteral
    metrics: list[MetricValueRead]


class AnalysisMetricsRead(ApiModel):
    analysis_run_id: uuid.UUID
    organization_id: uuid.UUID
    space: MetricSpaceLiteral
    definition_version: str
    track_count: int = Field(ge=0)
    tracks: list[TrackMetricsRead]
    generated_at: datetime


class MetricsCalculationRead(ApiModel):
    """The job queued to calculate a run's metrics."""

    analysis_run_id: uuid.UUID
    job_id: uuid.UUID
    status: ProcessingJobStatusLiteral
    progress: float = Field(ge=0, le=100)
