#!/usr/bin/env bash
#
# Check architectural boundaries enforced by CI.

set -uo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

FAILURES=0

pass() { printf '  \033[32mPASS\033[0m  %s\n' "$1"; }
fail() {
  printf '  \033[31mFAIL\033[0m  %s\n' "$1"
  printf '        %s\n' "$2"
  FAILURES=$((FAILURES + 1))
}

echo "Checking architectural boundaries"
echo

if grep -rEn "^\s*(from|import)\s+(fastapi|sqlalchemy|pydantic|alembic)" \
     backend/app/domain/ 2>/dev/null; then
  fail "domain layer is framework-free" \
       "backend/app/domain/ must not import FastAPI, SQLAlchemy, Pydantic or Alembic"
else
  pass "domain layer is framework-free"
fi

if grep -rEn "^\s*(from|import)\s+fastapi" backend/app/application/ 2>/dev/null; then
  fail "application layer is transport-free" \
       "backend/app/application/ must not import FastAPI"
else
  pass "application layer is transport-free"
fi

if grep -rEn "^\s*(from|import)\s+sqlalchemy" backend/app/domain/ backend/app/schemas/ 2>/dev/null; then
  fail "SQLAlchemy is confined to infrastructure" \
       "SQLAlchemy must not appear in the domain or schema layers"
else
  pass "SQLAlchemy is confined to infrastructure"
fi

if grep -rEn "^\s*(from|import)\s+['\"]?(pg|postgres|mysql2|sqlite3|mongodb|prisma)" \
     frontend/src/ 2>/dev/null; then
  fail "frontend has no database client" \
       "the frontend must reach data only through the FastAPI backend"
else
  pass "frontend has no database client"
fi

if grep -rEn "session\.(execute|commit|flush|add)\(" backend/app/api/ \
     --exclude=health.py 2>/dev/null; then
  fail "route handlers delegate to use cases" \
       "found direct session use in a route handler (health.py is exempt)"
else
  pass "route handlers delegate to use cases"
fi

if git ls-files 2>/dev/null | grep -qE "^\.env$|/\.env$|\.env\.local$|/\.env\.local$"; then
  fail "no environment files are tracked" \
       "a .env file is in git; secrets must not be committed"
else
  pass "no environment files are tracked"
fi

if git ls-files ml/models 2>/dev/null | grep -vqE "README.md|\.gitkeep"; then
  fail "no model artefacts are committed" \
       "see ml/models/README.md for the expected convention"
else
  pass "no model artefacts are committed"
fi

echo
if [[ "$FAILURES" -gt 0 ]]; then
  printf '\033[31m%d architectural rule(s) violated.\033[0m\n' "$FAILURES"
  echo "See docs/architecture/overview.md for why each rule exists."
  exit 1
fi

printf '\033[32mAll architectural rules hold.\033[0m\n'