from __future__ import annotations

from datetime import datetime
import json

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.api.deps import current_user
from app.api.pagination import Pagination, build_page, get_pagination
from app.core.database import get_db
from app.models.entities import (
    AgentConversation,
    AgentMessage,
    AgentRun,
    AgentStep,
    GeneratedImage,
    GenerationTask,
    TaskPanel,
    User,
    new_id,
)
from app.models.enums import AgentConversationStatus, AgentMessageRole, AgentRunStatus
from app.schemas.agent import (
    AgentConversationCreate,
    AgentConversationDetailRead,
    AgentConversationRead,
    AgentMessageCreate,
    AgentMessageRead,
    AgentResourceRef,
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
from app.services.agent_comic_creation import AgentComicCreationError, load_authorized_style


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
    if raw is None:
        return []
    try:
        value = json.loads(raw)
        return [AgentResourceRef.model_validate(item) for item in value]
    except (json.JSONDecodeError, TypeError, ValueError) as exc:
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


def task_inspector_image_to_read(image: GeneratedImage) -> AgentTaskInspectorImageRead:
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
        progress_current=task.progress_current,
        progress_total=task.progress_total,
        error_code=task.error_code,
        error_message=task.error_message,
        panels=panels,
    )


def task_inspector_to_read(
    conversation_id: str,
    task: GenerationTask,
) -> AgentTaskInspectorRead:
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
                    task_inspector_image_to_read(current_image)
                    if current_image is not None
                    else None
                ),
                versions=[task_inspector_image_to_read(image) for image in versions],
            )
        )
    return AgentTaskInspectorRead(
        conversation_id=conversation_id,
        task_id=task.id,
        title=task.display_title,
        status=task.status,
        progress_current=task.progress_current,
        progress_total=task.progress_total,
        error_code=task.error_code,
        error_message=task.error_message,
        panels=panels,
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
    return ApiData(
        data=AgentConversationDetailRead(
            **AgentConversationRead.model_validate(conversation).model_dump(),
            messages=[message_to_read(message) for message in visible],
            message_page=build_page(message_limit, message_cursor, len(messages)),
            task_cards=[task_card_to_read(run) for run in task_runs],
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
    return ApiData(data=task_inspector_to_read(conversation.id, task))


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

    style_refs = [item for item in payload.resource_refs if item.kind.value == "style"]
    if payload.resource_refs:
        if len(payload.resource_refs) != 1 or len(style_refs) != 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Sprint 106 每条漫画创建消息必须且只能选择一个风格",
            )
        try:
            style = load_authorized_style(db, style_refs[0].id)
        except AgentComicCreationError as exc:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
        payload = payload.model_copy(
            update={
                "resource_refs": [
                    style_refs[0].model_copy(update={"display_name": style.name})
                ]
            }
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
