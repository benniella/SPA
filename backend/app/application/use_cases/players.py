"""Player use cases."""

from __future__ import annotations

from datetime import date

from app.application.ports.unit_of_work import UnitOfWork
from app.core.errors import NotFoundError
from app.domain.players.entities import Player
from app.domain.shared import OrganizationId, PlayerId, TeamId


async def create_player(
    uow: UnitOfWork,
    *,
    organization_id: OrganizationId,
    display_name: str,
    date_of_birth: date | None = None,
    external_ref: str | None = None,
) -> Player:
    async with uow:
        organization = await uow.organizations.get(organization_id)
        if organization is None:
            raise NotFoundError(f"Organization {organization_id} does not exist.")

        player = Player(
            organization_id=organization_id,
            display_name=display_name,
            date_of_birth=date_of_birth,
            external_ref=external_ref,
        )
        await uow.players.add(player)
        await uow.commit()
        return player


async def get_player(
    uow: UnitOfWork,
    *,
    organization_id: OrganizationId,
    player_id: PlayerId,
) -> Player:
    async with uow:
        player = await uow.players.get(player_id)
        if player is None or player.organization_id != organization_id:
            raise NotFoundError(f"Player {player_id} does not exist.")
        return player


async def list_players(
    uow: UnitOfWork,
    *,
    organization_id: OrganizationId,
    team_id: TeamId | None = None,
    on_date: date | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[Player]:
    """List players, optionally as the squad was constituted on a given date.

    The ' 'on_date' ' parameter is why squad membership is modelled with a validity
    window: a season review must resolve the squad correctly for each match.
    """
    async with uow:
        if team_id is not None:
            return await uow.players.list_for_team(
                team_id, on_date=on_date, limit=limit, offset=offset
            )
        return await uow.players.list_for_organization(organization_id, limit=limit, offset=offset)
