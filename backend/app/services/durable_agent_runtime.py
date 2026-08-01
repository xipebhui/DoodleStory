from __future__ import annotations

from datetime import datetime, timedelta
import hashlib
import json

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.models.entities import (
    DurableAgentArtifact,
    DurableAgentAttempt,
    DurableAgentCheckpoint,
    DurableAgentGate,
    DurableAgentTask,
    DurableAgentWorkflow,
    NativeAgentArticleApproval,
    NativeAgentRun,
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


def _json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def _hash(value: object) -> str:
    return f"sha256:{hashlib.sha256(_json(value).encode('utf-8')).hexdigest()}"


def _now() -> datetime:
    return datetime.utcnow()


def workflow_for_native_run(db: Session, native_run_id: str) -> DurableAgentWorkflow | None:
    return db.scalar(
        select(DurableAgentWorkflow).where(
            DurableAgentWorkflow.native_run_id == native_run_id
        )
    )


def initialize_workflow(db: Session, *, native_run: NativeAgentRun) -> DurableAgentWorkflow:
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
    return workflow


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
    elif native_type == "article_review" or gate_count == 1:
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
    return record_artifact(
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
    return bool(tasks) and all(task.status == "succeeded" for task in tasks)


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
    return attempts


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
            recovered.append(replacement.id)
            continue
        recovered.append(attempt.id)
    return recovered
