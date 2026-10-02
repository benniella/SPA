"""Authentication and account-security request/response schemas.

No response model carries a raw session token, verification token, reset token or
OTP: tokens travel in the cookie or in a delivered message, never in a JSON body
the frontend might persist.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import EmailStr, Field

from app.schemas.common import ApiModel, PageMeta


class RegisterRequest(ApiModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=1024)
    display_name: str = Field(min_length=1, max_length=200)
    organization_name: str = Field(min_length=1, max_length=200)
    organization_slug: str = Field(min_length=2, max_length=80)


class LoginRequest(ApiModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=1024)


class TokenRequest(ApiModel):
    """A request carrying a challenge token from a delivered link."""

    token: str = Field(min_length=1, max_length=512)


class EmailRequest(ApiModel):
    email: EmailStr


class PasswordChangeRequest(ApiModel):
    current_password: str = Field(min_length=1, max_length=1024)
    new_password: str = Field(min_length=1, max_length=1024)


class PasswordResetRequest(ApiModel):
    token: str = Field(min_length=1, max_length=512)
    new_password: str = Field(min_length=1, max_length=1024)


class EmailChangeRequest(ApiModel):
    new_email: EmailStr
    current_password: str = Field(min_length=1, max_length=1024)


class PhoneRequest(ApiModel):
    phone_number: str = Field(min_length=6, max_length=32)


class PhoneVerifyRequest(ApiModel):
    code: str = Field(min_length=4, max_length=12)


class RecoveryStartRequest(ApiModel):
    email: EmailStr


class RecoveryCompleteRequest(ApiModel):
    email: EmailStr
    code: str = Field(min_length=4, max_length=12)
    new_password: str = Field(min_length=1, max_length=1024)


class OrganizationSummary(ApiModel):
    id: uuid.UUID
    name: str
    slug: str
    role: str


class AuthenticatedUser(ApiModel):
    id: uuid.UUID
    email: str
    display_name: str
    account_status: str
    email_verified: bool
    phone_verified: bool
    phone_number: str | None = None
    created_at: datetime
    last_login_at: datetime | None = None
    organizations: list[OrganizationSummary] = Field(default_factory=list)


class RegistrationAccepted(ApiModel):
    """The registration outcome.

    Identical for a new address and one already registered, so the endpoint
    cannot be used to discover which addresses have accounts.
    """

    status: str = "verification_required"
    verification_required: bool = True


class MessageAccepted(ApiModel):
    """A response that deliberately says only that the request was handled."""

    status: str = "accepted"


class SessionSummary(ApiModel):
    id: uuid.UUID
    created_at: datetime
    last_used_at: datetime
    expires_at: datetime
    revoked: bool
    current: bool
    description: str
    network: str | None = None


class SessionList(ApiModel):
    items: list[SessionSummary]
    meta: PageMeta


class SecurityEventRead(ApiModel):
    id: uuid.UUID
    event_type: str
    created_at: datetime
    description: str


class SecurityEventList(ApiModel):
    items: list[SecurityEventRead]
    meta: PageMeta
