from __future__ import annotations

import os
from collections.abc import Callable, Sequence
from datetime import UTC, datetime, timedelta
from typing import Protocol

from sc_core.execution import TaskExecutionResult

from src.app.domain.datasets import DesignBrowseRow, TraceDetail, TraceMetadataSummary
from src.app.domain.tasks import CharacterizationSetup, TaskDetail, TaskResultRefs
from src.app.infrastructure.persisted_characterization_runtime import (
    CharacterizationExecutionRequest,
    CharacterizationExecutionTrace,
    PersistedCharacterizationRepository,
)
from src.app.infrastructure.persisted_runtime import (
    run_real_post_processing_task,
    run_real_simulation_task,
)


class TaskDetailRepository(Protocol):
    def get_task(self, task_id: int) -> TaskDetail | None: ...


class TaskListingRepository(TaskDetailRepository, Protocol):
    def list_tasks(self) -> Sequence[TaskDetail]: ...


class CircuitDefinitionRepository(Protocol):
    def get_circuit_definition(self, definition_id: int) -> object | None: ...


class CharacterizationDatasetRepository(Protocol):
    def get_design(self, dataset_id: str, design_id: str) -> DesignBrowseRow | None: ...

    def list_trace_metadata(
        self,
        dataset_id: str,
        design_id: str,
    ) -> Sequence[TraceMetadataSummary]: ...

    def get_trace_detail(
        self,
        dataset_id: str,
        design_id: str,
        trace_id: str,
    ) -> TraceDetail | None: ...


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

        worker_pid = os.getpid()
        started_at = datetime.now(UTC)
        runtime = self._execution_runtime_factory()

        try:
            if task.definition_id is None:
                raise ValueError("Simulation definition_id is missing.")
            definition = self._circuit_definition_repository.get_circuit_definition(
                task.definition_id
            )
            definition_source_text = getattr(definition, "source_text", None)
            if not isinstance(definition_source_text, str) or len(
                definition_source_text.strip()
            ) == 0:
                raise ValueError("Simulation definition source is unavailable.")
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
                summary="Simulation worker is running the persisted solver path.",
                percent_complete=35,
                stage_label=task.worker_task_name,
                current_step=1,
                total_steps=2,
                stale_after_seconds=180,
                details=_heartbeat_details(task),
            )
            result_summary_payload, result_refs = run_real_simulation_task(
                task,
                definition_source_text=definition_source_text,
            )
            runtime.complete_task(
                task.task_id,
                recorded_at=heartbeat_at + timedelta(seconds=1),
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
        characterization_repository: PersistedCharacterizationRepository,
        execution_runtime_factory: Callable[[], TaskExecutionRuntime],
    ) -> None:
        self._task_repository = task_repository
        self._dataset_repository = dataset_repository
        self._characterization_repository = characterization_repository
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
        selected_trace_details = _resolve_characterization_trace_details(
            dataset_repository=self._dataset_repository,
            dataset_id=task.dataset_id,
            design_id=task.characterization_setup.design_id,
            selected_traces=selected_traces,
        )

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
                summary=(
                    "Characterization worker is running the persisted admittance "
                    "extraction path."
                ),
                percent_complete=78,
                stage_label=task.worker_task_name,
                current_step=2,
                total_steps=3,
                stale_after_seconds=180,
                details=_characterization_fit_details(task.characterization_setup),
            )
            execution_result = self._characterization_repository.run_admittance_extraction(
                CharacterizationExecutionRequest(
                    task=task,
                    design=design,
                    traces=tuple(
                        CharacterizationExecutionTrace(summary=summary, detail=detail)
                        for summary, detail in zip(
                            selected_traces,
                            selected_trace_details,
                            strict=True,
                        )
                    ),
                )
            )
            completed_at = started_at + timedelta(seconds=3)
            runtime.complete_task(
                task.task_id,
                recorded_at=completed_at,
                result=TaskExecutionResult(
                    result_summary_payload=execution_result.result_summary_payload,
                    analysis_run_id=execution_result.result_refs.analysis_run_id,
                ),
                result_refs=execution_result.result_refs,
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
        execution_runtime_factory: Callable[[], TaskExecutionRuntime],
    ) -> None:
        self._task_repository = task_repository
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
                summary="Post-processing worker is loading persisted upstream traces.",
                percent_complete=35,
                stage_label=task.worker_task_name,
                current_step=1,
                total_steps=2,
                stale_after_seconds=180,
                details=_post_processing_heartbeat_details(task, upstream_task),
            )
            result_summary_payload, result_refs = run_real_post_processing_task(
                task,
                upstream_task=upstream_task,
            )
            runtime.complete_task(
                task.task_id,
                recorded_at=started_at + timedelta(seconds=2),
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
        queued_local_tasks = sorted(
            (
                task
                for task in self._task_repository.list_tasks()
                if task.visibility_scope == "local" and task.status == "queued"
            ),
            key=lambda task: (task.submitted_at, task.task_id),
        )
        for task in queued_local_tasks:
            self.execute_submitted_task(task.task_id)

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


def _resolve_characterization_trace_details(
    *,
    dataset_repository: CharacterizationDatasetRepository,
    dataset_id: str,
    design_id: str,
    selected_traces: Sequence[TraceMetadataSummary],
) -> tuple[TraceDetail, ...]:
    trace_details: list[TraceDetail] = []
    for trace in selected_traces:
        detail = dataset_repository.get_trace_detail(
            dataset_id,
            design_id,
            trace.trace_id,
        )
        if detail is None:
            raise ValueError(
                "Selected characterization trace detail is not available in the dataset scope."
            )
        trace_details.append(detail)
    return tuple(trace_details)
