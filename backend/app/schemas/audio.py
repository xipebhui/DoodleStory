from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.common import TimestampFields
from app.schemas.style import FileAssetRead


class AudioReferenceCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=500)
    reference_text: str | None = Field(default=None, max_length=2000)
    voice_provider: str | None = Field(default=None, max_length=80)
    voice_model: str | None = Field(default=None, max_length=160)
    voice_name: str | None = Field(default=None, max_length=255)
    speech_speed: float = Field(default=1.0, ge=0.5, le=2.0)


class AudioReferenceUpdate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=500)
    speech_speed: float = Field(ge=0.5, le=2.0)


class AudioReferenceTestRequest(BaseModel):
    text: str = Field(min_length=1, max_length=2000)


class AudioReferenceTranscription(BaseModel):
    text: str


class AudioReferenceRead(TimestampFields):
    id: str
    owner_user_id: str
    owner_display_name: str | None = None
    owner_email: str | None = None
    name: str
    description: str | None
    reference_text: str | None
    voice_provider: str | None
    voice_model: str | None
    voice_name: str | None
    speech_speed: float
    deleted_at: datetime | None
    asset: FileAssetRead


class AudioReferenceListItem(TimestampFields):
    id: str
    owner_user_id: str
    owner_display_name: str | None = None
    owner_email: str | None = None
    name: str
    description: str | None
    voice_provider: str | None
    voice_model: str | None
    voice_name: str | None
    speech_speed: float
    asset: FileAssetRead
