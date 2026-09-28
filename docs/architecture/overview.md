# SPA — Architecture Overview

> **Phase 0.** This document describes the foundation that exists and the shape
> the system is intended to grow into. Where a decision is deliberately
> unresolved, it says so explicitly rather than implying a design that has not
> been chosen.

---

## 1. What SPA is

SPA turns sports video into structured performance data.

A coach uploads a match recording. SPA processes it, tracks the players and the
ball, derives movement, spatial and workload information, and presents it as
data a coach can act on — distances, sprint counts, heatmaps, team shape,
intensity profiles, and eventually reports.

The product statement matters architecturally because it contains two very
different kinds of work:

|                       | Core platform                                       | Video processing subsystem                       |
| --------------------- | --------------------------------------------------- | ------------------------------------------------ |
| **What it does**      | Accounts, workspaces, squads, matches, permissions, navigation, reporting | Detection, tracking, calibration, metric extraction |
| **Runtime shape**     | Fast, synchronous, request/response                 | Slow, asynchronous, batch, potentially GPU-bound  |
| **Change cadence**    | Continuous, product-driven                          | Episodic, research-driven                        |
| **Failure impact**    | Users cannot sign in or see data                    | One job is retried                               |
| **Who works on it**   | Product engineers                                   | ML engineers                                     |

Conflating these two is the most common way a platform like SPA becomes
unmaintainable. The architecture keeps them apart structurally, not by
convention: see §5.

---

## 2. Why a modular monolith

SPA is a **modular monolith with pragmatic Domain-Driven Design**.

The reasoning, and the alternatives that were rejected:

**Rejected: microservices from day one.** There is exactly one product to build
and no measured scaling problem. Splitting into services now would buy
independent deployability at the cost of distributed transactions, network
failure modes, service discovery, contract versioning and a local development
story that requires running eight processes. Every one of those costs is paid
immediately; the benefit is speculative.

**Rejected: a single unstructured application.** The opposite failure. A
codebase where route handlers query the database directly, where the ML pipeline
imports application internals, and where nothing can be changed without
understanding everything, cannot absorb the video-processing subsystem without a
rewrite.

**Chosen: one deployable unit, real internal boundaries.** The application
deploys as one process and one database. Internally, the boundaries are enforced
by the dependency rule (§3), and the seams that would eventually become service
boundaries — job dispatch, object storage — are already interfaces with one
implementation.

The practical test of whether this was the right call: extracting the video
worker later should require writing one adapter and changing one configuration
value, not restructuring the codebase. That property is designed in and tested
(§5).

### What "pragmatic DDD" means here

Full DDD — aggregates with strict consistency boundaries, domain events,
repositories returning aggregate roots, an anti-corruption layer per bounded
context — is a large investment that pays off on complex, long-lived domain
models.

SPA's core domain is genuinely simple: a workspace has teams, teams have players,
matches have videos, videos have analysis runs. Being dogmatic about that would
add ceremony without insight.

What *is* taken seriously:

* **A framework-free domain layer.** Entities and invariants are plain Python,
  testable in milliseconds, reusable inside a worker.
* **Explicit boundaries per domain concept.** One directory per aggregate, with
  named ownership.
* **Dependency inversion at the infrastructure edge.** The application declares
  what it needs; infrastructure provides it.

What is deliberately *not* done: no event sourcing, no CQRS, no domain events, no
specification pattern, no generic base repository hierarchy. Those are tools for
problems SPA does not have, and each would make the codebase harder to read for
the person who arrives next.

---

## 3. The dependency rule

The single most important structural rule in the backend:

'''
        ┌──────────────────────────────────────────────┐
        │  api/            FastAPI routers, DI, errors  │
        └───────────────────┬──────────────────────────┘
                            │ depends on
        ┌───────────────────▼──────────────────────────┐
        │  application/    use cases + ports            │
        └───────────────────┬──────────────────────────┘
                            │ depends on
        ┌───────────────────▼──────────────────────────┐
        │  domain/         entities, invariants         │
        │                  (no framework imports)       │
        └──────────────────────────────────────────────┘
                            ▲
                            │ implements ports
        ┌───────────────────┴──────────────────────────┐
        │  infrastructure/  database, storage, jobs     │
        └──────────────────────────────────────────────┘

        schemas/  — Pydantic, the API contract (used by api/ only)
'''

Dependencies point **inwards**. Consequences that are actually enforced:

* 'app/domain/**' imports no FastAPI, no SQLAlchemy, no Pydantic. Verified by
  reading: the domain modules import only 'dataclasses', 'datetime', 'uuid',
  're' and each other.
* 'app/application/**' imports no FastAPI. It depends on ports, which are
  'Protocol's.
* Route handlers contain no business logic. Every handler parses a request,
  calls a use case, and shapes a response.
* 'app/infrastructure/**' is the only package that imports SQLAlchemy.
* Pydantic API schemas are separate from SQLAlchemy models. A column rename is
  not an API change.

**Why this matters more than it sounds.** The payoff arrives when the worker is
extracted. Because the domain has no framework dependency and the use cases
depend on interfaces, a Celery task can call the same
'app.application.use_cases.videos.request_analysis_run' that the HTTP handler
calls. If business logic lived in route handlers, the worker would need its own
copy — and the two copies would diverge.

---

## 4. Domain boundaries

Nine domains, each owning a distinct concept. The test for whether a boundary is
real: *could this concept change independently, and would a change leak?*

### 'organizations' — tenancy

**Owns:** the workspace, and who belongs to it with which role.

**Why it is a boundary:** it is the data-ownership boundary. Every team, player,
match, video and analysis run belongs to exactly one organization, and every
organization-scoped query filters on it. Getting tenancy wrong is a data breach,
not a bug, so it is one concept with one owner rather than a column sprinkled
across tables.

**Contains:** 'Organization', 'OrganizationMembership', 'MembershipRole'.

### 'users' — identity

**Owns:** the person record — email, display name, active flag.

**Why separate from organizations:** a user is not owned by an organization. The
same analyst may work across two clubs. Keeping identity independent is what
allows that without duplicating records.

**Contains:** 'User', 'Email'.

**Deliberately absent:** credentials, sessions, tokens. See §8.

### 'teams' — squads

**Owns:** a squad within an organization, its sport and season.

**Contains:** 'Team'.

### 'players' — athletes

**Owns:** the athlete, and their registration in teams over time.

**Why separate from teams:** players transfer. If a player belonged to a team,
a transfer would either rewrite history or orphan the performance data attached
to them. 'TeamMembership' carries a validity window so a match played last season
resolves the squad as it actually was.

**Contains:** 'Player', 'TeamMembership'.

### 'matches' — the organising concept

**Owns:** the fixture that everything else hangs off.

**Why it is central:** a coach opens a match, not a video. One match can have
several recordings (two cameras, first half and second half as separate files),
so a match is not a video.

**Contains:** 'Match', 'MatchVenue'.

**Notable:** home and away teams may be a foreign key *or* a plain name. Opponents
are frequently outside the organization's own team list, and creating shadow
'Team' rows for every opponent would pollute the teams domain with records nobody
manages.

### 'videos' — source media

**Owns:** the uploaded recording and its ingestion lifecycle.

**Why its own domain:** ingestion is a state machine with real consequences. A
video that has not finished uploading must never be scheduled for analysis.
That rule lives in the domain ('VideoStatus', guarded transitions), not in a
route handler, so both the API and any future worker agree on it.

**Contains:** 'Video', 'VideoStatus', 'VideoSpec'.

### 'analysis' — runs, metrics, spatial output

**Owns:** the unit of processing work, and the performance data it produces.

**Why it is the most consequential domain:** it defines the contract between the
synchronous API and the asynchronous worker ('AnalysisRun' and its state
machine), and it holds the *relational* performance-metric model. Metrics are
rows, not JSON, because coaches will sort, filter and trend them.

**Contains:** 'AnalysisRun', 'AnalysisPipelineSpec', 'PerformanceMetric',
'HeatmapGrid', 'TeamShapeSample', 'IntensityZoneBreakdown', 'MetricScope',
'MetricCategory'.

**Deliberately absent:** per-frame tracking observation tables. See §8.

### 'tracking' — trajectories

**Owns:** the tracked positions of players and the ball over time.

**Why separate from 'analysis':** tracking is one expensive *stage* with one
pivotal output — stable identity across frames. Its artefacts are versioned and
immutable, and they are the largest data SPA produces. Keeping them apart means
the storage strategy for trajectories can change without disturbing how metrics
are modelled.

**Contains:** 'TrackingDataset', 'TrackObservation', 'TrackSegment',
'TrackObjectType'.

### 'reports' — shareable output

**Owns:** the generated document that leaves the platform.

**Why its own domain:** a report is a *snapshot*, not a view. A report a coach
downloaded last season must not change when models are re-run. That consumption
pattern is different enough from "query the current metrics" to be its own
concept.

**Contains:** 'Report', 'ReportScope', 'ReportStatus'.

### Where each domain is allowed to reach

| From               | May depend on                                        |
| ------------------ | ---------------------------------------------------- |
| 'organizations'    | 'shared'                                             |
| 'users'            | 'shared'                                             |
| 'teams'            | 'shared', 'organizations' (by id)                    |
| 'players'          | 'shared', 'organizations', 'teams' (by id)           |
| 'matches'          | 'shared', 'organizations', 'teams' (by id)           |
| 'videos'           | 'shared', 'organizations', 'matches' (by id)         |
| 'analysis'         | 'shared', 'videos', 'matches' (by id)                |
| 'tracking'         | 'shared', 'analysis', 'videos' (by id)               |
| 'reports'          | 'shared', 'users' (by id), 'matches', 'teams'        |

Cross-domain references are **by identifier**, not by object graph. A 'Video'
holds a 'MatchId', not a 'Match'. This keeps aggregates independently loadable
and, later, independently deployable.

---

## 5. The video-processing boundary

The rule, stated plainly:

> **No HTTP request ever performs video processing.**

Everything in this section follows from that one sentence.

### The synchronous contract

'''
POST /api/v1/videos                    → 201  presigned URL, no bytes touched
    client uploads bytes directly to object storage
POST /api/v1/videos/{id}/complete      → 202  records state, dispatches a job
POST /api/v1/analysis-runs             → 202  creates a run, dispatches a job
                                            + Location header
GET  /api/v1/analysis-runs/{id}        → 200  polled for progress
'''

'POST /analysis-runs' does two things: writes one 'AnalysisRun' row and hands a
JSON payload to a 'JobDispatcher'. It does not open the video, import a
computer-vision library, or wait for anything.

### The seam

'app/application/ports/jobs.py' declares 'JobDispatcher', 'Job', 'JobKind' and
'JobHandler'. The API depends on the interface. Today the only implementation is
'InlineJobDispatcher', which records dispatches without executing them.

That is not a stub for its own sake. It means:

* the asynchronous contract is exercised end to end in tests and locally;
* payloads are real, so JSON-serialisability is verified now rather than
  discovered when a broker is introduced;
* tests assert "requesting an analysis run dispatches exactly one
  'run_analysis' job" without running Redis.

### What changes when the worker is extracted

| Change                                | Type                 |
| ------------------------------------- | -------------------- |
| Add 'infrastructure/jobs/celery.py'   | New adapter          |
| Set 'SPA_JOB_BACKEND=celery'          | Configuration        |
| Add a 'worker' service to compose     | Infrastructure       |
| **Use cases, domain, routers**        | **Unchanged**        |

No use case, route handler, domain entity or database model needs to change.

### What is explicitly not yet decided

* **Where the worker runs.** Separate container, separate host, or the same
  process for early development. The port does not care.
* **Whether detections are persisted.** Persisting every raw detection for a
  90-minute match is far more data than persisting tracks. It is only worth it
  if a re-tracking feature is genuinely needed.
* **How tracking observations are stored.** ~3.1 million observations per match.
  A columnar file in object storage and a partitioned PostgreSQL table are both
  defensible; the right answer depends on measured query patterns.
  'TrackingDataset.storage_key' exists so either can be adopted without a schema
  change.

Full detail in ['video-processing.md'](video-processing.md).

---

## 6. The data path

'''
Next.js  ──HTTP──►  FastAPI  ──SQLAlchemy──►  PostgreSQL
                        │
                        │  dispatch only
                        ▼
                  Object storage  ──►  Worker  ──►  PostgreSQL
'''

**The frontend never touches PostgreSQL.** There is no database client in
'frontend/', no connection string, and no server action that queries a database.
This is not a style preference: a browser-reachable tier holding database
credentials would put business rules in two places, make the API optional, and
turn one query bug into a cross-tenant data leak.

The frontend's only data source is the versioned HTTP API, and its response types
are intended to be *generated* from the backend's OpenAPI document so the
contract has one source of truth. Full detail in
['database.md'](database.md) and ['frontend.md'](frontend.md).

---

## 7. Why PostgreSQL

SPA's data is overwhelmingly relational. Organizations contain teams; teams
contain players; matches reference two teams and contain videos; videos produce
analysis runs; runs produce metrics. Foreign keys, unique constraints and
transactions are exactly the right tools, and they are what make tenancy
enforceable.

The alternative was considered and rejected:

* **MongoDB / a document store as primary.** Analysis *metadata* is
  open-ended — model versions, calibration parameters, stage diagnostics — and
  JSONB handles that well. But making the whole model unstructured would make
  "top distance covered this season" a full collection scan and an
  application-side sort. The relational core is not a limitation to work around;
  it is the thing being queried.
* **SQLite.** Cannot be the primary architecture. SPA needs concurrent writers
  (API and workers), 'ON DELETE CASCADE' semantics, JSONB, 'uuid' columns and
  partial indexes. Testing against SQLite would mean the production-specific
  behaviour is never exercised — which is why the integration tests run against
  real PostgreSQL.

JSONB is used, deliberately and narrowly, in five places: video probe metadata,
analysis pipeline specification, per-stage results, tracking provenance, and
report snapshots. The test for whether JSONB is appropriate: **is the value read
and written whole, with no query on its internals?** If yes, JSONB. If a user
might filter or sort by it, it is a column.

Full detail in ['database.md'](database.md).

---

## 8. Decisions deliberately left open

These are unresolved on purpose. Each is listed with what it blocks and what
information would resolve it. Pretending to have decided would be worse than
saying "not yet".

### Authentication mechanism

**Blocks:** sign-in, per-user data scoping, publishing anything to real users.
**Status:** the 'users' table has no password, token or session column.
**Why open:** session cookies, JWT, an external identity provider (Auth0,
Clerk, Cognito) and SSO for clubs are genuinely different products with different
build costs and different multitenancy implications.
**What would resolve it:** whether club SSO (SAML/OIDC with a federation) is a
requirement in the first year. If it is, an external IdP is the answer and
building a credential system would be wasted work.

### Authorization granularity

**Blocks:** scoping what a coach may see versus an analyst.
**Status:** 'MembershipRole' has five roles and two coarse predicates
('can_manage_organization', 'can_manage_analysis').
**Why open:** a full permission matrix is real complexity. Whether it is needed
depends on whether customers ask for per-team or per-player access control, or
whether five roles suffice for a long time.

### Pitch calibration

**Blocks:** heatmaps and distance metrics that are comparable across matches.
**Status:** 'PitchCoordinate' is documented as normalised pitch metres, and the
pixel→metre mapping is explicitly an ML concern.
**Why open:** manual (four clicked points) versus automatic (pitch-line
detection) is a product and UX decision as much as a technical one, since manual
calibration pushes work onto the coach.

### Tracking observation storage

**Blocks:** implementing the tracking stage.
**Status:** 'TrackingDataset.storage_key' accommodates either strategy.
**Why open:** it depends on measured query patterns. If coaches scrub through
tracking frame by frame, a queryable table wins. If they only look at derived
heatmaps and metrics, a columnar file wins by a wide margin.

### Sports beyond football

**Blocks:** basketball, rugby, any second sport.
**Status:** 'Team.sport' is a free string, and 'MetricCategory' is a football-ish
vocabulary. Pitch geometry and metric definitions do not transfer between
sports.
**Why open:** choosing a sport-agnostic abstraction before implementing a second
sport would be designing for an unmeasured requirement. Phase 1 should implement
football properly and *observe* what generalises.

### Pagination strategy

**Blocks:** very large collections.
**Status:** offset pagination, with 'meta' as an object rather than a bare array
so a cursor can be added without breaking clients.
**Why open:** cursor pagination is more correct under concurrent writes but
harder for the frontend. Offset is adequate until measured otherwise.

### Real-time progress delivery

**Blocks:** a progress bar that updates smoothly on long analyses.
**Status:** polling 'GET /analysis-runs/{id}'.
**Why open:** SSE, WebSockets and polling are all fine. A 90-minute video is
hours of wall-clock processing; a 5-second poll is not the bottleneck, and
polling costs no infrastructure. Revisit when the worker exists and real timings
are known — not before.

---

## 9. Frontend architecture in brief

Feature-oriented App Router structure, with real route groups and real
boundaries.

'''
src/
├── app/
│   ├── (marketing)/    public pages
│   ├── (auth)/         sign-in, invitation acceptance
│   └── (dashboard)/    authenticated shell
├── features/           one directory per capability
├── components/         shared primitives (ui/, charts/, video/, sports/)
├── hooks/              shared hooks
├── lib/                api client, config, errors
├── services/           per-capability API modules
├── types/              api contract + domain vocabulary
└── styles/             design tokens
'''

Two rules carry the weight:

1. **Feature code may not import another feature's internals.** Cross-feature
   reuse goes through 'index.ts' or is promoted to a shared layer. Without this
   the 'features/' tree degrades into a second, worse 'components/' tree.
2. **All network I/O goes through 'lib/api-client.ts'.** Feature code calls
   'api.*'; it never calls 'fetch'. That single choke point is what makes adding
   auth headers, tracing or a generated client a one-file change.

Full detail in ['frontend.md'](frontend.md).

---

## 10. Local development

One command set, one infrastructure container, no containerised application code.

The Next.js and FastAPI processes run natively so that hot reload and a
debugger work normally. Only PostgreSQL runs in Docker, because it is the one
piece of infrastructure that genuinely benefits from containerisation — no
developer wants to manage a local PostgreSQL cluster by hand.

'''bash
make install     # backend venv + frontend node_modules
make db-up       # PostgreSQL only
make migrate     # Alembic upgrade head
make backend-dev # :8000
make frontend-dev # :3000
make check       # lint + typecheck + tests
'''

Full detail, including running the integration tests, in
['../product/local-development.md'](../product/local-development.md).

---

## 11. Future scaling path

Ordered by what would trigger each step. **None of these should be done
speculatively.**

| Trigger                                                  | Step                                                                  | Architectural change required |
| -------------------------------------------------------- | --------------------------------------------------------------------- | ----------------------------- |
| Processing loads become noticeable in the API process     | Extract the worker: Celery + Redis, one new adapter                    | None — the port exists        |
| Video storage exceeds one machine's disk                  | S3-compatible storage: one adapter, 'SPA_STORAGE_BACKEND=s3'           | None — the port exists        |
| Metrics queries slow as seasons accumulate               | Add indexes, then pre-aggregate per match                              | Schema migration only         |
| Tracking observations become the dominant storage cost    | Move to columnar files in object storage                               | 'storage_key' already exists  |
| GPU inference is needed                                   | Worker pool with GPU hosts, queue split by stage                       | Adapter configuration only    |
| Read load on the API becomes the bottleneck               | Read replicas, separate read models for dashboards                     | Repository implementations    |
| Real-time updates become a product requirement            | SSE or WebSockets for analysis progress                                | One new endpoint              |
| One domain grows a genuinely independent release cadence  | Extract that domain as a service; the boundary is already drawn        | Boundary exists; adapter work |

The last row is the point of the whole design: the option to extract is
preserved without paying for it today.

---

## 12. Related documents

| Document                                     | Covers                                                |
| -------------------------------------------- | ----------------------------------------------------- |
| ['frontend.md'](frontend.md)                 | Next.js structure, feature boundaries, API contract    |
| ['backend.md'](backend.md)                   | Layering, ports and adapters, error contract, testing  |
| ['database.md'](database.md)                 | Entity relationships, JSONB policy, indexing, migrations |
| ['video-processing.md'](video-processing.md) | The asynchronous pipeline in depth                     |