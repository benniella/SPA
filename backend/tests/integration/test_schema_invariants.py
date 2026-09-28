"""Integration tests that assert the database schema itself is sound.

Schema-level invariants belong here rather than in the API tests: a check
constraint must hold even if a future worker writes to the table directly,
bypassing every use case.
"""

from __future__ import annotations

import json
import uuid

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.core.config import get_settings
from app.infrastructure.database.engine import get_session_factory, session_scope

pytestmark = [pytest.mark.integration, pytest.mark.usefixtures("clean_database")]


@pytest_asyncio.fixture
async def session_factory() -> object:
    return get_session_factory(get_settings())


_INSERT_ORG = text("INSERT INTO organizations (id, name, slug) VALUES (:id, :name, :slug)")


async def _create_organization(session: object, slug_prefix: str) -> uuid.UUID:
    """Insert a bare organization and return its id.

    Written as raw SQL on purpose: these tests assert database-level invariants,
    so they must not depend on the repositories or the ORM mapping.
    """
    organization_id = uuid.uuid4()
    await session.execute(  # type: ignore[attr-defined]
        _INSERT_ORG,
        {
            "id": organization_id,
            "name": f"Org {slug_prefix}",
            "slug": f"{slug_prefix}-{organization_id.hex[:8]}",
        },
    )
    return organization_id


class TestMetricScopeConstraint:
    async def test_player_scoped_metric_requires_a_player(self, session_factory: object) -> None:
        async with session_scope(session_factory) as session:  # type: ignore[arg-type]
            org_id = await _create_organization(session, "metric")

            video_id = uuid.uuid4()
            await session.execute(
                text(
                    "INSERT INTO videos (id, organization_id, original_filename, storage_key, status)"
                    " VALUES (:id, :org, 'm.mp4', :key, 'stored')"
                ),
                {"id": video_id, "org": org_id, "key": f"k-{video_id}"},
            )
            run_id = uuid.uuid4()
            await session.execute(
                text(
                    "INSERT INTO analysis_runs (id, organization_id, video_id, status, progress_percent)"
                    " VALUES (:id, :org, :video, 'running', 0)"
                ),
                {"id": run_id, "org": org_id, "video": video_id},
            )

            # A player-scoped metric with no player must be rejected by the
            # database, not merely by the domain layer.
            with pytest.raises(IntegrityError):
                await session.execute(
                    text(
                        "INSERT INTO performance_metrics"
                        " (id, organization_id, analysis_run_id, scope, category, name, value,"
                        "  unit, definition_version)"
                        " VALUES (:id, :org, :run, 'player', 'movement', 'distance', 1.0, 'm', 'v1')"
                    ),
                    {"id": uuid.uuid4(), "org": org_id, "run": run_id},
                )
            await session.rollback()


class TestVideoLifecycleConstraint:
    async def test_negative_size_is_rejected(self, session_factory: object) -> None:
        async with session_scope(session_factory) as session:  # type: ignore[arg-type]
            org_id = await _create_organization(session, "negative")

            with pytest.raises(IntegrityError):
                await session.execute(
                    text(
                        "INSERT INTO videos"
                        " (id, organization_id, original_filename, storage_key, status, size_bytes)"
                        " VALUES (:id, :org, 'm.mp4', :key, 'stored', -1)"
                    ),
                    {"id": uuid.uuid4(), "org": org_id, "key": f"neg-{uuid.uuid4()}"},
                )
            await session.rollback()

    async def test_storage_key_is_unique(self, session_factory: object) -> None:
        key = f"shared-{uuid.uuid4()}"
        async with session_scope(session_factory) as session:  # type: ignore[arg-type]
            org_id = await _create_organization(session, "unique")
            statement = text(
                "INSERT INTO videos (id, organization_id, original_filename, storage_key, status)"
                " VALUES (:id, :org, 'm.mp4', :key, 'uploaded')"
            )
            await session.execute(statement, {"id": uuid.uuid4(), "org": org_id, "key": key})

            # Two videos must never point at the same blob.
            with pytest.raises(IntegrityError):
                await session.execute(statement, {"id": uuid.uuid4(), "org": org_id, "key": key})
            await session.rollback()


class TestCascadeBehaviour:
    async def test_deleting_a_video_removes_its_analysis_runs(
        self, session_factory: object
    ) -> None:
        video_id = uuid.uuid4()
        async with session_scope(session_factory) as session:  # type: ignore[arg-type]
            org_id = await _create_organization(session, "cascade")
            await session.execute(
                text(
                    "INSERT INTO videos (id, organization_id, original_filename, storage_key, status)"
                    " VALUES (:id, :org, 'm.mp4', :key, 'stored')"
                ),
                {"id": video_id, "org": org_id, "key": f"cascade-{video_id}"},
            )
            await session.execute(
                text(
                    "INSERT INTO analysis_runs (id, organization_id, video_id, status, progress_percent)"
                    " VALUES (:id, :org, :video, 'succeeded', 100)"
                ),
                {"id": uuid.uuid4(), "org": org_id, "video": video_id},
            )

            await session.execute(text("DELETE FROM videos WHERE id = :id"), {"id": video_id})
            remaining = await session.execute(
                text("SELECT count(*) FROM analysis_runs WHERE video_id = :id"),
                {"id": video_id},
            )
            assert remaining.scalar_one() == 0
            await session.commit()


class TestJsonbRoundTrip:
    async def test_analysis_run_stage_results_survive_a_round_trip(
        self, session_factory: object
    ) -> None:
        video_id = uuid.uuid4()
        run_id = uuid.uuid4()
        payload = {"detection": {"completed": True, "frames": 135000}}

        async with session_scope(session_factory) as session:  # type: ignore[arg-type]
            org_id = await _create_organization(session, "jsonb")
            await session.execute(
                text(
                    "INSERT INTO videos (id, organization_id, original_filename, storage_key, status)"
                    " VALUES (:id, :org, 'm.mp4', :key, 'stored')"
                ),
                {"id": video_id, "org": org_id, "key": f"jsonb-{video_id}"},
            )
            # The dict is serialised explicitly: a raw-text INSERT has no ORM
            # type information, so psycopg cannot adapt a Python dict to jsonb
            # on its own. The ORM path handles this, raw SQL does not.
            await session.execute(
                text(
                    "INSERT INTO analysis_runs"
                    " (id, organization_id, video_id, status, progress_percent, stage_results)"
                    " VALUES (:id, :org, :video, 'running', 50, CAST(:results AS jsonb))"
                ),
                {
                    "id": run_id,
                    "org": org_id,
                    "video": video_id,
                    "results": json.dumps(payload),
                },
            )
            await session.commit()

        async with session_scope(session_factory) as session:  # type: ignore[arg-type]
            result = await session.execute(
                text("SELECT stage_results FROM analysis_runs WHERE id = :id"),
                {"id": run_id},
            )
            assert result.scalar_one() == payload
