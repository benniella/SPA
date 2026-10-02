"""Report request/response schemas."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import Field

from app.schemas.common import ApiModel, PageMeta
from app.schemas.metrics import MetricNameLiteral, MetricSpaceLiteral, MetricUnitLiteral

ReportStatusLiteral = Literal["draft", "generating", "ready", "failed"]

ObservationTypeLiteral = Literal[
    "highest_observation_count",
    "highest_coverage",
    "highest_displacement",
    "highest_average_speed",
    "highest_peak_speed",
    "highest_peak_acceleration",
    "longest_duration",
]


class ReportRead(ApiModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    created_by_id: uuid.UUID | None
    title: str
    status: ReportStatusLiteral
    definition_version: str
    analysis_run_id: uuid.UUID | None
    match_id: uuid.UUID | None
    team_id: uuid.UUID | None
    storage_key: str | None
    error_message: str | None
    generated_at: datetime | None
    created_at: datetime
    updated_at: datetime


class ReportList(ApiModel):
    items: list[ReportRead]
    meta: PageMeta


class ReportOverviewRead(ApiModel):
    analysis_run_id: uuid.UUID
    analysis_status: str
    video_id: uuid.UUID
    video_filename: str
    match_id: uuid.UUID | None
    analysis_created_at: datetime
    analysis_finished_at: datetime | None
    source_width: int | None
    source_height: int | None
    observation_count: int = Field(ge=0)
    track_count: int = Field(ge=0)
    metric_definition_version: str
    space: MetricSpaceLiteral


class ReportMetricRead(ApiModel):
    name: MetricNameLiteral
    unit: MetricUnitLiteral
    availability: Literal["available", "unavailable"]
    value: float | None = None
    sample_count: int = Field(ge=0)


class ReportTrackRead(ApiModel):
    track_id: int = Field(ge=0)
    space: MetricSpaceLiteral
    metrics: list[ReportMetricRead]


class ReportObservationRead(ApiModel):
    type: ObservationTypeLiteral
    track_ids: list[int]
    metric_name: MetricNameLiteral
    unit: MetricUnitLiteral
    space: MetricSpaceLiteral
    value: float
    message: str


class ReportContentRead(ApiModel):
    definition_version: str
    overview: ReportOverviewRead
    tracks: list[ReportTrackRead]
    observations: list[ReportObservationRead]
    limitations: list[str]


class ReportDetailRead(ReportRead):
    """A report together with its snapshot body, when one has been generated."""

    content: ReportContentRead | None = None


class ReportExportRead(ApiModel):
    """A stored report export. The storage key is deliberately not exposed."""

    report_id: uuid.UUID
    filename: str
    content_type: str
    download_url: str
