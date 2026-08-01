from __future__ import annotations

from datetime import datetime, timedelta
import hashlib
import json

from sqlalchemy import func, inspect, select, update
from sqlalchemy.orm import Session

from app.models.entities import (
    DurableAgentArtifact,
    DurableAgentAttempt,
    DurableAgentCheckpoint,
    DurableAgentGate,
    DurableAgentImageQuality,
    DurableAgentMediaBinding,
    DurableAgentPlanRevision,
    DurableAgentTask,
    DurableAgentToolEffect,
    DurableAgentWorkflow,
    GeneratedImage,
    GenerationTask,
    NativeAgentArticleApproval,
    NativeAgentImage,
    NativeAgentRun,
    NativeAgentStep,
    TaskPanel,
    User,
)


class DurableAgentRuntimeError(RuntimeError):
    pass


LEASE_SECONDS = 45

ARTICLE_TASKS = (
    ("research_topics", "model", "生成候选选题", (), "topic_candidates"),
    (
        "topic_selection_gate",
        "gate",
        "等待确认选题",
        ("research_topics",),
        None,
    ),
    (
        "write_draft",
        "model",
        "撰写正文",
        ("topic_selection_gate",),
        "article_draft",
    ),
    (
        "draft_review_gate",
        "gate",
        "等待确认正文",
        ("write_draft",),
        None,
    ),
    (
        "review_draft",
        "model",
        "审阅正文",
        ("draft_review_gate",),
        "article_review",
    ),
    (
        "editorial_review_gate",
        "gate",
        "等待确认 Review",
        ("review_draft",),
        None,
    ),
)

ALLOWED_DYNAMIC_TASKS = {
    "supplement_research": {
        "title": "补充研究",
        "task_type": "model",
        "dependencies": ("topic_selection_gate",),
        "output_artifact_key": "research_addendum",
    },
}


def _json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def _hash(value: object) -> str:
    return f"sha256:{hashlib.sha256(_json(value).encode('utf-8')).hexdigest()}"


def _now() -> datetime:
    return datetime.utcnow()


def _visual_plan_artifact(
    db: Session, *, workflow_id: str
) -> DurableAgentArtifact:
    artifact = db.scalar(
        select(DurableAgentArtifact)
        .where(
            DurableAgentArtifact.workflow_id == workflow_id,
            DurableAgentArtifact.artifact_type == "visual_plan",
        )
        .order_by(DurableAgentArtifact.version.desc())
        .limit(1)
    )
    if artifact is None:
        raise DurableAgentRuntimeError("Durable Workflow 缺少视觉方案")
    return artifact


def _visual_plan_panels(artifact: DurableAgentArtifact) -> list[dict[str, object]]:
    content = json.loads(artifact.content_json)
    panels = content.get("panels") if isinstance(content, dict) else None
    if not isinstance(panels, list) or not panels:
        raise DurableAgentRuntimeError("视觉方案必须包含至少一个 Panel")
    normalized: list[dict[str, object]] = []
    seen: set[str] = set()
    for index, raw_panel in enumerate(panels, start=1):
        if not isinstance(raw_panel, dict):
            raise DurableAgentRuntimeError("视觉方案 Panel 必须是对象")
        panel_key = str(raw_panel.get("panel_key") or "").strip()
        prompt = str(raw_panel.get("prompt") or "").strip()
        if not panel_key or not prompt:
            raise DurableAgentRuntimeError("视觉方案 Panel 缺少 panel_key 或 prompt")
        if panel_key in seen:
            raise DurableAgentRuntimeError("视觉方案 panel_key 不能重复")
        seen.add(panel_key)
        normalized.append(
            {
                **raw_panel,
                "panel_key": panel_key,
                "prompt": prompt,
                "ordinal": index,
            }
        )
    return normalized


def workflow_for_native_run(db: Session, native_run_id: str) -> DurableAgentWorkflow | None:
    return db.scalar(
        select(DurableAgentWorkflow).where(
            DurableAgentWorkflow.native_run_id == native_run_id
        )
    )


def runtime_tables_available(db: Session) -> bool:
    return inspect(db.get_bind()).has_table("agent_durable_workflows")


def initialize_workflow(
    db: Session,
    *,
    native_run: NativeAgentRun,
    include_article_tasks: bool = True,
) -> DurableAgentWorkflow:
    existing = workflow_for_native_run(db, native_run.id)
    if existing is not None:
        return existing

    workflow = DurableAgentWorkflow(
        native_run_id=native_run.id,
        status="queued",
        state_version=1,
        allowed_actions_json=_json(["cancel_run"]),
    )
    db.add(workflow)
    db.flush()
    if not include_article_tasks:
        _append_checkpoint(
            db,
            workflow=workflow,
            reason="initial non-article workflow",
            state=_workflow_state(db, workflow),
        )
        append_plan_revision(
            db,
            workflow=workflow,
            reason="initial non-article workflow",
        )
        return workflow
    task_by_key: dict[str, DurableAgentTask] = {}
    for key, task_type, title, dependencies, output_key in ARTICLE_TASKS:
        task = DurableAgentTask(
            workflow_id=workflow.id,
            task_key=key,
            task_type=task_type,
            title=title,
            status="ready" if not dependencies else "pending",
            dependencies_json=_json(list(dependencies)),
            input_artifact_keys_json=_json(
                ["user_goal"] if key == "research_topics" else list(dependencies)
            ),
            output_artifact_key=output_key,
        )
        db.add(task)
        db.flush()
        task_by_key[key] = task
    _prepare_attempt(
        db,
        task=task_by_key["research_topics"],
        attempt_kind="initial",
        checkpoint_id=None,
    )
    _append_checkpoint(
        db,
        workflow=workflow,
        reason="initial article task plan",
        state=_workflow_state(db, workflow),
    )
    append_plan_revision(
        db,
        workflow=workflow,
        reason="initial task plan",
    )
    return workflow


def append_plan_revision(
    db: Session,
    *,
    workflow: DurableAgentWorkflow,
    reason: str,
) -> DurableAgentPlanRevision:
    tasks = db.scalars(
        select(DurableAgentTask)
        .where(DurableAgentTask.workflow_id == workflow.id)
        .order_by(DurableAgentTask.created_at)
    ).all()
    plan = [
        {
            "task_key": task.task_key,
            "title": task.title,
            "status": task.status,
            "dependencies": json.loads(task.dependencies_json),
            "input_artifacts": json.loads(task.input_artifact_keys_json),
            "output_artifact": task.output_artifact_key,
        }
        for task in tasks
    ]
    revision = (
        db.scalar(
            select(func.coalesce(func.max(DurableAgentPlanRevision.revision), 0)).where(
                DurableAgentPlanRevision.workflow_id == workflow.id
            )
        )
        or 0
    ) + 1
    row = DurableAgentPlanRevision(
        workflow_id=workflow.id,
        source_checkpoint_id=workflow.current_checkpoint_id,
        revision=revision,
        reason=reason,
        plan_json=_json(plan),
        plan_hash=_hash(plan),
    )
    db.add(row)
    db.flush()
    return row


def _prepare_attempt(
    db: Session,
    *,
    task: DurableAgentTask,
    attempt_kind: str,
    checkpoint_id: str | None,
) -> DurableAgentAttempt:
    number = (
        db.scalar(
            select(func.coalesce(func.max(DurableAgentAttempt.attempt_number), 0)).where(
                DurableAgentAttempt.task_id == task.id
            )
        )
        or 0
    ) + 1
    if number > task.max_attempts and attempt_kind not in {"resume", "rerun"}:
        raise DurableAgentRuntimeError("Task 已达到最大重试次数")
    attempt = DurableAgentAttempt(
        task_id=task.id,
        attempt_number=number,
        attempt_kind=attempt_kind,
        base_checkpoint_id=checkpoint_id,
        status="prepared",
        input_hash=_hash(
            {
                "task_id": task.id,
                "attempt_number": number,
                "checkpoint_id": checkpoint_id,
            }
        ),
    )
    db.add(attempt)
    db.flush()
    task.current_attempt_id = attempt.id
    task.status = "ready"
    task.error_code = None
    task.error_message = None
    task.finished_at = None
    return attempt


def claim_attempt(
    db: Session, *, attempt_id: str, worker_id: str
) -> DurableAgentAttempt | None:
    now = _now()
    claimed = db.scalar(
        update(DurableAgentAttempt)
        .where(
            DurableAgentAttempt.id == attempt_id,
            DurableAgentAttempt.status == "prepared",
        )
        .values(
            status="running",
            lease_owner=worker_id,
            lease_expires_at=now + timedelta(seconds=LEASE_SECONDS),
            heartbeat_at=now,
            started_at=now,
        )
        .returning(DurableAgentAttempt.id)
    )
    if claimed is None:
        return None
    attempt = db.get(DurableAgentAttempt, claimed)
    assert attempt is not None
    task = db.get(DurableAgentTask, attempt.task_id)
    assert task is not None
    workflow = db.get(DurableAgentWorkflow, task.workflow_id)
    assert workflow is not None
    task.status = "running"
    workflow.status = "running"
    workflow.state_version += 1
    return attempt


def record_artifact(
    db: Session,
    *,
    workflow: DurableAgentWorkflow,
    task_key: str,
    content: dict[str, object],
    artifact_type: str,
) -> DurableAgentArtifact:
    task = db.scalar(
        select(DurableAgentTask).where(
            DurableAgentTask.workflow_id == workflow.id,
            DurableAgentTask.task_key == task_key,
        )
    )
    if task is None:
        raise DurableAgentRuntimeError("Durable Task 不存在")
    version = (
        db.scalar(
            select(func.coalesce(func.max(DurableAgentArtifact.version), 0)).where(
                DurableAgentArtifact.workflow_id == workflow.id,
                DurableAgentArtifact.artifact_key == artifact_type,
            )
        )
        or 0
    ) + 1
    artifact = DurableAgentArtifact(
        workflow_id=workflow.id,
        task_id=task.id,
        artifact_key=artifact_type,
        artifact_type=artifact_type,
        version=version,
        content_json=_json(content),
        content_hash=_hash(content),
    )
    db.add(artifact)
    db.flush()
    task.status = "succeeded"
    task.finished_at = _now()
    attempt = db.get(DurableAgentAttempt, task.current_attempt_id)
    if attempt is not None and attempt.status == "running":
        attempt.status = "succeeded"
        attempt.output_hash = artifact.content_hash
        attempt.finished_at = _now()
        attempt.lease_owner = None
        attempt.lease_expires_at = None
    _append_checkpoint(
        db,
        workflow=workflow,
        reason=f"{task_key} completed",
        state=_workflow_state(db, workflow),
    )
    append_plan_revision(
        db,
        workflow=workflow,
        reason=f"{task_key} completed",
    )
    return artifact


def open_gate(
    db: Session,
    *,
    workflow: DurableAgentWorkflow,
    task_key: str,
    artifact: DurableAgentArtifact,
    purpose: str,
    on_approve_action: str,
    native_approval_id: str | None = None,
) -> DurableAgentGate:
    task = db.scalar(
        select(DurableAgentTask).where(
            DurableAgentTask.workflow_id == workflow.id,
            DurableAgentTask.task_key == task_key,
        )
    )
    if task is None:
        raise DurableAgentRuntimeError("Gate Task 不存在")
    gate = DurableAgentGate(
        native_approval_id=native_approval_id,
        workflow_id=workflow.id,
        task_id=task.id,
        artifact_id=artifact.id,
        purpose=purpose,
        on_approve_action=on_approve_action,
        requested_hash=artifact.content_hash,
    )
    db.add(gate)
    db.flush()
    task.status = "waiting_for_input"
    workflow.status = "waiting_for_input"
    workflow.current_gate_id = gate.id
    workflow.expected_input_kind = "approval"
    workflow.allowed_actions_json = _json(["approve", "request_changes", "cancel_run"])
    workflow.state_version += 1
    _append_checkpoint(
        db,
        workflow=workflow,
        reason=f"{purpose} waiting for user input",
        state=_workflow_state(db, workflow),
    )
    append_plan_revision(
        db,
        workflow=workflow,
        reason=f"{purpose} gate opened",
    )
    return gate


def mirror_native_article_approval(
    db: Session,
    *,
    native_run: NativeAgentRun,
    native_approval: NativeAgentArticleApproval,
) -> DurableAgentGate:
    existing = db.scalar(
        select(DurableAgentGate).where(
            DurableAgentGate.native_approval_id == native_approval.id
        )
    )
    if existing is not None:
        return existing
    workflow = initialize_workflow(db, native_run=native_run)
    native_type = native_approval.artifact.artifact_type
    gate_count = (
        db.scalar(
            select(func.count(DurableAgentGate.id)).where(
                DurableAgentGate.workflow_id == workflow.id
            )
        )
        or 0
    )
    content = native_approval.artifact.content_json.lower()
    looks_like_topic_candidates = any(
        marker in content
        for marker in ("topic_candidates", "候选选题", "account_brief")
    )
    if native_type == "final_article" and gate_count == 0 and not looks_like_topic_candidates:
        gate_key, artifact_key, purpose, action = (
            "editorial_review_gate",
            "review_draft",
            "editorial_review",
            "finish_run",
        )
    elif native_type == "article_review":
        gate_key, artifact_key, purpose, action = (
            "editorial_review_gate",
            "review_draft",
            "editorial_review",
            "finish_run",
        )
    elif native_type == "article_draft" or gate_count == 1:
        gate_key, artifact_key, purpose, action = (
            "draft_review_gate",
            "write_draft",
            "article_draft_review",
            "advance_to_review",
        )
    elif gate_count >= 2:
        gate_key, artifact_key, purpose, action = (
            "editorial_review_gate",
            "review_draft",
            "editorial_review",
            "finish_run",
        )
    else:
        gate_key, artifact_key, purpose, action = (
            (
                "topic_selection_gate",
                "research_topics",
                "topic_selection",
                "advance_to_draft",
            )
            if gate_count == 0
            else (
                "draft_review_gate",
                "write_draft",
                "article_draft_review",
                "advance_to_review",
            )
        )
    source_task = db.scalar(
        select(DurableAgentTask).where(
            DurableAgentTask.workflow_id == workflow.id,
            DurableAgentTask.task_key == artifact_key,
        )
    )
    if source_task is None:
        raise DurableAgentRuntimeError("Durable Artifact Task 不存在")
    artifact = db.scalar(
        select(DurableAgentArtifact).where(
            DurableAgentArtifact.workflow_id == workflow.id,
            DurableAgentArtifact.task_id == source_task.id,
            DurableAgentArtifact.content_hash == native_approval.artifact_hash,
        )
    )
    if artifact is None:
        artifact = DurableAgentArtifact(
            workflow_id=workflow.id,
            task_id=source_task.id,
            artifact_key=artifact_key,
            artifact_type=artifact_key,
            version=1,
            content_json=native_approval.artifact.content_json,
            content_hash=native_approval.artifact_hash,
        )
        db.add(artifact)
        db.flush()
        source_task.status = "succeeded"
        source_task.finished_at = _now()
    return open_gate(
        db,
        workflow=workflow,
        task_key=gate_key,
        artifact=artifact,
        purpose=purpose,
        on_approve_action=action,
        native_approval_id=native_approval.id,
    )


def sync_native_artifact(
    db: Session,
    *,
    native_run: NativeAgentRun,
    artifact_type: str,
    content: dict[str, object],
) -> DurableAgentArtifact | None:
    workflow = workflow_for_native_run(db, native_run.id)
    if workflow is None:
        return None
    task_key = current_task_key(db, native_run_id=native_run.id)
    expected = {
        "research_topics": "topic_candidates",
        "write_draft": "article_draft",
        "review_draft": "article_review",
        "supplement_research": "article_draft",
    }.get(task_key or "")
    if expected != artifact_type:
        return None
    task = db.scalar(
        select(DurableAgentTask).where(
            DurableAgentTask.workflow_id == workflow.id,
            DurableAgentTask.task_key == task_key,
        )
    )
    if task is None:
        return None
    attempt = db.get(DurableAgentAttempt, task.current_attempt_id)
    if attempt is not None and attempt.status == "prepared":
        claim_attempt(
            db,
            attempt_id=attempt.id,
            worker_id="native-agent-adapter",
        )
    artifact = record_artifact(
        db,
        workflow=workflow,
        task_key=task_key,
        artifact_type=(
            "topic_candidates"
            if task_key == "research_topics"
            else artifact_type
        ),
        content=content,
    )
    if task_key == "supplement_research":
        draft_task = db.scalar(
            select(DurableAgentTask).where(
                DurableAgentTask.workflow_id == workflow.id,
                DurableAgentTask.task_key == "write_draft",
            )
        )
        if draft_task is None:
            raise DurableAgentRuntimeError("补充研究后缺少正文 Task")
        _prepare_attempt(
            db,
            task=draft_task,
            attempt_kind="retry",
            checkpoint_id=workflow.current_checkpoint_id,
        )
        workflow.status = "queued"
        workflow.allowed_actions_json = _json(["cancel_run"])
        workflow.state_version += 1
        _append_checkpoint(
            db,
            workflow=workflow,
            reason="supplement research completed; draft revision prepared",
            state=_workflow_state(db, workflow),
        )
        append_plan_revision(
            db,
            workflow=workflow,
            reason="supplement research completed",
        )
    return artifact


def can_complete_native_run(db: Session, *, native_run_id: str) -> bool:
    workflow = workflow_for_native_run(db, native_run_id)
    if workflow is None:
        return True
    if workflow.status == "waiting_for_input":
        return False
    tasks = db.scalars(
        select(DurableAgentTask).where(
            DurableAgentTask.workflow_id == workflow.id,
            DurableAgentTask.required.is_(True),
        )
    ).all()
    return not tasks or all(task.status == "succeeded" for task in tasks)


def finalize_workflow_if_complete(
    db: Session,
    *,
    native_run_id: str,
) -> bool:
    workflow = workflow_for_native_run(db, native_run_id)
    if workflow is None or workflow.status in {"succeeded", "failed", "cancelled"}:
        return workflow is None or workflow.status == "succeeded"
    if not can_complete_native_run(db, native_run_id=native_run_id):
        return False
    workflow.status = "succeeded"
    workflow.allowed_actions_json = _json([])
    workflow.expected_input_kind = None
    workflow.finished_at = _now()
    workflow.state_version += 1
    _append_checkpoint(
        db,
        workflow=workflow,
        reason="native run completed",
        state=_workflow_state(db, workflow),
    )
    return True


def retry_durable_task(
    db: Session,
    *,
    workflow: DurableAgentWorkflow,
    task: DurableAgentTask,
) -> DurableAgentAttempt:
    if task.workflow_id != workflow.id:
        raise DurableAgentRuntimeError("Task 不属于当前 Durable Workflow")
    if task.status not in {"failed", "blocked"}:
        raise DurableAgentRuntimeError("只有明确失败或阻塞的 Task 可以重试")
    unknown_effect = db.scalar(
        select(DurableAgentToolEffect)
        .join(
            DurableAgentAttempt,
            DurableAgentAttempt.id == DurableAgentToolEffect.attempt_id,
        )
        .where(
            DurableAgentAttempt.task_id == task.id,
            DurableAgentToolEffect.status == "unknown",
        )
        .limit(1)
    )
    if unknown_effect is not None:
        raise DurableAgentRuntimeError("Task 存在 unknown Tool Effect，人工处理前不能重试")
    attempt = _prepare_attempt(
        db,
        task=task,
        attempt_kind="retry",
        checkpoint_id=workflow.current_checkpoint_id,
    )
    task.error_code = None
    task.error_message = None
    task.finished_at = None
    workflow.status = "retrying"
    workflow.error_code = None
    workflow.error_message = None
    workflow.finished_at = None
    workflow.allowed_actions_json = _json(["cancel_run"])
    workflow.state_version += 1
    _append_checkpoint(
        db,
        workflow=workflow,
        reason=f"task retry requested: {task.task_key}",
        state=_workflow_state(db, workflow),
    )
    append_plan_revision(
        db,
        workflow=workflow,
        reason=f"task retry requested: {task.task_key}",
    )
    return attempt


def resume_durable_workflow(
    db: Session,
    *,
    workflow: DurableAgentWorkflow,
) -> DurableAgentAttempt:
    if workflow.status not in {"failed", "retrying", "running"}:
        raise DurableAgentRuntimeError("当前 Durable Workflow 不可恢复")
    task = db.scalar(
        select(DurableAgentTask)
        .where(
            DurableAgentTask.workflow_id == workflow.id,
            DurableAgentTask.status.in_(["failed", "blocked"]),
        )
        .order_by(DurableAgentTask.updated_at.desc(), DurableAgentTask.id.desc())
        .limit(1)
    )
    if task is None:
        interrupted = db.scalar(
            select(DurableAgentAttempt)
            .join(DurableAgentTask, DurableAgentTask.id == DurableAgentAttempt.task_id)
            .where(
                DurableAgentTask.workflow_id == workflow.id,
                DurableAgentAttempt.status == "interrupted",
            )
            .order_by(DurableAgentAttempt.updated_at.desc())
            .limit(1)
        )
        if interrupted is None:
            raise DurableAgentRuntimeError("没有可安全恢复的失败或中断 Attempt")
        task = db.get(DurableAgentTask, interrupted.task_id)
        assert task is not None
        task.status = "failed"
    return retry_durable_task(db, workflow=workflow, task=task)


def cancel_durable_workflow(
    db: Session,
    *,
    workflow: DurableAgentWorkflow,
    reason: str,
) -> bool:
    if workflow.status in {"succeeded", "failed", "cancelled"}:
        raise DurableAgentRuntimeError("终态 Durable Workflow 不能取消")
    unknown_effect_created = False
    tasks = db.scalars(
        select(DurableAgentTask).where(DurableAgentTask.workflow_id == workflow.id)
    ).all()
    for task in tasks:
        if task.status in {"succeeded", "failed", "cancelled"}:
            continue
        attempts = db.scalars(
            select(DurableAgentAttempt).where(DurableAgentAttempt.task_id == task.id)
        ).all()
        task_has_unknown = False
        for attempt in attempts:
            effects = db.scalars(
                select(DurableAgentToolEffect).where(
                    DurableAgentToolEffect.attempt_id == attempt.id
                )
            ).all()
            for effect in effects:
                if effect.status == "submitted":
                    effect.status = "unknown"
                    task_has_unknown = True
                    unknown_effect_created = True
            if task_has_unknown and attempt.status == "running":
                attempt.status = "unknown"
                attempt.error_code = "CancelledWithUnknownEffect"
                attempt.error_message = reason
                attempt.finished_at = _now()
                attempt.lease_owner = None
                attempt.lease_expires_at = None
            elif attempt.status in {"prepared", "running", "interrupted"}:
                attempt.status = "cancelled"
                attempt.error_message = reason
                attempt.finished_at = _now()
                attempt.lease_owner = None
                attempt.lease_expires_at = None
        task.status = "blocked" if task_has_unknown else "cancelled"
        task.error_code = "CancelledWithUnknownEffect" if task_has_unknown else None
        task.error_message = reason
        task.finished_at = _now()
    workflow.current_gate_id = None
    workflow.expected_input_kind = (
        "unknown_effect_resolution" if unknown_effect_created else None
    )
    workflow.status = "waiting_for_input" if unknown_effect_created else "cancelled"
    workflow.allowed_actions_json = _json(
        ["resolve_unknown_effect"] if unknown_effect_created else []
    )
    workflow.error_code = (
        "CancelledWithUnknownEffect" if unknown_effect_created else None
    )
    workflow.error_message = reason
    workflow.finished_at = None if unknown_effect_created else _now()
    workflow.state_version += 1
    _append_checkpoint(
        db,
        workflow=workflow,
        reason="run cancellation requested",
        state=_workflow_state(db, workflow),
    )
    append_plan_revision(db, workflow=workflow, reason="run cancellation requested")
    return unknown_effect_created


def resolve_unknown_tool_effect(
    db: Session,
    *,
    workflow: DurableAgentWorkflow,
    effect: DurableAgentToolEffect,
    resolution: str,
    result_ref: dict[str, object] | None,
) -> None:
    attempt = db.get(DurableAgentAttempt, effect.attempt_id)
    if attempt is None:
        raise DurableAgentRuntimeError("unknown Tool Effect 缺少 Attempt")
    task = db.get(DurableAgentTask, attempt.task_id)
    if task is None or task.workflow_id != workflow.id:
        raise DurableAgentRuntimeError("unknown Tool Effect 不属于当前 Workflow")
    if effect.status != "unknown":
        raise DurableAgentRuntimeError("Tool Effect 不是 unknown 状态")
    if resolution not in {"succeeded", "failed"}:
        raise DurableAgentRuntimeError("unknown Tool Effect 只支持 succeeded/failed")
    if resolution == "succeeded" and not result_ref:
        raise DurableAgentRuntimeError("标记成功必须提供可核验 result_ref")
    effect.status = resolution
    effect.result_ref_json = _json(result_ref) if result_ref else None
    if (
        effect.effect_kind == "native_generate_image"
        and effect.idempotency_key.startswith("native-image-step:")
    ):
        native_step_id = effect.idempotency_key.removeprefix(
            "native-image-step:"
        )
        native_step = db.get(NativeAgentStep, native_step_id)
        if native_step is not None:
            native_step.status = resolution
            native_step.finished_at = _now()
            native_step.error_code = (
                None if resolution == "succeeded" else "UnknownEffectResolvedFailed"
            )
            native_step.error_message = None
    attempt.status = resolution
    attempt.finished_at = _now()
    attempt.lease_owner = None
    attempt.lease_expires_at = None
    task.status = resolution
    task.finished_at = _now()
    task.error_code = None if resolution == "succeeded" else "UnknownEffectResolvedFailed"
    task.error_message = None
    remaining = db.scalar(
        select(func.count(DurableAgentToolEffect.id))
        .join(
            DurableAgentAttempt,
            DurableAgentAttempt.id == DurableAgentToolEffect.attempt_id,
        )
        .join(DurableAgentTask, DurableAgentTask.id == DurableAgentAttempt.task_id)
        .where(
            DurableAgentTask.workflow_id == workflow.id,
            DurableAgentToolEffect.status == "unknown",
            DurableAgentToolEffect.id != effect.id,
        )
    ) or 0
    if remaining:
        workflow.status = "waiting_for_input"
        workflow.allowed_actions_json = _json(["resolve_unknown_effect"])
    else:
        workflow.status = "failed" if resolution == "failed" else "cancelled"
        workflow.allowed_actions_json = _json(
            ["retry_task", "resume_run"] if resolution == "failed" else []
        )
        workflow.expected_input_kind = None
        workflow.finished_at = _now()
    workflow.state_version += 1
    _append_checkpoint(
        db,
        workflow=workflow,
        reason=f"unknown effect resolved: {resolution}",
        state=_workflow_state(db, workflow),
    )
    append_plan_revision(
        db,
        workflow=workflow,
        reason=f"unknown effect resolved: {resolution}",
    )


def needs_native_review_gate(db: Session, *, native_run_id: str) -> bool:
    workflow = workflow_for_native_run(db, native_run_id)
    if workflow is None or workflow.current_gate_id is not None:
        return False
    tasks = {
        task.task_key: task
        for task in db.scalars(
            select(DurableAgentTask).where(
                DurableAgentTask.workflow_id == workflow.id
            )
        ).all()
    }
    return (
        tasks["review_draft"].status == "succeeded"
        and tasks["editorial_review_gate"].status == "pending"
    )


def resolve_gate(
    db: Session,
    *,
    gate: DurableAgentGate,
    user: User,
    decision: str,
    feedback: str | None,
) -> list[DurableAgentAttempt]:
    if decision not in {"approve", "changes_requested"}:
        raise DurableAgentRuntimeError("不支持的 Gate 决定")
    if gate.status != "pending":
        if gate.status == ("approved" if decision == "approve" else "changes_requested"):
            return []
        raise DurableAgentRuntimeError("Gate 已由其它决定处理")
    workflow = db.get(DurableAgentWorkflow, gate.workflow_id)
    assert workflow is not None
    artifact = db.get(DurableAgentArtifact, gate.artifact_id)
    assert artifact is not None
    if artifact.content_hash != gate.requested_hash:
        raise DurableAgentRuntimeError("待审 Artifact 已变化")
    gate.status = "approved" if decision == "approve" else "changes_requested"
    gate.feedback = feedback.strip() if feedback else None
    gate.resolved_by_user_id = user.id
    gate.resolved_at = _now()
    workflow.current_gate_id = None
    workflow.expected_input_kind = None
    attempts: list[DurableAgentAttempt] = []
    tasks = {
        task.task_key: task
        for task in db.scalars(
            select(DurableAgentTask).where(
                DurableAgentTask.workflow_id == workflow.id
            )
        ).all()
    }
    gate_task = db.get(DurableAgentTask, gate.task_id)
    assert gate_task is not None
    if decision == "approve":
        gate_task.status = "succeeded"
        if gate_task.task_key == "visual_plan_gate":
            panels = _visual_plan_panels(artifact)
            for panel in panels:
                panel_key = str(panel["panel_key"])
                task = DurableAgentTask(
                    workflow_id=workflow.id,
                    task_key=f"image:{panel_key}",
                    task_type="panel_image",
                    title=f"生成图片 {panel_key}",
                    status="pending",
                    dependencies_json=_json(["visual_plan_gate"]),
                    input_artifact_keys_json=_json(["visual_plan"]),
                    output_artifact_key=f"native_image:{panel_key}",
                )
                db.add(task)
                db.flush()
                attempts.append(
                    _prepare_attempt(
                        db,
                        task=task,
                        attempt_kind="initial",
                        checkpoint_id=workflow.current_checkpoint_id,
                    )
                )
            workflow.status = "queued"
            workflow.allowed_actions_json = _json(["cancel_run"])
            workflow.finished_at = None
            workflow.state_version += 1
            _append_checkpoint(
                db,
                workflow=workflow,
                reason="visual plan approved; panel image tasks prepared",
                state=_workflow_state(db, workflow),
            )
            append_plan_revision(
                db,
                workflow=workflow,
                reason="visual plan approved",
            )
            return attempts
        next_key = {
            "topic_selection_gate": "write_draft",
            "draft_review_gate": "review_draft",
        }.get(gate_task.task_key)
        if next_key:
            attempts.append(
                _prepare_attempt(
                    db,
                    task=tasks[next_key],
                    attempt_kind="initial",
                    checkpoint_id=workflow.current_checkpoint_id,
                )
            )
            workflow.status = "queued"
            workflow.allowed_actions_json = _json(["cancel_run"])
        else:
            workflow.status = "succeeded"
            workflow.allowed_actions_json = _json(["follow_up"])
            workflow.finished_at = _now()
    else:
        if gate_task.task_key == "visual_plan_gate":
            gate_task.status = "pending"
            workflow.status = "waiting_for_input"
            workflow.expected_input_kind = "visual_plan_revision"
            workflow.allowed_actions_json = _json(
                ["submit_visual_plan", "cancel_run"]
            )
            workflow.state_version += 1
            _append_checkpoint(
                db,
                workflow=workflow,
                reason="visual plan changes requested",
                state=_workflow_state(db, workflow),
            )
            append_plan_revision(
                db,
                workflow=workflow,
                reason="visual plan changes requested",
            )
            return []
        if (
            gate_task.task_key == "editorial_review_gate"
            and "补充研究" in (feedback or "")
        ):
            add_supplement_research_task(
                db,
                workflow=workflow,
                reason=feedback or "",
            )
            workflow.status = "queued"
            workflow.allowed_actions_json = _json(["cancel_run"])
            workflow.state_version += 1
            _append_checkpoint(
                db,
                workflow=workflow,
                reason="editorial review requested supplement research",
                state=_workflow_state(db, workflow),
            )
            append_plan_revision(
                db,
                workflow=workflow,
                reason="review requested supplement research",
            )
            return [
                db.scalar(
                    select(DurableAgentAttempt)
                    .join(
                        DurableAgentTask,
                        DurableAgentTask.id == DurableAgentAttempt.task_id,
                    )
                    .where(
                        DurableAgentTask.workflow_id == workflow.id,
                        DurableAgentTask.task_key == "supplement_research",
                    )
                    .order_by(DurableAgentAttempt.attempt_number.desc())
                    .limit(1)
                )
            ]
        retry_key = {
            "topic_selection_gate": "research_topics",
            "draft_review_gate": "write_draft",
            "editorial_review_gate": "write_draft",
        }.get(gate_task.task_key)
        if retry_key is None:
            raise DurableAgentRuntimeError("当前 Gate 不支持修改")
        attempts.append(
            _prepare_attempt(
                db,
                task=tasks[retry_key],
                attempt_kind="retry",
                checkpoint_id=workflow.current_checkpoint_id,
            )
        )
        for task in tasks.values():
            if task.task_key in {"draft_review_gate", "review_draft", "editorial_review_gate"}:
                task.status = "pending"
                task.current_attempt_id = None
                task.finished_at = None
        workflow.status = "retrying"
        workflow.allowed_actions_json = _json(["cancel_run"])
    workflow.state_version += 1
    _append_checkpoint(
        db,
        workflow=workflow,
        reason=f"{gate.purpose} {gate.status}",
        state=_workflow_state(db, workflow),
    )
    append_plan_revision(
        db,
        workflow=workflow,
        reason=f"{gate.purpose} {gate.status}",
    )
    return attempts


def add_supplement_research_task(
    db: Session,
    *,
    workflow: DurableAgentWorkflow,
    reason: str,
) -> DurableAgentAttempt:
    existing = db.scalar(
        select(DurableAgentTask).where(
            DurableAgentTask.workflow_id == workflow.id,
            DurableAgentTask.task_key == "supplement_research",
        )
    )
    if existing is not None:
        raise DurableAgentRuntimeError("补充研究 Task 已存在，不能重复追加")
    definition = ALLOWED_DYNAMIC_TASKS["supplement_research"]
    task = DurableAgentTask(
        workflow_id=workflow.id,
        task_key="supplement_research",
        task_type=str(definition["task_type"]),
        title=str(definition["title"]),
        status="pending",
        dependencies_json=_json(list(definition["dependencies"])),
        input_artifact_keys_json=_json(["topic_candidates"]),
        output_artifact_key=str(definition["output_artifact_key"]),
    )
    db.add(task)
    db.flush()
    prerequisites = {
        item.task_key: item.status
        for item in db.scalars(
            select(DurableAgentTask).where(
                DurableAgentTask.workflow_id == workflow.id
            )
        ).all()
    }
    if any(
        prerequisites.get(key) != "succeeded"
        for key in definition["dependencies"]
    ):
        raise DurableAgentRuntimeError("补充研究缺少已批准的上游选题")
    attempt = _prepare_attempt(
        db,
        task=task,
        attempt_kind="initial",
        checkpoint_id=workflow.current_checkpoint_id,
    )
    workflow.status = "queued"
    workflow.allowed_actions_json = _json(["cancel_run"])
    workflow.state_version += 1
    _append_checkpoint(
        db,
        workflow=workflow,
        reason=f"supplement research requested: {reason}",
        state=_workflow_state(db, workflow),
    )
    append_plan_revision(
        db,
        workflow=workflow,
        reason="review requested supplement research",
    )
    return attempt


def register_visual_plan(
    db: Session,
    *,
    workflow: DurableAgentWorkflow,
    content: dict[str, object],
) -> tuple[DurableAgentArtifact, DurableAgentGate]:
    editorial_gate_task = db.scalar(
        select(DurableAgentTask).where(
            DurableAgentTask.workflow_id == workflow.id,
            DurableAgentTask.task_key == "editorial_review_gate",
        )
    )
    if editorial_gate_task is None or editorial_gate_task.status != "succeeded":
        raise DurableAgentRuntimeError("正文 Review 尚未批准，不能创建视觉方案")
    panels = content.get("panels") if isinstance(content, dict) else None
    if not isinstance(panels, list):
        raise DurableAgentRuntimeError("视觉方案必须包含 panels")
    existing = db.scalar(
        select(DurableAgentTask).where(
            DurableAgentTask.workflow_id == workflow.id,
            DurableAgentTask.task_key == "visual_plan_gate",
        )
    )
    if existing is not None:
        pending_gate = db.scalar(
            select(DurableAgentGate).where(
                DurableAgentGate.workflow_id == workflow.id,
                DurableAgentGate.task_id == existing.id,
                DurableAgentGate.status == "pending",
            )
        )
        if pending_gate is not None:
            raise DurableAgentRuntimeError("视觉方案正在等待确认")
        if db.scalar(
            select(func.count(DurableAgentMediaBinding.id)).where(
                DurableAgentMediaBinding.workflow_id == workflow.id
            )
        ):
            raise DurableAgentRuntimeError("已经生成图片，不能覆盖视觉方案")
        plan_task = db.scalar(
            select(DurableAgentTask).where(
                DurableAgentTask.workflow_id == workflow.id,
                DurableAgentTask.task_key == "visual_plan",
            )
        )
        assert plan_task is not None
        gate_task = existing
    else:
        plan_task = DurableAgentTask(
            workflow_id=workflow.id,
            task_key="visual_plan",
            task_type="model",
            title="制定图片方案",
            status="succeeded",
            dependencies_json=_json(["editorial_review_gate"]),
            input_artifact_keys_json=_json(["article_review"]),
            output_artifact_key="visual_plan",
        )
        db.add(plan_task)
        db.flush()
        gate_task = DurableAgentTask(
            workflow_id=workflow.id,
            task_key="visual_plan_gate",
            task_type="gate",
            title="等待确认图片方案",
            status="pending",
            dependencies_json=_json(["visual_plan"]),
            input_artifact_keys_json=_json(["visual_plan"]),
            output_artifact_key=None,
        )
        db.add(gate_task)
        db.flush()
    version = (
        db.scalar(
            select(func.coalesce(func.max(DurableAgentArtifact.version), 0)).where(
                DurableAgentArtifact.workflow_id == workflow.id,
                DurableAgentArtifact.artifact_type == "visual_plan",
            )
        )
        or 0
    ) + 1
    artifact = DurableAgentArtifact(
        workflow_id=workflow.id,
        task_id=plan_task.id,
        artifact_key="visual_plan",
        artifact_type="visual_plan",
        version=version,
        content_json=_json(content),
        content_hash=_hash(content),
    )
    db.add(artifact)
    db.flush()
    _visual_plan_panels(artifact)
    gate = open_gate(
        db,
        workflow=workflow,
        task_key="visual_plan_gate",
        artifact=artifact,
        purpose="visual_plan_review",
        on_approve_action="create_panel_image_tasks",
    )
    append_plan_revision(
        db,
        workflow=workflow,
        reason="visual plan registered",
    )
    return artifact, gate


def bind_panel_image(
    db: Session,
    *,
    workflow: DurableAgentWorkflow,
    generated_image: GeneratedImage,
    plan_panel_key: str | None = None,
) -> DurableAgentMediaBinding:
    if generated_image.panel_id is None:
        raise DurableAgentRuntimeError("只能绑定 Panel 图片")
    panel = db.get(TaskPanel, generated_image.panel_id)
    task = db.get(GenerationTask, generated_image.task_id)
    if panel is None or task is None:
        raise DurableAgentRuntimeError("图片关联的 Panel 或任务不存在")
    existing = db.scalar(
        select(DurableAgentMediaBinding).where(
            DurableAgentMediaBinding.workflow_id == workflow.id,
            DurableAgentMediaBinding.generated_image_id == generated_image.id,
        )
    )
    if existing is not None:
        return existing
    visual_plan = _visual_plan_artifact(db, workflow_id=workflow.id)
    resolved_panel_key = plan_panel_key or str(panel.panel_order)
    image_task = db.scalar(
        select(DurableAgentTask).where(
            DurableAgentTask.workflow_id == workflow.id,
            DurableAgentTask.task_key == f"image:{resolved_panel_key}",
        )
    )
    if image_task is None:
        raise DurableAgentRuntimeError("图片没有对应的视觉方案 Panel Task")
    image_attempt = db.get(DurableAgentAttempt, image_task.current_attempt_id)
    if image_attempt is not None and image_attempt.status == "prepared":
        claim_attempt(
            db,
            attempt_id=image_attempt.id,
            worker_id="generation-image-adapter",
        )
    image_task.status = (
        "succeeded" if generated_image.status.value == "succeeded" else "failed"
    )
    image_task.finished_at = _now()
    if image_attempt is not None:
        image_attempt.status = image_task.status
        image_attempt.finished_at = _now()
        image_attempt.lease_owner = None
        image_attempt.lease_expires_at = None
    quality_task = DurableAgentTask(
        workflow_id=workflow.id,
        task_key=f"inspect:{generated_image.id}",
        task_type="image_quality",
        title=f"检查第 {panel.panel_order} 张图片",
        status="pending",
        dependencies_json=_json([image_task.task_key]),
        input_artifact_keys_json=_json([f"image:{generated_image.id}"]),
        output_artifact_key=f"quality:{generated_image.id}",
    )
    db.add(quality_task)
    db.flush()
    binding = DurableAgentMediaBinding(
        workflow_id=workflow.id,
        visual_plan_artifact_id=visual_plan.id,
        plan_panel_key=resolved_panel_key,
        generation_task_id=task.id,
        panel_id=panel.id,
        generated_image_id=generated_image.id,
        image_task_id=image_task.id,
        quality_task_id=quality_task.id,
        status="generated"
        if generated_image.status.value == "succeeded"
        else "failed",
    )
    db.add(binding)
    db.flush()
    if generated_image.status.value == "succeeded":
        _prepare_attempt(
            db,
            task=quality_task,
            attempt_kind="initial",
            checkpoint_id=workflow.current_checkpoint_id,
        )
    append_plan_revision(
        db,
        workflow=workflow,
        reason=f"panel image bound: {panel.panel_order}",
    )
    return binding


def bind_native_agent_image(
    db: Session,
    *,
    workflow: DurableAgentWorkflow,
    native_image: NativeAgentImage,
    native_step: NativeAgentStep,
) -> DurableAgentMediaBinding:
    existing = db.scalar(
        select(DurableAgentMediaBinding).where(
            DurableAgentMediaBinding.workflow_id == workflow.id,
            DurableAgentMediaBinding.native_agent_image_id == native_image.id,
        )
    )
    if existing is not None:
        return existing
    visual_plan = _visual_plan_artifact(db, workflow_id=workflow.id)
    image_task = db.scalar(
        select(DurableAgentTask)
        .where(
            DurableAgentTask.workflow_id == workflow.id,
            DurableAgentTask.task_type == "panel_image",
            DurableAgentTask.status.in_(["ready", "running", "retrying"]),
        )
        .order_by(DurableAgentTask.created_at)
        .limit(1)
    )
    if image_task is None:
        raise DurableAgentRuntimeError("Native 图片没有待执行的视觉方案 Panel Task")
    plan_panel_key = image_task.task_key.removeprefix("image:")
    image_attempt = db.get(DurableAgentAttempt, image_task.current_attempt_id)
    if image_attempt is None:
        raise DurableAgentRuntimeError("Native 图片 Task 缺少 Attempt")
    if image_attempt.status == "prepared":
        claimed = claim_attempt(
            db,
            attempt_id=image_attempt.id,
            worker_id="native-image-adapter",
        )
        if claimed is None:
            raise DurableAgentRuntimeError("Native 图片 Attempt 无法领取")
    image_task.status = "succeeded"
    image_task.finished_at = _now()
    image_attempt.status = "succeeded"
    image_attempt.finished_at = _now()
    image_attempt.lease_owner = None
    image_attempt.lease_expires_at = None
    binding = db.scalar(
        select(DurableAgentMediaBinding).where(
            DurableAgentMediaBinding.workflow_id == workflow.id,
            DurableAgentMediaBinding.image_task_id == image_task.id,
            DurableAgentMediaBinding.status == "rerun_requested",
        )
    )
    if binding is not None:
        binding.native_agent_image_id = native_image.id
        binding.status = "generated"
        quality_task = db.get(DurableAgentTask, binding.quality_task_id)
        if quality_task is None:
            raise DurableAgentRuntimeError("局部重跑缺少质量 Task")
        quality_task.status = "pending"
        quality_task.input_artifact_keys_json = _json(
            [f"native_image:{native_image.id}"]
        )
        quality_task.output_artifact_key = f"quality:native:{native_image.id}"
    else:
        quality_task = DurableAgentTask(
            workflow_id=workflow.id,
            task_key=f"inspect_native:{native_image.id}",
            task_type="image_quality",
            title="检查 Agent 图片",
            status="pending",
            dependencies_json=_json([image_task.task_key]),
            input_artifact_keys_json=_json([f"native_image:{native_image.id}"]),
            output_artifact_key=f"quality:native:{native_image.id}",
        )
        db.add(quality_task)
        db.flush()
        binding = DurableAgentMediaBinding(
            workflow_id=workflow.id,
            visual_plan_artifact_id=visual_plan.id,
            plan_panel_key=plan_panel_key,
            generation_task_id=None,
            panel_id=None,
            generated_image_id=None,
            native_agent_image_id=native_image.id,
            image_task_id=image_task.id,
            quality_task_id=quality_task.id,
            status="generated",
        )
        db.add(binding)
        db.flush()
    _prepare_attempt(
        db,
        task=quality_task,
        attempt_kind="initial",
        checkpoint_id=workflow.current_checkpoint_id,
    )
    effect_key = f"native-image-step:{native_step.id}"
    existing_effect = db.scalar(
        select(DurableAgentToolEffect).where(
            DurableAgentToolEffect.idempotency_key == effect_key
        )
    )
    if existing_effect is None:
        db.add(
            DurableAgentToolEffect(
                attempt_id=image_attempt.id,
                effect_kind="native_generate_image",
                idempotency_key=effect_key,
                status="succeeded",
                provider_request_id=native_image.provider_request_id,
                result_ref_json=_json(
                    {
                        "native_agent_image_id": native_image.id,
                        "native_step_id": native_step.id,
                        "asset_id": native_image.asset_id,
                    }
                ),
            )
        )
    else:
        existing_effect.status = "succeeded"
        existing_effect.provider_request_id = native_image.provider_request_id
        existing_effect.result_ref_json = _json(
            {
                "native_agent_image_id": native_image.id,
                "native_step_id": native_step.id,
                "asset_id": native_image.asset_id,
            }
        )
    append_plan_revision(
        db,
        workflow=workflow,
        reason=f"native agent image bound: {native_image.id}",
    )
    return binding


def media_runtime_enabled(db: Session, *, native_run_id: str) -> bool:
    workflow = workflow_for_native_run(db, native_run_id)
    if workflow is None:
        return False
    visual_gate = db.scalar(
        select(DurableAgentGate).where(
            DurableAgentGate.workflow_id == workflow.id,
            DurableAgentGate.purpose == "visual_plan_review",
            DurableAgentGate.status == "approved",
        )
    )
    return visual_gate is not None


def prepare_native_image_effect(
    db: Session,
    *,
    native_run_id: str,
    native_step: NativeAgentStep,
) -> DurableAgentToolEffect | None:
    if not media_runtime_enabled(db, native_run_id=native_run_id):
        return None
    workflow = workflow_for_native_run(db, native_run_id)
    assert workflow is not None
    image_task = db.scalar(
        select(DurableAgentTask)
        .where(
            DurableAgentTask.workflow_id == workflow.id,
            DurableAgentTask.task_type == "panel_image",
            DurableAgentTask.status.in_(["ready", "running", "retrying"]),
        )
        .order_by(DurableAgentTask.created_at)
        .limit(1)
    )
    if image_task is None:
        image_task = db.scalar(
            select(DurableAgentTask)
            .where(
                DurableAgentTask.workflow_id == workflow.id,
                DurableAgentTask.task_type == "panel_image",
                DurableAgentTask.status == "failed",
            )
            .order_by(DurableAgentTask.created_at)
            .limit(1)
        )
        if image_task is not None:
            _prepare_attempt(
                db,
                task=image_task,
                attempt_kind="retry",
                checkpoint_id=workflow.current_checkpoint_id,
            )
    if image_task is None or image_task.current_attempt_id is None:
        raise DurableAgentRuntimeError("图片 Tool 没有对应的 Durable Attempt")
    idempotency_key = f"native-image-step:{native_step.id}"
    existing = db.scalar(
        select(DurableAgentToolEffect).where(
            DurableAgentToolEffect.idempotency_key == idempotency_key
        )
    )
    if existing is not None:
        return existing
    effect = DurableAgentToolEffect(
        attempt_id=image_task.current_attempt_id,
        effect_kind="native_generate_image",
        idempotency_key=idempotency_key,
        status="prepared",
    )
    db.add(effect)
    db.flush()
    return effect


def update_native_image_effect(
    db: Session,
    *,
    native_step_id: str,
    status: str,
    provider_request_id: str | None = None,
    result: dict[str, object] | None = None,
) -> DurableAgentToolEffect | None:
    if status not in {"submitted", "succeeded", "failed", "unknown"}:
        raise DurableAgentRuntimeError("不支持的图片 Tool Effect 状态")
    effect = db.scalar(
        select(DurableAgentToolEffect).where(
            DurableAgentToolEffect.idempotency_key
            == f"native-image-step:{native_step_id}"
        )
    )
    if effect is None:
        return None
    if effect.status == "succeeded" and status != "succeeded":
        raise DurableAgentRuntimeError("成功的图片 Tool Effect 不能回退")
    effect.status = status
    if provider_request_id is not None:
        effect.provider_request_id = provider_request_id
    if result is not None:
        effect.result_ref_json = _json(result)
    if status in {"failed", "unknown"}:
        attempt = db.get(DurableAgentAttempt, effect.attempt_id)
        if attempt is not None:
            attempt.status = status
            attempt.finished_at = _now()
            attempt.lease_owner = None
            attempt.lease_expires_at = None
            task = db.get(DurableAgentTask, attempt.task_id)
            if task is not None:
                task.status = status
                task.finished_at = _now()
                if result is not None:
                    task.error_message = str(result.get("error_message") or "")[:500]
    return effect


def pending_media_context(
    db: Session, *, native_run_id: str
) -> list[dict[str, object]]:
    workflow = workflow_for_native_run(db, native_run_id)
    if workflow is None:
        return []
    artifact = _visual_plan_artifact(db, workflow_id=workflow.id)
    panels = {
        str(panel["panel_key"]): panel for panel in _visual_plan_panels(artifact)
    }
    tasks = db.scalars(
        select(DurableAgentTask)
        .where(
            DurableAgentTask.workflow_id == workflow.id,
            DurableAgentTask.task_type == "panel_image",
            DurableAgentTask.status.in_(["ready", "running", "retrying"]),
        )
        .order_by(DurableAgentTask.created_at)
    ).all()
    return [
        {
            **panels[task.task_key.removeprefix("image:")],
            "task_key": task.task_key,
            "attempt_id": task.current_attempt_id,
        }
        for task in tasks
        if task.task_key.removeprefix("image:") in panels
    ]


def media_ready_for_quality(db: Session, *, native_run_id: str) -> bool:
    workflow = workflow_for_native_run(db, native_run_id)
    if workflow is None:
        return False
    if (
        workflow.status == "waiting_for_input"
        and workflow.expected_input_kind == "image_quality"
    ):
        return True
    image_tasks = db.scalars(
        select(DurableAgentTask).where(
            DurableAgentTask.workflow_id == workflow.id,
            DurableAgentTask.task_type == "panel_image",
        )
    ).all()
    if not image_tasks or any(task.status != "succeeded" for task in image_tasks):
        return False
    binding_count = (
        db.scalar(
            select(func.count(DurableAgentMediaBinding.id)).where(
                DurableAgentMediaBinding.workflow_id == workflow.id
            )
        )
        or 0
    )
    if binding_count != len(image_tasks):
        return False
    workflow.status = "waiting_for_input"
    workflow.expected_input_kind = "image_quality"
    workflow.allowed_actions_json = _json(["record_quality", "cancel_run"])
    workflow.state_version += 1
    _append_checkpoint(
        db,
        workflow=workflow,
        reason="all panel images generated; waiting for quality decisions",
        state=_workflow_state(db, workflow),
    )
    append_plan_revision(
        db,
        workflow=workflow,
        reason="all panel images generated",
    )
    return True


def record_image_quality(
    db: Session,
    *,
    binding: DurableAgentMediaBinding,
    verdict: str,
    summary: str,
    details: dict[str, object],
) -> DurableAgentImageQuality:
    if verdict not in {"accepted", "changes_required", "blocked", "unknown"}:
        raise DurableAgentRuntimeError("不支持的图片质量结论")
    revision = (
        db.scalar(
            select(func.coalesce(func.max(DurableAgentImageQuality.revision), 0)).where(
                DurableAgentImageQuality.media_binding_id == binding.id
            )
        )
        or 0
    ) + 1
    quality = DurableAgentImageQuality(
        media_binding_id=binding.id,
        revision=revision,
        verdict=verdict,
        summary=summary,
        details_json=_json(details),
    )
    db.add(quality)
    quality_task = db.get(DurableAgentTask, binding.quality_task_id)
    if quality_task is not None:
        attempt = db.get(DurableAgentAttempt, quality_task.current_attempt_id)
        if attempt is not None and attempt.status == "prepared":
            claim_attempt(
                db,
                attempt_id=attempt.id,
                worker_id="image-quality-adapter",
            )
        quality_task.status = (
            "succeeded"
            if verdict == "accepted"
            else "unknown" if verdict == "unknown" else "failed"
        )
        quality_task.finished_at = _now()
        artifact_content = {
            "media_binding_id": binding.id,
            "revision": revision,
            "verdict": verdict,
            "summary": summary,
            "details": details,
        }
        artifact = DurableAgentArtifact(
            workflow_id=binding.workflow_id,
            task_id=quality_task.id,
            artifact_key=f"quality:{binding.id}",
            artifact_type="image_quality",
            version=revision,
            content_json=_json(artifact_content),
            content_hash=_hash(artifact_content),
        )
        db.add(artifact)
        db.flush()
        if attempt is not None:
            attempt.status = quality_task.status
            attempt.output_hash = artifact.content_hash
            attempt.finished_at = _now()
            attempt.lease_owner = None
            attempt.lease_expires_at = None
    binding.status = verdict
    workflow = db.get(DurableAgentWorkflow, binding.workflow_id)
    assert workflow is not None
    append_plan_revision(
        db,
        workflow=workflow,
        reason=f"image quality {verdict} for panel {binding.panel_id}",
    )
    return quality


def inspect_pending_native_media(
    *,
    native_run_id: str,
    session_factory,
) -> int:
    from app.services.agent_vision import AgentVisionError, inspect_image_asset

    inspected = 0
    with session_factory() as db:
        workflow = workflow_for_native_run(db, native_run_id)
        if workflow is None:
            return 0
        visual_plan = db.scalar(
            select(DurableAgentArtifact)
            .where(
                DurableAgentArtifact.workflow_id == workflow.id,
                DurableAgentArtifact.artifact_type == "visual_plan",
            )
            .order_by(DurableAgentArtifact.version.desc())
            .limit(1)
        )
        if visual_plan is None:
            return 0
        panels = {
            str(panel["panel_key"]): panel
            for panel in _visual_plan_panels(visual_plan)
        }
        bindings = db.scalars(
            select(DurableAgentMediaBinding).where(
                DurableAgentMediaBinding.workflow_id == workflow.id,
                DurableAgentMediaBinding.native_agent_image_id.is_not(None),
                DurableAgentMediaBinding.status == "generated",
            )
        ).all()
        for binding in bindings:
            native_image = db.get(NativeAgentImage, binding.native_agent_image_id)
            if native_image is None or native_image.asset is None:
                raise DurableAgentRuntimeError("Native 图片绑定引用的资产不存在")
            panel = panels.get(binding.plan_panel_key or "")
            if panel is None:
                raise DurableAgentRuntimeError("Native 图片绑定找不到视觉方案 Panel")
            requested_checks = panel.get("quality_criteria")
            checks = (
                [str(value) for value in requested_checks if str(value).strip()]
                if isinstance(requested_checks, list) and requested_checks
                else [
                    "story_alignment",
                    "character_consistency",
                    "continuity",
                    "text_accuracy",
                    "visual_artifacts",
                ]
            )
            expected = {
                "panel_key": binding.plan_panel_key,
                "prompt": panel["prompt"],
                "title": panel.get("title"),
            }
            try:
                result, provider, model, latency_ms = inspect_image_asset(
                    native_image.asset,
                    checks=checks,
                    expected=expected,
                )
                verdict = {
                    "accept": "accepted",
                    "revise": "changes_required",
                    "ask_user": "blocked",
                    "blocked": "blocked",
                }[result.verdict]
                issue_messages = [issue.message for issue in result.issues]
                summary = (
                    "；".join(issue_messages)
                    if issue_messages
                    else "图片质量检查通过"
                )
                details = {
                    "scores": result.scores,
                    "issues": [
                        issue.model_dump(mode="json") for issue in result.issues
                    ],
                    "provider": provider,
                    "model": model,
                    "latency_ms": latency_ms,
                }
            except AgentVisionError as exc:
                verdict = "blocked"
                summary = f"图片质量检查失败：{exc}"
                details = {
                    "error_code": type(exc).__name__,
                    "error_message": str(exc),
                }
            record_image_quality(
                db,
                binding=binding,
                verdict=verdict,
                summary=summary,
                details=details,
            )
            inspected += 1
        db.commit()
    return inspected


def request_panel_rerun(
    db: Session,
    *,
    binding: DurableAgentMediaBinding,
    user_feedback: str,
) -> DurableAgentAttempt:
    workflow = db.get(DurableAgentWorkflow, binding.workflow_id)
    assert workflow is not None
    if binding.status == "unknown":
        raise DurableAgentRuntimeError("图片 Provider 结果未知，必须人工对账后才能重跑")
    image_task = db.get(DurableAgentTask, binding.image_task_id)
    quality_task = db.get(DurableAgentTask, binding.quality_task_id)
    if image_task is None or quality_task is None:
        raise DurableAgentRuntimeError("图片 Durable Task 不完整")
    image_task.status = "retrying"
    quality_task.status = "pending"
    quality_task.current_attempt_id = None
    quality_task.finished_at = None
    attempt = _prepare_attempt(
        db,
        task=image_task,
        attempt_kind="rerun",
        checkpoint_id=workflow.current_checkpoint_id,
    )
    image_task.error_message = user_feedback
    binding.status = "rerun_requested"
    workflow.status = "queued"
    workflow.allowed_actions_json = _json(["cancel_run"])
    workflow.state_version += 1
    _append_checkpoint(
        db,
        workflow=workflow,
        reason=f"panel rerun requested: {binding.panel_id}",
        state=_workflow_state(db, workflow),
    )
    append_plan_revision(
        db,
        workflow=workflow,
        reason=f"panel rerun requested: {binding.panel_id}",
    )
    return attempt


def open_image_quality_gate(
    db: Session,
    *,
    workflow: DurableAgentWorkflow,
) -> DurableAgentGate:
    existing = db.scalar(
        select(DurableAgentGate).where(
            DurableAgentGate.workflow_id == workflow.id,
            DurableAgentGate.purpose == "image_quality_review",
            DurableAgentGate.status == "pending",
        )
    )
    if existing is not None:
        return existing
    bindings = db.scalars(
        select(DurableAgentMediaBinding).where(
            DurableAgentMediaBinding.workflow_id == workflow.id
        )
    ).all()
    if not bindings:
        raise DurableAgentRuntimeError("没有可汇总的图片质量结论")
    if any(
        binding.status
        not in {"accepted", "changes_required", "blocked", "unknown"}
        for binding in bindings
    ):
        raise DurableAgentRuntimeError("仍有图片质量检查未完成")
    if any(binding.status != "accepted" for binding in bindings):
        raise DurableAgentRuntimeError("仍有图片需要修改或人工对账，不能确认质量完成")
    task = DurableAgentTask(
        workflow_id=workflow.id,
        task_key="image_quality_gate",
        task_type="gate",
        title="等待确认图片质量",
        status="pending",
        dependencies_json=_json(
            [
                db.get(DurableAgentTask, binding.quality_task_id).task_key
                for binding in bindings
                if binding.quality_task_id
            ]
        ),
        input_artifact_keys_json=_json(
            [
                f"quality:{binding.generated_image_id or binding.native_agent_image_id}"
                for binding in bindings
            ]
        ),
        output_artifact_key=None,
    )
    db.add(task)
    db.flush()
    summary = {
        "bindings": [
            {
                "panel_id": binding.panel_id,
                "generated_image_id": binding.generated_image_id,
                "native_agent_image_id": binding.native_agent_image_id,
                "verdict": binding.status,
            }
            for binding in bindings
        ]
    }
    artifact = DurableAgentArtifact(
        workflow_id=workflow.id,
        task_id=task.id,
        artifact_key="image_quality_summary",
        artifact_type="image_quality_summary",
        version=1,
        content_json=_json(summary),
        content_hash=_hash(summary),
    )
    db.add(artifact)
    db.flush()
    return open_gate(
        db,
        workflow=workflow,
        task_key="image_quality_gate",
        artifact=artifact,
        purpose="image_quality_review",
        on_approve_action="finish_media_quality",
    )




def _workflow_state(db: Session, workflow: DurableAgentWorkflow) -> dict[str, object]:
    tasks = db.scalars(
        select(DurableAgentTask)
        .where(DurableAgentTask.workflow_id == workflow.id)
        .order_by(DurableAgentTask.created_at)
    ).all()
    return {
        "workflow_id": workflow.id,
        "native_run_id": workflow.native_run_id,
        "status": workflow.status,
        "tasks": [
            {
                "task_key": task.task_key,
                "status": task.status,
                "current_attempt_id": task.current_attempt_id,
            }
            for task in tasks
        ],
        "gate_id": workflow.current_gate_id,
    }


def _append_checkpoint(
    db: Session,
    *,
    workflow: DurableAgentWorkflow,
    reason: str,
    state: dict[str, object],
) -> DurableAgentCheckpoint:
    latest = db.scalar(
        select(DurableAgentCheckpoint)
        .where(DurableAgentCheckpoint.workflow_id == workflow.id)
        .order_by(DurableAgentCheckpoint.revision.desc())
        .limit(1)
    )
    checkpoint = DurableAgentCheckpoint(
        workflow_id=workflow.id,
        revision=(latest.revision if latest else 0) + 1,
        parent_checkpoint_id=latest.id if latest else None,
        reason=reason,
        state_json=_json(state),
        state_hash=_hash(state),
    )
    db.add(checkpoint)
    db.flush()
    workflow.current_checkpoint_id = checkpoint.id
    return checkpoint


def current_task_key(db: Session, *, native_run_id: str) -> str | None:
    workflow = workflow_for_native_run(db, native_run_id)
    if workflow is None:
        return None
    task = db.scalar(
        select(DurableAgentTask)
        .where(
            DurableAgentTask.workflow_id == workflow.id,
            DurableAgentTask.status.in_(["ready", "running", "retrying"]),
        )
        .order_by(DurableAgentTask.created_at)
        .limit(1)
    )
    return task.task_key if task is not None else None


def recover_attempts(db: Session) -> list[str]:
    now = _now()
    recovered: list[str] = []
    attempts = db.scalars(
        select(DurableAgentAttempt).where(
            DurableAgentAttempt.status.in_(["prepared", "running"])
        )
    ).all()
    for attempt in attempts:
        task = db.get(DurableAgentTask, attempt.task_id)
        assert task is not None
        workflow = db.get(DurableAgentWorkflow, task.workflow_id)
        assert workflow is not None
        if workflow.status == "waiting_for_input":
            continue
        if attempt.status == "running":
            if attempt.lease_expires_at and attempt.lease_expires_at >= now:
                continue
            attempt.status = "interrupted"
            attempt.error_code = "LeaseExpired"
            attempt.error_message = "Worker lease expired before recovery"
            attempt.finished_at = now
            replacement = _prepare_attempt(
                db,
                task=task,
                attempt_kind="resume",
                checkpoint_id=workflow.current_checkpoint_id,
            )
            append_plan_revision(
                db,
                workflow=workflow,
                reason=f"{task.task_key} resumed after lease expiry",
            )
            recovered.append(replacement.id)
            continue
        recovered.append(attempt.id)
    return recovered


def claim_current_attempt_for_native_run(
    db: Session,
    *,
    native_run_id: str,
    worker_id: str,
) -> DurableAgentAttempt | None:
    workflow = workflow_for_native_run(db, native_run_id)
    if workflow is None or workflow.status == "waiting_for_input":
        return None
    task = db.scalar(
        select(DurableAgentTask)
        .where(
            DurableAgentTask.workflow_id == workflow.id,
            DurableAgentTask.status.in_(["ready", "retrying"]),
        )
        .order_by(DurableAgentTask.created_at)
        .limit(1)
    )
    if task is None or task.current_attempt_id is None:
        return None
    attempt = claim_attempt(
        db,
        attempt_id=task.current_attempt_id,
        worker_id=worker_id,
    )
    db.commit()
    return attempt


def native_run_id_for_attempt(db: Session, *, attempt_id: str) -> str | None:
    attempt = db.get(DurableAgentAttempt, attempt_id)
    if attempt is None:
        return None
    task = db.get(DurableAgentTask, attempt.task_id)
    if task is None:
        return None
    workflow = db.get(DurableAgentWorkflow, task.workflow_id)
    return workflow.native_run_id if workflow is not None else None


def prepared_attempt_id_for_native_run(
    db: Session,
    *,
    native_run_id: str,
) -> str | None:
    workflow = workflow_for_native_run(db, native_run_id)
    if workflow is None or workflow.status == "waiting_for_input":
        return None
    return db.scalar(
        select(DurableAgentAttempt.id)
        .join(DurableAgentTask, DurableAgentTask.id == DurableAgentAttempt.task_id)
        .where(
            DurableAgentTask.workflow_id == workflow.id,
            DurableAgentTask.status.in_(["ready", "retrying"]),
            DurableAgentAttempt.status == "prepared",
        )
        .order_by(DurableAgentTask.created_at, DurableAgentAttempt.attempt_number)
        .limit(1)
    )
