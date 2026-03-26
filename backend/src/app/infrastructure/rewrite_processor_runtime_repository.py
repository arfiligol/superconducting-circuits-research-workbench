from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any, Protocol

from rq import Worker
from rq.job import Job
from sc_core.tasking import (
    LaneName,
    ProcessorHeartbeat,
    build_processor_heartbeat,
)

from src.app.domain.tasks import TaskDetail, TaskLane, WorkerLaneSummary
from src.app.infrastructure.worker_runtime.settings import WorkerRuntimeSettings

_ACTIVE_TASK_STATUSES = frozenset(
    {
        "queued",
        "dispatching",
        "running",
        "cancellation_requested",
        "cancelling",
        "termination_requested",
    }
)


class TaskListingRepository(Protocol):
    def list_tasks(self) -> Sequence[TaskDetail]: ...

    def get_task(self, task_id: int) -> TaskDetail | None: ...


class RedisProcessorRuntimeRepository:
    def __init__(
        self,
        *,
        task_repository: TaskListingRepository,
        settings: WorkerRuntimeSettings,
        connection_factory: Any,
    ) -> None:
        self._task_repository = task_repository
        self._settings = settings
        self._connection_factory = connection_factory

    def list_lane_summaries(self, workspace_id: str) -> tuple[WorkerLaneSummary, ...]:
        heartbeats = self.list_heartbeats(workspace_id)
        active_lanes = self._list_active_lanes(workspace_id)
        lanes = tuple(sorted({heartbeat.lane for heartbeat in heartbeats} | active_lanes))
        if len(lanes) == 0:
            return ()
        summary_counts: dict[TaskLane, dict[str, int]] = {
            lane: {
                "idle": 0,
                "running": 0,
                "degraded": 0,
                "draining": 0,
                "offline": 0,
            }
            for lane in lanes
        }
        # RQ worker registration proves the processor key is still present in Redis.
        # SimpleWorker can stay heartbeat-quiet while idle, so live summaries count
        # registered workers by their declared state instead of heartbeat age alone.
        for heartbeat in heartbeats:
            summary_counts[heartbeat.lane][heartbeat.state] += 1
        for lane in active_lanes:
            if _has_live_lane_presence(summary_counts[lane]):
                continue
            summary_counts[lane]["offline"] = 1
        return tuple(
            WorkerLaneSummary(
                lane=lane,
                idle_processors=summary_counts[lane]["idle"],
                running_processors=summary_counts[lane]["running"],
                degraded_processors=summary_counts[lane]["degraded"],
                draining_processors=summary_counts[lane]["draining"],
                offline_processors=summary_counts[lane]["offline"],
            )
            for lane in lanes
        )

    def list_heartbeats(self, workspace_id: str | None = None) -> tuple[ProcessorHeartbeat, ...]:
        workers = Worker.all(connection=self._connection_factory())
        heartbeats: list[ProcessorHeartbeat] = []
        for worker in workers:
            heartbeat = self._build_worker_heartbeat(worker, workspace_id=workspace_id)
            if heartbeat is None:
                continue
            heartbeats.append(heartbeat)
        return tuple(sorted(heartbeats, key=lambda item: (item.lane, item.processor_id)))

    def active_task_ids(self) -> set[int]:
        return {
            heartbeat.current_task_id
            for heartbeat in self.list_heartbeats()
            if heartbeat.current_task_id is not None
        }

    def mark_task_running(
        self,
        task: TaskDetail,
        *,
        recorded_at: datetime,
        worker_pid: int | None = None,
        stale_after_seconds: int | None = None,
    ) -> None:
        return None

    def acknowledge_cancellation(
        self,
        task: TaskDetail,
        *,
        recorded_at: datetime,
        worker_pid: int | None = None,
    ) -> None:
        return None

    def acknowledge_termination(
        self,
        task: TaskDetail,
        *,
        recorded_at: datetime,
        worker_pid: int | None = None,
    ) -> None:
        return None

    def mark_task_terminal(
        self,
        task: TaskDetail,
        *,
        recorded_at: datetime,
        terminal_status: str,
    ) -> None:
        return None

    def _build_worker_heartbeat(
        self,
        worker: Worker,
        *,
        workspace_id: str | None,
    ) -> ProcessorHeartbeat | None:
        lane = _resolve_worker_lane(worker, self._settings)
        if lane is None:
            return None
        current_job = _resolve_current_job(worker)
        task = self._resolve_task(current_job)
        if workspace_id is not None:
            if task is not None and task.workspace_id != workspace_id:
                return None
            if task is None and workspace_id != "local-space":
                return None
        return build_processor_heartbeat(
            processor_id=worker.name,
            lane=lane,
            state=_resolve_worker_state(task),
            current_task_id=task.task_id if task is not None else _resolve_task_id(current_job),
            last_heartbeat_at=_resolve_last_heartbeat(worker),
            runtime_metadata=_build_runtime_metadata(worker, lane, task),
        )

    def _resolve_task(self, job: Job | None) -> TaskDetail | None:
        task_id = _resolve_task_id(job)
        if task_id is None:
            return None
        return self._task_repository.get_task(task_id)

    def _list_active_lanes(self, workspace_id: str) -> set[TaskLane]:
        return {
            task.lane
            for task in self._task_repository.list_tasks()
            if task.workspace_id == workspace_id and task.status in _ACTIVE_TASK_STATUSES
        }


def _resolve_worker_lane(
    worker: Worker,
    settings: WorkerRuntimeSettings,
) -> TaskLane | None:
    queue_names = {queue.name for queue in worker.queues}
    if settings.simulation_queue_name in queue_names:
        return "simulation"
    if settings.characterization_queue_name in queue_names:
        return "characterization"
    return None


def _resolve_current_job(worker: Worker) -> Job | None:
    current_job = getattr(worker, "get_current_job", None)
    if callable(current_job):
        return current_job()
    job = getattr(worker, "current_job", None)
    return job if isinstance(job, Job) else None


def _resolve_task_id(job: Job | None) -> int | None:
    if job is None:
        return None
    task_id = job.meta.get("task_id")
    if isinstance(task_id, int):
        return task_id
    if len(job.args) > 0 and isinstance(job.args[0], int):
        return job.args[0]
    return None


def _resolve_last_heartbeat(worker: Worker) -> datetime:
    last_heartbeat = getattr(worker, "last_heartbeat", None)
    if isinstance(last_heartbeat, datetime):
        return last_heartbeat.astimezone(UTC)
    return datetime.now(UTC)


def _resolve_worker_state(task: TaskDetail | None) -> str:
    if task is None:
        return "idle"
    if task.status in {"cancellation_requested", "cancelling"}:
        return "draining"
    if task.status == "termination_requested":
        return "degraded"
    return "running"


def _build_runtime_metadata(
    worker: Worker,
    lane: LaneName,
    task: TaskDetail | None,
) -> dict[str, object]:
    queue_names = [queue.name for queue in worker.queues]
    worker_pid = _parse_worker_pid(worker.name)
    metadata: dict[str, object] = {
        "authority": "rq_redis",
        "execution_mode": "worker_process",
        "queue_names": queue_names,
        "lane": lane,
    }
    if worker_pid is not None:
        metadata["worker_pid"] = worker_pid
    if task is not None:
        metadata["worker_task_name"] = task.worker_task_name
    return metadata


def _parse_worker_pid(worker_name: str) -> int | None:
    _, _, suffix = worker_name.rpartition(":")
    if not suffix.isdigit():
        return None
    return int(suffix)


def _has_live_lane_presence(summary_counts: dict[str, int]) -> bool:
    return any(
        summary_counts[state] > 0
        for state in ("idle", "running", "degraded", "draining")
    )
