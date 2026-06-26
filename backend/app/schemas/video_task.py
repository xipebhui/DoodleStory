from datetime import datetime

from pydantic import BaseModel, Field

from app.models.enums import ImageCountMode, TaskStatus, VideoTaskStatus, VideoTaskStepName
from app.schemas.common import TimestampFields
from app.schemas.style import FileAssetRead
from app.schemas.task import TaskPreviewImageRead


class VideoTaskCreate(BaseModel):
    original_text: str = Field(min_length=1, max_length=20000)
    image_count_mode: ImageCountMode = ImageCountMode.auto
    requested_image_count: int | None = Field(default=None, ge=1, le=80)
    style_id: str = Field(min_length=1)
    audio_reference_id: str = Field(min_length=1)
    use_character_references: bool = True
    last_panel_real_photo: bool = False


class VideoTaskSourceTaskRead(BaseModel):
    id: str
    display_title: str
    status: TaskStatus
    progress_current: int
    progress_total: int
    error_code: str | None
    error_message: str | None
    style_name_snapshot: str
    style_aspect_ratio_snapshot: str
    image_count: int
    preview_images: list[TaskPreviewImageRead] = []


class VideoTaskAudioSegmentRead(TimestampFields):
    id: str
    panel_id: str
    panel_order: int
    narration_text: str
    duration_ms: int | None = None
    asset: FileAssetRead


class VideoTaskListItem(TimestampFields):
    id: str
    owner_user_id: str
    owner_display_name: str | None = None
    owner_email: str | None = None
    display_title: str
    original_text_preview: str
    status: VideoTaskStatus
    current_step: VideoTaskStepName
    progress_current: int
    progress_total: int
    error_code: str | None
    error_message: str | None
    audio_reference_name_snapshot: str
    video_provider_job_id: str | None = None
    video_provider_status: str | None = None
    source_task: VideoTaskSourceTaskRead
    output_video_asset: FileAssetRead | None = None


class VideoTaskRead(TimestampFields):
    id: str
    owner_user_id: str
    owner_display_name: str | None = None
    owner_email: str | None = None
    display_title: str
    original_text: str
    status: VideoTaskStatus
    current_step: VideoTaskStepName
    progress_current: int
    progress_total: int
    started_at: datetime | None
    finished_at: datetime | None
    error_code: str | None
    error_message: str | None
    audio_reference_id: str
    audio_reference_name_snapshot: str
    audio_reference_text_snapshot: str | None
    audio_reference_asset: FileAssetRead
    voice_provider_snapshot: str | None = None
    voice_model_snapshot: str | None = None
    voice_name_snapshot: str | None = None
    narration_audio_asset: FileAssetRead | None = None
    audio_segments: list[VideoTaskAudioSegmentRead] = []
    output_video_asset: FileAssetRead | None = None
    video_provider_job_id: str | None = None
    video_provider_status: str | None = None
    video_provider_output_url: str | None = None
    source_task: VideoTaskSourceTaskRead
