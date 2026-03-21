#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "$SCRIPT_DIR/platform_common.sh"

ROOT_DIR="$(platform_root_dir)"
platform_load_env "$ROOT_DIR"
APP_URL="$(platform_app_url)"

(
  cd "$ROOT_DIR"
  uv run python scripts/check_worker_runtime.py --app-url "$APP_URL"
)
