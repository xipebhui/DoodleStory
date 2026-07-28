#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
PARENT_DIR="$(cd "${PROJECT_DIR}/.." && pwd)"

sync_repo() {
  local target_dir="$1"
  local repo_url="$2"
  local ref="$3"

  if [[ ! -d "${target_dir}/.git" ]]; then
    git clone --branch "${ref}" "${repo_url}" "${target_dir}"
    return
  fi

  git -C "${target_dir}" remote set-url origin "${repo_url}"
  git -C "${target_dir}" fetch origin "${ref}"
  git -C "${target_dir}" checkout "${ref}"
  git -C "${target_dir}" merge --ff-only "origin/${ref}"
}

sync_repo \
  "${PARENT_DIR}/douyin-import-service" \
  "${SOCIAL_IMPORT_SERVICE_REPO:-https://github.com/xipebhui/douyin-import-service.git}" \
  "${SOCIAL_IMPORT_SERVICE_REF:-main}"
sync_repo \
  "${PARENT_DIR}/douyin-downloader" \
  "${DOUYIN_DOWNLOADER_REPO:-https://github.com/xipebhui/douyin-downloader.git}" \
  "${DOUYIN_DOWNLOADER_REF:-main}"
sync_repo \
  "${PARENT_DIR}/wechat-article-crawler" \
  "${WECHAT_CRAWLER_REPO:-https://github.com/xipebhui/wechat-article-crawler.git}" \
  "${WECHAT_CRAWLER_REF:-main}"
sync_repo \
  "${PARENT_DIR}/XHS-Downloader" \
  "${XHS_DOWNLOADER_REPO:-https://github.com/xipebhui/XHS-Downloader.git}" \
  "${XHS_DOWNLOADER_REF:-master}"
