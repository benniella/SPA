"""Database infrastructure: engine, models, mappers, repositories, unit of work.

This package is the only place in the backend that imports SQLAlchemy.
"""

from app.infrastructure.database.base import Base
from app.infrastructure.database.engine import (
    create_engine,
    dispose_engine,
    get_engine,
    get_session_factory,
    session_scope,
)
from app.infrastructure.database.unit_of_work import (
    SqlAlchemyUnitOfWork,
    SqlAlchemyUnitOfWorkFactory,
)

__all__ = [
    "Base",
    "SqlAlchemyUnitOfWork",
    "SqlAlchemyUnitOfWorkFactory",
    "create_engine",
    "dispose_engine",
    "get_engine",
    "get_session_factory",
    "session_scope",
]


def load_models() -> None:
    """Import every model module so that ' 'Base.metadata' ' is complete.

    Alembic autogenerate and ' 'create_all' ' both inspect ' 'Base.metadata' '; a
    model that was never imported is silently absent from a migration. Calling
    this explicitly is a deliberate footgun-removal.
    """
    from app.infrastructure.database import models  # noqa: F401
