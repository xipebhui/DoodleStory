#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"

echo "[check] repository root: $ROOT_DIR"

run_if_present() {
  local description="$1"
  local path="$2"
  shift 2

  if [ -e "$path" ]; then
    echo "[check] $description"
    (
      cd "$(dirname "$path")"
      "$@"
    )
  fi
}

if [ -f "$ROOT_DIR/backend/requirements.txt" ]; then
  echo "[check] backend python compile"
  python3.11 -m compileall "$ROOT_DIR/backend/app"
fi

run_if_present "frontend build" "$ROOT_DIR/frontend/package.json" npm run build

if [ -f "$ROOT_DIR/voice_gen.py" ]; then
  echo "[check] compiling standalone python entrypoints"
  python3 -m compileall "$ROOT_DIR/voice_gen.py"
fi

echo "[check] done"
