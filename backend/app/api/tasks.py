from io import BytesIO
from zipfile import ZIP_DEFLATED, ZipFile

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import or_, select
from sqlalchemy.orm import Session, selectinload

from app.api.deps import current_user
from app.api.pagination import Pagination, build_page, get_pagination
from app.core.database import get_db
from app.models.entities import FileAsset, GeneratedImage, GenerationStep, GenerationTask, Style, TaskDownload, User
from app.models.enums import (
    DownloadStatus,
    FileAssetPurpose,
    GeneratedImageStatus,
    GenerationStepName,
    ImageCountMode,
    StyleStatus,
    TaskStatus,
    UserRole,
)
from app.schemas.common import ApiData, ApiList
from app.schemas.task import TaskCreate, TaskDownloadRead, TaskRead
from app.services.generation_profiles import (
    GenerationProfileConfigError,
    UnknownGenerationProfileError,
    validate_generation_profile_key,
)
from app.services.task_worker import enqueue_task
from app.services.storage import resolve_storage_key, save_binary_file

router = APIRouter(prefix="/tasks", tags=["tasks"])


def task_access_filter(user: User):
    if user.role == UserRole.admin:
        return True
    return GenerationTask.owner_user_id == user.id


def task_options():
    return (
        selectinload(GenerationTask.panels),
        selectinload(GenerationTask.steps),
        selectinload(GenerationTask.generated_images).selectinload(GeneratedImage.asset),
        selectinload(GenerationTask.downloads).selectinload(TaskDownload.asset),
    )


def ensure_task_access(task: GenerationTask | None, user: User) -> GenerationTask:
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="任务不存在")
    if user.role != UserRole.admin and task.owner_user_id != user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="没有权限访问该任务")
    return task


@router.get("", response_model=ApiList[TaskRead])
def list_tasks(
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
    pagination: Pagination = Depends(get_pagination),
    query: str | None = Query(default=None, max_length=120),
    status_filter: TaskStatus | None = Query(default=None, alias="status"),
    style_id: str | None = Query(default=None),
    user_id: str | None = Query(default=None),
) -> ApiList[TaskRead]:
    if user.role != UserRole.admin and user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="普通用户不能按用户筛选任务")

    statement = (
        select(GenerationTask)
        .options(*task_options())
        .order_by(GenerationTask.created_at.desc())
        .offset(pagination.offset)
        .limit(pagination.limit + 1)
    )
    if user.role != UserRole.admin:
        statement = statement.where(GenerationTask.owner_user_id == user.id)
    elif user_id:
        statement = statement.where(GenerationTask.owner_user_id == user_id)
    if query:
        statement = statement.where(or_(GenerationTask.display_title.contains(query), GenerationTask.original_text.contains(query)))
    if status_filter:
        statement = statement.where(GenerationTask.status == status_filter)
    if style_id:
        statement = statement.where(GenerationTask.style_id == style_id)

    tasks = db.scalars(statement).all()
    visible_tasks = tasks[: pagination.limit]
    return ApiList(
        items=[TaskRead.model_validate(task) for task in visible_tasks],
        page=build_page(pagination.limit, pagination.offset, len(tasks)),
    )


@router.post("", response_model=ApiData[TaskRead], status_code=status.HTTP_202_ACCEPTED)
async def create_task(payload: TaskCreate, user: User = Depends(current_user), db: Session = Depends(get_db)) -> ApiData[TaskRead]:
    style = db.scalar(select(Style).where(Style.id == payload.style_id))
    if not style:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="风格不存在")
    if style.status != StyleStatus.active:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="只能使用启用状态的风格创建任务")
    if not style.generation_profile_key:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="风格尚未绑定后台生成配置 Key")
    if payload.image_count_mode == ImageCountMode.auto and payload.requested_image_count is not None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="自动判断图片数量时不能传 requested_image_count")
    if payload.image_count_mode == ImageCountMode.fixed and payload.requested_image_count is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="固定图片数量时必须传 requested_image_count")

    try:
        validate_generation_profile_key(style.generation_profile_key)
    except UnknownGenerationProfileError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except GenerationProfileConfigError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc

    display_title = payload.original_text.strip().replace("\n", " ")[:36] or "未命名任务"
    task = GenerationTask(
        owner_user_id=user.id,
        display_title=display_title,
        original_text=payload.original_text,
        image_count_mode=payload.image_count_mode,
        requested_image_count=payload.requested_image_count,
        style_id=style.id,
        style_name_snapshot=style.name,
        style_prompt_snapshot=style.style_prompt,
        generation_profile_key_snapshot=style.generation_profile_key,
        status=TaskStatus.queued,
        progress_current=0,
        progress_total=3,
    )
    db.add(task)
    db.flush()
    for step_name in (
        GenerationStepName.segment_story,
        GenerationStepName.generate_panel_prompts,
        GenerationStepName.generate_images,
    ):
        db.add(
            GenerationStep(
                task_id=task.id,
                step_name=step_name,
                idempotency_key=f"{task.id}:{step_name.value}",
            )
        )
    db.commit()
    db.refresh(task)
    await enqueue_task(task.id)

    task = db.scalar(
        select(GenerationTask)
        .where(GenerationTask.id == task.id)
        .options(*task_options())
    )
    return ApiData(data=TaskRead.model_validate(task))


@router.get("/{task_id}", response_model=ApiData[TaskRead])
def get_task(task_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)) -> ApiData[TaskRead]:
    task = db.scalar(
        select(GenerationTask)
        .where(GenerationTask.id == task_id)
        .options(*task_options())
    )
    task = ensure_task_access(task, user)

    return ApiData(data=TaskRead.model_validate(task))


@router.post("/{task_id}/cancel", response_model=ApiData[TaskRead])
def cancel_task(task_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)) -> ApiData[TaskRead]:
    task = db.scalar(
        select(GenerationTask)
        .where(GenerationTask.id == task_id)
        .options(*task_options())
    )
    task = ensure_task_access(task, user)
    if task.status in {TaskStatus.succeeded, TaskStatus.failed, TaskStatus.partial_succeeded, TaskStatus.cancelled}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="当前任务状态不能取消")

    task.status = TaskStatus.cancelled if task.status == TaskStatus.queued else TaskStatus.cancel_requested
    db.commit()
    db.refresh(task)
    return ApiData(data=TaskRead.model_validate(task))


@router.post("/{task_id}/downloads", response_model=ApiData[TaskDownloadRead])
def create_task_download(task_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)) -> ApiData[TaskDownloadRead]:
    task = db.scalar(
        select(GenerationTask)
        .where(GenerationTask.id == task_id)
        .options(*task_options())
    )
    task = ensure_task_access(task, user)

    images = [
        image
        for image in sorted(task.generated_images, key=lambda item: item.panel.panel_order if item.panel else 0)
        if image.status == GeneratedImageStatus.succeeded and image.asset is not None
    ]
    if not images:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="任务暂无可下载的成功图片")

    filename = f"doodlestory-{task.id}.zip"
    download = TaskDownload(
        task_id=task.id,
        status=DownloadStatus.running,
        image_count=len(images),
        filename=filename,
    )
    db.add(download)
    db.commit()
    db.refresh(download)

    try:
        buffer = BytesIO()
        with ZipFile(buffer, mode="w", compression=ZIP_DEFLATED) as archive:
            for index, image in enumerate(images, start=1):
                asset = image.asset
                source_path = resolve_storage_key(asset.storage_key)
                if not source_path.exists():
                    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="生成图片文件不存在")
                suffix = source_path.suffix or ".png"
                archive.write(source_path, arcname=f"panel-{index:02d}{suffix}")

        storage_key, byte_size, checksum = save_binary_file(
            FileAssetPurpose.download_archive.value,
            buffer.getvalue(),
            ".zip",
        )
        asset = FileAsset(
            purpose=FileAssetPurpose.download_archive,
            storage_key=storage_key,
            original_filename=filename,
            content_type="application/zip",
            byte_size=byte_size,
            checksum_sha256=checksum,
        )
        db.add(asset)
        db.flush()
        download.asset_id = asset.id
        download.status = DownloadStatus.ready
    except Exception as exc:
        download.status = DownloadStatus.failed
        download.error_code = exc.__class__.__name__
        download.error_message = str(exc)

    db.commit()
    download = db.scalar(
        select(TaskDownload)
        .where(TaskDownload.id == download.id)
        .options(selectinload(TaskDownload.asset))
    )
    return ApiData(data=TaskDownloadRead.model_validate(download))
