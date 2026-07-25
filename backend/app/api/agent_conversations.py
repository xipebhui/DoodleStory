from __future__ import annotations

from datetime import datetime
import asyncio
import json

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, status
from fastapi.responses import StreamingResponse
from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session, selectinload

from app.api.deps import current_user
from app.api.pagination import Pagination, build_page, get_pagination
from app.core.database import get_db
from app.models.entities import (
    AgentConversation,
    AgentApprovalRequest,
    AgentArtifact,
    AgentEvent,
    AgentMessage,
    AgentRun,
    AgentSkill,
    AgentSkillVersion,
    AgentStep,
    GeneratedImage,
    GenerationTask,
    Style,
    TaskPanel,
    User,
    UserCharacter,
    new_id,
)
from app.models.enums import (
    AgentConversationStatus,
    AgentEventType,
    AgentMessageRole,
    AgentRunStatus,
    AgentSkillStatus,
    StyleStatus,
)
from app.schemas.agent import (
    AgentApprovalDecision,
    AgentApprovalRead,
    AgentArtifactRead,
    AgentConversationCreate,
    AgentConversationDetailRead,
    AgentConversationRead,
    AgentMessageCreate,
    AgentMessageRead,
    AgentPanelRegenerationCreate,
    AgentImageInspectionRead,
    AgentResourceRef,
    AgentResourceKind,
    AgentResourceOption,
    AgentRunRead,
    AgentRunSummaryRead,
    AgentStepRead,
    AgentTaskCardImageRead,
    AgentTaskCardPanelRead,
    AgentTaskCardRead,
    AgentTaskInspectorImageRead,
    AgentTaskInspectorPanelRead,
    AgentTaskInspectorRead,
    AgentTurnAcceptedRead,
)
from app.schemas.common import ApiData, ApiList
from app.services.agent_runner import enqueue_agent_run
from app.services.agent_hitl import AgentApprovalError, decide_approval, emit_agent_event
from app.services.agent_resources import (
    AgentResourceResolutionError,
    AgentResourceResolver,
    parse_agent_resource_refs,
)
from app.core import database
from app.services.agent_panel_versions import (
    AgentPanelVersionError,
    accept_image_version,
    inspection_events_for_conversation,
    restore_image_version,
    start_panel_regeneration,
)
router = APIRouter(prefix="/agent", tags=["agent"])


def load_owned_conversation(db: Session, conversation_id: str, user: User) -> AgentConversation:
    conversation = db.scalar(
        select(AgentConversation).where(
            AgentConversation.id == conversation_id,
            AgentConversation.owner_user_id == user.id,
        )
    )
    if conversation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent 会话不存在")
    return conversation


def parse_resource_refs(raw: str | None) -> list[AgentResourceRef]:
    try:
        return parse_agent_resource_refs(raw)
    except AgentResourceResolutionError as exc:
        raise RuntimeError("Agent 消息资源引用数据损坏") from exc


def message_to_read(message: AgentMessage) -> AgentMessageRead:
    return AgentMessageRead(
        id=message.id,
        conversation_id=message.conversation_id,
        turn_id=message.turn_id,
        role=message.role,
        content=message.content,
        resource_refs=parse_resource_refs(message.resource_refs_json),
        sequence=message.sequence,
        created_at=message.created_at,
    )


def approval_to_read(approval: AgentApprovalRequest) -> AgentApprovalRead:
    return AgentApprovalRead(
        id=approval.id,
        artifact_id=approval.artifact_id,
        status=approval.status,
        artifact_hash=approval.artifact_hash,
        feedback=approval.feedback,
        requested_at=approval.requested_at,
        resolved_at=approval.resolved_at,
    )


def artifact_to_read(artifact: AgentArtifact) -> AgentArtifactRead:
    return AgentArtifactRead(
        id=artifact.id,
        conversation_id=artifact.conversation_id,
        run_id=artifact.run_id,
        artifact_type=artifact.artifact_type,
        version=artifact.version,
        status=artifact.status,
        content_hash=artifact.content_hash,
        content=json.loads(artifact.content_json),
        approval=(
            approval_to_read(artifact.approval_request)
            if artifact.approval_request is not None
            else None
        ),
        created_at=artifact.created_at,
        updated_at=artifact.updated_at,
    )


def run_to_read(db: Session, run: AgentRun) -> AgentRunRead:
    steps = db.scalars(
        select(AgentStep)
        .where(AgentStep.run_id == run.id)
        .order_by(AgentStep.sequence.asc())
        .limit(100)
    ).all()
    return AgentRunRead(
        id=run.id,
        conversation_id=run.conversation_id,
        turn_id=run.turn_id,
        task_id=run.task_id,
        skill_version_id=run.skill_version_id,
        skill_name=run.skill_version.name_snapshot if run.skill_version else None,
        skill_version_number=run.skill_version.version if run.skill_version else None,
        status=run.status,
        current_step_sequence=run.current_step_sequence,
        model_call_count=run.model_call_count,
        image_call_count=run.image_call_count,
        started_at=run.started_at,
        finished_at=run.finished_at,
        error_code=run.error_code,
        error_message=run.error_message,
        created_at=run.created_at,
        updated_at=run.updated_at,
        steps=[AgentStepRead.model_validate(step) for step in steps],
    )


def current_panel_image(images: list[GeneratedImage]) -> GeneratedImage | None:
    panel_images = [image for image in images if image.panel_id is not None]
    current_images = [image for image in panel_images if image.is_current]
    if not current_images:
        return None
    return max(
        current_images,
        key=lambda image: (image.generation_number, image.created_at, image.id),
    )


def current_or_latest_panel_image(images: list[GeneratedImage]) -> GeneratedImage | None:
    current_image = current_panel_image(images)
    if current_image is not None:
        return current_image
    panel_images = [image for image in images if image.panel_id is not None]
    if not panel_images:
        return None
    return max(
        panel_images,
        key=lambda image: (image.generation_number, image.created_at, image.id),
    )


def task_card_image_to_read(image: GeneratedImage) -> AgentTaskCardImageRead:
    return AgentTaskCardImageRead(
        id=image.id,
        status=image.status,
        asset_id=image.asset_id,
        width=image.asset.width if image.asset else None,
        height=image.asset.height if image.asset else None,
        error_code=image.error_code,
        error_message=image.error_message,
    )


def task_inspector_image_to_read(
    image: GeneratedImage,
    *,
    current_user_id: str | None = None,
    inspection_payload: dict[str, object] | None = None,
) -> AgentTaskInspectorImageRead:
    inspection = None
    if inspection_payload and inspection_payload.get("status") == "succeeded":
        inspected_at = inspection_payload.get("inspected_at")
        inspection = AgentImageInspectionRead(
            verdict=inspection_payload["verdict"],
            scores=inspection_payload.get("scores", {}),
            issues=inspection_payload.get("issues", []),
            provider=str(inspection_payload.get("provider") or ""),
            model=str(inspection_payload.get("model") or ""),
            inspected_at=datetime.fromisoformat(str(inspected_at)),
        )
    return AgentTaskInspectorImageRead(
        id=image.id,
        generation_number=image.generation_number,
        status=image.status,
        is_current=image.is_current,
        source_type=image.source_type,
        asset_id=image.asset_id,
        width=image.asset.width if image.asset else None,
        height=image.asset.height if image.asset else None,
        error_code=image.error_code,
        error_message=image.error_message,
        accepted_at=image.accepted_at,
        accepted_by_current_user=(
            current_user_id is not None
            and image.accepted_by_user_id == current_user_id
        ),
        inspection=inspection,
        created_at=image.created_at,
    )


def task_card_to_read(run: AgentRun) -> AgentTaskCardRead:
    task = run.task
    if task is None:
        raise RuntimeError("Agent Run 任务卡片缺少 GenerationTask")
    panels: list[AgentTaskCardPanelRead] = []
    for panel in sorted(task.panels, key=lambda item: item.panel_order):
        image = current_or_latest_panel_image(panel.generated_images)
        panels.append(
            AgentTaskCardPanelRead(
                id=panel.id,
                panel_order=panel.panel_order,
                story_beat=panel.original_text_segment,
                visual_goal=panel.text_layout,
                image=task_card_image_to_read(image) if image is not None else None,
            )
        )
    return AgentTaskCardRead(
        task_id=task.id,
        run_id=run.id,
        title=task.display_title,
        status=task.status,
        progress_current=sum(
            panel.image is not None
            and panel.image.status.value in {"succeeded", "failed", "cancelled"}
            for panel in panels
        ),
        progress_total=len(panels),
        error_code=task.error_code,
        error_message=task.error_message,
        panels=panels,
    )


def task_inspector_to_read(
    conversation_id: str,
    task: GenerationTask,
    *,
    current_user_id: str | None = None,
    inspections: dict[str, dict[str, object]] | None = None,
) -> AgentTaskInspectorRead:
    inspection_map = inspections or {}
    panels: list[AgentTaskInspectorPanelRead] = []
    for panel in sorted(task.panels, key=lambda item: item.panel_order):
        versions = sorted(
            (image for image in panel.generated_images if image.panel_id is not None),
            key=lambda image: (image.generation_number, image.created_at, image.id),
            reverse=True,
        )[:20]
        current_image = current_panel_image(panel.generated_images)
        latest_image = versions[0] if versions else None
        panels.append(
            AgentTaskInspectorPanelRead(
                id=panel.id,
                panel_order=panel.panel_order,
                story_beat=panel.original_text_segment,
                visual_goal=panel.text_layout,
                status=latest_image.status if latest_image is not None else None,
                error_code=latest_image.error_code if latest_image is not None else panel.error_code,
                error_message=latest_image.error_message if latest_image is not None else panel.error_message,
                current_image=(
                    task_inspector_image_to_read(
                        current_image,
                        current_user_id=current_user_id,
                        inspection_payload=inspection_map.get(current_image.id),
                    )
                    if current_image is not None
                    else None
                ),
                versions=[
                    task_inspector_image_to_read(
                        image,
                        current_user_id=current_user_id,
                        inspection_payload=inspection_map.get(image.id),
                    )
                    for image in versions
                ],
            )
        )
    return AgentTaskInspectorRead(
        conversation_id=conversation_id,
        task_id=task.id,
        title=task.display_title,
        status=task.status,
        progress_current=sum(
            panel.status is not None
            and panel.status.value in {"succeeded", "failed", "cancelled"}
            for panel in panels
        ),
        progress_total=len(panels),
        error_code=task.error_code,
        error_message=task.error_message,
        panels=panels,
    )


@router.get("/resources/styles", response_model=ApiList[AgentResourceOption])
def list_agent_style_resources(
    query: str = Query(default="", max_length=120),
    limit: int = Query(default=20, ge=1, le=50),
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> ApiList[AgentResourceOption]:
    del user
    statement = select(Style).where(
        Style.deleted_at.is_(None),
        Style.status == StyleStatus.active,
    )
    if query.strip():
        statement = statement.where(Style.name.ilike(f"%{query.strip()}%"))
    items = db.scalars(
        statement.order_by(Style.updated_at.desc(), Style.id.desc()).limit(limit + 1)
    ).all()
    visible = items[:limit]
    return ApiList(
        items=[
            AgentResourceOption(
                kind=AgentResourceKind.style,
                id=item.id,
                display_name=item.name,
                secondary_text=f"{item.aspect_ratio} · {item.image_model_name}",
                status=item.status.value,
            )
            for item in visible
        ],
        page=build_page(limit=limit, offset=0, item_count=len(items)),
    )


@router.get("/resources/skills", response_model=ApiList[AgentResourceOption])
def list_agent_skill_resources(
    query: str = Query(default="", max_length=120),
    limit: int = Query(default=20, ge=1, le=50),
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> ApiList[AgentResourceOption]:
    statement = (
        select(AgentSkill, AgentSkillVersion)
        .join(
            AgentSkillVersion,
            AgentSkillVersion.id == AgentSkill.active_version_id,
        )
        .where(
            AgentSkill.status == AgentSkillStatus.published,
            or_(
                AgentSkill.owner_user_id == user.id,
                AgentSkill.owner_user_id.is_(None),
            ),
        )
    )
    if query.strip():
        normalized = query.strip()
        statement = statement.where(
            or_(
                AgentSkill.name.ilike(f"%{normalized}%"),
                AgentSkill.description.ilike(f"%{normalized}%"),
            )
        )
    rows = db.execute(
        statement.order_by(AgentSkill.updated_at.desc(), AgentSkill.id.desc())
        .limit(limit + 1)
    ).all()
    visible = rows[:limit]
    return ApiList(
        items=[
            AgentResourceOption(
                kind=AgentResourceKind.skill,
                id=version.id,
                parent_id=skill.id,
                display_name=f"{version.name_snapshot} · v{version.version}",
                secondary_text=version.description_snapshot,
                status=skill.status.value,
            )
            for skill, version in visible
        ],
        page=build_page(limit=limit, offset=0, item_count=len(rows)),
    )


@router.get("/resources/characters", response_model=ApiList[AgentResourceOption])
def list_agent_character_resources(
    query: str = Query(default="", max_length=120),
    limit: int = Query(default=20, ge=1, le=50),
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> ApiList[AgentResourceOption]:
    statement = select(UserCharacter).where(
        UserCharacter.owner_user_id == user.id,
        UserCharacter.deleted_at.is_(None),
    )
    if query.strip():
        statement = statement.where(UserCharacter.name.ilike(f"%{query.strip()}%"))
    items = db.scalars(
        statement.order_by(UserCharacter.updated_at.desc(), UserCharacter.id.desc())
        .limit(limit + 1)
    ).all()
    visible = items[:limit]
    return ApiList(
        items=[
            AgentResourceOption(
                kind=AgentResourceKind.character,
                id=item.id,
                display_name=item.name,
                secondary_text=item.description,
            )
            for item in visible
        ],
        page=build_page(limit=limit, offset=0, item_count=len(items)),
    )


@router.get("/resources/tasks", response_model=ApiList[AgentResourceOption])
def list_agent_task_resources(
    query: str = Query(default="", max_length=120),
    limit: int = Query(default=20, ge=1, le=50),
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> ApiList[AgentResourceOption]:
    statement = select(GenerationTask).where(GenerationTask.owner_user_id == user.id)
    if query.strip():
        normalized = query.strip()
        statement = statement.where(
            or_(
                GenerationTask.display_title.ilike(f"%{normalized}%"),
                GenerationTask.id.ilike(f"%{normalized}%"),
            )
        )
    items = db.scalars(
        statement.order_by(GenerationTask.created_at.desc(), GenerationTask.id.desc())
        .limit(limit + 1)
    ).all()
    visible = items[:limit]
    return ApiList(
        items=[
            AgentResourceOption(
                kind=AgentResourceKind.task,
                id=item.id,
                display_name=item.display_title,
                secondary_text=item.style_name_snapshot,
                status=item.status.value,
            )
            for item in visible
        ],
        page=build_page(limit=limit, offset=0, item_count=len(items)),
    )


@router.get(
    "/resources/tasks/{task_id}/panels",
    response_model=ApiList[AgentResourceOption],
)
def list_agent_task_panel_resources(
    task_id: str,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> ApiList[AgentResourceOption]:
    task = db.scalar(
        select(GenerationTask).where(
            GenerationTask.id == task_id,
            GenerationTask.owner_user_id == user.id,
        )
    )
    if task is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="任务不存在")
    panels = db.scalars(
        select(TaskPanel)
        .where(TaskPanel.task_id == task.id)
        .order_by(TaskPanel.panel_order.asc())
        .limit(51)
    ).all()
    if len(panels) > 50:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="任务包含超过 50 个 Panel，无法作为 Agent 引用菜单加载",
        )
    return ApiList(
        items=[
            AgentResourceOption(
                kind=AgentResourceKind.panel,
                id=panel.id,
                display_name=f"Panel {panel.panel_order}",
                secondary_text=panel.original_text_segment,
                parent_id=task.id,
            )
            for panel in panels
        ],
        page=build_page(limit=50, offset=0, item_count=len(panels)),
    )


@router.get(
    "/resources/panels/{panel_id}/image-versions",
    response_model=ApiList[AgentResourceOption],
)
def list_agent_panel_image_resources(
    panel_id: str,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
    limit: int = Query(default=20, ge=1, le=50),
) -> ApiList[AgentResourceOption]:
    panel = db.scalar(
        select(TaskPanel)
        .join(GenerationTask, GenerationTask.id == TaskPanel.task_id)
        .where(
            TaskPanel.id == panel_id,
            GenerationTask.owner_user_id == user.id,
        )
    )
    if panel is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Panel 不存在")
    images = db.scalars(
        select(GeneratedImage)
        .where(
            GeneratedImage.panel_id == panel.id,
        )
        .order_by(
            GeneratedImage.generation_number.desc(),
            GeneratedImage.created_at.desc(),
        )
        .limit(limit + 1)
    ).all()
    visible = images[:limit]
    return ApiList(
        items=[
            AgentResourceOption(
                kind=AgentResourceKind.image_version,
                id=image.id,
                display_name=f"Panel {panel.panel_order} · v{image.generation_number}",
                secondary_text="当前版本" if image.is_current else None,
                parent_id=panel.id,
                status=image.status.value,
            )
            for image in visible
        ],
        page=build_page(limit=limit, offset=0, item_count=len(images)),
    )


@router.post("/conversations", response_model=ApiData[AgentConversationRead], status_code=status.HTTP_201_CREATED)
def create_agent_conversation(
    payload: AgentConversationCreate,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> ApiData[AgentConversationRead]:
    conversation = AgentConversation(owner_user_id=user.id, title=payload.title)
    db.add(conversation)
    db.commit()
    db.refresh(conversation)
    return ApiData(data=AgentConversationRead.model_validate(conversation))


@router.get("/conversations", response_model=ApiList[AgentConversationRead])
def list_agent_conversations(
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
    pagination: Pagination = Depends(get_pagination),
) -> ApiList[AgentConversationRead]:
    conversations = db.scalars(
        select(AgentConversation)
        .where(AgentConversation.owner_user_id == user.id)
        .order_by(AgentConversation.last_message_at.desc(), AgentConversation.id.desc())
        .offset(pagination.offset)
        .limit(pagination.limit + 1)
    ).all()
    visible = conversations[: pagination.limit]
    return ApiList(
        items=[AgentConversationRead.model_validate(conversation) for conversation in visible],
        page=build_page(pagination.limit, pagination.offset, len(conversations)),
    )


@router.get("/conversations/{conversation_id}", response_model=ApiData[AgentConversationDetailRead])
def get_agent_conversation(
    conversation_id: str,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
    message_limit: int = Query(default=50, ge=1, le=100),
    message_cursor: int = Query(default=0, ge=0),
) -> ApiData[AgentConversationDetailRead]:
    conversation = load_owned_conversation(db, conversation_id, user)
    messages = db.scalars(
        select(AgentMessage)
        .where(AgentMessage.conversation_id == conversation.id)
        .order_by(AgentMessage.sequence.asc())
        .offset(message_cursor)
        .limit(message_limit + 1)
    ).all()
    visible = messages[:message_limit]
    task_runs = db.scalars(
        select(AgentRun)
        .join(GenerationTask, GenerationTask.id == AgentRun.task_id)
        .where(
            AgentRun.conversation_id == conversation.id,
            AgentRun.task_id.is_not(None),
            GenerationTask.owner_user_id == conversation.owner_user_id,
        )
        .options(
            selectinload(AgentRun.task)
            .selectinload(GenerationTask.panels)
            .selectinload(TaskPanel.generated_images)
            .selectinload(GeneratedImage.asset),
            selectinload(AgentRun.task)
            .selectinload(GenerationTask.generated_images)
            .selectinload(GeneratedImage.asset),
        )
        .order_by(AgentRun.created_at.asc())
        .limit(20)
    ).all()
    recent_runs = db.scalars(
        select(AgentRun)
        .where(AgentRun.conversation_id == conversation.id)
        .order_by(AgentRun.created_at.desc())
        .limit(20)
    ).all()
    unique_task_runs: list[AgentRun] = []
    seen_task_ids: set[str] = set()
    for task_run in task_runs:
        if task_run.task_id is None or task_run.task_id in seen_task_ids:
            continue
        seen_task_ids.add(task_run.task_id)
        unique_task_runs.append(task_run)
    return ApiData(
        data=AgentConversationDetailRead(
            **AgentConversationRead.model_validate(conversation).model_dump(),
            messages=[message_to_read(message) for message in visible],
            message_page=build_page(message_limit, message_cursor, len(messages)),
            task_cards=[task_card_to_read(run) for run in unique_task_runs],
            runs=[AgentRunSummaryRead.model_validate(run) for run in recent_runs],
        )
    )


@router.get(
    "/conversations/{conversation_id}/tasks/{task_id}",
    response_model=ApiData[AgentTaskInspectorRead],
)
def get_agent_conversation_task(
    conversation_id: str,
    task_id: str,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> ApiData[AgentTaskInspectorRead]:
    conversation = load_owned_conversation(db, conversation_id, user)
    task = db.scalar(
        select(GenerationTask)
        .join(AgentRun, AgentRun.task_id == GenerationTask.id)
        .where(
            AgentRun.conversation_id == conversation.id,
            GenerationTask.id == task_id,
            GenerationTask.owner_user_id == conversation.owner_user_id,
        )
        .options(
            selectinload(GenerationTask.panels)
            .selectinload(TaskPanel.generated_images)
            .selectinload(GeneratedImage.asset)
        )
        .limit(1)
    )
    if task is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent 会话任务不存在")
    return ApiData(
        data=task_inspector_to_read(
            conversation.id,
            task,
            current_user_id=user.id,
            inspections=inspection_events_for_conversation(db, conversation.id),
        )
    )


@router.post(
    "/conversations/{conversation_id}/tasks/{task_id}/panels/{panel_id}/regenerations",
    response_model=ApiData[AgentRunRead],
    status_code=status.HTTP_202_ACCEPTED,
)
def regenerate_agent_panel(
    conversation_id: str,
    task_id: str,
    panel_id: str,
    payload: AgentPanelRegenerationCreate,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> ApiData[AgentRunRead]:
    try:
        run = start_panel_regeneration(
            db,
            conversation_id=conversation_id,
            task_id=task_id,
            panel_id=panel_id,
            payload=payload,
            owner_user_id=user.id,
        )
    except AgentPanelVersionError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    return ApiData(data=run_to_read(db, run))


@router.post(
    "/conversations/{conversation_id}/tasks/{task_id}/panels/{panel_id}/versions/{image_id}/accept",
    response_model=ApiData[AgentTaskInspectorImageRead],
)
def accept_agent_image_version(
    conversation_id: str,
    task_id: str,
    panel_id: str,
    image_id: str,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> ApiData[AgentTaskInspectorImageRead]:
    try:
        image = accept_image_version(
            db,
            conversation_id=conversation_id,
            task_id=task_id,
            panel_id=panel_id,
            image_id=image_id,
            owner_user_id=user.id,
        )
    except AgentPanelVersionError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    return ApiData(
        data=task_inspector_image_to_read(image, current_user_id=user.id)
    )


@router.post(
    "/conversations/{conversation_id}/tasks/{task_id}/panels/{panel_id}/versions/{image_id}/restore",
    response_model=ApiData[AgentTaskInspectorImageRead],
)
def restore_agent_image_version(
    conversation_id: str,
    task_id: str,
    panel_id: str,
    image_id: str,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> ApiData[AgentTaskInspectorImageRead]:
    try:
        image = restore_image_version(
            db,
            conversation_id=conversation_id,
            task_id=task_id,
            panel_id=panel_id,
            image_id=image_id,
            owner_user_id=user.id,
        )
    except AgentPanelVersionError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    return ApiData(
        data=task_inspector_image_to_read(image, current_user_id=user.id)
    )


@router.post(
    "/conversations/{conversation_id}/messages",
    response_model=ApiData[AgentTurnAcceptedRead],
    status_code=status.HTTP_202_ACCEPTED,
)
async def create_agent_message(
    conversation_id: str,
    payload: AgentMessageCreate,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> ApiData[AgentTurnAcceptedRead]:
    conversation = load_owned_conversation(db, conversation_id, user)
    if conversation.status != AgentConversationStatus.active:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="已归档的 Agent 会话不能发送消息")
    latest = db.scalar(
        select(AgentMessage)
        .where(AgentMessage.conversation_id == conversation.id)
        .order_by(AgentMessage.sequence.desc())
        .limit(1)
    )
    if latest is not None and latest.role == AgentMessageRole.user:
        pending_run = db.scalar(
            select(AgentRun).where(
                AgentRun.conversation_id == conversation.id,
                AgentRun.turn_id == latest.turn_id,
                AgentRun.status.not_in(
                    [AgentRunStatus.succeeded, AgentRunStatus.failed, AgentRunStatus.cancelled]
                ),
            )
        )
        if pending_run is not None:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="当前会话上一轮仍在运行")

    try:
        resolved_resources = AgentResourceResolver().resolve(
            db,
            owner_user_id=user.id,
            refs=payload.resource_refs,
        )
    except AgentResourceResolutionError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    payload = payload.model_copy(
        update={"resource_refs": resolved_resources.refs}
    )

    turn_id = new_id()
    message = AgentMessage(
        conversation_id=conversation.id,
        turn_id=turn_id,
        role=AgentMessageRole.user,
        content=payload.content,
        resource_refs_json=(
            json.dumps([item.model_dump(mode="json") for item in payload.resource_refs], ensure_ascii=False)
            if payload.resource_refs
            else None
        ),
        sequence=(latest.sequence + 1) if latest is not None else 1,
    )
    run = AgentRun(
        conversation_id=conversation.id,
        turn_id=turn_id,
        status=AgentRunStatus.queued,
        skill_version_id=(
            resolved_resources.skill_version.id
            if resolved_resources.skill_version is not None
            else None
        ),
    )
    conversation.last_message_at = datetime.utcnow()
    db.add_all([message, run])
    db.commit()
    db.refresh(message)
    db.refresh(run)
    await enqueue_agent_run(run.id)
    return ApiData(
        data=AgentTurnAcceptedRead(
            message=message_to_read(message),
            run=run_to_read(db, run),
        )
    )


@router.get("/runs/{run_id}", response_model=ApiData[AgentRunRead])
def get_agent_run(
    run_id: str,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> ApiData[AgentRunRead]:
    run = db.scalar(
        select(AgentRun)
        .join(AgentConversation, AgentConversation.id == AgentRun.conversation_id)
        .where(AgentRun.id == run_id, AgentConversation.owner_user_id == user.id)
    )
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent Run 不存在")
    return ApiData(data=run_to_read(db, run))


def _load_owned_run(db: Session, run_id: str, user_id: str) -> AgentRun:
    run = db.scalar(
        select(AgentRun)
        .join(AgentConversation, AgentConversation.id == AgentRun.conversation_id)
        .where(
            AgentRun.id == run_id,
            AgentConversation.owner_user_id == user_id,
        )
    )
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent Run 不存在")
    return run


@router.post("/runs/{run_id}/pause", response_model=ApiData[AgentRunRead])
def pause_agent_run(
    run_id: str,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> ApiData[AgentRunRead]:
    run = _load_owned_run(db, run_id, user.id)
    if run.status == AgentRunStatus.paused:
        return ApiData(data=run_to_read(db, run))
    if run.status in {
        AgentRunStatus.succeeded,
        AgentRunStatus.failed,
        AgentRunStatus.cancelled,
        AgentRunStatus.waiting_for_input,
    }:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="当前 Agent Run 不能暂停")
    run.status = AgentRunStatus.paused
    emit_agent_event(
        db,
        run=run,
        event_type=AgentEventType.run_paused,
        payload={
            "status": "paused",
            "message": "已暂停后续 Agent 步骤；已提交图片 Provider 的请求仍可能完成并保存。",
        },
        deduplicate=True,
    )
    db.commit()
    db.refresh(run)
    return ApiData(data=run_to_read(db, run))


@router.post("/runs/{run_id}/resume", response_model=ApiData[AgentRunRead])
async def resume_agent_run(
    run_id: str,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> ApiData[AgentRunRead]:
    run = _load_owned_run(db, run_id, user.id)
    if run.status in {
        AgentRunStatus.succeeded,
        AgentRunStatus.failed,
        AgentRunStatus.cancelled,
        AgentRunStatus.waiting_for_input,
    }:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="当前 Agent Run 不能继续")
    should_enqueue = run.status == AgentRunStatus.paused
    if should_enqueue:
        run.status = AgentRunStatus.queued
        emit_agent_event(
            db,
            run=run,
            event_type=AgentEventType.run_resumed,
            payload={"status": "queued"},
        )
        db.commit()
        await enqueue_agent_run(run.id)
        db.refresh(run)
    return ApiData(data=run_to_read(db, run))


@router.get(
    "/conversations/{conversation_id}/artifacts",
    response_model=ApiList[AgentArtifactRead],
)
def list_agent_artifacts(
    conversation_id: str,
    limit: int = Query(default=50, ge=1, le=100),
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> ApiList[AgentArtifactRead]:
    load_owned_conversation(db, conversation_id, user)
    artifacts = db.scalars(
        select(AgentArtifact)
        .where(AgentArtifact.conversation_id == conversation_id)
        .options(selectinload(AgentArtifact.approval_request))
        .order_by(AgentArtifact.created_at.asc(), AgentArtifact.version.asc())
        .limit(limit + 1)
    ).all()
    visible = artifacts[:limit]
    return ApiList(
        items=[artifact_to_read(artifact) for artifact in visible],
        page=build_page(limit=limit, offset=0, item_count=len(artifacts)),
    )


@router.post(
    "/approvals/{approval_id}/decisions",
    response_model=ApiData[AgentApprovalRead],
)
async def submit_agent_approval_decision(
    approval_id: str,
    payload: AgentApprovalDecision,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> ApiData[AgentApprovalRead]:
    approval = db.scalar(
        select(AgentApprovalRequest)
        .join(AgentConversation, AgentConversation.id == AgentApprovalRequest.conversation_id)
        .where(
            AgentApprovalRequest.id == approval_id,
            AgentConversation.owner_user_id == user.id,
        )
        .options(
            selectinload(AgentApprovalRequest.artifact),
            selectinload(AgentApprovalRequest.run),
        )
    )
    if approval is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="方案确认请求不存在")
    was_pending = approval.status.value == "pending"
    try:
        decided = decide_approval(
            db,
            approval=approval,
            user_id=user.id,
            decision=payload.decision,
            feedback=payload.feedback,
        )
    except AgentApprovalError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    if was_pending:
        await enqueue_agent_run(decided.run_id)
    return ApiData(data=approval_to_read(decided))


@router.get("/conversations/{conversation_id}/events")
async def stream_agent_events(
    conversation_id: str,
    request: Request,
    after: str | None = Query(default=None, max_length=32),
    last_event_id: str | None = Header(default=None, alias="Last-Event-ID"),
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> StreamingResponse:
    load_owned_conversation(db, conversation_id, user)
    cursor_id = after or last_event_id
    if cursor_id is not None:
        cursor = db.scalar(
            select(AgentEvent).where(
                AgentEvent.id == cursor_id,
                AgentEvent.conversation_id == conversation_id,
            )
        )
        if cursor is None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="事件 cursor 无效")

    async def event_stream():
        current_cursor = cursor_id
        while not await request.is_disconnected():
            with database.SessionLocal() as event_db:
                statement = select(AgentEvent).where(
                    AgentEvent.conversation_id == conversation_id
                )
                if current_cursor is None:
                    events = list(
                        reversed(
                            event_db.scalars(
                                statement.order_by(
                                    AgentEvent.created_at.desc(),
                                    AgentEvent.id.desc(),
                                ).limit(100)
                            ).all()
                        )
                    )
                else:
                    current = event_db.get(AgentEvent, current_cursor)
                    if current is None or current.conversation_id != conversation_id:
                        return
                    statement = statement.where(
                        or_(
                            AgentEvent.created_at > current.created_at,
                            and_(
                                AgentEvent.created_at == current.created_at,
                                AgentEvent.id > current.id,
                            ),
                        )
                    )
                    events = event_db.scalars(
                        statement.order_by(
                            AgentEvent.created_at.asc(),
                            AgentEvent.id.asc(),
                        ).limit(100)
                    ).all()
                frames = [
                    (
                        f"id: {event.id}\n"
                        f"event: {event.event_type.value}\n"
                        f"data: {json.dumps({'run_id': event.run_id, 'sequence': event.sequence, 'payload': json.loads(event.public_payload_json), 'created_at': event.created_at.isoformat()}, ensure_ascii=False)}\n\n"
                    )
                    for event in events
                ]
                if events:
                    current_cursor = events[-1].id
            if frames:
                for frame in frames:
                    yield frame
                continue
            yield ": heartbeat\n\n"
            await asyncio.sleep(10)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
