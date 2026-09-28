from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query, status

from app.api.dependencies import UnitOfWorkDep
from app.api.v1.params import Pagination, pagination
from app.api.v1.presenters import team_payload
from app.application.use_cases import teams as use_cases
from app.domain.shared import OrganizationId, TeamId
from app.schemas.common import ErrorResponse
from app.schemas.teams import TeamCreate, TeamList, TeamRead

router = APIRouter()


@router.post(
    "",
    response_model=TeamRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create a team",
    responses={404: {"model": ErrorResponse, "description": "Organization not found."}},
)
async def create_team(payload: TeamCreate, uow: UnitOfWorkDep) -> TeamRead:
    team = await use_cases.create_team(
        uow,
        organization_id=OrganizationId(payload.organization_id),
        name=payload.name,
        slug=payload.slug,
        sport=payload.sport,
        season=payload.season,
    )
    return TeamRead.model_validate(team_payload(team))


@router.get("", response_model=TeamList, summary="List teams in an organization")
async def list_teams(
    uow: UnitOfWorkDep,
    organization_id: uuid.UUID = Query(description="Owning organization."),
    page: Pagination = Depends(pagination),
) -> TeamList:
    teams = await use_cases.list_teams(
        uow,
        organization_id=OrganizationId(organization_id),
        limit=page.limit,
        offset=page.offset,
    )
    return TeamList(
        items=[TeamRead.model_validate(team_payload(team)) for team in teams],
        meta=page.meta(len(teams)),
    )


@router.get(
    "/{team_id}",
    response_model=TeamRead,
    summary="Get a team",
    responses={404: {"model": ErrorResponse, "description": "Not found."}},
)
async def get_team(
    team_id: uuid.UUID,
    uow: UnitOfWorkDep,
    organization_id: uuid.UUID = Query(description="Owning organization."),
) -> TeamRead:
    team = await use_cases.get_team(
        uow,
        organization_id=OrganizationId(organization_id),
        team_id=TeamId(team_id),
    )
    return TeamRead.model_validate(team_payload(team))
