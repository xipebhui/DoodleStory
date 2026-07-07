from enum import StrEnum


class UserRole(StrEnum):
    user = "user"
    admin = "admin"


class StyleStatus(StrEnum):
    draft = "draft"
    active = "active"
    disabled = "disabled"


class StyleReferenceMode(StrEnum):
    prompt = "prompt"
    image = "image"


class FileAssetPurpose(StrEnum):
    style_reference = "style_reference"
    user_character_reference = "user_character_reference"
    character_reference = "character_reference"
    generated_image = "generated_image"
    audio_reference = "audio_reference"
    generated_audio = "generated_audio"
    generated_video = "generated_video"
    download_archive = "download_archive"
    douyin_media = "douyin_media"
    douyin_audio = "douyin_audio"
    douyin_metadata = "douyin_metadata"


class ContentExtractionMediaKind(StrEnum):
    image = "image"
    video = "video"
    audio = "audio"
    metadata = "metadata"


class StorageBackend(StrEnum):
    local = "local"
    qiniu = "qiniu"
    aliyun_oss = "aliyun_oss"


class ImageCountMode(StrEnum):
    auto = "auto"
    fixed = "fixed"


class StoryInputMode(StrEnum):
    original = "original"
    adapted = "adapted"
    extracted_storyboard = "extracted_storyboard"
    knowledge_plan = "knowledge_plan"


class PanelType(StrEnum):
    cover = "cover"
    scene = "scene"


class TaskStatus(StrEnum):
    queued = "queued"
    running = "running"
    succeeded = "succeeded"
    partial_succeeded = "partial_succeeded"
    failed = "failed"
    cancel_requested = "cancel_requested"
    cancelled = "cancelled"
    retrying = "retrying"


class GenerationStepName(StrEnum):
    adapt_story = "adapt_story"
    segment_story = "segment_story"
    extract_characters = "extract_characters"
    generate_character_references = "generate_character_references"
    generate_panel_prompts = "generate_panel_prompts"
    generate_images = "generate_images"
    package_download = "package_download"


class StepStatus(StrEnum):
    queued = "queued"
    running = "running"
    succeeded = "succeeded"
    failed = "failed"
    cancelled = "cancelled"
    retrying = "retrying"


class PromptStatus(StrEnum):
    pending = "pending"
    generated = "generated"
    failed = "failed"


class GeneratedImageStatus(StrEnum):
    queued = "queued"
    running = "running"
    succeeded = "succeeded"
    failed = "failed"
    cancelled = "cancelled"


class GeneratedImageSourceType(StrEnum):
    initial = "initial"
    user_edit = "user_edit"
    retry = "retry"


class GeneratedImageJobKind(StrEnum):
    panel_image = "panel_image"
    character_reference = "character_reference"


class GeneratedImageWorkflowStep(StrEnum):
    rewrite_prompt = "rewrite_prompt"
    generate_image = "generate_image"


class WorkflowStatus(StrEnum):
    queued = "queued"
    running = "running"
    succeeded = "succeeded"
    failed = "failed"
    cancel_requested = "cancel_requested"
    cancelled = "cancelled"
    retrying = "retrying"


class DownloadStatus(StrEnum):
    queued = "queued"
    running = "running"
    ready = "ready"
    failed = "failed"


class VideoTaskStatus(StrEnum):
    waiting_for_images = "waiting_for_images"
    ready_for_audio = "ready_for_audio"
    audio_generating = "audio_generating"
    audio_ready = "audio_ready"
    video_generating = "video_generating"
    succeeded = "succeeded"
    failed = "failed"
    cancel_requested = "cancel_requested"
    cancelled = "cancelled"


class VideoTaskStepName(StrEnum):
    generate_source_images = "generate_source_images"
    generate_narration_audio = "generate_narration_audio"
    submit_video = "submit_video"
    download_video = "download_video"


class CreditTransactionType(StrEnum):
    initial_grant = "initial_grant"
    admin_adjustment = "admin_adjustment"
    activation_code_redeem = "activation_code_redeem"
    image_generation_reserve = "image_generation_reserve"
    image_generation_charge = "image_generation_charge"
    image_generation_release = "image_generation_release"
