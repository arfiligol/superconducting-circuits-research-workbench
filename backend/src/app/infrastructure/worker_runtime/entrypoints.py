from __future__ import annotations

import os

import uvicorn
from rq import Queue, Worker

from src.app.infrastructure.runtime import get_execution_recovery_service
from src.app.infrastructure.worker_runtime.redis_connection import build_queue_connection
from src.app.infrastructure.worker_runtime.settings import build_worker_runtime_settings
from src.app.settings import get_settings


def run_uvicorn_app() -> None:
    settings = build_worker_runtime_settings(get_settings())
    uvicorn.run(
        "src.app.main:app",
        host=settings.app_host,
        port=settings.app_port,
        reload=settings.app_reload,
    )


def run_simulation_worker() -> None:
    _run_lane_worker("simulation")


def run_characterization_worker() -> None:
    _run_lane_worker("characterization")


def _run_lane_worker(lane: str) -> None:
    runtime_settings = build_worker_runtime_settings(get_settings())
    connection = build_queue_connection(runtime_settings.redis_url)
    queue_name = runtime_settings.queue_name_for_lane(lane)  # type: ignore[arg-type]
    get_execution_recovery_service().recover_lane(
        lane,  # type: ignore[arg-type]
        stale_after_seconds=runtime_settings.reconcile_after_seconds,
    )
    worker = Worker(
        [Queue(queue_name, connection=connection)],
        connection=connection,
        name=f"sc-worker-{lane}:{os.getpid()}",
    )
    worker.work(with_scheduler=False)
