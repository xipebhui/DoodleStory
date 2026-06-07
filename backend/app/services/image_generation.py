import base64
import binascii
import copy
import json
import logging
import mimetypes
from time import monotonic, sleep
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import requests
from fastapi import HTTPException

from app.core.config import get_settings
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
IMAGE_GATEWAY_OPENAI_SIZE_BY_ASPECT_RATIO = {
    "1:1": "1024x1024",
    "16:9": "1792x1024",
    "9:16": "1024x1792",
    "4:3": "1152x864",
    "3:4": "864x1152",
}


class ImageProviderError(Exception):
    pass


class ImageProviderConfigError(ImageProviderError):
    pass


class ImageProviderResponseError(ImageProviderError):
    pass


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


@dataclass(frozen=True)
class ImageReference:
    url: str | None = None
    local_path: Path | None = None


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
    if reference.local_path:
        info["local_name"] = reference.local_path.name
        info["local_suffix"] = reference.local_path.suffix
        if reference.local_path.exists():
            info["local_bytes"] = reference.local_path.stat().st_size
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


def image_gateway_size_for_aspect_ratio(aspect_ratio: str) -> str:
    size = IMAGE_GATEWAY_OPENAI_SIZE_BY_ASPECT_RATIO.get(aspect_ratio)
    if not size:
        raise ImageProviderConfigError(f"统一生图 Gateway 不支持画面比例：{aspect_ratio}")
    return size


def image_gateway_reference_limit(image_model_name: str) -> int:
    model_name = image_model_name.strip()
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
        raise ImageProviderConfigError(f"{model_name} 最多支持 {reference_limit} 张参考图")

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
        "size": image_gateway_size_for_aspect_ratio(aspect_ratio),
    }
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
    configured = get_settings().xg_image_model.strip()
    return configured or image_model_name.strip()


def build_xgapi_generation_payload(
    *, prompt: str, image_model_name: str, aspect_ratio: str
) -> dict[str, Any]:
    return {
        "prompt": prompt,
        "model": xgapi_model_name(image_model_name),
        "aspect_ratio": aspect_ratio,
        "quality": get_settings().xg_image_quality.strip() or "1k",
        "response_format": "url",
    }


def xgapi_reference_paths(references: list[ImageReference]) -> list[Path]:
    paths: list[Path] = []
    for reference in references:
        if reference.local_path is None:
            raise ImageProviderConfigError("xgapi 带参考图生图必须提供本地参考图文件")
        if not reference.local_path.exists() or not reference.local_path.is_file():
            raise ImageProviderConfigError(f"xgapi 参考图文件不存在：{reference.local_path}")
        paths.append(reference.local_path)
    return paths


def build_xgapi_edit_data(
    *, prompt: str, image_model_name: str, aspect_ratio: str
) -> dict[str, str]:
    return {
        "model": xgapi_model_name(image_model_name),
        "prompt": prompt,
        "aspect_ratio": aspect_ratio,
        "quality": get_settings().xg_image_quality.strip() or "1k",
        "response_format": "url",
    }


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
                data = build_xgapi_edit_data(
                    prompt=prompt,
                    image_model_name=image_model_name,
                    aspect_ratio=aspect_ratio,
                )
                reference_paths = xgapi_reference_paths(references)
                opened_files = []
                files = []
                try:
                    for path in reference_paths:
                        file = path.open("rb")
                        opened_files.append(file)
                        files.append(
                            (
                                "image",
                                (path.name, file, mimetypes.guess_type(path.name)[0] or "application/octet-stream"),
                            )
                        )
                    logger.info(
                        "xgapi image request prepared endpoint=%s model=%s aspect_ratio=%s attempt=%s/%s reference_count=%s reference_files=%s prompt_chars=%s timeout_seconds=%s",
                        endpoint,
                        data.get("model"),
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
                            payload={**data, "image": [str(path.name) for path in reference_paths]},
                            max_chars=settings.image_provider_debug_log_raw_max_chars,
                            sanitize_request=True,
                        )
                    response = session.post(endpoint, headers=headers, data=data, files=files, timeout=300)
                finally:
                    for file in opened_files:
                        file.close()
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


def request_xg_image(
    *, prompt: str, references: list[ImageReference], image_model_name: str, aspect_ratio: str
) -> tuple[bytes, str, str | None]:
    provider = get_settings().image_provider.strip().lower()
    if provider == "xgapi":
        return request_xgapi_image(
            prompt=prompt,
            references=references,
            image_model_name=image_model_name,
            aspect_ratio=aspect_ratio,
        )
    if provider not in {"", "qy"}:
        raise ImageProviderConfigError(f"IMAGE_PROVIDER 不支持：{provider}，可用值：qy、xgapi")
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
    *, prompt: str, references: list[ImageReference], image_model_name: str, aspect_ratio: str
) -> GeneratedImageFile:
    content, content_type, provider_request_id = request_xg_image(
        prompt=prompt,
        references=references,
        image_model_name=image_model_name,
        aspect_ratio=aspect_ratio,
    )
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
