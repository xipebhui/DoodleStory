from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import current_user
from app.core.database import get_db
from app.models.entities import FileAsset, GeneratedImage, StyleReferenceImage, TaskDownload, User
from app.models.enums import FileAssetPurpose, UserRole
from app.schemas.common import ApiData
from app.schemas.style import FileAssetRead
from app.services.storage import resolve_storage_key

router = APIRouter(prefix="/assets", tags=["assets"])


def can_read_asset(asset: FileAsset, user: User, db: Session) -> bool:
    if asset.purpose == FileAssetPurpose.style_reference:
        reference = db.scalar(select(StyleReferenceImage).where(StyleReferenceImage.asset_id == asset.id))
        return reference is not None
    if user.role == UserRole.admin:
        return True
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
    return False


@router.get("/{asset_id}", response_model=ApiData[FileAssetRead])
def get_asset(asset_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)) -> ApiData[FileAssetRead]:
    asset = db.scalar(select(FileAsset).where(FileAsset.id == asset_id))
    if not asset:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="文件不存在")
    if not can_read_asset(asset, user, db):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="没有权限访问该文件")

    return ApiData(data=FileAssetRead.model_validate(asset))


@router.get("/{asset_id}/content")
def get_asset_content(asset_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)) -> FileResponse:
    asset = db.scalar(select(FileAsset).where(FileAsset.id == asset_id))
    if not asset:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="文件不存在")
    if not can_read_asset(asset, user, db):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="没有权限访问该文件")

    path = resolve_storage_key(asset.storage_key)
    if not path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="本地文件不存在")

    return FileResponse(path, media_type=asset.content_type, filename=asset.original_filename)
