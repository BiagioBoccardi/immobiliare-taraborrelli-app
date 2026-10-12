from typing import Annotated

from fastapi import Query
from pydantic import BaseModel, Field

MAX_PAGE_SIZE = 100


class PageParams(BaseModel):
    page: int = Field(default=1, ge=1)
    size: int = Field(default=20, ge=1, le=MAX_PAGE_SIZE)

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.size


def page_params(
    page: Annotated[int, Query(ge=1)] = 1,
    size: Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)] = 20,
) -> PageParams:
    return PageParams(page=page, size=size)


class Page[T](BaseModel):
    items: list[T]
    total: int
    page: int
    size: int

    @property
    def pages(self) -> int:
        return (self.total + self.size - 1) // self.size if self.size else 0
