from enum import StrEnum


class UserRole(StrEnum):
    user = "user"
    admin = "admin"


class StyleStatus(StrEnum):
    draft = "draft"
    active = "active"
    disabled = "disabled"


class FileAssetPurpose(StrEnum):
    style_reference = "style_reference"
    character_reference = "character_reference"
    generated_image = "generated_image"
    download_archive = "download_archive"


class StorageBackend(StrEnum):
    local = "local"
    qiniu = "qiniu"


class ImageCountMode(StrEnum):
    auto = "auto"
    fixed = "fixed"


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
