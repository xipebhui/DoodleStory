import base64
import binascii
import logging
import mimetypes
from time import monotonic
from contextlib import ExitStack
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import requests
from fastapi import HTTPException

from app.core.config import get_settings
from app.models.enums import FileAssetPurpose
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


def describe_proxy_url(proxy_url: str) -> str:
    if not proxy_url:
        return ""
    parsed = urlparse(proxy_url)
    if not parsed.scheme or not parsed.hostname:
        return "invalid-proxy-url"
    host = parsed.hostname
    port = f":{parsed.port}" if parsed.port else ""
    return f"{parsed.scheme}://{host}{port}"


def describe_reference_file(path: Path) -> dict[str, Any]:
    stat = path.stat()
    return {
        "name": path.name,
        "suffix": path.suffix,
        "bytes": stat.st_size,
        "content_type": mimetypes.guess_type(path.name)[0] or "application/octet-stream",
    }


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


def request_xg_image_edit(*, prompt: str, reference_paths: list[Path], image_model_name: str) -> tuple[bytes, str, str | None]:
    if not image_model_name.strip():
        raise ImageProviderConfigError("风格未绑定生图模型名")
    if not reference_paths:
        raise ImageProviderConfigError("XG 图片编辑接口至少需要一张参考图")

    settings = get_settings()
    if not settings.xg_api_key.strip():
        raise ImageProviderConfigError("XG_API_KEY 未配置")

    endpoint = f"{settings.xg_api_base_url.rstrip('/')}/v1/images/edits"
    data = {
        "model": image_model_name.strip(),
        "prompt": prompt,
        "aspect_ratio": "9:16",
        "response_format": "b64_json",
    }
    headers = {
        "Authorization": f"Bearer {settings.xg_api_key}",
        "Accept": "application/json",
    }
    proxy_url = settings.xg_proxy_url.strip()
    proxies = {"http": proxy_url, "https": proxy_url} if proxy_url else None
    proxy_description = describe_proxy_url(proxy_url)
    request_started_at = monotonic()

    with ExitStack() as stack:
        files = []
        reference_file_info = []
        for path in reference_paths:
            if not path.exists() or not path.is_file():
                raise ImageProviderConfigError(f"参考图文件不存在：{path}")
            file_info = describe_reference_file(path)
            reference_file_info.append(file_info)
            content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
            files.append(("image[]", (path.name, stack.enter_context(path.open("rb")), content_type)))

        try:
            logger.info(
                "XG image edit request prepared endpoint=%s model=%s reference_count=%s reference_files=%s prompt_chars=%s proxy_enabled=%s proxy=%s timeout_seconds=%s",
                endpoint,
                image_model_name.strip(),
                len(reference_paths),
                reference_file_info,
                len(prompt),
                bool(proxies),
                proxy_description,
                300,
            )
            session = requests.Session()
            session.trust_env = False
            response = session.post(endpoint, headers=headers, data=data, files=files, timeout=300, proxies=proxies)
        except requests.RequestException as exc:
            elapsed_ms = round((monotonic() - request_started_at) * 1000)
            logger.exception(
                "XG image edit request exception model=%s proxy_enabled=%s proxy=%s elapsed_ms=%s exception_type=%s",
                image_model_name.strip(),
                bool(proxies),
                proxy_description,
                elapsed_ms,
                exc.__class__.__name__,
            )
            raise ImageProviderResponseError(f"图片 Provider 请求异常：{exc}") from exc

    elapsed_ms = round((monotonic() - request_started_at) * 1000)
    provider_request_id = response.headers.get("x-oneapi-request-id") or response.headers.get("x-request-id")
    logger.info(
        "XG image edit response received status_code=%s elapsed_ms=%s response_bytes=%s content_type=%s provider_request_id=%s",
        response.status_code,
        elapsed_ms,
        len(response.content),
        response.headers.get("content-type"),
        provider_request_id,
    )

    if response.status_code >= 400:
        logger.warning(
            "XG image edit failed status_code=%s response_chars=%s provider_request_id=%s response_preview=%s",
            response.status_code,
            len(response.text),
            provider_request_id,
            response.text[:500],
        )
        raise ImageProviderResponseError(f"图片 Provider 请求失败：HTTP {response.status_code} {response.text}")

    try:
        body = response.json()
    except ValueError as exc:
        logger.warning(
            "XG image edit invalid JSON response status_code=%s response_bytes=%s provider_request_id=%s response_preview=%s",
            response.status_code,
            len(response.content),
            provider_request_id,
            response.text[:500],
        )
        raise ImageProviderResponseError("图片 Provider 返回内容不是合法 JSON") from exc
    if not isinstance(body, dict):
        raise ImageProviderResponseError("图片 Provider 返回 JSON 必须是对象结构")

    image_content = parse_image_b64(body)
    content_type = detect_image_content_type(image_content)
    response_body_request_id = body.get("id") if isinstance(body.get("id"), str) else None
    logger.info(
        "XG image edit returned b64 image content_type=%s bytes=%s provider_request_id=%s response_body_request_id=%s",
        content_type,
        len(image_content),
        provider_request_id,
        response_body_request_id,
    )
    return image_content, content_type, response_body_request_id or provider_request_id


def generate_xg_image_edit(*, prompt: str, reference_paths: list[Path], image_model_name: str) -> GeneratedImageFile:
    content, content_type, provider_request_id = request_xg_image_edit(
        prompt=prompt,
        reference_paths=reference_paths,
        image_model_name=image_model_name,
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
