"""KeyDB job queue tests.

These exercise the real KeyDB client, so they are marked 'integration' and skip
cleanly when KeyDB is unreachable rather than failing an ordinary unit run. The
behaviour under test is the reliable-queue contract: a dequeued job is not lost
until acknowledged, and a duplicate enqueue is collapsed.
"""

from __future__ import annotations

import os
from collections.abc import AsyncIterator

import pytest

from app.infrastructure.jobs.keydb_queue import KeyDbJobQueue

pytestmark = pytest.mark.integration

KEYDB_URL = os.environ.get("SPA_TEST_KEYDB_URL", "redis://localhost:6379/15")


@pytest.fixture
async def queue() -> AsyncIterator[KeyDbJobQueue]:
    instance = KeyDbJobQueue(KEYDB_URL, visibility_timeout_seconds=60)
    if not await instance.ping():
        pytest.skip("KeyDB is not reachable; set SPA_TEST_KEYDB_URL to run this.")
    await instance.flush()
    yield instance
    await instance.flush()
    await instance.close()


class TestReliableDelivery:
    async def test_enqueue_then_dequeue_returns_the_identifier(self, queue: KeyDbJobQueue) -> None:
        await queue.enqueue("job-1")
        assert await queue.dequeue(timeout_seconds=1) == "job-1"

    async def test_a_dequeued_job_is_not_lost_before_acknowledgement(
        self, queue: KeyDbJobQueue
    ) -> None:
        await queue.enqueue("job-1")
        assert await queue.dequeue(timeout_seconds=1) == "job-1"
        # Not acknowledged: a second worker must not see it, but it must still
        # exist so a reclaim can return it.
        assert await queue.dequeue(timeout_seconds=1) is None
        await queue.requeue("job-1")
        assert await queue.dequeue(timeout_seconds=1) == "job-1"

    async def test_acknowledgement_removes_the_job(self, queue: KeyDbJobQueue) -> None:
        await queue.enqueue("job-1")
        await queue.dequeue(timeout_seconds=1)
        await queue.acknowledge("job-1")
        assert await queue.dequeue(timeout_seconds=1) is None

    async def test_a_duplicate_enqueue_is_collapsed(self, queue: KeyDbJobQueue) -> None:
        await queue.enqueue("job-1")
        await queue.enqueue("job-1")
        assert await queue.dequeue(timeout_seconds=1) == "job-1"
        assert await queue.dequeue(timeout_seconds=1) is None

    async def test_an_empty_queue_returns_none(self, queue: KeyDbJobQueue) -> None:
        assert await queue.dequeue(timeout_seconds=1) is None
