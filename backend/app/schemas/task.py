from datetime import datetime

from pydantic import BaseModel, Field

from app.models.enums import (
    DownloadStatus,
    GeneratedImageStatus,
    GenerationStepName,
    ImageCountMode,
    PromptStatus,
    StepStatus,
    TaskStatus,
)
from app.schemas.common import TimestampFields
from app.schemas.style import FileAssetRead


class TaskCreate(BaseModel):
    original_text: str = Field(min_length=1, max_length=20000)
    image_count_mode: ImageCountMode
    requested_image_count: int | None = Field(default=None, ge=1, le=80)
    style_id: str = Field(min_length=1)


class TaskPanelRead(TimestampFields):
    id: str
    panel_order: int
    original_text_segment: str
    prompt_status: PromptStatus
    generated_prompt: str | None


class GenerationStepRead(TimestampFields):
    id: str
    step_name: GenerationStepName
    status: StepStatus
    attempts: int
    error_code: str | None
    error_message: str | None


class GeneratedImageRead(TimestampFields):
    id: str
    panel_id: str
    status: GeneratedImageStatus
    final_prompt: str
    asset: FileAssetRead | None = None
    error_code: str | None
    error_message: str | None


class TaskDownloadRead(TimestampFields):
    id: str
    status: DownloadStatus
    image_count: int
    filename: str
    asset: FileAssetRead | None = None
    error_code: str | None
    error_message: str | None


class TaskRead(TimestampFields):
    id: str
    owner_user_id: str
    display_title: str
    original_text: str
    image_count_mode: ImageCountMode
    requested_image_count: int | None
    style_id: str
    style_name_snapshot: str
    image_model_name_snapshot: str
    status: TaskStatus
    progress_current: int
    progress_total: int
    error_code: str | None
    error_message: str | None
    current_step: GenerationStepName | None
    panels: list[TaskPanelRead] = []
    steps: list[GenerationStepRead] = []
    generated_images: list[GeneratedImageRead] = []
    downloads: list[TaskDownloadRead] = []
