from datetime import datetime

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from sqlalchemy import or_, select
from sqlalchemy.orm import Session, selectinload

from app.api.deps import current_user
from app.api.pagination import Pagination, build_page, get_pagination
from app.core.database import get_db
from app.models.entities import FileAsset, User, UserCharacter
from app.models.enums import FileAssetPurpose
from app.schemas.character import UserCharacterRead
from app.schemas.common import ApiData, ApiList
from app.services.storage import save_upload_file

router = APIRouter(prefix="/characters", tags=["characters"])


def normalize_character_name(name: str) -> str:
    cleaned = " ".join(name.strip().split())
    if not cleaned:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="角色名字不能为空")
    if len(cleaned) > 120:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="角色名字不能超过 120 个字符")
    return cleaned


def normalize_character_description(description: str | None) -> str | None:
    if description is None:
        return None
    cleaned = description.strip()
    if len(cleaned) > 1000:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="角色描述不能超过 1000 个字符")
    return cleaned or None


def load_user_character(db: Session, character_id: str, user: User, *, include_deleted: bool = False) -> UserCharacter:
    statement = (
        select(UserCharacter)
        .where(UserCharacter.id == character_id, UserCharacter.owner_user_id == user.id)
        .options(selectinload(UserCharacter.reference_asset))
    )
    if not include_deleted:
        statement = statement.where(UserCharacter.deleted_at.is_(None))
    character = db.scalar(statement)
    if not character:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="角色不存在")
    return character


@router.get("", response_model=ApiList[UserCharacterRead])
def list_characters(
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
    pagination: Pagination = Depends(get_pagination),
    query: str | None = Query(default=None, max_length=120),
) -> ApiList[UserCharacterRead]:
    statement = (
        select(UserCharacter)
        .where(UserCharacter.owner_user_id == user.id, UserCharacter.deleted_at.is_(None))
        .options(selectinload(UserCharacter.reference_asset))
        .order_by(UserCharacter.updated_at.desc())
        .offset(pagination.offset)
        .limit(pagination.limit + 1)
    )
    if query:
        statement = statement.where(or_(UserCharacter.name.contains(query), UserCharacter.description.contains(query)))
    characters = db.scalars(statement).all()
    visible = characters[: pagination.limit]
    return ApiList(
        items=[UserCharacterRead.model_validate(character) for character in visible],
        page=build_page(pagination.limit, pagination.offset, len(characters)),
    )


@router.post("", response_model=ApiData[UserCharacterRead], status_code=status.HTTP_201_CREATED)
async def create_character(
    name: str = Form(...),
    description: str | None = Form(default=None),
    file: UploadFile = File(...),
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> ApiData[UserCharacterRead]:
    stored = await save_upload_file(FileAssetPurpose.user_character_reference.value, file)
    asset = FileAsset(
        purpose=FileAssetPurpose.user_character_reference,
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
    character = UserCharacter(
        owner_user_id=user.id,
        name=normalize_character_name(name),
        description=normalize_character_description(description),
        reference_asset_id=asset.id,
    )
    db.add(character)
    db.commit()
    character = load_user_character(db, character.id, user)
    return ApiData(data=UserCharacterRead.model_validate(character))


@router.get("/{character_id}", response_model=ApiData[UserCharacterRead])
def get_character(
    character_id: str,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> ApiData[UserCharacterRead]:
    return ApiData(data=UserCharacterRead.model_validate(load_user_character(db, character_id, user)))


@router.patch("/{character_id}", response_model=ApiData[UserCharacterRead])
async def update_character(
    character_id: str,
    name: str | None = Form(default=None),
    description: str | None = Form(default=None),
    file: UploadFile | None = File(default=None),
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> ApiData[UserCharacterRead]:
    character = load_user_character(db, character_id, user)
    if name is not None:
        character.name = normalize_character_name(name)
    if description is not None:
        character.description = normalize_character_description(description)
    if file is not None:
        stored = await save_upload_file(FileAssetPurpose.user_character_reference.value, file)
        asset = FileAsset(
            purpose=FileAssetPurpose.user_character_reference,
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
        character.reference_asset_id = asset.id
    db.commit()
    character = load_user_character(db, character_id, user)
    return ApiData(data=UserCharacterRead.model_validate(character))


@router.delete("/{character_id}", response_model=ApiData[dict[str, bool]])
def delete_character(
    character_id: str,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> ApiData[dict[str, bool]]:
    character = load_user_character(db, character_id, user, include_deleted=True)
    if character.deleted_at is None:
        character.deleted_at = datetime.utcnow()
        db.commit()
    return ApiData(data={"deleted": True})
