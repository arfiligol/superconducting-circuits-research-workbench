"""Startup reconcile helpers shared by task runtime entrypoints."""

from __future__ import annotations

import logging
import os
from datetime import timedelta

from core.shared.persistence import get_unit_of_work
from core.shared.persistence.models import utc_now
from core.shared.persistence.reconcile import ReconcileSummary, reconcile_stale_tasks_and_batches

logger = logging.getLogger(__name__)

def default_stale_timeout_seconds() -> int:
    """Return the safe startup reconcile timeout from environment."""
    raw_value = os.getenv("SC_TASK_STALE_TIMEOUT_SECONDS", "300").strip()
    return max(1, int(raw_value or "300"))


def run_startup_reconcile(
    *,
    source: str,
    stale_after_seconds: int | None = None,
) -> ReconcileSummary:
    """Run the safe startup reconcile pass and log one compact summary."""
    timeout_seconds = (
        default_stale_timeout_seconds()
        if stale_after_seconds is None
        else max(1, int(stale_after_seconds))
    )
    stale_before = utc_now() - timedelta(seconds=timeout_seconds)
    with get_unit_of_work() as uow:
        summary = reconcile_stale_tasks_and_batches(uow, stale_before=stale_before)
    logger.info(
        "%s startup reconcile stale_before=%s stale_tasks=%s failed_batches=%s "
        "orphan_batches=%s deleted_store_keys=%s",
        source,
        stale_before.isoformat(),
        summary.stale_task_ids,
        summary.failed_batch_ids,
        summary.orphan_batch_ids,
        summary.deleted_store_keys,
    )
    return summary
