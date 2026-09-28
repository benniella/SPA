# SPA Backend

FastAPI application for **SPA — Sport Performance Analysis**.

The backend is a **modular monolith with pragmatic DDD**. It serves the HTTP API
that the Next.js frontend consumes, owns the PostgreSQL schema, and dispatches —
but never executes — long-running video-processing work.

---

## Layering

The dependency rule points inwards. Nothing in 'domain' or 'application' may
import FastAPI or SQLAlchemy.

'''
app/
├── main.py                  FastAPI application factory (composition root)
│
├── api/                     ── INTERFACE LAYER ──
│   ├── dependencies.py        DI providers: adapters → ports
│   ├── exception_handlers.py  the only place status codes are chosen
│   └── v1/                    routers, grouped by domain (mirrors app/domain)
│
├── domain/                  ── DOMAIN LAYER ── pure Python, framework-free
│   ├── shared.py              ids, slugs, value objects, pagination
│   ├── organizations/         tenancy
│   ├── users/                 identity
│   ├── teams/  players/       performance subjects
│   ├── matches/               the organising concept
│   ├── videos/                media + ingestion lifecycle
│   ├── analysis/              runs, metrics, heatmaps, team shape
│   ├── tracking/              trajectories
│   └── reports/               shareable snapshots
│
├── application/             ── APPLICATION LAYER ── use-case orchestration
│   ├── ports/                 interfaces: repositories, jobs, storage, UoW
│   └── use_cases/             one module per capability
│
├── infrastructure/          ── INFRASTRUCTURE LAYER ── adapters
│   ├── database/              engine, models, mappers, repositories, UoW
│   ├── storage/               local filesystem (S3 adapter in Phase 1)
│   └── jobs/                  inline dispatcher (Celery adapter in Phase 1)
│
└── schemas/                 ── the public API contract (Pydantic)
'''

### Why domain entities and SQLAlchemy models are separate

'app/domain/**/entities.py' holds behaviour and invariants; 'app/infrastructure/
database/models.py' holds tables and columns; 'mappers.py' translates. They are
kept apart so that a column rename is not an API change, a domain rule change is
not a migration, and the domain can be reused verbatim inside a future worker
process.

### Why route handlers contain no business logic

A handler parses, delegates to a use case, and shapes a response. Everything
else lives behind the use-case boundary. This is what makes the API process
swappable: the same use case will be callable from a Celery task.

---

## Asynchronous video processing

'POST /analysis-runs' returns '202 Accepted' in milliseconds. It creates an
'AnalysisRun' row and hands a JSON payload to a 'JobDispatcher'. It never opens
the video, never imports a computer-vision library, and never blocks.

'GET /analysis-runs/{id}' is polled for progress; the worker owns every
subsequent state change.

The seam is 'app/application/ports/jobs.py'. Moving to Celery + Redis means
adding one adapter class and changing 'JOB_BACKEND'. No use case changes.

See 'docs/architecture/video-processing.md'.

---

## Commands

Run these from the repository root ('make help' lists everything):

'''bash
make backend-install    # create .venv and install dependencies
make migrate            # apply Alembic migrations
make backend-dev        # uvicorn --reload on :8000
make backend-test       # pytest (unit tests)
make backend-lint       # ruff check
make backend-fmt        # ruff format + autofix
make backend-typecheck  # mypy
'''

Integration tests need PostgreSQL:
'''bash
docker compose up -d postgres
cd backend && ALEMBIC_DATABASE_URL=$DATABASE_URL .venv/bin/alembic upgrade head
.venv/bin/pytest -m integration
'''

## Configuration

Copy '.env.example' to '.env'. 'DATABASE_URL' has no default on purpose: a
misconfigured environment fails at startup rather than silently connecting
somewhere unintended. No credential is ever committed.

## API documentation

FastAPI generates the OpenAPI document automatically:

* 'http://localhost:8000/docs' — Swagger UI
* 'http://localhost:8000/redoc' — ReDoc
* 'http://localhost:8000/openapi.json' — the document the frontend generates its
  typed client from

Every error uses one envelope: '{"error": {"code", "message", "details"}}'.
Switch on 'code', never on 'message'.