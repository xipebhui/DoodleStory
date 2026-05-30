import base64
import binascii
import logging
import mimetypes
from contextlib import ExitStack
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import requests
from fastapi import HTTPException

from app.core.config import get_settings
from app.models.enums import FileAssetPurpose
from app.services.generation_profiles import GenerationProfile, GenerationProfileConfigError
from app.services.storage import save_bytes

logger = logging.getLogger(__name__)


class ImageProviderError(Exception):
    pass


class ImageProviderConfigError(ImageProviderError):
    pass


class ImageProviderResponseError(ImageProviderError):
    pass


@dataclass(frozen=True)
class GeneratedImageFile:
    storage_key: str
    byte_size: int
    checksum_sha256: str
    content_type: str
    original_filename: str
    provider_request_id: str | None


def ensure_xg_profile(profile: GenerationProfile) -> None:
    if profile.image_provider != "xg":
        raise GenerationProfileConfigError(f"暂不支持的图片 provider：{profile.image_provider}")
    if profile.aspect_ratio != "9:16":
        raise GenerationProfileConfigError(f"当前产品只支持 9:16 图片比例，配置值为：{profile.aspect_ratio}")


def parse_image_b64(response_body: dict[str, Any]) -> bytes:
    data = response_body.get("data")
    if not isinstance(data, list) or not data:
        raise ImageProviderResponseError("图片 Provider 返回中缺少 data[0].b64_json")

    first_item = data[0]
    if not isinstance(first_item, dict):
        raise ImageProviderResponseError("图片 Provider 返回 data[0] 必须是对象")

    encoded = first_item.get("b64_json")
    if not isinstance(encoded, str) or not encoded.strip():
        raise ImageProviderResponseError("图片 Provider 返回中缺少 data[0].b64_json")

    try:
        content = base64.b64decode(encoded, validate=True)
    except binascii.Error as exc:
        raise ImageProviderResponseError("图片 Provider 返回的 b64_json 不是合法 Base64") from exc
    if not content:
        raise ImageProviderResponseError("图片 Provider 返回的 b64_json 内容为空")
    return content


def detect_image_content_type(content: bytes) -> str:
    if content.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if content.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if content.startswith(b"RIFF") and content[8:12] == b"WEBP":
        return "image/webp"
    raise ImageProviderResponseError("图片 Provider 返回的图片格式不是 PNG、JPEG 或 WebP")


def request_xg_image_edit(*, prompt: str, reference_paths: list[Path], profile: GenerationProfile) -> tuple[bytes, str, str | None]:
    ensure_xg_profile(profile)
    if not reference_paths:
        raise ImageProviderConfigError("XG 图片编辑接口至少需要一张参考图")

    settings = get_settings()
    if not settings.xg_api_key.strip():
        raise ImageProviderConfigError("XG_API_KEY 未配置")

    endpoint = f"{settings.xg_api_base_url.rstrip('/')}/v1/images/edits"
    data = {
        "model": profile.image_model,
        "prompt": prompt,
        "aspect_ratio": profile.aspect_ratio,
        "response_format": "b64_json",
    }
    headers = {
        "Authorization": f"Bearer {settings.xg_api_key}",
        "Accept": "application/json",
    }

    with ExitStack() as stack:
        files = []
        for path in reference_paths:
            if not path.exists() or not path.is_file():
                raise ImageProviderConfigError(f"参考图文件不存在：{path}")
            content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
            files.append(("image[]", (path.name, stack.enter_context(path.open("rb")), content_type)))

        try:
            response = requests.post(endpoint, headers=headers, data=data, files=files, timeout=300)
        except requests.RequestException as exc:
            raise ImageProviderResponseError(f"图片 Provider 请求异常：{exc}") from exc

    if response.status_code >= 400:
        raise ImageProviderResponseError(f"图片 Provider 请求失败：HTTP {response.status_code} {response.text}")

    try:
        body = response.json()
    except ValueError as exc:
        raise ImageProviderResponseError("图片 Provider 返回内容不是合法 JSON") from exc
    if not isinstance(body, dict):
        raise ImageProviderResponseError("图片 Provider 返回 JSON 必须是对象结构")

    image_content = parse_image_b64(body)
    content_type = detect_image_content_type(image_content)
    logger.info("XG image edit returned b64 image content_type=%s bytes=%s", content_type, len(image_content))
    return image_content, content_type, body.get("id") if isinstance(body.get("id"), str) else None


def generate_xg_image_edit(*, prompt: str, reference_paths: list[Path], profile: GenerationProfile) -> GeneratedImageFile:
    content, content_type, provider_request_id = request_xg_image_edit(
        prompt=prompt,
        reference_paths=reference_paths,
        profile=profile,
    )
    filename = f"generated-image{mimetypes.guess_extension(content_type) or '.png'}"
    try:
        storage_key, byte_size, checksum = save_bytes(
            FileAssetPurpose.generated_image.value,
            content,
            content_type,
            filename,
        )
    except HTTPException as exc:
        raise ImageProviderResponseError(str(exc.detail)) from exc
    return GeneratedImageFile(
        storage_key=storage_key,
        byte_size=byte_size,
        checksum_sha256=checksum,
        content_type=content_type,
        original_filename=filename,
        provider_request_id=provider_request_id,
    )
