from __future__ import annotations

from datetime import datetime
import hashlib
import json

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.entities import (
    AgentApprovalRequest,
    AgentArtifact,
    AgentEvent,
    AgentRun,
)
from app.models.enums import (
    AgentApprovalStatus,
    AgentApprovalType,
    AgentArtifactStatus,
    AgentArtifactType,
    AgentEventType,
    AgentRunStatus,
)
from app.schemas.agent import ComicPlan
from app.services.agent_observability import agent_span, set_span_result


class AgentApprovalError(RuntimeError):
    pass


def canonical_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def content_hash(content_json: str) -> str:
    return f"sha256:{hashlib.sha256(content_json.encode('utf-8')).hexdigest()}"


def _next_event_sequence(db: Session, run_id: str) -> int:
    maximum = db.scalar(select(func.max(AgentEvent.sequence)).where(AgentEvent.run_id == run_id))
    return int(maximum or 0) + 1


def emit_agent_event(
    db: Session,
    *,
    run: AgentRun,
    event_type: AgentEventType,
    payload: dict[str, object],
    deduplicate: bool = False,
) -> AgentEvent:
    payload_json = canonical_json(payload)
    if deduplicate:
        existing = db.scalar(
            select(AgentEvent)
            .where(
                AgentEvent.run_id == run.id,
                AgentEvent.event_type == event_type,
                AgentEvent.public_payload_json == payload_json,
            )
            .order_by(AgentEvent.sequence.desc())
            .limit(1)
        )
        if existing is not None:
            return existing
    event = AgentEvent(
        conversation_id=run.conversation_id,
        run_id=run.id,
        sequence=_next_event_sequence(db, run.id),
        event_type=event_type,
        public_payload_json=payload_json,
        created_at=datetime.utcnow(),
    )
    db.add(event)
    db.flush()
    return event


def latest_comic_artifact(db: Session, run_id: str) -> AgentArtifact | None:
    return db.scalar(
        select(AgentArtifact)
        .where(
            AgentArtifact.run_id == run_id,
            AgentArtifact.artifact_type == AgentArtifactType.comic_plan,
        )
        .order_by(AgentArtifact.version.desc())
        .limit(1)
    )


def create_comic_plan_artifact(
    db: Session,
    *,
    run: AgentRun,
    plan: ComicPlan,
) -> tuple[AgentArtifact, AgentApprovalRequest]:
    serialized = canonical_json(plan.model_dump(mode="json"))
    digest = content_hash(serialized)
    current = latest_comic_artifact(db, run.id)
    if current is not None and current.content_hash == digest:
        approval = current.approval_request
        if approval is None:
            raise AgentApprovalError("漫画方案缺少 Approval Request")
        return current, approval

    version = (current.version + 1) if current is not None else 1
    if current is not None:
        if current.approval_request is not None and current.approval_request.status == AgentApprovalStatus.pending:
            current.approval_request.status = AgentApprovalStatus.cancelled
            current.approval_request.resolved_at = datetime.utcnow()
        current.status = AgentArtifactStatus.superseded

    artifact = AgentArtifact(
        conversation_id=run.conversation_id,
        run_id=run.id,
        artifact_type=AgentArtifactType.comic_plan,
        version=version,
        status=AgentArtifactStatus.awaiting_approval,
        content_json=serialized,
        content_hash=digest,
    )
    db.add(artifact)
    db.flush()
    approval = AgentApprovalRequest(
        conversation_id=run.conversation_id,
        run_id=run.id,
        artifact_id=artifact.id,
        artifact_hash=digest,
        approval_type=AgentApprovalType.comic_plan,
        status=AgentApprovalStatus.pending,
    )
    db.add(approval)
    run.status = AgentRunStatus.waiting_for_input
    emit_agent_event(
        db,
        run=run,
        event_type=AgentEventType.artifact_created,
        payload={
            "artifact_id": artifact.id,
            "artifact_type": artifact.artifact_type.value,
            "version": artifact.version,
            "title": plan.title,
            "panel_count": len(plan.panels),
        },
    )
    emit_agent_event(
        db,
        run=run,
        event_type=AgentEventType.approval_requested,
        payload={
            "approval_id": approval.id,
            "artifact_id": artifact.id,
            "version": artifact.version,
            "estimated_image_credits": plan.estimated_image_credits,
        },
    )
    db.commit()
    db.refresh(artifact)
    db.refresh(approval)
    with agent_span(
        "agent.artifact",
        agent_run_id=run.id,
        span_type="CHAIN",
        attributes={
            "artifact_type": artifact.artifact_type.value,
            "artifact_version": artifact.version,
            "artifact_status": artifact.status.value,
        },
    ) as span:
        set_span_result(
            span,
            {
                "artifact_id": artifact.id,
                "approval_id": approval.id,
                "content_hash": artifact.content_hash,
            },
        )
    return artifact, approval


def approved_comic_plan(db: Session, run: AgentRun) -> tuple[AgentArtifact, ComicPlan] | None:
    artifact = latest_comic_artifact(db, run.id)
    if artifact is None or artifact.status != AgentArtifactStatus.approved:
        return None
    approval = artifact.approval_request
    if approval is None or approval.status != AgentApprovalStatus.approved:
        return None
    actual_hash = content_hash(artifact.content_json)
    if actual_hash != artifact.content_hash or actual_hash != approval.artifact_hash:
        raise AgentApprovalError("已批准漫画方案的内容 hash 不一致")
    return artifact, ComicPlan.model_validate_json(artifact.content_json)


def decide_approval(
    db: Session,
    *,
    approval: AgentApprovalRequest,
    user_id: str,
    decision: str,
    feedback: str | None,
) -> AgentApprovalRequest:
    artifact = approval.artifact
    run = approval.run
    actual_hash = content_hash(artifact.content_json)
    if actual_hash != artifact.content_hash or actual_hash != approval.artifact_hash:
        raise AgentApprovalError("漫画方案内容已变化，不能批准")

    target = (
        AgentApprovalStatus.approved
        if decision == "approve"
        else AgentApprovalStatus.changes_requested
    )
    normalized_feedback = feedback.strip() if feedback else None
    if approval.status == target:
        if target == AgentApprovalStatus.changes_requested and approval.feedback != normalized_feedback:
            raise AgentApprovalError("该修改请求已经用不同反馈完成")
        return approval
    if approval.status != AgentApprovalStatus.pending:
        raise AgentApprovalError("该确认请求已经处理")

    approval.status = target
    approval.resolved_at = datetime.utcnow()
    approval.decided_by_user_id = user_id
    approval.feedback = normalized_feedback
    if target == AgentApprovalStatus.approved:
        artifact.status = AgentArtifactStatus.approved
    else:
        artifact.status = AgentArtifactStatus.rejected
    run.status = AgentRunStatus.queued
    run.finished_at = None
    emit_agent_event(
        db,
        run=run,
        event_type=AgentEventType.approval_resolved,
        payload={
            "approval_id": approval.id,
            "artifact_id": artifact.id,
            "version": artifact.version,
            "decision": decision,
            "has_feedback": bool(normalized_feedback),
        },
    )
    db.commit()
    db.refresh(approval)
    with agent_span(
        "agent.approval",
        agent_run_id=run.id,
        span_type="CHAIN",
        attributes={
            "approval_type": approval.approval_type.value,
            "approval_status": approval.status.value,
            "artifact_version": artifact.version,
        },
    ) as span:
        set_span_result(
            span,
            {
                "approval_id": approval.id,
                "artifact_id": artifact.id,
                "decision": decision,
            },
        )
    return approval


def cancel_pending_approvals(db: Session, run: AgentRun) -> None:
    pending = db.scalars(
        select(AgentApprovalRequest).where(
            AgentApprovalRequest.run_id == run.id,
            AgentApprovalRequest.status == AgentApprovalStatus.pending,
        )
    ).all()
    for approval in pending:
        approval.status = AgentApprovalStatus.cancelled
        approval.resolved_at = datetime.utcnow()
