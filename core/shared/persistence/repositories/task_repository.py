"""Repository for TaskRecord lifecycle operations."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from typing import Any

from sc_core.execution import (
    TaskCreationSpec,
    TaskExecutionOperation,
    TaskExecutionTransition,
    TaskLifecycleMutation,
    TaskResultHandle,
    build_task_completed_mutation,
    build_task_creation_spec,
    build_task_failed_mutation,
    build_task_heartbeat_operation,
    build_task_queued_transition,
    build_task_running_mutation,
    normalize_task_dedupe_key,
)
from sc_core.storage import TraceResultLinkage
from sqlalchemy import desc, or_
from sqlmodel import Session, col, select

from core.shared.persistence.models import TaskRecord, utc_now

_ACTIVE_TASK_STATUSES = ("queued", "running")


def _normalize_status_filter(
    status_filter: str | Sequence[str] | None,
) -> list[str]:
    """Normalize optional task-status filters into concrete strings."""
    if status_filter is None:
        return []
    if isinstance(status_filter, str):
        normalized = status_filter.strip()
        return [normalized] if normalized else []
    return [status.strip() for status in status_filter if status.strip()]


class TaskRepository:
    """Repository for persisted task lifecycle state."""

    def __init__(self, session: Session):
        self._session = session

    def _require_task(self, task_id: int) -> TaskRecord:
        task = self._session.get(TaskRecord, task_id)
        if task is None:
            raise ValueError(f"Task ID {task_id} not found.")
        return task

    def _apply_task_mutation(self, task: TaskRecord, mutation: TaskLifecycleMutation) -> None:
        if mutation.status is not None:
            task.status = mutation.status
        if mutation.started_at is not None:
            task.started_at = mutation.started_at
        if mutation.heartbeat_at is not None:
            task.heartbeat_at = mutation.heartbeat_at
        if mutation.completed_at is not None:
            task.completed_at = mutation.completed_at
        if mutation.progress_payload is not None:
            task.progress_payload = dict(mutation.progress_payload)
        if mutation.result_summary_payload is not None:
            task.result_summary_payload = dict(mutation.result_summary_payload)
        if mutation.error_payload is not None:
            task.error_payload = dict(mutation.error_payload)
        if mutation.result_handle is not None:
            task.trace_batch_id = mutation.result_handle.trace_batch_id
            task.analysis_run_id = mutation.result_handle.analysis_run_id

    def _result_handle_from_inputs(
        self,
        result_linkage: TraceResultLinkage | int | None,
        *,
        analysis_run_id: int | None = None,
    ) -> TaskResultHandle:
        if isinstance(result_linkage, TraceResultLinkage):
            if analysis_run_id is not None:
                raise ValueError(
                    "analysis_run_id cannot be combined with TraceResultLinkage inputs."
                )
            return result_linkage.to_result_handle()
        return TaskResultHandle(
            trace_batch_id=result_linkage,
            analysis_run_id=analysis_run_id,
        )

    def create_task(
        self,
        task_kind: str,
        design_id: int,
        request_payload: dict[str, Any],
        requested_by: str,
        *,
        actor_id: int | None = None,
        dedupe_key: str | None = None,
        trace_batch_id: int | None = None,
        analysis_run_id: int | None = None,
    ) -> TaskRecord:
        """Create and flush one queued task record."""
        return self.create_task_from_spec(
            build_task_creation_spec(
                task_kind=task_kind,
                design_id=design_id,
                request_payload=request_payload,
                requested_by=requested_by,
                actor_id=actor_id,
                dedupe_key=dedupe_key,
                result_handle=TaskResultHandle(
                    trace_batch_id=trace_batch_id,
                    analysis_run_id=analysis_run_id,
                ),
            )
        )

    def create_task_from_spec(self, spec: TaskCreationSpec) -> TaskRecord:
        """Create and flush one queued task record from the canonical creation spec."""
        queued_transition = build_task_queued_transition(creation_spec=spec)
        task = TaskRecord(
            task_kind=spec.task_kind,
            status="queued",
            design_id=spec.design_id,
            requested_by=spec.requested_by,
            actor_id=spec.actor_id,
            dedupe_key=spec.dedupe_key,
            request_payload=dict(spec.request_payload),
        )
        self._apply_task_mutation(task, queued_transition.mutation)
        self._session.add(task)
        self._session.flush()
        return task

    def apply_lifecycle_mutation(self, task_id: int, mutation: TaskLifecycleMutation) -> None:
        """Apply one canonical lifecycle mutation to a persisted task record."""
        task = self._require_task(task_id)
        self._apply_task_mutation(task, mutation)
        self._session.add(task)
        self._session.flush()

    def apply_execution_transition(
        self,
        task_id: int,
        transition: TaskExecutionTransition,
    ) -> None:
        """Apply one canonical orchestration transition to a persisted task record."""
        self.apply_lifecycle_mutation(task_id, transition.mutation)

    def apply_execution_operation(self, operation: TaskExecutionOperation) -> None:
        """Apply one canonical persisted-task operation to the stored task row."""
        self.apply_execution_transition(operation.task_id, operation.transition)

    def mark_running(self, task_id: int) -> None:
        """Mark one task as running and stamp start/heartbeat timestamps."""
        self.apply_lifecycle_mutation(
            task_id,
            build_task_running_mutation(recorded_at=utc_now()),
        )

    def heartbeat(self, task_id: int, progress_payload: dict[str, Any]) -> None:
        """Persist one task heartbeat and progress snapshot."""
        self.apply_execution_operation(
            build_task_heartbeat_operation(
                task_id=task_id,
                recorded_at=utc_now(),
                progress_payload=progress_payload,
            ),
        )

    def mark_completed(
        self,
        task_id: int,
        result_linkage: TraceResultLinkage | int | None,
        result_summary_payload: dict[str, Any],
        *,
        analysis_run_id: int | None = None,
    ) -> None:
        """Mark one task as completed and link its persisted outputs."""
        self.apply_lifecycle_mutation(
            task_id,
            build_task_completed_mutation(
                recorded_at=utc_now(),
                result_summary_payload=result_summary_payload,
                result_handle=self._result_handle_from_inputs(
                    result_linkage,
                    analysis_run_id=analysis_run_id,
                ),
            ),
        )

    def mark_failed(self, task_id: int, error_payload: dict[str, Any]) -> None:
        """Mark one task as failed and persist structured error details."""
        self.apply_lifecycle_mutation(
            task_id,
            build_task_failed_mutation(
                recorded_at=utc_now(),
                error_payload=error_payload,
            ),
        )

    def get_task(self, task_id: int) -> TaskRecord | None:
        """Load one task by ID."""
        return self._session.get(TaskRecord, task_id)

    def list_tasks_by_design(
        self,
        design_id: int,
        status_filter: str | Sequence[str] | None = None,
    ) -> list[TaskRecord]:
        """List tasks for one design, newest first, with optional status filter."""
        statement = select(TaskRecord).where(col(TaskRecord.design_id) == design_id)
        normalized_statuses = _normalize_status_filter(status_filter)
        if normalized_statuses:
            statement = statement.where(col(TaskRecord.status).in_(normalized_statuses))
        statement = statement.order_by(desc(col(TaskRecord.created_at)), desc(col(TaskRecord.id)))
        return list(self._session.exec(statement).all())

    def get_latest_task_by_kind(self, design_id: int, task_kind: str) -> TaskRecord | None:
        """Get the newest task of one kind under one design."""
        statement = (
            select(TaskRecord)
            .where(col(TaskRecord.design_id) == design_id)
            .where(col(TaskRecord.task_kind) == task_kind)
            .order_by(desc(col(TaskRecord.created_at)), desc(col(TaskRecord.id)))
        )
        return self._session.exec(statement).first()

    def find_active_by_dedupe_key(self, dedupe_key: str) -> TaskRecord | None:
        """Find one queued/running task by its dedupe key."""
        normalized_key = normalize_task_dedupe_key(dedupe_key)
        if normalized_key is None:
            return None
        statement = (
            select(TaskRecord)
            .where(col(TaskRecord.dedupe_key) == normalized_key)
            .where(col(TaskRecord.status).in_(_ACTIVE_TASK_STATUSES))
            .order_by(desc(col(TaskRecord.created_at)), desc(col(TaskRecord.id)))
        )
        return self._session.exec(statement).first()

    def find_active_for_trace_batch(self, trace_batch_id: int) -> TaskRecord | None:
        """Find one queued/running task linked to a specific trace batch."""
        statement = (
            select(TaskRecord)
            .where(col(TaskRecord.trace_batch_id) == trace_batch_id)
            .where(col(TaskRecord.status).in_(_ACTIVE_TASK_STATUSES))
            .order_by(desc(col(TaskRecord.created_at)), desc(col(TaskRecord.id)))
        )
        return self._session.exec(statement).first()

    def list_stale_running_tasks(self, before_heartbeat_at: datetime) -> list[TaskRecord]:
        """List running tasks whose heartbeat is missing or older than the threshold."""
        statement = (
            select(TaskRecord)
            .where(col(TaskRecord.status) == "running")
            .where(
                or_(
                    col(TaskRecord.heartbeat_at).is_(None),
                    col(TaskRecord.heartbeat_at) < before_heartbeat_at,
                )
            )
            .order_by(col(TaskRecord.heartbeat_at), col(TaskRecord.id))
        )
        return list(self._session.exec(statement).all())
