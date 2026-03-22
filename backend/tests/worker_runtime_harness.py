from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from rq import Queue, SimpleWorker, Worker
from src.app.domain.tasks import TaskLane
from src.app.infrastructure.runtime import (
    get_execution_recovery_service,
    get_queue_connection_factory,
    get_worker_runtime_settings,
)


def drain_lane_queue(lane: TaskLane) -> None:
    queue = queue_for_lane(lane)
    worker = SimpleWorker([queue], connection=queue.connection)
    worker.work(burst=True)


def queue_for_lane(lane: TaskLane) -> Queue:
    settings = get_worker_runtime_settings()
    return Queue(
        settings.queue_name_for_lane(lane),
        connection=get_queue_connection_factory()(),
    )


def queue_job_count(lane: TaskLane) -> int:
    return len(queue_for_lane(lane).jobs)


def clear_queue_jobs(lane: TaskLane) -> None:
    queue = queue_for_lane(lane)
    job_ids = list(queue.job_ids)
    connection = queue.connection
    connection.delete(queue.key)
    for job_id in job_ids:
        connection.delete(f"rq:job:{job_id}")


def recover_lane(lane: TaskLane, *, stale_after_seconds: int | None = None) -> None:
    service = get_execution_recovery_service()
    if stale_after_seconds is None:
        service.recover_lane(lane)
        return
    service.recover_lane(lane, stale_after_seconds=stale_after_seconds)


@contextmanager
def registered_worker(lane: TaskLane, *, name: str) -> Iterator[Worker]:
    queue = queue_for_lane(lane)
    worker = Worker([queue], connection=queue.connection, name=name)
    worker.register_birth()
    try:
        yield worker
    finally:
        worker.register_death()
