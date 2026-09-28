"""Team use cases."""

from __future__ import annotations

from app.application.ports.repositories import TeamRepository
from app.application.ports.unit_of_work import UnitOfWork
from app.core.errors import NotFoundError
from app.domain.shared import OrganizationId, Slug, TeamId
from app.domain.teams.entities import Team


async def create_team(
    uow: UnitOfWork,
    *,
    organization_id: OrganizationId,
    name: str,
    slug: str,
    sport: str = "football",
    season: str | None = None,
) -> Team:
    """Create a team inside an organization.

    The organization is resolved first so that a team can never be created
    against a workspace that does not exist — a referential guarantee the
    database enforces too, but failing here produces a useful error message.
    """
    async with uow:
        organization = await uow.organizations.get(organization_id)
        if organization is None:
            raise NotFoundError(f"Organization {organization_id} does not exist.")

        team = Team(
            organization_id=organization_id,
            name=name,
            slug=Slug(slug),
            sport=sport,
            season=season,
        )
        await uow.teams.add(team)
        await uow.commit()
        return team


async def get_team(
    uow: UnitOfWork,
    *,
    organization_id: OrganizationId,
    team_id: TeamId,
) -> Team:
    async with uow:
        team = await uow.teams.get(team_id)
        if team is None or team.organization_id != organization_id:
            raise NotFoundError(f"Team {team_id} does not exist.")
        return team


async def list_teams(
    uow: UnitOfWork,
    *,
    organization_id: OrganizationId,
    limit: int = 50,
    offset: int = 0,
) -> list[Team]:
    async with uow:
        return await uow.teams.list_for_organization(organization_id, limit=limit, offset=offset)


def team_repository(uow: UnitOfWork) -> TeamRepository:
    """Typed accessor used by tests that only need the repository."""
    return uow.teams
