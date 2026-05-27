#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "$SCRIPT_DIR/platform_common.sh"

ROOT_DIR="$(platform_root_dir)"
platform_load_env "$ROOT_DIR"

PID_DIR="$ROOT_DIR/tmp/runtime_verify_pids"
LOG_DIR="$ROOT_DIR/tmp/runtime_verify_logs"
mkdir -p "$PID_DIR" "$LOG_DIR"

REDIS_CONTAINER=""
REDIS_PORT="${SC_PLATFORM_REDIS_PORT:-6391}"
export SC_APP_HOST="${SC_APP_HOST:-127.0.0.1}"
export SC_APP_PORT="${SC_APP_PORT:-8010}"
export SC_APP_BASE_URL="${SC_APP_BASE_URL:-http://${SC_APP_HOST}:${SC_APP_PORT}}"
APP_URL="$(platform_app_url)"
APP_PORT="$(platform_app_port)"
LOCAL_SIMULATION_DEFINITION_ID="c8f08463-bf18-4f8e-a5d5-735f3d7b0d6e"

cleanup() {
  platform_stop_service "$PID_DIR" app "runtime-verify-stop"
  platform_stop_service "$PID_DIR" worker-simulation "runtime-verify-stop"
  platform_stop_service "$PID_DIR" worker-characterization "runtime-verify-stop"
  if [[ -n "$REDIS_CONTAINER" ]]; then
    docker rm -f "$REDIS_CONTAINER" >/dev/null 2>&1 || true
  fi
}
trap cleanup EXIT

maybe_start_redis() {
  if uv run python "$ROOT_DIR/scripts/check_worker_runtime.py" --redis-only >/dev/null 2>&1; then
    return
  fi
  if [[ "${SC_PLATFORM_MANAGE_REDIS:-0}" != "1" ]]; then
    echo "[runtime-verify] Redis is not reachable and SC_PLATFORM_MANAGE_REDIS=1 was not set"
    exit 1
  fi
  REDIS_CONTAINER="codex-worker-runtime-hardening-redis-$RANDOM"
  export SC_RQ_REDIS_URL="redis://127.0.0.1:${REDIS_PORT}/0"
  docker run -d --rm --name "$REDIS_CONTAINER" -p "127.0.0.1:${REDIS_PORT}:6379" redis:7-alpine >/dev/null
  for _ in $(seq 1 30); do
    if uv run python "$ROOT_DIR/scripts/check_worker_runtime.py" --redis-only >/dev/null 2>&1; then
      echo "[runtime-verify] started disposable Redis container $REDIS_CONTAINER"
      return
    fi
    sleep 1
  done
  echo "[runtime-verify] Redis container did not become reachable"
  exit 1
}

json_eval() {
  local expression="$1"
  python3 -c "import json,sys; data=json.load(sys.stdin); print($expression)"
}

submit_task() {
  local payload="$1"
  curl --fail --silent \
    -H 'content-type: application/json' \
    -d "$payload" \
    "$APP_URL/tasks"
}

wait_for_task() {
  local task_id="$1"
  local expected_lane="$2"
  local observed_health_checks=0
  local observed_lane_match=0

  for _ in $(seq 1 90); do
    local detail
    detail="$(curl --fail --silent "$APP_URL/tasks/$task_id")"
    local status
    status="$(printf '%s' "$detail" | json_eval "data['data']['status']")"
    local lane
    lane="$(printf '%s' "$detail" | json_eval "data['data']['lane']")"
    if [[ "$lane" == "$expected_lane" ]]; then
      local processors
      processors="$(curl --fail --silent "$APP_URL/tasks/runtime/processors")"
      local lane_match
      lane_match="$(printf '%s' "$processors" | json_eval "any(p['lane'] == '$expected_lane' and p['current_task_id'] == $task_id for p in data['data']['processors'])")"
      if [[ "$lane_match" == "True" ]]; then
        observed_lane_match=1
      fi
    fi
    if [[ "$status" == "queued" || "$status" == "dispatching" || "$status" == "running" ]]; then
      curl --fail --silent "$APP_URL/health" >/dev/null
      observed_health_checks=$((observed_health_checks + 1))
      sleep 1
      continue
    fi
    if [[ "$status" == "completed" ]]; then
      if [[ "$observed_health_checks" -eq 0 ]]; then
        echo "[runtime-verify] task $task_id completed before app responsiveness could be observed"
      fi
      if [[ "$observed_lane_match" -eq 0 ]]; then
        echo "[runtime-verify] did not observe task $task_id attached to lane $expected_lane in processor view"
      fi
      echo "$observed_health_checks:$observed_lane_match"
      return
    fi
    echo "[runtime-verify] task $task_id ended in unexpected status: $status"
    exit 1
  done

  echo "[runtime-verify] task $task_id timed out"
  exit 1
}

maybe_start_redis
platform_require_path "$ROOT_DIR/.venv" "uv sync" "runtime-verify"
platform_require_free_port "$APP_PORT" app "runtime-verify"
platform_start_service "$PID_DIR" "$LOG_DIR" app bash -lc "cd '$ROOT_DIR' && exec uv run sc-app"
platform_start_service "$PID_DIR" "$LOG_DIR" worker-simulation bash -lc "cd '$ROOT_DIR' && exec uv run sc-worker-simulation"
platform_start_service "$PID_DIR" "$LOG_DIR" worker-characterization bash -lc "cd '$ROOT_DIR' && exec uv run sc-worker-characterization"

platform_wait_for_url "app" "$APP_URL/health" "$LOG_DIR/app.log" "$PID_DIR/app.pid"
platform_wait_for_runtime_health "$ROOT_DIR" "$APP_URL"

APP_PID="$(cat "$PID_DIR/app.pid")"
SIM_PID="$(cat "$PID_DIR/worker-simulation.pid")"
CHAR_PID="$(cat "$PID_DIR/worker-characterization.pid")"
if [[ "$APP_PID" == "$SIM_PID" || "$APP_PID" == "$CHAR_PID" || "$SIM_PID" == "$CHAR_PID" ]]; then
  echo "[runtime-verify] process separation failed"
  exit 1
fi

SIM_RESPONSE="$(submit_task '{
  "kind": "simulation",
  "dataset_id": "local-dataset-001",
  "definition_id": "'"$LOCAL_SIMULATION_DEFINITION_ID"'",
  "summary": "Runtime verification simulation",
  "simulation_setup": {
    "frequency_sweep": {"start_ghz": 4.0, "stop_ghz": 8.0, "point_count": 1601, "spacing": "linear"},
    "parameter_sweeps": [],
    "solver": {
      "solver_family": "hfss-hb",
      "max_iterations": 60,
      "convergence_tolerance": 1e-6,
      "harmonic_balance": {"enabled": true, "harmonic_count": 9, "oversample_factor": 3}
    },
    "sources": [{
      "source_id": "drive-port-a",
      "kind": "port_drive",
      "target": "port_1",
      "amplitude": -35.0,
      "frequency_ghz": 6.45,
      "phase_deg": 0.0
    }],
    "ptc": {"enabled": true, "mode": "auto", "compensate_ports": ["port_1", "port_2"]}
  }
}')"
SIM_TASK_ID="$(printf '%s' "$SIM_RESPONSE" | json_eval "data['data']['task']['task_id']")"
SIM_OBSERVATION="$(wait_for_task "$SIM_TASK_ID" "simulation")"

POST_RESPONSE="$(submit_task "{
  \"kind\": \"post_processing\",
  \"dataset_id\": \"local-dataset-001\",
  \"summary\": \"Runtime verification post processing\",
  \"upstream_task_id\": $SIM_TASK_ID,
  \"post_processing_setup\": {
    \"selections\": [{
      \"trace_family\": \"s_matrix\",
      \"representation\": \"db\",
      \"design_id\": \"design-alpha\",
      \"trace_ids\": [\"trace-s11-raw\"]
    }],
    \"operations\": []
  }
}")"
POST_TASK_ID="$(printf '%s' "$POST_RESPONSE" | json_eval "data['data']['task']['task_id']")"
POST_OBSERVATION="$(wait_for_task "$POST_TASK_ID" "simulation")"

CHAR_RESPONSE="$(submit_task '{
  "kind": "characterization",
  "characterization_setup": {
    "design_id": "design_local_flux_playground",
    "analysis_id": "admittance_extraction",
    "selected_trace_ids": ["trace_local_flux_measurement", "trace_local_flux_preview"],
    "analysis_config": {"fit_window": [4.85, 5.25], "residual_tolerance": 0.015}
  }
}')"
CHAR_TASK_ID="$(printf '%s' "$CHAR_RESPONSE" | json_eval "data['data']['task']['task_id']")"
CHAR_OBSERVATION="$(wait_for_task "$CHAR_TASK_ID" "characterization")"

PROCESSORS_JSON="$(curl --fail --silent "$APP_URL/tasks/runtime/processors")"
WORKER_LANES="$(printf '%s' "$PROCESSORS_JSON" | json_eval "','.join(sorted(summary['lane'] for summary in data['data']['worker_summary']))")"
if [[ "$WORKER_LANES" != "characterization,simulation" ]]; then
  echo "[runtime-verify] worker summary lanes were unexpected: $WORKER_LANES"
  exit 1
fi

SIM_HEALTH_CHECKS="${SIM_OBSERVATION%%:*}"
SIM_LANE_MATCH="${SIM_OBSERVATION##*:}"
POST_HEALTH_CHECKS="${POST_OBSERVATION%%:*}"
POST_LANE_MATCH="${POST_OBSERVATION##*:}"
CHAR_HEALTH_CHECKS="${CHAR_OBSERVATION%%:*}"
CHAR_LANE_MATCH="${CHAR_OBSERVATION##*:}"

if [[ $((SIM_HEALTH_CHECKS + POST_HEALTH_CHECKS + CHAR_HEALTH_CHECKS)) -le 0 ]]; then
  echo "[runtime-verify] app responsiveness under worker load was not observed"
  exit 1
fi
if [[ "$SIM_LANE_MATCH" != "1" || "$CHAR_LANE_MATCH" != "1" ]]; then
  echo "[runtime-verify] failed to observe simulation/characterization work on the expected lane"
  exit 1
fi
if [[ "$POST_LANE_MATCH" != "1" ]]; then
  echo "[runtime-verify] post-processing completed before lane attachment was observed; task detail lane remained simulation"
fi
POST_LANE="$(curl --fail --silent "$APP_URL/tasks/$POST_TASK_ID" | json_eval "data['data']['lane']")"
if [[ "$POST_LANE" != "simulation" ]]; then
  echo "[runtime-verify] post-processing task did not preserve the simulation lane"
  exit 1
fi

echo "[runtime-verify] redis-backed runtime verified"
echo "[runtime-verify] app pid: $APP_PID"
echo "[runtime-verify] simulation worker pid: $SIM_PID"
echo "[runtime-verify] characterization worker pid: $CHAR_PID"
echo "[runtime-verify] health checks during active work: $((SIM_HEALTH_CHECKS + POST_HEALTH_CHECKS + CHAR_HEALTH_CHECKS))"
