"""Compatibility wrapper for simulation API helpers."""

from legacy.legacy_nicegui_archived.features.simulation.api_client import (
    ApiClientError,
    get_design_tasks,
    get_latest_post_processing_result,
    get_latest_simulation_result,
    get_task,
    submit_post_processing_task,
    submit_simulation_task,
)

__all__ = [
    "ApiClientError",
    "get_design_tasks",
    "get_latest_post_processing_result",
    "get_latest_simulation_result",
    "get_task",
    "submit_post_processing_task",
    "submit_simulation_task",
]
