from datetime import datetime

from pydantic import BaseModel, Field

from app.models.enums import ContentExtractionMediaKind, ImageCountMode
from app.schemas.common import TimestampFields
from app.schemas.style import FileAssetRead


class ContentExtractionDownloadCreate(BaseModel):
    raw_input: str = Field(min_length=1, max_length=4000)


class ContentExtractionReplicateTaskCreate(ContentExtractionDownloadCreate):
    image_count_mode: ImageCountMode
    requested_image_count: int | None = Field(default=None, ge=1, le=80)
    style_id: str = Field(min_length=1)
    use_character_references: bool = True


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
    source_title: str | None = None
    source_description: str | None = None
    source_tags: list[str] = []
    processing_status: str
    processing_error_message: str | None = None
    extracted_text: str | None
    story_content: str | None = None
    story_highlight: str | None = None
    target_audience: str | None = None
    story_summary_model: str | None = None
    story_summarized_at: datetime | None = None
    linked_task_id: str | None = None
    task_create_status: str | None = None
    task_create_error_message: str | None = None
    media: list[ContentExtractionMediaRead] = []


class ContentExtractionListItemRead(TimestampFields):
    id: str
    owner_user_id: str
    source_url: str
    media_type: str
    aweme_id: str | None
    source_title: str | None = None
    source_description: str | None = None
    source_tags: list[str] = []
    processing_status: str
    processing_error_message: str | None = None
    raw_input_preview: str | None
    extracted_text_preview: str | None
    story_content_preview: str | None
    story_highlight_preview: str | None
    target_audience_preview: str | None
    has_extracted_text: bool
    has_story_summary: bool
    media_count: int
    linked_task_id: str | None = None
    task_create_status: str | None = None
    task_create_error_message: str | None = None


class ContentExtractionCreatedRead(BaseModel):
    id: str
    created_at: datetime
