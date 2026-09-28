"""Players and player-team registration."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime

from app.domain.shared import OrganizationId, PlayerId, TeamId, new_id, utcnow


@dataclass(slots=True)
class Player:
    """An athlete.

    A player belongs to the organization, not to a team: players transfer
    between squads, and a transfer must not rewrite or orphan the performance
    history attached to the player.
    """

    organization_id: OrganizationId
    display_name: str
    id: PlayerId = field(default_factory=lambda: PlayerId(new_id()))
    date_of_birth: date | None = None
    external_ref: str | None = None
    created_at: datetime = field(default_factory=utcnow)
    updated_at: datetime = field(default_factory=utcnow)

    def __post_init__(self) -> None:
        if not self.display_name.strip():
            raise ValueError("Player display_name must not be empty.")

    @property
    def age_years(self) -> int | None:
        if self.date_of_birth is None:
            return None
        today = utcnow().date()
        had_birthday = (today.month, today.day) >= (
            self.date_of_birth.month,
            self.date_of_birth.day,
        )
        return today.year - self.date_of_birth.year - (0 if had_birthday else 1)

    def rename(self, display_name: str) -> None:
        if not display_name.strip():
            raise ValueError("Player display_name must not be empty.")
        self.display_name = display_name
        self.updated_at = utcnow()


@dataclass(slots=True)
class TeamMembership:
    """A player's registration in a team for a period of time.

    Modelled as a record with a validity window rather than a foreign key on
    ' 'Player' ': analysis of a past match must resolve the squad as it was on
    that date, not as it is today. This is the difference between a correct
    performance history and one that silently changes after every transfer.
    """

    team_id: TeamId
    player_id: PlayerId
    joined_on: date
    left_on: date | None = None
    id: object = None
    # Shirt number is scoped to the registration period, not the player.
    shirt_number: int | None = None

    def __post_init__(self) -> None:
        if self.left_on is not None and self.left_on < self.joined_on:
            raise ValueError("left_on cannot be earlier than joined_on.")
        if self.shirt_number is not None and not (1 <= self.shirt_number <= 99):
            raise ValueError("shirt_number must be between 1 and 99.")

    def covers(self, on_date: date) -> bool:
        """Whether the player was registered to the team on ' 'on_date' '."""
        if on_date < self.joined_on:
            return False
        return self.left_on is None or on_date <= self.left_on

    @property
    def is_active(self) -> bool:
        return self.left_on is None
