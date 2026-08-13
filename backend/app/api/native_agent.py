from __future__ import annotations

import asyncio
from datetime import datetime
import json

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import StreamingResponse
from sqlalchemy import func, or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.api.deps import current_user
from app.api.pagination import build_page
from app.core.config import get_settings
from app.core.database import SessionLocal, get_db
from app.models.entities import (
    AgentSkill,
    AgentSkillVersion,
    DurableAgentGate,
    DurableAgentImageQuality,
    DurableAgentMediaBinding,
    DurableAgentTask,
    DurableAgentPlanRevision,
    DurableAgentWorkflow,
    NativeAgentAudio,
    NativeAgentArticleApproval,
    NativeAgentArtifact,
    NativeAgentConversation,
    NativeAgentContextItem,
    NativeAgentEvent,
    NativeAgentExternalContent,
    NativeAgentImage,
    NativeAgentItem,
    NativeAgentRun,
    NativeAgentStep,
    NativeAgentSubtitle,
    NativeAgentVideo,
    PublishableVideo,
    Style,
    StyleReferenceImage,
    User,
    YoutubeChannel,
)
from app.models.enums import (
    AgentRunStatus,
    AgentSkillStatus,
    NativeAgentItemType,
    NativeAgentStepStatus,
    NativeAgentStepType,
    StyleReferenceMode,
    StyleStatus,
    UserRole,
)
from app.schemas.common import ApiData, ApiList, normalize_api_datetimes
from app.schemas.agent import AgentResourceKind, AgentResourceOption
from app.schemas.native_agent import (
    DurableControlCommandCreate,
    DurableControlCommandRead,
    DurableControlStateRead,
    NativeAgentCapabilityRead,
    NativeAgentAudioRead,
    NativeAgentArticleApprovalDecision,
    NativeAgentArticleApprovalRead,
    NativeAgentArtifactRead,
    NativeAgentConversationCreate,
    NativeAgentConversationDetailRead,
    NativeAgentConversationRead,
    NativeAgentEventRead,
    NativeAgentExternalContentRead,
    NativeAgentImageRead,
    NativeAgentItemRead,
    NativeAgentRunCreate,
    NativeAgentFollowUpCreate,
    NativeAgentRunRead,
    NativeAgentStepRead,
    NativeAgentSubtitleRead,
    NativeAgentVideoRead,
    DurableGateDecision,
    DurableImageQualityDecision,
    DurablePanelRerunRequest,
    DurableVisualPlanCreate,
)
from app.services.native_agent_worker import (
    cancel_native_agent_run,
    enqueue_native_agent_run,
)
from app.services.agent_skill_management import parse_tool_names
from app.services.native_agent_persistence import (
    NativeAgentStore,
    add_native_agent_event,
)
from app.services.agent_control_commands import (
    AgentControlCommandError,
    durable_control_state,
    execute_durable_control_command,
)
from app.services.native_article_workflow import (
    NativeArticleWorkflowError,
    decide_article_approval,
)
from app.services.durable_agent_runtime import (
    DurableAgentRuntimeError,
    initialize_workflow,
    open_image_quality_gate,
    record_image_quality,
    register_visual_plan,
    request_panel_rerun,
    mirror_native_article_approval,
    resolve_gate,
    workflow_for_native_run,
)
from app.services.account_creation_context import (
    AccountCreationContextError,
    build_account_creation_context_snapshot,
)
from app.services.native_agent_follow_up import (
    NativeAgentFollowUpError,
    create_follow_up_run,
    find_idempotent_follow_up,
)
from app.services.native_agent_model_routes import (
    SILICONFLOW_CHAT_ROUTE,
    NativeAgentModelRouteConfigError,
    resolve_native_agent_model_route,
)
from app.services.native_agent_route_capabilities import (
    NativeAgentRouteCapabilityError,
    validate_native_agent_route_capability,
)


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


def _load_owned_durable_workflow(
    db: Session,
    *,
    run_id: str,
    owner_user_id: str,
) -> tuple[NativeAgentRun, DurableAgentWorkflow]:
    run = db.scalar(
        select(NativeAgentRun)
        .join(
            NativeAgentConversation,
            NativeAgentConversation.id == NativeAgentRun.conversation_id,
        )
        .where(
            NativeAgentRun.id == run_id,
            NativeAgentConversation.owner_user_id == owner_user_id,
        )
    )
    if run is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Native Agent Run 不存在",
        )
    workflow = workflow_for_native_run(db, run.id)
    if workflow is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Native Agent Run 尚未初始化 Durable Workflow",
        )
    return run, workflow


def _load_owned_media_binding(
    db: Session,
    *,
    binding_id: str,
    owner_user_id: str,
) -> tuple[NativeAgentRun, DurableAgentMediaBinding]:
    binding = db.get(DurableAgentMediaBinding, binding_id)
    if binding is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Durable 图片绑定不存在",
        )
    workflow = db.get(DurableAgentWorkflow, binding.workflow_id)
    if workflow is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Durable Workflow 不存在",
        )
    run, _ = _load_owned_durable_workflow(
        db,
        run_id=workflow.native_run_id,
        owner_user_id=owner_user_id,
    )
    return run, binding


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
        provider=image.provider_snapshot,
        image_model=image.image_model_snapshot,
        aspect_ratio=image.aspect_ratio_snapshot,
        width=image.asset.width,
        height=image.asset.height,
        created_at=image.created_at,
    )


def _audio_to_read(audio: NativeAgentAudio) -> NativeAgentAudioRead:
    return NativeAgentAudioRead(
        id=audio.id,
        asset_id=audio.asset_id,
        text=audio.text,
        provider=audio.provider_snapshot,
        resource_id=audio.resource_id_snapshot,
        model=audio.model_snapshot,
        speaker=audio.speaker_snapshot,
        response_format=audio.response_format_snapshot,
        sample_rate=audio.sample_rate_snapshot,
        duration_ms=audio.duration_ms,
        speed=audio.speed_snapshot,
        speech_rate=audio.speech_rate_snapshot,
        created_at=audio.created_at,
    )


def _subtitle_to_read(subtitle: NativeAgentSubtitle) -> NativeAgentSubtitleRead:
    return NativeAgentSubtitleRead(
        id=subtitle.id,
        audio_id=subtitle.audio_id,
        asset_id=subtitle.asset_id,
        provider=subtitle.provider_snapshot,
        model=subtitle.model_snapshot,
        language=subtitle.language,
        text=subtitle.text,
        cues=json.loads(subtitle.cues_json),
        duration_ms=subtitle.duration_ms,
        created_at=subtitle.created_at,
    )


def _video_to_read(video: NativeAgentVideo) -> NativeAgentVideoRead:
    return NativeAgentVideoRead(
        id=video.id,
        asset_id=video.asset_id,
        bgm_asset_id=video.bgm_asset_id,
        template_id=video.template_id_snapshot,
        renderer_version=video.renderer_version_snapshot,
        scenes=json.loads(video.scenes_json),
        duration_ms=video.duration_ms,
        duration_in_frames=video.duration_in_frames,
        fps=video.fps,
        width=video.width,
        height=video.height,
        created_at=video.created_at,
    )


def _external_content_to_read(
    content: NativeAgentExternalContent,
) -> NativeAgentExternalContentRead:
    return NativeAgentExternalContentRead(
        id=content.id,
        content_asset_id=content.content_asset_id,
        platform=content.platform,
        content_type=content.content_type,
        source_url=content.source_url,
        resolved_url=content.resolved_url,
        source_content_id=content.source_content_id,
        title=content.title,
        description=content.description,
        author_name=content.author_name,
        publish_time=content.publish_time,
        publish_timestamp=content.publish_timestamp,
        tags=json.loads(content.tags_json),
        metrics=json.loads(content.metrics_json),
        excerpt=content.excerpt,
        created_at=content.created_at,
    )


def _step_to_read(step: NativeAgentStep) -> NativeAgentStepRead:
    return NativeAgentStepRead(
        id=step.id,
        sequence=step.sequence,
        step_type=step.step_type,
        status=step.status,
        name=step.name,
        tool_call_id=step.tool_call_id,
        model_call_id=step.model_call_id,
        model_provider=step.model_provider,
        model_api_shape=step.model_api_shape,
        model_name=step.model_name,
        provider_response_id=step.provider_response_id,
        execution_attempt=step.execution_attempt,
        model_call_ordinal=step.model_call_ordinal,
        converted_message_count=step.converted_message_count,
        latency_ms=step.latency_ms,
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


def _article_approval_to_read(
    approval: NativeAgentArticleApproval,
) -> NativeAgentArticleApprovalRead:
    return NativeAgentArticleApprovalRead(
        id=approval.id,
        status=approval.status,
        feedback=approval.feedback,
        requested_at=approval.requested_at,
        resolved_at=approval.resolved_at,
    )


def _artifact_to_read(
    artifact: NativeAgentArtifact,
) -> NativeAgentArtifactRead:
    return NativeAgentArtifactRead(
        id=artifact.id,
        artifact_type=artifact.artifact_type,
        schema_version=artifact.schema_version,
        version=artifact.version,
        status=artifact.status,
        producer_role=artifact.producer_role,
        content=json.loads(artifact.content_json),
        content_hash=artifact.content_hash,
        approval=(
            _article_approval_to_read(artifact.approval)
            if artifact.approval is not None
            else None
        ),
        created_at=artifact.created_at,
        updated_at=artifact.updated_at,
    )


def _run_to_read(run: NativeAgentRun) -> NativeAgentRunRead:
    return NativeAgentRunRead(
        id=run.id,
        conversation_id=run.conversation_id,
        parent_run_id=run.parent_run_id,
        continued_from_checkpoint_id=run.continued_from_checkpoint_id,
        skill_version_id=run.skill_version_id,
        skill_name=run.skill_name_snapshot,
        skill_version=run.skill_version_snapshot,
        style_id=run.style_id,
        style_name=run.style_name_snapshot,
        creation_channel_id=run.creation_channel_id,
        creation_channel_name=(
            (run.creation_channel.alias or run.creation_channel.title)
            if run.creation_channel is not None
            else None
        ),
        youtube_channel_id=run.youtube_channel_id,
        youtube_channel_name=(
            (run.youtube_channel.alias or run.youtube_channel.title)
            if run.youtube_channel is not None
            else None
        ),
        youtube_publishable_video_id=run.youtube_publishable_video_id,
        youtube_publishable_video_title=(
            run.youtube_publishable_video.title
            if run.youtube_publishable_video is not None
            else None
        ),
        youtube_publish_confirmation=(
            json.loads(run.youtube_publish_confirmation_json)
            if run.youtube_publish_confirmation_json
            else None
        ),
        status=run.status,
        model_route=run.model_route_snapshot,
        model_provider=run.model_provider_snapshot,
        model_api_shape=run.model_api_shape_snapshot,
        model=run.model_snapshot,
        model_call_count=run.model_call_count,
        image_call_count=run.image_call_count,
        speech_call_count=run.speech_call_count,
        subtitle_call_count=run.subtitle_call_count,
        video_call_count=run.video_call_count,
        workflow_phase=run.workflow_phase,
        workflow_revision=run.workflow_revision,
        workflow_checkpoint=(
            json.loads(run.workflow_checkpoint_json)
            if run.workflow_checkpoint_json
            else None
        ),
        final_output=run.final_output,
        error_code=run.error_code,
        error_message=run.error_message,
        items=[
            _item_to_read(item)
            for item in sorted(run.items, key=lambda value: value.sequence)
        ],
        images=[
            _image_to_read(image)
            for image in sorted(
                run.images,
                key=lambda value: value.created_at,
            )
        ],
        audios=[
            _audio_to_read(audio)
            for audio in sorted(
                run.audios,
                key=lambda value: value.created_at,
            )
        ],
        subtitles=[
            _subtitle_to_read(subtitle)
            for subtitle in sorted(
                run.subtitles,
                key=lambda value: value.created_at,
            )
        ],
        videos=[
            _video_to_read(video)
            for video in sorted(
                run.videos,
                key=lambda value: value.created_at,
            )
        ],
        external_contents=[
            _external_content_to_read(content)
            for content in sorted(
                run.external_contents,
                key=lambda value: value.created_at,
            )
        ],
        steps=[
            _step_to_read(step)
            for step in sorted(run.steps, key=lambda value: value.sequence)
        ],
        events=[
            _event_to_read(event)
            for event in sorted(run.events, key=lambda value: value.sequence)
        ],
        artifacts=[
            _artifact_to_read(artifact)
            for artifact in sorted(
                run.artifacts,
                key=lambda value: (
                    value.created_at,
                    value.artifact_type,
                    value.version,
                ),
            )
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
            selectinload(NativeAgentRun.audios).selectinload(NativeAgentAudio.asset),
            selectinload(NativeAgentRun.subtitles).selectinload(NativeAgentSubtitle.asset),
            selectinload(NativeAgentRun.videos).selectinload(NativeAgentVideo.asset),
            selectinload(NativeAgentRun.external_contents).selectinload(
                NativeAgentExternalContent.content_asset
            ),
            selectinload(NativeAgentRun.steps),
            selectinload(NativeAgentRun.events),
            selectinload(NativeAgentRun.artifacts).selectinload(
                NativeAgentArtifact.approval
            ),
            selectinload(NativeAgentRun.creation_channel),
            selectinload(NativeAgentRun.youtube_channel),
            selectinload(NativeAgentRun.youtube_publishable_video),
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
            tools=[
                "generate_image",
                "generate_speech",
                "generate_subtitles",
                "generate_video_clip",
                "render_story_video",
                "publish_youtube_video",
                "capture_wechat_article",
                "get_account_creation_context",
                "inspect_youtube_channel",
            ],
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
            selectinload(NativeAgentRun.audios).selectinload(NativeAgentAudio.asset),
            selectinload(NativeAgentRun.subtitles).selectinload(NativeAgentSubtitle.asset),
            selectinload(NativeAgentRun.videos).selectinload(NativeAgentVideo.asset),
            selectinload(NativeAgentRun.external_contents).selectinload(
                NativeAgentExternalContent.content_asset
            ),
            selectinload(NativeAgentRun.steps),
            selectinload(NativeAgentRun.events),
            selectinload(NativeAgentRun.artifacts).selectinload(
                NativeAgentArtifact.approval
            ),
            selectinload(NativeAgentRun.creation_channel),
            selectinload(NativeAgentRun.youtube_channel),
            selectinload(NativeAgentRun.youtube_publishable_video),
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
    if (
        payload.model_route == SILICONFLOW_CHAT_ROUTE
        and user.role != UserRole.admin
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="只有管理员可以显式选择 SiliconFlow Chat 路由",
        )
    active_run = db.scalar(
        select(NativeAgentRun).where(
            NativeAgentRun.conversation_id == conversation.id,
            NativeAgentRun.status.in_(
                [
                    AgentRunStatus.queued,
                    AgentRunStatus.running,
                    AgentRunStatus.waiting_for_tool,
                    AgentRunStatus.waiting_for_input,
                    AgentRunStatus.retrying,
                    AgentRunStatus.cancel_requested,
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
    selected_tool_names = set(parse_tool_names(skill_version.tool_names_json))
    if (
        payload.youtube_channel_id is not None
        and "publish_youtube_video" not in selected_tool_names
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="当前 Skill Version 未授权 publish_youtube_video",
        )
    creation_channel = None
    creation_channel_context_json = None
    style = None
    if payload.creation_channel_id is not None:
        if user.role != UserRole.admin:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="只有管理员可以在 Agent 中选择创作账号",
            )
        creation_channel = db.scalar(
            select(YoutubeChannel)
            .where(YoutubeChannel.id == payload.creation_channel_id)
            .options(
                selectinload(YoutubeChannel.default_style)
                .selectinload(Style.reference_images)
                .selectinload(StyleReferenceImage.asset)
            )
        )
        if creation_channel is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="创作账号不存在",
            )
        if creation_channel.default_style is None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="所选创作账号尚未绑定风格，请先前往账号管理完成绑定",
            )
        style = creation_channel.default_style
        if style.status != StyleStatus.active or style.deleted_at is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="所选创作账号绑定的风格当前不可用，请先更换账号风格",
            )
        if payload.style_id is not None and payload.style_id != style.id:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Style 与创作账号绑定风格不一致，不能在单次创作中覆盖账号风格",
            )
        try:
            creation_channel_context_json = json.dumps(
                build_account_creation_context_snapshot(
                    db,
                    channel=creation_channel,
                ),
                ensure_ascii=False,
                separators=(",", ":"),
            )
        except AccountCreationContextError as exc:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"创作账号 Context 无法读取：{exc}",
            ) from exc
    elif payload.style_id is not None:
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
    reference_urls = _reference_urls(style) if style is not None else []

    youtube_channel = None
    youtube_publishable_video = None
    if payload.youtube_channel_id is not None:
        if user.role != UserRole.admin:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="只有管理员可以在 Agent 中选择 YouTube 频道",
            )
        youtube_channel = db.get(YoutubeChannel, payload.youtube_channel_id)
        if youtube_channel is None or youtube_channel.remote_status != "normal":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="所选 YouTube 频道当前不可发布",
            )
        youtube_publishable_video = db.scalar(
            select(PublishableVideo).where(
                PublishableVideo.id == payload.youtube_publishable_video_id,
                PublishableVideo.owner_user_id == user.id,
            )
        )
        if (
            youtube_publishable_video is None
            or youtube_publishable_video.review_status != "approved"
        ):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="所选视频不存在或尚未审核通过",
            )

    settings = get_settings()
    try:
        model_route = resolve_native_agent_model_route(
            settings,
            requested_route=payload.model_route,
        )
    except NativeAgentModelRouteConfigError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    try:
        validate_native_agent_route_capability(
            model_route,
            selected_tool_names=selected_tool_names,
            style_id=style.id if style is not None else None,
            creation_channel_id=payload.creation_channel_id,
            youtube_channel_id=payload.youtube_channel_id,
            youtube_publishable_video_id=payload.youtube_publishable_video_id,
            has_youtube_publish_confirmation=(
                payload.youtube_publish_confirmation is not None
            ),
        )
    except NativeAgentRouteCapabilityError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    run = NativeAgentRun(
        conversation_id=conversation.id,
        skill_version_id=skill_version.id,
        style_id=style.id if style is not None else None,
        status=AgentRunStatus.queued,
        model_snapshot=model_route.model,
        model_route_snapshot=model_route.route,
        model_provider_snapshot=model_route.provider,
        model_api_shape_snapshot=model_route.api_shape,
        skill_name_snapshot=skill_version.name_snapshot,
        skill_version_snapshot=skill_version.version,
        skill_content_hash_snapshot=skill_version.content_hash,
        style_name_snapshot=style.name if style is not None else None,
        style_prompt_snapshot=style.style_prompt if style is not None else None,
        image_model_snapshot=style.image_model_name if style is not None else None,
        aspect_ratio_snapshot=style.aspect_ratio if style is not None else None,
        style_reference_urls_json=json.dumps(reference_urls, ensure_ascii=False),
        creation_channel_id=(
            creation_channel.id if creation_channel is not None else None
        ),
        creation_channel_context_json=creation_channel_context_json,
        youtube_channel_id=(
            youtube_channel.id if youtube_channel is not None else None
        ),
        youtube_publishable_video_id=(
            youtube_publishable_video.id
            if youtube_publishable_video is not None
            else None
        ),
        youtube_publish_confirmation_json=(
            json.dumps(
                payload.youtube_publish_confirmation.model_dump(mode="json"),
                ensure_ascii=False,
                separators=(",", ":"),
            )
            if payload.youtube_publish_confirmation is not None
            else None
        ),
        youtube_publish_confirmed_at=(
            datetime.utcnow()
            if payload.youtube_publish_confirmation is not None
            else None
        ),
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
    add_native_agent_event(
        db,
        run.id,
        "run.created",
        {"status": AgentRunStatus.queued.value},
    )
    conversation.last_message_at = datetime.utcnow()
    initialize_workflow(
        db,
        native_run=run,
        include_article_tasks=bool(
            {
                "write_article",
                "review_article",
                "submit_final_article",
            }.intersection(selected_tool_names)
        ),
    )
    db.commit()

    await enqueue_native_agent_run(run.id)
    return ApiData(data=_run_to_read(_load_run_for_read(db, run.id)))


@router.post(
    "/runs/{parent_run_id}/follow-ups",
    response_model=ApiData[NativeAgentRunRead],
    status_code=status.HTTP_202_ACCEPTED,
)
async def create_native_agent_follow_up(
    parent_run_id: str,
    payload: NativeAgentFollowUpCreate,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> ApiData[NativeAgentRunRead]:
    parent_run = db.scalar(
        select(NativeAgentRun)
        .join(
            NativeAgentConversation,
            NativeAgentConversation.id == NativeAgentRun.conversation_id,
        )
        .where(
            NativeAgentRun.id == parent_run_id,
            NativeAgentConversation.owner_user_id == user.id,
        )
    )
    if parent_run is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="父 Run 不存在或不可访问",
        )
    try:
        run, replayed = create_follow_up_run(
            db,
            parent_run=parent_run,
            user=user,
            payload=payload,
        )
        db.commit()
    except NativeAgentFollowUpError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    except IntegrityError as exc:
        db.rollback()
        try:
            run = find_idempotent_follow_up(
                db,
                user=user,
                parent_run_id=parent_run_id,
                payload=payload,
            )
        except NativeAgentFollowUpError as replay_exc:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=str(replay_exc),
            ) from replay_exc
        if run is None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Follow-up 创建发生并发冲突，请使用相同幂等键重试",
            ) from exc
        replayed = True

    if not replayed:
        await enqueue_native_agent_run(run.id)
    return ApiData(data=_run_to_read(_load_run_for_read(db, run.id)))


@router.post(
    "/conversations/{conversation_id}/retry-latest",
    response_model=ApiData[NativeAgentRunRead],
    status_code=status.HTTP_202_ACCEPTED,
)
async def retry_latest_native_agent_run(
    conversation_id: str,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> ApiData[NativeAgentRunRead]:
    conversation = _load_owned_conversation(
        db,
        conversation_id=conversation_id,
        owner_user_id=user.id,
    )
    run = db.scalar(
        select(NativeAgentRun)
        .where(NativeAgentRun.conversation_id == conversation.id)
        .order_by(NativeAgentRun.created_at.desc(), NativeAgentRun.id.desc())
        .limit(1)
    )
    if run is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="当前会话还没有可重试的任务",
        )
    if run.status in {
        AgentRunStatus.queued,
        AgentRunStatus.running,
        AgentRunStatus.waiting_for_tool,
        AgentRunStatus.waiting_for_input,
        AgentRunStatus.retrying,
        AgentRunStatus.cancel_requested,
    }:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="最近一次任务仍在执行，不能重复提交重试",
        )
    if run.status == AgentRunStatus.cancelled:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="最近一次任务已由用户终止，不能自动重试",
        )

    unknown_step = db.scalar(
        select(NativeAgentStep)
        .where(
            NativeAgentStep.run_id == run.id,
            NativeAgentStep.step_type == NativeAgentStepType.tool_call,
            NativeAgentStep.status == NativeAgentStepStatus.unknown,
        )
        .order_by(NativeAgentStep.sequence.desc())
        .limit(1)
    )
    if unknown_step is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="最近一次任务存在结果未知的 Tool，为避免重复计费不能自动重试",
        )
    failed_step = db.scalar(
        select(NativeAgentStep)
        .where(
            NativeAgentStep.run_id == run.id,
            NativeAgentStep.step_type == NativeAgentStepType.tool_call,
            NativeAgentStep.status == NativeAgentStepStatus.failed,
        )
        .order_by(NativeAgentStep.sequence.desc())
        .limit(1)
    )
    if run.status == AgentRunStatus.succeeded and failed_step is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="最近一次任务已经完成，没有失败的 Tool 可以重试",
        )

    try:
        NativeAgentStore(run.id, session_factory=SessionLocal).request_retry(
            failed_step_id=failed_step.id if failed_step is not None else None
        )
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    conversation.last_message_at = datetime.utcnow()
    db.commit()
    await enqueue_native_agent_run(run.id)
    return ApiData(data=_run_to_read(_load_run_for_read(db, run.id)))


@router.post(
    "/article-approvals/{approval_id}/decision",
    response_model=ApiData[NativeAgentRunRead],
)
async def decide_native_article_approval(
    approval_id: str,
    payload: NativeAgentArticleApprovalDecision,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> ApiData[NativeAgentRunRead]:
    approval = db.scalar(
        select(NativeAgentArticleApproval)
        .join(
            NativeAgentRun,
            NativeAgentRun.id == NativeAgentArticleApproval.run_id,
        )
        .join(
            NativeAgentConversation,
            NativeAgentConversation.id == NativeAgentRun.conversation_id,
        )
        .where(
            NativeAgentArticleApproval.id == approval_id,
            NativeAgentConversation.owner_user_id == user.id,
        )
    )
    if approval is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="文案审批不存在",
        )
    try:
        durable_gate = mirror_native_article_approval(
            db,
            native_run=approval.run,
            native_approval=approval,
        )
        workflow = workflow_for_native_run(db, approval.run_id)
        if workflow is None:
            raise DurableAgentRuntimeError("文案审批缺少 Durable Workflow")
        _, result = execute_durable_control_command(
            db,
            run=approval.run,
            workflow=workflow,
            user=user,
            payload=DurableControlCommandCreate(
                command=(
                    "approve_gate"
                    if payload.decision == "approve"
                    else "request_changes"
                ),
                idempotency_key=(
                    f"legacy-article:{approval.id}:{payload.decision}"
                ),
                expected_state_version=workflow.state_version,
                target_id=durable_gate.id,
                feedback=payload.feedback,
            ),
        )
        run_id = approval.run_id
        db.commit()
    except (
        NativeArticleWorkflowError,
        DurableAgentRuntimeError,
        AgentControlCommandError,
    ) as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    db.expire_all()
    if result.get("enqueue_run"):
        await enqueue_native_agent_run(run_id)
    return ApiData(data=_run_to_read(_load_run_for_read(db, run_id)))


@router.post(
    "/runs/{run_id}/cancel",
    response_model=ApiData[NativeAgentRunRead],
    status_code=status.HTTP_202_ACCEPTED,
)
async def cancel_native_run(
    run_id: str,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> ApiData[NativeAgentRunRead]:
    run = db.scalar(
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
    if run is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Native Agent Run 不存在",
        )
    if run.status == AgentRunStatus.cancelled:
        return ApiData(data=_run_to_read(_load_run_for_read(db, run.id)))
    if run.status in {
        AgentRunStatus.succeeded,
        AgentRunStatus.failed,
    }:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="已结束的 Native Agent Run 不能终止",
        )
    workflow = workflow_for_native_run(db, run.id)
    if workflow is not None:
        try:
            _, result = execute_durable_control_command(
                db,
                run=run,
                workflow=workflow,
                user=user,
                payload=DurableControlCommandCreate(
                    command="cancel_run",
                    idempotency_key=f"legacy-cancel:{run.id}",
                    expected_state_version=workflow.state_version,
                    feedback="兼容取消入口请求终止",
                ),
            )
            db.commit()
        except AgentControlCommandError as exc:
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=str(exc),
            ) from exc
        if result.get("cancel_worker"):
            await cancel_native_agent_run(run.id)
        return ApiData(data=_run_to_read(_load_run_for_read(db, run.id)))
    if run.status != AgentRunStatus.cancel_requested:
        cancel_update = db.execute(
            update(NativeAgentRun)
            .where(
                NativeAgentRun.id == run.id,
                NativeAgentRun.status.notin_(
                    [
                        AgentRunStatus.succeeded,
                        AgentRunStatus.failed,
                        AgentRunStatus.cancelled,
                        AgentRunStatus.cancel_requested,
                    ]
                ),
            )
            .values(status=AgentRunStatus.cancel_requested)
            .execution_options(synchronize_session=False)
        )
        if cancel_update.rowcount == 0:
            db.expire_all()
            current_run = db.get(NativeAgentRun, run.id)
            if current_run is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Native Agent Run 不存在",
                )
            if current_run.status == AgentRunStatus.cancelled:
                return ApiData(
                    data=_run_to_read(_load_run_for_read(db, current_run.id))
                )
            if current_run.status in {
                AgentRunStatus.succeeded,
                AgentRunStatus.failed,
            }:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="已结束的 Native Agent Run 不能终止",
                )
        add_native_agent_event(
            db,
            run.id,
            "run.cancel_requested",
            {"status": AgentRunStatus.cancel_requested.value},
        )
        db.commit()
    await cancel_native_agent_run(run.id)
    return ApiData(data=_run_to_read(_load_run_for_read(db, run.id)))


@router.get(
    "/runs/{run_id}/control-state",
    response_model=ApiData[DurableControlStateRead],
)
def get_durable_control_state(
    run_id: str,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> ApiData[DurableControlStateRead]:
    _, workflow = _load_owned_durable_workflow(
        db,
        run_id=run_id,
        owner_user_id=user.id,
    )
    return ApiData(
        data=DurableControlStateRead.model_validate(
            durable_control_state(db, workflow=workflow)
        )
    )


@router.post(
    "/runs/{run_id}/commands",
    response_model=ApiData[DurableControlCommandRead],
)
async def execute_durable_command(
    run_id: str,
    payload: DurableControlCommandCreate,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> ApiData[DurableControlCommandRead]:
    run, workflow = _load_owned_durable_workflow(
        db,
        run_id=run_id,
        owner_user_id=user.id,
    )
    try:
        command, result = execute_durable_control_command(
            db,
            run=run,
            workflow=workflow,
            user=user,
            payload=payload,
        )
        db.commit()
    except AgentControlCommandError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    db.refresh(command)
    if result.get("cancel_worker"):
        await cancel_native_agent_run(run.id)
    if result.get("enqueue_run"):
        await enqueue_native_agent_run(run.id)
    return ApiData(
        data=DurableControlCommandRead(
            id=command.id,
            command=command.command_type,
            target_id=command.target_id,
            idempotency_key=command.idempotency_key,
            expected_state_version=command.expected_state_version,
            status=command.status,
            result=result,
            control_state=DurableControlStateRead.model_validate(
                durable_control_state(db, workflow=workflow)
            ),
            created_at=command.created_at,
        )
    )


@router.get(
    "/runs/{run_id}/plan-revisions",
    response_model=ApiData[list[dict[str, object]]],
)
def list_durable_plan_revisions(
    run_id: str,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> ApiData[list[dict[str, object]]]:
    run = db.scalar(
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
    if run is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Native Agent Run 不存在",
        )
    workflow = workflow_for_native_run(db, run.id)
    if workflow is None:
        return ApiData(data=[])
    revisions = db.scalars(
        select(DurableAgentPlanRevision)
        .where(DurableAgentPlanRevision.workflow_id == workflow.id)
        .order_by(DurableAgentPlanRevision.revision.asc())
    ).all()
    return ApiData(
        data=[
            {
                "id": item.id,
                "revision": item.revision,
                "reason": item.reason,
                "source_checkpoint_id": item.source_checkpoint_id,
                "plan": json.loads(item.plan_json),
                "created_at": item.created_at,
            }
            for item in revisions
        ]
    )


@router.post(
    "/runs/{run_id}/visual-plan",
    response_model=ApiData[dict[str, object]],
    status_code=status.HTTP_201_CREATED,
)
def create_durable_visual_plan(
    run_id: str,
    payload: DurableVisualPlanCreate,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> ApiData[dict[str, object]]:
    run, workflow = _load_owned_durable_workflow(
        db,
        run_id=run_id,
        owner_user_id=user.id,
    )
    try:
        artifact, gate = register_visual_plan(
            db,
            workflow=workflow,
            content=payload.model_dump(mode="json"),
        )
        run.status = AgentRunStatus.waiting_for_input
        run.workflow_phase = "visual_plan_review"
        run.finished_at = None
        db.commit()
    except DurableAgentRuntimeError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    return ApiData(
        data={
            "artifact_id": artifact.id,
            "artifact_version": artifact.version,
            "gate_id": gate.id,
            "gate_status": gate.status,
        }
    )


@router.post(
    "/runs/{run_id}/durable-gates/{gate_id}/decision",
    response_model=ApiData[dict[str, object]],
)
async def decide_durable_media_gate(
    run_id: str,
    gate_id: str,
    payload: DurableGateDecision,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> ApiData[dict[str, object]]:
    run, workflow = _load_owned_durable_workflow(
        db,
        run_id=run_id,
        owner_user_id=user.id,
    )
    gate = db.get(DurableAgentGate, gate_id)
    if gate is None or gate.workflow_id != workflow.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Durable Gate 不存在",
        )
    if gate.purpose not in {"visual_plan_review", "image_quality_review"}:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="该 Gate 必须通过原文案审批入口处理",
        )
    if gate.purpose == "image_quality_review" and payload.decision != "approve":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="图片质量修改必须通过具体 Panel 的局部重跑入口提交",
        )
    try:
        _, result = execute_durable_control_command(
            db,
            run=run,
            workflow=workflow,
            user=user,
            payload=DurableControlCommandCreate(
                command=(
                    "approve_gate"
                    if payload.decision == "approve"
                    else "request_changes"
                ),
                idempotency_key=f"legacy-media:{gate.id}:{payload.decision}",
                expected_state_version=workflow.state_version,
                target_id=gate.id,
                feedback=payload.feedback,
            ),
        )
        db.commit()
    except (DurableAgentRuntimeError, AgentControlCommandError) as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    if result.get("enqueue_run"):
        await enqueue_native_agent_run(run.id)
    db.refresh(gate)
    return ApiData(
        data={
            "gate_id": gate.id,
            "status": gate.status,
            "attempt_ids": result["attempt_ids"],
        }
    )


@router.get(
    "/runs/{run_id}/media-state",
    response_model=ApiData[dict[str, object]],
)
def get_durable_media_state(
    run_id: str,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> ApiData[dict[str, object]]:
    _, workflow = _load_owned_durable_workflow(
        db,
        run_id=run_id,
        owner_user_id=user.id,
    )
    bindings = db.scalars(
        select(DurableAgentMediaBinding)
        .where(DurableAgentMediaBinding.workflow_id == workflow.id)
        .order_by(DurableAgentMediaBinding.created_at)
    ).all()
    rows: list[dict[str, object]] = []
    for binding in bindings:
        latest_quality = db.scalar(
            select(DurableAgentImageQuality)
            .where(DurableAgentImageQuality.media_binding_id == binding.id)
            .order_by(DurableAgentImageQuality.revision.desc())
            .limit(1)
        )
        rows.append(
            {
                "binding_id": binding.id,
                "plan_panel_key": binding.plan_panel_key,
                "generated_image_id": binding.generated_image_id,
                "native_agent_image_id": binding.native_agent_image_id,
                "image_task_id": binding.image_task_id,
                "quality_task_id": binding.quality_task_id,
                "status": binding.status,
                "quality_revision": (
                    latest_quality.revision if latest_quality is not None else None
                ),
                "quality_summary": (
                    latest_quality.summary if latest_quality is not None else None
                ),
            }
        )
    return ApiData(
        data={
            "workflow_id": workflow.id,
            "state_version": workflow.state_version,
            "status": workflow.status,
            "bindings": rows,
        }
    )


@router.post(
    "/media-bindings/{binding_id}/quality",
    response_model=ApiData[dict[str, object]],
)
def decide_durable_image_quality(
    binding_id: str,
    payload: DurableImageQualityDecision,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> ApiData[dict[str, object]]:
    _, binding = _load_owned_media_binding(
        db,
        binding_id=binding_id,
        owner_user_id=user.id,
    )
    try:
        quality = record_image_quality(
            db,
            binding=binding,
            verdict=payload.verdict,
            summary=payload.summary,
            details=payload.details,
        )
        db.commit()
    except DurableAgentRuntimeError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    return ApiData(
        data={
            "binding_id": binding.id,
            "quality_id": quality.id,
            "revision": quality.revision,
            "verdict": quality.verdict,
        }
    )


@router.post(
    "/runs/{run_id}/media-quality-gate",
    response_model=ApiData[dict[str, object]],
    status_code=status.HTTP_201_CREATED,
)
def create_durable_media_quality_gate(
    run_id: str,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> ApiData[dict[str, object]]:
    run, workflow = _load_owned_durable_workflow(
        db,
        run_id=run_id,
        owner_user_id=user.id,
    )
    try:
        gate = open_image_quality_gate(db, workflow=workflow)
        run.status = AgentRunStatus.waiting_for_input
        run.workflow_phase = "image_quality_review"
        run.finished_at = None
        db.commit()
    except DurableAgentRuntimeError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    return ApiData(data={"gate_id": gate.id, "status": gate.status})


@router.post(
    "/media-bindings/{binding_id}/rerun",
    response_model=ApiData[dict[str, object]],
    status_code=status.HTTP_202_ACCEPTED,
)
async def rerun_durable_panel_image(
    binding_id: str,
    payload: DurablePanelRerunRequest,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> ApiData[dict[str, object]]:
    run, binding = _load_owned_media_binding(
        db,
        binding_id=binding_id,
        owner_user_id=user.id,
    )
    workflow = db.get(DurableAgentWorkflow, binding.workflow_id)
    if workflow is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Panel 绑定缺少 Durable Workflow",
        )
    try:
        _, result = execute_durable_control_command(
            db,
            run=run,
            workflow=workflow,
            user=user,
            payload=DurableControlCommandCreate(
                command="retry_task",
                idempotency_key=(
                    f"legacy-panel:{binding.id}:v{workflow.state_version}"
                ),
                expected_state_version=workflow.state_version,
                target_id=binding.image_task_id,
                feedback=payload.feedback,
            ),
        )
        db.commit()
    except (DurableAgentRuntimeError, AgentControlCommandError) as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    if result.get("enqueue_run"):
        await enqueue_native_agent_run(run.id)
    db.refresh(binding)
    return ApiData(
        data={
            "binding_id": binding.id,
            "attempt_id": result["attempt_ids"][0],
            "status": binding.status,
        }
    )


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
        resync_checked = False
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
                cursor_gap = False
                if not resync_checked:
                    cursor_gap = bool(
                        current_cursor > run.event_sequence
                        or (
                            events
                            and events[0].sequence > current_cursor + 1
                        )
                    )
                    if current_cursor > run.event_sequence:
                        current_cursor = 0
                        events = event_db.scalars(
                            select(NativeAgentEvent)
                            .where(NativeAgentEvent.run_id == run_id)
                            .order_by(NativeAgentEvent.sequence.asc())
                            .limit(100)
                        ).all()
                    resync_checked = True
                run_read = normalize_api_datetimes(_run_to_read(run))
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
            if cursor_gap:
                resync_payload = json.dumps(
                    {
                        "reason": "event_cursor_gap",
                        "requested_cursor": requested_cursor,
                        "last_event_id": header_cursor,
                        "current_event_sequence": run.event_sequence,
                    },
                    ensure_ascii=False,
                    separators=(",", ":"),
                )
                yield f"event: run.resync_required\ndata: {resync_payload}\n\n"
            if events:
                for event in events:
                    event_payload = json.dumps(
                        normalize_api_datetimes(
                            _event_to_read(event)
                        ).model_dump(mode="json"),
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
