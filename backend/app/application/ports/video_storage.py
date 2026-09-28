"""Object storage port for video originals and derived artefacts.

The database stores a 'storage_key'; this port resolves it, so local disk in
development and object storage in production share one code path.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol, runtime_checkable


@dataclass(frozen=True, slots=True)
class StoredObject:
    """Metadata about an object that exists in storage."""

    key: str
    size_bytes: int
    content_type: str | None = None
    etag: str | None = None
    last_modified: datetime | None = None


@runtime_checkable
class VideoStorage(Protocol):
    """Read/write access to video and artefact binaries.

    Uploads are presigned so large files never pass through the API process.
    """

    def build_key(
        self,
        organization_id: str,
        *,
        category: str,
        owner_id: str,
        filename: str,
    ) -> str:
        """Return the canonical storage key for a new object.

        Keys are namespaced by organization so tenancy is enforced at the
        storage layer as well as in SQL, and the owning record's id is part of
        the path so all of one video's objects share a deletable prefix.
        """
        ...

    async def presign_upload(
        self,
        key: str,
        *,
        content_type: str | None = None,
        expires_in: int = 3600,
    ) -> str: ...

    async def presign_download(self, key: str, *, expires_in: int = 3600) -> str: ...

    async def stat(self, key: str) -> StoredObject | None: ...

    async def delete(self, key: str) -> None: ...

    async def open(self, key: str) -> bytes:
        """Read an object fully. Intended for small artefacts, not match video."""
        ...
