#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
DOWNLOADER_ROOT="${DOUYIN_DOWNLOADER_ROOT:-}"
PYTHON_BIN="${DOUYIN_DOWNLOADER_PYTHON:-python3}"
OUTPUT_PATH="${DOUYIN_COOKIE_FILE:-$ROOT_DIR/.cache/douyin/cookies.json}"

if [ -z "$DOWNLOADER_ROOT" ]; then
  echo "缺少 DOUYIN_DOWNLOADER_ROOT，请指向 jiji262/douyin-downloader 仓库目录" >&2
  exit 1
fi

if [ ! -f "$DOWNLOADER_ROOT/run.py" ]; then
  echo "DOUYIN_DOWNLOADER_ROOT 不正确，未找到 $DOWNLOADER_ROOT/run.py" >&2
  exit 1
fi

mkdir -p "$(dirname "$OUTPUT_PATH")"

(
  cd "$DOWNLOADER_ROOT"
  "$PYTHON_BIN" -m tools.cookie_fetcher --output "$OUTPUT_PATH"
)

chmod 600 "$OUTPUT_PATH"
echo "Cookie 已保存到 $OUTPUT_PATH"
echo "请在 .env 中配置：DOUYIN_COOKIE_FILE=$OUTPUT_PATH"
