from dataclasses import dataclass
import re

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.entities import GenerationStep, GenerationTask, Style, StyleReferenceImage, TaskCharacter, TaskCharacterAppearance, User, UserCharacter
from app.models.enums import (
    GenerationStepName,
    ImageCountMode,
    StoryInputMode,
    StyleStatus,
    TaskStatus,
    WorkflowStatus,
)
from app.schemas.task import TaskCreate
from app.services.image_generation import ImageProviderConfigError
from app.services.style_references import snapshot_task_style_reference_images


DOUYIN_SHARE_URL_PATTERN = re.compile(
    r"https?://(?:v\.douyin\.com/[A-Za-z0-9_.~%-]+/?|www\.douyin\.com/(?:video|note)/[A-Za-z0-9_.~%-]+(?:\?[^\s，,。！!？?；;]*)?)"
)


@dataclass(frozen=True)
class TaskCreationError(Exception):
    status_code: int
    detail: str

    def __str__(self) -> str:
        return self.detail


def task_progress_total_for_creation(task: GenerationTask) -> int:
    total = 1
    total += 1
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
    if DOUYIN_SHARE_URL_PATTERN.search(payload.original_text):
        raise TaskCreationError(status_code=400, detail="检测到抖音分享链接，请使用 DY爆款复刻创建任务")
    seen_sources: set[str] = set()
    seen_character_ids: set[str] = set()
    for item in payload.story_characters:
        source_name = item.source_name.strip()
        if not source_name:
            raise TaskCreationError(status_code=400, detail="绑定角色名字不能为空")
        if source_name in seen_sources:
            raise TaskCreationError(status_code=400, detail="同一个故事角色不能重复绑定")
        if item.user_character_id in seen_character_ids:
            raise TaskCreationError(status_code=400, detail="同一个角色资产不能在同一任务中重复绑定")
        seen_sources.add(source_name)
        seen_character_ids.add(item.user_character_id)


def load_user_characters_for_task(db: Session, payload: TaskCreate, user: User) -> dict[str, UserCharacter]:
    ids = [item.user_character_id for item in payload.story_characters]
    if not ids:
        return {}
    characters = db.scalars(
        select(UserCharacter).where(
            UserCharacter.id.in_(ids),
            UserCharacter.owner_user_id == user.id,
            UserCharacter.deleted_at.is_(None),
        )
    ).all()
    by_id = {character.id: character for character in characters}
    missing = [character_id for character_id in ids if character_id not in by_id]
    if missing:
        raise TaskCreationError(status_code=403, detail="只能绑定当前用户自己的角色")
    return by_id


def persist_fixed_task_characters(
    *,
    db: Session,
    task: GenerationTask,
    payload: TaskCreate,
    user_characters: dict[str, UserCharacter],
) -> None:
    for index, item in enumerate(payload.story_characters, start=1):
        user_character = user_characters[item.user_character_id]
        source_name = item.source_name.strip()
        description = user_character.description or f"{source_name} 的固定角色参考"
        character = TaskCharacter(
            task_id=task.id,
            character_key=f"fixed_{index}",
            name=source_name,
            description=description,
            importance="primary",
        )
        db.add(character)
        db.flush()
        db.add(
            TaskCharacterAppearance(
                task_character_id=character.id,
                appearance_key=f"fixed_{index}_default",
                age_stage="固定角色",
                visual_prompt=f"{source_name}：{description}",
                reference_image_id=user_character.reference_asset_id,
                status=WorkflowStatus.succeeded,
            )
        )


def create_generation_task_record(
    *,
    db: Session,
    payload: TaskCreate,
    user: User,
) -> GenerationTask:
    validate_task_create_payload(payload)
    style = load_active_style_for_task(db, payload.style_id)
    fixed_user_characters = load_user_characters_for_task(db, payload, user)
    use_character_references = payload.use_character_references or bool(payload.story_characters)

    display_title = payload.original_text.strip().replace("\n", " ")[:36] or "未命名任务"
    task = GenerationTask(
        owner_user_id=user.id,
        display_title=display_title,
        original_text=payload.original_text,
        story_input_mode=payload.story_input_mode,
        image_count_mode=payload.image_count_mode,
        requested_image_count=payload.requested_image_count,
        use_character_references=use_character_references,
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
    persist_fixed_task_characters(
        db=db,
        task=task,
        payload=payload,
        user_characters=fixed_user_characters,
    )

    for step_name in generation_step_names_for_task(
        story_input_mode=payload.story_input_mode,
        use_character_references=use_character_references,
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
