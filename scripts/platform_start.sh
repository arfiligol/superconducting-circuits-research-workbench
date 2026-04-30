#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "$SCRIPT_DIR/platform_common.sh"

ROOT_DIR="$(platform_root_dir)"
platform_load_env "$ROOT_DIR"
APP_URL="$(platform_app_url)"
APP_PORT="$(platform_app_port)"

PID_DIR="$ROOT_DIR/tmp/platform_pids"
LOG_DIR="$ROOT_DIR/tmp/platform_logs"
mkdir -p "$PID_DIR" "$LOG_DIR"

platform_require_path "$ROOT_DIR/.venv" "npm run platform:install"
platform_require_path "$ROOT_DIR/backend/.venv" "npm run platform:install"
platform_require_path "$ROOT_DIR/frontend/node_modules" "npm run platform:install"
platform_require_free_port 3000 frontend
platform_require_free_port "$APP_PORT" app
platform_check_redis "$ROOT_DIR"

platform_start_service "$PID_DIR" "$LOG_DIR" frontend \
  bash -lc "cd '$ROOT_DIR/frontend' && exec ./node_modules/.bin/next dev --webpack --hostname 127.0.0.1 --port 3000"
platform_start_service "$PID_DIR" "$LOG_DIR" app \
  bash -lc "cd '$ROOT_DIR' && exec uv run sc-app"
platform_start_service "$PID_DIR" "$LOG_DIR" worker-simulation \
  bash -lc "cd '$ROOT_DIR' && exec uv run sc-worker-simulation"
platform_start_service "$PID_DIR" "$LOG_DIR" worker-characterization \
  bash -lc "cd '$ROOT_DIR' && exec uv run sc-worker-characterization"

platform_wait_for_url "frontend" "http://127.0.0.1:3000" "$LOG_DIR/frontend.log" "$PID_DIR/frontend.pid"
platform_wait_for_url "app" "$APP_URL/health" "$LOG_DIR/app.log" "$PID_DIR/app.pid"
platform_wait_for_runtime_health "$ROOT_DIR" "$APP_URL"
platform_record_listen_pid "$PID_DIR" frontend 3000
platform_record_listen_pid "$PID_DIR" app "$APP_PORT"

echo "[platform-start] Redis is an external prerequisite and was not started by this script"
echo "[platform-start] use ./scripts/platform_stop.sh to stop frontend/app/workers"
