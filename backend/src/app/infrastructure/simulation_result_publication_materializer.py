from __future__ import annotations

import math
from collections.abc import Sequence

from src.app.domain.datasets import TraceAxis, TraceDetail, TraceMetadataSummary
from src.app.domain.result_traces import (
    ResultTraceSelection,
    build_trace_id,
    build_trace_parameter,
    ptc_available,
)
from src.app.domain.tasks import TaskDetail
from src.app.infrastructure.storage_reference_factory import (
    build_metadata_record_ref,
    build_result_handle_ref,
    build_result_provenance_ref,
    build_trace_payload_ref,
)


def build_simulation_publication_key(
    *,
    task_id: int,
    dataset_id: str,
    design_id: str,
) -> str:
    return f"simulation-publication:{task_id}:{dataset_id}:{design_id}"


def build_simulation_publication_trace_details(
    *,
    task: TaskDetail,
    dataset_id: str,
    design_id: str,
) -> tuple[tuple[str, str, TraceDetail], ...]:
    point_count = (
        task.simulation_setup.frequency_sweep.point_count
        if task.simulation_setup is not None
        else 1
    )
    published_families: list[tuple[str, str, str]] = [
        ("s_matrix", "raw", "raw"),
        ("y_matrix", "raw", "postprocess"),
        ("z_matrix", "raw", "postprocess"),
    ]
    if (
        task.simulation_setup is not None
        and task.simulation_setup.ptc is not None
        and task.simulation_setup.ptc.enabled
    ):
        published_families.extend(
            [
                ("y_matrix", "ptc", "postprocess"),
                ("z_matrix", "ptc", "postprocess"),
            ]
        )
    trace_batch_record = build_metadata_record_ref(
        "trace_batch",
        f"trace_batch:published:{task.task_id}:{dataset_id}:{design_id}",
        version=1,
    )
    details: list[tuple[str, str, TraceDetail]] = []
    for family, source, _stage_kind in published_families:
        trace_id = f"trace_simulation_task_{task.task_id}_{family}_{source}"
        result_handle_record = build_metadata_record_ref(
            "result_handle",
            f"result_handle:published:{task.task_id}:{family}:{source}",
            version=2,
        )
        details.append(
            (
                family,
                source,
                TraceDetail(
                    trace_id=trace_id,
                    dataset_id=dataset_id,
                    design_id=design_id,
                    axes=(TraceAxis(name="frequency", unit="GHz", length=point_count),),
                    preview_payload={
                        "kind": "sampled_series",
                        "source": source,
                        "family": family,
                        "points": [
                            [1.0, 0.11],
                            [2.0, 0.18],
                            [3.0, 0.15],
                        ],
                    },
                    payload_ref=build_trace_payload_ref(
                        payload_role="dataset_primary",
                        store_key=(
                            f"datasets/{dataset_id}/designs/{design_id}/simulation-results/"
                            f"task_{task.task_id}/{trace_id}.zarr"
                        ),
                        store_uri=(
                            f"trace_store/datasets/{dataset_id}/designs/{design_id}/"
                            f"simulation-results/task_{task.task_id}/{trace_id}.zarr"
                        ),
                        group_path=(
                            f"/datasets/{dataset_id}/designs/{design_id}/simulation_results"
                        ),
                        array_path=trace_id,
                        dtype="complex64",
                        shape=(point_count, 2),
                        chunk_shape=(min(point_count, 64), 2),
                    ),
                    result_handles=(
                        build_result_handle_ref(
                            handle_id=f"published-result:{task.task_id}:{family}:{source}",
                            kind="simulation_trace",
                            status="materialized",
                            label=f"Published {family.upper()} {source.upper()} result",
                            metadata_record=result_handle_record,
                            payload_backend="local_zarr",
                            payload_format="zarr",
                            payload_role="trace_payload",
                            payload_locator=(
                                f"trace_store/datasets/{dataset_id}/designs/{design_id}/"
                                f"simulation-results/task_{task.task_id}/{trace_id}.zarr"
                            ),
                            provenance_task_id=task.task_id,
                            provenance=build_result_provenance_ref(
                                source_dataset_id=task.dataset_id,
                                source_task_id=task.task_id,
                                trace_batch_record=trace_batch_record,
                            ),
                        ),
                    ),
                ),
            )
        )
    return tuple(details)


def build_simulation_publication_trace_summary(
    *,
    detail: TraceDetail,
    task: TaskDetail,
    family: str,
    source: str,
) -> TraceMetadataSummary:
    return TraceMetadataSummary(
        trace_id=detail.trace_id,
        dataset_id=detail.dataset_id,
        design_id=detail.design_id,
        family=family,
        parameter=source,
        representation="complex_matrix",
        trace_mode_group="base",
        source_kind="circuit_simulation",
        stage_kind=(
            "postprocess"
            if source == "ptc" or family in {"y_matrix", "z_matrix"}
            else "raw"
        ),
        provenance_summary=f"Published from simulation task {task.task_id}",
    )


def build_result_trace_publication_detail(
    *,
    task: TaskDetail,
    basis_task: TaskDetail,
    dataset_id: str,
    design_id: str,
    selection: ResultTraceSelection,
) -> TraceDetail:
    point_count = (
        basis_task.simulation_setup.frequency_sweep.point_count
        if basis_task.simulation_setup is not None
        else 1
    )
    trace_id = build_trace_id(task_id=task.task_id, selection=selection)
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
            "kind": "sampled_series",
            "family": selection.family,
            "source": selection.source,
            "parameter": build_trace_parameter(selection),
            "output_port": selection.output_port,
            "input_port": selection.input_port,
            "trace_mode_group": selection.trace_mode_group,
            "output_mode": selection.output_mode,
            "input_mode": selection.input_mode,
            "trace_key": selection.to_trace_key(),
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
                label=(
                    "Published "
                    f"{build_trace_parameter(selection)} "
                    f"{selection.source.upper()} trace"
                ),
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
) -> TraceMetadataSummary:
    return TraceMetadataSummary(
        trace_id=detail.trace_id,
        dataset_id=detail.dataset_id,
        design_id=detail.design_id,
        family=selection.family,
        parameter=build_trace_parameter(selection),
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
        z0_ohm=z0_ohm,
    )
    matrices = family_bundle[selection.family][selection.source]
    row_index = selection.output_port - 1
    column_index = selection.input_port - 1
    sampled_indices = _sample_indices(len(frequencies))
    return [
        [
            round(frequencies[index], 6),
            round(matrices[index][row_index][column_index].real, 6),
            round(matrices[index][row_index][column_index].imag, 6),
        ]
        for index in sampled_indices
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


def _sample_indices(length: int) -> list[int]:
    if length <= 3:
        return list(range(length))
    middle = length // 2
    return [0, middle, length - 1]


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
    z0_ohm: float,
) -> dict[str, dict[str, list[list[list[complex]]]]]:
    assert task.simulation_setup is not None
    frequencies = _frequency_values(task.simulation_setup)
    raw_s = [
        _build_s_matrix(frequency, task=task, port_count=port_count)
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
            _apply_port_compensation(matrix, compensated_ports, scale=0.94)
            for matrix in raw_y
        ]
        family_bundle["z_matrix"]["ptc"] = [
            _apply_port_compensation(matrix, compensated_ports, scale=1.06)
            for matrix in raw_z
        ]
    return family_bundle


def _build_s_matrix(
    frequency_ghz: float,
    *,
    task: TaskDetail,
    port_count: int,
) -> list[list[complex]]:
    setup = task.simulation_setup
    assert setup is not None
    center = (setup.frequency_sweep.start_ghz + setup.frequency_sweep.stop_ghz) / 2
    span = max(setup.frequency_sweep.stop_ghz - setup.frequency_sweep.start_ghz, 0.1)
    width = max(span / 7, 0.12)
    normalized = (frequency_ghz - center) / span
    lorentz = 1 / math.sqrt(1 + ((frequency_ghz - center) / width) ** 2)
    phase = normalized * math.pi

    matrix: list[list[complex]] = []
    for output_index in range(port_count):
        row: list[complex] = []
        for input_index in range(port_count):
            port_distance = abs(output_index - input_index)
            if output_index == input_index:
                amplitude = 0.22 + (0.04 * output_index) - (0.18 * lorentz)
                angle = phase * (1 + (0.1 * output_index))
            else:
                amplitude = (0.72 / (1 + port_distance)) * lorentz
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


def _identity_matrix(size: int) -> list[list[complex]]:
    return [
        [1 + 0j if row == column else 0 + 0j for column in range(size)]
        for row in range(size)
    ]


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
    return [
        [value * scale for value in row]
        for row in matrix
    ]


def _matrix_multiply(
    left: Sequence[Sequence[complex]],
    right: Sequence[Sequence[complex]],
) -> list[list[complex]]:
    size = len(left)
    return [
        [
            sum(left[row][idx] * right[idx][column] for idx in range(size))
            for column in range(size)
        ]
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
