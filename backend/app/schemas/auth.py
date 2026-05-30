from pydantic import BaseModel, EmailStr, Field

from app.models.enums import UserRole
from app.schemas.common import OrmModel, TimestampFields


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    display_name: str | None = Field(default=None, max_length=120)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class UserRead(TimestampFields):
    id: str
    email: str
    display_name: str | None
    role: UserRole


class SessionRead(OrmModel):
    user: UserRead
