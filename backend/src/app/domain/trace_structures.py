from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, cast

from src.app.domain.datasets import (
    CharacterizationInputCollectionPayload,
    InputCollectionAxis,
    InputCollectionTraceSummary,
    TraceAxesSummary,
    TraceAxis,
    TraceCollectionProjection,
)


@dataclass(frozen=True)
class TraceStructureSummarySurface:
    ndim: int
    shape: tuple[int, ...]
    axes_summary: TraceAxesSummary
    axis_signature: str
    available_sweep_axes: tuple[str, ...]
    collection_projection: TraceCollectionProjection | None


@dataclass(frozen=True)
class _NormalizedAxis:
    name: str
    unit: str
    length: int
    coordinate_digest: str
    values: tuple[float, ...] = ()


def build_axis_coordinate_digest(
    *,
    axis_name: str,
    unit: str,
    length: int,
    values: Sequence[float] | None = None,
) -> str:
    normalized_values = (
        [round(float(value), 12) for value in values]
        if values is not None
        else None
    )
    payload = {
        "name": axis_name,
        "unit": unit,
        "length": int(length),
        "values": normalized_values,
    }
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()[:20]


def build_trace_structure_summary(
    *,
    dataset_id: str,
    design_id: str,
    family: str,
    trace_mode_group: str,
    source_kind: str,
    stage_kind: str,
    axes: Sequence[TraceAxis | Mapping[str, object]],
) -> TraceStructureSummarySurface:
    normalized_axes = tuple(_normalize_axis(axis) for axis in axes)
    shape = tuple(axis.length for axis in normalized_axes)
    axis_summary = TraceAxesSummary(
        rank=len(normalized_axes),
        axis_names=tuple(axis.name for axis in normalized_axes),
        axis_units=tuple(axis.unit for axis in normalized_axes),
        axis_lengths=shape,
    )
    axis_signature = "axsig_" + _stable_digest(
        {
            "axes": [
                {
                    "name": axis.name,
                    "unit": axis.unit,
                    "length": axis.length,
                    "coordinate_digest": axis.coordinate_digest,
                }
                for axis in normalized_axes
            ]
        }
    )
    available_sweep_axes = tuple(
        axis.name for index, axis in enumerate(normalized_axes) if index > 0 and axis.length > 1
    )
    collection_projection = (
        TraceCollectionProjection(
            collection_key="collection_"
            + _stable_digest(
                {
                    "dataset_id": dataset_id,
                    "design_id": design_id,
                    "family": family,
                    "axis_signature": axis_signature,
                }
            ),
            kind="trace_structure_group",
            group_label=_build_collection_group_label(
                family=family,
                axis_names=axis_summary.axis_names,
            ),
        )
        if len(normalized_axes) > 0
        else None
    )
    return TraceStructureSummarySurface(
        ndim=len(normalized_axes),
        shape=shape,
        axes_summary=axis_summary,
        axis_signature=axis_signature,
        available_sweep_axes=available_sweep_axes,
        collection_projection=collection_projection,
    )


def derive_input_collection_payload(
    traces: Sequence[object],
) -> CharacterizationInputCollectionPayload | None:
    if len(traces) == 0:
        return None
    selected_trace_ids = tuple(_trace_id(trace) for trace in traces)
    normalized_axes_by_trace = [
        tuple(_normalize_axis(axis) for axis in _trace_axes(trace))
        for trace in traces
    ]
    shared_axes = _shared_axes(normalized_axes_by_trace)
    sweep_axes = tuple(
        axis.name
        for index, axis in enumerate(shared_axes)
        if index > 0 and axis.length > 1
    )
    axis_signatures = tuple(
        signature
        for trace in traces
        if (signature := _trace_axis_signature(trace)) is not None
    )
    unique_axis_signatures = tuple(dict.fromkeys(axis_signatures))
    collection_projection = _common_collection_projection(traces)
    return CharacterizationInputCollectionPayload(
        selected_trace_ids=selected_trace_ids,
        trace_count=len(selected_trace_ids),
        axis_signature=unique_axis_signatures[0] if len(unique_axis_signatures) == 1 else None,
        available_sweep_axes=sweep_axes,
        shared_axes=tuple(
            InputCollectionAxis(
                name=axis.name,
                unit=axis.unit,
                length=axis.length,
                values=axis.values,
            )
            for axis in shared_axes
        ),
        grouping_summary=_grouping_summary(traces),
        collection_projection=collection_projection,
        traces=tuple(
            InputCollectionTraceSummary(
                trace_id=_trace_id(trace),
                family=cast(str, _field(trace, "family") or ""),
                parameter=str(_field(trace, "parameter") or ""),
                representation=str(_field(trace, "representation") or ""),
                axis_signature=str(_trace_axis_signature(trace) or ""),
                collection_key=(
                    collection_projection.collection_key
                    if collection_projection is not None
                    and _trace_collection_key(trace) == collection_projection.collection_key
                    else _trace_collection_key(trace)
                ),
            )
            for trace in traces
        ),
    )


def _shared_axes(
    axes_by_trace: Sequence[Sequence[_NormalizedAxis]],
) -> tuple[_NormalizedAxis, ...]:
    if len(axes_by_trace) == 0:
        return ()
    first = tuple(axes_by_trace[0])
    shared: list[_NormalizedAxis] = []
    for index, axis in enumerate(first):
        if any(index >= len(candidate) for candidate in axes_by_trace[1:]):
            break
        peer_axes = [candidate[index] for candidate in axes_by_trace[1:]]
        if all(_axes_share_semantic_identity(axis, candidate) for candidate in peer_axes):
            shared.append(_shared_axis(axis, peer_axes))
            continue
        break
    return tuple(shared)


def _axes_share_semantic_identity(left: _NormalizedAxis, right: _NormalizedAxis) -> bool:
    return (
        left.name == right.name
        and left.unit == right.unit
        and left.length == right.length
    )


def _shared_axis(
    axis: _NormalizedAxis,
    peers: Sequence[_NormalizedAxis],
) -> _NormalizedAxis:
    if all(axis.coordinate_digest == candidate.coordinate_digest for candidate in peers):
        return axis
    return _NormalizedAxis(
        name=axis.name,
        unit=axis.unit,
        length=axis.length,
        coordinate_digest=build_axis_coordinate_digest(
            axis_name=axis.name,
            unit=axis.unit,
            length=axis.length,
        ),
    )


def _grouping_summary(traces: Sequence[object]) -> str:
    collection_keys = {
        collection_key
        for trace in traces
        if (collection_key := _trace_collection_key(trace)) is not None
    }
    if len(collection_keys) <= 1:
        return f"{len(traces)} selected traces share one structural collection."
    return f"{len(traces)} selected traces span {len(collection_keys)} structural collections."


def _common_collection_projection(
    traces: Sequence[object],
) -> TraceCollectionProjection | None:
    projections = [
        projection
        for trace in traces
        if isinstance(
            (projection := _field(trace, "collection_projection")),
            TraceCollectionProjection,
        )
    ]
    if len(projections) != len(traces):
        return None
    first = projections[0]
    if any(projection.collection_key != first.collection_key for projection in projections[1:]):
        return None
    return first


def _trace_collection_key(trace: object) -> str | None:
    projection = _field(trace, "collection_projection")
    if isinstance(projection, TraceCollectionProjection):
        return projection.collection_key
    if isinstance(projection, Mapping):
        raw_key = projection.get("collection_key")
        if isinstance(raw_key, str):
            return raw_key
    return None


def _trace_axis_signature(trace: object) -> str | None:
    raw_value = _field(trace, "axis_signature")
    return str(raw_value) if isinstance(raw_value, str) and raw_value else None


def _trace_axes(trace: object) -> tuple[TraceAxis | Mapping[str, object], ...]:
    raw_axes = _field(trace, "axes")
    if isinstance(raw_axes, Sequence) and not isinstance(raw_axes, str | bytes):
        return tuple(
            axis
            for axis in raw_axes
            if isinstance(axis, TraceAxis | Mapping)
        )
    return ()


def _trace_id(trace: object) -> str:
    return str(_field(trace, "trace_id") or "")


def _normalize_axis(axis: TraceAxis | Mapping[str, object]) -> _NormalizedAxis:
    if isinstance(axis, TraceAxis):
        return _NormalizedAxis(
            name=axis.name,
            unit=axis.unit,
            length=int(axis.length),
            coordinate_digest=build_axis_coordinate_digest(
                axis_name=axis.name,
                unit=axis.unit,
                length=axis.length,
            ),
        )
    raw_values = axis.get("values")
    values = tuple(
        float(value)
        for value in raw_values
        if isinstance(value, int | float)
    ) if isinstance(raw_values, Sequence) and not isinstance(raw_values, str | bytes) else ()
    coordinate_digest = axis.get("coordinate_digest")
    resolved_name = str(axis.get("name", "")).strip()
    resolved_unit = str(axis.get("unit", "")).strip()
    resolved_length = int(axis.get("length", len(values)) or len(values))
    return _NormalizedAxis(
        name=resolved_name,
        unit=resolved_unit,
        length=resolved_length,
        coordinate_digest=(
            str(coordinate_digest)
            if isinstance(coordinate_digest, str) and coordinate_digest
            else build_axis_coordinate_digest(
                axis_name=resolved_name,
                unit=resolved_unit,
                length=resolved_length,
                values=values or None,
            )
        ),
        values=values,
    )


def _stable_digest(payload: Mapping[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()[:20]


def _field(record: object, field_name: str) -> object:
    if isinstance(record, Mapping):
        return record.get(field_name)
    return getattr(record, field_name, None)


def _build_collection_group_label(*, family: str, axis_names: Sequence[str]) -> str:
    family_label = family.replace("_", " ").upper()
    if len(axis_names) == 0:
        return family_label
    return f"{family_label} · {' x '.join(axis_names)}"
