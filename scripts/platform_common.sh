#!/usr/bin/env bash
set -euo pipefail

platform_root_dir() {
  cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd
}

platform_app_host() {
  printf '%s\n' "${SC_APP_HOST:-127.0.0.1}"
}

platform_app_port() {
  printf '%s\n' "${SC_APP_PORT:-8000}"
}

platform_app_url() {
  printf 'http://%s:%s\n' "$(platform_app_host)" "$(platform_app_port)"
}

platform_load_env() {
  local root_dir="$1"
  if [[ -f "$root_dir/.env" ]]; then
    set -a
    # shellcheck disable=SC1090
    source "$root_dir/.env"
    set +a
  fi
}

platform_require_path() {
  local path="$1"
  local hint="$2"
  local prefix="${3:-platform}"

  if [[ -e "$path" ]]; then
    return
  fi

  echo "[$prefix] missing $path"
  echo "[$prefix] run $hint first"
  exit 1
}

platform_require_free_port() {
  local port="$1"
  local name="$2"
  local prefix="${3:-platform}"
  local listeners

  listeners="$(lsof -nP -iTCP:"$port" -sTCP:LISTEN 2>/dev/null || true)"
  if [[ -z "$listeners" ]]; then
    return
  fi

  echo "[$prefix] $name cannot start because port $port is already in use"
  echo "$listeners"
  exit 1
}

platform_start_service() {
  local pid_dir="$1"
  local log_dir="$2"
  local name="$3"
  shift 3

  local pid_file="$pid_dir/$name.pid"
  local log_file="$log_dir/$name.log"

  if [[ -f "$pid_file" ]]; then
    local existing_pid
    existing_pid="$(cat "$pid_file")"
    if kill -0 "$existing_pid" 2>/dev/null; then
      echo "[start] $name already running (pid=$existing_pid)"
      return
    fi
    rm -f "$pid_file"
  fi

  local pid
  pid="$(
    python3 - "$pid_file" "$log_file" "$@" <<'PY'
import os
import subprocess
import sys

pid_path, log_path, *command = sys.argv[1:]

with open(log_path, "ab", buffering=0) as log_file, open(os.devnull, "rb") as devnull:
    process = subprocess.Popen(
        command,
        stdin=devnull,
        stdout=log_file,
        stderr=log_file,
        start_new_session=True,
    )

with open(pid_path, "w", encoding="utf-8") as handle:
    handle.write(f"{process.pid}\n")

print(process.pid)
PY
  )"
  printf '%s\n' "$pid" >"$pid_file"
  echo "[start] started $name (pid=$pid, log=$log_file)"

  sleep 1
  if ! kill -0 "$pid" 2>/dev/null; then
    echo "[start] $name exited during startup"
    if [[ -f "$log_file" ]]; then
      tail -n 40 "$log_file"
    fi
    exit 1
  fi
}

platform_stop_service() {
  local pid_dir="$1"
  local name="$2"
  local prefix="${3:-stop}"
  local pid_file="$pid_dir/$name.pid"

  if [[ ! -f "$pid_file" ]]; then
    echo "[$prefix] $name not running"
    return
  fi

  local pid
  pid="$(cat "$pid_file")"
  if kill -0 "$pid" 2>/dev/null; then
    kill "$pid"
    wait "$pid" 2>/dev/null || true
    echo "[$prefix] stopped $name (pid=$pid)"
  else
    echo "[$prefix] $name pid file was stale (pid=$pid)"
  fi
  rm -f "$pid_file"
}

platform_wait_for_url() {
  local name="$1"
  local url="$2"
  local log_file="$3"
  local pid_file="${4:-}"

  for _ in $(seq 1 45); do
    if curl --fail --silent "$url" >/dev/null 2>&1; then
      echo "[start] $name ready at $url"
      return
    fi
    if [[ -n "$pid_file" && -f "$pid_file" ]]; then
      local pid
      pid="$(cat "$pid_file")"
      if ! kill -0 "$pid" 2>/dev/null; then
        echo "[start] $name exited before becoming ready: $url"
        if [[ -f "$log_file" ]]; then
          tail -n 40 "$log_file"
        fi
        exit 1
      fi
    fi
    sleep 1
  done

  echo "[start] $name did not become ready: $url"
  if [[ -f "$log_file" ]]; then
    tail -n 40 "$log_file"
  fi
  exit 1
}

platform_record_listen_pid() {
  local pid_dir="$1"
  local name="$2"
  local port="$3"
  local pid_file="$pid_dir/$name.pid"
  local listen_pid

  listen_pid="$(lsof -ti tcp:"$port" -sTCP:LISTEN | head -n 1)"
  if [[ -n "$listen_pid" ]]; then
    printf '%s\n' "$listen_pid" >"$pid_file"
    echo "[start] recorded $name listener pid=$listen_pid"
  fi
}

platform_check_redis() {
  local root_dir="$1"
  local prefix="${2:-start}"
  if uv run python "$root_dir/scripts/check_worker_runtime.py" --redis-only >/dev/null; then
    return
  fi

  echo "[$prefix] Redis is not reachable via SC_RQ_REDIS_URL / SC_REDIS_URL."
  echo "[$prefix] Start Redis first, then retry app bring-up."
  exit 1
}

platform_wait_for_runtime_health() {
  local root_dir="$1"
  local app_url="${2:-http://127.0.0.1:8000}"

  for _ in $(seq 1 45); do
    if uv run python "$root_dir/scripts/check_worker_runtime.py" --app-url "$app_url" >/dev/null; then
      echo "[start] runtime topology is healthy"
      return
    fi
    sleep 1
  done

  echo "[start] runtime topology did not become healthy"
  uv run python "$root_dir/scripts/check_worker_runtime.py" --app-url "$app_url" || true
  exit 1
}
