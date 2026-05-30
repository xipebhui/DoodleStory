from datetime import datetime

from pydantic import BaseModel, Field

from app.models.enums import ImageCountMode, PromptStatus, TaskStatus
from app.schemas.common import TimestampFields


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


class TaskRead(TimestampFields):
    id: str
    owner_user_id: str
    display_title: str
    original_text: str
    image_count_mode: ImageCountMode
    requested_image_count: int | None
    style_id: str
    style_name_snapshot: str
    generation_profile_key_snapshot: str | None
    status: TaskStatus
    progress_current: int
    progress_total: int
    error_code: str | None
    error_message: str | None
    panels: list[TaskPanelRead] = []
