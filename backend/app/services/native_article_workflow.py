from __future__ import annotations

from datetime import datetime
import hashlib
import json

from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from app.core.database import SessionLocal
from app.models.entities import (
    NativeAgentArticleApproval,
    NativeAgentArtifact,
    NativeAgentContextItem,
    NativeAgentItem,
    NativeAgentRun,
)
from app.models.enums import AgentRunStatus, NativeAgentItemType
from app.services.native_agent_persistence import add_native_agent_event


ARTICLE_DRAFT = "article_draft"
ARTICLE_REVIEW = "article_review"
FINAL_ARTICLE = "final_article"
COMPILED_WORKFLOW_PLAN_SCHEMA_VERSION = 1


class NativeArticleWorkflowError(RuntimeError):
    pass


def _json_dumps(value: object) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )


def _content_hash(content_json: str) -> str:
    return f"sha256:{hashlib.sha256(content_json.encode('utf-8')).hexdigest()}"


def _next_sequence(db: Session, model, run_id: str) -> int:
    latest = db.scalar(select(func.max(model.sequence)).where(model.run_id == run_id))
    return int(latest or 0) + 1


def _checkpoint(run: NativeAgentRun) -> dict[str, object]:
    if not run.workflow_checkpoint_json:
        return {"schema_version": 1, "artifacts": {}}
    value = json.loads(run.workflow_checkpoint_json)
    if not isinstance(value, dict):
        raise NativeArticleWorkflowError("文案工作流 Checkpoint 数据损坏")
    return value


def _artifact_payload(artifact: NativeAgentArtifact) -> dict[str, object]:
    return {
        "id": artifact.id,
        "artifact_type": artifact.artifact_type,
        "schema_version": artifact.schema_version,
        "version": artifact.version,
        "status": artifact.status,
        "producer_role": artifact.producer_role,
        "content": json.loads(artifact.content_json),
        "content_hash": artifact.content_hash,
    }


def load_compiled_workflow_plan(
    run_id: str,
    *,
    skill_content_hash: str,
    session_factory: sessionmaker = SessionLocal,
) -> dict[str, object] | None:
    with session_factory() as db:
        run = db.get(NativeAgentRun, run_id)
        if run is None:
            raise NativeArticleWorkflowError("Native Agent Run 不存在")
        checkpoint = _checkpoint(run)
        compiled = checkpoint.get("compiled_workflow")
        if compiled is None:
            return None
        if not isinstance(compiled, dict):
            raise NativeArticleWorkflowError("文案工作流编译计划数据损坏")
        if (
            compiled.get("schema_version")
            != COMPILED_WORKFLOW_PLAN_SCHEMA_VERSION
        ):
            raise NativeArticleWorkflowError("文案工作流编译计划版本不受支持")
        if compiled.get("skill_content_hash") != skill_content_hash:
            raise NativeArticleWorkflowError("文案工作流编译计划与 Skill 版本不一致")
        plan = compiled.get("plan")
        if not isinstance(plan, dict):
            raise NativeArticleWorkflowError("文案工作流编译计划缺少 plan")
        return plan


def save_compiled_workflow_plan(
    run_id: str,
    *,
    skill_content_hash: str,
    plan: dict[str, object],
    session_factory: sessionmaker = SessionLocal,
) -> None:
    plan_json = _json_dumps(plan)
    plan_hash = _content_hash(plan_json)
    with session_factory() as db:
        run = db.get(NativeAgentRun, run_id)
        if run is None:
            raise NativeArticleWorkflowError("Native Agent Run 不存在")
        checkpoint = _checkpoint(run)
        existing = checkpoint.get("compiled_workflow")
        if existing is not None:
            if not isinstance(existing, dict):
                raise NativeArticleWorkflowError("文案工作流编译计划数据损坏")
            if (
                existing.get("skill_content_hash") == skill_content_hash
                and existing.get("plan_hash") == plan_hash
            ):
                return
            raise NativeArticleWorkflowError("同一 Run 已存在不同的文案工作流编译计划")
        checkpoint["schema_version"] = 1
        checkpoint["compiled_workflow"] = {
            "schema_version": COMPILED_WORKFLOW_PLAN_SCHEMA_VERSION,
            "skill_content_hash": skill_content_hash,
            "plan_hash": plan_hash,
            "plan": json.loads(plan_json),
        }
        if not run.workflow_phase:
            checkpoint["phase"] = "workflow_compiled"
            checkpoint["workflow_revision"] = run.workflow_revision
            run.workflow_phase = "workflow_compiled"
        run.workflow_checkpoint_json = _json_dumps(checkpoint)
        add_native_agent_event(
            db,
            run_id=run_id,
            event_type="workflow.compiled",
            payload={
                "schema_version": COMPILED_WORKFLOW_PLAN_SCHEMA_VERSION,
                "skill_content_hash": skill_content_hash,
                "plan_hash": plan_hash,
            },
        )
        db.commit()


def save_article_artifact(
    run_id: str,
    *,
    artifact_type: str,
    producer_role: str,
    content: dict[str, object],
    session_factory: sessionmaker = SessionLocal,
) -> dict[str, object]:
    if artifact_type not in {ARTICLE_DRAFT, ARTICLE_REVIEW}:
        raise NativeArticleWorkflowError("不支持的子 Agent Artifact 类型")
    content_json = _json_dumps(content)
    digest = _content_hash(content_json)
    with session_factory() as db:
        run = db.get(NativeAgentRun, run_id)
        if run is None:
            raise NativeArticleWorkflowError("Native Agent Run 不存在")
        latest = db.scalar(
            select(NativeAgentArtifact)
            .where(
                NativeAgentArtifact.run_id == run_id,
                NativeAgentArtifact.artifact_type == artifact_type,
            )
            .order_by(NativeAgentArtifact.version.desc())
            .limit(1)
        )
        if (
            latest is not None
            and latest.content_hash == digest
            and latest.status == "completed"
        ):
            return _artifact_payload(latest)
        version = (latest.version + 1) if latest is not None else 1
        if latest is not None and latest.status == "completed":
            latest.status = "superseded"
        artifact = NativeAgentArtifact(
            run_id=run_id,
            artifact_type=artifact_type,
            schema_version=1,
            version=version,
            status="completed",
            producer_role=producer_role,
            content_json=content_json,
            content_hash=digest,
        )
        db.add(artifact)
        db.flush()
        checkpoint = _checkpoint(run)
        artifacts = checkpoint.setdefault("artifacts", {})
        if not isinstance(artifacts, dict):
            raise NativeArticleWorkflowError("文案工作流 Artifact Checkpoint 数据损坏")
        artifacts[artifact_type] = artifact.id
        checkpoint["schema_version"] = 1
        checkpoint["phase"] = (
            "draft_ready" if artifact_type == ARTICLE_DRAFT else "review_ready"
        )
        checkpoint["workflow_revision"] = run.workflow_revision
        run.workflow_phase = str(checkpoint["phase"])
        run.workflow_checkpoint_json = _json_dumps(checkpoint)
        add_native_agent_event(
            db,
            run_id=run_id,
            event_type="artifact.created",
            payload={
                "artifact_id": artifact.id,
                "artifact_type": artifact.artifact_type,
                "version": artifact.version,
                "producer_role": producer_role,
            },
        )
        db.commit()
        return _artifact_payload(artifact)


def request_final_article_approval(
    run_id: str,
    *,
    title: str,
    body_markdown: str,
    session_factory: sessionmaker = SessionLocal,
) -> dict[str, object]:
    normalized_title = title.strip()
    normalized_body = body_markdown.strip()
    if not normalized_title or not normalized_body:
        raise NativeArticleWorkflowError("最终文案标题和正文不能为空")
    content = {"title": normalized_title, "body_markdown": normalized_body}
    content_json = _json_dumps(content)
    digest = _content_hash(content_json)
    with session_factory() as db:
        run = db.get(NativeAgentRun, run_id)
        if run is None:
            raise NativeArticleWorkflowError("Native Agent Run 不存在")
        latest = db.scalar(
            select(NativeAgentArtifact)
            .where(
                NativeAgentArtifact.run_id == run_id,
                NativeAgentArtifact.artifact_type == FINAL_ARTICLE,
            )
            .order_by(NativeAgentArtifact.version.desc())
            .limit(1)
        )
        if (
            latest is not None
            and latest.content_hash == digest
            and latest.approval is not None
            and latest.approval.status == "pending"
        ):
            return {
                "status": "waiting_for_approval",
                "artifact": _artifact_payload(latest),
                "approval_id": latest.approval.id,
            }
        pending_approvals = db.scalars(
            select(NativeAgentArticleApproval).where(
                NativeAgentArticleApproval.run_id == run_id,
                NativeAgentArticleApproval.status == "pending",
            )
        ).all()
        now = datetime.utcnow()
        for pending in pending_approvals:
            pending.status = "cancelled"
            pending.resolved_at = now
            pending.artifact.status = "superseded"
        version = (latest.version + 1) if latest is not None else 1
        artifact = NativeAgentArtifact(
            run_id=run_id,
            artifact_type=FINAL_ARTICLE,
            schema_version=1,
            version=version,
            status="awaiting_approval",
            producer_role="director",
            content_json=content_json,
            content_hash=digest,
        )
        db.add(artifact)
        db.flush()
        approval = NativeAgentArticleApproval(
            run_id=run_id,
            artifact_id=artifact.id,
            artifact_hash=digest,
            status="pending",
        )
        db.add(approval)
        db.flush()
        checkpoint = _checkpoint(run)
        artifacts = checkpoint.setdefault("artifacts", {})
        if not isinstance(artifacts, dict):
            raise NativeArticleWorkflowError("文案工作流 Artifact Checkpoint 数据损坏")
        artifacts[FINAL_ARTICLE] = artifact.id
        checkpoint.update(
            {
                "schema_version": 1,
                "phase": "waiting_for_article_approval",
                "pending_approval_id": approval.id,
                "workflow_revision": run.workflow_revision,
            }
        )
        run.workflow_phase = "waiting_for_article_approval"
        run.workflow_checkpoint_json = _json_dumps(checkpoint)
        add_native_agent_event(
            db,
            run_id=run_id,
            event_type="artifact.created",
            payload={
                "artifact_id": artifact.id,
                "artifact_type": FINAL_ARTICLE,
                "version": version,
                "producer_role": "director",
            },
        )
        add_native_agent_event(
            db,
            run_id=run_id,
            event_type="approval.requested",
            payload={
                "approval_id": approval.id,
                "artifact_id": artifact.id,
                "artifact_type": FINAL_ARTICLE,
                "version": version,
            },
        )
        from app.services.durable_agent_runtime import mirror_native_article_approval

        mirror_native_article_approval(
            db,
            native_run=run,
            native_approval=approval,
        )
        db.commit()
        return {
            "status": "waiting_for_approval",
            "artifact": _artifact_payload(artifact),
            "approval_id": approval.id,
        }


def has_pending_article_approval(
    run_id: str,
    *,
    session_factory: sessionmaker = SessionLocal,
) -> bool:
    with session_factory() as db:
        return (
            db.scalar(
                select(func.count(NativeAgentArticleApproval.id)).where(
                    NativeAgentArticleApproval.run_id == run_id,
                    NativeAgentArticleApproval.status == "pending",
                )
            )
            or 0
        ) > 0


def decide_article_approval(
    approval_id: str,
    *,
    user_id: str,
    decision: str,
    feedback: str | None,
    session_factory: sessionmaker = SessionLocal,
) -> tuple[str, str]:
    if decision not in {"approve", "changes_requested"}:
        raise NativeArticleWorkflowError("不支持的文案审批决定")
    normalized_feedback = feedback.strip() if feedback else None
    if decision == "changes_requested" and not normalized_feedback:
        raise NativeArticleWorkflowError("要求修改时必须填写具体意见")
    with session_factory() as db:
        approval = db.get(NativeAgentArticleApproval, approval_id)
        if approval is None:
            raise NativeArticleWorkflowError("文案审批不存在")
        run = approval.run
        artifact = approval.artifact
        if _content_hash(artifact.content_json) != approval.artifact_hash:
            raise NativeArticleWorkflowError("待审批文案内容校验失败")
        if approval.status != "pending":
            expected = (
                "approved" if decision == "approve" else "changes_requested"
            )
            if approval.status != expected:
                raise NativeArticleWorkflowError("文案审批已经由其它决定处理")
            return run.id, approval.status
        now = datetime.utcnow()
        approval.status = (
            "approved" if decision == "approve" else "changes_requested"
        )
        approval.feedback = normalized_feedback
        approval.resolved_at = now
        approval.decided_by_user_id = user_id
        checkpoint = _checkpoint(run)
        checkpoint["pending_approval_id"] = None
        if decision == "approve":
            artifact.status = "approved"
            content = json.loads(artifact.content_json)
            run.status = AgentRunStatus.succeeded
            run.workflow_phase = "article_approved"
            run.final_output = str(content["body_markdown"])
            run.finished_at = now
            checkpoint["phase"] = "article_approved"
            add_native_agent_event(
                db,
                run_id=run.id,
                event_type="run.completed",
                payload={"status": "succeeded", "result": "article_approved"},
            )
        else:
            artifact.status = "rejected"
            run.status = AgentRunStatus.retrying
            run.workflow_revision += 1
            run.workflow_phase = "revising_article"
            run.finished_at = None
            run.error_code = None
            run.error_message = None
            checkpoint.update(
                {
                    "phase": "revising_article",
                    "workflow_revision": run.workflow_revision,
                    "revision_feedback": normalized_feedback,
                }
            )
            next_context_sequence = _next_sequence(
                db, NativeAgentContextItem, run.id
            )
            db.add(
                NativeAgentContextItem(
                    run_id=run.id,
                    sequence=next_context_sequence,
                    item_json=_json_dumps(
                        {
                            "role": "user",
                            "content": (
                                "用户要求修改最终文案。请严格依据以下真实反馈重新调用 Writer "
                                f"和 Reviewer，提交完整新版本：{normalized_feedback}"
                            ),
                        }
                    ),
                )
            )
            db.add(
                NativeAgentItem(
                    run_id=run.id,
                    sequence=_next_sequence(db, NativeAgentItem, run.id),
                    item_type=NativeAgentItemType.user_input,
                    payload_json=_json_dumps(
                        {
                            "content": normalized_feedback,
                            "control": "article_changes_requested",
                        }
                    ),
                )
            )
        run.workflow_checkpoint_json = _json_dumps(checkpoint)
        add_native_agent_event(
            db,
            run_id=run.id,
            event_type="approval.resolved",
            payload={
                "approval_id": approval.id,
                "artifact_id": artifact.id,
                "decision": decision,
                "feedback": normalized_feedback,
            },
        )
        db.commit()
        return run.id, approval.status
