# SPA Documentation

**SPA — Sport Performance Analysis.** Turns sports video into structured
performance data.

> **Phase 0.** This documentation describes the repository foundation. Where a
> decision is deliberately unresolved, it says so rather than implying a design
> that has not been chosen.

---

## Start here

| I want to…                                  | Read                                                       |
| ------------------------------------------- | ---------------------------------------------------------- |
| Run SPA on my machine                       | ['product/local-development.md'](product/local-development.md) |
| Understand the architecture                 | ['architecture/overview.md'](architecture/overview.md)      |
| Understand what SPA is and what is built    | ['product/README.md'](product/README.md)                    |
| Work on the frontend                        | ['architecture/frontend.md'](architecture/frontend.md)      |
| Work on the backend                         | ['architecture/backend.md'](architecture/backend.md)        |
| Understand the database                     | ['architecture/database.md'](architecture/database.md)      |
| Understand video processing                 | ['architecture/video-processing.md'](architecture/video-processing.md) |
| Call the API                                | ['api/README.md'](api/README.md)                            |

---

## The repository in one picture

'''
spa/
├── frontend/     Next.js + React + TypeScript
├── backend/      FastAPI + SQLAlchemy 2.x + Alembic    ──► PostgreSQL
├── ml/           computer-vision boundary (Phase 1)
├── docs/         this
├── scripts/      developer helpers
├── .github/      CI
├── docker-compose.yml    PostgreSQL only
└── Makefile      every command you need
'''

'''
Next.js  ──HTTP──►  FastAPI  ──SQLAlchemy──►  PostgreSQL
                        │
                        │ dispatch only — never process
                        ▼
              Object storage ──► Job ──► ML/video worker ──► PostgreSQL
'''

Two rules that shape everything:

1. **The frontend never touches PostgreSQL.** Its only data source is the
   versioned API.
2. **No HTTP request performs video processing.** The API records intent and
   returns; a worker does the work.

---

## Documentation map

### 'architecture/'

| Document                                        | Contents                                                                                  |
| ----------------------------------------------- | ----------------------------------------------------------------------------------------- |
| ['overview.md'](architecture/overview.md)        | Why a modular monolith · the dependency rule · nine domain boundaries · JSONB policy · **decisions deliberately left open** · future scaling path |
| ['frontend.md'](architecture/frontend.md)        | App Router structure · route groups · feature boundaries · the API contract · design tokens · testing |
| ['backend.md'](architecture/backend.md)          | Four layers · ports and adapters · why domain ≠ ORM · route handlers without logic · error contract |
| ['database.md'](architecture/database.md)        | Entity model · relationship decisions · the metric model · JSONB policy · migrations · tenancy |
| ['video-processing.md'](architecture/video-processing.md) | The pipeline · the 'JobDispatcher' seam · migrating to Celery · versioning and provenance · the unresolved storage question |

### 'api/'

['README.md'](api/README.md) — endpoints, the error contract, the two-step upload
flow, the asynchronous analysis contract, and generating a typed client.

### 'product/'

['README.md'](product/README.md) — what SPA is, who it is for, the capability
roadmap, and the product principles that shaped the architecture.

['local-development.md'](product/local-development.md) — prerequisites, setup,
the full command reference, testing (including the integration-test database),
troubleshooting.

---

## Architectural rules worth knowing before you change anything

1. **Dependencies point inwards.** 'domain/' imports no framework.
   'infrastructure/' is the only place SQLAlchemy appears. Route handlers contain
   no business logic.
2. **The domain and the database are separate models**, joined by explicit
   mappers. A column rename is not an API change.
3. **All frontend network I/O goes through one module** ('lib/api-client.ts').
4. **Feature code may not import another feature's internals.** Reuse goes
   through 'index.ts' or is promoted to a shared layer.
5. **Long-running work is dispatched, never executed, in a request.**
6. **Tenancy is enforced in three places** — storage keys, queries, and a 404
   rather than a 403 for cross-tenant access.
7. **JSONB is for data read and written whole.** Anything a user filters or sorts
   by is a column.

Rationale for each is in ['architecture/overview.md'](architecture/overview.md).
Rule 4's reasoning is in ['architecture/frontend.md'](architecture/frontend.md);
rule 5's is in ['architecture/video-processing.md'](architecture/video-processing.md).

---

## A note on what is not here

This repository contains **no product features, no computer vision, and no
analytics**. The dashboard has no metric tiles, no charts and no player lists.
No endpoint returns a fabricated number, and no screen displays a value that was
not computed from real footage.

This is deliberate. Inventing plausible analytics is the most damaging thing an
early build can do: it makes an empty system look finished, it gets demoed as
though it works, and the lie eventually has to be unwound.

'docs/product/README.md' lists every capability with what blocks it, so
"planned" is always distinguishable from "built".