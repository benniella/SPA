from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, status

from app.api.dependencies import UnitOfWorkDep
from app.api.v1.params import Pagination, pagination
from app.api.v1.presenters import user_payload
from app.core.errors import ConflictError, NotFoundError
from app.domain.shared import UserId
from app.domain.users.entities import Email, User
from app.schemas.common import ErrorResponse
from app.schemas.users import UserCreate, UserList, UserRead

router = APIRouter()


@router.post(
    "",
    response_model=UserRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create a user",
    description=(
        "Creates the identity record only. Credentials and sessions are not "
        "implemented yet — see 'docs/architecture/overview.md'."
    ),
    responses={409: {"model": ErrorResponse, "description": "Email already registered."}},
)
async def create_user(payload: UserCreate, uow: UnitOfWorkDep) -> UserRead:
    async with uow:
        existing = await uow.users.get_by_email(str(payload.email))
        if existing is not None:
            raise ConflictError("A user with this email already exists.")

        user = User(email=Email(str(payload.email)), display_name=payload.display_name)
        await uow.users.add(user)
        await uow.commit()

    return UserRead.model_validate(user_payload(user))


@router.get("", response_model=UserList, summary="List users")
async def list_users(
    uow: UnitOfWorkDep,
    page: Pagination = Depends(pagination),
) -> UserList:
    async with uow:
        users = await uow.users.list(limit=page.limit, offset=page.offset)
    return UserList(
        items=[UserRead.model_validate(user_payload(user)) for user in users],
        meta=page.meta(len(users)),
    )


@router.get(
    "/{user_id}",
    response_model=UserRead,
    summary="Get a user",
    responses={404: {"model": ErrorResponse, "description": "Not found."}},
)
async def get_user(user_id: uuid.UUID, uow: UnitOfWorkDep) -> UserRead:
    async with uow:
        user = await uow.users.get(UserId(user_id))
    if user is None:
        raise NotFoundError(f"User {user_id} does not exist.")
    return UserRead.model_validate(user_payload(user))
