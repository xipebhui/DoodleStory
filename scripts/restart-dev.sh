#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
BACKEND_HOST="${BACKEND_HOST:-127.0.0.1}"
BACKEND_PORT="${BACKEND_PORT:-8000}"
FRONTEND_HOST="${FRONTEND_HOST:-127.0.0.1}"
FRONTEND_PORT="${FRONTEND_PORT:-3000}"

BACKEND_PID_FILE="${BACKEND_PID_FILE:-/tmp/doodlestory-backend.pid}"
FRONTEND_PID_FILE="${FRONTEND_PID_FILE:-/tmp/doodlestory-frontend.pid}"
BACKEND_LOG_FILE="${BACKEND_LOG_FILE:-/tmp/doodlestory-backend.log}"
FRONTEND_LOG_FILE="${FRONTEND_LOG_FILE:-/tmp/doodlestory-frontend.log}"

echo "[restart-dev] root: $ROOT_DIR"

kill_pid_file() {
  local name="$1"
  local pid_file="$2"

  if [ ! -f "$pid_file" ]; then
    return
  fi

  local pid
  pid="$(cat "$pid_file" 2>/dev/null || true)"
  if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
    echo "[restart-dev] stopping $name pid=$pid"
    kill "$pid" 2>/dev/null || true
  fi
  rm -f "$pid_file"
}

kill_port() {
  local name="$1"
  local port="$2"

  if ! command -v lsof >/dev/null 2>&1; then
    return
  fi

  local pids
  pids="$(lsof -tiTCP:"$port" -sTCP:LISTEN 2>/dev/null || true)"
  if [ -z "$pids" ]; then
    return
  fi

  echo "[restart-dev] stopping $name listener(s) on port $port: $pids"
  while IFS= read -r pid; do
    [ -n "$pid" ] && kill "$pid" 2>/dev/null || true
  done <<< "$pids"
}

wait_for_port() {
  local name="$1"
  local port="$2"
  local attempts="${3:-30}"

  if ! command -v lsof >/dev/null 2>&1; then
    return
  fi

  for _ in $(seq 1 "$attempts"); do
    if lsof -tiTCP:"$port" -sTCP:LISTEN >/dev/null 2>&1; then
      echo "[restart-dev] $name is listening on port $port"
      return
    fi
    sleep 1
  done

  echo "[restart-dev] ERROR: $name did not start on port $port" >&2
  return 1
}

backend_python() {
  if [ -x "$ROOT_DIR/backend/.venv/bin/python" ]; then
    echo "$ROOT_DIR/backend/.venv/bin/python"
  elif command -v python3.11 >/dev/null 2>&1; then
    command -v python3.11
  else
    command -v python3
  fi
}

kill_pid_file "backend" "$BACKEND_PID_FILE"
kill_pid_file "frontend" "$FRONTEND_PID_FILE"
kill_port "backend" "$BACKEND_PORT"
kill_port "frontend" "$FRONTEND_PORT"
sleep 1

BACKEND_PYTHON="$(backend_python)"
echo "[restart-dev] starting backend: http://$BACKEND_HOST:$BACKEND_PORT"
(
  cd "$ROOT_DIR"
  nohup env PYTHONPATH=backend "$BACKEND_PYTHON" -m uvicorn app.main:app \
    --host "$BACKEND_HOST" \
    --port "$BACKEND_PORT" \
    </dev/null >"$BACKEND_LOG_FILE" 2>&1 &
  echo $! > "$BACKEND_PID_FILE"
)

echo "[restart-dev] starting frontend: http://$FRONTEND_HOST:$FRONTEND_PORT"
(
  cd "$ROOT_DIR/frontend"
  nohup npm run dev -- --host "$FRONTEND_HOST" --port "$FRONTEND_PORT" \
    </dev/null >"$FRONTEND_LOG_FILE" 2>&1 &
  echo $! > "$FRONTEND_PID_FILE"
)

wait_for_port "backend" "$BACKEND_PORT"
wait_for_port "frontend" "$FRONTEND_PORT"

echo "[restart-dev] backend pid: $(cat "$BACKEND_PID_FILE")"
echo "[restart-dev] frontend pid: $(cat "$FRONTEND_PID_FILE")"
echo "[restart-dev] backend log: $BACKEND_LOG_FILE"
echo "[restart-dev] frontend log: $FRONTEND_LOG_FILE"
echo "[restart-dev] done"
