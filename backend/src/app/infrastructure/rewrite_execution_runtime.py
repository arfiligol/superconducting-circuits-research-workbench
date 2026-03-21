from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from typing import Protocol

from sc_core.execution import (
    TaskExecutionResult,
    TaskExecutionTransition,
    TaskLifecycleMutation,
    build_reconcile_stale_task_transition,
    build_task_heartbeat_payload,
    build_task_heartbeat_transition,
    build_worker_completed_transition,
    build_worker_execution_context,
    build_worker_failed_transition,
    build_worker_running_transition,
)

from src.app.domain.audit import AuditRecord
from src.app.domain.tasks import (
    TaskDetail,
    TaskLifecycleUpdate,
    TaskResultRefs,
    build_task_lifecycle_event,
)
from src.app.infrastructure.rewrite_task_repository import PersistedRewriteTaskRepository
from src.app.services.service_errors import service_error
from src.app.services.task_service import TaskService


class TaskAuditRepository(Protocol):
    def append(self, record: AuditRecord) -> None: ...


class ProcessorRuntimeRepository(Protocol):
    def mark_task_running(
        self,
        task: TaskDetail,
        *,
        recorded_at: datetime,
        worker_pid: int | None = None,
        stale_after_seconds: int | None = None,
    ) -> None: ...

    def acknowledge_cancellation(
        self,
        task: TaskDetail,
        *,
        recorded_at: datetime,
        worker_pid: int | None = None,
    ) -> None: ...

    def acknowledge_termination(
        self,
        task: TaskDetail,
        *,
        recorded_at: datetime,
        worker_pid: int | None = None,
    ) -> None: ...

    def mark_task_terminal(
        self,
        task: TaskDetail,
        *,
        recorded_at: datetime,
        terminal_status: str,
    ) -> None: ...


class RewriteExecutionRuntime:
    def __init__(
        self,
        *,
        task_service: TaskService,
        task_repository: PersistedRewriteTaskRepository,
        audit_repository: TaskAuditRepository,
        processor_runtime_repository: ProcessorRuntimeRepository,
    ) -> None:
        self._task_service = task_service
        self._task_repository = task_repository
        self._audit_repository = audit_repository
        self._processor_runtime_repository = processor_runtime_repository

    def start_task(
        self,
        task_id: int,
        *,
        recorded_at: datetime,
        worker_pid: int | None = None,
        stale_after_seconds: int = 300,
    ) -> TaskDetail:
        task = self._get_task(task_id)
        _ensure_task_status(task, allowed_statuses=("queued", "dispatching"), action="start")
        transition = build_worker_running_transition(
            task_id=task_id,
            recorded_at=recorded_at,
            context=build_worker_execution_context(
                lane=task.lane,
                worker_task_name=task.worker_task_name,
                worker_pid=worker_pid,
            ),
            stale_after_seconds=stale_after_seconds,
        )
        updated_task = self._apply_transition(
            task,
            transition,
            progress_percent_complete=max(task.progress.percent_complete, 5),
        )
        self._processor_runtime_repository.mark_task_running(
            updated_task,
            recorded_at=recorded_at,
            worker_pid=worker_pid,
            stale_after_seconds=stale_after_seconds,
        )
        self._append_runtime_audit(
            task=updated_task,
            action_kind="worker.task_started",
            outcome="accepted",
            recorded_at=recorded_at,
            payload={
                "worker_pid": worker_pid,
                "stale_after_seconds": stale_after_seconds,
            },
        )
        return self._task_service.get_task(updated_task.task_id)

    def dispatch_task(
        self,
        task_id: int,
        *,
        recorded_at: datetime,
        worker_pid: int | None = None,
    ) -> TaskDetail:
        task = self._get_task(task_id)
        _ensure_task_status(task, allowed_statuses=("queued",), action="dispatch")
        updated_task = self._task_service.update_task_lifecycle(
            TaskLifecycleUpdate(
                task_id=task_id,
                status="dispatching",
                progress_percent_complete=0,
                progress_summary="Worker claimed the queued task from Redis.",
                progress_updated_at=recorded_at.isoformat(),
                summary=task.summary,
            )
        )
        self._merge_runtime_event_metadata(
            updated_task,
            {
                "audit_action": "worker.task_dispatched",
                "worker_pid": worker_pid,
            },
        )
        self._append_runtime_audit(
            task=updated_task,
            action_kind="worker.task_dispatched",
            outcome="accepted",
            recorded_at=recorded_at,
            payload={"worker_pid": worker_pid},
        )
        return self._task_service.get_task(updated_task.task_id)

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
        details: Mapping[str, object] | None = None,
        extra_payload: Mapping[str, object] | None = None,
    ) -> TaskDetail:
        task = self._get_task(task_id)
        _ensure_task_status(task, allowed_statuses=("running",), action="heartbeat")
        transition = build_task_heartbeat_transition(
            recorded_at=recorded_at,
            progress_payload=build_task_heartbeat_payload(
                summary=summary,
                recorded_at=recorded_at,
                stage_label=stage_label or task.worker_task_name,
                current_step=current_step,
                total_steps=total_steps,
                warning=warning,
                stale_after_seconds=stale_after_seconds,
                details=details,
                extra_payload=extra_payload,
            ),
        )
        updated_task = self._apply_transition(
            task,
            transition,
            progress_percent_complete=_resolve_running_percent_complete(
                task=task,
                explicit_percent_complete=percent_complete,
                current_step=current_step,
                total_steps=total_steps,
            ),
        )
        self._processor_runtime_repository.mark_task_running(
            updated_task,
            recorded_at=recorded_at,
            stale_after_seconds=stale_after_seconds,
        )
        return self._task_service.get_task(updated_task.task_id)

    def complete_task(
        self,
        task_id: int,
        *,
        recorded_at: datetime,
        result: TaskExecutionResult,
        result_refs: TaskResultRefs | None = None,
    ) -> TaskDetail:
        task = self._get_task(task_id)
        _ensure_task_status(task, allowed_statuses=("running",), action="complete")
        transition = build_worker_completed_transition(
            task_id=task_id,
            recorded_at=recorded_at,
            context=build_worker_execution_context(
                lane=task.lane,
                worker_task_name=task.worker_task_name,
            ),
            result=result,
        )
        updated_task = self._apply_transition(
            task,
            transition,
            progress_percent_complete=100,
            result_refs=result_refs,
        )
        self._processor_runtime_repository.mark_task_terminal(
            updated_task,
            recorded_at=recorded_at,
            terminal_status="completed",
        )
        self._append_runtime_audit(
            task=updated_task,
            action_kind="worker.task_completed",
            outcome="completed",
            recorded_at=recorded_at,
            payload={"result_ready": updated_task.result_refs.trace_payload is not None},
        )
        return self._task_service.get_task(updated_task.task_id)

    def fail_task(
        self,
        task_id: int,
        *,
        recorded_at: datetime,
        exc_type: str,
        message: str,
        worker_pid: int | None = None,
    ) -> TaskDetail:
        task = self._get_task(task_id)
        _ensure_task_status(
            task,
            allowed_statuses=("queued", "dispatching", "running"),
            action="fail",
        )
        transition = build_worker_failed_transition(
            task_id=task_id,
            recorded_at=recorded_at,
            context=build_worker_execution_context(
                lane=task.lane,
                worker_task_name=task.worker_task_name,
                worker_pid=worker_pid,
            ),
            exc_type=exc_type,
            message=message,
        )
        updated_task = self._apply_transition(
            task,
            transition,
            progress_percent_complete=task.progress.percent_complete,
        )
        self._processor_runtime_repository.mark_task_terminal(
            updated_task,
            recorded_at=recorded_at,
            terminal_status="failed",
        )
        self._append_runtime_audit(
            task=updated_task,
            action_kind="worker.task_failed",
            outcome="failed",
            recorded_at=recorded_at,
            payload={"exc_type": exc_type},
        )
        return self._task_service.get_task(updated_task.task_id)

    def reconcile_stale_task(
        self,
        task_id: int,
        *,
        recorded_at: datetime,
        stale_before: datetime,
    ) -> TaskDetail:
        task = self._get_task(task_id)
        _ensure_task_status(
            task,
            allowed_statuses=(
                "dispatching",
                "running",
                "cancellation_requested",
                "cancelling",
                "termination_requested",
            ),
            action="reconcile",
        )
        transition = build_reconcile_stale_task_transition(
            task_id=task_id,
            recorded_at=recorded_at,
            stale_before=stale_before,
        )
        updated_task = self._apply_transition(
            task,
            transition,
            progress_percent_complete=task.progress.percent_complete,
        )
        self._processor_runtime_repository.mark_task_terminal(
            updated_task,
            recorded_at=recorded_at,
            terminal_status="failed",
        )
        self._append_runtime_audit(
            task=updated_task,
            action_kind="reconcile.task_failed",
            outcome="failed",
            recorded_at=recorded_at,
            payload={"stale_before": stale_before.isoformat()},
        )
        return self._task_service.get_task(updated_task.task_id)

    def consume_control_request(
        self,
        task_id: int,
        *,
        recorded_at: datetime,
        worker_pid: int | None = None,
    ) -> TaskDetail:
        task = self._get_task(task_id)
        if task.status == "cancellation_requested":
            updated_task = self._task_service.update_task_lifecycle(
                TaskLifecycleUpdate(
                    task_id=task.task_id,
                    status="cancelling",
                    progress_percent_complete=task.progress.percent_complete,
                    progress_summary="Runtime acknowledged the cancellation request.",
                    progress_updated_at=recorded_at.isoformat(),
                    summary=task.summary,
                )
            )
            self._processor_runtime_repository.acknowledge_cancellation(
                updated_task,
                recorded_at=recorded_at,
                worker_pid=worker_pid,
            )
            self._merge_runtime_event_metadata(
                updated_task,
                {
                    "audit_action": "worker.task_cancellation_acknowledged",
                    "worker_pid": worker_pid,
                    "control_state": "cancelling",
                },
            )
            self._append_runtime_audit(
                task=updated_task,
                action_kind="worker.task_cancellation_acknowledged",
                outcome="accepted",
                recorded_at=recorded_at,
                payload={"worker_pid": worker_pid},
            )
            return self._task_service.get_task(updated_task.task_id)

        if task.status == "termination_requested":
            updated_task = self._task_service.update_task_lifecycle(
                TaskLifecycleUpdate(
                    task_id=task.task_id,
                    status="termination_requested",
                    progress_percent_complete=task.progress.percent_complete,
                    progress_summary="Runtime acknowledged the terminate request.",
                    progress_updated_at=recorded_at.isoformat(),
                    summary=task.summary,
                )
            )
            self._processor_runtime_repository.acknowledge_termination(
                updated_task,
                recorded_at=recorded_at,
                worker_pid=worker_pid,
            )
            self._merge_runtime_event_metadata(
                updated_task,
                {
                    "audit_action": "worker.task_termination_acknowledged",
                    "worker_pid": worker_pid,
                    "control_state": "termination_requested",
                },
            )
            self._append_runtime_audit(
                task=updated_task,
                action_kind="worker.task_termination_acknowledged",
                outcome="accepted",
                recorded_at=recorded_at,
                payload={"worker_pid": worker_pid},
            )
            return self._task_service.get_task(updated_task.task_id)

        raise service_error(
            409,
            code="task_control_request_not_pending",
            category="conflict",
            message=f"Task {task.task_id} has no pending control request to consume.",
        )

    def finalize_cancelled(
        self,
        task_id: int,
        *,
        recorded_at: datetime,
        summary: str | None = None,
    ) -> TaskDetail:
        task = self._get_task(task_id)
        _ensure_task_status(
            task,
            allowed_statuses=("cancellation_requested", "cancelling"),
            action="cancel",
        )
        updated_task = self._task_service.update_task_lifecycle(
            TaskLifecycleUpdate(
                task_id=task.task_id,
                status="cancelled",
                progress_percent_complete=task.progress.percent_complete,
                progress_summary=summary or "Task cancellation completed in the runtime.",
                progress_updated_at=recorded_at.isoformat(),
                summary=summary or "Task cancellation completed in the runtime.",
            )
        )
        self._processor_runtime_repository.mark_task_terminal(
            updated_task,
            recorded_at=recorded_at,
            terminal_status="cancelled",
        )
        self._merge_runtime_event_metadata(
            updated_task,
            {"audit_action": "worker.task_cancelled"},
        )
        self._append_runtime_audit(
            task=updated_task,
            action_kind="worker.task_cancelled",
            outcome="completed",
            recorded_at=recorded_at,
            payload={},
        )
        return self._task_service.get_task(updated_task.task_id)

    def finalize_terminated(
        self,
        task_id: int,
        *,
        recorded_at: datetime,
        summary: str | None = None,
    ) -> TaskDetail:
        task = self._get_task(task_id)
        _ensure_task_status(task, allowed_statuses=("termination_requested",), action="terminate")
        updated_task = self._task_service.update_task_lifecycle(
            TaskLifecycleUpdate(
                task_id=task.task_id,
                status="terminated",
                progress_percent_complete=task.progress.percent_complete,
                progress_summary=summary or "Task was force terminated by the runtime.",
                progress_updated_at=recorded_at.isoformat(),
                summary=summary or "Task was force terminated by the runtime.",
            )
        )
        self._processor_runtime_repository.mark_task_terminal(
            updated_task,
            recorded_at=recorded_at,
            terminal_status="terminated",
        )
        self._merge_runtime_event_metadata(
            updated_task,
            {"audit_action": "worker.task_terminated"},
        )
        self._append_runtime_audit(
            task=updated_task,
            action_kind="worker.task_terminated",
            outcome="completed",
            recorded_at=recorded_at,
            payload={},
        )
        return self._task_service.get_task(updated_task.task_id)

    def _apply_transition(
        self,
        current_task: TaskDetail,
        transition: TaskExecutionTransition,
        *,
        progress_percent_complete: int,
        result_refs: TaskResultRefs | None = None,
    ) -> TaskDetail:
        mutation = transition.mutation
        updated_task = self._task_service.update_task_lifecycle(
            TaskLifecycleUpdate(
                task_id=current_task.task_id,
                status=mutation.status or current_task.status,
                progress_percent_complete=progress_percent_complete,
                progress_summary=_resolve_progress_summary(
                    mutation=mutation,
                    fallback=current_task.progress.summary,
                ),
                progress_updated_at=_resolve_recorded_at(
                    mutation=mutation,
                    fallback=current_task.progress.updated_at,
                ),
                summary=_resolve_task_summary(
                    current_task=current_task,
                    next_status=mutation.status or current_task.status,
                    progress_summary=_resolve_progress_summary(
                        mutation=mutation,
                        fallback=current_task.progress.summary,
                    ),
                ),
                result_refs=result_refs,
            )
        )
        lifecycle_event = build_task_lifecycle_event(updated_task)
        if lifecycle_event is None:
            return updated_task
        self._task_repository.merge_task_event_metadata(
            updated_task.task_id,
            lifecycle_event.event_key,
            _build_transition_event_metadata(transition),
        )
        return self._task_service.get_task(updated_task.task_id)

    def _merge_runtime_event_metadata(
        self,
        task: TaskDetail,
        metadata: dict[str, object],
    ) -> None:
        if len(task.events) == 0:
            return
        self._task_repository.merge_task_event_metadata(
            task.task_id,
            task.events[-1].event_key,
            metadata,
        )

    def _append_runtime_audit(
        self,
        *,
        task: TaskDetail,
        action_kind: str,
        outcome: str,
        recorded_at: datetime,
        payload: dict[str, object],
    ) -> None:
        audit_suffix = recorded_at.isoformat().replace(":", "-").replace("+", "z")
        self._audit_repository.append(
            AuditRecord(
                audit_id=f"audit:{action_kind}:{task.task_id}:{audit_suffix}",
                occurred_at=recorded_at.isoformat(),
                actor_user_id=f"runtime:{task.lane}",
                actor_display_name="Rewrite Execution Runtime",
                session_id=f"runtime-session:{task.workspace_id}",
                correlation_id=f"corr:{action_kind}:{task.task_id}",
                workspace_id=task.workspace_id,
                action_kind=action_kind,
                resource_kind="task",
                resource_id=str(task.task_id),
                outcome=outcome,
                payload={
                    "task_status": task.status,
                    "lane": task.lane,
                    **payload,
                },
                debug_ref=f"debug:{action_kind}:{task.task_id}",
            )
        )

    def _get_task(self, task_id: int) -> TaskDetail:
        return self._task_service.get_task(task_id)


def _ensure_task_status(
    task: TaskDetail,
    *,
    allowed_statuses: tuple[str, ...],
    action: str,
) -> None:
    if task.status in allowed_statuses:
        return
    allowed = ", ".join(allowed_statuses)
    raise service_error(
        409,
        code="task_execution_transition_invalid",
        category="conflict",
        message=(
            f"Cannot {action} task {task.task_id} from status {task.status}; "
            f"allowed: {allowed}."
        ),
    )


def _resolve_progress_summary(
    *,
    mutation: TaskLifecycleMutation,
    fallback: str,
) -> str:
    for payload in (
        mutation.progress_payload,
        mutation.result_summary_payload,
        mutation.error_payload,
    ):
        if payload is None:
            continue
        summary = payload.get("summary")
        if isinstance(summary, str) and len(summary.strip()) > 0:
            return summary
    return fallback


def _resolve_recorded_at(
    *,
    mutation: TaskLifecycleMutation,
    fallback: str,
) -> str:
    for timestamp in (mutation.completed_at, mutation.heartbeat_at, mutation.started_at):
        if timestamp is not None:
            return timestamp.isoformat()
    for payload in (
        mutation.progress_payload,
        mutation.result_summary_payload,
        mutation.error_payload,
    ):
        if payload is None:
            continue
        recorded_at = payload.get("recorded_at")
        if isinstance(recorded_at, str) and len(recorded_at.strip()) > 0:
            return recorded_at
    return fallback


def _resolve_task_summary(
    *,
    current_task: TaskDetail,
    next_status: str,
    progress_summary: str,
) -> str:
    if next_status in {"completed", "failed", "cancelled", "terminated"}:
        return progress_summary
    return current_task.summary


def _resolve_running_percent_complete(
    *,
    task: TaskDetail,
    explicit_percent_complete: int | None,
    current_step: int | None,
    total_steps: int | None,
) -> int:
    if explicit_percent_complete is not None:
        return min(max(explicit_percent_complete, 1), 99)
    if current_step is not None and total_steps is not None and total_steps > 0:
        computed = int((current_step / total_steps) * 100)
        return min(max(computed, 1), 99)
    return min(max(task.progress.percent_complete, 1), 99)


def _build_transition_event_metadata(
    transition: TaskExecutionTransition,
) -> dict[str, object]:
    metadata: dict[str, object] = {}
    if transition.audit_action_kind is not None:
        metadata["audit_action"] = transition.audit_action_kind
    if transition.audit_summary is not None:
        metadata["audit_summary"] = transition.audit_summary
    _merge_safe_payload_metadata(metadata, transition.audit_payload)
    _merge_safe_payload_metadata(metadata, transition.mutation.progress_payload)
    _merge_safe_payload_metadata(metadata, transition.mutation.result_summary_payload)
    _merge_safe_payload_metadata(metadata, transition.mutation.error_payload)
    if transition.mutation.result_handle is not None:
        if transition.mutation.result_handle.trace_batch_id is not None:
            metadata["trace_batch_id"] = transition.mutation.result_handle.trace_batch_id
        if transition.mutation.result_handle.analysis_run_id is not None:
            metadata["analysis_run_id"] = transition.mutation.result_handle.analysis_run_id
    return metadata


def _merge_safe_payload_metadata(
    destination: dict[str, object],
    payload: Mapping[str, object] | None,
) -> None:
    if payload is None:
        return
    safe_keys = (
        "phase",
        "recorded_at",
        "stage_label",
        "current_step",
        "total_steps",
        "warning",
        "stale_after_seconds",
        "lane",
        "worker_task_name",
        "worker_pid",
        "started_at",
        "completed_at",
        "crash_requested_at",
        "error_code",
        "stale_before",
        "characterization_result_id",
        "characterization_result_summary",
        "characterization_result_detail",
        "characterization_run_history_row",
        "simulation_raw_bundle",
        "simulation_ptc_bundle",
        "post_processing_raw_bundle",
        "post_processing_ptc_bundle",
    )
    rename_map = {
        "phase": "execution_phase",
        "lane": "worker_lane",
    }
    for key in safe_keys:
        value = payload.get(key)
        if value is None:
            continue
        destination[rename_map.get(key, key)] = value
