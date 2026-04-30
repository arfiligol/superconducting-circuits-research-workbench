#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PID_DIR="$ROOT_DIR/tmp/rewrite_pids"
LOG_DIR="$ROOT_DIR/tmp/rewrite_logs"

mkdir -p "$PID_DIR" "$LOG_DIR"

require_path() {
  local path="$1"
  local hint="$2"

  if [[ ! -e "$path" ]]; then
    echo "[rewrite-start] missing $path"
    echo "[rewrite-start] run $hint first"
    exit 1
  fi
}

start_service() {
  local name="$1"
  shift
  local pid_file="$PID_DIR/$name.pid"
  local log_file="$LOG_DIR/$name.log"

  if [[ -f "$pid_file" ]]; then
    local existing_pid
    existing_pid="$(cat "$pid_file")"
    if kill -0 "$existing_pid" 2>/dev/null; then
      echo "[rewrite-start] $name already running (pid=$existing_pid)"
      return
    fi
    rm -f "$pid_file"
  fi

  local pid
  pid="$(
    python3 - "$pid_file" "$log_file" "$@" <<'PY'
import os
import subprocess
import sys

pid_path, log_path, *command = sys.argv[1:]

with open(log_path, "ab", buffering=0) as log_file, open(os.devnull, "rb") as devnull:
    process = subprocess.Popen(
        command,
        stdin=devnull,
        stdout=log_file,
        stderr=log_file,
        start_new_session=True,
    )

with open(pid_path, "w", encoding="utf-8") as handle:
    handle.write(f"{process.pid}\n")

print(process.pid)
PY
  )"
  printf '%s\n' "$pid" >"$pid_file"
  echo "[rewrite-start] started $name (pid=$pid, log=$log_file)"
}

wait_for_url() {
  local name="$1"
  local url="$2"
  local log_file="$3"

  for _ in $(seq 1 45); do
    if curl --fail --silent "$url" >/dev/null 2>&1; then
      echo "[rewrite-start] $name ready at $url"
      return
    fi
    sleep 1
  done

  echo "[rewrite-start] $name did not become ready: $url"
  if [[ -f "$log_file" ]]; then
    tail -n 40 "$log_file"
  fi
  exit 1
}

record_listen_pid() {
  local name="$1"
  local port="$2"
  local pid_file="$PID_DIR/$name.pid"
  local listen_pid

  listen_pid="$(lsof -ti tcp:"$port" -sTCP:LISTEN | head -n 1)"
  if [[ -n "$listen_pid" ]]; then
    printf '%s\n' "$listen_pid" >"$pid_file"
    echo "[rewrite-start] recorded $name listener pid=$listen_pid"
  fi
}

require_path "$ROOT_DIR/frontend/node_modules" "npm run rewrite:install"
require_path "$ROOT_DIR/backend/.venv" "npm run rewrite:install"

start_service backend bash -lc "cd '$ROOT_DIR/backend' && export PYTHONPATH='$ROOT_DIR/backend' && exec ./.venv/bin/uvicorn src.app.main:app --host 127.0.0.1 --port 8000"
start_service frontend bash -lc "cd '$ROOT_DIR/frontend' && exec ./node_modules/.bin/next dev --webpack --hostname 127.0.0.1 --port 3000"

wait_for_url "backend" "http://127.0.0.1:8000/health" "$LOG_DIR/backend.log"
wait_for_url "frontend" "http://127.0.0.1:3000" "$LOG_DIR/frontend.log"
record_listen_pid "backend" 8000
record_listen_pid "frontend" 3000

echo "[rewrite-start] rewrite stack is ready"
echo "[rewrite-start] optional desktop shell: DESKTOP_START_URL=http://127.0.0.1:3000 npm run dev --prefix desktop"
echo "[rewrite-start] use ./scripts/rewrite_stop.sh to stop rewrite processes"
