from enum import StrEnum


class UserRole(StrEnum):
    user = "user"
    admin = "admin"


class AgentConversationStatus(StrEnum):
    active = "active"
    archived = "archived"


class AgentSkillStatus(StrEnum):
    draft = "draft"
    published = "published"
    archived = "archived"


class AgentMessageRole(StrEnum):
    user = "user"
    assistant = "assistant"
    system_event = "system_event"
    task_card = "task_card"


class AgentRunStatus(StrEnum):
    queued = "queued"
    running = "running"
    waiting_for_tool = "waiting_for_tool"
    waiting_for_input = "waiting_for_input"
    paused = "paused"
    retrying = "retrying"
    succeeded = "succeeded"
    failed = "failed"
    cancel_requested = "cancel_requested"
    cancelled = "cancelled"


class AgentStepType(StrEnum):
    model_call = "model_call"
    tool_call = "tool_call"
    tool_result = "tool_result"
    wait = "wait"
    final = "final"


class AgentStepStatus(StrEnum):
    pending = "pending"
    running = "running"
    succeeded = "succeeded"
    failed = "failed"
    cancelled = "cancelled"


class NativeAgentItemType(StrEnum):
    user_input = "user_input"
    tool_call = "tool_call"
    tool_result = "tool_result"
    assistant_output = "assistant_output"
    error = "error"


class AgentArtifactType(StrEnum):
    comic_plan = "comic_plan"


class AgentArtifactStatus(StrEnum):
    draft = "draft"
    awaiting_approval = "awaiting_approval"
    approved = "approved"
    rejected = "rejected"
    superseded = "superseded"


class AgentApprovalType(StrEnum):
    comic_plan = "comic_plan"


class AgentApprovalStatus(StrEnum):
    pending = "pending"
    approved = "approved"
    changes_requested = "changes_requested"
    cancelled = "cancelled"


class AgentEventType(StrEnum):
    run_started = "run.started"
    skill_selected = "skill.selected"
    skill_loaded = "skill.loaded"
    skill_version_pinned = "skill.version_pinned"
    skill_waiting_for_confirmation = "skill.waiting_for_confirmation"
    artifact_created = "artifact.created"
    approval_requested = "approval.requested"
    approval_resolved = "approval.resolved"
    tool_started = "tool.started"
    tool_progress = "tool.progress"
    tool_completed = "tool.completed"
    tool_failed = "tool.failed"
    assistant_message = "assistant.message"
    run_completed = "run.completed"
    run_failed = "run.failed"
    panel_revision_requested = "panel.revision_requested"
    image_version_created = "image.version_created"
    image_inspection_started = "image.inspection_started"
    image_inspection_completed = "image.inspection_completed"
    image_version_accepted = "image.version_accepted"
    image_version_restored = "image.version_restored"
    run_paused = "run.paused"
    run_resumed = "run.resumed"


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
