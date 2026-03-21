"""Archived persisted-task submission helpers.

The legacy NiceGUI task queue path has been intentionally disabled while the
canonical backend worker-isolation implementation is rebuilt.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from core.shared.persistence import get_unit_of_work
from core.shared.persistence.models import DesignRecord, TaskRecord
from legacy.legacy_nicegui_archived.services.execution_context import ActorContext

TaskSubmissionKind = str
_ARCHIVED_TASK_QUEUE_DISABLED_MESSAGE = (
    "Archived NiceGUI task submission is disabled. "
    "Use the canonical backend task workflow instead."
)


@dataclass(frozen=True)
class ArchivedDispatchRecord:
    """Compatibility-only dispatch placeholder for the archived API surface."""

    lane: str
    worker_task_name: str


@dataclass(frozen=True)
class SubmittedTask:
    """API-facing result of one task submission attempt."""

    task: TaskRecord
    dispatch: ArchivedDispatchRecord
    dedupe_hit: bool


def create_api_task(
    *,
    task_kind: TaskSubmissionKind,
    design_id: int,
    request_payload: dict[str, Any],
    actor: ActorContext,
    force_rerun: bool,
    source: str = "api",
) -> SubmittedTask:
    """Reject archived NiceGUI task submission until canonical worker isolation lands."""
    _ = (task_kind, design_id, request_payload, actor, force_rerun, source)
    raise RuntimeError(_ARCHIVED_TASK_QUEUE_DISABLED_MESSAGE)


def require_design(design_id: int) -> DesignRecord:
    """Load one design or raise if it does not exist."""
    with get_unit_of_work() as uow:
        design = uow.datasets.get(design_id)
        if design is None:
            raise ValueError(f"Design ID {design_id} not found.")
        return design
