"""Trace-record compatibility helpers for analysis consumers."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from core.analysis.domain.value_objects import TraceKind

_MISSING = object()

_FAMILY_ALIASES: dict[str, str] = {
    "s": TraceKind.S_PARAMETERS.value,
    "s_matrix": TraceKind.S_PARAMETERS.value,
    "scattering": TraceKind.S_PARAMETERS.value,
    "scattering_matrix": TraceKind.S_PARAMETERS.value,
    "y": TraceKind.Y_PARAMETERS.value,
    "y_matrix": TraceKind.Y_PARAMETERS.value,
    "admittance": TraceKind.Y_PARAMETERS.value,
    "admittance_matrix": TraceKind.Y_PARAMETERS.value,
    "z": TraceKind.Z_PARAMETERS.value,
    "z_matrix": TraceKind.Z_PARAMETERS.value,
    "impedance": TraceKind.Z_PARAMETERS.value,
    "impedance_matrix": TraceKind.Z_PARAMETERS.value,
}

_REPRESENTATION_ALIASES: dict[str, str] = {
    "imag": "imaginary",
    "im": "imaginary",
    "mag": "magnitude",
    "abs": "magnitude",
    "re": "real",
}

_INLINE_VALUE_KEYS: tuple[str, ...] = (
    "values",
    "trace_values",
    "inline_values",
    "numeric_payload",
    "payload_values",
)

_AXIS_VALUE_KEYS: tuple[str, ...] = (
    "axis_values",
    "axes_values",
    "axis_payload",
)


@dataclass(frozen=True)
class NormalizedTraceRecord:
    """Minimal trace shape consumed by characterization flows."""

    id: int | None
    dataset_id: int | None
    data_type: str
    parameter: str
    representation: str
    axes: list[dict[str, Any]]
    values: object
    store_ref: Mapping[str, Any] | None = None
    design_id: int | None = None

    def trace_shape(self) -> tuple[int, ...]:
        """Return shape metadata without requiring inline values to be populated."""
        if isinstance(self.store_ref, Mapping):
            raw_shape = self.store_ref.get("shape")
            if isinstance(raw_shape, Sequence) and not isinstance(raw_shape, str | bytes):
                return tuple(int(dimension) for dimension in raw_shape)

        shape: list[int] = []
        current: object = self.values
        while isinstance(current, Sequence) and not isinstance(current, str | bytes):
            shape.append(len(current))
            if not current:
                break
            current = current[0]
        return tuple(shape)

    def axis_length(self, index: int) -> int:
        """Return one axis length from metadata or shape hints."""
        if index >= len(self.axes):
            return 0
        axis = self.axes[index]
        raw_length = axis.get("length")
        if raw_length is not None:
            return int(raw_length)
        raw_values = axis.get("values")
        if isinstance(raw_values, Sequence) and not isinstance(raw_values, str | bytes):
            return len(raw_values)
        shape = self.trace_shape()
        if index < len(shape):
            return int(shape[index])
        return 0


def _field(record: object, *names: str) -> object:
    for name in names:
        if isinstance(record, Mapping) and name in record:
            return record[name]
        value = getattr(record, name, _MISSING)
        if value is not _MISSING:
            return value
    return None


def _normalize_axis_values(
    raw_axis_values: object,
) -> Mapping[str, object] | Sequence[object] | None:
    if isinstance(raw_axis_values, Mapping):
        return raw_axis_values
    if isinstance(raw_axis_values, Sequence) and not isinstance(raw_axis_values, str | bytes):
        return raw_axis_values
    return None


def _axis_values_source(record: object) -> Mapping[str, object] | Sequence[object] | None:
    containers = (
        record,
        _field(record, "trace_meta"),
        _field(record, "store_ref"),
    )
    for container in containers:
        if not isinstance(container, Mapping):
            continue
        for key in _AXIS_VALUE_KEYS:
            normalized = _normalize_axis_values(container.get(key))
            if normalized is not None:
                return normalized
    return None


def _inline_values(record: object) -> object:
    containers = (
        record,
        _field(record, "trace_meta"),
        _field(record, "store_ref"),
    )
    for container in containers:
        if isinstance(container, Mapping):
            for key in _INLINE_VALUE_KEYS:
                if key in container:
                    return container[key]
        else:
            for key in _INLINE_VALUE_KEYS:
                value = getattr(container, key, _MISSING)
                if value is not _MISSING:
                    return value
    return []


def _copy_axes(raw_axes: object) -> list[dict[str, Any]]:
    if not isinstance(raw_axes, Sequence) or isinstance(raw_axes, str | bytes):
        return []
    axes: list[dict[str, Any]] = []
    for axis in raw_axes:
        if isinstance(axis, Mapping):
            axes.append(dict(axis))
    return axes


def _attach_axis_values(
    *,
    axes: list[dict[str, Any]],
    axis_values: Mapping[str, object] | Sequence[object] | None,
) -> list[dict[str, Any]]:
    if axis_values is None:
        return axes

    if isinstance(axis_values, Mapping):
        by_name = {str(key).strip().casefold(): value for key, value in axis_values.items()}
        for axis in axes:
            axis_name = str(axis.get("name", "")).strip().casefold()
            if "values" in axis or axis_name not in by_name:
                continue
            axis["values"] = by_name[axis_name]
        return axes

    for index, axis in enumerate(axes):
        if "values" in axis or index >= len(axis_values):
            continue
        axis["values"] = axis_values[index]
    return axes


def _normalize_data_type(raw_value: object) -> str:
    token = str(raw_value or "").strip().lower()
    if not token:
        return ""
    canonical = _FAMILY_ALIASES.get(token)
    if canonical is not None:
        return canonical
    kind = TraceKind.from_token(token)
    return "" if kind is TraceKind.UNKNOWN else kind.value


def _normalize_representation(raw_value: object) -> str:
    token = str(raw_value or "").strip().lower()
    return _REPRESENTATION_ALIASES.get(token, token)


def trace_record_data_type(record: object) -> str:
    """Return the canonical analysis data-type token for one trace-like object."""
    return _normalize_data_type(_field(record, "family", "data_type"))


def trace_record_parameter(record: object) -> str:
    """Return the parameter token for one trace-like object."""
    return str(_field(record, "parameter") or "").strip()


def trace_record_representation(record: object) -> str:
    """Return the normalized representation token for one trace-like object."""
    return _normalize_representation(_field(record, "representation"))


def trace_record_dataset_id(record: object) -> int | None:
    """Return the persisted dataset authority identifier for one trace-like object."""
    raw_value = _field(record, "dataset_id")
    if raw_value is None:
        return None
    return int(raw_value) if isinstance(raw_value, int | str) else None


def trace_record_design_id(record: object) -> int | None:
    """Return the canonical dataset-local design scope identifier."""
    raw_value = _field(record, "design_id")
    if raw_value is None:
        return None
    return int(raw_value) if isinstance(raw_value, int | str) else None


def trace_record_axes(record: object) -> list[dict[str, Any]]:
    """Return axes with compatibility support for externalized axis-value payloads."""
    axes = _copy_axes(_field(record, "axes"))
    return _attach_axis_values(axes=axes, axis_values=_axis_values_source(record))


def trace_record_values(record: object) -> object:
    """Return inline numeric values when available on the trace-like object."""
    return _inline_values(record)


def normalize_trace_record(record: object) -> NormalizedTraceRecord:
    """Project one trace-like object into the canonical analysis shape."""
    raw_id = _field(record, "id")
    raw_store_ref = _field(record, "store_ref")
    return NormalizedTraceRecord(
        id=int(raw_id) if isinstance(raw_id, int | str) else None,
        dataset_id=trace_record_dataset_id(record),
        design_id=trace_record_design_id(record),
        data_type=trace_record_data_type(record),
        parameter=trace_record_parameter(record),
        representation=trace_record_representation(record),
        axes=trace_record_axes(record),
        values=trace_record_values(record),
        store_ref=raw_store_ref if isinstance(raw_store_ref, Mapping) else None,
    )


__all__ = [
    "NormalizedTraceRecord",
    "normalize_trace_record",
    "trace_record_axes",
    "trace_record_data_type",
    "trace_record_design_id",
    "trace_record_dataset_id",
    "trace_record_parameter",
    "trace_record_representation",
    "trace_record_values",
]
