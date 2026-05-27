from __future__ import annotations

from src.app.infrastructure.rewrite_catalog_repository import (
    COUPLER_DETUNING_DEMO_DEFINITION_ID,
    FLOATING_QUBIT_WITH_XY_LINE_DEFINITION_ID,
    FLUXONIUM_READOUT_CHAIN_DEFINITION_ID,
    LOCAL_SPACE_RESONATOR_DEFINITION_ID,
    _seed_characterization_analysis_registry,
    _seed_characterization_result_details,
    _seed_characterization_results,
    _seed_characterization_run_history,
    _seed_circuit_definitions,
    _seed_datasets,
    _seed_designs,
    _seed_trace_details,
    _seed_trace_summaries,
)


def build_seed_datasets():
    return _seed_datasets()


def build_seed_designs():
    return _seed_designs()


def build_seed_trace_summaries():
    return _seed_trace_summaries()


def build_seed_trace_details():
    return _seed_trace_details()


def build_seed_characterization_analysis_registry():
    return _seed_characterization_analysis_registry()


def build_seed_characterization_run_history():
    return _seed_characterization_run_history()


def build_seed_characterization_results():
    return _seed_characterization_results()


def build_seed_characterization_result_details():
    return _seed_characterization_result_details()


def build_seed_circuit_definitions():
    return _seed_circuit_definitions()


__all__ = [
    "COUPLER_DETUNING_DEMO_DEFINITION_ID",
    "FLOATING_QUBIT_WITH_XY_LINE_DEFINITION_ID",
    "FLUXONIUM_READOUT_CHAIN_DEFINITION_ID",
    "LOCAL_SPACE_RESONATOR_DEFINITION_ID",
    "build_seed_characterization_analysis_registry",
    "build_seed_characterization_result_details",
    "build_seed_characterization_results",
    "build_seed_characterization_run_history",
    "build_seed_circuit_definitions",
    "build_seed_datasets",
    "build_seed_designs",
    "build_seed_trace_details",
    "build_seed_trace_summaries",
]
