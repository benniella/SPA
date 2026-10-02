from __future__ import annotations

import uuid
from datetime import date

from fastapi import APIRouter, Depends, Query, status

from app.api.dependencies import CurrentUserDep, UnitOfWorkDep
from app.api.v1.params import Pagination, pagination
from app.api.v1.presenters import player_payload
from app.application.use_cases import players as use_cases
from app.application.use_cases.organizations import require_organization_member
from app.domain.shared import OrganizationId, PlayerId, TeamId
from app.schemas.common import ErrorResponse
from app.schemas.players import PlayerCreate, PlayerList, PlayerRead

router = APIRouter()


@router.post(
    "",
    response_model=PlayerRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create a player",
    responses={404: {"model": ErrorResponse, "description": "Organization not found."}},
)
async def create_player(
    payload: PlayerCreate, user: CurrentUserDep, uow: UnitOfWorkDep
) -> PlayerRead:
    await require_organization_member(
        uow,
        organization_id=OrganizationId(payload.organization_id),
        user_id=user.id,
    )
    player = await use_cases.create_player(
        uow,
        organization_id=OrganizationId(payload.organization_id),
        display_name=payload.display_name,
        date_of_birth=payload.date_of_birth,
        external_ref=payload.external_ref,
    )
    return PlayerRead.model_validate(player_payload(player))


@router.get("", response_model=PlayerList, summary="List players")
async def list_players(
    user: CurrentUserDep,
    uow: UnitOfWorkDep,
    organization_id: uuid.UUID = Query(description="Owning organization."),
    team_id: uuid.UUID | None = Query(
        default=None,
        description="Restrict to a team's squad.",
    ),
    on_date: date | None = Query(
        default=None,
        description=(
            "Resolve the squad as it was registered on this date. Critical for "
            "reviewing a past match after a transfer."
        ),
    ),
    page: Pagination = Depends(pagination),
) -> PlayerList:
    await require_organization_member(
        uow, organization_id=OrganizationId(organization_id), user_id=user.id
    )
    players = await use_cases.list_players(
        uow,
        organization_id=OrganizationId(organization_id),
        team_id=TeamId(team_id) if team_id else None,
        on_date=on_date,
        limit=page.limit,
        offset=page.offset,
    )
    return PlayerList(
        items=[PlayerRead.model_validate(player_payload(player)) for player in players],
        meta=page.meta(len(players)),
    )


@router.get(
    "/{player_id}",
    response_model=PlayerRead,
    summary="Get a player",
    responses={404: {"model": ErrorResponse, "description": "Not found."}},
)
async def get_player(
    player_id: uuid.UUID,
    user: CurrentUserDep,
    uow: UnitOfWorkDep,
    organization_id: uuid.UUID = Query(description="Owning organization."),
) -> PlayerRead:
    await require_organization_member(
        uow, organization_id=OrganizationId(organization_id), user_id=user.id
    )
    player = await use_cases.get_player(
        uow,
        organization_id=OrganizationId(organization_id),
        player_id=PlayerId(player_id),
    )
    return PlayerRead.model_validate(player_payload(player))
