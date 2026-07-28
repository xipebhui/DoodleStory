from __future__ import annotations

from datetime import datetime
import json

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.api.deps import current_user
from app.api.pagination import Pagination, build_page, get_pagination
from app.core.database import get_db
from app.models.entities import (
    NativeAgentVideo,
    PublishableVideo,
    User,
    YoutubeChannel,
    YoutubeChannelBenchmark,
    YoutubePublishTask,
    YoutubeUploadedVideo,
)
from app.models.enums import UserRole
from app.schemas.common import ApiData, ApiList
from app.schemas.youtube import (
    PublishableVideoCreate,
    PublishableVideoRead,
    YoutubeBenchmarkCreate,
    YoutubeBenchmarkRead,
    YoutubeChannelDetailRead,
    YoutubeChannelProfileUpdate,
    YoutubeChannelSummaryRead,
    YoutubePublishTaskCreate,
    YoutubePublishTaskRead,
    YoutubeUploadedVideoRead,
)
from app.services.storage import asset_content_url
from app.services.youtube_publisher import YoutubePublisherClient, YoutubePublisherError
from app.services.youtube_publishing import (
    YoutubePublishCommand,
    YoutubePublishingConflict,
    YoutubePublishingError,
    YoutubePublishingForbidden,
    create_youtube_publish_task,
    refresh_youtube_publish_task,
)


router = APIRouter(prefix="/youtube", tags=["youtube"])


def require_admin(user: User) -> None:
    if user.role != UserRole.admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="仅管理员可管理 YouTube 频道")


def parse_remote_time(value: object) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).replace(tzinfo=None)
    except ValueError:
        return None


def channel_summary(channel: YoutubeChannel) -> YoutubeChannelSummaryRead:
    return YoutubeChannelSummaryRead(
        id=channel.id,
        channel_id=channel.channel_id,
        title=channel.title,
        handle=channel.handle,
        avatar_url=channel.avatar_url,
        remote_status=channel.remote_status,
        alias=channel.alias,
        account_positioning=channel.account_positioning,
        total_subscribers=channel.total_subscribers,
        total_views=channel.total_views,
        total_watch_time_hours=channel.total_watch_time_hours,
        total_videos=channel.total_videos,
        last_sync_success_at=channel.last_sync_success_at,
        last_sync_error=channel.last_sync_error,
    )


def publish_task_read(task: YoutubePublishTask) -> YoutubePublishTaskRead:
    return YoutubePublishTaskRead(
        id=task.id,
        channel_id=task.channel_id,
        publishable_video_id=task.publishable_video_id,
        source_native_agent_video_id=task.source_native_agent_video_id,
        remote_task_id=task.remote_task_id,
        status=task.status,
        remote_status=task.remote_status,
        title=task.title_snapshot,
        thumbnail_url=task.thumbnail_url_snapshot,
        video_url=task.video_url_snapshot,
        visibility=task.visibility_snapshot,
        planned_publish_at=task.planned_publish_at,
        confirmed_at=task.confirmed_at,
        last_status_checked_at=task.last_status_checked_at,
        completed_at=task.completed_at,
        youtube_video_id=task.youtube_video_id,
        youtube_url=task.youtube_url,
        error_code=task.error_code,
        error_message=task.error_message,
        created_at=task.created_at,
    )


def publishable_video_read(item: PublishableVideo) -> PublishableVideoRead:
    return PublishableVideoRead(
        id=item.id,
        source_native_agent_video_id=item.source_native_agent_video_id,
        video_url=item.video_url,
        thumbnail_url=item.thumbnail_url,
        title=item.title,
        description=item.description,
        tags=json.loads(item.tags_json),
        planned_publish_at=item.planned_publish_at,
        contains_synthetic_media=item.contains_synthetic_media,
        review_status=item.review_status,
        created_at=item.created_at,
    )


def channel_detail(channel: YoutubeChannel) -> YoutubeChannelDetailRead:
    summary = channel_summary(channel).model_dump()
    return YoutubeChannelDetailRead(
        **summary,
        account_email=channel.account_email,
        target_audience=channel.target_audience,
        stage_goal=channel.stage_goal,
        ai_definition=channel.ai_definition,
        operation_notes=channel.operation_notes,
        analytics=json.loads(channel.analytics_json) if channel.analytics_json else None,
        benchmarks=[
            YoutubeBenchmarkRead(
                id=item.id,
                platform=item.platform,
                name=item.name,
                platform_account_id=item.platform_account_id,
                profile_url=item.profile_url,
                notes=item.notes,
                created_at=item.created_at,
            )
            for item in channel.benchmarks
        ],
        uploaded_videos=[
            YoutubeUploadedVideoRead(
                id=item.id,
                youtube_video_id=item.youtube_video_id,
                publish_task_id=item.publish_task_id,
                source_native_agent_video_id=item.source_native_agent_video_id,
                title=item.title,
                visibility=item.visibility,
                views=item.views,
                likes=item.likes,
                uploaded_at=item.uploaded_at,
                remote_last_sync_at=item.remote_last_sync_at,
                last_sync_error=item.last_sync_error,
            )
            for item in channel.uploaded_videos[:100]
        ],
        publish_tasks=[
            publish_task_read(item)
            for item in channel.publish_tasks[:100]
        ],
    )


def load_channel(db: Session, channel_id: str) -> YoutubeChannel:
    channel = db.scalar(
        select(YoutubeChannel)
        .options(
            selectinload(YoutubeChannel.benchmarks),
            selectinload(YoutubeChannel.uploaded_videos),
            selectinload(YoutubeChannel.publish_tasks),
        )
        .where(YoutubeChannel.id == channel_id)
    )
    if channel is None:
        raise HTTPException(status_code=404, detail="频道不存在")
    return channel


@router.get("/channels", response_model=ApiList[YoutubeChannelSummaryRead])
def list_channels(
    q: str | None = Query(default=None, max_length=120),
    remote_status: str | None = Query(default=None, max_length=40),
    pagination: Pagination = Depends(get_pagination),
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> ApiList[YoutubeChannelSummaryRead]:
    require_admin(user)
    filters = []
    if q and q.strip():
        pattern = f"%{q.strip()}%"
        filters.append(or_(YoutubeChannel.alias.ilike(pattern), YoutubeChannel.title.ilike(pattern), YoutubeChannel.handle.ilike(pattern)))
    if remote_status:
        filters.append(YoutubeChannel.remote_status == remote_status)
    total = db.scalar(select(func.count()).select_from(YoutubeChannel).where(*filters)) or 0
    rows = db.scalars(
        select(YoutubeChannel)
        .where(*filters)
        .order_by(YoutubeChannel.updated_at.desc(), YoutubeChannel.id)
        .offset(pagination.offset)
        .limit(pagination.limit + 1)
    ).all()
    return ApiList(
        items=[channel_summary(item) for item in rows[: pagination.limit]],
        page={**build_page(pagination.limit, pagination.offset, len(rows)), "total": total},
    )


@router.post("/channels/sync", response_model=ApiData[dict[str, int]])
def sync_channels(user: User = Depends(current_user), db: Session = Depends(get_db)) -> ApiData[dict[str, int]]:
    require_admin(user)
    try:
        remote_rows = YoutubePublisherClient().list_channels()
    except YoutubePublisherError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    created = 0
    for row in remote_rows:
        remote_id = str(row.get("channel_id") or "").strip()
        if not remote_id:
            raise HTTPException(status_code=502, detail="远程频道缺少 channel_id")
        channel = db.scalar(select(YoutubeChannel).where(YoutubeChannel.channel_id == remote_id))
        if channel is None:
            channel = YoutubeChannel(channel_id=remote_id, title=str(row.get("title") or remote_id), remote_status=str(row.get("status") or "unknown"))
            db.add(channel)
            created += 1
        channel.title = str(row.get("title") or remote_id)
        channel.handle = row.get("handle")
        channel.avatar_url = row.get("avatar_url") or row.get("thumbnail_url")
        channel.account_email = row.get("youtube_account_email") or row.get("email")
        channel.remote_status = str(row.get("status") or "unknown")
        channel.remote_last_sync_at = parse_remote_time(row.get("last_sync_at"))
        channel.last_sync_error = row.get("last_sync_error")
        if not channel.last_sync_error:
            channel.last_sync_success_at = parse_remote_time(row.get("last_sync_success_at") or row.get("last_sync_at"))
    db.commit()
    return ApiData(data={"total": len(remote_rows), "created": created, "updated": len(remote_rows) - created})


@router.get("/channels/{channel_pk}", response_model=ApiData[YoutubeChannelDetailRead])
def get_channel(channel_pk: str, user: User = Depends(current_user), db: Session = Depends(get_db)) -> ApiData[YoutubeChannelDetailRead]:
    require_admin(user)
    return ApiData(data=channel_detail(load_channel(db, channel_pk)))


@router.patch("/channels/{channel_pk}/profile", response_model=ApiData[YoutubeChannelDetailRead])
def update_channel_profile(channel_pk: str, payload: YoutubeChannelProfileUpdate, user: User = Depends(current_user), db: Session = Depends(get_db)) -> ApiData[YoutubeChannelDetailRead]:
    require_admin(user)
    channel = load_channel(db, channel_pk)
    for key, value in payload.model_dump().items():
        setattr(channel, key, value)
    db.commit()
    return ApiData(data=channel_detail(load_channel(db, channel_pk)))


@router.post("/channels/{channel_pk}/analytics/sync", response_model=ApiData[YoutubeChannelDetailRead])
def sync_channel_analytics(channel_pk: str, user: User = Depends(current_user), db: Session = Depends(get_db)) -> ApiData[YoutubeChannelDetailRead]:
    require_admin(user)
    channel = load_channel(db, channel_pk)
    try:
        payload = YoutubePublisherClient().channel_analytics(channel.channel_id)
    except YoutubePublisherError as exc:
        channel.last_sync_error = str(exc)
        db.commit()
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    analytics = payload.get("analytics") if isinstance(payload.get("analytics"), dict) else {}
    channel.analytics_json = json.dumps(analytics, ensure_ascii=False)
    channel.total_subscribers = analytics.get("total_subscribers")
    channel.total_views = analytics.get("total_views")
    channel.total_watch_time_hours = analytics.get("total_watch_time_hours")
    channel.last_sync_error = payload.get("last_sync_error")
    channel.last_sync_success_at = parse_remote_time(payload.get("last_sync_success_at") or payload.get("last_sync_at"))
    db.commit()
    return ApiData(data=channel_detail(load_channel(db, channel_pk)))


@router.post("/channels/{channel_pk}/videos/sync", response_model=ApiData[YoutubeChannelDetailRead])
def sync_channel_videos(channel_pk: str, user: User = Depends(current_user), db: Session = Depends(get_db)) -> ApiData[YoutubeChannelDetailRead]:
    require_admin(user)
    channel = load_channel(db, channel_pk)
    try:
        rows = YoutubePublisherClient().channel_videos(channel.channel_id)
    except YoutubePublisherError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    for row in rows:
        video_id = str(row.get("youtube_video_id") or "").strip()
        if not video_id:
            raise HTTPException(status_code=502, detail="远程视频缺少 youtube_video_id")
        video = db.scalar(select(YoutubeUploadedVideo).where(YoutubeUploadedVideo.youtube_video_id == video_id))
        if video is None:
            video = YoutubeUploadedVideo(
                channel_id=channel.id,
                youtube_video_id=video_id,
                uploaded_at=parse_remote_time(row.get("uploaded_at")) or datetime.utcnow(),
            )
            db.add(video)
        elif video.channel_id != channel.id:
            raise HTTPException(status_code=409, detail="YouTube 视频已关联到其他频道")
        video.remote_upload_task_id = row.get("upload_task_id")
        video.title = row.get("title")
        video.description = row.get("description")
        video.tags_json = json.dumps(row.get("tags") or [], ensure_ascii=False)
        video.visibility = row.get("visibility")
        video.views = row.get("views")
        video.likes = row.get("likes")
        video.remote_last_sync_at = parse_remote_time(row.get("last_sync_at"))
        video.last_sync_error = row.get("last_sync_error")
    channel.total_videos = len(rows)
    db.commit()
    return ApiData(data=channel_detail(load_channel(db, channel_pk)))


@router.post("/channels/{channel_pk}/benchmarks", response_model=ApiData[YoutubeBenchmarkRead])
def create_benchmark(channel_pk: str, payload: YoutubeBenchmarkCreate, user: User = Depends(current_user), db: Session = Depends(get_db)) -> ApiData[YoutubeBenchmarkRead]:
    require_admin(user)
    channel = load_channel(db, channel_pk)
    item = YoutubeChannelBenchmark(
        channel_id=channel.id,
        platform=payload.platform.strip(),
        name=payload.name.strip(),
        platform_account_id=payload.platform_account_id,
        profile_url=str(payload.profile_url),
        notes=payload.notes,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return ApiData(data=YoutubeBenchmarkRead(id=item.id, platform=item.platform, name=item.name, platform_account_id=item.platform_account_id, profile_url=item.profile_url, notes=item.notes, created_at=item.created_at))


@router.delete(
    "/channels/{channel_pk}/benchmarks/{benchmark_id}",
    status_code=204,
    response_class=Response,
    response_model=None,
)
def delete_benchmark(channel_pk: str, benchmark_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)) -> Response:
    require_admin(user)
    item = db.scalar(select(YoutubeChannelBenchmark).where(YoutubeChannelBenchmark.id == benchmark_id, YoutubeChannelBenchmark.channel_id == channel_pk))
    if item is None:
        raise HTTPException(status_code=404, detail="对标账号不存在")
    db.delete(item)
    db.commit()
    return Response(status_code=204)


@router.post("/publishable-videos", response_model=ApiData[PublishableVideoRead])
def create_publishable_video(payload: PublishableVideoCreate, user: User = Depends(current_user), db: Session = Depends(get_db)) -> ApiData[PublishableVideoRead]:
    require_admin(user)
    source = db.scalar(
        select(NativeAgentVideo)
        .options(selectinload(NativeAgentVideo.asset), selectinload(NativeAgentVideo.run))
        .where(NativeAgentVideo.id == payload.source_native_agent_video_id)
    )
    if source is None or source.run.owner_user_id != user.id:
        raise HTTPException(status_code=404, detail="Native Agent 视频不存在")
    if db.scalar(select(PublishableVideo).where(PublishableVideo.source_native_agent_video_id == source.id)):
        raise HTTPException(status_code=409, detail="该 Native Agent 视频已经登记")
    try:
        video_url = asset_content_url(source.asset)
    except HTTPException as exc:
        raise HTTPException(status_code=400, detail="Native Agent 视频没有公网 URL，不能登记发布") from exc
    item = PublishableVideo(
        owner_user_id=user.id,
        source_native_agent_video_id=source.id,
        video_url=video_url,
        thumbnail_url=str(payload.thumbnail_url) if payload.thumbnail_url else None,
        title=payload.title.strip(),
        description=payload.description,
        tags_json=json.dumps(payload.tags, ensure_ascii=False),
        planned_publish_at=payload.planned_publish_at.replace(tzinfo=None) if payload.planned_publish_at else None,
        contains_synthetic_media=payload.contains_synthetic_media,
        review_status=payload.review_status,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return ApiData(data=publishable_video_read(item))


@router.get("/publishable-videos", response_model=ApiList[PublishableVideoRead])
def list_publishable_videos(
    review_status: str | None = Query(default=None, max_length=40),
    pagination: Pagination = Depends(get_pagination),
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> ApiList[PublishableVideoRead]:
    require_admin(user)
    filters = [PublishableVideo.owner_user_id == user.id]
    if review_status:
        filters.append(PublishableVideo.review_status == review_status)
    total = db.scalar(
        select(func.count()).select_from(PublishableVideo).where(*filters)
    ) or 0
    rows = db.scalars(
        select(PublishableVideo)
        .where(*filters)
        .order_by(PublishableVideo.created_at.desc(), PublishableVideo.id.desc())
        .offset(pagination.offset)
        .limit(pagination.limit + 1)
    ).all()
    return ApiList(
        items=[publishable_video_read(item) for item in rows[: pagination.limit]],
        page={
            **build_page(pagination.limit, pagination.offset, len(rows)),
            "total": total,
        },
    )


@router.post(
    "/channels/{channel_pk}/publish-tasks",
    response_model=ApiData[YoutubePublishTaskRead],
    status_code=202,
)
def create_publish_task(
    channel_pk: str,
    payload: YoutubePublishTaskCreate,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> ApiData[YoutubePublishTaskRead]:
    require_admin(user)
    try:
        task = create_youtube_publish_task(
            db,
            YoutubePublishCommand(
                owner_user_id=user.id,
                channel_id=channel_pk,
                publishable_video_id=payload.publishable_video_id,
                visibility=payload.visibility,
                planned_publish_at=payload.planned_publish_at,
                notify_subscribers=payload.notify_subscribers,
                confirmed=payload.confirmed,
                idempotency_key=payload.idempotency_key,
            ),
        )
    except YoutubePublishingForbidden as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except YoutubePublishingConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except YoutubePublishingError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ApiData(data=publish_task_read(task))


@router.post(
    "/channels/{channel_pk}/publish-tasks/{task_id}/refresh",
    response_model=ApiData[YoutubePublishTaskRead],
)
def refresh_publish_task(
    channel_pk: str,
    task_id: str,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> ApiData[YoutubePublishTaskRead]:
    require_admin(user)
    task = db.scalar(
        select(YoutubePublishTask).where(
            YoutubePublishTask.id == task_id,
            YoutubePublishTask.channel_id == channel_pk,
            YoutubePublishTask.owner_user_id == user.id,
        )
    )
    if task is None:
        raise HTTPException(status_code=404, detail="YouTube 发布任务不存在")
    try:
        refreshed = refresh_youtube_publish_task(db, task)
    except YoutubePublishingConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return ApiData(data=publish_task_read(refreshed))
