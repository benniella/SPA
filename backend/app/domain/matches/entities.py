"""Matches: a recorded fixture that videos and analysis runs attach to.

A match is the *organising concept* of SPA: it is the thing a coach opens, and
every video, tracking dataset, metric and report hangs off it. It is deliberately
not the same record as a video, because one match can be covered by several
recordings (multiple cameras, first half / second half files).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime

from app.domain.shared import MatchId, OrganizationId, TeamId, new_id, utcnow


@dataclass(frozen=True, slots=True)
class MatchVenue:
    """Where a match was played.

    ' 'is_home' ' for the organization's own team decides which side of the
    analysis is "us" — a distinction every downstream metric depends on, so it
    is captured here rather than inferred at query time.
    """

    is_home: bool = True
    venue_name: str | None = None


@dataclass(slots=True)
class Match:
    """A fixture between two teams, recorded and analysed.

    ' 'home_team_id' ' / ' 'away_team_id' ' are nullable so that an opponent outside
    the organization's own team list can still be represented by name. Creating
    a shadow team record for every opponent would pollute the teams domain.
    """

    organization_id: OrganizationId
    played_on: date
    id: MatchId = field(default_factory=lambda: MatchId(new_id()))
    home_team_id: TeamId | None = None
    away_team_id: TeamId | None = None
    home_team_name: str | None = None
    away_team_name: str | None = None
    competition: str | None = None
    venue: MatchVenue = field(default_factory=MatchVenue)
    created_at: datetime = field(default_factory=utcnow)
    updated_at: datetime = field(default_factory=utcnow)

    def __post_init__(self) -> None:
        if self.home_team_id is None and not self.home_team_name:
            raise ValueError("A match requires either a home_team_id or a home_team_name.")
        if self.away_team_id is None and not self.away_team_name:
            raise ValueError("A match requires either an away_team_id or an away_team_name.")

    @property
    def label(self) -> str:
        """Human-readable fixture label, e.g. ' 'Home FC vs Away FC' '."""
        home = self.home_team_name or "Home"
        away = self.away_team_name or "Away"
        return f"{home} vs {away}"
