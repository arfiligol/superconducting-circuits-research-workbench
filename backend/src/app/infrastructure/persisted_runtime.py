from __future__ import annotations

import ast
import copy
import json
import math
import re
import shutil
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

import numpy as np
from sc_core.execution import TaskResultHandle

from src.app.domain.result_traces import ResultTraceSelection, build_trace_parameter
from src.app.domain.tasks import TaskDetail, TaskResultRefs
from src.app.infrastructure.storage_reference_factory import (
    build_metadata_record_ref,
    build_result_handle_ref,
    build_result_provenance_ref,
    build_trace_payload_ref,
)

SIMULATION_RAW_BUNDLE_KEY = "simulation_raw_bundle"
SIMULATION_PTC_BUNDLE_KEY = "simulation_ptc_bundle"
POST_PROCESSING_RAW_BUNDLE_KEY = "post_processing_raw_bundle"
POST_PROCESSING_PTC_BUNDLE_KEY = "post_processing_ptc_bundle"

_SIMULATION_CACHE: dict[str, dict[str, object]] = {}
_PARSED_BUNDLE_PAYLOAD_CACHE: dict[tuple[int, str, str], tuple[str, dict[str, object]]] = {}
_PARSED_BUNDLE_PAYLOAD_CACHE_MAX = 32
_MODE_TRACE_LABEL_PATTERN = re.compile(
    r"^[SYZ](?P<output_port>\d+)(?P<input_port>\d+)\[om=(?P<output_mode>\([^]]*\)),im=(?P<input_mode>\([^]]*\))\]$"
)
_POST_PROCESSING_BASIS_LABEL_PATTERN = re.compile(
    r"^(?P<family>cm|dm)\(\s*(?P<port_a>\d+)\s*,\s*(?P<port_b>\d+)\s*\)$",
    re.IGNORECASE,
)


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


def ensure_core_runtime_path() -> None:
    workspace_src = Path(__file__).resolve().parents[4] / "src"
    if str(workspace_src) not in sys.path:
        sys.path.insert(0, str(workspace_src))


def _trace_store() -> Any:
    symbols = _core_symbols()
    return symbols["LocalZarrTraceStore"](root_path=symbols["get_trace_store_path"]())


@lru_cache(maxsize=1)
def _core_symbols() -> dict[str, Any]:
    ensure_core_runtime_path()
    from core.shared.persistence.trace_store import LocalZarrTraceStore, get_trace_store_path
    from core.simulation.application.post_processing import (
        PortMatrixSweep,
        PortMatrixSweepPoint,
        PortMatrixSweepRun,
        apply_coordinate_transform,
        build_common_differential_transform,
        build_port_y_sweep,
        compensate_simulation_result_port_terminations,
        infer_port_termination_resistance_ohm,
        kron_reduce,
    )
    from core.simulation.application.run_simulation import (
        SimulationSweepAxis,
        SimulationSweepPointResult,
        SimulationSweepRun,
        build_simulation_sweep_plan,
        run_parameter_sweep,
        run_simulation,
        simulation_sweep_run_from_payload,
        simulation_sweep_run_to_payload,
    )
    from core.simulation.application.trace_architecture import (
        build_post_processed_trace_specs,
        build_raw_simulation_trace_specs,
        persist_trace_batch_bundle,
    )
    from core.simulation.domain.circuit import (
        CircuitDefinition,
        DriveSourceConfig,
        FrequencyRange,
        SimulationConfig,
        SimulationResult,
        parse_circuit_definition_source,
    )

    return {
        "CircuitDefinition": CircuitDefinition,
        "DriveSourceConfig": DriveSourceConfig,
        "FrequencyRange": FrequencyRange,
        "LocalZarrTraceStore": LocalZarrTraceStore,
        "PortMatrixSweep": PortMatrixSweep,
        "PortMatrixSweepPoint": PortMatrixSweepPoint,
        "PortMatrixSweepRun": PortMatrixSweepRun,
        "SimulationConfig": SimulationConfig,
        "SimulationResult": SimulationResult,
        "SimulationSweepAxis": SimulationSweepAxis,
        "SimulationSweepPointResult": SimulationSweepPointResult,
        "SimulationSweepRun": SimulationSweepRun,
        "apply_coordinate_transform": apply_coordinate_transform,
        "build_common_differential_transform": build_common_differential_transform,
        "build_port_y_sweep": build_port_y_sweep,
        "build_post_processed_trace_specs": build_post_processed_trace_specs,
        "build_raw_simulation_trace_specs": build_raw_simulation_trace_specs,
        "build_simulation_sweep_plan": build_simulation_sweep_plan,
        "compensate_simulation_result_port_terminations": (
            compensate_simulation_result_port_terminations
        ),
        "get_trace_store_path": get_trace_store_path,
        "infer_port_termination_resistance_ohm": infer_port_termination_resistance_ohm,
        "kron_reduce": kron_reduce,
        "parse_circuit_definition_source": parse_circuit_definition_source,
        "persist_trace_batch_bundle": persist_trace_batch_bundle,
        "run_parameter_sweep": run_parameter_sweep,
        "run_simulation": run_simulation,
        "simulation_sweep_run_from_payload": simulation_sweep_run_from_payload,
        "simulation_sweep_run_to_payload": simulation_sweep_run_to_payload,
    }


def run_real_simulation_task(
    task: TaskDetail,
    *,
    definition_source_text: str,
) -> tuple[dict[str, object], TaskResultRefs]:
    if task.simulation_setup is None:
        raise ValueError("Simulation setup is missing.")
    cached = _cached_simulation_runtime(task=task, definition_source_text=definition_source_text)
    raw_bundle = _persist_simulation_bundle(
        task=task,
        bundle_id=task.task_id,
        source_key="raw",
        result=copy.deepcopy(cached["raw_result"]),
        sweep_payload=copy.deepcopy(cached["raw_sweep_payload"]),
    )
    ptc_bundle = None
    if cached.get("ptc_result") is not None:
        ptc_bundle = _persist_simulation_bundle(
            task=task,
            bundle_id=(task.task_id * 1000) + 1,
            source_key="ptc",
            result=copy.deepcopy(cached["ptc_result"]),
            sweep_payload=copy.deepcopy(cached["ptc_sweep_payload"]),
        )
    return (
        {
            "summary": "Simulation completed in the local runtime.",
            "artifact_label": "simulation-trace-bundle",
            "task_kind": task.kind,
            "dataset_id": task.dataset_id,
            "definition_id": task.definition_id,
            "point_count": task.simulation_setup.frequency_sweep.point_count,
            "frequency_range_ghz": {
                "start": task.simulation_setup.frequency_sweep.start_ghz,
                "stop": task.simulation_setup.frequency_sweep.stop_ghz,
            },
            SIMULATION_RAW_BUNDLE_KEY: raw_bundle,
            **({SIMULATION_PTC_BUNDLE_KEY: ptc_bundle} if ptc_bundle is not None else {}),
        },
        _task_result_refs_from_bundle(
            task=task,
            bundle_payload=raw_bundle,
            handle_kind="simulation_trace",
            handle_label="Persisted simulation trace bundle",
            trace_batch_record_id=f"trace_batch:{task.task_id}",
        ),
    )


def run_real_post_processing_task(
    task: TaskDetail,
    *,
    upstream_task: TaskDetail,
) -> tuple[dict[str, object], TaskResultRefs]:
    if task.post_processing_setup is None:
        raise ValueError("Post-processing setup is missing.")
    if upstream_task.simulation_setup is None:
        raise ValueError("Upstream simulation setup is missing.")

    raw_input = _bundle_payload_for_task(upstream_task, SIMULATION_RAW_BUNDLE_KEY)
    if raw_input is None:
        raise ValueError("Upstream simulation raw bundle is missing.")
    raw_runtime = _build_post_processing_runtime_output(
        bundle_payload=raw_input,
        setup=task.post_processing_setup,
    )
    raw_bundle = _persist_post_processing_bundle(
        task=task,
        bundle_id=task.task_id,
        source_key="raw",
        runtime_output=raw_runtime,
    )
    ptc_bundle = None
    ptc_input = _bundle_payload_for_task(upstream_task, SIMULATION_PTC_BUNDLE_KEY)
    if ptc_input is not None:
        ptc_runtime = _build_post_processing_runtime_output(
            bundle_payload=ptc_input,
            setup=task.post_processing_setup,
        )
        ptc_bundle = _persist_post_processing_bundle(
            task=task,
            bundle_id=(task.task_id * 1000) + 1,
            source_key="ptc",
            runtime_output=ptc_runtime,
        )

    return (
        {
            "summary": "Post-processing completed in the local runtime.",
            "artifact_label": "post-processing-trace-bundle",
            "task_kind": task.kind,
            "dataset_id": task.dataset_id,
            "upstream_task_id": upstream_task.task_id,
            "operation_count": len(task.post_processing_setup.operations),
            "operations": [
                operation.operation
                for operation in task.post_processing_setup.operations
                if operation.enabled
            ],
            POST_PROCESSING_RAW_BUNDLE_KEY: raw_bundle,
            **({POST_PROCESSING_PTC_BUNDLE_KEY: ptc_bundle} if ptc_bundle is not None else {}),
        },
        _task_result_refs_from_bundle(
            task=task,
            bundle_payload=raw_bundle,
            handle_kind="fit_summary",
            handle_label="Persisted post-processing trace bundle",
            trace_batch_record_id=f"trace_batch:{task.task_id}",
        ),
    )


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
        from src.app.domain.result_traces import resolve_port_options

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
        if (
            compare_axis_index < 0
            or compare_axis_index >= len(task.simulation_setup.parameter_sweeps)
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
        magnitude_values = [
            float(20 * math.log10(max(abs(value), 1e-12))) for value in values
        ]
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
    resolved_store_key = (
        store_key or f"datasets/{dataset_id}/designs/{design_id}/{trace_id}.zarr"
    )
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
    resolved_store_key = (
        store_key or f"datasets/{dataset_id}/designs/{design_id}/{trace_id}.zarr"
    )
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


def _cached_simulation_runtime(
    *,
    task: TaskDetail,
    definition_source_text: str,
) -> dict[str, object]:
    if task.simulation_setup is None:
        raise ValueError("Simulation setup is missing.")
    cache_key = json.dumps(
        {
            "definition_source_text": definition_source_text,
            "simulation_setup": task.simulation_setup.to_mapping(),
        },
        sort_keys=True,
    )
    cached = _SIMULATION_CACHE.get(cache_key)
    if cached is not None:
        return copy.deepcopy(cached)

    symbols = _core_symbols()
    circuit = symbols["parse_circuit_definition_source"](definition_source_text)
    frequency_range = symbols["FrequencyRange"](
        start_ghz=task.simulation_setup.frequency_sweep.start_ghz,
        stop_ghz=task.simulation_setup.frequency_sweep.stop_ghz,
        points=task.simulation_setup.frequency_sweep.point_count,
    )
    config = _build_simulation_config(task=task)
    raw_result: object
    raw_sweep_payload: dict[str, object] | None
    if len(task.simulation_setup.parameter_sweeps) == 0:
        raw_result = symbols["run_simulation"](circuit, frequency_range, config)
        raw_sweep_payload = None
    else:
        axes = tuple(
            symbols["SimulationSweepAxis"](
                target_value_ref=sweep.parameter,
                values=tuple(float(value) for value in sweep.values),
                unit=sweep.unit or "",
            )
            for sweep in task.simulation_setup.parameter_sweeps
        )
        plan = symbols["build_simulation_sweep_plan"](
            circuit=circuit,
            axes=axes,
            config=config,
        )
        sweep_run = symbols["run_parameter_sweep"](
            circuit=circuit,
            freq_range=frequency_range,
            config=config,
            plan=plan,
        )
        raw_result = sweep_run.representative_result
        raw_sweep_payload = symbols["simulation_sweep_run_to_payload"](sweep_run)

    ptc_result = None
    ptc_sweep_payload = None
    if task.simulation_setup.ptc is not None and task.simulation_setup.ptc.enabled:
        ptc_result, ptc_sweep_payload = _apply_port_termination_compensation(
            circuit=circuit,
            raw_result=raw_result,
            raw_sweep_payload=raw_sweep_payload,
            compensated_ports=task.simulation_setup.ptc.compensate_ports,
        )

    cached = {
        "raw_result": raw_result,
        "raw_sweep_payload": raw_sweep_payload,
        "ptc_result": ptc_result,
        "ptc_sweep_payload": ptc_sweep_payload,
    }
    _SIMULATION_CACHE[cache_key] = copy.deepcopy(cached)
    return cached


def _build_simulation_config(*, task: TaskDetail) -> Any:
    if task.simulation_setup is None:
        raise ValueError("Simulation setup is missing.")
    symbols = _core_symbols()
    sources = [
        symbols["DriveSourceConfig"](
            pump_freq_ghz=source.frequency_ghz or 5.0,
            port=_extract_port_index(source.target) or 1,
            current_amp=source.amplitude,
        )
        for source in task.simulation_setup.sources
    ]
    harmonic_balance = task.simulation_setup.solver.harmonic_balance
    harmonic_count = (
        harmonic_balance.harmonic_count
        if harmonic_balance is not None and harmonic_balance.enabled
        else None
    )
    return symbols["SimulationConfig"](
        sources=sources or None,
        pump_freq_ghz=sources[0].pump_freq_ghz if sources else 5.0,
        pump_current_amp=sources[0].current_amp if sources else 0.0,
        pump_port=sources[0].port if sources else 1,
        n_modulation_harmonics=int(harmonic_count or 1),
        n_pump_harmonics=int(harmonic_count or 1),
        max_iterations=task.simulation_setup.solver.max_iterations,
        f_tol=task.simulation_setup.solver.convergence_tolerance,
    )


def _apply_port_termination_compensation(
    *,
    circuit: Any,
    raw_result: object,
    raw_sweep_payload: Mapping[str, object] | None,
    compensated_ports: Sequence[str],
) -> tuple[object, dict[str, object] | None]:
    symbols = _core_symbols()
    inference = symbols["infer_port_termination_resistance_ohm"](circuit)
    selected_ports = {
        port_index
        for label in compensated_ports
        if (port_index := _extract_port_index(label)) is not None
    }
    resistance_ohm_by_port = {
        port: resistance
        for port, resistance in inference.resistance_ohm_by_port.items()
        if port in selected_ports
    }
    if raw_sweep_payload is None:
        return (
            symbols["compensate_simulation_result_port_terminations"](
                raw_result,
                resistance_ohm_by_port=resistance_ohm_by_port,
            ),
            None,
        )

    raw_sweep_run = symbols["simulation_sweep_run_from_payload"](dict(raw_sweep_payload))
    compensated_points = tuple(
        symbols["SimulationSweepPointResult"](
            point_index=point.point_index,
            axis_indices=point.axis_indices,
            axis_values=dict(point.axis_values),
            result=symbols["compensate_simulation_result_port_terminations"](
                point.result,
                resistance_ohm_by_port=resistance_ohm_by_port,
            ),
        )
        for point in raw_sweep_run.points
    )
    compensated_run = symbols["SimulationSweepRun"](
        axes=raw_sweep_run.axes,
        points=compensated_points,
        representative_point_index=raw_sweep_run.representative_point_index,
    )
    return (
        compensated_run.representative_result,
        symbols["simulation_sweep_run_to_payload"](compensated_run),
    )


def _persist_simulation_bundle(
    *,
    task: TaskDetail,
    bundle_id: int,
    source_key: str,
    result: object,
    sweep_payload: Mapping[str, object] | None,
) -> dict[str, object]:
    symbols = _core_symbols()
    trace_specs = symbols["build_raw_simulation_trace_specs"](
        result=result,
        sweep_payload=sweep_payload,
    )
    return symbols["persist_trace_batch_bundle"](
        bundle_id=bundle_id,
        design_id=task.task_id,
        design_name=f"Task {task.task_id}",
        source_kind="circuit_simulation",
        stage_kind="postprocess" if source_key == "ptc" else "raw",
        setup_kind=f"simulation.{source_key}",
        setup_payload=(
            task.simulation_setup.to_mapping()
            if task.simulation_setup is not None
            else {}
        ),
        provenance_payload={
            "task_id": task.task_id,
            "definition_id": task.definition_id,
            "runtime_mode": "local",
            "source_key": source_key,
        },
        trace_specs=trace_specs,
        summary_payload={
            "trace_count": len(trace_specs),
            "point_count": _sweep_point_count(task),
            "representative_point_index": 0,
        },
    )


def _build_post_processing_runtime_output(
    *,
    bundle_payload: Mapping[str, object],
    setup: Any,
) -> Any:
    symbols = _core_symbols()
    result, sweep_payload = _simulation_bundle_to_runtime(bundle_payload)
    if sweep_payload is None:
        base_sweep = symbols["build_port_y_sweep"](
            result=result,
            mode=(0,),
            ports=list(result.available_port_indices),
        )
        return _apply_post_processing_operations(base_sweep, operations=setup.operations)

    sweep_run = symbols["simulation_sweep_run_from_payload"](dict(sweep_payload))
    points = tuple(
        symbols["PortMatrixSweepPoint"](
            point_index=point.point_index,
            axis_indices=point.axis_indices,
            axis_values=dict(point.axis_values),
            sweep=_apply_post_processing_operations(
                symbols["build_port_y_sweep"](
                    result=point.result,
                    mode=(0,),
                    ports=list(point.result.available_port_indices),
                ),
                operations=setup.operations,
            ),
        )
        for point in sweep_run.points
    )
    return symbols["PortMatrixSweepRun"](
        axes=sweep_run.axes,
        points=points,
        representative_point_index=sweep_run.representative_point_index,
    )


def _apply_post_processing_operations(
    sweep: Any,
    *,
    operations: Sequence[Any],
) -> Any:
    symbols = _core_symbols()
    current = sweep
    for operation in operations:
        if not operation.enabled:
            continue
        if operation.operation == "coordinate_transform":
            port_a = int(operation.config.get("port_a", 1)) - 1
            port_b = int(operation.config.get("port_b", 2)) - 1
            alpha = float(operation.config.get("alpha", 0.5))
            beta = float(operation.config.get("beta", 0.5))
            transform = symbols["build_common_differential_transform"](
                dimension=current.dimension,
                first_index=port_a,
                second_index=port_b,
                alpha=alpha,
                beta=beta,
            )
            labels = list(current.labels)
            first_label = labels[port_a]
            second_label = labels[port_b]
            labels[port_a] = f"CM({first_label},{second_label})"
            labels[port_b] = f"DM({first_label},{second_label})"
            current = symbols["apply_coordinate_transform"](
                current,
                transform,
                labels=tuple(labels),
            )
            continue
        if operation.operation == "kron_reduction":
            keep_labels = tuple(
                _normalize_post_processing_basis_label(label)
                for label in operation.config.get("keep_labels", ())
                if str(label).strip()
            )
            if len(keep_labels) == 0:
                raise ValueError("Kron reduction requires keep_labels.")
            keep_label_set = set(keep_labels)
            keep_indices = [
                index
                for index, label in enumerate(current.labels)
                if _normalize_post_processing_basis_label(label) in keep_label_set
            ]
            current = symbols["kron_reduce"](current, keep_indices=keep_indices)
            continue
    return current


def _normalize_post_processing_basis_label(label: object) -> str:
    trimmed = str(label).strip()
    transformed_match = _POST_PROCESSING_BASIS_LABEL_PATTERN.match(trimmed)
    if transformed_match is None:
        return trimmed
    family = (transformed_match.group("family") or "").upper()
    port_a = transformed_match.group("port_a") or ""
    port_b = transformed_match.group("port_b") or ""
    return f"{family}({port_a},{port_b})"


def _persist_post_processing_bundle(
    *,
    task: TaskDetail,
    bundle_id: int,
    source_key: str,
    runtime_output: object,
) -> dict[str, object]:
    symbols = _core_symbols()
    trace_specs = symbols["build_post_processed_trace_specs"](runtime_output=runtime_output)
    return symbols["persist_trace_batch_bundle"](
        bundle_id=bundle_id,
        design_id=task.task_id,
        design_name=f"Task {task.task_id}",
        source_kind="circuit_simulation",
        stage_kind="postprocess",
        setup_kind=f"post_processing.{source_key}",
        setup_payload=(
            task.post_processing_setup.to_mapping()
            if task.post_processing_setup is not None
            else {}
        ),
        provenance_payload={
            "task_id": task.task_id,
            "upstream_task_id": task.upstream_task_id,
            "runtime_mode": "local",
            "source_key": source_key,
        },
        trace_specs=trace_specs,
        summary_payload={
            "trace_count": len(trace_specs),
            "point_count": _sweep_point_count(task),
            "labels": list(getattr(runtime_output, "representative_sweep", runtime_output).labels),
        },
    )


def _simulation_bundle_to_runtime(
    bundle_payload: Mapping[str, object],
) -> tuple[Any, dict[str, object] | None]:
    symbols = _core_symbols()
    loaded_bundle = _load_bundle_trace_records(bundle_payload)
    frequencies = np.asarray(loaded_bundle.frequencies_ghz, dtype=float)
    axis_defs = loaded_bundle.first_record.get("axes", [])
    sweep_axes = axis_defs[1:] if isinstance(axis_defs, list) else []
    axis_values_lookup: list[tuple[str, tuple[float, ...], str]] = []
    for _axis_index, axis_def in enumerate(sweep_axes, start=1):
        if not isinstance(axis_def, Mapping):
            continue
        axis_name = str(axis_def.get("name", "")).strip()
        axis_unit = str(axis_def.get("unit", "")).strip()
        values = tuple(
            float(value)
            for value in _read_axis_values(
                loaded_bundle.trace_store,
                _require_mapping(
                    loaded_bundle.first_record.get("store_ref"),
                    field_name="store_ref",
                ),
                axis_name=axis_name,
            )
        )
        axis_values_lookup.append((axis_name, values, axis_unit))

    if len(axis_values_lookup) == 0:
        return _simulation_result_from_trace_records(
            trace_records=loaded_bundle.trace_records,
            frequencies_ghz=frequencies,
            axis_indices=(),
        ), None

    points: list[Any] = []
    symbols = _core_symbols()
    sweep_shape = tuple(len(values) for _, values, _ in axis_values_lookup)
    for point_index, axis_indices in enumerate(np.ndindex(*sweep_shape)):
        axis_values = {
            name: float(values[position])
            for (name, values, _), position in zip(axis_values_lookup, axis_indices, strict=False)
        }
        points.append(
            symbols["SimulationSweepPointResult"](
                point_index=point_index,
                axis_indices=tuple(int(value) for value in axis_indices),
                axis_values=axis_values,
                result=_simulation_result_from_trace_records(
                    trace_records=loaded_bundle.trace_records,
                    frequencies_ghz=frequencies,
                    axis_indices=tuple(int(value) for value in axis_indices),
                ),
            )
        )
    sweep_run = symbols["SimulationSweepRun"](
        axes=tuple(
            symbols["SimulationSweepAxis"](
                target_value_ref=name,
                values=values,
                unit=unit,
            )
            for name, values, unit in axis_values_lookup
        ),
        points=tuple(points),
        representative_point_index=0,
    )
    return sweep_run.representative_result, symbols["simulation_sweep_run_to_payload"](sweep_run)


def _simulation_result_from_trace_records(
    *,
    trace_records: Sequence[object],
    frequencies_ghz: np.ndarray,
    axis_indices: tuple[int, ...],
) -> Any:
    symbols = _core_symbols()
    trace_store = symbols["LocalZarrTraceStore"](root_path=symbols["get_trace_store_path"]())
    s_real: dict[str, list[float]] = {}
    s_imag: dict[str, list[float]] = {}
    y_real: dict[str, list[float]] = {}
    y_imag: dict[str, list[float]] = {}
    z_real: dict[str, list[float]] = {}
    z_imag: dict[str, list[float]] = {}
    ports: set[int] = set()
    modes: set[tuple[int, ...]] = set()
    for record in trace_records:
        if not isinstance(record, Mapping):
            continue
        trace_meta = record.get("trace_meta", {})
        if not isinstance(trace_meta, Mapping):
            continue
        output_port = int(trace_meta.get("output_port", 0) or 0)
        input_port = int(trace_meta.get("input_port", 0) or 0)
        output_mode = tuple(int(value) for value in trace_meta.get("output_mode", [])) or (0,)
        input_mode = tuple(int(value) for value in trace_meta.get("input_mode", [])) or (0,)
        ports.update({port for port in (output_port, input_port) if port > 0})
        modes.update({output_mode, input_mode})
        label = str(trace_meta.get("label", "")).strip()
        if len(label) == 0:
            continue
        values = _read_trace_values(
            trace_store,
            _require_mapping(record.get("store_ref"), field_name="store_ref"),
            axis_indices,
        )
        family = str(record.get("family", "")).strip()
        representation = str(record.get("representation", "")).strip()
        if family == "s_matrix":
            target = s_real if representation == "real" else s_imag
        elif family == "y_matrix":
            target = y_real if representation == "real" else y_imag
        elif family == "z_matrix":
            target = z_real if representation == "real" else z_imag
        else:
            continue
        target[label] = [float(value) for value in values]
    normalized_modes = sorted(
        modes,
        key=lambda mode: (len(mode), tuple(mode)),
    ) or [(0,)]
    normalized_ports = sorted(port for port in ports if port > 0) or [1]
    base_mode = next(
        (mode for mode in normalized_modes if all(value == 0 for value in mode)),
        normalized_modes[0],
    )
    first_port = normalized_ports[0]
    s11_label = _mode_trace_label(base_mode, first_port, base_mode, first_port)
    return symbols["SimulationResult"](
        frequencies_ghz=[float(value) for value in frequencies_ghz.tolist()],
        s11_real=list(s_real.get(s11_label, [0.0 for _ in frequencies_ghz])),
        s11_imag=list(s_imag.get(s11_label, [0.0 for _ in frequencies_ghz])),
        port_indices=normalized_ports,
        mode_indices=[tuple(int(value) for value in mode) for mode in normalized_modes],
        s_parameter_real={
            f"S{output_port}{input_port}": values
            for label, values in s_real.items()
            if (parsed := _parse_mode_trace_label(label)) is not None
            and parsed[0] == base_mode
            and parsed[2] == base_mode
            and (output_port := parsed[1]) > 0
            and (input_port := parsed[3]) > 0
        },
        s_parameter_imag={
            f"S{output_port}{input_port}": values
            for label, values in s_imag.items()
            if (parsed := _parse_mode_trace_label(label)) is not None
            and parsed[0] == base_mode
            and parsed[2] == base_mode
            and (output_port := parsed[1]) > 0
            and (input_port := parsed[3]) > 0
        },
        s_parameter_mode_real=s_real,
        s_parameter_mode_imag=s_imag,
        y_parameter_mode_real=y_real,
        y_parameter_mode_imag=y_imag,
        z_parameter_mode_real=z_real,
        z_parameter_mode_imag=z_imag,
        qe_parameter_mode={},
        qe_ideal_parameter_mode={},
        cm_parameter_mode={},
    )


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
        np.zeros((len(labels), len(labels)), dtype=np.complex128)
        for _ in range(len(sample_values))
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
        np.zeros((len(labels), len(labels)), dtype=np.complex128)
        for _ in range(len(sample_values))
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
    selection: tuple[object, ...] = (
        (slice(None), *axis_indices) if axis_indices else (slice(None),)
    )
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


def _sweep_point_count(task: TaskDetail) -> int:
    setup = task.simulation_setup
    if setup is None or len(setup.parameter_sweeps) == 0:
        return 1
    total = 1
    for axis in setup.parameter_sweeps:
        total *= max(len(axis.values), 1)
    return total


def _extract_port_index(token: object) -> int | None:
    if not isinstance(token, str):
        return None
    stripped = token.strip().lower()
    if stripped.startswith("port_") and stripped[5:].isdigit():
        return int(stripped[5:])
    if stripped.startswith("p") and stripped[1:].isdigit():
        return int(stripped[1:])
    return None


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


def _mode_trace_label(
    output_mode: tuple[int, ...],
    output_port: int,
    input_mode: tuple[int, ...],
    input_port: int,
) -> str:
    return f"S{output_port}{input_port}[om={tuple(output_mode)},im={tuple(input_mode)}]"


def _parse_mode_trace_label(label: str) -> tuple[tuple[int, ...], int, tuple[int, ...], int] | None:
    matched = _MODE_TRACE_LABEL_PATTERN.fullmatch(label.strip())
    if matched is None:
        return None
    try:
        output_mode = tuple(
            int(value)
            for value in matched.group("output_mode").strip("() ").split(",")
            if value.strip()
        )
        input_mode = tuple(
            int(value)
            for value in matched.group("input_mode").strip("() ").split(",")
            if value.strip()
        )
    except ValueError:
        return None
    return (
        output_mode or (0,),
        int(matched.group("output_port")),
        input_mode or (0,),
        int(matched.group("input_port")),
    )
