from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import current_user
from app.core.database import get_db
from app.models.entities import FileAsset, User
from app.services.storage import resolve_storage_key

router = APIRouter(prefix="/assets", tags=["assets"])


@router.get("/{asset_id}/content")
def get_asset_content(asset_id: str, _: User = Depends(current_user), db: Session = Depends(get_db)) -> FileResponse:
    asset = db.scalar(select(FileAsset).where(FileAsset.id == asset_id))
    if not asset:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="文件不存在")

    path = resolve_storage_key(asset.storage_key)
    if not path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="本地文件不存在")

    return FileResponse(path, media_type=asset.content_type, filename=asset.original_filename)
