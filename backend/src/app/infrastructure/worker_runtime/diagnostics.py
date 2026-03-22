from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from rq import Worker

from src.app.domain.tasks import TaskLane
from src.app.infrastructure.worker_runtime.settings import WorkerRuntimeSettings


@dataclass(frozen=True)
class QueueBackendDiagnostic:
    redis_url: str
    reachable: bool
    error_code: str | None = None
    detail: str | None = None


@dataclass(frozen=True)
class WorkerLaneDiagnostic:
    lane: TaskLane
    queue_name: str
    worker_names: tuple[str, ...]

    @property
    def worker_count(self) -> int:
        return len(self.worker_names)


@dataclass(frozen=True)
class WorkerRuntimeDiagnostic:
    queue_backend: QueueBackendDiagnostic
    lanes: tuple[WorkerLaneDiagnostic, ...]
    unexpected_workers: tuple[str, ...] = ()

    @property
    def worker_count(self) -> int:
        return sum(lane.worker_count for lane in self.lanes)

    @property
    def missing_lanes(self) -> tuple[TaskLane, ...]:
        return tuple(lane.lane for lane in self.lanes if lane.worker_count == 0)


def probe_worker_runtime(
    settings: WorkerRuntimeSettings,
    connection_factory: Any,
) -> WorkerRuntimeDiagnostic:
    try:
        connection = connection_factory()
        connection.ping()
    except Exception as exc:  # pragma: no cover - covered through unit tests
        return WorkerRuntimeDiagnostic(
            queue_backend=QueueBackendDiagnostic(
                redis_url=settings.redis_url,
                reachable=False,
                error_code=_queue_error_code(exc),
                detail=str(exc),
            ),
            lanes=_empty_lane_diagnostics(settings),
        )

    lane_workers: dict[TaskLane, list[str]] = {
        "simulation": [],
        "characterization": [],
    }
    unexpected_workers: list[str] = []
    for worker in Worker.all(connection=connection):
        lane = _resolve_worker_lane(worker, settings)
        if lane is None:
            unexpected_workers.append(worker.name)
            continue
        lane_workers[lane].append(worker.name)

    return WorkerRuntimeDiagnostic(
        queue_backend=QueueBackendDiagnostic(
            redis_url=settings.redis_url,
            reachable=True,
        ),
        lanes=(
            WorkerLaneDiagnostic(
                lane="simulation",
                queue_name=settings.simulation_queue_name,
                worker_names=tuple(sorted(lane_workers["simulation"])),
            ),
            WorkerLaneDiagnostic(
                lane="characterization",
                queue_name=settings.characterization_queue_name,
                worker_names=tuple(sorted(lane_workers["characterization"])),
            ),
        ),
        unexpected_workers=tuple(sorted(unexpected_workers)),
    )


def _empty_lane_diagnostics(
    settings: WorkerRuntimeSettings,
) -> tuple[WorkerLaneDiagnostic, ...]:
    return (
        WorkerLaneDiagnostic(
            lane="simulation",
            queue_name=settings.simulation_queue_name,
            worker_names=(),
        ),
        WorkerLaneDiagnostic(
            lane="characterization",
            queue_name=settings.characterization_queue_name,
            worker_names=(),
        ),
    )


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


def _queue_error_code(exc: Exception) -> str:
    error_name = exc.__class__.__name__.lower()
    if "connection" in error_name or "timeout" in error_name:
        return "queue_connection_failed"
    return "queue_runtime_unavailable"
