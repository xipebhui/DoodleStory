from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, status
from sqlalchemy import or_, select
from sqlalchemy.orm import Session, selectinload

from app.api.deps import current_user
from app.api.pagination import Pagination, build_page, get_pagination
from app.core.database import get_db
from app.models.entities import FileAsset, GenerationTask, Style, StyleReferenceImage, StyleTest, User
from app.models.enums import FileAssetPurpose, StyleStatus, WorkflowStatus
from app.schemas.common import ApiData, ApiList
from app.schemas.style import StyleCreate, StyleRead, StyleReferenceImageRead, StyleTestCreate, StyleTestRead, StyleUpdate
from app.services.image_generation import (
    ImageProviderConfigError,
    ImageProviderResponseError,
    generate_xg_image_edit,
)
from app.services.storage import save_upload_file
from app.services.storage import resolve_storage_key

router = APIRouter(prefix="/styles", tags=["styles"])


def style_load_options():
    return (
        selectinload(Style.reference_images).selectinload(StyleReferenceImage.asset),
        selectinload(Style.cover_asset),
    )


def style_to_read(style: Style) -> StyleRead:
    return StyleRead.model_validate(style)


def normalize_image_model_name(value: str) -> str:
    cleaned = value.strip()
    if not cleaned:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="风格必须绑定生图模型名")
    return cleaned


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
        items=[style_to_read(style) for style in visible_styles],
        page=build_page(pagination.limit, pagination.offset, len(styles)),
    )


@router.post("", response_model=ApiData[StyleRead], status_code=status.HTTP_201_CREATED)
def create_style(payload: StyleCreate, user: User = Depends(current_user), db: Session = Depends(get_db)) -> ApiData[StyleRead]:
    data = payload.model_dump()
    data["image_model_name"] = normalize_image_model_name(data["image_model_name"])

    style = Style(**data)
    db.add(style)
    db.commit()
    style = db.scalar(select(Style).where(Style.id == style.id).options(*style_load_options()))
    return ApiData(data=style_to_read(style))


@router.get("/{style_id}", response_model=ApiData[StyleRead])
def get_style(style_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)) -> ApiData[StyleRead]:
    style = db.scalar(
        select(Style)
        .where(Style.id == style_id)
        .options(*style_load_options())
    )
    if not style:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="风格不存在")
    return ApiData(data=style_to_read(style))


@router.patch("/{style_id}", response_model=ApiData[StyleRead])
def update_style(style_id: str, payload: StyleUpdate, user: User = Depends(current_user), db: Session = Depends(get_db)) -> ApiData[StyleRead]:
    style = db.scalar(select(Style).where(Style.id == style_id))
    if not style:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="风格不存在")

    data = payload.model_dump(exclude_unset=True)
    if "image_model_name" in data:
        data["image_model_name"] = normalize_image_model_name(data["image_model_name"])

    for key, value in data.items():
        setattr(style, key, value)

    db.commit()
    style = db.scalar(select(Style).where(Style.id == style_id).options(*style_load_options()))
    return ApiData(data=style_to_read(style))


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


@router.post("/{style_id}/tests", response_model=ApiData[StyleTestRead])
def create_style_test(
    style_id: str,
    payload: StyleTestCreate,
    _: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> ApiData[StyleTestRead]:
    style = db.scalar(
        select(Style)
        .where(Style.id == style_id)
        .options(selectinload(Style.reference_images).selectinload(StyleReferenceImage.asset))
    )
    if not style:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="风格不存在")

    if not style.reference_images:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="风格测试至少需要一张参考图")

    composed_prompt = "\n\n".join(
        [
            style.style_prompt.strip(),
            f"画面内容：{payload.test_text.strip()}",
            "输出要求：9:16 竖图，无文字、无水印、无 Logo。",
        ]
    )
    now = datetime.utcnow()
    style_test = StyleTest(
        style_id=style.id,
        test_text=payload.test_text,
        style_prompt_snapshot=style.style_prompt,
        image_model_name_snapshot=style.image_model_name,
        composed_prompt=composed_prompt,
        status=WorkflowStatus.running,
        attempts=1,
        started_at=now,
    )
    db.add(style_test)
    db.commit()
    db.refresh(style_test)

    try:
        reference_paths = [resolve_storage_key(reference.asset.storage_key) for reference in style.reference_images]
        generated = generate_xg_image_edit(
            prompt=composed_prompt,
            reference_paths=reference_paths,
            image_model_name=style.image_model_name,
        )
        asset = FileAsset(
            purpose=FileAssetPurpose.generated_image,
            storage_key=generated.storage_key,
            original_filename=generated.original_filename,
            content_type=generated.content_type,
            byte_size=generated.byte_size,
            checksum_sha256=generated.checksum_sha256,
        )
        db.add(asset)
        db.flush()
        style_test.output_asset_id = asset.id
        style_test.provider_request_id = generated.provider_request_id
        style_test.status = WorkflowStatus.succeeded
        style_test.finished_at = datetime.utcnow()
        style.last_tested_at = style_test.finished_at
    except (ImageProviderConfigError, ImageProviderResponseError) as exc:
        style_test.status = WorkflowStatus.failed
        style_test.error_code = exc.__class__.__name__
        style_test.error_message = str(exc)
        style_test.finished_at = datetime.utcnow()

    db.commit()
    style_test = db.scalar(
        select(StyleTest)
        .where(StyleTest.id == style_test.id)
        .options(selectinload(StyleTest.output_asset))
    )
    return ApiData(data=StyleTestRead.model_validate(style_test))
