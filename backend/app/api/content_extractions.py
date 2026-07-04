import json
import logging
import mimetypes
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from time import monotonic

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from PIL import Image, UnidentifiedImageError
from sqlalchemy import or_, select
from sqlalchemy.orm import Session, selectinload

from app.api.deps import current_user
from app.api.pagination import Pagination, build_page, get_pagination
from app.core.database import SessionLocal, get_db
from app.models.entities import ContentExtraction, ContentExtractionMedia, FileAsset, User
from app.models.enums import ContentExtractionMediaKind, FileAssetPurpose, StoryInputMode, UserRole
from app.schemas.common import ApiData, ApiList
from app.schemas.content_extraction import (
    ContentExtractionDownloadCreate,
    ContentExtractionHealthRead,
    ContentExtractionListItemRead,
    ContentExtractionRead,
    ContentExtractionReplicateTaskCreate,
)
from app.schemas.task import TaskCreate
from app.services.douyin_import_service import (
    DouyinImportConfigError,
    DouyinImportServiceError,
    check_douyin_import_health,
    download_douyin_content,
)
from app.services.llm import LLMConfigError, LLMProviderError, LLMResponseError
from app.services.media_text_extraction import (
    ImageExtractionReference,
    MAX_CONTENT_EXTRACTION_IMAGES,
    extract_ordered_gallery_comic_content,
    transcribe_video_audio,
)
from app.services.storage import save_binary_file
from app.services.task_creation import TaskCreationError, create_generation_task_record
from app.services.task_worker import enqueue_task_from_thread

router = APIRouter(prefix="/content-extractions", tags=["content-extractions"])
logger = logging.getLogger(__name__)

DOUYIN_URL_PATTERN = re.compile(
    r"https?://(?:v\.douyin\.com/[A-Za-z0-9_.~%-]+/?|www\.douyin\.com/(?:video|note)/[A-Za-z0-9_.~%-]+(?:\?[^\s，,。！!？?；;]*)?)"
)
IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp"}
VIDEO_SUFFIXES = {".mp4"}
ASSET_UPLOAD_CONCURRENCY = 6
CONTENT_EXTRACTION_INTERRUPTED_MESSAGE = "内容提取任务在后端重启或进程中断时停止，已标记为失败；请重新提取以使用当前处理链路"
TASK_CREATE_PENDING_STATUS = "pending"
TASK_CREATE_SUCCEEDED_STATUS = "succeeded"
TASK_CREATE_FAILED_STATUS = "failed"


@dataclass(frozen=True)
class DownloadedAssetCandidate:
    display_order: int
    path: Path
    media_kind: ContentExtractionMediaKind


@dataclass(frozen=True)
class SavedDownloadedAsset:
    candidate: DownloadedAssetCandidate
    asset: FileAsset


def content_extraction_options():
    return (selectinload(ContentExtraction.media).selectinload(ContentExtractionMedia.asset),)


def ensure_content_extraction_access(content: ContentExtraction | None, user: User) -> ContentExtraction:
    if not content:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="内容提取记录不存在")
    if user.role != UserRole.admin and content.owner_user_id != user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="没有权限访问该内容提取记录")
    return content


def extract_douyin_url(raw_input: str) -> str:
    match = DOUYIN_URL_PATTERN.search(raw_input)
    if not match:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="没有找到可用的抖音链接")
    return match.group(0).rstrip("，,。！!？?；;")


def media_kind_for_path(path: Path) -> ContentExtractionMediaKind:
    suffix = path.suffix.lower()
    if suffix in IMAGE_SUFFIXES:
        return ContentExtractionMediaKind.image
    if suffix in VIDEO_SUFFIXES:
        return ContentExtractionMediaKind.video
    return ContentExtractionMediaKind.metadata


def content_type_for_path(path: Path, media_kind: ContentExtractionMediaKind) -> str:
    guessed = mimetypes.guess_type(path.name)[0]
    if guessed:
        return guessed
    if media_kind == ContentExtractionMediaKind.video:
        return "video/mp4"
    if media_kind == ContentExtractionMediaKind.metadata:
        return "application/json"
    return "application/octet-stream"


def purpose_for_kind(media_kind: ContentExtractionMediaKind) -> FileAssetPurpose:
    if media_kind == ContentExtractionMediaKind.audio:
        return FileAssetPurpose.douyin_audio
    if media_kind == ContentExtractionMediaKind.metadata:
        return FileAssetPurpose.douyin_metadata
    return FileAssetPurpose.douyin_media


def dimensions_for_image(path: Path, content_type: str) -> tuple[int | None, int | None]:
    if not content_type.startswith("image/"):
        return None, None
    try:
        with Image.open(path) as image:
            return image.width, image.height
    except UnidentifiedImageError:
        return None, None


def save_path_as_asset(path: Path, media_kind: ContentExtractionMediaKind) -> FileAsset:
    if not path.exists() or not path.is_file() or path.stat().st_size <= 0:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"下载产物不存在或为空：{path}")
    suffix = path.suffix.lower() or ".bin"
    stored = save_binary_file(purpose_for_kind(media_kind).value, path.read_bytes(), suffix)
    content_type = content_type_for_path(path, media_kind)
    width, height = dimensions_for_image(path, content_type)
    return FileAsset(
        purpose=purpose_for_kind(media_kind),
        storage_backend=stored.storage_backend,
        storage_key=stored.storage_key,
        public_url=stored.public_url,
        original_filename=path.name,
        content_type=content_type,
        byte_size=stored.byte_size,
        checksum_sha256=stored.checksum_sha256,
        width=width,
        height=height,
    )


def save_downloaded_assets_parallel(candidates: list[DownloadedAssetCandidate]) -> list[SavedDownloadedAsset]:
    if not candidates:
        return []
    started = monotonic()
    max_workers = min(ASSET_UPLOAD_CONCURRENCY, len(candidates))
    logger.info(
        "content_extraction_debug asset_upload_parallel_start item_count=%s max_workers=%s display_orders=%s",
        len(candidates),
        max_workers,
        [candidate.display_order for candidate in candidates],
    )
    saved_by_order: dict[int, SavedDownloadedAsset] = {}
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_map = {
            executor.submit(save_path_as_asset, candidate.path, candidate.media_kind): candidate
            for candidate in candidates
        }
        for future in as_completed(future_map):
            candidate = future_map[future]
            asset = future.result()
            saved_by_order[candidate.display_order] = SavedDownloadedAsset(candidate=candidate, asset=asset)
            logger.info(
                "content_extraction_debug asset_upload_parallel_item_done display_order=%s media_kind=%s source_path=%s storage_backend=%s storage_key=%s byte_size=%s elapsed_ms=%s",
                candidate.display_order,
                candidate.media_kind.value,
                candidate.path,
                asset.storage_backend.value,
                asset.storage_key,
                asset.byte_size,
                round((monotonic() - started) * 1000),
            )
    saved = [saved_by_order[candidate.display_order] for candidate in candidates]
    logger.info(
        "content_extraction_debug asset_upload_parallel_done item_count=%s elapsed_ms=%s",
        len(saved),
        round((monotonic() - started) * 1000),
    )
    return saved


def content_preview(text: str | None, limit: int = 160) -> str | None:
    if not text:
        return None
    return text.strip().replace("\n", " ")[:limit]


def load_content_extraction(db: Session, content_id: str) -> ContentExtraction | None:
    return db.scalar(
        select(ContentExtraction)
        .where(ContentExtraction.id == content_id)
        .options(*content_extraction_options())
    )


def mark_content_extraction_interrupted(content: ContentExtraction) -> None:
    content.processing_status = "failed"
    content.processing_error_message = CONTENT_EXTRACTION_INTERRUPTED_MESSAGE
    if content.task_create_status == TASK_CREATE_PENDING_STATUS:
        content.task_create_status = TASK_CREATE_FAILED_STATUS
        content.task_create_error_message = CONTENT_EXTRACTION_INTERRUPTED_MESSAGE


def recover_interrupted_content_extractions() -> int:
    with SessionLocal() as db:
        interrupted = db.scalars(
            select(ContentExtraction).where(ContentExtraction.processing_status == "processing")
        ).all()
        if not interrupted:
            logger.info("content_extraction_debug startup_recovery_noop")
            return 0

        for content in interrupted:
            mark_content_extraction_interrupted(content)

        db.commit()
        logger.warning(
            "content_extraction_debug startup_recovered_interrupted count=%s content_ids=%s",
            len(interrupted),
            [content.id for content in interrupted],
        )
        return len(interrupted)


def list_item_for_content(content: ContentExtraction, media_count: int) -> ContentExtractionListItemRead:
    return ContentExtractionListItemRead(
        id=content.id,
        owner_user_id=content.owner_user_id,
        source_url=content.source_url,
        media_type=content.media_type,
        aweme_id=content.aweme_id,
        source_title=content.source_title,
        source_description=content.source_description,
        source_tags=content.source_tags,
        processing_status=content.processing_status,
        processing_error_message=content.processing_error_message,
        raw_input_preview=content_preview(content.raw_input, 120),
        extracted_text_preview=content_preview(content.extracted_text, 96),
        story_content_preview=content_preview(content.story_content, 96),
        story_highlight_preview=content_preview(content.story_highlight, 96),
        target_audience_preview=content_preview(content.target_audience, 96),
        has_extracted_text=bool(content.extracted_text and content.extracted_text.strip()),
        has_story_summary=bool(
            (content.story_content and content.story_content.strip())
            or (content.story_highlight and content.story_highlight.strip())
            or (content.target_audience and content.target_audience.strip())
        ),
        media_count=media_count,
        linked_task_id=content.linked_task_id,
        task_create_status=content.task_create_status,
        task_create_error_message=content.task_create_error_message,
        created_at=content.created_at,
        updated_at=content.updated_at,
    )


def create_pending_content_extraction(
    payload: ContentExtractionDownloadCreate,
    user: User,
    db: Session,
    *,
    processing_status: str = "processing",
) -> ContentExtraction:
    source_url = extract_douyin_url(payload.raw_input)
    content = ContentExtraction(
        owner_user_id=user.id,
        raw_input=payload.raw_input,
        source_url=source_url,
        media_type="pending",
        output_dir="",
        processing_status=processing_status,
    )
    db.add(content)
    db.flush()
    logger.info(
        "content_extraction_debug created content_id=%s owner_user_id=%s source_url=%s processing_status=%s raw_input_chars=%s",
        content.id,
        user.id,
        source_url,
        processing_status,
        len(payload.raw_input),
    )
    return content


def create_pending_replicate_content_extraction(
    payload: ContentExtractionReplicateTaskCreate,
    user: User,
    db: Session,
) -> ContentExtraction:
    content = create_pending_content_extraction(payload, user, db)
    content.task_create_status = TASK_CREATE_PENDING_STATUS
    content.task_create_error_message = None
    return content


def create_generation_task_from_content_extraction(
    content: ContentExtraction,
    payload: ContentExtractionReplicateTaskCreate,
    user: User,
    db: Session,
) -> str:
    if not content.extracted_text or not content.extracted_text.strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="内容提取结果为空，无法创建生成任务")

    task_payload = TaskCreate(
        original_text=content.extracted_text,
        story_input_mode=StoryInputMode.extracted_storyboard,
        image_count_mode=payload.image_count_mode,
        requested_image_count=payload.requested_image_count,
        style_id=payload.style_id,
        use_character_references=payload.use_character_references,
        last_panel_real_photo=payload.last_panel_real_photo,
        remove_image_text=payload.remove_image_text,
    )
    try:
        task = create_generation_task_record(db=db, payload=task_payload, user=user)
    except TaskCreationError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc

    content.linked_task_id = task.id
    content.task_create_status = TASK_CREATE_SUCCEEDED_STATUS
    content.task_create_error_message = None
    return task.id


def attach_douyin_download_result(content: ContentExtraction, db: Session) -> None:
    started = monotonic()
    logger.info(
        "content_extraction_debug download_start content_id=%s source_url=%s",
        content.id,
        content.source_url,
    )
    try:
        result = download_douyin_content(content.source_url)
    except DouyinImportConfigError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except DouyinImportServiceError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc

    content.media_type = result.media_type
    content.aweme_id = result.aweme_id
    content.output_dir = str(result.output_dir)
    content.manifest_path = str(result.manifest_path) if result.manifest_path else None
    content.source_title = result.title
    content.source_description = result.description
    content.source_tags_json = json.dumps(result.tags, ensure_ascii=False)
    logger.info(
        "content_extraction_debug download_result content_id=%s media_type=%s aweme_id=%s source_title_chars=%s source_tag_count=%s media_file_count=%s metadata_file_count=%s output_dir=%s manifest_path=%s elapsed_ms=%s",
        content.id,
        result.media_type,
        result.aweme_id,
        len(result.title or ""),
        len(result.tags),
        len(result.media_files),
        len(result.metadata_files),
        result.output_dir,
        result.manifest_path,
        round((monotonic() - started) * 1000),
    )

    candidates: list[DownloadedAssetCandidate] = []
    display_order = 1
    for path in result.media_files:
        candidates.append(
            DownloadedAssetCandidate(
                display_order=display_order,
                path=path,
                media_kind=media_kind_for_path(path),
            )
        )
        display_order += 1
    for path in result.metadata_files:
        candidates.append(
            DownloadedAssetCandidate(
                display_order=display_order,
                path=path,
                media_kind=ContentExtractionMediaKind.metadata,
            )
        )
        display_order += 1

    for saved in save_downloaded_assets_parallel(candidates):
        candidate = saved.candidate
        asset = saved.asset
        db.add(asset)
        db.flush()
        if candidate.media_kind == ContentExtractionMediaKind.metadata:
            logger.info(
                "content_extraction_debug metadata_registered content_id=%s display_order=%s source_path=%s asset_id=%s storage_backend=%s storage_key=%s byte_size=%s",
                content.id,
                candidate.display_order,
                candidate.path,
                asset.id,
                asset.storage_backend.value,
                asset.storage_key,
                asset.byte_size,
            )
        else:
            logger.info(
                "content_extraction_debug media_registered content_id=%s display_order=%s media_kind=%s source_path=%s asset_id=%s storage_backend=%s storage_key=%s byte_size=%s content_type=%s",
                content.id,
                candidate.display_order,
                candidate.media_kind.value,
                candidate.path,
                asset.id,
                asset.storage_backend.value,
                asset.storage_key,
                asset.byte_size,
                asset.content_type,
            )
        db.add(
            ContentExtractionMedia(
                content_extraction=content,
                asset=asset,
                source_path=str(candidate.path),
                media_kind=candidate.media_kind,
                display_order=candidate.display_order,
            )
        )

    db.flush()
    content.media.sort(key=lambda item: (item.display_order, item.media_kind.value))
    logger.info(
        "content_extraction_debug download_attached content_id=%s media_count=%s elapsed_ms=%s",
        content.id,
        len(content.media),
        round((monotonic() - started) * 1000),
    )


def create_content_from_douyin_download(
    payload: ContentExtractionDownloadCreate,
    user: User,
    db: Session,
) -> ContentExtraction:
    content = create_pending_content_extraction(payload, user, db, processing_status="succeeded")
    attach_douyin_download_result(content, db)
    return content


def media_by_kind(content: ContentExtraction) -> tuple[list[ContentExtractionMedia], list[ContentExtractionMedia]]:
    sorted_media = sorted(content.media, key=lambda media: media.display_order)
    image_media = [item for item in sorted_media if item.media_kind == ContentExtractionMediaKind.image]
    video_media = [item for item in sorted_media if item.media_kind == ContentExtractionMediaKind.video]
    return image_media, video_media


def source_media_path(media: ContentExtractionMedia) -> Path:
    path = Path(media.source_path)
    if not path.exists() or not path.is_file() or path.stat().st_size <= 0:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"下载原始媒体文件不存在或为空：{media.source_path}")
    return path


def apply_content_text_extraction(content: ContentExtraction, db: Session) -> None:
    started = monotonic()
    image_media, video_media = media_by_kind(content)
    logger.info(
        "content_extraction_debug text_extraction_start content_id=%s media_type=%s image_count=%s video_count=%s",
        content.id,
        content.media_type,
        len(image_media),
        len(video_media),
    )

    try:
        if content.media_type == "video" or (video_media and not image_media):
            if not video_media:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="没有可提取的视频文件")
            video_path = source_media_path(video_media[0])
            logger.info(
                "content_extraction_debug video_transcription_start content_id=%s media_id=%s source_path=%s",
                content.id,
                video_media[0].id,
                video_path,
            )
            transcription = transcribe_video_audio(video_path)
            audio_stored = save_binary_file(FileAssetPurpose.douyin_audio.value, transcription.audio_bytes, ".mp3")
            audio_asset = FileAsset(
                purpose=FileAssetPurpose.douyin_audio,
                storage_backend=audio_stored.storage_backend,
                storage_key=audio_stored.storage_key,
                public_url=audio_stored.public_url,
                original_filename=f"{content.id}-audio.mp3",
                content_type="audio/mpeg",
                byte_size=audio_stored.byte_size,
                checksum_sha256=audio_stored.checksum_sha256,
            )
            db.add(audio_asset)
            db.flush()
            db.add(
                ContentExtractionMedia(
                    content_extraction=content,
                    asset=audio_asset,
                    source_path=f"generated:{content.id}-audio.mp3",
                    media_kind=ContentExtractionMediaKind.audio,
                    display_order=max((media.display_order for media in content.media), default=0) + 1,
                    extracted_text=transcription.text,
                )
            )
            video_media[0].extracted_text = transcription.text
            content.extracted_text = transcription.text
            logger.info(
                "content_extraction_debug video_transcription_done content_id=%s media_id=%s model=%s text_chars=%s audio_bytes=%s elapsed_ms=%s",
                content.id,
                video_media[0].id,
                transcription.model,
                len(transcription.text),
                len(transcription.audio_bytes),
                round((monotonic() - started) * 1000),
            )
        else:
            if not image_media:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="没有可提取的图文图片")
            if len(image_media) > MAX_CONTENT_EXTRACTION_IMAGES:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"图文图片数量超过上限：{MAX_CONTENT_EXTRACTION_IMAGES}",
                )
            images: list[ImageExtractionReference] = []
            for media in image_media:
                source_path = source_media_path(media)
                public_url = (media.asset.public_url or "").strip()
                if not public_url.startswith(("http://", "https://")):
                    raise HTTPException(
                        status_code=status.HTTP_502_BAD_GATEWAY,
                        detail=f"图片理解需要已上传对象存储后的公网 URL：{media.source_path}",
                    )
                images.append(ImageExtractionReference(url=public_url, source_path=str(source_path)))
            logger.info(
                "content_extraction_debug ordered_gallery_extract_start content_id=%s image_count=%s image_urls=%s source_paths=%s",
                content.id,
                len(images),
                [image.url for image in images],
                [image.source_path for image in images],
            )
            result = extract_ordered_gallery_comic_content(images)
            content.extracted_text = result.text
            content.story_content = None
            content.story_highlight = None
            content.target_audience = None
            content.story_summary_model = None
            content.story_summarized_at = None
            logger.info(
                "content_extraction_debug ordered_gallery_extract_done content_id=%s model=%s image_count=%s final_text_chars=%s elapsed_ms=%s",
                content.id,
                result.model,
                len(images),
                len(result.text),
                round((monotonic() - started) * 1000),
            )
            logger.info(
                "content_extraction_ai_debug final_extracted_text content_id=%s model=%s extracted_text=%s",
                content.id,
                result.model,
                result.text,
            )
    except HTTPException:
        raise
    except (LLMConfigError, LLMProviderError, LLMResponseError) as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc

    db.flush()
    logger.info(
        "content_extraction_debug text_extraction_done content_id=%s final_text_chars=%s elapsed_ms=%s",
        content.id,
        len(content.extracted_text or ""),
        round((monotonic() - started) * 1000),
    )


def apply_content_story_summary(content: ContentExtraction, *, skip_video: bool = False) -> None:
    image_media, video_media = media_by_kind(content)
    logger.info(
        "content_extraction_debug story_summary_replaced content_id=%s media_type=%s image_count=%s video_count=%s skip_video=%s",
        content.id,
        content.media_type,
        len(image_media),
        len(video_media),
        skip_video,
    )
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="故事总结步骤已被整组图片内容提取替代")


def mark_replicate_task_create_failed(content_id: str, error_message: str) -> None:
    with SessionLocal() as db:
        content = load_content_extraction(db, content_id)
        if not content:
            return
        content.processing_status = "succeeded"
        content.processing_error_message = None
        content.task_create_status = TASK_CREATE_FAILED_STATUS
        content.task_create_error_message = error_message
        db.commit()


def run_content_extraction_processing(
    content_id: str,
    replicate_payload: ContentExtractionReplicateTaskCreate | None = None,
    owner_user_id: str | None = None,
) -> None:
    started = monotonic()
    logger.info("content_extraction_debug background_start content_id=%s", content_id)
    with SessionLocal() as db:
        content = load_content_extraction(db, content_id)
        if not content:
            logger.warning("content_extraction_debug background_missing_content content_id=%s", content_id)
            return
        try:
            content.processing_status = "processing"
            content.processing_error_message = None
            db.commit()
            logger.info("content_extraction_debug background_step_committed content_id=%s step=mark_processing", content_id)
            content = load_content_extraction(db, content_id)
            attach_douyin_download_result(content, db)
            db.commit()
            logger.info("content_extraction_debug background_step_committed content_id=%s step=download", content_id)
            content = load_content_extraction(db, content_id)
            apply_content_text_extraction(content, db)
            db.commit()
            logger.info("content_extraction_debug background_step_committed content_id=%s step=text_extraction", content_id)
            content = load_content_extraction(db, content_id)
            if replicate_payload is not None:
                try:
                    if not owner_user_id:
                        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="缺少复刻任务创建用户")
                    content.task_create_status = TASK_CREATE_PENDING_STATUS
                    content.task_create_error_message = None
                    owner = db.get(User, owner_user_id)
                    if not owner:
                        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="复刻任务创建用户不存在")
                    task_id = create_generation_task_from_content_extraction(
                        content=content,
                        payload=replicate_payload,
                        user=owner,
                        db=db,
                    )
                    db.commit()
                    enqueue_task_from_thread(task_id)
                    logger.info(
                        "content_extraction_debug linked_task_created content_id=%s task_id=%s",
                        content_id,
                        task_id,
                    )
                    content = load_content_extraction(db, content_id)
                except HTTPException as exc:
                    db.rollback()
                    mark_replicate_task_create_failed(content_id, str(exc.detail))
                    logger.warning(
                        "content_extraction_debug linked_task_create_failed content_id=%s error_type=HTTPException status_code=%s detail=%s elapsed_ms=%s",
                        content_id,
                        exc.status_code,
                        exc.detail,
                        round((monotonic() - started) * 1000),
                    )
                    return
                except Exception as exc:
                    db.rollback()
                    mark_replicate_task_create_failed(content_id, str(exc))
                    logger.exception(
                        "content_extraction_debug linked_task_create_unexpected_failed content_id=%s elapsed_ms=%s",
                        content_id,
                        round((monotonic() - started) * 1000),
                    )
                    return
            content.processing_status = "succeeded"
            content.processing_error_message = None
            db.commit()
            logger.info(
                "content_extraction_debug background_done content_id=%s elapsed_ms=%s",
                content_id,
                round((monotonic() - started) * 1000),
            )
        except HTTPException as exc:
            db.rollback()
            failed = load_content_extraction(db, content_id)
            if failed:
                failed.processing_status = "failed"
                failed.processing_error_message = str(exc.detail)
                db.commit()
            logger.warning(
                "content_extraction_debug background_failed content_id=%s error_type=HTTPException status_code=%s detail=%s elapsed_ms=%s",
                content_id,
                exc.status_code,
                exc.detail,
                round((monotonic() - started) * 1000),
            )
        except Exception as exc:
            db.rollback()
            failed = load_content_extraction(db, content_id)
            if failed:
                failed.processing_status = "failed"
                failed.processing_error_message = str(exc)
                db.commit()
            logger.exception(
                "content_extraction_debug background_unexpected_failed content_id=%s elapsed_ms=%s",
                content_id,
                round((monotonic() - started) * 1000),
            )


@router.get("/douyin-health", response_model=ApiData[ContentExtractionHealthRead])
def douyin_health(user: User = Depends(current_user)) -> ApiData[ContentExtractionHealthRead]:
    try:
        result = check_douyin_import_health()
    except DouyinImportServiceError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
    return ApiData(data=ContentExtractionHealthRead(**result))


@router.get("", response_model=ApiList[ContentExtractionListItemRead])
def list_content_extractions(
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
    pagination: Pagination = Depends(get_pagination),
    query: str | None = Query(default=None, max_length=120),
    media_type: str | None = Query(default=None, max_length=40),
    result_status: str | None = Query(default=None, max_length=40),
) -> ApiList[ContentExtractionListItemRead]:
    statement = (
        select(ContentExtraction)
        .order_by(ContentExtraction.created_at.desc())
        .offset(pagination.offset)
        .limit(pagination.limit + 1)
    )
    if user.role != UserRole.admin:
        statement = statement.where(ContentExtraction.owner_user_id == user.id)
    if query:
        statement = statement.where(
            or_(
                ContentExtraction.raw_input.contains(query),
                ContentExtraction.source_url.contains(query),
                ContentExtraction.extracted_text.contains(query),
                ContentExtraction.story_content.contains(query),
                ContentExtraction.story_highlight.contains(query),
                ContentExtraction.target_audience.contains(query),
            )
        )
    if media_type:
        statement = statement.where(ContentExtraction.media_type == media_type)
    if result_status:
        if result_status == "processing":
            statement = statement.where(ContentExtraction.processing_status == "processing")
        elif result_status == "failed":
            statement = statement.where(ContentExtraction.processing_status == "failed")
        elif result_status == "extracted":
            statement = statement.where(ContentExtraction.extracted_text.is_not(None))
        elif result_status == "summarized":
            statement = statement.where(ContentExtraction.story_content.is_not(None))
        elif result_status == "downloaded":
            statement = statement.where(
                ContentExtraction.extracted_text.is_(None),
                ContentExtraction.story_content.is_(None),
            )
        else:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="不支持的结果筛选")

    contents = db.scalars(statement).all()
    visible = contents[: pagination.limit]
    counts: dict[str, int] = {content.id: 0 for content in visible}
    if counts:
        media_statement = select(ContentExtractionMedia.content_extraction_id).where(
            ContentExtractionMedia.content_extraction_id.in_(list(counts.keys())),
            ContentExtractionMedia.media_kind.in_([ContentExtractionMediaKind.image, ContentExtractionMediaKind.video]),
        )
        for content_id in db.scalars(media_statement).all():
            counts[content_id] = counts.get(content_id, 0) + 1

    return ApiList(
        items=[list_item_for_content(content, counts.get(content.id, 0)) for content in visible],
        page=build_page(pagination.limit, pagination.offset, len(contents)),
    )


@router.get("/{content_id}", response_model=ApiData[ContentExtractionRead])
def get_content_extraction(
    content_id: str,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> ApiData[ContentExtractionRead]:
    content = load_content_extraction(db, content_id)
    content = ensure_content_extraction_access(content, user)
    content.media.sort(key=lambda item: (item.display_order, item.media_kind.value))
    return ApiData(data=ContentExtractionRead.model_validate(content))


@router.post("/download", response_model=ApiData[ContentExtractionRead])
def download_content_extraction(
    payload: ContentExtractionDownloadCreate,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> ApiData[ContentExtractionRead]:
    content = create_content_from_douyin_download(payload, user, db)
    db.commit()
    content = load_content_extraction(db, content.id)
    content.media.sort(key=lambda item: (item.display_order, item.media_kind.value))
    return ApiData(data=ContentExtractionRead.model_validate(content))


@router.post("/process", response_model=ApiData[ContentExtractionRead])
def process_content_extraction(
    payload: ContentExtractionDownloadCreate,
    background_tasks: BackgroundTasks,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> ApiData[ContentExtractionRead]:
    content = create_pending_content_extraction(payload, user, db)
    db.commit()
    content = load_content_extraction(db, content.id)
    background_tasks.add_task(run_content_extraction_processing, content.id)
    return ApiData(data=ContentExtractionRead.model_validate(content))


@router.post("/replicate-task", response_model=ApiData[ContentExtractionRead], status_code=status.HTTP_202_ACCEPTED)
def replicate_content_as_task(
    payload: ContentExtractionReplicateTaskCreate,
    background_tasks: BackgroundTasks,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> ApiData[ContentExtractionRead]:
    content = create_pending_replicate_content_extraction(payload, user, db)
    db.commit()
    content = load_content_extraction(db, content.id)
    background_tasks.add_task(run_content_extraction_processing, content.id, payload, user.id)
    return ApiData(data=ContentExtractionRead.model_validate(content))


@router.post("/{content_id}/extract", response_model=ApiData[ContentExtractionRead])
def extract_content_text(
    content_id: str,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> ApiData[ContentExtractionRead]:
    content = load_content_extraction(db, content_id)
    content = ensure_content_extraction_access(content, user)
    apply_content_text_extraction(content, db)
    db.commit()
    content = load_content_extraction(db, content.id)
    content.media.sort(key=lambda item: (item.display_order, item.media_kind.value))
    return ApiData(data=ContentExtractionRead.model_validate(content))


@router.post("/{content_id}/summarize-story", response_model=ApiData[ContentExtractionRead])
def summarize_content_story(
    content_id: str,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> ApiData[ContentExtractionRead]:
    content = load_content_extraction(db, content_id)
    content = ensure_content_extraction_access(content, user)
    apply_content_story_summary(content)
    db.commit()
    content = load_content_extraction(db, content.id)
    content.media.sort(key=lambda item: (item.display_order, item.media_kind.value))
    return ApiData(data=ContentExtractionRead.model_validate(content))
