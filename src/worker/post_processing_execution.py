"""Real WS7 post-processing worker execution over persisted TaskRecord inputs."""

from __future__ import annotations

from collections.abc import Mapping
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeoutError
from datetime import UTC, datetime

from sc_core.execution import build_task_heartbeat_operation, build_task_heartbeat_payload

from legacy.legacy_nicegui_archived.services.post_processing_batch_persistence import (
    mark_post_processing_batch_failed,
    persist_post_processing_result_into_batch,
)
from legacy.legacy_nicegui_archived.services.post_processing_runner import (
    PostProcessingInputSource,
    PostProcessingRunRequest,
    PostProcessingRunResult,
    execute_post_processing_pipeline,
)
from legacy.legacy_nicegui_archived.services.post_processing_support import (
    estimate_port_ground_cap_weights,
    extract_compensated_post_processing_payload,
)
from legacy.legacy_nicegui_archived.services.post_processing_task_contract import PersistedPostProcessingTaskRequest
from core.shared.persistence.unit_of_work import get_unit_of_work
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
    warning: str | None = None,
) -> None:
    recorded_at = _utcnow()
    details: dict[str, object] = {
        "elapsed_seconds": int(elapsed_seconds),
        "trace_batch_id": batch_id,
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
    request: PostProcessingRunRequest,
) -> PostProcessingRunResult:
    start_time = _utcnow()
    warning_emitted = False
    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(
            execute_post_processing_pipeline,
            request,
            estimate_auto_weights=lambda circuit_definition, port_a, port_b: (
                estimate_port_ground_cap_weights(
                    circuit_definition,
                    port_a=port_a,
                    port_b=port_b,
                )
            ),
        )
        while True:
            try:
                return future.result(timeout=_HEARTBEAT_INTERVAL_SECONDS)
            except FutureTimeoutError:
                elapsed_seconds = max(1, int((_utcnow() - start_time).total_seconds()))
                warning = None
                if not warning_emitted and elapsed_seconds >= _LONG_RUNNING_WARNING_SECONDS:
                    warning_emitted = True
                    warning = (
                        "Long-running post-processing detected; "
                        "persisted worker heartbeat is active."
                    )
                _heartbeat_task(
                    task_id=task_id,
                    batch_id=batch_id,
                    stage_label="post_processing",
                    elapsed_seconds=elapsed_seconds,
                    warning=warning,
                )


def execute_post_processing_task(task_id: int) -> TaskExecutionResult:
    """Execute one real WS7 post-processing task and persist it into TraceBatchRecord."""
    with get_unit_of_work() as uow:
        task = uow.tasks.get_task(task_id)
        if task is None:
            raise ValueError(f"Task ID {task_id} not found.")
        request_payload = task.request_payload.get("parameters", {})
        if not isinstance(request_payload, Mapping):
            raise ValueError("Persisted post-processing task parameters are missing.")
        raw_request = request_payload.get("request_payload", {})
        if not isinstance(raw_request, Mapping):
            raise ValueError("Persisted post-processing task request payload is missing.")
        request = PersistedPostProcessingTaskRequest.from_payload(
            dict(raw_request.get("post_processing_request", {}))
        )
        trace_batch_id = int(task.trace_batch_id) if task.trace_batch_id is not None else None
        if trace_batch_id is None:
            raise ValueError("Post-processing task is missing trace_batch_id.")
        source_snapshot = uow.result_bundles.get_snapshot(int(request.source_batch_id))
        if source_snapshot is None:
            raise ValueError(f"Source raw batch ID {request.source_batch_id} not found.")
        source_payload = source_snapshot.get("result_payload")
        if not isinstance(source_payload, Mapping):
            raise ValueError("Source raw batch payload is unavailable.")

    canonical_payload, authority = extract_compensated_post_processing_payload(
        source_payload=dict(source_payload),
        input_source=request.input_source,
        reference_impedance_ohm=request.reference_impedance_ohm,
        resistance_ohm_by_port=(
            request.termination_plan_payload.get("resistance_ohm_by_port", {})
            if isinstance(request.termination_plan_payload, Mapping)
            else {}
        ),
    )
    source_run_kind = "single_run"
    trace_batch_record = canonical_payload.get("trace_batch_record")
    if isinstance(trace_batch_record, Mapping):
        summary_payload = trace_batch_record.get("summary_payload", {})
        if isinstance(summary_payload, Mapping):
            source_run_kind = str(summary_payload.get("run_kind", "")).strip() or "single_run"
    else:
        source_run_kind = str(canonical_payload.get("run_kind", "")).strip() or "single_run"

    run_request = PostProcessingRunRequest(
        source=PostProcessingInputSource(
            source_batch_id=int(request.source_batch_id),
            canonical_payload=canonical_payload,
            authority=authority,
            run_kind=source_run_kind,
        ),
        input_source=request.input_source,
        mode_filter=request.mode_filter,
        mode_token=request.mode_token,
        reference_impedance_ohm=request.reference_impedance_ohm,
        step_sequence=[dict(step) for step in request.step_sequence],
        circuit_definition=request.circuit_definition(),
        context=request.use_case_context(),
    )

    try:
        run_result = _run_request_with_heartbeat(
            task_id=task_id,
            batch_id=trace_batch_id,
            request=run_request,
        )
        if not isinstance(run_result, PostProcessingRunResult):
            raise ValueError("Worker post-processing execution returned an invalid result.")
        flow_spec = dict(run_result.flow_spec)
        flow_spec["basis_labels"] = [str(label) for label in run_result.preview_sweep.labels]
        if request.termination_plan_payload is not None:
            flow_spec["termination_plan"] = dict(request.termination_plan_payload)
        with get_unit_of_work() as uow:
            summary_payload = persist_post_processing_result_into_batch(
                uow=uow,
                batch_id=trace_batch_id,
                source_batch_id=int(request.source_batch_id),
                runtime_output=run_result.runtime_output,
                flow_spec=flow_spec,
            )
            uow.commit()
        return TaskExecutionResult(
            trace_batch_id=trace_batch_id,
            result_summary_payload=summary_payload,
        )
    except Exception as exc:
        with get_unit_of_work() as uow:
            mark_post_processing_batch_failed(
                uow=uow,
                batch_id=trace_batch_id,
                error_code="post_processing_task_failed",
                error_summary=str(exc),
                source_batch_id=int(request.source_batch_id),
            )
            uow.commit()
        raise
