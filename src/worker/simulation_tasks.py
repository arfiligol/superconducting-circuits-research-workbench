"""Simulation-lane probe and failure task functions for RQ."""

from __future__ import annotations

import os
from typing import Any

from worker.post_processing_execution import execute_post_processing_task
from worker.runtime import TaskExecutionResult, execute_managed_task, mark_task_running_before_crash
from worker.simulation_execution import execute_simulation_task

_LANE_NAME = "simulation"


def simulation_run_task(task_id: int) -> dict[str, Any]:
    """Execute one real persisted simulation task through the WS6 worker boundary."""
    return execute_managed_task(
        task_id=task_id,
        lane_name=_LANE_NAME,
        worker_task_name="simulation_run_task",
        operation=lambda: execute_simulation_task(task_id),
    )


def simulation_probe_task(task_id: int) -> dict[str, Any]:
    """Queue one minimal successful task lifecycle round-trip."""
    return execute_managed_task(
        task_id=task_id,
        lane_name=_LANE_NAME,
        worker_task_name="simulation_probe_task",
        operation=lambda: TaskExecutionResult(
            result_summary_payload={"probe_result": "ok"},
        ),
    )


def post_processing_run_task(task_id: int) -> dict[str, Any]:
    """Execute one real persisted post-processing task on the simulation lane."""
    return execute_managed_task(
        task_id=task_id,
        lane_name=_LANE_NAME,
        worker_task_name="post_processing_run_task",
        operation=lambda: execute_post_processing_task(task_id),
    )


def post_processing_probe_task(task_id: int) -> dict[str, Any]:
    """Queue one minimal post-processing lifecycle round-trip on the simulation lane."""
    return execute_managed_task(
        task_id=task_id,
        lane_name=_LANE_NAME,
        worker_task_name="post_processing_probe_task",
        operation=lambda: TaskExecutionResult(
            result_summary_payload={
                "probe_result": "ok",
                "flow": "post_processing",
            },
        ),
    )


def simulation_failure_task(
    task_id: int,
    message: str = "simulation probe failure",
) -> dict[str, Any]:
    """Queue one task that fails with a structured Python exception payload."""
    return execute_managed_task(
        task_id=task_id,
        lane_name=_LANE_NAME,
        worker_task_name="simulation_failure_task",
        operation=lambda: (_ for _ in ()).throw(RuntimeError(message)),
    )


def simulation_crash_task(task_id: int, exit_code: int = 86) -> None:
    """Queue one task that intentionally crashes the worker process."""
    mark_task_running_before_crash(
        task_id=task_id,
        lane_name=_LANE_NAME,
        worker_task_name="simulation_crash_task",
    )
    os._exit(int(exit_code))
