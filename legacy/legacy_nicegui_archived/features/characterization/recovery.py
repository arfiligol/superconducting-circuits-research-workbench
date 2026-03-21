"""Persisted task/result recovery helpers for the WS8 characterization page."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from legacy.legacy_nicegui_archived.api.schemas import (
    DesignTasksResponse,
    LatestCharacterizationResponse,
    TaskResponse,
)

_LONG_RUNNING_WARN_AFTER_SECONDS = 60


def _utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


@dataclass(frozen=True)
class CharacterizationRecoveryState:
    """Recovered persisted characterization authority for one design."""

    task: TaskResponse | None
    latest_result: LatestCharacterizationResponse | None
    should_poll: bool
    long_running_warning: bool


def latest_characterization_task(tasks_response: DesignTasksResponse) -> TaskResponse | None:
    """Return the newest characterization task from one design-task listing."""
    for task in tasks_response.tasks:
        if task.task_kind == "characterization":
            return task
    return None


def build_recovery_state(
    *,
    tasks_response: DesignTasksResponse,
    latest_result: LatestCharacterizationResponse | None,
    now: datetime | None = None,
) -> CharacterizationRecoveryState:
    """Resolve polling/recovery authority for one characterization page refresh."""
    task = latest_characterization_task(tasks_response)
    current_now = now or _utcnow()
    should_poll = task is not None and task.status in {"queued", "running"}
    long_running_warning = False
    if task is not None and task.status == "running" and task.started_at is not None:
        long_running_warning = (
            current_now - task.started_at
        ).total_seconds() >= _LONG_RUNNING_WARN_AFTER_SECONDS
    return CharacterizationRecoveryState(
        task=task,
        latest_result=latest_result,
        should_poll=should_poll,
        long_running_warning=long_running_warning,
    )
