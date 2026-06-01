from datetime import datetime

from pydantic import BaseModel, Field

from app.models.enums import (
    DownloadStatus,
    GeneratedImageSourceType,
    GeneratedImageStatus,
    GeneratedImageWorkflowStep,
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
    use_character_references: bool = False


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
    generation_number: int
    is_current: bool
    source_type: GeneratedImageSourceType
    workflow_step: GeneratedImageWorkflowStep | None
    user_instruction: str | None
    previous_prompt: str | None
    image_prompt: str | None
    prompt_change_summary: str | None
    final_prompt: str | None
    asset: FileAssetRead | None = None
    error_code: str | None
    error_message: str | None


class PanelEditCreate(BaseModel):
    user_instruction: str = Field(min_length=1, max_length=2000)


class TaskCharacterReferenceRead(BaseModel):
    id: str
    name: str
    age_stage: str | None
    asset: FileAssetRead


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
    use_character_references: bool
    style_id: str
    style_name_snapshot: str
    image_model_name_snapshot: str
    style_aspect_ratio_snapshot: str
    status: TaskStatus
    progress_current: int
    progress_total: int
    error_code: str | None
    error_message: str | None
    current_step: GenerationStepName | None
    panels: list[TaskPanelRead] = []
    steps: list[GenerationStepRead] = []
    generated_images: list[GeneratedImageRead] = []
    character_references: list[TaskCharacterReferenceRead] = []
    downloads: list[TaskDownloadRead] = []
