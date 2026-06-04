#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "$SCRIPT_DIR/../_runtime_common.sh"

ROOT_DIR="$(runtime_root_dir)"
runtime_load_env "$ROOT_DIR"
APP_HOST="$(runtime_app_host)"
APP_PORT="$(runtime_app_port)"
APP_URL="$(runtime_app_url)"

PID_DIR="$ROOT_DIR/tmp/runtime_pids"
LOG_DIR="$ROOT_DIR/tmp/runtime_logs"
mkdir -p "$PID_DIR" "$LOG_DIR"

runtime_require_path "$ROOT_DIR/.venv" "uv sync --all-packages" "app:dev"
runtime_require_path "$ROOT_DIR/app/frontend/node_modules" "npm install --prefix app/frontend" "app:dev"
runtime_require_free_port 3000 frontend app:dev
runtime_require_free_port "$APP_PORT" backend app:dev

runtime_start_service "$PID_DIR" "$LOG_DIR" frontend \
  bash -lc "cd '$ROOT_DIR/app/frontend' && exec npm run dev -- --hostname 127.0.0.1 --port 3000"

runtime_start_service "$PID_DIR" "$LOG_DIR" backend \
  bash -lc "cd '$ROOT_DIR' && exec uv run --package superconducting-circuits-backend uvicorn app_backend.main:app --host '$APP_HOST' --port '$APP_PORT'"

runtime_wait_for_url "frontend" "http://127.0.0.1:3000" "$LOG_DIR/frontend.log" "$PID_DIR/frontend.pid"
runtime_wait_for_url "backend" "$APP_URL/health" "$LOG_DIR/backend.log" "$PID_DIR/backend.pid"

runtime_start_service "$PID_DIR" "$LOG_DIR" julia-runner \
  bash -lc "cd '$ROOT_DIR' && exec julia --project=core/julia/SuperconductingCircuitsRunner -e 'using SuperconductingCircuitsRunner; run_polling_runner(backend_url=\"${APP_URL}\")'"

runtime_record_listen_pid "$PID_DIR" frontend 3000
runtime_record_listen_pid "$PID_DIR" backend "$APP_PORT"

echo "[app:dev] frontend ready at http://127.0.0.1:3000"
echo "[app:dev] backend ready at $APP_URL"
echo "[app:dev] Julia Runner polling $APP_URL"
