from __future__ import annotations

from datetime import datetime
import hashlib
import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.entities import (
    AgentSkillVersion,
    DurableAgentArtifact,
    DurableAgentCheckpoint,
    DurableAgentWorkflow,
    NativeAgentArtifact,
    NativeAgentConversation,
    NativeAgentItem,
    NativeAgentRun,
    User,
)
from app.models.enums import AgentRunStatus, NativeAgentItemType
from app.schemas.native_agent import NativeAgentFollowUpCreate
from app.services.agent_skill_management import parse_tool_names
from app.services.durable_agent_runtime import initialize_workflow
from app.services.native_agent_persistence import add_native_agent_event
from app.services.native_agent_model_routes import SILICONFLOW_CHAT_ROUTE


FOLLOW_UP_CONTEXT_MAX_BYTES = 64_000
FOLLOW_UP_CONTEXT_MAX_ARTIFACTS = 50
ARTICLE_TOOL_NAMES = {
    "write_article",
    "review_article",
    "submit_final_article",
}
ACTIVE_RUN_STATUSES = (
    AgentRunStatus.queued,
    AgentRunStatus.running,
    AgentRunStatus.waiting_for_tool,
    AgentRunStatus.waiting_for_input,
    AgentRunStatus.retrying,
    AgentRunStatus.cancel_requested,
)


class NativeAgentFollowUpError(RuntimeError):
    pass


def _json(value: object) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )


def follow_up_request_hash(*, parent_run_id: str, content: str) -> str:
    value = _json({"content": content, "parent_run_id": parent_run_id})
    return f"sha256:{hashlib.sha256(value.encode('utf-8')).hexdigest()}"


def _parse_object(value: str, *, label: str) -> dict[str, object]:
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError as exc:
        raise NativeAgentFollowUpError(f"{label} 不是有效 JSON") from exc
    if not isinstance(parsed, dict):
        raise NativeAgentFollowUpError(f"{label} 必须是 JSON 对象")
    return parsed


def _continuation_context(
    db: Session,
    *,
    parent_run: NativeAgentRun,
    workflow: DurableAgentWorkflow,
    checkpoint: DurableAgentCheckpoint,
) -> str:
    durable_artifacts = db.scalars(
        select(DurableAgentArtifact)
        .where(
            DurableAgentArtifact.workflow_id == workflow.id,
            DurableAgentArtifact.status == "committed",
        )
        .order_by(
            DurableAgentArtifact.created_at,
            DurableAgentArtifact.artifact_key,
            DurableAgentArtifact.version,
        )
    ).all()
    native_artifacts = db.scalars(
        select(NativeAgentArtifact)
        .where(
            NativeAgentArtifact.run_id == parent_run.id,
            NativeAgentArtifact.status.in_(("completed", "approved")),
        )
        .order_by(
            NativeAgentArtifact.created_at,
            NativeAgentArtifact.artifact_type,
            NativeAgentArtifact.version,
        )
    ).all()
    artifact_count = len(durable_artifacts) + len(native_artifacts)
    if artifact_count > FOLLOW_UP_CONTEXT_MAX_ARTIFACTS:
        raise NativeAgentFollowUpError(
            "父 Run 产物数量超过 Follow-up 上下文上限，无法完整续接"
        )

    context = {
        "schema_version": 1,
        "source_run": {
            "id": parent_run.id,
            "status": parent_run.status.value,
            "final_output": parent_run.final_output,
        },
        "checkpoint": {
            "id": checkpoint.id,
            "revision": checkpoint.revision,
            "state_hash": checkpoint.state_hash,
            "state": _parse_object(
                checkpoint.state_json,
                label="父 Run Checkpoint State",
            ),
        },
        "durable_artifacts": [
            {
                "id": artifact.id,
                "artifact_key": artifact.artifact_key,
                "artifact_type": artifact.artifact_type,
                "version": artifact.version,
                "status": artifact.status,
                "content_hash": artifact.content_hash,
                "content": _parse_object(
                    artifact.content_json,
                    label=f"Durable Artifact {artifact.id}",
                ),
            }
            for artifact in durable_artifacts
        ],
        "native_artifacts": [
            {
                "id": artifact.id,
                "artifact_type": artifact.artifact_type,
                "schema_version": artifact.schema_version,
                "version": artifact.version,
                "status": artifact.status,
                "producer_role": artifact.producer_role,
                "content_hash": artifact.content_hash,
                "content": _parse_object(
                    artifact.content_json,
                    label=f"Native Artifact {artifact.id}",
                ),
            }
            for artifact in native_artifacts
        ],
    }
    serialized = _json(context)
    if len(serialized.encode("utf-8")) > FOLLOW_UP_CONTEXT_MAX_BYTES:
        raise NativeAgentFollowUpError(
            "父 Run 完整上下文超过 64000 字节，无法完整续接"
        )
    return serialized


def find_idempotent_follow_up(
    db: Session,
    *,
    user: User,
    parent_run_id: str,
    payload: NativeAgentFollowUpCreate,
) -> NativeAgentRun | None:
    existing = db.scalar(
        select(NativeAgentRun).where(
            NativeAgentRun.follow_up_idempotency_key == payload.idempotency_key
        )
    )
    if existing is None:
        return None
    conversation = db.get(NativeAgentConversation, existing.conversation_id)
    expected_hash = follow_up_request_hash(
        parent_run_id=parent_run_id,
        content=payload.content,
    )
    if (
        conversation is None
        or conversation.owner_user_id != user.id
        or existing.parent_run_id != parent_run_id
        or existing.follow_up_request_hash != expected_hash
    ):
        raise NativeAgentFollowUpError("幂等键已用于不同的 Follow-up 请求")
    return existing


def create_follow_up_run(
    db: Session,
    *,
    parent_run: NativeAgentRun,
    user: User,
    payload: NativeAgentFollowUpCreate,
) -> tuple[NativeAgentRun, bool]:
    if parent_run.model_route_snapshot == SILICONFLOW_CHAT_ROUTE:
        raise NativeAgentFollowUpError(
            "SiliconFlow Chat S03 Run 不允许创建 Follow-up"
        )
    existing = find_idempotent_follow_up(
        db,
        user=user,
        parent_run_id=parent_run.id,
        payload=payload,
    )
    if existing is not None:
        return existing, True

    conversation = db.get(NativeAgentConversation, parent_run.conversation_id)
    if conversation is None or conversation.owner_user_id != user.id:
        raise NativeAgentFollowUpError("父 Run 不存在或不可访问")
    if parent_run.status != AgentRunStatus.succeeded:
        raise NativeAgentFollowUpError("只有已成功完成的 Run 可以创建 Follow-up")
    active_run = db.scalar(
        select(NativeAgentRun).where(
            NativeAgentRun.conversation_id == conversation.id,
            NativeAgentRun.status.in_(ACTIVE_RUN_STATUSES),
        )
    )
    if active_run is not None:
        raise NativeAgentFollowUpError("当前会话仍有一轮正在运行")

    workflow = db.scalar(
        select(DurableAgentWorkflow).where(
            DurableAgentWorkflow.native_run_id == parent_run.id
        )
    )
    if workflow is None or workflow.current_checkpoint_id is None:
        raise NativeAgentFollowUpError("父 Run 缺少可续接的 Durable Checkpoint")
    checkpoint = db.get(DurableAgentCheckpoint, workflow.current_checkpoint_id)
    if checkpoint is None or checkpoint.workflow_id != workflow.id:
        raise NativeAgentFollowUpError("父 Run 当前 Checkpoint 无效")

    skill_version = db.get(AgentSkillVersion, parent_run.skill_version_id)
    if skill_version is None:
        raise NativeAgentFollowUpError("父 Run 固定的 Skill Version 已不存在")
    continuation_context_json = _continuation_context(
        db,
        parent_run=parent_run,
        workflow=workflow,
        checkpoint=checkpoint,
    )
    request_hash = follow_up_request_hash(
        parent_run_id=parent_run.id,
        content=payload.content,
    )
    run = NativeAgentRun(
        conversation_id=conversation.id,
        parent_run_id=parent_run.id,
        continued_from_checkpoint_id=checkpoint.id,
        follow_up_idempotency_key=payload.idempotency_key,
        follow_up_request_hash=request_hash,
        continuation_context_json=continuation_context_json,
        skill_version_id=parent_run.skill_version_id,
        style_id=parent_run.style_id,
        status=AgentRunStatus.queued,
        model_snapshot=parent_run.model_snapshot,
        model_route_snapshot=parent_run.model_route_snapshot,
        model_provider_snapshot=parent_run.model_provider_snapshot,
        model_api_shape_snapshot=parent_run.model_api_shape_snapshot,
        skill_name_snapshot=parent_run.skill_name_snapshot,
        skill_version_snapshot=parent_run.skill_version_snapshot,
        skill_content_hash_snapshot=parent_run.skill_content_hash_snapshot,
        style_name_snapshot=parent_run.style_name_snapshot,
        style_prompt_snapshot=parent_run.style_prompt_snapshot,
        image_model_snapshot=parent_run.image_model_snapshot,
        aspect_ratio_snapshot=parent_run.aspect_ratio_snapshot,
        style_reference_urls_json=parent_run.style_reference_urls_json,
        creation_channel_id=parent_run.creation_channel_id,
        creation_channel_context_json=parent_run.creation_channel_context_json,
        youtube_channel_id=parent_run.youtube_channel_id,
        youtube_publishable_video_id=parent_run.youtube_publishable_video_id,
        youtube_publish_confirmation_json=None,
        youtube_publish_confirmed_at=None,
    )
    db.add(run)
    db.flush()
    db.add(
        NativeAgentItem(
            run_id=run.id,
            sequence=1,
            item_type=NativeAgentItemType.user_input,
            payload_json=_json(
                {
                    "content": payload.content,
                    "follow_up_parent_run_id": parent_run.id,
                }
            ),
        )
    )
    add_native_agent_event(
        db,
        run.id,
        "follow_up.created",
        {
            "status": AgentRunStatus.queued.value,
            "parent_run_id": parent_run.id,
            "continued_from_checkpoint_id": checkpoint.id,
        },
    )
    conversation.last_message_at = datetime.utcnow()
    selected_tool_names = set(parse_tool_names(skill_version.tool_names_json))
    initialize_workflow(
        db,
        native_run=run,
        include_article_tasks=bool(ARTICLE_TOOL_NAMES & selected_tool_names),
    )
    db.flush()
    return run, False
