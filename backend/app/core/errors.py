"""Application-wide exceptions and the problems they map to.

Every expected failure is an 'AppError' subclass; 'app.api.exception_handlers'
is the only place that knows about status codes.
"""

from __future__ import annotations

from typing import Any


class AppError(Exception):
    """Base class for all expected, client-facing application failures.

    Attributes:
        code: Stable machine-readable identifier. The frontend switches on this,
            never on the human-readable message.
        message: Developer-facing description. Safe to expose for 4xx errors.
        status_code: HTTP status the API layer should return.
        details: Optional structured context (e.g. field errors).
    """

    code: str = "internal_error"
    status_code: int = 500

    def __init__(
        self,
        message: str | None = None,
        *,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message or self.__class__.__doc__ or self.code)
        self.message = message or self.__class__.__name__
        self.details = details or {}

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {"code": self.code, "message": self.message}
        if self.details:
            payload["details"] = self.details
        return payload


class ValidationError(AppError):
    """The request payload or parameters are invalid."""

    code = "validation_error"
    status_code = 422


class NotFoundError(AppError):
    """The requested resource does not exist in the caller's workspace."""

    code = "not_found"
    status_code = 404


class ConflictError(AppError):
    """The request conflicts with the current state of the resource."""

    code = "conflict"
    status_code = 409


class InvalidStateError(AppError):
    """An operation was attempted against a resource in the wrong state.

    Distinct from :class:'ConflictError' so the frontend can tell "you raced
    another writer" apart from "you skipped a step in the lifecycle".
    """

    code = "invalid_state"
    status_code = 409


class PermissionDeniedError(AppError):
    """The caller is authenticated but not allowed to perform this action."""

    code = "permission_denied"
    status_code = 403


class AuthenticationError(AppError):
    """The caller is not authenticated."""

    code = "authentication_required"
    status_code = 401


class SessionExpiredError(AuthenticationError):
    """The presented session is expired or revoked.

    Distinct from a missing credential so the frontend can tell "sign in" apart
    from "your session ended", which is what lets it explain the redirect instead
    of appearing to have lost the user's work.
    """

    code = "session_expired"


class AccountNotActiveError(AppError):
    """The account exists but may not authenticate right now.

    Deliberately vague in the response body: whether an account is suspended or
    deactivated is useful to its owner in the account page and not to an
    unauthenticated caller who guessed the password.
    """

    code = "account_not_active"
    status_code = 403


class EmailDeliveryError(AppError):
    """A message could not be handed to a provider."""

    code = "email_delivery_failed"
    status_code = 503


class RateLimitedError(AppError):
    """Too many attempts. The caller should retry after the stated delay."""

    code = "rate_limited"
    status_code = 429

    def __init__(
        self,
        message: str | None = None,
        *,
        details: dict[str, Any] | None = None,
        retry_after_seconds: int | None = None,
    ) -> None:
        payload = dict(details or {})
        if retry_after_seconds is not None:
            payload["retry_after_seconds"] = retry_after_seconds
            self.retry_after_seconds = retry_after_seconds
        super().__init__(message, details=payload)

    retry_after_seconds: int | None = None


class UnsupportedMediaError(AppError):
    """The uploaded media is of an unsupported type or is unreadable."""

    code = "unsupported_media"
    status_code = 415


class InfrastructureError(AppError):
    """A dependency (database, object storage, queue) failed."""

    code = "infrastructure_error"
    status_code = 503


class ConfigurationError(AppError):
    """The application is misconfigured and cannot serve this request.

    A deployment problem rather than a user error: the message is safe to log
    but is not echoed to the client in production.
    """

    code = "configuration_error"
    status_code = 500


class ProcessingFailedError(AppError):
    """An asynchronous analysis job terminated in a failed state."""

    code = "processing_failed"
    status_code = 500
