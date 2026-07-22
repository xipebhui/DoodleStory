from __future__ import annotations

from datetime import datetime
import json

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import current_user
from app.api.pagination import Pagination, build_page, get_pagination
from app.core.database import get_db
from app.models.entities import AgentConversation, AgentMessage, AgentRun, AgentStep, User, new_id
from app.models.enums import AgentConversationStatus, AgentMessageRole, AgentRunStatus
from app.schemas.agent import (
    AgentConversationCreate,
    AgentConversationDetailRead,
    AgentConversationRead,
    AgentMessageCreate,
    AgentMessageRead,
    AgentResourceRef,
    AgentRunRead,
    AgentStepRead,
    AgentTurnAcceptedRead,
)
from app.schemas.common import ApiData, ApiList
from app.services.agent_runner import enqueue_agent_run


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
    return ApiData(
        data=AgentConversationDetailRead(
            **AgentConversationRead.model_validate(conversation).model_dump(),
            messages=[message_to_read(message) for message in visible],
            message_page=build_page(message_limit, message_cursor, len(messages)),
        )
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
