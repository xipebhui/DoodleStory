from __future__ import annotations

from datetime import datetime
import json

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.core.config import get_settings
from app.models.entities import (
    AgentMessage,
    AgentRun,
    CreditTransaction,
    GeneratedImage,
    GenerationStep,
    GenerationTask,
    Style,
    StyleReferenceImage,
    TaskCharacter,
    TaskCharacterAppearance,
    TaskPanel,
    TaskPanelCharacterAppearance,
    UserCharacter,
)
from app.models.enums import (
    AgentMessageRole,
    AgentRunStatus,
    GeneratedImageStatus,
    GenerationStepName,
    ImageCountMode,
    PanelType,
    PromptStatus,
    StepStatus,
    StoryInputMode,
    StyleStatus,
    TaskStatus,
    WorkflowStatus,
)
from app.schemas.agent import ComicPlan
from app.services.image_generation import ImageProviderConfigError
from app.services.agent_tool_runtime import (
    GenericToolExecutor,
    build_runtime_context,
    create_default_tool_registry,
)
from app.services.style_references import snapshot_task_style_reference_images
from app.services.agent_hitl import emit_agent_event
from app.models.enums import AgentEventType


class AgentComicCreationError(RuntimeError):
    pass


def _json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def _next_message_sequence(db: Session, conversation_id: str) -> int:
    maximum = db.scalar(
        select(func.max(AgentMessage.sequence)).where(AgentMessage.conversation_id == conversation_id)
    )
    return int(maximum or 0) + 1


def load_authorized_style(db: Session, style_id: str) -> Style:
    style = db.scalar(
        select(Style)
        .where(
            Style.id == style_id,
            Style.deleted_at.is_(None),
            Style.status == StyleStatus.active,
        )
        .options(selectinload(Style.reference_images).selectinload(StyleReferenceImage.asset))
    )
    if style is None:
        raise AgentComicCreationError("所选风格不存在、已删除或未启用")
    if not style.image_model_name.strip():
        raise AgentComicCreationError("所选风格尚未绑定生图模型")
    return style


def build_style_context(style: Style) -> dict[str, object]:
    return {
        "id": style.id,
        "name": style.name,
        "style_prompt": style.style_prompt,
        "aspect_ratio": style.aspect_ratio,
        "reference_mode": style.style_reference_mode.value,
        "image_model": style.image_model_name,
    }


def create_comic_task_and_image_tools(
    *,
    db: Session,
    run: AgentRun,
    user_message: AgentMessage,
    style: Style,
    plan: ComicPlan,
    characters: list[UserCharacter],
) -> GenerationTask:
    if plan.style_ref_id != style.id:
        raise AgentComicCreationError("ComicPlan style_ref_id 与已鉴权风格不一致")
    if plan.aspect_ratio != style.aspect_ratio:
        raise AgentComicCreationError("ComicPlan 画面比例与数据库风格快照不一致")
    task = db.get(GenerationTask, run.task_id) if run.task_id else None
    if run.task_id and task is None:
        raise AgentComicCreationError("Agent Run 关联的漫画任务不存在")

    if task is None:
        task = GenerationTask(
            owner_user_id=run.conversation.owner_user_id,
            display_title=plan.title,
            original_text=user_message.content,
            story_input_mode=StoryInputMode.adapted,
            adapted_story_title=plan.title,
            adapted_story_hook=plan.story_summary,
            adapted_story_text=plan.story_summary,
            image_count_mode=ImageCountMode.fixed,
            requested_image_count=len(plan.panels),
            use_character_references=bool(characters),
            last_panel_real_photo=False,
            remove_image_text=False,
            style_id=style.id,
            style_name_snapshot=style.name,
            style_prompt_snapshot=style.style_prompt,
            image_model_name_snapshot=style.image_model_name,
            style_aspect_ratio_snapshot=plan.aspect_ratio,
            style_reference_mode_snapshot=style.style_reference_mode,
            status=TaskStatus.running,
            current_step=GenerationStepName.generate_images,
            progress_current=0,
            progress_total=1,
            started_at=datetime.utcnow(),
        )
        db.add(task)
        db.flush()
        try:
            snapshot_task_style_reference_images(db=db, task=task, style=style)
        except ImageProviderConfigError as exc:
            raise AgentComicCreationError(str(exc)) from exc

        generation_step = GenerationStep(
            task_id=task.id,
            step_name=GenerationStepName.generate_images,
            status=StepStatus.running,
            attempts=1,
            idempotency_key=f"{task.id}:{GenerationStepName.generate_images.value}",
            started_at=datetime.utcnow(),
        )
        db.add(generation_step)

        panels: list[TaskPanel] = []
        for order, planned_panel in enumerate(plan.panels, start=1):
            panel = TaskPanel(
                task_id=task.id,
                panel_order=order,
                panel_type=PanelType.scene,
                original_text_segment=planned_panel.story_beat,
                narration_text="\n".join(planned_panel.required_text) or None,
                dialogue_text=None,
                image_text_json=_json({"required_text": planned_panel.required_text}),
                text_layout=planned_panel.visual_goal,
                prompt_status=PromptStatus.generated,
                generated_prompt=planned_panel.image_prompt,
                prompt_model_snapshot="agent:gpt-5.5",
            )
            db.add(panel)
            panels.append(panel)
        db.flush()
        for character_order, user_character in enumerate(characters, start=1):
            description = user_character.description or f"{user_character.name} 的固定角色参考"
            task_character = TaskCharacter(
                task_id=task.id,
                character_key=f"fixed_{character_order}",
                name=user_character.name,
                description=description,
                importance="primary",
            )
            db.add(task_character)
            db.flush()
            appearance = TaskCharacterAppearance(
                task_character_id=task_character.id,
                appearance_key=f"fixed_{character_order}_default",
                age_stage="固定角色",
                visual_prompt=f"{user_character.name}：{description}",
                reference_image_id=user_character.reference_asset_id,
                status=WorkflowStatus.succeeded,
            )
            db.add(appearance)
            db.flush()
            for panel in panels:
                db.add(
                    TaskPanelCharacterAppearance(
                        panel_id=panel.id,
                        task_character_appearance_id=appearance.id,
                        reference_order=character_order,
                        usage_note="Agent 用户显式引用的固定角色",
                    )
                )
        run.task_id = task.id
        db.commit()
        db.refresh(task)
    else:
        panels = db.scalars(
            select(TaskPanel)
            .where(TaskPanel.task_id == task.id)
            .order_by(TaskPanel.panel_order)
        ).all()
        if len(panels) != len(plan.panels):
            raise AgentComicCreationError("Agent 漫画任务的 Panel checkpoint 与计划不一致")

    reference_image_ids = [
        reference.asset_id
        for reference in sorted(
            task.style_reference_images,
            key=lambda item: item.reference_order,
        )
    ] + [
        appearance.reference_image_id
        for character in task.characters
        for appearance in character.appearances
        if appearance.reference_image_id is not None
    ]
    executor = GenericToolExecutor(create_default_tool_registry())
    runtime_context = build_runtime_context(
        db,
        run,
        image_budget_limit=len(plan.panels),
    )
    for planned_panel in plan.panels:
        execution = executor.execute(
            db,
            run=run,
            tool_name="generate_image",
            arguments={
                "panel_key": planned_panel.panel_key,
                "purpose": "panel_image",
                "prompt": planned_panel.image_prompt,
                "aspect_ratio": plan.aspect_ratio,
                "reference_image_ids": reference_image_ids,
            },
            idempotency_key=(
                f"agent:{run.id}:generate_image:{planned_panel.panel_key}"
            ),
            context=runtime_context,
        )
        emit_agent_event(
            db,
            run=run,
            event_type=AgentEventType.tool_started,
            payload={
                "tool": "generate_image",
                "panel_key": planned_panel.panel_key,
                "image_job_id": (execution.checkpoint or {}).get("image_job_id"),
            },
            deduplicate=True,
        )
        emit_agent_event(
            db,
            run=run,
            event_type=AgentEventType.tool_progress,
            payload={
                "tool": "generate_image",
                "panel_key": planned_panel.panel_key,
                "status": "queued",
            },
            deduplicate=True,
        )
        db.commit()

    existing_task_card = db.scalar(
        select(AgentMessage).where(
            AgentMessage.conversation_id == run.conversation_id,
            AgentMessage.turn_id == run.turn_id,
            AgentMessage.role == AgentMessageRole.task_card,
        )
    )
    if existing_task_card is None:
        db.add(
            AgentMessage(
                conversation_id=run.conversation_id,
                turn_id=run.turn_id,
                role=AgentMessageRole.task_card,
                content=_json({"task_id": task.id, "title": task.display_title}),
                sequence=_next_message_sequence(db, run.conversation_id),
            )
        )
        db.commit()
    db.refresh(task)
    return task


def checkpoint_image_tool_results(db: Session, run: AgentRun) -> list[dict[str, object]] | None:
    if run.task_id is None:
        return None
    images = db.scalars(
        select(GeneratedImage)
        .join(TaskPanel, TaskPanel.id == GeneratedImage.panel_id)
        .where(GeneratedImage.task_id == run.task_id)
        .order_by(TaskPanel.panel_order.asc(), GeneratedImage.generation_number.asc())
    ).all()
    panel_count = db.scalar(
        select(func.count(TaskPanel.id)).where(TaskPanel.task_id == run.task_id)
    )
    if not panel_count or len(images) != panel_count:
        raise AgentComicCreationError("Agent 漫画任务的图片 job 数量与已批准方案不一致")
    if any(image.status in {GeneratedImageStatus.queued, GeneratedImageStatus.running} for image in images):
        return None

    outputs: list[dict[str, object]] = []
    credit_changes = {
        image_id: amount
        for image_id, amount in db.execute(
            select(
                CreditTransaction.generated_image_id,
                func.coalesce(func.sum(CreditTransaction.amount), 0),
            )
            .where(CreditTransaction.generated_image_id.in_([image.id for image in images]))
            .group_by(CreditTransaction.generated_image_id)
        ).all()
        if image_id is not None
    }
    executor = GenericToolExecutor(create_default_tool_registry())
    for index, image in enumerate(images, start=1):
        if image.status == GeneratedImageStatus.succeeded and image.asset_id:
            output: dict[str, object] = {
                "status": "succeeded",
                "panel_key": f"panel-{index}",
                "image_version_id": image.id,
                "asset_id": image.asset_id,
                "width": image.asset.width if image.asset is not None else None,
                "height": image.asset.height if image.asset is not None else None,
                "provider": get_settings().image_provider,
                "provider_request_id": image.provider_request_id,
                "model": image.image_model_name_snapshot,
            }
        else:
            output = {
                "status": "failed",
                "panel_key": f"panel-{index}",
                "error_code": image.error_code or "ImageGenerationFailed",
                "message": image.error_message or "图片生成失败",
                "retryable": False,
            }
        outputs.append(output)
        executor.complete_waiting(
            db,
            run=run,
            idempotency_key=f"agent:{run.id}:generate_image:panel-{index}",
            output=output,
            trace_attributes={
                "credit_change": credit_changes.get(image.id, 0),
            },
        )
        emit_agent_event(
            db,
            run=run,
            event_type=(
                AgentEventType.tool_completed
                if output["status"] == "succeeded"
                else AgentEventType.tool_failed
            ),
            payload={
                "tool": "generate_image",
                "panel_key": f"panel-{index}",
                "status": output["status"],
                "image_version_id": output.get("image_version_id"),
                "error_code": output.get("error_code"),
            },
            deduplicate=True,
        )
    run.status = AgentRunStatus.running
    db.commit()
    return outputs
