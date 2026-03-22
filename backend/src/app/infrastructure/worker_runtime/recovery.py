from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Protocol, cast

from src.app.domain.tasks import (
    TaskDetail,
    TaskDispatchReceipt,
    TaskEvent,
    TaskEventType,
    TaskLane,
)


class RecoveryTaskRepository(Protocol):
    def list_tasks(self) -> tuple[TaskDetail, ...]: ...

    def merge_task_event_metadata(
        self,
        task_id: int,
        event_key: str,
        metadata: dict[str, object],
    ) -> None: ...

    def append_task_event(
        self,
        task_id: int,
        event: TaskEvent,
    ) -> None: ...


class RecoveryExecutionRuntime(Protocol):
    def reconcile_stale_task(
        self,
        task_id: int,
        *,
        recorded_at: datetime,
        stale_before: datetime,
    ) -> TaskDetail: ...


class RecoveryProcessorRepository(Protocol):
    def active_task_ids(self) -> set[int]: ...


class RecoveryQueueDispatcher(Protocol):
    def enqueue_submitted_task(self, task: TaskDetail) -> TaskDispatchReceipt: ...

    def get_job_status(self, dispatch_key: str) -> str | None: ...


@dataclass(frozen=True)
class ExecutionRecoveryContext:
    lane: TaskLane
    stale_after_seconds: int


class LocalExecutionRecoveryService:
    def __init__(
        self,
        *,
        task_repository: RecoveryTaskRepository,
        execution_runtime: RecoveryExecutionRuntime,
        processor_repository: RecoveryProcessorRepository,
        queue_dispatcher: RecoveryQueueDispatcher,
    ) -> None:
        self._task_repository = task_repository
        self._execution_runtime = execution_runtime
        self._processor_repository = processor_repository
        self._queue_dispatcher = queue_dispatcher

    def recover_lane(self, lane: TaskLane, *, stale_after_seconds: int = 300) -> None:
        context = ExecutionRecoveryContext(
            lane=lane,
            stale_after_seconds=stale_after_seconds,
        )
        active_task_ids = self._processor_repository.active_task_ids()
        recorded_at = datetime.now(UTC)
        stale_before = recorded_at - timedelta(seconds=context.stale_after_seconds)

        for task in self._candidate_tasks(context.lane):
            if task.status in {"queued", "dispatching"}:
                self._recover_queued_task(task)
                continue
            if task.task_id in active_task_ids:
                continue
            if _parse_timestamp(task.progress.updated_at) > stale_before:
                continue
            self._execution_runtime.reconcile_stale_task(
                task.task_id,
                recorded_at=recorded_at,
                stale_before=stale_before,
            )

    def _candidate_tasks(self, lane: TaskLane) -> tuple[TaskDetail, ...]:
        return tuple(
            task
            for task in self._task_repository.list_tasks()
            if task.visibility_scope == "local"
            and task.lane == lane
            and task.status
            in {
                "queued",
                "dispatching",
                "running",
                "cancellation_requested",
                "cancelling",
                "termination_requested",
            }
        )

    def _recover_queued_task(self, task: TaskDetail) -> None:
        if task.dispatch is None:
            return
        job_status = self._queue_dispatcher.get_job_status(task.dispatch.dispatch_key)
        if job_status in {"queued", "started", "deferred", "scheduled"}:
            return
        receipt = self._queue_dispatcher.enqueue_submitted_task(task)
        self._persist_dispatch_metadata(task, receipt)
        self._task_repository.append_task_event(
            task.task_id,
            _build_requeue_event(task, receipt),
        )

    def _persist_dispatch_metadata(
        self,
        task: TaskDetail,
        receipt: TaskDispatchReceipt,
    ) -> None:
        if len(task.events) == 0:
            return
        self._task_repository.merge_task_event_metadata(
            task.task_id,
            task.events[0].event_key,
            {
                "queue_name": receipt.queue_name,
                "enqueued_at": receipt.enqueued_at,
                "runtime_job_id": receipt.runtime_job_id,
                "dispatch_attempt_count": receipt.dispatch_attempt_count,
                "last_dispatch_outcome": receipt.last_dispatch_outcome,
                "last_dispatch_error_code": receipt.last_dispatch_error_code,
            },
        )


def _parse_timestamp(value: str) -> datetime:
    return datetime.fromisoformat(value).astimezone(UTC)


def _build_requeue_event(
    task: TaskDetail,
    receipt: TaskDispatchReceipt,
) -> TaskEvent:
    occurred_at = receipt.enqueued_at or datetime.now(UTC).isoformat()
    return TaskEvent(
        event_key=f"task_requeued:{occurred_at}",
        event_type=cast(TaskEventType, "task_requeued"),
        level="warning",
        occurred_at=occurred_at,
        message="The runtime requeued the task after the worker job went missing.",
        metadata={
            "task_status": task.status,
            "dispatch_status": task.dispatch.status if task.dispatch is not None else None,
            "dispatch_key": task.dispatch.dispatch_key if task.dispatch is not None else None,
            "worker_task_name": task.worker_task_name,
            "queue_name": receipt.queue_name,
            "runtime_job_id": receipt.runtime_job_id,
            "dispatch_attempt_count": receipt.dispatch_attempt_count,
            "last_dispatch_outcome": receipt.last_dispatch_outcome,
            "last_dispatch_error_code": receipt.last_dispatch_error_code,
            "reconcile_required": True,
            "reconcile_reason": "queue_job_missing",
            "audit_action": "reconcile.task_requeued",
        },
    )
