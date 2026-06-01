import logging
from dataclasses import dataclass
from pathlib import Path

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
from app.services.image_generation import ImageProviderConfigError, ImageProviderResponseError, generate_xg_image
from app.services.llm import LLMResponseError, TaskCharacterPlan
from app.services.storage import resolve_storage_key

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PanelReferencePack:
    paths: list[Path]
    notes: list[str]
    character_count: int
    style_count: int


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
    stage = f" · {age_stage.strip()}" if age_stage else ""
    return "\n\n".join(
        [
            f"风格模板：{style_prompt.strip()}",
            f"画面比例：{aspect_ratio}",
            f"人物参考图：{character_name}{stage}",
            f"人物外观设定：{visual_prompt.strip()}",
            "生成要求：只生成这个人物的清晰角色参考图，保持正面或三分之二角度，完整呈现头发、脸部关键特征、服装、体态和标志物。",
            "禁止项：不要加入文字、标题、Logo、水印、对话框、复杂背景或其他主要人物。",
        ]
    )


def ensure_character_reference_images(
    *,
    db: Session,
    task: GenerationTask,
    style_reference_paths: list[Path],
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
            db.commit()
            try:
                logger.info(
                    "character reference image request task_id=%s character_key=%s appearance_key=%s prompt_chars=%s style_reference_count=%s",
                    task.id,
                    character.character_key,
                    appearance.appearance_key,
                    len(appearance.reference_prompt or ""),
                    len(style_reference_paths),
                )
                generated = generate_xg_image(
                    prompt=appearance.reference_prompt or "",
                    reference_paths=style_reference_paths,
                    image_model_name=task.image_model_name_snapshot,
                    aspect_ratio=task.style_aspect_ratio_snapshot,
                )
                asset = FileAsset(
                    purpose=FileAssetPurpose.character_reference,
                    storage_key=generated.storage_key,
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


def build_panel_reference_pack(
    *,
    panel: TaskPanel,
    style_reference_paths: list[Path],
) -> PanelReferencePack:
    character_paths: list[Path] = []
    notes: list[str] = []
    sorted_links = sorted(panel.character_appearances, key=lambda item: item.reference_order)
    for index, link in enumerate(sorted_links, start=1):
        appearance = link.appearance
        character = appearance.character
        if appearance.status != WorkflowStatus.succeeded or appearance.reference_image is None:
            raise ImageProviderConfigError(f"人物参考图尚未生成成功：{character.name}")
        character_paths.append(resolve_storage_key(appearance.reference_image.storage_key))
        stage = f" · {appearance.age_stage}" if appearance.age_stage else ""
        usage_note = f"，{link.usage_note}" if link.usage_note else ""
        notes.append(
            f"参考图{index}：{character.name}{stage}{usage_note}。必须保持该人物身份、年龄阶段、脸部关键特征、服装方向和标志物。"
        )

    paths = [*character_paths, *style_reference_paths]
    if character_paths and style_reference_paths:
        start = len(character_paths) + 1
        end = len(character_paths) + len(style_reference_paths)
        if start == end:
            notes.append(f"参考图{start}：风格参考图，用于保持整体画风、质感和色彩。")
        else:
            notes.append(f"参考图{start}-{end}：风格参考图，用于保持整体画风、质感和色彩。")
    return PanelReferencePack(
        paths=paths,
        notes=notes,
        character_count=len(character_paths),
        style_count=len(style_reference_paths),
    )
