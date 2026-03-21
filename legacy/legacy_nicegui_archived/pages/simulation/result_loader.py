"""Compatibility wrapper for simulation recovery helpers."""

from legacy.legacy_nicegui_archived.features.simulation.result_loader import (
    SimulationRecoveryState,
    TaskRecoveryState,
    build_recovery_state,
    build_task_recovery_state,
    latest_post_processing_task,
    latest_simulation_task,
    latest_task_by_kind,
)

__all__ = [
    "SimulationRecoveryState",
    "TaskRecoveryState",
    "build_recovery_state",
    "build_task_recovery_state",
    "latest_post_processing_task",
    "latest_simulation_task",
    "latest_task_by_kind",
]
