import logging
from datetime import datetime
from time import sleep

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, Query, UploadFile, status
from sqlalchemy import or_, select
from sqlalchemy.orm import Session, selectinload

from app.api.deps import current_user
from app.api.pagination import Pagination, build_page, get_pagination
from app.core.database import SessionLocal, get_db
from app.models.entities import FileAsset, User, UserCharacter
from app.models.enums import FileAssetPurpose
from app.schemas.character import CharacterReferenceDescriptionResult, UserCharacterRead
from app.schemas.common import ApiData, ApiList
from app.services.llm import LLMProviderError
from app.services.media_text_extraction import describe_character_reference_image
from app.services.storage import image_suffix_for_content_type, save_bytes

router = APIRouter(prefix="/characters", tags=["characters"])
logger = logging.getLogger(__name__)
CHARACTER_DESCRIPTION_RETRY_COUNT = 3


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


async def read_character_reference_upload(file: UploadFile) -> tuple[bytes, str]:
    content_type = file.content_type or ""
    image_suffix_for_content_type(content_type)
    content = await file.read()
    if not content:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="参考图不能为空")
    return content, content_type


def describe_reference_or_502(content: bytes, content_type: str) -> str:
    try:
        return describe_character_reference_image(content, content_type).text
    except LLMProviderError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc


def fill_character_description_from_reference(
    *,
    character_id: str,
    content: bytes,
    content_type: str,
) -> None:
    for attempt in range(1, CHARACTER_DESCRIPTION_RETRY_COUNT + 2):
        try:
            description = describe_character_reference_image(content, content_type).text
            with SessionLocal() as db:
                character = db.get(UserCharacter, character_id)
                if character is None or character.deleted_at is not None:
                    return
                if character.description and character.description.strip():
                    return
                character.description = description
                db.commit()
            logger.info(
                "character reference description filled character_id=%s attempt=%s",
                character_id,
                attempt,
            )
            return
        except Exception as exc:  # noqa: BLE001
            if attempt > CHARACTER_DESCRIPTION_RETRY_COUNT:
                logger.warning(
                    "character reference description failed character_id=%s attempts=%s error=%s",
                    character_id,
                    attempt,
                    exc,
                )
                return
            sleep(min(attempt, 3))


def enqueue_character_description_fill(
    *,
    background_tasks: BackgroundTasks | None,
    character_id: str,
    content: bytes,
    content_type: str,
) -> None:
    if background_tasks is None:
        return
    background_tasks.add_task(
        fill_character_description_from_reference,
        character_id=character_id,
        content=content,
        content_type=content_type,
    )


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
    background_tasks: BackgroundTasks,
    name: str = Form(...),
    description: str | None = Form(default=None),
    file: UploadFile = File(...),
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> ApiData[UserCharacterRead]:
    content, content_type = await read_character_reference_upload(file)
    cleaned_description = normalize_character_description(description)
    stored = save_bytes(
        FileAssetPurpose.user_character_reference.value,
        content,
        content_type,
        file.filename,
    )
    asset = FileAsset(
        purpose=FileAssetPurpose.user_character_reference,
        storage_backend=stored.storage_backend,
        storage_key=stored.storage_key,
        public_url=stored.public_url,
        original_filename=file.filename,
        content_type=content_type,
        byte_size=stored.byte_size,
        checksum_sha256=stored.checksum_sha256,
    )
    db.add(asset)
    db.flush()
    character = UserCharacter(
        owner_user_id=user.id,
        name=normalize_character_name(name),
        description=cleaned_description,
        reference_asset_id=asset.id,
    )
    db.add(character)
    db.commit()
    if not cleaned_description:
        enqueue_character_description_fill(
            background_tasks=background_tasks,
            character_id=character.id,
            content=content,
            content_type=content_type,
        )
    character = load_user_character(db, character.id, user)
    return ApiData(data=UserCharacterRead.model_validate(character))


@router.post("/describe-reference", response_model=ApiData[CharacterReferenceDescriptionResult])
async def describe_character_reference(
    file: UploadFile = File(...),
    _: User = Depends(current_user),
) -> ApiData[CharacterReferenceDescriptionResult]:
    content, content_type = await read_character_reference_upload(file)
    return ApiData(data=CharacterReferenceDescriptionResult(description=describe_reference_or_502(content, content_type)))


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
    background_tasks: BackgroundTasks,
    name: str | None = Form(default=None),
    description: str | None = Form(default=None),
    file: UploadFile | None = File(default=None),
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> ApiData[UserCharacterRead]:
    character = load_user_character(db, character_id, user)
    cleaned_description: str | None = None
    description_was_sent = description is not None
    if name is not None:
        character.name = normalize_character_name(name)
    if description_was_sent:
        cleaned_description = normalize_character_description(description)
        character.description = cleaned_description
    if file is not None:
        content, content_type = await read_character_reference_upload(file)
        stored = save_bytes(
            FileAssetPurpose.user_character_reference.value,
            content,
            content_type,
            file.filename,
        )
        asset = FileAsset(
            purpose=FileAssetPurpose.user_character_reference,
            storage_backend=stored.storage_backend,
            storage_key=stored.storage_key,
            public_url=stored.public_url,
            original_filename=file.filename,
            content_type=content_type,
            byte_size=stored.byte_size,
            checksum_sha256=stored.checksum_sha256,
        )
        db.add(asset)
        db.flush()
        character.reference_asset_id = asset.id
    db.commit()
    if file is not None and not (character.description and character.description.strip()):
        enqueue_character_description_fill(
            background_tasks=background_tasks,
            character_id=character.id,
            content=content,
            content_type=content_type,
        )
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
