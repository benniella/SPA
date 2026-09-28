from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query, status

from app.api.dependencies import UnitOfWorkDep
from app.api.v1.params import Pagination, pagination
from app.api.v1.presenters import match_payload
from app.application.use_cases import matches as use_cases
from app.domain.shared import MatchId, OrganizationId, TeamId
from app.schemas.common import ErrorResponse
from app.schemas.matches import MatchCreate, MatchList, MatchRead

router = APIRouter()


@router.post(
    "",
    response_model=MatchRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create a match",
    responses={404: {"model": ErrorResponse, "description": "Organization not found."}},
)
async def create_match(payload: MatchCreate, uow: UnitOfWorkDep) -> MatchRead:
    match = await use_cases.create_match(
        uow,
        organization_id=OrganizationId(payload.organization_id),
        played_on=payload.played_on,
        home_team_id=TeamId(payload.home_team_id) if payload.home_team_id else None,
        away_team_id=TeamId(payload.away_team_id) if payload.away_team_id else None,
        home_team_name=payload.home_team_name,
        away_team_name=payload.away_team_name,
        competition=payload.competition,
        is_home=payload.is_home,
        venue_name=payload.venue_name,
    )
    return MatchRead.model_validate(match_payload(match))


@router.get("", response_model=MatchList, summary="List matches in an organization")
async def list_matches(
    uow: UnitOfWorkDep,
    organization_id: uuid.UUID = Query(description="Owning organization."),
    page: Pagination = Depends(pagination),
) -> MatchList:
    matches = await use_cases.list_matches(
        uow,
        organization_id=OrganizationId(organization_id),
        limit=page.limit,
        offset=page.offset,
    )
    return MatchList(
        items=[MatchRead.model_validate(match_payload(match)) for match in matches],
        meta=page.meta(len(matches)),
    )


@router.get(
    "/{match_id}",
    response_model=MatchRead,
    summary="Get a match",
    responses={404: {"model": ErrorResponse, "description": "Not found."}},
)
async def get_match(
    match_id: uuid.UUID,
    uow: UnitOfWorkDep,
    organization_id: uuid.UUID = Query(description="Owning organization."),
) -> MatchRead:
    match = await use_cases.get_match(
        uow,
        organization_id=OrganizationId(organization_id),
        match_id=MatchId(match_id),
    )
    return MatchRead.model_validate(match_payload(match))
