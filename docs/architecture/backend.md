# Backend Architecture

FastAPI + Pydantic v2 + SQLAlchemy 2.x + Alembic, organised as a **modular
monolith** with four layers and a strict inward dependency rule.

---

## 1. The layers

'''
app/
├── main.py                    composition root — assembles the app, nothing else
│
├── api/                       ── INTERFACE ──
│   ├── dependencies.py          DI providers: build adapters, expose ports
│   ├── exception_handlers.py    the only place HTTP status codes are chosen
│   └── v1/
│       ├── __init__.py          aggregates the routers under /api/v1
│       ├── params.py            shared pagination
│       ├── presenters.py        domain entity → wire shape
│       └── <domain>.py          one router per domain
│
├── application/               ── APPLICATION ──
│   ├── ports/                   interfaces the app depends on
│   │   ├── repositories.py
│   │   ├── unit_of_work.py
│   │   ├── jobs.py              ← the async seam
│   │   └── video_storage.py
│   └── use_cases/               one module per capability
│
├── domain/                    ── DOMAIN ── pure Python
│   ├── shared.py                ids, value objects, pagination
│   └── <concept>/entities.py    one directory per aggregate
│
├── infrastructure/            ── INFRASTRUCTURE ── adapters
│   ├── database/
│   │   ├── engine.py            async engine + session factory
│   │   ├── base.py              DeclarativeBase, naming convention, mixins
│   │   ├── models.py            SQLAlchemy tables
│   │   ├── mappers.py           entity ↔ model translation
│   │   ├── repositories.py      SQL implementations of the ports
│   │   └── unit_of_work.py      transaction scope
│   ├── storage/                 local filesystem (+ S3 in Phase 1)
│   └── jobs/                    inline dispatcher (+ Celery in Phase 1)
│
└── schemas/                   ── API CONTRACT ── Pydantic request/response
'''

### The dependency rule

Dependencies point **inwards**. Nothing in 'domain/' or 'application/' may import
FastAPI, SQLAlchemy or Pydantic.

What enforces it in practice:

* the domain imports only 'dataclasses', 'datetime', 'uuid', 're';
* the application imports only ports and domain types;
* 'infrastructure/' is the only package importing SQLAlchemy;
* route handlers delegate — a handler that contains an 'if' about domain state is
  a bug in review.

**Why it is worth the discipline.** The payout arrives when the worker is
extracted. Because the domain has no framework dependency and use cases depend on
interfaces, a Celery task calls the *same*
'request_analysis_run' use case the HTTP handler calls. If business logic lived
in route handlers, the worker would need its own copy, and the two would diverge.

---

## 2. Why domain entities and SQLAlchemy models are separate

'''
app/domain/videos/entities.py        class Video          ← behaviour, invariants
app/infrastructure/database/models.py class VideoModel     ← table, columns
app/infrastructure/database/mappers.py  video_to_domain()  ← translation
'''

Merging them (the common 'Base = declarative_base()' + domain-methods-on-the-model
approach) is faster to start and worse to live with:

| Change                         | Merged                                  | Separate                          |
| ------------------------------ | --------------------------------------- | --------------------------------- |
| Rename a column                | Touches whatever used the attribute name | One mapper function               |
| Add a performance index        | Domain file changes                     | Migration only                    |
| Change a business rule         | Risky — it is in a persistence class    | Domain file, no migration         |
| Reuse the domain in a worker   | Must import the ORM and a session       | 'import app.domain'               |
| Unit-test an invariant         | Needs a session or a mocked one         | Plain Python, microseconds        |

The cost is one mapper function per aggregate. The benefit is that the two models
can evolve for their own reasons — which is exactly what a schema and a domain do.

**Cross-domain references are by identifier.** A 'Video' holds a 'MatchId', not a
'Match'. Aggregates load independently, and the boundary stays real.

---

## 3. Ports and adapters

Every external dependency is an interface in 'application/ports', declared with
'typing.Protocol' so adapters need not inherit from anything.

| Port                 | Purpose                                 | Phase 0 adapter          | Phase 1 adapter |
| -------------------- | --------------------------------------- | ------------------------ | --------------- |
| 'UnitOfWork'         | transaction scope exposing repositories  | 'SqlAlchemyUnitOfWork'   | same            |
| '*Repository' (10)   | persistence per aggregate                | SQL implementations      | same            |
| 'JobDispatcher'      | **dispatch** long-running work           | 'InlineJobDispatcher'    | Celery          |
| 'JobRegistry'        | map job kind → handler (worker side)     | 'InlineJobRegistry'      | Celery          |
| 'VideoStorage'       | object storage with presigned URLs       | 'LocalVideoStorage'      | S3              |

'Protocol' rather than ABC because a fake satisfying the interface needs no
import gymnastics, and because the port can be satisfied by a third-party object.

### 'JobDispatcher' is the most important interface in Phase 0

'''python
class JobDispatcher(Protocol):
    async def dispatch(self, job: Job) -> JobResult: ...
'''

Everything about the asynchronous video architecture follows from this being a
port:

* the API's only responsibility for long work is to write a row and hand over a
  small JSON payload;
* the payload is a 'dict', not an entity, because it must survive JSON
  serialisation into a broker;
* moving to Celery is a new adapter plus 'SPA_JOB_BACKEND=celery'. No use case,
  handler, or domain entity changes.

---

## 4. Why route handlers contain no business logic

A handler does exactly three things:

'''python
@router.post("", response_model=VideoRead, status_code=201)
async def request_upload(payload, uow, storage) -> VideoUploadTicket:
    ticket = await use_cases.request_video_upload(       # 2. delegate
        uow, organization_id=..., filename=..., storage=storage,
    )
    return VideoUploadTicket(video_id=ticket.video_id,   # 3. shape
                             upload_url=ticket.upload_url, ...)
'''

1. Parse the request (FastAPI + Pydantic).
2. Call a use case.
3. Shape the response.

Consequences that are the point:

* **The API process is swappable.** The same use case runs in a CLI, a Celery
  task, or a test with fakes and no HTTP server.
* **Rules have one home.** Slug validation lives in the 'Slug' value object, so
  HTTP today and an admin tool tomorrow enforce it identically.
* **Tests are fast.** 'tests/unit/application/test_videos.py' asserts the whole
  asynchronous contract with in-memory fakes, in milliseconds.

### Where the flattening happens: 'presenters.py'

The domain groups related values into value objects ('Slug', 'VideoSpec',
'MatchVenue', 'ReportScope'); the wire format flattens them. 'api/v1/presenters.py'
is the single translator between the two.

That indirection is deliberate. Teaching each value object to serialise itself
would put presentation concerns into the domain; flattening inline in each handler
would duplicate the mapping across list, detail and create endpoints — and the
three would drift.

### Documented exceptions

One handler touches the session directly:

| Location              | Why it is exempt                                                                                              |
| --------------------- | ------------------------------------------------------------------------------------------------------------- |
| 'api/v1/health.py'    | The readiness probe runs 'SELECT 1'. It has no domain meaning, so a use case would exist only to wrap a health check in a layer of indirection that benefits nothing. It is the sole raw SQL statement outside 'infrastructure/'. |

The exception is declared in the file's own docstring **and** in
'.github/workflows/architecture.yml', where the guard is scoped with
'--exclude=health.py'. A rule with a documented, auditable hole is better than a
rule that is quietly not enforced — the hole is visible in review.

---

## 5. The error contract

Every failure returns one shape, from 'api/exception_handlers.py' and nowhere
else:

'''json
{ "error": { "code": "not_found", "message": "Video abc does not exist." } }
'''

| Code                     | HTTP | Meaning                                        |
| ------------------------ | ---- | ---------------------------------------------- |
| 'validation_error'       | 422  | Payload invalid (includes field-level 'errors') |
| 'not_found'              | 404  | Does not exist **in the caller's workspace**    |
| 'conflict'               | 409  | Conflicts with current state                    |
| 'invalid_state'          | 409  | Wrong lifecycle state for this operation        |
| 'permission_denied'      | 403  | Authenticated but not allowed                   |
| 'authentication_required'| 401  | Not authenticated                               |
| 'unsupported_media'      | 415  | Unacceptable upload type                        |
| 'infrastructure_error'   | 503  | A dependency failed                             |
| 'internal_error'         | 500  | Unexpected                                      |

Design decisions worth noting:

* **Use cases raise, they do not return responses.** Domain and application code
  never choose a status code.
* **FastAPI's default 422 body is normalised.** Left alone, validation errors
  would be the one response shape the frontend must special-case forever.
* **A cross-tenant read returns 404, not 403.** Returning 403 would confirm that
  the id exists, leaking the existence of another tenant's data.
* **SQLAlchemy errors never leak SQL.** A database failure becomes a 503 with a
  generic message; the detail goes to the log.
* **'code' is the contract, 'message' is for humans.** The frontend switches on
  'code'. This is stated in the docstring and in the OpenAPI description, because
  'if (message.includes("not found"))' is exactly the shortcut that makes an API
  unmaintainable.

---

## 6. Configuration

'app/core/config.py', Pydantic Settings, **every variable prefixed 'SPA_'**.

Why the prefix is not cosmetic: 'DEBUG', 'ENVIRONMENT' and similar names are
commonly already set by shells, CI runners and container images. A collision
either breaks startup confusingly or — far worse — silently enables debug mode in
production.

Two deliberate choices:

* **'SPA_DATABASE_URL' has no default.** A misconfigured environment fails loudly
  at startup instead of silently connecting to an unintended database.
* **'Settings' is cached** ('functools.lru_cache') so imports do not re-parse the
  environment. Tests clear it, which is why 'conftest.py' resets the cache around
  every test — otherwise a configuration change leaks between tests and failures
  depend on execution order.

---

## 7. Database access

See ['database.md'](database.md) for the schema. The access pattern:

'''python
async def create_team(uow: UnitOfWork, *, organization_id, name, slug) -> Team:
    async with uow:                          # one session, one transaction
        organization = await uow.organizations.get(organization_id)
        if organization is None:
            raise NotFoundError(...)         # fails before any write

        team = Team(organization_id=..., name=..., slug=Slug(slug))
        await uow.teams.add(team)
        await uow.commit()
        return team
'''

* **One unit of work per use case**, not per request. A use case must not inherit
  a half-open transaction, and workers call use cases outside any request.
* **'expire_on_commit=False'.** Use cases return entities *after* committing;
  implicit expiry would turn that into an extra query or a lazy-load error in an
  async context.
* **Explicit 'update()' on repositories.** A repository that silently flushes on
  attribute access makes it impossible to tell where a write happens.
* **Every organization-scoped read filters by organization.** Applied in the
  repository, not the handler, because a handler that forgets is an incident.
* **Bulk metric inserts.** A match produces thousands of metric rows; per-row
  ORM inserts would dominate the worker's write path.

---

## 8. Testing strategy

Two tiers, deliberately:

### Unit tests ('tests/unit/')

No database, no server, milliseconds.

* 'domain/' — invariants on plain Python objects. These are the tests that
  justify keeping the domain framework-free.
* 'application/' — use cases against in-memory fakes from
  'tests/unit/application/fakes.py'. They assert outcomes (a job was dispatched
  with this payload, this state transition was persisted), not interaction
  choreography.
* 'api/' — the HTTP contract that does not need data: health, validation, the
  error envelope, CORS, and that 'POST /analysis-runs' is documented as '202'.
  That last assertion matters: if it ever becomes '200', the asynchronous
  architecture has been broken somewhere.

### Integration tests ('tests/integration/', marked 'integration')

Against real PostgreSQL, because the schema depends on PostgreSQL-specific
behaviour:

* JSONB round-trips;
* check constraints (a player-scoped metric with no player is rejected **by the
  database**, not only by the domain — a future worker writing directly must not
  be able to create orphan numbers);
* 'ON DELETE CASCADE' semantics;
* tenancy scoping through the real repositories.

Each test truncates every table first ('clean_database' fixture). Without that,
tests pass or fail depending on execution order and on what a previous run left
behind — the kind of flakiness that erodes trust in a suite.

A note on the test database: 'conftest.py' reads 'SPA_TEST_DATABASE_URL' and
**overwrites** 'SPA_DATABASE_URL' with it. A test run must never be able to write
to the database a developer is actually using.

---

## 9. Structural honesty about Phase 0

'UnitOfWorkStub' in the test suite is a fake, not the real thing, and the fakes
are not a substitute for the integration tests. The fake proves the *contract*;
only the integration tests prove the SQL works. Both exist, and neither is
presented as the other.

'InlineJobDispatcher' records dispatches and executes nothing. That is accurate
rather than a stub for its own sake — it makes the asynchronous contract real and
testable today; it just does not process video.

'build_job_queue' and 'build_video_storage' raise 'NotImplementedError' for the
'celery' and 's3' settings rather than silently falling back. A configuration
value that looks accepted but is ignored is worse than one that fails immediately.