from __future__ import annotations

import uuid

from fastapi import APIRouter

from app.api.dependencies import CurrentUserDep, UnitOfWorkDep
from app.api.v1.presenters import user_payload
from app.core.errors import NotFoundError
from app.domain.shared import UserId
from app.schemas.common import ErrorResponse
from app.schemas.users import UserRead

router = APIRouter()


@router.get(
    "/me",
    response_model=UserRead,
    summary="The authenticated identity record",
)
async def read_self(user: CurrentUserDep) -> UserRead:
    return UserRead.model_validate(user_payload(user))


@router.get(
    "/{user_id}",
    response_model=UserRead,
    summary="Get a user",
    responses={404: {"model": ErrorResponse, "description": "Not found."}},
)
async def get_user(user_id: uuid.UUID, user: CurrentUserDep, uow: UnitOfWorkDep) -> UserRead:
    """Read an identity record within the caller's own tenancy.

    A caller may read their own record and the records of people who share an
    organization with them. Anything else is reported as absent: the endpoint must
    not become a way to confirm which user ids exist platform-wide.
    """
    if user_id == user.id:
        return UserRead.model_validate(user_payload(user))

    async with uow:
        target = await uow.users.get(UserId(user_id))
        if target is None or not await _shares_organization(uow, user.id, target.id):
            raise NotFoundError(f"User {user_id} does not exist.")
    return UserRead.model_validate(user_payload(target))


async def _shares_organization(uow: UnitOfWorkDep, left: UserId, right: UserId) -> bool:
    mine = {str(m.organization_id) for m in await uow.organizations.list_for_user(left)}
    if not mine:
        return False
    theirs = await uow.organizations.list_for_user(right)
    return any(str(m.organization_id) in mine for m in theirs)
