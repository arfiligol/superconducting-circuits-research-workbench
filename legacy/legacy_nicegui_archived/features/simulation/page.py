"""Simulation page - Circuit visualization and analysis."""

from __future__ import annotations

import asyncio
import json
import re
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Any, TypedDict, cast
from uuid import uuid4

import numpy as np
import plotly.graph_objects as go
from nicegui import app, run, ui
from legacy.legacy_nicegui_archived.features.simulation.recovery.latest_result import (
    _resolve_latest_persisted_post_processing_snapshot,
    _resolve_persisted_post_processing_input_snapshot,
    _source_simulation_bundle_id_from_snapshot,
    _trace_batch_payload_from_snapshot,
    invalidate_persisted_authority_caches,
    load_persisted_post_processing_input_bundle,
    load_persisted_post_processing_output_bundle,
)
from legacy.legacy_nicegui_archived.features.simulation.recovery.polling import (
    SimulationRecoveryBindings,
    poll_current_post_processing_task,
    poll_current_simulation_task,
    refresh_simulation_authority,
)
from legacy.legacy_nicegui_archived.features.simulation.recovery.post_processing_restore import (
    render_post_processing_restore_prompt,
    render_simulation_restore_prompt,
    render_unavailable_authority_state,
)
from legacy.legacy_nicegui_archived.features.simulation.recovery.task_authority import (
    apply_post_processing_task_status as _apply_polled_post_processing_task_status_impl,
    apply_simulation_task_status as _apply_polled_task_status_impl,
)
from legacy.legacy_nicegui_archived.features.simulation.page_state import SimulationPageCoordinator
from legacy.legacy_nicegui_archived.features.simulation.setup.frequency_sweep import (
    _build_setup_payload,
    _normalized_simulation_setup_snapshot,
)
from legacy.legacy_nicegui_archived.features.simulation.setup.parameter_sweep import (
    _SWEEP_MAX_AXIS_COUNT,
    _SWEEP_MAX_CARTESIAN_POINTS,
    _SWEEP_MODE_OPTIONS,
    _default_sweep_axis_payload,
    _default_sweep_setup_payload,
    _estimate_sweep_cartesian_point_count,
    _extract_sweep_target_units,
    _normalize_sweep_setup_payload,
)
from legacy.legacy_nicegui_archived.features.simulation.setup.post_processing_setups import (
    _load_saved_post_process_setups_for_schema as _load_saved_post_process_setups_for_schema_impl,
    _load_selected_post_process_setup_id as _load_selected_post_process_setup_id_impl,
    _save_saved_post_process_setups_for_schema as _save_saved_post_process_setups_for_schema_impl,
    _save_selected_post_process_setup_id as _save_selected_post_process_setup_id_impl,
)
from legacy.legacy_nicegui_archived.features.simulation.setup.saved_setups import (
    _JOSEPHSON_BUILTIN_SETUP_PAYLOADS,
    _builtin_saved_setups_for_schema,
    _ensure_builtin_saved_setups as _ensure_builtin_saved_setups_impl,
    _has_selected_setup_entry as _has_selected_setup_entry_impl,
    _load_saved_setups_for_schema as _load_saved_setups_for_schema_impl,
    _load_selected_setup_id as _load_selected_setup_id_impl,
    _merge_saved_setups_with_builtin,
    _save_saved_setups_for_schema as _save_saved_setups_for_schema_impl,
    _save_selected_setup_id as _save_selected_setup_id_impl,
)
from legacy.legacy_nicegui_archived.features.simulation.setup.sources import (
    _build_source_payload,
    _compress_source_mode_components,
    _detect_harmonic_grid_coincidences,
    _estimate_mode_lattice_size,
    _extract_available_port_indices,
    _format_harmonic_grid_hint,
    _format_mode_lattice_hint,
    _format_source_mode_text,
    _normalize_source_mode_components,
    _parse_source_mode_text,
)
from legacy.legacy_nicegui_archived.features.simulation.setup.termination_compensation import (
    _TERMINATION_DEFAULT_RESISTANCE_OHM,
    _TERMINATION_MODE_OPTIONS,
    _build_termination_compensation_plan,
    _normalize_manual_termination_resistance_map,
    _normalize_termination_mode,
    _normalize_termination_selected_ports,
)
from legacy.legacy_nicegui_archived.features.simulation.state import (
    SimulationRuntimeState,
    TerminationSetupState,
    TerminationViewElements,
    default_post_processing_input_state,
    default_result_view_state,
    default_sweep_result_view_state,
)
from legacy.legacy_nicegui_archived.features.simulation.submit.post_processing_submit import (
    submit_post_processing_intent as _submit_post_processing_intent_impl,
)
from legacy.legacy_nicegui_archived.features.simulation.submit.request_builders import (
    hash_schema_source as _hash_schema_source_impl,
    hash_stable_json as _hash_stable_json_impl,
)
from legacy.legacy_nicegui_archived.features.simulation.submit.simulation_submit import submit_simulation_run
from legacy.legacy_nicegui_archived.features.simulation.submit.validation import (
    PreparedSimulationRun,
    SourceFormPayload,
    prepare_simulation_run,
)
from legacy.legacy_nicegui_archived.features.simulation.views.common import (
    _Z0_CONTROL_CLASSES,
    _Z0_CONTROL_PROPS,
    _user_storage_get,
    _user_storage_set,
    _with_test_id,
)
from legacy.legacy_nicegui_archived.ui.sections import section_card
from legacy.legacy_nicegui_archived.ui.states import render_empty_state
from legacy.legacy_nicegui_archived.features.simulation.views.plots import (
    _POST_PROCESSED_RESULT_FAMILY_OPTIONS,
    _POST_PROCESSED_SWEEP_COMPARE_FAMILY_OPTIONS,
    _RESULT_FAMILY_OPTIONS,
    _SWEEP_RESULT_FAMILY_OPTIONS,
    _build_simulation_result_figure,
    _coerce_int_value,
    _complex_component_series,
    _finite_float_or_none,
    _format_complex_scalar,
    _format_export_suffix,
    _format_mode_label,
    _matrix_element_name,
    _result_metric_options_for_family,
    _result_mode_options,
    _result_port_options,
    _result_trace_options_for_family,
    _resolve_option_key,
)
from legacy.legacy_nicegui_archived.features.simulation.views.post_processing import (
    _POST_PROCESS_INPUT_Y_SOURCE_OPTIONS,
    _coordinate_weight_fields_editable,
    _post_process_mode_options,
    _render_post_processing_panel,
)
from legacy.legacy_nicegui_archived.features.simulation.views.raw_results import (
    _RAW_RESULT_MATRIX_SOURCE_LABEL_BY_FAMILY,
    _RAW_RESULT_MATRIX_SOURCE_OPTIONS_BY_FAMILY,
    _default_result_trace_selection,
    _render_result_family_explorer,
)
from legacy.legacy_nicegui_archived.features.simulation.views.sweep_results import (
    _coerce_sweep_axis_option_index,
    _default_sweep_result_trace_selection,
    _format_sweep_value_token,
    _normalize_sweep_result_view_state_from_source as _normalize_sweep_result_view_state_from_source_impl,
    _resolve_representative_axis_index,
    _resolve_sweep_point_axis_index,
    _render_sweep_result_view_container as _render_sweep_result_view_container_impl,
    _sweep_axis_display_label,
    _sweep_axis_index_options,
    _sweep_payload_port_options,
    _build_sweep_metric_rows as _build_sweep_metric_rows_impl,
    _normalize_sweep_result_view_state as _normalize_sweep_result_view_state_impl,
)
from legacy.legacy_nicegui_archived.services.post_processing_step_registry import (
    POST_PROCESS_STEP_OPTIONS,
    build_default_step_config,
    normalize_saved_step_config,
    preview_pipeline_labels,
    serialize_post_processing_step,
)
from legacy.legacy_nicegui_archived.features.simulation.setup.manager import (
    delete_setup,
    get_setup_by_id,
    is_builtin_setup,
    rename_setup,
    save_setup_as,
)
from core.shared.persistence import SqliteUnitOfWork, get_unit_of_work
from core.shared.persistence.models import (
    CircuitRecord,
    DataRecord,
    DatasetRecord,
    ResultBundleRecord,
)
from core.shared.persistence.repositories.contracts import ResultBundleSnapshot
from core.shared.persistence.trace_store import LocalZarrTraceStore, get_trace_store_path
from core.shared.visualization import get_plotly_layout
from core.simulation.application.post_processing import (
    PortMatrixSweep,
    PortMatrixSweepRun,
    compensate_simulation_result_port_terminations,
    filtered_modes,
    infer_port_termination_resistance_ohm,
)
from core.simulation.application.run_simulation import (
    SimulationSweepAxis,
    SimulationSweepPlan,
    SimulationSweepPointResult,
    SimulationSweepRun,
    build_linear_sweep_values,
    build_simulation_sweep_plan,
    simulation_sweep_run_from_payload,
    simulation_sweep_run_to_payload,
    simulation_sweep_setup_snapshot,
)
from core.simulation.application.trace_architecture import (
    TRACE_BATCH_BUNDLE_SCHEMA_KIND,
    build_post_processed_trace_specs,
    build_raw_simulation_trace_specs,
    is_trace_batch_bundle_payload,
    load_raw_simulation_bundle,
    persist_trace_batch_bundle,
    rebind_trace_batch_bundle_payload,
)
from core.simulation.domain.circuit import (
    CircuitDefinition,
    DriveSourceConfig,
    FrequencyRange,
    SimulationConfig,
    SimulationResult,
    format_expanded_circuit_definition,
    parse_circuit_definition_source,
)

_POST_PROCESS_SETUP_STORAGE_KEY = "simulation_post_process_saved_setups_by_schema"
_POST_PROCESS_SELECTED_KEY = "simulation_post_process_selected_setup_id_by_schema"
# Legacy source-inspection markers kept for compatibility tests.
_SIM_METADATA_LEGACY_MARKER = 'ui.label("Dataset Metadata Summary")'
_SIM_METADATA_TARGET_LEGACY_MARKER = 'label="Target Dataset"'
_SYSTEM_SIMULATION_CACHE_DATASET_NAME = "__system__:simulation_result_cache"
_SIMULATION_HEARTBEAT_SECONDS = 5.0
_SIMULATION_LONG_RUNNING_WARN_AFTER_SECONDS = 60
_SWEEP_PROGRESS_MAX_LOG_LINES = 40


class _ResultTraceSelection(TypedDict):
    trace: str
    output_mode: tuple[int, ...]
    output_port: int
    input_mode: tuple[int, ...]
    input_port: int


@dataclass(frozen=True)
class _TraceStoreAxis:
    """One canonical axis definition for TraceRecord-style runtime reads."""

    name: str
    unit: str
    values: tuple[float, ...]


@dataclass(frozen=True)
class _TraceRecordAuthority:
    """One logical observable over axes plus a TraceStore locator."""

    family: str
    parameter: str
    representation: str
    axes: tuple[_TraceStoreAxis, ...]
    store_key: str
    trace_meta: dict[str, Any]
    store_ref: dict[str, Any] | None = None


@dataclass
class _ViewTraceStore:
    """In-memory TraceStore abstraction for slice-first result-view reads."""

    arrays: dict[str, Any] | None = None
    local_trace_store: LocalZarrTraceStore | None = None

    def read_frequency_slice(
        self,
        record: _TraceRecordAuthority,
        *,
        axis_index_by_name: Mapping[str, int] | None = None,
    ) -> list[float]:
        """Read exactly one frequency trace without materializing unrelated sweep slices."""
        selectors: list[Any] = []
        resolved_axis_indices = dict(axis_index_by_name or {})
        for axis in record.axes:
            if axis.name == "frequency":
                selectors.append(slice(None))
                continue
            axis_index = int(resolved_axis_indices.get(axis.name, 0))
            if axis_index < 0 or axis_index >= len(axis.values):
                raise IndexError(f"Axis index out of range for {axis.name}: {axis_index}")
            selectors.append(axis_index)
        if isinstance(self.arrays, dict) and record.store_key in self.arrays:
            raw_values = self.arrays[record.store_key][tuple(selectors)]
        elif self.local_trace_store is not None and isinstance(record.store_ref, Mapping):
            raw_values = self.local_trace_store.read_trace_slice(
                record.store_ref,
                selection=tuple(selectors),
            )
        else:
            raise KeyError(f"TraceStore key is unavailable for slice read: {record.store_key}")
        values = np.asarray(raw_values, dtype=np.float64)
        if values.ndim != 1:
            raise ValueError("TraceStore slice must resolve to exactly one frequency trace.")
        return [float(value) for value in values]


@dataclass(frozen=True)
class _TraceStoreResultBundle:
    """Canonical TraceRecord + TraceStore authority for one result or sweep view."""

    trace_records: tuple[_TraceRecordAuthority, ...]
    trace_store: _ViewTraceStore
    sweep_axes: tuple[SimulationSweepAxis, ...]
    representative_axis_indices: tuple[int, ...]
    representative_result: SimulationResult
    port_indices: tuple[int, ...]
    mode_indices: tuple[tuple[int, ...], ...]
    port_label_by_index: dict[int, str]

    @property
    def point_count(self) -> int:
        """Return the cartesian sweep size implied by canonical axes."""
        if not self.sweep_axes:
            return 1
        return int(np.prod([len(axis.values) for axis in self.sweep_axes], dtype=np.int64))


@dataclass(frozen=True)
class _SweepSourcePoint:
    """One lazily resolved sweep point from canonical trace authority."""

    point_index: int
    axis_indices: tuple[int, ...]
    axis_values: dict[str, float]
    result: SimulationResult


@dataclass(frozen=True)
class _SweepResultSource:
    """Unified sweep source for legacy payloads and TraceStore-backed runtime reads."""

    axes: tuple[SimulationSweepAxis, ...]
    representative_result: SimulationResult
    representative_axis_indices: tuple[int, ...]
    representative_point_index: int
    point_count: int
    port_options: dict[int, str]
    read_point: Callable[[tuple[int, ...]], _SweepSourcePoint | None]


def _trace_store_axis(
    *,
    name: str,
    unit: str,
    values: tuple[float, ...] | list[float],
) -> _TraceStoreAxis:
    """Build one immutable axis descriptor for TraceStore-backed reads."""
    return _TraceStoreAxis(
        name=str(name),
        unit=str(unit),
        values=tuple(float(value) for value in values),
    )


def _iter_simulation_result_trace_series(
    result: SimulationResult,
) -> list[tuple[str, str, str, list[float]]]:
    """Flatten one SimulationResult into canonical trace-series entries."""
    resolved_s_real = result.s_parameter_mode_real or result._resolved_mode_s_parameter_real()
    resolved_s_imag = result.s_parameter_mode_imag or result._resolved_mode_s_parameter_imag()
    entries: list[tuple[str, str, str, list[float]]] = []

    for label in sorted(set(resolved_s_real) & set(resolved_s_imag)):
        entries.append(("s_params", label, "real", list(resolved_s_real[label])))
        entries.append(("s_params", label, "imaginary", list(resolved_s_imag[label])))
    for label in sorted(set(result.z_parameter_mode_real) & set(result.z_parameter_mode_imag)):
        entries.append(("z_params", label, "real", list(result.z_parameter_mode_real[label])))
        entries.append(("z_params", label, "imaginary", list(result.z_parameter_mode_imag[label])))
    for label in sorted(set(result.y_parameter_mode_real) & set(result.y_parameter_mode_imag)):
        entries.append(("y_params", label, "real", list(result.y_parameter_mode_real[label])))
        entries.append(("y_params", label, "imaginary", list(result.y_parameter_mode_imag[label])))
    for label in sorted(result.qe_parameter_mode):
        entries.append(("qe", label, "value", list(result.qe_parameter_mode[label])))
    for label in sorted(result.qe_ideal_parameter_mode):
        entries.append(("qe_ideal", label, "value", list(result.qe_ideal_parameter_mode[label])))
    for label in sorted(result.cm_parameter_mode):
        entries.append(("commutation", label, "value", list(result.cm_parameter_mode[label])))
    return entries


def _trace_store_bundle_from_result_points(
    *,
    points: list[tuple[tuple[int, ...], SimulationResult]],
    sweep_axes: tuple[SimulationSweepAxis, ...],
    representative_axis_indices: tuple[int, ...],
    representative_result: SimulationResult,
    port_label_by_index: Mapping[int, str] | None = None,
) -> _TraceStoreResultBundle:
    """Materialize one canonical TraceRecord + TraceStore bundle from point results."""
    if not points:
        raise ValueError("TraceStore authority requires at least one point result.")

    frequency_axis = _trace_store_axis(
        name="frequency",
        unit="GHz",
        values=tuple(float(value) for value in representative_result.frequencies_ghz),
    )
    sweep_trace_axes = tuple(
        _trace_store_axis(
            name=axis.target_value_ref,
            unit=axis.unit,
            values=tuple(float(value) for value in axis.values),
        )
        for axis in sweep_axes
    )
    bundle_axes = (*sweep_trace_axes, frequency_axis)
    sweep_shape = tuple(len(axis.values) for axis in sweep_axes)
    frequency_count = len(frequency_axis.values)
    arrays: dict[str, Any] = {}
    trace_records: list[_TraceRecordAuthority] = []
    seen_store_keys: set[str] = set()
    port_indices: set[int] = set()
    mode_indices: set[tuple[int, ...]] = set()

    for axis_indices, result in points:
        if len(result.frequencies_ghz) != frequency_count:
            raise ValueError("Sweep point frequency grids must match for TraceStore reads.")
        port_indices.update(int(port) for port in result.available_port_indices)
        mode_indices.update(tuple(mode) for mode in result.available_mode_indices)
        target_index = (*axis_indices, slice(None))
        for (
            family,
            parameter,
            representation,
            values,
        ) in _iter_simulation_result_trace_series(result):
            store_key = f"{family}:{representation}:{parameter}"
            if store_key not in arrays:
                arrays[store_key] = np.full(
                    (*sweep_shape, frequency_count) if sweep_shape else (frequency_count,),
                    np.nan,
                    dtype=np.float64,
                )
            arrays[store_key][target_index] = np.asarray(values, dtype=np.float64)
            if store_key in seen_store_keys:
                continue
            seen_store_keys.add(store_key)
            trace_records.append(
                _TraceRecordAuthority(
                    family=family,
                    parameter=parameter,
                    representation=representation,
                    axes=bundle_axes,
                    store_key=store_key,
                    trace_meta={
                        "parameter": parameter,
                        "family": family,
                        "representation": representation,
                    },
                )
            )

    resolved_port_labels = {
        int(port): str((port_label_by_index or {}).get(port, port))
        for port in sorted(port_indices or set(representative_result.available_port_indices))
    }
    resolved_modes = tuple(
        sorted(
            mode_indices or {tuple(mode) for mode in representative_result.available_mode_indices}
        )
    )
    return _TraceStoreResultBundle(
        trace_records=tuple(trace_records),
        trace_store=_ViewTraceStore(arrays=arrays),
        sweep_axes=tuple(sweep_axes),
        representative_axis_indices=tuple(int(index) for index in representative_axis_indices),
        representative_result=representative_result,
        port_indices=tuple(
            sorted(port_indices or set(representative_result.available_port_indices))
        ),
        mode_indices=resolved_modes,
        port_label_by_index=resolved_port_labels or _result_port_options(representative_result),
    )


def _runtime_family_from_persisted_trace_family(family: str) -> str:
    """Map persisted TraceStore families back to result-view runtime families."""
    normalized = str(family).strip()
    if normalized == "s_matrix":
        return "s_params"
    if normalized == "z_matrix":
        return "z_params"
    if normalized == "y_matrix":
        return "y_params"
    return normalized


def _trace_store_bundle_from_trace_batch_payload(
    payload: Mapping[str, Any],
    *,
    port_label_by_index: Mapping[int, str] | None = None,
) -> _TraceStoreResultBundle:
    """Build one slice-first TraceStore authority directly from a persisted trace-batch payload."""
    raw_trace_records = payload.get("trace_records", [])
    if not isinstance(raw_trace_records, list) or not raw_trace_records:
        raise ValueError("Trace-batch payload has no trace records.")

    first_trace_record = raw_trace_records[0]
    if not isinstance(first_trace_record, Mapping):
        raise ValueError("Trace-batch payload has an invalid trace record entry.")
    first_store_ref = first_trace_record.get("store_ref")
    first_axes = first_trace_record.get("axes", [])
    if not isinstance(first_store_ref, Mapping) or not first_store_ref:
        raise ValueError("Trace-batch payload is missing store_ref metadata.")
    if not isinstance(first_axes, list) or not first_axes:
        raise ValueError("Trace-batch payload is missing axis metadata.")

    local_trace_store = LocalZarrTraceStore(root_path=get_trace_store_path())

    axis_values_by_name: dict[str, tuple[float, ...]] = {}
    bundle_axes: list[_TraceStoreAxis] = []
    for axis_entry in first_axes:
        if not isinstance(axis_entry, Mapping):
            raise ValueError("Trace-batch axis metadata entry is invalid.")
        axis_name = str(axis_entry.get("name", "")).strip()
        if not axis_name:
            raise ValueError("Trace-batch axis metadata is missing a name.")
        values = tuple(
            float(value)
            for value in np.asarray(
                local_trace_store.read_axis_slice(first_store_ref, axis_name=axis_name),
                dtype=np.float64,
            ).tolist()
        )
        axis_values_by_name[axis_name] = values
        bundle_axes.append(
            _trace_store_axis(
                name=axis_name,
                unit=str(axis_entry.get("unit", "")).strip(),
                values=values,
            )
        )

    sweep_axis_defs = bundle_axes[1:]
    sweep_axes = tuple(
        SimulationSweepAxis(
            target_value_ref=axis.name,
            unit=axis.unit,
            values=tuple(float(value) for value in axis.values),
        )
        for axis in sweep_axis_defs
    )
    sweep_shape = tuple(len(axis.values) for axis in sweep_axes)
    summary_payload = payload.get("trace_batch_record", {}).get("summary_payload", {})
    if not isinstance(summary_payload, Mapping):
        summary_payload = {}
    representative_point_index = int(summary_payload.get("representative_point_index", 0) or 0)
    if sweep_shape:
        max_point_index = max(0, int(np.prod(sweep_shape, dtype=np.int64)) - 1)
        representative_point_index = max(0, min(max_point_index, representative_point_index))
        representative_axis_indices = tuple(
            int(index) for index in np.unravel_index(representative_point_index, sweep_shape)
        )
    else:
        representative_axis_indices = ()

    trace_records: list[_TraceRecordAuthority] = []
    for raw_trace_record in raw_trace_records:
        if not isinstance(raw_trace_record, Mapping):
            raise ValueError("Trace-batch trace record entry is invalid.")
        raw_store_ref = raw_trace_record.get("store_ref")
        raw_axes = raw_trace_record.get("axes", [])
        if not isinstance(raw_store_ref, Mapping) or not raw_store_ref:
            raise ValueError("Trace-batch trace record is missing store_ref metadata.")
        if not isinstance(raw_axes, list) or not raw_axes:
            raise ValueError("Trace-batch trace record is missing axis metadata.")
        resolved_axes = tuple(
            _trace_store_axis(
                name=str(axis_entry.get("name", "")).strip(),
                unit=str(axis_entry.get("unit", "")).strip(),
                values=axis_values_by_name[str(axis_entry.get("name", "")).strip()],
            )
            for axis_entry in raw_axes
            if isinstance(axis_entry, Mapping)
        )
        trace_meta = (
            dict(raw_trace_record.get("trace_meta", {}))
            if isinstance(raw_trace_record.get("trace_meta"), Mapping)
            else {}
        )
        runtime_parameter = str(
            trace_meta.get("label")
            or trace_meta.get("parameter")
            or raw_trace_record.get("parameter")
            or ""
        )
        runtime_family = _runtime_family_from_persisted_trace_family(
            str(raw_trace_record.get("family") or raw_trace_record.get("data_type") or "")
        )
        trace_records.append(
            _TraceRecordAuthority(
                family=runtime_family,
                parameter=runtime_parameter,
                representation=str(raw_trace_record.get("representation") or ""),
                axes=resolved_axes,
                store_key=str(raw_store_ref.get("store_key", "")),
                trace_meta={
                    **trace_meta,
                    "family": runtime_family,
                    "parameter": runtime_parameter,
                    "representation": str(raw_trace_record.get("representation") or ""),
                },
                store_ref=dict(raw_store_ref),
            )
        )

    representative_result = _result_from_trace_store_bundle(
        _TraceStoreResultBundle(
            trace_records=tuple(trace_records),
            trace_store=_ViewTraceStore(local_trace_store=local_trace_store),
            sweep_axes=sweep_axes,
            representative_axis_indices=representative_axis_indices,
            representative_result=SimulationResult(
                frequencies_ghz=list(axis_values_by_name.get("frequency", ())),
                s11_real=[],
                s11_imag=[],
            ),
            port_indices=(),
            mode_indices=(),
            port_label_by_index={},
        ),
        axis_index_by_name={
            axis.target_value_ref: representative_axis_indices[axis_position]
            for axis_position, axis in enumerate(sweep_axes)
        },
    )
    resolved_port_labels = {
        int(port): str((port_label_by_index or {}).get(port, label))
        for port, label in _result_port_options(representative_result).items()
    }
    return _TraceStoreResultBundle(
        trace_records=tuple(trace_records),
        trace_store=_ViewTraceStore(local_trace_store=local_trace_store),
        sweep_axes=sweep_axes,
        representative_axis_indices=representative_axis_indices,
        representative_result=representative_result,
        port_indices=tuple(int(port) for port in representative_result.available_port_indices),
        mode_indices=tuple(
            tuple(int(value) for value in mode)
            for mode in representative_result.available_mode_indices
        ),
        port_label_by_index=resolved_port_labels,
    )


def _trace_store_bundle_from_simulation_result(
    result: SimulationResult,
) -> _TraceStoreResultBundle:
    """Build one canonical TraceStore bundle for a single simulation result."""
    return _trace_store_bundle_from_result_points(
        points=[((), result)],
        sweep_axes=(),
        representative_axis_indices=(),
        representative_result=result,
        port_label_by_index=_result_port_options(result),
    )


def _trace_store_bundle_from_sweep_run(
    sweep_run: SimulationSweepRun,
    *,
    port_label_by_index: Mapping[int, str] | None = None,
) -> _TraceStoreResultBundle:
    """Build one canonical TraceStore bundle for a simulation sweep."""
    representative_point = sweep_run.points[sweep_run.representative_point_index]
    return _trace_store_bundle_from_result_points(
        points=[
            (tuple(int(index) for index in point.axis_indices), point.result)
            for point in sweep_run.points
        ],
        sweep_axes=tuple(sweep_run.axes),
        representative_axis_indices=tuple(
            int(index) for index in representative_point.axis_indices
        ),
        representative_result=representative_point.result,
        port_label_by_index=port_label_by_index,
    )


def _trace_store_bundle_from_post_processed_sweep(
    sweep: PortMatrixSweep,
    *,
    reference_impedance_ohm: float,
) -> _TraceStoreResultBundle:
    """Build one canonical TraceStore bundle for one post-processed result."""
    result, port_options = _build_post_processed_result_payload(
        sweep,
        reference_impedance_ohm=reference_impedance_ohm,
    )
    return _trace_store_bundle_from_result_points(
        points=[((), result)],
        sweep_axes=(),
        representative_axis_indices=(),
        representative_result=result,
        port_label_by_index=port_options,
    )


def _trace_store_bundle_from_post_processed_sweep_run(
    runtime_output: PortMatrixSweepRun,
    *,
    reference_impedance_ohm: float,
) -> _TraceStoreResultBundle:
    """Build one canonical TraceStore bundle for one post-processed sweep."""
    converted_points: list[tuple[tuple[int, ...], SimulationResult]] = []
    representative_result: SimulationResult | None = None
    port_options: dict[int, str] = {}
    for point in runtime_output.points:
        converted, resolved_port_options = _build_post_processed_result_payload(
            point.sweep,
            reference_impedance_ohm=reference_impedance_ohm,
        )
        if representative_result is None:
            representative_result = converted
            port_options = resolved_port_options
        converted_points.append((tuple(int(index) for index in point.axis_indices), converted))
    if representative_result is None:
        raise ValueError("Post-processed sweep runtime has no points.")
    representative_point = runtime_output.points[runtime_output.representative_point_index]
    return _trace_store_bundle_from_result_points(
        points=converted_points,
        sweep_axes=tuple(runtime_output.axes),
        representative_axis_indices=tuple(
            int(index) for index in representative_point.axis_indices
        ),
        representative_result=representative_result,
        port_label_by_index=port_options,
    )


def _cached_trace_store_bundle_from_result(
    result: SimulationResult,
) -> _TraceStoreResultBundle:
    """Build one single-result TraceStore bundle without process-global caching."""
    return _trace_store_bundle_from_simulation_result(result)


def _cached_trace_store_bundle_from_sweep_payload(
    payload: Mapping[str, Any],
    *,
    port_label_by_index: Mapping[int, str] | None = None,
) -> _TraceStoreResultBundle:
    """Build one sweep TraceStore bundle without process-global caching."""
    if is_trace_batch_bundle_payload(payload):
        return _trace_store_bundle_from_trace_batch_payload(
            payload,
            port_label_by_index=port_label_by_index,
        )
    sweep_run = _cached_sweep_run_from_payload(payload)
    return _trace_store_bundle_from_sweep_run(
        sweep_run,
        port_label_by_index=port_label_by_index,
    )


def _cached_trace_store_bundle_from_post_processed_runtime(
    runtime_output: PortMatrixSweep | PortMatrixSweepRun | Mapping[str, Any],
    *,
    reference_impedance_ohm: float,
) -> _TraceStoreResultBundle:
    """Build one post-processed TraceStore bundle without process-global caching."""
    if isinstance(runtime_output, Mapping) and is_trace_batch_bundle_payload(runtime_output):
        return _trace_store_bundle_from_trace_batch_payload(runtime_output)
    if isinstance(runtime_output, PortMatrixSweepRun):
        return _trace_store_bundle_from_post_processed_sweep_run(
            runtime_output,
            reference_impedance_ohm=reference_impedance_ohm,
        )
    if not isinstance(runtime_output, PortMatrixSweep):
        raise TypeError("Post-processed runtime output must resolve to a PortMatrixSweep.")
    return _trace_store_bundle_from_post_processed_sweep(
        runtime_output,
        reference_impedance_ohm=reference_impedance_ohm,
    )


def _axis_index_by_name_from_bundle(
    bundle: _TraceStoreResultBundle,
    *,
    axis_index_by_name: Mapping[str, int] | None = None,
) -> dict[str, int]:
    """Normalize sweep-axis selectors for one TraceStore bundle."""
    raw_indices = dict(axis_index_by_name or {})
    resolved: dict[str, int] = {}
    for axis_position, axis in enumerate(bundle.sweep_axes):
        axis_index = int(raw_indices.get(axis.target_value_ref, 0))
        if (
            axis_position < len(bundle.representative_axis_indices)
            and axis.target_value_ref not in raw_indices
        ):
            axis_index = int(bundle.representative_axis_indices[axis_position])
        axis_index = max(0, min(len(axis.values) - 1, axis_index))
        resolved[axis.target_value_ref] = axis_index
    return resolved


def _result_from_trace_store_bundle(
    bundle: _TraceStoreResultBundle,
    *,
    axis_index_by_name: Mapping[str, int] | None = None,
) -> SimulationResult:
    """Slice one canonical TraceStore bundle back into a SimulationResult view payload."""
    resolved_axis_indices = _axis_index_by_name_from_bundle(
        bundle,
        axis_index_by_name=axis_index_by_name,
    )
    s_mode_real: dict[str, list[float]] = {}
    s_mode_imag: dict[str, list[float]] = {}
    z_mode_real: dict[str, list[float]] = {}
    z_mode_imag: dict[str, list[float]] = {}
    y_mode_real: dict[str, list[float]] = {}
    y_mode_imag: dict[str, list[float]] = {}
    qe_mode: dict[str, list[float]] = {}
    qe_ideal_mode: dict[str, list[float]] = {}
    cm_mode: dict[str, list[float]] = {}
    s_zero_mode_real: dict[str, list[float]] = {}
    s_zero_mode_imag: dict[str, list[float]] = {}

    for record in bundle.trace_records:
        values = bundle.trace_store.read_frequency_slice(
            record,
            axis_index_by_name=resolved_axis_indices,
        )
        family = str(record.trace_meta.get("family", record.family))
        parameter = str(record.trace_meta.get("parameter", record.parameter))
        if family == "s_params":
            if record.representation == "real":
                s_mode_real[parameter] = values
            else:
                s_mode_imag[parameter] = values
        elif family == "z_params":
            if record.representation == "real":
                z_mode_real[parameter] = values
            else:
                z_mode_imag[parameter] = values
        elif family == "y_params":
            if record.representation == "real":
                y_mode_real[parameter] = values
            else:
                y_mode_imag[parameter] = values
        elif family == "qe":
            qe_mode[parameter] = values
        elif family == "qe_ideal":
            qe_ideal_mode[parameter] = values
        elif family == "commutation":
            cm_mode[parameter] = values

    for label, values in s_mode_real.items():
        parsed = SimulationResult._parse_mode_trace_label(label)
        if parsed is None:
            continue
        output_mode, output_port, input_mode, input_port = parsed
        if all(value == 0 for value in output_mode) and all(value == 0 for value in input_mode):
            zero_label = f"S{output_port}{input_port}"
            s_zero_mode_real[zero_label] = list(values)
            if label in s_mode_imag:
                s_zero_mode_imag[zero_label] = list(s_mode_imag[label])

    zero_mode = next(
        (mode for mode in bundle.mode_indices if all(value == 0 for value in mode)),
        (0,),
    )
    s11_label = SimulationResult._mode_trace_label(tuple(zero_mode), 1, tuple(zero_mode), 1)
    frequency_values = list(bundle.representative_result.frequencies_ghz)
    s11_real = list(s_mode_real.get(s11_label, [0.0] * len(frequency_values)))
    s11_imag = list(s_mode_imag.get(s11_label, [0.0] * len(frequency_values)))
    return SimulationResult(
        frequencies_ghz=frequency_values,
        s11_real=s11_real,
        s11_imag=s11_imag,
        port_indices=list(bundle.port_indices),
        mode_indices=[tuple(mode) for mode in bundle.mode_indices],
        s_parameter_real=s_zero_mode_real,
        s_parameter_imag=s_zero_mode_imag,
        s_parameter_mode_real=s_mode_real,
        s_parameter_mode_imag=s_mode_imag,
        z_parameter_mode_real=z_mode_real,
        z_parameter_mode_imag=z_mode_imag,
        y_parameter_mode_real=y_mode_real,
        y_parameter_mode_imag=y_mode_imag,
        qe_parameter_mode=qe_mode,
        qe_ideal_parameter_mode=qe_ideal_mode,
        cm_parameter_mode=cm_mode,
    )


def _point_index_from_axis_indices(
    *,
    axis_indices: tuple[int, ...],
    axes: tuple[SimulationSweepAxis, ...],
) -> int:
    """Convert one sweep index tuple into a stable point index."""
    if not axes:
        return 0
    dims = tuple(len(axis.values) for axis in axes)
    if not dims:
        return 0
    return int(np.ravel_multi_index(axis_indices, dims=dims))


def _sweep_source_from_sweep_run(
    sweep_run: SimulationSweepRun,
    *,
    port_options: Mapping[int, str] | None = None,
) -> _SweepResultSource:
    """Adapt one legacy sweep payload into the common sweep-source interface."""
    point_lookup = _cached_sweep_point_lookup(sweep_run)
    representative_point = sweep_run.points[sweep_run.representative_point_index]
    resolved_port_options = (
        {int(key): str(value) for key, value in port_options.items()}
        if isinstance(port_options, Mapping) and port_options
        else _result_port_options(sweep_run.representative_result)
    )

    def read_point(axis_indices: tuple[int, ...]) -> _SweepSourcePoint | None:
        point = point_lookup.get(tuple(int(index) for index in axis_indices))
        if point is None:
            return None
        return _SweepSourcePoint(
            point_index=int(point.point_index),
            axis_indices=tuple(int(index) for index in point.axis_indices),
            axis_values={
                str(target_value_ref): float(value)
                for target_value_ref, value in point.axis_values.items()
            },
            result=point.result,
        )

    return _SweepResultSource(
        axes=tuple(sweep_run.axes),
        representative_result=sweep_run.representative_result,
        representative_axis_indices=tuple(
            int(index) for index in representative_point.axis_indices
        ),
        representative_point_index=int(sweep_run.representative_point_index),
        point_count=int(sweep_run.point_count),
        port_options=resolved_port_options,
        read_point=read_point,
    )


def _sweep_source_from_trace_store_bundle(
    bundle: _TraceStoreResultBundle,
) -> _SweepResultSource:
    """Adapt one TraceStore-backed sweep authority into the common sweep-source interface."""
    representative_axis_indices = tuple(int(index) for index in bundle.representative_axis_indices)

    def read_point(axis_indices: tuple[int, ...]) -> _SweepSourcePoint | None:
        resolved_axis_indices = tuple(int(index) for index in axis_indices)
        if len(resolved_axis_indices) != len(bundle.sweep_axes):
            return None
        axis_values = {
            axis.target_value_ref: float(axis.values[resolved_axis_indices[axis_position]])
            for axis_position, axis in enumerate(bundle.sweep_axes)
        }
        return _SweepSourcePoint(
            point_index=_point_index_from_axis_indices(
                axis_indices=resolved_axis_indices,
                axes=bundle.sweep_axes,
            ),
            axis_indices=resolved_axis_indices,
            axis_values=axis_values,
            result=_result_from_trace_store_bundle(
                bundle,
                axis_index_by_name={
                    axis.target_value_ref: resolved_axis_indices[axis_position]
                    for axis_position, axis in enumerate(bundle.sweep_axes)
                },
            ),
        )

    return _SweepResultSource(
        axes=tuple(bundle.sweep_axes),
        representative_result=bundle.representative_result,
        representative_axis_indices=representative_axis_indices,
        representative_point_index=_point_index_from_axis_indices(
            axis_indices=representative_axis_indices,
            axes=bundle.sweep_axes,
        ),
        point_count=int(bundle.point_count),
        port_options=dict(bundle.port_label_by_index),
        read_point=read_point,
    )


def _resolve_sweep_result_source(
    *,
    sweep_payload: Mapping[str, Any] | None = None,
    trace_store_bundle: _TraceStoreResultBundle | None = None,
) -> _SweepResultSource:
    """Resolve the canonical sweep source for result-view rendering."""
    if trace_store_bundle is not None:
        return _sweep_source_from_trace_store_bundle(trace_store_bundle)
    if not isinstance(sweep_payload, Mapping):
        raise ValueError("Sweep source requires one payload or TraceStore bundle.")
    sweep_run = _cached_sweep_run_from_payload(sweep_payload)
    return _sweep_source_from_sweep_run(
        sweep_run,
        port_options=_sweep_payload_port_options(
            sweep_payload,
            fallback_result=sweep_run.representative_result,
        ),
    )


def _resolve_representative_axis_index(
    *,
    representative_axis_indices: tuple[int, ...],
    axis_position: int,
    axis: SimulationSweepAxis,
) -> int:
    """Resolve one representative index along the compare axis."""
    if axis_position < len(representative_axis_indices):
        axis_index = int(representative_axis_indices[axis_position])
    else:
        axis_index = 0
    return max(0, min(len(axis.values) - 1, axis_index))


def _cached_sweep_run_from_payload(payload: Mapping[str, Any]) -> SimulationSweepRun:
    """Decode one sweep payload deterministically without process-global caching."""
    return simulation_sweep_run_from_payload(payload)


def _cached_sweep_point_lookup(
    sweep_run: SimulationSweepRun,
) -> dict[tuple[int, ...], SimulationSweepPointResult]:
    """Build one direct point lookup keyed by normalized axis-index tuples."""
    return {
        tuple(
            _resolve_sweep_point_axis_index(
                point,
                axis_position=axis_position,
                axis=axis,
            )
            for axis_position, axis in enumerate(sweep_run.axes)
        ): point
        for point in sweep_run.points
    }


def _user_storage_get(key: str, default: Any = None) -> Any:
    """Safely read one value from user storage with non-UI-context fallback."""
    try:
        return app.storage.user.get(key, default)
    except RuntimeError:
        return default


def _user_storage_set(key: str, value: Any) -> None:
    """Safely write one value into user storage when UI context is available."""
    try:
        app.storage.user[key] = value
    except RuntimeError:
        return


def _hash_stable_json(payload: dict[str, Any]) -> str:
    """Compatibility wrapper around feature-local submit hash helpers."""
    return _hash_stable_json_impl(payload)


def _hash_schema_source(source_text: str) -> str:
    """Compatibility wrapper around feature-local submit hash helpers."""
    return _hash_schema_source_impl(source_text)


def _ensure_simulation_cache_dataset(uow: SqliteUnitOfWork) -> DatasetRecord:
    """Return the hidden dataset used for automatic simulation-result caching."""
    existing = uow.datasets.get_by_name(_SYSTEM_SIMULATION_CACHE_DATASET_NAME)
    if existing is not None:
        if not existing.source_meta.get("system_hidden"):
            existing.source_meta = {
                **existing.source_meta,
                "system_hidden": True,
                "collection_origin": "system_cache",
                "cache_kind": "simulation_result",
            }
        return existing

    dataset = DatasetRecord(
        name=_SYSTEM_SIMULATION_CACHE_DATASET_NAME,
        source_meta={
            "collection_origin": "system_cache",
            "cache_kind": "simulation_result",
            "system_hidden": True,
        },
        parameters={},
    )
    uow.datasets.add(dataset)
    uow.flush()
    return dataset


def _load_cached_simulation_result(
    uow: SqliteUnitOfWork,
    *,
    schema_source_hash: str,
    simulation_setup_hash: str,
) -> tuple[int, int, SimulationResult | None, dict[str, Any] | None] | None:
    """Load one cached simulation result from the hidden system dataset."""
    cache_dataset = _ensure_simulation_cache_dataset(uow)
    if cache_dataset.id is None:
        return None

    bundle = uow.result_bundles.find_simulation_cache(
        dataset_id=cache_dataset.id,
        schema_source_hash=schema_source_hash,
        simulation_setup_hash=simulation_setup_hash,
    )
    if bundle is None or not bundle.result_payload:
        return None

    try:
        result, sweep_payload = _decode_simulation_result_payload(bundle.result_payload)
    except Exception:
        return None

    if is_trace_batch_bundle_payload(bundle.result_payload):
        trace_batch_record = bundle.result_payload.get("trace_batch_record", {})
        summary_payload = trace_batch_record.get("summary_payload", {})
        if (
            isinstance(summary_payload, Mapping)
            and str(summary_payload.get("run_kind", "")).strip() == "parameter_sweep"
        ):
            if bundle.id is None:
                return None
            return (bundle.id, int(cache_dataset.id), None, dict(bundle.result_payload))

    if not is_trace_batch_bundle_payload(bundle.result_payload):
        source_meta = dict(bundle.source_meta) if isinstance(bundle.source_meta, dict) else {}
        design_id = int(source_meta.get("circuit_id") or bundle.dataset_id)
        design_name = str(
            source_meta.get("circuit_name")
            or source_meta.get("design_name")
            or source_meta.get("dataset_name")
            or f"design-{design_id}"
        )
        provenance_payload = {
            **source_meta,
            "schema_source_hash": schema_source_hash,
            "simulation_setup_hash": simulation_setup_hash,
            "run_kind": "parameter_sweep" if sweep_payload is not None else "single_run",
        }
        trace_specs = build_raw_simulation_trace_specs(
            result=result,
            sweep_payload=sweep_payload,
        )
        bundle.source_meta = {
            **source_meta,
            "schema_kind": TRACE_BATCH_BUNDLE_SCHEMA_KIND,
            "design_id": design_id,
            "design_name": design_name,
        }
        bundle.result_payload = persist_trace_batch_bundle(
            bundle_id=int(bundle.id or 0),
            design_id=design_id,
            design_name=design_name,
            source_kind="circuit_simulation",
            stage_kind="raw",
            setup_kind="circuit_simulation.raw",
            setup_payload=(
                dict(bundle.config_snapshot) if isinstance(bundle.config_snapshot, dict) else {}
            ),
            provenance_payload=provenance_payload,
            trace_specs=trace_specs,
            summary_payload={
                "trace_count": len(trace_specs),
                "run_kind": provenance_payload["run_kind"],
                "frequency_points": len(result.frequencies_ghz),
                "point_count": (
                    int(sweep_payload.get("point_count", 0))
                    if isinstance(sweep_payload, Mapping)
                    else 1
                ),
                "representative_point_index": (
                    int(sweep_payload.get("representative_point_index", 0))
                    if isinstance(sweep_payload, Mapping)
                    else 0
                ),
            },
        )
        uow.commit()
        if sweep_payload is not None:
            if bundle.id is None:
                return None
            return (bundle.id, int(cache_dataset.id), None, dict(bundle.result_payload))

    if bundle.id is None:
        return None

    return (bundle.id, cache_dataset.id, result, sweep_payload)


def _load_cached_simulation_result_io(
    *,
    schema_source_hash: str,
    simulation_setup_hash: str,
) -> tuple[int, int, SimulationResult | None, dict[str, Any] | None] | None:
    """Run one cache lookup inside a background IO worker."""
    with get_unit_of_work() as uow:
        return _load_cached_simulation_result(
            uow,
            schema_source_hash=schema_source_hash,
            simulation_setup_hash=simulation_setup_hash,
        )


def _decode_simulation_result_payload(
    payload: Mapping[str, Any],
) -> tuple[SimulationResult, dict[str, Any] | None]:
    """Decode one persisted payload into preview result plus optional canonical sweep payload."""
    if is_trace_batch_bundle_payload(payload):
        trace_store_bundle = _cached_trace_store_bundle_from_sweep_payload(payload)
        if trace_store_bundle.sweep_axes:
            return (trace_store_bundle.representative_result, dict(payload))
        return (trace_store_bundle.representative_result, None)
    run_kind = str(payload.get("run_kind", "")).strip() if isinstance(payload, Mapping) else ""
    if run_kind == "parameter_sweep":
        sweep_run = simulation_sweep_run_from_payload(payload)
        return (sweep_run.representative_result, simulation_sweep_run_to_payload(sweep_run))
    result = SimulationResult.model_validate(payload)
    return (result, None)


def _coerce_parameter_sweep_payload(
    payload: Mapping[str, Any] | None,
) -> dict[str, Any] | None:
    """Coerce one canonical sweep payload into legacy parameter-sweep shape when needed."""
    if not isinstance(payload, Mapping):
        return None
    if is_trace_batch_bundle_payload(payload):
        try:
            _result, sweep_payload = load_raw_simulation_bundle(payload)
        except Exception:
            return None
        if not isinstance(sweep_payload, Mapping):
            return None
        return json.loads(json.dumps(sweep_payload))
    if str(payload.get("run_kind", "")).strip() != "parameter_sweep":
        return None
    return json.loads(json.dumps(payload))


def _normalize_selected_design_ids(selection: object) -> tuple[int, ...]:
    """Normalize persisted UI selection payload into one stable design-id tuple."""
    if selection is None:
        return ()
    if isinstance(selection, (str, int)):
        selection_iterable: list[object] = [selection]
    elif isinstance(selection, (list, tuple, set)):
        selection_iterable = list(selection)
    else:
        return ()
    normalized: list[int] = []
    for value in selection_iterable:
        if not isinstance(value, int | str):
            continue
        try:
            design_id = int(value)
        except ValueError:
            continue
        if design_id not in normalized:
            normalized.append(design_id)
    return tuple(normalized)

def _resolved_sweep_point_count(payload: Mapping[str, Any] | None) -> int:
    """Resolve one sweep point count across legacy and trace-batch payload shapes."""
    if not isinstance(payload, Mapping):
        return 0
    if is_trace_batch_bundle_payload(payload):
        summary_payload = payload.get("trace_batch_record", {}).get("summary_payload", {})
        if isinstance(summary_payload, Mapping):
            return int(summary_payload.get("point_count", 0) or 0)
        return 0
    return int(payload.get("point_count", 0) or 0)


def _post_processed_runtime_is_sweep(
    runtime_output: PortMatrixSweep | PortMatrixSweepRun | Mapping[str, Any] | None,
    flow_spec: Mapping[str, Any] | None = None,
) -> bool:
    """Return whether one post-processed runtime represents a parameter sweep."""
    if isinstance(runtime_output, PortMatrixSweepRun):
        return True
    if isinstance(runtime_output, Mapping) and is_trace_batch_bundle_payload(runtime_output):
        summary_payload = runtime_output.get("trace_batch_record", {}).get("summary_payload", {})
        if isinstance(summary_payload, Mapping):
            return str(summary_payload.get("run_kind", "")).strip() == "parameter_sweep"
    if isinstance(flow_spec, Mapping):
        return str(flow_spec.get("run_kind", "")).strip() == "parameter_sweep"
    return False


def _resolved_frequency_point_count_from_payload(payload: Mapping[str, Any] | None) -> int:
    """Resolve one frequency point count across legacy and trace-batch payload shapes."""
    if not isinstance(payload, Mapping):
        return 0
    if is_trace_batch_bundle_payload(payload):
        summary_payload = payload.get("trace_batch_record", {}).get("summary_payload", {})
        if isinstance(summary_payload, Mapping):
            return int(summary_payload.get("frequency_points", 0) or 0)
        return 0
    try:
        representative = simulation_sweep_run_from_payload(payload).representative_result
    except Exception:
        return 0
    return len(representative.frequencies_ghz)


def _build_compensated_simulation_sweep_payload(
    sweep_payload: Mapping[str, Any],
    *,
    resistance_ohm_by_port: Mapping[int, float],
    reference_impedance_ohm: float,
) -> dict[str, Any]:
    """Apply port-termination compensation point-wise while preserving full sweep provenance."""
    resolved_sweep_payload = _coerce_parameter_sweep_payload(sweep_payload)
    if not isinstance(resolved_sweep_payload, Mapping):
        raise ValueError("Sweep payload is unavailable for termination compensation.")
    sweep_run = simulation_sweep_run_from_payload(resolved_sweep_payload)
    compensated_points = tuple(
        SimulationSweepPointResult(
            point_index=int(point.point_index),
            axis_indices=tuple(int(index) for index in point.axis_indices),
            axis_values={
                str(target_value_ref): float(value)
                for target_value_ref, value in point.axis_values.items()
            },
            result=compensate_simulation_result_port_terminations(
                point.result,
                resistance_ohm_by_port={
                    int(port): float(value) for port, value in resistance_ohm_by_port.items()
                },
                reference_impedance_ohm=reference_impedance_ohm,
            ),
        )
        for point in sweep_run.points
    )
    return simulation_sweep_run_to_payload(
        SimulationSweepRun(
            axes=tuple(sweep_run.axes),
            points=compensated_points,
            representative_point_index=int(sweep_run.representative_point_index),
        )
    )


def _persist_simulation_result_bundle(
    *,
    uow: SqliteUnitOfWork,
    dataset_id: int,
    result: SimulationResult,
    role: str,
    source_meta: dict[str, Any],
    config_snapshot: dict[str, Any],
    schema_source_hash: str | None = None,
    simulation_setup_hash: str | None = None,
    include_data_records: bool = True,
    result_payload: dict[str, Any] | None = None,
) -> int:
    """Persist one simulation result bundle using the trace-batch + TraceStore contract."""
    trace_batch_payload = (
        dict(result_payload)
        if isinstance(result_payload, Mapping) and is_trace_batch_bundle_payload(result_payload)
        else None
    )
    normalized_result_payload = None if trace_batch_payload is not None else result_payload

    design_id = int(source_meta.get("circuit_id") or dataset_id)
    design_name = str(
        source_meta.get("circuit_name")
        or source_meta.get("design_name")
        or source_meta.get("dataset_name")
        or f"design-{design_id}"
    )
    bundle = ResultBundleRecord(
        dataset_id=dataset_id,
        bundle_type="circuit_simulation",
        role=role,
        status="in_progress",
        schema_source_hash=schema_source_hash,
        simulation_setup_hash=simulation_setup_hash,
        source_meta={
            **dict(source_meta),
            "schema_kind": TRACE_BATCH_BUNDLE_SCHEMA_KIND,
            "design_id": design_id,
            "design_name": design_name,
        },
        config_snapshot=dict(config_snapshot),
        result_payload={},
        completed_at=None,
    )
    uow.result_bundles.add(bundle)
    uow.flush()

    if bundle.id is None:
        raise ValueError("Failed to allocate a result bundle id.")
    bundle_id = bundle.id
    uow.commit()

    try:
        provenance_payload = {
            **dict(source_meta),
            "schema_source_hash": schema_source_hash,
            "simulation_setup_hash": simulation_setup_hash,
            "run_kind": (
                "parameter_sweep"
                if (
                    trace_batch_payload is not None
                    or (
                        isinstance(normalized_result_payload, Mapping)
                        and str(normalized_result_payload.get("run_kind", "")).strip()
                        == "parameter_sweep"
                    )
                )
                else "single_run"
            ),
        }
        summary_payload = {
            "run_kind": provenance_payload["run_kind"],
            "frequency_points": len(result.frequencies_ghz),
            "point_count": (
                int(
                    trace_batch_payload.get("trace_batch_record", {})
                    .get("summary_payload", {})
                    .get("point_count", 0)
                )
                if trace_batch_payload is not None
                else (
                    int(normalized_result_payload.get("point_count", 0))
                    if isinstance(normalized_result_payload, Mapping)
                    else 1
                )
            ),
            "representative_point_index": (
                int(
                    trace_batch_payload.get("trace_batch_record", {})
                    .get("summary_payload", {})
                    .get("representative_point_index", 0)
                )
                if trace_batch_payload is not None
                else (
                    int(normalized_result_payload.get("representative_point_index", 0))
                    if isinstance(normalized_result_payload, Mapping)
                    else 0
                )
            ),
        }
        if trace_batch_payload is not None:
            summary_payload["trace_count"] = len(list(trace_batch_payload.get("trace_records", [])))
            bundle.result_payload = rebind_trace_batch_bundle_payload(
                trace_batch_payload,
                bundle_id=bundle_id,
                design_id=design_id,
                design_name=design_name,
                source_kind="circuit_simulation",
                stage_kind="raw",
                setup_kind="circuit_simulation.raw",
                setup_payload=config_snapshot,
                provenance_payload=provenance_payload,
                summary_payload=summary_payload,
            )
        else:
            trace_specs = build_raw_simulation_trace_specs(
                result=result,
                sweep_payload=normalized_result_payload,
            )
            summary_payload["trace_count"] = len(trace_specs)
            bundle.result_payload = persist_trace_batch_bundle(
                bundle_id=bundle_id,
                design_id=design_id,
                design_name=design_name,
                source_kind="circuit_simulation",
                stage_kind="raw",
                setup_kind="circuit_simulation.raw",
                setup_payload=config_snapshot,
                provenance_payload=provenance_payload,
                trace_specs=trace_specs,
                summary_payload=summary_payload,
            )

        if include_data_records:
            records: list[DataRecord]
            if trace_batch_payload is not None:
                records = _build_trace_batch_data_records(
                    dataset_id=dataset_id,
                    trace_batch_payload=bundle.result_payload,
                )
            elif isinstance(normalized_result_payload, Mapping) and (
                str(normalized_result_payload.get("run_kind", "")) == "parameter_sweep"
            ):
                records = _build_sweep_result_bundle_data_records(
                    dataset_id=dataset_id,
                    sweep_payload=normalized_result_payload,
                )
            else:
                records = _build_result_bundle_data_records(dataset_id=dataset_id, result=result)
            for record in records:
                uow.data_records.add(record)
            uow.flush()

            record_ids = [record.id for record in records if record.id is not None]
            if len(record_ids) != len(records):
                raise ValueError("Failed to allocate one or more data record ids.")

            uow.result_bundles.attach_data_records(bundle_id=bundle_id, data_record_ids=record_ids)

        uow.result_bundles.mark_completed(bundle_id)
        uow.commit()
        return bundle_id
    except Exception as exc:
        uow.result_bundles.mark_failed(
            bundle_id,
            summary_payload={
                "error_code": "trace_batch_persist_failed",
                "error_summary": str(exc),
            },
        )
        uow.commit()
        raise


def _persist_simulation_result_bundle_io(
    *,
    result: SimulationResult,
    schema_source_hash: str,
    simulation_setup_hash: str,
    source_meta: dict[str, Any],
    config_snapshot: dict[str, Any],
    sweep_setup_hash: str | None = None,
    result_payload: dict[str, Any] | None = None,
) -> tuple[int, int]:
    """Persist one cache bundle inside a background IO worker and return ids."""
    with get_unit_of_work() as uow:
        cache_dataset = _ensure_simulation_cache_dataset(uow)
        if cache_dataset.id is None:
            raise ValueError("Failed to allocate cache dataset id.")
        cache_dataset_id = int(cache_dataset.id)
        bundle_id = _persist_simulation_result_bundle(
            uow=uow,
            dataset_id=cache_dataset_id,
            result=result,
            role="cache",
            source_meta={
                **dict(source_meta),
                "sweep_setup_hash": sweep_setup_hash,
            },
            config_snapshot=config_snapshot,
            schema_source_hash=schema_source_hash,
            simulation_setup_hash=simulation_setup_hash,
            include_data_records=False,
            result_payload=result_payload,
        )
        uow.commit()
    return (cache_dataset_id, bundle_id)


def _result_metric_options_for_family(view_family: str) -> dict[str, str]:
    """Return metric selector options for a result-view family."""
    from legacy.legacy_nicegui_archived.features.simulation.views.plots import (
        _result_metric_options_for_family as _result_metric_options_for_family_impl,
    )

    return _result_metric_options_for_family_impl(view_family)


def _result_trace_options_for_family(view_family: str) -> dict[str, str]:
    """Return trace selector options for a result-view family."""
    from legacy.legacy_nicegui_archived.features.simulation.views.plots import (
        _result_trace_options_for_family as _result_trace_options_for_family_impl,
    )

    return _result_trace_options_for_family_impl(view_family)


def _result_port_options(result: SimulationResult) -> dict[int, str]:
    """Return available output/input port options for the current result bundle."""
    return {port: str(port) for port in result.available_port_indices}


def _format_mode_label(mode: tuple[int, ...]) -> str:
    """Return a readable label for one signal/idler mode tuple."""
    values = ", ".join(str(value) for value in mode)
    if all(value == 0 for value in mode):
        return f"Signal ({values})"
    return f"Sideband ({values})"


def _result_mode_options(result: SimulationResult) -> dict[str, str]:
    """Return mode selector options for the current result bundle."""
    return {
        SimulationResult.mode_token(mode): _format_mode_label(mode)
        for mode in result.available_mode_indices
    }


def _first_option_key(options: dict[str, str]) -> str:
    """Return the first key from a non-empty options dict."""
    return next(iter(options))


def _resolve_option_key(options: dict[str, str], value: object) -> str:
    """Resolve a select value to one option key, accepting either key or label."""
    if not options:
        return ""
    first_key = _first_option_key(options)
    if value is None:
        return first_key
    text = str(value).strip()
    if text in options:
        return text
    normalized = text.casefold()
    for key, label in options.items():
        if normalized == str(label).strip().casefold():
            return key
    return first_key


def _coerce_int_value(value: object, default: int) -> int:
    """Convert a dynamic UI value to int with a safe fallback."""
    try:
        return int(float(str(value)))
    except Exception:
        return default


def _require_ui_element(element: Any | None, name: str) -> Any:
    """Require one lazily populated UI element before mutating it."""
    if element is None:
        raise RuntimeError(f"{name} is unavailable.")
    return element


def _finite_float_or_none(value: float) -> float | None:
    """Return value only when finite, otherwise None for Plotly gaps."""
    import math

    return value if math.isfinite(value) else None


def _complex_component_series(
    values: list[complex],
    component: str,
) -> list[float | None]:
    """Project complex values to the requested scalar component."""
    import math

    if component == "real":
        return [_finite_float_or_none(value.real) for value in values]
    if component == "imag":
        return [_finite_float_or_none(value.imag) for value in values]
    if component == "magnitude":
        return [_finite_float_or_none(abs(value)) for value in values]
    if component == "phase_deg":
        return [
            _finite_float_or_none(math.degrees(math.atan2(value.imag, value.real)))
            for value in values
        ]
    raise ValueError(f"Unsupported complex component: {component}")


def _post_process_mode_options(
    result: SimulationResult,
    mode_filter: str,
) -> dict[str, str]:
    """Return mode options constrained by one post-processing mode filter."""
    filter_key = str(mode_filter).strip().lower()
    if filter_key == "sideband":
        options = filtered_modes(result, "sideband")
    elif filter_key == "all":
        options = filtered_modes(result, "all")
    else:
        options = filtered_modes(result, "base")
    return {SimulationResult.mode_token(mode): _format_mode_label(mode) for mode in options}


def _format_complex_scalar(value: complex) -> str:
    """Format one complex value into a compact string."""
    return f"{value.real:.4e}{value.imag:+.4e}j"


def _coordinate_weight_fields_editable(weight_mode: str) -> bool:
    """Return whether coordinate-transform alpha/beta fields are editable."""
    return str(weight_mode).strip().lower() == "manual"


def _can_save_post_processed_results(
    runtime_output: PortMatrixSweep | PortMatrixSweepRun | Mapping[str, Any] | None,
    flow_spec: dict[str, Any] | None,
) -> bool:
    """Return whether post-processed results are ready for dataset persistence."""
    return (
        isinstance(runtime_output, (PortMatrixSweep, PortMatrixSweepRun))
        or (isinstance(runtime_output, Mapping) and is_trace_batch_bundle_payload(runtime_output))
    ) and isinstance(flow_spec, dict)


def _build_post_processed_result_payload(
    sweep: PortMatrixSweep,
    *,
    reference_impedance_ohm: float,
) -> tuple[SimulationResult, dict[int, str]]:
    """Convert one post-processed Y sweep into a SimulationResult-like payload."""
    if reference_impedance_ohm <= 0:
        raise ValueError("Reference impedance must be positive.")
    if sweep.dimension < 1:
        raise ValueError("Post-processed sweep has no basis labels.")

    mode = SimulationResult.normalize_mode(sweep.mode)
    frequencies = [float(value) for value in sweep.frequencies_ghz]
    if not frequencies:
        raise ValueError("Post-processed sweep has no frequency points.")

    matrix_count = len(frequencies)
    dim = sweep.dimension
    identity = np.eye(dim, dtype=np.complex128)
    y_matrices: list[np.ndarray] = []
    z_matrices: list[np.ndarray] = []
    s_matrices: list[np.ndarray] = []
    for matrix in sweep.y_matrices:
        y_matrix = np.asarray(matrix, dtype=np.complex128)
        if y_matrix.shape != (dim, dim):
            raise ValueError("Post-processed sweep matrix shape is inconsistent.")
        y_matrices.append(y_matrix)
        try:
            z_matrix = np.linalg.solve(y_matrix, identity)
        except np.linalg.LinAlgError as exc:
            raise ValueError(f"Y->Z conversion failed: {exc}") from exc
        z_matrices.append(z_matrix)
        try:
            s_matrix = np.linalg.solve(
                (z_matrix + (reference_impedance_ohm * identity)).T,
                (z_matrix - (reference_impedance_ohm * identity)).T,
            ).T
        except np.linalg.LinAlgError as exc:
            raise ValueError(f"Z->S conversion failed: {exc}") from exc
        s_matrices.append(s_matrix)

    if len(y_matrices) != matrix_count:
        raise ValueError("Post-processed sweep matrix count does not match frequency points.")

    port_indices = list(range(1, dim + 1))
    port_options = {port: str(sweep.labels[port - 1]) for port in port_indices}
    s_mode_real: dict[str, list[float]] = {}
    s_mode_imag: dict[str, list[float]] = {}
    z_mode_real: dict[str, list[float]] = {}
    z_mode_imag: dict[str, list[float]] = {}
    y_mode_real: dict[str, list[float]] = {}
    y_mode_imag: dict[str, list[float]] = {}
    s_zero_mode_real: dict[str, list[float]] = {}
    s_zero_mode_imag: dict[str, list[float]] = {}

    for output_pos, output_port in enumerate(port_indices):
        for input_pos, input_port in enumerate(port_indices):
            mode_label = SimulationResult._mode_trace_label(mode, output_port, mode, input_port)
            zero_label = f"S{output_port}{input_port}"
            s_trace = [complex(matrix[output_pos, input_pos]) for matrix in s_matrices]
            z_trace = [complex(matrix[output_pos, input_pos]) for matrix in z_matrices]
            y_trace = [complex(matrix[output_pos, input_pos]) for matrix in y_matrices]
            s_mode_real[mode_label] = [float(value.real) for value in s_trace]
            s_mode_imag[mode_label] = [float(value.imag) for value in s_trace]
            z_mode_real[mode_label] = [float(value.real) for value in z_trace]
            z_mode_imag[mode_label] = [float(value.imag) for value in z_trace]
            y_mode_real[mode_label] = [float(value.real) for value in y_trace]
            y_mode_imag[mode_label] = [float(value.imag) for value in y_trace]
            if all(value == 0 for value in mode):
                s_zero_mode_real[zero_label] = list(s_mode_real[mode_label])
                s_zero_mode_imag[zero_label] = list(s_mode_imag[mode_label])

    s11_label = SimulationResult._mode_trace_label(mode, 1, mode, 1)
    s11_real = list(s_mode_real.get(s11_label, [0.0] * matrix_count))
    s11_imag = list(s_mode_imag.get(s11_label, [0.0] * matrix_count))
    converted = SimulationResult(
        frequencies_ghz=frequencies,
        s11_real=s11_real,
        s11_imag=s11_imag,
        port_indices=port_indices,
        mode_indices=[mode],
        s_parameter_real=s_zero_mode_real,
        s_parameter_imag=s_zero_mode_imag,
        s_parameter_mode_real=s_mode_real,
        s_parameter_mode_imag=s_mode_imag,
        z_parameter_mode_real=z_mode_real,
        z_parameter_mode_imag=z_mode_imag,
        y_parameter_mode_real=y_mode_real,
        y_parameter_mode_imag=y_mode_imag,
    )
    return (converted, port_options)


def _build_post_processed_sweep_explorer_payload(
    runtime_output: PortMatrixSweepRun,
    *,
    reference_impedance_ohm: float,
) -> dict[str, Any]:
    """Convert canonical post-processed sweep runtime into one explorer-only sweep payload."""
    converted_points = tuple(
        SimulationSweepPointResult(
            point_index=int(point.point_index),
            axis_indices=tuple(int(index) for index in point.axis_indices),
            axis_values={
                str(target_value_ref): float(value)
                for target_value_ref, value in point.axis_values.items()
            },
            result=_build_post_processed_result_payload(
                point.sweep,
                reference_impedance_ohm=reference_impedance_ohm,
            )[0],
        )
        for point in runtime_output.points
    )
    payload = simulation_sweep_run_to_payload(
        SimulationSweepRun(
            axes=tuple(runtime_output.axes),
            points=converted_points,
            representative_point_index=int(runtime_output.representative_point_index),
        )
    )
    payload["port_labels"] = {
        str(index + 1): str(label)
        for index, label in enumerate(runtime_output.representative_sweep.labels)
    }
    return payload


def _sweep_payload_port_options(
    sweep_payload: Mapping[str, Any] | None,
    *,
    fallback_result: SimulationResult,
) -> dict[int, str]:
    """Resolve one sweep compare port-label mapping from payload metadata or result fallback."""
    if not isinstance(sweep_payload, Mapping):
        return _result_port_options(fallback_result)
    raw_labels = sweep_payload.get("port_labels")
    if not isinstance(raw_labels, Mapping):
        return _result_port_options(fallback_result)
    resolved: dict[int, str] = {}
    for raw_port, raw_label in raw_labels.items():
        try:
            port = int(str(raw_port))
        except Exception:
            continue
        resolved[port] = str(raw_label)
    return resolved or _result_port_options(fallback_result)


def _default_result_trace_selection(
    result: SimulationResult,
    family: str,
    *,
    port_options: dict[int, str],
) -> _ResultTraceSelection:
    """Return the default trace-card payload for one result family."""
    mode_options = _result_mode_options(result)
    trace_options = _result_trace_options_for_family(family)
    default_mode_token = _first_option_key(mode_options) if mode_options else "0"
    default_port = next(iter(port_options)) if port_options else 1
    return {
        "trace": _first_option_key(trace_options),
        "output_mode": SimulationResult.parse_mode_token(default_mode_token),
        "output_port": default_port,
        "input_mode": SimulationResult.parse_mode_token(default_mode_token),
        "input_port": default_port,
    }


def _default_sweep_result_trace_selection(
    result: SimulationResult,
    family: str,
    *,
    port_options: dict[int, str],
    sweep_axis_index: int,
) -> dict[str, Any]:
    """Return one default trace-card payload for frequency-first sweep comparison."""
    selection = dict(
        _default_result_trace_selection(
            result,
            family,
            port_options=port_options,
        )
    )
    selection["sweep_axis_index"] = int(sweep_axis_index)
    return selection



def _format_export_suffix(
    output_mode: tuple[int, ...],
    input_mode: tuple[int, ...] | None = None,
) -> str:
    """Build a concise mode suffix for exported dataset parameter names."""
    if input_mode is None:
        if all(value == 0 for value in output_mode):
            return ""
        return f" [om={output_mode}]"

    if all(value == 0 for value in output_mode) and all(value == 0 for value in input_mode):
        return ""
    return f" [om={output_mode}, im={input_mode}]"


def _format_mode_matrix_parameter_name(
    prefix: str,
    label: str,
) -> str:
    """Convert an internal mode-aware trace key into a user-facing parameter name."""
    parsed = SimulationResult._parse_mode_trace_label(label)
    if parsed is None:
        return f"{prefix}?"
    output_mode, output_port, input_mode, input_port = parsed
    base = f"{prefix}{output_port}{input_port}"
    return f"{base}{_format_export_suffix(output_mode, input_mode)}"


def _format_mode_cm_parameter_name(label: str) -> str:
    """Convert an internal CM trace key into a user-facing parameter name."""
    parsed = SimulationResult._parse_cm_trace_label(label)
    if parsed is None:
        return "CM?"
    output_mode, output_port = parsed
    base = f"CM{output_port}"
    return f"{base}{_format_export_suffix(output_mode)}"


def _build_mode_complex_data_records(
    *,
    dataset_id: int,
    data_type: str,
    parameter_prefix: str,
    real_map: dict[str, list[float]],
    imag_map: dict[str, list[float]],
    frequencies_ghz: list[float],
    additional_axes: list[dict[str, Any]] | None = None,
    parameter_suffix: str = "",
) -> list[DataRecord]:
    """Convert one complex-valued bundle into DataRecord rows."""
    frequency_axis = [{"name": "frequency", "unit": "GHz", "values": frequencies_ghz}]
    if additional_axes:
        frequency_axis.extend(dict(axis) for axis in additional_axes)
    records: list[DataRecord] = []

    for label in sorted(set(real_map) & set(imag_map)):
        parameter_name = (
            f"{_format_mode_matrix_parameter_name(parameter_prefix, label)}{parameter_suffix}"
        )
        records.append(
            DataRecord(
                dataset_id=dataset_id,
                data_type=data_type,
                parameter=parameter_name,
                representation="real",
                axes=frequency_axis,
                values=real_map[label],
            )
        )
        records.append(
            DataRecord(
                dataset_id=dataset_id,
                data_type=data_type,
                parameter=parameter_name,
                representation="imaginary",
                axes=frequency_axis,
                values=imag_map[label],
            )
        )

    return records


def _build_mode_scalar_data_records(
    *,
    dataset_id: int,
    data_type: str,
    parameter_prefix: str,
    values_map: dict[str, list[float]],
    frequencies_ghz: list[float],
    additional_axes: list[dict[str, Any]] | None = None,
    parameter_suffix: str = "",
) -> list[DataRecord]:
    """Convert one scalar-valued bundle into DataRecord rows."""
    frequency_axis = [{"name": "frequency", "unit": "GHz", "values": frequencies_ghz}]
    if additional_axes:
        frequency_axis.extend(dict(axis) for axis in additional_axes)
    records: list[DataRecord] = []

    for label in sorted(values_map):
        parameter_name = (
            _format_mode_cm_parameter_name(label)
            if parameter_prefix == "CM"
            else _format_mode_matrix_parameter_name(parameter_prefix, label)
        )
        parameter_name = f"{parameter_name}{parameter_suffix}"
        records.append(
            DataRecord(
                dataset_id=dataset_id,
                data_type=data_type,
                parameter=parameter_name,
                representation="value",
                axes=frequency_axis,
                values=values_map[label],
            )
        )

    return records


def _sanitize_postprocess_label_token(label: str) -> str:
    """Sanitize one transformed basis label for parameter naming."""
    sanitized = (
        str(label)
        .replace(" ", "")
        .replace("(", "_")
        .replace(")", "")
        .replace(",", "_")
        .replace("[", "_")
        .replace("]", "")
        .replace("/", "_")
        .replace("-", "_")
    )
    while "__" in sanitized:
        sanitized = sanitized.replace("__", "_")
    return sanitized.strip("_") or "x"


def _format_post_processed_y_parameter_name(
    *,
    row_label: str,
    col_label: str,
    mode: tuple[int, ...],
) -> str:
    """Build one output parameter name for a post-processed Y-matrix entry."""
    if row_label.isdigit() and col_label.isdigit():
        base = f"Y{row_label}{col_label}"
    else:
        sanitized_row = _sanitize_postprocess_label_token(row_label)
        sanitized_col = _sanitize_postprocess_label_token(col_label)
        base = f"Y_{sanitized_row}_{sanitized_col}"
    return f"{base}{_format_export_suffix(mode, mode)}"


def _build_post_processed_y_data_records(
    *,
    dataset_id: int,
    sweep: PortMatrixSweep,
    additional_axes: list[dict[str, Any]] | None = None,
    parameter_suffix: str = "",
) -> list[DataRecord]:
    """Convert one post-processed Y sweep into real/imaginary DataRecord rows."""
    frequency_axis = [{"name": "frequency", "unit": "GHz", "values": list(sweep.frequencies_ghz)}]
    if additional_axes:
        frequency_axis.extend(dict(axis) for axis in additional_axes)
    records: list[DataRecord] = []

    for row_index, row_label in enumerate(sweep.labels):
        for col_index, col_label in enumerate(sweep.labels):
            parameter_name = (
                _format_post_processed_y_parameter_name(
                    row_label=row_label,
                    col_label=col_label,
                    mode=sweep.mode,
                )
                + parameter_suffix
            )
            trace_values = sweep.trace(row_index, col_index)
            records.append(
                DataRecord(
                    dataset_id=dataset_id,
                    data_type="y_params",
                    parameter=parameter_name,
                    representation="real",
                    axes=frequency_axis,
                    values=[_finite_float_or_none(value.real) for value in trace_values],
                )
            )
            records.append(
                DataRecord(
                    dataset_id=dataset_id,
                    data_type="y_params",
                    parameter=parameter_name,
                    representation="imaginary",
                    axes=frequency_axis,
                    values=[_finite_float_or_none(value.imag) for value in trace_values],
                )
            )
    return records


def _build_post_processed_runtime_data_records(
    *,
    dataset_id: int,
    runtime_output: PortMatrixSweep | PortMatrixSweepRun,
) -> list[DataRecord]:
    """Materialize post-processed runtime output into dataset trace records."""
    if isinstance(runtime_output, PortMatrixSweep):
        return _build_post_processed_y_data_records(dataset_id=dataset_id, sweep=runtime_output)

    axis_units = {axis.target_value_ref: axis.unit for axis in runtime_output.axes}
    records: list[DataRecord] = []
    for point in runtime_output.points:
        parameter_suffix = _format_sweep_parameter_suffix(
            axis_values=point.axis_values,
            axis_units=axis_units,
        )
        additional_axes = [
            {
                "name": str(axis.target_value_ref),
                "unit": str(axis.unit),
                "values": [
                    float(
                        point.axis_values.get(
                            axis.target_value_ref,
                            axis.values[
                                int(point.axis_indices[axis_position])
                                if axis_position < len(point.axis_indices)
                                else 0
                            ],
                        )
                    )
                ],
                "index": (
                    int(point.axis_indices[axis_position])
                    if axis_position < len(point.axis_indices)
                    else 0
                ),
                "axis_points": len(axis.values),
            }
            for axis_position, axis in enumerate(runtime_output.axes)
        ]
        records.extend(
            _build_post_processed_y_data_records(
                dataset_id=dataset_id,
                sweep=point.sweep,
                additional_axes=additional_axes,
                parameter_suffix=parameter_suffix,
            )
        )
    return records


def _build_trace_batch_data_records(
    *,
    dataset_id: int,
    trace_batch_payload: Mapping[str, Any],
) -> list[DataRecord]:
    """Materialize metadata-only trace rows from one persisted trace-batch payload."""
    if not is_trace_batch_bundle_payload(trace_batch_payload):
        raise ValueError("Payload is not a trace-batch bundle.")

    raw_trace_records = trace_batch_payload.get("trace_records", [])
    if not isinstance(raw_trace_records, list) or not raw_trace_records:
        raise ValueError("Trace-batch payload has no trace records.")

    records: list[DataRecord] = []
    for raw_trace_record in raw_trace_records:
        if not isinstance(raw_trace_record, Mapping):
            raise ValueError("Trace-batch trace record entry is invalid.")
        store_ref = raw_trace_record.get("store_ref")
        raw_axes = raw_trace_record.get("axes", [])
        if not isinstance(store_ref, Mapping) or not store_ref:
            raise ValueError("Trace-batch trace record is missing store_ref metadata.")
        if not isinstance(raw_axes, list) or not raw_axes:
            raise ValueError("Trace-batch trace record is missing axis metadata.")
        records.append(
            DataRecord(
                dataset_id=dataset_id,
                data_type=str(
                    raw_trace_record.get("family") or raw_trace_record.get("data_type") or ""
                ),
                parameter=str(raw_trace_record.get("parameter") or ""),
                representation=str(raw_trace_record.get("representation") or ""),
                axes=[dict(axis) for axis in raw_axes if isinstance(axis, Mapping)],
                values=[],
                store_ref=dict(store_ref),
            )
        )
    return records


def _resolved_source_run_kind(
    source_bundle_snapshot: ResultBundleSnapshot | None,
    *,
    source_sweep_payload: Mapping[str, Any] | None = None,
) -> str:
    """Resolve one canonical source run kind from stored bundle payload or runtime fallback."""
    result_payload = source_bundle_snapshot["result_payload"] if source_bundle_snapshot else None
    if isinstance(result_payload, Mapping):
        if is_trace_batch_bundle_payload(result_payload):
            summary_payload = result_payload.get("trace_batch_record", {}).get(
                "summary_payload", {}
            )
            run_kind = str(summary_payload.get("run_kind", "")).strip()
        else:
            run_kind = str(result_payload.get("run_kind", "")).strip()
        if run_kind:
            return run_kind
    if isinstance(source_sweep_payload, Mapping):
        if is_trace_batch_bundle_payload(source_sweep_payload):
            summary_payload = source_sweep_payload.get("trace_batch_record", {}).get(
                "summary_payload", {}
            )
            run_kind = str(summary_payload.get("run_kind", "")).strip()
        else:
            run_kind = str(source_sweep_payload.get("run_kind", "")).strip()
        if run_kind:
            return run_kind
    return "single_run"


def _resolved_source_sweep_setup_hash(
    source_bundle_snapshot: ResultBundleSnapshot | None,
) -> str | None:
    """Extract one stable sweep-setup hash from the source simulation bundle snapshot."""
    if source_bundle_snapshot is None:
        return None
    source_meta = source_bundle_snapshot["source_meta"]
    if isinstance(source_meta, Mapping):
        raw_hash = source_meta.get("sweep_setup_hash")
        if isinstance(raw_hash, str) and raw_hash.strip():
            return raw_hash.strip()

    config_snapshot = source_bundle_snapshot["config_snapshot"]
    if not isinstance(config_snapshot, Mapping):
        return None
    raw_hash = config_snapshot.get("sweep_setup_hash")
    if isinstance(raw_hash, str) and raw_hash.strip():
        return raw_hash.strip()
    sweep_snapshot = config_snapshot.get("sweep")
    if not isinstance(sweep_snapshot, Mapping):
        return None
    nested_hash = sweep_snapshot.get("setup_hash")
    if isinstance(nested_hash, str) and nested_hash.strip():
        return nested_hash.strip()
    return None


def _resolved_source_sweep_payload(
    source_bundle_snapshot: ResultBundleSnapshot | None,
    *,
    source_sweep_payload: Mapping[str, Any] | None = None,
) -> dict[str, Any] | None:
    """Resolve one canonical sweep payload from bundle storage or runtime fallback."""
    if source_bundle_snapshot is not None:
        result_payload = source_bundle_snapshot["result_payload"]
        resolved_payload = _coerce_parameter_sweep_payload(result_payload)
        if isinstance(resolved_payload, Mapping):
            return resolved_payload
    resolved_runtime_payload = _coerce_parameter_sweep_payload(source_sweep_payload)
    if isinstance(resolved_runtime_payload, Mapping):
        return resolved_runtime_payload
    return None


def _build_post_processed_sweep_point_metadata(
    *,
    source_point: Mapping[str, Any],
    source_simulation_bundle_id: int | None,
    input_source_type: str,
) -> dict[str, Any]:
    """Build one reproducible point-handle entry for a post-processed sweep bundle."""
    axis_indices = source_point.get("axis_indices", [])
    if not isinstance(axis_indices, list):
        axis_indices = []
    raw_axis_values = source_point.get("axis_values", {})
    if not isinstance(raw_axis_values, Mapping):
        raw_axis_values = {}

    point_index = int(source_point.get("point_index", 0))
    handle: dict[str, Any] = {
        "kind": "replay_from_source_bundle_point",
        "source_point_index": point_index,
        "input_source_type": input_source_type,
        "flow_spec_ref": "config_snapshot",
    }
    if source_simulation_bundle_id is not None:
        handle["source_simulation_bundle_id"] = int(source_simulation_bundle_id)

    return {
        "source_point_index": point_index,
        "axis_indices": [int(value) for value in axis_indices],
        "axis_values": {
            str(target): float(value) for target, value in sorted(raw_axis_values.items())
        },
        "postprocess_result_handle": handle,
    }


def _build_post_processed_bundle_artifacts(
    *,
    sweep: PortMatrixSweep,
    flow_spec: Mapping[str, Any],
    source_simulation_bundle_id: int | None,
    source_bundle_snapshot: ResultBundleSnapshot | None = None,
    source_sweep_payload: Mapping[str, Any] | None = None,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    """Build source_meta/config/provenance payloads for one post-processed trace batch."""
    input_source_type = str(flow_spec.get("input_y_source", "raw_y")).strip() or "raw_y"
    source_run_kind = _resolved_source_run_kind(
        source_bundle_snapshot,
        source_sweep_payload=source_sweep_payload,
    )
    resolved_sweep_payload = _resolved_source_sweep_payload(
        source_bundle_snapshot,
        source_sweep_payload=source_sweep_payload,
    )

    source_meta: dict[str, Any] = {
        "origin": "simulation_postprocess",
        "source_simulation_bundle_id": source_simulation_bundle_id,
        "source_run_kind": source_run_kind,
        "source_kind": sweep.source_kind,
        "input_source_type": input_source_type,
        "mode_token": SimulationResult.mode_token(sweep.mode),
    }
    if source_bundle_snapshot is not None:
        source_meta["source_bundle_type"] = source_bundle_snapshot["bundle_type"]

    config_snapshot = json.loads(json.dumps(flow_spec))
    config_snapshot["input_source_type"] = input_source_type
    config_snapshot["source_run_kind"] = source_run_kind
    if source_simulation_bundle_id is not None:
        config_snapshot["source_simulation_bundle_id"] = int(source_simulation_bundle_id)
    if (sweep_setup_hash := _resolved_source_sweep_setup_hash(source_bundle_snapshot)) is not None:
        config_snapshot["sweep_setup_hash"] = sweep_setup_hash

    provenance_payload: dict[str, Any] = {
        "kind": "trace_batch_postprocess_lineage",
        "run_kind": source_run_kind,
        "dimension": int(sweep.dimension),
        "labels": list(sweep.labels),
        "mode": [int(value) for value in sweep.mode],
        "frequency_points": len(sweep.frequencies_ghz),
        "input_source_type": input_source_type,
        "canonical_authority": {
            "kind": "trace_batch_record",
            "scope": "postprocess_trace_batch",
        },
        "projection": {
            "kind": "trace_store_projection",
            "family": "y_matrix",
            "frequency_points": len(sweep.frequencies_ghz),
            "mode_token": SimulationResult.mode_token(sweep.mode),
        },
    }
    if source_simulation_bundle_id is not None:
        provenance_payload["canonical_authority"]["source_simulation_bundle_id"] = int(
            source_simulation_bundle_id
        )

    if isinstance(resolved_sweep_payload, Mapping):
        source_points = resolved_sweep_payload.get("points", [])
        if not isinstance(source_points, list):
            source_points = []
        representative_point_index = int(
            resolved_sweep_payload.get("representative_point_index", 0)
        )
        provenance_payload.update(
            {
                "source_bundle": {
                    "bundle_type": (
                        source_bundle_snapshot["bundle_type"]
                        if source_bundle_snapshot is not None
                        else "circuit_simulation"
                    ),
                    "bundle_id": source_simulation_bundle_id,
                    "run_kind": "parameter_sweep",
                },
                "sweep_axes": json.loads(json.dumps(resolved_sweep_payload.get("sweep_axes", []))),
                "point_count": int(resolved_sweep_payload.get("point_count", len(source_points))),
                "representative_point_index": representative_point_index,
                "points": [
                    _build_post_processed_sweep_point_metadata(
                        source_point=point,
                        source_simulation_bundle_id=source_simulation_bundle_id,
                        input_source_type=input_source_type,
                    )
                    for point in source_points
                    if isinstance(point, Mapping)
                ],
            }
        )
        provenance_payload["projection"]["representative_source_point_index"] = (
            representative_point_index
        )

    return (source_meta, config_snapshot, provenance_payload)


def _port_label_token(label: str) -> str:
    """Convert one port label into a stable matrix-name token."""
    normalized = str(label).strip()
    if not normalized:
        return "x"
    head = normalized.split("(", maxsplit=1)[0].strip()
    candidate = head or normalized
    if candidate.isdigit():
        return candidate
    sanitized = re.sub(r"[^0-9a-zA-Z]+", "_", candidate).strip("_")
    return (sanitized or "x").lower()



def _build_s_parameter_data_records(
    dataset_id: int,
    result: SimulationResult,
    *,
    additional_axes: list[dict[str, Any]] | None = None,
    parameter_suffix: str = "",
) -> list[DataRecord]:
    """Convert the cached zero-mode S-parameter bundle into DataRecord rows."""
    frequency_axis = [{"name": "frequency", "unit": "GHz", "values": result.frequencies_ghz}]
    if additional_axes:
        frequency_axis.extend(dict(axis) for axis in additional_axes)
    records: list[DataRecord] = []

    for trace_label in result.available_s_parameter_labels:
        parameter_name = f"{trace_label}{parameter_suffix}"
        records.append(
            DataRecord(
                dataset_id=dataset_id,
                data_type="s_params",
                parameter=parameter_name,
                representation="real",
                axes=frequency_axis,
                values=result.get_s_parameter_real_by_label(trace_label),
            )
        )
        records.append(
            DataRecord(
                dataset_id=dataset_id,
                data_type="s_params",
                parameter=parameter_name,
                representation="imaginary",
                axes=frequency_axis,
                values=result.get_s_parameter_imag_by_label(trace_label),
            )
        )

    return records


def _build_result_bundle_data_records(
    dataset_id: int,
    result: SimulationResult,
    *,
    additional_axes: list[dict[str, Any]] | None = None,
    parameter_suffix: str = "",
) -> list[DataRecord]:
    """Convert all cached simulation bundles into DataRecord rows."""
    records: list[DataRecord] = []

    records.extend(
        _build_mode_complex_data_records(
            dataset_id=dataset_id,
            data_type="s_params",
            parameter_prefix="S",
            real_map=result.s_parameter_mode_real or result._resolved_mode_s_parameter_real(),
            imag_map=result.s_parameter_mode_imag or result._resolved_mode_s_parameter_imag(),
            frequencies_ghz=result.frequencies_ghz,
            additional_axes=additional_axes,
            parameter_suffix=parameter_suffix,
        )
    )
    records.extend(
        _build_mode_complex_data_records(
            dataset_id=dataset_id,
            data_type="z_params",
            parameter_prefix="Z",
            real_map=result.z_parameter_mode_real,
            imag_map=result.z_parameter_mode_imag,
            frequencies_ghz=result.frequencies_ghz,
            additional_axes=additional_axes,
            parameter_suffix=parameter_suffix,
        )
    )
    records.extend(
        _build_mode_complex_data_records(
            dataset_id=dataset_id,
            data_type="y_params",
            parameter_prefix="Y",
            real_map=result.y_parameter_mode_real,
            imag_map=result.y_parameter_mode_imag,
            frequencies_ghz=result.frequencies_ghz,
            additional_axes=additional_axes,
            parameter_suffix=parameter_suffix,
        )
    )
    records.extend(
        _build_mode_scalar_data_records(
            dataset_id=dataset_id,
            data_type="qe",
            parameter_prefix="QE",
            values_map=result.qe_parameter_mode,
            frequencies_ghz=result.frequencies_ghz,
            additional_axes=additional_axes,
            parameter_suffix=parameter_suffix,
        )
    )
    records.extend(
        _build_mode_scalar_data_records(
            dataset_id=dataset_id,
            data_type="qe_ideal",
            parameter_prefix="QEideal",
            values_map=result.qe_ideal_parameter_mode,
            frequencies_ghz=result.frequencies_ghz,
            additional_axes=additional_axes,
            parameter_suffix=parameter_suffix,
        )
    )
    records.extend(
        _build_mode_scalar_data_records(
            dataset_id=dataset_id,
            data_type="commutation",
            parameter_prefix="CM",
            values_map=result.cm_parameter_mode,
            frequencies_ghz=result.frequencies_ghz,
            additional_axes=additional_axes,
            parameter_suffix=parameter_suffix,
        )
    )

    if not records:
        records.extend(
            _build_s_parameter_data_records(
                dataset_id,
                result,
                additional_axes=additional_axes,
                parameter_suffix=parameter_suffix,
            )
        )

    return records


def _format_sweep_value_token(value: float) -> str:
    """Format one sweep coordinate value into a compact stable token."""
    return f"{float(value):.10g}"


def _sweep_progress_log_step(point_count: int) -> int:
    """Return one stable progress log interval for long sweep runs."""
    normalized_points = max(1, int(point_count))
    if normalized_points <= _SWEEP_PROGRESS_MAX_LOG_LINES:
        return 1
    return max(1, normalized_points // _SWEEP_PROGRESS_MAX_LOG_LINES)


def _should_log_sweep_point_progress(*, point_index: int, point_count: int, step: int) -> bool:
    """Decide whether to emit one per-point progress status line."""
    if point_count <= 1:
        return True
    point_no = int(point_index) + 1
    if point_no <= 1 or point_no >= int(point_count):
        return True
    return point_no % max(1, int(step)) == 0


def _format_sweep_parameter_suffix(
    *,
    axis_values: Mapping[str, float],
    axis_units: Mapping[str, str],
) -> str:
    """Build one per-point suffix to keep sweep-exported parameters distinguishable."""
    tokens: list[str] = []
    for target_value_ref in sorted(axis_values):
        value = _format_sweep_value_token(float(axis_values[target_value_ref]))
        unit = str(axis_units.get(target_value_ref, "")).strip()
        if unit:
            tokens.append(f"{target_value_ref}={value} {unit}")
        else:
            tokens.append(f"{target_value_ref}={value}")
    if not tokens:
        return ""
    return f" [sweep {', '.join(tokens)}]"


def _build_sweep_point_axes(
    *,
    run: SimulationSweepRun,
    point_axis_indices: tuple[int, ...],
    point_axis_values: Mapping[str, float],
) -> list[dict[str, Any]]:
    """Build `DataRecord.axes` metadata rows for one sweep point."""
    axes: list[dict[str, Any]] = []
    for axis_position, axis in enumerate(run.axes):
        axis_index = (
            int(point_axis_indices[axis_position]) if axis_position < len(point_axis_indices) else 0
        )
        axis_value = float(point_axis_values.get(axis.target_value_ref, axis.values[axis_index]))
        axes.append(
            {
                "name": f"sweep:{axis.target_value_ref}",
                "unit": str(axis.unit),
                "values": [axis_value],
                "index": axis_index,
                "axis_points": len(axis.values),
            }
        )
    return axes


def _build_sweep_result_bundle_data_records(
    *,
    dataset_id: int,
    sweep_payload: Mapping[str, Any],
) -> list[DataRecord]:
    """Convert a structured sweep payload into per-point trace `DataRecord` rows."""
    sweep_run = simulation_sweep_run_from_payload(sweep_payload)
    axis_units = {axis.target_value_ref: axis.unit for axis in sweep_run.axes}
    records: list[DataRecord] = []
    for point in sweep_run.points:
        parameter_suffix = _format_sweep_parameter_suffix(
            axis_values=point.axis_values,
            axis_units=axis_units,
        )
        records.extend(
            _build_result_bundle_data_records(
                dataset_id=dataset_id,
                result=point.result,
                additional_axes=_build_sweep_point_axes(
                    run=sweep_run,
                    point_axis_indices=point.axis_indices,
                    point_axis_values=point.axis_values,
                ),
                parameter_suffix=parameter_suffix,
            )
        )
    return records



def _normalize_sweep_result_view_state(*,
    view_state: dict[str, Any],
    sweep_run: SimulationSweepRun,
    family_options: Mapping[str, str] | None = None,
    port_options: Mapping[int, str] | None = None,
) -> dict[str, Any]:
    return _normalize_sweep_result_view_state_impl(
        view_state=view_state,
        sweep_run=sweep_run,
        family_options=family_options,
        port_options=port_options,
        _sweep_source_from_sweep_run_cb=_sweep_source_from_sweep_run,
    )


def _normalize_sweep_result_view_state_from_source(*,
    view_state: dict[str, Any],
    sweep_source: Any,
    family_options: Mapping[str, str] | None = None,
    port_options: Mapping[int, str] | None = None,
) -> dict[str, Any]:
    return _normalize_sweep_result_view_state_from_source_impl(
        view_state=view_state,
        sweep_source=sweep_source,
        family_options=family_options,
        port_options=port_options,
    )


def _build_sweep_metric_rows(*,
    sweep_payload: Mapping[str, Any] | None,
    trace_store_bundle: Any = None,
    family: str,
    metric: str,
    trace_selection: Mapping[str, Any] | None = None,
    trace_selections: list[Mapping[str, Any]] | None = None,
    view_axis_target_value_ref: str | None = None,
    fixed_axis_indices: Mapping[str, int] | None = None,
    z0: float,
    frequency_index: int,
    dark_mode: bool,
    port_label_by_index: Mapping[int, str] | None = None,
) -> dict[str, Any]:
    return _build_sweep_metric_rows_impl(
        sweep_payload=sweep_payload,
        trace_store_bundle=trace_store_bundle,
        family=family,
        metric=metric,
        trace_selection=trace_selection,
        trace_selections=trace_selections,
        view_axis_target_value_ref=view_axis_target_value_ref,
        fixed_axis_indices=fixed_axis_indices,
        z0=z0,
        frequency_index=frequency_index,
        dark_mode=dark_mode,
        port_label_by_index=port_label_by_index,
        _resolve_sweep_result_source_cb=_resolve_sweep_result_source,
        _build_simulation_result_figure_cb=_build_simulation_result_figure,
    )


def _render_sweep_result_view_container(*,
    container: Any,
    sweep_payload: Mapping[str, Any] | None,
    trace_store_bundle: Any = None,
    view_state: dict[str, Any],
    family_options: Mapping[str, str],
    title: str,
    empty_message: str,
    header_message: str | None = None,
    summary_prefix: str | None = None,
    testid_prefix: str,
    save_button_label: str | None = None,
    on_save_click: Callable[[], None] | None = None,
    save_enabled: bool = True,
    context_lines: tuple[str, ...] = (),
) -> None:
    return _render_sweep_result_view_container_impl(
        container=container,
        sweep_payload=sweep_payload,
        trace_store_bundle=trace_store_bundle,
        view_state=view_state,
        family_options=family_options,
        title=title,
        empty_message=empty_message,
        header_message=header_message,
        summary_prefix=summary_prefix,
        testid_prefix=testid_prefix,
        save_button_label=save_button_label,
        on_save_click=on_save_click,
        save_enabled=save_enabled,
        context_lines=context_lines,
        _resolve_sweep_result_source_cb=_resolve_sweep_result_source,
        _build_sweep_metric_rows_cb=_build_sweep_metric_rows,
    )


def _build_simulation_workflow_context_lines(
    *,
    circuit_record: CircuitRecord | None,
    source_kind: str,
    stage_kind: str,
    run_kind: str,
    provenance_tokens: tuple[str, ...] = (),
) -> tuple[str, ...]:
    """Build product-facing workflow lines without exposing backend-specific locators."""
    if circuit_record is not None and circuit_record.id is not None:
        design_scope = (
            f"Current Design Scope: live schema {circuit_record.name} "
            f"(Schema #{int(circuit_record.id)})"
        )
    elif circuit_record is not None:
        design_scope = f"Current Design Scope: live schema {circuit_record.name}"
    else:
        design_scope = "Current Design Scope: live simulation runtime"

    provenance = [token for token in provenance_tokens if token]
    provenance_line = "Trace Batch Provenance: " + " | ".join(
        (
            f"source={source_kind}",
            f"stage={stage_kind}",
            f"run={run_kind}",
            *provenance,
        )
    )
    return (
        design_scope,
        "TraceStore-first authority is active for result inspection on this page.",
        provenance_line,
        (
            "Cross-source compare is inspect-only here and stays blocked until traces are "
            "saved into the same Design scope. Use Raw Data or Characterization for "
            "trace-first compare."
        ),
    )


def _summarize_simulation_error(error: Exception | str) -> tuple[str, str]:
    """Map raw Julia/Python errors to a user-friendly summary and detail."""
    detail = str(error)
    if len(detail) > 4000:
        detail = f"{detail[:4000]}\n... (truncated)"

    if "SimulationInputError:" in detail:
        message = detail.split("SimulationInputError:", maxsplit=1)[1].strip().splitlines()[0]
        return (f"Input error: {message}", detail)
    if "SimulationNumericalError:" in detail:
        message = detail.split("SimulationNumericalError:", maxsplit=1)[1].strip().splitlines()[0]
        return (f"Numerical solver error: {message}", detail)
    if "Ports without resistors detected" in detail:
        return (
            "Invalid schema: each port needs a matching resistor (for example 50 Ohm).",
            detail,
        )
    if "SingularException" in detail:
        return (
            "Simulation matrix became singular. Check topology connectivity and parameter values.",
            detail,
        )
    if "Package JosephsonCircuits not found" in detail:
        return (
            "Julia dependency is not ready in this worker process. Please retry once.",
            detail,
        )

    first_line = next(
        (line.strip() for line in detail.splitlines() if line.strip()),
        "Unknown error",
    )
    return (first_line[:220], detail)


def _simulation_validation_notify_message(message: str) -> str:
    """Map validation errors to concise UI notify text."""
    if message == "At least one source is required.":
        return "Please add at least one source"
    return message


def _load_latest_circuit_definition(schema_id: int) -> tuple[CircuitRecord, CircuitDefinition]:
    """Load the latest schema record from DB and parse CircuitDefinition."""
    with get_unit_of_work() as uow:
        latest_record = uow.circuits.get(schema_id)

    if latest_record is None:
        raise ValueError(f"SimulationInputError: schema id={schema_id} was not found.")

    try:
        circuit_def = parse_circuit_definition_source(latest_record.definition_json)
    except Exception as exc:
        raise ValueError(
            "SimulationInputError: active schema is invalid. "
            "Required fields: name, components, topology."
        ) from exc

    return latest_record, circuit_def


def _load_saved_setups_for_schema(schema_id: int) -> list[dict[str, Any]]:
    """Compatibility wrapper around feature-local saved setup storage."""
    return _load_saved_setups_for_schema_impl(
        schema_id,
        storage_get=_user_storage_get,
    )


def _save_saved_setups_for_schema(schema_id: int, setups: list[dict[str, Any]]) -> None:
    """Compatibility wrapper around feature-local saved setup persistence."""
    _save_saved_setups_for_schema_impl(
        schema_id,
        setups,
        storage_get=_user_storage_get,
        storage_set=_user_storage_set,
    )


def _load_selected_setup_id(schema_id: int) -> str:
    """Compatibility wrapper around feature-local selected-setup storage."""
    return _load_selected_setup_id_impl(
        schema_id,
        storage_get=_user_storage_get,
    )


def _save_selected_setup_id(schema_id: int, setup_id: str) -> None:
    """Compatibility wrapper around feature-local selected-setup persistence."""
    _save_selected_setup_id_impl(
        schema_id,
        setup_id,
        storage_get=_user_storage_get,
        storage_set=_user_storage_set,
    )


def _load_saved_post_process_setups_for_schema(schema_id: int) -> list[dict[str, Any]]:
    """Compatibility wrapper around feature-local post-processing setup storage."""
    return _load_saved_post_process_setups_for_schema_impl(
        schema_id,
        storage_get=_user_storage_get,
    )


def _save_saved_post_process_setups_for_schema(
    schema_id: int,
    setups: list[dict[str, Any]],
) -> None:
    """Compatibility wrapper around feature-local post-processing setup persistence."""
    _save_saved_post_process_setups_for_schema_impl(
        schema_id,
        setups,
        storage_get=_user_storage_get,
        storage_set=_user_storage_set,
    )


def _load_selected_post_process_setup_id(schema_id: int) -> str:
    """Compatibility wrapper around feature-local post-processing selected-id storage."""
    return _load_selected_post_process_setup_id_impl(
        schema_id,
        storage_get=_user_storage_get,
    )


def _save_selected_post_process_setup_id(schema_id: int, setup_id: str) -> None:
    """Compatibility wrapper around feature-local post-processing selected-id persistence."""
    _save_selected_post_process_setup_id_impl(
        schema_id,
        setup_id,
        storage_get=_user_storage_get,
        storage_set=_user_storage_set,
    )


def _ensure_builtin_saved_setups(schema_id: int, schema_name: str) -> list[dict[str, Any]]:
    """Compatibility wrapper around feature-local built-in setup seeding."""
    return _ensure_builtin_saved_setups_impl(
        schema_id,
        schema_name,
        storage_get=_user_storage_get,
        storage_set=_user_storage_set,
    )


def _has_selected_setup_entry(schema_id: int) -> bool:
    """Compatibility wrapper around feature-local selected-setup lookup."""
    return _has_selected_setup_entry_impl(
        schema_id,
        storage_get=_user_storage_get,
    )



def build_page() -> None:
    def content():
        ui.label("Circuit Simulation").classes("text-2xl font-bold text-fg mb-6")
        _render_simulation_environment()

    content()


def _render_simulation_environment():
    """Render the Simulation Execution environment."""
    owner_client = ui.context.client

    @ui.refreshable
    def sim_env():
        try:
            with get_unit_of_work() as uow:
                circuits = uow.circuits.list_all()
        except Exception:
            circuits = []

        if not circuits:
            render_empty_state(
                icon="warning",
                title="No Schemas Available",
                message="Please create a circuit schema in the Schema Manager first.",
                action_label="Go to Schemas",
                on_action=lambda: ui.navigate.to("/schemas"),
                icon_classes="text-warning mb-4",
            )
            return

        circuit_options = {c.id: c.name for c in circuits}

        # Load from storage or default to first
        active_circuit_id = _user_storage_get("simulation_active_circuit")
        if active_circuit_id not in circuit_options:
            active_circuit_id = circuits[0].id
            _user_storage_set("simulation_active_circuit", active_circuit_id)

        # --- Top Selector ---
        with ui.row().classes("w-full items-center gap-4 mb-4 bg-surface p-4 rounded-xl"):
            ui.label("Active Schema:").classes("text-sm font-bold text-fg")

            def on_circuit_change(e: Any) -> None:
                _user_storage_set("simulation_active_circuit", e.value)
                sim_env.refresh()

            ui.select(
                options=circuit_options, value=active_circuit_id, on_change=on_circuit_change
            ).props("dense outlined options-dense").classes("w-64")

        # Get active record
        active_record = next((c for c in circuits if c.id == active_circuit_id), circuits[0])
        active_record_id = active_record.id
        if active_record_id is None:
            with section_card():
                ui.label("Selected schema is missing a persistent id.").classes("text-danger")
            return
        try:
            active_record, active_circuit_def = _load_latest_circuit_definition(active_record_id)
        except Exception as e:
            with section_card():
                ui.label(f"Error parsing selected schema: {e}").classes("text-danger")
            return
        active_record_id = active_record.id
        if active_record_id is None:
            with section_card():
                ui.label("Selected schema is missing a persistent id.").classes("text-danger")
            return
        displayed_netlist = format_expanded_circuit_definition(active_circuit_def)
        latest_circuit_definition_ref: dict[str, CircuitDefinition] = {
            "definition": active_circuit_def
        }

        runtime_state = SimulationRuntimeState()
        page_coordinator = SimulationPageCoordinator()
        status_container: Any | None = None
        simulation_results_container: Any = None
        simulation_sweep_results_container: Any = None
        post_processing_container: Any = None
        post_processing_results_container: Any = None
        post_processing_sweep_results_container: Any = None
        restored_simulation_batch_id_ref: dict[str, int | None] = {"value": None}
        restored_post_processing_batch_id_ref: dict[str, int | None] = {"value": None}
        poll_timer: Any | None = None
        post_processing_poll_timer: Any | None = None
        raw_view_state = default_result_view_state(
            family_sources={
                family: _first_option_key(options)
                for family, options in _RAW_RESULT_MATRIX_SOURCE_OPTIONS_BY_FAMILY.items()
            }
        )
        post_view_state = default_result_view_state()
        sweep_result_view_state = default_sweep_result_view_state()
        post_processed_sweep_view_state = default_sweep_result_view_state()
        post_processing_input_state = default_post_processing_input_state()
        sweep_target_unit_by_value_ref = _extract_sweep_target_units(active_circuit_def)
        available_setup_ports = sorted(active_circuit_def.available_port_indices)
        termination_inferred_resistance_ohm_by_port: dict[int, float] = {
            port: _TERMINATION_DEFAULT_RESISTANCE_OHM for port in available_setup_ports
        }
        termination_inferred_source_by_port: dict[int, str] = {
            port: "fallback_default_50" for port in available_setup_ports
        }
        termination_inferred_warning_by_port: dict[int, str] = {
            port: (
                f"Port {port}: fallback to {_TERMINATION_DEFAULT_RESISTANCE_OHM:g} Ohm "
                "because schema inference is unavailable."
            )
            for port in available_setup_ports
        }
        try:
            termination_inference = infer_port_termination_resistance_ohm(active_circuit_def)
            termination_inferred_resistance_ohm_by_port = dict(
                termination_inference.resistance_ohm_by_port
            )
            termination_inferred_source_by_port = dict(termination_inference.source_by_port)
            termination_inferred_warning_by_port = dict(termination_inference.warning_by_port)
        except Exception as inference_exc:
            for port in available_setup_ports:
                termination_inferred_warning_by_port[port] = (
                    f"Port {port}: schema inference failed ({inference_exc}); "
                    f"fallback to {_TERMINATION_DEFAULT_RESISTANCE_OHM:g} Ohm."
                )

        termination_state = TerminationSetupState.create(
            available_ports=available_setup_ports,
            default_ohm=_TERMINATION_DEFAULT_RESISTANCE_OHM,
        )
        termination_view_elements = TerminationViewElements()

        def append_status(level: str, message: str) -> None:
            runtime_state.append_status(
                level=level,
                message=message,
                time_label=datetime.now().strftime("%H:%M:%S"),
            )
            render_status()

        def reset_status(message: str | None = None) -> None:
            runtime_state.status_history.clear()
            if message:
                append_status("info", message)
            else:
                render_status()

        def render_status() -> None:
            if status_container is None:
                return

            icon_map = {
                "info": "info",
                "warning": "warning",
                "negative": "error",
                "positive": "check_circle",
            }
            color_map = {
                "info": "text-primary",
                "warning": "text-warning",
                "negative": "text-danger",
                "positive": "text-positive",
            }

            try:
                status_container.clear()
                with status_container:
                    if not runtime_state.status_history:
                        ui.label("No logs yet. Run a simulation to see process messages.").classes(
                            "text-sm text-muted"
                        )
                        return

                    for item in runtime_state.status_history:
                        with ui.row().classes("w-full items-start gap-2"):
                            ui.icon(icon_map.get(item["level"], "info"), size="xs").classes(
                                color_map.get(item["level"], "text-primary mt-1")
                            )
                            ui.label(f"[{item['time']}] {item['message']}").classes(
                                "text-sm text-fg whitespace-pre-wrap break-all"
                            )
            except RuntimeError:
                # Ignore stale status rerenders after the owning client/container has been deleted.
                return

        def _reset_result_view_state(
            view_state: dict[str, Any],
            family_options: dict[str, str],
        ) -> None:
            fallback_family = next(iter(family_options), "s")
            selected_family = str(view_state.get("family", fallback_family))
            if selected_family not in family_options:
                selected_family = fallback_family
            metric_options = _result_metric_options_for_family(selected_family)
            view_state["family"] = selected_family
            view_state["metric"] = (
                _first_option_key(metric_options) if metric_options else "magnitude_linear"
            )
            view_state["traces"] = []

        def _resolved_termination_plan() -> dict[str, Any]:
            return _build_termination_compensation_plan(
                enabled=bool(termination_state.enabled),
                mode=_normalize_termination_mode(termination_state.mode),
                selected_ports=_normalize_termination_selected_ports(
                    termination_state.selected_ports,
                    available_ports=available_setup_ports,
                ),
                manual_resistance_ohm_by_port=_normalize_manual_termination_resistance_map(
                    termination_state.manual_resistance_ohm_by_port,
                    available_ports=available_setup_ports,
                    default_ohm=_TERMINATION_DEFAULT_RESISTANCE_OHM,
                ),
                inferred_resistance_ohm_by_port=termination_inferred_resistance_ohm_by_port,
                inferred_source_by_port=termination_inferred_source_by_port,
                inferred_warning_by_port=termination_inferred_warning_by_port,
                fallback_ohm=_TERMINATION_DEFAULT_RESISTANCE_OHM,
            )

        def _termination_plan_summary(plan: dict[str, Any]) -> str:
            if not bool(plan.get("enabled", False)):
                return "Termination compensation: disabled."
            selected_ports = [int(port) for port in plan.get("selected_ports", [])]
            resistance_map = dict(plan.get("resistance_ohm_by_port", {}))
            source_map = dict(plan.get("source_by_port", {}))
            details = []
            for port in selected_ports:
                resistance = float(resistance_map.get(port, _TERMINATION_DEFAULT_RESISTANCE_OHM))
                source = str(source_map.get(port, "manual"))
                details.append(f"p{port}={resistance:g} Ohm ({source})")
            mode = str(plan.get("mode", "auto"))
            return (
                "Termination compensation: "
                f"enabled, mode={mode}, ports={selected_ports or []}, values={'; '.join(details)}."
            )

        persisted_post_process_input_cache: dict[str, Any] = {
            "selection": None,
            "bundle_id": None,
            "result": None,
            "sweep_payload": None,
            "snapshot": None,
        }
        persisted_post_process_output_cache: dict[str, Any] = {
            "selection": None,
            "bundle_id": None,
            "runtime_output": None,
            "flow_spec": None,
            "source_bundle_id": None,
        }
        resolved_post_process_source_bundle_id_ref: dict[str, int | None] = {"value": None}

        def _selected_design_ids() -> tuple[int, ...]:
            return _normalize_selected_design_ids(app.storage.user.get("selected_datasets", []))

        def _active_persisted_design_id() -> int | None:
            selected_design_ids = _selected_design_ids()
            if not selected_design_ids:
                return None
            return int(selected_design_ids[0])

        page_coordinator.set_active_design(_active_persisted_design_id())

        def _persisted_post_processing_input_bundle() -> tuple[
            SimulationResult | None, dict[str, Any] | None, int | None
        ]:
            return load_persisted_post_processing_input_bundle(
                selected_design_ids=_selected_design_ids(),
                input_cache=persisted_post_process_input_cache,
                get_unit_of_work=get_unit_of_work,
                decode_simulation_result_payload=_decode_simulation_result_payload,
            )

        def _persisted_post_processing_output_bundle() -> tuple[
            Mapping[str, Any] | None, dict[str, Any] | None, int | None, int | None
        ]:
            return load_persisted_post_processing_output_bundle(
                selected_design_ids=_selected_design_ids(),
                output_cache=persisted_post_process_output_cache,
                get_unit_of_work=get_unit_of_work,
            )

        def _invalidate_persisted_authority_caches() -> None:
            invalidate_persisted_authority_caches(
                input_cache=persisted_post_process_input_cache,
                output_cache=persisted_post_process_output_cache,
            )

        def _apply_polled_task_status(task: Any) -> None:
            _apply_polled_task_status_impl(
                task,
                runtime_state=runtime_state,
                append_status=append_status,
            )

        def _apply_polled_post_processing_task_status(task: Any) -> None:
            _apply_polled_post_processing_task_status_impl(
                task,
                runtime_state=runtime_state,
                append_status=append_status,
            )

        def _load_persisted_simulation_views() -> None:
            restored_simulation_batch_id_ref["value"] = runtime_state.current_trace_batch_id
            _invalidate_persisted_authority_caches()
            _reset_result_view_state(raw_view_state, _RESULT_FAMILY_OPTIONS)
            sweep_result_view_state.clear()
            sweep_result_view_state.update(default_sweep_result_view_state())
            render_simulation_result_view()
            _render_simulation_sweep_result_view()
            _render_post_processing_input_panel()

        def _load_persisted_post_processing_views() -> None:
            restored_post_processing_batch_id_ref["value"] = (
                runtime_state.current_post_processing_trace_batch_id
            )
            _invalidate_persisted_authority_caches()
            _reset_result_view_state(post_view_state, _POST_PROCESSED_RESULT_FAMILY_OPTIONS)
            post_processed_sweep_view_state.clear()
            post_processed_sweep_view_state.update(default_sweep_result_view_state())
            _render_post_processed_sweep_result_view()
            render_post_processed_result_view()

        def _render_simulation_restore_prompt(
            latest_result: LatestTraceBatchResponse,
        ) -> None:
            render_simulation_restore_prompt(
                latest_result=latest_result,
                simulation_results_container=simulation_results_container,
                simulation_sweep_results_container=simulation_sweep_results_container,
                post_processing_container=post_processing_container,
                on_load_latest=_load_persisted_simulation_views,
            )

        def _render_post_processing_restore_prompt(
            latest_result: LatestTraceBatchResponse,
        ) -> None:
            render_post_processing_restore_prompt(
                latest_result=latest_result,
                post_processing_results_container=post_processing_results_container,
                post_processing_sweep_results_container=post_processing_sweep_results_container,
                on_load_latest=_load_persisted_post_processing_views,
            )

        def _render_unavailable_authority_state() -> None:
            render_unavailable_authority_state(
                simulation_results_container=simulation_results_container,
                simulation_sweep_results_container=simulation_sweep_results_container,
                post_processing_container=post_processing_container,
                post_processing_results_container=post_processing_results_container,
                post_processing_sweep_results_container=post_processing_sweep_results_container,
            )

        def _recovery_bindings() -> SimulationRecoveryBindings:
            return SimulationRecoveryBindings(
                owner_client=owner_client,
                runtime_state=runtime_state,
                append_status=append_status,
                load_persisted_simulation_views=_load_persisted_simulation_views,
                load_persisted_post_processing_views=_load_persisted_post_processing_views,
                render_simulation_restore_prompt=_render_simulation_restore_prompt,
                render_post_processing_restore_prompt=_render_post_processing_restore_prompt,
                render_unavailable_authority_state=_render_unavailable_authority_state,
                restored_simulation_batch_id_ref=restored_simulation_batch_id_ref,
                restored_post_processing_batch_id_ref=restored_post_processing_batch_id_ref,
                resolved_post_process_source_bundle_id_ref=resolved_post_process_source_bundle_id_ref,
                poll_timer=poll_timer,
                post_processing_poll_timer=post_processing_poll_timer,
                coordinator=page_coordinator,
            )

        async def _refresh_simulation_authority(
            *,
            preferred_task_id: int | None = None,
            hydrate_views: bool = False,
        ) -> None:
            await refresh_simulation_authority(
                active_design_id=_active_persisted_design_id(),
                bindings=_recovery_bindings(),
                preferred_task_id=preferred_task_id,
                hydrate_views=hydrate_views,
            )

        async def _poll_current_simulation_task() -> None:
            await poll_current_simulation_task(
                active_design_id=_active_persisted_design_id(),
                bindings=_recovery_bindings(),
            )

        async def _poll_current_post_processing_task() -> None:
            await poll_current_post_processing_task(
                active_design_id=_active_persisted_design_id(),
                bindings=_recovery_bindings(),
            )

        def _raw_simulation_result() -> SimulationResult | None:
            persisted_result, _persisted_sweep_payload, persisted_bundle_id = (
                _persisted_post_processing_input_bundle()
            )
            if isinstance(persisted_result, SimulationResult):
                resolved_post_process_source_bundle_id_ref["value"] = persisted_bundle_id
                return persisted_result
            return None

        def _ptc_simulation_result(
            *,
            reference_impedance_ohm: float,
        ) -> SimulationResult | None:
            raw_result = _raw_simulation_result()
            if not isinstance(raw_result, SimulationResult):
                return None
            plan = _resolved_termination_plan()
            if not bool(plan.get("enabled", False)):
                return None
            try:
                return compensate_simulation_result_port_terminations(
                    raw_result,
                    resistance_ohm_by_port=dict(plan.get("resistance_ohm_by_port", {})),
                    reference_impedance_ohm=reference_impedance_ohm,
                )
            except Exception as exc:
                message = f"Termination compensation skipped: {exc}"
                if runtime_state.termination_last_warning != message:
                    runtime_state.termination_last_warning = message
                    append_status("warning", message)
                return raw_result

        def _ptc_simulation_sweep_payload(
            *,
            reference_impedance_ohm: float,
        ) -> dict[str, Any] | None:
            raw_sweep_payload = None
            _persisted_result, persisted_sweep_payload, persisted_bundle_id = (
                _persisted_post_processing_input_bundle()
            )
            if isinstance(persisted_sweep_payload, Mapping):
                raw_sweep_payload = _coerce_parameter_sweep_payload(persisted_sweep_payload)
                resolved_post_process_source_bundle_id_ref["value"] = persisted_bundle_id
            if not isinstance(raw_sweep_payload, Mapping):
                return None
            plan = _resolved_termination_plan()
            if not bool(plan.get("enabled", False)):
                return None
            try:
                return _build_compensated_simulation_sweep_payload(
                    raw_sweep_payload,
                    resistance_ohm_by_port=dict(plan.get("resistance_ohm_by_port", {})),
                    reference_impedance_ohm=reference_impedance_ohm,
                )
            except Exception as exc:
                message = f"Termination compensation sweep payload skipped: {exc}"
                if runtime_state.termination_last_warning != message:
                    runtime_state.termination_last_warning = message
                    append_status("warning", message)
                return None

        def _resolve_post_processing_input_bundle(
            source: str,
            reference_impedance_ohm: float,
        ) -> tuple[SimulationResult, dict[str, Any] | None, int | None]:
            persisted_result = None
            persisted_sweep_payload = None
            persisted_bundle_id = None
            _persisted_result, persisted_sweep_payload, persisted_bundle_id = (
                _persisted_post_processing_input_bundle()
            )
            if isinstance(_persisted_result, SimulationResult):
                persisted_result = _persisted_result
            if isinstance(persisted_sweep_payload, Mapping):
                persisted_sweep_payload = _coerce_parameter_sweep_payload(persisted_sweep_payload)
            raw_result = persisted_result
            if not isinstance(raw_result, SimulationResult):
                raise ValueError("Simulation result is unavailable.")

            canonical_sweep_payload = persisted_sweep_payload
            source_bundle_id = persisted_bundle_id
            if source_bundle_id is not None:
                resolved_post_process_source_bundle_id_ref["value"] = source_bundle_id
            if source == "ptc_y":
                ptc_result = _ptc_simulation_result(
                    reference_impedance_ohm=reference_impedance_ohm,
                )
                if not isinstance(ptc_result, SimulationResult):
                    raise ValueError("PTC Y is unavailable for post-processing.")
                if canonical_sweep_payload is None:
                    return (ptc_result, None, source_bundle_id)
                return (ptc_result, canonical_sweep_payload, source_bundle_id)

            return (raw_result, canonical_sweep_payload, source_bundle_id)

        def _render_post_processing_input_panel() -> None:
            if post_processing_container is None:
                return
            post_processing_container.clear()
            try:
                raw_result, _raw_sweep_payload, resolved_source_bundle_id = (
                    _resolve_post_processing_input_bundle(
                        "raw_y",
                        _TERMINATION_DEFAULT_RESISTANCE_OHM,
                    )
                )
            except ValueError:
                with post_processing_container:
                    ui.label(
                        "Run a simulation first, then apply port-level coordinate transforms "
                        "and Kron reduction here."
                    ).classes("text-sm text-muted")
                return
            if resolved_source_bundle_id is not None:
                resolved_post_process_source_bundle_id_ref["value"] = resolved_source_bundle_id
            ptc_result = _ptc_simulation_result(
                reference_impedance_ohm=_TERMINATION_DEFAULT_RESISTANCE_OHM,
            )

            async def _submit_post_processing_intent(intent: dict[str, Any]) -> Any:
                return await _submit_post_processing_intent_impl(
                    intent,
                    owner_client=owner_client,
                )

            def _record_post_processing_source_bundle(bundle_id: int | None) -> None:
                resolved_post_process_source_bundle_id_ref["value"] = bundle_id

            with post_processing_container:
                _render_post_processing_panel(
                    raw_result=raw_result,
                    ptc_result=ptc_result,
                    initial_input_y_source=str(
                        post_processing_input_state.get("input_y_source", "raw_y")
                    ),
                    on_input_y_source_change=(
                        lambda source: post_processing_input_state.__setitem__(
                            "input_y_source",
                            str(source),
                        )
                    ),
                    resolve_input_bundle=_resolve_post_processing_input_bundle,
                    circuit_definition=latest_circuit_definition_ref["definition"],
                    design_id=_active_persisted_design_id(),
                    schema_id=active_record_id,
                    schema_name=active_record.name,
                    append_status=append_status,
                    on_processing_start=_render_post_processing_results_pending,
                    on_result=handle_post_processing_result,
                    on_source_bundle_resolved=_record_post_processing_source_bundle,
                    resolve_termination_plan=_resolved_termination_plan,
                    on_task_submitted=_handle_post_processing_dispatch,
                    load_saved_setups_for_schema=_load_saved_post_process_setups_for_schema,
                    save_saved_setups_for_schema=_save_saved_post_process_setups_for_schema,
                    load_selected_setup_id=_load_selected_post_process_setup_id,
                    save_selected_setup_id=_save_selected_post_process_setup_id,
                    on_submit=_submit_post_processing_intent,
                )

        def _handle_post_processing_dispatch(dispatch: Any) -> None:
            runtime_state.current_post_processing_task_id = (
                int(dispatch.task.id) if dispatch.task.id is not None else None
            )
            runtime_state.current_post_processing_task_status = str(dispatch.task.status)
            runtime_state.current_post_processing_trace_batch_id = dispatch.task.trace_batch_id
            runtime_state.current_post_processing_task_error = None
            runtime_state.last_post_processing_task_poll_signature = None
            runtime_state.post_processing_long_running_warning_shown = False
            page_coordinator.record_post_processing_dispatch(
                task_id=int(dispatch.task.id) if dispatch.task.id is not None else None,
                trace_batch_id=(
                    int(dispatch.task.trace_batch_id)
                    if dispatch.task.trace_batch_id is not None
                    else None
                ),
                source_batch_id=resolved_post_process_source_bundle_id_ref["value"],
            )
            _invalidate_persisted_authority_caches()
            _reset_result_view_state(post_view_state, _POST_PROCESSED_RESULT_FAMILY_OPTIONS)
            post_processed_sweep_view_state.clear()
            post_processed_sweep_view_state.update(default_sweep_result_view_state())
            render_post_processed_result_view()
            if post_processing_poll_timer is not None:
                post_processing_poll_timer.active = True

        def _render_post_processing_results_pending() -> None:
            if post_processing_results_container is None:
                return
            post_processing_results_container.clear()
            with (
                post_processing_results_container,
                ui.column().classes("w-full items-center justify-center gap-3 py-8"),
            ):
                ui.spinner(size="2.25em").classes("text-primary")
                ui.label("Updating Post Processing Result View...").classes("text-sm text-muted")
            if post_processing_sweep_results_container is not None:
                post_processing_sweep_results_container.clear()
                with post_processing_sweep_results_container:
                    ui.label(
                        "Post-processed sweep explorer will refresh from persisted task output."
                    ).classes("text-sm text-muted")

        def _raw_result_provider(
            _reference_impedance: float,
            view_family: str,
            source_token: str,
        ) -> tuple[SimulationResult, dict[int, str]] | None:
            raw_result = _raw_simulation_result()
            if not isinstance(raw_result, SimulationResult):
                return None
            use_ptc_matrix_source = (
                view_family in _RAW_RESULT_MATRIX_SOURCE_OPTIONS_BY_FAMILY
                and str(source_token or "raw") == "ptc"
            )
            if use_ptc_matrix_source:
                ptc_result = _ptc_simulation_result(
                    reference_impedance_ohm=float(_reference_impedance),
                )
                if isinstance(ptc_result, SimulationResult):
                    bundle = _cached_trace_store_bundle_from_result(ptc_result)
                    return (
                        _result_from_trace_store_bundle(bundle),
                        dict(bundle.port_label_by_index),
                    )
            bundle = _cached_trace_store_bundle_from_result(raw_result)
            return (_result_from_trace_store_bundle(bundle), dict(bundle.port_label_by_index))

        def _post_processed_result_provider(
            reference_impedance: float,
            _view_family: str,
            _source_token: str,
        ) -> tuple[SimulationResult, dict[int, str]] | None:
            persisted_runtime_output, _flow_spec, _bundle_id, source_bundle_id = (
                _persisted_post_processing_output_bundle()
            )
            if not isinstance(persisted_runtime_output, Mapping):
                return None
            resolved_post_process_source_bundle_id_ref["value"] = source_bundle_id
            bundle = _cached_trace_store_bundle_from_post_processed_runtime(
                persisted_runtime_output,
                reference_impedance_ohm=reference_impedance,
            )
            return (_result_from_trace_store_bundle(bundle), dict(bundle.port_label_by_index))

        def _render_simulation_sweep_result_view() -> None:
            if simulation_sweep_results_container is None:
                return
            trace_store_bundle = None
            _persisted_result, persisted_sweep_payload, persisted_bundle_id = (
                _persisted_post_processing_input_bundle()
            )
            resolved_sweep_payload = (
                _coerce_parameter_sweep_payload(persisted_sweep_payload)
                if isinstance(persisted_sweep_payload, Mapping)
                else None
            )
            compensated_sweep_payload = _ptc_simulation_sweep_payload(
                reference_impedance_ohm=float(
                    sweep_result_view_state.get("z0", raw_view_state.get("z0", 50.0)) or 50.0
                )
            )
            display_sweep_payload = (
                compensated_sweep_payload
                if isinstance(compensated_sweep_payload, Mapping)
                else resolved_sweep_payload
            )
            if isinstance(display_sweep_payload, Mapping):
                trace_store_bundle = _cached_trace_store_bundle_from_sweep_payload(
                    display_sweep_payload,
                )
                resolved_post_process_source_bundle_id_ref["value"] = persisted_bundle_id
            context_lines = _build_simulation_workflow_context_lines(
                circuit_record=active_record,
                source_kind="circuit_simulation",
                stage_kind="raw",
                run_kind="parameter_sweep",
                provenance_tokens=(
                    "persisted_batch",
                    (
                        "view=ptc_preview"
                        if isinstance(compensated_sweep_payload, Mapping)
                        else "view=raw"
                    ),
                    "save-path=worker_persisted",
                ),
            )
            _render_sweep_result_view_container(
                container=simulation_sweep_results_container,
                sweep_payload=display_sweep_payload,
                trace_store_bundle=trace_store_bundle,
                view_state=sweep_result_view_state,
                family_options=_SWEEP_RESULT_FAMILY_OPTIONS,
                title="Sweep Result View",
                empty_message=(
                    "Sweep Result View is available after a parameter sweep run. "
                    "Cross-source compare stays blocked here until the traces are "
                    "saved into a Design."
                ),
                context_lines=context_lines,
                testid_prefix="simulation-sweep",
            )

        def _render_post_processed_sweep_result_view() -> None:
            if post_processing_sweep_results_container is None:
                return
            stale_reason = page_coordinator.post_processing_result_stale_reason
            if stale_reason:
                post_processing_sweep_results_container.clear()
                with post_processing_sweep_results_container:
                    ui.icon("warning", size="md").classes("text-warning mb-2")
                    ui.label("Post-processed sweep results are stale.").classes(
                        "text-sm font-medium text-warning"
                    )
                    ui.label(str(stale_reason)).classes("text-sm text-muted")
                return
            runtime_output, flow_spec, _bundle_id, source_bundle_id = (
                _persisted_post_processing_output_bundle()
            )
            if not isinstance(runtime_output, Mapping):
                post_processing_sweep_results_container.clear()
                with post_processing_sweep_results_container:
                    if runtime_state.current_post_processing_task_status in {"queued", "running"}:
                        ui.label(
                            "Post-processed sweep explorer will refresh from persisted task output."
                        ).classes("text-sm text-muted")
                    else:
                        ui.label(
                            "Post-processed sweep explorer is available after a "
                            "parameter-sweep post-processing run."
                        ).classes("text-sm text-muted")
                return
            typed_flow_spec = flow_spec if isinstance(flow_spec, Mapping) else {}
            post_sweep_context_lines = _build_simulation_workflow_context_lines(
                circuit_record=active_record,
                source_kind="circuit_simulation",
                stage_kind="postprocess",
                run_kind="parameter_sweep",
                provenance_tokens=(
                    f"input={typed_flow_spec.get('input_y_source', 'raw_y')!s}",
                    (
                        f"source-bundle=#{int(source_bundle_id)}"
                        if source_bundle_id is not None
                        else "source-bundle=persisted_batch"
                    ),
                    "save-path=worker_persisted",
                ),
            )
            if not _post_processed_runtime_is_sweep(runtime_output, typed_flow_spec):
                _render_sweep_result_view_container(
                    container=post_processing_sweep_results_container,
                    sweep_payload=None,
                    view_state=post_processed_sweep_view_state,
                    family_options=_POST_PROCESSED_RESULT_FAMILY_OPTIONS,
                    title="Post-Processed Sweep Result View",
                    empty_message=(
                        "Post-processed sweep explorer is available after a "
                        "parameter-sweep post-processing run. "
                        "Cross-source compare stays blocked here until the traces are "
                        "saved into a Design."
                    ),
                    context_lines=post_sweep_context_lines,
                    testid_prefix="post-processed-sweep",
                )
                return
            resolved_post_process_source_bundle_id_ref["value"] = source_bundle_id
            try:
                trace_store_bundle = _cached_trace_store_bundle_from_post_processed_runtime(
                    runtime_output,
                    reference_impedance_ohm=float(
                        post_processed_sweep_view_state.get(
                            "z0",
                            post_view_state.get("z0", 50.0),
                        )
                        or 50.0
                    ),
                )
            except Exception as exc:
                post_processing_sweep_results_container.clear()
                with post_processing_sweep_results_container:
                    ui.label(f"Post-processed sweep payload build failed: {exc}").classes(
                        "text-sm text-warning"
                    )
                return
            preview_projection: Mapping[str, object]
            if isinstance(flow_spec, Mapping):
                raw_preview_projection = flow_spec.get("preview_projection")
                preview_projection = (
                    cast(Mapping[str, object], raw_preview_projection)
                    if isinstance(raw_preview_projection, Mapping)
                    else {}
                )
            else:
                preview_projection = {}
            summary_prefix = (
                "canonical=parameter_sweep"
                " | preview=representative point "
                f"#{_coerce_int_value(preview_projection.get('point_index'), 0) + 1}"
            )
            _render_sweep_result_view_container(
                container=post_processing_sweep_results_container,
                sweep_payload=None,
                trace_store_bundle=trace_store_bundle,
                view_state=post_processed_sweep_view_state,
                family_options=_POST_PROCESSED_RESULT_FAMILY_OPTIONS,
                title="Post-Processed Sweep Result View",
                empty_message=(
                    "Post-processed sweep explorer is available after a "
                    "parameter-sweep post-processing run. "
                    "Cross-source compare stays blocked here until the traces are "
                    "saved into a Design."
                ),
                summary_prefix=summary_prefix,
                testid_prefix="post-processed-sweep",
                context_lines=post_sweep_context_lines,
            )

        def render_simulation_result_view() -> None:
            if simulation_results_container is None:
                return

            _persisted_result, persisted_sweep_payload, persisted_bundle_id = (
                _persisted_post_processing_input_bundle()
            )
            resolved_raw_sweep_payload = (
                _coerce_parameter_sweep_payload(persisted_sweep_payload)
                if isinstance(persisted_sweep_payload, Mapping)
                else None
            )
            if persisted_bundle_id is not None:
                resolved_post_process_source_bundle_id_ref["value"] = persisted_bundle_id
            if isinstance(resolved_raw_sweep_payload, Mapping):
                trace_store_bundle = _cached_trace_store_bundle_from_sweep_payload(
                    resolved_raw_sweep_payload,
                )
                context_lines = _build_simulation_workflow_context_lines(
                    circuit_record=active_record,
                    source_kind="circuit_simulation",
                    stage_kind="raw",
                    run_kind="parameter_sweep",
                    provenance_tokens=(
                        "persisted_batch",
                        "save-path=worker_persisted",
                    ),
                )
                _render_sweep_result_view_container(
                    container=simulation_results_container,
                    sweep_payload=resolved_raw_sweep_payload,
                    trace_store_bundle=trace_store_bundle,
                    view_state=sweep_result_view_state,
                    family_options=_SWEEP_RESULT_FAMILY_OPTIONS,
                    title="Parameter Sweep Compare",
                    header_message=(
                        "Simulation sweep view keeps Frequency on the x-axis and overlays "
                        "multiple traces for selected sweep values."
                    ),
                    empty_message="Sweep compare view is available after a parameter sweep run.",
                    testid_prefix="simulation-sweep",
                    context_lines=context_lines,
                )
                return

            raw_context_lines = _build_simulation_workflow_context_lines(
                circuit_record=active_record,
                source_kind="circuit_simulation",
                stage_kind="raw",
                run_kind="single_run",
                provenance_tokens=(
                    "persisted_batch",
                    "save-path=worker_persisted",
                ),
            )
            _render_result_family_explorer(
                container=simulation_results_container,
                view_state=raw_view_state,
                family_options=_RESULT_FAMILY_OPTIONS,
                result_provider=_raw_result_provider,
                family_source_options=_RAW_RESULT_MATRIX_SOURCE_OPTIONS_BY_FAMILY,
                family_source_labels=_RAW_RESULT_MATRIX_SOURCE_LABEL_BY_FAMILY,
                header_message="Raw quick-inspect view from latest simulation run.",
                empty_message=(
                    "Run simulation to inspect raw result traces. "
                    "Cross-source compare becomes available only after saving into a Design."
                ),
                context_lines=raw_context_lines,
                testid_prefix="raw-result-view",
            )

        def render_post_processed_result_view() -> None:
            if post_processing_results_container is None:
                return
            stale_reason = page_coordinator.post_processing_result_stale_reason
            if stale_reason:
                post_processing_results_container.clear()
                with post_processing_results_container:
                    ui.icon("warning", size="lg").classes("text-warning mb-2")
                    ui.label("Post-processing results are stale.").classes(
                        "text-sm font-medium text-warning"
                    )
                    ui.label(str(stale_reason)).classes("text-sm text-muted")
                return

            runtime_output, flow_spec, _persisted_batch_id, resolved_source_bundle_id = (
                _persisted_post_processing_output_bundle()
            )
            if not isinstance(runtime_output, Mapping):
                post_processing_results_container.clear()
                with post_processing_results_container:
                    if runtime_state.current_post_processing_task_status in {"queued", "running"}:
                        ui.spinner(size="2em").classes("text-primary mb-2")
                        ui.label(
                            "Post-processing task is running. "
                            "Results will load from persisted output."
                        ).classes("text-sm text-muted")
                        ui.label(
                            f"task=#{runtime_state.current_post_processing_task_id} | "
                            f"batch={runtime_state.current_post_processing_trace_batch_id}"
                        ).classes("text-xs text-muted")
                    elif runtime_state.current_post_processing_task_status == "failed":
                        ui.icon("error", size="lg").classes("text-danger mb-2")
                        ui.label(
                            runtime_state.current_post_processing_task_error
                            or "Post-processing task failed."
                        ).classes("text-sm text-danger")
                    else:
                        ui.icon("data_object", size="xl").classes("text-muted mb-4 opacity-50")
                        ui.label("Run Post Processing to view pipeline output traces.").classes(
                            "text-sm text-muted mt-2"
                        )
                return
            context_line = None
            typed_flow_spec = flow_spec if isinstance(flow_spec, dict) else None
            post_context_lines = _build_simulation_workflow_context_lines(
                circuit_record=active_record,
                source_kind="circuit_simulation",
                stage_kind="postprocess",
                run_kind=(
                    "parameter_sweep"
                    if _post_processed_runtime_is_sweep(runtime_output, typed_flow_spec)
                    else "single_run"
                ),
                provenance_tokens=(
                    (
                        f"input={typed_flow_spec.get('input_y_source', 'raw_y')!s}"
                        if isinstance(typed_flow_spec, dict)
                        else "input=raw_y"
                    ),
                    (
                        f"source-bundle=#{int(resolved_source_bundle_id)}"
                        if resolved_source_bundle_id is not None
                        else "source-bundle=persisted_batch"
                    ),
                    "save-path=worker_persisted",
                ),
            )
            if isinstance(typed_flow_spec, dict):
                step_count = len(typed_flow_spec.get("steps", []))
                input_source = str(typed_flow_spec.get("input_y_source", "raw_y"))
                hfss_comparable = bool(typed_flow_spec.get("hfss_comparable", False))
                hfss_reason = str(typed_flow_spec.get("hfss_not_comparable_reason", "")).strip()
                hfss_token = "HFSS Comparable=Yes" if hfss_comparable else "HFSS Comparable=No"
                if not hfss_comparable and hfss_reason:
                    hfss_token = f"{hfss_token} ({hfss_reason})"
                preview_token = ""
                if str(typed_flow_spec.get("run_kind", "single_result")) == "parameter_sweep":
                    raw_projection = typed_flow_spec.get("preview_projection")
                    projection: Mapping[str, object] = (
                        cast(Mapping[str, object], raw_projection)
                        if isinstance(raw_projection, Mapping)
                        else {}
                    )
                    point_count = _coerce_int_value(typed_flow_spec.get("point_count"), 0)
                    point_index = _coerce_int_value(projection.get("point_index"), 0) + 1
                    preview_token = (
                        f" | canonical=parameter_sweep({point_count} points) "
                        f"| preview=representative point #{point_index}"
                    )
                context_line = (
                    f"Pipeline steps applied: {step_count} | "
                    f"mode={typed_flow_spec.get('mode_token', 'unknown')} | "
                    f"basis={', '.join(typed_flow_spec.get('basis_labels', []))} | "
                    f"input={input_source}{preview_token} | {hfss_token}"
                )
            if _post_processed_runtime_is_sweep(runtime_output, typed_flow_spec):
                try:
                    trace_store_bundle = _cached_trace_store_bundle_from_post_processed_runtime(
                        runtime_output,
                        reference_impedance_ohm=float(
                            post_processed_sweep_view_state.get(
                                "z0",
                                post_view_state.get("z0", 50.0),
                            )
                            or 50.0
                        ),
                    )
                except Exception as exc:
                    post_processing_results_container.clear()
                    with post_processing_results_container:
                        ui.label(f"Post-processed sweep payload build failed: {exc}").classes(
                            "text-sm text-warning"
                        )
                    return
                _render_sweep_result_view_container(
                    container=post_processing_results_container,
                    sweep_payload=None,
                    trace_store_bundle=trace_store_bundle,
                    view_state=post_processed_sweep_view_state,
                    family_options=_POST_PROCESSED_SWEEP_COMPARE_FAMILY_OPTIONS,
                    title="Parameter Sweep Compare",
                    header_message=(
                        "Post-processed sweep view keeps Frequency on the x-axis and overlays "
                        "multiple traces for selected sweep values."
                    ),
                    empty_message=(
                        "Post-processed sweep compare view is available after a "
                        "parameter-sweep post-processing run."
                    ),
                    summary_prefix=context_line,
                    testid_prefix="post-processed-sweep",
                    context_lines=post_context_lines,
                )
                return

            _render_result_family_explorer(
                container=post_processing_results_container,
                view_state=post_view_state,
                family_options=_POST_PROCESSED_RESULT_FAMILY_OPTIONS,
                result_provider=_post_processed_result_provider,
                header_message=(
                    "Result View consumes the latest Post Processing pipeline output node."
                ),
                empty_message="Run Post Processing to generate the pipeline output node.",
                context_line=context_line,
                context_lines=post_context_lines,
                testid_prefix="post-result-view",
            )

        def handle_post_processing_result(_run_result: Any | None) -> None:
            page_coordinator.clear_post_processing_result_stale()
            _invalidate_persisted_authority_caches()
            _reset_result_view_state(post_view_state, _POST_PROCESSED_RESULT_FAMILY_OPTIONS)
            post_processed_sweep_view_state.clear()
            post_processed_sweep_view_state.update(default_sweep_result_view_state())
            _render_post_processed_sweep_result_view()
            render_post_processed_result_view()

        # --- Single-column full-width flow ---
        with ui.column().classes("w-full gap-6"):
            with section_card():
                with ui.row().classes("items-center gap-2 mb-4"):
                    ui.icon("description", size="sm").classes("text-primary")
                    ui.label("Netlist Configuration").classes("text-lg font-bold text-fg")
                ui.label(
                    "This is the expanded netlist that will actually be sent to the simulator. "
                    "It uses the same repeat-expansion pipeline as the Schema Editor preview."
                ).classes("text-sm text-muted mb-3")
                with ui.element("div").classes(
                    "w-full max-h-[480px] overflow-auto rounded-lg border border-border bg-bg p-3"
                ):
                    ui.markdown(f"```python\n{displayed_netlist}\n```").classes("w-full")

            with section_card():
                had_selected_setup_entry = _has_selected_setup_entry(active_record_id)
                saved_setups = _ensure_builtin_saved_setups(active_record_id, active_record.name)
                saved_setup_by_id = {
                    str(setup.get("id")): setup
                    for setup in saved_setups
                    if setup.get("id") and setup.get("name")
                }
                saved_setup_options = {"": "Current (Unsaved)"}
                saved_setup_options.update(
                    {
                        setup_id: str(setup.get("name"))
                        for setup_id, setup in saved_setup_by_id.items()
                    }
                )
                selected_setup_id = _load_selected_setup_id(active_record_id)
                builtin_setup_ids = [
                    str(setup.get("id"))
                    for setup in saved_setups
                    if str(setup.get("saved_at")) == "builtin" and setup.get("id")
                ]
                default_builtin_setup_id = builtin_setup_ids[0] if builtin_setup_ids else ""
                if selected_setup_id not in saved_setup_options:
                    selected_setup_id = default_builtin_setup_id or ""
                elif not had_selected_setup_entry and default_builtin_setup_id:
                    selected_setup_id = default_builtin_setup_id
                _save_selected_setup_id(active_record_id, selected_setup_id)

                with ui.row().classes("w-full items-center justify-between mb-4"):
                    with ui.row().classes("items-center gap-2"):
                        ui.icon("settings", size="sm").classes("text-primary")
                        ui.label("Simulation Setup").classes("text-lg font-bold text-fg")
                    with ui.row().classes("items-center gap-2"):
                        saved_setup_select: Any = (
                            ui.select(
                                label="Saved Setup",
                                options=saved_setup_options,
                                value=selected_setup_id,
                            )
                            .props("dense outlined options-dense")
                            .classes("w-60")
                        )
                        _with_test_id(saved_setup_select, "simulation-saved-setup-select")
                        manage_setups_button = ui.button(
                            "Manage Setups",
                            icon="tune",
                        ).props("outline color=primary size=sm")
                        _with_test_id(manage_setups_button, "simulation-manage-setups-button")
                        save_setup_button = ui.button("Save", icon="save").props(
                            "outline color=primary size=sm"
                        )

                with ui.card().classes("w-full bg-elevated border border-border rounded-lg p-4"):
                    ui.label("Signal Frequency Sweep Range").classes(
                        "text-sm font-bold text-fg mb-2"
                    )
                    with ui.row().classes("w-full gap-4"):
                        start_input = ui.number("Start Freq (GHz)", value=1.0).classes("flex-grow")
                        stop_input = ui.number("Stop Freq (GHz)", value=10.0).classes("flex-grow")
                        points_input = ui.number("Points", value=1001, format="%.0f").classes(
                            "flex-grow"
                        )

                sweep_target_options = {
                    value_ref: (f"{value_ref} ({unit})" if str(unit).strip() else value_ref)
                    for value_ref, unit in sorted(sweep_target_unit_by_value_ref.items())
                }
                sweep_setup_defaults = _normalize_sweep_setup_payload(
                    None,
                    available_target_units=sweep_target_unit_by_value_ref,
                )
                sweep_axis_forms: list[dict[str, Any]] = []
                sweep_axes_container: Any = None
                sweep_mode_select: Any
                sweep_add_axis_button: Any
                with _with_test_id(
                    ui.card().classes(
                        "w-full bg-elevated border border-border rounded-lg p-4 mt-3"
                    ),
                    "simulation-sweep-setup-card",
                ):
                    ui.label("Parameter Sweeps").classes("text-sm font-bold text-fg mb-2")
                    with ui.row().classes("w-full gap-3 items-end flex-wrap"):
                        sweep_enabled_switch = ui.switch(
                            "Enable Sweep",
                            value=bool(sweep_setup_defaults["enabled"]),
                        )
                        sweep_mode_select = (
                            ui.select(
                                label="Sweep Mode",
                                options=_SWEEP_MODE_OPTIONS,
                                value=str(sweep_setup_defaults.get("mode", "cartesian")),
                            )
                            .props("dense outlined options-dense")
                            .classes("w-52")
                        )
                        sweep_add_axis_button = ui.button(
                            "Add Axis",
                            icon="add",
                        ).props("outline color=primary size=sm")
                        _with_test_id(sweep_add_axis_button, "simulation-sweep-add-axis-button")
                    sweep_hint_label = ui.label("").classes("text-xs text-muted mt-2")
                    sweep_axes_container = ui.column().classes("w-full gap-2 mt-2")

                def _default_sweep_target() -> str:
                    return next(iter(sweep_target_options), "")

                def _normalize_sweep_mode_value(value: Any) -> str:
                    mode = str(value or "cartesian").strip().lower()
                    if mode not in _SWEEP_MODE_OPTIONS:
                        return "cartesian"
                    return mode

                def _collect_sweep_setup_payload(*, notify_errors: bool) -> dict[str, Any] | None:
                    sweep_enabled = bool(sweep_enabled_switch.value)
                    axes_payload: list[dict[str, Any]] = []
                    for axis_idx, axis_form in enumerate(sweep_axis_forms, start=1):
                        target_select = axis_form["target_select"]
                        start_value = axis_form["start_input"].value
                        stop_value = axis_form["stop_input"].value
                        points_value = axis_form["points_input"].value
                        target_value_ref = str(target_select.value or "").strip()
                        if not target_value_ref:
                            target_value_ref = _default_sweep_target()
                        if sweep_enabled and target_value_ref not in sweep_target_options:
                            if notify_errors:
                                ui.notify(
                                    f"Sweep axis {axis_idx} target is invalid.",
                                    type="warning",
                                )
                            return None
                        if sweep_enabled and (
                            start_value is None or stop_value is None or points_value is None
                        ):
                            if notify_errors:
                                ui.notify(
                                    (
                                        f"Sweep axis {axis_idx} requires "
                                        "start/stop/points when sweep is enabled."
                                    ),
                                    type="warning",
                                )
                            return None
                        axis_points = max(1, int(points_value or 11))
                        if sweep_enabled and axis_points < 1:
                            if notify_errors:
                                ui.notify("Sweep points must be >= 1.", type="warning")
                            return None
                        axes_payload.append(
                            {
                                "target_value_ref": target_value_ref,
                                "start": float(start_value or 0.0),
                                "stop": float(
                                    stop_value if stop_value is not None else (start_value or 0.0)
                                ),
                                "points": axis_points,
                                "unit": str(
                                    sweep_target_unit_by_value_ref.get(
                                        target_value_ref,
                                        "",
                                    )
                                ),
                            }
                        )

                    if not axes_payload:
                        axes_payload = [_default_sweep_axis_payload()]
                    if sweep_enabled:
                        dedup_targets = [
                            str(axis["target_value_ref"]).strip() for axis in axes_payload
                        ]
                        if len(set(dedup_targets)) != len(dedup_targets):
                            if notify_errors:
                                ui.notify(
                                    "Each sweep axis target must be unique.",
                                    type="warning",
                                )
                            return None
                    normalized = _normalize_sweep_setup_payload(
                        {
                            "enabled": sweep_enabled,
                            "mode": _normalize_sweep_mode_value(sweep_mode_select.value),
                            "axes": axes_payload,
                        },
                        available_target_units=sweep_target_unit_by_value_ref,
                    )
                    return normalized

                def _reindex_sweep_axis_forms() -> None:
                    has_multiple_axes = len(sweep_axis_forms) > 1
                    for axis_idx, axis_form in enumerate(sweep_axis_forms, start=1):
                        axis_form["title"].text = f"Sweep Axis {axis_idx}"
                        axis_form["remove_button"].enabled = has_multiple_axes

                def refresh_sweep_controls() -> None:
                    has_targets = bool(sweep_target_options)
                    if not has_targets:
                        sweep_enabled_switch.value = False
                        sweep_enabled_switch.disable()
                    else:
                        sweep_enabled_switch.enable()

                    sweep_mode_select.value = _normalize_sweep_mode_value(sweep_mode_select.value)
                    if bool(sweep_enabled_switch.value) and has_targets:
                        sweep_mode_select.enable()
                    else:
                        sweep_mode_select.disable()

                    if bool(sweep_enabled_switch.value) and has_targets:
                        sweep_add_axis_button.enable()
                    else:
                        sweep_add_axis_button.disable()

                    for axis_form in sweep_axis_forms:
                        target_select = axis_form["target_select"]
                        target_select.options = dict(sweep_target_options)
                        target_value_ref = str(target_select.value or "").strip()
                        if has_targets and target_value_ref not in sweep_target_options:
                            target_value_ref = _default_sweep_target()
                            target_select.value = target_value_ref
                        unit_label = axis_form["unit_label"]
                        unit_hint = str(
                            sweep_target_unit_by_value_ref.get(target_value_ref, "")
                        ).strip()
                        unit_label.text = f"Unit: {unit_hint or '-'}"
                        controls = [
                            target_select,
                            axis_form["start_input"],
                            axis_form["stop_input"],
                            axis_form["points_input"],
                        ]
                        if bool(sweep_enabled_switch.value) and has_targets:
                            for control in controls:
                                control.enable()
                        else:
                            for control in controls:
                                control.disable()

                    _reindex_sweep_axis_forms()
                    normalized_payload = _collect_sweep_setup_payload(notify_errors=False)
                    if not has_targets:
                        sweep_hint_label.text = "No sweepable targets in current schema/setup."
                        return
                    if normalized_payload is None:
                        sweep_hint_label.text = "Sweep axes are invalid; fix inputs before run."
                        return
                    total_points = _estimate_sweep_cartesian_point_count(
                        list(normalized_payload.get("axes", []))
                    )
                    axis_count = len(list(normalized_payload.get("axes", [])))
                    if bool(normalized_payload.get("enabled", False)):
                        mode_value = str(normalized_payload.get("mode", "cartesian"))
                        if mode_value == "cartesian" and total_points > _SWEEP_MAX_CARTESIAN_POINTS:
                            sweep_hint_label.text = (
                                f"Warning: total Cartesian points = {total_points} "
                                f"(limit {_SWEEP_MAX_CARTESIAN_POINTS}). "
                                "Run is blocked until points are reduced."
                            )
                        else:
                            sweep_hint_label.text = (
                                f"Enabled | mode={mode_value} | axes={axis_count} | "
                                f"total points={total_points} | "
                                "targets from netlist value_ref + source fields."
                            )
                    else:
                        sweep_hint_label.text = (
                            "Sweep disabled. Configure axes now; run path stays single-run."
                        )

                def add_sweep_axis_form(
                    initial: Mapping[str, Any] | None = None,
                    *,
                    refresh_after: bool = True,
                ) -> None:
                    if len(sweep_axis_forms) >= _SWEEP_MAX_AXIS_COUNT:
                        ui.notify(
                            f"At most {_SWEEP_MAX_AXIS_COUNT} sweep axes are supported.",
                            type="warning",
                        )
                        return
                    initial_axis = (
                        dict(initial)
                        if isinstance(initial, Mapping)
                        else _default_sweep_axis_payload()
                    )
                    target_value_ref = str(initial_axis.get("target_value_ref", "")).strip()
                    if target_value_ref not in sweep_target_options:
                        target_value_ref = _default_sweep_target()
                    with (
                        sweep_axes_container,
                        ui.card().classes(
                            "w-full bg-bg border border-border rounded-lg p-3"
                        ) as axis_card,
                    ):
                        with ui.row().classes("w-full items-center justify-between mb-2"):
                            title_label = ui.label("Sweep Axis").classes(
                                "text-sm font-bold text-fg"
                            )
                            remove_button = ui.button(
                                icon="delete",
                                on_click=lambda card=axis_card: remove_sweep_axis_form(card),
                            ).props("flat dense round color=negative")
                        with ui.row().classes("w-full gap-3 items-end flex-wrap"):
                            target_select = (
                                ui.select(
                                    label="Sweep Target",
                                    options=dict(sweep_target_options),
                                    value=(target_value_ref or None),
                                )
                                .props("dense outlined options-dense")
                                .classes("min-w-[320px]")
                            )
                            _with_test_id(target_select, "simulation-sweep-target-select")
                            start_axis_input = ui.number(
                                "Sweep Start",
                                value=float(initial_axis.get("start", 0.0)),
                                format="%.6g",
                            ).classes("w-40")
                            stop_axis_input = ui.number(
                                "Sweep Stop",
                                value=float(
                                    initial_axis.get(
                                        "stop",
                                        initial_axis.get("start", 0.0),
                                    )
                                ),
                                format="%.6g",
                            ).classes("w-40")
                            points_axis_input = ui.number(
                                "Sweep Points",
                                value=int(initial_axis.get("points", 11)),
                                format="%.0f",
                            ).classes("w-40")
                        unit_label = ui.label("").classes("text-xs text-muted mt-2")

                    sweep_axis_forms.append(
                        {
                            "card": axis_card,
                            "title": title_label,
                            "remove_button": remove_button,
                            "target_select": target_select,
                            "start_input": start_axis_input,
                            "stop_input": stop_axis_input,
                            "points_input": points_axis_input,
                            "unit_label": unit_label,
                        }
                    )
                    target_select.on_value_change(lambda _e: refresh_sweep_controls())
                    if refresh_after:
                        refresh_sweep_controls()

                def set_sweep_axis_forms(axis_payloads: list[Mapping[str, Any]]) -> None:
                    for axis_form in list(sweep_axis_forms):
                        axis_card = axis_form["card"]
                        axis_card.delete()
                    sweep_axis_forms.clear()
                    input_payloads = axis_payloads[:_SWEEP_MAX_AXIS_COUNT] if axis_payloads else []
                    if not input_payloads:
                        input_payloads = [_default_sweep_axis_payload()]
                    for axis_payload in input_payloads:
                        add_sweep_axis_form(axis_payload, refresh_after=False)
                    refresh_sweep_controls()

                def remove_sweep_axis_form(axis_card: Any) -> None:
                    if len(sweep_axis_forms) <= 1:
                        ui.notify("At least one sweep axis card must remain.", type="warning")
                        return
                    for idx, axis_form in enumerate(sweep_axis_forms):
                        if axis_form["card"] is axis_card:
                            sweep_axis_forms.pop(idx)
                            axis_card.delete()
                            refresh_sweep_controls()
                            return

                sweep_enabled_switch.on_value_change(lambda _e: refresh_sweep_controls())
                sweep_mode_select.on_value_change(lambda _e: refresh_sweep_controls())
                sweep_add_axis_button.on_click(lambda _e: add_sweep_axis_form())
                set_sweep_axis_forms(list(sweep_setup_defaults.get("axes", [])))

                with ui.card().classes(
                    "w-full bg-elevated border border-border rounded-lg p-4 mt-3"
                ):
                    ui.label("HB Solve Setting").classes("text-sm font-bold text-fg mb-2")
                    with ui.row().classes("w-full gap-4"):
                        n_mod_input = ui.number(
                            "Nmodulation Harmonics",
                            value=10,
                            format="%.0f",
                        ).classes("flex-grow")
                        n_pump_input = ui.number(
                            "Npump Harmonics",
                            value=20,
                            format="%.0f",
                        ).classes("flex-grow")

                source_forms: list[dict[str, Any]] = []
                with ui.card().classes(
                    "w-full bg-elevated border border-border rounded-lg p-4 mt-3"
                ):
                    with ui.row().classes("w-full items-center justify-between"):
                        ui.label("Sources").classes("text-sm font-bold text-fg")
                        add_source_button = ui.button("Add Source", icon="add").props(
                            "outline color=primary size=sm"
                        )
                    sources_container = ui.column().classes("w-full gap-3 mt-3")
                applying_saved_setup = False
                suppress_saved_setup_select_callback = False

                def _collect_sources_for_sweep_targets() -> list[DriveSourceConfig]:
                    """Collect source snapshots used for sweep-target discovery."""
                    resolved_sources: list[DriveSourceConfig] = []
                    for source_index, source_form in enumerate(source_forms, start=1):
                        source_pump_freq_input = source_form["source_pump_freq_input"]
                        port_input = source_form["port_input"]
                        current_input = source_form["current_input"]
                        mode_input = source_form["mode_input"]
                        if (
                            source_pump_freq_input.value is None
                            or port_input.value is None
                            or current_input.value is None
                        ):
                            continue
                        try:
                            parsed_mode = _parse_source_mode_text(mode_input.value)
                        except ValueError:
                            parsed_mode = None
                        normalized_mode = _normalize_source_mode_components(
                            parsed_mode,
                            source_index=source_index - 1,
                            source_count=max(len(source_forms), 1),
                        )
                        resolved_sources.append(
                            DriveSourceConfig(
                                pump_freq_ghz=float(source_pump_freq_input.value),
                                port=int(port_input.value),
                                current_amp=float(current_input.value),
                                mode_components=normalized_mode,
                            )
                        )
                    return resolved_sources

                def refresh_sweep_target_options() -> None:
                    """Refresh sweep target options from current schema + source setup."""
                    source_snapshots = _collect_sources_for_sweep_targets()
                    config_hint: SimulationConfig | None = None
                    if source_snapshots:
                        first_source = source_snapshots[0]
                        config_hint = SimulationConfig(
                            pump_freq_ghz=float(first_source.pump_freq_ghz),
                            pump_current_amp=float(first_source.current_amp),
                            pump_port=int(first_source.port),
                            pump_mode_index=1,
                            sources=source_snapshots,
                        )
                    latest_units = _extract_sweep_target_units(
                        active_circuit_def,
                        config=config_hint,
                    )
                    sweep_target_unit_by_value_ref.clear()
                    sweep_target_unit_by_value_ref.update(latest_units)
                    sweep_target_options.clear()
                    sweep_target_options.update(
                        {
                            value_ref: (f"{value_ref} ({unit})" if str(unit).strip() else value_ref)
                            for value_ref, unit in sorted(latest_units.items())
                        }
                    )
                    refresh_sweep_controls()

                def normalize_source_mode_inputs() -> None:
                    for source_form in source_forms:
                        mode_input = source_form["mode_input"]
                        try:
                            parsed_mode = _parse_source_mode_text(mode_input.value)
                        except ValueError:
                            continue
                        normalized_text = _format_source_mode_text(parsed_mode)
                        if mode_input.value != normalized_text:
                            mode_input.value = normalized_text

                def refresh_source_forms() -> None:
                    has_multiple_sources = len(source_forms) > 1
                    for idx, source_form in enumerate(source_forms, start=1):
                        title = source_form["title"]
                        remove_button = source_form["remove_button"]
                        title.text = f"Source {idx}"
                        remove_button.enabled = has_multiple_sources
                    normalize_source_mode_inputs()
                    refresh_sweep_target_options()

                def remove_source_form(source_card: Any) -> None:
                    if len(source_forms) <= 1:
                        ui.notify("At least one source is required.", type="warning")
                        return

                    for idx, source_form in enumerate(source_forms):
                        card = source_form["card"]
                        if card is source_card:
                            source_forms.pop(idx)
                            card.delete()
                            refresh_source_forms()
                            return

                def add_source_form(initial: DriveSourceConfig | None = None) -> None:
                    if initial is None:
                        next_index = len(source_forms)
                        fallback_mode = [0] * (next_index + 1)
                        fallback_mode[next_index] = 1
                        source_defaults = DriveSourceConfig(mode_components=tuple(fallback_mode))
                    else:
                        source_defaults = initial
                    with (
                        sources_container,
                        ui.card().classes(
                            "w-full bg-elevated border border-border rounded-lg p-4"
                        ) as source_card,
                    ):
                        with ui.row().classes("w-full items-center justify-between mb-2"):
                            title_label = ui.label("").classes("text-sm font-bold text-fg")
                            remove_button = ui.button(
                                icon="delete",
                                on_click=lambda card=source_card: remove_source_form(card),
                            ).props("flat dense round color=negative")

                        with ui.row().classes("w-full gap-4"):
                            source_pump_freq_input = ui.number(
                                "Pump Freq (GHz)",
                                value=float(source_defaults.pump_freq_ghz),
                            ).classes("flex-grow")
                            port_input = ui.number(
                                "Source Port",
                                value=int(source_defaults.port),
                                format="%.0f",
                            ).classes("flex-grow")
                            current_input = ui.number(
                                "Source Current Ip (A)",
                                value=float(source_defaults.current_amp),
                            ).classes("flex-grow")
                            mode_input = ui.input(
                                "Source Mode",
                                value=_format_source_mode_text(source_defaults.mode_components),
                                placeholder="e.g. 1 or 0, 1",
                            ).classes("flex-grow")

                    source_forms.append(
                        {
                            "card": source_card,
                            "title": title_label,
                            "remove_button": remove_button,
                            "source_pump_freq_input": source_pump_freq_input,
                            "port_input": port_input,
                            "current_input": current_input,
                            "mode_input": mode_input,
                        }
                    )
                    refresh_source_forms()

                add_source_button.on_click(lambda _e: add_source_form())

                add_source_form(
                    DriveSourceConfig(
                        pump_freq_ghz=5.0,
                        port=1,
                        current_amp=0.0,
                        mode_components=(1,),
                    )
                )

                termination_state.selected_ports = list(available_setup_ports)
                termination_state.manual_resistance_ohm_by_port = {
                    int(port): _TERMINATION_DEFAULT_RESISTANCE_OHM for port in available_setup_ports
                }

                with _with_test_id(
                    ui.card().classes(
                        "w-full bg-elevated border border-border rounded-lg p-4 mt-4"
                    ),
                    "termination-compensation-card",
                ):
                    ui.label("Port Termination Compensation").classes(
                        "text-sm font-bold text-fg mb-2"
                    )
                    with ui.row().classes("w-full items-end gap-3 flex-wrap"):
                        termination_enabled_switch = ui.switch(
                            "Enable",
                            value=bool(termination_state.enabled),
                        )
                        _with_test_id(termination_enabled_switch, "termination-enabled-switch")
                        termination_mode_select = (
                            ui.select(
                                label="Mode",
                                options=_TERMINATION_MODE_OPTIONS,
                                value=str(termination_state.mode),
                            )
                            .props("dense outlined options-dense")
                            .classes("w-56")
                        )
                        _with_test_id(termination_mode_select, "termination-mode-select")
                        termination_ports_select = (
                            ui.select(
                                label="Compensate Ports",
                                options={port: str(port) for port in available_setup_ports},
                                value=list(termination_state.selected_ports),
                                multiple=True,
                            )
                            .props("dense outlined options-dense use-chips")
                            .classes("w-64")
                        )
                        _with_test_id(termination_ports_select, "termination-ports-select")
                        termination_reset_button = (
                            ui.button(
                                "Reset Manual to 50 Ohm",
                                icon="restart_alt",
                            )
                            .props("outline color=primary size=sm")
                            .classes("shrink-0")
                        )
                        _with_test_id(termination_reset_button, "termination-reset-button")
                    termination_summary_label = ui.label("").classes("text-xs text-muted mt-2")
                    termination_details_container = ui.column().classes("w-full gap-1 mt-2")

                termination_view_elements.enabled_switch = termination_enabled_switch
                termination_view_elements.mode_select = termination_mode_select
                termination_view_elements.ports_select = termination_ports_select
                termination_view_elements.reset_button = termination_reset_button
                termination_view_elements.summary_label = termination_summary_label
                termination_view_elements.details_container = termination_details_container

                refreshing_termination_controls = False

                def refresh_termination_controls() -> None:
                    nonlocal refreshing_termination_controls
                    enabled_switch = termination_view_elements.enabled_switch
                    mode_select = termination_view_elements.mode_select
                    ports_select = termination_view_elements.ports_select
                    reset_button = termination_view_elements.reset_button
                    summary_label = termination_view_elements.summary_label
                    details_container = termination_view_elements.details_container
                    if (
                        enabled_switch is None
                        or mode_select is None
                        or ports_select is None
                        or reset_button is None
                        or summary_label is None
                        or details_container is None
                    ):
                        return

                    if refreshing_termination_controls:
                        return

                    refreshing_termination_controls = True
                    try:
                        normalized_mode = _normalize_termination_mode(mode_select.value)
                        if mode_select.value != normalized_mode:
                            mode_select.value = normalized_mode
                        selected_ports = _normalize_termination_selected_ports(
                            ports_select.value,
                            available_ports=available_setup_ports,
                        )
                        if enabled_switch.value and not selected_ports and available_setup_ports:
                            selected_ports = [available_setup_ports[0]]
                        if list(ports_select.value or []) != selected_ports:
                            ports_select.value = selected_ports

                        normalized_manual_map = _normalize_manual_termination_resistance_map(
                            termination_state.manual_resistance_ohm_by_port,
                            available_ports=available_setup_ports,
                            default_ohm=_TERMINATION_DEFAULT_RESISTANCE_OHM,
                        )
                        termination_state.enabled = bool(enabled_switch.value)
                        termination_state.mode = normalized_mode
                        termination_state.selected_ports = list(selected_ports)
                        termination_state.manual_resistance_ohm_by_port = normalized_manual_map

                        resolved_plan = _resolved_termination_plan()
                        summary_label.text = _termination_plan_summary(resolved_plan)
                        if normalized_mode == "manual":
                            reset_button.enable()
                        else:
                            reset_button.disable()

                        details_container.clear()
                        with details_container:
                            if not bool(resolved_plan.get("enabled", False)):
                                ui.label("Disabled: raw solver output is used directly.").classes(
                                    "text-xs text-muted"
                                )
                                return

                            selected = [int(port) for port in resolved_plan.get("selected_ports", [])]
                            resolved_values = dict(resolved_plan.get("resistance_ohm_by_port", {}))
                            source_values = dict(resolved_plan.get("source_by_port", {}))
                            for port in selected:
                                source = str(source_values.get(port, "manual"))
                                resistance = float(
                                    resolved_values.get(port, _TERMINATION_DEFAULT_RESISTANCE_OHM)
                                )
                                if normalized_mode == "manual":
                                    row_label = f"Port {port} · Manual R (Ohm)"
                                    manual_input = (
                                        ui.number(
                                            row_label,
                                            value=float(
                                                normalized_manual_map.get(
                                                    port,
                                                    _TERMINATION_DEFAULT_RESISTANCE_OHM,
                                                )
                                            ),
                                            format="%.6g",
                                        )
                                        .props("dense outlined")
                                        .classes("w-56")
                                    )

                                    def _on_manual_change(
                                        e: Any,
                                        *,
                                        target_port: int,
                                    ) -> None:
                                        if refreshing_termination_controls:
                                            return
                                        manual_map = dict(
                                            termination_state.manual_resistance_ohm_by_port
                                        )
                                        try:
                                            value = float(e.value)
                                        except Exception:
                                            value = _TERMINATION_DEFAULT_RESISTANCE_OHM
                                        manual_map[target_port] = value
                                        termination_state.manual_resistance_ohm_by_port = manual_map
                                        if not applying_saved_setup:
                                            on_termination_setup_change()
                                        else:
                                            refresh_termination_controls()

                                    manual_input.on_value_change(
                                        lambda e, target_port=port: _on_manual_change(
                                            e,
                                            target_port=target_port,
                                        )
                                    )
                                    ui.label(f"Resolved: {resistance:g} Ohm ({source})").classes(
                                        "text-xs text-muted"
                                    )
                                else:
                                    ui.label(f"Port {port}: {resistance:g} Ohm ({source})").classes(
                                        "text-xs text-fg"
                                    )

                            for warning in list(resolved_plan.get("warnings", [])):
                                ui.label(str(warning)).classes("text-xs text-warning")
                    finally:
                        refreshing_termination_controls = False

                def on_termination_setup_change() -> None:
                    if refreshing_termination_controls:
                        return
                    refresh_termination_controls()
                    if applying_saved_setup:
                        return
                    resolved_plan = _resolved_termination_plan()
                    summary_text = _termination_plan_summary(resolved_plan)
                    warning_text = "\n".join(
                        str(warning) for warning in resolved_plan.get("warnings", [])
                    )
                    page_coordinator.set_termination_summary(
                        summary=summary_text,
                        warning=warning_text,
                    )
                    current_family = str(raw_view_state.get("family", ""))
                    family_sources = raw_view_state.get("family_sources", {})
                    current_source_token = (
                        str(family_sources.get(current_family, "raw"))
                        if isinstance(family_sources, Mapping)
                        else "raw"
                    )
                    _persisted_result, persisted_sweep_payload, _persisted_bundle_id = (
                        _persisted_post_processing_input_bundle()
                    )
                    should_refresh_simulation_preview = bool(
                        isinstance(_coerce_parameter_sweep_payload(persisted_sweep_payload), Mapping)
                        or (
                            isinstance(_persisted_result, SimulationResult)
                            and current_family in _RAW_RESULT_MATRIX_SOURCE_OPTIONS_BY_FAMILY
                            and current_source_token == "ptc"
                        )
                    )
                    should_refresh_post_processing_input = (
                        str(post_processing_input_state.get("input_y_source", "raw_y")).strip()
                        == "ptc_y"
                    )
                    page_coordinator.mark_setup_changed(
                        reason=(
                            "Simulation setup changed after post-processing results were generated. "
                            "Re-run post-processing to refresh processed results."
                        ),
                        refresh_simulation_preview=should_refresh_simulation_preview,
                        refresh_post_processing_input=should_refresh_post_processing_input,
                    )
                    if page_coordinator.consume_simulation_preview_refresh():
                        render_simulation_result_view()
                    if page_coordinator.consume_post_processing_input_refresh():
                        _render_post_processing_input_panel()
                    if runtime_state.current_post_processing_task_id is not None or (
                        runtime_state.current_post_processing_trace_batch_id is not None
                    ):
                        _render_post_processed_sweep_result_view()
                        render_post_processed_result_view()
                    if runtime_state.termination_last_summary != summary_text:
                        runtime_state.termination_last_summary = summary_text
                        append_status(
                            "info",
                            (
                                "Termination compensation updated without Julia rerun. "
                                f"{summary_text}"
                            ),
                        )

                termination_enabled_switch.on_value_change(lambda _e: on_termination_setup_change())
                termination_mode_select.on_value_change(lambda _e: on_termination_setup_change())
                termination_ports_select.on_value_change(lambda _e: on_termination_setup_change())

                def on_reset_termination_manual_defaults() -> None:
                    manual_map = _normalize_manual_termination_resistance_map(
                        termination_state.manual_resistance_ohm_by_port,
                        available_ports=available_setup_ports,
                        default_ohm=_TERMINATION_DEFAULT_RESISTANCE_OHM,
                    )
                    selected_ports = _normalize_termination_selected_ports(
                        termination_state.selected_ports,
                        available_ports=available_setup_ports,
                    )
                    for port in selected_ports:
                        manual_map[port] = _TERMINATION_DEFAULT_RESISTANCE_OHM
                    termination_state.manual_resistance_ohm_by_port = manual_map
                    on_termination_setup_change()

                termination_reset_button.on_click(lambda _e: on_reset_termination_manual_defaults())
                refresh_termination_controls()

                def collect_current_setup_payload() -> dict[str, Any] | None:
                    required_values = [
                        start_input.value,
                        stop_input.value,
                        points_input.value,
                        n_mod_input.value,
                        n_pump_input.value,
                    ]
                    if any(value is None for value in required_values):
                        ui.notify("Please fill all simulation parameters first.", type="warning")
                        return None

                    setup_sources: list[dict[str, float | int]] = []
                    for idx, source_form in enumerate(source_forms, start=1):
                        source_pump_freq_input = source_form["source_pump_freq_input"]
                        port_input = source_form["port_input"]
                        current_input = source_form["current_input"]
                        mode_input = source_form["mode_input"]

                        if (
                            source_pump_freq_input.value is None
                            or port_input.value is None
                            or current_input.value is None
                        ):
                            ui.notify(f"Source {idx} has missing parameters.", type="warning")
                            return None

                        try:
                            parsed_mode = _parse_source_mode_text(mode_input.value)
                        except ValueError:
                            ui.notify(
                                (
                                    f"Source {idx} has an invalid mode tuple. "
                                    "Use comma-separated integers, for example 0 or 1, 0."
                                ),
                                type="warning",
                            )
                            return None

                        normalized_mode = _normalize_source_mode_components(
                            parsed_mode,
                            source_index=idx - 1,
                            source_count=len(source_forms),
                        )
                        persisted_mode = (
                            _compress_source_mode_components(parsed_mode)
                            if parsed_mode is not None
                            else _compress_source_mode_components(normalized_mode)
                        )

                        setup_sources.append(
                            _build_source_payload(
                                pump_freq_ghz=float(source_pump_freq_input.value),
                                port=int(port_input.value),
                                current_amp=float(current_input.value),
                                mode=persisted_mode,
                            )
                        )

                    sweep_payload = _collect_sweep_setup_payload(notify_errors=True)
                    if sweep_payload is None:
                        return None

                    return {
                        "freq_range": {
                            "start_ghz": float(start_input.value),
                            "stop_ghz": float(stop_input.value),
                            "points": int(points_input.value),
                        },
                        "harmonics": {
                            "n_modulation_harmonics": int(n_mod_input.value),
                            "n_pump_harmonics": int(n_pump_input.value),
                        },
                        "sources": setup_sources,
                        "advanced": {
                            "include_dc": bool(include_dc_switch.value),
                            "enable_three_wave_mixing": bool(three_wave_switch.value),
                            "enable_four_wave_mixing": bool(four_wave_switch.value),
                            "max_intermod_order": int(max_intermod_input.value),
                            "max_iterations": int(max_iterations_input.value),
                            "f_tol": float(ftol_input.value),
                            "line_search_switch_tol": float(linesearch_tol_input.value),
                            "alpha_min": float(alpha_min_input.value),
                        },
                        "termination_compensation": {
                            "enabled": bool(termination_state.enabled),
                            "mode": _normalize_termination_mode(termination_state.mode),
                            "selected_ports": _normalize_termination_selected_ports(
                                termination_state.selected_ports,
                                available_ports=available_setup_ports,
                            ),
                            "manual_resistance_ohm_by_port": {
                                str(port): float(value)
                                for port, value in _normalize_manual_termination_resistance_map(
                                    termination_state.manual_resistance_ohm_by_port,
                                    available_ports=available_setup_ports,
                                    default_ohm=_TERMINATION_DEFAULT_RESISTANCE_OHM,
                                ).items()
                            },
                        },
                        "sweep": sweep_payload,
                    }

                def apply_saved_setup(setup_record: dict[str, Any]) -> None:
                    nonlocal applying_saved_setup
                    payload = setup_record.get("payload")
                    if not isinstance(payload, dict):
                        ui.notify("Selected setup payload is invalid.", type="warning")
                        return

                    freq_payload = payload.get("freq_range", {})
                    harmonics_payload = payload.get("harmonics", {})
                    sources_payload = payload.get("sources", [])
                    advanced_payload = payload.get("advanced", {})
                    termination_payload = payload.get("termination_compensation", {})
                    sweep_payload = _normalize_sweep_setup_payload(
                        payload.get("sweep") if isinstance(payload.get("sweep"), Mapping) else None,
                        available_target_units=sweep_target_unit_by_value_ref,
                    )

                    applying_saved_setup = True
                    try:
                        start_input.value = float(freq_payload.get("start_ghz", 1.0))
                        stop_input.value = float(freq_payload.get("stop_ghz", 10.0))
                        points_input.value = int(freq_payload.get("points", 1001))
                        n_mod_input.value = int(harmonics_payload.get("n_modulation_harmonics", 10))
                        n_pump_input.value = int(harmonics_payload.get("n_pump_harmonics", 20))
                        include_dc_switch.value = bool(advanced_payload.get("include_dc", False))
                        three_wave_switch.value = bool(
                            advanced_payload.get("enable_three_wave_mixing", False)
                        )
                        four_wave_switch.value = bool(
                            advanced_payload.get("enable_four_wave_mixing", True)
                        )
                        max_intermod_input.value = int(
                            advanced_payload.get("max_intermod_order", -1)
                        )
                        max_iterations_input.value = int(
                            advanced_payload.get("max_iterations", 1000)
                        )
                        ftol_input.value = float(advanced_payload.get("f_tol", 1e-8))
                        linesearch_tol_input.value = float(
                            advanced_payload.get("line_search_switch_tol", 1e-5)
                        )
                        alpha_min_input.value = float(advanced_payload.get("alpha_min", 1e-4))
                        sweep_enabled_switch.value = bool(sweep_payload.get("enabled", False))
                        sweep_mode_select.value = str(sweep_payload.get("mode", "cartesian"))
                        set_sweep_axis_forms(
                            [
                                axis
                                for axis in list(sweep_payload.get("axes", []))
                                if isinstance(axis, Mapping)
                            ]
                        )
                        refresh_sweep_controls()
                        termination_enabled = bool(
                            termination_payload.get("enabled", False)
                            if isinstance(termination_payload, dict)
                            else False
                        )
                        termination_mode = _normalize_termination_mode(
                            termination_payload.get("mode", "auto")
                            if isinstance(termination_payload, dict)
                            else "auto"
                        )
                        termination_selected_ports = _normalize_termination_selected_ports(
                            termination_payload.get("selected_ports", available_setup_ports)
                            if isinstance(termination_payload, dict)
                            else available_setup_ports,
                            available_ports=available_setup_ports,
                        )
                        termination_manual_map = _normalize_manual_termination_resistance_map(
                            termination_payload.get("manual_resistance_ohm_by_port", {})
                            if isinstance(termination_payload, dict)
                            else {},
                            available_ports=available_setup_ports,
                            default_ohm=_TERMINATION_DEFAULT_RESISTANCE_OHM,
                        )
                        termination_state.enabled = termination_enabled
                        termination_state.mode = termination_mode
                        termination_state.selected_ports = list(termination_selected_ports)
                        termination_state.manual_resistance_ohm_by_port = termination_manual_map
                        if termination_view_elements.enabled_switch is not None:
                            termination_view_elements.enabled_switch.value = termination_enabled
                        if termination_view_elements.mode_select is not None:
                            termination_view_elements.mode_select.value = termination_mode
                        if termination_view_elements.ports_select is not None:
                            termination_view_elements.ports_select.value = (
                                termination_selected_ports
                            )
                        refresh_termination_controls()

                        for source_form in list(source_forms):
                            source_card = source_form["card"]
                            source_card.delete()
                        source_forms.clear()

                        valid_sources = [
                            source
                            for source in sources_payload
                            if isinstance(source, dict)
                            and source.get("pump_freq_ghz") is not None
                            and source.get("port") is not None
                            and source.get("current_amp") is not None
                        ]
                        if not valid_sources:
                            valid_sources = [{"pump_freq_ghz": 5.0, "port": 1, "current_amp": 0.0}]

                        generated_mode_width = max(len(valid_sources), 1)
                        for source_index, source in enumerate(valid_sources, start=1):
                            raw_mode = source.get("mode")
                            try:
                                parsed_mode = _parse_source_mode_text(raw_mode)
                            except ValueError:
                                parsed_mode = None
                            display_mode = (
                                parsed_mode
                                if parsed_mode is not None
                                else _normalize_source_mode_components(
                                    None,
                                    source_index=source_index - 1,
                                    source_count=generated_mode_width,
                                )
                            )
                            add_source_form(
                                DriveSourceConfig(
                                    pump_freq_ghz=float(source["pump_freq_ghz"]),
                                    port=int(source["port"]),
                                    current_amp=float(source["current_amp"]),
                                    mode_components=display_mode,
                                )
                            )
                    finally:
                        applying_saved_setup = False

                def refresh_saved_setup_select(preferred_id: str | None = None) -> None:
                    nonlocal saved_setups, saved_setup_by_id
                    saved_setups = _ensure_builtin_saved_setups(
                        active_record_id,
                        active_record.name,
                    )
                    saved_setup_by_id = {
                        str(setup.get("id")): setup
                        for setup in saved_setups
                        if setup.get("id") and setup.get("name")
                    }
                    options = {"": "Current (Unsaved)"}
                    options.update(
                        {
                            setup_id: str(setup.get("name"))
                            for setup_id, setup in saved_setup_by_id.items()
                        }
                    )
                    saved_setup_select.options = options

                    current = preferred_id if preferred_id in options else saved_setup_select.value
                    if current not in options:
                        current = ""
                    saved_setup_select.value = current
                    _save_selected_setup_id(active_record_id, str(current))
                    if current and current in saved_setup_by_id:
                        apply_saved_setup(saved_setup_by_id[current])

                def on_saved_setup_change(e: Any) -> None:
                    if applying_saved_setup or suppress_saved_setup_select_callback:
                        return

                    setup_id = str(e.value or "")
                    if not setup_id:
                        _save_selected_setup_id(active_record_id, setup_id)
                        return

                    load_setup_by_id(setup_id, notify_loaded=True)

                def load_setup_by_id(setup_id: str, *, notify_loaded: bool) -> bool:
                    nonlocal suppress_saved_setup_select_callback
                    setup_record = saved_setup_by_id.get(str(setup_id))
                    if setup_record is None:
                        ui.notify("Saved setup not found.", type="warning")
                        return False
                    suppress_saved_setup_select_callback = True
                    try:
                        saved_setup_select.value = str(setup_id)
                    finally:
                        suppress_saved_setup_select_callback = False
                    _save_selected_setup_id(active_record_id, str(setup_id))
                    apply_saved_setup(setup_record)
                    on_termination_setup_change()
                    if notify_loaded:
                        ui.notify(f"Loaded setup: {setup_record.get('name')}", type="positive")
                    return True

                saved_setup_select.on_value_change(on_saved_setup_change)

                def on_manage_setups_click() -> None:
                    with ui.dialog() as dialog, ui.card().classes("w-full max-w-lg bg-surface p-4"):
                        ui.label("Manage Simulation Setups").classes(
                            "text-lg font-bold text-fg mb-3"
                        )
                        setup_options = {
                            setup_id: str(setup.get("name"))
                            for setup_id, setup in saved_setup_by_id.items()
                        }
                        if not setup_options:
                            ui.label("No saved setups yet. Use Add New / Save As first.").classes(
                                "text-sm text-muted mb-2"
                            )
                            manage_select = None
                        else:
                            default_manage_id = str(saved_setup_select.value or "")
                            if default_manage_id not in setup_options:
                                default_manage_id = next(iter(setup_options))
                            manage_select = (
                                ui.select(
                                    label="Saved Setup",
                                    options=setup_options,
                                    value=default_manage_id,
                                )
                                .props("dense outlined options-dense")
                                .classes("w-full")
                            )
                        rename_input = ui.input("Rename To", value="").classes("w-full mt-2")
                        save_as_name_input = ui.input(
                            "New Setup Name",
                            value=f"{active_record.name} Setup {len(saved_setups) + 1}",
                        ).classes("w-full")

                        def _selected_setup_id() -> str:
                            if manage_select is None:
                                return ""
                            return str(manage_select.value or "").strip()

                        def _refresh_manage_options(preferred_id: str | None = None) -> None:
                            nonlocal manage_select
                            if manage_select is None:
                                return
                            options = {
                                setup_id: str(setup.get("name"))
                                for setup_id, setup in saved_setup_by_id.items()
                            }
                            manage_select.options = options
                            if not options:
                                manage_select.value = None
                                rename_input.value = ""
                                return
                            next_id = (
                                preferred_id if preferred_id in options else _selected_setup_id()
                            )
                            if next_id not in options:
                                next_id = next(iter(options))
                            manage_select.value = next_id
                            selected = get_setup_by_id(saved_setups, next_id)
                            rename_input.value = str(selected.get("name", "")) if selected else ""

                        def _on_manage_select_change(_e: Any) -> None:
                            selected = get_setup_by_id(saved_setups, _selected_setup_id())
                            rename_input.value = str(selected.get("name", "")) if selected else ""

                        if manage_select is not None:
                            manage_select.on_value_change(_on_manage_select_change)
                            _on_manage_select_change(None)

                        def _on_load_click() -> None:
                            selected_id = _selected_setup_id()
                            if not selected_id:
                                ui.notify("Select one setup first.", type="warning")
                                return
                            if load_setup_by_id(selected_id, notify_loaded=True):
                                dialog.close()

                        def _on_add_new_click() -> None:
                            setup_name = str(save_as_name_input.value or "").strip()
                            payload = collect_current_setup_payload()
                            if payload is None:
                                return
                            try:
                                updated_setups, new_record = save_setup_as(
                                    saved_setups,
                                    name=setup_name,
                                    payload=payload,
                                )
                            except ValueError as exc:
                                ui.notify(str(exc), type="warning")
                                return
                            _save_saved_setups_for_schema(active_record_id, updated_setups)
                            refresh_saved_setup_select(preferred_id=str(new_record.get("id")))
                            _refresh_manage_options(preferred_id=str(new_record.get("id")))
                            ui.notify(f"Added setup: {new_record.get('name')}", type="positive")

                        def _on_save_as_click() -> None:
                            _on_add_new_click()

                        def _on_rename_click() -> None:
                            selected_id = _selected_setup_id()
                            if not selected_id:
                                ui.notify("Select one setup first.", type="warning")
                                return
                            selected = get_setup_by_id(saved_setups, selected_id)
                            if selected is None:
                                ui.notify("Saved setup not found.", type="warning")
                                return
                            if is_builtin_setup(selected):
                                ui.notify(
                                    "Built-in setups cannot be renamed. Use Save As instead.",
                                    type="warning",
                                )
                                return
                            try:
                                updated_setups, updated_record = rename_setup(
                                    saved_setups,
                                    setup_id=selected_id,
                                    new_name=str(rename_input.value or ""),
                                )
                            except ValueError as exc:
                                ui.notify(str(exc), type="warning")
                                return
                            _save_saved_setups_for_schema(active_record_id, updated_setups)
                            refresh_saved_setup_select(preferred_id=str(updated_record.get("id")))
                            _refresh_manage_options(preferred_id=str(updated_record.get("id")))
                            ui.notify(
                                f"Renamed setup: {updated_record.get('name')}",
                                type="positive",
                            )

                        def _on_delete_click() -> None:
                            selected_id = _selected_setup_id()
                            if not selected_id:
                                ui.notify("Select one setup first.", type="warning")
                                return
                            selected = get_setup_by_id(saved_setups, selected_id)
                            if selected is None:
                                ui.notify("Saved setup not found.", type="warning")
                                return
                            if is_builtin_setup(selected):
                                ui.notify(
                                    "Built-in setups cannot be deleted. Use Save As instead.",
                                    type="warning",
                                )
                                return
                            try:
                                updated_setups = delete_setup(
                                    saved_setups,
                                    setup_id=selected_id,
                                )
                            except ValueError as exc:
                                ui.notify(str(exc), type="warning")
                                return
                            _save_saved_setups_for_schema(active_record_id, updated_setups)
                            refresh_saved_setup_select(preferred_id="")
                            _refresh_manage_options()
                            ui.notify("Deleted setup.", type="positive")

                        with ui.row().classes("w-full justify-between gap-2 mt-4 flex-wrap"):
                            ui.button("Load", icon="download", on_click=_on_load_click).props(
                                "outline color=primary"
                            )
                            ui.button(
                                "Rename",
                                icon="drive_file_rename_outline",
                                on_click=_on_rename_click,
                            ).props("outline color=primary")
                            ui.button("Delete", icon="delete", on_click=_on_delete_click).props(
                                "outline color=negative"
                            )
                        with ui.row().classes("w-full justify-between gap-2 mt-2 flex-wrap"):
                            ui.button("Add New", icon="add", on_click=_on_add_new_click).props(
                                "outline color=primary"
                            )
                            ui.button("Save As", icon="save_as", on_click=_on_save_as_click).props(
                                "outline color=primary"
                            )
                            ui.button("Close", on_click=dialog.close).props("flat")

                    dialog.open()

                def on_save_setup_click() -> None:
                    with ui.dialog() as dialog, ui.card().classes("w-full max-w-md bg-surface p-4"):
                        ui.label("Save Simulation Setup").classes("text-lg font-bold text-fg mb-3")
                        default_name = f"{active_record.name} Setup {len(saved_setups) + 1}"
                        name_input = ui.input("Setup Name", value=default_name).classes("w-full")

                        def do_save() -> None:
                            setup_name = str(name_input.value or "").strip()
                            if not setup_name:
                                ui.notify("Setup name is required.", type="warning")
                                return

                            payload = collect_current_setup_payload()
                            if payload is None:
                                return

                            existing = next(
                                (s for s in saved_setups if str(s.get("name")) == setup_name),
                                None,
                            )
                            setup_id = (
                                str(existing.get("id"))
                                if existing is not None and existing.get("id")
                                else datetime.now().strftime("%Y%m%d%H%M%S%f")
                            )

                            setup_record = {
                                "id": setup_id,
                                "name": setup_name,
                                "saved_at": datetime.now().isoformat(),
                                "payload": payload,
                            }
                            updated_setups = [
                                s for s in saved_setups if str(s.get("id")) != setup_id
                            ]
                            updated_setups.append(setup_record)
                            _save_saved_setups_for_schema(active_record_id, updated_setups)
                            refresh_saved_setup_select(preferred_id=setup_id)
                            ui.notify(f"Saved setup: {setup_name}", type="positive")
                            dialog.close()

                        with ui.row().classes("w-full justify-end gap-2 mt-4"):
                            ui.button("Cancel", on_click=dialog.close).props("flat")
                            ui.button("Save", on_click=do_save).props("color=primary")

                    dialog.open()

                manage_setups_button.on("click", on_manage_setups_click)
                save_setup_button.on("click", on_save_setup_click)

                with (
                    ui.card().classes(
                        "w-full bg-elevated border border-border rounded-lg p-4 mt-3"
                    ),
                    ui.expansion("Advanced hbsolve Options").classes("w-full"),
                ):
                    with ui.row().classes("w-full gap-6 items-center"):
                        include_dc_switch = ui.switch("Include DC", value=False)
                        three_wave_switch = ui.switch("Enable 3-Wave Mixing", value=False)
                        four_wave_switch = ui.switch("Enable 4-Wave Mixing", value=True)
                    with ui.row().classes("w-full gap-4 mt-3"):
                        max_intermod_input = ui.number(
                            "Max Intermod Order (-1 = Inf)",
                            value=-1,
                            format="%.0f",
                        ).classes("flex-grow")
                        max_iterations_input = ui.number(
                            "Max Iterations",
                            value=1000,
                            format="%.0f",
                        ).classes("flex-grow")
                    with ui.row().classes("w-full gap-4 mt-3"):
                        ftol_input = ui.number("f_tol", value=1e-8).classes("flex-grow")
                        linesearch_tol_input = ui.number(
                            "Line Search Switch Tol",
                            value=1e-5,
                        ).classes("flex-grow")
                        alpha_min_input = ui.number("alpha_min", value=1e-4).classes("flex-grow")

                if selected_setup_id and selected_setup_id in saved_setup_by_id:
                    apply_saved_setup(saved_setup_by_id[selected_setup_id])
                    on_termination_setup_change()

                async def run_sim():
                    harmonic_grid_hits: list[tuple[int, int, float, int]] = []
                    try:
                        sim_button.disable()
                        sim_button.props("loading")
                        runtime_state.current_task_id = None
                        runtime_state.current_task_status = None
                        runtime_state.current_trace_batch_id = None
                        runtime_state.current_task_error = None
                        runtime_state.last_task_poll_signature = None
                        runtime_state.long_running_warning_shown = False
                        runtime_state.current_post_processing_task_id = None
                        runtime_state.current_post_processing_task_status = None
                        runtime_state.current_post_processing_trace_batch_id = None
                        runtime_state.current_post_processing_task_error = None
                        runtime_state.last_post_processing_task_poll_signature = None
                        runtime_state.post_processing_long_running_warning_shown = False
                        if post_processing_poll_timer is not None:
                            post_processing_poll_timer.active = False
                        _invalidate_persisted_authority_caches()
                        handle_post_processing_result(None)
                        simulation_results_container.clear()
                        if simulation_sweep_results_container is not None:
                            simulation_sweep_results_container.clear()
                        post_processing_container.clear()
                        post_processing_results_container.clear()
                        if post_processing_sweep_results_container is not None:
                            post_processing_sweep_results_container.clear()
                        with simulation_results_container:
                            ui.spinner(size="3em").classes("text-primary")
                            ui.label("Preparing simulation...").classes("text-muted mt-2")
                        if simulation_sweep_results_container is not None:
                            with simulation_sweep_results_container:
                                ui.label(
                                    "Sweep Result View will refresh after the current run."
                                ).classes("text-sm text-muted")
                        with post_processing_container:
                            ui.label(
                                "Post Processing will be available after simulation completes."
                            ).classes("text-sm text-muted")
                        with post_processing_results_container:
                            ui.label(
                                "Run Post Processing to populate post-processed output traces."
                            ).classes("text-sm text-muted")
                        if post_processing_sweep_results_container is not None:
                            with post_processing_sweep_results_container:
                                ui.label(
                                    "Post-processed sweep explorer will refresh after "
                                    "post-processing completes."
                                ).classes("text-sm text-muted")
                        await asyncio.sleep(0)
                        # Always fetch latest schema from DB at run-time.
                        latest_record, latest_circuit_def = await run.io_bound(
                            _load_latest_circuit_definition,
                            active_record_id,
                        )
                        latest_circuit_definition_ref["definition"] = latest_circuit_def

                        harmonic_grid_hits: list[Any] = []
                        source_rows = [
                            SourceFormPayload(
                                pump_freq_ghz=(
                                    float(source_form["source_pump_freq_input"].value)
                                    if source_form["source_pump_freq_input"].value is not None
                                    else None
                                ),
                                port=(
                                    int(source_form["port_input"].value)
                                    if source_form["port_input"].value is not None
                                    else None
                                ),
                                current_amp=(
                                    float(source_form["current_input"].value)
                                    if source_form["current_input"].value is not None
                                    else None
                                ),
                                mode_text=str(source_form["mode_input"].value or ""),
                            )
                            for source_form in source_forms
                        ]
                        raw_sweep_setup_payload = _collect_sweep_setup_payload(notify_errors=False)
                        try:
                            prepared_run: PreparedSimulationRun = prepare_simulation_run(
                                latest_record=latest_record,
                                latest_circuit_def=latest_circuit_def,
                                start_ghz=(
                                    float(start_input.value)
                                    if start_input.value is not None
                                    else None
                                ),
                                stop_ghz=(
                                    float(stop_input.value)
                                    if stop_input.value is not None
                                    else None
                                ),
                                points=(
                                    int(points_input.value)
                                    if points_input.value is not None
                                    else None
                                ),
                                n_modulation_harmonics=(
                                    int(n_mod_input.value) if n_mod_input.value is not None else None
                                ),
                                n_pump_harmonics=(
                                    int(n_pump_input.value)
                                    if n_pump_input.value is not None
                                    else None
                                ),
                                include_dc=bool(include_dc_switch.value),
                                enable_three_wave_mixing=bool(three_wave_switch.value),
                                enable_four_wave_mixing=bool(four_wave_switch.value),
                                max_intermod_order_raw=(
                                    int(max_intermod_input.value)
                                    if max_intermod_input.value is not None
                                    else None
                                ),
                                max_iterations=(
                                    int(max_iterations_input.value)
                                    if max_iterations_input.value is not None
                                    else None
                                ),
                                f_tol=(
                                    float(ftol_input.value) if ftol_input.value is not None else None
                                ),
                                line_search_switch_tol=(
                                    float(linesearch_tol_input.value)
                                    if linesearch_tol_input.value is not None
                                    else None
                                ),
                                alpha_min=(
                                    float(alpha_min_input.value)
                                    if alpha_min_input.value is not None
                                    else None
                                ),
                                source_rows=source_rows,
                                raw_sweep_setup_payload=raw_sweep_setup_payload,
                            )
                        except ValueError as exc:
                            message = str(exc)
                            reset_status()
                            append_status("warning", message)
                            ui.notify(_simulation_validation_notify_message(message), type="warning")
                            return
                        harmonic_grid_hits = list(prepared_run.harmonic_grid_hits)

                        simulation_run_id = f"sim-{uuid4().hex[:10]}"
                        runtime_state.set_log_context(
                            run_id=simulation_run_id,
                            circuit_id=latest_record.id,
                        )
                        reset_status("Simulation started.")
                        append_status(
                            "info",
                            (
                                f"Sweep: {prepared_run.freq_range.start_ghz:.3f} to "
                                f"{prepared_run.freq_range.stop_ghz:.3f} GHz, "
                                f"{prepared_run.freq_range.points} points."
                            ),
                        )
                        for warning in prepared_run.warnings:
                            append_status("warning", warning)
                        if prepared_run.sweep_plan is not None:
                            axis_tokens = "; ".join(
                                (
                                    f"{axis.target_value_ref}[{len(axis.values)}]"
                                    f"{(' ' + axis.unit) if str(axis.unit).strip() else ''}"
                                )
                                for axis in prepared_run.sweep_plan.axes
                            )
                            append_status(
                                "info",
                                (
                                    "Parameter sweep enabled: "
                                    f"mode={prepared_run.sweep_mode}, "
                                    f"dim={prepared_run.sweep_plan.dimension}, "
                                    f"points={prepared_run.sweep_plan.point_count}, "
                                    f"axes={axis_tokens}."
                                ),
                            )
                        append_status(
                            "info",
                            (
                                f"Loaded latest schema: {latest_record.name} "
                                f"(id={latest_record.id})."
                            ),
                        )
                        append_status(
                            "info",
                            (
                                f"Configured {len(prepared_run.sources)} source(s). "
                                "Each source has independent pump frequency."
                            ),
                        )
                        for source_idx, source in enumerate(prepared_run.sources, start=1):
                            mode_label = (
                                str(source.mode_components)
                                if source.mode_components is not None
                                else "auto"
                            )
                            append_status(
                                "info",
                                (
                                    f"S{source_idx}: fp={source.pump_freq_ghz:.5f} GHz, "
                                    f"port={source.port}, mode={mode_label}, "
                                    f"Ip={source.current_amp:.3e} A."
                                ),
                            )
                        append_status(
                            "info",
                            (
                                f"Harmonics: Nmod={prepared_run.config.n_modulation_harmonics}, "
                                f"Npump={prepared_run.config.n_pump_harmonics}, "
                                f"DC={prepared_run.config.include_dc}, "
                                f"3WM={prepared_run.config.enable_three_wave_mixing}, "
                                f"4WM={prepared_run.config.enable_four_wave_mixing}."
                            ),
                        )
                        if all(
                            abs(source.current_amp) < 1e-18 for source in prepared_run.sources
                        ):
                            append_status(
                                "info",
                                "All source currents are zero (Ip=0, linear drive case).",
                            )
                        if harmonic_grid_hits:
                            append_status(
                                "warning",
                                _format_harmonic_grid_hint(harmonic_grid_hits),
                            )
                        if prepared_run.estimated_mode_lattice >= 128:
                            append_status(
                                "warning",
                                _format_mode_lattice_hint(
                                    prepared_run.sources,
                                    prepared_run.config.n_modulation_harmonics,
                                ),
                            )
                        termination_plan = _resolved_termination_plan()
                        append_status("info", _termination_plan_summary(termination_plan))
                        for warning in list(termination_plan.get("warnings", [])):
                            append_status("warning", str(warning))
                        append_status("info", "Normalized simulation setup snapshot prepared.")
                        if (
                            prepared_run.sweep_plan is not None
                            and prepared_run.sweep_setup_hash is not None
                        ):
                            append_status(
                                "info",
                                f"Sweep setup hash: {prepared_run.sweep_setup_hash}",
                            )
                        append_status("info", "Submitting persisted simulation task...")
                        simulation_results_container.clear()
                        with simulation_results_container:
                            ui.spinner(size="3em").classes("text-primary")
                            ui.label("Queueing simulation task...").classes("text-muted mt-2")
                        await asyncio.sleep(0)
                        runtime_state.set_log_context(
                            run_id=simulation_run_id,
                            circuit_id=latest_record.id,
                        )
                        append_status(
                            "info",
                            (
                                "Canonical execution path is now worker-backed. "
                                "NiceGUI only queues the persisted task and polls status."
                            ),
                        )
                        if simulation_sweep_results_container is not None:
                            simulation_sweep_results_container.clear()
                            with simulation_sweep_results_container:
                                ui.label(
                                    "Sweep Result View is waiting for persisted worker output."
                                ).classes("text-sm text-muted")
                        post_processing_container.clear()
                        with post_processing_container:
                            ui.label("Waiting for persisted simulation output...").classes(
                                "text-sm text-muted"
                            )
                        with post_processing_results_container:
                            ui.label(
                                "Post-processed results will refresh from persisted batches."
                            ).classes("text-sm text-muted")
                        if post_processing_sweep_results_container is not None:
                            post_processing_sweep_results_container.clear()
                            with post_processing_sweep_results_container:
                                ui.label(
                                    "Post-processed sweep explorer is waiting for persisted output."
                                ).classes("text-sm text-muted")

                        persisted_design_id = _active_persisted_design_id()
                        if persisted_design_id is None:
                            raise ValueError(
                                "Select at least one active dataset before running simulation."
                            )
                        if latest_record.id is None:
                            raise ValueError("Latest schema id is unavailable.")
                        dispatch = await submit_simulation_run(
                            prepared_run=prepared_run,
                            design_id=persisted_design_id,
                            latest_record=latest_record,
                            latest_circuit_def=latest_circuit_def,
                            simulation_run_id=simulation_run_id,
                            owner_client=owner_client,
                        )
                        runtime_state.current_task_id = int(dispatch.task.id)
                        runtime_state.current_task_status = str(dispatch.task.status)
                        runtime_state.current_trace_batch_id = dispatch.task.trace_batch_id
                        runtime_state.current_task_error = None
                        runtime_state.last_task_poll_signature = None
                        page_coordinator.record_simulation_dispatch(
                            task_id=int(dispatch.task.id) if dispatch.task.id is not None else None,
                            trace_batch_id=dispatch.task.trace_batch_id,
                        )
                        if poll_timer is not None:
                            poll_timer.active = True
                        _apply_polled_task_status(dispatch.task)
                        append_status(
                            "info",
                            (
                                f"Dispatched worker task '{dispatch.worker_task_name}' "
                                f"on lane '{dispatch.dispatched_lane}'."
                            ),
                        )
                        if dispatch.dedupe_hit:
                            append_status(
                                "info",
                                "Soft dedupe reused the active persisted simulation task.",
                            )
                        await _refresh_simulation_authority(preferred_task_id=int(dispatch.task.id))

                    except Exception as e:
                        summary, detail = _summarize_simulation_error(e)
                        if (
                            "Numerical solver error:" in summary
                            and "solver matrix became singular" in summary
                            and harmonic_grid_hits
                        ):
                            hint = _format_harmonic_grid_hint(harmonic_grid_hits)
                            append_status("warning", hint)
                            detail = f"{detail}\n\nLikely cause from current configuration:\n{hint}"
                        append_status("negative", summary)
                        runtime_state.current_task_error = summary
                        runtime_state.current_task_status = "failed"
                        runtime_state.long_running_warning_shown = False
                        runtime_state.current_post_processing_task_id = None
                        runtime_state.current_post_processing_task_status = None
                        runtime_state.current_post_processing_trace_batch_id = None
                        runtime_state.current_post_processing_task_error = None
                        runtime_state.last_post_processing_task_poll_signature = None
                        runtime_state.post_processing_long_running_warning_shown = False
                        if post_processing_poll_timer is not None:
                            post_processing_poll_timer.active = False
                        _invalidate_persisted_authority_caches()
                        handle_post_processing_result(None)
                        simulation_results_container.clear()
                        if simulation_sweep_results_container is not None:
                            simulation_sweep_results_container.clear()
                        post_processing_container.clear()
                        post_processing_results_container.clear()
                        if post_processing_sweep_results_container is not None:
                            post_processing_sweep_results_container.clear()
                        with post_processing_container:
                            ui.label(
                                "Post Processing is unavailable because simulation failed."
                            ).classes("text-sm text-muted")
                        with post_processing_results_container:
                            ui.label(
                                "Post Processing Result View is unavailable "
                                "because simulation failed."
                            ).classes("text-sm text-muted")
                        if post_processing_sweep_results_container is not None:
                            with post_processing_sweep_results_container:
                                ui.label(
                                    "Post-processed sweep explorer is unavailable "
                                    "because simulation failed."
                                ).classes("text-sm text-muted")
                        with simulation_results_container:
                            ui.icon("error", size="lg").classes("text-danger mb-2")
                            ui.label(summary).classes("text-danger text-sm")
                            with ui.expansion("Technical Details").classes("w-full mt-3"):
                                ui.label(detail).classes(
                                    "text-xs text-muted whitespace-pre-wrap break-all"
                                )
                        if simulation_sweep_results_container is not None:
                            with simulation_sweep_results_container:
                                ui.label(
                                    "Sweep Result View is unavailable because simulation failed."
                                ).classes("text-sm text-muted")
                    finally:
                        sim_button.enable()
                        sim_button.props(remove="loading")

                sim_button = (
                    ui.button("Run Simulation", on_click=run_sim, icon="play_arrow")
                    .props("color=primary")
                    .classes("w-full mt-4")
                )
                _with_test_id(sim_button, "simulation-run-button")

            with section_card():
                with ui.row().classes("items-center gap-2 mb-3"):
                    ui.icon("terminal", size="sm").classes("text-primary")
                    ui.label("Simulation Log").classes("text-lg font-bold text-fg")
                status_container = ui.column().classes("w-full gap-2")
                render_status()

            with _with_test_id(
                ui.card().classes("w-full bg-surface rounded-xl p-6 min-h-[360px]"),
                "simulation-results-card",
            ):
                with ui.row().classes("items-center gap-2 mb-4"):
                    ui.icon("bar_chart", size="sm").classes("text-primary")
                    ui.label("Simulation Results").classes("text-lg font-bold text-fg")

                simulation_results_container = ui.column().classes(
                    "w-full h-full flex items-center justify-center p-4"
                )
                with simulation_results_container:
                    ui.icon("show_chart", size="xl").classes("text-muted mb-4 opacity-50")
                    ui.label("Run simulation to inspect raw result families.").classes(
                        "text-sm text-muted mt-2"
                    )

            with _with_test_id(
                ui.card().classes("w-full bg-surface rounded-xl p-6"),
                "post-processing-card",
            ):
                with ui.row().classes("items-center gap-2 mb-3"):
                    ui.icon("tune", size="sm").classes("text-primary")
                    ui.label("Post Processing").classes("text-lg font-bold text-fg")
                post_processing_container = ui.column().classes("w-full gap-3")
                with post_processing_container:
                    ui.label(
                        "Run a simulation first, then apply port-level coordinate transforms "
                        "and Kron reduction here."
                    ).classes("text-sm text-muted")

            with _with_test_id(
                ui.card().classes("w-full bg-surface rounded-xl p-6 min-h-[320px]"),
                "post-processing-results-card",
            ):
                with ui.row().classes("items-center gap-2 mb-4"):
                    ui.icon("tune", size="sm").classes("text-primary")
                    ui.label("Post Processing Results").classes("text-lg font-bold text-fg")
                post_processing_results_container = ui.column().classes("w-full gap-4")
                with post_processing_results_container:
                    ui.icon("data_object", size="xl").classes("text-muted mb-4 opacity-50")
                    ui.label("Run Post Processing to view pipeline output traces.").classes(
                        "text-sm text-muted mt-2"
                    )

            poll_timer = ui.timer(
                2.0,
                callback=lambda: asyncio.create_task(_poll_current_simulation_task()),
                active=False,
            )
            post_processing_poll_timer = ui.timer(
                2.0,
                callback=lambda: asyncio.create_task(_poll_current_post_processing_task()),
                active=False,
            )
            ui.timer(
                0.2,
                callback=lambda: asyncio.create_task(_refresh_simulation_authority()),
                active=True,
                once=True,
            )

    sim_env()


def _save_simulation_results_dialog(
    circuit_record: CircuitRecord,
    freq_range: FrequencyRange,
    result: SimulationResult,
    *,
    setup_snapshot: dict[str, Any] | None = None,
    schema_source_hash: str | None = None,
    simulation_setup_hash: str | None = None,
    sweep_setup_hash: str | None = None,
    sweep_result_payload: dict[str, Any] | None = None,
):
    """Dialog for saving SimulationResult into DataRecords."""
    if isinstance(sweep_result_payload, Mapping) and is_trace_batch_bundle_payload(
        sweep_result_payload
    ):
        bundle_records = _build_trace_batch_data_records(
            dataset_id=0,
            trace_batch_payload=sweep_result_payload,
        )
        sweep_point_count = int(
            sweep_result_payload.get("trace_batch_record", {})
            .get("summary_payload", {})
            .get("point_count", 0)
            or 0
        )
    elif sweep_result_payload is not None:
        bundle_records = _build_sweep_result_bundle_data_records(
            dataset_id=0,
            sweep_payload=sweep_result_payload,
        )
        sweep_point_count = int(sweep_result_payload.get("point_count", 0) or 0)
    else:
        bundle_records = _build_result_bundle_data_records(dataset_id=0, result=result)
        sweep_point_count = 0
    bundle_trace_count = len(
        {
            (
                record.data_type,
                record.parameter,
            )
            for record in bundle_records
        }
    )

    with ui.dialog() as dialog, ui.card().classes("w-full max-w-lg bg-surface"):
        ui.label("Save Simulation Results").classes("text-xl font-bold mb-4")
        if sweep_result_payload is None:
            ui.label(
                "This saves the cached result bundle "
                f"({bundle_trace_count} trace(s), including sidebands / QE / CM when available)."
            ).classes("text-sm text-muted mb-3")
        else:
            ui.label(
                "This saves the cached parameter-sweep bundle "
                f"({bundle_trace_count} trace(s), "
                f"{sweep_point_count} sweep points)."
            ).classes("text-sm text-muted mb-3")

        try:
            with get_unit_of_work() as uow:
                datasets = uow.datasets.list_all()
        except Exception:
            datasets = []

        mode_options = ["Create New"]
        if datasets:
            mode_options.append("Append to Existing")

        mode_toggle = ui.toggle(mode_options, value="Create New").classes("mb-4")

        default_name = f"{circuit_record.name} Sim {datetime.now().strftime('%m%d_%H%M')}"
        name_input = (
            ui.input("New Dataset Name", value=default_name)
            .classes("w-full mb-4 text-lg")
            .props("outlined")
        ).bind_visibility_from(mode_toggle, "value", value="Create New")

        dataset_options = {d.id: d.name for d in datasets}

        dataset_select: Any = (
            ui.select(options=dataset_options, label="Select Existing Dataset")
            .classes("w-full mb-4")
            .props("outlined options-dense")
            .bind_visibility_from(mode_toggle, "value", value="Append to Existing")
        )

        def _save_to_dataset(
            mode: str,
            *,
            new_dataset_name: str,
            selected_dataset_id: int | None,
        ) -> str:
            """Persist the manual-export result bundle and return target dataset name."""
            with get_unit_of_work() as uow:
                if mode == "Create New":
                    ds = DatasetRecord(
                        name=new_dataset_name,
                        source_meta={
                            "origin": "circuit_simulation",
                            "circuit_id": circuit_record.id,
                            "circuit_name": circuit_record.name,
                        },
                        parameters={
                            "start_ghz": freq_range.start_ghz,
                            "stop_ghz": freq_range.stop_ghz,
                            "points": freq_range.points,
                        },
                    )
                    uow.datasets.add(ds)
                    uow.flush()
                    ds_id = ds.id
                    if ds_id is None:
                        raise ValueError("Failed to allocate a dataset id.")
                    ds_name = new_dataset_name
                else:
                    if selected_dataset_id is None:
                        raise ValueError("Please select an existing dataset.")
                    ds_id = selected_dataset_id
                    ds_name = dataset_options[ds_id]

                export_setup_snapshot = setup_snapshot or {
                    "freq_range": {
                        "start_ghz": float(freq_range.start_ghz),
                        "stop_ghz": float(freq_range.stop_ghz),
                        "points": int(freq_range.points),
                    }
                }
                _persist_simulation_result_bundle(
                    uow=uow,
                    dataset_id=ds_id,
                    result=result,
                    role="manual_export",
                    source_meta={
                        "origin": "circuit_simulation",
                        "export_kind": "manual",
                        "circuit_id": circuit_record.id,
                        "circuit_name": circuit_record.name,
                        "sweep_setup_hash": sweep_setup_hash,
                    },
                    config_snapshot=export_setup_snapshot,
                    schema_source_hash=schema_source_hash,
                    simulation_setup_hash=simulation_setup_hash,
                    result_payload=sweep_result_payload,
                )
                uow.commit()
                return ds_name

        async def save() -> None:
            mode = str(mode_toggle.value)
            name = name_input.value.strip()
            selected_dataset_id = (
                int(dataset_select.value) if isinstance(dataset_select.value, int) else None
            )

            if mode == "Create New" and not name:
                ui.notify("Dataset Name is required.", type="warning")
                return
            if mode != "Create New" and selected_dataset_id is None:
                ui.notify("Please select an existing dataset.", type="warning")
                return

            save_button.disable()
            cancel_button.disable()
            save_button.props(add="loading")
            await asyncio.sleep(0)

            try:
                ds_name = await run.io_bound(
                    _save_to_dataset,
                    mode,
                    new_dataset_name=name,
                    selected_dataset_id=selected_dataset_id,
                )
                ui.notify(
                    f"Saved {bundle_trace_count} trace(s) to: {ds_name}",
                    type="positive",
                )
                dialog.close()
            except Exception as e:
                if "UNIQUE constraint failed" in str(e):
                    ui.notify("A dataset with this name already exists.", type="negative")
                else:
                    ui.notify(f"Failed to save: {e}", type="negative")
            finally:
                save_button.props(remove="loading")
                save_button.enable()
                cancel_button.enable()

        with ui.row().classes("w-full justify-end mt-4 gap-2"):
            cancel_button = ui.button("Cancel", on_click=dialog.close).props("flat")
            save_button = ui.button("Save", on_click=save).props("color=primary")

    dialog.open()


def _save_post_processed_results_dialog(
    *,
    runtime_output: PortMatrixSweep | PortMatrixSweepRun | Mapping[str, Any],
    representative_sweep: PortMatrixSweep | None,
    flow_spec: dict[str, Any],
    circuit_record: CircuitRecord | None,
    source_simulation_bundle_id: int | None,
    source_sweep_payload: dict[str, Any] | None,
    schema_source_hash: str | None,
    simulation_setup_hash: str | None,
) -> None:
    """Dialog for saving one post-processed Y sweep into a result bundle."""
    resolved_representative_sweep = (
        runtime_output.representative_sweep
        if isinstance(runtime_output, PortMatrixSweepRun)
        else representative_sweep
        if isinstance(representative_sweep, PortMatrixSweep)
        else runtime_output
        if isinstance(runtime_output, PortMatrixSweep)
        else None
    )
    if not isinstance(resolved_representative_sweep, PortMatrixSweep):
        raise ValueError("Representative post-processed sweep is unavailable.")
    if isinstance(runtime_output, Mapping) and is_trace_batch_bundle_payload(runtime_output):
        bundle_records = _build_trace_batch_data_records(
            dataset_id=0,
            trace_batch_payload=runtime_output,
        )
    else:
        if not isinstance(runtime_output, (PortMatrixSweep, PortMatrixSweepRun)):
            raise ValueError("Post-processed runtime output is unavailable.")
        bundle_records = _build_post_processed_runtime_data_records(
            dataset_id=0,
            runtime_output=runtime_output,
        )
    bundle_trace_count = len(
        {
            (
                record.data_type,
                record.parameter,
            )
            for record in bundle_records
        }
    )

    with ui.dialog() as dialog, ui.card().classes("w-full max-w-lg bg-surface"):
        ui.label("Save Post-Processed Results").classes("text-xl font-bold mb-4")
        ui.label(
            "This saves the processed port-level Y bundle "
            "("
            f"{bundle_trace_count} trace(s), "
            f"mode={SimulationResult.mode_token(resolved_representative_sweep.mode)}"
            ")."
        ).classes("text-sm text-muted mb-3")

        try:
            with get_unit_of_work() as uow:
                datasets = uow.datasets.list_all()
        except Exception:
            datasets = []

        mode_options = ["Create New"]
        if datasets:
            mode_options.append("Append to Existing")

        mode_toggle = ui.toggle(mode_options, value="Create New").classes("mb-4")

        circuit_name = str(circuit_record.name) if circuit_record is not None else "Simulation"
        default_name = f"{circuit_name} Post {datetime.now().strftime('%m%d_%H%M')}"
        name_input = (
            ui.input("New Dataset Name", value=default_name)
            .classes("w-full mb-4 text-lg")
            .props("outlined")
        ).bind_visibility_from(mode_toggle, "value", value="Create New")

        dataset_options = {d.id: d.name for d in datasets}

        dataset_select: Any = (
            ui.select(options=dataset_options, label="Select Existing Dataset")
            .classes("w-full mb-4")
            .props("outlined options-dense")
            .bind_visibility_from(mode_toggle, "value", value="Append to Existing")
        )

        def _save_to_dataset(
            mode: str,
            *,
            new_dataset_name: str,
            selected_dataset_id: int | None,
        ) -> str:
            with get_unit_of_work() as uow:
                source_bundle_snapshot = (
                    uow.result_bundles.get_snapshot(source_simulation_bundle_id)
                    if source_simulation_bundle_id is not None
                    else None
                )
                bundle_source_meta, bundle_config_snapshot, bundle_provenance_payload = (
                    _build_post_processed_bundle_artifacts(
                        sweep=resolved_representative_sweep,
                        flow_spec=flow_spec,
                        source_simulation_bundle_id=source_simulation_bundle_id,
                        source_bundle_snapshot=source_bundle_snapshot,
                        source_sweep_payload=source_sweep_payload,
                    )
                )
                if mode == "Create New":
                    dataset = DatasetRecord(
                        name=new_dataset_name,
                        source_meta={
                            **bundle_source_meta,
                            "circuit_id": (
                                int(circuit_record.id)
                                if circuit_record is not None and circuit_record.id is not None
                                else None
                            ),
                            "circuit_name": circuit_name,
                        },
                        parameters={
                            "start_ghz": float(resolved_representative_sweep.frequencies_ghz[0]),
                            "stop_ghz": float(resolved_representative_sweep.frequencies_ghz[-1]),
                            "points": len(resolved_representative_sweep.frequencies_ghz),
                        },
                    )
                    uow.datasets.add(dataset)
                    uow.flush()
                    ds_id = dataset.id
                    if ds_id is None:
                        raise ValueError("Failed to allocate a dataset id.")
                    ds_name = str(dataset.name)
                else:
                    if selected_dataset_id is None:
                        raise ValueError("Please select an existing dataset.")
                    ds_id = int(selected_dataset_id)
                    ds_name = str(dataset_options[ds_id])

                bundle = ResultBundleRecord(
                    dataset_id=ds_id,
                    bundle_type="simulation_postprocess",
                    role="derived_from_simulation",
                    status="in_progress",
                    schema_source_hash=schema_source_hash,
                    simulation_setup_hash=simulation_setup_hash,
                    source_meta={
                        **bundle_source_meta,
                        "schema_kind": TRACE_BATCH_BUNDLE_SCHEMA_KIND,
                        "circuit_id": (
                            int(circuit_record.id)
                            if circuit_record is not None and circuit_record.id is not None
                            else None
                        ),
                        "circuit_name": circuit_name,
                    },
                    config_snapshot=bundle_config_snapshot,
                    result_payload={},
                    completed_at=None,
                )
                uow.result_bundles.add(bundle)
                uow.flush()
                if bundle.id is None:
                    raise ValueError("Failed to allocate a post-process bundle id.")
                uow.commit()

                design_id = (
                    int(circuit_record.id)
                    if circuit_record is not None and circuit_record.id is not None
                    else ds_id
                )
                design_name = (
                    str(circuit_record.name)
                    if circuit_record is not None and circuit_record.id is not None
                    else ds_name
                )
                try:
                    if isinstance(runtime_output, Mapping) and is_trace_batch_bundle_payload(
                        runtime_output
                    ):
                        summary_payload = runtime_output.get("trace_batch_record", {}).get(
                            "summary_payload",
                            {},
                        )
                        bundle.result_payload = rebind_trace_batch_bundle_payload(
                            runtime_output,
                            bundle_id=int(bundle.id),
                            design_id=design_id,
                            design_name=design_name,
                            source_kind="circuit_simulation",
                            stage_kind="postprocess",
                            setup_kind="circuit_simulation.postprocess",
                            setup_payload=bundle_config_snapshot,
                            provenance_payload=bundle_provenance_payload,
                            parent_batch_id=source_simulation_bundle_id,
                            summary_payload=(
                                summary_payload if isinstance(summary_payload, Mapping) else None
                            ),
                        )
                    else:
                        if not isinstance(runtime_output, (PortMatrixSweep, PortMatrixSweepRun)):
                            raise ValueError("Post-processed runtime output is unavailable.")
                        trace_specs = build_post_processed_trace_specs(
                            runtime_output=runtime_output
                        )
                        bundle.result_payload = persist_trace_batch_bundle(
                            bundle_id=int(bundle.id),
                            design_id=design_id,
                            design_name=design_name,
                            source_kind="circuit_simulation",
                            stage_kind="postprocess",
                            setup_kind="circuit_simulation.postprocess",
                            setup_payload=bundle_config_snapshot,
                            provenance_payload=bundle_provenance_payload,
                            trace_specs=trace_specs,
                            parent_batch_id=source_simulation_bundle_id,
                            summary_payload={
                                "trace_count": len(trace_specs),
                                "run_kind": (
                                    "parameter_sweep"
                                    if isinstance(runtime_output, PortMatrixSweepRun)
                                    else "single_run"
                                ),
                                "frequency_points": len(
                                    resolved_representative_sweep.frequencies_ghz
                                ),
                                "point_count": (
                                    runtime_output.point_count
                                    if isinstance(runtime_output, PortMatrixSweepRun)
                                    else 1
                                ),
                                "representative_point_index": (
                                    runtime_output.representative_point_index
                                    if isinstance(runtime_output, PortMatrixSweepRun)
                                    else 0
                                ),
                            },
                        )
                    persisted_records = _build_trace_batch_data_records(
                        dataset_id=ds_id,
                        trace_batch_payload=bundle.result_payload,
                    )
                    persisted_trace_ids: list[int] = []
                    for persisted_record in persisted_records:
                        uow.data_records.add(persisted_record)
                        uow.flush()
                        if persisted_record.id is None:
                            raise ValueError("Failed to allocate a post-processed trace id.")
                        persisted_trace_ids.append(int(persisted_record.id))
                    if persisted_trace_ids:
                        uow.result_bundles.attach_traces(
                            batch_id=int(bundle.id),
                            trace_ids=persisted_trace_ids,
                        )
                    uow.result_bundles.mark_completed(int(bundle.id))
                    uow.commit()
                    return ds_name
                except Exception as exc:
                    uow.result_bundles.mark_failed(
                        int(bundle.id),
                        summary_payload={
                            "error_code": "trace_batch_persist_failed",
                            "error_summary": str(exc),
                        },
                    )
                    uow.commit()
                    raise

        async def save() -> None:
            mode = str(mode_toggle.value)
            name = str(name_input.value or "").strip()
            selected_dataset_id = (
                int(dataset_select.value) if isinstance(dataset_select.value, int) else None
            )
            if mode == "Create New" and not name:
                ui.notify("Dataset Name is required.", type="warning")
                return
            if mode != "Create New" and selected_dataset_id is None:
                ui.notify("Please select an existing dataset.", type="warning")
                return

            save_button.disable()
            cancel_button.disable()
            save_button.props(add="loading")
            await asyncio.sleep(0)

            try:
                ds_name = await run.io_bound(
                    _save_to_dataset,
                    mode,
                    new_dataset_name=name,
                    selected_dataset_id=selected_dataset_id,
                )
                ui.notify(
                    f"Saved {bundle_trace_count} post-processed trace(s) to: {ds_name}",
                    type="positive",
                )
                dialog.close()
            except Exception as exc:
                if "UNIQUE constraint failed" in str(exc):
                    ui.notify("A dataset with this name already exists.", type="negative")
                else:
                    ui.notify(f"Failed to save post-processed results: {exc}", type="negative")
            finally:
                save_button.props(remove="loading")
                save_button.enable()
                cancel_button.enable()

        with ui.row().classes("w-full justify-end mt-4 gap-2"):
            cancel_button = ui.button("Cancel", on_click=dialog.close).props("flat")
            save_button = ui.button("Save", on_click=save).props("color=primary")

    dialog.open()
