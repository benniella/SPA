"""Organization request/response schemas."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import Field

from app.schemas.common import ApiModel, PageMeta

SLUG_PATTERN = r"^[a-z0-9]+(?:-[a-z0-9]+)*$"


class OrganizationCreate(ApiModel):
    name: str = Field(min_length=1, max_length=200)
    slug: str = Field(
        min_length=2,
        max_length=80,
        pattern=SLUG_PATTERN,
        description="URL-safe identifier, lowercase with single hyphens.",
        examples=["acme-fc"],
    )


class OrganizationRead(ApiModel):
    id: uuid.UUID
    name: str
    slug: str
    created_at: datetime
    updated_at: datetime


class OrganizationList(ApiModel):
    items: list[OrganizationRead]
    meta: PageMeta
