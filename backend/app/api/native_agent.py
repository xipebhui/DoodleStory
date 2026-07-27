from __future__ import annotations

import asyncio
from datetime import datetime
import json

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import StreamingResponse
from sqlalchemy import or_, select
from sqlalchemy.orm import Session, selectinload

from app.api.deps import current_user
from app.api.pagination import build_page
from app.core.config import get_settings
from app.core.database import SessionLocal, get_db
from app.models.entities import (
    AgentSkill,
    AgentSkillVersion,
    NativeAgentConversation,
    NativeAgentEvent,
    NativeAgentImage,
    NativeAgentItem,
    NativeAgentRun,
    NativeAgentStep,
    Style,
    StyleReferenceImage,
    User,
)
from app.models.enums import (
    AgentRunStatus,
    AgentSkillStatus,
    NativeAgentItemType,
    StyleReferenceMode,
    StyleStatus,
)
from app.schemas.common import ApiData, ApiList
from app.schemas.agent import AgentResourceKind, AgentResourceOption
from app.schemas.native_agent import (
    NativeAgentCapabilityRead,
    NativeAgentConversationCreate,
    NativeAgentConversationDetailRead,
    NativeAgentConversationRead,
    NativeAgentEventRead,
    NativeAgentImageRead,
    NativeAgentItemRead,
    NativeAgentRunCreate,
    NativeAgentRunRead,
    NativeAgentStepRead,
)
from app.services.native_agent_worker import enqueue_native_agent_run


router = APIRouter(prefix="/agent-loop", tags=["native-agent-loop"])


def _load_owned_conversation(
    db: Session,
    *,
    conversation_id: str,
    owner_user_id: str,
) -> NativeAgentConversation:
    conversation = db.scalar(
        select(NativeAgentConversation).where(
            NativeAgentConversation.id == conversation_id,
            NativeAgentConversation.owner_user_id == owner_user_id,
        )
    )
    if conversation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="最小 Agent 会话不存在",
        )
    return conversation


def _item_to_read(item: NativeAgentItem) -> NativeAgentItemRead:
    return NativeAgentItemRead(
        id=item.id,
        sequence=item.sequence,
        item_type=item.item_type,
        payload=json.loads(item.payload_json),
        created_at=item.created_at,
    )


def _image_to_read(image: NativeAgentImage) -> NativeAgentImageRead:
    return NativeAgentImageRead(
        id=image.id,
        asset_id=image.asset_id,
        prompt=image.prompt,
        image_model=image.image_model_snapshot,
        aspect_ratio=image.aspect_ratio_snapshot,
        width=image.asset.width,
        height=image.asset.height,
        created_at=image.created_at,
    )


def _step_to_read(step: NativeAgentStep) -> NativeAgentStepRead:
    return NativeAgentStepRead(
        id=step.id,
        sequence=step.sequence,
        step_type=step.step_type,
        status=step.status,
        name=step.name,
        tool_call_id=step.tool_call_id,
        attempts=step.attempts,
        started_at=step.started_at,
        finished_at=step.finished_at,
        error_code=step.error_code,
        error_message=step.error_message,
    )


def _event_to_read(event: NativeAgentEvent) -> NativeAgentEventRead:
    return NativeAgentEventRead(
        id=event.id,
        sequence=event.sequence,
        event_type=event.event_type,
        payload=json.loads(event.payload_json),
        created_at=event.created_at,
    )


def _run_to_read(run: NativeAgentRun) -> NativeAgentRunRead:
    return NativeAgentRunRead(
        id=run.id,
        conversation_id=run.conversation_id,
        skill_version_id=run.skill_version_id,
        skill_name=run.skill_name_snapshot,
        skill_version=run.skill_version_snapshot,
        style_id=run.style_id,
        style_name=run.style_name_snapshot,
        status=run.status,
        model=run.model_snapshot,
        model_call_count=run.model_call_count,
        image_call_count=run.image_call_count,
        final_output=run.final_output,
        error_code=run.error_code,
        error_message=run.error_message,
        items=[_item_to_read(item) for item in sorted(run.items, key=lambda value: value.sequence)],
        images=[_image_to_read(image) for image in sorted(run.images, key=lambda value: value.created_at)],
        steps=[
            _step_to_read(step)
            for step in sorted(run.steps, key=lambda value: value.sequence)
        ],
        events=[
            _event_to_read(event)
            for event in sorted(run.events, key=lambda value: value.sequence)
        ],
        started_at=run.started_at,
        finished_at=run.finished_at,
        created_at=run.created_at,
        updated_at=run.updated_at,
    )


def _load_run_for_read(db: Session, run_id: str) -> NativeAgentRun:
    run = db.scalar(
        select(NativeAgentRun)
        .where(NativeAgentRun.id == run_id)
        .options(
            selectinload(NativeAgentRun.items),
            selectinload(NativeAgentRun.images).selectinload(NativeAgentImage.asset),
            selectinload(NativeAgentRun.steps),
            selectinload(NativeAgentRun.events),
        )
    )
    if run is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="最小 Agent Run 不存在",
        )
    return run


def _reference_urls(style: Style) -> list[str]:
    if style.style_reference_mode != StyleReferenceMode.image:
        return []
    urls: list[str] = []
    for reference in sorted(style.reference_images, key=lambda item: item.display_order):
        if not reference.asset.public_url:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="当前 Style 使用参考图模式，但参考图没有 Provider 可访问的公网 URL",
            )
        urls.append(reference.asset.public_url)
    if not urls:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="当前 Style 使用参考图模式，但没有可用参考图",
        )
    return urls


@router.get("/capabilities", response_model=ApiData[NativeAgentCapabilityRead])
def get_native_agent_capabilities(
    user: User = Depends(current_user),
) -> ApiData[NativeAgentCapabilityRead]:
    del user
    return ApiData(
        data=NativeAgentCapabilityRead(
            loop="agents_sdk",
            tools=["generate_image"],
            image_review="native_model_vision",
        )
    )


@router.get("/skills", response_model=ApiList[AgentResourceOption])
def list_native_agent_skills(
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> ApiList[AgentResourceOption]:
    rows = db.execute(
        select(AgentSkill, AgentSkillVersion)
        .join(AgentSkillVersion, AgentSkillVersion.id == AgentSkill.active_version_id)
        .where(
            AgentSkill.status == AgentSkillStatus.published,
            or_(
                AgentSkill.owner_user_id == user.id,
                AgentSkill.owner_user_id.is_(None),
            ),
        )
        .order_by(AgentSkill.owner_user_id.is_not(None), AgentSkill.updated_at.desc())
        .limit(51)
    ).all()
    eligible = rows[:50]
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
            for skill, version in eligible
        ],
        page=build_page(limit=50, offset=0, item_count=len(eligible)),
    )


@router.get("/styles", response_model=ApiList[AgentResourceOption])
def list_native_agent_styles(
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> ApiList[AgentResourceOption]:
    del user
    styles = db.scalars(
        select(Style)
        .where(
            Style.status == StyleStatus.active,
            Style.deleted_at.is_(None),
        )
        .order_by(Style.updated_at.desc(), Style.id.desc())
        .limit(51)
    ).all()
    visible = styles[:50]
    return ApiList(
        items=[
            AgentResourceOption(
                kind=AgentResourceKind.style,
                id=style.id,
                display_name=style.name,
                secondary_text=f"{style.aspect_ratio} · {style.image_model_name}",
                status=style.status.value,
            )
            for style in visible
        ],
        page=build_page(limit=50, offset=0, item_count=len(styles)),
    )


@router.post(
    "/conversations",
    response_model=ApiData[NativeAgentConversationRead],
    status_code=status.HTTP_201_CREATED,
)
def create_native_agent_conversation(
    payload: NativeAgentConversationCreate,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> ApiData[NativeAgentConversationRead]:
    conversation = NativeAgentConversation(
        owner_user_id=user.id,
        title=payload.title,
    )
    db.add(conversation)
    db.commit()
    db.refresh(conversation)
    return ApiData(data=NativeAgentConversationRead.model_validate(conversation))


@router.get(
    "/conversations",
    response_model=ApiList[NativeAgentConversationRead],
)
def list_native_agent_conversations(
    limit: int = Query(default=30, ge=1, le=100),
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> ApiList[NativeAgentConversationRead]:
    conversations = db.scalars(
        select(NativeAgentConversation)
        .where(NativeAgentConversation.owner_user_id == user.id)
        .order_by(
            NativeAgentConversation.last_message_at.desc(),
            NativeAgentConversation.id.desc(),
        )
        .limit(limit + 1)
    ).all()
    visible = conversations[:limit]
    return ApiList(
        items=[
            NativeAgentConversationRead.model_validate(conversation)
            for conversation in visible
        ],
        page=build_page(
            limit=limit,
            offset=0,
            item_count=len(conversations),
        ),
    )


@router.get(
    "/conversations/{conversation_id}",
    response_model=ApiData[NativeAgentConversationDetailRead],
)
def get_native_agent_conversation(
    conversation_id: str,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> ApiData[NativeAgentConversationDetailRead]:
    conversation = _load_owned_conversation(
        db,
        conversation_id=conversation_id,
        owner_user_id=user.id,
    )
    runs = db.scalars(
        select(NativeAgentRun)
        .where(NativeAgentRun.conversation_id == conversation.id)
        .options(
            selectinload(NativeAgentRun.items),
            selectinload(NativeAgentRun.images).selectinload(NativeAgentImage.asset),
            selectinload(NativeAgentRun.steps),
            selectinload(NativeAgentRun.events),
        )
        .order_by(NativeAgentRun.created_at.asc())
        .limit(50)
    ).all()
    return ApiData(
        data=NativeAgentConversationDetailRead(
            **NativeAgentConversationRead.model_validate(conversation).model_dump(),
            runs=[_run_to_read(run) for run in runs],
        )
    )


@router.post(
    "/conversations/{conversation_id}/runs",
    response_model=ApiData[NativeAgentRunRead],
    status_code=status.HTTP_202_ACCEPTED,
)
async def create_native_agent_run(
    conversation_id: str,
    payload: NativeAgentRunCreate,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> ApiData[NativeAgentRunRead]:
    conversation = _load_owned_conversation(
        db,
        conversation_id=conversation_id,
        owner_user_id=user.id,
    )
    active_run = db.scalar(
        select(NativeAgentRun).where(
            NativeAgentRun.conversation_id == conversation.id,
            NativeAgentRun.status.in_(
                [
                    AgentRunStatus.queued,
                    AgentRunStatus.running,
                    AgentRunStatus.waiting_for_tool,
                ]
            ),
        )
    )
    if active_run is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="当前最小 Agent 会话仍有一轮正在运行",
        )

    skill_version = db.scalar(
        select(AgentSkillVersion)
        .join(AgentSkill, AgentSkill.id == AgentSkillVersion.skill_id)
        .where(
            AgentSkillVersion.id == payload.skill_version_id,
            AgentSkill.active_version_id == AgentSkillVersion.id,
            AgentSkill.status == AgentSkillStatus.published,
            or_(
                AgentSkill.owner_user_id == user.id,
                AgentSkill.owner_user_id.is_(None),
            ),
        )
    )
    if skill_version is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="发布版 Skill 不存在或不可用",
        )
    style = None
    reference_urls: list[str] = []
    if payload.style_id is not None:
        style = db.scalar(
            select(Style)
            .where(
                Style.id == payload.style_id,
                Style.status == StyleStatus.active,
                Style.deleted_at.is_(None),
            )
            .options(
                selectinload(Style.reference_images).selectinload(
                    StyleReferenceImage.asset
                )
            )
        )
        if style is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Style 不存在或未启用",
            )
        reference_urls = _reference_urls(style)

    settings = get_settings()
    run = NativeAgentRun(
        conversation_id=conversation.id,
        skill_version_id=skill_version.id,
        style_id=style.id if style is not None else None,
        status=AgentRunStatus.queued,
        model_snapshot=settings.agent_model.strip(),
        skill_name_snapshot=skill_version.name_snapshot,
        skill_version_snapshot=skill_version.version,
        skill_content_hash_snapshot=skill_version.content_hash,
        style_name_snapshot=style.name if style is not None else None,
        style_prompt_snapshot=style.style_prompt if style is not None else None,
        image_model_snapshot=style.image_model_name if style is not None else None,
        aspect_ratio_snapshot=style.aspect_ratio if style is not None else None,
        style_reference_urls_json=json.dumps(reference_urls, ensure_ascii=False),
    )
    db.add(run)
    db.flush()
    db.add(
        NativeAgentItem(
            run_id=run.id,
            sequence=1,
            item_type=NativeAgentItemType.user_input,
            payload_json=json.dumps(
                {"content": payload.content},
                ensure_ascii=False,
                separators=(",", ":"),
            ),
        )
    )
    db.add(
        NativeAgentEvent(
            run_id=run.id,
            sequence=1,
            event_type="run.created",
            payload_json=json.dumps(
                {"status": AgentRunStatus.queued.value},
                ensure_ascii=False,
                separators=(",", ":"),
            ),
        )
    )
    conversation.last_message_at = datetime.utcnow()
    db.commit()

    await enqueue_native_agent_run(run.id)
    return ApiData(data=_run_to_read(_load_run_for_read(db, run.id)))


@router.get("/runs/{run_id}/events")
async def stream_native_agent_run_events(
    run_id: str,
    request: Request,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
    after: int | None = Query(default=None, ge=0),
) -> StreamingResponse:
    owned_run = db.scalar(
        select(NativeAgentRun)
        .join(
            NativeAgentConversation,
            NativeAgentConversation.id == NativeAgentRun.conversation_id,
        )
        .where(
            NativeAgentRun.id == run_id,
            NativeAgentConversation.owner_user_id == user.id,
        )
    )
    if owned_run is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="最小 Agent Run 不存在",
        )

    headers = getattr(request, "headers", {})
    header_cursor = headers.get("last-event-id") if headers else None
    requested_cursor = after if isinstance(after, int) else None
    try:
        current_cursor = (
            requested_cursor
            if requested_cursor is not None
            else int(header_cursor or 0)
        )
    except ValueError:
        current_cursor = 0

    async def event_stream():
        nonlocal current_cursor
        heartbeat_ticks = 0
        sent_snapshot = False
        while not await request.is_disconnected():
            with SessionLocal() as event_db:
                events = event_db.scalars(
                    select(NativeAgentEvent)
                    .where(
                        NativeAgentEvent.run_id == run_id,
                        NativeAgentEvent.sequence > current_cursor,
                    )
                    .order_by(NativeAgentEvent.sequence.asc())
                    .limit(100)
                ).all()
                run = _load_run_for_read(event_db, run_id)
                run_read = _run_to_read(run)
                snapshot = json.dumps(
                    run_read.model_dump(mode="json"),
                    ensure_ascii=False,
                    separators=(",", ":"),
                )
                terminal = run.status in {
                    AgentRunStatus.succeeded,
                    AgentRunStatus.failed,
                    AgentRunStatus.cancelled,
                }
            if events:
                for event in events:
                    event_payload = json.dumps(
                        _event_to_read(event).model_dump(mode="json"),
                        ensure_ascii=False,
                        separators=(",", ":"),
                    )
                    yield (
                        f"id: {event.sequence}\n"
                        f"event: native.event\n"
                        f"data: {event_payload}\n\n"
                    )
                    current_cursor = event.sequence
                yield f"event: run.updated\ndata: {snapshot}\n\n"
                sent_snapshot = True
                heartbeat_ticks = 0
            elif not sent_snapshot:
                yield f"event: run.updated\ndata: {snapshot}\n\n"
                sent_snapshot = True
            if terminal and not events:
                return
            if not events:
                heartbeat_ticks += 1
                if heartbeat_ticks >= 24:
                    yield ": heartbeat\n\n"
                    heartbeat_ticks = 0
            else:
                heartbeat_ticks = 0
            await asyncio.sleep(0.25)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
