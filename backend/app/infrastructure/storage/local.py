"""Local-filesystem implementation of the video storage port.

Implements the same presign-based contract as the future S3 adapter, so
switching 'STORAGE_BACKEND' changes no application code. With this adapter the
presigned URLs point at the API's own upload/download endpoints.
"""

from __future__ import annotations

import hashlib
import mimetypes
import shutil
from datetime import UTC, datetime
from pathlib import Path
from typing import IO
from urllib.parse import quote

from app.application.ports.video_storage import StoredObject
from app.core.config import Settings
from app.infrastructure.storage.keys import build_storage_key


class LocalVideoStorage:
    """Stores objects as files under ' 'STORAGE_LOCAL_ROOT' '."""

    def __init__(self, settings: Settings, *, api_base_url: str = "http://localhost:8000") -> None:
        self._root = Path(settings.storage_local_root).resolve()
        self._api_base_url = api_base_url.rstrip("/")
        self._root.mkdir(parents=True, exist_ok=True)

    def build_key(
        self, organization_id: str, *, category: str, owner_id: str, filename: str
    ) -> str:
        return build_storage_key(
            organization_id, category=category, owner_id=owner_id, filename=filename
        )

    def _resolve(self, key: str) -> Path:
        """Resolve a key to a path, refusing to escape the storage root.

        A storage key is attacker-influenced (it derives from a filename), so
        path traversal must be rejected here rather than trusted upstream.
        """
        candidate = (self._root / key).resolve()
        if not candidate.is_relative_to(self._root):
            raise ValueError("Storage key escapes the configured storage root.")
        return candidate

    async def presign_upload(
        self,
        key: str,
        *,
        content_type: str | None = None,
        expires_in: int = 3600,
    ) -> str:
        return f"{self._api_base_url}/api/v1/uploads/{quote(key)}"

    async def presign_download(self, key: str, *, expires_in: int = 3600) -> str:
        return f"{self._api_base_url}/api/v1/uploads/{quote(key)}"

    async def stat(self, key: str) -> StoredObject | None:
        path = self._resolve(key)
        if not path.is_file():
            return None
        stat_result = path.stat()
        return StoredObject(
            key=key,
            size_bytes=stat_result.st_size,
            content_type=_guess_content_type(path),
            etag=_checksum(path),
            last_modified=datetime.fromtimestamp(stat_result.st_mtime, tz=UTC),
        )

    async def delete(self, key: str) -> None:
        path = self._resolve(key)
        path.unlink(missing_ok=True)

    async def open(self, key: str) -> bytes:
        return self._resolve(key).read_bytes()

    async def write_bytes(self, key: str, payload: bytes) -> None:
        path = self._resolve(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(payload)

    def open_for_write(self, key: str) -> Path:
        """Return a path to write an uploaded object to."""
        path = self._resolve(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        return path

    def path_for(self, key: str) -> Path:
        """Return the filesystem path of an existing object, creating no directory."""
        return self._resolve(key)

    def write_stream(self, key: str, source: IO[bytes]) -> int:
        """Copy a readable byte stream to disk, returning the bytes written.

        Used by the local upload endpoint (an alternative to S3 direct upload).
        Streamed in shutil's default chunks so a multi-gigabyte upload never
        lands in memory.
        """
        destination = self.open_for_write(key)
        with destination.open("wb") as handle:
            shutil.copyfileobj(source, handle)
        return destination.stat().st_size


def _guess_content_type(path: Path) -> str | None:
    """Infer a media type from the stored extension.

    Used so the completion check can compare what the client declared against
    what was actually stored; a filesystem has no content type of its own.
    """
    guessed, _ = mimetypes.guess_type(path.name)
    return guessed


def _checksum(path: Path, *, chunk_size: int = 1024 * 1024) -> str:
    """Streamed SHA-256, so a multi-gigabyte video does not fill memory.

    Duplicate detection and integrity verification both need a cheap content
    identifier; using the filesystem ' 'etag' ' for that would be wrong on S3
    multipart uploads.
    """
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()
