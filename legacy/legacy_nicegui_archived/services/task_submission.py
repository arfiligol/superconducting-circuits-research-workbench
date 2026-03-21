"""Persisted task submission helpers for API-authenticated callers."""

from __future__ import annotations

import json
from dataclasses import dataclass
from hashlib import sha256
from typing import Any

from core.shared.persistence import get_unit_of_work
from core.shared.persistence.models import DesignRecord, TaskRecord
from legacy.legacy_nicegui_archived.services.characterization_runner import (
    create_pending_analysis_run,
)
from legacy.legacy_nicegui_archived.services.characterization_task_contract import (
    extract_characterization_request_from_api_payload,
)
from legacy.legacy_nicegui_archived.services.execution_context import ActorContext, UseCaseContext
from legacy.legacy_nicegui_archived.services.post_processing_batch_persistence import (
    create_pending_post_processing_batch,
)
from legacy.legacy_nicegui_archived.services.post_processing_task_contract import (
    extract_post_processing_request_from_api_payload,
)
from legacy.legacy_nicegui_archived.services.simulation_batch_persistence import (
    create_pending_simulation_batch,
)
from legacy.legacy_nicegui_archived.services.simulation_task_contract import (
    extract_simulation_request_from_api_payload,
)

from worker.dispatch import DispatchedWorkerTask, TaskSubmissionKind, enqueue_task


@dataclass(frozen=True)
class SubmittedTask:
    """API-facing result of one task submission attempt."""

    task: TaskRecord
    dispatch: DispatchedWorkerTask
    dedupe_hit: bool


def _detach_task(task: TaskRecord) -> TaskRecord:
    """Return a detached copy of one persisted task record."""
    return TaskRecord(
        id=task.id,
        task_kind=task.task_kind,
        status=task.status,
        design_id=task.design_id,
        trace_batch_id=task.trace_batch_id,
        analysis_run_id=task.analysis_run_id,
        requested_by=task.requested_by,
        actor_id=task.actor_id,
        dedupe_key=task.dedupe_key,
        request_payload=dict(task.request_payload),
        progress_payload=dict(task.progress_payload),
        result_summary_payload=dict(task.result_summary_payload),
        error_payload=dict(task.error_payload),
        created_at=task.created_at,
        started_at=task.started_at,
        heartbeat_at=task.heartbeat_at,
        completed_at=task.completed_at,
    )


def _stable_json_payload(payload: dict[str, Any]) -> str:
    """Return one stable JSON string for dedupe-key derivation."""
    return json.dumps(payload, separators=(",", ":"), sort_keys=True, ensure_ascii=True)


def _build_dedupe_key(
    *,
    task_kind: TaskSubmissionKind,
    design_id: int,
    normalized_payload: dict[str, Any],
) -> str:
    """Build one stable soft-dedupe key for a task submission request."""
    canonical = _stable_json_payload(
        {
            "task_kind": task_kind,
            "design_id": int(design_id),
            "request": normalized_payload,
        }
    )
    return f"sha256:{sha256(canonical.encode('utf-8')).hexdigest()}"


def create_api_task(
    *,
    task_kind: TaskSubmissionKind,
    design_id: int,
    request_payload: dict[str, Any],
    actor: ActorContext,
    force_rerun: bool,
    source: str = "api",
) -> SubmittedTask:
    """Create one persisted task record and enqueue it on the frozen worker lane."""
    context = UseCaseContext(
        actor=actor,
        source=source,
        force_rerun=bool(force_rerun),
        metadata={"task_kind": task_kind, "design_id": int(design_id)},
    )
    normalized_request_payload = dict(request_payload)
    dedupe_key = _build_dedupe_key(
        task_kind=task_kind,
        design_id=design_id,
        normalized_payload=normalized_request_payload,
    )

    with get_unit_of_work() as uow:
        design = uow.datasets.get(design_id)
        if design is None:
            raise ValueError(f"Design ID {design_id} not found.")

        if not force_rerun:
            existing = uow.tasks.find_active_by_dedupe_key(dedupe_key)
            if existing is not None:
                dispatch = _dispatch_metadata_for_task(existing)
                uow.audit_logs.append_log(
                    actor_id=actor.actor_id,
                    action_kind="task.dedupe_reused",
                    resource_kind="task",
                    resource_id=existing.id or 0,
                    summary=(
                        f"Reused active {task_kind} task {existing.id} for design {design_id}."
                    ),
                    payload={"dedupe_key": dedupe_key, "task_kind": task_kind},
                )
                uow.commit()
                return SubmittedTask(
                    task=_detach_task(existing),
                    dispatch=dispatch,
                    dedupe_hit=True,
                )

        persisted_request_payload = {
            "task_kind": task_kind,
            "design_id": int(design_id),
            "parameters": normalized_request_payload,
            "context": context.to_payload(),
        }
        trace_batch_id: int | None = None
        simulation_request = (
            extract_simulation_request_from_api_payload(dict(normalized_request_payload))
            if task_kind == "simulation"
            else None
        )
        post_processing_request = (
            extract_post_processing_request_from_api_payload(dict(normalized_request_payload))
            if task_kind == "post_processing"
            else None
        )
        characterization_request = (
            extract_characterization_request_from_api_payload(dict(normalized_request_payload))
            if task_kind == "characterization"
            else None
        )
        analysis_run_id: int | None = None
        if simulation_request is not None:
            pending_batch = create_pending_simulation_batch(
                uow=uow,
                design_id=int(design_id),
                source_meta=simulation_request.source_meta,
                config_snapshot=simulation_request.config_snapshot,
                schema_source_hash=simulation_request.schema_source_hash,
                simulation_setup_hash=simulation_request.simulation_setup_hash,
                sweep_setup_hash=simulation_request.sweep_setup_hash,
            )
            trace_batch_id = int(pending_batch.id or 0)
        elif post_processing_request is not None:
            pending_batch = create_pending_post_processing_batch(
                uow=uow,
                design_id=int(design_id),
                source_batch_id=int(post_processing_request.source_batch_id),
                input_source=post_processing_request.input_source,
                mode_filter=post_processing_request.mode_filter,
                mode_token=post_processing_request.mode_token,
                reference_impedance_ohm=post_processing_request.reference_impedance_ohm,
                step_sequence=post_processing_request.step_sequence,
            )
            trace_batch_id = int(pending_batch.id or 0)
        elif characterization_request is not None:
            pending_analysis_run = create_pending_analysis_run(
                characterization_request.to_run_request(),
                selected_trace_ids=characterization_request.trace_record_ids,
                uow=uow,
            )
            analysis_run_id = int(pending_analysis_run.id or 0)
        task = uow.tasks.create_task(
            task_kind=task_kind,
            design_id=design_id,
            request_payload=persisted_request_payload,
            requested_by=context.requested_by,
            actor_id=actor.actor_id,
            dedupe_key=None if force_rerun else dedupe_key,
            trace_batch_id=trace_batch_id,
            analysis_run_id=analysis_run_id,
        )
        uow.audit_logs.append_log(
            actor_id=actor.actor_id,
            action_kind="task.requested",
            resource_kind="task",
            resource_id=task.id or 0,
            summary=f"Requested {task_kind} task for design {design_id}.",
            payload={
                "task_kind": task_kind,
                "design_id": int(design_id),
                "force_rerun": bool(force_rerun),
                "dedupe_key": None if force_rerun else dedupe_key,
            },
        )
        uow.commit()
        detached_task = _detach_task(task)

    if detached_task.id is None:
        raise ValueError("Task submission did not produce a persisted task ID.")
    dispatch = enqueue_task(
        task_kind,
        task_id=int(detached_task.id),
        request_payload=dict(detached_task.request_payload),
        trace_batch_id=detached_task.trace_batch_id,
    )
    return SubmittedTask(task=detached_task, dispatch=dispatch, dedupe_hit=False)


def _dispatch_metadata_for_task(task: TaskRecord) -> DispatchedWorkerTask:
    """Return static dispatch metadata without enqueueing a new task."""
    if task.task_kind == "simulation":
        simulation_request = extract_simulation_request_from_api_payload(
            dict(task.request_payload.get("parameters", {}))
        )
        if simulation_request is not None and task.trace_batch_id is not None:
            return _build_dispatch_metadata(
                lane="simulation",
                worker_task_name="simulation_run_task",
                execution_mode="run",
                request_ready=True,
                requires_trace_batch=True,
            )
        return _build_dispatch_metadata(
            lane="simulation",
            worker_task_name="simulation_probe_task",
            execution_mode="probe",
            request_ready=False,
            requires_trace_batch=True,
        )
    if task.task_kind == "post_processing":
        post_processing_request = extract_post_processing_request_from_api_payload(
            dict(task.request_payload.get("parameters", {}))
        )
        if post_processing_request is not None and task.trace_batch_id is not None:
            return _build_dispatch_metadata(
                lane="simulation",
                worker_task_name="post_processing_run_task",
                execution_mode="run",
                request_ready=True,
                requires_trace_batch=True,
            )
        return _build_dispatch_metadata(
            lane="simulation",
            worker_task_name="post_processing_probe_task",
            execution_mode="probe",
            request_ready=False,
            requires_trace_batch=True,
        )
    if task.task_kind == "characterization":
        characterization_request = extract_characterization_request_from_api_payload(
            dict(task.request_payload.get("parameters", {}))
        )
        if characterization_request is not None and task.analysis_run_id is not None:
            return _build_dispatch_metadata(
                lane="characterization",
                worker_task_name="characterization_run_task",
                execution_mode="run",
                request_ready=True,
                requires_trace_batch=False,
            )
        return _build_dispatch_metadata(
            lane="characterization",
            worker_task_name="characterization_probe_task",
            execution_mode="probe",
            request_ready=False,
            requires_trace_batch=False,
        )
    raise ValueError(f"Unsupported task kind '{task.task_kind}'.")


def _build_dispatch_metadata(
    *,
    lane: str,
    worker_task_name: str,
    execution_mode: str,
    request_ready: bool,
    requires_trace_batch: bool,
) -> DispatchedWorkerTask:
    return DispatchedWorkerTask(
        lane=lane,
        queue_name=lane,
        worker_task_name=worker_task_name,
        execution_mode=execution_mode,
        request_ready=request_ready,
        requires_trace_batch=requires_trace_batch,
    )


def require_design(design_id: int) -> DesignRecord:
    """Load one design or raise if it does not exist."""
    with get_unit_of_work() as uow:
        design = uow.datasets.get(design_id)
        if design is None:
            raise ValueError(f"Design ID {design_id} not found.")
        return design
