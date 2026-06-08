from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.entities import GenerationStep, GenerationTask, Style, StyleReferenceImage, User
from app.models.enums import (
    GenerationStepName,
    ImageCountMode,
    StoryInputMode,
    StyleStatus,
    TaskStatus,
)
from app.schemas.task import TaskCreate
from app.services.image_generation import ImageProviderConfigError
from app.services.style_references import snapshot_task_style_reference_images


@dataclass(frozen=True)
class TaskCreationError(Exception):
    status_code: int
    detail: str

    def __str__(self) -> str:
        return self.detail


def task_progress_total_for_creation(task: GenerationTask) -> int:
    total = 1
    if task.story_input_mode in {StoryInputMode.adapted, StoryInputMode.extracted_storyboard}:
        total += 1
    else:
        total += 2
    if task.use_character_references:
        total += 2
    return total


def generation_step_names_for_task(
    *,
    story_input_mode: StoryInputMode,
    use_character_references: bool,
) -> list[GenerationStepName]:
    if story_input_mode in {StoryInputMode.adapted, StoryInputMode.extracted_storyboard}:
        step_names = [GenerationStepName.adapt_story]
    else:
        step_names = [GenerationStepName.segment_story]
    if use_character_references:
        step_names.extend([GenerationStepName.extract_characters, GenerationStepName.generate_character_references])
    if story_input_mode not in {StoryInputMode.adapted, StoryInputMode.extracted_storyboard}:
        step_names.append(GenerationStepName.generate_panel_prompts)
    step_names.append(GenerationStepName.generate_images)
    return step_names


def load_active_style_for_task(db: Session, style_id: str) -> Style:
    style = db.scalar(
        select(Style)
        .where(Style.id == style_id, Style.deleted_at.is_(None))
        .options(selectinload(Style.reference_images).selectinload(StyleReferenceImage.asset))
    )
    if not style:
        raise TaskCreationError(status_code=404, detail="风格不存在")
    if style.status != StyleStatus.active:
        raise TaskCreationError(status_code=400, detail="只能使用启用状态的风格创建任务")
    if not style.image_model_name.strip():
        raise TaskCreationError(status_code=400, detail="风格尚未绑定生图模型名")
    return style


def validate_task_create_payload(payload: TaskCreate) -> None:
    if payload.image_count_mode == ImageCountMode.auto and payload.requested_image_count is not None:
        raise TaskCreationError(status_code=400, detail="自动判断图片数量时不能传 requested_image_count")
    if payload.image_count_mode == ImageCountMode.fixed and payload.requested_image_count is None:
        raise TaskCreationError(status_code=400, detail="固定图片数量时必须传 requested_image_count")


def create_generation_task_record(
    *,
    db: Session,
    payload: TaskCreate,
    user: User,
) -> GenerationTask:
    validate_task_create_payload(payload)
    style = load_active_style_for_task(db, payload.style_id)

    display_title = payload.original_text.strip().replace("\n", " ")[:36] or "未命名任务"
    task = GenerationTask(
        owner_user_id=user.id,
        display_title=display_title,
        original_text=payload.original_text,
        story_input_mode=payload.story_input_mode,
        image_count_mode=payload.image_count_mode,
        requested_image_count=payload.requested_image_count,
        use_character_references=payload.use_character_references,
        style_id=style.id,
        style_name_snapshot=style.name,
        style_prompt_snapshot=style.style_prompt,
        image_model_name_snapshot=style.image_model_name,
        style_aspect_ratio_snapshot=style.aspect_ratio,
        style_reference_mode_snapshot=style.style_reference_mode,
        status=TaskStatus.queued,
        progress_current=0,
    )
    task.progress_total = task_progress_total_for_creation(task)
    db.add(task)
    db.flush()

    for step_name in generation_step_names_for_task(
        story_input_mode=payload.story_input_mode,
        use_character_references=payload.use_character_references,
    ):
        db.add(
            GenerationStep(
                task_id=task.id,
                step_name=step_name,
                idempotency_key=f"{task.id}:{step_name.value}",
            )
        )

    try:
        snapshot_task_style_reference_images(db=db, task=task, style=style)
    except ImageProviderConfigError:
        raise
    db.flush()
    return task
