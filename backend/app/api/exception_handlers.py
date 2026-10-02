from __future__ import annotations

import logging

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.application.admin_authz import (
    AdministratorMayNotAct,
    MfaNotSatisfied,
    MissingPrivilege,
    NotAnAdministrator,
)
from app.core.config import Settings
from app.core.errors import AppError

logger = logging.getLogger(__name__)


def _error_body(code: str, message: str, details: dict[str, object] | None = None) -> dict:
    payload: dict = {"code": code, "message": message}
    if details:
        payload["details"] = details
    return {"error": payload}


def register_exception_handlers(app: FastAPI, settings: Settings) -> None:
    @app.exception_handler(AppError)
    async def handle_app_error(_: Request, exc: AppError) -> JSONResponse:
        if exc.status_code >= 500:
            logger.exception("application error: %s", exc.code)
        return JSONResponse(
            status_code=exc.status_code,
            content=_error_body(exc.code, exc.message, exc.details),
        )

    @app.exception_handler(NotAnAdministrator)
    @app.exception_handler(AdministratorMayNotAct)
    @app.exception_handler(MissingPrivilege)
    async def handle_admin_authorization_error(_: Request, exc: Exception) -> JSONResponse:
        return JSONResponse(
            status_code=403,
            content=_error_body("permission_denied", str(exc)),
        )

    @app.exception_handler(MfaNotSatisfied)
    async def handle_mfa_not_satisfied(_: Request, exc: MfaNotSatisfied) -> JSONResponse:
        return JSONResponse(
            status_code=401,
            content=_error_body("authentication_required", str(exc)),
        )

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content=_error_body(
                "validation_error",
                "The request payload is invalid.",
                {"errors": _serialise_errors(exc)},
            ),
        )

    @app.exception_handler(StarletteHTTPException)
    async def handle_http_exception(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        code = {
            401: "authentication_required",
            403: "permission_denied",
            404: "not_found",
            405: "method_not_allowed",
        }.get(exc.status_code, "http_error")
        return JSONResponse(
            status_code=exc.status_code,
            content=_error_body(code, str(exc.detail)),
        )

    @app.exception_handler(SQLAlchemyError)
    async def handle_database_error(_: Request, exc: SQLAlchemyError) -> JSONResponse:
        logger.exception("database error")
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content=_error_body(
                "infrastructure_error",
                "The database is temporarily unavailable.",
            ),
        )

    @app.exception_handler(Exception)
    async def handle_unexpected(_: Request, exc: Exception) -> JSONResponse:
        logger.exception("unhandled exception")
        message = (
            f"{type(exc).__name__}: {exc}" if settings.is_local else "An unexpected error occurred."
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=_error_body("internal_error", message),
        )


def _serialise_errors(exc: RequestValidationError) -> list[dict[str, object]]:
    errors: list[dict[str, object]] = []
    for error in exc.errors():
        errors.append(
            {
                "location": [str(part) for part in error.get("loc", ())],
                "message": error.get("msg", ""),
                "type": error.get("type", ""),
            }
        )
    return errors
