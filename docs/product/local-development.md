# Local Development

Everything needed to run SPA on one machine, and to verify that it works.

---

## 1. Prerequisites

| Tool        | Version    | Notes                                          |
| ----------- | ---------- | ---------------------------------------------- |
| Docker      | any recent | Only for PostgreSQL                            |
| Python      | 3.11+      | 3.12 tested                                    |
| Node.js     | 20.9+      | Next.js 16 requires it                         |
| GNU Make    | any        | The single entry point for every task           |

Check:

'''bash
docker --version && docker compose version
python3 --version
node --version
make --version
'''

---

## 2. First-time setup

'''bash
git clone <repository> spa && cd spa

# Environment files. Each is created from a committed example; none is committed.
cp .env.example .env                     # infrastructure (Postgres credentials/port)
cp backend/.env.example backend/.env     # API configuration
cp frontend/.env.example frontend/.env.local

# Dependencies: backend virtualenv + frontend node_modules
make install
'''

'make env' does the three 'cp' commands for you and is idempotent — it will not
overwrite an existing file.

### A note on the PostgreSQL port

The compose file maps the container's 5432 to 'POSTGRES_PORT' on the host
(default 5432). **If another PostgreSQL already listens on 5432**, change it:

'''bash
# .env
POSTGRES_PORT=5442

# backend/.env — must match
SPA_DATABASE_URL=postgresql+psycopg://spa:spa@localhost:5442/spa
'''

Check with:

'''bash
(nc -z localhost 5432 && echo "5432 in use") || echo "5432 free"
'''

---

## 3. Running the stack

Four terminals, or four background commands.

'''bash
# 1. PostgreSQL and KeyDB (the containerised infrastructure)
make db-up

# 2. Database schema
make migrate

# 3. FastAPI  ->  http://localhost:8000/docs
make backend-dev

# 4. Next.js  ->  http://localhost:3000
make frontend-dev
'''

To run processing asynchronously, set 'SPA_JOB_BACKEND=queued' in 'backend/.env'
and start the worker in a fifth terminal:

'''bash
make worker-dev
'''

With 'SPA_JOB_BACKEND=inline' (the default) the API writes the job row but nothing
delivers it, so no worker and no KeyDB are needed. That is enough to exercise the
asynchronous contract by hand; the worker is what actually runs a job.

Then open:

| URL                                  | What                                              |
| ------------------------------------ | ------------------------------------------------- |
| 'http://localhost:3000'               | Next.js marketing page                            |
| 'http://localhost:3000/dashboard'     | Dashboard — includes a live API/DB status card     |
| 'http://localhost:8000/docs'          | Swagger UI                                        |
| 'http://localhost:8000/redoc'         | ReDoc                                             |
| 'http://localhost:8000/openapi.json'  | The OpenAPI document                              |

The status card on '/dashboard' is a real check: it calls the readiness endpoint,
which queries PostgreSQL. If it shows **Operational**, Next.js → FastAPI →
PostgreSQL is working.

### Why only PostgreSQL is containerised

The Next.js and FastAPI processes run natively so hot reload and a debugger work
normally. Containerising them would add rebuild cycles on every dependency change
and complicate attaching a debugger — a cost paid on every working day to solve
a problem (environment drift) that only appears at deploy time.

PostgreSQL is containerised because a local cluster managed by hand has real
cost and no benefit.

---

## 4. Command reference

'make help' lists every target. The ones that matter:

### Setup

| Command                  | What it does                                        |
| ------------------------ | --------------------------------------------------- |
| 'make install'           | Backend venv + frontend 'node_modules'               |
| 'make env'               | Create '.env' files from the examples if missing     |
| 'make clean'             | Remove caches and build output                       |

### Infrastructure

| Command           | What it does                                     |
| ----------------- | ------------------------------------------------ |
| 'make db-up'      | Start PostgreSQL and wait for it to be healthy    |
| 'make db-down'    | Stop it, keeping the data volume                  |
| 'make db-reset'   | **Destroy** the data volume and recreate it       |
| 'make db-shell'   | 'psql' session                                    |

### Database

| Command                        | What it does                            |
| ------------------------------ | --------------------------------------- |
| 'make migrate'                 | Apply all pending migrations            |
| 'make migrate-down'            | Roll back one revision                  |
| 'make migration m="add teams"' | Autogenerate a revision                 |

Always review an autogenerated migration before committing it. Alembic cannot
know that a dropped column was still in use.

### Applications

| Command              | What it does                          |
| -------------------- | ------------------------------------- |
| 'make backend-dev'   | uvicorn with '--reload' on :8000      |
| 'make worker-dev'    | The processing worker (needs KeyDB)   |
| 'make frontend-dev'  | Next.js dev server on :3000           |
| 'make frontend-build'| Production build                      |

### Quality

| Command                   | What it does                                    |
| ------------------------- | ----------------------------------------------- |
| 'make test'               | Backend + frontend test suites                   |
| 'make lint'               | Ruff (backend) + ESLint (frontend)               |
| 'make fmt'                | Ruff format + Prettier                           |
| 'make typecheck'          | mypy + 'tsc --noEmit'                            |
| 'make check'              | **The CI gate**: lint + typecheck + test         |
| 'make backend-test'       | pytest unit tests only                           |
| 'make backend-typecheck'  | mypy on 'app/'                                   |
| 'make frontend-test'      | Vitest                                           |

---

## 5. Testing

### Backend

'''bash
make backend-test        # unit tests: no database, ~2 seconds
'''

Unit tests cover the domain, the use cases (against in-memory fakes) and the HTTP
contract. They need nothing running.

**Integration tests need PostgreSQL** and run against **their own database**, so
a test run can never write to the database you are using:

'''bash
# One-time: create the test database
docker exec spa-postgres psql -U spa -d postgres -c "CREATE DATABASE spa_test OWNER spa;"

# Apply migrations to it
cd backend && SPA_DATABASE_URL="postgresql+psycopg://spa:spa@localhost:5442/spa_test" \
  .venv/bin/alembic upgrade head && cd ..

# Run them
cd backend && SPA_TEST_DATABASE_URL="postgresql+psycopg://spa:spa@localhost:5442/spa_test" \
  .venv/bin/pytest -m integration && cd ..
'''

'conftest.py' reads 'SPA_TEST_DATABASE_URL' and **overwrites** 'SPA_DATABASE_URL'
with it. That is deliberate. Each integration test truncates every table first,
so tests do not depend on execution order or on what a previous run left behind.

Why integration tests use real PostgreSQL rather than a substitute: the schema
depends on JSONB round-trips, check constraints, 'ON DELETE CASCADE' and 'uuid'
columns. A substitute would test a different database than the one that runs in
production.

### Frontend

'''bash
make frontend-test       # Vitest, jsdom
'''

---

## 6. Verifying the asynchronous contract by hand

The most instructive thing to do in Phase 0. It proves that analysis is
asynchronous end to end.

'''bash
ORG=$(curl -s -X POST localhost:8000/api/v1/organizations \
  -H 'content-type: application/json' \
  -d '{"name":"Demo FC","slug":"demo-fc"}' | jq -r .id)

# 1. Reserve an upload slot — notice no bytes are sent
TICKET=$(curl -s -X POST localhost:8000/api/v1/videos \
  -H 'content-type: application/json' \
  -d '{"organization_id":"'$ORG'","filename":"match.mp4","content_type":"video/mp4"}')

VIDEO_ID=$(echo "$TICKET" | jq -r .video_id)
UPLOAD_URL=$(echo "$TICKET" | jq -r .upload_url)

# 2. Upload bytes straight to storage
curl -X PUT "$UPLOAD_URL" -H 'content-type: video/mp4' --data-binary "fake video bytes"

# 3. Confirm — 202, and an ingest job is dispatched
curl -i -X POST "localhost:8000/api/v1/videos/$VIDEO_ID/complete" \
  -H 'content-type: application/json' -d '{"size_bytes":16}'

# 4. Request analysis — 202 + Location, in milliseconds
curl -i -X POST localhost:8000/api/v1/analysis-runs \
  -H 'content-type: application/json' \
  -d '{"video_id":"'$VIDEO_ID'","organization_id":"'$ORG'"}'

# 5. Poll it
curl -s "localhost:8000/api/v1/analysis-runs/<run-id>?organization_id=$ORG" | jq
'''

Watch the API log: it prints 'job dispatched' with the job kind, because
'InlineJobDispatcher' records every dispatch and executes none. In Phase 0 the
run stays 'queued' forever — correctly, because no worker exists. That is the
honest state of the system, and it is visible rather than hidden behind a fake
completion.

Also worth doing: request analysis for a video whose upload never completed. It
returns **409**, not a job — proving the lifecycle guard is enforced by the
domain rather than by hope.

---

## 7. Troubleshooting

### The API fails to start with a settings error

'SPA_DATABASE_URL' is required and has no default — a misconfigured environment
fails loudly instead of silently connecting to an unintended database. Ensure
'backend/.env' exists ('make env').

### 'asyncpg' / 'greenlet' import error

The async SQLAlchemy ORM needs 'greenlet'. 'pyproject.toml' declares
'sqlalchemy[asyncio]', so a fresh 'make install' provides it. If you installed
before that was declared:

'''bash
cd backend && .venv/bin/pip install "sqlalchemy[asyncio]>=2.0.36,<2.2"
'''

### 'Could not translate host name' or connection refused

PostgreSQL is not up or the port is wrong:

'''bash
docker compose ps
docker compose logs postgres | tail
'''

Confirm 'POSTGRES_PORT' in '.env' matches the port in
'backend/.env''s 'SPA_DATABASE_URL'.

### 'target database is being accessed by other users'

Something holds a connection — usually a running uvicorn or the test suite.
Stop them, then:

'''bash
docker exec spa-postgres psql -U spa -d postgres \
  -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname='spa';"
'''

### Integration tests hang or fail with authentication errors

Check 'SPA_TEST_DATABASE_URL' — it must point at the **test** database, not your
development one.

### The dashboard status card says "Unreachable"

'NEXT_PUBLIC_API_URL' in 'frontend/.env.local' must match where the backend is
listening. Note that 'NEXT_PUBLIC_' variables are inlined at build time, so
**restart the dev server** after changing one.

### 'Module not found: Can't resolve '@/…''

The path alias is configured in both 'tsconfig.json' and 'vitest.config.ts'. If
you added a new alias, add it to both.

### ESLint: 'TypeError: Converting circular structure to JSON'

You are on an older 'eslint.config.mjs' that used 'FlatCompat'.
'eslint-config-next' v16 ships native flat configs and the compat shim crashes on
the circular plugin references Next's config legitimately contains. Use the
direct imports (see the committed config).

---

## 8. Editor setup

Recommended, not required:

* **VS Code extensions:** Python (Pylance), Ruff, ESLint, Prettier, Tailwind CSS
  (for when it lands).
* **Format on save** with Prettier for the frontend and Ruff for the backend.
  Both are configured in the repository, so the editor should defer to them
  rather than its own defaults — otherwise formatting fights between the editor
  and 'make fmt'.
* **'make check' before pushing.** It is exactly what CI runs, so a green local
  run means a green build.

---

## 9. Where to look next

| Question                                          | Document                                                    |
| ------------------------------------------------- | ----------------------------------------------------------- |
| Why is the code organised this way?                | ['../architecture/overview.md'](../architecture/overview.md) |
| How does the frontend structure work?              | ['../architecture/frontend.md'](../architecture/frontend.md) |
| How do the backend layers relate?                  | ['../architecture/backend.md'](../architecture/backend.md)   |
| What are the tables and relationships?             | ['../architecture/database.md'](../architecture/database.md) |
| How will video actually be processed?              | ['../architecture/video-processing.md'](../architecture/video-processing.md) |
| How do I call the API?                             | ['../api/README.md'](../api/README.md)                       |