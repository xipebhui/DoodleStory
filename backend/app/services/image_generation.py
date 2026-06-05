import base64
import binascii
import copy
import json
import logging
import mimetypes
import re
from time import monotonic, sleep
from contextlib import ExitStack
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

CHAT_IMAGE_REFERENCE_PATTERN = re.compile(
    r"!\[[^\]]*\]\((?P<markdown>(?:https?://|data:image/)[^)\s]+)\)|(?P<plain>(?:https?://|data:image/)[^\s)]+)"
)
APEXERAPI_CHAT_IMAGE_MODEL_PREFIXES = ("nano-banana", "nana-banana")
SILICONFLOW_IMAGE_GENERATION_MODELS = {
    "Qwen/Qwen-Image-Edit-2509",
    "Qwen/Qwen-Image-Edit",
    "baidu/ERNIE-Image-Turbo",
    "Qwen/Qwen-Image",
}
SILICONFLOW_IMAGE_EDIT_2509_MODEL = "Qwen/Qwen-Image-Edit-2509"
SILICONFLOW_QWEN_IMAGE_MODEL = "Qwen/Qwen-Image"
SILICONFLOW_QWEN_IMAGE_SIZES = {
    "1:1": "1328x1328",
    "16:9": "1664x928",
    "9:16": "928x1664",
    "4:3": "1472x1140",
    "3:4": "1140x1472",
}
SILICONFLOW_DEFAULT_IMAGE_SIZES = {
    "1:1": "1024x1024",
    "16:9": "1280x720",
    "9:16": "720x1280",
    "4:3": "1024x768",
    "3:4": "768x1024",
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
        return {key: sanitize_provider_log_value(item) for key, item in value.items()}
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


def is_apexerapi_chat_image_model(image_model_name: str) -> bool:
    normalized = image_model_name.strip().lower().replace("_", "-")
    if normalized.startswith("gemini-") and "image" in normalized:
        return True
    return any(normalized.startswith(prefix) for prefix in APEXERAPI_CHAT_IMAGE_MODEL_PREFIXES)


def is_siliconflow_image_generation_model(image_model_name: str) -> bool:
    return image_model_name.strip() in SILICONFLOW_IMAGE_GENERATION_MODELS


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


def encode_reference_image(path: Path) -> dict[str, Any]:
    if not path.exists() or not path.is_file():
        raise ImageProviderConfigError(f"参考图文件不存在：{path}")
    content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    with path.open("rb") as file:
        encoded = base64.b64encode(file.read()).decode("ascii")
    return {"type": "image_url", "image_url": {"url": f"data:{content_type};base64,{encoded}"}}


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


def parse_chat_image_reference(response_body: dict[str, Any]) -> str:
    choices = response_body.get("choices")
    if not isinstance(choices, list) or not choices:
        raise ImageProviderResponseError("图片 Provider 返回中缺少 choices[0]")
    first_choice = choices[0]
    if not isinstance(first_choice, dict):
        raise ImageProviderResponseError("图片 Provider 返回 choices[0] 必须是对象")
    message = first_choice.get("message")
    if not isinstance(message, dict):
        raise ImageProviderResponseError("图片 Provider 返回 choices[0].message 必须是对象")
    content = message.get("content")
    if isinstance(content, str):
        text = content
    elif isinstance(content, list):
        text_parts = []
        direct_image_reference = None
        for item in content:
            if isinstance(item, dict) and isinstance(item.get("text"), str):
                text_parts.append(item["text"])
            elif isinstance(item, dict) and isinstance(item.get("image_url"), dict):
                image_url = item["image_url"].get("url")
                if isinstance(image_url, str) and (
                    image_url.startswith("data:image/") or image_url.startswith(("http://", "https://"))
                ):
                    direct_image_reference = image_url
            elif isinstance(item, str):
                text_parts.append(item)
        text = "\n".join(text_parts)
        if direct_image_reference:
            return direct_image_reference
    else:
        raise ImageProviderResponseError("图片 Provider 返回 message.content 必须是字符串或文本数组")

    match = CHAT_IMAGE_REFERENCE_PATTERN.search(text)
    if not match:
        raise ImageProviderResponseError("图片 Provider 返回中未找到图片 URL 或 data URL")
    return match.group("markdown") or match.group("plain")


def download_generated_image(
    image_url: str,
    provider_request_id: str | None,
    *,
    provider_name: str = "ApexerAPI chat image",
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


def siliconflow_image_size_for_model(image_model_name: str, aspect_ratio: str) -> str:
    if image_model_name.strip() == SILICONFLOW_QWEN_IMAGE_MODEL:
        size = SILICONFLOW_QWEN_IMAGE_SIZES.get(aspect_ratio)
    else:
        size = SILICONFLOW_DEFAULT_IMAGE_SIZES.get(aspect_ratio)
    if not size:
        raise ImageProviderConfigError(f"SiliconFlow 图片生成不支持画面比例：{aspect_ratio}")
    return size


def build_siliconflow_image_generation_payload(
    *, prompt: str, reference_paths: list[Path], image_model_name: str, aspect_ratio: str
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    model_name = image_model_name.strip()
    reference_file_info = []
    for path in reference_paths:
        if not path.exists() or not path.is_file():
            raise ImageProviderConfigError(f"参考图文件不存在：{path}")
        reference_file_info.append(describe_reference_file(path))
    payload: dict[str, Any] = {
        "model": model_name,
        "prompt": prompt,
        "num_inference_steps": 20,
    }

    if model_name == SILICONFLOW_IMAGE_EDIT_2509_MODEL:
        if len(reference_paths) > 3:
            raise ImageProviderConfigError("Qwen/Qwen-Image-Edit-2509 最多支持 3 张参考图")
        for index, path in enumerate(reference_paths):
            field_name = "image" if index == 0 else f"image{index + 1}"
            payload[field_name] = encode_reference_image_data_url(path)
        payload["cfg"] = 4
        return payload, reference_file_info

    if model_name == "Qwen/Qwen-Image-Edit":
        if len(reference_paths) > 1:
            raise ImageProviderConfigError("Qwen/Qwen-Image-Edit 最多支持 1 张参考图")
        if reference_paths:
            payload["image"] = encode_reference_image_data_url(reference_paths[0])
        payload["cfg"] = 4
        return payload, reference_file_info

    if len(reference_paths) > 1:
        raise ImageProviderConfigError(f"{model_name} 最多支持 1 张参考图")
    if reference_paths:
        payload["image"] = encode_reference_image_data_url(reference_paths[0])
    payload["image_size"] = siliconflow_image_size_for_model(model_name, aspect_ratio)
    if model_name == SILICONFLOW_QWEN_IMAGE_MODEL:
        payload["num_inference_steps"] = 50
        payload["cfg"] = 4
    return payload, reference_file_info


def parse_siliconflow_image_url(response_body: dict[str, Any]) -> str:
    images = response_body.get("images")
    if not isinstance(images, list) or not images:
        raise ImageProviderResponseError("SiliconFlow 图片生成返回中缺少 images[0].url")
    first_item = images[0]
    if not isinstance(first_item, dict):
        raise ImageProviderResponseError("SiliconFlow 图片生成返回 images[0] 必须是对象")
    image_url = first_item.get("url")
    if not isinstance(image_url, str) or not image_url.strip():
        raise ImageProviderResponseError("SiliconFlow 图片生成返回中缺少 images[0].url")
    return image_url


def request_siliconflow_image_generation(
    *, prompt: str, reference_paths: list[Path], image_model_name: str, aspect_ratio: str
) -> tuple[bytes, str, str | None]:
    if not image_model_name.strip():
        raise ImageProviderConfigError("风格未绑定生图模型名")

    settings = get_settings()
    api_key = settings.siliconflow_api_key.strip()
    base_url = settings.siliconflow_base_url.strip()
    if not api_key:
        raise ImageProviderConfigError("SILICONFLOW_API_KEY 未配置")
    if not base_url:
        raise ImageProviderConfigError("SILICONFLOW_BASE_URL 未配置")

    endpoint = f"{base_url.rstrip('/')}/images/generations"
    payload, reference_file_info = build_siliconflow_image_generation_payload(
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
                "SiliconFlow image generation request prepared endpoint=%s model=%s aspect_ratio=%s attempt=%s/%s reference_count=%s reference_files=%s prompt_chars=%s timeout_seconds=%s",
                endpoint,
                image_model_name.strip(),
                aspect_ratio,
                attempt,
                max_attempts,
                len(reference_paths),
                reference_file_info,
                len(prompt),
                300,
            )
            if settings.image_provider_debug_log_raw_io:
                log_provider_raw_io(
                    provider_name="SiliconFlow image generation",
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
                    "SiliconFlow image generation request exception will retry model=%s attempt=%s/%s elapsed_ms=%s exception_type=%s timeout_retry=%s retry_delay_seconds=%s error=%s",
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
        provider_request_id = response.headers.get("x-siliconcloud-trace-id") or response.headers.get("x-request-id")
        logger.info(
            "SiliconFlow image generation response received status_code=%s attempt=%s/%s elapsed_ms=%s response_bytes=%s content_type=%s provider_request_id=%s",
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
                provider_name="SiliconFlow image generation",
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
            "SiliconFlow image generation retryable response will retry status_code=%s attempt=%s/%s provider_request_id=%s timeout_retry=%s retry_delay_seconds=%s response_preview=%s",
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
    provider_request_id = response.headers.get("x-siliconcloud-trace-id") or response.headers.get("x-request-id")
    logger.info(
        "SiliconFlow image generation final response status_code=%s total_elapsed_ms=%s response_bytes=%s content_type=%s provider_request_id=%s",
        response.status_code,
        elapsed_ms,
        len(response.content),
        response.headers.get("content-type"),
        provider_request_id,
    )
    if response.status_code >= 400:
        logger.warning(
            "SiliconFlow image generation failed status_code=%s response_chars=%s provider_request_id=%s response_preview=%s",
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

    image_url = parse_siliconflow_image_url(body)
    response_body_request_id = f"seed:{body['seed']}" if isinstance(body.get("seed"), int) else None
    image_content, content_type = download_generated_image(
        image_url,
        response_body_request_id or provider_request_id,
        provider_name="SiliconFlow image generation",
    )
    logger.info(
        "SiliconFlow image generation returned downloadable image content_type=%s bytes=%s provider_request_id=%s response_body_request_id=%s",
        content_type,
        len(image_content),
        provider_request_id,
        response_body_request_id,
    )
    return image_content, content_type, response_body_request_id or provider_request_id


def request_apexerapi_chat_image(
    *, prompt: str, reference_paths: list[Path], image_model_name: str, aspect_ratio: str
) -> tuple[bytes, str, str | None]:
    if not image_model_name.strip():
        raise ImageProviderConfigError("风格未绑定生图模型名")
    if not reference_paths:
        raise ImageProviderConfigError("ApexerAPI Chat 图片模型至少需要一张参考图")

    settings = get_settings()
    api_key = settings.apexerapi_api_key.strip()
    base_url = settings.apexerapi_base.strip()
    if not api_key:
        raise ImageProviderConfigError("APEXERAPI_API_KEY 未配置")
    if not base_url:
        raise ImageProviderConfigError("APEXERAPI_BASE 未配置")

    endpoint = f"{base_url.rstrip('/')}/v1/chat/completions"
    content: list[dict[str, Any]] = [{"type": "text", "text": prompt}]
    reference_file_info = []
    for path in reference_paths:
        if not path.exists() or not path.is_file():
            raise ImageProviderConfigError(f"参考图文件不存在：{path}")
        reference_file_info.append(describe_reference_file(path))
        content.append(encode_reference_image(path))

    payload = {
        "model": image_model_name.strip(),
        "aspect_ratio": aspect_ratio,
        "messages": [{"role": "user", "content": content}],
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Accept": "application/json",
        "Content-Type": "application/json",
    }
    proxy_url = settings.apexerapi_proxy_url.strip()
    proxies = {"http": proxy_url, "https": proxy_url} if proxy_url else None
    proxy_description = describe_proxy_url(proxy_url)
    standard_max_attempts, timeout_max_attempts = image_provider_attempt_limits()
    max_attempts = max(standard_max_attempts, timeout_max_attempts)
    response: requests.Response | None = None
    request_started_at = monotonic()

    for attempt in range(1, max_attempts + 1):
        attempt_started_at = monotonic()
        try:
            logger.info(
                "ApexerAPI chat image request prepared endpoint=%s model=%s aspect_ratio=%s attempt=%s/%s reference_count=%s reference_files=%s prompt_chars=%s proxy_enabled=%s proxy=%s timeout_seconds=%s",
                endpoint,
                image_model_name.strip(),
                aspect_ratio,
                attempt,
                max_attempts,
                len(reference_paths),
                reference_file_info,
                len(prompt),
                bool(proxies),
                proxy_description,
                300,
            )
            if settings.image_provider_debug_log_raw_io:
                log_provider_raw_io(
                    provider_name="ApexerAPI chat image",
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
                    "ApexerAPI chat image request exception will retry model=%s attempt=%s/%s proxy_enabled=%s proxy=%s elapsed_ms=%s exception_type=%s timeout_retry=%s retry_delay_seconds=%s error=%s",
                    image_model_name.strip(),
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
            raise ImageProviderResponseError(f"图片 Provider 请求异常：{exc}") from exc

        elapsed_ms = round((monotonic() - attempt_started_at) * 1000)
        provider_request_id = response.headers.get("x-oneapi-request-id") or response.headers.get("x-request-id")
        logger.info(
            "ApexerAPI chat image response received status_code=%s attempt=%s/%s elapsed_ms=%s response_bytes=%s content_type=%s provider_request_id=%s",
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
                provider_name="ApexerAPI chat image",
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
            "ApexerAPI chat image retryable response will retry status_code=%s attempt=%s/%s provider_request_id=%s timeout_retry=%s retry_delay_seconds=%s response_preview=%s",
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
    provider_request_id = response.headers.get("x-oneapi-request-id") or response.headers.get("x-request-id")
    logger.info(
        "ApexerAPI chat image final response status_code=%s total_elapsed_ms=%s response_bytes=%s content_type=%s provider_request_id=%s",
        response.status_code,
        elapsed_ms,
        len(response.content),
        response.headers.get("content-type"),
        provider_request_id,
    )
    if response.status_code >= 400:
        logger.warning(
            "ApexerAPI chat image failed status_code=%s response_chars=%s provider_request_id=%s response_preview=%s",
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

    response_body_request_id = body.get("id") if isinstance(body.get("id"), str) else None
    image_reference = parse_chat_image_reference(body)
    if image_reference.startswith("data:image/"):
        image_content, content_type = parse_image_data_url(image_reference)
    else:
        image_content, content_type = download_generated_image(image_reference, response_body_request_id or provider_request_id)
    logger.info(
        "ApexerAPI chat image returned downloadable image content_type=%s bytes=%s provider_request_id=%s response_body_request_id=%s",
        content_type,
        len(image_content),
        provider_request_id,
        response_body_request_id,
    )
    return image_content, content_type, response_body_request_id or provider_request_id


def request_xg_image_edit(
    *, prompt: str, reference_paths: list[Path], image_model_name: str, aspect_ratio: str
) -> tuple[bytes, str, str | None]:
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
        "response_format": "b64_json",
    }
    headers = {
        "Authorization": f"Bearer {settings.xg_api_key}",
        "Accept": "application/json",
    }
    proxy_url = settings.xg_proxy_url.strip()
    proxies = {"http": proxy_url, "https": proxy_url} if proxy_url else None
    proxy_description = describe_proxy_url(proxy_url)
    standard_max_attempts, timeout_max_attempts = image_provider_attempt_limits()
    max_attempts = max(standard_max_attempts, timeout_max_attempts)
    response: requests.Response | None = None
    request_started_at = monotonic()

    for attempt in range(1, max_attempts + 1):
        attempt_started_at = monotonic()
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
                    "XG image edit request prepared endpoint=%s model=%s aspect_ratio=%s attempt=%s/%s reference_count=%s reference_files=%s prompt_chars=%s proxy_enabled=%s proxy=%s timeout_seconds=%s",
                    endpoint,
                    image_model_name.strip(),
                    aspect_ratio,
                    attempt,
                    max_attempts,
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
                elapsed_ms = round((monotonic() - attempt_started_at) * 1000)
                if should_retry_provider_exception(
                    exc,
                    attempt=attempt,
                    standard_max_attempts=standard_max_attempts,
                    timeout_max_attempts=timeout_max_attempts,
                ):
                    delay = retry_delay_seconds(settings.xg_request_retry_backoff_seconds, attempt)
                    logger.warning(
                        "XG image edit request exception will retry model=%s attempt=%s/%s proxy_enabled=%s proxy=%s elapsed_ms=%s exception_type=%s timeout_retry=%s retry_delay_seconds=%s error=%s",
                        image_model_name.strip(),
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
                logger.exception(
                    "XG image edit request exception model=%s attempt=%s/%s proxy_enabled=%s proxy=%s elapsed_ms=%s exception_type=%s",
                    image_model_name.strip(),
                    attempt,
                    max_attempts,
                    bool(proxies),
                    proxy_description,
                    elapsed_ms,
                    exc.__class__.__name__,
                )
                raise ImageProviderResponseError(f"图片 Provider 请求异常：{exc}") from exc

        elapsed_ms = round((monotonic() - attempt_started_at) * 1000)
        provider_request_id = response.headers.get("x-oneapi-request-id") or response.headers.get("x-request-id")
        logger.info(
            "XG image edit response received status_code=%s attempt=%s/%s elapsed_ms=%s response_bytes=%s content_type=%s provider_request_id=%s",
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
            "XG image edit retryable response will retry status_code=%s attempt=%s/%s provider_request_id=%s timeout_retry=%s retry_delay_seconds=%s response_preview=%s",
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
    provider_request_id = response.headers.get("x-oneapi-request-id") or response.headers.get("x-request-id")
    logger.info(
        "XG image edit final response status_code=%s total_elapsed_ms=%s response_bytes=%s content_type=%s provider_request_id=%s",
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


def request_xg_image(
    *, prompt: str, reference_paths: list[Path], image_model_name: str, aspect_ratio: str
) -> tuple[bytes, str, str | None]:
    if is_siliconflow_image_generation_model(image_model_name):
        return request_siliconflow_image_generation(
            prompt=prompt,
            reference_paths=reference_paths,
            image_model_name=image_model_name,
            aspect_ratio=aspect_ratio,
        )
    if is_apexerapi_chat_image_model(image_model_name):
        return request_apexerapi_chat_image(
            prompt=prompt,
            reference_paths=reference_paths,
            image_model_name=image_model_name,
            aspect_ratio=aspect_ratio,
        )
    return request_xg_image_edit(
        prompt=prompt,
        reference_paths=reference_paths,
        image_model_name=image_model_name,
        aspect_ratio=aspect_ratio,
    )


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
