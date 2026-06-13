"""Persistence-level reconcile helpers for stale tasks and incomplete trace batches."""

from __future__ import annotations

import shutil
from dataclasses import dataclass, field
from datetime import datetime
from typing import Final, cast

from app_backend.domain.runtime_contracts.execution import (
    STALE_TASK_TIMEOUT_ERROR_CODE,
    build_reconcile_batch_failed_event,
    build_reconcile_stale_task_operation,
)
from app_backend.infrastructure.local_store.models import TraceBatchRecord, utc_now
from app_backend.infrastructure.local_store.trace_store import (
    LocalZarrTraceStoreBackend,
    get_trace_store_backend_binding,
)
from app_backend.infrastructure.local_store.unit_of_work import SqliteUnitOfWork

_STALE_TASK_RECONCILE_REASON: Final[str] = STALE_TASK_TIMEOUT_ERROR_CODE
_ORPHAN_BATCH_RECONCILE_REASON: Final[str] = "orphan_incomplete_batch"


@dataclass(frozen=True)
class ReconcileSummary:
    """Structured summary for one reconcile pass."""

    stale_task_ids: list[int] = field(default_factory=list)
    failed_batch_ids: list[int] = field(default_factory=list)
    orphan_batch_ids: list[int] = field(default_factory=list)
    deleted_store_keys: list[str] = field(default_factory=list)
    audit_log_ids: list[int] = field(default_factory=list)


def _extract_store_keys(batch: TraceBatchRecord) -> list[str]:
    """Collect local trace-store keys referenced by one batch payload."""
    result_payload = batch.result_payload if isinstance(batch.result_payload, dict) else {}
    trace_records = result_payload.get("trace_records")
    if not isinstance(trace_records, list):
        return []

    keys: list[str] = []
    for record in trace_records:
        if not isinstance(record, dict):
            continue
        store_ref = record.get("store_ref")
        if not isinstance(store_ref, dict):
            continue
        store_key = store_ref.get("store_key")
        backend = str(store_ref.get("backend", "")).strip()
        if not isinstance(store_key, str) or not store_key.strip():
            continue
        if backend and backend != "local_zarr":
            continue
        keys.append(store_key.strip())
    return sorted(set(keys))


def _cleanup_store_keys(store_keys: list[str]) -> list[str]:
    """Delete local trace-store directories for known store keys."""
    if not store_keys:
        return []
    binding = cast(
        LocalZarrTraceStoreBackend,
        get_trace_store_backend_binding(backend="local_zarr"),
    )
    deleted: list[str] = []
    for store_key in store_keys:
        store_path = binding.resolve_store_path(store_key=store_key)
        if store_path.exists():
            shutil.rmtree(store_path)
            deleted.append(store_key)
    return deleted


def _reconcile_summary_payload(*, reason: str, stale_before: datetime) -> dict[str, str]:
    """Return the small reconcile-only summary payload merged into batch metadata."""
    return {
        "reconcile_reason": reason,
        "reconcile_stale_before": stale_before.isoformat(),
    }


def _persist_task_reconcile_operation(
    uow: SqliteUnitOfWork,
    *,
    task_id: int,
    recorded_at: datetime,
    stale_before: datetime,
) -> int | None:
    operation = build_reconcile_stale_task_operation(
        task_id=task_id,
        recorded_at=recorded_at,
        stale_before=stale_before,
    )
    uow.tasks.apply_execution_operation(operation)
    log = uow.audit_logs.append_execution_operation(operation)
    if log is None or log.id is None:
        return None
    return int(log.id)


def reconcile_stale_tasks_and_batches(
    uow: SqliteUnitOfWork,
    *,
    stale_before: datetime,
) -> ReconcileSummary:
    """Mark stale tasks and orphaned incomplete batches as failed and clean safe stores."""
    stale_task_ids: list[int] = []
    failed_batch_ids: list[int] = []
    orphan_batch_ids: list[int] = []
    pending_store_keys: list[str] = []
    audit_log_ids: list[int] = []

    for task in uow.tasks.list_stale_running_tasks(stale_before):
        if task.id is None:
            continue
        stale_task_ids.append(int(task.id))
        related_batch = (
            uow.result_bundles.get(int(task.trace_batch_id))
            if task.trace_batch_id is not None
            else None
        )
        if related_batch is not None and str(related_batch.status) != "completed":
            pending_store_keys.extend(_extract_store_keys(related_batch))
            if related_batch.id is not None:
                related_batch_id = int(related_batch.id)
                uow.result_bundles.mark_failed(
                    related_batch_id,
                    summary_payload=_reconcile_summary_payload(
                        reason=_STALE_TASK_RECONCILE_REASON,
                        stale_before=stale_before,
                    ),
                )
                failed_batch_ids.append(related_batch_id)

        audit_log_id = _persist_task_reconcile_operation(
            uow,
            task_id=int(task.id),
            recorded_at=utc_now(),
            stale_before=stale_before,
        )
        if audit_log_id is not None:
            audit_log_ids.append(audit_log_id)

    for batch in uow.result_bundles.list_incomplete_batches():
        if batch.id is None:
            continue
        batch_id = int(batch.id)
        if uow.tasks.find_active_for_trace_batch(batch_id) is not None:
            continue
        if batch_id in failed_batch_ids:
            continue

        pending_store_keys.extend(_extract_store_keys(batch))
        uow.result_bundles.mark_failed(
            batch_id,
            summary_payload=_reconcile_summary_payload(
                reason=_ORPHAN_BATCH_RECONCILE_REASON,
                stale_before=stale_before,
            ),
        )
        orphan_batch_ids.append(batch_id)
        failed_batch_ids.append(batch_id)
        log = uow.audit_logs.append_execution_event(
            actor_id=None,
            event=build_reconcile_batch_failed_event(
                batch_id=batch_id,
                recorded_at=utc_now(),
                stale_before=stale_before,
            ),
        )
        if log.id is not None:
            audit_log_ids.append(int(log.id))

    try:
        uow.commit()
    except Exception:
        uow.rollback()
        raise

    deleted_store_keys = _cleanup_store_keys(sorted(set(pending_store_keys)))

    return ReconcileSummary(
        stale_task_ids=stale_task_ids,
        failed_batch_ids=failed_batch_ids,
        orphan_batch_ids=orphan_batch_ids,
        deleted_store_keys=sorted(set(deleted_store_keys)),
        audit_log_ids=audit_log_ids,
    )
