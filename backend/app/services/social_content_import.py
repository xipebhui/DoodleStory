from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import requests

from app.core.config import get_settings


SOCIAL_CONTENT_IMPORT_TIMEOUT_SECONDS = 180


class SocialContentImportError(RuntimeError):
    pass


class SocialContentImportConfigError(SocialContentImportError):
    pass


@dataclass(frozen=True)
class SocialContentImportResult:
    platform: str
    url: str
    resolved_url: str
    output_dir: Path
    content_type: str | None
    content_id: str | None
    title: str | None
    description: str | None
    tags: list[str]
    author_name: str | None
    publish_time: str | None
    publish_timestamp: int | None
    media_files: list[Path]
    metadata_files: list[Path]
    metrics: dict[str, bool | int | float | str | None]


def social_content_import_base_url() -> str:
    base_url = get_settings().douyin_import_service_base_url.strip().rstrip("/")
    if not base_url:
        raise SocialContentImportConfigError(
            "缺少 DOUYIN_IMPORT_SERVICE_BASE_URL，无法调用多平台素材导入服务"
        )
    return base_url


def _required_text(payload: dict[str, object], field_name: str) -> str:
    value = payload.get(field_name)
    if not isinstance(value, str) or not value.strip():
        raise SocialContentImportError(
            f"多平台素材导入服务未返回有效字段 {field_name}"
        )
    return value.strip()


def _optional_text(payload: dict[str, object], field_name: str) -> str | None:
    value = payload.get(field_name)
    if value is None:
        return None
    if not isinstance(value, str):
        raise SocialContentImportError(
            f"多平台素材导入服务返回字段 {field_name} 必须是字符串"
        )
    return value.strip() or None


def _string_list(payload: dict[str, object], field_name: str) -> list[str]:
    value = payload.get(field_name)
    if value is None:
        return []
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise SocialContentImportError(
            f"多平台素材导入服务返回字段 {field_name} 必须是字符串数组"
        )
    return [item.strip() for item in value if item.strip()]


def _path_list(payload: dict[str, object], field_name: str) -> list[Path]:
    return [Path(value) for value in _string_list(payload, field_name)]


def _metrics(
    payload: dict[str, object],
) -> dict[str, bool | int | float | str | None]:
    value = payload.get("metrics")
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise SocialContentImportError(
            "多平台素材导入服务返回字段 metrics 必须是 JSON object"
        )
    allowed_types = (bool, int, float, str)
    if any(
        item is not None and not isinstance(item, allowed_types)
        for item in value.values()
    ):
        raise SocialContentImportError(
            "多平台素材导入服务返回字段 metrics 包含不支持的值"
        )
    return {str(key): item for key, item in value.items()}


def import_social_content(url: str) -> SocialContentImportResult:
    normalized_url = url.strip()
    if not normalized_url:
        raise SocialContentImportConfigError("素材链接不能为空")

    try:
        response = requests.post(
            f"{social_content_import_base_url()}/api/v1/import",
            json={"url": normalized_url, "include_comments": False},
            timeout=SOCIAL_CONTENT_IMPORT_TIMEOUT_SECONDS,
        )
    except requests.RequestException as exc:
        raise SocialContentImportError(f"多平台素材导入服务不可用：{exc}") from exc

    if response.status_code in {400, 502}:
        try:
            response_payload = response.json()
            detail = (
                response_payload.get("detail")
                if isinstance(response_payload, dict)
                else None
            )
        except ValueError:
            detail = response.text
        raise SocialContentImportError(
            f"素材导入失败：{detail or f'HTTP {response.status_code}'}"
        )
    if response.status_code != 200:
        raise SocialContentImportError(
            f"多平台素材导入服务返回异常：HTTP {response.status_code}"
        )

    try:
        payload = response.json()
    except ValueError as exc:
        raise SocialContentImportError(
            "多平台素材导入服务返回内容不是合法 JSON"
        ) from exc
    if not isinstance(payload, dict):
        raise SocialContentImportError(
            "多平台素材导入服务返回内容必须是 JSON object"
        )

    publish_timestamp = payload.get("publish_timestamp")
    if publish_timestamp is not None and (
        isinstance(publish_timestamp, bool)
        or not isinstance(publish_timestamp, int)
    ):
        raise SocialContentImportError(
            "多平台素材导入服务返回字段 publish_timestamp 必须是整数"
        )

    return SocialContentImportResult(
        platform=_required_text(payload, "platform"),
        url=_required_text(payload, "url"),
        resolved_url=_required_text(payload, "resolved_url"),
        output_dir=Path(_required_text(payload, "output_dir")),
        content_type=_optional_text(payload, "content_type"),
        content_id=_optional_text(payload, "content_id"),
        title=_optional_text(payload, "title"),
        description=_optional_text(payload, "description"),
        tags=_string_list(payload, "tags"),
        author_name=_optional_text(payload, "author_name"),
        publish_time=_optional_text(payload, "publish_time"),
        publish_timestamp=publish_timestamp,
        media_files=_path_list(payload, "media_files"),
        metadata_files=_path_list(payload, "metadata_files"),
        metrics=_metrics(payload),
    )
