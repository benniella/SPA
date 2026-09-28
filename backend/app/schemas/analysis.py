"""Analysis request/response schemas."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import Field

from app.schemas.common import ApiModel, PageMeta


class PipelineSpecSchema(ApiModel):
    """Declarative request for what the pipeline should compute."""

    stages: list[str] = Field(
        default_factory=list,
        description=(
            "Ordered stage identifiers. Empty means the server's default "
            "pipeline, so the client does not have to know the stage vocabulary."
        ),
        examples=[["ingest", "detection", "tracking", "movement", "metrics"]],
    )
    model_versions: dict[str, str] = Field(
        default_factory=dict,
        description="Pin a specific model version per stage, e.g. {'detection': 'v2'}.",
    )
    params: dict[str, object] = Field(
        default_factory=dict,
        description="Stage parameters such as frame sampling or period boundaries.",
    )


class AnalysisRunCreate(ApiModel):
    video_id: uuid.UUID
    organization_id: uuid.UUID
    pipeline: PipelineSpecSchema | None = Field(
        default=None,
        description="Omit to run the default pipeline.",
    )


class AnalysisRunRead(ApiModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    video_id: uuid.UUID
    match_id: uuid.UUID | None
    status: Literal[
        "pending",
        "queued",
        "running",
        "succeeded",
        "partially_succeeded",
        "failed",
        "cancelled",
    ]
    progress_percent: float = Field(ge=0, le=100)
    error_message: str | None
    started_at: datetime | None
    finished_at: datetime | None
    created_at: datetime
    updated_at: datetime


class AnalysisRunList(ApiModel):
    items: list[AnalysisRunRead]
    meta: PageMeta
