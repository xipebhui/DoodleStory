#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
PARENT_DIR="$(cd "${PROJECT_DIR}/.." && pwd)"
TARGET_DIR="${DOUYIN_DOWNLOADER_DIR:-${PARENT_DIR}/douyin-downloader}"
REPO_URL="${DOUYIN_DOWNLOADER_REPO:-git@github.com:xipebhui/douyin-downloader.git}"
REF="${DOUYIN_DOWNLOADER_REF:-main}"

if [[ ! -d "${TARGET_DIR}/.git" ]]; then
  git clone --branch "${REF}" "${REPO_URL}" "${TARGET_DIR}"
  exit 0
fi

cd "${TARGET_DIR}"
git remote set-url origin "${REPO_URL}"
git fetch origin "${REF}"
git checkout "${REF}"
git merge --ff-only "origin/${REF}"
