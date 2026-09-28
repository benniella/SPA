"""Match use cases."""

from __future__ import annotations

from datetime import date

from app.application.ports.unit_of_work import UnitOfWork
from app.core.errors import NotFoundError
from app.domain.matches.entities import Match, MatchVenue
from app.domain.shared import MatchId, OrganizationId, TeamId


async def create_match(
    uow: UnitOfWork,
    *,
    organization_id: OrganizationId,
    played_on: date,
    home_team_id: TeamId | None = None,
    away_team_id: TeamId | None = None,
    home_team_name: str | None = None,
    away_team_name: str | None = None,
    competition: str | None = None,
    is_home: bool = True,
    venue_name: str | None = None,
) -> Match:
    """Create a fixture.

    Opponents are frequently outside the organization's own team list, which is
    why a name may be supplied instead of a team id — see ' 'Match' '.
    """
    async with uow:
        organization = await uow.organizations.get(organization_id)
        if organization is None:
            raise NotFoundError(f"Organization {organization_id} does not exist.")

        match = Match(
            organization_id=organization_id,
            played_on=played_on,
            home_team_id=home_team_id,
            away_team_id=away_team_id,
            home_team_name=home_team_name,
            away_team_name=away_team_name,
            competition=competition,
            venue=MatchVenue(is_home=is_home, venue_name=venue_name),
        )
        await uow.matches.add(match)
        await uow.commit()
        return match


async def get_match(
    uow: UnitOfWork,
    *,
    organization_id: OrganizationId,
    match_id: MatchId,
) -> Match:
    async with uow:
        match = await uow.matches.get(match_id)
        if match is None or match.organization_id != organization_id:
            raise NotFoundError(f"Match {match_id} does not exist.")
        return match


async def list_matches(
    uow: UnitOfWork,
    *,
    organization_id: OrganizationId,
    limit: int = 50,
    offset: int = 0,
) -> list[Match]:
    async with uow:
        return await uow.matches.list_for_organization(organization_id, limit=limit, offset=offset)
