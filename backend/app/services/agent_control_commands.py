from __future__ import annotations

import hashlib
import json

from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.entities import (
    DurableAgentAttempt,
    DurableAgentCommand,
    DurableAgentGate,
    DurableAgentTask,
    DurableAgentToolEffect,
    DurableAgentWorkflow,
    NativeAgentRun,
    NativeAgentArticleApproval,
    NativeAgentContextItem,
    NativeAgentItem,
    User,
)
from app.models.enums import AgentRunStatus, NativeAgentItemType
from app.schemas.native_agent import DurableControlCommandCreate
from app.services.durable_agent_runtime import (
    DurableAgentRuntimeError,
    cancel_durable_workflow,
    resolve_gate,
    resolve_unknown_tool_effect,
    resume_durable_workflow,
    retry_durable_task,
)
from app.services.native_agent_persistence import add_native_agent_event


class AgentControlCommandError(RuntimeError):
    pass


def _json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def _hash(value: object) -> str:
    return f"sha256:{hashlib.sha256(_json(value).encode('utf-8')).hexdigest()}"


def durable_control_state(
    db: Session,
    *,
    workflow: DurableAgentWorkflow,
) -> dict[str, object]:
    tasks = db.scalars(
        select(DurableAgentTask)
        .where(DurableAgentTask.workflow_id == workflow.id)
        .order_by(DurableAgentTask.created_at, DurableAgentTask.id)
    ).all()
    unknown_effects = db.scalars(
        select(DurableAgentToolEffect)
        .join(
            DurableAgentAttempt,
            DurableAgentAttempt.id == DurableAgentToolEffect.attempt_id,
        )
        .join(DurableAgentTask, DurableAgentTask.id == DurableAgentAttempt.task_id)
        .where(
            DurableAgentTask.workflow_id == workflow.id,
            DurableAgentToolEffect.status == "unknown",
        )
        .order_by(DurableAgentToolEffect.created_at, DurableAgentToolEffect.id)
    ).all()
    allowed: set[str] = set()
    current_gate = (
        db.get(DurableAgentGate, workflow.current_gate_id)
        if workflow.current_gate_id
        else None
    )
    if current_gate is not None and current_gate.status == "pending":
        allowed.update({"approve_gate", "request_changes"})
    if unknown_effects:
        allowed.add("resolve_unknown_effect")
    retryable = [task for task in tasks if task.status in {"failed", "blocked"}]
    if retryable and not unknown_effects:
        allowed.add("retry_task")
        allowed.add("resume_run")
    if workflow.status not in {"succeeded", "failed", "cancelled"}:
        allowed.add("cancel_run")
    if workflow.status == "failed" and retryable and not unknown_effects:
        allowed.add("resume_run")
    return {
        "workflow_id": workflow.id,
        "status": workflow.status,
        "state_version": workflow.state_version,
        "current_checkpoint_id": workflow.current_checkpoint_id,
        "current_gate_id": workflow.current_gate_id,
        "expected_input_kind": workflow.expected_input_kind,
        "allowed_actions": sorted(allowed),
        "tasks": [
            {
                "id": task.id,
                "task_key": task.task_key,
                "task_type": task.task_type,
                "title": task.title,
                "status": task.status,
                "required": task.required,
                "current_attempt_id": task.current_attempt_id,
                "error_code": task.error_code,
                "error_message": task.error_message,
            }
            for task in tasks
        ],
        "unknown_effects": [
            {
                "id": effect.id,
                "attempt_id": effect.attempt_id,
                "effect_kind": effect.effect_kind,
                "provider_request_id": effect.provider_request_id,
            }
            for effect in unknown_effects
        ],
    }


def execute_durable_control_command(
    db: Session,
    *,
    run: NativeAgentRun,
    workflow: DurableAgentWorkflow,
    user: User,
    payload: DurableControlCommandCreate,
) -> tuple[DurableAgentCommand, dict[str, object]]:
    payload_data = payload.model_dump(mode="json")
    payload_hash = _hash(payload_data)
    existing = db.scalar(
        select(DurableAgentCommand).where(
            DurableAgentCommand.workflow_id == workflow.id,
            DurableAgentCommand.idempotency_key == payload.idempotency_key,
        )
    )
    if existing is not None:
        if existing.payload_hash != payload_hash:
            raise AgentControlCommandError(
                "同一 idempotency_key 已用于不同控制命令"
            )
        replay_result = json.loads(existing.result_json)
        # 幂等重放只返回第一次的业务结果，不能再次触发队列或 Worker 副作用。
        replay_result["enqueue_run"] = False
        replay_result["cancel_worker"] = False
        replay_result["idempotent_replay"] = True
        return existing, replay_result
    if payload.expected_state_version != workflow.state_version:
        raise AgentControlCommandError(
            f"控制命令基于过期状态：期望 {payload.expected_state_version}，"
            f"当前 {workflow.state_version}"
        )
    state_before = durable_control_state(db, workflow=workflow)
    allowed_actions = set(state_before["allowed_actions"])
    if payload.command not in allowed_actions:
        raise AgentControlCommandError(
            f"当前状态不允许 {payload.command}；可用操作："
            f"{', '.join(sorted(allowed_actions)) or '无'}"
        )

    attempt_ids: list[str] = []
    enqueue_run = False
    cancel_worker = False
    try:
        if payload.command in {"approve_gate", "request_changes"}:
            gate_id = payload.target_id or workflow.current_gate_id
            gate = db.get(DurableAgentGate, gate_id) if gate_id else None
            if gate is None or gate.workflow_id != workflow.id:
                raise DurableAgentRuntimeError("当前 Gate 不存在")
            attempts = resolve_gate(
                db,
                gate=gate,
                user=user,
                decision=(
                    "approve"
                    if payload.command == "approve_gate"
                    else "changes_requested"
                ),
                feedback=payload.feedback,
            )
            attempt_ids = [attempt.id for attempt in attempts]
            enqueue_run = bool(attempts)
            if gate.native_approval_id:
                native_approval = db.get(
                    NativeAgentArticleApproval,
                    gate.native_approval_id,
                )
                if native_approval is None:
                    raise DurableAgentRuntimeError("Gate 引用的文案审批不存在")
                native_approval.status = (
                    "approved"
                    if payload.command == "approve_gate"
                    else "changes_requested"
                )
                native_approval.feedback = (
                    payload.feedback.strip() if payload.feedback else None
                )
                native_approval.resolved_at = datetime.utcnow()
                native_approval.decided_by_user_id = user.id
                if payload.command == "approve_gate" and enqueue_run:
                    next_context_sequence = (
                        db.scalar(
                            select(
                                func.coalesce(
                                    func.max(NativeAgentContextItem.sequence),
                                    0,
                                )
                            ).where(NativeAgentContextItem.run_id == run.id)
                        )
                        or 0
                    ) + 1
                    selection_context = {
                        "topic_selection": (
                            "用户已批准当前候选选题。请只基于批准的候选和以下反馈进入正文阶段，"
                            "不得重新生成候选选题或结束 Run："
                        ),
                        "article_draft_review": (
                            "用户已确认当前正文草稿。请只进入 Review 阶段，不得重新选题或改写正文："
                        ),
                    }.get(
                        gate.purpose,
                        "用户已批准当前阶段，请只执行 Durable Workflow 指定的后继阶段：",
                    ) + (native_approval.feedback or "未提供额外反馈")
                    db.add(
                        NativeAgentContextItem(
                            run_id=run.id,
                            sequence=next_context_sequence,
                            item_json=_json(
                                {"role": "user", "content": selection_context}
                            ),
                        )
                    )
                    db.add(
                        NativeAgentItem(
                            run_id=run.id,
                            sequence=(
                                db.scalar(
                                    select(
                                        func.coalesce(
                                            func.max(NativeAgentItem.sequence),
                                            0,
                                        )
                                    ).where(NativeAgentItem.run_id == run.id)
                                )
                                or 0
                            )
                            + 1,
                            item_type=NativeAgentItemType.user_input,
                            payload_json=_json(
                                {
                                    "content": native_approval.feedback
                                    or "批准当前阶段，继续执行",
                                    "control": "durable_gate_approved",
                                }
                            ),
                        )
                    )
            if enqueue_run:
                run.status = AgentRunStatus.retrying
                run.finished_at = None
                run.error_code = None
                run.error_message = None
                run.workflow_phase = gate.on_approve_action
            elif workflow.status == "succeeded":
                run.status = AgentRunStatus.succeeded
                run.finished_at = datetime.utcnow()
                run.workflow_phase = "article_approved"
            else:
                run.status = AgentRunStatus.waiting_for_input
        elif payload.command == "retry_task":
            task = db.get(DurableAgentTask, payload.target_id)
            if task is None:
                raise DurableAgentRuntimeError("待重试 Task 不存在")
            attempt = retry_durable_task(db, workflow=workflow, task=task)
            attempt_ids = [attempt.id]
            enqueue_run = True
            run.status = AgentRunStatus.retrying
            run.finished_at = None
            run.error_code = None
            run.error_message = None
        elif payload.command == "resume_run":
            attempt = resume_durable_workflow(db, workflow=workflow)
            attempt_ids = [attempt.id]
            enqueue_run = True
            run.status = AgentRunStatus.retrying
            run.finished_at = None
            run.error_code = None
            run.error_message = None
        elif payload.command == "cancel_run":
            has_unknown = cancel_durable_workflow(
                db,
                workflow=workflow,
                reason=(payload.feedback or "用户取消 Run").strip(),
            )
            cancel_worker = True
            run.status = (
                AgentRunStatus.cancel_requested
                if has_unknown
                else AgentRunStatus.cancelled
            )
            if not has_unknown:
                run.finished_at = workflow.finished_at
        elif payload.command == "resolve_unknown_effect":
            effect = db.get(DurableAgentToolEffect, payload.target_id)
            if effect is None:
                raise DurableAgentRuntimeError("unknown Tool Effect 不存在")
            assert payload.resolution is not None
            resolve_unknown_tool_effect(
                db,
                workflow=workflow,
                effect=effect,
                resolution=payload.resolution,
                result_ref=payload.result_ref,
            )
            run.status = (
                AgentRunStatus.failed
                if workflow.status == "failed"
                else AgentRunStatus.cancelled
            )
            run.finished_at = workflow.finished_at
    except DurableAgentRuntimeError as exc:
        raise AgentControlCommandError(str(exc)) from exc

    result = {
        "attempt_ids": attempt_ids,
        "enqueue_run": enqueue_run,
        "cancel_worker": cancel_worker,
        "run_status": run.status.value,
        "workflow_status": workflow.status,
        "state_version": workflow.state_version,
        "idempotent_replay": False,
    }
    command = DurableAgentCommand(
        workflow_id=workflow.id,
        requested_by_user_id=user.id,
        command_type=payload.command,
        target_id=payload.target_id,
        idempotency_key=payload.idempotency_key,
        expected_state_version=payload.expected_state_version,
        payload_hash=payload_hash,
        payload_json=_json(payload_data),
        status="applied",
        result_json=_json(result),
    )
    db.add(command)
    db.flush()
    add_native_agent_event(
        db,
        run.id,
        "control.command.applied",
        {
            "command_id": command.id,
            "command": payload.command,
            "target_id": payload.target_id,
            "state_version": workflow.state_version,
        },
    )
    return command, result
