"""Helpers for loading store-backed traces into analysis-friendly payloads."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import numpy as np

from core.analysis.domain import NormalizedTraceRecord, normalize_trace_record
from core.shared.persistence import LocalZarrTraceStore


def _axis_has_values(axis: Mapping[str, object]) -> bool:
    raw_values = axis.get("values")
    return isinstance(raw_values, list) and bool(raw_values)


def _needs_materialization(record: NormalizedTraceRecord) -> bool:
    if record.store_ref is None:
        return False
    if isinstance(record.values, list) and record.values:
        return any(not _axis_has_values(axis) for axis in record.axes)
    return True


def materialize_trace_record(
    record: object,
    *,
    trace_store: LocalZarrTraceStore | None = None,
) -> NormalizedTraceRecord:
    """Return one trace with axis arrays and numeric payload loaded when needed."""
    normalized = normalize_trace_record(record)
    if not _needs_materialization(normalized):
        return normalized
    if normalized.store_ref is None:
        return normalized

    store = trace_store or LocalZarrTraceStore()
    shape = tuple(int(dimension) for dimension in normalized.store_ref.get("shape", []))
    selection = tuple(slice(None) for _ in shape)
    values = store.read_trace_slice(normalized.store_ref, selection=selection)

    axes: list[dict[str, Any]] = []
    for axis in normalized.axes:
        copied_axis = dict(axis)
        if not _axis_has_values(copied_axis):
            axis_name = str(copied_axis.get("name", "")).strip()
            if axis_name:
                copied_axis["values"] = store.read_axis_slice(
                    normalized.store_ref,
                    axis_name=axis_name,
                ).tolist()
        axes.append(copied_axis)

    return NormalizedTraceRecord(
        id=normalized.id,
        dataset_id=normalized.dataset_id,
        data_type=normalized.data_type,
        parameter=normalized.parameter,
        representation=normalized.representation,
        axes=axes,
        values=np.asarray(values).tolist(),
        store_ref=normalized.store_ref,
    )


__all__ = ["materialize_trace_record"]
