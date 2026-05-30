from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, status
from sqlalchemy import or_, select
from sqlalchemy.orm import Session, selectinload

from app.api.deps import current_user
from app.api.pagination import Pagination, build_page, get_pagination
from app.core.database import get_db
from app.models.entities import FileAsset, GenerationTask, Style, StyleReferenceImage, User
from app.models.enums import FileAssetPurpose, StyleStatus, UserRole
from app.schemas.common import ApiData, ApiList
from app.schemas.style import StyleCreate, StyleRead, StyleReferenceImageRead, StyleTestCreate, StyleUpdate
from app.services.storage import save_upload_file

router = APIRouter(prefix="/styles", tags=["styles"])


def style_load_options():
    return (
        selectinload(Style.reference_images).selectinload(StyleReferenceImage.asset),
        selectinload(Style.cover_asset),
    )


def style_to_read(style: Style, user: User) -> StyleRead:
    result = StyleRead.model_validate(style)
    result.generation_profile_configured = bool(style.generation_profile_key)
    if user.role != UserRole.admin:
        result.generation_profile_key = None
    return result


def normalize_profile_key(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    return cleaned or None


@router.get("", response_model=ApiList[StyleRead])
def list_styles(
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
    pagination: Pagination = Depends(get_pagination),
    query: str | None = Query(default=None, max_length=120),
    status_filter: StyleStatus | None = Query(default=None, alias="status"),
) -> ApiList[StyleRead]:
    statement = (
        select(Style)
        .options(*style_load_options())
        .order_by(Style.updated_at.desc())
        .offset(pagination.offset)
        .limit(pagination.limit + 1)
    )
    if query:
        statement = statement.where(or_(Style.name.contains(query), Style.description.contains(query)))
    if status_filter:
        statement = statement.where(Style.status == status_filter)

    styles = db.scalars(statement).all()
    visible_styles = styles[: pagination.limit]
    return ApiList(
        items=[style_to_read(style, user) for style in visible_styles],
        page=build_page(pagination.limit, pagination.offset, len(styles)),
    )


@router.post("", response_model=ApiData[StyleRead], status_code=status.HTTP_201_CREATED)
def create_style(payload: StyleCreate, user: User = Depends(current_user), db: Session = Depends(get_db)) -> ApiData[StyleRead]:
    data = payload.model_dump()
    data["generation_profile_key"] = normalize_profile_key(data.get("generation_profile_key"))
    if user.role != UserRole.admin and data["generation_profile_key"] is not None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="只有管理员可以设置生成配置 Key")

    style = Style(**data)
    db.add(style)
    db.commit()
    style = db.scalar(select(Style).where(Style.id == style.id).options(*style_load_options()))
    return ApiData(data=style_to_read(style, user))


@router.get("/{style_id}", response_model=ApiData[StyleRead])
def get_style(style_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)) -> ApiData[StyleRead]:
    style = db.scalar(
        select(Style)
        .where(Style.id == style_id)
        .options(*style_load_options())
    )
    if not style:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="风格不存在")
    return ApiData(data=style_to_read(style, user))


@router.patch("/{style_id}", response_model=ApiData[StyleRead])
def update_style(style_id: str, payload: StyleUpdate, user: User = Depends(current_user), db: Session = Depends(get_db)) -> ApiData[StyleRead]:
    style = db.scalar(select(Style).where(Style.id == style_id))
    if not style:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="风格不存在")

    data = payload.model_dump(exclude_unset=True)
    if "generation_profile_key" in data:
        if user.role != UserRole.admin:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="只有管理员可以设置生成配置 Key")
        data["generation_profile_key"] = normalize_profile_key(data["generation_profile_key"])

    for key, value in data.items():
        setattr(style, key, value)

    db.commit()
    style = db.scalar(select(Style).where(Style.id == style_id).options(*style_load_options()))
    return ApiData(data=style_to_read(style, user))


@router.delete("/{style_id}", response_model=ApiData[dict[str, bool]])
def delete_style(style_id: str, _: User = Depends(current_user), db: Session = Depends(get_db)) -> ApiData[dict[str, bool]]:
    style = db.scalar(select(Style).where(Style.id == style_id))
    if not style:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="风格不存在")

    task_count = db.query(GenerationTask).filter(GenerationTask.style_id == style_id).count()
    if task_count > 0:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="已有任务引用该风格，不能删除")

    db.delete(style)
    db.commit()
    return ApiData(data={"deleted": True})


@router.post("/{style_id}/reference-images")
async def upload_reference_image(
    style_id: str,
    file: UploadFile,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> ApiData[StyleReferenceImageRead]:
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
    if style.cover_asset_id is None:
        style.cover_asset_id = asset.id
    db.commit()
    reference = db.scalar(
        select(StyleReferenceImage)
        .where(StyleReferenceImage.id == reference.id)
        .options(selectinload(StyleReferenceImage.asset))
    )
    return ApiData(data=StyleReferenceImageRead.model_validate(reference))


@router.delete("/{style_id}/reference-images/{reference_id}", response_model=ApiData[dict[str, bool]])
def delete_reference_image(
    style_id: str,
    reference_id: str,
    _: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> ApiData[dict[str, bool]]:
    style = db.scalar(select(Style).where(Style.id == style_id))
    if not style:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="风格不存在")

    reference = db.scalar(
        select(StyleReferenceImage).where(
            StyleReferenceImage.id == reference_id,
            StyleReferenceImage.style_id == style_id,
        )
    )
    if not reference:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="参考图不存在")

    asset_id = reference.asset_id
    db.delete(reference)
    db.flush()

    if style.cover_asset_id == asset_id:
        next_reference = db.scalar(
            select(StyleReferenceImage)
            .where(StyleReferenceImage.style_id == style_id)
            .order_by(StyleReferenceImage.display_order.asc())
        )
        style.cover_asset_id = next_reference.asset_id if next_reference else None

    remaining_asset_refs = db.query(StyleReferenceImage).filter(StyleReferenceImage.asset_id == asset_id).count()
    if remaining_asset_refs == 0:
        asset = db.scalar(select(FileAsset).where(FileAsset.id == asset_id))
        if asset:
            db.delete(asset)

    db.commit()
    return ApiData(data={"deleted": True})


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
