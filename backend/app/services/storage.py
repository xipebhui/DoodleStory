import hashlib
import mimetypes
from pathlib import Path
from uuid import uuid4

from fastapi import HTTPException, UploadFile, status

from app.core.config import get_settings

ALLOWED_IMAGE_TYPES = {"image/png", "image/jpeg", "image/webp"}


def image_suffix_for_content_type(content_type: str) -> str:
    clean_content_type = content_type.split(";", 1)[0].strip().lower()
    if clean_content_type not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail="仅支持 PNG、JPEG 或 WebP 图片")
    return mimetypes.guess_extension(clean_content_type) or ".png"


async def save_upload_file(purpose: str, file: UploadFile) -> tuple[str, int, str]:
    suffix = image_suffix_for_content_type(file.content_type or "")

    settings = get_settings()
    today = Path(purpose)
    original_suffix = Path(file.filename or "").suffix.lower()
    if original_suffix in {".png", ".jpg", ".jpeg", ".webp"}:
        suffix = original_suffix
    storage_key = str(today / f"{uuid4().hex}{suffix}")
    absolute_path = settings.storage_root / storage_key
    absolute_path.parent.mkdir(parents=True, exist_ok=True)

    content = await file.read()
    if not content:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="上传文件不能为空")
    absolute_path.write_bytes(content)
    checksum = hashlib.sha256(content).hexdigest()
    return storage_key, len(content), checksum


def save_bytes(purpose: str, content: bytes, content_type: str, filename_hint: str | None = None) -> tuple[str, int, str]:
    if not content:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="文件内容不能为空")

    suffix = image_suffix_for_content_type(content_type)
    if filename_hint:
        original_suffix = Path(filename_hint).suffix.lower()
        if original_suffix in {".png", ".jpg", ".jpeg", ".webp"}:
            suffix = original_suffix

    storage_key = str(Path(purpose) / f"{uuid4().hex}{suffix}")
    absolute_path = get_settings().storage_root / storage_key
    absolute_path.parent.mkdir(parents=True, exist_ok=True)
    absolute_path.write_bytes(content)
    checksum = hashlib.sha256(content).hexdigest()
    return storage_key, len(content), checksum


def resolve_storage_key(storage_key: str) -> Path:
    if Path(storage_key).is_absolute() or ".." in Path(storage_key).parts:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="非法文件路径")

    return get_settings().storage_root / storage_key
