import hashlib
import mimetypes
from dataclasses import dataclass
from pathlib import Path
from tempfile import NamedTemporaryFile
from urllib.parse import quote
from uuid import uuid4

import requests
from fastapi import HTTPException, UploadFile, status
from PIL import Image, ImageOps, UnidentifiedImageError

from app.core.config import get_settings
from app.models.enums import StorageBackend

ALLOWED_IMAGE_TYPES = {"image/png", "image/jpeg", "image/webp"}
ASSET_URL_VARIANT_ORIGINAL = "original"
ASSET_URL_VARIANT_THUMBNAIL = "thumbnail"


@dataclass(frozen=True)
class StoredFile:
    storage_backend: StorageBackend
    storage_key: str
    byte_size: int
    checksum_sha256: str
    public_url: str | None = None


def configured_storage_backend() -> StorageBackend:
    raw_backend = get_settings().storage_backend.strip().lower()
    try:
        return StorageBackend(raw_backend)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="存储后端配置不支持") from exc


def image_suffix_for_content_type(content_type: str) -> str:
    clean_content_type = content_type.split(";", 1)[0].strip().lower()
    if clean_content_type not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail="仅支持 PNG、JPEG 或 WebP 图片")
    return mimetypes.guess_extension(clean_content_type) or ".png"


def safe_storage_key(purpose: str, suffix: str) -> str:
    if not suffix.startswith(".") or "/" in suffix or "\\" in suffix:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="文件后缀不合法")
    return str(Path(purpose) / f"{uuid4().hex}{suffix}")


def write_local_file(storage_key: str, content: bytes) -> None:
    absolute_path = resolve_storage_key(storage_key)
    absolute_path.parent.mkdir(parents=True, exist_ok=True)
    absolute_path.write_bytes(content)


def qiniu_auth():
    settings = get_settings()
    missing = [
        name
        for name, value in {
            "QINIU_ACCESS_KEY": settings.qiniu_access_key,
            "QINIU_SECRET_KEY": settings.qiniu_secret_key,
            "QINIU_BUCKET": settings.qiniu_bucket,
            "QINIU_BUCKET_DOMAIN": settings.qiniu_bucket_domain,
        }.items()
        if not value.strip()
    ]
    if missing:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"七牛对象存储配置缺失：{', '.join(missing)}",
        )
    try:
        from qiniu import Auth
    except ImportError as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="缺少 qiniu Python SDK") from exc
    return Auth(settings.qiniu_access_key, settings.qiniu_secret_key)


def qiniu_base_url(storage_key: str) -> str:
    domain = get_settings().qiniu_bucket_domain.strip().rstrip("/")
    if not domain:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="七牛 Bucket 域名未配置")
    if not domain.startswith(("http://", "https://")):
        domain = f"https://{domain}"
    return f"{domain}/{quote(storage_key, safe='/')}"


def qiniu_signed_url(base_url: str) -> str:
    settings = get_settings()
    if not settings.qiniu_private_bucket:
        return base_url
    return qiniu_auth().private_download_url(base_url, expires=settings.qiniu_download_url_expires_seconds)


def qiniu_asset_url(storage_key: str, variant: str) -> str:
    base_url = qiniu_base_url(storage_key)
    if variant == ASSET_URL_VARIANT_THUMBNAIL:
        thumbnail_fop = get_settings().qiniu_thumbnail_fop.strip()
        if not thumbnail_fop:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="七牛缩略图处理参数未配置")
        base_url = f"{base_url}?{thumbnail_fop}"
    return qiniu_signed_url(base_url)


def upload_qiniu_file(storage_key: str, local_path: Path) -> str:
    try:
        from qiniu import put_file_v2
    except ImportError as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="缺少 qiniu Python SDK") from exc

    settings = get_settings()
    token = qiniu_auth().upload_token(settings.qiniu_bucket, storage_key, 3600)
    result, info = put_file_v2(token, storage_key, str(local_path), version="v2")
    status_code = getattr(info, "status_code", None)
    if status_code != 200 or not isinstance(result, dict) or result.get("key") != storage_key:
        error_text = getattr(info, "text_body", "") or getattr(info, "error", "") or "未知错误"
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"七牛上传失败：{error_text}")
    return qiniu_base_url(storage_key)


def store_content(purpose: str, content: bytes, suffix: str) -> StoredFile:
    if not content:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="文件内容不能为空")
    storage_key = safe_storage_key(purpose, suffix)
    checksum = hashlib.sha256(content).hexdigest()
    backend = configured_storage_backend()
    if backend == StorageBackend.local:
        write_local_file(storage_key, content)
        return StoredFile(StorageBackend.local, storage_key, len(content), checksum)
    if backend == StorageBackend.qiniu:
        with NamedTemporaryFile(suffix=suffix) as temp_file:
            temp_file.write(content)
            temp_file.flush()
            public_url = upload_qiniu_file(storage_key, Path(temp_file.name))
        return StoredFile(StorageBackend.qiniu, storage_key, len(content), checksum, public_url)
    raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="存储后端配置不支持")


async def save_upload_file(purpose: str, file: UploadFile) -> StoredFile:
    suffix = image_suffix_for_content_type(file.content_type or "")
    original_suffix = Path(file.filename or "").suffix.lower()
    if original_suffix in {".png", ".jpg", ".jpeg", ".webp"}:
        suffix = original_suffix
    content = await file.read()
    return store_content(purpose, content, suffix)


def save_bytes(purpose: str, content: bytes, content_type: str, filename_hint: str | None = None) -> StoredFile:
    suffix = image_suffix_for_content_type(content_type)
    if filename_hint:
        original_suffix = Path(filename_hint).suffix.lower()
        if original_suffix in {".png", ".jpg", ".jpeg", ".webp"}:
            suffix = original_suffix
    return store_content(purpose, content, suffix)


def save_binary_file(purpose: str, content: bytes, suffix: str) -> StoredFile:
    return store_content(purpose, content, suffix)


def resolve_storage_key(storage_key: str) -> Path:
    if Path(storage_key).is_absolute() or ".." in Path(storage_key).parts:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="非法文件路径")

    return get_settings().storage_root / storage_key


def local_thumbnail_path(asset_id: str) -> Path:
    return get_settings().storage_root / "_derived" / "thumbnails" / f"{asset_id}.webp"


def ensure_local_thumbnail(asset) -> Path:
    if not str(asset.content_type).startswith("image/"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="该文件不支持缩略图")
    source_path = resolve_storage_key(asset.storage_key)
    if not source_path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="本地文件不存在")
    thumbnail_path = local_thumbnail_path(asset.id)
    if thumbnail_path.exists() and thumbnail_path.stat().st_mtime >= source_path.stat().st_mtime:
        return thumbnail_path

    settings = get_settings()
    thumbnail_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with Image.open(source_path) as image:
            thumbnail = ImageOps.fit(
                image.convert("RGB"),
                (settings.local_thumbnail_width, settings.local_thumbnail_height),
                method=Image.Resampling.LANCZOS,
            )
            thumbnail.save(thumbnail_path, format="WEBP", quality=75)
    except UnidentifiedImageError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="图片文件无法生成缩略图") from exc
    return thumbnail_path


def asset_content_url(asset, variant: str = ASSET_URL_VARIANT_ORIGINAL) -> str:
    if variant not in {ASSET_URL_VARIANT_ORIGINAL, ASSET_URL_VARIANT_THUMBNAIL}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="资产访问变体不支持")
    if asset.storage_backend == StorageBackend.qiniu:
        return qiniu_asset_url(asset.storage_key, variant)
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="本地资产没有外部访问 URL")


def materialize_asset_to_local(asset) -> Path:
    if asset.storage_backend == StorageBackend.local:
        path = resolve_storage_key(asset.storage_key)
        if not path.exists():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="本地文件不存在")
        return path
    if asset.storage_backend == StorageBackend.qiniu:
        suffix = Path(asset.storage_key).suffix or mimetypes.guess_extension(asset.content_type) or ".bin"
        cache_path = get_settings().storage_root / "_cache" / "qiniu" / f"{asset.id}{suffix}"
        if cache_path.exists() and cache_path.stat().st_size > 0:
            return cache_path
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        response = requests.get(qiniu_asset_url(asset.storage_key, ASSET_URL_VARIANT_ORIGINAL), timeout=120)
        if response.status_code != 200 or not response.content:
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="七牛资产下载失败")
        cache_path.write_bytes(response.content)
        return cache_path
    raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="资产存储后端不支持")
