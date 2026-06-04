from datetime import datetime

from pydantic import BaseModel, Field

from app.models.enums import ContentExtractionMediaKind
from app.schemas.common import TimestampFields
from app.schemas.style import FileAssetRead


class ContentExtractionDownloadCreate(BaseModel):
    raw_input: str = Field(min_length=1, max_length=4000)


class ContentExtractionHealthRead(BaseModel):
    ok: bool
    service_base_url: str
    response: dict[str, object] | None = None


class ContentExtractionMediaRead(TimestampFields):
    id: str
    media_kind: ContentExtractionMediaKind
    display_order: int
    asset: FileAssetRead
    extracted_text: str | None = None


class ContentExtractionRead(TimestampFields):
    id: str
    owner_user_id: str
    raw_input: str
    source_url: str
    media_type: str
    aweme_id: str | None
    extracted_text: str | None
    media: list[ContentExtractionMediaRead] = []


class ContentExtractionListItemRead(TimestampFields):
    id: str
    owner_user_id: str
    source_url: str
    media_type: str
    aweme_id: str | None
    extracted_text_preview: str | None
    media_count: int


class ContentExtractionCreatedRead(BaseModel):
    id: str
    created_at: datetime
