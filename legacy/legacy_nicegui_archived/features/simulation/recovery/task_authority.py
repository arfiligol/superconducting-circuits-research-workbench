"""Task authority helpers for simulation recovery."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from legacy.legacy_nicegui_archived.api.schemas import DesignTasksResponse, LatestTraceBatchResponse, TaskResponse
from legacy.legacy_nicegui_archived.features.simulation.state import SimulationRuntimeState

_LONG_RUNNING_WARN_AFTER_SECONDS = 60

StatusAppender = Callable[[str, str], None]


def _utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


@dataclass(frozen=True)
class TaskRecoveryState:
    """Recovered persisted task authority for one design and task kind."""

    task: TaskResponse | None
    should_poll: bool
    long_running_warning: bool


@dataclass(frozen=True)
class SimulationRecoveryState:
    """Recovered persisted simulation authority for one design."""

    task: TaskResponse | None
    latest_result: LatestTraceBatchResponse | None
    should_poll: bool
    long_running_warning: bool


def latest_task_by_kind(
    tasks_response: DesignTasksResponse,
    *,
    task_kind: str,
) -> TaskResponse | None:
    """Return the newest task of one kind from one design-task listing."""
    for task in tasks_response.tasks:
        if task.task_kind == task_kind:
            return task
    return None


def latest_simulation_task(tasks_response: DesignTasksResponse) -> TaskResponse | None:
    """Return the newest simulation task from one design-task listing."""
    return latest_task_by_kind(tasks_response, task_kind="simulation")


def latest_post_processing_task(tasks_response: DesignTasksResponse) -> TaskResponse | None:
    """Return the newest post-processing task from one design-task listing."""
    return latest_task_by_kind(tasks_response, task_kind="post_processing")


def build_task_recovery_state(
    *,
    tasks_response: DesignTasksResponse,
    task_kind: str,
    now: datetime | None = None,
) -> TaskRecoveryState:
    """Resolve polling/recovery authority for one task kind on page refresh."""
    task = latest_task_by_kind(tasks_response, task_kind=task_kind)
    current_now = now or _utcnow()
    should_poll = task is not None and task.status in {"queued", "running"}
    long_running_warning = False
    if task is not None and task.status == "running" and task.started_at is not None:
        elapsed = (current_now - task.started_at).total_seconds()
        long_running_warning = elapsed >= _LONG_RUNNING_WARN_AFTER_SECONDS
    return TaskRecoveryState(
        task=task,
        should_poll=should_poll,
        long_running_warning=long_running_warning,
    )


def build_recovery_state(
    *,
    tasks_response: DesignTasksResponse,
    latest_result: LatestTraceBatchResponse | None,
    now: datetime | None = None,
) -> SimulationRecoveryState:
    """Resolve polling/recovery authority for one simulation page refresh."""
    task_state = build_task_recovery_state(
        tasks_response=tasks_response,
        task_kind="simulation",
        now=now,
    )
    return SimulationRecoveryState(
        task=task_state.task,
        latest_result=latest_result,
        should_poll=task_state.should_poll,
        long_running_warning=task_state.long_running_warning,
    )


def clear_runtime_recovery_state(runtime_state: SimulationRuntimeState) -> None:
    """Clear persisted task authority when no valid active dataset is available."""
    runtime_state.current_task_id = None
    runtime_state.current_task_status = None
    runtime_state.current_trace_batch_id = None
    runtime_state.current_task_error = None
    runtime_state.last_task_poll_signature = None
    runtime_state.long_running_warning_shown = False
    runtime_state.current_post_processing_task_id = None
    runtime_state.current_post_processing_task_status = None
    runtime_state.current_post_processing_trace_batch_id = None
    runtime_state.current_post_processing_task_error = None
    runtime_state.last_post_processing_task_poll_signature = None
    runtime_state.post_processing_long_running_warning_shown = False


def task_status_signature(task: Any) -> str:
    """Return a stable signature for one polled task payload."""
    return "|".join(
        [
            str(getattr(task, "id", "")),
            str(getattr(task, "status", "")),
            str(getattr(task, "trace_batch_id", "")),
            str(getattr(task, "heartbeat_at", "")),
            str(getattr(task, "completed_at", "")),
        ]
    )


def _error_summary(task: Any, fallback: str) -> str:
    error_payload = getattr(task, "error_payload", {})
    if isinstance(error_payload, Mapping):
        summary = error_payload.get("summary")
        if summary not in (None, ""):
            return str(summary)
        details = error_payload.get("details")
        if isinstance(details, Mapping) and details.get("message") not in (None, ""):
            return str(details.get("message"))
    return fallback


def apply_simulation_task_status(
    task: Any,
    *,
    runtime_state: SimulationRuntimeState,
    append_status: StatusAppender,
) -> None:
    """Apply one polled simulation task payload to runtime state."""
    signature = task_status_signature(task)
    if runtime_state.last_task_poll_signature == signature:
        return
    runtime_state.last_task_poll_signature = signature
    runtime_state.current_task_id = int(task.id) if task.id is not None else None
    runtime_state.current_task_status = str(task.status)
    runtime_state.current_trace_batch_id = (
        int(task.trace_batch_id) if task.trace_batch_id is not None else None
    )
    runtime_state.current_task_error = None
    if task.status == "queued":
        append_status(
            "info",
            f"Simulation task queued: task=#{int(task.id)}, batch=#{task.trace_batch_id}.",
        )
        return
    if task.status == "running":
        append_status(
            "info",
            f"Simulation task running: task=#{int(task.id)}, batch=#{task.trace_batch_id}.",
        )
        return
    if task.status == "completed":
        append_status(
            "positive",
            f"Simulation task completed: task=#{int(task.id)}, batch=#{task.trace_batch_id}.",
        )
        return
    if task.status == "failed":
        error_summary = _error_summary(task, "Simulation task failed.")
        runtime_state.current_task_error = error_summary
        append_status(
            "negative",
            f"Simulation task failed: task=#{int(task.id)}, batch=#{task.trace_batch_id}. {error_summary}",
        )


def apply_post_processing_task_status(
    task: Any,
    *,
    runtime_state: SimulationRuntimeState,
    append_status: StatusAppender,
) -> None:
    """Apply one polled post-processing task payload to runtime state."""
    signature = task_status_signature(task)
    if runtime_state.last_post_processing_task_poll_signature == signature:
        return
    runtime_state.last_post_processing_task_poll_signature = signature
    runtime_state.current_post_processing_task_id = (
        int(task.id) if task.id is not None else None
    )
    runtime_state.current_post_processing_task_status = str(task.status)
    runtime_state.current_post_processing_trace_batch_id = (
        int(task.trace_batch_id) if task.trace_batch_id is not None else None
    )
    runtime_state.current_post_processing_task_error = None
    if task.status == "queued":
        append_status(
            "info",
            f"Post-processing task queued: task=#{int(task.id)}, batch=#{task.trace_batch_id}.",
        )
        return
    if task.status == "running":
        append_status(
            "info",
            f"Post-processing task running: task=#{int(task.id)}, batch=#{task.trace_batch_id}.",
        )
        return
    if task.status == "completed":
        append_status(
            "positive",
            f"Post-processing task completed: task=#{int(task.id)}, batch=#{task.trace_batch_id}.",
        )
        return
    if task.status == "failed":
        error_summary = _error_summary(task, "Post-processing task failed.")
        runtime_state.current_post_processing_task_error = error_summary
        append_status(
            "negative",
            f"Post-processing task failed: task=#{int(task.id)}, batch=#{task.trace_batch_id}. {error_summary}",
        )
