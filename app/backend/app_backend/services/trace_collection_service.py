from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

from app_backend.domain.datasets import (
    CharacterizationAnalysisRegistryRow,
    CharacterizationCollectionMemberSummary,
    CharacterizationDataCollectionReview,
    CharacterizationInputCollectionPayload,
    CharacterizationReviewAnalysisSummary,
    TraceDetail,
)
from app_backend.domain.trace_structures import derive_input_collection_payload


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
            self._materialize_trace_for_collection(detail) for detail in trace_details
        )
        return derive_input_collection_payload(materialized)

    def derive_data_collection_review_from_trace_details(
        self,
        trace_details: Sequence[TraceDetail],
        registry_rows: Sequence[CharacterizationAnalysisRegistryRow],
    ) -> CharacterizationDataCollectionReview | None:
        collection = self.derive_input_collection_payload_from_trace_details(trace_details)
        if collection is None:
            return None
        runnable = tuple(
            CharacterizationReviewAnalysisSummary(
                analysis_id=row.analysis_id,
                label=row.label,
                availability_state=row.availability_state,
                prerequisite_state=row.prerequisite_state,
                summary=row.trace_compatibility.summary,
            )
            for row in registry_rows
            if row.prerequisite_state == "ready"
            and row.availability_state in {"recommended", "available"}
        )
        blocked = tuple(
            CharacterizationReviewAnalysisSummary(
                analysis_id=row.analysis_id,
                label=row.label,
                availability_state=row.availability_state,
                prerequisite_state=row.prerequisite_state,
                summary=(
                    row.upstream_result_requirement.summary
                    if row.upstream_result_requirement is not None
                    and len(row.upstream_result_requirement.summary) > 0
                    and row.prerequisite_state != "ready"
                    else row.trace_compatibility.summary
                ),
            )
            for row in registry_rows
            if not (
                row.prerequisite_state == "ready"
                and row.availability_state in {"recommended", "available"}
            )
        )
        members = tuple(
            CharacterizationCollectionMemberSummary(
                member_key=_member_key(detail),
                trace_id=detail.trace_id,
                label=_member_label(detail),
                source_kind=detail.source_kind,
                stage_kind=detail.stage_kind,
                trace_mode_group=detail.trace_mode_group,
                family=detail.family,
                parameter=detail.parameter,
                representation=detail.representation,
                provenance_summary=_member_provenance_summary(detail),
                axis_signature=detail.axis_signature,
                collection_key=(
                    detail.collection_projection.collection_key
                    if detail.collection_projection is not None
                    else None
                ),
            )
            for detail in trace_details
        )
        source_coverage: dict[str, int] = {}
        for detail in trace_details:
            source_coverage[detail.source_kind] = source_coverage.get(detail.source_kind, 0) + 1
        readiness_state = (
            "ready" if len(runnable) > 0 else ("inspect_only" if len(blocked) > 0 else "blocked")
        )
        trace_noun = "trace" if collection.trace_count == 1 else "traces"
        return CharacterizationDataCollectionReview(
            selected_trace_ids=collection.selected_trace_ids,
            selection_summary=(
                f"{collection.trace_count} selected {trace_noun} materialize a derived "
                "characterization collection."
            ),
            shared_axes=collection.shared_axes,
            available_sweep_axes=collection.available_sweep_axes,
            collection_members=members,
            source_coverage=source_coverage,
            grouping_summary=collection.grouping_summary,
            readiness_state=readiness_state,
            runnable_analyses=runnable,
            blocked_analyses=blocked,
            collection_projection=collection.collection_projection,
        )

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


def _member_key(detail: TraceDetail) -> str:
    return f"{detail.source_kind}:{detail.trace_id}"


def _member_label(detail: TraceDetail) -> str:
    return f"{detail.source_kind.replace('_', ' ')} · {detail.parameter} ({detail.representation})"


def _member_provenance_summary(detail: TraceDetail) -> str:
    preview_payload = detail.preview_payload
    if isinstance(preview_payload, dict):
        raw_summary = preview_payload.get("provenance_summary")
        if isinstance(raw_summary, str) and len(raw_summary) > 0:
            return raw_summary
    return (
        f"{detail.source_kind.replace('_', ' ')} {detail.parameter} {detail.representation} trace."
    )
