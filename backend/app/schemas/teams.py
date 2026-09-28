"""Team request/response schemas."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import Field

from app.schemas.common import ApiModel, PageMeta
from app.schemas.organizations import SLUG_PATTERN


class TeamCreate(ApiModel):
    organization_id: uuid.UUID = Field(description="Owning organization.")
    name: str = Field(min_length=1, max_length=200)
    slug: str = Field(min_length=2, max_length=80, pattern=SLUG_PATTERN)
    sport: str = Field(default="football", min_length=1, max_length=64)
    season: str | None = Field(default=None, max_length=64)


class TeamRead(ApiModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    name: str
    slug: str
    sport: str
    season: str | None
    created_at: datetime
    updated_at: datetime


class TeamList(ApiModel):
    items: list[TeamRead]
    meta: PageMeta
