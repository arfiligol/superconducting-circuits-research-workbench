"""Materialize trace-first records from inline payloads or the TraceStore."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

import numpy as np

from core.analysis.domain import NormalizedTraceRecord, normalize_trace_record
from core.shared.persistence import LocalZarrTraceStore, TraceStore


def _has_sequence_values(value: object) -> bool:
    return isinstance(value, Sequence) and not isinstance(value, str | bytes) and len(value) > 0


def _materialized_axes(
    record: NormalizedTraceRecord,
    *,
    trace_store: TraceStore,
) -> list[dict[str, Any]]:
    axes = [dict(axis) for axis in record.axes]
    store_ref = record.store_ref
    if not isinstance(store_ref, Mapping):
        return axes

    for axis in axes:
        if _has_sequence_values(axis.get("values")):
            continue
        axis_name = str(axis.get("name", "")).strip()
        if not axis_name:
            continue
        axis_values = trace_store.read_axis_slice(store_ref, axis_name=axis_name)
        axis["values"] = axis_values.tolist()
        axis["length"] = int(axis_values.shape[0])
    return axes


def _materialized_values(
    record: NormalizedTraceRecord,
    *,
    trace_store: TraceStore,
) -> object:
    if _has_sequence_values(record.values):
        return record.values

    store_ref = record.store_ref
    if not isinstance(store_ref, Mapping):
        return record.values

    selection = tuple(slice(None) for _ in range(len(record.trace_shape())))
    if not selection:
        return record.values
    return trace_store.read_trace_slice(store_ref, selection=selection).tolist()


def materialize_trace_record(
    record: object,
    *,
    trace_store: TraceStore | None = None,
) -> NormalizedTraceRecord:
    """Return one trace record with axis arrays and numeric payload hydrated."""
    normalized = normalize_trace_record(record)
    store_ref = normalized.store_ref
    if not isinstance(store_ref, Mapping) or not store_ref:
        return normalized

    store = trace_store or LocalZarrTraceStore()
    return NormalizedTraceRecord(
        id=normalized.id,
        dataset_id=normalized.dataset_id,
        data_type=normalized.data_type,
        parameter=normalized.parameter,
        representation=normalized.representation,
        axes=_materialized_axes(normalized, trace_store=store),
        values=_materialized_values(normalized, trace_store=store),
        store_ref=store_ref,
    )


def materialize_trace_values(
    record: object,
    *,
    trace_store: TraceStore | None = None,
) -> np.ndarray:
    """Load one trace payload as a NumPy array."""
    materialized = materialize_trace_record(record, trace_store=trace_store)
    return np.asarray(materialized.values)


__all__ = [
    "materialize_trace_record",
    "materialize_trace_values",
]
