from __future__ import annotations

from datetime import datetime
import json

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.models.entities import (
    AgentMessage,
    AgentRun,
    AgentStep,
    CreditTransaction,
    GeneratedImage,
    GenerationStep,
    GenerationTask,
    Style,
    StyleReferenceImage,
    TaskPanel,
)
from app.models.enums import (
    AgentMessageRole,
    AgentRunStatus,
    AgentStepStatus,
    AgentStepType,
    GeneratedImageJobKind,
    GeneratedImageSourceType,
    GeneratedImageStatus,
    GeneratedImageWorkflowStep,
    GenerationStepName,
    ImageCountMode,
    PanelType,
    PromptStatus,
    StepStatus,
    StoryInputMode,
    StyleStatus,
    TaskStatus,
)
from app.schemas.agent import AgentResourceKind, AgentResourceRef, ComicPlan
from app.services.image_generation import ImageProviderConfigError
from app.services.agent_observability import (
    agent_span,
    safe_idempotency_digest,
    set_span_result,
)
from app.services.style_references import snapshot_task_style_reference_images


class AgentComicCreationError(RuntimeError):
    pass


def _json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def _next_step_sequence(db: Session, run_id: str) -> int:
    maximum = db.scalar(select(func.max(AgentStep.sequence)).where(AgentStep.run_id == run_id))
    return int(maximum or 0) + 1


def _next_message_sequence(db: Session, conversation_id: str) -> int:
    maximum = db.scalar(
        select(func.max(AgentMessage.sequence)).where(AgentMessage.conversation_id == conversation_id)
    )
    return int(maximum or 0) + 1


def style_ref_from_message(message: AgentMessage) -> AgentResourceRef | None:
    if not message.resource_refs_json:
        return None
    try:
        refs = [AgentResourceRef.model_validate(item) for item in json.loads(message.resource_refs_json)]
    except (json.JSONDecodeError, TypeError, ValueError) as exc:
        raise AgentComicCreationError("Agent 消息的风格资源引用无法读取") from exc
    style_refs = [ref for ref in refs if ref.kind == AgentResourceKind.style]
    if not style_refs:
        return None
    if len(style_refs) != 1 or len(refs) != 1:
        raise AgentComicCreationError("Sprint 106 每轮只允许绑定一个风格资源")
    return style_refs[0]


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
) -> GenerationTask:
    if run.task_id:
        existing = db.get(GenerationTask, run.task_id)
        if existing is None:
            raise AgentComicCreationError("Agent Run 关联的漫画任务不存在")
        return existing

    task = GenerationTask(
        owner_user_id=run.conversation.owner_user_id,
        display_title=plan.title,
        original_text=user_message.content,
        story_input_mode=StoryInputMode.adapted,
        adapted_story_title=plan.title,
        adapted_story_hook=plan.summary,
        adapted_story_text=plan.summary,
        image_count_mode=ImageCountMode.fixed,
        requested_image_count=2,
        use_character_references=False,
        last_panel_real_photo=False,
        remove_image_text=False,
        style_id=style.id,
        style_name_snapshot=style.name,
        style_prompt_snapshot=style.style_prompt,
        image_model_name_snapshot=style.image_model_name,
        style_aspect_ratio_snapshot=style.aspect_ratio,
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

    tool_trace_records: list[dict[str, object]] = []
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
        db.flush()
        tool_key = f"agent:{run.id}:generate_image:{planned_panel.panel_key}"
        tool_step = AgentStep(
            run_id=run.id,
            sequence=_next_step_sequence(db, run.id),
            step_type=AgentStepType.tool_call,
            status=AgentStepStatus.succeeded,
            attempt=1,
            idempotency_key=tool_key,
            input_ref=_json(
                {
                    "tool": "generate_image",
                    "panel_key": planned_panel.panel_key,
                    "purpose": "panel_image",
                    "prompt": planned_panel.image_prompt,
                    "aspect_ratio": style.aspect_ratio,
                    "reference_image_ids": [
                        reference.asset_id
                        for reference in sorted(style.reference_images, key=lambda item: item.display_order)
                    ]
                    if style.style_reference_mode.value == "image"
                    else [],
                }
            ),
            started_at=datetime.utcnow(),
        )
        db.add(tool_step)
        db.flush()
        image = GeneratedImage(
            task_id=task.id,
            panel_id=panel.id,
            owner_user_id=run.conversation.owner_user_id,
            job_kind=GeneratedImageJobKind.panel_image,
            status=GeneratedImageStatus.queued,
            generation_number=1,
            is_current=False,
            source_type=GeneratedImageSourceType.initial,
            workflow_step=GeneratedImageWorkflowStep.generate_image,
            queued_at=datetime.utcnow(),
            queue_group=run.conversation.owner_user_id,
            image_prompt=planned_panel.image_prompt,
            image_text_json=panel.image_text_json,
            text_layout=planned_panel.visual_goal,
            final_prompt=planned_panel.image_prompt,
            image_model_name_snapshot=style.image_model_name,
        )
        db.add(image)
        db.flush()
        tool_step.output_ref = _json({"status": "queued", "image_job_id": image.id})
        tool_step.finished_at = datetime.utcnow()
        tool_trace_records.append(
            {
                "tool_name": "generate_image",
                "agent_step_id": tool_step.id,
                "idempotency_digest": safe_idempotency_digest(tool_key),
                "task_id": task.id,
                "panel_id": panel.id,
                "image_job_id": image.id,
                "tool_status": "queued",
                "image_call_count": 1,
                "credit_change": 0,
            }
        )

    run.task_id = task.id
    run.status = AgentRunStatus.waiting_for_tool
    run.image_call_count = 2
    db.add(
        AgentStep(
            run_id=run.id,
            sequence=_next_step_sequence(db, run.id),
            step_type=AgentStepType.wait,
            status=AgentStepStatus.running,
            attempt=1,
            idempotency_key=f"agent:{run.id}:wait:generate_image",
            input_ref=_json({"task_id": task.id, "image_job_count": 2}),
            started_at=datetime.utcnow(),
        )
    )
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
    for attributes in tool_trace_records:
        with agent_span(
            "agent.tool_call",
            agent_run_id=run.id,
            span_type="TOOL",
            attributes=attributes,
        ):
            pass
    db.refresh(task)
    return task


def checkpoint_image_tool_results(db: Session, run: AgentRun) -> list[dict[str, object]] | None:
    if run.task_id is None:
        return None
    images = db.scalars(
        select(GeneratedImage)
        .where(GeneratedImage.task_id == run.task_id)
        .order_by(GeneratedImage.generation_number.asc(), GeneratedImage.created_at.asc())
    ).all()
    if len(images) != 2:
        raise AgentComicCreationError("Agent 漫画任务没有且仅有两个图片 job")
    if any(image.status in {GeneratedImageStatus.queued, GeneratedImageStatus.running} for image in images):
        return None

    existing_results = {
        step.idempotency_key
        for step in db.scalars(
            select(AgentStep).where(
                AgentStep.run_id == run.id,
                AgentStep.step_type == AgentStepType.tool_result,
            )
        ).all()
    }
    outputs: list[dict[str, object]] = []
    tool_result_trace_records: list[tuple[dict[str, object], dict[str, object]]] = []
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
    for index, image in enumerate(images, start=1):
        if image.status == GeneratedImageStatus.succeeded and image.asset_id:
            output: dict[str, object] = {
                "status": "succeeded",
                "panel_key": f"panel-{index}",
                "image_version_id": image.id,
                "asset_id": image.asset_id,
                "provider_request_id": image.provider_request_id,
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
        result_key = f"agent:{run.id}:generate_image:panel-{index}:result"
        if result_key not in existing_results:
            result_step = AgentStep(
                run_id=run.id,
                sequence=_next_step_sequence(db, run.id),
                step_type=AgentStepType.tool_result,
                status=AgentStepStatus.succeeded,
                attempt=1,
                idempotency_key=result_key,
                input_ref=_json({"image_job_id": image.id}),
                output_ref=_json(output),
                started_at=datetime.utcnow(),
                finished_at=datetime.utcnow(),
            )
            db.add(result_step)
            db.flush()
            tool_result_trace_records.append(
                (
                    {
                        "tool_name": "generate_image",
                        "agent_step_id": result_step.id,
                        "idempotency_digest": safe_idempotency_digest(result_key),
                        "task_id": run.task_id,
                        "panel_id": image.panel_id,
                        "image_job_id": image.id,
                        "tool_status": output["status"],
                        "image_call_count": 1,
                        "credit_change": credit_changes.get(image.id, 0),
                    },
                    {
                        "provider_request_id": image.provider_request_id,
                        "error_code": image.error_code,
                    },
                )
            )

    wait_step = db.scalar(
        select(AgentStep).where(
            AgentStep.run_id == run.id,
            AgentStep.step_type == AgentStepType.wait,
            AgentStep.idempotency_key == f"agent:{run.id}:wait:generate_image",
        )
    )
    if wait_step is not None and wait_step.status == AgentStepStatus.running:
        wait_step.status = AgentStepStatus.succeeded
        wait_step.output_ref = _json(outputs)
        wait_step.finished_at = datetime.utcnow()
    run.status = AgentRunStatus.running
    db.commit()
    for attributes, result_attributes in tool_result_trace_records:
        with agent_span(
            "agent.tool_result",
            agent_run_id=run.id,
            span_type="TOOL",
            attributes=attributes,
        ) as span:
            set_span_result(span, result_attributes)
    return outputs
