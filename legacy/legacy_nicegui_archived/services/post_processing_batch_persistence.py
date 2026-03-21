"""Page-free post-processing batch persistence helpers for WS7 execution."""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any, cast

from legacy.legacy_nicegui_archived.services.simulation_batch_persistence import (
    build_trace_batch_data_records,
)
from core.shared.persistence.models import TraceBatchRecord
from core.shared.persistence.unit_of_work import SqliteUnitOfWork
from core.simulation.application.post_processing import PortMatrixSweep, PortMatrixSweepRun
from core.simulation.application.trace_architecture import (
    TRACE_BATCH_BUNDLE_SCHEMA_KIND,
    build_post_processed_trace_specs,
    is_trace_batch_bundle_payload,
    persist_trace_batch_bundle,
    rebind_trace_batch_bundle_payload,
)


def _preview_projection_point_index(flow_spec: Mapping[str, Any]) -> int:
    preview_projection = flow_spec.get("preview_projection")
    if not isinstance(preview_projection, Mapping):
        return 0
    return int(preview_projection.get("point_index", 0) or 0)


def _trace_count_from_runtime_output(
    runtime_output: PortMatrixSweep | PortMatrixSweepRun | Mapping[str, Any],
) -> int:
    if isinstance(runtime_output, Mapping) and is_trace_batch_bundle_payload(runtime_output):
        return len(list(runtime_output.get("trace_records", [])))
    resolved_runtime_output = cast(PortMatrixSweep | PortMatrixSweepRun, runtime_output)
    return len(build_post_processed_trace_specs(runtime_output=resolved_runtime_output))


def _resolved_source_run_kind(source_snapshot: Mapping[str, Any]) -> str:
    result_payload = source_snapshot.get("result_payload")
    if isinstance(result_payload, Mapping):
        if is_trace_batch_bundle_payload(result_payload):
            summary_payload = result_payload.get("trace_batch_record", {}).get(
                "summary_payload", {}
            )
            if isinstance(summary_payload, Mapping):
                run_kind = str(summary_payload.get("run_kind", "")).strip()
                if run_kind:
                    return run_kind
        run_kind = str(result_payload.get("run_kind", "")).strip()
        if run_kind:
            return run_kind
    return "single_run"


def _resolved_source_sweep_setup_hash(source_snapshot: Mapping[str, Any]) -> str | None:
    source_meta = source_snapshot.get("source_meta")
    if isinstance(source_meta, Mapping):
        raw_hash = source_meta.get("sweep_setup_hash")
        if isinstance(raw_hash, str) and raw_hash.strip():
            return raw_hash.strip()
    config_snapshot = source_snapshot.get("config_snapshot")
    if not isinstance(config_snapshot, Mapping):
        return None
    raw_hash = config_snapshot.get("sweep_setup_hash")
    if isinstance(raw_hash, str) and raw_hash.strip():
        return raw_hash.strip()
    sweep_snapshot = config_snapshot.get("sweep")
    if not isinstance(sweep_snapshot, Mapping):
        return None
    nested_hash = sweep_snapshot.get("setup_hash")
    if isinstance(nested_hash, str) and nested_hash.strip():
        return nested_hash.strip()
    return None


def _build_post_processing_config_snapshot(
    *,
    flow_spec: Mapping[str, Any],
    source_batch_id: int,
    source_snapshot: Mapping[str, Any],
) -> dict[str, Any]:
    config_snapshot = json.loads(json.dumps(dict(flow_spec)))
    config_snapshot["source_simulation_bundle_id"] = int(source_batch_id)
    config_snapshot["source_run_kind"] = _resolved_source_run_kind(source_snapshot)
    config_snapshot.setdefault("setup_kind", "circuit_simulation.postprocess")
    config_snapshot.setdefault("setup_version", "1.0")
    sweep_setup_hash = _resolved_source_sweep_setup_hash(source_snapshot)
    if sweep_setup_hash is not None:
        config_snapshot["sweep_setup_hash"] = sweep_setup_hash
    return config_snapshot


def _build_post_processing_source_meta(
    *,
    flow_spec: Mapping[str, Any],
    source_batch_id: int,
    source_snapshot: Mapping[str, Any],
    design_id: int,
    design_name: str,
) -> dict[str, Any]:
    source_meta: dict[str, Any] = {
        "origin": "simulation_postprocess",
        "schema_kind": TRACE_BATCH_BUNDLE_SCHEMA_KIND,
        "design_id": int(design_id),
        "design_name": design_name,
        "source_kind": "circuit_simulation",
        "stage_kind": "postprocess",
        "source_simulation_bundle_id": int(source_batch_id),
        "source_run_kind": _resolved_source_run_kind(source_snapshot),
        "input_source_type": str(flow_spec.get("input_y_source", "raw_y")),
        "mode_token": str(flow_spec.get("mode_token", "")),
    }
    source_bundle_type = source_snapshot.get("bundle_type")
    if isinstance(source_bundle_type, str) and source_bundle_type.strip():
        source_meta["source_bundle_type"] = source_bundle_type.strip()
    return source_meta


def _build_post_processing_summary(
    *,
    runtime_output: PortMatrixSweep | PortMatrixSweepRun | Mapping[str, Any],
    flow_spec: Mapping[str, Any],
    representative_frequency_points: int,
) -> dict[str, Any]:
    run_kind = str(flow_spec.get("run_kind", "")).strip() or (
        "parameter_sweep" if isinstance(runtime_output, PortMatrixSweepRun) else "single_run"
    )
    if isinstance(runtime_output, Mapping) and is_trace_batch_bundle_payload(runtime_output):
        raw_summary = runtime_output.get("trace_batch_record", {}).get("summary_payload", {})
        if isinstance(raw_summary, Mapping):
            summary = dict(raw_summary)
            summary.setdefault("run_kind", run_kind)
            summary.setdefault("point_count", int(flow_spec.get("point_count", 1) or 1))
            summary.setdefault(
                "representative_point_index",
                _preview_projection_point_index(flow_spec),
            )
            summary.setdefault("frequency_points", int(representative_frequency_points))
            return summary
    point_count = (
        int(runtime_output.point_count)
        if isinstance(runtime_output, PortMatrixSweepRun)
        else int(flow_spec.get("point_count", 1) or 1)
    )
    representative_point_index = _preview_projection_point_index(flow_spec)
    return {
        "trace_count": _trace_count_from_runtime_output(runtime_output),
        "run_kind": run_kind,
        "frequency_points": int(representative_frequency_points),
        "point_count": point_count,
        "representative_point_index": representative_point_index,
        "input_source": str(flow_spec.get("input_y_source", "raw_y")),
        "mode_token": str(flow_spec.get("mode_token", "")),
    }


def create_pending_post_processing_batch(
    *,
    uow: SqliteUnitOfWork,
    design_id: int,
    source_batch_id: int,
    input_source: str,
    mode_filter: str,
    mode_token: str,
    reference_impedance_ohm: float,
    step_sequence: list[dict[str, Any]],
) -> TraceBatchRecord:
    """Create one persisted in-progress post-processing batch boundary."""
    design = uow.datasets.get(design_id)
    design_name = str(design.name) if design is not None else f"design-{design_id}"
    source_snapshot = uow.result_bundles.get_snapshot(int(source_batch_id))
    if source_snapshot is None:
        raise ValueError(f"Source raw batch ID {source_batch_id} not found.")
    batch = TraceBatchRecord(
        dataset_id=int(design_id),
        parent_batch_id=int(source_batch_id),
        bundle_type="simulation_postprocess",
        role="task_run",
        status="in_progress",
        schema_source_hash=(
            str(source_snapshot.get("schema_source_hash"))
            if source_snapshot.get("schema_source_hash") is not None
            else None
        ),
        simulation_setup_hash=(
            str(source_snapshot.get("simulation_setup_hash"))
            if source_snapshot.get("simulation_setup_hash") is not None
            else None
        ),
        source_meta={
            "schema_kind": TRACE_BATCH_BUNDLE_SCHEMA_KIND,
            "design_id": int(design_id),
            "design_name": design_name,
            "source_kind": "circuit_simulation",
            "stage_kind": "postprocess",
            "source_simulation_bundle_id": int(source_batch_id),
            "source_run_kind": _resolved_source_run_kind(source_snapshot),
            "input_source_type": str(input_source),
            "mode_token": str(mode_token),
        },
        config_snapshot={
            "setup_kind": "circuit_simulation.postprocess",
            "setup_version": "1.0",
            "input_y_source": str(input_source),
            "mode_filter": str(mode_filter),
            "mode_token": str(mode_token),
            "reference_impedance_ohm": float(reference_impedance_ohm),
            "steps": [dict(step) for step in step_sequence],
            "source_simulation_bundle_id": int(source_batch_id),
            "source_run_kind": _resolved_source_run_kind(source_snapshot),
        },
        result_payload={
            "trace_batch_record": {
                "id": None,
                "design_id": int(design_id),
                "source_kind": "circuit_simulation",
                "stage_kind": "postprocess",
                "parent_batch_id": int(source_batch_id),
                "status": "in_progress",
                "setup_kind": "circuit_simulation.postprocess",
                "setup_version": "1.0",
                "setup_payload": {
                    "input_y_source": str(input_source),
                    "mode_filter": str(mode_filter),
                    "mode_token": str(mode_token),
                    "reference_impedance_ohm": float(reference_impedance_ohm),
                    "steps": [dict(step) for step in step_sequence],
                },
                "provenance_payload": {
                    "source_simulation_bundle_id": int(source_batch_id),
                    "source_run_kind": _resolved_source_run_kind(source_snapshot),
                },
                "summary_payload": {
                    "phase": "queued",
                    "summary": "Post-processing task queued.",
                },
            },
            "trace_records": [],
        },
    )
    uow.result_bundles.add(batch)
    uow.flush()
    if batch.id is None:
        raise ValueError("Failed to allocate a post-processing trace batch ID.")
    batch.result_payload = {
        "trace_batch_record": {
            **dict(batch.result_payload.get("trace_batch_record", {})),
            "id": int(batch.id),
        },
        "trace_records": [],
    }
    uow.result_bundles.mark_in_progress(
        int(batch.id),
        summary_payload={"phase": "queued", "summary": "Post-processing task queued."},
    )
    return batch


def persist_post_processing_result_into_batch(
    *,
    uow: SqliteUnitOfWork,
    batch_id: int,
    source_batch_id: int,
    runtime_output: PortMatrixSweep | PortMatrixSweepRun | Mapping[str, Any],
    flow_spec: Mapping[str, Any],
) -> dict[str, Any]:
    """Materialize post-processed traces into one existing batch."""
    batch = uow.result_bundles.get(batch_id)
    if batch is None:
        raise ValueError(f"Trace batch ID {batch_id} not found.")
    source_snapshot = uow.result_bundles.get_snapshot(int(source_batch_id))
    if source_snapshot is None:
        raise ValueError(f"Source raw batch ID {source_batch_id} not found.")
    design_id = int(batch.dataset_id)
    design = uow.datasets.get(design_id)
    design_name = str(design.name) if design is not None else f"design-{design_id}"
    representative_frequency_points = (
        len(runtime_output.representative_sweep.frequencies_ghz)
        if isinstance(runtime_output, PortMatrixSweepRun)
        else len(runtime_output.frequencies_ghz)
        if isinstance(runtime_output, PortMatrixSweep)
        else int(
            runtime_output.get("trace_batch_record", {})
            .get("summary_payload", {})
            .get("frequency_points", 0)
            or 0
        )
    )
    if representative_frequency_points <= 0:
        raise ValueError(
            "Persisted post-processing payload is missing representative sweep metadata."
        )
    summary_payload = _build_post_processing_summary(
        runtime_output=runtime_output,
        flow_spec=flow_spec,
        representative_frequency_points=representative_frequency_points,
    )
    config_snapshot = _build_post_processing_config_snapshot(
        flow_spec=flow_spec,
        source_batch_id=source_batch_id,
        source_snapshot=source_snapshot,
    )
    source_meta = _build_post_processing_source_meta(
        flow_spec=flow_spec,
        source_batch_id=source_batch_id,
        source_snapshot=source_snapshot,
        design_id=design_id,
        design_name=design_name,
    )
    batch.source_meta = dict(source_meta)
    batch.config_snapshot = dict(config_snapshot)
    if isinstance(runtime_output, Mapping) and is_trace_batch_bundle_payload(runtime_output):
        batch.result_payload = rebind_trace_batch_bundle_payload(
            runtime_output,
            bundle_id=int(batch_id),
            design_id=design_id,
            design_name=design_name,
            source_kind="circuit_simulation",
            stage_kind="postprocess",
            setup_kind="circuit_simulation.postprocess",
            setup_payload=config_snapshot,
            provenance_payload=source_meta,
            parent_batch_id=int(source_batch_id),
            summary_payload=summary_payload,
        )
    else:
        resolved_runtime_output = cast(PortMatrixSweep | PortMatrixSweepRun, runtime_output)
        trace_specs = build_post_processed_trace_specs(runtime_output=resolved_runtime_output)
        batch.result_payload = persist_trace_batch_bundle(
            bundle_id=int(batch_id),
            design_id=design_id,
            design_name=design_name,
            source_kind="circuit_simulation",
            stage_kind="postprocess",
            setup_kind="circuit_simulation.postprocess",
            setup_payload=config_snapshot,
            provenance_payload=source_meta,
            trace_specs=trace_specs,
            parent_batch_id=int(source_batch_id),
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
        raise ValueError("Failed to allocate one or more post-processing trace metadata IDs.")
    uow.result_bundles.attach_data_records(bundle_id=int(batch_id), data_record_ids=record_ids)
    uow.result_bundles.mark_completed(int(batch_id), summary_payload=summary_payload)
    return {
        "batch_id": int(batch_id),
        "source_batch_id": int(source_batch_id),
        **summary_payload,
    }


def mark_post_processing_batch_failed(
    *,
    uow: SqliteUnitOfWork,
    batch_id: int,
    error_code: str,
    error_summary: str,
    source_batch_id: int | None = None,
) -> None:
    """Persist one stable post-processing batch failure summary."""
    summary_payload: dict[str, Any] = {
        "error_code": str(error_code),
        "error_summary": str(error_summary),
        "phase": "failed",
    }
    if source_batch_id is not None:
        summary_payload["source_batch_id"] = int(source_batch_id)
    uow.result_bundles.mark_failed(int(batch_id), summary_payload=summary_payload)
