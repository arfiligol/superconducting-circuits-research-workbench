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

from src.app.domain.datasets import (
    CharacterizationAppliedTag,
    CharacterizationArtifactRef,
    CharacterizationDesignatedMetricOption,
    CharacterizationDiagnostic,
    CharacterizationIdentifySurface,
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
    frequencies_ghz: tuple[float, ...]
    values: np.ndarray


@dataclass(frozen=True)
class _AdmittanceExtractionResult:
    measurement_trace_ids: tuple[str, ...]
    simulation_trace_ids: tuple[str, ...]
    frequencies_ghz: tuple[float, ...]
    averaged_measurement: np.ndarray
    averaged_simulation: np.ndarray
    residual_series: np.ndarray
    fit_window_ghz: tuple[float, float]
    residual_tolerance: float
    f01_ghz: float
    residual_rms: float
    fit_table: tuple[dict[str, object], ...]
    diagnostics: tuple[CharacterizationDiagnostic, ...]
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
            frequencies_ghz=analysis.frequencies_ghz,
            residual_series=analysis.residual_series,
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
                    f"with residual RMS {analysis.residual_rms:.6f}."
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
            run
            for run in runs
            if _matches_dataset_scope(run.summary_payload, dataset_id, None)
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
        frequencies = trace_store.read_axis_slice(
            store_ref,
            axis_name="frequency",
            selection=slice(None),
        )
        values = trace_store.read_trace_slice(store_ref, selection=(slice(None),))
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
        values = np.asarray([point[1] for point in preview_points], dtype=np.float64)

    return _LoadedTraceSeries(
        summary=trace.summary,
        frequencies_ghz=tuple(float(value) for value in np.asarray(frequencies).reshape(-1)),
        values=np.asarray(values, dtype=np.float64).reshape(-1),
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


def _run_admittance_extraction(
    *,
    task: TaskDetail,
    loaded_traces: Sequence[_LoadedTraceSeries],
) -> _AdmittanceExtractionResult:
    if task.characterization_setup is None:
        raise ValueError("Characterization setup is missing.")

    measurement_traces = [
        trace
        for trace in loaded_traces
        if trace.summary.source_kind == "measurement"
    ]
    simulation_traces = [
        trace
        for trace in loaded_traces
        if trace.summary.source_kind in {"layout_simulation", "circuit_simulation"}
    ]
    if len(measurement_traces) == 0 or len(simulation_traces) == 0:
        raise ValueError(
            "Admittance extraction requires both measurement and simulation-backed traces."
        )

    frequencies = measurement_traces[0].frequencies_ghz
    averaged_measurement = _average_trace_values(
        measurement_traces,
        reference_frequencies=frequencies,
    )
    averaged_simulation = _average_trace_values(
        simulation_traces,
        reference_frequencies=frequencies,
    )
    residual_series = averaged_measurement - averaged_simulation

    fit_window = _resolve_fit_window(task.characterization_setup.analysis_config)
    residual_tolerance = float(task.characterization_setup.analysis_config["residual_tolerance"])
    mask = np.asarray(
        [
            fit_window[0] <= frequency <= fit_window[1]
            for frequency in frequencies
        ],
        dtype=bool,
    )
    if not np.any(mask):
        raise ValueError("The selected fit window does not overlap the persisted trace axis.")
    measurement_window = averaged_measurement[mask]
    simulation_window = averaged_simulation[mask]
    window_frequencies = np.asarray(
        [freq for freq, keep in zip(frequencies, mask, strict=False) if keep]
    )
    residual_window = measurement_window - simulation_window

    f01_ghz = float(window_frequencies[int(np.argmin(np.abs(measurement_window)))])
    residual_rms = float(np.sqrt(np.mean(np.square(residual_window))))
    diagnostics = (
        CharacterizationDiagnostic(
            severity="info" if residual_rms <= residual_tolerance else "warning",
            code="residual_rms_evaluated",
            message=(
                "Residual RMS stays within the configured tolerance."
                if residual_rms <= residual_tolerance
                else "Residual RMS exceeds the configured tolerance but the run completed."
            ),
            blocking=False,
        ),
    )
    fit_table = (
        {"parameter": "f01", "value": round(f01_ghz, 6), "unit": "GHz"},
        {"parameter": "residual_rms", "value": round(residual_rms, 8), "unit": "S"},
        {
            "parameter": "window_span",
            "value": round(float(fit_window[1] - fit_window[0]), 6),
            "unit": "GHz",
        },
    )
    return _AdmittanceExtractionResult(
        measurement_trace_ids=tuple(trace.summary.trace_id for trace in measurement_traces),
        simulation_trace_ids=tuple(trace.summary.trace_id for trace in simulation_traces),
        frequencies_ghz=frequencies,
        averaged_measurement=averaged_measurement,
        averaged_simulation=averaged_simulation,
        residual_series=residual_series,
        fit_window_ghz=fit_window,
        residual_tolerance=residual_tolerance,
        f01_ghz=f01_ghz,
        residual_rms=residual_rms,
        fit_table=fit_table,
        diagnostics=diagnostics,
        provenance_summary=_provenance_summary(loaded_traces),
        sources_summary=(
            f"Y base {len(measurement_traces) + len(simulation_traces)}"
        ),
    )


def _average_trace_values(
    traces: Sequence[_LoadedTraceSeries],
    *,
    reference_frequencies: Sequence[float],
) -> np.ndarray:
    stacked = np.stack(
        [
            _aligned_trace_values(trace, reference_frequencies=reference_frequencies)
            for trace in traces
        ],
        axis=0,
    )
    return np.mean(stacked, axis=0)


def _aligned_trace_values(
    trace: _LoadedTraceSeries,
    *,
    reference_frequencies: Sequence[float],
) -> np.ndarray:
    reference = np.asarray(reference_frequencies, dtype=np.float64)
    candidate_frequencies = np.asarray(trace.frequencies_ghz, dtype=np.float64)
    if candidate_frequencies.shape == reference.shape and np.allclose(
        candidate_frequencies,
        reference,
    ):
        return np.asarray(trace.values, dtype=np.float64)
    if reference[0] < candidate_frequencies[0] or reference[-1] > candidate_frequencies[-1]:
        raise ValueError("Selected traces do not overlap on a shared persisted frequency axis.")
    return np.interp(
        reference,
        candidate_frequencies,
        np.asarray(trace.values, dtype=np.float64),
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
        analysis_label="Admittance Extraction",
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
            "fit_window": list(analysis.fit_window_ghz),
            "residual_tolerance": analysis.residual_tolerance,
            "selected_trace_ids": list(task.characterization_setup.selected_trace_ids),
            "selected_trace_count": len(task.characterization_setup.selected_trace_ids),
            "selected_trace_mode_group": "base",
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
    residual_series: np.ndarray,
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
        values=np.asarray(residual_series, dtype=np.float64),
        axes=(
            {
                "name": "frequency",
                "unit": "GHz",
                "values": np.asarray(tuple(float(value) for value in frequencies_ghz)),
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

    fit_table_path = artifact_dir / "fit-table.json"
    fit_table_path.write_text(json.dumps(list(analysis.fit_table), indent=2), encoding="utf-8")

    report_path = artifact_dir / "fit-report.json"
    report_path.write_text(
        json.dumps(
            {
                "f01_ghz": analysis.f01_ghz,
                "residual_rms": analysis.residual_rms,
                "fit_window_ghz": list(analysis.fit_window_ghz),
                "measurement_trace_ids": list(analysis.measurement_trace_ids),
                "simulation_trace_ids": list(analysis.simulation_trace_ids),
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    overlay_path = artifact_dir / "overlay.svg"
    overlay_path.write_text(
        _build_overlay_svg(
            frequencies_ghz=analysis.frequencies_ghz,
            measurement=analysis.averaged_measurement,
            simulation=analysis.averaged_simulation,
        ),
        encoding="utf-8",
    )

    return (
        (
            CharacterizationArtifactRef(
                artifact_id=f"{result_id}:fit-table",
                category="fit_table",
                view_kind="table",
                title="Admittance fit table",
                payload_format="json",
                payload_locator=_artifact_locator(fit_table_path),
            ),
            CharacterizationArtifactRef(
                artifact_id=f"{result_id}:overlay",
                category="plot",
                view_kind="plot",
                title="Measurement vs simulation overlay",
                payload_format="svg",
                payload_locator=_artifact_locator(overlay_path),
            ),
            CharacterizationArtifactRef(
                artifact_id=f"{result_id}:report",
                category="report",
                view_kind="json",
                title="Characterization report",
                payload_format="json",
                payload_locator=_artifact_locator(report_path),
            ),
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
    designated_metrics = (
        CharacterizationDesignatedMetricOption(
            metric_key="f01",
            label="Qubit Transition",
        ),
        CharacterizationDesignatedMetricOption(
            metric_key="residual_rms",
            label="Residual RMS",
        ),
    )
    identify_surface = CharacterizationIdentifySurface(
        source_parameters=tuple(
            CharacterizationSourceParameterOption(
                artifact_id=artifact_refs[0].artifact_id,
                source_parameter=str(row["parameter"]),
                label=str(row["parameter"]).replace("_", " "),
                artifact_title=artifact_refs[0].title,
                current_designated_metric=None,
            )
            for row in analysis.fit_table
        ),
        designated_metrics=designated_metrics,
        applied_tags=(),
    )
    detail = CharacterizationResultDetail(
        result_id=result_id,
        dataset_id=task.dataset_id,
        design_id=task.characterization_setup.design_id,
        analysis_id=task.characterization_setup.analysis_id,
        title=f"{design.name} admittance extraction",
        status="completed",
        freshness_summary="Persisted admittance extraction completed from saved design traces.",
        provenance_summary=analysis.provenance_summary,
        trace_count=len(task.characterization_setup.selected_trace_ids),
        updated_at=updated_at,
        input_trace_ids=task.characterization_setup.selected_trace_ids,
        payload={
            "analysis_run_id": analysis_run_id,
            "fit_window": list(analysis.fit_window_ghz),
            "analysis_config": dict(task.characterization_setup.analysis_config),
            "fit_table": list(analysis.fit_table),
        },
        diagnostics=analysis.diagnostics,
        artifact_refs=tuple(artifact_refs),
        identify_surface=identify_surface,
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
    }


def _build_overlay_svg(
    *,
    frequencies_ghz: Sequence[float],
    measurement: np.ndarray,
    simulation: np.ndarray,
) -> str:
    width = 640
    height = 280
    padding_x = 48
    padding_y = 20
    x_values = np.asarray(frequencies_ghz, dtype=np.float64)
    y_values = np.concatenate((measurement, simulation))
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
            y = height - padding_y - (
                ((float(y_value) - min_y) / span_y) * (height - (2 * padding_y))
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
        f'points="{_project(measurement)}"/>'
        f'<polyline fill="none" stroke="#d62728" stroke-width="2" '
        f'points="{_project(simulation)}"/>'
        f'<text x="{padding_x}" y="16" font-size="12" fill="#111827">Measurement</text>'
        f'<text x="{padding_x + 110}" y="16" font-size="12" fill="#111827">Simulation</text>'
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
            trace.summary.provenance_summary.split("·", maxsplit=1)[0].strip()
            for trace in traces
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
