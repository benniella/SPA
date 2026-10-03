from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.application.use_cases import platform_configuration
from app.domain.configuration.settings import MAINTENANCE_ENABLED, MAINTENANCE_MESSAGE

MAINTENANCE_CODE = "maintenance"


def maintenance_exempt_path(path: str, api_prefix: str) -> bool:
    normalized = path.rstrip("/")
    if normalized in {f"{api_prefix}/health", f"{api_prefix}/health/ready"}:
        return True
    return normalized == f"{api_prefix}/admin" or normalized.startswith(f"{api_prefix}/admin/")


class MaintenanceMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: object, *, unit_of_work_factory: object, api_prefix: str) -> None:
        super().__init__(app)  # type: ignore[arg-type]
        self._unit_of_work_factory = unit_of_work_factory
        self._api_prefix = api_prefix

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        if request.method == "OPTIONS" or maintenance_exempt_path(
            request.url.path, self._api_prefix
        ):
            return await call_next(request)

        enabled, message = await self._read()
        if not enabled:
            return await call_next(request)

        return JSONResponse(
            status_code=503,
            headers={"Retry-After": "300"},
            content={
                "error": {
                    "code": MAINTENANCE_CODE,
                    "message": message.strip()
                    or "SPA is temporarily unavailable for maintenance.",
                }
            },
        )

    async def _read(self) -> tuple[bool, str]:
        try:
            unit_of_work = self._unit_of_work_factory()  # type: ignore[operator]
            async with unit_of_work as uow:
                configuration = await platform_configuration.read_effective_configuration(
                    settings=uow.platform_settings
                )
            return (
                configuration.bool(MAINTENANCE_ENABLED),
                configuration.string(MAINTENANCE_MESSAGE),
            )
        except Exception:
            return False, ""
