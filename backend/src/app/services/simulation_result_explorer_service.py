from __future__ import annotations

import math
from collections.abc import Mapping

import numpy as np

from src.app.domain.result_traces import ResultTraceSelection
from src.app.domain.tasks import SimulationSetup, TaskDetail
from src.app.infrastructure.persisted_runtime import (
    available_sources_for_task_family,
    load_task_family_bundle,
    port_options_for_task,
)
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
        definition = self._task_service.get_circuit_definition(basis_task.definition_id)
        port_options = port_options_for_task(
            task,
            basis_task=basis_task,
            definition=definition,
        )
        default_selection = _default_selection(task, port_options=port_options)
        selection = _resolve_selection(
            explorer_task=task,
            basis_task=basis_task,
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
        bundle = _load_bundle_for_selection(
            task,
            basis_task=basis_task,
            selection=selection,
        )
        response = _build_explorer_response(
            task,
            basis_task=basis_task,
            bundle=bundle,
            selection=selection,
            port_options=port_options,
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
    bundle,
    selection: dict[str, object],
    port_options: dict[int, str],
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

    matrices = bundle.family_bundle[family][source]
    selected_values = _extract_metric_values(
        matrices,
        metric=metric,
        output_port=output_port,
        input_port=input_port,
    )
    metric_config = _FAMILY_METRICS[family][metric]
    output_label = port_options[output_port]
    input_label = port_options[input_port]
    trace_key = _build_trace_selection(selection).to_trace_key()

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
        "trace_key": trace_key,
    }
    plot_metadata: dict[str, object] = {
        "trace_key": trace_key,
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
        default_selection_payload["sweep_index"] = int(default_selection.get("sweep_index", 0))
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
                        for source_key in _available_sources_for_task(task, family_key)
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
                for family_key in _available_families_for_task(task)
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
                "values": [float(value) for value in bundle.frequencies_ghz],
            },
            "y_axis": {
                "label": metric_config["label"],
                "unit": metric_config["unit"],
            },
            "series": [
                {
                    "series_id": f"{family}:{source}:{metric}:{output_port}:{input_port}",
                    "label": (
                        f"{_SOURCE_LABELS[source]} {family.upper()} {output_label} {input_label} "
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
    *,
    port_options: dict[int, str],
) -> dict[str, object]:
    default_port = min(port_options) if len(port_options) > 0 else 1
    default_sweep_index = (
        _default_sweep_index(task.simulation_setup)
        if task.kind == "simulation"
        else None
    )
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
            available_sources = _available_sources_for_task(task, family)
            return {
                "family": family,
                "source": available_sources[0],
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
    basis_task: TaskDetail,
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
    if resolved_family not in _available_families_for_task(explorer_task):
        raise service_error(
            400,
            code="request_validation_failed",
            category="validation_error",
            message="family is not available for this persisted result.",
        )
    sources = _available_sources_for_task(explorer_task, resolved_family)
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
    _validate_sweep_index(basis_task.simulation_setup, resolved_sweep_index)
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


def _available_families_for_task(task: TaskDetail) -> tuple[str, ...]:
    return tuple(
        family
        for family in ("s_matrix", "y_matrix", "z_matrix")
        if len(_available_sources_for_task(task, family)) > 0
    )


def _available_sources_for_task(task: TaskDetail, family: str) -> tuple[str, ...]:
    return available_sources_for_task_family(task, family)


def _default_sweep_index(setup: SimulationSetup) -> int | None:
    return 0 if len(setup.parameter_sweeps) > 0 else None


def _sweep_point_count(setup: SimulationSetup) -> int:
    if len(setup.parameter_sweeps) == 0:
        return 1
    total = 1
    for sweep in setup.parameter_sweeps:
        total *= max(len(sweep.values), 1)
    return total


def _validate_sweep_index(setup: SimulationSetup, sweep_index: int | None) -> None:
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


def _decode_sweep_index(setup: SimulationSetup, sweep_index: int | None) -> tuple[int, ...]:
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
        axes.append(
            {
                "parameter": sweep.parameter,
                "label": sweep.parameter,
                "unit": sweep.unit,
                "values": [float(value) for value in sweep.values],
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


def _load_bundle_for_selection(
    task: TaskDetail,
    *,
    basis_task: TaskDetail,
    selection: Mapping[str, object],
):
    try:
        return load_task_family_bundle(
            task,
            basis_task=basis_task,
            z0_ohm=float(selection["z0_ohm"]),
            sweep_index=(
                int(selection["sweep_index"])
                if selection.get("sweep_index") is not None
                else None
            ),
        )
    except ValueError as exc:
        raise service_error(
            409,
            code="simulation_result_explorer_unavailable",
            category="conflict",
            message=str(exc),
        ) from exc


def _extract_metric_values(
    matrices: list[np.ndarray],
    *,
    metric: str,
    output_port: int,
    input_port: int,
) -> list[float]:
    output_index = output_port - 1
    input_index = input_port - 1
    values = [
        complex(matrix[output_index, input_index])
        for matrix in matrices
    ]
    if metric == "real":
        return [float(value.real) for value in values]
    if metric == "imag":
        return [float(value.imag) for value in values]
    if metric == "phase_deg":
        return [float(math.degrees(math.atan2(value.imag, value.real))) for value in values]
    if metric == "magnitude_db":
        return [float(20 * math.log10(max(abs(value), 1e-12))) for value in values]
    if metric == "magnitude":
        return [float(abs(value)) for value in values]
    raise ValueError(f"Unsupported metric: {metric}")


def _build_trace_selection(selection: Mapping[str, object]) -> ResultTraceSelection:
    return ResultTraceSelection(
        family=str(selection["family"]),
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
            if str(selection["family"]) in {"y_matrix", "z_matrix"}
            else None
        ),
    )
