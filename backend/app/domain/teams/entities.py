"""Teams: the grouping of players that matches are recorded against."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from app.domain.shared import OrganizationId, Slug, TeamId, new_id, utcnow


@dataclass(slots=True)
class Team:
    """A squad within an organization.

    'sport' is a free string: sport-specific behaviour needs a taxonomy, and
    choosing one before the first sport is implemented would be guessing.
    """

    organization_id: OrganizationId
    name: str
    slug: Slug
    sport: str = "football"
    id: TeamId = field(default_factory=lambda: TeamId(new_id()))
    season: str | None = None
    created_at: datetime = field(default_factory=utcnow)
    updated_at: datetime = field(default_factory=utcnow)

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("Team name must not be empty.")
        if not self.sport.strip():
            raise ValueError("Team sport must not be empty.")

    def rename(self, name: str) -> None:
        if not name.strip():
            raise ValueError("Team name must not be empty.")
        self.name = name
        self.updated_at = utcnow()
