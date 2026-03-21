"""Request and hash builders for simulation submit flows."""

from __future__ import annotations

import hashlib
import json
from typing import Any, cast

from legacy.legacy_nicegui_archived.services.execution_context import build_ui_use_case_context
from legacy.legacy_nicegui_archived.services.post_processing_task_contract import build_post_processing_submission
from legacy.legacy_nicegui_archived.services.simulation_submission import (
    PreparedSimulationSubmission,
    build_simulation_submission,
)
from core.shared.persistence.models import CircuitRecord
from core.simulation.domain.circuit import CircuitDefinition


def hash_stable_json(payload: dict[str, Any]) -> str:
    """Return a stable hash for one JSON-compatible payload."""
    normalized = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    )
    return f"sha256:{hashlib.sha256(normalized.encode('utf-8')).hexdigest()}"


def hash_schema_source(source_text: str) -> str:
    """Return a stable hash for the stored source-form schema text."""
    return f"sha256:{hashlib.sha256(source_text.encode('utf-8')).hexdigest()}"


def build_simulation_submit_request(
    *,
    design_id: int,
    latest_record: CircuitRecord,
    latest_circuit_def: CircuitDefinition,
    simulation_run_id: str,
    freq_range_payload: Any,
    config_payload: Any,
    setup_snapshot: dict[str, Any],
    schema_source_hash: str,
    simulation_setup_hash: str,
    sweep_setup_payload: dict[str, Any] | None,
    sweep_setup_hash: str | None,
) -> PreparedSimulationSubmission:
    """Build the persisted simulation submit request for one validated run."""
    return build_simulation_submission(
        design_id=design_id,
        design_name=str(latest_record.name),
        circuit=latest_circuit_def,
        freq_range=freq_range_payload,
        config=config_payload,
        config_snapshot=setup_snapshot,
        source_meta={
            "origin": "simulation_page",
            "storage": "design_trace_store",
            "run_id": simulation_run_id,
            "circuit_id": latest_record.id,
            "circuit_name": latest_record.name,
        },
        schema_source_hash=schema_source_hash,
        simulation_setup_hash=simulation_setup_hash,
        sweep_setup_payload=sweep_setup_payload,
        sweep_setup_hash=sweep_setup_hash,
        context=build_ui_use_case_context(
            metadata={
                "flow": "simulation",
                "run_id": simulation_run_id,
                "schema_id": int(latest_record.id or 0),
            }
        ),
        force_rerun=False,
    )


def build_post_processing_submit_request(
    intent: dict[str, Any],
) -> Any:
    """Build the persisted post-processing submit request for one UI intent."""
    return build_post_processing_submission(
        design_id=int(intent["design_id"]),
        source_batch_id=int(intent["source_batch_id"]),
        input_source=str(intent["input_source"]),
        mode_filter=str(intent["mode_filter"]),
        mode_token=str(intent["mode_token"]),
        reference_impedance_ohm=float(intent["reference_impedance_ohm"]),
        step_sequence=[dict(step) for step in list(intent["step_sequence"])],
        termination_plan_payload=(
            dict(intent["termination_plan_payload"])
            if isinstance(intent.get("termination_plan_payload"), dict)
            else None
        ),
        circuit_definition=cast(
            CircuitDefinition | None,
            intent.get("circuit_definition"),
        ),
        context=build_ui_use_case_context(
            metadata={
                "flow": "post_processing",
                "design_id": int(intent["design_id"]),
                "schema_id": int(intent.get("schema_id") or 0),
                "source_batch_id": int(intent["source_batch_id"]),
            }
        ),
        force_rerun=False,
    )
