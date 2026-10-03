"""Administrative platform-configuration and security-control schemas."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import Field, field_validator

from app.schemas.common import ApiModel, PageMeta


class SettingRead(ApiModel):
    key: str
    type: str
    section: str
    value: object
    default: object
    description: str
    is_default: bool
    restart_required: bool
    privilege: str


class SettingList(ApiModel):
    items: list[SettingRead]


class SettingUpdate(ApiModel):
    value: object
    reason: str | None = Field(default=None, max_length=500)


class MaintenanceStatus(ApiModel):
    enabled: bool
    message: str
    affects_public: bool = True


class CountryPolicyRead(ApiModel):
    mode: str
    allowlist: list[str]
    denylist: list[str]


class CountryPolicyUpdate(ApiModel):
    mode: str = Field(description="One of 'off', 'allowlist' or 'denylist'.")
    allowlist: list[str] | None = None
    denylist: list[str] | None = None


class IpBlockCreate(ApiModel):
    network: str = Field(min_length=1, max_length=64, description="An address or CIDR.")
    kind: str = Field(description="'temporary' or 'permanent'.")
    reason: str = Field(min_length=1, max_length=300)
    expires_at: datetime | None = None

    @field_validator("reason")
    @classmethod
    def _reason_not_blank(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("reason must not be blank.")
        return stripped


class IpBlockRead(ApiModel):
    id: uuid.UUID
    network: str
    kind: str
    reason: str
    created_by: uuid.UUID | None
    expires_at: datetime | None
    removed_at: datetime | None
    active: bool
    created_at: datetime


class IpBlockList(ApiModel):
    items: list[IpBlockRead]
    meta: PageMeta


class RateLimitResetRequest(ApiModel):
    scope: str = Field(min_length=1, max_length=64)
    identifier: str = Field(min_length=1, max_length=320)


class RateLimitResetResult(ApiModel):
    scope: str
    identifier: str


class RateLimitStateRead(ApiModel):
    scope: str
    identifier: str
    count: int | None


class SuspiciousIpPolicyRead(ApiModel):
    enabled: bool
    failure_threshold: int
    window_minutes: int
