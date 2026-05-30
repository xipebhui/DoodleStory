from datetime import datetime
from typing import Any, Generic, TypeVar

from pydantic import BaseModel, ConfigDict

T = TypeVar("T")


class ApiData(BaseModel, Generic[T]):
    data: T


class PageInfo(BaseModel):
    limit: int
    next_cursor: str | None
    has_more: bool


class ApiList(BaseModel, Generic[T]):
    items: list[T]
    page: PageInfo


class ApiError(BaseModel):
    code: str
    message: str
    fields: dict[str, Any] | None = None
    request_id: str


class ApiErrorResponse(BaseModel):
    error: ApiError


class OrmModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class TimestampFields(OrmModel):
    created_at: datetime
    updated_at: datetime
