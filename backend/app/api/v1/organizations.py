from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, status

from app.api.dependencies import UnitOfWorkDep
from app.api.v1.params import Pagination, pagination
from app.api.v1.presenters import organization_payload
from app.application.use_cases import organizations as use_cases
from app.domain.shared import OrganizationId
from app.schemas.common import ErrorResponse
from app.schemas.organizations import (
    OrganizationCreate,
    OrganizationList,
    OrganizationRead,
)

router = APIRouter()


@router.post(
    "",
    response_model=OrganizationRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create an organization",
    responses={409: {"model": ErrorResponse, "description": "Slug already in use."}},
)
async def create_organization(
    payload: OrganizationCreate,
    uow: UnitOfWorkDep,
) -> OrganizationRead:
    organization = await use_cases.create_organization(
        uow,
        name=payload.name,
        slug=payload.slug,
    )
    return OrganizationRead.model_validate(organization_payload(organization))


@router.get(
    "",
    response_model=OrganizationList,
    summary="List organizations",
)
async def list_organizations(
    uow: UnitOfWorkDep,
    page: Pagination = Depends(pagination),
) -> OrganizationList:
    organizations = await use_cases.list_organizations(
        uow,
        limit=page.limit,
        offset=page.offset,
    )
    return OrganizationList(
        items=[
            OrganizationRead.model_validate(organization_payload(item)) for item in organizations
        ],
        meta=page.meta(len(organizations)),
    )


@router.get(
    "/{organization_id}",
    response_model=OrganizationRead,
    summary="Get an organization",
    responses={404: {"model": ErrorResponse, "description": "Not found."}},
)
async def get_organization(
    organization_id: uuid.UUID,
    uow: UnitOfWorkDep,
) -> OrganizationRead:
    organization = await use_cases.get_organization(
        uow,
        organization_id=OrganizationId(organization_id),
    )
    return OrganizationRead.model_validate(organization_payload(organization))
