from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import pytest
from rq import Worker
from src.app.domain.tasks import WorkerLaneSummary
from src.app.infrastructure.rewrite_processor_runtime_repository import (
    RedisProcessorRuntimeRepository,
)
from src.app.infrastructure.worker_runtime.settings import WorkerRuntimeSettings


@dataclass(frozen=True)
class _FakeTask:
    task_id: int
    status: str
    workspace_id: str
    lane: str
    worker_task_name: str


class _FakeTaskRepository:
    def __init__(self, tasks: tuple[_FakeTask, ...]) -> None:
        self._tasks = {task.task_id: task for task in tasks}

    def list_tasks(self) -> tuple[_FakeTask, ...]:
        return tuple(self._tasks.values())

    def get_task(self, task_id: int) -> _FakeTask | None:
        return self._tasks.get(task_id)


@dataclass(frozen=True)
class _FakeQueue:
    name: str


@dataclass(frozen=True)
class _FakeJob:
    meta: dict[str, object]
    args: tuple[object, ...] = ()


class _FakeWorker:
    def __init__(
        self,
        *,
        name: str,
        lane_queue_name: str,
        last_heartbeat: datetime,
        current_job: _FakeJob | None = None,
    ) -> None:
        self.name = name
        self.queues = [_FakeQueue(lane_queue_name)]
        self.last_heartbeat = last_heartbeat
        self._current_job = current_job

    def get_current_job(self) -> _FakeJob | None:
        return self._current_job


def _build_repository(
    monkeypatch: pytest.MonkeyPatch,
    *,
    tasks: tuple[_FakeTask, ...] = (),
    workers: tuple[_FakeWorker, ...] = (),
) -> RedisProcessorRuntimeRepository:
    monkeypatch.setattr(Worker, "all", classmethod(lambda cls, connection: list(workers)))
    return RedisProcessorRuntimeRepository(
        task_repository=_FakeTaskRepository(tasks),
        settings=WorkerRuntimeSettings(
            redis_url="fakeredis://processor-runtime-repository",
            simulation_queue_name="simulation",
            characterization_queue_name="characterization",
            job_timeout_seconds=600,
            failure_ttl_seconds=3600,
            result_ttl_seconds=3600,
            stale_after_seconds=300,
            reconcile_after_seconds=180,
            app_host="127.0.0.1",
            app_port=8000,
            app_reload=False,
        ),
        connection_factory=lambda: object(),
    )


def test_stale_idle_worker_presence_stays_idle_in_runtime_summary(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    recorded_at = datetime(2026, 3, 27, 12, 0, tzinfo=UTC)
    repository = _build_repository(
        monkeypatch,
        workers=(
            _FakeWorker(
                name="sc-worker-simulation:5001",
                lane_queue_name="simulation",
                last_heartbeat=recorded_at - timedelta(minutes=15),
            ),
        ),
    )

    heartbeats = repository.list_heartbeats("local-space")
    summaries = repository.list_lane_summaries("local-space")

    assert len(heartbeats) == 1
    assert heartbeats[0].state == "idle"
    assert heartbeats[0].current_task_id is None
    assert summaries == (
        WorkerLaneSummary(
            lane="simulation",
            idle_processors=1,
            running_processors=0,
            degraded_processors=0,
            draining_processors=0,
            offline_processors=0,
        ),
    )


def test_running_worker_presence_stays_running_in_runtime_summary(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    task = _FakeTask(
        task_id=42,
        status="running",
        workspace_id="local-space",
        lane="simulation",
        worker_task_name="simulation_run_task",
    )
    repository = _build_repository(
        monkeypatch,
        tasks=(task,),
        workers=(
            _FakeWorker(
                name="sc-worker-simulation:5002",
                lane_queue_name="simulation",
                last_heartbeat=datetime(2026, 3, 27, 12, 0, tzinfo=UTC),
                current_job=_FakeJob(meta={"task_id": 42}),
            ),
        ),
    )

    heartbeats = repository.list_heartbeats("local-space")
    summaries = repository.list_lane_summaries("local-space")

    assert heartbeats[0].state == "running"
    assert heartbeats[0].current_task_id == 42
    assert summaries[0].running_processors == 1
    assert summaries[0].offline_processors == 0


def test_active_lane_without_live_worker_surfaces_offline_summary(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = _build_repository(
        monkeypatch,
        tasks=(
            _FakeTask(
                task_id=77,
                status="queued",
                workspace_id="local-space",
                lane="simulation",
                worker_task_name="simulation_run_task",
            ),
        ),
    )

    assert repository.list_heartbeats("local-space") == ()
    assert repository.list_lane_summaries("local-space") == (
        WorkerLaneSummary(
            lane="simulation",
            idle_processors=0,
            running_processors=0,
            degraded_processors=0,
            draining_processors=0,
            offline_processors=1,
        ),
    )
