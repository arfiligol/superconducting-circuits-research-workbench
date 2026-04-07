from __future__ import annotations

import copy
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from functools import lru_cache
from hashlib import sha256
from pathlib import Path
from typing import Any

import numpy as np
from sc_core.execution import TaskResultHandle

from src.app.domain.admittance_result_contract import (
    AdmittanceResultMember,
    AdmittanceResultSurface,
    annotate_admittance_artifact_refs,
    build_admittance_artifact_refs,
    build_admittance_identify_surface,
    build_admittance_summary_metrics,
    parse_admittance_surface,
    query_admittance_artifact_payload,
    serialize_admittance_surface,
    summarize_admittance_surface,
)
from src.app.domain.characterization_analysis import get_characterization_analysis_spec
from src.app.domain.datasets import (
    CharacterizationAppliedTag,
    CharacterizationArtifactAxisSpec,
    CharacterizationArtifactMetricSpec,
    CharacterizationArtifactPayload,
    CharacterizationArtifactPayloadQuery,
    CharacterizationArtifactPreset,
    CharacterizationArtifactQuerySpec,
    CharacterizationArtifactRef,
    CharacterizationArtifactViewModeDefault,
    CharacterizationDesignatedMetricOption,
    CharacterizationDiagnostic,
    CharacterizationIdentifySurface,
    CharacterizationInputResultRef,
    CharacterizationResultDetail,
    CharacterizationResultSummary,
    CharacterizationRunHistoryRow,
    CharacterizationSourceParameterOption,
    DesignBrowseRow,
    TaggedCoreMetricSummary,
    TraceDetail,
    TraceMetadataSummary,
)
from src.app.domain.tasks import TaskDetail, TaskResultRefs
from src.app.infrastructure.persistence.storage_metadata_repository import (
    SqliteRewriteStorageMetadataRepository,
)
from src.app.infrastructure.storage_reference_factory import (
    build_metadata_record_ref,
    build_result_handle_ref,
    build_result_provenance_ref,
    build_trace_payload_ref,
)
from src.app.settings import get_settings


@dataclass(frozen=True)
class CharacterizationExecutionTrace:
    summary: TraceMetadataSummary
    detail: TraceDetail


@dataclass(frozen=True)
class CharacterizationExecutionRequest:
    task: TaskDetail
    design: DesignBrowseRow
    traces: tuple[CharacterizationExecutionTrace, ...]


@dataclass(frozen=True)
class PersistedCharacterizationExecutionResult:
    result_summary_payload: dict[str, object]
    result_refs: TaskResultRefs


@dataclass(frozen=True)
class _LoadedTraceSeries:
    summary: TraceMetadataSummary
    input_axis_key: str
    input_axis_label: str
    input_axis_unit: str | None
    input_axis_values: tuple[float, ...]
    frequencies_ghz: tuple[float, ...]
    values_grid: np.ndarray


@dataclass(frozen=True)
class _AdmittanceExtractionResult:
    selected_trace_ids: tuple[str, ...]
    surface: AdmittanceResultSurface
    residual_tensor: np.ndarray
    provenance_summary: str
    sources_summary: str


@dataclass(frozen=True)
class _PersistedRunPayload:
    result_summary: dict[str, object]
    run_history_row: dict[str, object]
    result_detail: dict[str, object]


class PersistedCharacterizationRepository:
    def __init__(
        self,
        storage_metadata_repository: SqliteRewriteStorageMetadataRepository,
    ) -> None:
        self._storage_metadata_repository = storage_metadata_repository

    def run_admittance_extraction(
        self,
        request: CharacterizationExecutionRequest,
    ) -> PersistedCharacterizationExecutionResult:
        if request.task.characterization_setup is None:
            raise ValueError("Characterization setup is missing.")

        loaded_traces = _load_execution_traces(request.traces)
        analysis = _run_admittance_extraction(
            task=request.task,
            loaded_traces=loaded_traces,
        )
        recorded_at = datetime.now(UTC)
        persisted_run = _persist_analysis_run(
            task=request.task,
            design=request.design,
            analysis=analysis,
            recorded_at=recorded_at,
        )
        projection_ref = _write_projection_trace(
            task=request.task,
            analysis_run_id=persisted_run.id,
            frequencies_ghz=loaded_traces[0].frequencies_ghz,
            residual_tensor=analysis.residual_tensor,
            input_axis_key=analysis.surface.input_axis_key,
            input_axis_unit=analysis.surface.input_axis_unit,
            input_axis_values=analysis.surface.input_axis_values,
            members=analysis.surface.members,
        )
        artifact_refs, report_path = _write_artifacts(
            result_id=_result_id_for_run(persisted_run.id),
            analysis=analysis,
        )
        payload = _build_persisted_run_payload(
            task=request.task,
            design=request.design,
            analysis_run_id=persisted_run.id,
            recorded_at=recorded_at,
            analysis=analysis,
            artifact_refs=artifact_refs,
        )
        persisted_run.summary_payload = {
            "result_id": payload.result_summary["result_id"],
            "result_summary": payload.result_summary,
            "run_history_row": payload.run_history_row,
            "result_detail": payload.result_detail,
            "admittance_surface": serialize_admittance_surface(analysis.surface),
        }
        _save_analysis_run(persisted_run)

        analysis_run_record = build_metadata_record_ref(
            "analysis_run",
            f"analysis_run:{persisted_run.id}",
            version=1,
        )
        result_handle_record = build_metadata_record_ref(
            "result_handle",
            f"result_handle:analysis_run:{persisted_run.id}",
            version=1,
        )
        report_handle = build_result_handle_ref(
            handle_id=f"analysis-run:{persisted_run.id}:report",
            kind="characterization_report",
            status="materialized",
            label="Persisted characterization report",
            metadata_record=result_handle_record,
            payload_backend="json_artifact",
            payload_format="json",
            payload_role="report_artifact",
            payload_locator=_artifact_locator(report_path),
            provenance_task_id=request.task.task_id,
            provenance=build_result_provenance_ref(
                source_dataset_id=request.task.dataset_id,
                source_task_id=request.task.task_id,
                analysis_run_record=analysis_run_record,
            ),
        )
        self._storage_metadata_repository.save_trace_payload(analysis_run_record, projection_ref)
        self._storage_metadata_repository.save_result_handle(report_handle)

        return PersistedCharacterizationExecutionResult(
            result_summary_payload={
                "summary": (
                    "Characterization completed from persisted design traces "
                    f"with mode capacity {len(analysis.surface.derived_axis_values)}."
                ),
                "characterization_result_id": payload.result_summary["result_id"],
            },
            result_refs=TaskResultRefs(
                result_handle=TaskResultHandle(analysis_run_id=persisted_run.id),
                metadata_records=(analysis_run_record, result_handle_record),
                trace_payload=projection_ref,
                result_handles=(report_handle,),
            ),
        )

    def list_result_summaries(
        self,
        dataset_id: str,
        design_id: str,
    ) -> tuple[CharacterizationResultSummary, ...]:
        rows = [
            summary
            for run in self._list_runs_for_design(dataset_id, design_id)
            if (summary := _summary_from_run(run)) is not None
        ]
        rows.sort(key=lambda row: row.updated_at, reverse=True)
        return tuple(rows)

    def list_run_history(
        self,
        dataset_id: str,
        design_id: str,
    ) -> tuple[CharacterizationRunHistoryRow, ...]:
        rows = [
            row
            for run in self._list_runs_for_design(dataset_id, design_id)
            if (row := _run_history_from_run(run)) is not None
        ]
        rows.sort(key=lambda row: row.updated_at, reverse=True)
        return tuple(rows)

    def get_result_detail(
        self,
        dataset_id: str,
        design_id: str,
        result_id: str,
    ) -> CharacterizationResultDetail | None:
        run = self._find_run(dataset_id, design_id, result_id)
        if run is None:
            return None
        return _detail_from_run(run)

    def get_artifact_payload(
        self,
        dataset_id: str,
        design_id: str,
        result_id: str,
        artifact_id: str,
        query: CharacterizationArtifactPayloadQuery,
    ) -> CharacterizationArtifactPayload | None:
        run = self._find_run(dataset_id, design_id, result_id)
        if run is None:
            return None
        surface = parse_admittance_surface(run.summary_payload.get("admittance_surface"))
        if surface is None:
            return None
        return query_admittance_artifact_payload(
            surface=surface,
            artifact_id=artifact_id,
            query=query,
        )

    def list_tagged_core_metrics(
        self,
        dataset_id: str,
    ) -> tuple[TaggedCoreMetricSummary, ...]:
        metrics_by_pair: dict[tuple[str, str], TaggedCoreMetricSummary] = {}
        for run in self._list_runs_for_dataset(dataset_id):
            detail = _detail_from_run(run)
            if detail is None:
                continue
            for applied_tag in detail.identify_surface.applied_tags:
                key = (applied_tag.source_parameter, applied_tag.designated_metric)
                metrics_by_pair[key] = TaggedCoreMetricSummary(
                    metric_id=_build_tagged_metric_id(dataset_id, applied_tag.designated_metric),
                    label=applied_tag.designated_metric_label,
                    source_parameter=applied_tag.source_parameter,
                    designated_metric=applied_tag.designated_metric,
                    tagged_at=applied_tag.tagged_at,
                )
        metrics = list(metrics_by_pair.values())
        metrics.sort(key=lambda metric: metric.tagged_at, reverse=True)
        return tuple(metrics)

    def apply_tagging(
        self,
        dataset_id: str,
        design_id: str,
        result_id: str,
        *,
        artifact_id: str,
        source_parameter: str,
        designated_metric: str,
    ) -> CharacterizationTaggingResultPayload | None:
        run = self._find_run(dataset_id, design_id, result_id)
        if run is None:
            return None
        detail = _detail_from_run(run)
        if detail is None:
            return None

        metric_option = next(
            (
                option
                for option in detail.identify_surface.designated_metrics
                if option.metric_key == designated_metric
            ),
            None,
        )
        if metric_option is None:
            raise ValueError("Designated metric is not available for this result.")

        tagged_at = _utc_timestamp(datetime.now(UTC))
        tagged_metric = TaggedCoreMetricSummary(
            metric_id=_build_tagged_metric_id(dataset_id, designated_metric),
            label=metric_option.label,
            source_parameter=source_parameter,
            designated_metric=designated_metric,
            tagged_at=tagged_at,
        )
        updated_detail = _detail_with_applied_tag(
            detail,
            artifact_id=artifact_id,
            source_parameter=source_parameter,
            metric_option=metric_option,
            tagged_at=tagged_at,
        )
        updated_payload = copy.deepcopy(run.summary_payload)
        updated_payload["result_detail"] = _detail_to_payload(updated_detail)
        run.summary_payload = updated_payload
        _save_analysis_run(run)
        return CharacterizationTaggingResultPayload(
            dataset_id=dataset_id,
            design_id=design_id,
            result_id=result_id,
            artifact_id=artifact_id,
            source_parameter=source_parameter,
            designated_metric=designated_metric,
            tagged_metric=tagged_metric,
        )

    def upsert_seed_result(
        self,
        *,
        summary: CharacterizationResultSummary,
        run_history: CharacterizationRunHistoryRow,
        detail: CharacterizationResultDetail,
        artifact_surface: AdmittanceResultSurface | None = None,
    ) -> None:
        existing = self._find_run(summary.dataset_id, summary.design_id, summary.result_id)
        payload = {
            "result_id": summary.result_id,
            "result_summary": _summary_to_payload(summary),
            "run_history_row": _run_history_to_payload(run_history),
            "result_detail": _detail_to_payload(detail),
        }
        if artifact_surface is not None:
            payload["admittance_surface"] = serialize_admittance_surface(artifact_surface)
        if existing is not None:
            existing.summary_payload = payload
            _save_analysis_run(existing)
            return

        updated_at = datetime.fromisoformat(summary.updated_at.replace("Z", "+00:00"))
        analysis_run_record = _core_symbols()["AnalysisRunRecord"](
            dataset_id=_stable_positive_int(summary.dataset_id),
            design_id=_stable_positive_int(summary.dataset_id, summary.design_id),
            analysis_id=summary.analysis_id,
            analysis_label=summary.title,
            run_id=run_history.run_id,
            status=summary.status,
            input_trace_ids=[
                _stable_positive_int(summary.dataset_id, summary.design_id, trace_id)
                for trace_id in detail.input_trace_ids
            ],
            input_batch_ids=[],
            input_scope="seeded_catalog",
            trace_mode_group="base",
            config_payload={},
            summary_payload=payload,
            created_at=updated_at,
            completed_at=updated_at,
        )
        with _core_symbols()["get_unit_of_work"]() as uow:
            uow.result_bundles.analysis_runs.add(analysis_run_record)
            uow.commit()

    def _find_run(
        self,
        dataset_id: str,
        design_id: str,
        result_id: str,
    ) -> Any | None:
        for run in self._list_runs_for_design(dataset_id, design_id):
            persisted_result_id = run.summary_payload.get("result_id")
            if isinstance(persisted_result_id, str) and persisted_result_id == result_id:
                return run
            summary = run.summary_payload.get("result_summary")
            if isinstance(summary, Mapping) and summary.get("result_id") == result_id:
                return run
        return None

    def _list_runs_for_design(
        self,
        dataset_id: str,
        design_id: str,
    ) -> tuple[Any, ...]:
        design_scope_id = _stable_positive_int(dataset_id, design_id)
        with _core_symbols()["get_unit_of_work"]() as uow:
            runs = uow.result_bundles.analysis_runs.list_by_design(design_scope_id)
        return tuple(
            run
            for run in runs
            if _matches_dataset_scope(run.summary_payload, dataset_id, design_id)
        )

    def _list_runs_for_dataset(
        self,
        dataset_id: str,
    ) -> tuple[Any, ...]:
        dataset_scope_id = _stable_positive_int(dataset_id)
        with _core_symbols()["get_unit_of_work"]() as uow:
            runs = uow.result_bundles.analysis_runs.list_by_dataset(dataset_scope_id)
        return tuple(
            run for run in runs if _matches_dataset_scope(run.summary_payload, dataset_id, None)
        )


@dataclass(frozen=True)
class CharacterizationTaggingResultPayload:
    dataset_id: str
    design_id: str
    result_id: str
    artifact_id: str
    source_parameter: str
    designated_metric: str
    tagged_metric: TaggedCoreMetricSummary


def ensure_core_runtime_path() -> None:
    workspace_src = Path(__file__).resolve().parents[4] / "src"
    if str(workspace_src) not in _core_symbols()["sys"].path:
        _core_symbols()["sys"].path.insert(0, str(workspace_src))


@lru_cache(maxsize=1)
def _core_symbols() -> dict[str, Any]:
    import sys

    workspace_src = Path(__file__).resolve().parents[4] / "src"
    if str(workspace_src) not in sys.path:
        sys.path.insert(0, str(workspace_src))

    from core.shared.persistence import get_unit_of_work
    from core.shared.persistence.models import AnalysisRunRecord
    from core.shared.persistence.trace_store import LocalZarrTraceStore, get_trace_store_path

    return {
        "AnalysisRunRecord": AnalysisRunRecord,
        "LocalZarrTraceStore": LocalZarrTraceStore,
        "get_trace_store_path": get_trace_store_path,
        "get_unit_of_work": get_unit_of_work,
        "sys": sys,
    }


def _load_execution_traces(
    traces: Sequence[CharacterizationExecutionTrace],
) -> tuple[_LoadedTraceSeries, ...]:
    return tuple(_load_trace_series(trace) for trace in traces)


def _load_trace_series(
    trace: CharacterizationExecutionTrace,
) -> _LoadedTraceSeries:
    detail = trace.detail
    payload_ref = detail.payload_ref
    if payload_ref is None:
        raise ValueError(f"Trace {detail.trace_id} is missing a persisted payload.")
    store_ref = _payload_ref_to_store_ref(payload_ref)
    trace_store = _core_symbols()["LocalZarrTraceStore"](
        root_path=_core_symbols()["get_trace_store_path"]()
    )
    try:
        frequencies = np.asarray(
            trace_store.read_axis_slice(
                store_ref,
                axis_name="frequency",
                selection=slice(None),
            ),
            dtype=np.float64,
        )
        selection = (
            tuple(slice(None) for _ in detail.axes) if len(detail.axes) > 0 else (slice(None),)
        )
        raw_values = np.asarray(trace_store.read_trace_slice(store_ref, selection=selection))
        input_axis_key, input_axis_label, input_axis_unit, input_axis_values, values_grid = (
            _materialize_trace_grid(
                trace=trace,
                trace_store=trace_store,
                store_ref=store_ref,
                raw_values=raw_values,
            )
        )
    except Exception:
        preview_points = _preview_points(detail.preview_payload)
        if preview_points is None:
            raise
        materialized = trace_store.write_trace(
            design_id=_stable_positive_int(detail.dataset_id, detail.design_id),
            batch_id=_stable_positive_int(detail.dataset_id, detail.design_id, detail.trace_id),
            trace_id=1,
            values=np.asarray([point[1] for point in preview_points], dtype=np.float64),
            axes=(
                {
                    "name": detail.axes[0].name if detail.axes else "frequency",
                    "unit": detail.axes[0].unit if detail.axes else "GHz",
                    "values": np.asarray([point[0] for point in preview_points], dtype=np.float64),
                },
            ),
            array_path=payload_ref.array_path,
            store_key=payload_ref.store_key,
            payload_role="analysis",
            writer_version="characterization.seed_trace_materialization",
        )
        store_ref = materialized.store_ref
        frequencies = np.asarray([point[0] for point in preview_points], dtype=np.float64)
        values_grid = np.asarray([[point[1]] for point in preview_points], dtype=np.float64)
        input_axis_key = "selected_scope"
        input_axis_label = "Selected trace bundle"
        input_axis_unit = None
        input_axis_values = (0.0,)

    return _LoadedTraceSeries(
        summary=trace.summary,
        input_axis_key=input_axis_key,
        input_axis_label=input_axis_label,
        input_axis_unit=input_axis_unit,
        input_axis_values=tuple(float(value) for value in input_axis_values),
        frequencies_ghz=tuple(float(value) for value in np.asarray(frequencies).reshape(-1)),
        values_grid=np.asarray(values_grid, dtype=np.float64),
    )


def _preview_points(
    preview_payload: Mapping[str, object],
) -> tuple[tuple[float, float], ...] | None:
    raw_points = preview_payload.get("points")
    if not isinstance(raw_points, list):
        return None
    points: list[tuple[float, float]] = []
    for item in raw_points:
        if not isinstance(item, list) or len(item) != 2:
            return None
        if not isinstance(item[0], int | float) or not isinstance(item[1], int | float):
            return None
        points.append((float(item[0]), float(item[1])))
    return tuple(points)


def _materialize_trace_grid(
    *,
    trace: CharacterizationExecutionTrace,
    trace_store: Any,
    store_ref: Mapping[str, object],
    raw_values: np.ndarray,
) -> tuple[str, str, str | None, tuple[float, ...], np.ndarray]:
    detail = trace.detail
    axis_names = [axis.name for axis in detail.axes]
    if "frequency" not in axis_names:
        raise ValueError("Admittance extraction requires a persisted frequency axis.")
    frequency_axis_index = axis_names.index("frequency")
    values = np.asarray(raw_values)
    if frequency_axis_index != 0:
        values = np.moveaxis(values, frequency_axis_index, 0)
    response_values = _response_component_values(
        representation=trace.summary.representation,
        values=values,
    )
    remaining_axes = [axis for axis in detail.axes if axis.name != "frequency"]
    sweep_axes = [axis for axis in remaining_axes if axis.length > 1]
    if len(sweep_axes) == 0:
        return (
            "selected_scope",
            "Selected trace bundle",
            None,
            (0.0,),
            np.asarray(response_values, dtype=np.float64).reshape(response_values.shape[0], 1),
        )
    if len(sweep_axes) > 1:
        raise ValueError(
            "Admittance extraction currently supports traces with at most one sweep axis."
        )
    sweep_axis = sweep_axes[0]
    input_axis_values = np.asarray(
        trace_store.read_axis_slice(
            store_ref,
            axis_name=sweep_axis.name,
            selection=slice(None),
        ),
        dtype=np.float64,
    ).reshape(-1)
    values_grid = np.asarray(response_values, dtype=np.float64).reshape(
        response_values.shape[0],
        -1,
    )
    if values_grid.shape[1] != len(input_axis_values):
        raise ValueError("Persisted trace payload does not match its declared sweep axis.")
    return (
        sweep_axis.name,
        sweep_axis.name,
        sweep_axis.unit,
        tuple(float(value) for value in input_axis_values),
        values_grid,
    )


def _response_component_values(
    *,
    representation: str,
    values: np.ndarray,
) -> np.ndarray:
    normalized_representation = representation.casefold()
    if normalized_representation in {"imag", "imaginary"}:
        response = np.imag(values)
    elif normalized_representation == "phase":
        response = np.angle(values)
    elif normalized_representation == "magnitude" or normalized_representation == "complex":
        response = np.abs(values)
    else:
        response = np.real(values)
    numeric = np.asarray(response, dtype=np.float64)
    numeric[~np.isfinite(numeric)] = np.nan
    return numeric


def _extract_mode_frequencies(
    *,
    window_frequencies: np.ndarray,
    response_window: np.ndarray,
    max_mode_count: int = 4,
) -> tuple[float, ...]:
    if len(window_frequencies) == 0:
        return ()
    amplitudes = np.asarray(np.abs(response_window), dtype=np.float64)
    candidate_indices: list[int] = []
    for index, amplitude in enumerate(amplitudes):
        if not np.isfinite(amplitude):
            continue
        left = amplitudes[index - 1] if index > 0 else float("-inf")
        right = amplitudes[index + 1] if index < len(amplitudes) - 1 else float("-inf")
        if amplitude >= left and amplitude >= right:
            candidate_indices.append(index)
    if len(candidate_indices) == 0:
        finite_indices = np.flatnonzero(np.isfinite(amplitudes))
        if len(finite_indices) == 0:
            return ()
        candidate_indices = [int(finite_indices[int(np.argmax(amplitudes[finite_indices]))])]
    ranked = sorted(
        candidate_indices,
        key=lambda idx: (float(amplitudes[idx]), -float(window_frequencies[idx])),
        reverse=True,
    )[:max_mode_count]
    return tuple(
        float(window_frequencies[index])
        for index in sorted(ranked, key=lambda idx: float(window_frequencies[idx]))
    )


def _build_admittance_diagnostics(
    *,
    masked_input_count: int,
    tolerance_exceeded_count: int,
    residual_tolerance: float,
) -> tuple[CharacterizationDiagnostic, ...]:
    diagnostics: list[CharacterizationDiagnostic] = []
    diagnostics.append(
        CharacterizationDiagnostic(
            severity="warning" if tolerance_exceeded_count > 0 else "info",
            code="fit_residual_rms_evaluated",
            message=(
                "All persisted input positions stay within the configured residual tolerance."
                if tolerance_exceeded_count == 0
                else (
                    f"{tolerance_exceeded_count} input positions exceed the configured "
                    f"residual tolerance of {residual_tolerance:.6f}."
                )
            ),
            blocking=False,
        )
    )
    if masked_input_count > 0:
        diagnostics.append(
            CharacterizationDiagnostic(
                severity="warning",
                code="masked_input_positions_preserved",
                message=(
                    f"{masked_input_count} input positions remained fully masked and were "
                    "preserved in the persisted result surface."
                ),
                blocking=False,
            )
        )
    return tuple(diagnostics)


def _run_admittance_extraction(
    *,
    task: TaskDetail,
    loaded_traces: Sequence[_LoadedTraceSeries],
) -> _AdmittanceExtractionResult:
    if task.characterization_setup is None:
        raise ValueError("Characterization setup is missing.")
    if len(loaded_traces) == 0:
        raise ValueError("Admittance extraction requires at least one eligible trace.")

    reference_trace = loaded_traces[0]
    frequencies = reference_trace.frequencies_ghz
    fit_window = _resolve_fit_window(task.characterization_setup.analysis_config)
    residual_tolerance = float(task.characterization_setup.analysis_config["residual_tolerance"])
    fit_window_mask = np.asarray(
        [fit_window[0] <= frequency <= fit_window[1] for frequency in frequencies],
        dtype=bool,
    )
    if not np.any(fit_window_mask):
        raise ValueError("The selected fit window does not overlap the persisted trace axis.")
    member_frequency_grids: list[tuple[tuple[float | None, ...], ...]] = []
    member_residual_rms: list[tuple[float | None, ...]] = []
    masked_input_indices_by_member: list[tuple[int, ...]] = []
    residual_grids: list[np.ndarray] = []
    members: list[AdmittanceResultMember] = []
    total_masked_input_count = 0
    tolerance_exceeded_count = 0
    frequency_array = np.asarray(frequencies, dtype=np.float64)
    for trace in loaded_traces:
        aligned_grid = _aligned_trace_grid(
            trace,
            reference_frequencies=frequencies,
            reference_input_axis=reference_trace.input_axis_values,
            reference_input_axis_key=reference_trace.input_axis_key,
        )
        residual_grid = np.full_like(aligned_grid, np.nan, dtype=np.float64)
        extracted_modes_by_input: list[tuple[float, ...]] = []
        residual_rms_by_input: list[float | None] = []
        masked_input_indices: list[int] = []
        for input_index in range(aligned_grid.shape[1]):
            response_series = np.asarray(aligned_grid[:, input_index], dtype=np.float64)
            valid_window_mask = fit_window_mask & np.isfinite(response_series)
            if not np.any(valid_window_mask):
                extracted_modes_by_input.append(())
                residual_rms_by_input.append(None)
                masked_input_indices.append(input_index)
                continue
            window_frequencies = frequency_array[valid_window_mask]
            response_window = response_series[valid_window_mask]
            fitted_window = _fit_window_response(
                window_frequencies=window_frequencies,
                response_window=response_window,
            )
            residual_window = np.asarray(response_window - fitted_window, dtype=np.float64)
            residual_grid[valid_window_mask, input_index] = residual_window
            residual_rms = float(np.sqrt(np.mean(np.square(residual_window))))
            residual_rms_by_input.append(residual_rms)
            if residual_rms > residual_tolerance:
                tolerance_exceeded_count += 1
            extracted_modes = _extract_mode_frequencies(
                window_frequencies=window_frequencies,
                response_window=response_window,
            )
            if len(extracted_modes) == 0:
                masked_input_indices.append(input_index)
            extracted_modes_by_input.append(extracted_modes)
        mode_capacity = max(1, max((len(row) for row in extracted_modes_by_input), default=0))
        member_frequency_grids.append(
            tuple(
                tuple(
                    row[mode_index] if mode_index < len(row) else None
                    for mode_index in range(mode_capacity)
                )
                for row in extracted_modes_by_input
            )
        )
        member_residual_rms.append(tuple(residual_rms_by_input))
        masked_indices = tuple(masked_input_indices)
        masked_input_indices_by_member.append(masked_indices)
        total_masked_input_count += len(masked_indices)
        residual_grids.append(residual_grid)
        members.append(_result_member_from_trace(trace.summary))

    diagnostics = _build_admittance_diagnostics(
        masked_input_count=total_masked_input_count,
        tolerance_exceeded_count=tolerance_exceeded_count,
        residual_tolerance=residual_tolerance,
    )
    surface = AdmittanceResultSurface(
        input_axis_key=reference_trace.input_axis_key,
        input_axis_label=reference_trace.input_axis_label,
        input_axis_unit=reference_trace.input_axis_unit,
        input_axis_values=reference_trace.input_axis_values,
        members=tuple(members),
        frequency_grid_by_member=tuple(member_frequency_grids),
        residual_rms_by_member=tuple(member_residual_rms),
        fit_window_ghz=fit_window,
        masked_input_indices_by_member=tuple(masked_input_indices_by_member),
        diagnostics=diagnostics,
    )
    input_axis_suffix = (
        ""
        if reference_trace.input_axis_key == "selected_scope"
        else f" x {reference_trace.input_axis_key}"
    )
    return _AdmittanceExtractionResult(
        selected_trace_ids=tuple(trace.summary.trace_id for trace in loaded_traces),
        surface=surface,
        residual_tensor=np.stack(residual_grids, axis=2),
        provenance_summary=_provenance_summary(loaded_traces),
        sources_summary=f"Y base {len(loaded_traces)} members{input_axis_suffix}",
    )


def _fit_window_response(
    *,
    window_frequencies: np.ndarray,
    response_window: np.ndarray,
) -> np.ndarray:
    if len(window_frequencies) < 2:
        return np.asarray(response_window, dtype=np.float64)
    polynomial_degree = min(2, len(window_frequencies) - 1)
    coefficients = np.polyfit(
        np.asarray(window_frequencies, dtype=np.float64),
        np.asarray(response_window, dtype=np.float64),
        deg=polynomial_degree,
    )
    polynomial = np.poly1d(coefficients)
    return np.asarray(polynomial(window_frequencies), dtype=np.float64)


def _average_trace_grids(
    traces: Sequence[_LoadedTraceSeries],
    *,
    reference_frequencies: Sequence[float],
    reference_input_axis: Sequence[float],
    reference_input_axis_key: str,
) -> np.ndarray:
    stacked = np.stack(
        [
            _aligned_trace_grid(
                trace,
                reference_frequencies=reference_frequencies,
                reference_input_axis=reference_input_axis,
                reference_input_axis_key=reference_input_axis_key,
            )
            for trace in traces
        ],
        axis=0,
    )
    valid_counts = np.sum(np.isfinite(stacked), axis=0)
    sums = np.nansum(stacked, axis=0)
    averaged = np.full_like(sums, np.nan, dtype=np.float64)
    np.divide(sums, valid_counts, out=averaged, where=valid_counts > 0)
    return averaged


def _aligned_trace_grid(
    trace: _LoadedTraceSeries,
    *,
    reference_frequencies: Sequence[float],
    reference_input_axis: Sequence[float],
    reference_input_axis_key: str,
) -> np.ndarray:
    reference = np.asarray(reference_frequencies, dtype=np.float64)
    candidate_frequencies = np.asarray(trace.frequencies_ghz, dtype=np.float64)
    if trace.input_axis_key != reference_input_axis_key or not np.allclose(
        np.asarray(trace.input_axis_values, dtype=np.float64),
        np.asarray(reference_input_axis, dtype=np.float64),
    ):
        raise ValueError("Selected traces do not share one persisted input axis structure.")
    if candidate_frequencies.shape == reference.shape and np.allclose(
        candidate_frequencies,
        reference,
    ):
        return np.asarray(trace.values_grid, dtype=np.float64)
    if reference[0] < candidate_frequencies[0] or reference[-1] > candidate_frequencies[-1]:
        raise ValueError("Selected traces do not overlap on a shared persisted frequency axis.")
    aligned_columns = [
        np.interp(
            reference,
            candidate_frequencies,
            np.asarray(trace.values_grid[:, column_index], dtype=np.float64),
        )
        for column_index in range(trace.values_grid.shape[1])
    ]
    return np.asarray(aligned_columns, dtype=np.float64).T


def _result_member_from_trace(summary: TraceMetadataSummary) -> AdmittanceResultMember:
    return AdmittanceResultMember(
        member_key=f"{summary.source_kind}:{summary.trace_id}",
        label=(
            f"{summary.source_kind.replace('_', ' ')} · "
            f"{summary.parameter} ({summary.representation})"
        ),
        trace_id=summary.trace_id,
        source_kind=summary.source_kind,
        trace_mode_group=summary.trace_mode_group,
        parameter=summary.parameter,
        representation=summary.representation,
        provenance_summary=summary.provenance_summary,
    )


def _resolve_fit_window(
    analysis_config: Mapping[str, object],
) -> tuple[float, float]:
    raw_window = analysis_config.get("fit_window", ())
    if (
        not isinstance(raw_window, list)
        or len(raw_window) != 2
        or not isinstance(raw_window[0], int | float)
        or not isinstance(raw_window[1], int | float)
    ):
        raise ValueError("analysis_config.fit_window must contain two numeric bounds.")
    return (float(raw_window[0]), float(raw_window[1]))


def _persist_analysis_run(
    *,
    task: TaskDetail,
    design: DesignBrowseRow,
    analysis: _AdmittanceExtractionResult,
    recorded_at: datetime,
) -> Any:
    if task.dataset_id is None or task.characterization_setup is None:
        raise ValueError("Characterization task is missing dataset scope.")

    analysis_run_record = _core_symbols()["AnalysisRunRecord"](
        dataset_id=_stable_positive_int(task.dataset_id),
        design_id=_stable_positive_int(task.dataset_id, design.design_id),
        analysis_id=task.characterization_setup.analysis_id,
        analysis_label="Admittance Resonance Extraction",
        run_id=f"analysis-run-pending-{task.task_id}",
        status="completed",
        input_trace_ids=[
            _stable_positive_int(task.dataset_id, design.design_id, trace_id)
            for trace_id in task.characterization_setup.selected_trace_ids
        ],
        input_batch_ids=[],
        input_scope="selected_design_traces",
        trace_mode_group="base",
        config_payload={
            "fit_window": list(analysis.surface.fit_window_ghz),
            "residual_tolerance": task.characterization_setup.analysis_config.get(
                "residual_tolerance"
            ),
            "selected_trace_ids": list(task.characterization_setup.selected_trace_ids),
            "selected_trace_count": len(task.characterization_setup.selected_trace_ids),
            "selected_trace_mode_group": "base",
            "input_result_refs": [
                {
                    "analysis_id": ref.analysis_id,
                    "result_id": ref.result_id,
                    "run_id": ref.run_id,
                    "artifact_id": ref.artifact_id,
                    "contract_version": ref.contract_version,
                    "title": ref.title,
                }
                for ref in task.characterization_setup.input_result_refs
            ],
        },
        summary_payload={},
        created_at=recorded_at,
        completed_at=recorded_at,
    )
    with _core_symbols()["get_unit_of_work"]() as uow:
        persisted = uow.result_bundles.analysis_runs.add(analysis_run_record)
        uow.commit()
    if persisted.id is None:
        raise ValueError("Persisted analysis run did not receive an id.")
    persisted.run_id = _run_id_for_analysis_run(persisted.id)
    return persisted


def _save_analysis_run(run: Any) -> None:
    with _core_symbols()["get_unit_of_work"]() as uow:
        uow.result_bundles.analysis_runs.save(run)
        uow.commit()


def _write_projection_trace(
    *,
    task: TaskDetail,
    analysis_run_id: int,
    frequencies_ghz: Sequence[float],
    residual_tensor: np.ndarray,
    input_axis_key: str,
    input_axis_unit: str | None,
    input_axis_values: Sequence[float],
    members: Sequence[AdmittanceResultMember],
) -> Any:
    if task.dataset_id is None or task.characterization_setup is None:
        raise ValueError("Characterization task is missing dataset scope.")
    trace_store = _core_symbols()["LocalZarrTraceStore"](
        root_path=_core_symbols()["get_trace_store_path"]()
    )
    store_key = (
        f"datasets/{task.dataset_id}/designs/{task.characterization_setup.design_id}/"
        f"analysis-runs/{analysis_run_id}/residual.zarr"
    )
    write_result = trace_store.write_trace(
        design_id=_stable_positive_int(task.dataset_id, task.characterization_setup.design_id),
        batch_id=analysis_run_id,
        trace_id=1,
        values=np.asarray(residual_tensor, dtype=np.float64),
        axes=(
            {
                "name": "frequency",
                "unit": "GHz",
                "values": np.asarray(tuple(float(value) for value in frequencies_ghz)),
            },
            {
                "name": input_axis_key,
                "unit": input_axis_unit or "",
                "values": np.asarray(tuple(float(value) for value in input_axis_values)),
            },
            {
                "name": "member_index",
                "unit": "",
                "values": np.asarray(tuple(float(index) for index, _ in enumerate(members))),
            },
        ),
        store_key=store_key,
        payload_role="analysis",
        writer_version="characterization.local_runtime",
    )
    return _trace_payload_ref_from_store_ref(
        write_result.store_ref,
        payload_role="analysis_projection",
    )


def _write_artifacts(
    *,
    result_id: str,
    analysis: _AdmittanceExtractionResult,
) -> tuple[tuple[CharacterizationArtifactRef, ...], Path]:
    artifact_dir = _artifact_directory(result_id)
    artifact_dir.mkdir(parents=True, exist_ok=True)

    surface_path = artifact_dir / "mode-frequency-grid.json"
    surface_path.write_text(
        json.dumps(serialize_admittance_surface(analysis.surface), indent=2),
        encoding="utf-8",
    )

    identify_summary_path = artifact_dir / "identify-summary.json"
    identify_summary_path.write_text(
        json.dumps(
            {
                "rows": [
                    {
                        "parameter": metric.parameter,
                        "label": metric.label,
                        "value": metric.value,
                        "unit": metric.unit,
                    }
                    for metric in build_admittance_summary_metrics(analysis.surface)
                ]
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    report_path = artifact_dir / "report.json"
    report_path.write_text(
        json.dumps(
            {
                "contract_version": "admittance_member_phase1_v1",
                "input_axis_key": analysis.surface.input_axis_key,
                "input_axis_unit": analysis.surface.input_axis_unit,
                "member_count": len(analysis.surface.members),
                "members": [
                    {
                        "member_key": member.member_key,
                        "trace_id": member.trace_id,
                        "source_kind": member.source_kind,
                        "parameter": member.parameter,
                        "representation": member.representation,
                    }
                    for member in analysis.surface.members
                ],
                "mode_capacity": len(analysis.surface.derived_axis_values),
                "masked_input_indices_by_member": [
                    list(indices) for indices in analysis.surface.masked_input_indices_by_member
                ],
                "fit_window_ghz": list(analysis.surface.fit_window_ghz),
                "selected_trace_ids": list(analysis.selected_trace_ids),
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    return (
        annotate_admittance_artifact_refs(
            build_admittance_artifact_refs(result_id=result_id),
            analysis.surface,
        ),
        report_path,
    )


def _build_persisted_run_payload(
    *,
    task: TaskDetail,
    design: DesignBrowseRow,
    analysis_run_id: int,
    recorded_at: datetime,
    analysis: _AdmittanceExtractionResult,
    artifact_refs: Sequence[CharacterizationArtifactRef],
) -> _PersistedRunPayload:
    if task.dataset_id is None or task.characterization_setup is None:
        raise ValueError("Characterization task is missing dataset scope.")

    result_id = _result_id_for_run(analysis_run_id)
    updated_at = _utc_timestamp(recorded_at)
    analysis_spec = get_characterization_analysis_spec(task.characterization_setup.analysis_id)
    identify_surface = build_admittance_identify_surface(
        result_id=result_id,
        surface=analysis.surface,
    )
    detail = CharacterizationResultDetail(
        result_id=result_id,
        dataset_id=task.dataset_id,
        design_id=task.characterization_setup.design_id,
        analysis_id=task.characterization_setup.analysis_id,
        title=f"{design.name} admittance resonance extraction",
        status="completed",
        freshness_summary=(
            "Persisted admittance resonance extraction completed from saved design traces."
        ),
        provenance_summary=analysis.provenance_summary,
        trace_count=len(task.characterization_setup.selected_trace_ids),
        updated_at=updated_at,
        input_trace_ids=task.characterization_setup.selected_trace_ids,
        input_result_refs=task.characterization_setup.input_result_refs,
        payload=summarize_admittance_surface(
            analysis_run_id=analysis_run_id,
            analysis_config=task.characterization_setup.analysis_config,
            surface=analysis.surface,
        ),
        diagnostics=analysis.surface.diagnostics,
        artifact_refs=tuple(artifact_refs),
        identify_surface=identify_surface,
        downstream_unlock_analysis_ids=(
            analysis_spec.downstream_analysis_ids if analysis_spec is not None else ()
        ),
    )
    summary = CharacterizationResultSummary(
        result_id=result_id,
        dataset_id=task.dataset_id,
        design_id=task.characterization_setup.design_id,
        analysis_id=task.characterization_setup.analysis_id,
        title=detail.title,
        status="completed",
        freshness_summary=detail.freshness_summary,
        provenance_summary=analysis.provenance_summary,
        trace_count=detail.trace_count,
        artifact_count=len(artifact_refs),
        updated_at=updated_at,
    )
    run_history_row = CharacterizationRunHistoryRow(
        run_id=_run_id_for_analysis_run(analysis_run_id),
        dataset_id=task.dataset_id,
        design_id=task.characterization_setup.design_id,
        analysis_id=task.characterization_setup.analysis_id,
        label=detail.title,
        status="completed",
        scope="design_traces",
        trace_count=detail.trace_count,
        sources_summary=analysis.sources_summary,
        provenance_summary=analysis.provenance_summary,
        updated_at=updated_at,
        result_id=result_id,
        input_result_refs=task.characterization_setup.input_result_refs,
    )
    return _PersistedRunPayload(
        result_summary=_summary_to_payload(summary),
        run_history_row=_run_history_to_payload(run_history_row),
        result_detail=_detail_to_payload(detail),
    )


def _summary_from_run(run: Any) -> CharacterizationResultSummary | None:
    payload = run.summary_payload.get("result_summary")
    if not isinstance(payload, Mapping):
        return None
    return CharacterizationResultSummary(
        result_id=str(payload["result_id"]),
        dataset_id=str(payload["dataset_id"]),
        design_id=str(payload["design_id"]),
        analysis_id=str(payload["analysis_id"]),
        title=str(payload["title"]),
        status=str(payload["status"]),
        freshness_summary=str(payload["freshness_summary"]),
        provenance_summary=str(payload["provenance_summary"]),
        trace_count=int(payload["trace_count"]),
        artifact_count=int(payload["artifact_count"]),
        updated_at=str(payload["updated_at"]),
    )


def _run_history_from_run(run: Any) -> CharacterizationRunHistoryRow | None:
    payload = run.summary_payload.get("run_history_row")
    if not isinstance(payload, Mapping):
        return None
    result_id = payload.get("result_id")
    return CharacterizationRunHistoryRow(
        run_id=str(payload["run_id"]),
        dataset_id=str(payload["dataset_id"]),
        design_id=str(payload["design_id"]),
        analysis_id=str(payload["analysis_id"]),
        label=str(payload["label"]),
        status=str(payload["status"]),
        scope=str(payload["scope"]),
        trace_count=int(payload["trace_count"]),
        sources_summary=str(payload["sources_summary"]),
        provenance_summary=str(payload["provenance_summary"]),
        updated_at=str(payload["updated_at"]),
        result_id=str(result_id) if isinstance(result_id, str) else None,
        input_result_refs=tuple(
            CharacterizationInputResultRef(
                analysis_id=str(item.get("analysis_id", "")),
                result_id=str(item.get("result_id", "")),
                run_id=str(item.get("run_id")) if isinstance(item.get("run_id"), str) else None,
                artifact_id=(
                    str(item.get("artifact_id"))
                    if isinstance(item.get("artifact_id"), str)
                    else None
                ),
                contract_version=(
                    str(item.get("contract_version"))
                    if isinstance(item.get("contract_version"), str)
                    else None
                ),
                title=str(item.get("title")) if isinstance(item.get("title"), str) else None,
            )
            for item in payload.get("input_result_refs", ())
            if isinstance(item, Mapping)
        ),
    )


def _detail_from_run(run: Any) -> CharacterizationResultDetail | None:
    payload = run.summary_payload.get("result_detail")
    if not isinstance(payload, Mapping):
        return None
    diagnostics = payload.get("diagnostics", ())
    artifact_refs = payload.get("artifact_refs", ())
    identify_surface = payload.get("identify_surface", {})
    source_parameters = identify_surface.get("source_parameters", [])
    designated_metrics = identify_surface.get("designated_metrics", [])
    applied_tags = identify_surface.get("applied_tags", [])
    input_trace_ids = payload.get("input_trace_ids", ())
    input_result_refs = payload.get("input_result_refs", ())
    downstream_unlock_analysis_ids = payload.get("downstream_unlock_analysis_ids", ())
    return CharacterizationResultDetail(
        result_id=str(payload["result_id"]),
        dataset_id=str(payload["dataset_id"]),
        design_id=str(payload["design_id"]),
        analysis_id=str(payload["analysis_id"]),
        title=str(payload["title"]),
        status=str(payload["status"]),
        freshness_summary=str(payload["freshness_summary"]),
        provenance_summary=str(payload["provenance_summary"]),
        trace_count=int(payload["trace_count"]),
        updated_at=str(payload["updated_at"]),
        input_trace_ids=tuple(
            str(trace_id) for trace_id in input_trace_ids if isinstance(trace_id, str)
        ),
        input_result_refs=tuple(
            CharacterizationInputResultRef(
                analysis_id=str(item.get("analysis_id", "")),
                result_id=str(item.get("result_id", "")),
                run_id=str(item.get("run_id")) if isinstance(item.get("run_id"), str) else None,
                artifact_id=(
                    str(item.get("artifact_id"))
                    if isinstance(item.get("artifact_id"), str)
                    else None
                ),
                contract_version=(
                    str(item.get("contract_version"))
                    if isinstance(item.get("contract_version"), str)
                    else None
                ),
                title=str(item.get("title")) if isinstance(item.get("title"), str) else None,
            )
            for item in input_result_refs
            if isinstance(item, Mapping)
        ),
        payload=dict(payload.get("payload", {})),
        diagnostics=tuple(
            CharacterizationDiagnostic(
                severity=str(item["severity"]),
                code=str(item["code"]),
                message=str(item["message"]),
                blocking=bool(item["blocking"]),
            )
            for item in diagnostics
            if isinstance(item, Mapping)
        ),
        artifact_refs=tuple(
            CharacterizationArtifactRef(
                artifact_id=str(item["artifact_id"]),
                category=str(item["category"]),
                view_kind=str(item["view_kind"]),
                title=str(item["title"]),
                payload_format=str(item["payload_format"]),
                payload_locator=(
                    str(item["payload_locator"])
                    if isinstance(item.get("payload_locator"), str)
                    else None
                ),
                axes=tuple(
                    CharacterizationArtifactAxisSpec(
                        axis_key=str(axis["axis_key"]),
                        label=str(axis["label"]),
                        role=str(axis["role"]),
                        unit=str(axis["unit"]) if isinstance(axis.get("unit"), str) else None,
                        length=int(axis["length"]),
                    )
                    for axis in item.get("axes", ())
                    if isinstance(axis, Mapping)
                ),
                metric=(
                    CharacterizationArtifactMetricSpec(
                        metric_key=str(item["metric"]["metric_key"]),
                        label=str(item["metric"]["label"]),
                        unit=(
                            str(item["metric"]["unit"])
                            if isinstance(item["metric"].get("unit"), str)
                            else None
                        ),
                    )
                    if isinstance(item.get("metric"), Mapping)
                    else None
                ),
                presets=tuple(
                    CharacterizationArtifactPreset(
                        preset_id=str(preset["preset_id"]),
                        label=str(preset["label"]),
                        view_kind=str(preset["view_kind"]),
                        rows_axis=(
                            str(preset["rows_axis"])
                            if isinstance(preset.get("rows_axis"), str)
                            else None
                        ),
                        columns_axis=(
                            str(preset["columns_axis"])
                            if isinstance(preset.get("columns_axis"), str)
                            else None
                        ),
                        cell_metric=(
                            str(preset["cell_metric"])
                            if isinstance(preset.get("cell_metric"), str)
                            else None
                        ),
                        x_axis=(
                            str(preset["x_axis"]) if isinstance(preset.get("x_axis"), str) else None
                        ),
                        y_metric=(
                            str(preset["y_metric"])
                            if isinstance(preset.get("y_metric"), str)
                            else None
                        ),
                        series_axis=(
                            str(preset["series_axis"])
                            if isinstance(preset.get("series_axis"), str)
                            else None
                        ),
                        compare_axis=(
                            str(preset["compare_axis"])
                            if isinstance(preset.get("compare_axis"), str)
                            else None
                        ),
                    )
                    for preset in item.get("presets", ())
                    if isinstance(preset, Mapping)
                ),
                default_preset_id=(
                    str(item["default_preset_id"])
                    if isinstance(item.get("default_preset_id"), str)
                    else None
                ),
                query_spec=(
                    CharacterizationArtifactQuerySpec(
                        query_style=str(item["query_spec"]["query_style"]),
                        supported_query_fields=tuple(
                            str(field)
                            for field in item["query_spec"].get("supported_query_fields", ())
                            if isinstance(field, str)
                        ),
                        supported_view_modes=tuple(
                            str(mode)
                            for mode in item["query_spec"].get("supported_view_modes", ())
                            if isinstance(mode, str)
                        ),
                        supported_preset_ids=tuple(
                            str(preset_id)
                            for preset_id in item["query_spec"].get("supported_preset_ids", ())
                            if isinstance(preset_id, str)
                        ),
                        default_preset_id=(
                            str(item["query_spec"]["default_preset_id"])
                            if isinstance(item["query_spec"].get("default_preset_id"), str)
                            else None
                        ),
                        default_presets_by_view_mode=tuple(
                            CharacterizationArtifactViewModeDefault(
                                view_mode=str(default_item["view_mode"]),
                                preset_id=str(default_item["preset_id"]),
                            )
                            for default_item in item["query_spec"].get(
                                "default_presets_by_view_mode",
                                (),
                            )
                            if isinstance(default_item, Mapping)
                        ),
                    )
                    if isinstance(item.get("query_spec"), Mapping)
                    else None
                ),
                identify_source=bool(item.get("identify_source", False)),
            )
            for item in artifact_refs
            if isinstance(item, Mapping)
        ),
        identify_surface=CharacterizationIdentifySurface(
            source_parameters=tuple(
                CharacterizationSourceParameterOption(
                    artifact_id=str(item["artifact_id"]),
                    source_parameter=str(item["source_parameter"]),
                    label=str(item["label"]),
                    artifact_title=str(item["artifact_title"]),
                    current_designated_metric=(
                        str(item["current_designated_metric"])
                        if isinstance(item.get("current_designated_metric"), str)
                        else None
                    ),
                )
                for item in source_parameters
                if isinstance(item, Mapping)
            ),
            designated_metrics=tuple(
                CharacterizationDesignatedMetricOption(
                    metric_key=str(item["metric_key"]),
                    label=str(item["label"]),
                )
                for item in designated_metrics
                if isinstance(item, Mapping)
            ),
            applied_tags=tuple(
                CharacterizationAppliedTag(
                    artifact_id=str(item["artifact_id"]),
                    source_parameter=str(item["source_parameter"]),
                    designated_metric=str(item["designated_metric"]),
                    designated_metric_label=str(item["designated_metric_label"]),
                    tagged_at=str(item["tagged_at"]),
                )
                for item in applied_tags
                if isinstance(item, Mapping)
            ),
        ),
        downstream_unlock_analysis_ids=tuple(
            str(analysis_id)
            for analysis_id in downstream_unlock_analysis_ids
            if isinstance(analysis_id, str)
        ),
    )


def _detail_with_applied_tag(
    detail: CharacterizationResultDetail,
    *,
    artifact_id: str,
    source_parameter: str,
    metric_option: CharacterizationDesignatedMetricOption,
    tagged_at: str,
) -> CharacterizationResultDetail:
    updated_source_parameters = tuple(
        replace(
            option,
            current_designated_metric=metric_option.metric_key,
        )
        if option.artifact_id == artifact_id and option.source_parameter == source_parameter
        else option
        for option in detail.identify_surface.source_parameters
    )
    updated_tags = (
        *(
            tag
            for tag in detail.identify_surface.applied_tags
            if not (tag.artifact_id == artifact_id and tag.source_parameter == source_parameter)
        ),
        CharacterizationAppliedTag(
            artifact_id=artifact_id,
            source_parameter=source_parameter,
            designated_metric=metric_option.metric_key,
            designated_metric_label=metric_option.label,
            tagged_at=tagged_at,
        ),
    )
    return replace(
        detail,
        identify_surface=replace(
            detail.identify_surface,
            source_parameters=updated_source_parameters,
            applied_tags=updated_tags,
        ),
    )


def _summary_to_payload(summary: CharacterizationResultSummary) -> dict[str, object]:
    return {
        "result_id": summary.result_id,
        "dataset_id": summary.dataset_id,
        "design_id": summary.design_id,
        "analysis_id": summary.analysis_id,
        "title": summary.title,
        "status": summary.status,
        "freshness_summary": summary.freshness_summary,
        "provenance_summary": summary.provenance_summary,
        "trace_count": summary.trace_count,
        "artifact_count": summary.artifact_count,
        "updated_at": summary.updated_at,
    }


def _run_history_to_payload(row: CharacterizationRunHistoryRow) -> dict[str, object]:
    return {
        "run_id": row.run_id,
        "dataset_id": row.dataset_id,
        "design_id": row.design_id,
        "analysis_id": row.analysis_id,
        "label": row.label,
        "status": row.status,
        "scope": row.scope,
        "trace_count": row.trace_count,
        "sources_summary": row.sources_summary,
        "provenance_summary": row.provenance_summary,
        "updated_at": row.updated_at,
        "result_id": row.result_id,
        "input_result_refs": [
            {
                "analysis_id": ref.analysis_id,
                "result_id": ref.result_id,
                "run_id": ref.run_id,
                "artifact_id": ref.artifact_id,
                "contract_version": ref.contract_version,
                "title": ref.title,
            }
            for ref in row.input_result_refs
        ],
    }


def _detail_to_payload(detail: CharacterizationResultDetail) -> dict[str, object]:
    return {
        "result_id": detail.result_id,
        "dataset_id": detail.dataset_id,
        "design_id": detail.design_id,
        "analysis_id": detail.analysis_id,
        "title": detail.title,
        "status": detail.status,
        "freshness_summary": detail.freshness_summary,
        "provenance_summary": detail.provenance_summary,
        "trace_count": detail.trace_count,
        "updated_at": detail.updated_at,
        "input_trace_ids": list(detail.input_trace_ids),
        "input_result_refs": [
            {
                "analysis_id": ref.analysis_id,
                "result_id": ref.result_id,
                "run_id": ref.run_id,
                "artifact_id": ref.artifact_id,
                "contract_version": ref.contract_version,
                "title": ref.title,
            }
            for ref in detail.input_result_refs
        ],
        "payload": dict(detail.payload),
        "diagnostics": [
            {
                "severity": diagnostic.severity,
                "code": diagnostic.code,
                "message": diagnostic.message,
                "blocking": diagnostic.blocking,
            }
            for diagnostic in detail.diagnostics
        ],
        "artifact_refs": [
            {
                "artifact_id": artifact.artifact_id,
                "category": artifact.category,
                "view_kind": artifact.view_kind,
                "title": artifact.title,
                "payload_format": artifact.payload_format,
                "payload_locator": artifact.payload_locator,
                "axes": [
                    {
                        "axis_key": axis.axis_key,
                        "label": axis.label,
                        "role": axis.role,
                        "unit": axis.unit,
                        "length": axis.length,
                    }
                    for axis in artifact.axes
                ],
                "metric": (
                    {
                        "metric_key": artifact.metric.metric_key,
                        "label": artifact.metric.label,
                        "unit": artifact.metric.unit,
                    }
                    if artifact.metric is not None
                    else None
                ),
                "presets": [
                    {
                        "preset_id": preset.preset_id,
                        "label": preset.label,
                        "view_kind": preset.view_kind,
                        "rows_axis": preset.rows_axis,
                        "columns_axis": preset.columns_axis,
                        "cell_metric": preset.cell_metric,
                        "x_axis": preset.x_axis,
                        "y_metric": preset.y_metric,
                        "series_axis": preset.series_axis,
                        "compare_axis": preset.compare_axis,
                    }
                    for preset in artifact.presets
                ],
                "default_preset_id": artifact.default_preset_id,
                "query_spec": (
                    {
                        "query_style": artifact.query_spec.query_style,
                        "supported_query_fields": list(
                            artifact.query_spec.supported_query_fields
                        ),
                        "supported_view_modes": list(artifact.query_spec.supported_view_modes),
                        "supported_preset_ids": list(artifact.query_spec.supported_preset_ids),
                        "default_preset_id": artifact.query_spec.default_preset_id,
                        "default_presets_by_view_mode": [
                            {
                                "view_mode": default_item.view_mode,
                                "preset_id": default_item.preset_id,
                            }
                            for default_item in artifact.query_spec.default_presets_by_view_mode
                        ],
                    }
                    if artifact.query_spec is not None
                    else None
                ),
                "identify_source": artifact.identify_source,
            }
            for artifact in detail.artifact_refs
        ],
        "identify_surface": {
            "source_parameters": [
                {
                    "artifact_id": option.artifact_id,
                    "source_parameter": option.source_parameter,
                    "label": option.label,
                    "artifact_title": option.artifact_title,
                    "current_designated_metric": option.current_designated_metric,
                }
                for option in detail.identify_surface.source_parameters
            ],
            "designated_metrics": [
                {
                    "metric_key": option.metric_key,
                    "label": option.label,
                }
                for option in detail.identify_surface.designated_metrics
            ],
            "applied_tags": [
                {
                    "artifact_id": tag.artifact_id,
                    "source_parameter": tag.source_parameter,
                    "designated_metric": tag.designated_metric,
                    "designated_metric_label": tag.designated_metric_label,
                    "tagged_at": tag.tagged_at,
                }
                for tag in detail.identify_surface.applied_tags
            ],
        },
        "downstream_unlock_analysis_ids": list(detail.downstream_unlock_analysis_ids),
    }


def _build_overlay_svg(
    *,
    frequencies_ghz: Sequence[float],
    observed: np.ndarray,
    fitted: np.ndarray,
) -> str:
    width = 640
    height = 280
    padding_x = 48
    padding_y = 20
    x_values = np.asarray(frequencies_ghz, dtype=np.float64)
    y_values = np.concatenate((observed, fitted))
    min_x = float(np.min(x_values))
    max_x = float(np.max(x_values))
    min_y = float(np.min(y_values))
    max_y = float(np.max(y_values))
    span_x = max(max_x - min_x, 1e-9)
    span_y = max(max_y - min_y, 1e-9)

    def _project(points: np.ndarray) -> str:
        coords: list[str] = []
        for x_value, y_value in zip(x_values, points, strict=False):
            x = padding_x + (((x_value - min_x) / span_x) * (width - (2 * padding_x)))
            y = (
                height
                - padding_y
                - (((float(y_value) - min_y) / span_y) * (height - (2 * padding_y)))
            )
            coords.append(f"{x:.2f},{y:.2f}")
        return " ".join(coords)

    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}">'
        '<rect x="0" y="0" width="100%" height="100%" fill="#ffffff"/>'
        f'<line x1="{padding_x}" y1="{height - padding_y}" x2="{width - padding_x}" '
        f'y2="{height - padding_y}" stroke="#8892a0" stroke-width="1"/>'
        f'<line x1="{padding_x}" y1="{padding_y}" x2="{padding_x}" '
        f'y2="{height - padding_y}" stroke="#8892a0" stroke-width="1"/>'
        f'<polyline fill="none" stroke="#1f77b4" stroke-width="2" '
        f'points="{_project(observed)}"/>'
        f'<polyline fill="none" stroke="#d62728" stroke-width="2" '
        f'points="{_project(fitted)}"/>'
        f'<text x="{padding_x}" y="16" font-size="12" fill="#111827">Observed</text>'
        f'<text x="{padding_x + 92}" y="16" font-size="12" fill="#111827">Fitted</text>'
        "</svg>"
    )


def _payload_ref_to_store_ref(payload_ref: Any) -> dict[str, object]:
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


def _trace_payload_ref_from_store_ref(
    store_ref: Mapping[str, object],
    *,
    payload_role: str,
) -> Any:
    return build_trace_payload_ref(
        payload_role=payload_role,
        store_key=str(store_ref["store_key"]),
        store_uri=str(store_ref.get("store_uri", "")),
        group_path=str(store_ref["group_path"]),
        array_path=str(store_ref["array_path"]),
        dtype=str(store_ref["dtype"]),
        shape=tuple(int(value) for value in store_ref["shape"]),
        chunk_shape=tuple(int(value) for value in store_ref["chunk_shape"]),
        backend=str(store_ref.get("backend", "local_zarr")),
        schema_version=str(store_ref.get("schema_version", "1.0")),
    )


def _artifact_directory(result_id: str) -> Path:
    artifact_root = Path(get_settings().database_path).expanduser().resolve().parent / "artifacts"
    return artifact_root / "characterization" / result_id


def _artifact_locator(path: Path) -> str:
    artifact_root = path.parents[2]
    return path.relative_to(artifact_root).as_posix()


def _matches_dataset_scope(
    summary_payload: Mapping[str, object],
    dataset_id: str,
    design_id: str | None,
) -> bool:
    summary = summary_payload.get("result_summary")
    if not isinstance(summary, Mapping):
        return False
    if str(summary.get("dataset_id")) != dataset_id:
        return False
    if design_id is None:
        return True
    return str(summary.get("design_id")) == design_id


def _result_id_for_run(analysis_run_id: int) -> str:
    return f"char-admittance-run-{analysis_run_id}"


def _run_id_for_analysis_run(analysis_run_id: int) -> str:
    return f"analysis-run-{analysis_run_id}"


def _provenance_summary(
    traces: Sequence[_LoadedTraceSeries],
) -> str:
    labels = list(
        dict.fromkeys(
            trace.summary.provenance_summary.split("·", maxsplit=1)[0].strip() for trace in traces
        )
    )
    return " + ".join(labels)


def _build_tagged_metric_id(dataset_id: str, designated_metric: str) -> str:
    normalized_dataset = dataset_id.replace("_", "-")
    normalized_metric = designated_metric.replace("_", "-")
    return f"metric-{normalized_dataset}-{normalized_metric}"


def _utc_timestamp(value: datetime) -> str:
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _stable_positive_int(*parts: object) -> int:
    token = "|".join(str(part) for part in parts)
    digest = sha256(token.encode("utf-8")).hexdigest()
    return (int(digest[:12], 16) % 900_000_000) + 1
