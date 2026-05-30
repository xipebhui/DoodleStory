from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.api.deps import current_user
from app.core.database import get_db
from app.models.entities import FileAsset, Style, StyleReferenceImage, User
from app.models.enums import FileAssetPurpose, WorkflowStatus
from app.schemas.common import ApiData
from app.schemas.style import StyleCreate, StyleRead, StyleTestCreate, StyleUpdate
from app.services.storage import save_upload_file

router = APIRouter(prefix="/styles", tags=["styles"])


@router.get("", response_model=ApiData[list[StyleRead]])
def list_styles(_: User = Depends(current_user), db: Session = Depends(get_db)) -> ApiData[list[StyleRead]]:
    styles = db.scalars(
        select(Style)
        .options(selectinload(Style.reference_images).selectinload(StyleReferenceImage.asset))
        .order_by(Style.updated_at.desc())
    ).all()
    return ApiData(data=[StyleRead.model_validate(style) for style in styles])


@router.post("", response_model=ApiData[StyleRead], status_code=status.HTTP_201_CREATED)
def create_style(payload: StyleCreate, _: User = Depends(current_user), db: Session = Depends(get_db)) -> ApiData[StyleRead]:
    style = Style(**payload.model_dump())
    db.add(style)
    db.commit()
    db.refresh(style)
    return ApiData(data=StyleRead.model_validate(style))


@router.get("/{style_id}", response_model=ApiData[StyleRead])
def get_style(style_id: str, _: User = Depends(current_user), db: Session = Depends(get_db)) -> ApiData[StyleRead]:
    style = db.scalar(
        select(Style)
        .where(Style.id == style_id)
        .options(selectinload(Style.reference_images).selectinload(StyleReferenceImage.asset))
    )
    if not style:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="风格不存在")
    return ApiData(data=StyleRead.model_validate(style))


@router.patch("/{style_id}", response_model=ApiData[StyleRead])
def update_style(style_id: str, payload: StyleUpdate, _: User = Depends(current_user), db: Session = Depends(get_db)) -> ApiData[StyleRead]:
    style = db.scalar(select(Style).where(Style.id == style_id))
    if not style:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="风格不存在")

    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(style, key, value)

    db.commit()
    db.refresh(style)
    return ApiData(data=StyleRead.model_validate(style))


@router.delete("/{style_id}")
def delete_style(style_id: str, _: User = Depends(current_user), db: Session = Depends(get_db)) -> dict[str, bool]:
    style = db.scalar(select(Style).where(Style.id == style_id))
    if not style:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="风格不存在")

    db.delete(style)
    db.commit()
    return {"deleted": True}


@router.post("/{style_id}/reference-images")
async def upload_reference_image(
    style_id: str,
    file: UploadFile,
    _: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> dict[str, str]:
    style = db.scalar(select(Style).where(Style.id == style_id))
    if not style:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="风格不存在")

    storage_key, byte_size, checksum = await save_upload_file(FileAssetPurpose.style_reference.value, file)
    asset = FileAsset(
        purpose=FileAssetPurpose.style_reference,
        storage_key=storage_key,
        original_filename=file.filename,
        content_type=file.content_type or "application/octet-stream",
        byte_size=byte_size,
        checksum_sha256=checksum,
    )
    db.add(asset)
    db.flush()
    order = db.query(StyleReferenceImage).filter(StyleReferenceImage.style_id == style_id).count()
    reference = StyleReferenceImage(style_id=style_id, asset_id=asset.id, display_order=order)
    db.add(reference)
    db.commit()
    return {"id": reference.id}


@router.post("/{style_id}/tests")
def create_style_test(
    style_id: str,
    payload: StyleTestCreate,
    _: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> None:
    style = db.scalar(select(Style).where(Style.id == style_id))
    if not style:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="风格不存在")

    raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="图片生成 Provider 尚未接入，暂不允许创建风格测试")
