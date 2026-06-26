from datetime import datetime

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Response, UploadFile, status
from sqlalchemy import or_, select
from sqlalchemy.orm import Session, selectinload

from app.api.deps import current_user
from app.api.pagination import Pagination, build_page, get_pagination
from app.core.config import get_settings
from app.core.database import get_db
from app.models.entities import AudioReference, FileAsset, User
from app.models.enums import FileAssetPurpose, UserRole
from app.schemas.audio import (
    AudioReferenceListItem,
    AudioReferenceRead,
    AudioReferenceTestRequest,
    AudioReferenceTranscription,
    AudioReferenceUpdate,
)
from app.schemas.common import ApiData, ApiList
from app.services.local_whisper import LocalWhisperError, transcribe_audio_content
from app.services.siliconflow_voice import SiliconFlowVoiceClient, SiliconFlowVoiceError
from app.services.storage import materialize_asset_to_local, read_upload_audio_content, save_binary_file

router = APIRouter(prefix="/audio-references", tags=["audio-references"])


def ensure_audio_reference_access(reference: AudioReference | None, user: User) -> AudioReference:
    if not reference or reference.deleted_at is not None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="音频参考不存在")
    if user.role != UserRole.admin and reference.owner_user_id != user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="没有权限访问该音频参考")
    return reference


def audio_reference_read(reference: AudioReference) -> AudioReferenceRead:
    return AudioReferenceRead(
        id=reference.id,
        owner_user_id=reference.owner_user_id,
        owner_display_name=reference.owner.display_name if reference.owner else None,
        owner_email=reference.owner.email if reference.owner else None,
        name=reference.name,
        description=reference.description,
        reference_text=reference.reference_text,
        voice_provider=reference.voice_provider,
        voice_model=reference.voice_model,
        voice_name=reference.voice_name,
        speech_speed=reference.speech_speed,
        deleted_at=reference.deleted_at,
        asset=reference.asset,
        created_at=reference.created_at,
        updated_at=reference.updated_at,
    )


@router.get("", response_model=ApiList[AudioReferenceListItem])
def list_audio_references(
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
    pagination: Pagination = Depends(get_pagination),
    query: str | None = Query(default=None, max_length=120),
) -> ApiList[AudioReferenceListItem]:
    statement = (
        select(AudioReference)
        .where(AudioReference.deleted_at.is_(None))
        .options(selectinload(AudioReference.asset), selectinload(AudioReference.owner))
        .order_by(AudioReference.created_at.desc())
        .offset(pagination.offset)
        .limit(pagination.limit + 1)
    )
    if user.role != UserRole.admin:
        statement = statement.where(AudioReference.owner_user_id == user.id)
    if query:
        statement = statement.where(or_(AudioReference.name.contains(query), AudioReference.description.contains(query)))

    references = db.scalars(statement).all()
    visible = references[: pagination.limit]
    return ApiList(
        items=[
            AudioReferenceListItem(
                id=reference.id,
                owner_user_id=reference.owner_user_id,
                owner_display_name=reference.owner.display_name if reference.owner else None,
                owner_email=reference.owner.email if reference.owner else None,
                name=reference.name,
                description=reference.description,
                voice_provider=reference.voice_provider,
                voice_model=reference.voice_model,
                voice_name=reference.voice_name,
                speech_speed=reference.speech_speed,
                asset=reference.asset,
                created_at=reference.created_at,
                updated_at=reference.updated_at,
            )
            for reference in visible
        ],
        page=build_page(pagination.limit, pagination.offset, len(references)),
    )


@router.post("", response_model=ApiData[AudioReferenceRead], status_code=status.HTTP_201_CREATED)
async def create_audio_reference(
    name: str = Form(..., min_length=1, max_length=120),
    description: str = Form(default="", max_length=500),
    reference_text: str = Form(default="", max_length=2000),
    voice_provider: str = Form(default="", max_length=80),
    voice_model: str = Form(default="", max_length=160),
    voice_name: str = Form(default="", max_length=255),
    speech_speed: float = Form(default=1.0, ge=0.5, le=2.0),
    file: UploadFile = File(...),
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> ApiData[AudioReferenceRead]:
    content, content_type, suffix = await read_upload_audio_content(file)
    clean_reference_text = reference_text.strip()
    if not clean_reference_text:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="参考音频必须先完成本地转写")
    stored = save_binary_file(FileAssetPurpose.audio_reference.value, content, suffix)
    asset = FileAsset(
        purpose=FileAssetPurpose.audio_reference,
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
    reference = AudioReference(
        owner_user_id=user.id,
        name=name.strip(),
        description=description.strip() or None,
        reference_text=clean_reference_text,
        asset_id=asset.id,
        voice_provider=voice_provider.strip() or None,
        voice_model=voice_model.strip() or None,
        voice_name=voice_name.strip() or None,
        speech_speed=speech_speed,
    )
    db.add(reference)
    db.commit()
    reference = db.scalar(
        select(AudioReference)
        .where(AudioReference.id == reference.id)
        .options(selectinload(AudioReference.asset), selectinload(AudioReference.owner))
    )
    return ApiData(data=audio_reference_read(reference))


@router.post("/transcribe", response_model=ApiData[AudioReferenceTranscription])
async def transcribe_audio_reference(
    file: UploadFile = File(...),
    _user: User = Depends(current_user),
) -> ApiData[AudioReferenceTranscription]:
    content, _content_type, suffix = await read_upload_audio_content(file)
    try:
        text = transcribe_audio_content(content, suffix)
    except LocalWhisperError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    return ApiData(data=AudioReferenceTranscription(text=text))


def resolve_audio_reference_voice(db: Session, reference: AudioReference) -> tuple[str, str]:
    settings = get_settings()
    provider = (reference.voice_provider or "").strip() or settings.video_tts_provider.strip()
    model = (reference.voice_model or "").strip() or settings.video_tts_model.strip()
    voice_name = (reference.voice_name or "").strip()
    if provider != "siliconflow":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"暂不支持的音频参考 TTS provider：{provider}")
    if voice_name:
        return model, voice_name
    reference_text = (reference.reference_text or "").strip()
    if not reference_text:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="音频参考缺少参考文本，无法注册声音")
    try:
        reference_path = materialize_asset_to_local(reference.asset)
        voice_name = SiliconFlowVoiceClient().upload_reference_voice(
            file_path=reference_path,
            model=model,
            custom_name=f"doodlestory_audio_{reference.id}",
            text=reference_text,
            timeout=settings.video_tts_timeout_seconds,
        )
    except (SiliconFlowVoiceError, HTTPException) as exc:
        if isinstance(exc, HTTPException):
            raise
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
    reference.voice_provider = provider
    reference.voice_model = model
    reference.voice_name = voice_name
    db.commit()
    db.refresh(reference)
    return model, voice_name


@router.patch("/{reference_id}", response_model=ApiData[AudioReferenceRead])
def update_audio_reference(
    reference_id: str,
    payload: AudioReferenceUpdate,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> ApiData[AudioReferenceRead]:
    reference = db.scalar(
        select(AudioReference)
        .where(AudioReference.id == reference_id)
        .options(selectinload(AudioReference.asset), selectinload(AudioReference.owner))
    )
    reference = ensure_audio_reference_access(reference, user)
    reference.name = payload.name.strip()
    reference.description = (payload.description or "").strip() or None
    reference.speech_speed = payload.speech_speed
    db.commit()
    reference = db.scalar(
        select(AudioReference)
        .where(AudioReference.id == reference_id)
        .options(selectinload(AudioReference.asset), selectinload(AudioReference.owner))
    )
    return ApiData(data=audio_reference_read(reference))


@router.post("/{reference_id}/test")
def test_audio_reference(
    reference_id: str,
    payload: AudioReferenceTestRequest,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> Response:
    reference = db.scalar(
        select(AudioReference)
        .where(AudioReference.id == reference_id)
        .options(selectinload(AudioReference.asset), selectinload(AudioReference.owner))
    )
    reference = ensure_audio_reference_access(reference, user)
    model, voice_name = resolve_audio_reference_voice(db, reference)
    settings = get_settings()
    try:
        audio_bytes, content_type = SiliconFlowVoiceClient().generate_speech(
            text=payload.text,
            voice_uri=voice_name,
            model=model,
            response_format=settings.video_tts_response_format,
            sample_rate=settings.video_tts_sample_rate,
            speed=reference.speech_speed,
            gain=settings.video_tts_gain,
            timeout=settings.video_tts_timeout_seconds,
        )
    except SiliconFlowVoiceError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
    return Response(content=audio_bytes, media_type=content_type or "audio/mpeg")


@router.get("/{reference_id}", response_model=ApiData[AudioReferenceRead])
def get_audio_reference(
    reference_id: str,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> ApiData[AudioReferenceRead]:
    reference = db.scalar(
        select(AudioReference)
        .where(AudioReference.id == reference_id)
        .options(selectinload(AudioReference.asset), selectinload(AudioReference.owner))
    )
    return ApiData(data=audio_reference_read(ensure_audio_reference_access(reference, user)))


@router.delete("/{reference_id}", response_model=ApiData[dict[str, bool]])
def delete_audio_reference(
    reference_id: str,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> ApiData[dict[str, bool]]:
    reference = db.scalar(select(AudioReference).where(AudioReference.id == reference_id))
    reference = ensure_audio_reference_access(reference, user)
    reference.deleted_at = datetime.utcnow()
    db.commit()
    return ApiData(data={"deleted": True})
