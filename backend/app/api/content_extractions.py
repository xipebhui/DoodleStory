import mimetypes
import re
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query, status
from PIL import Image, UnidentifiedImageError
from sqlalchemy import or_, select
from sqlalchemy.orm import Session, selectinload

from app.api.deps import current_user
from app.api.pagination import Pagination, build_page, get_pagination
from app.core.database import get_db
from app.models.entities import ContentExtraction, ContentExtractionMedia, FileAsset, User
from app.models.enums import ContentExtractionMediaKind, FileAssetPurpose, UserRole
from app.schemas.common import ApiData, ApiList
from app.schemas.content_extraction import (
    ContentExtractionDownloadCreate,
    ContentExtractionHealthRead,
    ContentExtractionListItemRead,
    ContentExtractionRead,
)
from app.services.douyin_import_service import (
    DouyinImportConfigError,
    DouyinImportServiceError,
    check_douyin_import_health,
    download_douyin_content,
)
from app.services.llm import LLMConfigError, LLMProviderError, LLMResponseError
from app.services.media_text_extraction import (
    MAX_CONTENT_EXTRACTION_IMAGES,
    extract_image_text,
    transcribe_video_audio,
)
from app.services.storage import materialize_asset_to_local, save_binary_file

router = APIRouter(prefix="/content-extractions", tags=["content-extractions"])

DOUYIN_URL_PATTERN = re.compile(
    r"https?://(?:v\.douyin\.com/[A-Za-z0-9_.~%-]+/?|www\.douyin\.com/(?:video|note)/[A-Za-z0-9_.~%-]+(?:\?[^\s，,。！!？?；;]*)?)"
)
IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp"}
VIDEO_SUFFIXES = {".mp4"}


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


def content_preview(text: str | None) -> str | None:
    if not text:
        return None
    return text.strip().replace("\n", " ")[:160]


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
            )
        )

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
        items=[
            ContentExtractionListItemRead(
                id=content.id,
                owner_user_id=content.owner_user_id,
                source_url=content.source_url,
                media_type=content.media_type,
                aweme_id=content.aweme_id,
                extracted_text_preview=content_preview(content.extracted_text),
                media_count=counts.get(content.id, 0),
                created_at=content.created_at,
                updated_at=content.updated_at,
            )
            for content in visible
        ],
        page=build_page(pagination.limit, pagination.offset, len(contents)),
    )


@router.get("/{content_id}", response_model=ApiData[ContentExtractionRead])
def get_content_extraction(
    content_id: str,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> ApiData[ContentExtractionRead]:
    content = db.scalar(
        select(ContentExtraction)
        .where(ContentExtraction.id == content_id)
        .options(*content_extraction_options())
    )
    content = ensure_content_extraction_access(content, user)
    content.media.sort(key=lambda item: (item.display_order, item.media_kind.value))
    return ApiData(data=ContentExtractionRead.model_validate(content))


@router.post("/download", response_model=ApiData[ContentExtractionRead])
def download_content_extraction(
    payload: ContentExtractionDownloadCreate,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> ApiData[ContentExtractionRead]:
    source_url = extract_douyin_url(payload.raw_input)
    try:
        result = download_douyin_content(source_url)
    except DouyinImportConfigError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except DouyinImportServiceError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc

    content = ContentExtraction(
        owner_user_id=user.id,
        raw_input=payload.raw_input,
        source_url=source_url,
        media_type=result.media_type,
        aweme_id=result.aweme_id,
        output_dir=str(result.output_dir),
        manifest_path=str(result.manifest_path) if result.manifest_path else None,
    )
    db.add(content)
    db.flush()

    display_order = 1
    for path in result.media_files:
        media_kind = media_kind_for_path(path)
        asset = save_path_as_asset(path, media_kind)
        db.add(asset)
        db.flush()
        db.add(
            ContentExtractionMedia(
                content_extraction_id=content.id,
                asset_id=asset.id,
                source_path=str(path),
                media_kind=media_kind,
                display_order=display_order,
            )
        )
        display_order += 1

    for path in result.metadata_files:
        asset = save_path_as_asset(path, ContentExtractionMediaKind.metadata)
        db.add(asset)
        db.flush()
        db.add(
            ContentExtractionMedia(
                content_extraction_id=content.id,
                asset_id=asset.id,
                source_path=str(path),
                media_kind=ContentExtractionMediaKind.metadata,
                display_order=display_order,
            )
        )
        display_order += 1

    db.commit()
    content = db.scalar(
        select(ContentExtraction)
        .where(ContentExtraction.id == content.id)
        .options(*content_extraction_options())
    )
    return ApiData(data=ContentExtractionRead.model_validate(content))


@router.post("/{content_id}/extract", response_model=ApiData[ContentExtractionRead])
def extract_content_text(
    content_id: str,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> ApiData[ContentExtractionRead]:
    content = db.scalar(
        select(ContentExtraction)
        .where(ContentExtraction.id == content_id)
        .options(*content_extraction_options())
    )
    content = ensure_content_extraction_access(content, user)

    image_media = [
        item
        for item in sorted(content.media, key=lambda media: media.display_order)
        if item.media_kind == ContentExtractionMediaKind.image
    ]
    video_media = [
        item
        for item in sorted(content.media, key=lambda media: media.display_order)
        if item.media_kind == ContentExtractionMediaKind.video
    ]

    try:
        if content.media_type == "video" or (video_media and not image_media):
            if not video_media:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="没有可提取的视频文件")
            video_asset = video_media[0].asset
            video_path = materialize_asset_to_local(video_asset)
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
                    content_extraction_id=content.id,
                    asset_id=audio_asset.id,
                    source_path=f"generated:{content.id}-audio.mp3",
                    media_kind=ContentExtractionMediaKind.audio,
                    display_order=max((media.display_order for media in content.media), default=0) + 1,
                    extracted_text=transcription.text,
                )
            )
            video_media[0].extracted_text = transcription.text
            content.extracted_text = transcription.text
        else:
            if not image_media:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="没有可提取的图文图片")
            if len(image_media) > MAX_CONTENT_EXTRACTION_IMAGES:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"图文图片数量超过上限：{MAX_CONTENT_EXTRACTION_IMAGES}",
                )
            parts: list[str] = []
            for media in image_media:
                asset = media.asset
                image_path = materialize_asset_to_local(asset)
                result = extract_image_text(image_path, asset.content_type)
                media.extracted_text = result.text
                if result.text.strip():
                    parts.append(result.text.strip())
            content.extracted_text = "\n\n".join(parts)
    except HTTPException:
        raise
    except (LLMConfigError, LLMProviderError, LLMResponseError) as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc

    db.commit()
    content = db.scalar(
        select(ContentExtraction)
        .where(ContentExtraction.id == content.id)
        .options(*content_extraction_options())
    )
    return ApiData(data=ContentExtractionRead.model_validate(content))
