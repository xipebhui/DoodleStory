#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
SOURCE_PATH="${1:-${DOUYIN_COOKIE_SOURCE:-}}"
COMPOSE_PROJECT_NAME="${COMPOSE_PROJECT_NAME:-}"
COOKIE_TARGET="/app/douyin-import-service/.cache/douyin/cookies.json"

if [[ -z "${SOURCE_PATH}" ]]; then
  for candidate in \
    "${PROJECT_DIR}/../douyin-downloader/cookies.json" \
    "${PROJECT_DIR}/../douyin-downloader/.cookies.json"
  do
    if [[ -f "${candidate}" ]]; then
      SOURCE_PATH="${candidate}"
      break
    fi
  done
fi

if [[ -z "${SOURCE_PATH}" ]]; then
  echo "未找到 Cookie 文件。请传入 cookies.json 路径，或设置 DOUYIN_COOKIE_SOURCE。" >&2
  exit 1
fi

if [[ ! -f "${SOURCE_PATH}" ]]; then
  echo "Cookie 文件不存在：${SOURCE_PATH}" >&2
  exit 1
fi

compose_args=()
if [[ -n "${COMPOSE_PROJECT_NAME}" ]]; then
  compose_args=(-p "${COMPOSE_PROJECT_NAME}")
fi

cd "${PROJECT_DIR}"
docker-compose "${compose_args[@]}" \
  -f docker-compose.coolify.yml \
  -f docker-compose.local.yml \
  exec -T douyin-import-service sh -c "mkdir -p \"$(dirname "${COOKIE_TARGET}")\" && cat > \"${COOKIE_TARGET}\" && chmod 600 \"${COOKIE_TARGET}\"" \
  < "${SOURCE_PATH}"

echo "已写入抖音 Cookie：${COOKIE_TARGET}"
