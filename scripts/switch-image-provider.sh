#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
PROVIDER="${1:-}"

if [ "$PROVIDER" != "qy" ] && [ "$PROVIDER" != "xgapi" ] && [ "$PROVIDER" != "grok" ]; then
  echo "Usage: $0 qy|xgapi|grok" >&2
  exit 2
fi

set_env_value() {
  local file="$1"
  local key="$2"
  local value="$3"

  if [ ! -f "$file" ]; then
    return
  fi

  local tmp_file
  tmp_file="$(mktemp)"
  if grep -q "^${key}=" "$file"; then
    awk -v key="$key" -v value="$value" 'BEGIN { prefix = key "=" } index($0, prefix) == 1 { print key "=" value; next } { print }' "$file" > "$tmp_file"
  else
    cp "$file" "$tmp_file"
    printf '\n%s=%s\n' "$key" "$value" >> "$tmp_file"
  fi
  mv "$tmp_file" "$file"
}

UPDATED=0
for env_file in "$ROOT_DIR/.env" "$ROOT_DIR/backend/.env"; do
  if [ -f "$env_file" ]; then
    set_env_value "$env_file" "IMAGE_PROVIDER" "$PROVIDER"
    echo "[switch-image-provider] updated IMAGE_PROVIDER in $env_file"
    UPDATED=1
  fi
done

if [ "$UPDATED" -eq 0 ]; then
  echo "[switch-image-provider] no .env file found; create .env from .env.example first" >&2
  exit 1
fi

echo "[switch-image-provider] selected provider: $PROVIDER"
echo "[switch-image-provider] restart backend service for the change to take effect"
