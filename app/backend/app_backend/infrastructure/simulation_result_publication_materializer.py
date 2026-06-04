from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass, replace
from typing import cast

from app_backend.domain.characterization_analysis import (
    evaluate_trace_analysis_capabilities,
)
from app_backend.domain.datasets import TraceAxis, TraceDetail, TraceMetadataSummary
from app_backend.domain.result_traces import (
    ResultTraceSelection,
    build_trace_id,
    build_trace_parameter,
    ptc_available,
    resolve_saved_trace_parameter,
)
from app_backend.domain.tasks import TaskDetail
from app_backend.domain.trace_structures import build_trace_structure_summary
from app_backend.infrastructure.persisted_runtime import (
    available_sources_for_task_family,
    build_trace_preview_payload,
    extract_selection_trace_data,
    extract_selection_trace_nd_data,
    write_nd_complex_trace_payload,
)
from app_backend.infrastructure.storage_reference_factory import (
    build_metadata_record_ref,
    build_result_handle_ref,
    build_result_provenance_ref,
    build_trace_payload_ref,
)


@dataclass(frozen=True)
class MaterializedSimulationPublicationTrace:
    family: str
    source: str
    summary: TraceMetadataSummary
    detail: TraceDetail


def build_simulation_publication_key(
    *,
    task_id: int,
    dataset_id: str,
    design_id: str,
) -> str:
    return f"simulation-publication:{task_id}:{dataset_id}:{design_id}"


def build_simulation_publication_traces(
    *,
    task: TaskDetail,
    dataset_family: str,
    dataset_id: str,
    design_id: str,
) -> tuple[MaterializedSimulationPublicationTrace, ...]:
    traces: list[MaterializedSimulationPublicationTrace] = []
    for family, source in _simulation_publication_targets(task):
        traces.append(
            _materialize_simulation_publication_trace(
                task=task,
                dataset_family=dataset_family,
                dataset_id=dataset_id,
                design_id=design_id,
                family=family,
                source=source,
            )
        )
    return tuple(traces)


def build_result_trace_publication_detail(
    *,
    task: TaskDetail,
    basis_task: TaskDetail,
    dataset_id: str,
    design_id: str,
    selection: ResultTraceSelection,
    parameter_name: str | None = None,
) -> TraceDetail:
    point_count = (
        basis_task.simulation_setup.frequency_sweep.point_count
        if basis_task.simulation_setup is not None
        else 1
    )
    saved_parameter = resolve_saved_trace_parameter(selection, parameter_name)
    trace_id = build_trace_id(
        task_id=task.task_id,
        selection=selection,
        parameter_name=saved_parameter,
    )
    trace_batch_record = build_metadata_record_ref(
        "trace_batch",
        f"trace_batch:published:{task.task_id}:{dataset_id}:{design_id}",
        version=1,
    )
    result_handle_record = build_metadata_record_ref(
        "result_handle",
        f"result_handle:published:{task.task_id}:{trace_id}",
        version=2,
    )
    preview_points = _build_preview_points(basis_task=basis_task, selection=selection)
    return TraceDetail(
        trace_id=trace_id,
        dataset_id=dataset_id,
        design_id=design_id,
        axes=(TraceAxis(name="frequency", unit="GHz", length=point_count),),
        preview_payload={
            "kind": "series",
            "family": selection.family,
            "source": selection.source,
            "parameter": saved_parameter,
            "default_parameter": build_trace_parameter(selection),
            "output_port": selection.output_port,
            "input_port": selection.input_port,
            "trace_mode_group": selection.trace_mode_group,
            "output_mode": selection.output_mode,
            "input_mode": selection.input_mode,
            "trace_key": selection.to_trace_key(),
            "history_steps": _build_trace_history_steps(task=task, selection=selection),
            "history_summary": _build_trace_history_summary(task=task, selection=selection),
            "points": preview_points,
        },
        payload_ref=build_trace_payload_ref(
            payload_role="dataset_primary",
            store_key=(
                f"datasets/{dataset_id}/designs/{design_id}/result-traces/"
                f"task_{task.task_id}/{trace_id}.zarr"
            ),
            store_uri=(
                f"trace_store/datasets/{dataset_id}/designs/{design_id}/"
                f"result-traces/task_{task.task_id}/{trace_id}.zarr"
            ),
            group_path=f"/datasets/{dataset_id}/designs/{design_id}/result_traces",
            array_path=trace_id,
            dtype="complex64",
            shape=(point_count, 2),
            chunk_shape=(min(point_count, 64), 2),
        ),
        result_handles=(
            build_result_handle_ref(
                handle_id=f"published-result:{task.task_id}:{trace_id}",
                kind="simulation_trace",
                status="materialized",
                label=(f"Published {saved_parameter} {selection.source.upper()} trace"),
                metadata_record=result_handle_record,
                payload_backend="local_zarr",
                payload_format="zarr",
                payload_role="trace_payload",
                payload_locator=(
                    f"trace_store/datasets/{dataset_id}/designs/{design_id}/"
                    f"result-traces/task_{task.task_id}/{trace_id}.zarr"
                ),
                provenance_task_id=task.task_id,
                provenance=build_result_provenance_ref(
                    source_dataset_id=task.dataset_id,
                    source_task_id=task.task_id,
                    trace_batch_record=trace_batch_record,
                ),
            ),
        ),
    )


def build_result_trace_publication_summary(
    *,
    task: TaskDetail,
    detail: TraceDetail,
    selection: ResultTraceSelection,
    parameter_name: str | None = None,
) -> TraceMetadataSummary:
    saved_parameter = resolve_saved_trace_parameter(selection, parameter_name)
    return TraceMetadataSummary(
        trace_id=detail.trace_id,
        dataset_id=detail.dataset_id,
        design_id=detail.design_id,
        family=selection.family,
        parameter=saved_parameter,
        representation="complex",
        trace_mode_group=selection.trace_mode_group,
        source_kind="circuit_simulation",
        stage_kind=_stage_kind_for_trace(task=task, selection=selection),
        provenance_summary=_provenance_summary_for_trace(task=task, selection=selection),
    )


def _build_preview_points(
    *,
    basis_task: TaskDetail,
    selection: ResultTraceSelection,
) -> list[list[float]]:
    if basis_task.simulation_setup is None:
        return []
    port_count = max(
        selection.output_port,
        selection.input_port,
        *_setup_port_indices(basis_task),
        1,
    )
    z0_ohm = selection.z0_ohm or 50.0
    frequencies = _frequency_values(basis_task.simulation_setup)
    compensated_ports = _compensated_port_indices(basis_task)
    family_bundle = _build_family_bundle(
        basis_task,
        port_count=port_count,
        compensated_ports=compensated_ports,
        sweep_index=selection.sweep_index,
        z0_ohm=z0_ohm,
    )
    matrices = family_bundle[selection.family][selection.source]
    row_index = selection.output_port - 1
    column_index = selection.input_port - 1
    return [
        [
            round(frequency, 6),
            round(matrix[row_index][column_index].real, 6),
            round(matrix[row_index][column_index].imag, 6),
        ]
        for frequency, matrix in zip(frequencies, matrices, strict=True)
    ]


def _stage_kind_for_trace(*, task: TaskDetail, selection: ResultTraceSelection) -> str:
    if task.kind == "post_processing":
        return "postprocess"
    if selection.source == "ptc" or selection.family in {"y_matrix", "z_matrix"}:
        return "postprocess"
    return "raw"


def _provenance_summary_for_trace(
    *,
    task: TaskDetail,
    selection: ResultTraceSelection,
) -> str:
    if task.kind == "post_processing":
        return (
            f"Published from post-processing task {task.task_id} "
            f"({selection.source.upper()} {build_trace_parameter(selection)})"
        )
    return f"Published from simulation task {task.task_id}"


def _simulation_publication_targets(task: TaskDetail) -> tuple[tuple[str, str], ...]:
    targets: list[tuple[str, str]] = []
    if "raw" in available_sources_for_task_family(task, "s_matrix"):
        targets.append(("s_matrix", "raw"))
    if "raw" in available_sources_for_task_family(task, "y_matrix"):
        targets.append(("y_matrix", "raw"))
    if "raw" in available_sources_for_task_family(task, "z_matrix"):
        targets.append(("z_matrix", "raw"))
    if "ptc" in available_sources_for_task_family(task, "y_matrix"):
        targets.append(("y_matrix", "ptc"))
    if "ptc" in available_sources_for_task_family(task, "z_matrix"):
        targets.append(("z_matrix", "ptc"))
    return tuple(targets)


def _materialize_simulation_publication_trace(
    *,
    task: TaskDetail,
    dataset_family: str,
    dataset_id: str,
    design_id: str,
    family: str,
    source: str,
) -> MaterializedSimulationPublicationTrace:
    selection = ResultTraceSelection(
        family=family,
        source=source,
        output_port=1,
        input_port=1,
        z0_ohm=50.0 if family in {"y_matrix", "z_matrix"} else None,
    )
    trace_data = extract_selection_trace_data(
        task,
        basis_task=task,
        selection=selection,
    )
    nd_trace_data = extract_selection_trace_nd_data(
        task,
        basis_task=task,
        selection=selection,
    )
    trace_id = f"trace_simulation_task_{task.task_id}_{family}_{source}"
    payload_ref = write_nd_complex_trace_payload(
        dataset_id=dataset_id,
        design_id=design_id,
        trace_id=trace_id,
        axes=nd_trace_data.axes,
        values=nd_trace_data.values,
    )
    trace_batch_record = build_metadata_record_ref(
        "trace_batch",
        f"trace_batch:published:{task.task_id}:{dataset_id}:{design_id}",
        version=1,
    )
    result_handle_record = build_metadata_record_ref(
        "result_handle",
        f"result_handle:published:{task.task_id}:{family}:{source}",
        version=2,
    )
    result_handle = build_result_handle_ref(
        handle_id=f"published-result:{task.task_id}:{family}:{source}",
        kind="simulation_trace",
        status="materialized",
        label=f"Published {family.upper()} {source.upper()} result",
        metadata_record=result_handle_record,
        payload_backend="local_zarr",
        payload_format="zarr",
        payload_role="trace_payload",
        payload_locator=payload_ref.store_uri or payload_ref.store_key,
        provenance_task_id=task.task_id,
        provenance=build_result_provenance_ref(
            source_dataset_id=task.dataset_id,
            source_task_id=task.task_id,
            trace_batch_record=trace_batch_record,
        ),
    )
    axes = tuple(
        TraceAxis(
            name=str(axis["name"]),
            unit=str(axis["unit"]),
            length=int(axis["length"]),
        )
        for axis in nd_trace_data.axes
    )
    structure = build_trace_structure_summary(
        dataset_id=dataset_id,
        design_id=design_id,
        family=selection.family,
        parameter=source,
        representation="complex_matrix",
        trace_mode_group=selection.trace_mode_group,
        source_kind=cast(str, nd_trace_data.source_kind),
        stage_kind=cast(str, nd_trace_data.stage_kind),
        axes=nd_trace_data.axes,
    )
    summary = TraceMetadataSummary(
        trace_id=trace_id,
        dataset_id=dataset_id,
        design_id=design_id,
        family=selection.family,
        parameter=source,
        representation="complex_matrix",
        trace_mode_group=selection.trace_mode_group,
        source_kind=cast(str, nd_trace_data.source_kind),
        stage_kind=cast(str, nd_trace_data.stage_kind),
        ndim=structure.ndim,
        shape=structure.shape,
        axes_summary=structure.axes_summary,
        axis_signature=structure.axis_signature,
        available_sweep_axes=structure.available_sweep_axes,
        collection_projection=structure.collection_projection,
        provenance_summary=f"Published from simulation task {task.task_id}",
    )
    analysis_capabilities = evaluate_trace_analysis_capabilities(
        dataset_family=dataset_family,
        trace=summary,
        axes=axes,
    )
    preview = build_trace_preview_payload(
        selection=selection,
        trace_data=trace_data,
    )
    preview["kind"] = "series"
    preview["family"] = selection.family
    preview["source"] = selection.source
    preview["parameter"] = source
    preview["default_parameter"] = build_trace_parameter(selection)
    preview["output_port"] = selection.output_port
    preview["input_port"] = selection.input_port
    preview["trace_mode_group"] = selection.trace_mode_group
    preview["output_mode"] = selection.output_mode
    preview["input_mode"] = selection.input_mode
    preview["history_steps"] = _build_trace_history_steps(task=task, selection=selection)
    preview["history_summary"] = " -> ".join(preview["history_steps"])
    preview["points"] = [
        [float(frequency), float(value.real), float(value.imag)]
        for frequency, value in zip(
            trace_data.frequencies_ghz,
            trace_data.values,
            strict=True,
        )
    ]
    detail = TraceDetail(
        trace_id=trace_id,
        dataset_id=dataset_id,
        design_id=design_id,
        family=selection.family,
        parameter=summary.parameter,
        representation=summary.representation,
        trace_mode_group=selection.trace_mode_group,
        source_kind=cast(str, nd_trace_data.source_kind),
        stage_kind=cast(str, nd_trace_data.stage_kind),
        axes=axes,
        ndim=structure.ndim,
        shape=structure.shape,
        axes_summary=structure.axes_summary,
        axis_signature=structure.axis_signature,
        available_sweep_axes=structure.available_sweep_axes,
        collection_projection=structure.collection_projection,
        preview_payload=preview,
        payload_ref=payload_ref,
        result_handles=(result_handle,),
        analysis_capabilities=analysis_capabilities,
    )
    return MaterializedSimulationPublicationTrace(
        family=family,
        source=source,
        summary=replace(summary, analysis_capabilities=analysis_capabilities),
        detail=detail,
    )


def _build_trace_history_steps(
    *,
    task: TaskDetail,
    selection: ResultTraceSelection,
) -> list[str]:
    history = ["PTC" if selection.source == "ptc" else "Raw"]
    if task.kind != "post_processing" or task.post_processing_setup is None:
        return history

    for operation in task.post_processing_setup.operations:
        if not operation.enabled:
            continue
        history.append(_humanize_post_processing_operation(operation.operation))
    return history


def _build_trace_history_summary(
    *,
    task: TaskDetail,
    selection: ResultTraceSelection,
) -> str:
    return " -> ".join(_build_trace_history_steps(task=task, selection=selection))


def _humanize_post_processing_operation(operation: str) -> str:
    if operation == "coordinate_transform":
        return "Coordinate Transformation"
    if operation == "kron_reduction":
        return "Kron Reduction"
    return operation.replace("_", " ").title()


def _setup_port_indices(task: TaskDetail) -> tuple[int, ...]:
    if task.simulation_setup is None:
        return ()
    indices: set[int] = set()
    for source in task.simulation_setup.sources:
        port_index = _extract_port_index(source.target)
        if port_index is not None:
            indices.add(port_index)
    if task.simulation_setup.ptc is not None:
        for port in task.simulation_setup.ptc.compensate_ports:
            port_index = _extract_port_index(port)
            if port_index is not None:
                indices.add(port_index)
    return tuple(sorted(indices))


def _extract_port_index(token: object) -> int | None:
    if not isinstance(token, str):
        return None
    stripped = token.strip().lower()
    if stripped.startswith("port_") and stripped[5:].isdigit():
        return int(stripped[5:])
    if stripped.startswith("p") and stripped[1:].isdigit():
        return int(stripped[1:])
    return None


def _compensated_port_indices(task: TaskDetail) -> set[int]:
    if task.simulation_setup is None or task.simulation_setup.ptc is None:
        return set()
    return {
        port_index
        for label in task.simulation_setup.ptc.compensate_ports
        if (port_index := _extract_port_index(label)) is not None
    }


def _frequency_values(setup) -> list[float]:
    point_count = max(setup.frequency_sweep.point_count, 1)
    start = setup.frequency_sweep.start_ghz
    stop = setup.frequency_sweep.stop_ghz
    if point_count == 1:
        return [round(start, 6)]
    step = (stop - start) / (point_count - 1)
    return [round(start + (step * index), 6) for index in range(point_count)]


def _build_family_bundle(
    task: TaskDetail,
    *,
    port_count: int,
    compensated_ports: set[int],
    sweep_index: int | None,
    z0_ohm: float,
) -> dict[str, dict[str, list[list[list[complex]]]]]:
    assert task.simulation_setup is not None
    frequencies = _frequency_values(task.simulation_setup)
    raw_s = [
        _build_s_matrix(
            frequency,
            task=task,
            port_count=port_count,
            sweep_index=sweep_index,
        )
        for frequency in frequencies
    ]
    raw_z = [_matrix_to_z(matrix, z0_ohm=z0_ohm) for matrix in raw_s]
    raw_y = [_matrix_to_y(matrix, z0_ohm=z0_ohm) for matrix in raw_s]
    family_bundle: dict[str, dict[str, list[list[list[complex]]]]] = {
        "s_matrix": {"raw": raw_s},
        "y_matrix": {"raw": raw_y},
        "z_matrix": {"raw": raw_z},
    }
    if ptc_available(task):
        family_bundle["y_matrix"]["ptc"] = [
            _apply_port_compensation(matrix, compensated_ports, scale=0.94) for matrix in raw_y
        ]
        family_bundle["z_matrix"]["ptc"] = [
            _apply_port_compensation(matrix, compensated_ports, scale=1.06) for matrix in raw_z
        ]
    return family_bundle


def _build_s_matrix(
    frequency_ghz: float,
    *,
    task: TaskDetail,
    port_count: int,
    sweep_index: int | None,
) -> list[list[complex]]:
    setup = task.simulation_setup
    assert setup is not None
    sweep_bias = _resolve_sweep_bias(setup, sweep_index)
    center = (setup.frequency_sweep.start_ghz + setup.frequency_sweep.stop_ghz) / 2
    span = max(setup.frequency_sweep.stop_ghz - setup.frequency_sweep.start_ghz, 0.1)
    center += sweep_bias * (span / 6)
    width = max((span / 7) * (1 + (0.18 * sweep_bias)), 0.12)
    normalized = (frequency_ghz - center) / span
    lorentz = 1 / math.sqrt(1 + ((frequency_ghz - center) / width) ** 2)
    phase = normalized * math.pi

    matrix: list[list[complex]] = []
    for output_index in range(port_count):
        row: list[complex] = []
        for input_index in range(port_count):
            port_distance = abs(output_index - input_index)
            if output_index == input_index:
                amplitude = 0.22 + (0.04 * output_index) - (0.18 * lorentz) + (0.012 * sweep_bias)
                angle = phase * (1 + (0.1 * output_index))
            else:
                amplitude = ((0.72 / (1 + port_distance)) * lorentz) * (1 + (0.08 * sweep_bias))
                angle = -phase * (1 + (0.08 * (output_index + input_index)))
            row.append(complex(amplitude * math.cos(angle), amplitude * math.sin(angle)))
        matrix.append(row)
    return matrix


def _matrix_to_z(
    matrix_s: list[list[complex]],
    *,
    z0_ohm: float,
) -> list[list[complex]]:
    identity = _identity_matrix(len(matrix_s))
    numerator = _matrix_add(identity, matrix_s)
    denominator = _matrix_subtract(identity, matrix_s)
    return _matrix_scale(_matrix_multiply(numerator, _matrix_inverse(denominator)), z0_ohm)


def _matrix_to_y(
    matrix_s: list[list[complex]],
    *,
    z0_ohm: float,
) -> list[list[complex]]:
    identity = _identity_matrix(len(matrix_s))
    numerator = _matrix_subtract(identity, matrix_s)
    denominator = _matrix_add(identity, matrix_s)
    return _matrix_scale(_matrix_multiply(numerator, _matrix_inverse(denominator)), 1 / z0_ohm)


def _apply_port_compensation(
    matrix: list[list[complex]],
    compensated_ports: set[int],
    *,
    scale: float,
) -> list[list[complex]]:
    updated = [[value for value in row] for row in matrix]
    for port_index in compensated_ports:
        idx = port_index - 1
        if idx < 0 or idx >= len(updated):
            continue
        updated[idx][idx] *= scale
        for neighbor in range(len(updated)):
            if neighbor == idx:
                continue
            coupling_scale = 1 - ((abs(scale - 1.0)) / 2)
            updated[idx][neighbor] *= coupling_scale
            updated[neighbor][idx] *= coupling_scale
    return updated


def _resolve_sweep_bias(setup, sweep_index: int | None) -> float:
    parameter_sweeps = getattr(setup, "parameter_sweeps", ())
    if len(parameter_sweeps) == 0:
        return 0.0

    resolved_index = sweep_index if sweep_index is not None else 0
    coordinates = [0] * len(parameter_sweeps)
    remaining = resolved_index
    for axis_index in range(len(parameter_sweeps) - 1, -1, -1):
        axis_size = max(len(parameter_sweeps[axis_index].values), 1)
        coordinates[axis_index] = remaining % axis_size
        remaining //= axis_size

    bias = 0.0
    for axis_index, (sweep, value_index) in enumerate(
        zip(parameter_sweeps, coordinates, strict=False)
    ):
        if len(sweep.values) == 0:
            continue
        if len(sweep.values) == 1:
            normalized = 0.0
        else:
            min_value = min(sweep.values)
            max_value = max(sweep.values)
            span = max(max_value - min_value, 1e-9)
            normalized = ((sweep.values[value_index] - min_value) / span) - 0.5
        bias += normalized * (1 + (0.15 * axis_index))
    return bias


def _identity_matrix(size: int) -> list[list[complex]]:
    return [[1 + 0j if row == column else 0 + 0j for column in range(size)] for row in range(size)]


def _matrix_add(
    left: Sequence[Sequence[complex]],
    right: Sequence[Sequence[complex]],
) -> list[list[complex]]:
    return [
        [left[row][column] + right[row][column] for column in range(len(left[row]))]
        for row in range(len(left))
    ]


def _matrix_subtract(
    left: Sequence[Sequence[complex]],
    right: Sequence[Sequence[complex]],
) -> list[list[complex]]:
    return [
        [left[row][column] - right[row][column] for column in range(len(left[row]))]
        for row in range(len(left))
    ]


def _matrix_scale(
    matrix: Sequence[Sequence[complex]],
    scale: float,
) -> list[list[complex]]:
    return [[value * scale for value in row] for row in matrix]


def _matrix_multiply(
    left: Sequence[Sequence[complex]],
    right: Sequence[Sequence[complex]],
) -> list[list[complex]]:
    size = len(left)
    return [
        [sum(left[row][idx] * right[idx][column] for idx in range(size)) for column in range(size)]
        for row in range(size)
    ]


def _matrix_inverse(matrix: Sequence[Sequence[complex]]) -> list[list[complex]]:
    size = len(matrix)
    augmented = [
        [complex(matrix[row][column]) for column in range(size)]
        + [1 + 0j if row == column else 0 + 0j for column in range(size)]
        for row in range(size)
    ]
    for pivot_index in range(size):
        pivot = augmented[pivot_index][pivot_index]
        if abs(pivot) < 1e-12:
            swap_index = next(
                (
                    row_index
                    for row_index in range(pivot_index + 1, size)
                    if abs(augmented[row_index][pivot_index]) >= 1e-12
                ),
                None,
            )
            if swap_index is None:
                raise ValueError("matrix is singular")
            augmented[pivot_index], augmented[swap_index] = (
                augmented[swap_index],
                augmented[pivot_index],
            )
            pivot = augmented[pivot_index][pivot_index]
        augmented[pivot_index] = [value / pivot for value in augmented[pivot_index]]
        for row_index in range(size):
            if row_index == pivot_index:
                continue
            factor = augmented[row_index][pivot_index]
            augmented[row_index] = [
                augmented[row_index][column] - (factor * augmented[pivot_index][column])
                for column in range(size * 2)
            ]
    return [row[size:] for row in augmented]
