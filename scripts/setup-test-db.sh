#!/usr/bin/env bash
#
# Prepare the integration-test database.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND_DIR="$REPO_ROOT/backend"

# Default matches the compose file and the port used throughout the docs.
DEFAULT_TEST_URL="postgresql+psycopg://spa:spa@localhost:5442/spa_test"
TEST_URL="${1:-${SPA_TEST_DATABASE_URL:-$DEFAULT_TEST_URL}}"

# Require a dedicated test database.
case "$TEST_URL" in
  *spa_test*)
    ;;
  *)
    echo "error: refusing to prepare '$TEST_URL'." >&2
    echo "       The test database URL must contain 'spa_test' so that it cannot" >&2
    echo "       be confused with a development database." >&2
    exit 1
    ;;
esac

if [[ ! -x "$BACKEND_DIR/.venv/bin/alembic" ]]; then
  echo "error: backend virtualenv not found." >&2
  echo "       Run 'make backend-install' first." >&2
  exit 1
fi

# Derive the psql-visible parts for the CREATE DATABASE step.
DB_NAME="$(printf '%s' "$TEST_URL" | sed -E 's|.*/([^/?]+)(\?.*)?$|\1|')"
PG_USER="$(printf '%s' "$TEST_URL" | sed -E 's|^[^:]+://([^:@]+).*|\1|')"
HOST_PORT="$(printf '%s' "$TEST_URL" | sed -E 's|^[^:]+://[^@]*@([^/]+)/.*|\1|')"
PG_HOST="${HOST_PORT%%:*}"
PG_PORT="${HOST_PORT##*:}"

echo "Preparing test database"
echo "  url:  $TEST_URL"
echo "  name: $DB_NAME"
echo "  host: $PG_HOST:$PG_PORT"
echo

# Database creation is idempotent; migrations provide the actual check.
if command -v docker >/dev/null 2>&1 && docker ps --format '{{.Names}}' | grep -q '^spa-postgres$'; then
  echo "Creating database if absent (via container)..."
  docker exec spa-postgres psql -U "$PG_USER" -d postgres -c "CREATE DATABASE $DB_NAME;" 2>/dev/null \
    || echo "  already exists (or could not be created; continuing)"
elif command -v psql >/dev/null 2>&1; then
  echo "Creating database if absent (via local psql)..."
  PGPASSWORD="${PGPASSWORD:-spa}" psql -h "$PG_HOST" -p "$PG_PORT" -U "$PG_USER" -d postgres \
    -c "CREATE DATABASE $DB_NAME;" 2>/dev/null \
    || echo "  already exists (or could not be created; continuing)"
else
  echo "Neither docker nor psql is available; assuming the database already exists."
fi

echo
echo "Applying migrations..."
(
  cd "$BACKEND_DIR"
  SPA_DATABASE_URL="$TEST_URL" .venv/bin/alembic upgrade head
)

echo
echo "Test database ready. Run the integration suite with:"
echo
echo "  cd backend && SPA_TEST_DATABASE_URL=\"$TEST_URL\" .venv/bin/pytest -m integration"