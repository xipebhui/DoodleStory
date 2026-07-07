import hashlib
import logging
import mimetypes
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from urllib.parse import quote, urlparse
from uuid import uuid4

import requests
from fastapi import HTTPException, UploadFile, status
from PIL import Image, ImageOps, UnidentifiedImageError

from app.core.config import get_settings
from app.models.enums import StorageBackend

logger = logging.getLogger(__name__)
ALLOWED_IMAGE_TYPES = {"image/png", "image/jpeg", "image/webp"}
IMAGE_UPLOAD_MAX_BYTES = 10 * 1024 * 1024
AUDIO_UPLOAD_MAX_BYTES = 50 * 1024 * 1024
ALLOWED_AUDIO_TYPES = {
    "audio/mpeg",
    "audio/mp3",
    "audio/wav",
    "audio/x-wav",
    "audio/wave",
    "audio/webm",
    "audio/ogg",
    "audio/mp4",
    "video/mp4",
}
AUDIO_TYPE_SUFFIXES = {
    "audio/mpeg": ".mp3",
    "audio/mp3": ".mp3",
    "audio/wav": ".wav",
    "audio/x-wav": ".wav",
    "audio/wave": ".wav",
    "audio/webm": ".webm",
    "audio/ogg": ".ogg",
    "audio/mp4": ".m4a",
    "video/mp4": ".mp4",
}
IMAGE_FORMAT_CONTENT_TYPES = {
    "PNG": "image/png",
    "JPEG": "image/jpeg",
    "WEBP": "image/webp",
}
IMAGE_TYPE_SUFFIXES = {
    "image/png": {".png"},
    "image/jpeg": {".jpg", ".jpeg"},
    "image/webp": {".webp"},
}
ASSET_URL_VARIANT_ORIGINAL = "original"
ASSET_URL_VARIANT_THUMBNAIL = "thumbnail"


@dataclass(frozen=True)
class StoredFile:
    storage_backend: StorageBackend
    storage_key: str
    byte_size: int
    checksum_sha256: str
    public_url: str | None = None


@dataclass(frozen=True)
class QiniuConfig:
    access_key: str
    secret_key: str
    bucket: str
    public_base_url: str
    use_https: bool


@dataclass(frozen=True)
class AliyunOssConfig:
    access_key_id: str
    access_key_secret: str
    bucket: str
    endpoint: str
    public_base_url: str


def qiniu_config() -> QiniuConfig:
    settings = get_settings()
    qiniu_public_base_url = settings.qiniu_bucket_domain.strip()
    qny_public_base_url = settings.qny_public_base_url.strip() or settings.qny_domain.strip()
    return QiniuConfig(
        access_key=settings.qiniu_access_key.strip() or settings.qny_access_key.strip(),
        secret_key=settings.qiniu_secret_key.strip() or settings.qny_secret_key.strip(),
        bucket=settings.qiniu_bucket.strip() or settings.qny_bucket.strip(),
        public_base_url=qiniu_public_base_url or qny_public_base_url,
        use_https=True if qiniu_public_base_url else settings.qny_use_https,
    )


def aliyun_oss_config() -> AliyunOssConfig:
    settings = get_settings()
    return AliyunOssConfig(
        access_key_id=settings.aliyun_oss_access_key_id.strip(),
        access_key_secret=settings.aliyun_oss_access_key_secret.strip(),
        bucket=settings.aliyun_oss_bucket.strip(),
        endpoint=settings.aliyun_oss_endpoint.strip().rstrip("/"),
        public_base_url=settings.aliyun_oss_public_base_url.strip().rstrip("/"),
    )


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


async def read_upload_image_content(file: UploadFile) -> bytes:
    content = await file.read(IMAGE_UPLOAD_MAX_BYTES + 1)
    if len(content) > IMAGE_UPLOAD_MAX_BYTES:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="图片不能超过 10MB")
    return content


async def read_upload_audio_content(file: UploadFile) -> tuple[bytes, str, str]:
    content = await file.read(AUDIO_UPLOAD_MAX_BYTES + 1)
    if len(content) > AUDIO_UPLOAD_MAX_BYTES:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="音频不能超过 50MB")
    if not content:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="文件内容不能为空")
    content_type = (file.content_type or "").split(";", 1)[0].strip().lower()
    if content_type not in ALLOWED_AUDIO_TYPES:
        raise HTTPException(status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail="仅支持 MP3、WAV、M4A、WebM、OGG 或 MP4 音频")
    filename_suffix = Path(file.filename or "").suffix.lower()
    suffix = AUDIO_TYPE_SUFFIXES[content_type]
    allowed_suffixes = {".mp3", ".wav", ".m4a", ".mp4", ".webm", ".ogg"}
    if filename_suffix in allowed_suffixes:
        suffix = filename_suffix
    return content, content_type, suffix


def detect_verified_image_content_type(content: bytes, declared_content_type: str | None = None) -> str:
    if not content:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="文件内容不能为空")
    try:
        with Image.open(BytesIO(content)) as image:
            image.verify()
            detected = IMAGE_FORMAT_CONTENT_TYPES.get((image.format or "").upper())
    except (UnidentifiedImageError, OSError) as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="上传文件不是有效图片") from exc

    if detected not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail="仅支持 PNG、JPEG 或 WebP 图片")

    declared = (declared_content_type or "").split(";", 1)[0].strip().lower()
    if declared in ALLOWED_IMAGE_TYPES and declared != detected:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="图片内容与文件类型不一致")
    return detected


def image_suffix_for_upload(filename: str | None, content_type: str) -> str:
    original_suffix = Path(filename or "").suffix.lower()
    if original_suffix in IMAGE_TYPE_SUFFIXES.get(content_type, set()):
        return original_suffix
    return image_suffix_for_content_type(content_type)


def safe_storage_key(purpose: str, suffix: str) -> str:
    if not suffix.startswith(".") or "/" in suffix or "\\" in suffix:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="文件后缀不合法")
    return str(Path(purpose) / f"{uuid4().hex}{suffix}")


def write_local_file(storage_key: str, content: bytes) -> None:
    absolute_path = resolve_storage_key(storage_key)
    absolute_path.parent.mkdir(parents=True, exist_ok=True)
    absolute_path.write_bytes(content)


def keep_object_storage_local_mirror() -> bool:
    return bool(getattr(get_settings(), "object_storage_keep_local_mirror", False))


def remove_local_file(path: Path) -> None:
    try:
        path.unlink(missing_ok=True)
    except OSError as exc:
        logger.warning("local storage cleanup failed path=%s error=%s", path, exc)


def remove_local_mirror_if_unneeded(storage_key: str) -> None:
    if keep_object_storage_local_mirror():
        return
    remove_local_file(resolve_storage_key(storage_key))


def storage_cache_root() -> Path:
    return get_settings().storage_root / "_cache"


def remove_materialized_cache_file(path: Path) -> None:
    try:
        path.resolve().relative_to(storage_cache_root().resolve())
    except ValueError:
        return
    remove_local_file(path)


def qiniu_auth():
    config = qiniu_config()
    missing = [
        name
        for name, value in {
            "QINIU_ACCESS_KEY 或 QNY_ACCESS_KEY": config.access_key,
            "QINIU_SECRET_KEY 或 QNY_SECRET_KEY": config.secret_key,
            "QINIU_BUCKET 或 QNY_BUCKET": config.bucket,
            "QINIU_BUCKET_DOMAIN、QNY_PUBLIC_BASE_URL 或 QNY_DOMAIN": config.public_base_url,
        }.items()
        if not value
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
    return Auth(config.access_key, config.secret_key)


def qiniu_base_url(storage_key: str) -> str:
    config = qiniu_config()
    public_base_url = config.public_base_url.rstrip("/")
    if not public_base_url:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="七牛 Bucket 域名未配置")
    if not public_base_url.startswith(("http://", "https://")):
        scheme = "https" if config.use_https else "http"
        public_base_url = f"{scheme}://{public_base_url}"
    return f"{public_base_url}/{quote(storage_key, safe='/')}"


def qiniu_asset_url(storage_key: str, variant: str) -> str:
    base_url = qiniu_base_url(storage_key)
    if variant == ASSET_URL_VARIANT_THUMBNAIL:
        return base_url
    return base_url


def aliyun_oss_public_base_url() -> str:
    config = aliyun_oss_config()
    if config.public_base_url:
        return config.public_base_url
    if not config.bucket or not config.endpoint:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="阿里云 OSS 公开访问域名未配置")

    endpoint = config.endpoint
    if not endpoint.startswith(("http://", "https://")):
        endpoint = f"https://{endpoint}"
    parsed = urlparse(endpoint)
    if not parsed.netloc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="阿里云 OSS Endpoint 配置不合法")
    return f"{parsed.scheme}://{config.bucket}.{parsed.netloc}"


def aliyun_oss_asset_url(storage_key: str, variant: str) -> str:
    base_url = aliyun_oss_public_base_url().rstrip("/")
    if variant == ASSET_URL_VARIANT_THUMBNAIL:
        return f"{base_url}/{quote(storage_key, safe='/')}"
    return f"{base_url}/{quote(storage_key, safe='/')}"


def upload_qiniu_file(storage_key: str, local_path: Path) -> str:
    try:
        from qiniu import put_file_v2
    except ImportError as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="缺少 qiniu Python SDK") from exc

    token = qiniu_auth().upload_token(qiniu_config().bucket, storage_key, 3600)
    result, info = put_file_v2(token, storage_key, str(local_path), version="v2")
    status_code = getattr(info, "status_code", None)
    if status_code != 200 or not isinstance(result, dict) or result.get("key") != storage_key:
        error_text = getattr(info, "text_body", "") or getattr(info, "error", "") or "未知错误"
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"七牛上传失败：{error_text}")
    return qiniu_base_url(storage_key)


def upload_aliyun_oss_file(storage_key: str, local_path: Path) -> str:
    config = aliyun_oss_config()
    missing = [
        name
        for name, value in {
            "ALIYUN_OSS_ACCESS_KEY_ID": config.access_key_id,
            "ALIYUN_OSS_ACCESS_KEY_SECRET": config.access_key_secret,
            "ALIYUN_OSS_BUCKET": config.bucket,
            "ALIYUN_OSS_ENDPOINT": config.endpoint,
        }.items()
        if not value
    ]
    if missing:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"阿里云 OSS 配置缺失：{', '.join(missing)}",
        )
    try:
        import oss2
    except ImportError as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="缺少 oss2 Python SDK") from exc

    endpoint = config.endpoint
    if not endpoint.startswith(("http://", "https://")):
        endpoint = f"https://{endpoint}"
    auth = oss2.Auth(config.access_key_id, config.access_key_secret)
    bucket = oss2.Bucket(auth, endpoint, config.bucket)
    result = bucket.put_object_from_file(storage_key, str(local_path))
    status_code = getattr(result, "status", None)
    if status_code not in {200, 201}:
        request_id = getattr(result, "request_id", "") or "未知 request id"
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"阿里云 OSS 上传失败：{request_id}")
    return aliyun_oss_asset_url(storage_key, ASSET_URL_VARIANT_ORIGINAL)


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
        write_local_file(storage_key, content)
        public_url = upload_qiniu_file(storage_key, resolve_storage_key(storage_key))
        remove_local_mirror_if_unneeded(storage_key)
        return StoredFile(StorageBackend.qiniu, storage_key, len(content), checksum, public_url)
    if backend == StorageBackend.aliyun_oss:
        write_local_file(storage_key, content)
        public_url = upload_aliyun_oss_file(storage_key, resolve_storage_key(storage_key))
        remove_local_mirror_if_unneeded(storage_key)
        return StoredFile(StorageBackend.aliyun_oss, storage_key, len(content), checksum, public_url)
    raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="存储后端配置不支持")


def store_local_content(purpose: str, content: bytes, suffix: str) -> StoredFile:
    if not content:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="文件内容不能为空")
    storage_key = safe_storage_key(purpose, suffix)
    checksum = hashlib.sha256(content).hexdigest()
    write_local_file(storage_key, content)
    return StoredFile(StorageBackend.local, storage_key, len(content), checksum)


async def save_upload_file(purpose: str, file: UploadFile) -> StoredFile:
    content = await read_upload_image_content(file)
    content_type = detect_verified_image_content_type(content, file.content_type)
    suffix = image_suffix_for_upload(file.filename, content_type)
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


def save_local_binary_file(purpose: str, content: bytes, suffix: str) -> StoredFile:
    return store_local_content(purpose, content, suffix)


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
    if asset.storage_backend == StorageBackend.aliyun_oss:
        return aliyun_oss_asset_url(asset.storage_key, variant)
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="本地资产没有外部访问 URL")


def materialize_asset_to_local(asset) -> Path:
    if asset.storage_backend == StorageBackend.local:
        path = resolve_storage_key(asset.storage_key)
        if not path.exists():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="本地文件不存在")
        return path
    if asset.storage_backend in {StorageBackend.qiniu, StorageBackend.aliyun_oss}:
        mirrored_path = resolve_storage_key(asset.storage_key)
        if mirrored_path.exists() and mirrored_path.stat().st_size > 0:
            return mirrored_path
        suffix = Path(asset.storage_key).suffix or mimetypes.guess_extension(asset.content_type) or ".bin"
        cache_path = storage_cache_root() / asset.storage_backend.value / f"{asset.id}{suffix}"
        if cache_path.exists() and cache_path.stat().st_size > 0:
            return cache_path
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        response = requests.get(asset_content_url(asset, ASSET_URL_VARIANT_ORIGINAL), timeout=120)
        if response.status_code != 200 or not response.content:
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="对象存储资产下载失败")
        cache_path.write_bytes(response.content)
        return cache_path
    raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="资产存储后端不支持")


def existing_local_asset_path(asset) -> Path:
    if asset.storage_backend == StorageBackend.local:
        path = resolve_storage_key(asset.storage_key)
        if not path.exists():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="本地文件不存在")
        return path
    if asset.storage_backend in {StorageBackend.qiniu, StorageBackend.aliyun_oss}:
        mirrored_path = resolve_storage_key(asset.storage_key)
        if mirrored_path.exists():
            return mirrored_path
        suffix = Path(asset.storage_key).suffix or mimetypes.guess_extension(asset.content_type) or ".bin"
        cache_path = storage_cache_root() / asset.storage_backend.value / f"{asset.id}{suffix}"
        if cache_path.exists() and cache_path.stat().st_size > 0:
            return cache_path
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="图片本地文件不存在，无法从本地打包；请重新生成图片或补齐服务器本地资产镜像",
        )
    raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="资产存储后端不支持")
