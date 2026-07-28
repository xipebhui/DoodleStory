from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.entities import (
    PublishableVideo,
    YoutubeChannel,
    YoutubePublishTask,
    YoutubeUploadedVideo,
)
from app.services.youtube_publisher import (
    YoutubePublisherClient,
    YoutubePublisherOutcomeUnknown,
    YoutubePublisherRequestRejected,
)


class YoutubePublishingError(RuntimeError):
    pass


class YoutubePublishingConflict(YoutubePublishingError):
    pass


class YoutubePublishingForbidden(YoutubePublishingError):
    pass


@dataclass(frozen=True)
class YoutubePublishCommand:
    owner_user_id: str
    channel_id: str
    publishable_video_id: str
    visibility: str
    planned_publish_at: datetime | None
    notify_subscribers: bool
    confirmed: bool
    idempotency_key: str


def _utc_naive(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value
    return value.astimezone(timezone.utc).replace(tzinfo=None)


def _remote_time(value: object) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(
            timezone.utc
        ).replace(tzinfo=None)
    except ValueError:
        return None


def _remote_iso(value: datetime) -> str:
    return value.replace(tzinfo=timezone.utc).isoformat().replace("+00:00", "Z")


def _create_payload(
    task: YoutubePublishTask,
    channel: YoutubeChannel,
) -> dict[str, object]:
    return {
        "channel_id": channel.channel_id,
        "plan_run_at": _remote_iso(task.planned_publish_at),
        "upload_args": {
            "body": {
                "snippet": {
                    "title": task.title_snapshot,
                    "description": task.description_snapshot,
                    "tags": json.loads(task.tags_json),
                },
                "status": {
                    "privacyStatus": task.visibility_snapshot,
                    "selfDeclaredMadeForKids": False,
                    "containsSyntheticMedia": (
                        task.contains_synthetic_media_snapshot
                    ),
                },
                "paidProductPlacementDetails": {
                    "hasPaidProductPlacement": False,
                },
            },
            "query": {
                "notifySubscribers": task.notify_subscribers,
            },
        },
        "thumbnail_url": task.thumbnail_url_snapshot,
        "download_url": task.video_url_snapshot,
    }


def create_youtube_publish_task(
    db: Session,
    command: YoutubePublishCommand,
    *,
    client: YoutubePublisherClient | None = None,
) -> YoutubePublishTask:
    if not command.confirmed:
        raise YoutubePublishingForbidden("发布 YouTube 视频前必须明确确认")
    if command.visibility not in {"public", "private", "unlisted"}:
        raise YoutubePublishingError("YouTube 可见性参数不正确")
    existing_key = db.scalar(
        select(YoutubePublishTask).where(
            YoutubePublishTask.idempotency_key == command.idempotency_key
        )
    )
    if existing_key is not None:
        return existing_key
    existing_video = db.scalar(
        select(YoutubePublishTask).where(
            YoutubePublishTask.channel_id == command.channel_id,
            YoutubePublishTask.publishable_video_id
            == command.publishable_video_id,
        )
    )
    if existing_video is not None:
        raise YoutubePublishingConflict("该视频已经提交到这个频道，不能重复发布")

    channel = db.get(YoutubeChannel, command.channel_id)
    if channel is None:
        raise YoutubePublishingError("YouTube 频道不存在")
    if channel.remote_status != "normal":
        raise YoutubePublishingForbidden("当前 YouTube 频道状态不可发布")
    publishable = db.scalar(
        select(PublishableVideo)
        .options(selectinload(PublishableVideo.source_native_agent_video))
        .where(
            PublishableVideo.id == command.publishable_video_id,
            PublishableVideo.owner_user_id == command.owner_user_id,
        )
    )
    if publishable is None:
        raise YoutubePublishingError("可发布视频不存在")
    if publishable.review_status != "approved":
        raise YoutubePublishingForbidden("视频尚未审核通过，不能发布")
    if not publishable.video_url.startswith(("http://", "https://")):
        raise YoutubePublishingForbidden("视频没有可访问的公网 URL")

    now = datetime.utcnow()
    planned_at = _utc_naive(
        command.planned_publish_at
        or publishable.planned_publish_at
        or now
    )
    task = YoutubePublishTask(
        owner_user_id=command.owner_user_id,
        channel_id=channel.id,
        publishable_video_id=publishable.id,
        source_native_agent_video_id=publishable.source_native_agent_video_id,
        idempotency_key=command.idempotency_key,
        status="submitting",
        title_snapshot=publishable.title,
        description_snapshot=publishable.description,
        tags_json=publishable.tags_json,
        thumbnail_url_snapshot=publishable.thumbnail_url,
        video_url_snapshot=publishable.video_url,
        visibility_snapshot=command.visibility,
        contains_synthetic_media_snapshot=publishable.contains_synthetic_media,
        planned_publish_at=planned_at,
        notify_subscribers=command.notify_subscribers,
        confirmed_at=now,
    )
    db.add(task)
    db.commit()
    db.refresh(task)

    publisher = client or YoutubePublisherClient()
    try:
        remote = publisher.create_upload_task(_create_payload(task, channel))
    except YoutubePublisherRequestRejected as exc:
        task.status = "failed"
        task.error_code = "RemoteRequestRejected"
        task.error_message = str(exc)
        db.commit()
        return task
    except YoutubePublisherOutcomeUnknown as exc:
        task.status = "outcome_unknown"
        task.error_code = "RemoteOutcomeUnknown"
        task.error_message = str(exc)
        db.commit()
        return task

    remote_task_id = str(remote.get("id") or "").strip()
    if not remote_task_id:
        task.status = "outcome_unknown"
        task.error_code = "RemoteTaskIdMissing"
        task.error_message = "远程创建响应没有任务 ID，结果不明确"
        task.remote_payload_json = json.dumps(remote, ensure_ascii=False)
        db.commit()
        return task
    task.remote_task_id = remote_task_id
    task.remote_status = str(remote.get("task_status") or "pending")
    task.status = _local_status(task.remote_status, remote.get("last_run_error"))
    task.remote_payload_json = json.dumps(remote, ensure_ascii=False)
    task.error_message = remote.get("last_run_error")
    db.commit()
    db.refresh(task)
    return task


def _local_status(remote_status: str, remote_error: object) -> str:
    if remote_status == "pending":
        return "pending"
    if remote_status == "running":
        return "running"
    if remote_status == "completed":
        return "succeeded"
    if remote_status == "cancelled":
        error = str(remote_error or "").strip()
        normalized = error.lower()
        if not error or any(
            marker in normalized
            for marker in ("cancel by user", "user cancelled", "manual cancel", "用户取消", "手动取消")
        ):
            return "cancelled"
        return "failed"
    return "outcome_unknown"


def refresh_youtube_publish_task(
    db: Session,
    task: YoutubePublishTask,
    *,
    client: YoutubePublisherClient | None = None,
) -> YoutubePublishTask:
    if not task.remote_task_id:
        raise YoutubePublishingConflict("远程任务 ID 缺失，不能安全查询状态")
    publisher = client or YoutubePublisherClient()
    try:
        remote = publisher.upload_task(task.remote_task_id)
    except (YoutubePublisherRequestRejected, YoutubePublisherOutcomeUnknown) as exc:
        task.error_code = type(exc).__name__
        task.error_message = str(exc)
        task.last_status_checked_at = datetime.utcnow()
        db.commit()
        return task

    now = datetime.utcnow()
    task.remote_status = str(remote.get("task_status") or "")
    task.status = _local_status(task.remote_status, remote.get("last_run_error"))
    task.error_code = None
    task.error_message = remote.get("last_run_error")
    task.last_status_checked_at = now
    task.remote_payload_json = json.dumps(remote, ensure_ascii=False)
    youtube_video_id = str(remote.get("youtube_video_id") or "").strip() or None
    if task.status == "succeeded":
        if youtube_video_id is None:
            task.status = "outcome_unknown"
            task.error_code = "CompletedVideoIdMissing"
            task.error_message = "远程任务已完成，但没有返回 YouTube 视频 ID"
        else:
            task.youtube_video_id = youtube_video_id
            task.youtube_url = f"https://www.youtube.com/watch?v={youtube_video_id}"
            task.completed_at = (
                _remote_time(remote.get("updated_at"))
                or _remote_time(remote.get("last_run_at"))
                or now
            )
            uploaded = db.scalar(
                select(YoutubeUploadedVideo).where(
                    YoutubeUploadedVideo.youtube_video_id == youtube_video_id
                )
            )
            if uploaded is None:
                uploaded = YoutubeUploadedVideo(
                    channel_id=task.channel_id,
                    youtube_video_id=youtube_video_id,
                    uploaded_at=task.completed_at,
                )
                db.add(uploaded)
            elif uploaded.channel_id != task.channel_id:
                raise YoutubePublishingConflict("远程视频已关联到其他频道")
            uploaded.remote_upload_task_id = task.remote_task_id
            uploaded.publish_task_id = task.id
            uploaded.source_native_agent_video_id = (
                task.source_native_agent_video_id
            )
            uploaded.title = task.title_snapshot
            uploaded.description = task.description_snapshot
            uploaded.tags_json = task.tags_json
            uploaded.visibility = task.visibility_snapshot
            uploaded.remote_last_sync_at = now
    db.commit()
    db.refresh(task)
    return task
