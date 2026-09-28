from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Response, status
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.api.dependencies import SessionDep, SettingsDep
from app.schemas.common import HealthResponse

router = APIRouter()


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Liveness probe",
    description="Cheap check that the API process is up. Does not touch PostgreSQL.",
)
async def health(settings: SettingsDep) -> HealthResponse:
    return HealthResponse(
        status="ok",
        environment=settings.environment,
        database="not_checked",
        version="0.0.0",
        timestamp=datetime.now(UTC),
    )


@router.get(
    "/health/ready",
    response_model=HealthResponse,
    summary="Readiness probe",
    description="Verifies that the API can reach PostgreSQL.",
    responses={503: {"description": "A dependency is unavailable."}},
)
async def readiness(
    settings: SettingsDep,
    session: SessionDep,
    response: Response,
) -> HealthResponse:
    database = "connected"
    try:
        await session.execute(text("SELECT 1"))
    except SQLAlchemyError:
        database = "unavailable"
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    return HealthResponse(
        status="ok" if database == "connected" else "degraded",
        environment=settings.environment,
        database=database,
        version="0.0.0",
        timestamp=datetime.now(UTC),
    )
