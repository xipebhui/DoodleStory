from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import FileResponse, RedirectResponse, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import current_user
from app.core.database import get_db
from app.models.entities import (
    AudioReference,
    ContentExtractionMedia,
    FileAsset,
    GeneratedImage,
    StyleReferenceImage,
    TaskCharacter,
    TaskCharacterAppearance,
    TaskDownload,
    User,
    UserCharacter,
    VideoTask,
    VideoTaskAudioSegment,
)
from app.models.enums import FileAssetPurpose, UserRole
from app.schemas.common import ApiData
from app.schemas.style import FileAssetRead
from app.models.enums import StorageBackend
from app.services.storage import (
    ASSET_URL_VARIANT_ORIGINAL,
    ASSET_URL_VARIANT_THUMBNAIL,
    asset_content_url,
    ensure_local_thumbnail,
    resolve_storage_key,
)

router = APIRouter(prefix="/assets", tags=["assets"])
ASSET_CACHE_HEADERS = {
    "Cache-Control": "private, max-age=31536000, immutable",
    "Vary": "Cookie",
}


def can_read_asset(asset: FileAsset, user: User, db: Session) -> bool:
    if asset.purpose == FileAssetPurpose.style_reference:
        reference = db.scalar(select(StyleReferenceImage).where(StyleReferenceImage.asset_id == asset.id))
        return reference is not None
    if asset.purpose == FileAssetPurpose.user_character_reference:
        if user.role == UserRole.admin:
            return True
        character = db.scalar(
            select(UserCharacter).where(
                UserCharacter.reference_asset_id == asset.id,
                UserCharacter.owner_user_id == user.id,
                UserCharacter.deleted_at.is_(None),
            )
        )
        if character is not None:
            return True
        task_reference = db.scalar(
            select(TaskCharacterAppearance)
            .join(TaskCharacterAppearance.character)
            .join(TaskCharacter.task)
            .where(
                TaskCharacterAppearance.reference_image_id == asset.id,
                TaskCharacter.task.has(owner_user_id=user.id),
            )
        )
        return task_reference is not None
    if user.role == UserRole.admin:
        return True
    if asset.purpose == FileAssetPurpose.character_reference:
        task_reference = db.scalar(
            select(TaskCharacterAppearance)
            .join(TaskCharacterAppearance.character)
            .join(TaskCharacter.task)
            .where(
                TaskCharacterAppearance.reference_image_id == asset.id,
                TaskCharacter.task.has(owner_user_id=user.id),
            )
        )
        return task_reference is not None
    if asset.purpose == FileAssetPurpose.generated_image:
        image = db.scalar(
            select(GeneratedImage)
            .join(GeneratedImage.task)
            .where(GeneratedImage.asset_id == asset.id, GeneratedImage.task.has(owner_user_id=user.id))
        )
        return image is not None
    if asset.purpose == FileAssetPurpose.download_archive:
        download = db.scalar(
            select(TaskDownload)
            .join(TaskDownload.task)
            .where(TaskDownload.asset_id == asset.id, TaskDownload.task.has(owner_user_id=user.id))
        )
        return download is not None
    if asset.purpose == FileAssetPurpose.audio_reference:
        reference = db.scalar(
            select(AudioReference).where(
                AudioReference.asset_id == asset.id,
                AudioReference.owner_user_id == user.id,
                AudioReference.deleted_at.is_(None),
            )
        )
        if reference is not None:
            return True
        video_task = db.scalar(
            select(VideoTask).where(
                VideoTask.audio_reference_asset_id_snapshot == asset.id,
                VideoTask.owner_user_id == user.id,
            )
        )
        return video_task is not None
    if asset.purpose == FileAssetPurpose.generated_audio:
        video_task = db.scalar(
            select(VideoTask).where(
                VideoTask.narration_audio_asset_id == asset.id,
                VideoTask.owner_user_id == user.id,
            )
        )
        if video_task is not None:
            return True
        audio_segment = db.scalar(
            select(VideoTaskAudioSegment)
            .join(VideoTaskAudioSegment.video_task)
            .where(
                VideoTaskAudioSegment.asset_id == asset.id,
                VideoTask.owner_user_id == user.id,
            )
        )
        return audio_segment is not None
    if asset.purpose == FileAssetPurpose.generated_video:
        video_task = db.scalar(
            select(VideoTask).where(
                VideoTask.output_video_asset_id == asset.id,
                VideoTask.owner_user_id == user.id,
            )
        )
        return video_task is not None
    if asset.purpose in {FileAssetPurpose.douyin_media, FileAssetPurpose.douyin_audio, FileAssetPurpose.douyin_metadata}:
        media = db.scalar(
            select(ContentExtractionMedia)
            .join(ContentExtractionMedia.content_extraction)
            .where(
                ContentExtractionMedia.asset_id == asset.id,
                ContentExtractionMedia.content_extraction.has(owner_user_id=user.id),
            )
        )
        return media is not None
    return False


@router.get("/{asset_id}", response_model=ApiData[FileAssetRead])
def get_asset(asset_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)) -> ApiData[FileAssetRead]:
    asset = db.scalar(select(FileAsset).where(FileAsset.id == asset_id))
    if not asset:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="文件不存在")
    if not can_read_asset(asset, user, db):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="没有权限访问该文件")

    return ApiData(data=FileAssetRead.model_validate(asset))


@router.get("/{asset_id}/content", response_model=None)
def get_asset_content(
    asset_id: str,
    variant: str = Query(default=ASSET_URL_VARIANT_ORIGINAL),
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> Response:
    asset = db.scalar(select(FileAsset).where(FileAsset.id == asset_id))
    if not asset:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="文件不存在")
    if not can_read_asset(asset, user, db):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="没有权限访问该文件")
    if variant not in {ASSET_URL_VARIANT_ORIGINAL, ASSET_URL_VARIANT_THUMBNAIL}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="资产访问变体不支持")

    if asset.storage_backend == StorageBackend.qiniu:
        return RedirectResponse(
            asset_content_url(asset, variant),
            status_code=status.HTTP_307_TEMPORARY_REDIRECT,
            headers=ASSET_CACHE_HEADERS,
        )

    if variant == ASSET_URL_VARIANT_THUMBNAIL:
        thumbnail_path = ensure_local_thumbnail(asset)
        return FileResponse(thumbnail_path, media_type="image/webp", filename=f"{asset.id}.webp", headers=ASSET_CACHE_HEADERS)

    path = resolve_storage_key(asset.storage_key)
    if not path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="本地文件不存在")

    return FileResponse(path, media_type=asset.content_type, filename=asset.original_filename, headers=ASSET_CACHE_HEADERS)
