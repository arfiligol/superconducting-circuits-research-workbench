"""Simulation submit orchestration helpers."""

from __future__ import annotations

from typing import Any

from legacy.legacy_nicegui_archived.features.simulation.api_client import submit_simulation_task
from legacy.legacy_nicegui_archived.features.simulation.submit.request_builders import build_simulation_submit_request
from legacy.legacy_nicegui_archived.features.simulation.submit.validation import PreparedSimulationRun
from core.shared.persistence.models import CircuitRecord
from core.simulation.domain.circuit import CircuitDefinition


async def submit_simulation_run(
    *,
    prepared_run: PreparedSimulationRun,
    design_id: int,
    latest_record: CircuitRecord,
    latest_circuit_def: CircuitDefinition,
    simulation_run_id: str,
    owner_client: Any,
) -> Any:
    """Submit one validated simulation run through the persisted task API."""
    submission = build_simulation_submit_request(
        design_id=design_id,
        latest_record=latest_record,
        latest_circuit_def=latest_circuit_def,
        simulation_run_id=simulation_run_id,
        freq_range_payload=prepared_run.freq_range,
        config_payload=prepared_run.config,
        setup_snapshot=prepared_run.setup_snapshot,
        schema_source_hash=prepared_run.schema_source_hash,
        simulation_setup_hash=prepared_run.simulation_setup_hash,
        sweep_setup_payload=prepared_run.sweep_setup_payload,
        sweep_setup_hash=prepared_run.sweep_setup_hash,
    )
    return await submit_simulation_task(
        submission.api_request,
        client=owner_client,
    )
