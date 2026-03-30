from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

from src.app.domain.datasets import CharacterizationInputCollectionPayload, TraceDetail
from src.app.domain.trace_structures import derive_input_collection_payload


class TraceAxisValueLoader(Protocol):
    def load_axis_values(
        self,
        detail: TraceDetail,
        axis_name: str,
    ) -> tuple[float, ...] | None: ...


class TraceCollectionService:
    def __init__(
        self,
        axis_value_loader: TraceAxisValueLoader | None = None,
    ) -> None:
        self._axis_value_loader = axis_value_loader

    def derive_input_collection_payload_from_trace_details(
        self,
        trace_details: Sequence[TraceDetail],
    ) -> CharacterizationInputCollectionPayload | None:
        if len(trace_details) == 0:
            return None
        materialized = tuple(
            self._materialize_trace_for_collection(detail)
            for detail in trace_details
        )
        return derive_input_collection_payload(materialized)

    def _materialize_trace_for_collection(self, detail: TraceDetail) -> dict[str, object]:
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
                    "coordinate_digest": None,
                    "values": self._axis_values(detail, axis.name),
                }
                for axis in detail.axes
            ],
        }

    def _axis_values(
        self,
        detail: TraceDetail,
        axis_name: str,
    ) -> tuple[float, ...]:
        if self._axis_value_loader is not None:
            loaded_values = self._axis_value_loader.load_axis_values(detail, axis_name)
            if loaded_values is not None:
                return loaded_values
        return self._axis_values_from_preview_payload(detail, axis_name)

    def _axis_values_from_preview_payload(
        self,
        detail: TraceDetail,
        axis_name: str,
    ) -> tuple[float, ...]:
        preview_payload = detail.preview_payload
        if not isinstance(preview_payload, dict):
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
