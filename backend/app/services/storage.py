import hashlib
from pathlib import Path
from uuid import uuid4

from fastapi import HTTPException, UploadFile, status

from app.core.config import get_settings

ALLOWED_IMAGE_TYPES = {"image/png", "image/jpeg", "image/webp"}


async def save_upload_file(purpose: str, file: UploadFile) -> tuple[str, int, str]:
    if file.content_type not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail="仅支持 PNG、JPEG 或 WebP 图片")

    settings = get_settings()
    today = Path(purpose)
    suffix = Path(file.filename or "").suffix.lower()
    storage_key = str(today / f"{uuid4().hex}{suffix}")
    absolute_path = settings.storage_root / storage_key
    absolute_path.parent.mkdir(parents=True, exist_ok=True)

    content = await file.read()
    absolute_path.write_bytes(content)
    checksum = hashlib.sha256(content).hexdigest()
    return storage_key, len(content), checksum


def resolve_storage_key(storage_key: str) -> Path:
    if Path(storage_key).is_absolute() or ".." in Path(storage_key).parts:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="非法文件路径")

    return get_settings().storage_root / storage_key
