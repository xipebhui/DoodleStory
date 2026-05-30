from datetime import datetime
from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict

T = TypeVar("T")


class ApiData(BaseModel, Generic[T]):
    data: T


class ApiError(BaseModel):
    code: str
    message: str


class ApiErrorResponse(BaseModel):
    error: ApiError


class OrmModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class TimestampFields(OrmModel):
    created_at: datetime
    updated_at: datetime
