"""Unit tests for page-level runtime log context formatting."""

from legacy.legacy_nicegui_archived.pages.characterization.state import CharacterizationRuntimeState
from legacy.legacy_nicegui_archived.pages.simulation.state import SimulationRuntimeState


def test_simulation_runtime_state_prefixes_status_with_context_tokens() -> None:
    """Simulation logs should include sorted context tokens when present."""
    state = SimulationRuntimeState()
    state.set_log_context(bundle_id=12, run_id="sim-abc", dataset_id=5)

    state.append_status(
        "info",
        "Cache hit.",
        time_label="10:00:00",
    )

    assert state.status_history[-1]["message"] == (
        "[bundle_id=12 dataset_id=5 run_id=sim-abc] Cache hit."
    )


def test_characterization_runtime_state_prefixes_status_with_context_tokens() -> None:
    """Characterization logs should include sorted context tokens when present."""
    state = CharacterizationRuntimeState.create()
    state.set_log_context(analysis_id="admittance_extraction", dataset_id=7, run_id="char-xyz")

    state.append_status(
        "positive",
        "Analysis completed.",
        time_label="11:30:00",
    )

    assert state.analysis_status_history[-1]["message"] == (
        "[analysis_id=admittance_extraction dataset_id=7 run_id=char-xyz] Analysis completed."
    )


def test_runtime_state_context_clear_stops_prefixing() -> None:
    """After clearing context, new log rows should no longer include token prefixes."""
    state = SimulationRuntimeState()
    state.set_log_context(run_id="sim-123")
    state.clear_log_context()

    state.append_status(
        "info",
        "Simulation started.",
        time_label="12:00:00",
    )

    assert state.status_history[-1]["message"] == "Simulation started."
