from __future__ import annotations

import ast
import json
import math
import shutil
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

import numpy as np

from app_backend.domain.result_traces import ResultTraceSelection, build_trace_parameter
from app_backend.domain.runtime_contracts.execution import TaskResultHandle
from app_backend.domain.tasks import TaskDetail, TaskResultRefs
from app_backend.infrastructure.storage_reference_factory import (
    build_metadata_record_ref,
    build_result_handle_ref,
    build_result_provenance_ref,
    build_trace_payload_ref,
)

SIMULATION_RAW_BUNDLE_KEY = "simulation_raw_bundle"
SIMULATION_PTC_BUNDLE_KEY = "simulation_ptc_bundle"
POST_PROCESSING_RAW_BUNDLE_KEY = "post_processing_raw_bundle"
POST_PROCESSING_PTC_BUNDLE_KEY = "post_processing_ptc_bundle"

_PARSED_BUNDLE_PAYLOAD_CACHE: dict[tuple[int, str, str], tuple[str, dict[str, object]]] = {}
_PARSED_BUNDLE_PAYLOAD_CACHE_MAX = 32


@dataclass(frozen=True)
class PersistedExplorerBundle:
    frequencies_ghz: tuple[float, ...]
    labels: tuple[str, ...]
    family_bundle: dict[str, dict[str, list[np.ndarray]]]


@dataclass(frozen=True)
class PersistedTraceSelectionData:
    frequencies_ghz: tuple[float, ...]
    values: np.ndarray
    output_label: str
    input_label: str
    source_kind: str
    stage_kind: str


@dataclass(frozen=True)
class PersistedNdTraceSelectionData:
    axes: tuple[dict[str, object], ...]
    values: np.ndarray
    output_label: str
    input_label: str
    source_kind: str
    stage_kind: str


@dataclass(frozen=True)
class PersistedSimulationTraceGridData:
    frequencies_ghz: tuple[float, ...]
    compare_values: tuple[float, ...] | None
    values: np.ndarray


@dataclass(frozen=True)
class _TaskBundlePayloadKeys:
    raw: str
    ptc: str


@dataclass(frozen=True)
class _PersistedBundleTraceRecords:
    trace_records: list[dict[str, object]]
    trace_store: Any
    first_record: dict[str, object]
    frequencies_ghz: tuple[float, ...]


def _trace_store() -> Any:
    symbols = _core_symbols()
    return symbols["LocalZarrTraceStore"](root_path=symbols["get_trace_store_path"]())


@lru_cache(maxsize=1)
def _core_symbols() -> dict[str, Any]:
    from app_backend.infrastructure.local_store.trace_store import (
        LocalZarrTraceStore,
        get_trace_store_path,
    )

    return {
        "LocalZarrTraceStore": LocalZarrTraceStore,
        "get_trace_store_path": get_trace_store_path,
    }


def _in_process_runtime_removed() -> RuntimeError:
    return RuntimeError(
        "In-process Python simulation runtime was archived; submit simulation work "
        "to the Julia Runner instead."
    )


def run_real_simulation_task(
    task: TaskDetail,
    *,
    definition_source_text: str,
) -> tuple[dict[str, object], TaskResultRefs]:
    del task, definition_source_text
    raise _in_process_runtime_removed()


def run_real_post_processing_task(
    task: TaskDetail,
    *,
    upstream_task: TaskDetail,
) -> tuple[dict[str, object], TaskResultRefs]:
    del task, upstream_task
    raise _in_process_runtime_removed()


def available_sources_for_task_family(task: TaskDetail, family: str) -> tuple[str, ...]:
    payload_keys = _bundle_payload_keys_for_task(task)
    if payload_keys is None:
        return ()
    raw_available = _bundle_payload_for_task(task, payload_keys.raw) is not None
    ptc_available = _bundle_payload_for_task(task, payload_keys.ptc) is not None

    sources: list[str] = []
    if raw_available:
        sources.append("raw")
    if ptc_available and family in {"y_matrix", "z_matrix"}:
        sources.append("ptc")
    return tuple(sources)


def _bundle_payload_keys_for_task(task: TaskDetail) -> _TaskBundlePayloadKeys | None:
    if task.kind == "simulation":
        return _TaskBundlePayloadKeys(
            raw=SIMULATION_RAW_BUNDLE_KEY,
            ptc=SIMULATION_PTC_BUNDLE_KEY,
        )
    if task.kind == "post_processing":
        return _TaskBundlePayloadKeys(
            raw=POST_PROCESSING_RAW_BUNDLE_KEY,
            ptc=POST_PROCESSING_PTC_BUNDLE_KEY,
        )
    return None


def _bundle_payload_for_source(
    task: TaskDetail,
    source: str,
) -> dict[str, object] | None:
    payload_keys = _bundle_payload_keys_for_task(task)
    if payload_keys is None:
        return None
    if source == "raw":
        return _bundle_payload_for_task(task, payload_keys.raw)
    if source == "ptc":
        return _bundle_payload_for_task(task, payload_keys.ptc)
    raise ValueError(f"Unsupported simulation trace source: {source}")


def _required_bundle_payload(
    task: TaskDetail,
    *,
    source: str,
    missing_message: str,
) -> dict[str, object]:
    payload = _bundle_payload_for_source(task, source)
    if payload is None:
        raise ValueError(missing_message)
    return payload


def port_options_for_task(
    task: TaskDetail,
    *,
    basis_task: TaskDetail | None = None,
    definition: object | None = None,
) -> dict[int, str]:
    if task.kind != "post_processing":
        if basis_task is None:
            raise ValueError("basis_task is required for simulation port resolution.")
        from app_backend.domain.result_traces import resolve_port_options

        return resolve_port_options(basis_task, definition=definition)

    bundle = load_task_family_bundle(task, basis_task=basis_task, z0_ohm=50.0, sweep_index=0)
    resolved: dict[int, str] = {}
    for index, label in enumerate(bundle.labels, start=1):
        resolved[index] = f"Port {label}" if label.isdigit() else label
    return resolved or {1: "Port 1"}


def load_task_family_bundle(
    task: TaskDetail,
    *,
    basis_task: TaskDetail | None = None,
    z0_ohm: float,
    sweep_index: int | None,
) -> PersistedExplorerBundle:
    axis_indices = _decode_axis_indices(
        (basis_task.simulation_setup if basis_task is not None else task.simulation_setup),
        sweep_index,
    )
    if task.kind == "simulation":
        return _load_simulation_bundle_view(
            task=task,
            axis_indices=axis_indices,
        )

    if task.kind != "post_processing":
        raise ValueError("Persisted family bundles are only available for result tasks.")

    return _load_post_processing_bundle_view(
        task=task,
        axis_indices=axis_indices,
        z0_ohm=z0_ohm,
    )


def _load_simulation_bundle_view(
    *,
    task: TaskDetail,
    axis_indices: tuple[int, ...],
) -> PersistedExplorerBundle:
    merged = _build_simulation_bundle_view(
        bundle_payload=_required_bundle_payload(
            task,
            source="raw",
            missing_message="Simulation raw bundle is missing.",
        ),
        axis_indices=axis_indices,
        source_key="raw",
    )
    ptc_payload = _bundle_payload_for_source(task, "ptc")
    if ptc_payload is None:
        return merged
    return _merge_bundle_views(
        merged,
        _build_simulation_bundle_view(
            bundle_payload=ptc_payload,
            axis_indices=axis_indices,
            source_key="ptc",
        ),
    )


def _load_post_processing_bundle_view(
    *,
    task: TaskDetail,
    axis_indices: tuple[int, ...],
    z0_ohm: float,
) -> PersistedExplorerBundle:
    merged = _build_post_processing_bundle_view(
        bundle_payload=_required_bundle_payload(
            task,
            source="raw",
            missing_message="Post-processing raw bundle is missing.",
        ),
        axis_indices=axis_indices,
        source_key="raw",
        z0_ohm=z0_ohm,
    )
    ptc_payload = _bundle_payload_for_source(task, "ptc")
    if ptc_payload is None:
        return merged
    return _merge_bundle_views(
        merged,
        _build_post_processing_bundle_view(
            bundle_payload=ptc_payload,
            axis_indices=axis_indices,
            source_key="ptc",
            z0_ohm=z0_ohm,
        ),
    )


def extract_selection_trace_data(
    task: TaskDetail,
    *,
    basis_task: TaskDetail | None = None,
    selection: ResultTraceSelection,
) -> PersistedTraceSelectionData:
    bundle = load_task_family_bundle(
        task,
        basis_task=basis_task,
        z0_ohm=selection.z0_ohm or 50.0,
        sweep_index=selection.sweep_index,
    )
    matrices = bundle.family_bundle.get(selection.family, {}).get(selection.source)
    if matrices is None:
        raise ValueError("Selected trace family/source is not available.")
    output_index = selection.output_port - 1
    input_index = selection.input_port - 1
    if output_index < 0 or output_index >= len(bundle.labels):
        raise ValueError("Selected output_port is not available.")
    if input_index < 0 or input_index >= len(bundle.labels):
        raise ValueError("Selected input_port is not available.")
    values = np.asarray(
        [complex(matrix[output_index, input_index]) for matrix in matrices],
        dtype=np.complex128,
    )
    return PersistedTraceSelectionData(
        frequencies_ghz=bundle.frequencies_ghz,
        values=values,
        output_label=bundle.labels[output_index],
        input_label=bundle.labels[input_index],
        source_kind="circuit_simulation",
        stage_kind=(
            "postprocess"
            if task.kind == "post_processing"
            or selection.source == "ptc"
            or selection.family in {"y_matrix", "z_matrix"}
            else "raw"
        ),
    )


def extract_selection_trace_nd_data(
    task: TaskDetail,
    *,
    basis_task: TaskDetail | None = None,
    selection: ResultTraceSelection,
) -> PersistedNdTraceSelectionData:
    bundle_payload = _bundle_payload_for_source(
        basis_task if basis_task is not None else task,
        selection.source,
    )
    if bundle_payload is None:
        raise ValueError("Selected trace family/source is not available.")
    loaded_bundle = _load_bundle_trace_records(bundle_payload)
    real_record = None
    imag_record = None
    for record in loaded_bundle.trace_records:
        if record.get("family") != selection.family:
            continue
        trace_meta = _require_mapping(record.get("trace_meta"), field_name="trace_meta")
        if (
            int(trace_meta.get("output_port", 0) or 0) != selection.output_port
            or int(trace_meta.get("input_port", 0) or 0) != selection.input_port
        ):
            continue
        representation = str(record.get("representation", "")).strip()
        if representation == "real":
            real_record = record
        elif representation == "imaginary":
            imag_record = record
    if real_record is None or imag_record is None:
        raise ValueError("Selected trace family/source is not available.")

    trace_store = loaded_bundle.trace_store
    real_store_ref = _require_mapping(real_record.get("store_ref"), field_name="store_ref")
    imag_store_ref = _require_mapping(imag_record.get("store_ref"), field_name="store_ref")
    shape = tuple(int(value) for value in real_store_ref.get("shape", []))
    selection_slices = tuple(slice(None) for _ in shape)
    real_values = np.asarray(
        trace_store.read_trace_slice(real_store_ref, selection=selection_slices),
        dtype=np.float64,
    )
    imag_values = np.asarray(
        trace_store.read_trace_slice(imag_store_ref, selection=selection_slices),
        dtype=np.float64,
    )
    axes = []
    for axis_index, axis in enumerate(real_record.get("axes", ())):
        axis_payload = _require_mapping(axis, field_name=f"axes[{axis_index}]")
        axis_name = str(axis_payload.get("name", "")).strip()
        axis_unit = str(axis_payload.get("unit", "")).strip()
        axis_values = tuple(
            float(value)
            for value in _read_axis_values(
                trace_store,
                real_store_ref,
                axis_name=axis_name,
            )
        )
        axes.append(
            {
                "name": axis_name,
                "unit": axis_unit,
                "length": int(axis_payload.get("length", len(axis_values)) or len(axis_values)),
                "values": list(axis_values),
            }
        )
    return PersistedNdTraceSelectionData(
        axes=tuple(axes),
        values=np.asarray(real_values + (1j * imag_values), dtype=np.complex128),
        output_label=(
            loaded_bundle.first_record.get("trace_meta", {}).get("output_label")
            if isinstance(loaded_bundle.first_record.get("trace_meta"), Mapping)
            else str(selection.output_port)
        )
        or str(selection.output_port),
        input_label=(
            loaded_bundle.first_record.get("trace_meta", {}).get("input_label")
            if isinstance(loaded_bundle.first_record.get("trace_meta"), Mapping)
            else str(selection.input_port)
        )
        or str(selection.input_port),
        source_kind="circuit_simulation",
        stage_kind=(
            "postprocess"
            if task.kind == "post_processing"
            or selection.source == "ptc"
            or selection.family in {"y_matrix", "z_matrix"}
            else "raw"
        ),
    )


def extract_simulation_trace_grid_data(
    task: TaskDetail,
    *,
    family: str,
    source: str,
    output_port: int,
    input_port: int,
    sweep_index: int | None,
    compare_axis_index: int | None,
) -> PersistedSimulationTraceGridData:
    if task.kind != "simulation" or task.simulation_setup is None:
        raise ValueError("Simulation trace grid extraction requires a persisted simulation task.")

    bundle_payload = _bundle_payload_for_source(task, source)
    if bundle_payload is None:
        raise ValueError("Simulation bundle payload is missing.")

    loaded_bundle = _load_bundle_trace_records(bundle_payload)
    trace_records = loaded_bundle.trace_records
    real_record = None
    imag_record = None
    for record in trace_records:
        if record.get("family") != family:
            continue
        trace_meta = _require_mapping(record.get("trace_meta"), field_name="trace_meta")
        if (
            int(trace_meta.get("output_port", 0) or 0) != output_port
            or int(trace_meta.get("input_port", 0) or 0) != input_port
        ):
            continue
        representation = str(record.get("representation", "")).strip()
        if representation == "real":
            real_record = record
        elif representation == "imaginary":
            imag_record = record
    if real_record is None or imag_record is None:
        raise ValueError("Persisted simulation trace grid is missing real/imaginary pairs.")

    frequencies = loaded_bundle.frequencies_ghz

    coordinates = list(_decode_axis_indices(task.simulation_setup, sweep_index))
    compare_values: tuple[float, ...] | None = None
    if compare_axis_index is not None:
        if compare_axis_index < 0 or compare_axis_index >= len(
            task.simulation_setup.parameter_sweeps
        ):
            raise ValueError("compare_axis_index is outside the available parameter sweep range.")
        compare_axis = task.simulation_setup.parameter_sweeps[compare_axis_index]
        compare_values = tuple(float(value) for value in compare_axis.values)
        selectors: list[object] = [int(coordinate) for coordinate in coordinates]
        selectors[compare_axis_index] = slice(None)
    else:
        selectors = [int(coordinate) for coordinate in coordinates]

    selection: tuple[object, ...] = (
        (slice(None), *selectors) if len(selectors) > 0 else (slice(None),)
    )
    real_grid = _read_trace_grid_values(
        loaded_bundle.trace_store,
        _require_mapping(real_record.get("store_ref"), field_name="store_ref"),
        selection=selection,
        frequency_count=len(frequencies),
    )
    imag_grid = _read_trace_grid_values(
        loaded_bundle.trace_store,
        _require_mapping(imag_record.get("store_ref"), field_name="store_ref"),
        selection=selection,
        frequency_count=len(frequencies),
    )
    return PersistedSimulationTraceGridData(
        frequencies_ghz=frequencies,
        compare_values=compare_values,
        values=np.asarray(real_grid + (1j * imag_grid), dtype=np.complex128),
    )


def extract_result_trace_grid_data(
    task: TaskDetail,
    *,
    basis_task: TaskDetail | None = None,
    family: str,
    source: str,
    output_port: int,
    input_port: int,
    sweep_index: int | None,
    compare_axis_index: int | None,
    z0_ohm: float,
) -> PersistedSimulationTraceGridData:
    if task.kind == "simulation":
        return extract_simulation_trace_grid_data(
            task,
            family=family,
            source=source,
            output_port=output_port,
            input_port=input_port,
            sweep_index=sweep_index,
            compare_axis_index=compare_axis_index,
        )

    if task.kind != "post_processing" or basis_task is None or basis_task.simulation_setup is None:
        raise ValueError(
            "Result trace grid extraction requires a persisted simulation or post-processing task."
        )

    bundle_payload = _bundle_payload_for_source(task, source)
    if bundle_payload is None:
        raise ValueError("Selected trace family/source is not available.")

    loaded_bundle = _load_bundle_trace_records(bundle_payload)
    labels = _post_processing_labels(loaded_bundle.trace_records, loaded_bundle.first_record)
    if len(labels) == 0:
        raise ValueError("Persisted post-processing bundle is missing matrix labels.")
    frequencies = loaded_bundle.frequencies_ghz
    coordinates = list(_decode_axis_indices(basis_task.simulation_setup, sweep_index))
    compare_values: tuple[float, ...] | None = None
    if compare_axis_index is not None:
        if compare_axis_index < 0 or compare_axis_index >= len(
            basis_task.simulation_setup.parameter_sweeps
        ):
            raise ValueError("compare_axis_index is outside the available parameter sweep range.")
        compare_axis = basis_task.simulation_setup.parameter_sweeps[compare_axis_index]
        compare_values = tuple(float(value) for value in compare_axis.values)
        selectors: list[object] = [int(coordinate) for coordinate in coordinates]
        selectors[compare_axis_index] = slice(None)
    else:
        selectors = [int(coordinate) for coordinate in coordinates]

    selection: tuple[object, ...] = (
        (slice(None), *selectors) if len(selectors) > 0 else (slice(None),)
    )
    y_grid = _materialize_post_processing_y_matrix_grid(
        trace_store=loaded_bundle.trace_store,
        trace_records=loaded_bundle.trace_records,
        labels=labels,
        selection=selection,
        frequency_count=len(frequencies),
    )
    if family == "y_matrix":
        values = y_grid[:, :, output_port - 1, input_port - 1]
    elif family == "z_matrix":
        values = np.empty((y_grid.shape[0], y_grid.shape[1]), dtype=np.complex128)
        for frequency_index in range(y_grid.shape[0]):
            for compare_index in range(y_grid.shape[1]):
                matrix = _matrix_inverse(y_grid[frequency_index, compare_index])
                values[frequency_index, compare_index] = matrix[output_port - 1, input_port - 1]
    elif family == "s_matrix":
        values = np.empty((y_grid.shape[0], y_grid.shape[1]), dtype=np.complex128)
        for frequency_index in range(y_grid.shape[0]):
            for compare_index in range(y_grid.shape[1]):
                matrix = _matrix_s_from_y(
                    y_grid[frequency_index, compare_index],
                    z0_ohm=z0_ohm,
                )
                values[frequency_index, compare_index] = matrix[output_port - 1, input_port - 1]
    else:
        raise ValueError("Selected trace family/source is not available.")
    return PersistedSimulationTraceGridData(
        frequencies_ghz=frequencies,
        compare_values=compare_values,
        values=np.asarray(values, dtype=np.complex128),
    )


def build_trace_preview_payload(
    *,
    selection: ResultTraceSelection,
    trace_data: PersistedTraceSelectionData,
) -> dict[str, object]:
    values = np.asarray(trace_data.values, dtype=np.complex128)
    if selection.family == "s_matrix":
        magnitude_values = [float(20 * math.log10(max(abs(value), 1e-12))) for value in values]
        magnitude_label = "Magnitude (dB)"
    else:
        magnitude_values = [float(abs(value)) for value in values]
        magnitude_label = "Magnitude"
    return {
        "trace_key": selection.to_trace_key(),
        "parameter": build_trace_parameter(selection),
        "x_axis": {
            "label": "Frequency",
            "unit": "GHz",
            "values": [float(value) for value in trace_data.frequencies_ghz],
        },
        "series": [
            {
                "series_id": "real",
                "label": "Real",
                "values": [float(value.real) for value in values],
            },
            {
                "series_id": "imaginary",
                "label": "Imaginary",
                "values": [float(value.imag) for value in values],
            },
            {
                "series_id": "magnitude",
                "label": magnitude_label,
                "values": magnitude_values,
            },
        ],
        "history_summary": "PTC" if selection.source == "ptc" else "Raw",
    }


def write_complex_trace_payload(
    *,
    dataset_id: str,
    design_id: str,
    trace_id: str,
    frequencies_ghz: Sequence[float],
    values: np.ndarray,
    store_key: str | None = None,
) -> Any:
    trace_store = _core_symbols()["LocalZarrTraceStore"](
        root_path=_core_symbols()["get_trace_store_path"]()
    )
    resolved_store_key = store_key or f"datasets/{dataset_id}/designs/{design_id}/{trace_id}.zarr"
    write_result = trace_store.write_trace(
        design_id=_stable_positive_int(dataset_id, design_id),
        batch_id=_stable_positive_int(trace_id, dataset_id),
        trace_id=1,
        values=np.asarray(values, dtype=np.complex128),
        axes=(
            {
                "name": "frequency",
                "unit": "GHz",
                "values": np.asarray(tuple(float(value) for value in frequencies_ghz)),
            },
        ),
        store_key=resolved_store_key,
        payload_role="raw",
        writer_version="local_runtime.trace_publish",
    )
    return _trace_payload_ref_from_store_ref(
        write_result.store_ref,
        payload_role="dataset_primary",
    )


def write_nd_complex_trace_payload(
    *,
    dataset_id: str,
    design_id: str,
    trace_id: str,
    axes: Sequence[Mapping[str, object]],
    values: np.ndarray,
    store_key: str | None = None,
) -> Any:
    trace_store = _core_symbols()["LocalZarrTraceStore"](
        root_path=_core_symbols()["get_trace_store_path"]()
    )
    resolved_store_key = store_key or f"datasets/{dataset_id}/designs/{design_id}/{trace_id}.zarr"
    write_result = trace_store.write_trace(
        design_id=_stable_positive_int(dataset_id, design_id),
        batch_id=_stable_positive_int(trace_id, dataset_id),
        trace_id=1,
        values=np.asarray(values, dtype=np.complex128),
        axes=tuple(dict(axis) for axis in axes),
        store_key=resolved_store_key,
        payload_role="raw",
        writer_version="local_runtime.trace_publish_nd",
    )
    return _trace_payload_ref_from_store_ref(
        write_result.store_ref,
        payload_role="dataset_primary",
    )


def delete_trace_payload_store(store_key: str) -> None:
    trace_store_root = Path(_core_symbols()["get_trace_store_path"]()).resolve()
    store_path = (trace_store_root / store_key).resolve()
    if not store_path.is_relative_to(trace_store_root):
        raise ValueError("trace payload store_key escapes the configured trace store root")
    if store_path.is_dir():
        shutil.rmtree(store_path)
        return
    if store_path.exists():
        store_path.unlink()


def _bundle_payload_for_task(task: TaskDetail, key: str) -> dict[str, object] | None:
    completion_event = next(
        (
            event
            for event in reversed(task.events)
            if event.event_type == "task_completed" and key in event.metadata
        ),
        None,
    )
    if completion_event is None:
        return None
    payload = completion_event.metadata.get(key)
    if isinstance(payload, dict):
        return payload
    if isinstance(payload, str):
        cache_key = (task.task_id, completion_event.event_key, key)
        cached = _PARSED_BUNDLE_PAYLOAD_CACHE.get(cache_key)
        if cached is not None and cached[0] == payload:
            return cached[1]
        parsed = _parse_bundle_payload(payload)
        if parsed is None:
            return None
        _PARSED_BUNDLE_PAYLOAD_CACHE[cache_key] = (payload, parsed)
        while len(_PARSED_BUNDLE_PAYLOAD_CACHE) > _PARSED_BUNDLE_PAYLOAD_CACHE_MAX:
            oldest_key = next(iter(_PARSED_BUNDLE_PAYLOAD_CACHE))
            _PARSED_BUNDLE_PAYLOAD_CACHE.pop(oldest_key, None)
        return parsed
    return None


def _parse_bundle_payload(payload: str) -> dict[str, object] | None:
    try:
        parsed = json.loads(payload)
    except json.JSONDecodeError:
        try:
            parsed = ast.literal_eval(payload)
        except (SyntaxError, ValueError):
            return None
    return parsed if isinstance(parsed, dict) else None


def _load_bundle_trace_records(
    bundle_payload: Mapping[str, object],
) -> _PersistedBundleTraceRecords:
    trace_records = _require_trace_records(bundle_payload)
    first_record = trace_records[0]
    trace_store = _trace_store()
    first_store_ref = _require_mapping(first_record.get("store_ref"), field_name="store_ref")
    frequencies = tuple(
        float(value)
        for value in _read_axis_values(
            trace_store,
            first_store_ref,
            axis_name="frequency",
        )
    )
    return _PersistedBundleTraceRecords(
        trace_records=trace_records,
        trace_store=trace_store,
        first_record=first_record,
        frequencies_ghz=frequencies,
    )


def _build_simulation_bundle_view(
    *,
    bundle_payload: Mapping[str, object],
    axis_indices: tuple[int, ...],
    source_key: str,
) -> PersistedExplorerBundle:
    loaded_bundle = _load_bundle_trace_records(bundle_payload)
    trace_records = loaded_bundle.trace_records
    ports = sorted(
        {
            int(trace_meta.get("output_port", 0))
            for record in trace_records
            if isinstance(record, Mapping)
            and isinstance((trace_meta := record.get("trace_meta")), Mapping)
            and int(trace_meta.get("output_port", 0) or 0) > 0
        }
        | {
            int(trace_meta.get("input_port", 0))
            for record in trace_records
            if isinstance(record, Mapping)
            and isinstance((trace_meta := record.get("trace_meta")), Mapping)
            and int(trace_meta.get("input_port", 0) or 0) > 0
        }
    )
    labels = tuple(str(port) for port in ports)
    family_bundle: dict[str, dict[str, list[np.ndarray]]] = {}
    for family in ("s_matrix", "y_matrix", "z_matrix"):
        family_records = [
            record
            for record in trace_records
            if isinstance(record, Mapping) and record.get("family") == family
        ]
        if len(family_records) == 0:
            continue
        family_bundle[family] = {
            source_key: _materialize_simulation_family_matrices(
                trace_records=family_records,
                labels=labels,
                axis_indices=axis_indices,
            )
        }
    return PersistedExplorerBundle(
        frequencies_ghz=loaded_bundle.frequencies_ghz,
        labels=labels,
        family_bundle=family_bundle,
    )


def _build_post_processing_bundle_view(
    *,
    bundle_payload: Mapping[str, object],
    axis_indices: tuple[int, ...],
    source_key: str,
    z0_ohm: float,
) -> PersistedExplorerBundle:
    loaded_bundle = _load_bundle_trace_records(bundle_payload)
    trace_records = loaded_bundle.trace_records
    labels = _post_processing_labels(trace_records, loaded_bundle.first_record)
    if len(labels) == 0:
        raise ValueError("Persisted post-processing bundle is missing matrix labels.")
    y_matrices = _materialize_post_processing_y_matrices(
        trace_records=trace_records,
        labels=labels,
        axis_indices=axis_indices,
    )
    family_bundle: dict[str, dict[str, list[np.ndarray]]] = {
        "y_matrix": {source_key: y_matrices},
        "z_matrix": {source_key: [_matrix_inverse(matrix) for matrix in y_matrices]},
    }
    if source_key == "raw":
        family_bundle["s_matrix"] = {
            source_key: [_matrix_s_from_y(matrix, z0_ohm=z0_ohm) for matrix in y_matrices]
        }
    return PersistedExplorerBundle(
        frequencies_ghz=loaded_bundle.frequencies_ghz,
        labels=labels,
        family_bundle=family_bundle,
    )


def _materialize_simulation_family_matrices(
    *,
    trace_records: Sequence[Mapping[str, object]],
    labels: tuple[str, ...],
    axis_indices: tuple[int, ...],
) -> list[np.ndarray]:
    trace_store = _trace_store()
    grouped: dict[tuple[int, int], dict[str, np.ndarray]] = {}
    for record in trace_records:
        trace_meta = _require_mapping(record.get("trace_meta"), field_name="trace_meta")
        key = (
            int(trace_meta.get("output_port", 0)),
            int(trace_meta.get("input_port", 0)),
        )
        grouped.setdefault(key, {})[str(record.get("representation"))] = _read_trace_values(
            trace_store,
            _require_mapping(record.get("store_ref"), field_name="store_ref"),
            axis_indices,
        )
    sample = next(iter(grouped.values()))
    sample_values = sample.get("real")
    if sample_values is None:
        sample_values = sample.get("imaginary")
    if sample_values is None:
        raise ValueError("Persisted trace family is missing numeric values.")
    matrices = [
        np.zeros((len(labels), len(labels)), dtype=np.complex128) for _ in range(len(sample_values))
    ]
    label_positions = {int(label): index for index, label in enumerate(labels)}
    for (output_port, input_port), representations in grouped.items():
        output_index = label_positions[output_port]
        input_index = label_positions[input_port]
        real_values = representations.get("real")
        imag_values = representations.get("imaginary")
        if real_values is None or imag_values is None:
            raise ValueError("Persisted trace family is missing real/imaginary pairs.")
        for frequency_index in range(len(matrices)):
            matrices[frequency_index][output_index, input_index] = complex(
                real_values[frequency_index],
                imag_values[frequency_index],
            )
    return matrices


def _materialize_post_processing_y_matrices(
    *,
    trace_records: Sequence[Mapping[str, object]],
    labels: tuple[str, ...],
    axis_indices: tuple[int, ...],
) -> list[np.ndarray]:
    trace_store = _trace_store()
    label_positions = {label: index for index, label in enumerate(labels)}
    grouped: dict[tuple[str, str], dict[str, np.ndarray]] = {}
    for record in trace_records:
        trace_meta = _require_mapping(record.get("trace_meta"), field_name="trace_meta")
        key = (
            str(trace_meta.get("row_label", "")),
            str(trace_meta.get("col_label", "")),
        )
        grouped.setdefault(key, {})[str(record.get("representation"))] = _read_trace_values(
            trace_store,
            _require_mapping(record.get("store_ref"), field_name="store_ref"),
            axis_indices,
        )
    sample = next(iter(grouped.values()))
    sample_values = sample.get("real")
    if sample_values is None:
        sample_values = sample.get("imaginary")
    if sample_values is None:
        raise ValueError("Persisted post-processing family is missing numeric values.")
    matrices = [
        np.zeros((len(labels), len(labels)), dtype=np.complex128) for _ in range(len(sample_values))
    ]
    for (row_label, col_label), representations in grouped.items():
        row_index = label_positions[row_label]
        col_index = label_positions[col_label]
        real_values = representations.get("real")
        imag_values = representations.get("imaginary")
        if real_values is None or imag_values is None:
            raise ValueError("Persisted post-processing traces are missing real/imaginary pairs.")
        for frequency_index in range(len(matrices)):
            matrices[frequency_index][row_index, col_index] = complex(
                real_values[frequency_index],
                imag_values[frequency_index],
            )
    return matrices


def _materialize_post_processing_y_matrix_grid(
    *,
    trace_store: Any,
    trace_records: Sequence[Mapping[str, object]],
    labels: tuple[str, ...],
    selection: tuple[object, ...],
    frequency_count: int,
) -> np.ndarray:
    label_positions = {label: index for index, label in enumerate(labels)}
    grouped: dict[tuple[str, str], dict[str, np.ndarray]] = {}
    for record in trace_records:
        trace_meta = _require_mapping(record.get("trace_meta"), field_name="trace_meta")
        key = (
            str(trace_meta.get("row_label", "")),
            str(trace_meta.get("col_label", "")),
        )
        grouped.setdefault(key, {})[str(record.get("representation"))] = _read_trace_grid_values(
            trace_store,
            _require_mapping(record.get("store_ref"), field_name="store_ref"),
            selection=selection,
            frequency_count=frequency_count,
        )
    sample = next(iter(grouped.values()))
    sample_values = sample.get("real")
    if sample_values is None:
        sample_values = sample.get("imaginary")
    if sample_values is None:
        raise ValueError("Persisted post-processing traces are missing real/imaginary pairs.")
    matrix_grid = np.zeros(
        (frequency_count, sample_values.shape[1], len(labels), len(labels)),
        dtype=np.complex128,
    )
    for (row_label, col_label), representations in grouped.items():
        row_index = label_positions[row_label]
        col_index = label_positions[col_label]
        real_values = representations.get("real")
        imag_values = representations.get("imaginary")
        if real_values is None or imag_values is None:
            raise ValueError("Persisted post-processing traces are missing real/imaginary pairs.")
        matrix_grid[:, :, row_index, col_index] = real_values + (1j * imag_values)
    return matrix_grid


def _merge_bundle_views(
    left: PersistedExplorerBundle,
    right: PersistedExplorerBundle,
) -> PersistedExplorerBundle:
    merged = {
        family: {source: list(matrices) for source, matrices in sources.items()}
        for family, sources in left.family_bundle.items()
    }
    for family, sources in right.family_bundle.items():
        merged.setdefault(family, {}).update(
            {source: list(matrices) for source, matrices in sources.items()}
        )
    return PersistedExplorerBundle(
        frequencies_ghz=left.frequencies_ghz or right.frequencies_ghz,
        labels=left.labels or right.labels,
        family_bundle=merged,
    )


def _post_processing_labels(
    trace_records: Sequence[Mapping[str, object]],
    first_record: Mapping[str, object],
) -> tuple[str, ...]:
    first_meta = _require_mapping(
        first_record.get("trace_meta"),
        field_name="trace_meta",
    )
    raw_labels = first_meta.get("labels", ())
    labels = tuple(str(label) for label in raw_labels) if isinstance(raw_labels, list) else ()
    if len(labels) > 0:
        return labels
    return tuple(
        sorted(
            {
                str(
                    _require_mapping(
                        record.get("trace_meta"),
                        field_name="trace_meta",
                    ).get("row_label", "")
                )
                for record in trace_records
                if isinstance(record, Mapping)
            }
        )
    )


def _task_result_refs_from_bundle(
    *,
    task: TaskDetail,
    bundle_payload: Mapping[str, object],
    handle_kind: str,
    handle_label: str,
    trace_batch_record_id: str,
) -> TaskResultRefs:
    trace_batch_record = build_metadata_record_ref("trace_batch", trace_batch_record_id, version=1)
    result_handle_record = build_metadata_record_ref(
        "result_handle",
        f"result_handle:{task.task_id}",
        version=2,
    )
    first_trace = _require_trace_records(bundle_payload)[0]
    trace_payload = _trace_payload_ref_from_store_ref(
        _require_mapping(first_trace.get("store_ref"), field_name="store_ref"),
        payload_role="task_output",
    )
    result_handle = build_result_handle_ref(
        handle_id=f"task-result:{task.task_id}:primary",
        kind=handle_kind,
        status="materialized",
        label=handle_label,
        metadata_record=result_handle_record,
        payload_backend="local_zarr",
        payload_format="zarr",
        payload_role="trace_payload",
        payload_locator=trace_payload.store_uri or trace_payload.store_key,
        provenance_task_id=task.task_id,
        provenance=build_result_provenance_ref(
            source_dataset_id=task.dataset_id,
            source_task_id=task.task_id,
            trace_batch_record=trace_batch_record,
        ),
    )
    return TaskResultRefs(
        result_handle=TaskResultHandle(trace_batch_id=task.task_id),
        metadata_records=(trace_batch_record, result_handle_record),
        trace_payload=trace_payload,
        result_handles=(result_handle,),
    )


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


def _read_trace_values(
    trace_store: Any,
    store_ref: Mapping[str, object],
    axis_indices: tuple[int, ...],
) -> np.ndarray:
    selection: tuple[object, ...] = (slice(None), *axis_indices) if axis_indices else (slice(None),)
    values = np.asarray(trace_store.read_trace_slice(store_ref, selection=selection))
    return np.asarray(values).reshape(-1)


def _read_trace_grid_values(
    trace_store: Any,
    store_ref: Mapping[str, object],
    *,
    selection: tuple[object, ...],
    frequency_count: int,
) -> np.ndarray:
    values = np.asarray(trace_store.read_trace_slice(store_ref, selection=selection))
    if values.ndim == 1:
        if values.shape[0] == frequency_count:
            return values.reshape(frequency_count, 1)
        return values.reshape(1, -1).T
    if values.shape[0] == frequency_count:
        return values.reshape(frequency_count, -1)
    if values.shape[-1] == frequency_count:
        return np.moveaxis(values, -1, 0).reshape(frequency_count, -1)
    return values.reshape(frequency_count, -1)


def _read_axis_values(
    trace_store: Any,
    store_ref: Mapping[str, object],
    *,
    axis_name: str,
) -> np.ndarray:
    return np.asarray(
        trace_store.read_axis_slice(
            store_ref,
            axis_name=axis_name,
            selection=slice(None),
        )
    )


def _decode_axis_indices(setup: object | None, sweep_index: int | None) -> tuple[int, ...]:
    parameter_sweeps = tuple(getattr(setup, "parameter_sweeps", ()) or ())
    if len(parameter_sweeps) == 0:
        return ()
    resolved_index = sweep_index if sweep_index is not None else 0
    coordinates = [0] * len(parameter_sweeps)
    remaining = resolved_index
    for axis_index in range(len(parameter_sweeps) - 1, -1, -1):
        axis_size = max(len(parameter_sweeps[axis_index].values), 1)
        coordinates[axis_index] = remaining % axis_size
        remaining //= axis_size
    return tuple(coordinates)


def _matrix_inverse(matrix: np.ndarray) -> np.ndarray:
    identity = np.eye(matrix.shape[0], dtype=np.complex128)
    return np.linalg.solve(np.asarray(matrix, dtype=np.complex128), identity)


def _matrix_s_from_y(matrix_y: np.ndarray, *, z0_ohm: float) -> np.ndarray:
    z_matrix = _matrix_inverse(np.asarray(matrix_y, dtype=np.complex128))
    identity = np.eye(z_matrix.shape[0], dtype=np.complex128)
    return np.linalg.solve((z_matrix + (z0_ohm * identity)).T, (z_matrix - (z0_ohm * identity)).T).T


def _require_mapping(payload: object, *, field_name: str) -> dict[str, object]:
    if not isinstance(payload, Mapping):
        raise ValueError(f"{field_name} must be a mapping.")
    return dict(payload)


def _require_trace_records(payload: Mapping[str, object]) -> list[dict[str, object]]:
    trace_records = payload.get("trace_records", ())
    if not isinstance(trace_records, list) or len(trace_records) == 0:
        raise ValueError("Trace bundle payload has no trace records.")
    return [_require_mapping(record, field_name="trace_record") for record in trace_records]


def _stable_positive_int(*parts: object) -> int:
    token = "|".join(str(part) for part in parts)
    return (abs(hash(token)) % 900_000_000) + 1
