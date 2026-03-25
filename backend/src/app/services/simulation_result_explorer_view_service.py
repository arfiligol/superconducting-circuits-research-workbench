from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass

import numpy as np

from src.app.infrastructure.persisted_runtime import (
    available_sources_for_task_family,
    extract_simulation_trace_grid_data,
    load_task_family_bundle,
)
from src.app.services.service_errors import service_error
from src.app.services.simulation_result_explorer_models import (
    FAMILY_LABELS,
    FAMILY_METRICS,
    SOURCE_LABELS,
    ExplorerContext,
    ResolvedSelection,
)
from src.app.services.simulation_result_explorer_query_service import (
    decode_sweep_index,
    default_selection_trace_key,
    encode_sweep_index,
    replace_sweep_index,
    serialize_parameter_sweep_bootstrap,
)


@dataclass(frozen=True)
class _PlotContext:
    metric_config: Mapping[str, str]
    selection_payload: dict[str, object]
    plot_metadata: dict[str, object]
    base_series_id: str
    base_series_label: str


class SimulationResultExplorerViewService:
    def build_bootstrap_payload(self, context: ExplorerContext) -> dict[str, object]:
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
            "trace_key": default_selection_trace_key(context.default_selection),
        }
        return {
            "families": [
                {
                    "key": family_key,
                    "label": FAMILY_LABELS[family_key],
                    "available_sources": [
                        {"key": source_key, "label": SOURCE_LABELS[source_key]}
                        for source_key in _available_sources(context, family_key)
                    ],
                    "available_metrics": [
                        {
                            "key": metric_key,
                            "label": config["label"],
                            "unit": config["unit"],
                        }
                        for metric_key, config in FAMILY_METRICS[family_key].items()
                    ],
                }
                for family_key in _available_families(context)
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
            "parameter_sweep": serialize_parameter_sweep_bootstrap(
                context.basis_task.simulation_setup,
                sweep_index=sweep_index,
                compare_axis_index=compare_axis_index,
            ),
            "default_selection": default_selection_payload,
        }

    def build_view_payload(
        self,
        *,
        context: ExplorerContext,
        selection: ResolvedSelection,
    ) -> dict[str, object]:
        if context.explorer_task.kind == "simulation":
            return self._build_selected_view_payload_fast(
                context=context,
                selection=selection,
            )
        bundle = self._load_bundle_for_selection(context=context, selection=selection)
        return self._build_selected_view_payload(
            context=context,
            bundle=bundle,
            selection=selection,
        )

    def _build_selected_view_payload(
        self,
        *,
        context: ExplorerContext,
        bundle,
        selection: ResolvedSelection,
    ) -> dict[str, object]:
        plot_context = _build_plot_context(context=context, selection=selection)
        metric_config = plot_context.metric_config
        plot_series = self._build_plot_series(
            context=context,
            bundle=bundle,
            selection=selection,
            plot_context=plot_context,
        )
        return _build_plot_payload(
            selection_payload=plot_context.selection_payload,
            x_axis_values=bundle.frequencies_ghz,
            metric_config=metric_config,
            plot_series=plot_series,
            plot_metadata=plot_context.plot_metadata,
        )

    def _build_selected_view_payload_fast(
        self,
        *,
        context: ExplorerContext,
        selection: ResolvedSelection,
    ) -> dict[str, object]:
        plot_context = _build_plot_context(context=context, selection=selection)
        metric_config = plot_context.metric_config
        trace_grid = extract_simulation_trace_grid_data(
            context.explorer_task,
            family=selection.family,
            source=selection.source,
            output_port=selection.output_port,
            input_port=selection.input_port,
            sweep_index=selection.sweep_index,
            compare_axis_index=selection.compare_axis_index,
        )
        plot_series = self._build_plot_series_from_trace_grid(
            context=context,
            selection=selection,
            trace_grid=trace_grid,
            plot_context=plot_context,
        )
        return _build_plot_payload(
            selection_payload=plot_context.selection_payload,
            x_axis_values=trace_grid.frequencies_ghz,
            metric_config=metric_config,
            plot_series=plot_series,
            plot_metadata=plot_context.plot_metadata,
        )

    def _load_bundle_for_selection(
        self,
        *,
        context: ExplorerContext,
        selection: ResolvedSelection,
    ):
        try:
            return load_task_family_bundle(
                context.explorer_task,
                basis_task=context.basis_task,
                z0_ohm=selection.z0_ohm,
                sweep_index=selection.sweep_index,
            )
        except ValueError as exc:
            raise service_error(
                409,
                code="simulation_result_explorer_unavailable",
                category="conflict",
                message=str(exc),
            ) from exc

    def _build_plot_series(
        self,
        *,
        context: ExplorerContext,
        bundle,
        selection: ResolvedSelection,
        plot_context: _PlotContext,
    ) -> list[dict[str, object]]:
        if selection.compare_axis_index is None or context.basis_task.simulation_setup is None:
            matrices = bundle.family_bundle[selection.family][selection.source]
            selected_values = _extract_metric_values(
                matrices,
                metric=selection.metric,
                output_port=selection.output_port,
                input_port=selection.input_port,
            )
            return [
                _build_series_entry(
                    selection=selection,
                    plot_context=plot_context,
                    values=selected_values,
                )
            ]

        setup = context.basis_task.simulation_setup
        coordinates = list(decode_sweep_index(setup, selection.sweep_index))
        compare_axis = setup.parameter_sweeps[selection.compare_axis_index]
        current_sweep_index = selection.sweep_index
        series_entries: list[dict[str, object]] = []
        for value_index, sweep_value in enumerate(compare_axis.values):
            coordinates[selection.compare_axis_index] = value_index
            trace_sweep_index = encode_sweep_index(setup, tuple(coordinates))
            trace_selection = replace_sweep_index(selection, trace_sweep_index)
            trace_bundle = (
                bundle
                if trace_sweep_index == current_sweep_index
                else self._load_bundle_for_selection(context=context, selection=trace_selection)
            )
            matrices = trace_bundle.family_bundle[selection.family][selection.source]
            selected_values = _extract_metric_values(
                matrices,
                metric=selection.metric,
                output_port=selection.output_port,
                input_port=selection.input_port,
            )
            series_entries.append(
                _build_series_entry(
                    selection=trace_selection,
                    plot_context=plot_context,
                    values=selected_values,
                    compare_axis_label=_format_compare_axis_series_label(
                        compare_axis.parameter,
                        float(sweep_value),
                        compare_axis.unit,
                    ),
                )
            )
        return series_entries

    def _build_plot_series_from_trace_grid(
        self,
        *,
        context: ExplorerContext,
        selection: ResolvedSelection,
        trace_grid,
        plot_context: _PlotContext,
    ) -> list[dict[str, object]]:
        metric_grid = _extract_metric_grid_values(trace_grid.values, metric=selection.metric)
        if selection.compare_axis_index is None or trace_grid.compare_values is None:
            return [
                _build_series_entry(
                    selection=selection,
                    plot_context=plot_context,
                    values=[float(value) for value in metric_grid[:, 0]],
                )
            ]

        compare_axis = context.basis_task.simulation_setup.parameter_sweeps[
            selection.compare_axis_index
        ]
        coordinates = list(
            decode_sweep_index(
                context.basis_task.simulation_setup,
                selection.sweep_index,
            )
        )
        series_entries: list[dict[str, object]] = []
        for value_index, sweep_value in enumerate(trace_grid.compare_values):
            coordinates[selection.compare_axis_index] = value_index
            trace_sweep_index = encode_sweep_index(
                context.basis_task.simulation_setup,
                tuple(coordinates),
            )
            trace_selection = replace_sweep_index(selection, trace_sweep_index)
            series_entries.append(
                _build_series_entry(
                    selection=trace_selection,
                    plot_context=plot_context,
                    values=[float(value) for value in metric_grid[:, value_index]],
                    compare_axis_label=_format_compare_axis_series_label(
                        compare_axis.parameter,
                        float(sweep_value),
                        compare_axis.unit,
                    ),
                )
            )
        return series_entries


def build_base_payload(context: ExplorerContext) -> dict[str, object]:
    task = context.explorer_task
    return {
        "task_id": task.task_id,
        "task_status": task.status,
        "runtime_mode": "local" if task.visibility_scope == "local" else "online",
    }


def build_result_basis_payload(context: ExplorerContext) -> dict[str, object]:
    task = context.explorer_task
    return {
        "trace_payload_available": task.result_refs.trace_payload is not None,
        "primary_result_handle_id": (
            task.result_refs.result_handles[0].handle_id
            if len(task.result_refs.result_handles) > 0
            else None
        ),
        "trace_batch_id": task.result_refs.trace_batch_id,
    }


def _available_families(context: ExplorerContext) -> tuple[str, ...]:
    return tuple(
        family_key
        for family_key in ("s_matrix", "y_matrix", "z_matrix")
        if len(_available_sources(context, family_key)) > 0
    )


def _available_sources(context: ExplorerContext, family: str) -> tuple[str, ...]:
    return available_sources_for_task_family(context.explorer_task, family)


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
    values = [complex(matrix[output_index, input_index]) for matrix in matrices]
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


def _build_plot_context(
    *,
    context: ExplorerContext,
    selection: ResolvedSelection,
) -> _PlotContext:
    metric_config = FAMILY_METRICS[selection.family][selection.metric]
    output_label = context.port_options[selection.output_port]
    input_label = context.port_options[selection.input_port]
    selection_payload = {
        **{
            key: value
            for key, value in selection.to_mapping().items()
            if key not in {"sweep_index", "compare_axis_index"} or value is not None
        },
        "trace_mode_group": "base",
        "output_port_label": output_label,
        "input_port_label": input_label,
        "output_mode": "mode_0",
        "input_mode": "mode_0",
        "trace_key": selection.trace_key,
    }
    plot_metadata: dict[str, object] = {
        "trace_key": selection.trace_key,
        "family": selection.family,
        "source": selection.source,
        "metric": selection.metric,
        "z0_ohm": selection.z0_ohm,
        "output_port": selection.output_port,
        "input_port": selection.input_port,
        "output_port_label": output_label,
        "input_port_label": input_label,
        "trace_payload_store_key": (
            context.explorer_task.result_refs.trace_payload.store_key
            if context.explorer_task.result_refs.trace_payload is not None
            else None
        ),
    }
    if selection.sweep_index is not None:
        selection_payload["sweep_index"] = selection.sweep_index
        plot_metadata["sweep_index"] = selection.sweep_index
    if selection.compare_axis_index is not None:
        selection_payload["compare_axis_index"] = selection.compare_axis_index
        plot_metadata["compare_axis_index"] = selection.compare_axis_index
    return _PlotContext(
        metric_config=metric_config,
        selection_payload=selection_payload,
        plot_metadata=plot_metadata,
        base_series_id=(
            f"{selection.family}:{selection.source}:{selection.metric}:"
            f"{selection.output_port}:{selection.input_port}"
        ),
        base_series_label=(
            f"{SOURCE_LABELS[selection.source]} {selection.family.upper()} "
            f"{output_label} {input_label} {metric_config['label']}"
        ),
    )


def _build_plot_payload(
    *,
    selection_payload: dict[str, object],
    x_axis_values: tuple[float, ...],
    metric_config: Mapping[str, str],
    plot_series: list[dict[str, object]],
    plot_metadata: dict[str, object],
) -> dict[str, object]:
    return {
        "selection": selection_payload,
        "plot": {
            "x_axis": {
                "label": "Frequency",
                "unit": "GHz",
                "values": [float(value) for value in x_axis_values],
            },
            "y_axis": {
                "label": metric_config["label"],
                "unit": metric_config["unit"],
            },
            "series": plot_series,
            "metadata": plot_metadata,
        },
    }


def _build_series_entry(
    *,
    selection: ResolvedSelection,
    plot_context: _PlotContext,
    values: list[float],
    compare_axis_label: str | None = None,
) -> dict[str, object]:
    series_id = plot_context.base_series_id
    if selection.sweep_index is not None and compare_axis_label is not None:
        series_id = f"{series_id}:sweep:{selection.sweep_index}"
    return {
        "series_id": series_id,
        "label": compare_axis_label or plot_context.base_series_label,
        "trace_key": selection.trace_key,
        "values": values,
        "unit": plot_context.metric_config["unit"],
    }
