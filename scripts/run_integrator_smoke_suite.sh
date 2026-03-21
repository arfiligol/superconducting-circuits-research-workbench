#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

STRICT_MODE="${SC_SMOKE_STRICT:-0}"
declare -a BASELINE_FAILURES=()

run_required() {
  local label="$1"
  shift
  echo "[smoke] $label"
  "$@"
}

run_report_or_fail() {
  local label="$1"
  shift
  echo "[smoke] $label"
  if "$@"; then
    return 0
  fi

  if [[ "$STRICT_MODE" == "1" ]]; then
    echo "[smoke] strict mode failure: $label" >&2
    exit 1
  fi

  BASELINE_FAILURES+=("$label")
  echo "[smoke] warning: baseline check failed but runtime smoke will continue: $label" >&2
}

check_ruff_format() {
  uv run ruff format . --check
}

check_ruff() {
  uv run ruff check .
}

check_basedpyright() {
  uv run basedpyright
}

check_pytest_matrix() {
  uv run pytest tests/core tests/app tests/scripts
}

run_app_startup_smoke() {
  local port="${SC_APP_PORT:-8099}"
  SC_APP_HOST="${SC_APP_HOST:-127.0.0.1}" \
  SC_APP_PORT="$port" \
  NICEGUI_SCREEN_TEST_PORT="$port" \
  SC_RQ_REDIS_URL="${SC_RQ_REDIS_URL:-fakeredis://integrator-smoke}" \
  uv run python - <<'PY'
import contextlib
import http.client
import os
import socket
import subprocess
import time
from pathlib import Path

root = Path.cwd()
port = int(os.environ["SC_APP_PORT"])
env = dict(os.environ)
proc = subprocess.Popen(
    [str(root / ".venv/bin/sc-legacy-nicegui")],
    cwd=root,
    env=env,
    stdout=subprocess.DEVNULL,
    stderr=subprocess.DEVNULL,
)
try:
    deadline = time.monotonic() + 60.0
    while time.monotonic() < deadline:
        try:
            conn = http.client.HTTPConnection("127.0.0.1", port, timeout=1)
            conn.request("GET", "/login")
            response = conn.getresponse()
            response.read()
            conn.close()
            if response.status == 200:
                print(f"sc-legacy-nicegui ready on http://127.0.0.1:{port}")
                raise SystemExit(0)
        except Exception:
            time.sleep(0.2)
    raise SystemExit("sc-legacy-nicegui startup smoke timed out")
finally:
    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(timeout=5)
PY
}

run_required \
  "sc-worker-simulation startup" \
  env SC_RQ_REDIS_URL="${SC_RQ_REDIS_URL:-fakeredis://integrator-smoke}" \
  uv run sc-worker-simulation --max-tasks 0
run_required \
  "sc-worker-characterization startup" \
  env SC_RQ_REDIS_URL="${SC_RQ_REDIS_URL:-fakeredis://integrator-smoke}" \
  uv run sc-worker-characterization --max-tasks 0
run_required "sc-legacy-nicegui startup" run_app_startup_smoke
run_required \
  "focused runtime validation" \
  uv run pytest tests/app/pages/test_unaffected_page_routes.py tests/scripts/test_runtime_smokes.py tests/scripts/cli/test_sim_tasks.py -q

run_report_or_fail "ruff format . --check" check_ruff_format
run_report_or_fail "ruff check ." check_ruff
run_report_or_fail "basedpyright" check_basedpyright
run_report_or_fail "pytest tests/core tests/app tests/scripts" check_pytest_matrix

if [[ "${SC_SMOKE_INCLUDE_EXTENDED:-0}" == "1" ]]; then
  run_required \
    "extended playwright characterization e2e" \
    env RUN_PLAYWRIGHT_CHARACTERIZATION_E2E=1 uv run pytest tests/app/e2e/test_characterization_playwright.py -q

  run_required \
    "extended playwright josephson e2e" \
    env RUN_PLAYWRIGHT_JOSEPHSON_E2E=1 uv run pytest tests/app/e2e/test_josephson_examples_playwright.py \
      -k "linear_series_lc or port_termination_compensation_modes_in_ui" -q
fi

if [[ "${#BASELINE_FAILURES[@]}" -gt 0 ]]; then
  echo "[smoke] completed required runtime smoke with report-only baseline failures:" >&2
  printf '  - %s\n' "${BASELINE_FAILURES[@]}" >&2
  echo "[smoke] re-run with SC_SMOKE_STRICT=1 to make baseline checks fatal" >&2
fi

echo "[smoke] complete"
