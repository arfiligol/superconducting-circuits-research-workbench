"""Compatibility wrapper for simulation page state helpers."""

from legacy.legacy_nicegui_archived.features.simulation.state import (
    SimulationRuntimeState,
    TerminationSetupState,
    TerminationViewElements,
    default_post_processing_input_state,
    default_result_view_state,
    default_sweep_result_view_state,
)

__all__ = [
    "SimulationRuntimeState",
    "TerminationSetupState",
    "TerminationViewElements",
    "default_post_processing_input_state",
    "default_result_view_state",
    "default_sweep_result_view_state",
]
