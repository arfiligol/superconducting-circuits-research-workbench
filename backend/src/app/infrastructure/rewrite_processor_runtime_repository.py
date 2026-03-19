from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime
from typing import ClassVar, Protocol

from sc_core.tasking import (
    LaneName,
    ProcessorHeartbeat,
    ProcessorState,
    build_lane_processor_summaries,
    build_processor_heartbeat,
)

from src.app.domain.tasks import TaskDetail, TaskLane, TaskStatus, WorkerLaneSummary


class TaskListingRepository(Protocol):
    def list_tasks(self) -> Sequence[TaskDetail]: ...


class InMemoryProcessorRuntimeRepository:
    _BASELINE_PROCESSORS: ClassVar[dict[TaskLane, tuple[str, ...]]] = {
        "simulation": ("simulation-processor-1", "simulation-processor-2"),
        "characterization": ("characterization-processor-1",),
    }

    def __init__(self, task_repository: TaskListingRepository) -> None:
        self._task_repository = task_repository
        self._heartbeats: dict[str, ProcessorHeartbeat] = {}
        self._task_assignments: dict[int, str] = {}
        self._bootstrap_from_tasks()

    def list_lane_summaries(self, workspace_id: str) -> tuple[WorkerLaneSummary, ...]:
        raw_heartbeats = self.list_heartbeats(workspace_id)
        recorded_at = max(
            (heartbeat.last_heartbeat_at for heartbeat in raw_heartbeats),
            default=datetime.now(UTC),
        )
        heartbeats = tuple(
            _refresh_idle_heartbeat(heartbeat, recorded_at)
            for heartbeat in raw_heartbeats
        )
        summaries = build_lane_processor_summaries(
            heartbeats,
            recorded_at=recorded_at,
            offline_after_seconds=90,
        )
        ordered = tuple(
            WorkerLaneSummary(
                lane=summary.lane,
                healthy_processors=summary.healthy_processors,
                busy_processors=summary.busy_processors,
                degraded_processors=summary.degraded_processors,
                draining_processors=summary.draining_processors,
                offline_processors=summary.offline_processors,
            )
            for summary in summaries
        )
        return tuple(sorted(ordered, key=lambda summary: _lane_order(summary.lane)))

    def list_heartbeats(self, workspace_id: str | None = None) -> tuple[ProcessorHeartbeat, ...]:
        return tuple(
            sorted(
                (
                    heartbeat
                    for key, heartbeat in self._heartbeats.items()
                    if workspace_id is None or key.startswith(f"{workspace_id}:")
                ),
                key=lambda heartbeat: (heartbeat.lane, heartbeat.processor_id),
            )
        )

    def mark_task_running(
        self,
        task: TaskDetail,
        *,
        recorded_at: datetime,
        worker_pid: int | None = None,
        stale_after_seconds: int | None = None,
    ) -> None:
        recorded_at = _normalize_datetime(recorded_at)
        self._set_task_heartbeat(
            task=task,
            state="busy",
            recorded_at=recorded_at,
            runtime_metadata=_runtime_metadata(
                task=task,
                stale_after_seconds=stale_after_seconds,
                worker_pid=worker_pid,
                execution_phase="running",
            ),
        )

    def acknowledge_cancellation(
        self,
        task: TaskDetail,
        *,
        recorded_at: datetime,
        worker_pid: int | None = None,
    ) -> None:
        recorded_at = _normalize_datetime(recorded_at)
        self._set_task_heartbeat(
            task=task,
            state="draining",
            recorded_at=recorded_at,
            runtime_metadata=_runtime_metadata(
                task=task,
                worker_pid=worker_pid,
                execution_phase="cancelling",
            ),
        )

    def acknowledge_termination(
        self,
        task: TaskDetail,
        *,
        recorded_at: datetime,
        worker_pid: int | None = None,
    ) -> None:
        recorded_at = _normalize_datetime(recorded_at)
        self._set_task_heartbeat(
            task=task,
            state="degraded",
            recorded_at=recorded_at,
            runtime_metadata=_runtime_metadata(
                task=task,
                worker_pid=worker_pid,
                execution_phase="termination_requested",
            ),
        )

    def mark_task_terminal(
        self,
        task: TaskDetail,
        *,
        recorded_at: datetime,
        terminal_status: TaskStatus,
    ) -> None:
        recorded_at = _normalize_datetime(recorded_at)
        processor_id = self._task_assignments.pop(task.task_id, None)
        if processor_id is None:
            processor_id = self._first_processor_for_lane(task.workspace_id, task.lane)
        self._heartbeats[processor_id] = build_processor_heartbeat(
            processor_id=_display_processor_id(processor_id),
            lane=_normalize_lane(task.lane),
            state="healthy",
            current_task_id=None,
            last_heartbeat_at=recorded_at,
            runtime_metadata={
                "worker_task_name": task.worker_task_name,
                "task_status": terminal_status,
                "terminal_task_id": task.task_id,
            },
        )

    def _bootstrap_from_tasks(self) -> None:
        self._heartbeats.clear()
        self._task_assignments.clear()
        tasks = tuple(self._task_repository.list_tasks())
        recorded_at = max(
            (_parse_task_timestamp(task.progress.updated_at) for task in tasks),
            default=datetime.now(UTC),
        )
        workspace_ids = {task.workspace_id for task in tasks}

        for workspace_id in workspace_ids:
            for lane, processor_ids in self._BASELINE_PROCESSORS.items():
                for processor_id in processor_ids:
                    key = _processor_key(workspace_id, processor_id)
                    self._heartbeats[key] = build_processor_heartbeat(
                        processor_id=processor_id,
                        lane=lane,
                        state="healthy",
                        current_task_id=None,
                        last_heartbeat_at=recorded_at,
                        runtime_metadata={
                            "authority": "runtime_bootstrap",
                            "workspace_id": workspace_id,
                        },
                    )

        active_tasks = sorted(
            (
                task
                for task in tasks
                if task.status
                in {
                    "dispatching",
                    "running",
                    "cancellation_requested",
                    "cancelling",
                    "termination_requested",
                }
            ),
            key=lambda task: (task.progress.updated_at, task.task_id),
            reverse=True,
        )

        for task in active_tasks:
            state = _processor_state_for_status(task.status)
            if state is None:
                continue
            processor_id = self._choose_processor_for_lane(task.workspace_id, task.lane)
            self._task_assignments[task.task_id] = processor_id
            self._heartbeats[processor_id] = build_processor_heartbeat(
                processor_id=_display_processor_id(processor_id),
                lane=_normalize_lane(task.lane),
                state=state,
                current_task_id=task.task_id,
                last_heartbeat_at=recorded_at,
                runtime_metadata=_runtime_metadata(
                    task=task,
                    execution_phase=task.status,
                ),
            )

    def _set_task_heartbeat(
        self,
        *,
        task: TaskDetail,
        state: ProcessorState,
        recorded_at: datetime,
        runtime_metadata: dict[str, object],
    ) -> None:
        processor_id = self._task_assignments.get(task.task_id)
        if processor_id is None:
            processor_id = self._choose_processor_for_lane(task.workspace_id, task.lane)
            self._task_assignments[task.task_id] = processor_id
        self._heartbeats[processor_id] = build_processor_heartbeat(
            processor_id=_display_processor_id(processor_id),
            lane=_normalize_lane(task.lane),
            state=state,
            current_task_id=task.task_id,
            last_heartbeat_at=recorded_at,
            runtime_metadata=runtime_metadata,
        )

    def _choose_processor_for_lane(self, workspace_id: str, lane: TaskLane | str) -> str:
        canonical_lane = _normalize_lane(lane)
        for processor_id in self._BASELINE_PROCESSORS[canonical_lane]:
            key = _processor_key(workspace_id, processor_id)
            heartbeat = self._heartbeats.get(key)
            if heartbeat is None or heartbeat.current_task_id is None:
                return key
        overflow_count = sum(
            1
            for key in self._heartbeats
            if key.startswith(f"{workspace_id}:{canonical_lane}-processor-overflow-")
        )
        processor_id = f"{canonical_lane}-processor-overflow-{overflow_count + 1}"
        key = _processor_key(workspace_id, processor_id)
        self._heartbeats[key] = build_processor_heartbeat(
            processor_id=processor_id,
            lane=canonical_lane,
            state="healthy",
            current_task_id=None,
            last_heartbeat_at=self._latest_workspace_recorded_at(workspace_id),
            runtime_metadata={
                "authority": "runtime_overflow",
                "workspace_id": workspace_id,
            },
        )
        return key

    def _first_processor_for_lane(self, workspace_id: str, lane: TaskLane | str) -> str:
        canonical_lane = _normalize_lane(lane)
        return _processor_key(workspace_id, self._BASELINE_PROCESSORS[canonical_lane][0])

    def _latest_workspace_recorded_at(self, workspace_id: str) -> datetime:
        return max(
            (
                heartbeat.last_heartbeat_at
                for key, heartbeat in self._heartbeats.items()
                if key.startswith(f"{workspace_id}:")
            ),
            default=datetime.now(UTC),
        )


def _processor_state_for_status(status: TaskStatus) -> ProcessorState | None:
    if status in {"dispatching", "running"}:
        return "busy"
    if status in {"cancellation_requested", "cancelling"}:
        return "draining"
    if status == "termination_requested":
        return "degraded"
    return None


def _runtime_metadata(
    *,
    task: TaskDetail,
    execution_phase: TaskStatus,
    stale_after_seconds: int | None = None,
    worker_pid: int | None = None,
) -> dict[str, object]:
    metadata: dict[str, object] = {
        "worker_task_name": task.worker_task_name,
        "task_status": task.status,
        "execution_phase": execution_phase,
        "workspace_id": task.workspace_id,
    }
    if worker_pid is not None:
        metadata["worker_pid"] = worker_pid
    if stale_after_seconds is not None:
        metadata["stale_after_seconds"] = stale_after_seconds
    return metadata


def _normalize_lane(lane: TaskLane | str) -> TaskLane:
    if lane == "post_processing":
        return "simulation"
    return lane


def _processor_key(workspace_id: str, processor_id: str) -> str:
    return f"{workspace_id}:{processor_id}"


def _display_processor_id(processor_key: str) -> str:
    return processor_key.split(":", 1)[1]


def _normalize_datetime(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _lane_order(lane: LaneName) -> int:
    if lane == "simulation":
        return 0
    if lane == "characterization":
        return 1
    return 2


def _parse_task_timestamp(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _refresh_idle_heartbeat(
    heartbeat: ProcessorHeartbeat,
    recorded_at: datetime,
) -> ProcessorHeartbeat:
    if heartbeat.current_task_id is not None:
        return heartbeat
    if heartbeat.state != "healthy":
        return heartbeat
    return build_processor_heartbeat(
        processor_id=heartbeat.processor_id,
        lane=heartbeat.lane,
        state=heartbeat.state,
        current_task_id=None,
        last_heartbeat_at=recorded_at,
        runtime_metadata=heartbeat.runtime_metadata,
    )
