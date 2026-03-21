"""Persisted latest-result lookup helpers for `/api/v1` surfaces."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from core.shared.persistence import get_unit_of_work
from core.shared.persistence.models import AnalysisRunRecord, TaskRecord
from core.shared.persistence.repositories.contracts import TraceBatchSnapshot


@dataclass(frozen=True)
class LatestTraceBatchArtifact:
    """Latest persisted trace-producing artifact under one design."""

    batch: TraceBatchSnapshot
    task: TaskRecord | None


@dataclass(frozen=True)
class LatestCharacterizationArtifact:
    """Latest persisted characterization run under one design."""

    analysis_run: AnalysisRunRecord
    task: TaskRecord | None


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


def _latest_timestamp(*, created_at: datetime | None, completed_at: datetime | None) -> datetime:
    """Return the latest meaningful timestamp for ordering."""
    if completed_at is not None:
        return completed_at
    if created_at is not None:
        return created_at
    return datetime.min


def _match_batch_kind(snapshot: TraceBatchSnapshot, *, source_kind: str, stage_kind: str) -> bool:
    return (
        str(snapshot["source_kind"]).strip() == source_kind
        and str(snapshot["stage_kind"]).strip() == stage_kind
        and str(snapshot["status"]).strip() == "completed"
    )


def latest_simulation_result(design_id: int) -> LatestTraceBatchArtifact | None:
    """Return the newest completed raw-simulation artifact."""
    return _latest_trace_batch(
        design_id=design_id,
        source_kind="circuit_simulation",
        stage_kind="raw",
        task_kind="simulation",
    )


def latest_post_processing_result(design_id: int) -> LatestTraceBatchArtifact | None:
    """Return the newest completed post-processing artifact."""
    return _latest_trace_batch(
        design_id=design_id,
        source_kind="circuit_simulation",
        stage_kind="postprocess",
        task_kind="post_processing",
    )


def _latest_trace_batch(
    *,
    design_id: int,
    source_kind: str,
    stage_kind: str,
    task_kind: str,
) -> LatestTraceBatchArtifact | None:
    with get_unit_of_work() as uow:
        latest_snapshot: TraceBatchSnapshot | None = None
        latest_sort_key = datetime.min
        for batch in uow.result_bundles.list_provenance_by_design(design_id):
            if batch.id is None:
                continue
            snapshot = uow.result_bundles.get_trace_batch_snapshot(int(batch.id))
            if snapshot is None or not _match_batch_kind(
                snapshot,
                source_kind=source_kind,
                stage_kind=stage_kind,
            ):
                continue
            sort_key = _latest_timestamp(
                created_at=getattr(batch, "created_at", None),
                completed_at=getattr(batch, "completed_at", None),
            )
            if sort_key >= latest_sort_key:
                latest_snapshot = snapshot
                latest_sort_key = sort_key

        if latest_snapshot is None:
            return None

        latest_task = uow.tasks.get_latest_task_by_kind(design_id, task_kind)
        if (
            latest_task is not None
            and latest_task.trace_batch_id is not None
            and int(latest_task.trace_batch_id) != int(latest_snapshot["id"])
        ):
            latest_task = None
        return LatestTraceBatchArtifact(
            batch=latest_snapshot,
            task=_detach_task(latest_task) if latest_task is not None else None,
        )


def latest_characterization_result(design_id: int) -> LatestCharacterizationArtifact | None:
    """Return the newest persisted characterization run for one design."""
    with get_unit_of_work() as uow:
        runs = [
            run
            for run in uow.result_bundles.analysis_runs.list_by_design(design_id)
            if str(run.status).strip() == "completed"
        ]
        if not runs:
            return None
        latest_run = max(
            runs,
            key=lambda run: _latest_timestamp(
                created_at=getattr(run, "created_at", None),
                completed_at=getattr(run, "completed_at", None),
            ),
        )
        latest_task = uow.tasks.get_latest_task_by_kind(design_id, "characterization")
        if (
            latest_task is not None
            and latest_task.analysis_run_id is not None
            and latest_run.id is not None
            and int(latest_task.analysis_run_id) != int(latest_run.id)
        ):
            latest_task = None
        return LatestCharacterizationArtifact(
            analysis_run=latest_run,
            task=_detach_task(latest_task) if latest_task is not None else None,
        )


def require_task(task_id: int) -> TaskRecord:
    """Load one persisted task or raise if absent."""
    with get_unit_of_work() as uow:
        task = uow.tasks.get_task(task_id)
        if task is None:
            raise ValueError(f"Task ID {task_id} not found.")
        return _detach_task(task)


def list_design_tasks(design_id: int) -> list[TaskRecord]:
    """List persisted tasks under one design, newest first."""
    with get_unit_of_work() as uow:
        design = uow.datasets.get(design_id)
        if design is None:
            raise ValueError(f"Design ID {design_id} not found.")
        return [_detach_task(task) for task in uow.tasks.list_tasks_by_design(design_id)]


def list_audit_logs(*, actor_id: int | None = None) -> list[Any]:
    """List audit logs, optionally filtered by actor."""
    with get_unit_of_work() as uow:
        if actor_id is None:
            return uow.audit_logs.list_logs()
        return uow.audit_logs.list_logs_by_actor(actor_id)
