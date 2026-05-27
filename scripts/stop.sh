#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "$SCRIPT_DIR/_runtime_common.sh"

ROOT_DIR="$(runtime_root_dir)"
PID_DIR="$ROOT_DIR/tmp/runtime_pids"

runtime_stop_service "$PID_DIR" frontend
runtime_stop_service "$PID_DIR" app
runtime_stop_service "$PID_DIR" worker-simulation
runtime_stop_service "$PID_DIR" worker-characterization

echo "[stop] Redis was not managed by this script"
