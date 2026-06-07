import logging
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
from app.schemas.style import (
    STYLE_ASPECT_RATIOS,
    StyleCreate,
    StyleRead,
    StyleReferenceImageRead,
    StyleTestCreate,
    StyleTestRead,
    StyleUpdate,
)
from app.services.image_generation import (
    ImageProviderConfigError,
    ImageProviderResponseError,
    generate_xg_image,
)
from app.services.prompt_templates import render_prompt_template
from app.services.storage import save_upload_file

router = APIRouter(prefix="/styles", tags=["styles"])
logger = logging.getLogger(__name__)


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


def normalize_aspect_ratio(value: str) -> str:
    cleaned = value.strip()
    if cleaned not in STYLE_ASPECT_RATIOS:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="画面比例不支持")
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
    statement = statement.where(Style.deleted_at.is_(None))

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
    data["aspect_ratio"] = normalize_aspect_ratio(data["aspect_ratio"])

    style = Style(**data)
    db.add(style)
    db.commit()
    style = db.scalar(select(Style).where(Style.id == style.id).options(*style_load_options()))
    return ApiData(data=style_to_read(style))


@router.get("/{style_id}", response_model=ApiData[StyleRead])
def get_style(style_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)) -> ApiData[StyleRead]:
    style = db.scalar(
        select(Style)
        .where(Style.id == style_id, Style.deleted_at.is_(None))
        .options(*style_load_options())
    )
    if not style:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="风格不存在")
    return ApiData(data=style_to_read(style))


@router.patch("/{style_id}", response_model=ApiData[StyleRead])
def update_style(style_id: str, payload: StyleUpdate, user: User = Depends(current_user), db: Session = Depends(get_db)) -> ApiData[StyleRead]:
    style = db.scalar(select(Style).where(Style.id == style_id, Style.deleted_at.is_(None)))
    if not style:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="风格不存在")

    data = payload.model_dump(exclude_unset=True)
    if "image_model_name" in data:
        data["image_model_name"] = normalize_image_model_name(data["image_model_name"])
    if "aspect_ratio" in data:
        data["aspect_ratio"] = normalize_aspect_ratio(data["aspect_ratio"])

    for key, value in data.items():
        setattr(style, key, value)

    db.commit()
    style = db.scalar(select(Style).where(Style.id == style_id, Style.deleted_at.is_(None)).options(*style_load_options()))
    return ApiData(data=style_to_read(style))


@router.delete("/{style_id}", response_model=ApiData[dict[str, bool]])
def delete_style(style_id: str, _: User = Depends(current_user), db: Session = Depends(get_db)) -> ApiData[dict[str, bool]]:
    style = db.scalar(select(Style).where(Style.id == style_id))
    if not style:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="风格不存在")
    if style.deleted_at is not None:
        return ApiData(data={"deleted": True})

    task_count = db.query(GenerationTask).filter(GenerationTask.style_id == style_id).count()
    test_count = db.query(StyleTest).filter(StyleTest.style_id == style_id).count()
    if task_count > 0 or test_count > 0:
        style.deleted_at = datetime.utcnow()
        style.status = StyleStatus.disabled
        style.name = f"{style.name[:56]} [deleted:{style.id[:8]}]"
        db.commit()
        return ApiData(data={"deleted": True})

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
    style = db.scalar(select(Style).where(Style.id == style_id, Style.deleted_at.is_(None)))
    if not style:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="风格不存在")

    stored = await save_upload_file(FileAssetPurpose.style_reference.value, file)
    asset = FileAsset(
        purpose=FileAssetPurpose.style_reference,
        storage_backend=stored.storage_backend,
        storage_key=stored.storage_key,
        public_url=stored.public_url,
        original_filename=file.filename,
        content_type=file.content_type or "application/octet-stream",
        byte_size=stored.byte_size,
        checksum_sha256=stored.checksum_sha256,
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
    style = db.scalar(select(Style).where(Style.id == style_id, Style.deleted_at.is_(None)))
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
        .where(Style.id == style_id, Style.deleted_at.is_(None))
        .options(selectinload(Style.reference_images).selectinload(StyleReferenceImage.asset))
    )
    if not style:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="风格不存在")

    composed_prompt = render_prompt_template(
        "style_test_image_prompt_v1.md",
        {
            "style_prompt": style.style_prompt.strip(),
            "aspect_ratio": style.aspect_ratio,
            "test_text": payload.test_text.strip(),
        },
    )
    now = datetime.utcnow()
    style_test = StyleTest(
        style_id=style.id,
        test_text=payload.test_text,
        style_prompt_snapshot=style.style_prompt,
        image_model_name_snapshot=style.image_model_name,
        aspect_ratio_snapshot=style.aspect_ratio,
        composed_prompt=composed_prompt,
        status=WorkflowStatus.running,
        attempts=1,
        started_at=now,
    )
    db.add(style_test)
    db.commit()
    db.refresh(style_test)
    logger.info(
        "style test started style_test_id=%s style_id=%s image_model=%s test_text_chars=%s provider_reference_count=%s preview_reference_count=%s",
        style_test.id,
        style.id,
        style.image_model_name,
        len(payload.test_text),
        0,
        len(style.reference_images),
    )

    try:
        generated = generate_xg_image(
            prompt=composed_prompt,
            reference_paths=[],
            image_model_name=style.image_model_name,
            aspect_ratio=style.aspect_ratio,
        )
        asset = FileAsset(
            purpose=FileAssetPurpose.generated_image,
            storage_backend=generated.storage_backend,
            storage_key=generated.storage_key,
            public_url=generated.public_url,
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
        logger.info(
            "style test succeeded style_test_id=%s style_id=%s asset_storage_key=%s bytes=%s",
            style_test.id,
            style.id,
            generated.storage_key,
            generated.byte_size,
        )
    except (ImageProviderConfigError, ImageProviderResponseError) as exc:
        logger.warning(
            "style test failed style_test_id=%s style_id=%s error_type=%s error=%s",
            style_test.id,
            style.id,
            exc.__class__.__name__,
            exc,
        )
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
