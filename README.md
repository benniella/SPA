# SPA — Sport Performance Analysis

**Turn sports video into performance data.**

SPA is an AI-powered sports performance analysis platform that turns sports
video into structured performance data for athletes, coaches, teams and
analysts.

> **Status: Phase 0 — repository foundation only.**
> The architecture, boundaries, configuration, database foundation and tooling
> are in place. No product features, no computer vision, no analytics and no
> dashboard have been implemented. See
> [docs/architecture/overview.md](docs/architecture/overview.md) for the
> roadmap.

---

## What is in this repository

| Path               | Purpose                                                                 |
| ------------------ | ----------------------------------------------------------------------- |
| 'frontend/'        | Next.js (App Router) + React + TypeScript application                   |
| 'backend/'         | FastAPI + SQLAlchemy 2.x + Alembic application (modular monolith)       |
| 'ml/'              | Python computer-vision / tracking / analysis boundary (experimentation) |
| 'docs/'            | Architecture, product and API documentation                             |
| 'scripts/'         | Developer and CI helper scripts                                         |
| '.github/'         | CI workflows                                                            |
| 'docker-compose.yml' | Local PostgreSQL                                                        |
| 'Makefile'         | Single entry point for all developer commands                           |

---

## Architecture in one picture

'''
Next.js  ──►  FastAPI  ──►  PostgreSQL
                 │
                 │  (Phase 1+, asynchronous — never inside the request)
                 ▼
        Object Storage ──► Job ──► ML / Video Worker ──► Analysis Results
                                                              │
                                                              ▼
                                                          PostgreSQL
                                                              │
                                                              ▼
                                                          Next.js
'''

The frontend **never** talks to PostgreSQL. All access goes through the
versioned HTTP API ('/api/v1'). Video processing is **never** performed
synchronously inside an HTTP request.

---

## Quick start

Prerequisites: **Docker**, **Python 3.11+**, **Node.js 20+**, **GNU Make**.

'''bash
# 1. Configure environment
cp .env.example .env
cp backend/.env.example backend/.env
cp frontend/.env.example frontend/.env.local

# 2. Install dependencies
make install

# 3. Start PostgreSQL
make db-up

# 4. Apply migrations
make migrate

# 5. Run the API            (http://localhost:8000/docs)
make backend-dev

# 6. Run the web app        (http://localhost:3000)
make frontend-dev
'''

Postgres is mapped to host port **5432** by default. If that port is already
taken on your machine, set 'POSTGRES_PORT=5442' in '.env' and update
'DATABASE_URL' in 'backend/.env' accordingly.

### Verify everything works

'''bash
make check     # lint + typecheck + tests on both applications
'''

### Full command reference

Run 'make help' to list every available target. The most common ones:

| Command                  | What it does                                            |
| ------------------------ | ------------------------------------------------------- |
| 'make install'           | Install backend + frontend dependencies                 |
| 'make db-up' / 'db-down' | Start / stop local PostgreSQL                           |
| 'make migrate'           | Apply Alembic migrations ('alembic upgrade head')        |
| 'make migration m="..."' | Autogenerate a new Alembic revision                     |
| 'make backend-dev'       | Start FastAPI with reload on ':8000'                    |
| 'make frontend-dev'      | Start Next.js dev server on ':3000'                     |
| 'make test'              | Run backend + frontend test suites                      |
| 'make lint' / 'make fmt' | Lint / format both applications                         |
| 'make check'             | Lint + typecheck + tests (the CI gate)                  |

---

## Technology stack

- **Frontend** — Next.js 16 (App Router), React 19, TypeScript (strict),
  Tailwind CSS, ESLint, Prettier, Vitest + Testing Library.
- **Backend** — Python 3.12, FastAPI, Pydantic v2, SQLAlchemy 2.x, Alembic,
  Uvicorn, pytest, Ruff, mypy.
- **Database** — PostgreSQL 16.
- **ML / CV** — Python, deliberately isolated from the API process.

---

## Documentation

- [Architecture overview](docs/architecture/overview.md)
- [Frontend architecture](docs/architecture/frontend.md)
- [Backend architecture](docs/architecture/backend.md)
- [Database & domain model](docs/architecture/database.md)
- [Video-processing architecture](docs/architecture/video-processing.md)
- [API documentation](docs/api/README.md)
- [Local development](docs/product/local-development.md)