from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated, TypeVar

from fastapi import Query

from app.domain.shared import Page
from app.schemas.common import PageMeta

T = TypeVar("T")


@dataclass(frozen=True, slots=True)
class Pagination:
    limit: int
    offset: int

    def to_page(self) -> Page:
        return Page(limit=self.limit, offset=self.offset)

    def meta(self, count: int) -> PageMeta:
        return PageMeta(limit=self.limit, offset=self.offset, count=count)


PaginationDep = Annotated[
    Pagination,
    Query(
        description=(
            "Offset pagination. Deliberately chosen over cursors: "
            "simpler for the frontend, adequate at current volumes, and safe to "
            "replace because 'meta' is an object rather than a bare array."
        )
    ),
]


def pagination(
    limit: Annotated[int, Query(ge=1, le=200, description="Maximum items to return.")] = 50,
    offset: Annotated[int, Query(ge=0, description="Number of items to skip.")] = 0,
) -> Pagination:
    return Pagination(limit=limit, offset=offset)
