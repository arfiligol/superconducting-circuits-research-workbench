"""Polling and authority refresh orchestration for simulation recovery."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from legacy.legacy_nicegui_archived.features.simulation.api_client import (
    ApiClientError,
    get_design_tasks,
    get_latest_post_processing_result,
    get_latest_simulation_result,
    get_task,
)
from legacy.legacy_nicegui_archived.features.simulation.page_state import SimulationPageCoordinator
from legacy.legacy_nicegui_archived.features.simulation.recovery.task_authority import (
    apply_post_processing_task_status,
    apply_simulation_task_status,
    build_recovery_state,
    build_task_recovery_state,
    clear_runtime_recovery_state,
)
from legacy.legacy_nicegui_archived.features.simulation.state import SimulationRuntimeState


@dataclass
class SimulationRecoveryBindings:
    """Injected page callbacks and mutable references for recovery orchestration."""

    owner_client: Any
    runtime_state: SimulationRuntimeState
    append_status: Callable[[str, str], None]
    load_persisted_simulation_views: Callable[[], None]
    load_persisted_post_processing_views: Callable[[], None]
    render_simulation_restore_prompt: Callable[[Any], None]
    render_post_processing_restore_prompt: Callable[[Any], None]
    render_unavailable_authority_state: Callable[[], None]
    restored_simulation_batch_id_ref: dict[str, int | None]
    restored_post_processing_batch_id_ref: dict[str, int | None]
    resolved_post_process_source_bundle_id_ref: dict[str, int | None]
    poll_timer: Any | None = None
    post_processing_poll_timer: Any | None = None
    coordinator: SimulationPageCoordinator | None = None


def _set_timer_active(timer: Any | None, active: bool) -> None:
    if timer is not None:
        timer.active = active


def _append_task_warning(
    task: Any,
    *,
    append_status: Callable[[str, str], None],
    warning_already_shown: bool,
) -> bool:
    progress_payload = getattr(task, "progress_payload", {})
    warning = ""
    if isinstance(progress_payload, dict):
        warning = str(progress_payload.get("warning", "")).strip()
    if warning and not warning_already_shown:
        append_status("warning", warning)
        return True
    return warning_already_shown


async def refresh_simulation_authority(
    *,
    active_design_id: int | None,
    bindings: SimulationRecoveryBindings,
    preferred_task_id: int | None = None,
    hydrate_views: bool = False,
) -> None:
    """Refresh persisted task/result authority for the active design."""
    if active_design_id is None:
        if bindings.coordinator is not None:
            bindings.coordinator.clear_authority()
        _set_timer_active(bindings.poll_timer, False)
        _set_timer_active(bindings.post_processing_poll_timer, False)
        return
    if bindings.coordinator is not None:
        bindings.coordinator.set_active_design(active_design_id)
    try:
        tasks_response = await get_design_tasks(
            active_design_id,
            client=bindings.owner_client,
        )
        latest_result = await get_latest_simulation_result(
            active_design_id,
            client=bindings.owner_client,
        )
        latest_post_processing_result = await get_latest_post_processing_result(
            active_design_id,
            client=bindings.owner_client,
        )
    except ApiClientError as exc:
        if exc.status_code != 404:
            raise
        clear_runtime_recovery_state(bindings.runtime_state)
        if bindings.coordinator is not None:
            bindings.coordinator.clear_authority()
        _set_timer_active(bindings.poll_timer, False)
        _set_timer_active(bindings.post_processing_poll_timer, False)
        bindings.render_unavailable_authority_state()
        return

    recovery_state = build_recovery_state(
        tasks_response=tasks_response,
        latest_result=latest_result,
    )
    post_processing_recovery_state = build_task_recovery_state(
        tasks_response=tasks_response,
        task_kind="post_processing",
    )
    task = recovery_state.task
    post_processing_task = post_processing_recovery_state.task
    if preferred_task_id is not None:
        fetched_task = await get_task(preferred_task_id, client=bindings.owner_client)
        if fetched_task.task_kind == "simulation" and fetched_task.design_id == active_design_id:
            task = fetched_task
        elif (
            fetched_task.task_kind == "post_processing"
            and fetched_task.design_id == active_design_id
        ):
            post_processing_task = fetched_task

    if task is not None:
        apply_simulation_task_status(
            task,
            runtime_state=bindings.runtime_state,
            append_status=bindings.append_status,
        )
        if bindings.coordinator is not None:
            bindings.coordinator.sync_simulation_authority(
                task_id=int(task.id) if task.id is not None else None,
                trace_batch_id=(
                    int(task.trace_batch_id) if task.trace_batch_id is not None else None
                ),
            )
        bindings.runtime_state.long_running_warning_shown = _append_task_warning(
            task,
            append_status=bindings.append_status,
            warning_already_shown=bindings.runtime_state.long_running_warning_shown,
        )
    _set_timer_active(bindings.poll_timer, bool(task is not None and task.status in {"queued", "running"}))

    if post_processing_task is not None:
        apply_post_processing_task_status(
            post_processing_task,
            runtime_state=bindings.runtime_state,
            append_status=bindings.append_status,
        )
        if bindings.coordinator is not None:
            bindings.coordinator.sync_post_processing_authority(
                task_id=int(post_processing_task.id) if post_processing_task.id is not None else None,
                trace_batch_id=(
                    int(post_processing_task.trace_batch_id)
                    if post_processing_task.trace_batch_id is not None
                    else None
                ),
                source_batch_id=bindings.resolved_post_process_source_bundle_id_ref["value"],
            )
        bindings.runtime_state.post_processing_long_running_warning_shown = _append_task_warning(
            post_processing_task,
            append_status=bindings.append_status,
            warning_already_shown=bindings.runtime_state.post_processing_long_running_warning_shown,
        )
    _set_timer_active(
        bindings.post_processing_poll_timer,
        bool(post_processing_task is not None and post_processing_task.status in {"queued", "running"}),
    )

    if latest_result is not None:
        bindings.resolved_post_process_source_bundle_id_ref["value"] = latest_result.batch_id
        bindings.runtime_state.current_trace_batch_id = int(latest_result.batch_id)
        if bindings.coordinator is not None:
            bindings.coordinator.record_simulation_restore(batch_id=int(latest_result.batch_id))
        if hydrate_views:
            bindings.load_persisted_simulation_views()
        elif bindings.restored_simulation_batch_id_ref["value"] != int(latest_result.batch_id):
            bindings.render_simulation_restore_prompt(latest_result)
    if latest_post_processing_result is not None:
        bindings.resolved_post_process_source_bundle_id_ref["value"] = (
            latest_post_processing_result.parent_batch_id
            or bindings.resolved_post_process_source_bundle_id_ref["value"]
        )
        bindings.runtime_state.current_post_processing_trace_batch_id = int(
            latest_post_processing_result.batch_id
        )
        if bindings.coordinator is not None:
            bindings.coordinator.record_post_processing_restore(
                batch_id=int(latest_post_processing_result.batch_id),
                source_batch_id=(
                    int(latest_post_processing_result.parent_batch_id)
                    if latest_post_processing_result.parent_batch_id is not None
                    else bindings.resolved_post_process_source_bundle_id_ref["value"]
                ),
            )
        if hydrate_views:
            bindings.load_persisted_post_processing_views()
        elif bindings.restored_post_processing_batch_id_ref["value"] != int(
            latest_post_processing_result.batch_id
        ):
            bindings.render_post_processing_restore_prompt(latest_post_processing_result)


async def poll_current_simulation_task(
    *,
    active_design_id: int | None,
    bindings: SimulationRecoveryBindings,
) -> None:
    """Poll the current persisted simulation task and refresh authority when it settles."""
    if bindings.runtime_state.current_task_id is None:
        return
    try:
        task = await get_task(int(bindings.runtime_state.current_task_id), client=bindings.owner_client)
    except ApiClientError as exc:
        bindings.append_status("warning", f"Task polling failed: {exc.detail}")
        return
    apply_simulation_task_status(
        task,
        runtime_state=bindings.runtime_state,
        append_status=bindings.append_status,
    )
    if bindings.coordinator is not None:
        bindings.coordinator.sync_simulation_authority(
            task_id=int(task.id) if task.id is not None else None,
            trace_batch_id=int(task.trace_batch_id) if task.trace_batch_id is not None else None,
        )
    bindings.runtime_state.long_running_warning_shown = _append_task_warning(
        task,
        append_status=bindings.append_status,
        warning_already_shown=bindings.runtime_state.long_running_warning_shown,
    )
    if task.status in {"completed", "failed"}:
        _set_timer_active(bindings.poll_timer, False)
        await refresh_simulation_authority(
            active_design_id=active_design_id,
            bindings=bindings,
            preferred_task_id=int(task.id),
            hydrate_views=task.status == "completed",
        )


async def poll_current_post_processing_task(
    *,
    active_design_id: int | None,
    bindings: SimulationRecoveryBindings,
) -> None:
    """Poll the current persisted post-processing task and refresh authority when it settles."""
    if bindings.runtime_state.current_post_processing_task_id is None:
        return
    try:
        task = await get_task(
            int(bindings.runtime_state.current_post_processing_task_id),
            client=bindings.owner_client,
        )
    except ApiClientError as exc:
        bindings.append_status("warning", f"Post-processing task polling failed: {exc.detail}")
        return
    apply_post_processing_task_status(
        task,
        runtime_state=bindings.runtime_state,
        append_status=bindings.append_status,
    )
    if bindings.coordinator is not None:
        bindings.coordinator.sync_post_processing_authority(
            task_id=int(task.id) if task.id is not None else None,
            trace_batch_id=int(task.trace_batch_id) if task.trace_batch_id is not None else None,
            source_batch_id=bindings.resolved_post_process_source_bundle_id_ref["value"],
        )
    bindings.runtime_state.post_processing_long_running_warning_shown = _append_task_warning(
        task,
        append_status=bindings.append_status,
        warning_already_shown=bindings.runtime_state.post_processing_long_running_warning_shown,
    )
    if task.status in {"completed", "failed"}:
        _set_timer_active(bindings.post_processing_poll_timer, False)
        await refresh_simulation_authority(
            active_design_id=active_design_id,
            bindings=bindings,
            preferred_task_id=int(task.id),
            hydrate_views=task.status == "completed",
        )
