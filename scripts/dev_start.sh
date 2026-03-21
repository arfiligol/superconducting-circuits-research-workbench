#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if [[ -f .env ]]; then
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
fi

PID_DIR="$ROOT_DIR/tmp/dev_pids"
LOG_DIR="$ROOT_DIR/tmp/dev_logs"
mkdir -p "$PID_DIR" "$LOG_DIR"

start_service() {
  local name="$1"
  shift
  local pid_file="$PID_DIR/$name.pid"
  local log_file="$LOG_DIR/$name.log"

  if [[ -f "$pid_file" ]]; then
    local existing_pid
    existing_pid="$(cat "$pid_file")"
    if kill -0 "$existing_pid" 2>/dev/null; then
      echo "[dev-start] $name already running (pid=$existing_pid)"
      return
    fi
    rm -f "$pid_file"
  fi

  "$@" >"$log_file" 2>&1 &
  local pid=$!
  printf '%s\n' "$pid" >"$pid_file"
  echo "[dev-start] started $name (pid=$pid, log=$log_file)"
}

start_service app uv run sc-app
start_service worker-simulation uv run sc-worker-simulation
start_service worker-characterization uv run sc-worker-characterization
echo "[dev-start] started app + worker local stack"
echo "[dev-start] use ./scripts/dev_stop.sh to stop all started processes"
