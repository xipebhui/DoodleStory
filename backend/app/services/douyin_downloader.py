import json
import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import uuid4

from app.core.config import get_settings

MEDIA_SUFFIXES = {".mp4", ".jpg", ".jpeg", ".png", ".webp", ".gif"}


class DouyinDownloaderError(RuntimeError):
    pass


class DouyinDownloaderConfigError(DouyinDownloaderError):
    pass


@dataclass(frozen=True)
class DouyinDownloadResult:
    url: str
    output_dir: Path
    media_files: list[Path]
    metadata_files: list[Path]
    manifest_path: Path | None
    stdout: str
    stderr: str


def _configured_downloader_root() -> Path:
    root = get_settings().douyin_downloader_root.strip()
    if not root:
        raise DouyinDownloaderConfigError("缺少 DOUYIN_DOWNLOADER_ROOT，无法定位 jiji262/douyin-downloader 仓库")
    path = Path(root).expanduser().resolve()
    run_py = path / "run.py"
    if not run_py.exists():
        raise DouyinDownloaderConfigError(f"DOUYIN_DOWNLOADER_ROOT 不正确，未找到 {run_py}")
    return path


def _configured_python() -> str:
    configured = get_settings().douyin_downloader_python.strip()
    if configured:
        return configured
    return sys.executable


def _cookie_header_from_file(path: Path) -> str:
    if not path.exists():
        raise DouyinDownloaderConfigError(f"DOUYIN_COOKIE_FILE 不存在：{path}")
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise DouyinDownloaderConfigError(f"DOUYIN_COOKIE_FILE 不是合法 JSON：{path}") from exc
    if not isinstance(raw, dict):
        raise DouyinDownloaderConfigError("DOUYIN_COOKIE_FILE 必须是官方 cookie_fetcher 生成的 JSON object")
    pairs = [
        f"{key}={value}"
        for key, value in raw.items()
        if isinstance(key, str) and key.strip() and isinstance(value, str) and value.strip()
    ]
    if not pairs:
        raise DouyinDownloaderConfigError("DOUYIN_COOKIE_FILE 中没有可用 Cookie")
    return "; ".join(pairs)


def _configured_cookie_header() -> str:
    settings = get_settings()
    if settings.douyin_cookie.strip():
        return settings.douyin_cookie.strip()
    if settings.douyin_cookie_file.strip():
        return _cookie_header_from_file(Path(settings.douyin_cookie_file).expanduser())
    raise DouyinDownloaderConfigError("缺少 DOUYIN_COOKIE 或 DOUYIN_COOKIE_FILE，无法请求抖音详情接口")


def _redact_cookie_values(text: str, cookie_header: str) -> str:
    redacted = text
    for part in cookie_header.split(";"):
        if "=" not in part:
            continue
        key, value = part.split("=", 1)
        value = value.strip()
        if value:
            redacted = redacted.replace(value, "[REDACTED]")
        key = key.strip()
        if key:
            redacted = re.sub(rf"({re.escape(key)}=)[^;\s]+", rf"\1[REDACTED]", redacted)
    return redacted


def _write_config(config_path: Path, output_dir: Path) -> None:
    config_path.write_text(
        f"""link: []
path: {output_dir}

music: false
cover: false
avatar: false
json: true
folderstyle: true
filename_template: "{{date}}_{{title}}_{{id}}"
folder_template: "{{date}}_{{title}}_{{id}}"
author_dir: "nickname_uid"
download_pinned: false

mode:
  - post

number:
  post: 1
  like: 0
  allmix: 0
  mix: 0
  music: 0
  collect: 0
  collectmix: 0

increase:
  post: false
  like: false
  allmix: false
  mix: false
  music: false

thread: 1
retry_times: 1
rate_limit: 1
proxy: ""
database: false
database_path: {output_dir / "dy_downloader.db"}

progress:
  quiet_logs: false

browser_fallback:
  enabled: false
  headless: true
  max_scrolls: 0
  idle_rounds: 0
  wait_timeout_seconds: 10

comments:
  enabled: false
  include_replies: false
  max_comments: 0
  page_size: 20

transcript:
  enabled: false
  model: gpt-4o-mini-transcribe
  output_dir: ""
  response_formats:
    - txt
    - json
  api_url: https://api.openai.com/v1/audio/transcriptions
  api_key_env: OPENAI_API_KEY
  api_key: ""

notifications:
  enabled: false
  on_success: true
  on_failure: true
  providers: []
""",
        encoding="utf-8",
    )
    config_path.chmod(0o600)


def _collect_downloaded_files(output_dir: Path) -> tuple[list[Path], list[Path], Path | None]:
    media_files: list[Path] = []
    metadata_files: list[Path] = []
    manifest_path: Path | None = None
    if not output_dir.exists():
        return media_files, metadata_files, manifest_path
    for path in output_dir.rglob("*"):
        if not path.is_file():
            continue
        suffix = path.suffix.lower()
        if suffix in MEDIA_SUFFIXES and path.stat().st_size > 0:
            media_files.append(path)
        elif suffix == ".json" and path.stat().st_size > 0:
            metadata_files.append(path)
        elif path.name == "download_manifest.jsonl" and path.stat().st_size > 0:
            manifest_path = path
    return sorted(media_files), sorted(metadata_files), manifest_path


def download_douyin_media(url: str, output_dir: Path | None = None) -> DouyinDownloadResult:
    if not url.strip():
        raise DouyinDownloaderConfigError("抖音链接不能为空")
    root = _configured_downloader_root()
    cookie_header = _configured_cookie_header()
    python_bin = _configured_python()
    if not shutil.which(python_bin) and not Path(python_bin).exists():
        raise DouyinDownloaderConfigError(f"DOUYIN_DOWNLOADER_PYTHON 不可执行：{python_bin}")

    settings = get_settings()
    target_dir = output_dir or settings.storage_root / "_imports" / "douyin" / uuid4().hex
    target_dir.mkdir(parents=True, exist_ok=True)

    with TemporaryDirectory(prefix="doodlestory-douyin-") as temp_dir:
        config_path = Path(temp_dir) / "config.yml"
        _write_config(config_path, target_dir)
        env = os.environ.copy()
        env["DOUYIN_COOKIE"] = cookie_header
        process = subprocess.run(
            [
                python_bin,
                str(root / "run.py"),
                "-c",
                str(config_path),
                "-u",
                url.strip(),
                "-p",
                str(target_dir),
                "--show-warnings",
            ],
            cwd=root,
            env=env,
            text=True,
            capture_output=True,
            timeout=max(1, settings.douyin_download_timeout_seconds),
            check=False,
        )

    stdout = _redact_cookie_values(process.stdout, cookie_header)
    stderr = _redact_cookie_values(process.stderr, cookie_header)
    if process.returncode != 0:
        raise DouyinDownloaderError(f"抖音下载器退出失败 code={process.returncode}\n{stdout}\n{stderr}".strip())

    media_files, metadata_files, manifest_path = _collect_downloaded_files(target_dir)
    if not media_files:
        raise DouyinDownloaderError(f"抖音下载未产生媒体文件\n{stdout}\n{stderr}".strip())

    return DouyinDownloadResult(
        url=url.strip(),
        output_dir=target_dir,
        media_files=media_files,
        metadata_files=metadata_files,
        manifest_path=manifest_path,
        stdout=stdout,
        stderr=stderr,
    )
