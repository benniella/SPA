"""Player request/response schemas."""

from __future__ import annotations

import uuid
from datetime import date, datetime

from pydantic import Field

from app.schemas.common import ApiModel, PageMeta


class PlayerCreate(ApiModel):
    organization_id: uuid.UUID
    display_name: str = Field(min_length=1, max_length=200)
    date_of_birth: date | None = None
    external_ref: str | None = Field(
        default=None,
        max_length=128,
        description="Identifier in an external squad-management system.",
    )


class PlayerRead(ApiModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    display_name: str
    date_of_birth: date | None
    external_ref: str | None
    created_at: datetime
    updated_at: datetime


class PlayerList(ApiModel):
    items: list[PlayerRead]
    meta: PageMeta
