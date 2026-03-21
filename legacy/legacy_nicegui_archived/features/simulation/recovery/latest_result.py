"""Latest-result and persisted restore helpers for simulation recovery."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from typing import Any

from core.shared.persistence import SqliteUnitOfWork
from core.shared.persistence.repositories.contracts import ResultBundleSnapshot
from core.simulation.application.trace_architecture import is_trace_batch_bundle_payload
from core.simulation.domain.circuit import SimulationResult

UnitOfWorkFactory = Callable[[], Any]
DecodeResultPayload = Callable[[Any], tuple[SimulationResult | None, dict[str, Any] | None]]


def _trace_batch_payload_from_snapshot(
    snapshot: ResultBundleSnapshot | None,
) -> Mapping[str, Any] | None:
    """Return one canonical trace-batch payload from a detached snapshot."""
    if not isinstance(snapshot, Mapping):
        return None
    payload = snapshot.get("result_payload")
    if isinstance(payload, Mapping) and is_trace_batch_bundle_payload(payload):
        return payload
    return None


def _resolved_batch_source_stage_from_snapshot(
    snapshot: ResultBundleSnapshot | None,
) -> tuple[str, str]:
    """Resolve one canonical source/stage tuple across legacy and trace-batch snapshots."""
    payload = _trace_batch_payload_from_snapshot(snapshot)
    if isinstance(payload, Mapping):
        trace_batch_record = payload.get("trace_batch_record", {})
        if isinstance(trace_batch_record, Mapping):
            return (
                str(trace_batch_record.get("source_kind", "")).strip(),
                str(trace_batch_record.get("stage_kind", "")).strip(),
            )
    if not isinstance(snapshot, Mapping):
        return ("", "")
    source_meta = snapshot.get("source_meta")
    if not isinstance(source_meta, Mapping):
        return ("", "")
    return (
        str(source_meta.get("source_kind", "")).strip(),
        str(source_meta.get("stage_kind", "")).strip(),
    )


def _source_simulation_bundle_id_from_snapshot(
    snapshot: ResultBundleSnapshot | None,
) -> int | None:
    """Extract one raw simulation parent bundle id from persisted provenance."""
    if not isinstance(snapshot, Mapping):
        return None
    payload = _trace_batch_payload_from_snapshot(snapshot)
    if isinstance(payload, Mapping):
        trace_batch_record = payload.get("trace_batch_record", {})
        if isinstance(trace_batch_record, Mapping):
            parent_batch_id = trace_batch_record.get("parent_batch_id")
            if parent_batch_id is not None:
                try:
                    return int(parent_batch_id)
                except (TypeError, ValueError):
                    pass
            provenance_payload = trace_batch_record.get("provenance_payload", {})
            if isinstance(provenance_payload, Mapping):
                canonical_authority = provenance_payload.get("canonical_authority", {})
                if isinstance(canonical_authority, Mapping):
                    source_batch_id = canonical_authority.get("source_simulation_bundle_id")
                    if source_batch_id is not None:
                        try:
                            return int(source_batch_id)
                        except (TypeError, ValueError):
                            pass
    for container_key in ("config_snapshot", "source_meta"):
        container = snapshot.get(container_key)
        if not isinstance(container, Mapping):
            continue
        source_batch_id = container.get("source_simulation_bundle_id")
        if source_batch_id is None:
            continue
        try:
            return int(source_batch_id)
        except (TypeError, ValueError):
            continue
    return None


def _is_completed_raw_simulation_snapshot(snapshot: ResultBundleSnapshot | None) -> bool:
    """Return whether one detached snapshot is a completed raw circuit-simulation batch."""
    if not isinstance(snapshot, Mapping):
        return False
    if str(snapshot.get("status", "")).strip() != "completed":
        return False
    source_kind, stage_kind = _resolved_batch_source_stage_from_snapshot(snapshot)
    return source_kind == "circuit_simulation" and stage_kind == "raw"


def _is_completed_postprocess_snapshot(snapshot: ResultBundleSnapshot | None) -> bool:
    """Return whether one detached snapshot is a completed post-processing batch."""
    if not isinstance(snapshot, Mapping):
        return False
    if str(snapshot.get("status", "")).strip() != "completed":
        return False
    source_kind, stage_kind = _resolved_batch_source_stage_from_snapshot(snapshot)
    return source_kind == "circuit_simulation" and stage_kind == "postprocess"


def _resolve_persisted_post_processing_input_snapshot(
    uow: SqliteUnitOfWork,
    *,
    design_ids: Sequence[int],
) -> ResultBundleSnapshot | None:
    """Resolve the best persisted raw simulation batch for post-processing input."""
    candidate_source_ids: list[int] = []
    for design_id in design_ids:
        design_batches = sorted(
            uow.result_bundles.list_provenance_by_design(int(design_id)),
            key=lambda batch: int(batch.id or 0),
            reverse=True,
        )
        for batch in design_batches:
            if batch.id is None:
                continue
            snapshot = uow.result_bundles.get_snapshot(int(batch.id))
            if _is_completed_raw_simulation_snapshot(snapshot):
                return snapshot
            source_batch_id = _source_simulation_bundle_id_from_snapshot(snapshot)
            if source_batch_id is not None and source_batch_id not in candidate_source_ids:
                candidate_source_ids.append(source_batch_id)

    for batch_id in candidate_source_ids:
        snapshot = uow.result_bundles.get_snapshot(int(batch_id))
        if _is_completed_raw_simulation_snapshot(snapshot):
            return snapshot
    return None


def _resolve_latest_persisted_post_processing_snapshot(
    uow: SqliteUnitOfWork,
    *,
    design_ids: Sequence[int],
) -> ResultBundleSnapshot | None:
    """Resolve the latest completed persisted post-processing batch for one selected design."""
    for design_id in design_ids:
        design_batches = sorted(
            uow.result_bundles.list_provenance_by_design(int(design_id)),
            key=lambda batch: int(batch.id or 0),
            reverse=True,
        )
        for batch in design_batches:
            if batch.id is None:
                continue
            snapshot = uow.result_bundles.get_snapshot(int(batch.id))
            if _is_completed_postprocess_snapshot(snapshot):
                return snapshot
    return None


def invalidate_persisted_authority_caches(
    *,
    input_cache: dict[str, Any],
    output_cache: dict[str, Any],
) -> None:
    """Clear persisted recovery caches after new authority becomes available."""
    input_cache.update(
        {
            "selection": None,
            "bundle_id": None,
            "result": None,
            "sweep_payload": None,
            "snapshot": None,
        }
    )
    output_cache.update(
        {
            "selection": None,
            "bundle_id": None,
            "runtime_output": None,
            "flow_spec": None,
            "source_bundle_id": None,
        }
    )


def load_persisted_post_processing_input_bundle(
    *,
    selected_design_ids: Sequence[int],
    input_cache: dict[str, Any],
    get_unit_of_work: UnitOfWorkFactory,
    decode_simulation_result_payload: DecodeResultPayload,
) -> tuple[SimulationResult | None, dict[str, Any] | None, int | None]:
    """Load the latest raw simulation bundle eligible for post-processing restore."""
    selection = tuple(int(design_id) for design_id in selected_design_ids)
    if input_cache["selection"] == selection and input_cache["result"] is not None:
        return (
            input_cache["result"],
            input_cache["sweep_payload"],
            input_cache["bundle_id"],
        )
    if not selection:
        input_cache.update(
            {
                "selection": selection,
                "bundle_id": None,
                "result": None,
                "sweep_payload": None,
                "snapshot": None,
            }
        )
        return (None, None, None)
    with get_unit_of_work() as uow:
        snapshot = _resolve_persisted_post_processing_input_snapshot(
            uow,
            design_ids=selection,
        )
    if snapshot is None:
        input_cache.update(
            {
                "selection": selection,
                "bundle_id": None,
                "result": None,
                "sweep_payload": None,
                "snapshot": None,
            }
        )
        return (None, None, None)
    result, sweep_payload = decode_simulation_result_payload(snapshot["result_payload"])
    input_cache.update(
        {
            "selection": selection,
            "bundle_id": int(snapshot["id"]),
            "result": result,
            "sweep_payload": sweep_payload,
            "snapshot": snapshot,
        }
    )
    return (result, sweep_payload, int(snapshot["id"]))


def load_persisted_post_processing_output_bundle(
    *,
    selected_design_ids: Sequence[int],
    output_cache: dict[str, Any],
    get_unit_of_work: UnitOfWorkFactory,
) -> tuple[Mapping[str, Any] | None, dict[str, Any] | None, int | None, int | None]:
    """Load the latest persisted post-processing output bundle for the active selection."""
    selection = tuple(int(design_id) for design_id in selected_design_ids)
    if output_cache["selection"] == selection and isinstance(output_cache["runtime_output"], Mapping):
        return (
            output_cache["runtime_output"],
            output_cache["flow_spec"],
            output_cache["bundle_id"],
            output_cache["source_bundle_id"],
        )
    if not selection:
        output_cache.update(
            {
                "selection": selection,
                "bundle_id": None,
                "runtime_output": None,
                "flow_spec": None,
                "source_bundle_id": None,
            }
        )
        return (None, None, None, None)
    with get_unit_of_work() as uow:
        snapshot = _resolve_latest_persisted_post_processing_snapshot(
            uow,
            design_ids=selection,
        )
    payload = _trace_batch_payload_from_snapshot(snapshot)
    if payload is None:
        output_cache.update(
            {
                "selection": selection,
                "bundle_id": None,
                "runtime_output": None,
                "flow_spec": None,
                "source_bundle_id": None,
            }
        )
        return (None, None, None, None)
    flow_spec = (
        dict(snapshot.get("config_snapshot"))
        if isinstance(snapshot, Mapping) and isinstance(snapshot.get("config_snapshot"), Mapping)
        else None
    )
    bundle_id = int(snapshot["id"]) if isinstance(snapshot, Mapping) else None
    source_bundle_id = _source_simulation_bundle_id_from_snapshot(snapshot)
    output_cache.update(
        {
            "selection": selection,
            "bundle_id": bundle_id,
            "runtime_output": dict(payload),
            "flow_spec": flow_spec,
            "source_bundle_id": source_bundle_id,
        }
    )
    return (dict(payload), flow_spec, bundle_id, source_bundle_id)
