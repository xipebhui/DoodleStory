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
    generated_image = "generated_image"
    download_archive = "download_archive"


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


class WorkflowStatus(StrEnum):
    queued = "queued"
    running = "running"
    succeeded = "succeeded"
    failed = "failed"
    cancel_requested = "cancel_requested"
    cancelled = "cancelled"
    retrying = "retrying"
