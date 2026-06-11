from datetime import datetime
from io import BytesIO
import json
from zipfile import ZIP_DEFLATED, ZipFile

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import or_, select
from sqlalchemy.orm import Session, selectinload

from app.api.deps import current_user
from app.api.pagination import Pagination, build_page, get_pagination
from app.core.database import get_db
from app.models.entities import (
    FileAsset,
    GeneratedImage,
    GenerationTask,
    ContentExtraction,
    Style,
    StyleReferenceImage,
    TaskStyleReferenceImage,
    TaskCharacter,
    TaskCharacterAppearance,
    TaskDownload,
    TaskPanel,
    User,
)
from app.models.enums import (
    DownloadStatus,
    FileAssetPurpose,
    GeneratedImageSourceType,
    GeneratedImageStatus,
    GeneratedImageWorkflowStep,
    PromptStatus,
    StepStatus,
    StyleStatus,
    TaskStatus,
    UserRole,
)
from app.schemas.common import ApiData, ApiList
from app.schemas.character import CharacterNameExtractionRequest, CharacterNameExtractionResult, StoryCharacterMergeRequest, StoryCharacterMergeResult
from app.schemas.task import PanelEditCreate, TaskCreate, TaskDownloadRead, TaskListItemRead, TaskPreviewImageRead, TaskRead
from app.services.task_creation import TaskCreationError, create_generation_task_record
from app.services.task_worker import enqueue_panel_edit, enqueue_task, next_generation_number, task_progress_total
from app.services.image_generation import ImageProviderConfigError
from app.services.llm import LLMProviderError, extract_character_names_from_story, merge_character_into_story
from app.services.style_references import snapshot_task_style_reference_images
from app.services.storage import existing_local_asset_path, save_local_binary_file

router = APIRouter(prefix="/tasks", tags=["tasks"])
SUPERSEDED_IMAGE_ERROR_CODE = "ImageGenerationSuperseded"
SUPERSEDED_IMAGE_ERROR_MESSAGE = "任务重新生成后旧图片生成记录已失效"


def task_access_filter(user: User):
    if user.role == UserRole.admin:
        return True
    return GenerationTask.owner_user_id == user.id


def task_options():
    return (
        selectinload(GenerationTask.panels),
        selectinload(GenerationTask.steps),
        selectinload(GenerationTask.generated_images).selectinload(GeneratedImage.asset),
        selectinload(GenerationTask.characters)
        .selectinload(TaskCharacter.appearances)
        .selectinload(TaskCharacterAppearance.reference_image),
        selectinload(GenerationTask.style_reference_images).selectinload(TaskStyleReferenceImage.asset),
        selectinload(GenerationTask.downloads).selectinload(TaskDownload.asset),
    )


def ensure_task_access(task: GenerationTask | None, user: User) -> GenerationTask:
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="任务不存在")
    if user.role != UserRole.admin and task.owner_user_id != user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="没有权限访问该任务")
    return task


def current_or_latest_image_for_panel(task: GenerationTask, panel_id: str) -> GeneratedImage | None:
    panel_images = [image for image in task.generated_images if image.panel_id == panel_id]
    current = [image for image in panel_images if image.is_current]
    if current:
        return sorted(current, key=lambda image: image.generation_number, reverse=True)[0]
    succeeded = [image for image in panel_images if image.status == GeneratedImageStatus.succeeded and image.asset_id]
    if succeeded:
        return sorted(succeeded, key=lambda image: image.generation_number, reverse=True)[0]
    return sorted(panel_images, key=lambda image: image.generation_number, reverse=True)[0] if panel_images else None


def current_succeeded_images_for_panels(task: GenerationTask) -> list[GeneratedImage]:
    images_by_panel: dict[str, GeneratedImage] = {}
    for image in task.generated_images:
        if not image.is_current or image.status != GeneratedImageStatus.succeeded or image.asset_id is None:
            continue
        existing = images_by_panel.get(image.panel_id)
        if existing is None or image.generation_number > existing.generation_number:
            images_by_panel[image.panel_id] = image
    return [
        images_by_panel[panel.id]
        for panel in sorted(task.panels, key=lambda item: item.panel_order)
        if panel.id in images_by_panel
    ]


def task_has_all_panel_images(task: GenerationTask) -> bool:
    return bool(task.panels) and len(current_succeeded_images_for_panels(task)) == len(task.panels)


def retire_superseded_running_images(task: GenerationTask) -> int:
    count = 0
    for image in task.generated_images:
        if image.status not in {GeneratedImageStatus.queued, GeneratedImageStatus.running}:
            continue
        image.status = GeneratedImageStatus.failed
        image.is_current = False
        image.error_code = SUPERSEDED_IMAGE_ERROR_CODE
        image.error_message = SUPERSEDED_IMAGE_ERROR_MESSAGE
        image.finished_at = image.finished_at or datetime.utcnow()
        count += 1
    return count


def task_original_text_preview(task: GenerationTask) -> str:
    text = task.original_text.strip().replace("\n", " ")
    return text[:160]


def download_meta_for_content_extraction(content: ContentExtraction) -> dict[str, object]:
    return {
        "title": content.source_title or "",
        "description": content.source_description or "",
        "tags": content.source_tags,
    }


def douyin_source_content_for_task(db: Session, task_id: str) -> ContentExtraction | None:
    return db.scalar(select(ContentExtraction).where(ContentExtraction.linked_task_id == task_id))


@router.post("/extract-character-names", response_model=ApiData[CharacterNameExtractionResult])
def extract_character_names(
    payload: CharacterNameExtractionRequest,
    _: User = Depends(current_user),
) -> ApiData[CharacterNameExtractionResult]:
    try:
        result = extract_character_names_from_story(
            text=payload.text,
            trace_context={"operation": "extract_character_names_api"},
        )
    except LLMProviderError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
    return ApiData(data=CharacterNameExtractionResult.model_validate(result))


@router.post("/merge-character-into-story", response_model=ApiData[StoryCharacterMergeResult])
def merge_story_character(
    payload: StoryCharacterMergeRequest,
    _: User = Depends(current_user),
) -> ApiData[StoryCharacterMergeResult]:
    try:
        result = merge_character_into_story(
            story_text=payload.story_text,
            character_name=payload.character_name,
            character_description=payload.character_description,
            trace_context={"operation": "merge_character_into_story_api"},
        )
    except LLMProviderError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
    return ApiData(data=StoryCharacterMergeResult.model_validate(result))


@router.get("", response_model=ApiList[TaskListItemRead])
def list_tasks(
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
    pagination: Pagination = Depends(get_pagination),
    query: str | None = Query(default=None, max_length=120),
    status_filter: TaskStatus | None = Query(default=None, alias="status"),
    style_id: str | None = Query(default=None),
    user_id: str | None = Query(default=None),
) -> ApiList[TaskListItemRead]:
    if user.role != UserRole.admin and user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="普通用户不能按用户筛选任务")

    statement = (
        select(GenerationTask)
        .options(selectinload(GenerationTask.owner))
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
    task_ids = [task.id for task in visible_tasks]
    preview_images_by_task: dict[str, list[GeneratedImage]] = {task_id: [] for task_id in task_ids}
    if task_ids:
        preview_statement = (
            select(GeneratedImage)
            .join(GeneratedImage.panel)
            .where(
                GeneratedImage.task_id.in_(task_ids),
                GeneratedImage.is_current.is_(True),
                GeneratedImage.status == GeneratedImageStatus.succeeded,
                GeneratedImage.asset_id.is_not(None),
            )
            .options(selectinload(GeneratedImage.asset), selectinload(GeneratedImage.panel))
            .order_by(GeneratedImage.task_id, TaskPanel.panel_order)
        )
        for image in db.scalars(preview_statement).all():
            preview_images_by_task.setdefault(image.task_id, []).append(image)

    return ApiList(
        items=[
            TaskListItemRead(
                id=task.id,
                owner_user_id=task.owner_user_id,
                owner_display_name=task.owner.display_name if task.owner else None,
                owner_email=task.owner.email if task.owner else None,
                display_title=task.display_title,
                original_text_preview=task_original_text_preview(task),
                story_input_mode=task.story_input_mode,
                image_count_mode=task.image_count_mode,
                requested_image_count=task.requested_image_count,
                use_character_references=task.use_character_references,
                style_id=task.style_id,
                style_name_snapshot=task.style_name_snapshot,
                image_model_name_snapshot=task.image_model_name_snapshot,
                style_aspect_ratio_snapshot=task.style_aspect_ratio_snapshot,
                style_reference_mode_snapshot=task.style_reference_mode_snapshot,
                status=task.status,
                progress_current=task.progress_current,
                progress_total=task.progress_total,
                error_code=task.error_code,
                error_message=task.error_message,
                current_step=task.current_step,
                image_count=len(preview_images_by_task.get(task.id, [])),
                preview_images=[
                    TaskPreviewImageRead(id=image.id, panel_id=image.panel_id, asset=image.asset)
                    for image in preview_images_by_task.get(task.id, [])[:4]
                    if image.asset is not None
                ],
                created_at=task.created_at,
                updated_at=task.updated_at,
            )
            for task in visible_tasks
        ],
        page=build_page(pagination.limit, pagination.offset, len(tasks)),
    )


@router.post("", response_model=ApiData[TaskRead], status_code=status.HTTP_202_ACCEPTED)
async def create_task(payload: TaskCreate, user: User = Depends(current_user), db: Session = Depends(get_db)) -> ApiData[TaskRead]:
    try:
        task = create_generation_task_record(db=db, payload=payload, user=user)
    except TaskCreationError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
    except ImageProviderConfigError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    db.commit()
    db.refresh(task)
    await enqueue_task(task.id)

    task = db.scalar(
        select(GenerationTask)
        .where(GenerationTask.id == task.id)
        .options(*task_options())
    )
    return ApiData(data=TaskRead.model_validate(task))


@router.post("/{task_id}/retry", response_model=ApiData[TaskRead], status_code=status.HTTP_202_ACCEPTED)
async def retry_task(task_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)) -> ApiData[TaskRead]:
    task = db.scalar(
        select(GenerationTask)
        .where(GenerationTask.id == task_id)
        .options(*task_options())
    )
    task = ensure_task_access(task, user)
    if task.status not in {TaskStatus.failed, TaskStatus.partial_succeeded}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="只有失败或部分完成的任务可以重试")

    style = db.scalar(
        select(Style)
        .where(Style.id == task.style_id, Style.deleted_at.is_(None))
        .options(selectinload(Style.reference_images).selectinload(StyleReferenceImage.asset))
    )
    if not style:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="任务绑定的风格不存在")
    if style.status != StyleStatus.active:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="任务绑定的风格不是启用状态，不能重试")
    if not style.image_model_name.strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="任务绑定的风格尚未绑定生图模型名")

    retire_superseded_running_images(task)
    for image in list(task.generated_images):
        if image.status != GeneratedImageStatus.succeeded or image.asset_id is None:
            image.is_current = False
    for panel in list(task.panels):
        if panel.prompt_status == PromptStatus.failed:
            panel.prompt_status = PromptStatus.pending
            panel.generated_prompt = None
            panel.error_code = None
            panel.error_message = None
    for step in task.steps:
        step.status = StepStatus.queued
        step.error_code = None
        step.error_message = None
        step.started_at = None
        step.finished_at = None
    db.flush()

    task.status = TaskStatus.retrying
    task.current_step = None
    task.progress_total = task_progress_total(task)
    prompts_ready = bool(task.panels) and all(
        panel.prompt_status == PromptStatus.generated and panel.generated_prompt for panel in task.panels
    )
    task.progress_current = (task.progress_total - 1) if prompts_ready else 0
    task.attempts += 1
    task.next_run_at = None
    task.cancel_requested_at = None
    task.started_at = None
    task.finished_at = None
    task.error_code = None
    task.error_message = None
    task.internal_error_ref = None
    task.style_name_snapshot = style.name
    task.style_prompt_snapshot = style.style_prompt
    task.image_model_name_snapshot = style.image_model_name
    task.style_aspect_ratio_snapshot = style.aspect_ratio
    task.style_reference_mode_snapshot = style.style_reference_mode
    try:
        snapshot_task_style_reference_images(db=db, task=task, style=style)
    except ImageProviderConfigError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    db.commit()
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


@router.post("/{task_id}/panels/{panel_id}/edits", response_model=ApiData[TaskRead], status_code=status.HTTP_202_ACCEPTED)
async def edit_panel_image(
    task_id: str,
    panel_id: str,
    payload: PanelEditCreate,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> ApiData[TaskRead]:
    task = db.scalar(
        select(GenerationTask)
        .where(GenerationTask.id == task_id)
        .options(*task_options())
    )
    task = ensure_task_access(task, user)
    if task.status in {TaskStatus.queued, TaskStatus.running, TaskStatus.retrying, TaskStatus.cancel_requested}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="任务生成中，暂不能修改单个分镜")

    panel = next((item for item in task.panels if item.id == panel_id), None)
    if panel is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="分镜不存在")
    if panel.prompt_status != PromptStatus.generated or not panel.generated_prompt:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="分镜提示词尚未生成，不能修改画面")

    running_image = next(
        (
            image
            for image in task.generated_images
            if image.panel_id == panel_id and image.status in {GeneratedImageStatus.queued, GeneratedImageStatus.running}
        ),
        None,
    )
    if running_image:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="该分镜已有修改或生成正在进行")

    current_image = current_or_latest_image_for_panel(task, panel_id)
    previous_prompt = (current_image.image_prompt if current_image and current_image.image_prompt else panel.generated_prompt) or ""
    previous_image_text_json = (
        current_image.image_text_json if current_image and current_image.image_text_json else panel.image_text_json
    )
    previous_text_layout = current_image.text_layout if current_image and current_image.text_layout else panel.text_layout
    image = GeneratedImage(
        task_id=task.id,
        panel_id=panel.id,
        status=GeneratedImageStatus.queued,
        generation_number=next_generation_number(db, panel.id),
        is_current=False,
        source_type=GeneratedImageSourceType.user_edit,
        workflow_step=GeneratedImageWorkflowStep.rewrite_prompt,
        user_instruction=payload.user_instruction.strip(),
        previous_prompt=previous_prompt,
        image_text_json=previous_image_text_json,
        text_layout=previous_text_layout,
        image_model_name_snapshot=task.image_model_name_snapshot,
    )
    db.add(image)
    db.commit()
    await enqueue_panel_edit(image.id)

    task = db.scalar(
        select(GenerationTask)
        .where(GenerationTask.id == task.id)
        .options(*task_options())
    )
    return ApiData(data=TaskRead.model_validate(task))


@router.post("/{task_id}/downloads", response_model=ApiData[TaskDownloadRead])
def create_task_download(task_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)) -> ApiData[TaskDownloadRead]:
    task = db.scalar(
        select(GenerationTask)
        .where(GenerationTask.id == task_id)
        .options(*task_options())
    )
    task = ensure_task_access(task, user)

    images = current_succeeded_images_for_panels(task)
    if task.status != TaskStatus.succeeded or len(images) != len(task.panels):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="所有分镜图片生成成功后才能下载")
    if any(image.asset is None for image in images):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="下载资产尚未准备完成")

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
        source_content = douyin_source_content_for_task(db, task.id)
        source_meta = download_meta_for_content_extraction(source_content) if source_content else None
        buffer = BytesIO()
        with ZipFile(buffer, mode="w", compression=ZIP_DEFLATED) as archive:
            for index, image in enumerate(images, start=1):
                asset = image.asset
                source_path = existing_local_asset_path(asset)
                suffix = source_path.suffix or ".png"
                archive.write(source_path, arcname=f"panel-{index:02d}{suffix}")
            if source_meta is not None:
                archive.writestr(
                    "meta.json",
                    json.dumps(source_meta, ensure_ascii=False, indent=2).encode("utf-8"),
                )

        stored = save_local_binary_file(
            FileAssetPurpose.download_archive.value,
            buffer.getvalue(),
            ".zip",
        )
        asset = FileAsset(
            purpose=FileAssetPurpose.download_archive,
            storage_backend=stored.storage_backend,
            storage_key=stored.storage_key,
            public_url=stored.public_url,
            original_filename=filename,
            content_type="application/zip",
            byte_size=stored.byte_size,
            checksum_sha256=stored.checksum_sha256,
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
