import base64
import binascii
import copy
import json
import logging
import mimetypes
import os
import subprocess
import tempfile
from io import BytesIO
from time import monotonic, sleep
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import requests
from fastapi import HTTPException
from PIL import Image, UnidentifiedImageError

from app.core.config import get_settings
from app.services.grokcli_runtime import serialized_grokcli_call
from app.models.enums import FileAssetPurpose, StorageBackend
from app.services.storage import save_bytes

logger = logging.getLogger(__name__)

IMAGE_GATEWAY_GENERATION_MODELS = {
    "gpt-image-2",
    "Tongyi-MAI/Z-Image",
    "Qwen/Qwen-Image",
    "baidu/ERNIE-Image-Turbo",
    "gemini_3.1_flash_image_preview",
    "gemini_3.0_pro_image_preview",
    "gemini_3.1_flash_image_preview_4K",
    "gemini_3.0_pro_image_preview_4K",
    "gemini-3.1-flash-image-preview",
    "gemini-3-pro-image-preview",
    "gpt-image-2(线路XF)",
    "gr-image-2",
    "nano-banana",
    "nano-banana-hd",
    "nano-banana-pro",
}
IMAGE_GATEWAY_SILICONFLOW_MODELS = {
    "Tongyi-MAI/Z-Image",
    "Qwen/Qwen-Image",
    "baidu/ERNIE-Image-Turbo",
}
IMAGE_GATEWAY_APEXER_MODELS = {
    "gemini_3.1_flash_image_preview",
    "gemini_3.0_pro_image_preview",
    "gemini_3.1_flash_image_preview_4K",
    "gemini_3.0_pro_image_preview_4K",
}
IMAGE_GATEWAY_IMAGE_SIZE_BY_ASPECT_RATIO = {
    "1:1": "1024x1024",
    "16:9": "1792x1024",
    "9:16": "1024x1792",
}
IMAGE_PROVIDERS = frozenset({"qy", "xgapi", "grok"})
GROKCLI_ASPECT_RATIOS = frozenset(
    {"1:1", "16:9", "9:16", "4:3", "3:4", "3:2", "2:3"}
)
GROKCLI_RETRYABLE_EXIT_CODES = frozenset({5, 6})


class ImageProviderError(Exception):
    pass


class ImageProviderConfigError(ImageProviderError):
    pass


class ImageProviderResponseError(ImageProviderError):
    pass


class ImageAspectRatioMismatchError(ImageProviderResponseError):
    pass


@dataclass(frozen=True)
class ImageDimensions:
    width: int
    height: int


@dataclass(frozen=True)
class GeneratedImageFile:
    storage_backend: StorageBackend
    storage_key: str
    byte_size: int
    checksum_sha256: str
    content_type: str
    original_filename: str
    provider_request_id: str | None
    public_url: str | None = None
    width: int | None = None
    height: int | None = None
    provider: str | None = None
    model: str | None = None


@dataclass(frozen=True)
class ImageReference:
    url: str | None = None


def resolve_image_provider(image_provider: str | None = None) -> str:
    provider = (
        image_provider
        if image_provider is not None
        else get_settings().image_provider
    ).strip().lower()
    provider = provider or "qy"
    if provider not in IMAGE_PROVIDERS:
        supported = "、".join(sorted(IMAGE_PROVIDERS))
        raise ImageProviderConfigError(
            f"IMAGE_PROVIDER 不支持：{provider}，可用值：{supported}"
        )
    return provider


def resolve_image_provider_model(
    *,
    provider: str,
    references: list[ImageReference],
    image_model_name: str,
) -> str:
    if provider != "grok":
        return image_model_name.strip()
    settings = get_settings()
    return (
        settings.grokcli_image_edit_model
        if references
        else settings.grokcli_image_model
    ).strip()


def describe_reference_url(url: str) -> dict[str, Any]:
    parsed = urlparse(url)
    return {
        "scheme": parsed.scheme,
        "host": parsed.hostname,
        "path_suffix": Path(parsed.path).suffix,
    }


def describe_reference(reference: ImageReference) -> dict[str, Any]:
    info: dict[str, Any] = {}
    if reference.url:
        info.update(describe_reference_url(reference.url))
    return info


def truncate_raw_log_text(value: str, max_chars: int) -> str:
    if max_chars <= 0 or len(value) <= max_chars:
        return value
    return f"{value[:max_chars]}...[truncated {len(value) - max_chars} chars]"


def sanitize_provider_log_value(value: Any) -> Any:
    if isinstance(value, str) and value.startswith("data:image/"):
        header, separator, encoded = value.partition(",")
        if separator == ",":
            return f"{header},<base64 omitted chars={len(encoded)}>"
        return "<data image omitted>"
    if isinstance(value, str) and value.startswith(("http://", "https://")):
        parsed = urlparse(value)
        return f"<image url omitted host={parsed.hostname or 'unknown'}>"
    if isinstance(value, dict):
        sanitized = {}
        for key, item in value.items():
            if key == "b64_json" and isinstance(item, str):
                sanitized[key] = f"<base64 omitted chars={len(item)}>"
            else:
                sanitized[key] = sanitize_provider_log_value(item)
        return sanitized
    if isinstance(value, list):
        return [sanitize_provider_log_value(item) for item in value]
    return value


def sanitize_provider_payload_for_log(payload: dict[str, Any]) -> dict[str, Any]:
    return sanitize_provider_log_value(copy.deepcopy(payload))


def log_provider_raw_io(
    *,
    provider_name: str,
    direction: str,
    payload: dict[str, Any] | str,
    max_chars: int,
    sanitize_request: bool,
) -> None:
    if isinstance(payload, str):
        if sanitize_request:
            body = payload
        else:
            try:
                parsed = json.loads(payload)
            except ValueError:
                body = payload
            else:
                sanitized = sanitize_provider_log_value(parsed)
                body = json.dumps(sanitized, ensure_ascii=False, separators=(",", ":"))
    else:
        log_payload = sanitize_provider_payload_for_log(payload)
        body = json.dumps(log_payload, ensure_ascii=False, separators=(",", ":"))
    logger.info(
        "%s raw %s body_chars=%s body=%s",
        provider_name,
        direction,
        len(body),
        truncate_raw_log_text(body, max_chars),
    )


def retryable_xg_status(status_code: int) -> bool:
    return status_code in {408, 409, 425, 429} or status_code >= 500


def is_timeout_exception(exc: requests.RequestException) -> bool:
    if isinstance(exc, requests.Timeout):
        return True
    message = str(exc).lower()
    return any(token in message for token in ("timeout", "timed out", "read timed out", "connection timed out"))


def is_timeout_response(response: requests.Response) -> bool:
    if response.status_code in {408, 504}:
        return True
    if response.status_code < 400:
        return False
    return any(
        token in response.text.lower()
        for token in ("timeout", "timed out", "read timed out", "connection timed out")
    )


def image_provider_attempt_limits() -> tuple[int, int]:
    settings = get_settings()
    standard_max_attempts = max(1, settings.xg_request_max_attempts)
    timeout_max_attempts = max(1, settings.image_provider_timeout_retry_attempts + 1)
    return standard_max_attempts, timeout_max_attempts


def should_retry_provider_exception(
    exc: requests.RequestException,
    *,
    attempt: int,
    standard_max_attempts: int,
    timeout_max_attempts: int,
) -> bool:
    if is_timeout_exception(exc):
        return attempt < timeout_max_attempts
    return attempt < standard_max_attempts


def should_retry_provider_response(
    response: requests.Response,
    *,
    attempt: int,
    standard_max_attempts: int,
    timeout_max_attempts: int,
) -> bool:
    if response.status_code < 400:
        return False
    if is_timeout_response(response):
        return attempt < timeout_max_attempts
    return retryable_xg_status(response.status_code) and attempt < standard_max_attempts


def retry_delay_seconds(base_delay: float, attempt: int) -> float:
    return max(0.0, base_delay) * attempt


def is_image_gateway_generation_model(image_model_name: str) -> bool:
    return image_model_name.strip() in IMAGE_GATEWAY_GENERATION_MODELS


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


def read_image_dimensions(content: bytes) -> ImageDimensions:
    try:
        with Image.open(BytesIO(content)) as image:
            width, height = image.size
    except (UnidentifiedImageError, OSError) as exc:
        raise ImageProviderResponseError("图片 Provider 返回的图片无法读取尺寸") from exc
    if width <= 0 or height <= 0:
        raise ImageProviderResponseError("图片 Provider 返回的图片尺寸无效")
    return ImageDimensions(width=width, height=height)


def parse_aspect_ratio(aspect_ratio: str) -> tuple[int, int]:
    parts = aspect_ratio.strip().split(":", 1)
    if len(parts) != 2:
        raise ImageProviderConfigError(f"画面比例配置不合法：{aspect_ratio}")
    try:
        width_ratio = int(parts[0])
        height_ratio = int(parts[1])
    except ValueError as exc:
        raise ImageProviderConfigError(f"画面比例配置不合法：{aspect_ratio}") from exc
    if width_ratio <= 0 or height_ratio <= 0:
        raise ImageProviderConfigError(f"画面比例配置不合法：{aspect_ratio}")
    return width_ratio, height_ratio


def image_matches_aspect_ratio(
    *, width: int, height: int, aspect_ratio: str, tolerance: float = 0.02
) -> bool:
    target_width, target_height = parse_aspect_ratio(aspect_ratio)
    actual_ratio = width / height
    target_ratio = target_width / target_height
    return abs(actual_ratio - target_ratio) / target_ratio <= tolerance


def validate_image_aspect_ratio(dimensions: ImageDimensions, aspect_ratio: str) -> None:
    if image_matches_aspect_ratio(
        width=dimensions.width,
        height=dimensions.height,
        aspect_ratio=aspect_ratio,
    ):
        return
    raise ImageAspectRatioMismatchError(
        f"图片比例不符合目标比例：目标 {aspect_ratio}，实际 {dimensions.width}:{dimensions.height}"
    )


def parse_image_data_url(data_url: str) -> tuple[bytes, str]:
    header, separator, encoded = data_url.partition(",")
    if separator != "," or not header.startswith("data:image/") or ";base64" not in header:
        raise ImageProviderResponseError("图片 Provider 返回的 data URL 不是合法 Base64 图片")
    content_type = header.removeprefix("data:").split(";", 1)[0]
    try:
        content = base64.b64decode(encoded, validate=True)
    except binascii.Error as exc:
        raise ImageProviderResponseError("图片 Provider 返回的 data URL 不是合法 Base64") from exc
    if not content:
        raise ImageProviderResponseError("图片 Provider 返回的 data URL 内容为空")
    detected_content_type = detect_image_content_type(content)
    if content_type not in {"image/png", "image/jpeg", "image/webp"}:
        content_type = detected_content_type
    return content, content_type


def download_generated_image(
    image_url: str,
    provider_request_id: str | None,
    *,
    provider_name: str = "Unified image gateway",
) -> tuple[bytes, str]:
    settings = get_settings()
    standard_max_attempts, timeout_max_attempts = image_provider_attempt_limits()
    max_attempts = max(standard_max_attempts, timeout_max_attempts)
    response: requests.Response | None = None

    for attempt in range(1, max_attempts + 1):
        started_at = monotonic()
        try:
            session = requests.Session()
            session.trust_env = False
            logger.info(
                "%s download prepared url_host=%s attempt=%s/%s provider_request_id=%s timeout_seconds=%s",
                provider_name,
                urlparse(image_url).hostname,
                attempt,
                max_attempts,
                provider_request_id,
                300,
            )
            response = session.get(image_url, headers={"Accept": "image/*"}, timeout=300)
        except requests.RequestException as exc:
            elapsed_ms = round((monotonic() - started_at) * 1000)
            if should_retry_provider_exception(
                exc,
                attempt=attempt,
                standard_max_attempts=standard_max_attempts,
                timeout_max_attempts=timeout_max_attempts,
            ):
                delay = retry_delay_seconds(settings.xg_request_retry_backoff_seconds, attempt)
                logger.warning(
                    "%s download exception will retry attempt=%s/%s elapsed_ms=%s exception_type=%s timeout_retry=%s retry_delay_seconds=%s error=%s",
                    provider_name,
                    attempt,
                    max_attempts,
                    elapsed_ms,
                    exc.__class__.__name__,
                    is_timeout_exception(exc),
                    delay,
                    exc,
                )
                sleep(delay)
                continue
            raise ImageProviderResponseError(f"图片 Provider 结果图下载异常：{exc}") from exc

        elapsed_ms = round((monotonic() - started_at) * 1000)
        logger.info(
            "%s download response received status_code=%s attempt=%s/%s elapsed_ms=%s response_bytes=%s content_type=%s provider_request_id=%s",
            provider_name,
            response.status_code,
            attempt,
            max_attempts,
            elapsed_ms,
            len(response.content),
            response.headers.get("content-type"),
            provider_request_id,
        )
        if not should_retry_provider_response(
            response,
            attempt=attempt,
            standard_max_attempts=standard_max_attempts,
            timeout_max_attempts=timeout_max_attempts,
        ):
            break
        delay = retry_delay_seconds(settings.xg_request_retry_backoff_seconds, attempt)
        logger.warning(
            "%s download retryable response will retry status_code=%s attempt=%s/%s timeout_retry=%s retry_delay_seconds=%s provider_request_id=%s",
            provider_name,
            response.status_code,
            attempt,
            max_attempts,
            is_timeout_response(response),
            delay,
            provider_request_id,
        )
        sleep(delay)

    if response is None:
        raise ImageProviderResponseError("图片 Provider 结果图下载未执行")
    if response.status_code >= 400:
        raise ImageProviderResponseError(f"图片 Provider 结果图下载失败：HTTP {response.status_code}")
    if not response.content:
        raise ImageProviderResponseError("图片 Provider 结果图下载内容为空")
    return response.content, detect_image_content_type(response.content)


def image_gateway_size_for_aspect_ratio(aspect_ratio: str) -> str | None:
    return IMAGE_GATEWAY_IMAGE_SIZE_BY_ASPECT_RATIO.get(aspect_ratio)


def image_gateway_reference_limit(image_model_name: str) -> int:
    model_name = image_model_name.strip()
    if model_name == "gpt-image-2":
        return 4
    if model_name in IMAGE_GATEWAY_APEXER_MODELS:
        return 1
    return 3


def validate_reference_url(url: str) -> str:
    cleaned = url.strip()
    parsed = urlparse(cleaned)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ImageProviderConfigError("参考图必须提供可公开访问的 HTTP(S) URL")
    return cleaned


def qy_reference_urls(references: list[ImageReference]) -> list[str]:
    urls = []
    for reference in references:
        if not reference.url:
            raise ImageProviderConfigError("QY 生图参考图必须提供公网 URL")
        urls.append(validate_reference_url(reference.url))
    return urls


def add_image_gateway_reference_fields(payload: dict[str, Any], reference_urls: list[str]) -> None:
    for index, url in enumerate(reference_urls, start=1):
        key = "image" if index == 1 else f"image{index}"
        payload[key] = url


def build_image_gateway_generation_payload(
    *, prompt: str, references: list[ImageReference], image_model_name: str, aspect_ratio: str
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    model_name = image_model_name.strip()
    if model_name not in IMAGE_GATEWAY_GENERATION_MODELS:
        supported = "、".join(sorted(IMAGE_GATEWAY_GENERATION_MODELS))
        raise ImageProviderConfigError(f"生图模型未接入统一 Gateway：{model_name}。当前可用模型：{supported}")

    reference_urls = qy_reference_urls(references)
    reference_limit = image_gateway_reference_limit(model_name)
    if len(reference_urls) > reference_limit:
        logger.warning(
            "Unified image gateway reference list truncated model=%s original_reference_count=%s kept_reference_count=%s",
            model_name,
            len(reference_urls),
            reference_limit,
        )
        reference_urls = reference_urls[:reference_limit]

    reference_file_info = []
    validated_reference_urls = []
    for url in reference_urls:
        validated_url = validate_reference_url(url)
        reference_file_info.append(describe_reference_url(validated_url))
        validated_reference_urls.append(validated_url)

    payload: dict[str, Any] = {
        "model": model_name,
        "prompt": prompt,
        "n": 1,
    }
    image_size = image_gateway_size_for_aspect_ratio(aspect_ratio)
    if image_size:
        payload["size"] = image_size
    add_image_gateway_reference_fields(payload, validated_reference_urls)

    if model_name in IMAGE_GATEWAY_APEXER_MODELS:
        image_size = "4K" if model_name.endswith("_4K") else "1K"
        payload["extra_body"] = {
            "google": {
                "image_config": {
                    "aspect_ratio": aspect_ratio,
                    "image_size": image_size,
                }
            }
        }

    return payload, reference_file_info


def xgapi_endpoint(base_url: str, path: str) -> str:
    cleaned = base_url.rstrip("/")
    if cleaned.endswith("/v1"):
        return f"{cleaned}{path}"
    return f"{cleaned}/v1{path}"


def xgapi_model_name(image_model_name: str) -> str:
    model_name = image_model_name.strip()
    if not model_name:
        raise ImageProviderConfigError("生图模型未配置，不能调用 xgapi")
    return model_name


def xgapi_image_quality() -> str:
    configured = (get_settings().xg_image_quality or "").strip().lower()
    if not configured:
        return "high"
    if configured in {"auto", "low", "medium", "high"}:
        return configured
    if configured in {"1k", "2k", "4k"}:
        return "high"
    raise ImageProviderConfigError("XG_IMAGE_QUALITY 在 xgapi 图片接口中只支持 auto、low、medium、high 或 1k/2k/4k")


def build_xgapi_generation_payload(
    *, prompt: str, image_model_name: str, aspect_ratio: str
) -> dict[str, Any]:
    return {
        "prompt": prompt,
        "model": xgapi_model_name(image_model_name),
        "aspect_ratio": aspect_ratio,
        "quality": xgapi_image_quality(),
        "response_format": "url",
    }


def xgapi_reference_urls(references: list[ImageReference]) -> list[str]:
    urls: list[str] = []
    for reference in references:
        if not reference.url:
            raise ImageProviderConfigError("xgapi 带参考图生图必须提供公网 URL")
        urls.append(validate_reference_url(reference.url))
    return urls


def build_xgapi_edit_payload(
    *, prompt: str, reference_urls: list[str], image_model_name: str, aspect_ratio: str
) -> dict[str, Any]:
    return {
        "model": xgapi_model_name(image_model_name),
        "prompt": prompt,
        "aspect_ratio": aspect_ratio,
        "quality": xgapi_image_quality(),
        "response_format": "url",
    }


def build_xgapi_edit_files(reference_urls: list[str]) -> list[tuple[str, tuple[str, bytes, str]]]:
    files: list[tuple[str, tuple[str, bytes, str]]] = []
    for index, url in enumerate(reference_urls, start=1):
        content, content_type = download_generated_image(
            url,
            provider_request_id=None,
            provider_name="xgapi reference image",
        )
        extension = mimetypes.guess_extension(content_type) or ".png"
        files.append(("image", (f"reference-{index}{extension}", content, content_type)))
    return files


def parse_openai_image_generation_item(response_body: dict[str, Any]) -> dict[str, Any]:
    data = response_body.get("data")
    if not isinstance(data, list) or not data:
        raise ImageProviderResponseError("图片 Provider 返回中缺少 data[0]")
    first_item = data[0]
    if not isinstance(first_item, dict):
        raise ImageProviderResponseError("图片 Provider 返回 data[0] 必须是对象")
    return first_item


def image_gateway_response_body_request_id(response_body: dict[str, Any]) -> str | None:
    response_id = response_body.get("id")
    if isinstance(response_id, str) and response_id.strip():
        return response_id
    seed = response_body.get("seed")
    if isinstance(seed, int):
        return f"seed:{seed}"
    return None


def read_image_gateway_generation_result(
    response_body: dict[str, Any],
    provider_request_id: str | None,
    *,
    provider_name: str = "Unified image gateway",
) -> tuple[bytes, str, str | None]:
    first_item = parse_openai_image_generation_item(response_body)
    response_body_request_id = image_gateway_response_body_request_id(response_body)
    result_request_id = response_body_request_id or provider_request_id

    encoded = first_item.get("b64_json")
    if isinstance(encoded, str) and encoded.strip():
        image_content = parse_image_b64(response_body)
        return image_content, detect_image_content_type(image_content), result_request_id

    image_url = first_item.get("url")
    if isinstance(image_url, str) and image_url.strip():
        if image_url.startswith("data:image/"):
            image_content, content_type = parse_image_data_url(image_url)
            return image_content, content_type, result_request_id
        image_content, content_type = download_generated_image(
            image_url,
            result_request_id,
            provider_name=provider_name,
        )
        return image_content, content_type, result_request_id

    raise ImageProviderResponseError("图片 Provider 返回中缺少 data[0].url 或 data[0].b64_json")


def request_image_gateway_generation(
    *, prompt: str, references: list[ImageReference], image_model_name: str, aspect_ratio: str
) -> tuple[bytes, str, str | None]:
    if not image_model_name.strip():
        raise ImageProviderConfigError("风格未绑定生图模型名")

    settings = get_settings()
    api_key = settings.image_gateway_api_key.strip()
    base_url = settings.image_gateway_base_url.strip()
    if not api_key:
        raise ImageProviderConfigError("IMAGE_GATEWAY_API_KEY 未配置")
    if not base_url:
        raise ImageProviderConfigError("IMAGE_GATEWAY_BASE_URL 未配置")

    endpoint = f"{base_url.rstrip('/')}/images/generations"
    payload, reference_file_info = build_image_gateway_generation_payload(
        prompt=prompt,
        references=references,
        image_model_name=image_model_name,
        aspect_ratio=aspect_ratio,
    )
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Accept": "application/json",
        "Content-Type": "application/json",
    }
    standard_max_attempts, timeout_max_attempts = image_provider_attempt_limits()
    max_attempts = max(standard_max_attempts, timeout_max_attempts)
    response: requests.Response | None = None
    request_started_at = monotonic()

    for attempt in range(1, max_attempts + 1):
        attempt_started_at = monotonic()
        try:
            logger.info(
                "Unified image gateway request prepared endpoint=%s model=%s aspect_ratio=%s size=%s attempt=%s/%s reference_count=%s reference_files=%s prompt_chars=%s timeout_seconds=%s",
                endpoint,
                image_model_name.strip(),
                aspect_ratio,
                payload.get("size"),
                attempt,
                max_attempts,
                len(references),
                reference_file_info,
                len(prompt),
                300,
            )
            if settings.image_provider_debug_log_raw_io:
                log_provider_raw_io(
                    provider_name="Unified image gateway",
                    direction="request",
                    payload=payload,
                    max_chars=settings.image_provider_debug_log_raw_max_chars,
                    sanitize_request=True,
                )
            session = requests.Session()
            session.trust_env = False
            response = session.post(endpoint, headers=headers, json=payload, timeout=300)
        except requests.RequestException as exc:
            elapsed_ms = round((monotonic() - attempt_started_at) * 1000)
            if should_retry_provider_exception(
                exc,
                attempt=attempt,
                standard_max_attempts=standard_max_attempts,
                timeout_max_attempts=timeout_max_attempts,
            ):
                delay = retry_delay_seconds(settings.xg_request_retry_backoff_seconds, attempt)
                logger.warning(
                    "Unified image gateway request exception will retry model=%s attempt=%s/%s elapsed_ms=%s exception_type=%s timeout_retry=%s retry_delay_seconds=%s error=%s",
                    image_model_name.strip(),
                    attempt,
                    max_attempts,
                    elapsed_ms,
                    exc.__class__.__name__,
                    is_timeout_exception(exc),
                    delay,
                    exc,
                )
                sleep(delay)
                continue
            raise ImageProviderResponseError(f"图片 Provider 请求异常：{exc}") from exc

        elapsed_ms = round((monotonic() - attempt_started_at) * 1000)
        provider_request_id = (
            response.headers.get("x-oneapi-request-id")
            or response.headers.get("x-request-id")
            or response.headers.get("x-siliconcloud-trace-id")
        )
        logger.info(
            "Unified image gateway response received status_code=%s attempt=%s/%s elapsed_ms=%s response_bytes=%s content_type=%s provider_request_id=%s",
            response.status_code,
            attempt,
            max_attempts,
            elapsed_ms,
            len(response.content),
            response.headers.get("content-type"),
            provider_request_id,
        )
        if settings.image_provider_debug_log_raw_io:
            log_provider_raw_io(
                provider_name="Unified image gateway",
                direction="response",
                payload=response.text,
                max_chars=settings.image_provider_debug_log_raw_max_chars,
                sanitize_request=False,
            )
        if not should_retry_provider_response(
            response,
            attempt=attempt,
            standard_max_attempts=standard_max_attempts,
            timeout_max_attempts=timeout_max_attempts,
        ):
            break
        delay = retry_delay_seconds(settings.xg_request_retry_backoff_seconds, attempt)
        logger.warning(
            "Unified image gateway retryable response will retry status_code=%s attempt=%s/%s provider_request_id=%s timeout_retry=%s retry_delay_seconds=%s response_preview=%s",
            response.status_code,
            attempt,
            max_attempts,
            provider_request_id,
            is_timeout_response(response),
            delay,
            response.text[:500],
        )
        sleep(delay)

    if response is None:
        raise ImageProviderResponseError("图片 Provider 请求未执行")

    elapsed_ms = round((monotonic() - request_started_at) * 1000)
    provider_request_id = (
        response.headers.get("x-oneapi-request-id")
        or response.headers.get("x-request-id")
        or response.headers.get("x-siliconcloud-trace-id")
    )
    logger.info(
        "Unified image gateway final response status_code=%s total_elapsed_ms=%s response_bytes=%s content_type=%s provider_request_id=%s",
        response.status_code,
        elapsed_ms,
        len(response.content),
        response.headers.get("content-type"),
        provider_request_id,
    )
    if response.status_code >= 400:
        logger.warning(
            "Unified image gateway failed status_code=%s response_chars=%s provider_request_id=%s response_preview=%s",
            response.status_code,
            len(response.text),
            provider_request_id,
            response.text[:500],
        )
        raise ImageProviderResponseError(f"图片 Provider 请求失败：HTTP {response.status_code} {response.text}")

    try:
        body = response.json()
    except ValueError as exc:
        raise ImageProviderResponseError("图片 Provider 返回内容不是合法 JSON") from exc
    if not isinstance(body, dict):
        raise ImageProviderResponseError("图片 Provider 返回 JSON 必须是对象结构")

    image_content, content_type, result_request_id = read_image_gateway_generation_result(body, provider_request_id)
    logger.info(
        "Unified image gateway returned image content_type=%s bytes=%s provider_request_id=%s result_request_id=%s",
        content_type,
        len(image_content),
        provider_request_id,
        result_request_id,
    )
    return image_content, content_type, result_request_id


def request_xgapi_image(
    *, prompt: str, references: list[ImageReference], image_model_name: str, aspect_ratio: str
) -> tuple[bytes, str, str | None]:
    settings = get_settings()
    api_key = settings.xg_api_key.strip()
    base_url = settings.xg_base_url.strip()
    if not api_key:
        raise ImageProviderConfigError("XG_API_KEY 未配置")
    if not base_url:
        raise ImageProviderConfigError("XG_BASE_URL 未配置")

    has_references = bool(references)
    endpoint = xgapi_endpoint(base_url, "/images/edits" if has_references else "/images/generations")
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Accept": "application/json",
    }
    standard_max_attempts, timeout_max_attempts = image_provider_attempt_limits()
    max_attempts = max(standard_max_attempts, timeout_max_attempts)
    response: requests.Response | None = None
    request_started_at = monotonic()
    reference_file_info = [describe_reference(reference) for reference in references]

    for attempt in range(1, max_attempts + 1):
        attempt_started_at = monotonic()
        try:
            session = requests.Session()
            session.trust_env = False
            if has_references:
                reference_urls = xgapi_reference_urls(references)
                payload = build_xgapi_edit_payload(
                    prompt=prompt,
                    reference_urls=reference_urls,
                    image_model_name=image_model_name,
                    aspect_ratio=aspect_ratio,
                )
                files = build_xgapi_edit_files(reference_urls)
                headers.pop("Content-Type", None)
                logger.info(
                    "xgapi image request prepared endpoint=%s model=%s aspect_ratio=%s attempt=%s/%s reference_count=%s reference_files=%s prompt_chars=%s timeout_seconds=%s",
                    endpoint,
                    payload.get("model"),
                    aspect_ratio,
                    attempt,
                    max_attempts,
                    len(references),
                    reference_file_info,
                    len(prompt),
                    300,
                )
                if settings.image_provider_debug_log_raw_io:
                    log_provider_raw_io(
                        provider_name="xgapi image provider",
                        direction="request",
                        payload=payload,
                        max_chars=settings.image_provider_debug_log_raw_max_chars,
                        sanitize_request=True,
                    )
                response = session.post(endpoint, headers=headers, data=payload, files=files, timeout=300)
            else:
                payload = build_xgapi_generation_payload(
                    prompt=prompt,
                    image_model_name=image_model_name,
                    aspect_ratio=aspect_ratio,
                )
                headers["Content-Type"] = "application/json"
                logger.info(
                    "xgapi image request prepared endpoint=%s model=%s aspect_ratio=%s attempt=%s/%s reference_count=%s prompt_chars=%s timeout_seconds=%s",
                    endpoint,
                    payload.get("model"),
                    aspect_ratio,
                    attempt,
                    max_attempts,
                    0,
                    len(prompt),
                    300,
                )
                if settings.image_provider_debug_log_raw_io:
                    log_provider_raw_io(
                        provider_name="xgapi image provider",
                        direction="request",
                        payload=payload,
                        max_chars=settings.image_provider_debug_log_raw_max_chars,
                        sanitize_request=True,
                    )
                response = session.post(endpoint, headers=headers, json=payload, timeout=300)
        except requests.RequestException as exc:
            elapsed_ms = round((monotonic() - attempt_started_at) * 1000)
            if should_retry_provider_exception(
                exc,
                attempt=attempt,
                standard_max_attempts=standard_max_attempts,
                timeout_max_attempts=timeout_max_attempts,
            ):
                delay = retry_delay_seconds(settings.xg_request_retry_backoff_seconds, attempt)
                logger.warning(
                    "xgapi image request exception will retry model=%s attempt=%s/%s elapsed_ms=%s exception_type=%s timeout_retry=%s retry_delay_seconds=%s error=%s",
                    xgapi_model_name(image_model_name),
                    attempt,
                    max_attempts,
                    elapsed_ms,
                    exc.__class__.__name__,
                    is_timeout_exception(exc),
                    delay,
                    exc,
                )
                sleep(delay)
                continue
            raise ImageProviderResponseError(f"图片 Provider 请求异常：{exc}") from exc

        elapsed_ms = round((monotonic() - attempt_started_at) * 1000)
        provider_request_id = (
            response.headers.get("x-oneapi-request-id")
            or response.headers.get("x-request-id")
            or response.headers.get("x-siliconcloud-trace-id")
        )
        logger.info(
            "xgapi image response received status_code=%s attempt=%s/%s elapsed_ms=%s response_bytes=%s content_type=%s provider_request_id=%s",
            response.status_code,
            attempt,
            max_attempts,
            elapsed_ms,
            len(response.content),
            response.headers.get("content-type"),
            provider_request_id,
        )
        if settings.image_provider_debug_log_raw_io:
            log_provider_raw_io(
                provider_name="xgapi image provider",
                direction="response",
                payload=response.text,
                max_chars=settings.image_provider_debug_log_raw_max_chars,
                sanitize_request=False,
            )
        if not should_retry_provider_response(
            response,
            attempt=attempt,
            standard_max_attempts=standard_max_attempts,
            timeout_max_attempts=timeout_max_attempts,
        ):
            break
        delay = retry_delay_seconds(settings.xg_request_retry_backoff_seconds, attempt)
        logger.warning(
            "xgapi image retryable response will retry status_code=%s attempt=%s/%s provider_request_id=%s timeout_retry=%s retry_delay_seconds=%s response_preview=%s",
            response.status_code,
            attempt,
            max_attempts,
            provider_request_id,
            is_timeout_response(response),
            delay,
            response.text[:500],
        )
        sleep(delay)

    if response is None:
        raise ImageProviderResponseError("图片 Provider 请求未执行")

    elapsed_ms = round((monotonic() - request_started_at) * 1000)
    provider_request_id = (
        response.headers.get("x-oneapi-request-id")
        or response.headers.get("x-request-id")
        or response.headers.get("x-siliconcloud-trace-id")
    )
    logger.info(
        "xgapi image final response status_code=%s total_elapsed_ms=%s response_bytes=%s content_type=%s provider_request_id=%s",
        response.status_code,
        elapsed_ms,
        len(response.content),
        response.headers.get("content-type"),
        provider_request_id,
    )
    if response.status_code >= 400:
        logger.warning(
            "xgapi image failed status_code=%s response_chars=%s provider_request_id=%s response_preview=%s",
            response.status_code,
            len(response.text),
            provider_request_id,
            response.text[:500],
        )
        raise ImageProviderResponseError(f"图片 Provider 请求失败：HTTP {response.status_code} {response.text}")

    try:
        body = response.json()
    except ValueError as exc:
        raise ImageProviderResponseError("图片 Provider 返回内容不是合法 JSON") from exc
    if not isinstance(body, dict):
        raise ImageProviderResponseError("图片 Provider 返回 JSON 必须是对象结构")

    image_content, content_type, result_request_id = read_image_gateway_generation_result(
        body,
        provider_request_id,
        provider_name="xgapi image provider",
    )
    logger.info(
        "xgapi image returned image content_type=%s bytes=%s provider_request_id=%s result_request_id=%s",
        content_type,
        len(image_content),
        provider_request_id,
        result_request_id,
    )
    return image_content, content_type, result_request_id


def grokcli_reference_urls(references: list[ImageReference]) -> list[str]:
    if len(references) > 3:
        raise ImageProviderConfigError("Grok image-edit 最多支持 3 张参考图")
    urls: list[str] = []
    for reference in references:
        url = (reference.url or "").strip()
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ImageProviderConfigError(
                "Grok 带参考图生图必须提供可公开访问的 HTTP(S) URL"
            )
        urls.append(url)
    return urls


def build_grokcli_image_command(
    *,
    prompt: str,
    references: list[ImageReference],
    aspect_ratio: str,
) -> list[str]:
    settings = get_settings()
    executable = settings.grokcli_executable.strip()
    if not executable:
        raise ImageProviderConfigError("GROKCLI_EXECUTABLE 未配置")
    if aspect_ratio not in GROKCLI_ASPECT_RATIOS:
        supported = "、".join(sorted(GROKCLI_ASPECT_RATIOS))
        raise ImageProviderConfigError(
            f"Grok 不支持画面比例 {aspect_ratio}，可用值：{supported}"
        )
    resolution = settings.grokcli_image_resolution.strip().lower()
    if resolution not in {"1k", "2k"}:
        raise ImageProviderConfigError("GROKCLI_IMAGE_RESOLUTION 只支持 1k 或 2k")

    command = [executable]
    if references:
        model = settings.grokcli_image_edit_model.strip()
        command.extend(
            [
                "image-edit",
                prompt,
                "--model",
                model,
            ]
        )
        for url in grokcli_reference_urls(references):
            command.extend(["--image", url])
    else:
        model = settings.grokcli_image_model.strip()
        command.extend(
            [
                "image",
                prompt,
                "--model",
                model,
            ]
        )
    if not model:
        model_setting = (
            "GROKCLI_IMAGE_EDIT_MODEL" if references else "GROKCLI_IMAGE_MODEL"
        )
        raise ImageProviderConfigError(f"{model_setting} 未配置")
    command.extend(
        [
            "--aspect",
            aspect_ratio,
            "--resolution",
            resolution,
            "--count",
            "1",
            "--timeout",
            str(settings.grokcli_timeout_seconds),
            "--output",
            "json",
            "--no-color",
        ]
    )
    return command


def parse_grokcli_image_output(stdout: str, output_root: Path) -> tuple[bytes, str]:
    try:
        body = json.loads(stdout)
    except json.JSONDecodeError as exc:
        raise ImageProviderResponseError("grokcli 返回内容不是合法 JSON") from exc
    paths = body.get("paths") if isinstance(body, dict) else None
    if not isinstance(paths, list) or len(paths) != 1 or not isinstance(paths[0], str):
        raise ImageProviderResponseError("grokcli 返回中必须包含唯一图片路径")
    image_path = Path(paths[0]).expanduser().resolve()
    output_root = output_root.resolve()
    if not image_path.is_relative_to(output_root):
        raise ImageProviderResponseError("grokcli 返回了输出目录之外的图片路径")
    try:
        content = image_path.read_bytes()
    except OSError as exc:
        raise ImageProviderResponseError("无法读取 grokcli 生成的图片") from exc
    if not content:
        raise ImageProviderResponseError("grokcli 生成的图片内容为空")
    return content, detect_image_content_type(content)


def request_grokcli_image(
    *,
    prompt: str,
    references: list[ImageReference],
    aspect_ratio: str,
) -> tuple[bytes, str, str | None]:
    settings = get_settings()
    command = build_grokcli_image_command(
        prompt=prompt,
        references=references,
        aspect_ratio=aspect_ratio,
    )
    environment = os.environ.copy()
    environment["NO_COLOR"] = "1"
    if settings.grokcli_home.strip():
        environment["GROKCLI_HOME"] = settings.grokcli_home.strip()

    for attempt in range(1, settings.grokcli_request_max_attempts + 1):
        with tempfile.TemporaryDirectory(prefix="doodlestory-grokcli-") as temporary_dir:
            working_directory = Path(temporary_dir)
            output_root = working_directory / "output"
            environment["GROKCLI_OUTPUT_DIR"] = str(output_root)
            started_at = monotonic()
            try:
                with serialized_grokcli_call():
                    completed = subprocess.run(
                        command,
                        cwd=working_directory,
                        env=environment,
                        capture_output=True,
                        text=True,
                        timeout=settings.grokcli_timeout_seconds + 15,
                        check=False,
                    )
            except FileNotFoundError as exc:
                raise ImageProviderConfigError(
                    f"找不到 grokcli 可执行文件：{command[0]}"
                ) from exc
            except subprocess.TimeoutExpired as exc:
                if attempt < settings.grokcli_request_max_attempts:
                    logger.warning(
                        "grokcli image subprocess timed out and will retry attempt=%s/%s",
                        attempt,
                        settings.grokcli_request_max_attempts,
                    )
                    sleep(settings.grokcli_retry_backoff_seconds * attempt)
                    continue
                raise ImageProviderResponseError("grokcli 生图超时") from exc

            elapsed_ms = round((monotonic() - started_at) * 1000)
            if completed.returncode == 0:
                content, content_type = parse_grokcli_image_output(
                    completed.stdout,
                    output_root,
                )
                logger.info(
                    "grokcli image succeeded mode=%s aspect_ratio=%s reference_count=%s bytes=%s content_type=%s elapsed_ms=%s",
                    "edit" if references else "generation",
                    aspect_ratio,
                    len(references),
                    len(content),
                    content_type,
                    elapsed_ms,
                )
                return content, content_type, None

            error_preview = (completed.stderr or completed.stdout).strip()[:1000]
            if (
                completed.returncode in GROKCLI_RETRYABLE_EXIT_CODES
                and attempt < settings.grokcli_request_max_attempts
            ):
                logger.warning(
                    "grokcli image transient failure will retry exit_code=%s attempt=%s/%s elapsed_ms=%s error=%s",
                    completed.returncode,
                    attempt,
                    settings.grokcli_request_max_attempts,
                    elapsed_ms,
                    error_preview,
                )
                sleep(settings.grokcli_retry_backoff_seconds * attempt)
                continue
            if completed.returncode in {2, 3}:
                raise ImageProviderConfigError(
                    f"grokcli 配置或认证失败（退出码 {completed.returncode}）：{error_preview}"
                )
            raise ImageProviderResponseError(
                f"grokcli 生图失败（退出码 {completed.returncode}）：{error_preview}"
            )

    raise ImageProviderResponseError("grokcli 生图请求未执行")


def request_xg_image(
    *,
    prompt: str,
    references: list[ImageReference],
    image_model_name: str,
    aspect_ratio: str,
    image_provider: str | None = None,
) -> tuple[bytes, str, str | None]:
    provider = resolve_image_provider(image_provider)
    if provider == "grok":
        return request_grokcli_image(
            prompt=prompt,
            references=references,
            aspect_ratio=aspect_ratio,
        )
    if provider == "xgapi":
        return request_xgapi_image(
            prompt=prompt,
            references=references,
            image_model_name=image_model_name,
            aspect_ratio=aspect_ratio,
        )
    if is_image_gateway_generation_model(image_model_name):
        return request_image_gateway_generation(
            prompt=prompt,
            references=references,
            image_model_name=image_model_name,
            aspect_ratio=aspect_ratio,
        )
    supported = "、".join(sorted(IMAGE_GATEWAY_GENERATION_MODELS))
    raise ImageProviderConfigError(f"生图模型未接入统一 Gateway：{image_model_name.strip()}。当前可用模型：{supported}")


def generate_xg_image(
    *,
    prompt: str,
    references: list[ImageReference],
    image_model_name: str,
    aspect_ratio: str,
    validate_result_aspect_ratio: bool = False,
    image_provider: str | None = None,
) -> GeneratedImageFile:
    resolved_provider = resolve_image_provider(image_provider)
    resolved_model = resolve_image_provider_model(
        provider=resolved_provider,
        references=references,
        image_model_name=image_model_name,
    )
    content, content_type, provider_request_id = request_xg_image(
        prompt=prompt,
        references=references,
        image_model_name=image_model_name,
        aspect_ratio=aspect_ratio,
        image_provider=resolved_provider,
    )
    dimensions = read_image_dimensions(content)
    if validate_result_aspect_ratio:
        validate_image_aspect_ratio(dimensions, aspect_ratio)
    filename = f"generated-image{mimetypes.guess_extension(content_type) or '.png'}"
    try:
        stored = save_bytes(
            FileAssetPurpose.generated_image.value,
            content,
            content_type,
            filename,
        )
    except HTTPException as exc:
        raise ImageProviderResponseError(str(exc.detail)) from exc
    return GeneratedImageFile(
        storage_backend=stored.storage_backend,
        storage_key=stored.storage_key,
        byte_size=stored.byte_size,
        checksum_sha256=stored.checksum_sha256,
        content_type=content_type,
        original_filename=filename,
        provider_request_id=provider_request_id,
        public_url=stored.public_url,
        width=dimensions.width,
        height=dimensions.height,
        provider=resolved_provider,
        model=resolved_model,
    )


def generate_xg_image_edit(
    *, prompt: str, references: list[ImageReference], image_model_name: str, aspect_ratio: str = "9:16"
) -> GeneratedImageFile:
    return generate_xg_image(
        prompt=prompt,
        references=references,
        image_model_name=image_model_name,
        aspect_ratio=aspect_ratio,
    )
