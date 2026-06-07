import logging
from dataclasses import dataclass

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.entities import (
    FileAsset,
    GenerationTask,
    TaskCharacter,
    TaskCharacterAppearance,
    TaskPanel,
    TaskPanelCharacterAppearance,
)
from app.models.enums import FileAssetPurpose, WorkflowStatus
from app.services.image_generation import (
    ImageProviderConfigError,
    ImageProviderResponseError,
    ImageReference,
    generate_xg_image,
)
from app.services.llm import LLMResponseError, TaskCharacterPlan
from app.services.prompt_logging import log_prompt_trace
from app.services.prompt_templates import render_prompt_template
from app.services.storage import asset_content_url

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PanelReferencePack:
    references: list[ImageReference]
    notes: list[str]
    character_count: int


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


def build_character_reference_prompt(
    *,
    style_prompt: str,
    aspect_ratio: str,
    character_name: str,
    age_stage: str | None,
    visual_prompt: str,
) -> str:
    return render_prompt_template(
        "character_reference_image_prompt_v1.md",
        {
            "style_prompt": style_prompt.strip(),
            "aspect_ratio": aspect_ratio,
            "character_name": character_name,
            "age_stage": age_stage.strip() if age_stage else "未指定",
            "visual_prompt": visual_prompt.strip(),
        },
    )


def ensure_character_reference_images(
    *,
    db: Session,
    task: GenerationTask,
) -> None:
    characters = load_task_characters(db, task.id)
    for character in characters:
        for appearance in sorted(character.appearances, key=lambda item: item.appearance_key):
            if appearance.status == WorkflowStatus.succeeded and appearance.reference_image_id:
                continue
            appearance.status = WorkflowStatus.running
            appearance.error_code = None
            appearance.error_message = None
            appearance.reference_prompt = build_character_reference_prompt(
                style_prompt=task.style_prompt_snapshot,
                aspect_ratio=task.style_aspect_ratio_snapshot,
                character_name=character.name,
                age_stage=appearance.age_stage,
                visual_prompt=appearance.visual_prompt,
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
                reference_count=0,
            )
            db.commit()
            try:
                logger.info(
                    "character reference image request task_id=%s character_key=%s appearance_key=%s prompt_chars=%s reference_count=%s",
                    task.id,
                    character.character_key,
                    appearance.appearance_key,
                    len(appearance.reference_prompt or ""),
                    0,
                )
                generated = generate_xg_image(
                    prompt=appearance.reference_prompt or "",
                    references=[],
                    image_model_name=task.image_model_name_snapshot,
                    aspect_ratio=task.style_aspect_ratio_snapshot,
                )
                asset = FileAsset(
                    purpose=FileAssetPurpose.character_reference,
                    storage_backend=generated.storage_backend,
                    storage_key=generated.storage_key,
                    public_url=generated.public_url,
                    original_filename=generated.original_filename,
                    content_type=generated.content_type,
                    byte_size=generated.byte_size,
                    checksum_sha256=generated.checksum_sha256,
                )
                db.add(asset)
                db.flush()
                appearance.reference_image_id = asset.id
                appearance.provider_request_id = generated.provider_request_id
                appearance.status = WorkflowStatus.succeeded
                logger.info(
                    "character reference image succeeded task_id=%s appearance_key=%s asset_storage_key=%s bytes=%s",
                    task.id,
                    appearance.appearance_key,
                    generated.storage_key,
                    generated.byte_size,
                )
            except (ImageProviderConfigError, ImageProviderResponseError) as exc:
                appearance.status = WorkflowStatus.failed
                appearance.error_code = exc.__class__.__name__
                appearance.error_message = str(exc)
                db.commit()
                raise
            db.commit()


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
        notes.append(f"{character.name}参考（参考图{index}）")

    return PanelReferencePack(
        references=character_references,
        notes=notes,
        character_count=len(character_references),
    )
