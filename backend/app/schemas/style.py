from datetime import datetime
from pydantic import BaseModel, Field, computed_field

from app.models.enums import StyleReferenceMode, StyleStatus, WorkflowStatus
from app.schemas.common import TimestampFields

STYLE_ASPECT_RATIOS = ("1:1", "3:4", "4:3", "9:16", "16:9")


class StyleCreate(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    description: str | None = Field(default=None, max_length=500)
    status: StyleStatus = StyleStatus.draft
    image_model_name: str = Field(min_length=1, max_length=120)
    aspect_ratio: str = Field(default="9:16")
    style_reference_mode: StyleReferenceMode = StyleReferenceMode.prompt
    style_prompt: str = Field(min_length=1, max_length=8000)


class StyleUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=80)
    description: str | None = Field(default=None, max_length=500)
    status: StyleStatus | None = None
    image_model_name: str | None = Field(default=None, min_length=1, max_length=120)
    aspect_ratio: str | None = None
    style_reference_mode: StyleReferenceMode | None = None
    style_prompt: str | None = Field(default=None, min_length=1, max_length=8000)


class FileAssetRead(TimestampFields):
    id: str
    purpose: str
    storage_backend: str
    original_filename: str | None
    content_type: str
    byte_size: int
    public_url: str | None = None
    width: int | None = None
    height: int | None = None

    def is_qiniu_asset(self) -> bool:
        return self.storage_backend == "qiniu" and bool(self.public_url)

    @computed_field
    @property
    def content_url(self) -> str:
        if self.is_qiniu_asset():
            return self.public_url or ""
        return f"/api/v1/assets/{self.id}/content"

    @computed_field
    @property
    def thumbnail_url(self) -> str:
        if self.is_qiniu_asset():
            return self.public_url or ""
        return f"/api/v1/assets/{self.id}/content?variant=thumbnail"


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
    image_model_name: str
    aspect_ratio: str
    style_reference_mode: StyleReferenceMode
    style_prompt: str
    cover_asset: FileAssetRead | None = None
    last_tested_at: datetime | None
    reference_images: list[StyleReferenceImageRead] = []


class StyleTestCreate(BaseModel):
    test_text: str = Field(min_length=1, max_length=2000)


class StyleTestRead(TimestampFields):
    id: str
    style_id: str
    test_text: str
    style_prompt_snapshot: str
    image_model_name_snapshot: str
    aspect_ratio_snapshot: str
    style_reference_mode_snapshot: StyleReferenceMode
    composed_prompt: str
    status: WorkflowStatus
    output_asset: FileAssetRead | None = None
    provider_request_id: str | None
    error_code: str | None
    error_message: str | None
    started_at: datetime | None
    finished_at: datetime | None
