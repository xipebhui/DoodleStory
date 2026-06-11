from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.common import TimestampFields
from app.schemas.style import FileAssetRead


class UserCharacterRead(TimestampFields):
    id: str
    owner_user_id: str
    name: str
    description: str | None
    reference_asset: FileAssetRead
    deleted_at: datetime | None


class CharacterNameExtractionRequest(BaseModel):
    text: str = Field(min_length=1, max_length=20000)


class CharacterNameExtractionResult(BaseModel):
    names: list[str]


class StoryCharacterBindingCreate(BaseModel):
    source_name: str = Field(min_length=1, max_length=120)
    user_character_id: str = Field(min_length=1, max_length=32)


class StoryCharacterMergeRequest(BaseModel):
    story_text: str = Field(min_length=1, max_length=20000)
    character_name: str = Field(min_length=1, max_length=120)
    character_description: str | None = Field(default=None, max_length=1000)


class StoryCharacterMergeResult(BaseModel):
    story_text: str = Field(min_length=1)
    change_summary: str = Field(min_length=1)
