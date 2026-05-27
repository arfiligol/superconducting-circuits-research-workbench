#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "$SCRIPT_DIR/platform_common.sh"

ROOT_DIR="$(platform_root_dir)"
PID_DIR="$ROOT_DIR/tmp/platform_pids"

platform_stop_service "$PID_DIR" frontend
platform_stop_service "$PID_DIR" app
platform_stop_service "$PID_DIR" worker-simulation
platform_stop_service "$PID_DIR" worker-characterization

echo "[stop] Redis was not managed by this script"
