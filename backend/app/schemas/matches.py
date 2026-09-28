"""Match request/response schemas.

The validator enforces the same rule as the 'Match' entity: a fixture must
identify both sides. Expressing it in the contract too means the client gets
a 422 instead of a 500 from a domain invariant.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime

from pydantic import Field, model_validator

from app.schemas.common import ApiModel, PageMeta


class MatchCreate(ApiModel):
    organization_id: uuid.UUID
    played_on: date
    home_team_id: uuid.UUID | None = None
    away_team_id: uuid.UUID | None = None
    home_team_name: str | None = Field(default=None, max_length=200)
    away_team_name: str | None = Field(default=None, max_length=200)
    competition: str | None = Field(default=None, max_length=200)
    is_home: bool = Field(
        default=True,
        description="Whether the organization's own team played at home.",
    )
    venue_name: str | None = Field(default=None, max_length=200)

    @model_validator(mode="after")
    def _both_sides_identified(self) -> MatchCreate:
        if self.home_team_id is None and not self.home_team_name:
            raise ValueError("Provide home_team_id or home_team_name.")
        if self.away_team_id is None and not self.away_team_name:
            raise ValueError("Provide away_team_id or away_team_name.")
        return self


class MatchRead(ApiModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    played_on: date
    home_team_id: uuid.UUID | None
    away_team_id: uuid.UUID | None
    home_team_name: str | None
    away_team_name: str | None
    competition: str | None
    is_home: bool
    venue_name: str | None
    created_at: datetime
    updated_at: datetime

    @property
    def label(self) -> str:
        home = self.home_team_name or "Home"
        away = self.away_team_name or "Away"
        return f"{home} vs {away}"


class MatchList(ApiModel):
    items: list[MatchRead]
    meta: PageMeta
