import base64
import binascii
import copy
import json
import logging
import mimetypes
from contextlib import ExitStack
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
XG_FALLBACK_IMAGE_QUALITY = "1k"


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
    if isinstance(value, dict):
        sanitized = {}
        for key, item in value.items():
            if key == "b64_json" and isinstance(item, str):
                sanitized[key] = f"<base64 omitted chars={len(item)}>"
            elif key == "url" and isinstance(item, str) and item.startswith(("http://", "https://")):
                parsed = urlparse(item)
                sanitized[key] = f"<image url omitted host={parsed.hostname or 'unknown'}>"
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


def encode_reference_image_data_url(path: Path) -> str:
    if not path.exists() or not path.is_file():
        raise ImageProviderConfigError(f"参考图文件不存在：{path}")
    content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    with path.open("rb") as file:
        encoded = base64.b64encode(file.read()).decode("ascii")
    return f"data:{content_type};base64,{encoded}"


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
    if model_name in IMAGE_GATEWAY_SILICONFLOW_MODELS:
        return 3
    return 4


def build_image_gateway_generation_payload(
    *, prompt: str, reference_paths: list[Path], image_model_name: str, aspect_ratio: str
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    model_name = image_model_name.strip()
    if model_name not in IMAGE_GATEWAY_GENERATION_MODELS:
        supported = "、".join(sorted(IMAGE_GATEWAY_GENERATION_MODELS))
        raise ImageProviderConfigError(f"生图模型未接入统一 Gateway：{model_name}。当前可用模型：{supported}")

    reference_limit = image_gateway_reference_limit(model_name)
    if len(reference_paths) > reference_limit:
        raise ImageProviderConfigError(f"{model_name} 最多支持 {reference_limit} 张参考图")

    reference_file_info = []
    reference_images = []
    for path in reference_paths:
        if not path.exists() or not path.is_file():
            raise ImageProviderConfigError(f"参考图文件不存在：{path}")
        reference_file_info.append(describe_reference_file(path))
        reference_images.append(encode_reference_image_data_url(path))

    payload: dict[str, Any] = {
        "model": model_name,
        "prompt": prompt,
        "n": 1,
        "size": image_gateway_size_for_aspect_ratio(aspect_ratio),
    }
    if reference_images:
        payload["images"] = reference_images

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
    *, prompt: str, reference_paths: list[Path], image_model_name: str, aspect_ratio: str
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
        reference_paths=reference_paths,
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
                len(reference_paths),
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


def xg_fallback_model_name() -> str:
    model_name = get_settings().xg_fallback_image_model.strip()
    if not model_name:
        raise ImageProviderConfigError("XG_FALLBACK_IMAGE_MODEL 未配置")
    return model_name


def xg_fallback_endpoint(path: str) -> str:
    settings = get_settings()
    base_url = settings.xg_api_base_url.strip()
    if not base_url:
        raise ImageProviderConfigError("XG_API_BASE_URL 未配置")
    return f"{base_url.rstrip('/')}{path}"


def build_xg_fallback_generation_payload(*, prompt: str, aspect_ratio: str) -> dict[str, Any]:
    return {
        "model": xg_fallback_model_name(),
        "prompt": prompt,
        "aspect_ratio": aspect_ratio,
        "quality": XG_FALLBACK_IMAGE_QUALITY,
        "response_format": "url",
    }


def build_xg_fallback_edit_data(*, prompt: str, aspect_ratio: str) -> dict[str, str]:
    return {
        "model": xg_fallback_model_name(),
        "prompt": prompt,
        "aspect_ratio": aspect_ratio,
        "quality": XG_FALLBACK_IMAGE_QUALITY,
        "response_format": "url",
    }


def xg_edit_image_field_name(reference_count: int) -> str:
    return "image[]" if reference_count > 1 else "image"


def xg_response_request_id(response: requests.Response, response_body: dict[str, Any] | None = None) -> str | None:
    response_id = response.headers.get("x-oneapi-request-id") or response.headers.get("x-request-id")
    if response_id:
        return response_id
    if response_body is None:
        return None
    body_id = response_body.get("id")
    return body_id if isinstance(body_id, str) and body_id.strip() else None


def xg_proxy_config() -> tuple[dict[str, str] | None, str]:
    proxy_url = get_settings().xg_proxy_url.strip()
    proxies = {"http": proxy_url, "https": proxy_url} if proxy_url else None
    return proxies, describe_proxy_url(proxy_url)


def parse_xg_image_response(response: requests.Response, *, provider_name: str) -> tuple[bytes, str, str | None]:
    provider_request_id = xg_response_request_id(response)
    try:
        body = response.json()
    except ValueError as exc:
        logger.warning(
            "%s invalid JSON response status_code=%s response_bytes=%s provider_request_id=%s response_preview=%s",
            provider_name,
            response.status_code,
            len(response.content),
            provider_request_id,
            response.text[:500],
        )
        raise ImageProviderResponseError("XG 图片 Provider 返回内容不是合法 JSON") from exc
    if not isinstance(body, dict):
        raise ImageProviderResponseError("XG 图片 Provider 返回 JSON 必须是对象结构")

    provider_request_id = xg_response_request_id(response, body)
    image_content, content_type, result_request_id = read_image_gateway_generation_result(
        body,
        provider_request_id,
        provider_name=provider_name,
    )
    logger.info(
        "%s returned image content_type=%s bytes=%s provider_request_id=%s result_request_id=%s",
        provider_name,
        content_type,
        len(image_content),
        provider_request_id,
        result_request_id,
    )
    return image_content, content_type, result_request_id


def request_xg_fallback_generation(*, prompt: str, aspect_ratio: str) -> tuple[bytes, str, str | None]:
    settings = get_settings()
    api_key = settings.xg_api_key.strip()
    if not api_key:
        raise ImageProviderConfigError("XG_API_KEY 未配置")

    endpoint = xg_fallback_endpoint("/v1/images/generations")
    payload = build_xg_fallback_generation_payload(prompt=prompt, aspect_ratio=aspect_ratio)
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Accept": "application/json",
        "Content-Type": "application/json",
    }
    standard_max_attempts, timeout_max_attempts = image_provider_attempt_limits()
    max_attempts = max(standard_max_attempts, timeout_max_attempts)
    proxies, proxy_description = xg_proxy_config()
    response: requests.Response | None = None
    request_started_at = monotonic()

    for attempt in range(1, max_attempts + 1):
        attempt_started_at = monotonic()
        try:
            logger.info(
                "XG fallback image generation request prepared endpoint=%s model=%s aspect_ratio=%s quality=%s attempt=%s/%s prompt_chars=%s proxy_enabled=%s proxy=%s timeout_seconds=%s",
                endpoint,
                payload["model"],
                aspect_ratio,
                payload["quality"],
                attempt,
                max_attempts,
                len(prompt),
                bool(proxies),
                proxy_description,
                300,
            )
            if settings.image_provider_debug_log_raw_io:
                log_provider_raw_io(
                    provider_name="XG fallback image generation",
                    direction="request",
                    payload=payload,
                    max_chars=settings.image_provider_debug_log_raw_max_chars,
                    sanitize_request=True,
                )
            session = requests.Session()
            session.trust_env = False
            response = session.post(endpoint, headers=headers, json=payload, timeout=300, proxies=proxies)
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
                    "XG fallback image generation request exception will retry model=%s attempt=%s/%s proxy_enabled=%s proxy=%s elapsed_ms=%s exception_type=%s timeout_retry=%s retry_delay_seconds=%s error=%s",
                    payload["model"],
                    attempt,
                    max_attempts,
                    bool(proxies),
                    proxy_description,
                    elapsed_ms,
                    exc.__class__.__name__,
                    is_timeout_exception(exc),
                    delay,
                    exc,
                )
                sleep(delay)
                continue
            raise ImageProviderResponseError(f"XG 图片 Provider 请求异常：{exc}") from exc

        elapsed_ms = round((monotonic() - attempt_started_at) * 1000)
        provider_request_id = xg_response_request_id(response)
        logger.info(
            "XG fallback image generation response received status_code=%s attempt=%s/%s elapsed_ms=%s response_bytes=%s content_type=%s provider_request_id=%s",
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
                provider_name="XG fallback image generation",
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
            "XG fallback image generation retryable response will retry status_code=%s attempt=%s/%s provider_request_id=%s timeout_retry=%s retry_delay_seconds=%s response_preview=%s",
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
        raise ImageProviderResponseError("XG 图片 Provider 请求未执行")

    elapsed_ms = round((monotonic() - request_started_at) * 1000)
    provider_request_id = xg_response_request_id(response)
    logger.info(
        "XG fallback image generation final response status_code=%s total_elapsed_ms=%s response_bytes=%s content_type=%s provider_request_id=%s",
        response.status_code,
        elapsed_ms,
        len(response.content),
        response.headers.get("content-type"),
        provider_request_id,
    )
    if response.status_code >= 400:
        logger.warning(
            "XG fallback image generation failed status_code=%s response_chars=%s provider_request_id=%s response_preview=%s",
            response.status_code,
            len(response.text),
            provider_request_id,
            response.text[:500],
        )
        raise ImageProviderResponseError(f"XG 图片 Provider 请求失败：HTTP {response.status_code} {response.text}")

    return parse_xg_image_response(response, provider_name="XG fallback image generation")


def request_xg_fallback_edit(
    *, prompt: str, reference_paths: list[Path], aspect_ratio: str
) -> tuple[bytes, str, str | None]:
    settings = get_settings()
    api_key = settings.xg_api_key.strip()
    if not api_key:
        raise ImageProviderConfigError("XG_API_KEY 未配置")
    if not reference_paths:
        raise ImageProviderConfigError("XG 图片编辑接口至少需要一张参考图")

    endpoint = xg_fallback_endpoint("/v1/images/edits")
    data = build_xg_fallback_edit_data(prompt=prompt, aspect_ratio=aspect_ratio)
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Accept": "application/json",
    }
    standard_max_attempts, timeout_max_attempts = image_provider_attempt_limits()
    max_attempts = max(standard_max_attempts, timeout_max_attempts)
    proxies, proxy_description = xg_proxy_config()
    response: requests.Response | None = None
    request_started_at = monotonic()

    for attempt in range(1, max_attempts + 1):
        attempt_started_at = monotonic()
        with ExitStack() as stack:
            files = []
            reference_file_info = []
            image_field_name = xg_edit_image_field_name(len(reference_paths))
            for path in reference_paths:
                if not path.exists() or not path.is_file():
                    raise ImageProviderConfigError(f"参考图文件不存在：{path}")
                reference_file_info.append(describe_reference_file(path))
                content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
                files.append((image_field_name, (path.name, stack.enter_context(path.open("rb")), content_type)))

            try:
                logger.info(
                    "XG fallback image edit request prepared endpoint=%s model=%s aspect_ratio=%s quality=%s attempt=%s/%s reference_count=%s reference_field=%s reference_files=%s prompt_chars=%s proxy_enabled=%s proxy=%s timeout_seconds=%s",
                    endpoint,
                    data["model"],
                    aspect_ratio,
                    data["quality"],
                    attempt,
                    max_attempts,
                    len(reference_paths),
                    image_field_name,
                    reference_file_info,
                    len(prompt),
                    bool(proxies),
                    proxy_description,
                    300,
                )
                if settings.image_provider_debug_log_raw_io:
                    log_provider_raw_io(
                        provider_name="XG fallback image edit",
                        direction="request",
                        payload={**data, "reference_files": reference_file_info, "reference_field": image_field_name},
                        max_chars=settings.image_provider_debug_log_raw_max_chars,
                        sanitize_request=True,
                    )
                session = requests.Session()
                session.trust_env = False
                response = session.post(endpoint, headers=headers, data=data, files=files, timeout=300, proxies=proxies)
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
                        "XG fallback image edit request exception will retry model=%s attempt=%s/%s proxy_enabled=%s proxy=%s elapsed_ms=%s exception_type=%s timeout_retry=%s retry_delay_seconds=%s error=%s",
                        data["model"],
                        attempt,
                        max_attempts,
                        bool(proxies),
                        proxy_description,
                        elapsed_ms,
                        exc.__class__.__name__,
                        is_timeout_exception(exc),
                        delay,
                        exc,
                    )
                    sleep(delay)
                    continue
                raise ImageProviderResponseError(f"XG 图片 Provider 请求异常：{exc}") from exc

        elapsed_ms = round((monotonic() - attempt_started_at) * 1000)
        provider_request_id = xg_response_request_id(response)
        logger.info(
            "XG fallback image edit response received status_code=%s attempt=%s/%s elapsed_ms=%s response_bytes=%s content_type=%s provider_request_id=%s",
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
                provider_name="XG fallback image edit",
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
            "XG fallback image edit retryable response will retry status_code=%s attempt=%s/%s provider_request_id=%s timeout_retry=%s retry_delay_seconds=%s response_preview=%s",
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
        raise ImageProviderResponseError("XG 图片 Provider 请求未执行")

    elapsed_ms = round((monotonic() - request_started_at) * 1000)
    provider_request_id = xg_response_request_id(response)
    logger.info(
        "XG fallback image edit final response status_code=%s total_elapsed_ms=%s response_bytes=%s content_type=%s provider_request_id=%s",
        response.status_code,
        elapsed_ms,
        len(response.content),
        response.headers.get("content-type"),
        provider_request_id,
    )
    if response.status_code >= 400:
        logger.warning(
            "XG fallback image edit failed status_code=%s response_chars=%s provider_request_id=%s response_preview=%s",
            response.status_code,
            len(response.text),
            provider_request_id,
            response.text[:500],
        )
        raise ImageProviderResponseError(f"XG 图片 Provider 请求失败：HTTP {response.status_code} {response.text}")

    return parse_xg_image_response(response, provider_name="XG fallback image edit")


def request_xg_fallback_image(
    *, prompt: str, reference_paths: list[Path], aspect_ratio: str
) -> tuple[bytes, str, str | None]:
    if reference_paths:
        return request_xg_fallback_edit(prompt=prompt, reference_paths=reference_paths, aspect_ratio=aspect_ratio)
    return request_xg_fallback_generation(prompt=prompt, aspect_ratio=aspect_ratio)


def request_xg_image(
    *, prompt: str, reference_paths: list[Path], image_model_name: str, aspect_ratio: str
) -> tuple[bytes, str, str | None]:
    if is_image_gateway_generation_model(image_model_name):
        try:
            return request_image_gateway_generation(
                prompt=prompt,
                reference_paths=reference_paths,
                image_model_name=image_model_name,
                aspect_ratio=aspect_ratio,
            )
        except ImageProviderResponseError as gateway_exc:
            fallback_model = get_settings().xg_fallback_image_model.strip() or "<未配置>"
            logger.warning(
                "Unified image gateway exhausted retries; switching to XG fallback model=%s fallback_model=%s aspect_ratio=%s reference_count=%s error=%s",
                image_model_name.strip(),
                fallback_model,
                aspect_ratio,
                len(reference_paths),
                gateway_exc,
            )
            try:
                return request_xg_fallback_image(
                    prompt=prompt,
                    reference_paths=reference_paths,
                    aspect_ratio=aspect_ratio,
                )
            except (ImageProviderConfigError, ImageProviderResponseError) as xg_exc:
                raise ImageProviderResponseError(
                    f"统一生图 Gateway 重试后失败，XG 备用生图也失败：Gateway={gateway_exc}；XG={xg_exc}"
                ) from xg_exc
    supported = "、".join(sorted(IMAGE_GATEWAY_GENERATION_MODELS))
    raise ImageProviderConfigError(f"生图模型未接入统一 Gateway：{image_model_name.strip()}。当前可用模型：{supported}")


def generate_xg_image(
    *, prompt: str, reference_paths: list[Path], image_model_name: str, aspect_ratio: str
) -> GeneratedImageFile:
    content, content_type, provider_request_id = request_xg_image(
        prompt=prompt,
        reference_paths=reference_paths,
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
    *, prompt: str, reference_paths: list[Path], image_model_name: str, aspect_ratio: str = "9:16"
) -> GeneratedImageFile:
    return generate_xg_image(
        prompt=prompt,
        reference_paths=reference_paths,
        image_model_name=image_model_name,
        aspect_ratio=aspect_ratio,
    )
