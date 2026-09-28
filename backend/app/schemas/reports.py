"""Report request/response schemas."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import Field, model_validator

from app.schemas.common import ApiModel, PageMeta


class ReportCreate(ApiModel):
    organization_id: uuid.UUID
    title: str = Field(min_length=1, max_length=300)
    match_id: uuid.UUID | None = None
    team_id: uuid.UUID | None = None
    analysis_run_ids: list[uuid.UUID] = Field(default_factory=list)

    @model_validator(mode="after")
    def _scope_present(self) -> ReportCreate:
        if self.match_id is None and self.team_id is None and not self.analysis_run_ids:
            raise ValueError("Provide match_id, team_id or analysis_run_ids.")
        return self


class ReportRead(ApiModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    created_by_id: uuid.UUID | None
    title: str
    status: Literal["draft", "generating", "ready", "failed"]
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
