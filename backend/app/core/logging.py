"""Logging setup.

One place decides log format and level so that every module can simply use
' 'logging.getLogger(__name__)' '.
"""

from __future__ import annotations

import logging
import sys

from app.core.config import Settings

_LOG_FORMAT = "%(asctime)s %(levelname)-8s %(name)s %(message)s"


def configure_logging(settings: Settings) -> None:
    """Configure root logging once, at application startup.

    Development gets human-readable output; every other environment gets a
    single-line format that a log collector can parse.
    """
    level = logging.DEBUG if settings.debug and settings.is_local else logging.INFO

    logging.basicConfig(
        level=level,
        format=_LOG_FORMAT,
        stream=sys.stdout,
        force=True,
    )

    # SQLAlchemy echoes statements via its own logger; only when explicitly asked.
    logging.getLogger("sqlalchemy.engine").setLevel(
        logging.INFO if settings.db_echo else logging.WARNING
    )
    # Access logs are informative locally and noise in a deployed environment,
    # where the reverse proxy already records requests.
    logging.getLogger("uvicorn.access").setLevel(
        logging.INFO if settings.is_local else logging.WARNING
    )


def get_logger(name: str) -> logging.Logger:
    """Return a module-scoped logger."""
    return logging.getLogger(name)
