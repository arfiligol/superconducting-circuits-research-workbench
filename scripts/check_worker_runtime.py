#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict

import httpx
from src.app.infrastructure.runtime import (
    get_queue_connection_factory,
    get_worker_runtime_settings,
    reset_runtime_state,
)
from src.app.infrastructure.worker_runtime.diagnostics import probe_worker_runtime


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--app-url", default="http://127.0.0.1:8000")
    parser.add_argument("--redis-only", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    reset_runtime_state()
    settings = get_worker_runtime_settings()
    runtime = probe_worker_runtime(settings, get_queue_connection_factory())

    app_status = _probe_app(args.app_url) if not args.redis_only else {"reachable": None}
    processors_status = (
        _probe_runtime_processors(args.app_url)
        if not args.redis_only and app_status["reachable"]
        else {"reachable": None}
    )
    payload = {
        "redis": asdict(runtime.queue_backend),
        "workers": {
            lane.lane: {
                "queue_name": lane.queue_name,
                "worker_count": lane.worker_count,
                "worker_names": list(lane.worker_names),
            }
            for lane in runtime.lanes
        },
        "unexpected_workers": list(runtime.unexpected_workers),
        "app": app_status,
        "runtime_processors": processors_status,
    }
    payload["state"] = _resolve_state(runtime, app_status, processors_status)

    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        _print_human_summary(payload)

    if args.redis_only:
        return 0 if runtime.queue_backend.reachable else 1
    return 0 if payload["state"] == "healthy" else 1


def _probe_app(app_url: str) -> dict[str, object]:
    try:
        response = httpx.get(f"{app_url}/health", timeout=2.0)
        response.raise_for_status()
    except Exception as exc:
        return {
            "reachable": False,
            "error": str(exc),
        }
    payload = response.json()
    return {
        "reachable": True,
        "status": payload.get("status"),
        "service": payload.get("service"),
    }


def _probe_runtime_processors(app_url: str) -> dict[str, object]:
    try:
        response = httpx.get(f"{app_url}/tasks/runtime/processors", timeout=2.0)
        response.raise_for_status()
        payload = response.json()["data"]
    except Exception as exc:
        return {
            "reachable": False,
            "error": str(exc),
        }
    return {
        "reachable": True,
        "processor_count": len(payload.get("processors", [])),
        "worker_summary_lanes": sorted(
            summary["lane"] for summary in payload.get("worker_summary", [])
        ),
    }


def _resolve_state(
    runtime,
    app_status: dict[str, object],
    processors_status: dict[str, object],
) -> str:
    if not runtime.queue_backend.reachable:
        return "missing_redis"
    app_reachable = bool(app_status.get("reachable"))
    has_workers = runtime.worker_count > 0
    missing_lanes = set(runtime.missing_lanes)
    worker_summary_lanes = set(processors_status.get("worker_summary_lanes", []))

    if app_reachable and not has_workers:
        return "app_only"
    if has_workers and not app_reachable:
        return "workers_only"
    if not app_reachable:
        return "partial"
    if missing_lanes:
        return "missing_workers"
    if worker_summary_lanes != {"simulation", "characterization"}:
        return "runtime_summary_mismatch"
    return "healthy"


def _print_human_summary(payload: dict[str, object]) -> None:
    redis_status = payload["redis"]
    app_status = payload["app"]
    workers = payload["workers"]
    processors = payload["runtime_processors"]

    if redis_status["reachable"]:
        print(f"[platform-check] redis: ok ({redis_status['redis_url']})")
    else:
        print(
            "[platform-check] redis: unavailable "
            f"({redis_status['error_code']}: {redis_status['detail']})"
        )

    if app_status.get("reachable") is True:
        print(f"[platform-check] app: ok ({app_status.get('service')})")
    elif app_status.get("reachable") is False:
        print(f"[platform-check] app: unavailable ({app_status.get('error')})")

    for lane in ("simulation", "characterization"):
        lane_status = workers[lane]
        print(
            f"[platform-check] {lane} workers: "
            f"{lane_status['worker_count']} ({', '.join(lane_status['worker_names']) or 'none'})"
        )

    unexpected_workers = payload["unexpected_workers"]
    if unexpected_workers:
        print(
            "[platform-check] unexpected workers: "
            + ", ".join(unexpected_workers)
        )

    if processors.get("reachable") is True:
        print(
            "[platform-check] runtime processor lanes: "
            + ", ".join(processors["worker_summary_lanes"])
        )
    elif processors.get("reachable") is False:
        print(
            f"[platform-check] runtime processors: unavailable ({processors.get('error')})"
        )

    print(f"[platform-check] state: {payload['state']}")


if __name__ == "__main__":
    sys.exit(main())
