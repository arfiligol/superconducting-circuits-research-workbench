"""Real WS6 simulation worker execution over persisted TaskRecord inputs."""

from __future__ import annotations

from collections.abc import Mapping
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeoutError
from datetime import UTC, datetime
from typing import Any

from sc_core.execution import build_task_heartbeat_operation, build_task_heartbeat_payload

from legacy.legacy_nicegui_archived.services.simulation_batch_persistence import (
    mark_simulation_batch_failed,
    persist_simulation_result_into_batch,
)
from legacy.legacy_nicegui_archived.services.simulation_runner import SimulationRunRequest, execute_simulation_run
from legacy.legacy_nicegui_archived.services.simulation_task_contract import PersistedSimulationTaskRequest
from core.shared.persistence.unit_of_work import get_unit_of_work
from core.simulation.application.run_simulation import (
    SimulationSweepAxis,
    apply_simulation_sweep_config_overrides,
    apply_simulation_sweep_overrides,
    build_linear_sweep_values,
    build_simulation_sweep_plan,
    list_simulation_sweep_targets,
)
from core.simulation.application.trace_architecture import IncrementalRawSimulationSweepWriter
from core.simulation.domain.circuit import CircuitDefinition, SimulationConfig, SimulationResult
from worker.runtime import TaskExecutionResult

_HEARTBEAT_INTERVAL_SECONDS = 5.0
_LONG_RUNNING_WARNING_SECONDS = 60.0


def _utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _heartbeat_task(
    *,
    task_id: int,
    batch_id: int | None,
    stage_label: str,
    elapsed_seconds: int,
    point_label: str | None = None,
    warning: str | None = None,
) -> None:
    recorded_at = _utcnow()
    details: dict[str, object] = {
        "elapsed_seconds": int(elapsed_seconds),
        "trace_batch_id": batch_id,
        "point_label": point_label,
        "warning": warning,
    }
    with get_unit_of_work() as uow:
        uow.tasks.apply_execution_operation(
            build_task_heartbeat_operation(
                task_id=task_id,
                recorded_at=recorded_at,
                progress_payload=build_task_heartbeat_payload(
                    phase="running",
                    summary=warning or f"{stage_label} still running ({elapsed_seconds}s).",
                    recorded_at=recorded_at,
                    stage_label=stage_label,
                    stale_after_seconds=300,
                    warning=warning,
                    details=details,
                    extra_payload=details,
                ),
            )
        )
        uow.commit()


def _run_request_with_heartbeat(
    *,
    task_id: int,
    batch_id: int | None,
    request: SimulationRunRequest,
    point_label: str | None = None,
) -> SimulationResult:
    start_time = _utcnow()
    warning_emitted = False
    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(execute_simulation_run, request)
        while True:
            try:
                return future.result(timeout=_HEARTBEAT_INTERVAL_SECONDS).simulation_result
            except FutureTimeoutError:
                elapsed_seconds = max(1, int((_utcnow() - start_time).total_seconds()))
                warning = None
                if not warning_emitted and elapsed_seconds >= _LONG_RUNNING_WARNING_SECONDS:
                    warning_emitted = True
                    warning = (
                        "Long-running simulation detected; persisted worker heartbeat is active."
                    )
                _heartbeat_task(
                    task_id=task_id,
                    batch_id=batch_id,
                    stage_label=request.stage_label,
                    elapsed_seconds=elapsed_seconds,
                    point_label=point_label,
                    warning=warning,
                )


def _sweep_axes(
    *,
    circuit: CircuitDefinition,
    config: SimulationConfig,
    sweep_setup_payload: Mapping[str, Any],
) -> tuple[SimulationSweepAxis, ...]:
    available_units = {
        str(item["value_ref"]): str(item["unit"])
        for item in list_simulation_sweep_targets(circuit=circuit, config=config)
        if isinstance(item, Mapping) and "value_ref" in item
    }
    resolved_axes: list[SimulationSweepAxis] = []
    for axis_payload in list(sweep_setup_payload.get("axes", [])):
        if not isinstance(axis_payload, Mapping):
            continue
        target_value_ref = str(axis_payload.get("target_value_ref", "")).strip()
        if not target_value_ref:
            continue
        resolved_axes.append(
            SimulationSweepAxis(
                target_value_ref=target_value_ref,
                values=build_linear_sweep_values(
                    start=float(axis_payload.get("start", 0.0)),
                    stop=float(axis_payload.get("stop", 0.0)),
                    points=max(1, int(axis_payload.get("points", 1))),
                ),
                unit=available_units.get(target_value_ref, str(axis_payload.get("unit", ""))),
            )
        )
    return tuple(resolved_axes)


def execute_simulation_task(task_id: int) -> TaskExecutionResult:
    """Execute one real WS6 simulation task and persist it into the linked TraceBatchRecord."""
    with get_unit_of_work() as uow:
        task = uow.tasks.get_task(task_id)
        if task is None:
            raise ValueError(f"Task ID {task_id} not found.")
        request_payload = task.request_payload.get("parameters", {})
        if not isinstance(request_payload, Mapping):
            raise ValueError("Persisted simulation task parameters are missing.")
        raw_request = request_payload.get("request_payload", {})
        if not isinstance(raw_request, Mapping):
            raise ValueError("Persisted simulation task request payload is missing.")
        request = PersistedSimulationTaskRequest.from_payload(
            dict(raw_request.get("simulation_request", {}))
        )
        trace_batch_id = int(task.trace_batch_id) if task.trace_batch_id is not None else None
        if trace_batch_id is None:
            raise ValueError("Simulation task is missing trace_batch_id.")

    circuit = request.circuit_definition()
    freq_range = request.frequency_range()
    config = request.simulation_config()
    context = request.use_case_context()
    sweep_setup_payload = (
        dict(request.sweep_setup_payload)
        if isinstance(request.sweep_setup_payload, Mapping)
        else None
    )

    try:
        if not sweep_setup_payload or not bool(sweep_setup_payload.get("enabled", False)):
            result = _run_request_with_heartbeat(
                task_id=task_id,
                batch_id=trace_batch_id,
                request=SimulationRunRequest(
                    circuit=circuit,
                    freq_range=freq_range,
                    config=config,
                    context=context,
                    stage_label="simulation",
                ),
            )
            result_payload = None
        else:
            sweep_plan = build_simulation_sweep_plan(
                circuit=circuit,
                axes=_sweep_axes(
                    circuit=circuit,
                    config=config,
                    sweep_setup_payload=sweep_setup_payload,
                ),
                config=config,
            )
            writer = IncrementalRawSimulationSweepWriter(
                design_id=int(request.design_id),
                design_name=str(request.design_name),
                run_id=f"task-{task_id}",
                sweep_axes=tuple(sweep_plan.axes),
            )
            try:
                for point in sweep_plan.points:
                    swept_circuit = apply_simulation_sweep_overrides(
                        circuit=circuit,
                        value_ref_overrides=point.value_ref_overrides,
                    )
                    swept_config = apply_simulation_sweep_config_overrides(
                        config=config,
                        target_overrides=point.value_ref_overrides,
                    )
                    point_result = _run_request_with_heartbeat(
                        task_id=task_id,
                        batch_id=trace_batch_id,
                        request=SimulationRunRequest(
                            circuit=swept_circuit,
                            freq_range=freq_range,
                            config=swept_config,
                            context=context,
                            stage_label="simulation_sweep_point",
                        ),
                        point_label=f"{int(point.point_index) + 1}/{int(sweep_plan.point_count)}",
                    )
                    writer.append_point(
                        point_index=int(point.point_index),
                        axis_indices=tuple(point.axis_indices),
                        axis_values=dict(point.value_ref_overrides),
                        result=point_result,
                    )
                result = writer.representative_result
                result_payload = writer.build_payload(
                    summary_payload={
                        "trace_count": writer.trace_count,
                        "run_kind": "parameter_sweep",
                        "frequency_points": len(result.frequencies_ghz),
                        "point_count": int(sweep_plan.point_count),
                        "representative_point_index": 0,
                    }
                )
            except Exception:
                writer.cleanup()
                raise

        with get_unit_of_work() as uow:
            summary_payload = persist_simulation_result_into_batch(
                uow=uow,
                batch_id=trace_batch_id,
                result=result,
                source_meta=request.source_meta,
                config_snapshot=request.config_snapshot,
                schema_source_hash=request.schema_source_hash,
                simulation_setup_hash=request.simulation_setup_hash,
                result_payload=result_payload,
            )
            uow.commit()
        return TaskExecutionResult(
            trace_batch_id=trace_batch_id,
            result_summary_payload=summary_payload,
        )
    except Exception as exc:
        with get_unit_of_work() as uow:
            mark_simulation_batch_failed(
                uow=uow,
                batch_id=trace_batch_id,
                error_code="simulation_task_failed",
                error_summary=str(exc),
            )
            uow.commit()
        raise
