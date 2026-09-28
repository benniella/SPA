# Developer and CI entry points.

SHELL := /bin/bash
.DEFAULT_GOAL := help

BACKEND_DIR  := backend
FRONTEND_DIR := frontend
ML_DIR       := ml
VENV         := $(BACKEND_DIR)/.venv
PY           := $(VENV)/bin/python
PIP          := $(VENV)/bin/pip

PYTHON       ?= python3
NPM          ?= npm
COMPOSE      ?= docker compose
POSTGRES_PORT ?= 5432

.PHONY: help
help: ## Show this help
	@grep -hE '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-22s\033[0m %s\n", $$1, $$2}'

# Bootstrap

.PHONY: install
install: backend-install frontend-install ## Install all dependencies

.PHONY: env
env: ## Create local .env files from the checked-in examples
	@[ -f .env ] || cp .env.example .env
	@[ -f $(BACKEND_DIR)/.env ] || cp $(BACKEND_DIR)/.env.example $(BACKEND_DIR)/.env
	@[ -f $(FRONTEND_DIR)/.env.local ] || cp $(FRONTEND_DIR)/.env.example $(FRONTEND_DIR)/.env.local
	@echo "Environment files ready."

.PHONY: backend-install
backend-install: ## Create the backend virtualenv and install dependencies
	@test -d $(VENV) || $(PYTHON) -m venv $(VENV)
	$(PIP) install --upgrade pip
	$(PIP) install -e "$(BACKEND_DIR)[dev]"

.PHONY: frontend-install
frontend-install: ## Install frontend dependencies
	cd $(FRONTEND_DIR) && $(NPM) install

.PHONY: db-up
db-up: ## Start local PostgreSQL and KeyDB
	$(COMPOSE) up -d postgres keydb
	@echo "Waiting for PostgreSQL to become healthy..."
	@until [ "$$($(COMPOSE) ps --format json postgres | grep -c healthy)" -ge 1 ]; do sleep 1; done
	@echo "PostgreSQL is ready on localhost:$(POSTGRES_PORT)."
	@echo "Waiting for KeyDB to become healthy..."
	@until [ "$$($(COMPOSE) ps --format json keydb | grep -c healthy)" -ge 1 ]; do sleep 1; done
	@echo "KeyDB is ready on localhost:$${KEYDB_PORT:-6379}."

.PHONY: db-down
db-down: ## Stop local PostgreSQL (keeps the data volume)
	$(COMPOSE) down

.PHONY: db-reset
db-reset: ## Destroy local PostgreSQL data and recreate it (DESTRUCTIVE)
	$(COMPOSE) down -v
	$(MAKE) db-up

.PHONY: db-shell
db-shell: ## Open a psql shell against the local database
	$(COMPOSE) exec postgres psql -U spa -d spa

.PHONY: migrate
migrate: ## Apply all pending database migrations
	cd $(BACKEND_DIR) && .venv/bin/alembic upgrade head

.PHONY: migrate-down
migrate-down: ## Roll back the most recent migration
	cd $(BACKEND_DIR) && .venv/bin/alembic downgrade -1

.PHONY: migration
migration: ## Autogenerate a migration: make migration m="add teams table"
	@test -n "$(m)" || { echo 'Usage: make migration m="description"'; exit 1; }
	cd $(BACKEND_DIR) && .venv/bin/alembic revision --autogenerate -m "$(m)"

.PHONY: backend-dev
backend-dev: ## Run the FastAPI dev server on :8000
	cd $(BACKEND_DIR) && .venv/bin/uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

.PHONY: worker-dev
worker-dev: ## Run the processing worker (requires SPA_JOB_BACKEND=queued and KeyDB)
	cd $(BACKEND_DIR) && .venv/bin/python -m app.worker.main

.PHONY: backend-test
backend-test: ## Run backend tests
	cd $(BACKEND_DIR) && .venv/bin/pytest

.PHONY: ml-test
ml-test: ## Run the computer-vision test suite (ml/)
	$(VENV)/bin/python -m pytest ml/tests -q -p no:cacheprovider

.PHONY: ml-lint
ml-lint: ## Lint the computer-vision code (ruff check)
	$(VENV)/bin/ruff check ml

.PHONY: ml-typecheck
ml-typecheck: ## Type-check the computer-vision code (mypy)
	$(VENV)/bin/mypy ml/detection ml/tracking ml/video ml/pipelines

.PHONY: integration-test
integration-test: ## Prepare the test database and run the integration tests
	scripts/setup-test-db.sh
	cd $(BACKEND_DIR) && \
		SPA_TEST_DATABASE_URL="$${SPA_TEST_DATABASE_URL:-postgresql+psycopg://spa:spa@localhost:$(POSTGRES_PORT)/spa_test}" \
		.venv/bin/pytest -m integration

.PHONY: backend-lint
backend-lint: ## Lint the backend (ruff check)
	cd $(BACKEND_DIR) && .venv/bin/ruff check .

.PHONY: backend-fmt
backend-fmt: ## Format the backend (ruff format + autofix)
	cd $(BACKEND_DIR) && .venv/bin/ruff format . && .venv/bin/ruff check --fix .

.PHONY: backend-typecheck
backend-typecheck: ## Type-check the backend (mypy)
	cd $(BACKEND_DIR) && .venv/bin/mypy app

.PHONY: frontend-dev
frontend-dev: ## Run the Next.js dev server on :3000
	cd $(FRONTEND_DIR) && $(NPM) run dev

.PHONY: frontend-build
frontend-build: ## Production build of the frontend
	cd $(FRONTEND_DIR) && $(NPM) run build

.PHONY: frontend-test
frontend-test: ## Run frontend tests
	cd $(FRONTEND_DIR) && $(NPM) run test

.PHONY: frontend-lint
frontend-lint: ## Lint the frontend
	cd $(FRONTEND_DIR) && $(NPM) run lint

.PHONY: frontend-fmt
frontend-fmt: ## Format the frontend
	cd $(FRONTEND_DIR) && $(NPM) run format

.PHONY: frontend-typecheck
frontend-typecheck: ## Type-check the frontend
	cd $(FRONTEND_DIR) && $(NPM) run typecheck

.PHONY: architecture
architecture: ## Check architectural boundaries (the same script CI runs)
	bash scripts/check-architecture.sh

.PHONY: lint
lint: backend-lint ml-lint frontend-lint ## Lint everything

.PHONY: fmt
fmt: backend-fmt frontend-fmt ## Format everything

.PHONY: typecheck
typecheck: backend-typecheck ml-typecheck frontend-typecheck ## Type-check everything

.PHONY: test
test: backend-test ml-test frontend-test ## Run all test suites

.PHONY: check
check: architecture lint typecheck test ## The CI gate: architecture + lint + typecheck + test

.PHONY: clean
clean: ## Remove build artefacts and caches
	find . -type d -name __pycache__ -prune -exec rm -rf {} + 2>/dev/null || true
	rm -rf $(BACKEND_DIR)/.pytest_cache $(BACKEND_DIR)/.ruff_cache $(BACKEND_DIR)/.mypy_cache
	rm -rf $(FRONTEND_DIR)/.next $(FRONTEND_DIR)/node_modules/.cache
	@echo "Cleaned."