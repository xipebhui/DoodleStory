import logging
from dataclasses import dataclass
from datetime import datetime

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.entities import (
    FileAsset,
    GeneratedImage,
    GenerationTask,
    TaskCharacter,
    TaskCharacterAppearance,
    TaskPanel,
    TaskPanelCharacterAppearance,
)
from app.models.enums import (
    GeneratedImageJobKind,
    GeneratedImageSourceType,
    GeneratedImageStatus,
    GeneratedImageWorkflowStep,
    WorkflowStatus,
)
from app.services.image_generation import ImageProviderConfigError, ImageReference, image_gateway_reference_limit
from app.services.llm import LLMResponseError, TaskCharacterPlan
from app.services.prompt_logging import log_prompt_trace
from app.services.prompt_templates import render_prompt_template
from app.services.storage import asset_content_url
from app.services.style_references import StyleReferencePack, build_task_style_reference_pack

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PanelReferencePack:
    references: list[ImageReference]
    notes: list[str]
    character_count: int


@dataclass(frozen=True)
class CharacterReferenceJobPlan:
    created_count: int
    active_count: int
    succeeded_count: int
    failed_count: int


def load_task_characters(db: Session, task_id: str) -> list[TaskCharacter]:
    return db.scalars(
        select(TaskCharacter)
        .where(TaskCharacter.task_id == task_id)
        .options(
            selectinload(TaskCharacter.appearances).selectinload(TaskCharacterAppearance.reference_image),
        )
        .order_by(TaskCharacter.character_key.asc())
    ).all()


def characters_to_plans(characters: list[TaskCharacter]) -> list[TaskCharacterPlan]:
    return [
        TaskCharacterPlan(
            character_key=character.character_key,
            name=character.name,
            description=character.description,
            appearances=[
                {
                    "appearance_key": appearance.appearance_key,
                    "age_stage": appearance.age_stage,
                    "visual_prompt": appearance.visual_prompt,
                    "panel_orders": [],
                }
                for appearance in sorted(character.appearances, key=lambda item: item.appearance_key)
            ],
        )
        for character in sorted(characters, key=lambda item: item.character_key)
    ]


def is_fixed_task_character(character: TaskCharacter) -> bool:
    return character.character_key.startswith("fixed_")


def persist_character_plans(db: Session, task: GenerationTask, character_plans: list[TaskCharacterPlan]) -> None:
    for existing in load_task_characters(db, task.id):
        db.delete(existing)
    db.flush()
    for character_plan in character_plans:
        character = TaskCharacter(
            task_id=task.id,
            character_key=character_plan.character_key,
            name=character_plan.name,
            description=character_plan.description,
            importance="primary",
        )
        db.add(character)
        db.flush()
        for appearance_plan in character_plan.appearances:
            db.add(
                TaskCharacterAppearance(
                    task_character_id=character.id,
                    appearance_key=appearance_plan.appearance_key,
                    age_stage=appearance_plan.age_stage,
                    visual_prompt=appearance_plan.visual_prompt,
                    status=WorkflowStatus.queued,
                )
            )
    db.commit()


def persist_missing_generated_character_plans(
    db: Session,
    task: GenerationTask,
    character_plans: list[TaskCharacterPlan],
) -> list[TaskCharacterPlan]:
    existing_characters = load_task_characters(db, task.id)
    existing_names = {character.name.strip() for character in existing_characters if character.name.strip()}
    existing_keys = {character.character_key for character in existing_characters}
    existing_appearance_keys = {
        appearance.appearance_key
        for character in existing_characters
        for appearance in character.appearances
    }
    persisted: list[TaskCharacterPlan] = []
    for character_plan in character_plans:
        name = character_plan.name.strip()
        if not name or name in existing_names or character_plan.character_key in existing_keys:
            continue
        character = TaskCharacter(
            task_id=task.id,
            character_key=character_plan.character_key,
            name=character_plan.name,
            description=character_plan.description,
            importance="primary",
        )
        db.add(character)
        db.flush()
        for appearance_plan in character_plan.appearances:
            if appearance_plan.appearance_key in existing_appearance_keys:
                continue
            db.add(
                TaskCharacterAppearance(
                    task_character_id=character.id,
                    appearance_key=appearance_plan.appearance_key,
                    age_stage=appearance_plan.age_stage,
                    visual_prompt=appearance_plan.visual_prompt,
                    status=WorkflowStatus.queued,
                )
            )
            existing_appearance_keys.add(appearance_plan.appearance_key)
        existing_names.add(name)
        existing_keys.add(character_plan.character_key)
        persisted.append(character_plan)
    db.commit()
    return persisted


def build_character_reference_prompt(
    *,
    style_prompt: str,
    aspect_ratio: str,
    character_name: str,
    age_stage: str | None,
    visual_prompt: str,
    style_reference_notes: list[str] | None = None,
) -> str:
    style_instruction = character_reference_style_instruction(
        style_prompt=style_prompt,
        style_reference_notes=style_reference_notes,
    )
    return render_prompt_template(
        "character_reference_image_prompt_v1.md",
        {
            "style_instruction": style_instruction,
            "aspect_ratio": aspect_ratio,
            "character_name": character_name,
            "age_stage": age_stage.strip() if age_stage else "未指定",
            "visual_prompt": visual_prompt.strip(),
        },
    )


def character_reference_style_instruction(
    *,
    style_prompt: str,
    style_reference_notes: list[str] | None = None,
) -> str:
    notes = [note.strip() for note in style_reference_notes or [] if note.strip()]
    if notes:
        return "\n".join(
            [
                "风格参考图（必须直接用于这张人物参考图的画风、人物比例、线条、色彩、服装质感、五官表达和整体气质）：",
                f"请优先参考随请求提供的{'、'.join(notes)}。",
                "这些图片只作为风格参考，不代表人物身份或剧情内容；人物身份、年龄阶段和外观以本文字设定为准。",
            ]
        )
    return "\n".join(
        [
            "风格提示词（必须直接用于这张人物参考图的画风、人物比例、线条、色彩、服装质感、五官表达和整体气质）：",
            style_prompt.strip(),
        ]
    )


def build_character_style_reference_pack(task: GenerationTask) -> StyleReferencePack:
    reference_pack = build_task_style_reference_pack(task, start_index=1)
    reference_limit = image_gateway_reference_limit(task.image_model_name_snapshot)
    if len(reference_pack.references) <= reference_limit:
        return reference_pack

    logger.warning(
        "character style reference pack truncated task_id=%s image_model=%s original_reference_count=%s "
        "kept_reference_count=%s",
        task.id,
        task.image_model_name_snapshot,
        len(reference_pack.references),
        reference_limit,
    )
    return StyleReferencePack(
        references=reference_pack.references[:reference_limit],
        notes=reference_pack.notes[:reference_limit],
        style_count=reference_limit,
    )


def ensure_character_reference_image_jobs(
    *,
    db: Session,
    task: GenerationTask,
) -> CharacterReferenceJobPlan:
    characters = load_task_characters(db, task.id)
    created_count = 0
    active_count = 0
    succeeded_count = 0
    failed_count = 0
    style_reference_pack: StyleReferencePack | None = None
    for character in characters:
        for appearance in sorted(character.appearances, key=lambda item: item.appearance_key):
            if appearance.status == WorkflowStatus.succeeded and appearance.reference_image_id:
                succeeded_count += 1
                continue
            active_job = db.scalar(
                select(GeneratedImage)
                .where(
                    GeneratedImage.job_kind == GeneratedImageJobKind.character_reference,
                    GeneratedImage.character_appearance_id == appearance.id,
                    GeneratedImage.status.in_([GeneratedImageStatus.queued, GeneratedImageStatus.running]),
                )
                .order_by(GeneratedImage.created_at.desc())
            )
            if active_job is not None:
                active_count += 1
                if appearance.status not in {WorkflowStatus.queued, WorkflowStatus.running}:
                    appearance.status = WorkflowStatus.running
                continue
            if appearance.status == WorkflowStatus.failed:
                failed_count += 1
                continue

            appearance.status = WorkflowStatus.queued
            appearance.error_code = None
            appearance.error_message = None
            if style_reference_pack is None:
                style_reference_pack = build_character_style_reference_pack(task)
            appearance.reference_prompt = build_character_reference_prompt(
                style_prompt=task.style_prompt_snapshot,
                aspect_ratio=task.style_aspect_ratio_snapshot,
                character_name=character.name,
                age_stage=appearance.age_stage,
                visual_prompt=appearance.visual_prompt,
                style_reference_notes=style_reference_pack.notes,
            )
            log_prompt_trace(
                logger,
                "character_reference_prompt_composed",
                context={
                    "task_id": task.id,
                    "style_id": task.style_id,
                    "story_input_mode": task.story_input_mode.value,
                    "step": "generate_character_references",
                    "character_id": character.id,
                    "character_key": character.character_key,
                    "appearance_id": appearance.id,
                    "appearance_key": appearance.appearance_key,
                },
                character_name=character.name,
                age_stage=appearance.age_stage,
                visual_prompt=appearance.visual_prompt,
                reference_prompt_chars=len(appearance.reference_prompt or ""),
                reference_prompt=appearance.reference_prompt,
                reference_count=len(style_reference_pack.references),
                style_reference_count=style_reference_pack.style_count,
                reference_notes=style_reference_pack.notes,
            )
            image = GeneratedImage(
                task_id=task.id,
                panel_id=None,
                character_appearance_id=appearance.id,
                owner_user_id=task.owner_user_id,
                job_kind=GeneratedImageJobKind.character_reference,
                status=GeneratedImageStatus.queued,
                generation_number=1,
                is_current=False,
                source_type=GeneratedImageSourceType.retry if task.attempts > 0 else GeneratedImageSourceType.initial,
                workflow_step=GeneratedImageWorkflowStep.generate_image,
                queued_at=datetime.utcnow(),
                queue_group=task.owner_user_id,
                image_prompt=appearance.visual_prompt,
                final_prompt=appearance.reference_prompt,
                image_model_name_snapshot=task.image_model_name_snapshot,
            )
            db.add(image)
            db.flush()
            created_count += 1
            logger.info(
                "character reference image job created task_id=%s character_key=%s appearance_key=%s image_id=%s prompt_chars=%s",
                task.id,
                character.character_key,
                appearance.appearance_key,
                image.id,
                len(appearance.reference_prompt or ""),
            )
    db.commit()
    return CharacterReferenceJobPlan(
        created_count=created_count,
        active_count=active_count,
        succeeded_count=succeeded_count,
        failed_count=failed_count,
    )


def clear_panel_character_links(db: Session, task: GenerationTask) -> None:
    panel_ids = [panel.id for panel in task.panels]
    if not panel_ids:
        return
    for link in db.scalars(
        select(TaskPanelCharacterAppearance).where(TaskPanelCharacterAppearance.panel_id.in_(panel_ids))
    ).all():
        db.delete(link)
    db.flush()


def save_panel_character_links(
    *,
    db: Session,
    task: GenerationTask,
    panel: TaskPanel,
    appearance_keys: list[str],
    usage_notes: dict[str, str],
) -> None:
    appearances = {
        appearance.appearance_key: appearance
        for character in load_task_characters(db, task.id)
        for appearance in character.appearances
    }
    for reference_order, appearance_key in enumerate(appearance_keys, start=1):
        appearance = appearances.get(appearance_key)
        if appearance is None:
            raise LLMResponseError(f"panel 引用了不存在的人物 appearance_key：{appearance_key}")
        db.add(
            TaskPanelCharacterAppearance(
                panel_id=panel.id,
                task_character_appearance_id=appearance.id,
                reference_order=reference_order,
                usage_note=usage_notes.get(appearance_key),
            )
        )


def save_character_plan_panel_links(
    *,
    db: Session,
    task: GenerationTask,
    character_plans: list[TaskCharacterPlan],
) -> None:
    clear_panel_character_links(db, task)
    panels_by_order = {panel.panel_order: panel for panel in task.panels}
    appearances = {
        appearance.appearance_key: appearance
        for character in load_task_characters(db, task.id)
        for appearance in character.appearances
    }
    panel_keys: dict[int, list[tuple[str, str]]] = {}
    for character_plan in character_plans:
        for appearance_plan in character_plan.appearances:
            stage = f" · {appearance_plan.age_stage}" if appearance_plan.age_stage else ""
            note = f"{character_plan.name}{stage}，主要人物参考"
            for panel_order in appearance_plan.panel_orders:
                panel_keys.setdefault(panel_order, []).append((appearance_plan.appearance_key, note))

    for panel_order, key_notes in panel_keys.items():
        panel = panels_by_order.get(panel_order)
        if panel is None:
            raise LLMResponseError(f"人物 appearance 引用了不存在的 panel_order：{panel_order}")
        seen_keys: set[str] = set()
        reference_order = 1
        for appearance_key, note in key_notes:
            if appearance_key in seen_keys:
                continue
            seen_keys.add(appearance_key)
            appearance = appearances.get(appearance_key)
            if appearance is None:
                raise LLMResponseError(f"人物 appearance_key 尚未持久化：{appearance_key}")
            db.add(
                TaskPanelCharacterAppearance(
                    panel_id=panel.id,
                    task_character_appearance_id=appearance.id,
                    reference_order=reference_order,
                    usage_note=note,
                )
            )
            reference_order += 1


def ensure_fixed_character_panel_links_by_name(db: Session, task: GenerationTask) -> None:
    panels = sorted(task.panels, key=lambda item: item.panel_order)
    if not panels:
        return

    characters = [character for character in load_task_characters(db, task.id) if is_fixed_task_character(character)]
    reference_order_by_panel: dict[str, int] = {}
    linked_appearance_ids_by_panel = {
        panel.id: {link.task_character_appearance_id for link in panel.character_appearances}
        for panel in panels
    }
    for character in characters:
        appearances = sorted(character.appearances, key=lambda item: item.appearance_key)
        if not appearances:
            continue
        appearance = appearances[0]
        if appearance.status != WorkflowStatus.succeeded or appearance.reference_image_id is None:
            continue
        name = character.name.strip()
        if not name:
            continue
        for panel in panels:
            haystack = "\n".join(
                value or ""
                for value in [
                    panel.original_text_segment,
                    panel.narration_text,
                    panel.dialogue_text,
                    panel.generated_prompt,
                    panel.image_text_json,
                    panel.text_layout,
                ]
            )
            if name not in haystack:
                continue
            if appearance.id in linked_appearance_ids_by_panel.get(panel.id, set()):
                continue
            existing_orders = [link.reference_order for link in panel.character_appearances]
            reference_order = reference_order_by_panel.get(panel.id, max(existing_orders, default=0) + 1)
            db.add(
                TaskPanelCharacterAppearance(
                    panel_id=panel.id,
                    task_character_appearance_id=appearance.id,
                    reference_order=reference_order,
                    usage_note=f"{name}，用户固定角色参考",
                )
            )
            reference_order_by_panel[panel.id] = reference_order + 1
    db.flush()


def reference_asset_public_url(asset: FileAsset) -> str | None:
    if asset.public_url and asset.public_url.strip():
        return asset.public_url.strip()
    try:
        return asset_content_url(asset)
    except HTTPException as exc:
        logger.info("character reference asset has no public url asset_id=%s reason=%s", asset.id, exc.detail)
        return None


def build_panel_reference_pack(
    *,
    panel: TaskPanel,
) -> PanelReferencePack:
    character_references: list[ImageReference] = []
    notes: list[str] = []
    sorted_links = sorted(panel.character_appearances, key=lambda item: item.reference_order)
    for index, link in enumerate(sorted_links, start=1):
        appearance = link.appearance
        character = appearance.character
        if appearance.status != WorkflowStatus.succeeded or appearance.reference_image is None:
            raise ImageProviderConfigError(f"人物参考图尚未生成成功：{character.name}")
        character_references.append(
            ImageReference(
                url=reference_asset_public_url(appearance.reference_image),
            )
        )
        anchor = appearance.visual_prompt or character.description or character.name
        notes.append(
            "\n".join(
                [
                    f"固定角色参考（参考图{index}）：{character.name}",
                    f"外观锁定：{anchor}",
                    "参考强度：固定角色身份 > 当前剧情动作/情绪 > 风格表现方式 > 风格模板默认人物外观。",
                    "一致性规则：保持该角色的年龄阶段、发型、体态、服装轮廓和标志性配饰不变；表情、姿势、动作、光照可随当前剧情变化；颜色可按当前画风转译。",
                ]
            )
        )

    return PanelReferencePack(
        references=character_references,
        notes=notes,
        character_count=len(character_references),
    )
