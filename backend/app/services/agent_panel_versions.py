from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import json

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.entities import (
    AgentConversation,
    AgentEvent,
    AgentMessage,
    AgentRun,
    AgentStep,
    GeneratedImage,
    GenerationTask,
    TaskPanel,
    new_id,
)
from app.models.enums import (
    AgentConversationStatus,
    AgentEventType,
    AgentMessageRole,
    AgentRunStatus,
    AgentStepType,
    GeneratedImageStatus,
)
from app.schemas.agent import (
    AgentPanelRegenerationCreate,
    AgentResourceKind,
    AgentResourceRef,
)
from app.services.agent_hitl import emit_agent_event
from app.services.agent_resources import AgentResourceResolver
from app.services.agent_tool_runtime import (
    GenericToolExecutor,
    build_runtime_context,
    create_default_tool_registry,
)


class AgentPanelVersionError(RuntimeError):
    def __init__(self, message: str, *, status_code: int = 400):
        super().__init__(message)
        self.status_code = status_code


@dataclass(frozen=True)
class RevisionRunOutcome:
    state: str
    message: str


def load_agent_task_chain(
    db: Session,
    *,
    conversation_id: str,
    task_id: str,
    panel_id: str | None,
    image_id: str | None,
    owner_user_id: str,
) -> tuple[AgentConversation, GenerationTask, TaskPanel | None, GeneratedImage | None]:
    conversation = db.scalar(
        select(AgentConversation).where(
            AgentConversation.id == conversation_id,
            AgentConversation.owner_user_id == owner_user_id,
        )
    )
    if conversation is None:
        raise AgentPanelVersionError("Agent 会话不存在", status_code=404)
    task = db.scalar(
        select(GenerationTask)
        .join(AgentRun, AgentRun.task_id == GenerationTask.id)
        .where(
            GenerationTask.id == task_id,
            GenerationTask.owner_user_id == owner_user_id,
            AgentRun.conversation_id == conversation.id,
        )
        .limit(1)
    )
    if task is None:
        raise AgentPanelVersionError("当前 Agent 会话未关联该任务", status_code=404)
    panel = None
    if panel_id is not None:
        panel = db.scalar(
            select(TaskPanel).where(
                TaskPanel.id == panel_id,
                TaskPanel.task_id == task.id,
            )
        )
        if panel is None:
            raise AgentPanelVersionError("Panel 不属于当前任务", status_code=404)
    image = None
    if image_id is not None:
        image = db.scalar(
            select(GeneratedImage).where(
                GeneratedImage.id == image_id,
                GeneratedImage.task_id == task.id,
                GeneratedImage.panel_id == (panel.id if panel is not None else None),
            )
        )
        if image is None:
            raise AgentPanelVersionError("图片版本不属于当前 Panel", status_code=404)
    return conversation, task, panel, image


def latest_linked_run(
    db: Session,
    *,
    conversation_id: str,
    task_id: str,
) -> AgentRun:
    run = db.scalar(
        select(AgentRun)
        .where(
            AgentRun.conversation_id == conversation_id,
            AgentRun.task_id == task_id,
        )
        .order_by(AgentRun.created_at.desc(), AgentRun.id.desc())
        .limit(1)
    )
    if run is None:
        raise AgentPanelVersionError("Agent 会话缺少任务运行记录", status_code=404)
    return run


def accept_image_version(
    db: Session,
    *,
    conversation_id: str,
    task_id: str,
    panel_id: str,
    image_id: str,
    owner_user_id: str,
) -> GeneratedImage:
    _, _, _, image = load_agent_task_chain(
        db,
        conversation_id=conversation_id,
        task_id=task_id,
        panel_id=panel_id,
        image_id=image_id,
        owner_user_id=owner_user_id,
    )
    assert image is not None
    if image.status != GeneratedImageStatus.succeeded or not image.is_current:
        raise AgentPanelVersionError("只能接受当前成功图片版本")
    if image.accepted_at is None:
        image.accepted_at = datetime.utcnow()
        image.accepted_by_user_id = owner_user_id
    run = latest_linked_run(db, conversation_id=conversation_id, task_id=task_id)
    emit_agent_event(
        db,
        run=run,
        event_type=AgentEventType.image_version_accepted,
        payload={
            "task_id": task_id,
            "panel_id": panel_id,
            "image_version_id": image.id,
            "generation_number": image.generation_number,
        },
        deduplicate=True,
    )
    db.commit()
    db.refresh(image)
    return image


def restore_image_version(
    db: Session,
    *,
    conversation_id: str,
    task_id: str,
    panel_id: str,
    image_id: str,
    owner_user_id: str,
) -> GeneratedImage:
    _, _, panel, image = load_agent_task_chain(
        db,
        conversation_id=conversation_id,
        task_id=task_id,
        panel_id=panel_id,
        image_id=image_id,
        owner_user_id=owner_user_id,
    )
    assert panel is not None and image is not None
    if image.status != GeneratedImageStatus.succeeded or image.asset_id is None:
        raise AgentPanelVersionError("只能恢复成功且具有资产的图片版本")
    if not image.is_current:
        db.execute(
            update(GeneratedImage)
            .where(
                GeneratedImage.panel_id == panel.id,
                GeneratedImage.id != image.id,
                GeneratedImage.is_current.is_(True),
            )
            .values(is_current=False)
        )
        image.is_current = True
    run = latest_linked_run(db, conversation_id=conversation_id, task_id=task_id)
    emit_agent_event(
        db,
        run=run,
        event_type=AgentEventType.image_version_restored,
        payload={
            "task_id": task_id,
            "panel_id": panel_id,
            "image_version_id": image.id,
            "generation_number": image.generation_number,
        },
        deduplicate=True,
    )
    db.commit()
    db.refresh(image)
    return image


def _next_message_sequence(db: Session, conversation_id: str) -> int:
    maximum = db.scalar(
        select(func.max(AgentMessage.sequence)).where(
            AgentMessage.conversation_id == conversation_id
        )
    )
    return int(maximum or 0) + 1


def start_panel_regeneration(
    db: Session,
    *,
    conversation_id: str,
    task_id: str,
    panel_id: str,
    payload: AgentPanelRegenerationCreate,
    owner_user_id: str,
) -> AgentRun:
    conversation, task, panel, source = load_agent_task_chain(
        db,
        conversation_id=conversation_id,
        task_id=task_id,
        panel_id=panel_id,
        image_id=payload.source_image_version_id,
        owner_user_id=owner_user_id,
    )
    assert panel is not None and source is not None
    if conversation.status != AgentConversationStatus.active:
        raise AgentPanelVersionError("已归档会话不能创建新版本")
    if source.status != GeneratedImageStatus.succeeded or source.asset_id is None:
        raise AgentPanelVersionError("来源图片版本尚未成功")
    active = db.scalar(
        select(GeneratedImage).where(
            GeneratedImage.panel_id == panel.id,
            GeneratedImage.status.in_(
                [GeneratedImageStatus.queued, GeneratedImageStatus.running]
            ),
        )
    )
    if active is not None:
        raise AgentPanelVersionError("该 Panel 已有图片版本正在生成", status_code=409)
    resolved = AgentResourceResolver().resolve(
        db,
        owner_user_id=owner_user_id,
        refs=[
            AgentResourceRef(kind=AgentResourceKind.task, id=task.id),
            AgentResourceRef(kind=AgentResourceKind.panel, id=panel.id),
            AgentResourceRef(kind=AgentResourceKind.image_version, id=source.id),
        ],
    )
    turn_id = new_id()
    message = AgentMessage(
        conversation_id=conversation.id,
        turn_id=turn_id,
        role=AgentMessageRole.user,
        content=payload.instruction.strip(),
        resource_refs_json=json.dumps(
            [item.model_dump(mode="json") for item in resolved.refs],
            ensure_ascii=False,
        ),
        sequence=_next_message_sequence(db, conversation.id),
    )
    run = AgentRun(
        conversation_id=conversation.id,
        turn_id=turn_id,
        task_id=task.id,
        status=AgentRunStatus.running,
        started_at=datetime.utcnow(),
    )
    db.add_all([message, run])
    db.commit()
    db.refresh(run)
    context = build_runtime_context(db, run, image_budget_limit=2)
    panel_key = f"panel-{panel.panel_order}"
    result = GenericToolExecutor(create_default_tool_registry()).execute(
        db,
        run=run,
        tool_name="generate_image",
        arguments={
            "panel_key": panel_key,
            "purpose": "panel_image",
            "prompt": source.final_prompt
            or source.image_prompt
            or panel.generated_prompt
            or "",
            "aspect_ratio": task.style_aspect_ratio_snapshot,
            "reference_image_ids": sorted(context.authorized_reference_image_ids),
            "revision_instruction": payload.instruction.strip(),
            "source_image_version_id": source.id,
            "allow_auto_revision": payload.allow_auto_revision,
        },
        idempotency_key=f"agent:{run.id}:generate_image:{panel_key}:revision",
        context=context,
    )
    checkpoint = result.checkpoint or {}
    emit_agent_event(
        db,
        run=run,
        event_type=AgentEventType.panel_revision_requested,
        payload={
            "task_id": task.id,
            "panel_id": panel.id,
            "source_image_version_id": source.id,
            "expected_credit_cost": 1,
            "auto_revision_authorized": payload.allow_auto_revision,
        },
    )
    emit_agent_event(
        db,
        run=run,
        event_type=AgentEventType.image_version_created,
        payload={
            "task_id": task.id,
            "panel_id": panel.id,
            "image_version_id": checkpoint.get("image_job_id"),
            "status": "queued",
        },
    )
    emit_agent_event(
        db,
        run=run,
        event_type=AgentEventType.tool_started,
        payload={
            "tool": "generate_image",
            "panel_key": panel_key,
            "image_job_id": checkpoint.get("image_job_id"),
        },
    )
    db.commit()
    return run


def _tool_calls(db: Session, run_id: str) -> list[tuple[AgentStep, dict[str, object]]]:
    calls = db.scalars(
        select(AgentStep)
        .where(
            AgentStep.run_id == run_id,
            AgentStep.step_type == AgentStepType.tool_call,
        )
        .order_by(AgentStep.sequence)
    ).all()
    result: list[tuple[AgentStep, dict[str, object]]] = []
    for step in calls:
        try:
            payload = json.loads(step.input_ref or "")
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            result.append((step, payload))
    return result


def is_panel_revision_run(db: Session, run_id: str) -> bool:
    return any(
        payload.get("tool") == "generate_image"
        and isinstance(payload.get("arguments"), dict)
        and payload["arguments"].get("revision_instruction")
        for _, payload in _tool_calls(db, run_id)
    )


def _image_output(image: GeneratedImage, panel_key: str) -> dict[str, object]:
    if image.status == GeneratedImageStatus.succeeded and image.asset_id is not None:
        return {
            "status": "succeeded",
            "panel_key": panel_key,
            "image_version_id": image.id,
            "asset_id": image.asset_id,
            "width": image.asset.width if image.asset else None,
            "height": image.asset.height if image.asset else None,
            "provider": get_settings().image_provider,
            "model": image.image_model_name_snapshot,
            "provider_request_id": image.provider_request_id,
        }
    return {
        "status": "failed",
        "panel_key": panel_key,
        "error_code": image.error_code or "ImageGenerationFailed",
        "message": image.error_message or "图片生成失败",
        "retryable": False,
    }


def _inspection_expected(panel: TaskPanel, image: GeneratedImage) -> dict[str, object]:
    required_text: list[str] = []
    try:
        image_text = json.loads(image.image_text_json or panel.image_text_json or "{}")
    except json.JSONDecodeError:
        image_text = {}
    if isinstance(image_text, dict):
        for value in image_text.values():
            if isinstance(value, str) and value.strip():
                required_text.append(value.strip())
            elif isinstance(value, list):
                required_text.extend(
                    item.strip() for item in value if isinstance(item, str) and item.strip()
                )
    return {
        "story_beat": panel.original_text_segment,
        "characters": [],
        "required_text": required_text[:50],
    }


def process_panel_revision_run(db: Session, run: AgentRun) -> RevisionRunOutcome | None:
    calls = [
        (step, payload)
        for step, payload in _tool_calls(db, run.id)
        if payload.get("tool") == "generate_image"
        and isinstance(payload.get("arguments"), dict)
        and payload["arguments"].get("revision_instruction")
    ]
    if not calls:
        return None
    has_auto_call = any(
        (step.idempotency_key or "").endswith(":auto-revision")
        for step, _ in calls
    )
    executor = GenericToolExecutor(create_default_tool_registry())
    for call_step, payload in calls:
        arguments = payload["arguments"]
        checkpoint = json.loads(call_step.output_ref or "{}")
        image_id = checkpoint.get("image_job_id")
        image = db.get(GeneratedImage, image_id) if isinstance(image_id, str) else None
        if image is None:
            raise AgentPanelVersionError("Panel 再生成 checkpoint 缺少图片任务")
        if image.status in {GeneratedImageStatus.queued, GeneratedImageStatus.running}:
            run.status = AgentRunStatus.waiting_for_tool
            db.commit()
            return RevisionRunOutcome("waiting_tool", "图片版本仍在生成")
        panel_key = str(arguments["panel_key"])
        image_result = executor.complete_waiting(
            db,
            run=run,
            idempotency_key=call_step.idempotency_key or "",
            output=_image_output(image, panel_key),
        )
        if image_result.output and image_result.output["status"] == "failed":
            emit_agent_event(
                db,
                run=run,
                event_type=AgentEventType.tool_failed,
                payload={
                    "tool": "generate_image",
                    "panel_key": panel_key,
                    "image_version_id": image.id,
                    "error_code": image.error_code,
                },
                deduplicate=True,
            )
            db.commit()
            return RevisionRunOutcome(
                "completed",
                f"Panel 新版本生成失败：{image.error_message or '图片生成失败'}。旧版本保持不变。",
            )
        emit_agent_event(
            db,
            run=run,
            event_type=AgentEventType.tool_completed,
            payload={
                "tool": "generate_image",
                "panel_key": panel_key,
                "image_version_id": image.id,
                "status": "succeeded",
            },
            deduplicate=True,
        )
        inspection_key = f"agent:{run.id}:inspect_image:{image.id}"
        emit_agent_event(
            db,
            run=run,
            event_type=AgentEventType.image_inspection_started,
            payload={"image_version_id": image.id, "panel_id": image.panel_id},
            deduplicate=True,
        )
        inspection = executor.execute(
            db,
            run=run,
            tool_name="inspect_image",
            arguments={
                "image_version_ids": [image.id],
                "checks": [
                    "story_alignment",
                    "character_consistency",
                    "continuity",
                    "text_accuracy",
                    "visual_artifacts",
                ],
                "expected": _inspection_expected(image.panel, image),
            },
            idempotency_key=inspection_key,
            context=build_runtime_context(db, run, image_budget_limit=2),
        )
        output = inspection.output or {}
        if output.get("status") != "succeeded":
            emit_agent_event(
                db,
                run=run,
                event_type=AgentEventType.image_inspection_completed,
                payload={
                    "image_version_id": image.id,
                    "status": "failed",
                    "error_code": output.get("error_code"),
                    "message": output.get("message"),
                    "inspected_at": datetime.utcnow().isoformat(),
                },
                deduplicate=True,
            )
            db.commit()
            return RevisionRunOutcome(
                "waiting_input",
                f"新版本 v{image.generation_number} 已生成，但真实 VL 检查失败："
                f"{output.get('message') or '检查服务返回失败'}。我没有把它标记为通过，也没有继续生图。",
            )
        event_payload = {
            "image_version_id": image.id,
            "panel_id": image.panel_id,
            "status": "succeeded",
            "verdict": output.get("verdict"),
            "scores": output.get("scores", {}),
            "issues": output.get("issues", []),
            "provider": output.get("provider"),
            "model": output.get("model"),
            "inspected_at": datetime.utcnow().isoformat(),
        }
        emit_agent_event(
            db,
            run=run,
            event_type=AgentEventType.image_inspection_completed,
            payload=event_payload,
            deduplicate=True,
        )
        db.commit()
        verdict = output.get("verdict")
        is_auto_call = (call_step.idempotency_key or "").endswith(":auto-revision")
        if has_auto_call and not is_auto_call:
            continue
        if (
            verdict == "revise"
            and bool(arguments.get("allow_auto_revision"))
            and not is_auto_call
            and run.image_call_count < 2
        ):
            issues = output.get("issues") or []
            instruction = "；".join(
                str(item.get("suggested_change") or item.get("message"))
                for item in issues
                if isinstance(item, dict)
            ).strip("；")
            if not instruction:
                return RevisionRunOutcome(
                    "waiting_input",
                    f"VL 建议修改 v{image.generation_number}，但没有给出可执行的修改说明，请你决定下一步。",
                )
            context = build_runtime_context(db, run, image_budget_limit=2)
            auto = executor.execute(
                db,
                run=run,
                tool_name="generate_image",
                arguments={
                    "panel_key": panel_key,
                    "purpose": "panel_image",
                    "prompt": image.final_prompt
                    or image.image_prompt
                    or image.panel.generated_prompt
                    or "",
                    "aspect_ratio": image.task.style_aspect_ratio_snapshot,
                    "reference_image_ids": sorted(context.authorized_reference_image_ids),
                    "revision_instruction": instruction,
                    "source_image_version_id": image.id,
                    "allow_auto_revision": False,
                },
                idempotency_key=f"agent:{run.id}:generate_image:{panel_key}:auto-revision",
                context=context,
            )
            emit_agent_event(
                db,
                run=run,
                event_type=AgentEventType.image_version_created,
                payload={
                    "task_id": image.task_id,
                    "panel_id": image.panel_id,
                    "image_version_id": (auto.checkpoint or {}).get("image_job_id"),
                    "status": "queued",
                    "automatic_revision": True,
                },
            )
            db.commit()
            return RevisionRunOutcome("waiting_tool", "已按授权创建一次自动修订")
        if verdict == "accept":
            return RevisionRunOutcome(
                "completed",
                f"Panel 新版本 v{image.generation_number} 已生成，VL 检查建议接受。"
                "我不会替你接受，请在检查器中确认。",
            )
        if verdict == "revise":
            return RevisionRunOutcome(
                "waiting_input",
                f"Panel 新版本 v{image.generation_number} 已生成，VL 建议修改。"
                "本轮不会再自动生图，请查看检查结果后决定。",
            )
        if verdict == "ask_user":
            return RevisionRunOutcome(
                "waiting_input",
                f"Panel 新版本 v{image.generation_number} 已生成，VL 证据不足，需要你决定是否接受。",
            )
        return RevisionRunOutcome(
            "waiting_input",
            f"Panel 新版本 v{image.generation_number} 已生成，但 VL 检查被阻断，未继续生图。",
        )
    return RevisionRunOutcome("waiting_tool", "等待图片版本完成")


def inspection_events_for_conversation(
    db: Session,
    conversation_id: str,
) -> dict[str, dict[str, object]]:
    events = db.scalars(
        select(AgentEvent)
        .where(
            AgentEvent.conversation_id == conversation_id,
            AgentEvent.event_type == AgentEventType.image_inspection_completed,
        )
        .order_by(AgentEvent.created_at.asc(), AgentEvent.sequence.asc())
        .limit(500)
    ).all()
    result: dict[str, dict[str, object]] = {}
    for event in events:
        try:
            payload = json.loads(event.public_payload_json)
        except json.JSONDecodeError:
            continue
        image_id = payload.get("image_version_id") if isinstance(payload, dict) else None
        if isinstance(image_id, str):
            result[image_id] = payload
    return result
