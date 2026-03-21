"""Real WS8 characterization worker execution over persisted TaskRecord inputs."""

from __future__ import annotations

import asyncio
from dataclasses import replace
from datetime import UTC, datetime

from sc_core.execution import build_task_heartbeat_operation

from legacy.legacy_nicegui_archived.services.characterization_runner import (
    execute_characterization_run_async,
    save_analysis_run_status,
)
from legacy.legacy_nicegui_archived.services.characterization_task_contract import PersistedCharacterizationTaskRequest
from legacy.legacy_nicegui_archived.services.task_progress import TaskProgressUpdate
from core.shared.persistence.unit_of_work import get_unit_of_work
from worker.runtime import TaskExecutionResult


def _utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def execute_characterization_task(task_id: int) -> TaskExecutionResult:
    """Execute one real WS8 characterization task and persist its lifecycle."""
    with get_unit_of_work() as uow:
        task = uow.tasks.get_task(task_id)
        if task is None:
            raise ValueError(f"Task ID {task_id} not found.")
        request_payload = task.request_payload.get("parameters", {})
        if not isinstance(request_payload, dict):
            raise ValueError("Persisted characterization task parameters are missing.")
        raw_request_payload = request_payload.get("request_payload", {})
        if not isinstance(raw_request_payload, dict):
            raise ValueError("Persisted characterization request payload is missing.")
        request = PersistedCharacterizationTaskRequest.from_payload(
            dict(raw_request_payload.get("characterization_request", {}))
        ).to_run_request()
        request = replace(
            request,
            context=replace(request.context, source="worker", task_id=task_id),
        )
        analysis_run_id = int(task.analysis_run_id) if task.analysis_run_id is not None else None
        if analysis_run_id is None:
            raise ValueError("Characterization task is missing analysis_run_id.")

    selected_trace_ids = tuple(int(trace_id) for trace_id in (request.trace_record_ids or ()))
    save_analysis_run_status(
        request,
        analysis_run_id=analysis_run_id,
        selected_trace_ids=selected_trace_ids,
        status="running",
        summary_payload={
            **dict(request.summary_payload),
            "phase": "running",
            "selected_trace_count": len(selected_trace_ids),
        },
    )

    def _handle_progress(update: TaskProgressUpdate) -> None:
        recorded_at = _utcnow()
        with get_unit_of_work() as uow:
            uow.tasks.apply_execution_operation(
                build_task_heartbeat_operation(
                    task_id=task_id,
                    recorded_at=recorded_at,
                    progress_payload=update.to_payload(
                        recorded_at=recorded_at,
                        extra={
                            "analysis_run_id": analysis_run_id,
                            "analysis_id": request.analysis_id,
                        },
                    ),
                )
            )
            uow.commit()

    try:
        result = asyncio.run(
            execute_characterization_run_async(
                request,
                progress_callback=_handle_progress,
                persist_analysis_run=True,
                analysis_run_id=analysis_run_id,
            )
        )
    except Exception as exc:
        save_analysis_run_status(
            request,
            analysis_run_id=analysis_run_id,
            selected_trace_ids=selected_trace_ids,
            status="failed",
            summary_payload={
                **dict(request.summary_payload),
                "phase": "failed",
                "selected_trace_count": len(selected_trace_ids),
                "error_code": "characterization_task_failed",
                "error_summary": str(exc),
            },
            completed_at=_utcnow(),
        )
        raise

    if result.analysis_run is None or result.analysis_run.id is None:
        raise ValueError("Characterization worker did not persist an analysis run.")

    return TaskExecutionResult(
        analysis_run_id=int(result.analysis_run.id),
        result_summary_payload={
            "analysis_run_id": int(result.analysis_run.id),
            "analysis_id": result.analysis_id,
            "selected_trace_count": len(result.selected_trace_ids),
            "selected_batch_count": len(result.selected_batch_ids),
            "trace_mode_group": result.trace_mode_group,
        },
    )
