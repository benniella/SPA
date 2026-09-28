"""Shared schema building blocks."""

from __future__ import annotations

from datetime import datetime
from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field

T = TypeVar("T")


class ApiModel(BaseModel):
    """Base for every schema in the public contract.

    ' 'from_attributes=True' ' lets a response model be built directly from a
    domain dataclass, which is how the API layer avoids hand-written conversion
    functions for every entity.
    """

    model_config = ConfigDict(from_attributes=True, extra="forbid")


class PageMeta(ApiModel):
    """Pagination metadata returned alongside every collection."""

    limit: int = Field(ge=1, le=200, description="Maximum number of items requested.")
    offset: int = Field(ge=0, description="Number of items skipped.")
    count: int = Field(ge=0, description="Number of items in this page.")


class Page(ApiModel, Generic[T]):
    """A page of results.

    ' 'items' ' and ' 'meta' ' rather than a bare array: adding a total count or a
    cursor later must not be a breaking change for the frontend.
    """

    items: list[T]
    meta: PageMeta


class HealthResponse(ApiModel):
    """Liveness/readiness payload."""

    status: str = Field(description="'ok' when the service is serving requests.")
    environment: str
    database: str = Field(description="'connected', 'unavailable', or 'not_checked'.")
    version: str = "0.0.0"
    timestamp: datetime


class ErrorBody(ApiModel):
    """Machine-readable error payload.

    ' 'code' ' is the stable contract; ' 'message' ' is for humans and may change.
    """

    code: str
    message: str
    details: dict[str, object] | None = None


class ErrorResponse(ApiModel):
    """The envelope wrapping every error the API returns."""

    error: ErrorBody


class IdResponse(ApiModel):
    """Minimal response for operations that only create or acknowledge."""

    id: str
    status: str
