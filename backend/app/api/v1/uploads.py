from __future__ import annotations

import logging

from fastapi import APIRouter, Request, Response, status
from fastapi.responses import FileResponse

from app.api.dependencies import SettingsDep, VideoStorageDep
from app.core.errors import ConfigurationError, NotFoundError, UnsupportedMediaError
from app.infrastructure.storage.local import LocalVideoStorage

logger = logging.getLogger(__name__)
router = APIRouter()

_CHUNK_SIZE = 1024 * 1024

ALLOWED_CONTENT_TYPES = frozenset(
    {
        "video/mp4",
        "video/quicktime",
        "video/x-matroska",
        "video/webm",
        "application/octet-stream",  # some clients do not set a type
    }
)


@router.put(
    "/{key:path}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Receive an uploaded object (local storage only)",
    description=(
        "Backing endpoint for presigned upload URLs when 'STORAGE_BACKEND=local'. "
        "Streams the request body straight to disk."
    ),
)
async def upload_object(
    key: str,
    request: Request,
    settings: SettingsDep,
    storage: VideoStorageDep,
) -> Response:
    if settings.storage_backend != "local":
        raise ConfigurationError("Direct uploads are only accepted in local storage mode.")
    if not isinstance(storage, LocalVideoStorage):  # pragma: no cover - defensive
        raise ConfigurationError("Storage adapter does not support local uploads.")

    content_type = (request.headers.get("content-type") or "").split(";")[0].strip()
    if content_type and content_type not in ALLOWED_CONTENT_TYPES:
        raise UnsupportedMediaError(
            f"Unsupported content type: {content_type}.",
            details={"allowed": sorted(ALLOWED_CONTENT_TYPES)},
        )

    declared_length = request.headers.get("content-length")
    if declared_length and int(declared_length) > settings.max_upload_bytes:
        raise UnsupportedMediaError(
            "Upload exceeds the configured maximum size.",
            details={"max_upload_bytes": settings.max_upload_bytes},
        )

    written = 0
    destination = storage.open_for_write(key)
    try:
        with destination.open("wb") as handle:
            async for chunk in request.stream():
                written += len(chunk)
                if written > settings.max_upload_bytes:
                    raise UnsupportedMediaError(
                        "Upload exceeds the configured maximum size.",
                        details={"max_upload_bytes": settings.max_upload_bytes},
                    )
                handle.write(chunk)
    except Exception:
        # A partial object in storage would look like a valid upload to the
        # 'complete' endpoint, so it is removed on failure.
        destination.unlink(missing_ok=True)
        raise

    logger.info("stored upload bytes=%s key=%s", written, key)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    "/{key:path}",
    summary="Download an object (local storage only)",
    description="Backing endpoint for presigned download URLs when 'STORAGE_BACKEND=local'.",
)
async def download_object(
    key: str,
    settings: SettingsDep,
    storage: VideoStorageDep,
) -> Response:
    if settings.storage_backend != "local":
        raise ConfigurationError("Direct downloads are only served in local storage mode.")
    if not isinstance(storage, LocalVideoStorage):  # pragma: no cover - defensive
        raise ConfigurationError("Storage adapter does not support local downloads.")

    stored = await storage.stat(key)
    if stored is None:
        raise NotFoundError("No object exists at this key.")

    return FileResponse(
        path=storage.path_for(key),
        media_type="application/octet-stream",
        filename=key.rsplit("/", 1)[-1],
    )
