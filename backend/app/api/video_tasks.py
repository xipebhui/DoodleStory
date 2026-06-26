from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import or_, select
from sqlalchemy.orm import Session, selectinload

from app.api.deps import current_user
from app.api.pagination import Pagination, build_page, get_pagination
from app.core.database import get_db
from app.models.entities import AudioReference, GeneratedImage, GenerationTask, TaskPanel, User, VideoTask, VideoTaskAudioSegment
from app.models.enums import (
    GeneratedImageJobKind,
    GeneratedImageStatus,
    StoryInputMode,
    TaskStatus,
    UserRole,
    VideoTaskStatus,
    VideoTaskStepName,
)
from app.schemas.common import ApiData, ApiList
from app.schemas.task import TaskCreate, TaskPreviewImageRead
from app.schemas.video_task import VideoTaskAudioSegmentRead, VideoTaskCreate, VideoTaskListItem, VideoTaskRead, VideoTaskSourceTaskRead
from app.services.image_generation import ImageProviderConfigError
from app.services.task_creation import TaskCreationError, create_generation_task_record
from app.services.task_worker import enqueue_task

router = APIRouter(prefix="/video-tasks", tags=["video-tasks"])


def ensure_video_task_access(video_task: VideoTask | None, user: User) -> VideoTask:
    if not video_task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="视频任务不存在")
    if user.role != UserRole.admin and video_task.owner_user_id != user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="没有权限访问该视频任务")
    return video_task


def ensure_audio_reference_for_video(reference: AudioReference | None, user: User) -> AudioReference:
    if not reference or reference.deleted_at is not None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="音频参考不存在")
    if user.role != UserRole.admin and reference.owner_user_id != user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="只能使用自己的音频参考")
    return reference


def video_task_options():
    return (
        selectinload(VideoTask.owner),
        selectinload(VideoTask.source_task).selectinload(GenerationTask.panels),
        selectinload(VideoTask.source_task).selectinload(GenerationTask.generated_images).selectinload(GeneratedImage.asset),
        selectinload(VideoTask.audio_reference),
        selectinload(VideoTask.audio_reference_asset_snapshot),
        selectinload(VideoTask.audio_segments).selectinload(VideoTaskAudioSegment.asset),
        selectinload(VideoTask.narration_audio_asset),
        selectinload(VideoTask.output_video_asset),
    )


def source_preview_images(source_task: GenerationTask) -> list[GeneratedImage]:
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
    return [
        images_by_panel[panel.id]
        for panel in sorted(source_task.panels, key=lambda item: item.panel_order)
        if panel.id in images_by_panel
    ]


def sync_video_task_from_source(video_task: VideoTask) -> bool:
    source = video_task.source_task
    if video_task.status not in {VideoTaskStatus.waiting_for_images, VideoTaskStatus.ready_for_audio}:
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


def source_task_read(source_task: GenerationTask) -> VideoTaskSourceTaskRead:
    images = source_preview_images(source_task)
    return VideoTaskSourceTaskRead(
        id=source_task.id,
        display_title=source_task.display_title,
        status=source_task.status,
        progress_current=source_task.progress_current,
        progress_total=source_task.progress_total,
        error_code=source_task.error_code,
        error_message=source_task.error_message,
        style_name_snapshot=source_task.style_name_snapshot,
        style_aspect_ratio_snapshot=source_task.style_aspect_ratio_snapshot,
        image_count=len(images),
        preview_images=[
            TaskPreviewImageRead(id=image.id, panel_id=image.panel_id, asset=image.asset)
            for image in images[:4]
            if image.panel_id and image.asset
        ],
    )


def original_text_preview(text: str) -> str:
    return text.strip().replace("\n", " ")[:160]


def video_task_list_item(video_task: VideoTask) -> VideoTaskListItem:
    return VideoTaskListItem(
        id=video_task.id,
        owner_user_id=video_task.owner_user_id,
        owner_display_name=video_task.owner.display_name if video_task.owner else None,
        owner_email=video_task.owner.email if video_task.owner else None,
        display_title=video_task.display_title,
        original_text_preview=original_text_preview(video_task.original_text),
        status=video_task.status,
        current_step=video_task.current_step,
        progress_current=video_task.progress_current,
        progress_total=video_task.progress_total,
        error_code=video_task.error_code,
        error_message=video_task.error_message,
        audio_reference_name_snapshot=video_task.audio_reference_name_snapshot,
        video_provider_job_id=video_task.video_provider_job_id,
        video_provider_status=video_task.video_provider_status,
        source_task=source_task_read(video_task.source_task),
        output_video_asset=video_task.output_video_asset,
        created_at=video_task.created_at,
        updated_at=video_task.updated_at,
    )


def video_task_read(video_task: VideoTask) -> VideoTaskRead:
    return VideoTaskRead(
        id=video_task.id,
        owner_user_id=video_task.owner_user_id,
        owner_display_name=video_task.owner.display_name if video_task.owner else None,
        owner_email=video_task.owner.email if video_task.owner else None,
        display_title=video_task.display_title,
        original_text=video_task.original_text,
        status=video_task.status,
        current_step=video_task.current_step,
        progress_current=video_task.progress_current,
        progress_total=video_task.progress_total,
        started_at=video_task.started_at,
        finished_at=video_task.finished_at,
        error_code=video_task.error_code,
        error_message=video_task.error_message,
        audio_reference_id=video_task.audio_reference_id,
        audio_reference_name_snapshot=video_task.audio_reference_name_snapshot,
        audio_reference_text_snapshot=video_task.audio_reference_text_snapshot,
        audio_reference_asset=video_task.audio_reference_asset_snapshot,
        voice_provider_snapshot=video_task.voice_provider_snapshot,
        voice_model_snapshot=video_task.voice_model_snapshot,
        voice_name_snapshot=video_task.voice_name_snapshot,
        voice_speed_snapshot=video_task.voice_speed_snapshot,
        narration_audio_asset=video_task.narration_audio_asset,
        audio_segments=[
            VideoTaskAudioSegmentRead(
                id=segment.id,
                panel_id=segment.panel_id,
                panel_order=segment.panel_order,
                narration_text=segment.narration_text,
                duration_ms=segment.duration_ms,
                asset=segment.asset,
                created_at=segment.created_at,
                updated_at=segment.updated_at,
            )
            for segment in sorted(video_task.audio_segments, key=lambda item: item.panel_order)
            if segment.asset is not None
        ],
        output_video_asset=video_task.output_video_asset,
        video_provider_job_id=video_task.video_provider_job_id,
        video_provider_status=video_task.video_provider_status,
        video_provider_output_url=video_task.video_provider_output_url,
        source_task=source_task_read(video_task.source_task),
        created_at=video_task.created_at,
        updated_at=video_task.updated_at,
    )


@router.get("", response_model=ApiList[VideoTaskListItem])
def list_video_tasks(
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
    pagination: Pagination = Depends(get_pagination),
    query: str | None = Query(default=None, max_length=120),
    status_filter: VideoTaskStatus | None = Query(default=None, alias="status"),
) -> ApiList[VideoTaskListItem]:
    statement = (
        select(VideoTask)
        .options(*video_task_options())
        .order_by(VideoTask.created_at.desc())
        .offset(pagination.offset)
        .limit(pagination.limit + 1)
    )
    if user.role != UserRole.admin:
        statement = statement.where(VideoTask.owner_user_id == user.id)
    if query:
        statement = statement.where(or_(VideoTask.display_title.contains(query), VideoTask.original_text.contains(query)))
    if status_filter:
        statement = statement.where(VideoTask.status == status_filter)

    video_tasks = db.scalars(statement).all()
    visible = video_tasks[: pagination.limit]
    changed = any(sync_video_task_from_source(video_task) for video_task in visible)
    if changed:
        db.commit()
        for video_task in visible:
            db.refresh(video_task)
    return ApiList(
        items=[video_task_list_item(video_task) for video_task in visible],
        page=build_page(pagination.limit, pagination.offset, len(video_tasks)),
    )


@router.post("", response_model=ApiData[VideoTaskRead], status_code=status.HTTP_202_ACCEPTED)
async def create_video_task(
    payload: VideoTaskCreate,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> ApiData[VideoTaskRead]:
    reference = db.scalar(
        select(AudioReference)
        .where(AudioReference.id == payload.audio_reference_id)
        .options(selectinload(AudioReference.asset))
    )
    reference = ensure_audio_reference_for_video(reference, user)
    source_payload = TaskCreate(
        original_text=payload.original_text,
        story_input_mode=StoryInputMode.original,
        image_count_mode=payload.image_count_mode,
        requested_image_count=payload.requested_image_count,
        style_id=payload.style_id,
        use_character_references=payload.use_character_references,
        last_panel_real_photo=payload.last_panel_real_photo,
        story_characters=[],
    )
    try:
        source_task = create_generation_task_record(db=db, payload=source_payload, user=user)
    except TaskCreationError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
    except ImageProviderConfigError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    video_task = VideoTask(
        owner_user_id=user.id,
        source_task_id=source_task.id,
        audio_reference_id=reference.id,
        display_title=source_task.display_title,
        original_text=payload.original_text,
        audio_reference_name_snapshot=reference.name,
        audio_reference_text_snapshot=reference.reference_text,
        audio_reference_asset_id_snapshot=reference.asset_id,
        voice_provider_snapshot=reference.voice_provider,
        voice_model_snapshot=reference.voice_model,
        voice_name_snapshot=reference.voice_name,
        voice_speed_snapshot=reference.speech_speed,
        status=VideoTaskStatus.waiting_for_images,
        current_step=VideoTaskStepName.generate_source_images,
        progress_current=0,
        progress_total=4,
        started_at=datetime.utcnow(),
    )
    db.add(video_task)
    db.commit()
    await enqueue_task(source_task.id)

    video_task = db.scalar(select(VideoTask).where(VideoTask.id == video_task.id).options(*video_task_options()))
    return ApiData(data=video_task_read(video_task))


@router.get("/{video_task_id}", response_model=ApiData[VideoTaskRead])
def get_video_task(
    video_task_id: str,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> ApiData[VideoTaskRead]:
    video_task = db.scalar(select(VideoTask).where(VideoTask.id == video_task_id).options(*video_task_options()))
    video_task = ensure_video_task_access(video_task, user)
    if sync_video_task_from_source(video_task):
        db.commit()
        video_task = db.scalar(select(VideoTask).where(VideoTask.id == video_task_id).options(*video_task_options()))
    return ApiData(data=video_task_read(video_task))
