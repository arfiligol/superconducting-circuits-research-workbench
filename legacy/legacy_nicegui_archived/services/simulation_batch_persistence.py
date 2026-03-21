"""Page-free raw simulation batch persistence helpers for WS6 worker execution."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from core.shared.persistence.models import TraceBatchRecord, TraceRecord
from core.shared.persistence.unit_of_work import SqliteUnitOfWork
from core.simulation.application.trace_architecture import (
    TRACE_BATCH_BUNDLE_SCHEMA_KIND,
    build_raw_simulation_trace_specs,
    is_trace_batch_bundle_payload,
    persist_trace_batch_bundle,
    rebind_trace_batch_bundle_payload,
)
from core.simulation.domain.circuit import SimulationResult


def create_pending_simulation_batch(
    *,
    uow: SqliteUnitOfWork,
    design_id: int,
    source_meta: Mapping[str, Any],
    config_snapshot: Mapping[str, Any],
    schema_source_hash: str,
    simulation_setup_hash: str,
    sweep_setup_hash: str | None,
) -> TraceBatchRecord:
    """Create one persisted in-progress raw-simulation batch boundary."""
    design = uow.datasets.get(design_id)
    design_name = str(design.name) if design is not None else f"design-{design_id}"
    batch = TraceBatchRecord(
        dataset_id=int(design_id),
        bundle_type="circuit_simulation",
        role="task_run",
        status="in_progress",
        schema_source_hash=schema_source_hash,
        simulation_setup_hash=simulation_setup_hash,
        source_meta={
            **dict(source_meta),
            "schema_kind": TRACE_BATCH_BUNDLE_SCHEMA_KIND,
            "design_id": int(design_id),
            "design_name": design_name,
            "source_kind": "circuit_simulation",
            "stage_kind": "raw",
            "sweep_setup_hash": sweep_setup_hash,
        },
        config_snapshot=dict(config_snapshot),
        result_payload={
            "trace_batch_record": {
                "id": None,
                "design_id": int(design_id),
                "source_kind": "circuit_simulation",
                "stage_kind": "raw",
                "status": "in_progress",
                "setup_kind": "circuit_simulation.raw",
                "setup_version": "1.0",
                "setup_payload": dict(config_snapshot),
                "provenance_payload": {
                    **dict(source_meta),
                    "schema_source_hash": schema_source_hash,
                    "simulation_setup_hash": simulation_setup_hash,
                },
                "summary_payload": {
                    "phase": "queued",
                    "summary": "Simulation task queued.",
                },
            },
            "trace_records": [],
        },
    )
    uow.result_bundles.add(batch)
    uow.flush()
    if batch.id is None:
        raise ValueError("Failed to allocate a simulation trace batch ID.")
    batch.result_payload = {
        "trace_batch_record": {
            **dict(batch.result_payload.get("trace_batch_record", {})),
            "id": int(batch.id),
        },
        "trace_records": [],
    }
    uow.result_bundles.mark_in_progress(
        int(batch.id),
        summary_payload={"phase": "queued", "summary": "Simulation task queued."},
    )
    return batch


def persist_simulation_result_into_batch(
    *,
    uow: SqliteUnitOfWork,
    batch_id: int,
    result: SimulationResult,
    source_meta: Mapping[str, Any],
    config_snapshot: Mapping[str, Any],
    schema_source_hash: str,
    simulation_setup_hash: str,
    result_payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Materialize trace-store-backed raw simulation results into one existing batch."""
    batch = uow.result_bundles.get(batch_id)
    if batch is None:
        raise ValueError(f"Trace batch ID {batch_id} not found.")
    design_id = int(batch.dataset_id)
    design = uow.datasets.get(design_id)
    design_name = str(design.name) if design is not None else f"design-{design_id}"
    trace_batch_payload = (
        dict(result_payload)
        if isinstance(result_payload, Mapping) and is_trace_batch_bundle_payload(result_payload)
        else None
    )
    normalized_result_payload = None if trace_batch_payload is not None else result_payload
    provenance_payload = {
        **dict(source_meta),
        "schema_source_hash": schema_source_hash,
        "simulation_setup_hash": simulation_setup_hash,
        "run_kind": (
            "parameter_sweep"
            if (
                trace_batch_payload is not None
                or (
                    isinstance(normalized_result_payload, Mapping)
                    and str(normalized_result_payload.get("run_kind", "")).strip()
                    == "parameter_sweep"
                )
            )
            else "single_run"
        ),
    }
    summary_payload = {
        "run_kind": provenance_payload["run_kind"],
        "frequency_points": len(result.frequencies_ghz),
        "point_count": (
            int(
                trace_batch_payload.get("trace_batch_record", {})
                .get("summary_payload", {})
                .get("point_count", 0)
            )
            if trace_batch_payload is not None
            else (
                int(normalized_result_payload.get("point_count", 0))
                if isinstance(normalized_result_payload, Mapping)
                else 1
            )
        ),
        "representative_point_index": (
            int(
                trace_batch_payload.get("trace_batch_record", {})
                .get("summary_payload", {})
                .get("representative_point_index", 0)
            )
            if trace_batch_payload is not None
            else (
                int(normalized_result_payload.get("representative_point_index", 0))
                if isinstance(normalized_result_payload, Mapping)
                else 0
            )
        ),
    }
    if trace_batch_payload is not None:
        summary_payload["trace_count"] = len(list(trace_batch_payload.get("trace_records", [])))
        batch.result_payload = rebind_trace_batch_bundle_payload(
            trace_batch_payload,
            bundle_id=int(batch_id),
            design_id=design_id,
            design_name=design_name,
            source_kind="circuit_simulation",
            stage_kind="raw",
            setup_kind="circuit_simulation.raw",
            setup_payload=config_snapshot,
            provenance_payload=provenance_payload,
            summary_payload=summary_payload,
            status="completed",
        )
    else:
        trace_specs = build_raw_simulation_trace_specs(
            result=result,
            sweep_payload=normalized_result_payload,
        )
        summary_payload["trace_count"] = len(trace_specs)
        batch.result_payload = persist_trace_batch_bundle(
            bundle_id=int(batch_id),
            design_id=design_id,
            design_name=design_name,
            source_kind="circuit_simulation",
            stage_kind="raw",
            setup_kind="circuit_simulation.raw",
            setup_payload=config_snapshot,
            provenance_payload=provenance_payload,
            trace_specs=trace_specs,
            summary_payload=summary_payload,
        )

    records = build_trace_batch_data_records(
        dataset_id=design_id,
        trace_batch_payload=batch.result_payload,
    )
    for record in records:
        uow.data_records.add(record)
    uow.flush()
    record_ids = [record.id for record in records if record.id is not None]
    if len(record_ids) != len(records):
        raise ValueError("Failed to allocate one or more trace metadata record IDs.")
    uow.result_bundles.attach_data_records(bundle_id=int(batch_id), data_record_ids=record_ids)
    uow.result_bundles.mark_completed(int(batch_id), summary_payload=summary_payload)
    return {
        "batch_id": int(batch_id),
        **summary_payload,
    }


def mark_simulation_batch_failed(
    *,
    uow: SqliteUnitOfWork,
    batch_id: int,
    error_code: str,
    error_summary: str,
) -> None:
    """Persist one stable raw-simulation batch failure summary."""
    uow.result_bundles.mark_failed(
        int(batch_id),
        summary_payload={
            "error_code": str(error_code),
            "error_summary": str(error_summary),
            "phase": "failed",
        },
    )


def build_trace_batch_data_records(
    *,
    dataset_id: int,
    trace_batch_payload: Mapping[str, Any],
) -> list[TraceRecord]:
    """Materialize metadata-only TraceRecord rows from one trace-batch payload."""
    if not is_trace_batch_bundle_payload(trace_batch_payload):
        raise ValueError("Payload is not a trace-batch bundle.")
    raw_trace_records = trace_batch_payload.get("trace_records", [])
    if not isinstance(raw_trace_records, list) or not raw_trace_records:
        raise ValueError("Trace-batch payload has no trace records.")

    records: list[TraceRecord] = []
    for raw_trace_record in raw_trace_records:
        if not isinstance(raw_trace_record, Mapping):
            raise ValueError("Trace-batch trace record entry is invalid.")
        store_ref = raw_trace_record.get("store_ref")
        raw_axes = raw_trace_record.get("axes", [])
        if not isinstance(store_ref, Mapping) or not store_ref:
            raise ValueError("Trace-batch trace record is missing store_ref metadata.")
        if not isinstance(raw_axes, list) or not raw_axes:
            raise ValueError("Trace-batch trace record is missing axis metadata.")
        records.append(
            TraceRecord(
                dataset_id=int(dataset_id),
                data_type=str(
                    raw_trace_record.get("family") or raw_trace_record.get("data_type") or ""
                ),
                parameter=str(raw_trace_record.get("parameter") or ""),
                representation=str(raw_trace_record.get("representation") or ""),
                axes=[dict(axis) for axis in raw_axes if isinstance(axis, Mapping)],
                values=[],
                store_ref=dict(store_ref),
            )
        )
    return records
