from __future__ import annotations

import asyncio
import json
import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.models.entities import (
    AudioReference,
    FileAsset,
    GeneratedImage,
    GenerationTask,
    TaskPanel,
    VideoTask,
    VideoTaskAudioSegment,
)
from app.models.enums import (
    FileAssetPurpose,
    GeneratedImageJobKind,
    GeneratedImageStatus,
    TaskStatus,
    VideoTaskStatus,
    VideoTaskStepName,
)
from app.services.comic_video import ComicVideoServiceClient
from app.services.siliconflow_voice import SiliconFlowVoiceClient
from app.services.storage import materialize_asset_to_local, save_binary_file

logger = logging.getLogger(__name__)

_queue: asyncio.Queue[str] | None = None
_queue_loop: asyncio.AbstractEventLoop | None = None
_worker_tasks: list[asyncio.Task] = []
_running_video_task_ids: set[str] = set()
_running_video_task_ids_lock: asyncio.Lock | None = None


def init_video_task_queue() -> None:
    global _queue, _queue_loop, _worker_tasks, _running_video_task_ids_lock
    settings = get_settings()
    _queue_loop = asyncio.get_running_loop()
    _queue = asyncio.Queue()
    _running_video_task_ids.clear()
    _running_video_task_ids_lock = asyncio.Lock()
    _worker_tasks = [
        asyncio.create_task(video_task_worker_loop(worker_index=worker_index))
        for worker_index in range(settings.video_task_worker_concurrency)
    ]
    logger.info("video task queue initialized worker_count=%s", len(_worker_tasks))


async def shutdown_video_task_queue() -> None:
    global _queue, _queue_loop, _worker_tasks, _running_video_task_ids_lock
    if not _worker_tasks:
        return
    for worker_task in _worker_tasks:
        worker_task.cancel()
    await asyncio.gather(*_worker_tasks, return_exceptions=True)
    _worker_tasks = []
    _running_video_task_ids.clear()
    _running_video_task_ids_lock = None
    _queue = None
    _queue_loop = None
    logger.info("video task queue shutdown complete")


async def enqueue_video_task(video_task_id: str) -> None:
    if _queue is None:
        raise RuntimeError("视频任务队列尚未初始化")
    await _queue.put(video_task_id)
    logger.info("video task enqueued video_task_id=%s queue_size=%s", video_task_id, _queue.qsize())


def enqueue_video_task_from_thread(video_task_id: str) -> None:
    if _queue_loop is None:
        raise RuntimeError("视频任务队列事件循环尚未初始化")
    future = asyncio.run_coroutine_threadsafe(enqueue_video_task(video_task_id), _queue_loop)
    future.result(timeout=5)


async def video_task_worker_loop(*, worker_index: int) -> None:
    if _queue is None or _running_video_task_ids_lock is None:
        raise RuntimeError("视频任务队列尚未初始化")
    logger.info("video task worker loop started worker_index=%s", worker_index)
    while True:
        video_task_id = await _queue.get()
        try:
            async with _running_video_task_ids_lock:
                if video_task_id in _running_video_task_ids:
                    logger.info("video task already running video_task_id=%s", video_task_id)
                    continue
                _running_video_task_ids.add(video_task_id)
            await asyncio.to_thread(process_video_task, video_task_id)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("video task worker failed video_task_id=%s", video_task_id)
            mark_video_task_failed_by_unhandled_error(video_task_id)
        finally:
            async with _running_video_task_ids_lock:
                _running_video_task_ids.discard(video_task_id)
            _queue.task_done()


def load_video_task(db: Session, video_task_id: str) -> VideoTask | None:
    return db.scalar(
        select(VideoTask)
        .where(VideoTask.id == video_task_id)
        .options(
            selectinload(VideoTask.source_task).selectinload(GenerationTask.panels),
            selectinload(VideoTask.source_task).selectinload(GenerationTask.generated_images).selectinload(GeneratedImage.asset),
            selectinload(VideoTask.audio_reference),
            selectinload(VideoTask.audio_reference_asset_snapshot),
            selectinload(VideoTask.audio_segments).selectinload(VideoTaskAudioSegment.asset),
            selectinload(VideoTask.narration_audio_asset),
            selectinload(VideoTask.output_video_asset),
        )
    )


def sync_video_task_source_state(video_task: VideoTask) -> bool:
    source = video_task.source_task
    if video_task.status not in {
        VideoTaskStatus.waiting_for_images,
        VideoTaskStatus.ready_for_audio,
        VideoTaskStatus.audio_generating,
        VideoTaskStatus.audio_ready,
        VideoTaskStatus.video_generating,
    }:
        return False
    if source.status in {TaskStatus.failed, TaskStatus.cancelled, TaskStatus.cancel_requested}:
        video_task.status = VideoTaskStatus.failed
        video_task.current_step = VideoTaskStepName.generate_source_images
        video_task.progress_current = 0
        video_task.error_code = source.error_code or "SourceImageTaskFailed"
        video_task.error_message = source.error_message or "上游图片任务失败，无法继续生成视频"
        video_task.finished_at = datetime.utcnow()
        return True
    if source.status == TaskStatus.partial_succeeded:
        video_task.status = VideoTaskStatus.failed
        video_task.current_step = VideoTaskStepName.generate_source_images
        video_task.progress_current = 0
        video_task.error_code = "SourceImageTaskPartialSucceeded"
        video_task.error_message = "上游图片任务只有部分图片成功，无法继续生成视频"
        video_task.finished_at = datetime.utcnow()
        return True
    if source.status == TaskStatus.succeeded and video_task.status == VideoTaskStatus.waiting_for_images:
        video_task.status = VideoTaskStatus.ready_for_audio
        video_task.current_step = VideoTaskStepName.generate_narration_audio
        video_task.progress_current = 1
        video_task.error_code = None
        video_task.error_message = None
        return True
    return False


def trigger_video_tasks_for_source_task(source_task_id: str) -> None:
    with SessionLocal() as db:
        video_tasks = db.scalars(
            select(VideoTask)
            .where(VideoTask.source_task_id == source_task_id)
            .options(selectinload(VideoTask.source_task))
        ).all()
        enqueue_ids: list[str] = []
        for video_task in video_tasks:
            changed = sync_video_task_source_state(video_task)
            if changed and video_task.status == VideoTaskStatus.ready_for_audio:
                enqueue_ids.append(video_task.id)
        db.commit()
    for video_task_id in enqueue_ids:
        enqueue_video_task_from_thread(video_task_id)


async def recover_video_tasks() -> None:
    if _queue is None:
        raise RuntimeError("视频任务队列尚未初始化")
    with SessionLocal() as db:
        video_tasks = db.scalars(
            select(VideoTask)
            .where(
                VideoTask.status.in_(
                    [
                        VideoTaskStatus.waiting_for_images,
                        VideoTaskStatus.ready_for_audio,
                        VideoTaskStatus.audio_generating,
                        VideoTaskStatus.audio_ready,
                        VideoTaskStatus.video_generating,
                    ]
                )
            )
            .options(selectinload(VideoTask.source_task))
            .order_by(VideoTask.created_at.asc())
        ).all()
        enqueue_ids: list[str] = []
        for video_task in video_tasks:
            sync_video_task_source_state(video_task)
            if video_task.status == VideoTaskStatus.audio_generating:
                video_task.status = VideoTaskStatus.ready_for_audio
                video_task.current_step = VideoTaskStepName.generate_narration_audio
            if video_task.status in {VideoTaskStatus.ready_for_audio, VideoTaskStatus.audio_ready, VideoTaskStatus.video_generating}:
                enqueue_ids.append(video_task.id)
        db.commit()
    for video_task_id in enqueue_ids:
        await _queue.put(video_task_id)
    logger.info("recovered video tasks count=%s", len(enqueue_ids))


def current_panel_images(source_task: GenerationTask) -> dict[str, GeneratedImage]:
    images_by_panel: dict[str, GeneratedImage] = {}
    for image in source_task.generated_images:
        if (
            image.job_kind != GeneratedImageJobKind.panel_image
            or image.status != GeneratedImageStatus.succeeded
            or not image.is_current
            or image.asset is None
            or image.panel_id is None
        ):
            continue
        existing = images_by_panel.get(image.panel_id)
        if existing is None or image.generation_number > existing.generation_number:
            images_by_panel[image.panel_id] = image
    return images_by_panel


def parse_image_text_json(value: str | None) -> dict[str, str | None]:
    if not value:
        return {}
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return {}
    if not isinstance(parsed, dict):
        return {}
    return {str(key): str(item) if item is not None else None for key, item in parsed.items()}


def narration_text_for_panel(panel: TaskPanel) -> str:
    image_text = parse_image_text_json(panel.image_text_json)
    text = (
        panel.narration_text
        or image_text.get("narration")
        or panel.original_text_segment
        or ""
    )
    return sanitize_narration_text(text)


def sanitize_narration_text(text: str) -> str:
    cleaned = re.sub(r"[【】《》「」『』（）()#*_`]+", "", text or "")
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


def subtitle_text(text: str) -> str:
    cleaned = re.sub(r"[，。！？!?；;：:“”\"'、,.…—\-]+", " ", text or "")
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned or text.strip()


def file_suffix_for_audio(content_type: str, response_format: str) -> str:
    normalized = content_type.lower()
    if "wav" in normalized:
        return ".wav"
    if "ogg" in normalized or "opus" in normalized:
        return ".ogg"
    if response_format:
        return f".{response_format.lstrip('.')}"
    return ".mp3"


def create_asset_from_stored_file(
    db: Session,
    *,
    purpose: FileAssetPurpose,
    content: bytes,
    suffix: str,
    content_type: str,
    original_filename: str,
) -> FileAsset:
    stored = save_binary_file(purpose.value, content, suffix)
    asset = FileAsset(
        purpose=purpose,
        storage_backend=stored.storage_backend,
        storage_key=stored.storage_key,
        public_url=stored.public_url,
        original_filename=original_filename,
        content_type=content_type,
        byte_size=stored.byte_size,
        checksum_sha256=stored.checksum_sha256,
    )
    db.add(asset)
    db.flush()
    return asset


def resolve_voice_config(db: Session, video_task: VideoTask) -> tuple[str, str, str]:
    settings = get_settings()
    provider = (video_task.voice_provider_snapshot or "").strip()
    model = (video_task.voice_model_snapshot or "").strip()
    voice_name = (video_task.voice_name_snapshot or "").strip()
    reference = video_task.audio_reference
    if reference:
        provider = provider or (reference.voice_provider or "").strip()
        model = model or (reference.voice_model or "").strip()
        voice_name = voice_name or (reference.voice_name or "").strip()
    provider = provider or settings.video_tts_provider.strip()
    model = model or settings.video_tts_model.strip()
    if provider != "siliconflow":
        raise RuntimeError(f"暂不支持的视频任务 TTS provider：{provider}")
    video_task.voice_provider_snapshot = provider
    video_task.voice_model_snapshot = model
    if voice_name:
        video_task.voice_name_snapshot = voice_name
        return provider, model, voice_name

    reference_text = (video_task.audio_reference_text_snapshot or "").strip()
    if not reference_text:
        raise RuntimeError("参考音频缺少参考文本，无法注册声音")
    reference_path = materialize_asset_to_local(video_task.audio_reference_asset_snapshot)
    voice_client = SiliconFlowVoiceClient()
    custom_name = f"doodlestory_{video_task.audio_reference_id}_{video_task.id[:8]}"
    voice_name = voice_client.upload_reference_voice(
        file_path=reference_path,
        model=model,
        custom_name=custom_name,
        text=reference_text,
        timeout=settings.video_tts_timeout_seconds,
    )
    video_task.voice_name_snapshot = voice_name
    if reference and not reference.voice_name:
        reference.voice_provider = provider
        reference.voice_model = model
        reference.voice_name = voice_name
    db.commit()
    return provider, model, voice_name


def generate_audio_segments(db: Session, video_task: VideoTask) -> None:
    settings = get_settings()
    _, model, voice_name = resolve_voice_config(db, video_task)
    source_task = video_task.source_task
    images = current_panel_images(source_task)
    panels = sorted(source_task.panels, key=lambda item: item.panel_order)
    if not panels:
        raise RuntimeError("上游图片任务没有分镜，无法生成视频")
    if len(images) != len(panels):
        raise RuntimeError(f"上游图片数量不完整：当前 {len(images)} / 共 {len(panels)} 张")
    existing_by_panel_id = {segment.panel_id: segment for segment in video_task.audio_segments}
    voice_client = SiliconFlowVoiceClient()
    first_asset_id: str | None = video_task.narration_audio_asset_id
    for panel in panels:
        if panel.id in existing_by_panel_id:
            first_asset_id = first_asset_id or existing_by_panel_id[panel.id].asset_id
            continue
        text = narration_text_for_panel(panel)
        if not text:
            raise RuntimeError(f"第 {panel.panel_order} 个分镜缺少可用旁白文本")
        audio_bytes, content_type = voice_client.generate_speech(
            text=text,
            voice_uri=voice_name,
            model=model,
            response_format=settings.video_tts_response_format,
            sample_rate=settings.video_tts_sample_rate,
            speed=video_task.voice_speed_snapshot,
            gain=settings.video_tts_gain,
            timeout=settings.video_tts_timeout_seconds,
        )
        suffix = file_suffix_for_audio(content_type, settings.video_tts_response_format)
        asset = create_asset_from_stored_file(
            db,
            purpose=FileAssetPurpose.generated_audio,
            content=audio_bytes,
            suffix=suffix,
            content_type=content_type or "audio/mpeg",
            original_filename=f"{video_task.id}-panel-{panel.panel_order}{suffix}",
        )
        segment = VideoTaskAudioSegment(
            video_task_id=video_task.id,
            panel_id=panel.id,
            panel_order=panel.panel_order,
            narration_text=text,
            asset_id=asset.id,
        )
        db.add(segment)
        first_asset_id = first_asset_id or asset.id
        video_task.narration_audio_asset_id = first_asset_id
        db.commit()
        db.refresh(video_task)


def build_episode(video_task: VideoTask) -> dict[str, Any]:
    settings = get_settings()
    source_task = video_task.source_task
    images = current_panel_images(source_task)
    audio_by_panel_id = {segment.panel_id: segment for segment in video_task.audio_segments}
    shots: list[dict[str, Any]] = []
    for panel in sorted(source_task.panels, key=lambda item: item.panel_order):
        image = images.get(panel.id)
        audio = audio_by_panel_id.get(panel.id)
        if image is None or image.asset is None:
            raise RuntimeError(f"第 {panel.panel_order} 个分镜缺少当前图片资产")
        if audio is None or audio.asset is None:
            raise RuntimeError(f"第 {panel.panel_order} 个分镜缺少旁白音频资产")
        image_path = materialize_asset_to_local(image.asset)
        audio_path = materialize_asset_to_local(audio.asset)
        text = audio.narration_text or narration_text_for_panel(panel)
        shots.append(
            {
                "id": f"{panel.panel_order:03d}",
                "image": str(image_path),
                "audio": str(audio_path),
                "text": subtitle_text(text),
                "emphasis": [],
                "emotion": "calm",
                "camera": "push-in-slow",
                "effects": [],
                "transition": {"type": "fade", "duration": 0.25},
            }
        )
    return {
        "version": "1.0",
        "title": video_task.display_title,
        "theme": settings.comic_video_episode_theme,
        "resolution": {"width": settings.comic_video_episode_width, "height": settings.comic_video_episode_height},
        "fps": settings.comic_video_episode_fps,
        "shots": shots,
    }


def render_video(db: Session, video_task: VideoTask) -> None:
    settings = get_settings()
    episode = build_episode(video_task)
    video_task.video_episode_json = json.dumps(episode, ensure_ascii=False)
    db.commit()
    client = ComicVideoServiceClient()
    output_name = f"doodlestory-{video_task.id}"
    job_id = (video_task.video_provider_job_id or "").strip()
    if not job_id:
        job_id = client.submit_episode(
            episode=episode,
            output_name=output_name,
            speed=settings.comic_video_speed,
        )
        video_task.video_provider_job_id = job_id
        video_task.video_provider_status = "queued"
        db.commit()
    result = client.poll_job(
        job_id,
        timeout_seconds=settings.comic_video_poll_timeout_seconds,
        interval_seconds=settings.comic_video_poll_interval_seconds,
    )
    output_url = str(result.get("output_url") or "").strip()
    video_bytes = client.download_output(output_url)
    asset = create_asset_from_stored_file(
        db,
        purpose=FileAssetPurpose.generated_video,
        content=video_bytes,
        suffix=".mp4",
        content_type="video/mp4",
        original_filename=f"{output_name}.mp4",
    )
    video_task.output_video_asset_id = asset.id
    video_task.video_provider_status = str(result.get("status") or "succeeded")
    video_task.video_provider_output_url = output_url
    video_task.video_provider_result_json = json.dumps(result, ensure_ascii=False)


def process_video_task(video_task_id: str) -> None:
    with SessionLocal() as db:
        video_task = load_video_task(db, video_task_id)
        if video_task is None or video_task.status in {
            VideoTaskStatus.succeeded,
            VideoTaskStatus.failed,
            VideoTaskStatus.cancelled,
        }:
            return
        try:
            if sync_video_task_source_state(video_task):
                db.commit()
                if video_task.status == VideoTaskStatus.failed:
                    return
            if video_task.status == VideoTaskStatus.waiting_for_images:
                db.commit()
                return

            if video_task.status in {VideoTaskStatus.ready_for_audio, VideoTaskStatus.audio_generating}:
                video_task.status = VideoTaskStatus.audio_generating
                video_task.current_step = VideoTaskStepName.generate_narration_audio
                video_task.progress_current = 1
                video_task.error_code = None
                video_task.error_message = None
                db.commit()
                generate_audio_segments(db, video_task)
                video_task = load_video_task(db, video_task_id)
                if video_task is None:
                    return
                video_task.status = VideoTaskStatus.audio_ready
                video_task.current_step = VideoTaskStepName.submit_video
                video_task.progress_current = 2
                db.commit()

            if video_task.status in {VideoTaskStatus.audio_ready, VideoTaskStatus.video_generating}:
                video_task.status = VideoTaskStatus.video_generating
                video_task.current_step = VideoTaskStepName.submit_video
                video_task.progress_current = 3
                db.commit()
                render_video(db, video_task)
                video_task.status = VideoTaskStatus.succeeded
                video_task.current_step = VideoTaskStepName.download_video
                video_task.progress_current = video_task.progress_total
                video_task.error_code = None
                video_task.error_message = None
                video_task.finished_at = datetime.utcnow()
                db.commit()
        except Exception as exc:
            video_task = load_video_task(db, video_task_id)
            if video_task is None:
                raise
            video_task.status = VideoTaskStatus.failed
            video_task.error_code = exc.__class__.__name__
            video_task.error_message = str(exc)
            video_task.finished_at = datetime.utcnow()
            db.commit()
            raise


def mark_video_task_failed_by_unhandled_error(video_task_id: str, exc: Exception | None = None) -> None:
    with SessionLocal() as db:
        video_task = db.get(VideoTask, video_task_id)
        if video_task is None or video_task.status in {VideoTaskStatus.succeeded, VideoTaskStatus.failed, VideoTaskStatus.cancelled}:
            return
        video_task.status = VideoTaskStatus.failed
        video_task.error_code = (exc.__class__.__name__ if exc else "UnhandledVideoTaskError")
        video_task.error_message = str(exc or "视频任务执行异常")
        video_task.finished_at = datetime.utcnow()
        db.commit()
