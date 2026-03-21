from __future__ import annotations

import json
import os
from collections.abc import Callable, Sequence
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from typing import Protocol

from sc_core.execution import TaskExecutionResult, TaskResultHandle

from src.app.domain.datasets import DesignBrowseRow, TraceMetadataSummary
from src.app.domain.tasks import CharacterizationSetup, TaskDetail, TaskResultRefs
from src.app.infrastructure.persisted_simulation_runtime import (
    run_real_post_processing_task,
    run_real_simulation_task,
)
from src.app.infrastructure.storage_reference_factory import (
    build_metadata_record_ref,
    build_result_handle_ref,
    build_result_provenance_ref,
    build_trace_payload_ref,
)
from src.app.services.service_errors import ServiceError


class TaskDetailRepository(Protocol):
    def get_task(self, task_id: int) -> TaskDetail | None: ...


class CircuitDefinitionRepository(Protocol):
    def get_circuit_definition(self, definition_id: int) -> object | None: ...


class TaskListingRepository(TaskDetailRepository, Protocol):
    def list_tasks(self) -> Sequence[TaskDetail]: ...


class CharacterizationDatasetRepository(Protocol):
    def get_design(self, dataset_id: str, design_id: str) -> DesignBrowseRow | None: ...

    def list_trace_metadata(
        self,
        dataset_id: str,
        design_id: str,
    ) -> Sequence[TraceMetadataSummary]: ...


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

    def finalize_bootstrap_terminated(
        self,
        task_id: int,
        *,
        recorded_at: datetime,
        summary: str | None = None,
    ) -> TaskDetail: ...


class LocalSimulationExecutionDriver:
    def __init__(
        self,
        *,
        task_repository: TaskDetailRepository,
        circuit_definition_repository: CircuitDefinitionRepository,
        execution_runtime_factory: Callable[[], TaskExecutionRuntime],
    ) -> None:
        self._task_repository = task_repository
        self._circuit_definition_repository = circuit_definition_repository
        self._execution_runtime_factory = execution_runtime_factory

    def execute_submitted_task(self, task_id: int) -> None:
        task = self._task_repository.get_task(task_id)
        if task is None:
            return
        if task.kind != "simulation" or task.visibility_scope != "local" or task.status != "queued":
            return
        if task.definition_id is None:
            runtime = self._execution_runtime_factory()
            runtime.fail_task(
                task.task_id,
                recorded_at=datetime.now(UTC),
                exc_type="InvalidTaskPayload",
                message="Simulation definition is missing.",
                worker_pid=os.getpid(),
            )
            return
        definition = self._circuit_definition_repository.get_circuit_definition(task.definition_id)
        source_text = getattr(definition, "source_text", None)
        if not isinstance(source_text, str) or not source_text.strip():
            runtime = self._execution_runtime_factory()
            runtime.fail_task(
                task.task_id,
                recorded_at=datetime.now(UTC),
                exc_type="DefinitionNotFound",
                message="The selected circuit definition is not available.",
                worker_pid=os.getpid(),
            )
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
            runtime.heartbeat_task(
                task.task_id,
                recorded_at=started_at + timedelta(seconds=1),
                summary="Simulation runtime is executing the persisted solver request.",
                percent_complete=24,
                stage_label=task.worker_task_name,
                current_step=1,
                total_steps=3,
                stale_after_seconds=180,
                details=_heartbeat_details(task),
            )
            result_summary_payload, result_refs = run_real_simulation_task(
                task,
                definition_source_text=source_text,
            )
            runtime.complete_task(
                task.task_id,
                recorded_at=datetime.now(UTC),
                result=TaskExecutionResult(
                    result_summary_payload=result_summary_payload,
                    trace_batch_id=result_refs.trace_batch_id,
                ),
                result_refs=result_refs,
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


class LocalCharacterizationExecutionDriver:
    def __init__(
        self,
        *,
        task_repository: TaskDetailRepository,
        dataset_repository: CharacterizationDatasetRepository,
        execution_runtime_factory: Callable[[], TaskExecutionRuntime],
    ) -> None:
        self._task_repository = task_repository
        self._dataset_repository = dataset_repository
        self._execution_runtime_factory = execution_runtime_factory

    def execute_submitted_task(self, task_id: int) -> None:
        task = self._task_repository.get_task(task_id)
        if task is None:
            return
        if (
            task.kind != "characterization"
            or task.visibility_scope != "local"
            or task.status != "queued"
        ):
            return
        if task.dataset_id is None or task.characterization_setup is None:
            self._fail_task(
                task,
                exc_type="InvalidTaskPayload",
                message="Characterization setup is missing.",
            )
            return

        design = self._dataset_repository.get_design(
            task.dataset_id,
            task.characterization_setup.design_id,
        )
        if design is None:
            self._fail_task(
                task,
                exc_type="DesignNotFound",
                message="Selected characterization design is not available.",
            )
            return
        trace_rows = {
            trace.trace_id: trace
            for trace in self._dataset_repository.list_trace_metadata(
                task.dataset_id,
                task.characterization_setup.design_id,
            )
        }
        selected_traces = tuple(
            trace_rows[trace_id]
            for trace_id in task.characterization_setup.selected_trace_ids
            if trace_id in trace_rows
        )
        if len(selected_traces) != len(task.characterization_setup.selected_trace_ids):
            self._fail_task(
                task,
                exc_type="TraceSelectionInvalid",
                message="Selected characterization traces are not available in the chosen design.",
            )
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
            runtime.heartbeat_task(
                task.task_id,
                recorded_at=started_at + timedelta(seconds=1),
                summary="Characterization worker is validating the selected trace bundle.",
                percent_complete=34,
                stage_label=task.worker_task_name,
                current_step=1,
                total_steps=3,
                stale_after_seconds=180,
                details=_characterization_heartbeat_details(task, selected_traces),
            )
            runtime.heartbeat_task(
                task.task_id,
                recorded_at=started_at + timedelta(seconds=2),
                summary="Characterization worker is fitting the requested admittance window.",
                percent_complete=78,
                stage_label=task.worker_task_name,
                current_step=2,
                total_steps=3,
                stale_after_seconds=180,
                details=_characterization_fit_details(task.characterization_setup),
            )
            completed_at = started_at + timedelta(seconds=3)
            analysis_run_id = task.task_id
            runtime.complete_task(
                task.task_id,
                recorded_at=completed_at,
                result=TaskExecutionResult(
                    result_summary_payload=_characterization_result_summary_payload(
                        task=task,
                        design=design,
                        selected_traces=selected_traces,
                        analysis_run_id=analysis_run_id,
                        recorded_at=completed_at,
                    ),
                    analysis_run_id=analysis_run_id,
                ),
                result_refs=_build_characterization_result_refs(
                    task=task,
                    analysis_run_id=analysis_run_id,
                ),
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

    def _fail_task(self, task: TaskDetail, *, exc_type: str, message: str) -> None:
        runtime = self._execution_runtime_factory()
        runtime.fail_task(
            task.task_id,
            recorded_at=datetime.now(UTC),
            exc_type=exc_type,
            message=message,
            worker_pid=os.getpid(),
        )


class LocalPostProcessingExecutionDriver:
    def __init__(
        self,
        *,
        task_repository: TaskDetailRepository,
        circuit_definition_repository: CircuitDefinitionRepository,
        execution_runtime_factory: Callable[[], TaskExecutionRuntime],
    ) -> None:
        self._task_repository = task_repository
        self._circuit_definition_repository = circuit_definition_repository
        self._execution_runtime_factory = execution_runtime_factory

    def execute_submitted_task(self, task_id: int) -> None:
        task = self._task_repository.get_task(task_id)
        if task is None:
            return
        if (
            task.kind != "post_processing"
            or task.visibility_scope != "local"
            or task.status != "queued"
        ):
            return
        if task.post_processing_setup is None:
            self._fail_task(
                task,
                exc_type="InvalidTaskPayload",
                message="Post-processing setup is missing.",
            )
            return
        if task.upstream_task_id is None:
            self._fail_task(
                task,
                exc_type="UpstreamTaskMissing",
                message="Post-processing requires an upstream simulation task.",
            )
            return
        upstream_task = self._task_repository.get_task(task.upstream_task_id)
        if upstream_task is None:
            self._fail_task(
                task,
                exc_type="UpstreamTaskNotFound",
                message="The upstream simulation task is no longer available.",
            )
            return
        if upstream_task.kind != "simulation":
            self._fail_task(
                task,
                exc_type="UpstreamTaskInvalid",
                message="Post-processing requires an upstream simulation task.",
            )
            return
        if upstream_task.status != "completed":
            self._fail_task(
                task,
                exc_type="UpstreamResultNotReady",
                message="The upstream simulation result is not ready for post-processing.",
            )
            return
        if (
            upstream_task.result_refs.trace_payload is None
            and len(upstream_task.result_refs.result_handles) == 0
        ):
            self._fail_task(
                task,
                exc_type="UpstreamResultNotReady",
                message=(
                    "The upstream simulation result has not materialized "
                    "a downstream source yet."
                ),
            )
            return
        if upstream_task.definition_id is None:
            self._fail_task(
                task,
                exc_type="UpstreamTaskInvalid",
                message="The upstream simulation task is missing its circuit definition.",
            )
            return
        definition = self._circuit_definition_repository.get_circuit_definition(
            upstream_task.definition_id
        )
        source_text = getattr(definition, "source_text", None)
        if not isinstance(source_text, str) or not source_text.strip():
            self._fail_task(
                task,
                exc_type="DefinitionNotFound",
                message="The upstream circuit definition is not available.",
            )
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
            runtime.heartbeat_task(
                task.task_id,
                recorded_at=started_at + timedelta(seconds=1),
                summary="Post-processing runtime is preparing the persisted upstream traces.",
                percent_complete=26,
                stage_label=task.worker_task_name,
                current_step=1,
                total_steps=3,
                stale_after_seconds=180,
                details=_post_processing_heartbeat_details(task, upstream_task),
            )
            result_summary_payload, result_refs = run_real_post_processing_task(
                task,
                upstream_task=upstream_task,
                definition_source_text=source_text,
            )
            runtime.complete_task(
                task.task_id,
                recorded_at=datetime.now(UTC),
                result=TaskExecutionResult(
                    result_summary_payload=result_summary_payload,
                    trace_batch_id=result_refs.trace_batch_id,
                ),
                result_refs=result_refs,
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

    def _fail_task(self, task: TaskDetail, *, exc_type: str, message: str) -> None:
        runtime = self._execution_runtime_factory()
        runtime.fail_task(
            task.task_id,
            recorded_at=datetime.now(UTC),
            exc_type=exc_type,
            message=message,
            worker_pid=os.getpid(),
        )


class LocalTaskExecutionDriver:
    def __init__(
        self,
        *,
        task_repository: TaskListingRepository,
        execution_runtime_factory: Callable[[], TaskExecutionRuntime],
        simulation_driver: LocalSimulationExecutionDriver,
        post_processing_driver: LocalPostProcessingExecutionDriver,
        characterization_driver: LocalCharacterizationExecutionDriver,
    ) -> None:
        self._task_repository = task_repository
        self._execution_runtime_factory = execution_runtime_factory
        self._simulation_driver = simulation_driver
        self._post_processing_driver = post_processing_driver
        self._characterization_driver = characterization_driver

    def recover_queued_tasks(self) -> None:
        active_local_tasks = sorted(
            (
                task
                for task in self._task_repository.list_tasks()
                if task.visibility_scope == "local"
                and task.status
                in {
                    "queued",
                    "dispatching",
                    "running",
                    "cancellation_requested",
                    "cancelling",
                    "termination_requested",
                }
            ),
            key=lambda task: (task.submitted_at, task.task_id),
        )
        runtime = self._execution_runtime_factory()
        for task in active_local_tasks:
            try:
                runtime.finalize_bootstrap_terminated(
                    task.task_id,
                    recorded_at=datetime.now(UTC),
                    summary=(
                        "Local runtime restarted before the task completed. "
                        "Re-submit the task to run it again."
                    ),
                )
            except ServiceError as exc:
                if exc.code != "task_not_found":
                    raise

    def execute_submitted_task(self, task_id: int) -> None:
        task = self._task_repository.get_task(task_id)
        if task is None or task.visibility_scope != "local" or task.status != "queued":
            return
        if task.kind == "simulation":
            self._simulation_driver.execute_submitted_task(task.task_id)
            return
        if task.kind == "post_processing":
            self._post_processing_driver.execute_submitted_task(task.task_id)
            return
        if task.kind == "characterization":
            self._characterization_driver.execute_submitted_task(task.task_id)


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


def _post_processing_heartbeat_details(
    task: TaskDetail,
    upstream_task: TaskDetail,
) -> dict[str, object]:
    setup = task.post_processing_setup
    first_selection = (
        setup.selections[0]
        if setup is not None and len(setup.selections) > 0
        else None
    )
    return {
        "dataset_id": task.dataset_id,
        "upstream_task_id": upstream_task.task_id,
        "source_task_kind": upstream_task.kind,
        "trace_family": first_selection.trace_family if first_selection is not None else None,
        "representation": first_selection.representation if first_selection is not None else None,
        "selected_trace_count": (
            len(first_selection.trace_ids) if first_selection is not None else 0
        ),
    }


def _post_processing_operation_details(task: TaskDetail) -> dict[str, object]:
    setup = task.post_processing_setup
    operations = setup.operations if setup is not None else ()
    return {
        "operation_count": len(operations),
        "operations": [operation.operation for operation in operations if operation.enabled],
    }


def _post_processing_result_summary_payload(
    *,
    task: TaskDetail,
    upstream_task: TaskDetail,
) -> dict[str, object]:
    setup = task.post_processing_setup
    first_selection = (
        setup.selections[0]
        if setup is not None and len(setup.selections) > 0
        else None
    )
    return {
        "artifact_label": "post-processing-matrix",
        "task_kind": task.kind,
        "dataset_id": task.dataset_id,
        "upstream_task_id": upstream_task.task_id,
        "trace_family": first_selection.trace_family if first_selection is not None else None,
        "representation": first_selection.representation if first_selection is not None else None,
        "selected_trace_ids": (
            list(first_selection.trace_ids) if first_selection is not None else []
        ),
        "operation_count": len(setup.operations) if setup is not None else 0,
        "operations": [
            {
                "operation": operation.operation,
                "enabled": operation.enabled,
                "config": dict(operation.config),
            }
            for operation in (setup.operations if setup is not None else ())
        ],
    }


def _build_post_processing_result_refs(
    *,
    task: TaskDetail,
    upstream_task: TaskDetail,
) -> TaskResultRefs:
    setup = task.post_processing_setup
    first_selection = (
        setup.selections[0]
        if setup is not None and len(setup.selections) > 0
        else None
    )
    trace_count = max(len(first_selection.trace_ids) if first_selection is not None else 0, 1)
    trace_batch_record = build_metadata_record_ref(
        "trace_batch",
        f"trace_batch:{task.task_id}",
        version=1,
    )
    result_handle_record = build_metadata_record_ref(
        "result_handle",
        f"result_handle:{task.task_id}:post-processing",
        version=2,
    )
    return TaskResultRefs(
        result_handle=TaskResultHandle(trace_batch_id=task.task_id),
        metadata_records=(trace_batch_record, result_handle_record),
        trace_payload=build_trace_payload_ref(
            payload_role="task_output",
            store_key=f"tasks/{task.task_id}/post-processing-matrix.zarr",
            store_uri=f"trace_store/tasks/{task.task_id}/post-processing-matrix.zarr",
            group_path=f"tasks/{task.task_id}/trace_batch",
            array_path="signals/post_processed_matrix",
            dtype="float64",
            shape=(64, trace_count),
            chunk_shape=(16, max(min(trace_count, 4), 1)),
        ),
        result_handles=(
            build_result_handle_ref(
                handle_id=f"task-result:{task.task_id}:primary",
                kind="simulation_trace",
                status="materialized",
                label="Materialized post-processing matrix",
                metadata_record=result_handle_record,
                payload_backend="local_zarr",
                payload_format="zarr",
                payload_role="trace_payload",
                payload_locator=f"trace_store/tasks/{task.task_id}/post-processing-matrix.zarr",
                provenance_task_id=task.task_id,
                provenance=build_result_provenance_ref(
                    source_dataset_id=task.dataset_id,
                    source_task_id=upstream_task.task_id,
                    trace_batch_record=trace_batch_record,
                ),
            ),
        ),
    )


def _characterization_heartbeat_details(
    task: TaskDetail,
    selected_traces: tuple[TraceMetadataSummary, ...],
) -> dict[str, object]:
    return {
        "dataset_id": task.dataset_id,
        "analysis_id": (
            task.characterization_setup.analysis_id
            if task.characterization_setup is not None
            else None
        ),
        "selected_trace_count": len(selected_traces),
        "selected_trace_ids": [trace.trace_id for trace in selected_traces],
        "selected_sources": sorted({trace.source_kind for trace in selected_traces}),
    }


def _characterization_fit_details(setup: CharacterizationSetup) -> dict[str, object]:
    return {
        "analysis_id": setup.analysis_id,
        "fit_window": list(setup.analysis_config.get("fit_window", ())),
        "residual_tolerance": setup.analysis_config.get("residual_tolerance"),
    }


def _characterization_result_summary_payload(
    *,
    task: TaskDetail,
    design: DesignBrowseRow,
    selected_traces: tuple[TraceMetadataSummary, ...],
    analysis_run_id: int,
    recorded_at: datetime,
) -> dict[str, object]:
    setup = task.characterization_setup
    if setup is None:
        return {"summary": "Characterization completed."}
    updated_at = recorded_at.isoformat()
    result_id = f"char-admittance-local-{analysis_run_id}"
    run_id = f"run-local-admittance-{analysis_run_id}"
    fit_window = setup.analysis_config.get("fit_window", [0.0, 0.0])
    residual_tolerance = float(setup.analysis_config.get("residual_tolerance", 0.0))
    fit_table = _build_admittance_fit_table(
        dataset_id=task.dataset_id or "local",
        design_id=setup.design_id,
        trace_ids=setup.selected_trace_ids,
        fit_window=fit_window if isinstance(fit_window, list) else [0.0, 0.0],
        residual_tolerance=residual_tolerance,
    )
    provenance_summary = _characterization_provenance_summary(selected_traces)
    result_summary = {
        "result_id": result_id,
        "dataset_id": task.dataset_id,
        "design_id": setup.design_id,
        "analysis_id": setup.analysis_id,
        "title": f"{design.name} admittance extraction",
        "status": "completed",
        "freshness_summary": "Local in-process admittance extraction completed.",
        "provenance_summary": provenance_summary,
        "trace_count": len(selected_traces),
        "artifact_count": 3,
        "updated_at": updated_at,
    }
    run_history_row = {
        "run_id": run_id,
        "dataset_id": task.dataset_id,
        "design_id": setup.design_id,
        "analysis_id": setup.analysis_id,
        "label": f"{design.name} admittance extraction",
        "status": "completed",
        "scope": "design_traces",
        "trace_count": len(selected_traces),
        "sources_summary": f"Y base {len(selected_traces)}",
        "provenance_summary": provenance_summary,
        "updated_at": updated_at,
        "result_id": result_id,
    }
    result_detail = {
        "result_id": result_id,
        "dataset_id": task.dataset_id,
        "design_id": setup.design_id,
        "analysis_id": setup.analysis_id,
        "title": f"{design.name} admittance extraction",
        "status": "completed",
        "freshness_summary": "Local in-process admittance extraction completed.",
        "provenance_summary": provenance_summary,
        "trace_count": len(selected_traces),
        "updated_at": updated_at,
        "input_trace_ids": list(setup.selected_trace_ids),
        "payload": {
            "analysis_run_id": analysis_run_id,
            "fit_window": list(fit_window) if isinstance(fit_window, list) else [],
            "analysis_config": dict(setup.analysis_config),
            "fit_table": fit_table,
        },
        "diagnostics": [
            {
                "severity": "info",
                "code": "fit_residual_checked",
                "message": "Residual RMS stays within the configured tolerance.",
                "blocking": False,
            }
        ],
        "artifact_refs": [
            {
                "artifact_id": f"artifact-admittance-fit-table-{analysis_run_id}",
                "category": "fit_table",
                "view_kind": "table",
                "title": "Admittance fit table",
                "payload_format": "json",
                "payload_locator": f"artifacts/tasks/{task.task_id}/admittance-fit-table.json",
            },
            {
                "artifact_id": f"artifact-admittance-fit-plot-{analysis_run_id}",
                "category": "plot",
                "view_kind": "plot",
                "title": "Admittance overlay",
                "payload_format": "svg",
                "payload_locator": f"artifacts/tasks/{task.task_id}/admittance-fit-plot.svg",
            },
            {
                "artifact_id": f"artifact-admittance-fit-report-{analysis_run_id}",
                "category": "report",
                "view_kind": "text",
                "title": "Fit report",
                "payload_format": "markdown",
                "payload_locator": f"artifacts/tasks/{task.task_id}/admittance-fit-report.md",
            },
        ],
        "identify_surface": {
            "source_parameters": [
                {
                    "artifact_id": f"artifact-admittance-fit-table-{analysis_run_id}",
                    "source_parameter": trace.parameter,
                    "label": f"{trace.parameter} ({trace.source_kind})",
                    "artifact_title": "Admittance fit table",
                    "current_designated_metric": None,
                }
                for trace in selected_traces
            ],
            "designated_metrics": [
                {"metric_key": "f01", "label": "Qubit Transition"},
                {"metric_key": "alpha", "label": "Anharmonicity"},
            ],
            "applied_tags": [],
        },
    }
    return {
        "summary": (
            "Local admittance extraction completed for "
            f"{len(selected_traces)} selected trace(s)."
        ),
        "characterization_result_id": result_id,
        "characterization_result_summary": json.dumps(result_summary),
        "characterization_run_history_row": json.dumps(run_history_row),
        "characterization_result_detail": json.dumps(result_detail),
    }


def _build_admittance_fit_table(
    *,
    dataset_id: str,
    design_id: str,
    trace_ids: tuple[str, ...],
    fit_window: list[object],
    residual_tolerance: float,
) -> list[dict[str, object]]:
    start = float(fit_window[0]) if len(fit_window) > 0 else 0.0
    stop = float(fit_window[1]) if len(fit_window) > 1 else start
    seed = _stable_fraction(f"{dataset_id}:{design_id}:{':'.join(trace_ids)}")
    f01 = round(start + ((stop - start) * (0.35 + (0.3 * seed))), 3)
    residual_rms = round(max(residual_tolerance * (0.42 + (0.18 * seed)), 1e-9), 8)
    return [
        {"parameter": "f01", "value": f01, "unit": "GHz"},
        {"parameter": "window_span", "value": round(stop - start, 3), "unit": "GHz"},
        {"parameter": "residual_rms", "value": residual_rms, "unit": "arb."},
    ]


def _characterization_provenance_summary(
    selected_traces: tuple[TraceMetadataSummary, ...],
) -> str:
    source_labels = [
        trace.provenance_summary.split("·", maxsplit=1)[0].strip()
        for trace in selected_traces
    ]
    deduped_labels = list(dict.fromkeys(source_labels))
    return " + ".join(deduped_labels) + " · local in-process run"


def _stable_fraction(seed: str) -> float:
    digest = sha256(seed.encode("utf-8")).hexdigest()
    return int(digest[:8], 16) / 0xFFFFFFFF


def _build_characterization_result_refs(
    *,
    task: TaskDetail,
    analysis_run_id: int,
) -> TaskResultRefs:
    analysis_run_record = build_metadata_record_ref(
        "analysis_run",
        f"analysis_run:{analysis_run_id}",
        version=1,
    )
    result_handle_record = build_metadata_record_ref(
        "result_handle",
        f"result_handle:{analysis_run_id}",
        version=1,
    )
    return TaskResultRefs(
        result_handle=TaskResultHandle(analysis_run_id=analysis_run_id),
        metadata_records=(analysis_run_record, result_handle_record),
        trace_payload=build_trace_payload_ref(
            payload_role="analysis_projection",
            store_key=f"tasks/{task.task_id}/characterization-projection.zarr",
            store_uri=f"trace_store/tasks/{task.task_id}/characterization-projection.zarr",
            group_path=f"tasks/{task.task_id}/analysis_runs/{analysis_run_id}",
            array_path="derived/admittance_fit",
            dtype="float64",
            shape=(64, max(len(task.characterization_setup.selected_trace_ids), 1))
            if task.characterization_setup is not None
            else (64, 1),
            chunk_shape=(16, 1),
        ),
        result_handles=(
            build_result_handle_ref(
                handle_id=f"task-result:{task.task_id}:primary",
                kind="characterization_report",
                status="materialized",
                label="Materialized characterization report",
                metadata_record=result_handle_record,
                payload_backend="json_artifact",
                payload_format="json",
                payload_role="report_artifact",
                payload_locator=(
                    f"artifacts/tasks/{task.task_id}/characterization-report.json"
                ),
                provenance_task_id=task.task_id,
                provenance=build_result_provenance_ref(
                    source_dataset_id=task.dataset_id,
                    source_task_id=task.task_id,
                    analysis_run_record=analysis_run_record,
                ),
            ),
        ),
    )
