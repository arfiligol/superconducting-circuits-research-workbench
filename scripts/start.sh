#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "$SCRIPT_DIR/_runtime_common.sh"

ROOT_DIR="$(runtime_root_dir)"
runtime_load_env "$ROOT_DIR"
APP_URL="$(runtime_app_url)"
APP_PORT="$(runtime_app_port)"

PID_DIR="$ROOT_DIR/tmp/runtime_pids"
LOG_DIR="$ROOT_DIR/tmp/runtime_logs"
mkdir -p "$PID_DIR" "$LOG_DIR"

runtime_require_path "$ROOT_DIR/.venv" "uv sync" "start"
runtime_require_path "$ROOT_DIR/backend/.venv" "cd backend && uv sync" "start"
runtime_require_path "$ROOT_DIR/frontend/node_modules" "npm install --prefix frontend" "start"
runtime_require_free_port 3000 frontend
runtime_require_free_port "$APP_PORT" app
runtime_check_redis "$ROOT_DIR"

runtime_start_service "$PID_DIR" "$LOG_DIR" frontend \
  bash -lc "cd '$ROOT_DIR/frontend' && exec ./node_modules/.bin/next dev --webpack --hostname 127.0.0.1 --port 3000"
runtime_start_service "$PID_DIR" "$LOG_DIR" app \
  bash -lc "cd '$ROOT_DIR' && exec uv run sc-app"
runtime_start_service "$PID_DIR" "$LOG_DIR" worker-simulation \
  bash -lc "cd '$ROOT_DIR' && exec uv run sc-worker-simulation"
runtime_start_service "$PID_DIR" "$LOG_DIR" worker-characterization \
  bash -lc "cd '$ROOT_DIR' && exec uv run sc-worker-characterization"

runtime_wait_for_url "frontend" "http://127.0.0.1:3000" "$LOG_DIR/frontend.log" "$PID_DIR/frontend.pid"
runtime_wait_for_url "app" "$APP_URL/health" "$LOG_DIR/app.log" "$PID_DIR/app.pid"
runtime_wait_for_runtime_health "$ROOT_DIR" "$APP_URL"
runtime_record_listen_pid "$PID_DIR" frontend 3000
runtime_record_listen_pid "$PID_DIR" app "$APP_PORT"

echo "[start] Redis is an external prerequisite and was not started by this script"
echo "[start] use npm run stop or ./scripts/stop.sh to stop frontend/app/workers"
