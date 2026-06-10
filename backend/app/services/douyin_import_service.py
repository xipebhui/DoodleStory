from dataclasses import dataclass
from pathlib import Path

import requests

from app.core.config import get_settings

DOUYIN_IMPORT_TIMEOUT_SECONDS = 180


class DouyinImportServiceError(RuntimeError):
    pass


class DouyinImportConfigError(DouyinImportServiceError):
    pass


@dataclass(frozen=True)
class DouyinImportResult:
    url: str
    output_dir: Path
    media_type: str
    aweme_id: str | None
    title: str | None
    description: str | None
    tags: list[str]
    media_files: list[Path]
    metadata_files: list[Path]
    manifest_path: Path | None


def douyin_import_base_url() -> str:
    base_url = get_settings().douyin_import_service_base_url.strip().rstrip("/")
    if not base_url:
        raise DouyinImportConfigError("缺少 DOUYIN_IMPORT_SERVICE_BASE_URL，无法调用抖音下载服务")
    return base_url


def check_douyin_import_health() -> dict[str, object]:
    base_url = douyin_import_base_url()
    try:
        response = requests.get(f"{base_url}/health", timeout=10)
    except requests.RequestException as exc:
        raise DouyinImportServiceError(f"抖音下载服务不可用：{exc}") from exc
    if response.status_code != 200:
        raise DouyinImportServiceError(f"抖音下载服务健康检查失败：HTTP {response.status_code}")
    try:
        payload = response.json()
    except ValueError:
        payload = {"raw": response.text}
    return {"ok": True, "service_base_url": base_url, "response": payload}


def _path_list(values: object, field_name: str) -> list[Path]:
    if values is None:
        return []
    if not isinstance(values, list):
        raise DouyinImportServiceError(f"抖音下载服务返回字段 {field_name} 必须是数组")
    paths: list[Path] = []
    for value in values:
        if not isinstance(value, str) or not value.strip():
            raise DouyinImportServiceError(f"抖音下载服务返回字段 {field_name} 包含非法路径")
        paths.append(Path(value))
    return paths


def _optional_text(payload: dict[str, object], field_name: str) -> str | None:
    value = payload.get(field_name)
    if value is None:
        return None
    if not isinstance(value, str):
        raise DouyinImportServiceError(f"抖音下载服务返回字段 {field_name} 必须是字符串")
    value = value.strip()
    return value or None


def _optional_tags(payload: dict[str, object]) -> list[str]:
    value = payload.get("tags")
    if value is None:
        return []
    if not isinstance(value, list):
        raise DouyinImportServiceError("抖音下载服务返回字段 tags 必须是数组")
    tags: list[str] = []
    for item in value:
        if not isinstance(item, str):
            raise DouyinImportServiceError("抖音下载服务返回字段 tags 只能包含字符串")
        item = item.strip()
        if item:
            tags.append(item)
    return tags


def download_douyin_content(url: str) -> DouyinImportResult:
    if not url.strip():
        raise DouyinImportConfigError("抖音链接不能为空")

    base_url = douyin_import_base_url()
    try:
        response = requests.post(
            f"{base_url}/api/v1/download",
            json={"url": url.strip()},
            timeout=DOUYIN_IMPORT_TIMEOUT_SECONDS,
        )
    except requests.RequestException as exc:
        raise DouyinImportServiceError(f"抖音下载服务不可用：{exc}") from exc

    if response.status_code in {400, 502}:
        try:
            detail = response.json().get("detail")
        except ValueError:
            detail = response.text
        message = detail or f"HTTP {response.status_code}"
        raise DouyinImportServiceError(f"抖音下载失败：{message}")
    if response.status_code != 200:
        raise DouyinImportServiceError(f"抖音下载服务返回异常：HTTP {response.status_code}")

    try:
        payload = response.json()
    except ValueError as exc:
        raise DouyinImportServiceError("抖音下载服务返回内容不是合法 JSON") from exc
    if not isinstance(payload, dict):
        raise DouyinImportServiceError("抖音下载服务返回内容必须是 JSON object")

    output_dir = payload.get("output_dir")
    media_type = payload.get("media_type")
    if not isinstance(output_dir, str) or not output_dir.strip():
        raise DouyinImportServiceError("抖音下载服务未返回 output_dir")
    if not isinstance(media_type, str) or not media_type.strip():
        raise DouyinImportServiceError("抖音下载服务未返回 media_type")

    media_files = _path_list(payload.get("media_files"), "media_files")
    if not media_files:
        raise DouyinImportServiceError("抖音下载未产生媒体文件")

    manifest_path = payload.get("manifest_path")
    return DouyinImportResult(
        url=str(payload.get("url") or url).strip(),
        output_dir=Path(output_dir),
        media_type=media_type.strip(),
        aweme_id=str(payload["aweme_id"]).strip() if payload.get("aweme_id") else None,
        title=_optional_text(payload, "title"),
        description=_optional_text(payload, "description"),
        tags=_optional_tags(payload),
        media_files=media_files,
        metadata_files=_path_list(payload.get("metadata_files"), "metadata_files"),
        manifest_path=Path(manifest_path) if isinstance(manifest_path, str) and manifest_path.strip() else None,
    )
