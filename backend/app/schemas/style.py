from datetime import datetime

from pydantic import BaseModel, Field

from app.models.enums import StyleStatus
from app.schemas.common import TimestampFields


class StyleCreate(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    description: str | None = Field(default=None, max_length=500)
    status: StyleStatus = StyleStatus.draft
    generation_profile_key: str | None = Field(default=None, max_length=120)
    style_prompt: str = Field(min_length=1, max_length=8000)


class StyleUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=80)
    description: str | None = Field(default=None, max_length=500)
    status: StyleStatus | None = None
    generation_profile_key: str | None = Field(default=None, max_length=120)
    style_prompt: str | None = Field(default=None, min_length=1, max_length=8000)


class FileAssetRead(TimestampFields):
    id: str
    purpose: str
    original_filename: str | None
    content_type: str
    byte_size: int


class StyleReferenceImageRead(BaseModel):
    id: str
    display_order: int
    created_at: datetime
    asset: FileAssetRead

    model_config = {"from_attributes": True}


class StyleRead(TimestampFields):
    id: str
    name: str
    description: str | None
    status: StyleStatus
    generation_profile_key: str | None
    style_prompt: str
    last_tested_at: datetime | None
    reference_images: list[StyleReferenceImageRead] = []


class StyleTestCreate(BaseModel):
    test_text: str = Field(min_length=1, max_length=2000)
