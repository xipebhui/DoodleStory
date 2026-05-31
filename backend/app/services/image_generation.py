import base64
import binascii
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
from app.models.enums import FileAssetPurpose
from app.services.storage import save_bytes

logger = logging.getLogger(__name__)

CHAT_IMAGE_REFERENCE_PATTERN = re.compile(
    r"!\[[^\]]*\]\((?P<markdown>(?:https?://|data:image/)[^)\s]+)\)|(?P<plain>(?:https?://|data:image/)[^\s)]+)"
)


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


def retryable_xg_status(status_code: int) -> bool:
    return status_code in {408, 409, 425, 429} or status_code >= 500


def retry_delay_seconds(base_delay: float, attempt: int) -> float:
    return max(0.0, base_delay) * attempt


def is_xg_chat_image_model(image_model_name: str) -> bool:
    normalized = image_model_name.strip().lower()
    return normalized.startswith("gemini-") and "image" in normalized


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
        for item in content:
            if isinstance(item, dict) and isinstance(item.get("text"), str):
                text_parts.append(item["text"])
            elif isinstance(item, str):
                text_parts.append(item)
        text = "\n".join(text_parts)
    else:
        raise ImageProviderResponseError("图片 Provider 返回 message.content 必须是字符串或文本数组")

    match = CHAT_IMAGE_REFERENCE_PATTERN.search(text)
    if not match:
        raise ImageProviderResponseError("图片 Provider 返回中未找到图片 URL 或 data URL")
    return match.group("markdown") or match.group("plain")


def download_generated_image(image_url: str, provider_request_id: str | None) -> tuple[bytes, str]:
    settings = get_settings()
    max_attempts = max(1, settings.xg_request_max_attempts)
    response: requests.Response | None = None

    for attempt in range(1, max_attempts + 1):
        started_at = monotonic()
        try:
            session = requests.Session()
            session.trust_env = False
            logger.info(
                "XG chat image download prepared url_host=%s attempt=%s/%s provider_request_id=%s timeout_seconds=%s",
                urlparse(image_url).hostname,
                attempt,
                max_attempts,
                provider_request_id,
                300,
            )
            response = session.get(image_url, headers={"Accept": "image/*"}, timeout=300)
        except requests.RequestException as exc:
            elapsed_ms = round((monotonic() - started_at) * 1000)
            if attempt < max_attempts:
                delay = retry_delay_seconds(settings.xg_request_retry_backoff_seconds, attempt)
                logger.warning(
                    "XG chat image download exception will retry attempt=%s/%s elapsed_ms=%s exception_type=%s retry_delay_seconds=%s error=%s",
                    attempt,
                    max_attempts,
                    elapsed_ms,
                    exc.__class__.__name__,
                    delay,
                    exc,
                )
                sleep(delay)
                continue
            raise ImageProviderResponseError(f"图片 Provider 结果图下载异常：{exc}") from exc

        elapsed_ms = round((monotonic() - started_at) * 1000)
        logger.info(
            "XG chat image download response received status_code=%s attempt=%s/%s elapsed_ms=%s response_bytes=%s content_type=%s provider_request_id=%s",
            response.status_code,
            attempt,
            max_attempts,
            elapsed_ms,
            len(response.content),
            response.headers.get("content-type"),
            provider_request_id,
        )
        if response.status_code < 400 or not retryable_xg_status(response.status_code) or attempt == max_attempts:
            break
        delay = retry_delay_seconds(settings.xg_request_retry_backoff_seconds, attempt)
        logger.warning(
            "XG chat image download retryable response will retry status_code=%s attempt=%s/%s retry_delay_seconds=%s provider_request_id=%s",
            response.status_code,
            attempt,
            max_attempts,
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


def request_xg_chat_image(*, prompt: str, reference_paths: list[Path], image_model_name: str) -> tuple[bytes, str, str | None]:
    if not image_model_name.strip():
        raise ImageProviderConfigError("风格未绑定生图模型名")
    if not reference_paths:
        raise ImageProviderConfigError("XG Chat 图片模型至少需要一张参考图")

    settings = get_settings()
    if not settings.xg_api_key.strip():
        raise ImageProviderConfigError("XG_API_KEY 未配置")

    endpoint = f"{settings.xg_api_base_url.rstrip('/')}/v1/chat/completions"
    content: list[dict[str, Any]] = [{"type": "text", "text": prompt}]
    reference_file_info = []
    for path in reference_paths:
        if not path.exists() or not path.is_file():
            raise ImageProviderConfigError(f"参考图文件不存在：{path}")
        reference_file_info.append(describe_reference_file(path))
        content.append(encode_reference_image(path))

    payload = {
        "model": image_model_name.strip(),
        "messages": [{"role": "user", "content": content}],
    }
    headers = {
        "Authorization": f"Bearer {settings.xg_api_key}",
        "Accept": "application/json",
        "Content-Type": "application/json",
    }
    max_attempts = max(1, settings.xg_request_max_attempts)
    response: requests.Response | None = None
    request_started_at = monotonic()

    for attempt in range(1, max_attempts + 1):
        attempt_started_at = monotonic()
        try:
            logger.info(
                "XG chat image request prepared endpoint=%s model=%s attempt=%s/%s reference_count=%s reference_files=%s prompt_chars=%s proxy_enabled=%s timeout_seconds=%s",
                endpoint,
                image_model_name.strip(),
                attempt,
                max_attempts,
                len(reference_paths),
                reference_file_info,
                len(prompt),
                False,
                300,
            )
            session = requests.Session()
            session.trust_env = False
            response = session.post(endpoint, headers=headers, json=payload, timeout=300)
        except requests.RequestException as exc:
            elapsed_ms = round((monotonic() - attempt_started_at) * 1000)
            if attempt < max_attempts:
                delay = retry_delay_seconds(settings.xg_request_retry_backoff_seconds, attempt)
                logger.warning(
                    "XG chat image request exception will retry model=%s attempt=%s/%s elapsed_ms=%s exception_type=%s retry_delay_seconds=%s error=%s",
                    image_model_name.strip(),
                    attempt,
                    max_attempts,
                    elapsed_ms,
                    exc.__class__.__name__,
                    delay,
                    exc,
                )
                sleep(delay)
                continue
            raise ImageProviderResponseError(f"图片 Provider 请求异常：{exc}") from exc

        elapsed_ms = round((monotonic() - attempt_started_at) * 1000)
        provider_request_id = response.headers.get("x-oneapi-request-id") or response.headers.get("x-request-id")
        logger.info(
            "XG chat image response received status_code=%s attempt=%s/%s elapsed_ms=%s response_bytes=%s content_type=%s provider_request_id=%s",
            response.status_code,
            attempt,
            max_attempts,
            elapsed_ms,
            len(response.content),
            response.headers.get("content-type"),
            provider_request_id,
        )
        if response.status_code < 400 or not retryable_xg_status(response.status_code) or attempt == max_attempts:
            break
        delay = retry_delay_seconds(settings.xg_request_retry_backoff_seconds, attempt)
        logger.warning(
            "XG chat image retryable response will retry status_code=%s attempt=%s/%s provider_request_id=%s retry_delay_seconds=%s response_preview=%s",
            response.status_code,
            attempt,
            max_attempts,
            provider_request_id,
            delay,
            response.text[:500],
        )
        sleep(delay)

    if response is None:
        raise ImageProviderResponseError("图片 Provider 请求未执行")

    elapsed_ms = round((monotonic() - request_started_at) * 1000)
    provider_request_id = response.headers.get("x-oneapi-request-id") or response.headers.get("x-request-id")
    logger.info(
        "XG chat image final response status_code=%s total_elapsed_ms=%s response_bytes=%s content_type=%s provider_request_id=%s",
        response.status_code,
        elapsed_ms,
        len(response.content),
        response.headers.get("content-type"),
        provider_request_id,
    )
    if response.status_code >= 400:
        logger.warning(
            "XG chat image failed status_code=%s response_chars=%s provider_request_id=%s response_preview=%s",
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
        "XG chat image returned downloadable image content_type=%s bytes=%s provider_request_id=%s response_body_request_id=%s",
        content_type,
        len(image_content),
        provider_request_id,
        response_body_request_id,
    )
    return image_content, content_type, response_body_request_id or provider_request_id


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
    max_attempts = max(1, settings.xg_request_max_attempts)
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
                    "XG image edit request prepared endpoint=%s model=%s attempt=%s/%s reference_count=%s reference_files=%s prompt_chars=%s proxy_enabled=%s proxy=%s timeout_seconds=%s",
                    endpoint,
                    image_model_name.strip(),
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
                if attempt < max_attempts:
                    delay = retry_delay_seconds(settings.xg_request_retry_backoff_seconds, attempt)
                    logger.warning(
                        "XG image edit request exception will retry model=%s attempt=%s/%s proxy_enabled=%s proxy=%s elapsed_ms=%s exception_type=%s retry_delay_seconds=%s error=%s",
                        image_model_name.strip(),
                        attempt,
                        max_attempts,
                        bool(proxies),
                        proxy_description,
                        elapsed_ms,
                        exc.__class__.__name__,
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
        if response.status_code < 400 or not retryable_xg_status(response.status_code) or attempt == max_attempts:
            break
        delay = retry_delay_seconds(settings.xg_request_retry_backoff_seconds, attempt)
        logger.warning(
            "XG image edit retryable response will retry status_code=%s attempt=%s/%s provider_request_id=%s retry_delay_seconds=%s response_preview=%s",
            response.status_code,
            attempt,
            max_attempts,
            provider_request_id,
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


def request_xg_image(*, prompt: str, reference_paths: list[Path], image_model_name: str) -> tuple[bytes, str, str | None]:
    if is_xg_chat_image_model(image_model_name):
        return request_xg_chat_image(prompt=prompt, reference_paths=reference_paths, image_model_name=image_model_name)
    return request_xg_image_edit(prompt=prompt, reference_paths=reference_paths, image_model_name=image_model_name)


def generate_xg_image(*, prompt: str, reference_paths: list[Path], image_model_name: str) -> GeneratedImageFile:
    content, content_type, provider_request_id = request_xg_image(
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


def generate_xg_image_edit(*, prompt: str, reference_paths: list[Path], image_model_name: str) -> GeneratedImageFile:
    return generate_xg_image(prompt=prompt, reference_paths=reference_paths, image_model_name=image_model_name)
