from datetime import datetime, timezone
from typing import Any, Generic, TypeVar

from pydantic import BaseModel, ConfigDict, model_validator

T = TypeVar("T")


def as_utc_datetime(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def api_datetime_iso(value: datetime) -> str:
    return as_utc_datetime(value).isoformat().replace("+00:00", "Z")


def normalize_api_datetimes(value: Any) -> Any:
    if isinstance(value, datetime):
        return as_utc_datetime(value)
    if isinstance(value, BaseModel):
        updates = {
            field_name: normalize_api_datetimes(getattr(value, field_name))
            for field_name in type(value).model_fields
        }
        return value.model_copy(update=updates)
    if isinstance(value, dict):
        return {
            key: normalize_api_datetimes(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [normalize_api_datetimes(item) for item in value]
    if isinstance(value, tuple):
        return tuple(normalize_api_datetimes(item) for item in value)
    if isinstance(value, set):
        return {normalize_api_datetimes(item) for item in value}
    if isinstance(value, frozenset):
        return frozenset(normalize_api_datetimes(item) for item in value)
    return value


class ApiData(BaseModel, Generic[T]):
    data: T

    @model_validator(mode="after")
    def normalize_datetimes_as_utc(self) -> "ApiData[T]":
        self.data = normalize_api_datetimes(self.data)
        return self


class PageInfo(BaseModel):
    limit: int
    next_cursor: str | None
    has_more: bool
    total: int | None = None


class ApiList(BaseModel, Generic[T]):
    items: list[T]
    page: PageInfo

    @model_validator(mode="after")
    def normalize_datetimes_as_utc(self) -> "ApiList[T]":
        self.items = normalize_api_datetimes(self.items)
        return self


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
