from __future__ import annotations

import uuid

import pytest

from app.core.config import Settings
from app.infrastructure.storage.local import LocalVideoStorage


def storage(tmp_path: object) -> LocalVideoStorage:
    settings = Settings(
        database_url="postgresql+psycopg://spa:spa@localhost/spa",
        session_secret="x" * 40,
        storage_local_root=str(tmp_path),
    )
    return LocalVideoStorage(settings)


class TestWriteBytes:
    async def test_written_bytes_are_read_back(self, tmp_path: object) -> None:
        adapter = storage(tmp_path)
        key = adapter.build_key(
            str(uuid.uuid4()), category="reports", owner_id=str(uuid.uuid4()), filename="report.html"
        )

        await adapter.write_bytes(key, b"<html>report</html>")

        assert await adapter.open(key) == b"<html>report</html>"

    async def test_a_written_object_is_reported_by_stat(self, tmp_path: object) -> None:
        adapter = storage(tmp_path)
        key = adapter.build_key(
            str(uuid.uuid4()), category="reports", owner_id=str(uuid.uuid4()), filename="report.html"
        )

        await adapter.write_bytes(key, b"abc")

        stored = await adapter.stat(key)
        assert stored is not None
        assert stored.size_bytes == 3

    async def test_a_key_cannot_escape_the_storage_root(self, tmp_path: object) -> None:
        adapter = storage(tmp_path)

        with pytest.raises(ValueError):
            await adapter.write_bytes("../escape.html", b"x")

    async def test_overwriting_a_key_replaces_the_object(self, tmp_path: object) -> None:
        adapter = storage(tmp_path)
        key = adapter.build_key(
            str(uuid.uuid4()), category="reports", owner_id=str(uuid.uuid4()), filename="report.html"
        )

        await adapter.write_bytes(key, b"first")
        await adapter.write_bytes(key, b"second")

        assert await adapter.open(key) == b"second"
