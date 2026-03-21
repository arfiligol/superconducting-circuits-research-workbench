#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "$SCRIPT_DIR/platform_common.sh"

ROOT_DIR="$(platform_root_dir)"
platform_load_env "$ROOT_DIR"
cd "$ROOT_DIR"
APP_URL="$(platform_app_url)"
APP_PORT="$(platform_app_port)"

PID_DIR="$ROOT_DIR/tmp/dev_pids"
LOG_DIR="$ROOT_DIR/tmp/dev_logs"
mkdir -p "$PID_DIR" "$LOG_DIR"
platform_require_path "$ROOT_DIR/.venv" "npm run platform:install" "dev-start"
platform_require_free_port "$APP_PORT" app "dev-start"
platform_check_redis "$ROOT_DIR"
platform_start_service "$PID_DIR" "$LOG_DIR" app bash -lc "cd '$ROOT_DIR' && exec uv run sc-app"
platform_start_service "$PID_DIR" "$LOG_DIR" worker-simulation bash -lc "cd '$ROOT_DIR' && exec uv run sc-worker-simulation"
platform_start_service "$PID_DIR" "$LOG_DIR" worker-characterization bash -lc "cd '$ROOT_DIR' && exec uv run sc-worker-characterization"
platform_wait_for_url "app" "$APP_URL/health" "$LOG_DIR/app.log" "$PID_DIR/app.pid"
platform_wait_for_runtime_health "$ROOT_DIR" "$APP_URL"
echo "[dev-start] started app + worker local stack with external Redis"
echo "[dev-start] use ./scripts/dev_stop.sh to stop all started processes"
