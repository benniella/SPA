"""User request/response schemas.

No password field exists: credentials are an unresolved design decision, and a
half-designed one in the contract would be worse than leaving it out.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import EmailStr, Field

from app.schemas.common import ApiModel, PageMeta


class UserCreate(ApiModel):
    email: EmailStr
    display_name: str = Field(min_length=1, max_length=200)


class UserRead(ApiModel):
    id: uuid.UUID
    email: str
    display_name: str
    is_active: bool
    created_at: datetime
    updated_at: datetime


class UserList(ApiModel):
    items: list[UserRead]
    meta: PageMeta


class UserUpdate(ApiModel):
    display_name: str = Field(min_length=1, max_length=200)
