from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import hashlib
import json
from pathlib import Path
import subprocess
from typing import Any, Callable

import requests
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.entities import (
    AgentSkillVersion,
    FileAsset,
    NativeAgentConversation,
    NativeAgentRun,
    NativeAgentVideo,
    PublishableVideo,
    User,
    YoutubeChannel,
    YoutubePublishTask,
)
from app.models.enums import AgentRunStatus, FileAssetPurpose, UserRole
from app.services.storage import (
    StoredFile,
    asset_content_url,
    save_binary_file,
)
from app.services.youtube_publisher import YoutubePublisherClient
from app.services.youtube_publishing import (
    YoutubePublishCommand,
    create_youtube_publish_task,
    refresh_youtube_publish_task,
)


EXPECTED_ACCEPTANCE_STATUS = "ready_for_user_manual_upload_footerless"
IMPORT_KIND = "reviewed_local_video_import"


class ReviewedLocalVideoPublicationError(RuntimeError):
    pass


@dataclass(frozen=True)
class ReviewedVideoFacts:
    acceptance_path: str
    source_video_path: str
    checksum_sha256: str
    byte_size: int
    duration_ms: int
    frames: int
    width: int
    height: int
    fps: int
    video_codec: str
    audio_codec: str
    pixel_format: str


@dataclass(frozen=True)
class RankedChannel:
    channel_id: str
    title: str
    status: str
    published_video_count: int
    remote: dict[str, Any]


@dataclass(frozen=True)
class RegisteredPublication:
    asset_id: str
    native_agent_video_id: str
    publishable_video_id: str
    channel_pk: str
    publish_task_id: str
    remote_task_id: str | None
    status: str
    youtube_video_id: str | None
    youtube_url: str | None


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _ffprobe(path: Path) -> dict[str, Any]:
    executable = get_settings().ffprobe_executable
    completed = subprocess.run(
        [
            executable,
            "-v",
            "error",
            "-count_frames",
            "-show_streams",
            "-show_format",
            "-of",
            "json",
            str(path),
        ],
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    if completed.returncode != 0:
        raise ReviewedLocalVideoPublicationError(
            f"ffprobe 失败：{completed.stderr.strip()[-1000:]}"
        )
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise ReviewedLocalVideoPublicationError("ffprobe 返回了无效 JSON") from exc
    if not isinstance(payload, dict):
        raise ReviewedLocalVideoPublicationError("ffprobe 返回结构不正确")
    return payload


def _stream(probe: dict[str, Any], codec_type: str) -> dict[str, Any]:
    rows = [
        item
        for item in probe.get("streams", [])
        if isinstance(item, dict) and item.get("codec_type") == codec_type
    ]
    if len(rows) != 1:
        raise ReviewedLocalVideoPublicationError(
            f"最终视频必须恰好包含一个 {codec_type} 流"
        )
    return rows[0]


def _integer_frame_rate(value: object) -> int:
    text = str(value or "")
    try:
        numerator, denominator = text.split("/", maxsplit=1)
        result = float(numerator) / float(denominator)
    except (ValueError, ZeroDivisionError) as exc:
        raise ReviewedLocalVideoPublicationError("视频帧率无效") from exc
    rounded = round(result)
    if abs(result - rounded) > 0.01:
        raise ReviewedLocalVideoPublicationError("视频帧率不是整数")
    return rounded


def load_reviewed_video_facts(
    project_root: Path,
    *,
    acceptance_path: Path,
    video_path: Path,
) -> ReviewedVideoFacts:
    if not acceptance_path.is_file():
        raise ReviewedLocalVideoPublicationError("Sprint 203 acceptance 文件不存在")
    if not video_path.is_file():
        raise ReviewedLocalVideoPublicationError("待发布 MP4 不存在")
    try:
        acceptance = json.loads(acceptance_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ReviewedLocalVideoPublicationError("Sprint 203 acceptance 无法读取") from exc
    if acceptance.get("status") != EXPECTED_ACCEPTANCE_STATUS:
        raise ReviewedLocalVideoPublicationError("Sprint 203 acceptance 尚未进入可手动发布终态")
    render = acceptance.get("render")
    if not isinstance(render, dict):
        raise ReviewedLocalVideoPublicationError("Sprint 203 acceptance 缺少 render")
    expected_relative = str(render.get("video") or "")
    try:
        actual_relative = video_path.resolve().relative_to(project_root.resolve()).as_posix()
        acceptance_relative = acceptance_path.resolve().relative_to(
            project_root.resolve()
        ).as_posix()
    except ValueError as exc:
        raise ReviewedLocalVideoPublicationError("验收文件和视频必须位于项目目录内") from exc
    if expected_relative != actual_relative:
        raise ReviewedLocalVideoPublicationError("待发布 MP4 不是 acceptance 锁定的文件")
    actual_sha256 = sha256_file(video_path)
    actual_size = video_path.stat().st_size
    if actual_sha256 != render.get("sha256"):
        raise ReviewedLocalVideoPublicationError("待发布 MP4 SHA-256 与 acceptance 不一致")
    if actual_size != int(render.get("bytes") or 0):
        raise ReviewedLocalVideoPublicationError("待发布 MP4 大小与 acceptance 不一致")

    probe = _ffprobe(video_path)
    video = _stream(probe, "video")
    audio = _stream(probe, "audio")
    format_row = probe.get("format") if isinstance(probe.get("format"), dict) else {}
    duration_ms = round(float(format_row.get("duration") or 0) * 1000)
    frames = int(video.get("nb_read_frames") or 0)
    facts = ReviewedVideoFacts(
        acceptance_path=acceptance_relative,
        source_video_path=actual_relative,
        checksum_sha256=actual_sha256,
        byte_size=actual_size,
        duration_ms=duration_ms,
        frames=frames,
        width=int(video.get("width") or 0),
        height=int(video.get("height") or 0),
        fps=_integer_frame_rate(video.get("avg_frame_rate")),
        video_codec=str(video.get("codec_name") or ""),
        audio_codec=str(audio.get("codec_name") or ""),
        pixel_format=str(video.get("pix_fmt") or ""),
    )
    expected = {
        "duration_ms": int(render.get("duration_ms") or 0),
        "frames": int(render.get("frames") or 0),
        "width": int(render.get("width") or 0),
        "height": int(render.get("height") or 0),
        "fps": int(render.get("fps") or 0),
        "video_codec": str(render.get("video_codec") or ""),
        "audio_codec": str(render.get("audio_codec") or ""),
        "pixel_format": str(render.get("pixel_format") or ""),
    }
    observed = {
        "duration_ms": facts.duration_ms,
        "frames": facts.frames,
        "width": facts.width,
        "height": facts.height,
        "fps": facts.fps,
        "video_codec": facts.video_codec,
        "audio_codec": facts.audio_codec,
        "pixel_format": facts.pixel_format,
    }
    mismatches = [
        name
        for name, expected_value in expected.items()
        if (
            abs(observed[name] - expected_value) > 10
            if name == "duration_ms"
            else observed[name] != expected_value
        )
    ]
    if mismatches:
        raise ReviewedLocalVideoPublicationError(
            f"待发布 MP4 媒体事实与 acceptance 不一致：{', '.join(mismatches)}"
        )
    return facts


def rank_normal_channels(
    client: YoutubePublisherClient,
) -> list[RankedChannel]:
    ranked: list[RankedChannel] = []
    for remote in client.list_channels():
        channel_id = str(remote.get("channel_id") or "").strip()
        status = str(remote.get("status") or "unknown")
        if not channel_id or status != "normal":
            continue
        ranked.append(
            RankedChannel(
                channel_id=channel_id,
                title=str(remote.get("title") or channel_id),
                status=status,
                published_video_count=len(client.channel_videos(channel_id)),
                remote=remote,
            )
        )
    if not ranked:
        raise ReviewedLocalVideoPublicationError("发布服务没有状态正常的频道")
    return sorted(
        ranked,
        key=lambda item: (item.published_video_count, item.channel_id),
    )


def require_single_admin(db: Session) -> User:
    rows = db.scalars(select(User).where(User.role == UserRole.admin)).all()
    if len(rows) != 1:
        raise ReviewedLocalVideoPublicationError(
            "本次受控导入要求本地数据库恰好存在一个 Admin"
        )
    return rows[0]


def require_import_skill_version(db: Session) -> AgentSkillVersion:
    rows = db.scalars(
        select(AgentSkillVersion)
        .where(AgentSkillVersion.name_snapshot.like("Paynes Creek S03%"))
        .order_by(AgentSkillVersion.published_at.desc())
    ).all()
    if len(rows) != 1:
        raise ReviewedLocalVideoPublicationError(
            "本次受控导入要求唯一的 Paynes Creek Skill Version"
        )
    return rows[0]


def upsert_target_channel(
    db: Session,
    ranked: RankedChannel,
) -> YoutubeChannel:
    channel = db.scalar(
        select(YoutubeChannel).where(YoutubeChannel.channel_id == ranked.channel_id)
    )
    if channel is None:
        channel = YoutubeChannel(
            channel_id=ranked.channel_id,
            title=ranked.title,
            remote_status=ranked.status,
        )
        db.add(channel)
    remote = ranked.remote
    channel.title = ranked.title
    channel.handle = remote.get("handle")
    channel.avatar_url = remote.get("avatar_url") or remote.get("thumbnail_url")
    channel.account_email = remote.get("youtube_account_email") or remote.get("email")
    channel.remote_status = ranked.status
    channel.total_videos = ranked.published_video_count
    channel.last_sync_error = None
    channel.last_sync_success_at = datetime.utcnow()
    db.commit()
    db.refresh(channel)
    return channel


def _verify_public_video_url(url: str) -> None:
    try:
        response = requests.get(
            url,
            headers={"Range": "bytes=0-0"},
            timeout=30,
            allow_redirects=True,
        )
    except requests.RequestException as exc:
        raise ReviewedLocalVideoPublicationError("OSS 视频公网读取失败") from exc
    if response.status_code not in {200, 206}:
        raise ReviewedLocalVideoPublicationError(
            f"OSS 视频公网读取返回 HTTP {response.status_code}"
        )


def register_reviewed_video(
    db: Session,
    *,
    owner: User,
    skill_version: AgentSkillVersion,
    facts: ReviewedVideoFacts,
    video_path: Path,
    source_git_commit: str,
    title: str,
    description: str,
    tags: list[str],
    store_file: Callable[[str, bytes, str], StoredFile] = save_binary_file,
) -> tuple[FileAsset, NativeAgentVideo, PublishableVideo]:
    asset = db.scalar(
        select(FileAsset).where(
            FileAsset.purpose == FileAssetPurpose.generated_video,
            FileAsset.checksum_sha256 == facts.checksum_sha256,
            FileAsset.byte_size == facts.byte_size,
        )
    )
    if asset is None:
        stored = store_file(
            FileAssetPurpose.generated_video.value,
            video_path.read_bytes(),
            ".mp4",
        )
        asset = FileAsset(
            purpose=FileAssetPurpose.generated_video,
            storage_backend=stored.storage_backend,
            storage_key=stored.storage_key,
            public_url=stored.public_url,
            original_filename=video_path.name,
            content_type="video/mp4",
            byte_size=stored.byte_size,
            checksum_sha256=stored.checksum_sha256,
            width=facts.width,
            height=facts.height,
        )
        db.add(asset)
        db.commit()
        db.refresh(asset)
    if asset.checksum_sha256 != facts.checksum_sha256:
        raise ReviewedLocalVideoPublicationError("已登记资产 hash 与验收视频不一致")
    video_url = asset_content_url(asset)
    _verify_public_video_url(video_url)

    video = db.scalar(
        select(NativeAgentVideo).where(NativeAgentVideo.asset_id == asset.id)
    )
    if video is None:
        now = datetime.utcnow()
        conversation = NativeAgentConversation(
            owner_user_id=owner.id,
            title=f"Paynes Creek reviewed import · {facts.checksum_sha256[:12]}",
        )
        db.add(conversation)
        db.flush()
        run = NativeAgentRun(
            conversation_id=conversation.id,
            skill_version_id=skill_version.id,
            status=AgentRunStatus.succeeded,
            model_snapshot="none:reviewed-local-video-import",
            model_route_snapshot="local_import",
            model_provider_snapshot="none",
            model_api_shape_snapshot="none",
            skill_name_snapshot=skill_version.name_snapshot,
            skill_version_snapshot=skill_version.version,
            skill_content_hash_snapshot=skill_version.content_hash,
            model_call_count=0,
            image_call_count=0,
            speech_call_count=0,
            subtitle_call_count=0,
            video_call_count=0,
            final_output=(
                "Imported one already reviewed local video without model or media "
                f"provider calls. Acceptance: {facts.acceptance_path}."
            ),
            started_at=now,
            finished_at=now,
        )
        db.add(run)
        db.flush()
        provenance = [
            {
                "kind": IMPORT_KIND,
                "source_git_commit": source_git_commit,
                "source_acceptance": facts.acceptance_path,
                "source_video": facts.source_video_path,
                "source_video_sha256": facts.checksum_sha256,
                "provider_calls": 0,
            }
        ]
        video = NativeAgentVideo(
            run_id=run.id,
            asset_id=asset.id,
            bgm_asset_id=None,
            template_id_snapshot="paynes-creek-grok-ai-short-v1",
            renderer_version_snapshot="sprint-203-v2",
            scenes_json=json.dumps(provenance, ensure_ascii=False),
            duration_ms=facts.duration_ms,
            duration_in_frames=facts.frames,
            fps=facts.fps,
            width=facts.width,
            height=facts.height,
        )
        db.add(video)
        db.commit()
        db.refresh(video)
    elif video.run.conversation.owner_user_id != owner.id:
        raise ReviewedLocalVideoPublicationError("已登记视频不属于本次 Admin")

    publishable = db.scalar(
        select(PublishableVideo).where(
            PublishableVideo.source_native_agent_video_id == video.id
        )
    )
    expected_tags_json = json.dumps(tags, ensure_ascii=False)
    if publishable is None:
        publishable = PublishableVideo(
            owner_user_id=owner.id,
            source_native_agent_video_id=video.id,
            video_url=video_url,
            thumbnail_url=None,
            title=title,
            description=description,
            tags_json=expected_tags_json,
            planned_publish_at=None,
            contains_synthetic_media=True,
            review_status="approved",
        )
        db.add(publishable)
        db.commit()
        db.refresh(publishable)
    else:
        expected = (
            owner.id,
            video_url,
            title,
            description,
            expected_tags_json,
            True,
            "approved",
        )
        observed = (
            publishable.owner_user_id,
            publishable.video_url,
            publishable.title,
            publishable.description,
            publishable.tags_json,
            publishable.contains_synthetic_media,
            publishable.review_status,
        )
        if observed != expected:
            raise ReviewedLocalVideoPublicationError(
                "既有可发布视频元数据与本次冻结参数不一致"
            )
    return asset, video, publishable


def submit_publication(
    db: Session,
    *,
    owner: User,
    channel: YoutubeChannel,
    publishable: PublishableVideo,
    idempotency_key: str,
    client: YoutubePublisherClient,
) -> YoutubePublishTask:
    return create_youtube_publish_task(
        db,
        YoutubePublishCommand(
            owner_user_id=owner.id,
            channel_id=channel.id,
            publishable_video_id=publishable.id,
            visibility="public",
            planned_publish_at=None,
            notify_subscribers=False,
            confirmed=True,
            idempotency_key=idempotency_key,
        ),
        client=client,
    )


def refresh_publication(
    db: Session,
    *,
    task_id: str,
    client: YoutubePublisherClient,
) -> YoutubePublishTask:
    task = db.get(YoutubePublishTask, task_id)
    if task is None:
        raise ReviewedLocalVideoPublicationError("本地 YouTube 发布任务不存在")
    if task.status in {"succeeded", "failed", "cancelled", "outcome_unknown"}:
        return task
    return refresh_youtube_publish_task(db, task, client=client)


def publication_result(
    *,
    asset: FileAsset,
    video: NativeAgentVideo,
    publishable: PublishableVideo,
    channel: YoutubeChannel,
    task: YoutubePublishTask,
) -> RegisteredPublication:
    return RegisteredPublication(
        asset_id=asset.id,
        native_agent_video_id=video.id,
        publishable_video_id=publishable.id,
        channel_pk=channel.id,
        publish_task_id=task.id,
        remote_task_id=task.remote_task_id,
        status=task.status,
        youtube_video_id=task.youtube_video_id,
        youtube_url=task.youtube_url,
    )
