from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from src.app.domain.tasks import TaskLane
from src.app.infrastructure.runtime import (
    get_characterization_execution_driver,
    get_execution_recovery_service,
    get_post_processing_execution_driver,
    get_simulation_execution_driver,
    get_task_execution_runtime,
    get_task_service,
)


@dataclass(frozen=True)
class WorkerJobContext:
    task_id: int
    lane: TaskLane


def execute_simulation_lane_task(task_id: int) -> None:
    _execute_lane_task(WorkerJobContext(task_id=task_id, lane="simulation"))


def execute_characterization_lane_task(task_id: int) -> None:
    _execute_lane_task(WorkerJobContext(task_id=task_id, lane="characterization"))


def _execute_lane_task(context: WorkerJobContext) -> None:
    recovery_service = get_execution_recovery_service()
    recovery_service.recover_lane(context.lane)

    task_service = get_task_service()
    task = task_service.get_task(context.task_id)
    if task.visibility_scope != "local" or task.status not in {"queued", "dispatching"}:
        return
    if task.lane != context.lane:
        return

    runtime = get_task_execution_runtime()
    claimed_at = datetime.now(UTC)
    runtime.dispatch_task(
        context.task_id,
        recorded_at=claimed_at,
        worker_pid=_worker_pid(),
    )

    if task.kind == "simulation":
        get_simulation_execution_driver().execute_submitted_task(context.task_id)
        return
    if task.kind == "post_processing":
        get_post_processing_execution_driver().execute_submitted_task(context.task_id)
        return
    if task.kind == "characterization":
        get_characterization_execution_driver().execute_submitted_task(context.task_id)


def reconcile_worker_lane(lane: TaskLane) -> None:
    get_execution_recovery_service().recover_lane(lane)


def _worker_pid() -> int:
    import os

    return os.getpid()
