from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass

import numpy as np

from src.app.domain.result_traces import ResultTraceSelection
from src.app.domain.tasks import SimulationSetup, TaskDetail
from src.app.infrastructure.persisted_runtime import (
    available_sources_for_task_family,
    extract_simulation_trace_grid_data,
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


@dataclass(frozen=True)
class ExplorerSelectionRequest:
    family: str | None = None
    source: str | None = None
    metric: str | None = None
    sweep_index: int | None = None
    compare_axis_index: int | None = None
    z0_ohm: float | None = None
    output_port: int | None = None
    input_port: int | None = None


@dataclass(frozen=True)
class _ExplorerContext:
    explorer_task: TaskDetail
    basis_task: TaskDetail
    port_options: dict[int, str]
    default_selection: dict[str, object]


class SimulationResultExplorerService:
    def __init__(self, task_service: TaskService) -> None:
        self._task_service = task_service

    def get_bootstrap_payload(self, task_id: int) -> dict[str, object]:
        context = self._build_context(task_id)
        payload = _build_base_payload(context.explorer_task)
        payload["bootstrap"] = _build_bootstrap_payload(context)
        payload["result_basis"] = _build_result_basis_payload(context.explorer_task)
        return payload

    def get_view_payload(
        self,
        task_id: int,
        selection_request: ExplorerSelectionRequest,
    ) -> dict[str, object]:
        context = self._build_context(task_id)
        payload = _build_base_payload(context.explorer_task)
        payload.update(
            self._build_selected_view_payload(
                context=context,
                selection_request=selection_request,
            )
        )
        return payload

    def get_explorer_payload(
        self,
        task_id: int,
        selection_request: ExplorerSelectionRequest,
    ) -> dict[str, object]:
        context = self._build_context(task_id)
        payload = self.get_bootstrap_payload(task_id)
        payload.update(
            self._build_selected_view_payload(
                context=context,
                selection_request=selection_request,
            )
        )
        return payload

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

    def _build_context(self, task_id: int) -> _ExplorerContext:
        explorer_task = self._task_service.get_task(task_id)
        self._ensure_task_ready_for_explorer(explorer_task)
        basis_task = _resolve_basis_task(explorer_task, task_service=self._task_service)
        definition = self._task_service.get_circuit_definition(basis_task.definition_id)
        port_options = port_options_for_task(
            explorer_task,
            basis_task=basis_task,
            definition=definition,
        )
        return _ExplorerContext(
            explorer_task=explorer_task,
            basis_task=basis_task,
            port_options=port_options,
            default_selection=_default_selection(
                explorer_task,
                basis_task=basis_task,
                port_options=port_options,
            ),
        )

    def _build_selected_view_payload(
        self,
        *,
        context: _ExplorerContext,
        selection_request: ExplorerSelectionRequest,
    ) -> dict[str, object]:
        selection = _resolve_selection(
            context=context,
            selection_request=selection_request,
        )
        if context.explorer_task.kind == "simulation":
            return _build_selected_view_payload_fast(
                context=context,
                selection=selection,
            )
        bundle = _load_bundle_for_selection(context=context, selection=selection)
        return _build_selected_view_payload(
            context=context,
            bundle=bundle,
            selection=selection,
        )


def _build_base_payload(task: TaskDetail) -> dict[str, object]:
    return {
        "task_id": task.task_id,
        "task_status": task.status,
        "runtime_mode": "local" if task.visibility_scope == "local" else "online",
    }


def _build_result_basis_payload(task: TaskDetail) -> dict[str, object]:
    return {
        "trace_payload_available": task.result_refs.trace_payload is not None,
        "primary_result_handle_id": (
            task.result_refs.result_handles[0].handle_id
            if len(task.result_refs.result_handles) > 0
            else None
        ),
        "trace_batch_id": task.result_refs.trace_batch_id,
    }


def _build_bootstrap_payload(context: _ExplorerContext) -> dict[str, object]:
    sweep_index = (
        int(context.default_selection["sweep_index"])
        if context.default_selection.get("sweep_index") is not None
        else None
    )
    compare_axis_index = (
        int(context.default_selection["compare_axis_index"])
        if context.default_selection.get("compare_axis_index") is not None
        else None
    )
    default_selection_payload: dict[str, object] = {
        **{
            key: value
            for key, value in context.default_selection.items()
            if key not in {"sweep_index", "compare_axis_index"} or value is not None
        },
        "trace_key": _build_trace_selection(context.default_selection).to_trace_key(),
    }
    return {
        "families": [
            {
                "key": family_key,
                "label": _FAMILY_LABELS[family_key],
                "available_sources": [
                    {"key": source_key, "label": _SOURCE_LABELS[source_key]}
                    for source_key in _available_sources_for_task(context.explorer_task, family_key)
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
            for family_key in _available_families_for_task(context.explorer_task)
        ],
        "trace_selector": {
            "output_ports": [
                {"port": port, "label": label}
                for port, label in context.port_options.items()
            ],
            "input_ports": [
                {"port": port, "label": label}
                for port, label in context.port_options.items()
            ],
            "output_modes": [{"key": "mode_0", "label": "Mode 0"}],
            "input_modes": [{"key": "mode_0", "label": "Mode 0"}],
        },
        "parameter_sweep": _serialize_parameter_sweep_bootstrap(
            context.basis_task.simulation_setup,
            sweep_index=sweep_index,
            compare_axis_index=compare_axis_index,
        ),
        "default_selection": default_selection_payload,
    }


def _build_selected_view_payload(
    *,
    context: _ExplorerContext,
    bundle,
    selection: dict[str, object],
) -> dict[str, object]:
    family = str(selection["family"])
    source = str(selection["source"])
    metric = str(selection["metric"])
    sweep_index = (
        int(selection["sweep_index"])
        if selection.get("sweep_index") is not None
        else None
    )
    compare_axis_index = (
        int(selection["compare_axis_index"])
        if selection.get("compare_axis_index") is not None
        else None
    )
    z0_ohm = float(selection["z0_ohm"])
    output_port = int(selection["output_port"])
    input_port = int(selection["input_port"])

    metric_config = _FAMILY_METRICS[family][metric]
    output_label = context.port_options[output_port]
    input_label = context.port_options[input_port]
    trace_key = _build_trace_selection(selection).to_trace_key()
    selection_payload: dict[str, object] = {
        **{
            key: value
            for key, value in selection.items()
            if key not in {"sweep_index", "compare_axis_index"} or value is not None
        },
        "trace_mode_group": "base",
        "output_port_label": output_label,
        "input_port_label": input_label,
        "output_mode": "mode_0",
        "input_mode": "mode_0",
        "trace_key": trace_key,
    }
    if compare_axis_index is not None:
        selection_payload["compare_axis_index"] = compare_axis_index
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
            context.explorer_task.result_refs.trace_payload.store_key
            if context.explorer_task.result_refs.trace_payload is not None
            else None
        ),
    }
    if sweep_index is not None:
        selection_payload["sweep_index"] = sweep_index
        plot_metadata["sweep_index"] = sweep_index
    if compare_axis_index is not None:
        plot_metadata["compare_axis_index"] = compare_axis_index

    plot_series = _build_plot_series(
        context=context,
        bundle=bundle,
        selection=selection,
        compare_axis_index=compare_axis_index,
        metric=metric,
        metric_config=metric_config,
        family=family,
        source=source,
        output_port=output_port,
        input_port=input_port,
    )

    return {
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
            "series": plot_series,
            "metadata": plot_metadata,
        },
    }


def _build_selected_view_payload_fast(
    *,
    context: _ExplorerContext,
    selection: dict[str, object],
) -> dict[str, object]:
    family = str(selection["family"])
    source = str(selection["source"])
    metric = str(selection["metric"])
    sweep_index = (
        int(selection["sweep_index"])
        if selection.get("sweep_index") is not None
        else None
    )
    compare_axis_index = (
        int(selection["compare_axis_index"])
        if selection.get("compare_axis_index") is not None
        else None
    )
    z0_ohm = float(selection["z0_ohm"])
    output_port = int(selection["output_port"])
    input_port = int(selection["input_port"])

    metric_config = _FAMILY_METRICS[family][metric]
    output_label = context.port_options[output_port]
    input_label = context.port_options[input_port]
    trace_key = _build_trace_selection(selection).to_trace_key()
    selection_payload: dict[str, object] = {
        **{
            key: value
            for key, value in selection.items()
            if key not in {"sweep_index", "compare_axis_index"} or value is not None
        },
        "trace_mode_group": "base",
        "output_port_label": output_label,
        "input_port_label": input_label,
        "output_mode": "mode_0",
        "input_mode": "mode_0",
        "trace_key": trace_key,
    }
    if compare_axis_index is not None:
        selection_payload["compare_axis_index"] = compare_axis_index
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
            context.explorer_task.result_refs.trace_payload.store_key
            if context.explorer_task.result_refs.trace_payload is not None
            else None
        ),
    }
    if sweep_index is not None:
        selection_payload["sweep_index"] = sweep_index
        plot_metadata["sweep_index"] = sweep_index
    if compare_axis_index is not None:
        plot_metadata["compare_axis_index"] = compare_axis_index

    trace_grid = extract_simulation_trace_grid_data(
        context.explorer_task,
        family=family,
        source=source,
        output_port=output_port,
        input_port=input_port,
        sweep_index=sweep_index,
        compare_axis_index=compare_axis_index,
    )
    plot_series = _build_plot_series_from_trace_grid(
        context=context,
        selection=selection,
        trace_grid=trace_grid,
        compare_axis_index=compare_axis_index,
        metric=metric,
        metric_config=metric_config,
        family=family,
        source=source,
        output_port=output_port,
        input_port=input_port,
    )

    return {
        "selection": selection_payload,
        "plot": {
            "x_axis": {
                "label": "Frequency",
                "unit": "GHz",
                "values": [float(value) for value in trace_grid.frequencies_ghz],
            },
            "y_axis": {
                "label": metric_config["label"],
                "unit": metric_config["unit"],
            },
            "series": plot_series,
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
    basis_task: TaskDetail,
    port_options: dict[int, str],
) -> dict[str, object]:
    default_port = min(port_options) if len(port_options) > 0 else 1
    basis_setup = basis_task.simulation_setup
    default_sweep_index = (
        _default_sweep_index(basis_setup)
        if basis_setup is not None
        else None
    )
    default_compare_axis_index = (
        _default_compare_axis_index(basis_setup)
        if basis_setup is not None
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
                "compare_axis_index": default_compare_axis_index,
                "z0_ohm": 50.0,
                "output_port": default_port,
                "input_port": default_port,
            }

    return {
        "family": "s_matrix",
        "source": "raw",
        "metric": "magnitude_db",
        "sweep_index": default_sweep_index,
        "compare_axis_index": default_compare_axis_index,
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
    *,
    context: _ExplorerContext,
    selection_request: ExplorerSelectionRequest,
) -> dict[str, object]:
    resolved_family = selection_request.family or str(context.default_selection["family"])
    if resolved_family not in _available_families_for_task(context.explorer_task):
        raise service_error(
            400,
            code="request_validation_failed",
            category="validation_error",
            message="family is not available for this persisted result.",
        )
    sources = _available_sources_for_task(context.explorer_task, resolved_family)
    resolved_source = selection_request.source or str(context.default_selection["source"])
    if resolved_source not in sources:
        raise service_error(
            400,
            code="request_validation_failed",
            category="validation_error",
            message=f"source {resolved_source} is not available for family {resolved_family}.",
        )
    metric_options = _FAMILY_METRICS[resolved_family]
    resolved_metric = selection_request.metric or str(context.default_selection["metric"])
    if resolved_metric not in metric_options:
        raise service_error(
            400,
            code="request_validation_failed",
            category="validation_error",
            message=f"metric {resolved_metric} is not available for family {resolved_family}.",
        )
    resolved_sweep_index = (
        selection_request.sweep_index
        if selection_request.sweep_index is not None
        else (
            int(context.default_selection["sweep_index"])
            if context.default_selection.get("sweep_index") is not None
            else None
        )
    )
    basis_setup = context.basis_task.simulation_setup
    _validate_sweep_index(basis_setup, resolved_sweep_index)
    resolved_compare_axis_index = _resolve_compare_axis_index(
        basis_setup,
        selection_request.compare_axis_index
        if selection_request.compare_axis_index is not None
        else (
            int(context.default_selection["compare_axis_index"])
            if context.default_selection.get("compare_axis_index") is not None
            else None
        ),
    )
    resolved_z0 = float(
        selection_request.z0_ohm
        if selection_request.z0_ohm is not None
        else context.default_selection["z0_ohm"]
    )
    if resolved_z0 <= 0:
        raise service_error(
            400,
            code="request_validation_failed",
            category="validation_error",
            message="z0 must be positive.",
        )
    resolved_output_port = (
        selection_request.output_port or int(context.default_selection["output_port"])
    )
    resolved_input_port = (
        selection_request.input_port or int(context.default_selection["input_port"])
    )
    if (
        resolved_output_port not in context.port_options
        or resolved_input_port not in context.port_options
    ):
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
        "compare_axis_index": resolved_compare_axis_index,
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


def _default_compare_axis_index(setup: SimulationSetup) -> int | None:
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


def _resolve_compare_axis_index(
    setup: SimulationSetup,
    compare_axis_index: int | None,
) -> int | None:
    if len(setup.parameter_sweeps) == 0:
        if compare_axis_index is not None:
            raise service_error(
                400,
                code="request_validation_failed",
                category="validation_error",
                message="compare_axis_index is not available for this persisted result.",
            )
        return None

    resolved_index = compare_axis_index if compare_axis_index is not None else 0
    if resolved_index < 0 or resolved_index >= len(setup.parameter_sweeps):
        raise service_error(
            400,
            code="request_validation_failed",
            category="validation_error",
            message="compare_axis_index is outside the available parameter sweep range.",
        )
    return resolved_index


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


def _encode_sweep_index(
    setup: SimulationSetup,
    coordinates: tuple[int, ...],
) -> int | None:
    if len(setup.parameter_sweeps) == 0:
        return None

    encoded = 0
    for axis_index, sweep in enumerate(setup.parameter_sweeps):
        axis_size = max(len(sweep.values), 1)
        coordinate = coordinates[axis_index] if axis_index < len(coordinates) else 0
        coordinate = min(max(coordinate, 0), axis_size - 1)
        encoded = (encoded * axis_size) + coordinate
    return encoded


def _serialize_parameter_sweep_bootstrap(
    setup: SimulationSetup,
    *,
    sweep_index: int | None,
    compare_axis_index: int | None,
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
        "compare_axis_index": compare_axis_index,
    }


def _load_bundle_for_selection(
    *,
    context: _ExplorerContext,
    selection: Mapping[str, object],
):
    try:
        return load_task_family_bundle(
            context.explorer_task,
            basis_task=context.basis_task,
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


def _build_plot_series(
    *,
    context: _ExplorerContext,
    bundle,
    selection: Mapping[str, object],
    compare_axis_index: int | None,
    metric: str,
    metric_config: Mapping[str, str],
    family: str,
    source: str,
    output_port: int,
    input_port: int,
) -> list[dict[str, object]]:
    base_series_id = f"{family}:{source}:{metric}:{output_port}:{input_port}"
    if compare_axis_index is None or context.basis_task.simulation_setup is None:
        matrices = bundle.family_bundle[family][source]
        selected_values = _extract_metric_values(
            matrices,
            metric=metric,
            output_port=output_port,
            input_port=input_port,
        )
        return [
            {
                "series_id": base_series_id,
                "label": (
                    f"{_SOURCE_LABELS[source]} {family.upper()} "
                    f"{context.port_options[output_port]} {context.port_options[input_port]} "
                    f"{metric_config['label']}"
                ),
                "trace_key": _build_trace_selection(selection).to_trace_key(),
                "values": selected_values,
                "unit": metric_config["unit"],
            }
        ]

    setup = context.basis_task.simulation_setup
    coordinates = list(
        _decode_sweep_index(
            setup,
            int(selection["sweep_index"]) if selection.get("sweep_index") is not None else None,
        )
    )
    compare_axis = setup.parameter_sweeps[compare_axis_index]
    current_sweep_index = (
        int(selection["sweep_index"])
        if selection.get("sweep_index") is not None
        else None
    )
    series_entries: list[dict[str, object]] = []
    for value_index, sweep_value in enumerate(compare_axis.values):
        coordinates[compare_axis_index] = value_index
        trace_sweep_index = _encode_sweep_index(setup, tuple(coordinates))
        trace_selection = dict(selection)
        trace_selection["sweep_index"] = trace_sweep_index
        trace_bundle = (
            bundle
            if trace_sweep_index == current_sweep_index
            else _load_bundle_for_selection(context=context, selection=trace_selection)
        )
        matrices = trace_bundle.family_bundle[family][source]
        selected_values = _extract_metric_values(
            matrices,
            metric=metric,
            output_port=output_port,
            input_port=input_port,
        )
        series_entries.append(
            {
                "series_id": (
                    f"{base_series_id}:sweep:{trace_sweep_index}"
                    if trace_sweep_index is not None
                    else base_series_id
                ),
                "label": _format_compare_axis_series_label(
                    compare_axis.parameter,
                    float(sweep_value),
                    compare_axis.unit,
                ),
                "trace_key": _build_trace_selection(trace_selection).to_trace_key(),
                "values": selected_values,
                "unit": metric_config["unit"],
            }
        )
    return series_entries


def _build_plot_series_from_trace_grid(
    *,
    context: _ExplorerContext,
    selection: Mapping[str, object],
    trace_grid,
    compare_axis_index: int | None,
    metric: str,
    metric_config: Mapping[str, str],
    family: str,
    source: str,
    output_port: int,
    input_port: int,
) -> list[dict[str, object]]:
    metric_grid = _extract_metric_grid_values(trace_grid.values, metric=metric)
    base_series_id = f"{family}:{source}:{metric}:{output_port}:{input_port}"
    if compare_axis_index is None or trace_grid.compare_values is None:
        return [
            {
                "series_id": base_series_id,
                "label": (
                    f"{_SOURCE_LABELS[source]} {family.upper()} "
                    f"{context.port_options[output_port]} {context.port_options[input_port]} "
                    f"{metric_config['label']}"
                ),
                "trace_key": _build_trace_selection(selection).to_trace_key(),
                "values": [float(value) for value in metric_grid[:, 0]],
                "unit": metric_config["unit"],
            }
        ]

    compare_axis = context.basis_task.simulation_setup.parameter_sweeps[compare_axis_index]
    coordinates = list(
        _decode_sweep_index(
            context.basis_task.simulation_setup,
            int(selection["sweep_index"]) if selection.get("sweep_index") is not None else None,
        )
    )
    series_entries: list[dict[str, object]] = []
    for value_index, sweep_value in enumerate(trace_grid.compare_values):
        coordinates[compare_axis_index] = value_index
        trace_sweep_index = _encode_sweep_index(
            context.basis_task.simulation_setup,
            tuple(coordinates),
        )
        trace_selection = dict(selection)
        trace_selection["sweep_index"] = trace_sweep_index
        series_entries.append(
            {
                "series_id": f"{base_series_id}:sweep:{value_index}",
                "label": _format_compare_axis_series_label(
                    compare_axis.parameter,
                    float(sweep_value),
                    compare_axis.unit,
                ),
                "trace_key": _build_trace_selection(trace_selection).to_trace_key(),
                "values": [float(value) for value in metric_grid[:, value_index]],
                "unit": metric_config["unit"],
            }
        )
    return series_entries


def _format_compare_axis_series_label(
    parameter: str,
    value: float,
    unit: str | None,
) -> str:
    compact_value = (
        str(int(value))
        if float(value).is_integer()
        else format(float(value), ".6f").rstrip("0").rstrip(".")
    )
    if unit:
        return f"{parameter} = {compact_value} {unit}"
    return f"{parameter} = {compact_value}"


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


def _extract_metric_grid_values(
    values: np.ndarray,
    *,
    metric: str,
) -> np.ndarray:
    if metric == "real":
        return np.asarray(values.real, dtype=float)
    if metric == "imag":
        return np.asarray(values.imag, dtype=float)
    if metric == "phase_deg":
        return np.asarray(np.degrees(np.angle(values)), dtype=float)
    if metric == "magnitude_db":
        return np.asarray(20 * np.log10(np.maximum(np.abs(values), 1e-12)), dtype=float)
    if metric == "magnitude":
        return np.asarray(np.abs(values), dtype=float)
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
