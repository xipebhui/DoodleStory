#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
URL="${1:-}"

if [ -z "$URL" ]; then
  echo "用法：$0 <douyin-url>" >&2
  exit 1
fi

cd "$ROOT_DIR"
PYTHON_BIN="${BACKEND_PYTHON:-$ROOT_DIR/backend/.venv/bin/python}"
if [ ! -x "$PYTHON_BIN" ]; then
  PYTHON_BIN="python3.11"
fi

PYTHONPATH="$ROOT_DIR/backend" "$PYTHON_BIN" - "$URL" <<'PY'
import sys
from app.services.douyin_downloader import DouyinDownloaderError, download_douyin_media

url = sys.argv[1]
try:
    result = download_douyin_media(url)
except DouyinDownloaderError as exc:
    print(f"抖音下载测试失败：{exc}", file=sys.stderr)
    raise SystemExit(1) from exc
print(f"output_dir={result.output_dir}")
print(f"media_count={len(result.media_files)}")
for path in result.media_files:
    print(f"media={path}")
if result.manifest_path:
    print(f"manifest={result.manifest_path}")
PY
