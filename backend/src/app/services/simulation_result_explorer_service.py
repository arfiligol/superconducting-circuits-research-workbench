from __future__ import annotations

import ast
import math
import re
from collections.abc import Mapping, Sequence

from src.app.domain.result_traces import (
    ResultTraceSelection,
    available_sources_for_family,
    ptc_available,
    resolve_port_options,
)
from src.app.domain.tasks import SimulationSetup, TaskDetail
from src.app.services.service_errors import service_error
from src.app.services.task_service import TaskService

_FAMILY_LABELS = {
    "s_matrix": "S Matrix",
    "y_matrix": "Y Matrix",
    "z_matrix": "Z Matrix",
}
_SOURCE_LABELS = {
    "raw": "Raw",
    "ptc": "PTC",
}
_DEFINITION_PORT_PATTERN = re.compile(r"^P(\d+)$", re.IGNORECASE)
_SETUP_PORT_PATTERN = re.compile(r"^(?:port_|P)(\d+)$", re.IGNORECASE)
_FAMILY_METRICS = {
    "s_matrix": {
        "magnitude_db": {"label": "Magnitude (dB)", "unit": "dB"},
        "phase_deg": {"label": "Phase (deg)", "unit": "deg"},
        "real": {"label": "Real", "unit": "unitless"},
        "imag": {"label": "Imaginary", "unit": "unitless"},
    },
    "y_matrix": {
        "magnitude": {"label": "Magnitude", "unit": "S"},
        "real": {"label": "Real", "unit": "S"},
        "imag": {"label": "Imaginary", "unit": "S"},
    },
    "z_matrix": {
        "magnitude": {"label": "Magnitude", "unit": "ohm"},
        "real": {"label": "Real", "unit": "ohm"},
        "imag": {"label": "Imaginary", "unit": "ohm"},
    },
}


class SimulationResultExplorerService:
    def __init__(self, task_service: TaskService) -> None:
        self._task_service = task_service

    def get_explorer_payload(
        self,
        task_id: int,
        *,
        family: str | None = None,
        source: str | None = None,
        metric: str | None = None,
        sweep_index: int | None = None,
        z0_ohm: float | None = None,
        output_port: int | None = None,
        input_port: int | None = None,
    ) -> dict[str, object]:
        task = self._task_service.get_task(task_id)
        self._ensure_task_ready_for_explorer(task)
        basis_task = _resolve_basis_task(task, task_service=self._task_service)

        port_options = resolve_port_options(
            basis_task,
            definition=self._task_service.get_circuit_definition(basis_task.definition_id),
        )
        compensated_ports = _compensated_port_indices(basis_task, available_ports=port_options)
        default_selection = _default_selection(task, basis_task, port_options)
        selection = _resolve_selection(
            task,
            basis_task,
            family=family,
            source=source,
            metric=metric,
            sweep_index=sweep_index,
            z0_ohm=z0_ohm,
            output_port=output_port,
            input_port=input_port,
            port_options=port_options,
            default_selection=default_selection,
        )
        response = _build_explorer_response(
            task,
            basis_task=basis_task,
            selection=selection,
            port_options=port_options,
            compensated_ports=compensated_ports,
            default_selection=default_selection,
        )
        return {
            "task_id": task.task_id,
            "task_status": task.status,
            "runtime_mode": "local" if task.visibility_scope == "local" else "online",
            "bootstrap": response["bootstrap"],
            "selection": response["selection"],
            "plot": response["plot"],
            "result_basis": {
                "trace_payload_available": task.result_refs.trace_payload is not None,
                "primary_result_handle_id": (
                    task.result_refs.result_handles[0].handle_id
                    if len(task.result_refs.result_handles) > 0
                    else None
                ),
                "trace_batch_id": task.result_refs.trace_batch_id,
            },
        }

    def _ensure_task_ready_for_explorer(self, task: TaskDetail) -> None:
        if task.kind not in {"simulation", "post_processing"}:
            raise service_error(
                409,
                code="simulation_result_explorer_task_invalid",
                category="conflict",
                message=(
                    "Simulation result explorer only supports simulation and post-processing tasks."
                ),
            )
        if task.status in {"failed", "cancelled", "terminated"}:
            raise service_error(
                409,
                code="simulation_result_explorer_unavailable",
                category="conflict",
                message="Simulation result explorer is unavailable for terminal non-success tasks.",
            )
        handoff = self._task_service.get_task_result_handoff(task.task_id)
        if handoff.availability != "ready":
            raise service_error(
                409,
                code="simulation_result_explorer_not_ready",
                category="conflict",
                message="Simulation results are not available for explorer access yet.",
            )
        if task.kind == "simulation" and task.simulation_setup is None:
            raise service_error(
                409,
                code="simulation_result_explorer_setup_missing",
                category="conflict",
                message="Simulation result explorer requires persisted simulation_setup.",
            )


def _build_explorer_response(
    task: TaskDetail,
    *,
    basis_task: TaskDetail,
    selection: dict[str, object],
    port_options: dict[int, str],
    compensated_ports: set[int],
    default_selection: dict[str, object],
) -> dict[str, object]:
    family = str(selection["family"])
    source = str(selection["source"])
    metric = str(selection["metric"])
    sweep_index = (
        int(selection["sweep_index"])
        if selection.get("sweep_index") is not None
        else None
    )
    z0_ohm = float(selection["z0_ohm"])
    output_port = int(selection["output_port"])
    input_port = int(selection["input_port"])

    frequencies = _frequency_values(basis_task.simulation_setup)
    family_bundle = _build_family_bundle(
        basis_task,
        port_count=len(port_options),
        compensated_ports=compensated_ports,
        sweep_index=sweep_index,
        z0_ohm=z0_ohm,
    )
    selected_values = _extract_metric_values(
        family_bundle[family][source],
        metric=metric,
        output_port=output_port,
        input_port=input_port,
    )
    metric_config = _FAMILY_METRICS[family][metric]
    output_label = port_options[output_port]
    input_label = port_options[input_port]

    default_selection_payload: dict[str, object] = {
        **{
            key: value
            for key, value in default_selection.items()
            if not (key == "sweep_index" and value is None)
        },
        "trace_key": _build_trace_selection(default_selection).to_trace_key(),
    }
    selection_payload: dict[str, object] = {
        **{
            key: value
            for key, value in selection.items()
            if not (key == "sweep_index" and value is None)
        },
        "trace_mode_group": "base",
        "output_port_label": output_label,
        "input_port_label": input_label,
        "output_mode": "mode_0",
        "input_mode": "mode_0",
        "trace_key": _build_trace_selection(selection).to_trace_key(),
    }
    plot_metadata: dict[str, object] = {
        "trace_key": _build_trace_selection(selection).to_trace_key(),
        "family": family,
        "source": source,
        "metric": metric,
        "z0_ohm": z0_ohm,
        "output_port": output_port,
        "input_port": input_port,
        "output_port_label": output_label,
        "input_port_label": input_label,
        "trace_payload_store_key": (
            task.result_refs.trace_payload.store_key
            if task.result_refs.trace_payload is not None
            else None
        ),
    }
    if sweep_index is not None:
        default_selection_payload["sweep_index"] = sweep_index
        selection_payload["sweep_index"] = sweep_index
        plot_metadata["sweep_index"] = sweep_index

    return {
        "bootstrap": {
            "families": [
                {
                    "key": family_key,
                    "label": _FAMILY_LABELS[family_key],
                    "available_sources": [
                        {"key": source_key, "label": _SOURCE_LABELS[source_key]}
                        for source_key in _available_sources_for_task(
                            task,
                            basis_task,
                            family_key,
                        )
                    ],
                    "available_metrics": [
                        {
                            "key": metric_key,
                            "label": config["label"],
                            "unit": config["unit"],
                        }
                        for metric_key, config in _FAMILY_METRICS[family_key].items()
                    ],
                }
                for family_key in _available_families_for_task(task, basis_task)
            ],
            "trace_selector": {
                "output_ports": [
                    {"port": port, "label": label} for port, label in port_options.items()
                ],
                "input_ports": [
                    {"port": port, "label": label} for port, label in port_options.items()
                ],
                "output_modes": [{"key": "mode_0", "label": "Mode 0"}],
                "input_modes": [{"key": "mode_0", "label": "Mode 0"}],
            },
            "parameter_sweep": _serialize_parameter_sweep_bootstrap(
                basis_task.simulation_setup,
                sweep_index=sweep_index,
            ),
            "default_selection": default_selection_payload,
        },
        "selection": selection_payload,
        "plot": {
            "x_axis": {
                "label": "Frequency",
                "unit": "GHz",
                "values": frequencies,
            },
            "y_axis": {
                "label": metric_config["label"],
                "unit": metric_config["unit"],
            },
            "series": [
                {
                    "series_id": (
                        f"{family}:{source}:{metric}:{output_port}:{input_port}"
                    ),
                    "label": (
                        f"{_SOURCE_LABELS[source]} {family.upper()} {output_port}{input_port} "
                        f"{metric_config['label']}"
                    ),
                    "values": selected_values,
                    "unit": metric_config["unit"],
                }
            ],
            "metadata": plot_metadata,
        },
    }


def _resolve_basis_task(task: TaskDetail, *, task_service: TaskService) -> TaskDetail:
    if task.kind == "simulation":
        if task.simulation_setup is None:
            raise service_error(
                409,
                code="simulation_result_explorer_setup_missing",
                category="conflict",
                message="Simulation result explorer requires persisted simulation_setup.",
            )
        return task

    if task.upstream_task_id is None:
        raise service_error(
            409,
            code="simulation_result_explorer_upstream_missing",
            category="conflict",
            message="Post-processing explorer requires an upstream simulation task.",
        )

    upstream_task = task_service.get_task(task.upstream_task_id)
    if upstream_task.kind != "simulation" or upstream_task.simulation_setup is None:
        raise service_error(
            409,
            code="simulation_result_explorer_upstream_invalid",
            category="conflict",
            message="Post-processing explorer requires a persisted upstream simulation result.",
        )
    return upstream_task


def _default_selection(
    task: TaskDetail,
    basis_task: TaskDetail,
    port_options: dict[int, str],
) -> dict[str, object]:
    default_port = min(port_options) if len(port_options) > 0 else 1
    default_sweep_index = _default_sweep_index(basis_task.simulation_setup)
    if task.kind == "post_processing" and task.post_processing_setup is not None:
        selection = (
            task.post_processing_setup.selections[0]
            if task.post_processing_setup.selections
            else None
        )
        if selection is not None:
            family = (
                selection.trace_family
                if selection.trace_family in _FAMILY_LABELS
                else "s_matrix"
            )
            available_sources = _available_sources(basis_task, family)
            source = available_sources[0]
            return {
                "family": family,
                "source": source,
                "metric": _metric_from_post_processing_representation(
                    family,
                    selection.representation,
                ),
                "sweep_index": default_sweep_index,
                "z0_ohm": 50.0,
                "output_port": default_port,
                "input_port": default_port,
            }

    return {
        "family": "s_matrix",
        "source": "raw",
        "metric": "magnitude_db",
        "sweep_index": default_sweep_index,
        "z0_ohm": 50.0,
        "output_port": default_port,
        "input_port": default_port,
    }


def _metric_from_post_processing_representation(family: str, representation: str) -> str:
    normalized = representation.strip().lower()
    if normalized in {"imag", "imaginary"}:
        candidate = "imag"
    elif normalized == "real":
        candidate = "real"
    elif normalized == "phase":
        candidate = "phase_deg"
    elif normalized in {"db", "magnitude_db", "magnitude"}:
        candidate = "magnitude_db" if family == "s_matrix" else "magnitude"
    else:
        candidate = "magnitude_db" if family == "s_matrix" else "magnitude"

    if candidate in _FAMILY_METRICS[family]:
        return candidate
    return next(iter(_FAMILY_METRICS[family]))


def _resolve_selection(
    explorer_task: TaskDetail,
    task: TaskDetail,
    *,
    family: str | None,
    source: str | None,
    metric: str | None,
    sweep_index: int | None,
    z0_ohm: float | None,
    output_port: int | None,
    input_port: int | None,
    port_options: dict[int, str],
    default_selection: Mapping[str, object],
) -> dict[str, object]:
    resolved_family = family or str(default_selection["family"])
    if resolved_family not in _available_families_for_task(explorer_task, task):
        raise service_error(
            400,
            code="request_validation_failed",
            category="validation_error",
            message="family is not available for this persisted result.",
        )
    sources = _available_sources_for_task(explorer_task, task, resolved_family)
    resolved_source = source or str(default_selection["source"])
    if resolved_source not in sources:
        raise service_error(
            400,
            code="request_validation_failed",
            category="validation_error",
            message=f"source {resolved_source} is not available for family {resolved_family}.",
        )
    metric_options = _FAMILY_METRICS[resolved_family]
    resolved_metric = metric or str(default_selection["metric"])
    if resolved_metric not in metric_options:
        raise service_error(
            400,
            code="request_validation_failed",
            category="validation_error",
            message=f"metric {resolved_metric} is not available for family {resolved_family}.",
        )
    resolved_sweep_index = (
        sweep_index
        if sweep_index is not None
        else (
            int(default_selection["sweep_index"])
            if default_selection.get("sweep_index") is not None
            else None
        )
    )
    _validate_sweep_index(task.simulation_setup, resolved_sweep_index)
    resolved_z0 = float(z0_ohm if z0_ohm is not None else default_selection["z0_ohm"])
    if resolved_z0 <= 0:
        raise service_error(
            400,
            code="request_validation_failed",
            category="validation_error",
            message="z0 must be positive.",
        )
    resolved_output_port = output_port or int(default_selection["output_port"])
    resolved_input_port = input_port or int(default_selection["input_port"])
    if resolved_output_port not in port_options or resolved_input_port not in port_options:
        raise service_error(
            400,
            code="request_validation_failed",
            category="validation_error",
            message="Requested trace selection ports are not available for this simulation result.",
        )
    return {
        "family": resolved_family,
        "source": resolved_source,
        "metric": resolved_metric,
        "sweep_index": resolved_sweep_index,
        "z0_ohm": resolved_z0,
        "output_port": resolved_output_port,
        "input_port": resolved_input_port,
    }


def _available_families_for_task(
    task: TaskDetail,
    basis_task: TaskDetail,
) -> tuple[str, ...]:
    return ("s_matrix", "y_matrix", "z_matrix")


def _available_sources_for_task(
    task: TaskDetail,
    basis_task: TaskDetail,
    family: str,
) -> tuple[str, ...]:
    return _available_sources(basis_task, family)


def _available_sources(task: TaskDetail, family: str) -> tuple[str, ...]:
    return available_sources_for_family(task, family)


def _resolve_port_indices(
    task: TaskDetail,
    *,
    task_service: TaskService,
) -> tuple[int, ...]:
    definition = task_service.get_circuit_definition(task.definition_id)
    definition_indices = _extract_definition_port_indices(definition)
    if len(definition_indices) > 0:
        return definition_indices

    setup_indices = _extract_setup_port_indices(task)
    if len(setup_indices) > 0:
        return setup_indices

    return (1,)


def _extract_definition_port_indices(definition: object | None) -> tuple[int, ...]:
    if definition is None:
        return ()

    normalized_output = _parse_mapping_literal(getattr(definition, "normalized_output", None))
    if normalized_output is not None:
        expanded_payload = normalized_output.get("expanded")
        expanded_mapping = (
            expanded_payload
            if isinstance(expanded_payload, Mapping)
            else _parse_mapping_literal(expanded_payload)
        )
        expanded_indices = _extract_topology_port_indices(
            None if expanded_mapping is None else expanded_mapping.get("topology")
        )
        if len(expanded_indices) > 0:
            return expanded_indices

    source_payload = _parse_mapping_literal(getattr(definition, "source_text", None))
    if source_payload is None:
        return ()
    return _extract_topology_port_indices(source_payload.get("topology"))


def _parse_mapping_literal(value: object) -> Mapping[str, object] | None:
    if isinstance(value, Mapping):
        return value
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    if len(stripped) == 0:
        return None
    try:
        parsed = ast.literal_eval(stripped)
    except (SyntaxError, ValueError):
        return None
    return parsed if isinstance(parsed, Mapping) else None


def _extract_topology_port_indices(topology: object) -> tuple[int, ...]:
    if not isinstance(topology, Sequence) or isinstance(topology, (str, bytes)):
        return ()

    indices: set[int] = set()
    for row in topology:
        port_index = _extract_port_index_from_topology_row(row)
        if port_index is not None:
            indices.add(port_index)
    return tuple(sorted(indices))


def _extract_port_index_from_topology_row(row: object) -> int | None:
    if not isinstance(row, Sequence) or isinstance(row, (str, bytes)) or len(row) < 4:
        return None
    element_name = row[0]
    if not isinstance(element_name, str):
        return None
    match = _DEFINITION_PORT_PATTERN.fullmatch(element_name.strip())
    if match is None:
        return None
    value_ref = row[3]
    if isinstance(value_ref, int) and value_ref >= 1:
        return value_ref
    return int(match.group(1))


def _extract_setup_port_indices(task: TaskDetail) -> tuple[int, ...]:
    if task.simulation_setup is None:
        return ()

    indices: set[int] = set()
    for source in task.simulation_setup.sources:
        port_index = _extract_port_index_from_token(source.target)
        if port_index is not None:
            indices.add(port_index)
    if task.simulation_setup.ptc is not None:
        for port in task.simulation_setup.ptc.compensate_ports:
            port_index = _extract_port_index_from_token(port)
            if port_index is not None:
                indices.add(port_index)
    return tuple(sorted(indices))


def _extract_port_index_from_token(token: object) -> int | None:
    if not isinstance(token, str):
        return None
    match = _SETUP_PORT_PATTERN.fullmatch(token.strip())
    if match is None:
        return None
    return int(match.group(1))


def _format_port_label(index: int) -> str:
    return f"Port {index}"


def _frequency_values(setup: SimulationSetup) -> list[float]:
    point_count = max(setup.frequency_sweep.point_count, 1)
    start = setup.frequency_sweep.start_ghz
    stop = setup.frequency_sweep.stop_ghz
    if point_count == 1:
        return [round(start, 6)]
    step = (stop - start) / (point_count - 1)
    return [round(start + (step * index), 6) for index in range(point_count)]


def _default_sweep_index(setup: SimulationSetup) -> int | None:
    return 0 if len(setup.parameter_sweeps) > 0 else None


def _sweep_point_count(setup: SimulationSetup) -> int:
    if len(setup.parameter_sweeps) == 0:
        return 1

    total = 1
    for sweep in setup.parameter_sweeps:
        total *= max(len(sweep.values), 1)
    return total


def _validate_sweep_index(
    setup: SimulationSetup,
    sweep_index: int | None,
) -> None:
    if len(setup.parameter_sweeps) == 0:
        if sweep_index not in {None, 0}:
            raise service_error(
                400,
                code="request_validation_failed",
                category="validation_error",
                message="sweep_index is not available for this persisted result.",
            )
        return

    if sweep_index is None or sweep_index < 0 or sweep_index >= _sweep_point_count(setup):
        raise service_error(
            400,
            code="request_validation_failed",
            category="validation_error",
            message="sweep_index is outside the available parameter sweep range.",
        )


def _decode_sweep_index(
    setup: SimulationSetup,
    sweep_index: int | None,
) -> tuple[int, ...]:
    if len(setup.parameter_sweeps) == 0:
        return ()

    resolved_index = sweep_index if sweep_index is not None else 0
    remaining = resolved_index
    coordinates = [0] * len(setup.parameter_sweeps)
    for axis_index in range(len(setup.parameter_sweeps) - 1, -1, -1):
        axis_size = max(len(setup.parameter_sweeps[axis_index].values), 1)
        coordinates[axis_index] = remaining % axis_size
        remaining //= axis_size
    return tuple(coordinates)


def _serialize_parameter_sweep_bootstrap(
    setup: SimulationSetup,
    *,
    sweep_index: int | None,
) -> dict[str, object]:
    coordinates = _decode_sweep_index(setup, sweep_index)
    axes: list[dict[str, object]] = []
    for axis_index, sweep in enumerate(setup.parameter_sweeps):
        values = [float(value) for value in sweep.values]
        axes.append(
            {
                "parameter": sweep.parameter,
                "label": sweep.parameter,
                "unit": sweep.unit,
                "values": values,
                "selected_value_index": (
                    coordinates[axis_index] if axis_index < len(coordinates) else 0
                ),
            }
        )
    return {
        "axes": axes,
        "point_count": _sweep_point_count(setup),
        "active": len(axes) > 0,
    }


def _build_family_bundle(
    task: TaskDetail,
    *,
    port_count: int,
    compensated_ports: set[int],
    sweep_index: int | None,
    z0_ohm: float,
) -> dict[str, dict[str, list[list[list[complex]]]]]:
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
            _apply_port_compensation(matrix, compensated_ports, scale=0.94)
            for matrix in raw_y
        ]
        family_bundle["z_matrix"]["ptc"] = [
            _apply_port_compensation(matrix, compensated_ports, scale=1.06)
            for matrix in raw_z
        ]
    return family_bundle


def _compensated_port_indices(
    task: TaskDetail,
    *,
    available_ports: Mapping[int, str],
) -> set[int]:
    if task.simulation_setup is None or task.simulation_setup.ptc is None:
        return set()
    return {
        port_index
        for label in task.simulation_setup.ptc.compensate_ports
        if (port_index := _extract_port_index_from_token(label)) is not None
        and port_index in available_ports
    }


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
                amplitude = (
                    0.22
                    + (0.04 * output_index)
                    - (0.18 * lorentz)
                    + (0.012 * sweep_bias)
                )
                angle = phase * (1 + (0.1 * output_index))
            else:
                amplitude = ((0.72 / (1 + port_distance)) * lorentz) * (
                    1 + (0.08 * sweep_bias)
                )
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


def _extract_metric_values(
    matrices: Sequence[list[list[complex]]],
    *,
    metric: str,
    output_port: int,
    input_port: int,
) -> list[float]:
    row_index = output_port - 1
    column_index = input_port - 1
    values: list[float] = []
    for matrix in matrices:
        complex_value = matrix[row_index][column_index]
        if metric == "magnitude_db":
            values.append(round(20 * math.log10(max(abs(complex_value), 1e-9)), 6))
        elif metric == "phase_deg":
            phase_degrees = math.degrees(
                math.atan2(complex_value.imag, complex_value.real)
            )
            values.append(round(phase_degrees, 6))
        elif metric == "magnitude":
            values.append(round(abs(complex_value), 6))
        elif metric == "real":
            values.append(round(complex_value.real, 6))
        else:
            values.append(round(complex_value.imag, 6))
    return values


def _resolve_sweep_bias(
    setup: SimulationSetup,
    sweep_index: int | None,
) -> float:
    if len(setup.parameter_sweeps) == 0:
        return 0.0

    coordinates = _decode_sweep_index(setup, sweep_index)
    bias = 0.0
    for axis_index, (sweep, value_index) in enumerate(
        zip(setup.parameter_sweeps, coordinates, strict=False)
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


def _build_trace_selection(selection: Mapping[str, object]) -> ResultTraceSelection:
    family = str(selection["family"])
    return ResultTraceSelection(
        family=family,
        source=str(selection["source"]),
        output_port=int(selection["output_port"]),
        input_port=int(selection["input_port"]),
        sweep_index=(
            int(selection["sweep_index"])
            if selection.get("sweep_index") is not None
            else None
        ),
        trace_mode_group="base",
        output_mode="mode_0",
        input_mode="mode_0",
        z0_ohm=(
            float(selection["z0_ohm"])
            if family in {"y_matrix", "z_matrix"}
            else None
        ),
    )


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


def _matrix_scale(matrix: Sequence[Sequence[complex]], scalar: float) -> list[list[complex]]:
    return [
        [value * scalar for value in row]
        for row in matrix
    ]


def _matrix_multiply(
    left: Sequence[Sequence[complex]],
    right: Sequence[Sequence[complex]],
) -> list[list[complex]]:
    size = len(left)
    return [
        [
            sum(left[row][k] * right[k][column] for k in range(size))
            for column in range(size)
        ]
        for row in range(size)
    ]


def _matrix_inverse(matrix: Sequence[Sequence[complex]]) -> list[list[complex]]:
    size = len(matrix)
    augmented = [
        [complex(value) for value in row]
        + [
            1 + 0j if row_index == column else 0 + 0j
            for column in range(size)
        ]
        for row_index, row in enumerate(matrix)
    ]
    for pivot_index in range(size):
        pivot_row = max(
            range(pivot_index, size),
            key=lambda row_index: abs(augmented[row_index][pivot_index]),
        )
        pivot_value = augmented[pivot_row][pivot_index]
        if abs(pivot_value) <= 1e-12:
            raise service_error(
                409,
                code="simulation_result_explorer_unavailable",
                category="conflict",
                message="Simulation explorer could not invert the selected result matrix.",
            )
        if pivot_row != pivot_index:
            augmented[pivot_index], augmented[pivot_row] = (
                augmented[pivot_row],
                augmented[pivot_index],
            )
        normalized_pivot = augmented[pivot_index][pivot_index]
        augmented[pivot_index] = [value / normalized_pivot for value in augmented[pivot_index]]
        for row_index in range(size):
            if row_index == pivot_index:
                continue
            factor = augmented[row_index][pivot_index]
            augmented[row_index] = [
                augmented[row_index][column] - (factor * augmented[pivot_index][column])
                for column in range(size * 2)
            ]
    return [row[size:] for row in augmented]
