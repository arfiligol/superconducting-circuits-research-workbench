from __future__ import annotations

import os
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Protocol

from sc_core.execution import TaskExecutionResult, TaskResultHandle

from src.app.domain.tasks import TaskDetail, TaskResultRefs
from src.app.infrastructure.storage_reference_factory import (
    build_metadata_record_ref,
    build_result_handle_ref,
    build_result_provenance_ref,
    build_trace_payload_ref,
)


class TaskDetailRepository(Protocol):
    def get_task(self, task_id: int) -> TaskDetail | None: ...


class TaskExecutionRuntime(Protocol):
    def start_task(
        self,
        task_id: int,
        *,
        recorded_at: datetime,
        worker_pid: int | None = None,
        stale_after_seconds: int = 300,
    ) -> TaskDetail: ...

    def heartbeat_task(
        self,
        task_id: int,
        *,
        recorded_at: datetime,
        summary: str,
        percent_complete: int | None = None,
        stage_label: str | None = None,
        current_step: int | None = None,
        total_steps: int | None = None,
        warning: str | None = None,
        stale_after_seconds: int | None = None,
        details: dict[str, object] | None = None,
        extra_payload: dict[str, object] | None = None,
    ) -> TaskDetail: ...

    def complete_task(
        self,
        task_id: int,
        *,
        recorded_at: datetime,
        result: TaskExecutionResult,
        result_refs: TaskResultRefs | None = None,
    ) -> TaskDetail: ...

    def fail_task(
        self,
        task_id: int,
        *,
        recorded_at: datetime,
        exc_type: str,
        message: str,
        worker_pid: int | None = None,
    ) -> TaskDetail: ...


class LocalSimulationExecutionDriver:
    def __init__(
        self,
        *,
        task_repository: TaskDetailRepository,
        execution_runtime_factory: Callable[[], TaskExecutionRuntime],
    ) -> None:
        self._task_repository = task_repository
        self._execution_runtime_factory = execution_runtime_factory

    def execute_submitted_task(self, task_id: int) -> None:
        task = self._task_repository.get_task(task_id)
        if task is None:
            return
        if task.kind != "simulation" or task.visibility_scope != "local" or task.status != "queued":
            return

        worker_pid = os.getpid()
        started_at = datetime.now(UTC)
        runtime = self._execution_runtime_factory()

        try:
            runtime.start_task(
                task.task_id,
                recorded_at=started_at,
                worker_pid=worker_pid,
                stale_after_seconds=180,
            )
            heartbeat_at = started_at + timedelta(seconds=1)
            runtime.heartbeat_task(
                task.task_id,
                recorded_at=heartbeat_at,
                summary="Simulation worker is sweeping the requested frequency range.",
                percent_complete=72,
                stage_label=task.worker_task_name,
                current_step=2,
                total_steps=3,
                stale_after_seconds=180,
                details=_heartbeat_details(task),
            )
            runtime.complete_task(
                task.task_id,
                recorded_at=heartbeat_at + timedelta(seconds=1),
                result=TaskExecutionResult(
                    result_summary_payload=_result_summary_payload(task),
                    trace_batch_id=task.task_id,
                ),
                result_refs=_build_simulation_result_refs(task),
            )
        except Exception as exc:
            current_task = self._task_repository.get_task(task_id)
            if current_task is None or current_task.status not in {"queued", "running"}:
                return
            runtime.fail_task(
                task.task_id,
                recorded_at=datetime.now(UTC),
                exc_type=type(exc).__name__,
                message=str(exc),
                worker_pid=worker_pid,
            )


def _heartbeat_details(task: TaskDetail) -> dict[str, object]:
    point_count = (
        task.simulation_setup.frequency_sweep.point_count
        if task.simulation_setup is not None
        else None
    )
    source_count = len(task.simulation_setup.sources) if task.simulation_setup is not None else 0
    return {
        "dataset_id": task.dataset_id,
        "definition_id": task.definition_id,
        "frequency_points": point_count,
        "source_count": source_count,
        "ptc_enabled": (
            task.simulation_setup.ptc.enabled
            if task.simulation_setup is not None and task.simulation_setup.ptc is not None
            else False
        ),
    }


def _result_summary_payload(task: TaskDetail) -> dict[str, object]:
    frequency_sweep = (
        task.simulation_setup.frequency_sweep
        if task.simulation_setup is not None
        else None
    )
    return {
        "artifact_label": "simulation-trace",
        "task_kind": task.kind,
        "dataset_id": task.dataset_id,
        "definition_id": task.definition_id,
        "point_count": frequency_sweep.point_count if frequency_sweep is not None else None,
        "frequency_range_ghz": {
            "start": frequency_sweep.start_ghz if frequency_sweep is not None else None,
            "stop": frequency_sweep.stop_ghz if frequency_sweep is not None else None,
        },
    }


def _build_simulation_result_refs(task: TaskDetail) -> TaskResultRefs:
    point_count = (
        task.simulation_setup.frequency_sweep.point_count
        if task.simulation_setup is not None
        else 1
    )
    chunk_point_count = max(min(point_count, 64), 1)
    trace_batch_record = build_metadata_record_ref(
        "trace_batch",
        f"trace_batch:{task.task_id}",
        version=1,
    )
    result_handle_record = build_metadata_record_ref(
        "result_handle",
        f"result_handle:{task.task_id}",
        version=2,
    )
    return TaskResultRefs(
        result_handle=TaskResultHandle(trace_batch_id=task.task_id),
        metadata_records=(trace_batch_record, result_handle_record),
        trace_payload=build_trace_payload_ref(
            payload_role="task_output",
            store_key=f"tasks/{task.task_id}/simulation-trace.zarr",
            store_uri=f"trace_store/tasks/{task.task_id}/simulation-trace.zarr",
            group_path=f"tasks/{task.task_id}/trace_batch",
            array_path="signals/s_parameters",
            dtype="float64",
            shape=(point_count, 2),
            chunk_shape=(chunk_point_count, 2),
        ),
        result_handles=(
            build_result_handle_ref(
                handle_id=f"task-result:{task.task_id}:primary",
                kind="simulation_trace",
                status="materialized",
                label="Materialized simulation trace",
                metadata_record=result_handle_record,
                payload_backend="local_zarr",
                payload_format="zarr",
                payload_role="trace_payload",
                payload_locator=f"trace_store/tasks/{task.task_id}/simulation-trace.zarr",
                provenance_task_id=task.task_id,
                provenance=build_result_provenance_ref(
                    source_dataset_id=task.dataset_id,
                    source_task_id=task.task_id,
                    trace_batch_record=trace_batch_record,
                ),
            ),
        ),
    )
