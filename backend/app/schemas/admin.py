"""Admin API request and response schemas."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import EmailStr, Field

from app.schemas.common import ApiModel, PageMeta


class AdministratorRead(ApiModel):
    id: uuid.UUID
    user_id: uuid.UUID
    email: str | None = Field(default=None, description="Absent when the account is gone.")
    status: str
    roles: list[str]
    privileges: list[str]
    mfa_enrolled: bool
    created_at: datetime
    updated_at: datetime


class AdministratorList(ApiModel):
    items: list[AdministratorRead]
    meta: PageMeta


class RoleList(ApiModel):
    items: list[str]


class PrivilegeList(ApiModel):
    items: list[str]


class RolesUpdate(ApiModel):
    roles: list[str] = Field(default_factory=list, description="The complete set to hold.")


class InvitationCreate(ApiModel):
    email: EmailStr
    role: str = Field(min_length=1, max_length=64)


class InvitationRead(ApiModel):
    id: uuid.UUID
    email: str
    role: str
    status: str
    invited_by: uuid.UUID | None
    expires_at: datetime
    accepted_at: datetime | None
    revoked_at: datetime | None
    created_at: datetime


class InvitationList(ApiModel):
    items: list[InvitationRead]
    meta: PageMeta


class InvitationToken(ApiModel):
    token: str = Field(min_length=16, max_length=512, description="From the invitation email.")


class InvitationAccepted(ApiModel):
    administrator_id: uuid.UUID
    status: str = Field(description="'invited': activation requires MFA enrollment.")


class MfaEnrollment(ApiModel):
    secret: str = Field(description="The shared secret, shown once during enrolment.")
    provisioning_uri: str = Field(description="otpauth URI for an authenticator app.")


class MfaCodeSubmit(ApiModel):
    code: str = Field(min_length=6, max_length=10)


class MfaRecoveryCodes(ApiModel):
    codes: list[str] = Field(description="Shown once; regenerating replaces these.")


class MfaChallengeStarted(ApiModel):
    expires_at: datetime
    max_attempts: int


class AuditEventRead(ApiModel):
    id: uuid.UUID
    actor_id: uuid.UUID | None
    event_type: str
    metadata: dict[str, object]
    created_at: datetime


class AuditEventList(ApiModel):
    items: list[AuditEventRead]
    meta: PageMeta
