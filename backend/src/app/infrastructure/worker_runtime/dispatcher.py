from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from rq import Queue
from rq.job import Job, NoSuchJobError

from src.app.domain.tasks import (
    TaskDetail,
    TaskDispatchOutcome,
    TaskDispatchReceipt,
    TaskEnqueueError,
)
from src.app.infrastructure.worker_runtime.settings import WorkerRuntimeSettings

_ACTIVE_JOB_STATUSES = {"queued", "started", "deferred", "scheduled"}


@dataclass(frozen=True)
class QueueDispatchRequest:
    task_id: int
    dispatch_key: str
    task_kind: str
    queue_name: str
    job_timeout_seconds: int
    failure_ttl_seconds: int
    result_ttl_seconds: int


class LocalTaskQueueDispatcher:
    def __init__(
        self,
        *,
        settings: WorkerRuntimeSettings,
        connection_factory: Any,
    ) -> None:
        self._settings = settings
        self._connection_factory = connection_factory

    def enqueue_submitted_task(self, task: TaskDetail) -> TaskDispatchReceipt:
        request = self._build_dispatch_request(task)
        connection = self._connection_factory()
        existing_job = self.get_job(request.dispatch_key)
        if existing_job is not None:
            status = existing_job.get_status(refresh=False)
            if status in _ACTIVE_JOB_STATUSES:
                return _dispatch_receipt(task, request)
            existing_job.delete()

        queue = Queue(request.queue_name, connection=connection)
        try:
            queue.enqueue(
                _job_callable_for_lane(task.lane),
                request.task_id,
                job_id=_rq_job_id(request.dispatch_key),
                meta=_build_dispatch_metadata(request, task),
                job_timeout=request.job_timeout_seconds,
                failure_ttl=request.failure_ttl_seconds,
                result_ttl=request.result_ttl_seconds,
            )
        except Exception as exc:  # pragma: no cover - exercised via tests with fake dispatcher
            raise TaskEnqueueError(
                code=_dispatch_error_code(exc),
                message=str(exc),
                receipt=_dispatch_receipt(
                    task,
                    request,
                    outcome="failed",
                    error_code=_dispatch_error_code(exc),
                    enqueued_at=None,
                ),
            ) from exc
        return _dispatch_receipt(task, request)

    def get_job(self, dispatch_key: str) -> Job | None:
        try:
            return Job.fetch(_rq_job_id(dispatch_key), connection=self._connection_factory())
        except NoSuchJobError:
            return None

    def get_job_status(self, dispatch_key: str) -> str | None:
        job = self.get_job(dispatch_key)
        if job is None:
            return None
        return job.get_status(refresh=False)

    def _build_dispatch_request(self, task: TaskDetail) -> QueueDispatchRequest:
        dispatch_key = (
            task.dispatch.dispatch_key
            if task.dispatch is not None
            else f"dispatch:{task.task_id}:{task.worker_task_name}"
        )
        return QueueDispatchRequest(
            task_id=task.task_id,
            dispatch_key=dispatch_key,
            task_kind=task.kind,
            queue_name=self._settings.queue_name_for_task(task),
            job_timeout_seconds=self._settings.job_timeout_seconds,
            failure_ttl_seconds=self._settings.failure_ttl_seconds,
            result_ttl_seconds=self._settings.result_ttl_seconds,
        )


def _job_callable_for_lane(lane: str) -> str:
    if lane == "simulation":
        return "src.app.infrastructure.worker_runtime.jobs.execute_simulation_lane_task"
    return "src.app.infrastructure.worker_runtime.jobs.execute_characterization_lane_task"


def _rq_job_id(dispatch_key: str) -> str:
    return dispatch_key.replace(":", "__")


def _build_dispatch_metadata(
    request: QueueDispatchRequest,
    task: TaskDetail,
) -> dict[str, object]:
    return {
        "task_id": request.task_id,
        "task_kind": request.task_kind,
        "lane": task.lane,
        "queue_name": request.queue_name,
        "worker_task_name": task.worker_task_name,
        "execution_mode": task.execution_mode,
        "request_ready": task.request_ready,
    }


def _dispatch_receipt(
    task: TaskDetail,
    request: QueueDispatchRequest,
    *,
    outcome: TaskDispatchOutcome = "accepted",
    error_code: str | None = None,
    enqueued_at: str | None = None,
) -> TaskDispatchReceipt:
    current_attempt_count = _dispatch_attempt_count(task)
    return TaskDispatchReceipt(
        queue_name=request.queue_name,
        enqueued_at=enqueued_at or datetime.now(UTC).isoformat(),
        runtime_job_id=_rq_job_id(request.dispatch_key),
        dispatch_attempt_count=current_attempt_count + 1,
        last_dispatch_outcome=outcome,
        last_dispatch_error_code=error_code,
    )


def _dispatch_error_code(exc: Exception) -> str:
    error_name = exc.__class__.__name__.lower()
    if "connection" in error_name or "timeout" in error_name:
        return "queue_connection_failed"
    return "queue_enqueue_failed"


def _dispatch_attempt_count(task: TaskDetail) -> int:
    for event in task.events:
        count = event.metadata.get("dispatch_attempt_count")
        if isinstance(count, int) and count >= 0:
            return count
    return 0
