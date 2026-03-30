from __future__ import annotations

from collections.abc import Mapping, Sequence

import numpy as np
from core.shared.persistence import LocalZarrTraceStore, get_trace_store_path

from src.app.domain.datasets import CharacterizationInputCollectionPayload, TraceDetail
from src.app.domain.trace_structures import derive_input_collection_payload


def derive_input_collection_payload_from_trace_details(
    trace_details: Sequence[TraceDetail],
) -> CharacterizationInputCollectionPayload | None:
    if len(trace_details) == 0:
        return None
    materialized = tuple(_materialize_trace_for_collection(detail) for detail in trace_details)
    return derive_input_collection_payload(materialized)


def _materialize_trace_for_collection(detail: TraceDetail) -> dict[str, object]:
    return {
        "trace_id": detail.trace_id,
        "family": detail.family,
        "parameter": detail.parameter,
        "representation": detail.representation,
        "axis_signature": detail.axis_signature,
        "collection_projection": detail.collection_projection,
        "axes": [
            {
                "name": axis.name,
                "unit": axis.unit,
                "length": axis.length,
                "coordinate_digest": _axis_coordinate_digest(detail, axis.name),
                "values": _axis_values(detail, axis.name),
            }
            for axis in detail.axes
        ],
    }


def _axis_values(detail: TraceDetail, axis_name: str) -> tuple[float, ...]:
    store_ref = _payload_ref_to_store_ref(detail)
    if store_ref is not None:
        trace_store = LocalZarrTraceStore(root_path=get_trace_store_path())
        try:
            axis_values = trace_store.read_axis_slice(
                store_ref,
                axis_name=axis_name,
                selection=slice(None),
            )
        except (KeyError, ValueError, FileNotFoundError):
            pass
        else:
            return tuple(float(value) for value in np.asarray(axis_values).reshape(-1))
    return _axis_values_from_preview_payload(detail, axis_name)


def _axis_coordinate_digest(detail: TraceDetail, axis_name: str) -> str | None:
    for axis in detail.axes:
        if axis.name == axis_name and hasattr(axis, "coordinate_digest"):
            raw_value = getattr(axis, "coordinate_digest", None)
            if isinstance(raw_value, str) and raw_value:
                return raw_value
    return None


def _axis_values_from_preview_payload(
    detail: TraceDetail,
    axis_name: str,
) -> tuple[float, ...]:
    preview_payload = detail.preview_payload
    if not isinstance(preview_payload, Mapping):
        return ()
    if len(detail.axes) == 0 or axis_name != detail.axes[0].name:
        return ()
    raw_points = preview_payload.get("points")
    if not isinstance(raw_points, Sequence) or isinstance(raw_points, str | bytes):
        return ()
    values: list[float] = []
    for point in raw_points:
        if (
            isinstance(point, Sequence)
            and not isinstance(point, str | bytes)
            and len(point) >= 1
            and isinstance(point[0], int | float)
        ):
            values.append(float(point[0]))
    return tuple(values)


def _payload_ref_to_store_ref(detail: TraceDetail) -> Mapping[str, object] | None:
    payload_ref = detail.payload_ref
    if payload_ref is None:
        return None
    return {
        "backend": payload_ref.backend,
        "store_key": payload_ref.store_key,
        "store_uri": payload_ref.store_uri,
        "group_path": payload_ref.group_path,
        "array_path": payload_ref.array_path,
        "dtype": payload_ref.dtype,
        "shape": list(payload_ref.shape),
        "chunk_shape": list(payload_ref.chunk_shape),
        "schema_version": payload_ref.schema_version,
    }
