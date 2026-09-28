"""Alembic environment.

Migrations run with a **synchronous** psycopg connection derived from the same
' 'DATABASE_URL' ' the application uses, so there is exactly one source of truth
for the database location.

' 'target_metadata' ' comes from the application's ' 'Base' ', which is what makes
' 'alembic revision --autogenerate' ' able to see new models. ' 'load_models()' ' is
called explicitly so that a model module that was never imported cannot be
silently missing from a generated migration.
"""

from __future__ import annotations

import os
import sys
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy import engine_from_config, pool

# Make 'app' importable when Alembic is invoked from the backend directory.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import get_settings
from app.infrastructure.database import load_models
from app.infrastructure.database.base import Base
from app.infrastructure.database.engine import to_sync_database_url

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

load_models()
target_metadata = Base.metadata


def _database_url() -> str:
    """Resolve the migration URL.

    ' 'ALEMBIC_DATABASE_URL' ' overrides everything, which is how CI and a
    throwaway test database point migrations somewhere else without touching
    application settings.
    """
    override = os.getenv("ALEMBIC_DATABASE_URL")
    if override:
        return to_sync_database_url(override)
    return to_sync_database_url(get_settings().database_url)


def run_migrations_offline() -> None:
    """Emit SQL to stdout instead of executing it (' 'alembic upgrade --sql' ')."""
    context.configure(
        url=_database_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Apply migrations against a live database."""
    configuration = config.get_section(config.config_ini_section, {})
    configuration["sqlalchemy.url"] = _database_url()

    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            # Detect type and default changes; without these, a subtle schema
            # drift goes unnoticed until it breaks at runtime.
            compare_type=True,
            compare_server_default=True,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
