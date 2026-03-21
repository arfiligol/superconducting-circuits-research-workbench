from __future__ import annotations

from dataclasses import dataclass

from src.app.domain.tasks import TaskDetail, TaskLane
from src.app.settings import AppSettings


@dataclass(frozen=True)
class WorkerRuntimeSettings:
    redis_url: str
    simulation_queue_name: str
    characterization_queue_name: str
    job_timeout_seconds: int
    failure_ttl_seconds: int
    result_ttl_seconds: int
    stale_after_seconds: int
    reconcile_after_seconds: int
    app_host: str
    app_port: int
    app_reload: bool

    def queue_name_for_lane(self, lane: TaskLane) -> str:
        if lane == "simulation":
            return self.simulation_queue_name
        return self.characterization_queue_name

    def queue_name_for_task(self, task: TaskDetail) -> str:
        return self.queue_name_for_lane(task.lane)


def build_worker_runtime_settings(app_settings: AppSettings) -> WorkerRuntimeSettings:
    return WorkerRuntimeSettings(
        redis_url=_resolve_redis_url(app_settings),
        simulation_queue_name=app_settings.simulation_queue_name,
        characterization_queue_name=app_settings.characterization_queue_name,
        job_timeout_seconds=app_settings.rq_job_timeout_seconds,
        failure_ttl_seconds=app_settings.rq_failure_ttl_seconds,
        result_ttl_seconds=app_settings.rq_result_ttl_seconds,
        stale_after_seconds=_resolve_worker_stale_timeout_seconds(app_settings),
        reconcile_after_seconds=app_settings.rq_reconcile_after_seconds,
        app_host=app_settings.app_host,
        app_port=app_settings.app_port,
        app_reload=app_settings.app_reload,
    )


def _resolve_redis_url(app_settings: AppSettings) -> str:
    candidate = app_settings.rq_redis_url or app_settings.redis_url
    if candidate is not None and candidate.strip():
        return candidate.strip()
    return "redis://127.0.0.1:6379/0"


def _resolve_worker_stale_timeout_seconds(app_settings: AppSettings) -> int:
    if app_settings.worker_stale_timeout_seconds is not None:
        return app_settings.worker_stale_timeout_seconds
    if app_settings.rq_worker_stale_after_seconds is not None:
        return app_settings.rq_worker_stale_after_seconds
    return 300
