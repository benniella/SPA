"""Shared test fixtures.

Tests are organised in two tiers:

* **Unit tests** (the default) exercise domain, application and HTTP-contract
  code. They need no database and run in milliseconds, which is what makes them
  useful during development.
* **Integration tests** (marked ' 'integration' ') exercise the API against a real
  PostgreSQL database, because SPA's schema relies on PostgreSQL-specific
  behaviour (JSONB, check constraints, ' 'ON DELETE' ' semantics) that a substitute
  database would not faithfully reproduce.

The HTTP client fixture runs the application's lifespan. That matters: adapters
are built during startup and stashed on ' 'app.state' ', so a client that bypassed
lifespan would see an unconfigured application and produce misleading 500s where
real behaviour was expected.

' 'SPA_TEST_DATABASE_URL' ' must point at a disposable database for integration
tests. It is read in preference to ' 'SPA_DATABASE_URL' ' on purpose: the test
suite must never be able to write to the database a developer is actually using.
See ' 'docs/product/local-development.md' ', or run ' 'make integration-test' ', which
provisions and migrates that database for you.
"""

from __future__ import annotations

import os
from collections.abc import AsyncIterator, Iterator

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

# Settings are read once, at first use, so the test database must be selected
# before any application module is imported. Variables carry the SPA_ prefix
# (see 'app.core.config') to avoid collisions with the ambient environment.
#
# 'SPA_TEST_DATABASE_URL' deliberately *overrides* rather than defers to
# 'SPA_DATABASE_URL': a test run must never be able to write to the database a
# developer is using, even if backend/.env points at it.
TEST_DATABASE_URL = os.environ.get(
    "SPA_TEST_DATABASE_URL",
    "postgresql+psycopg://spa:spa@localhost:5442/spa_test",
)
os.environ["SPA_DATABASE_URL"] = TEST_DATABASE_URL
os.environ.setdefault("SPA_ENVIRONMENT", "local")
os.environ.setdefault("SPA_CORS_ORIGINS", "http://localhost:3000")


@pytest.fixture(scope="session")
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture(autouse=True)
def _reset_settings_cache() -> Iterator[None]:
    """Clear the settings singleton around every test.

    Without this, a test that changes configuration leaks the cached Settings
    into the next test, producing failures that depend on execution order.
    """
    from app.core.config import get_settings

    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def app() -> FastAPI:
    """A fresh application instance bound to the test settings."""
    from app.core.config import get_settings
    from app.main import create_app

    return create_app(get_settings())


@pytest_asyncio.fixture
async def client(app: FastAPI) -> AsyncIterator[AsyncClient]:
    """An HTTP client that talks to the app in-process, with lifespan running.

    ' 'LifespanManager' ' is used rather than a bare ' 'ASGITransport' ' so that
    startup actually executes. The job dispatcher and storage adapter are built
    there and stashed on ' 'app.state' '; without them, every endpoint that
    dispatches work would fail with a configuration error instead of exercising
    the behaviour under test.
    """
    from asgi_lifespan import LifespanManager

    async with (
        LifespanManager(app) as manager,
        AsyncClient(
            transport=ASGITransport(app=manager.app),
            base_url="http://testserver",
        ) as http_client,
    ):
        yield http_client


@pytest.fixture
async def clean_database() -> AsyncIterator[None]:
    """Truncate every table before an integration test runs.

    Integration tests share one PostgreSQL database because starting a fresh one
    per test is far slower than truncating. Without this, tests pass or fail
    depending on execution order and on what a previous run left behind — which
    is exactly the kind of flakiness that erodes trust in a suite.

    ' 'TRUNCATE ... CASCADE' ' is used rather than ' 'DELETE' ' so that sequence and
    identity state is reset too, and one statement clears the whole dependency
    graph.
    """
    from sqlalchemy import text

    from app.core.config import get_settings
    from app.infrastructure.database import load_models
    from app.infrastructure.database.base import Base
    from app.infrastructure.database.engine import get_session_factory, session_scope

    settings = get_settings()
    load_models()
    tables = ", ".join(f'"{table.name}"' for table in reversed(Base.metadata.sorted_tables))

    session_factory = get_session_factory(settings)
    async with session_scope(session_factory) as session:
        await session.execute(text(f"TRUNCATE {tables} CASCADE"))
        await session.commit()

    yield


@pytest.fixture
def organization_id() -> str:
    """A stable identifier so unit tests do not rely on random UUIDs."""
    return "11111111-1111-1111-1111-111111111111"


@pytest.fixture
def failing_job_dispatcher() -> Iterator[object]:
    """A dispatcher that records dispatches without executing them.

    Imported lazily so that unit tests which never dispatch a job do not pay for
    importing the infrastructure package.
    """
    from app.application.ports.jobs import Job, JobResult

    class RecordingDispatcher:
        def __init__(self) -> None:
            self.jobs: list[Job] = []

        async def dispatch(self, job: Job) -> JobResult:
            self.jobs.append(job)
            return JobResult(accepted=True, job_id=f"job-{len(self.jobs)}")

    yield RecordingDispatcher()
