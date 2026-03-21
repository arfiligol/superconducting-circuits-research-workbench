"""Frequency-first sweep result view helpers."""

from __future__ import annotations

import re
from collections.abc import Callable, Mapping, Sequence
from typing import Any, cast

import numpy as np
import plotly.graph_objects as go
from nicegui import ui

from legacy.legacy_nicegui_archived.features.simulation.views.common import (
    _Z0_CONTROL_CLASSES,
    _Z0_CONTROL_PROPS,
    _user_storage_get,
    _with_test_id,
)
from legacy.legacy_nicegui_archived.features.simulation.views.plots import (
    _RESULT_TRACE_COLORS,
    _SWEEP_RESULT_FAMILY_OPTIONS,
    _build_simulation_result_figure,
    _coerce_int_value,
    _first_option_key,
    _result_metric_options_for_family,
    _result_mode_options,
    _result_port_options,
    _result_trace_options_for_family,
)
from legacy.legacy_nicegui_archived.features.simulation.views.raw_results import _default_result_trace_selection
from core.shared.visualization import get_plotly_layout
from core.simulation.application.run_simulation import (
    SimulationSweepAxis,
    SimulationSweepPointResult,
    SimulationSweepRun,
)
from core.simulation.domain.circuit import SimulationResult


def _format_sweep_value_token(value: float) -> str:
    """Format one sweep coordinate value into a compact stable token."""
    return f"{float(value):.10g}"


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


def _normalize_sweep_result_view_state(
    *,
    view_state: dict[str, Any],
    sweep_run: SimulationSweepRun,
    family_options: Mapping[str, str] | None = None,
    port_options: Mapping[int, str] | None = None,
    _sweep_source_from_sweep_run_cb: Callable[..., Any],
) -> dict[str, Any]:
    """Normalize sweep result-view selectors against one sweep payload."""
    return _normalize_sweep_result_view_state_from_source(
        view_state=view_state,
        sweep_source=_sweep_source_from_sweep_run_cb(
            sweep_run,
            port_options=port_options,
        ),
        family_options=family_options,
        port_options=port_options,
    )


def _normalize_sweep_result_view_state_from_source(
    *,
    view_state: dict[str, Any],
    sweep_source: Any,
    family_options: Mapping[str, str] | None = None,
    port_options: Mapping[int, str] | None = None,
) -> dict[str, Any]:
    """Normalize sweep result-view selectors against one resolved sweep source."""
    representative = sweep_source.representative_result
    resolved_family_options = (
        dict(family_options)
        if isinstance(family_options, Mapping)
        else _SWEEP_RESULT_FAMILY_OPTIONS
    )
    fallback_family = _first_option_key(resolved_family_options)
    family = str(view_state.get("family", fallback_family))
    if family not in resolved_family_options:
        family = fallback_family

    metric_options = _result_metric_options_for_family(family)
    metric = str(view_state.get("metric", _first_option_key(metric_options)))
    if metric not in metric_options:
        metric = _first_option_key(metric_options)

    resolved_port_options = (
        {int(key): str(value) for key, value in port_options.items()}
        if isinstance(port_options, Mapping) and port_options
        else dict(sweep_source.port_options)
    )
    mode_options = _result_mode_options(representative)
    trace_options = _result_trace_options_for_family(family)

    trace_entries = view_state.get("traces")
    if not isinstance(trace_entries, list):
        trace_entries = []
    if not trace_entries:
        legacy = view_state.get("trace_selection")
        if isinstance(legacy, Mapping):
            trace_entries = [legacy]

    default_port = next(iter(resolved_port_options)) if resolved_port_options else 1
    normalized_traces: list[dict[str, Any]] = []
    for raw_trace in trace_entries:
        if not isinstance(raw_trace, Mapping):
            continue
        trace_key = str(raw_trace.get("trace", _first_option_key(trace_options)))
        if trace_key not in trace_options:
            trace_key = _first_option_key(trace_options)
        output_mode = SimulationResult.parse_mode_token(
            SimulationResult.mode_token(tuple(raw_trace.get("output_mode", (0,))))
        )
        input_mode = SimulationResult.parse_mode_token(
            SimulationResult.mode_token(tuple(raw_trace.get("input_mode", (0,))))
        )
        if SimulationResult.mode_token(output_mode) not in mode_options:
            output_mode = SimulationResult.parse_mode_token(_first_option_key(mode_options))
        if SimulationResult.mode_token(input_mode) not in mode_options:
            input_mode = SimulationResult.parse_mode_token(_first_option_key(mode_options))

        output_port = _coerce_int_value(raw_trace.get("output_port"), default_port)
        input_port = _coerce_int_value(raw_trace.get("input_port"), default_port)
        if output_port not in resolved_port_options:
            output_port = default_port
        if input_port not in resolved_port_options:
            input_port = default_port
        normalized_traces.append(
            {
                "trace": trace_key,
                "output_mode": tuple(output_mode),
                "output_port": output_port,
                "input_mode": tuple(input_mode),
                "input_port": input_port,
                "sweep_axis_index": raw_trace.get("sweep_axis_index"),
            }
        )
    frequency_count = max(len(representative.frequencies_ghz), 1)
    frequency_index = _coerce_int_value(view_state.get("frequency_index"), 0)
    frequency_index = max(0, min(frequency_count - 1, frequency_index))
    z0 = float(view_state.get("z0", 50.0) or 50.0)
    if z0 <= 0:
        z0 = 50.0

    axis_keys = [axis.target_value_ref for axis in sweep_source.axes]
    view_axis_target = str(view_state.get("view_axis_target_value_ref", "")).strip()
    if view_axis_target not in axis_keys:
        view_axis_target = axis_keys[0] if axis_keys else ""
    compare_axis = next(
        (axis for axis in sweep_source.axes if axis.target_value_ref == view_axis_target),
        sweep_source.axes[0],
    )
    compare_axis_position = next(
        idx
        for idx, axis in enumerate(sweep_source.axes)
        if axis.target_value_ref == compare_axis.target_value_ref
    )
    representative_axis_index = _resolve_representative_axis_index(
        representative_axis_indices=sweep_source.representative_axis_indices,
        axis_position=compare_axis_position,
        axis=compare_axis,
    )
    if not normalized_traces:
        normalized_traces = [
            _default_sweep_result_trace_selection(
                representative,
                family,
                port_options=dict(port_options) if port_options is not None else {},
                sweep_axis_index=representative_axis_index,
            )
        ]
    raw_fixed_indices = view_state.get("fixed_axis_indices")
    fixed_indices_input = raw_fixed_indices if isinstance(raw_fixed_indices, Mapping) else {}
    fixed_axis_indices: dict[str, int] = {}
    for axis in sweep_source.axes:
        if axis.target_value_ref == view_axis_target:
            continue
        default_axis_index = len(axis.values) // 2
        axis_index = _coerce_sweep_axis_option_index(
            axis,
            fixed_indices_input.get(axis.target_value_ref),
            default_axis_index,
        )
        axis_index = max(0, min(len(axis.values) - 1, axis_index))
        fixed_axis_indices[axis.target_value_ref] = axis_index

    for trace in normalized_traces:
        sweep_axis_index = _coerce_sweep_axis_option_index(
            compare_axis,
            trace.get("sweep_axis_index"),
            representative_axis_index,
        )
        trace["sweep_axis_index"] = max(0, min(len(compare_axis.values) - 1, sweep_axis_index))

    normalized = {
        "family": family,
        "metric": metric,
        "z0": z0,
        "frequency_index": frequency_index,
        "view_axis_target_value_ref": view_axis_target,
        "representative_axis_index": representative_axis_index,
        "fixed_axis_indices": fixed_axis_indices,
        "traces": normalized_traces,
        "trace_selection": dict(normalized_traces[0]),
    }
    view_state.update(normalized)
    return normalized


def _sweep_axis_display_label(axis: SimulationSweepAxis) -> str:
    """Format one sweep axis key into compact selector text."""
    if str(axis.unit).strip():
        return f"{axis.target_value_ref} ({axis.unit})"
    return axis.target_value_ref


def _sweep_axis_index_options(axis: SimulationSweepAxis) -> dict[int, str]:
    """Build fixed-axis index selector options."""
    options: dict[int, str] = {}
    for idx, value in enumerate(axis.values):
        token = _format_sweep_value_token(float(value))
        if str(axis.unit).strip():
            options[idx] = f"{idx + 1}: {token} {axis.unit}"
        else:
            options[idx] = f"{idx + 1}: {token}"
    return options


def _coerce_sweep_axis_option_index(
    axis: SimulationSweepAxis,
    raw_value: Any,
    default_index: int,
) -> int:
    """Resolve one sweep-axis selector value from option key or rendered label text."""
    raw_text = str(raw_value).strip()
    if isinstance(raw_value, int):
        if 0 <= raw_value < len(axis.values):
            return raw_value
    elif raw_text and raw_text.lstrip("-").isdigit():
        resolved = int(raw_text)
        if 0 <= resolved < len(axis.values):
            return resolved

    if raw_text:
        normalized_text = re.sub(r"\s+", " ", raw_text).strip().casefold()
        for axis_index, label in _sweep_axis_index_options(axis).items():
            normalized_label = re.sub(r"\s+", " ", label).strip().casefold()
            if normalized_text == normalized_label:
                return axis_index
    return max(0, min(len(axis.values) - 1, default_index))


def _resolve_sweep_point_axis_index(
    point: SimulationSweepPointResult,
    *,
    axis_position: int,
    axis: SimulationSweepAxis,
) -> int:
    """Resolve one point's index on the requested sweep axis."""
    if axis_position < len(point.axis_indices):
        axis_index = int(point.axis_indices[axis_position])
    else:
        axis_value = point.axis_values.get(axis.target_value_ref, axis.values[0])
        axis_index = min(
            range(len(axis.values)),
            key=lambda idx: abs(float(axis.values[idx]) - float(axis_value)),
        )
    return max(0, min(len(axis.values) - 1, axis_index))


def _sweep_metric_series_for_point(
    *,
    result: SimulationResult,
    family: str,
    metric: str,
    trace_selection: Mapping[str, Any],
    z0: float,
    dark_mode: bool,
    port_label_by_index: Mapping[int, str] | None = None,
    build_simulation_result_figure_cb: Callable[..., Any] = _build_simulation_result_figure,
) -> tuple[list[float | None], str, str]:
    """Resolve one scalar metric series across frequency for one sweep point."""
    figure = build_simulation_result_figure_cb(
        result=result,
        view_family=family,
        metric=metric,
        trace=str(trace_selection.get("trace", "s")),
        output_mode=tuple(trace_selection.get("output_mode", (0,))),
        output_port=int(trace_selection.get("output_port", 1)),
        input_mode=tuple(trace_selection.get("input_mode", (0,))),
        input_port=int(trace_selection.get("input_port", 1)),
        reference_impedance_ohm=float(z0),
        dark_mode=dark_mode,
        trace_selections=[
            {
                "trace": str(trace_selection.get("trace", "s")),
                "output_mode": tuple(trace_selection.get("output_mode", (0,))),
                "output_port": int(trace_selection.get("output_port", 1)),
                "input_mode": tuple(trace_selection.get("input_mode", (0,))),
                "input_port": int(trace_selection.get("input_port", 1)),
            }
        ],
        port_label_by_index=dict(port_label_by_index) if port_label_by_index else None,
    )
    if not figure.data:
        return ([], "", "")

    resolved_values: list[float | None] = []
    y_values = getattr(figure.data[0], "y", [])
    for raw in list(cast(Sequence[object], y_values)):
        if not isinstance(raw, int | float | str):
            resolved_values.append(None)
            continue
        try:
            value = float(raw)
        except Exception:
            resolved_values.append(None)
            continue
        resolved_values.append(value if np.isfinite(value) else None)
    trace_label = str(getattr(figure.data[0], "name", "") or "")
    y_axis_title = str(getattr(figure.layout.yaxis.title, "text", "") or "")
    return (resolved_values, trace_label, y_axis_title)


def _build_sweep_metric_rows(
    *,
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
    _resolve_sweep_result_source_cb: Callable[..., Any],
    _build_simulation_result_figure_cb: Callable[..., Any] = _build_simulation_result_figure,
) -> dict[str, Any]:
    """Build one frequency-first multi-trace sweep compare payload."""
    sweep_source = _resolve_sweep_result_source_cb(
        sweep_payload=sweep_payload,
        trace_store_bundle=trace_store_bundle,
    )
    representative = sweep_source.representative_result
    axis_by_target = {axis.target_value_ref: axis for axis in sweep_source.axes}
    if not axis_by_target:
        raise ValueError("Sweep payload has no axis metadata.")

    resolved_view_axis_target = str(view_axis_target_value_ref or "").strip()
    if resolved_view_axis_target not in axis_by_target:
        resolved_view_axis_target = sweep_source.axes[0].target_value_ref
    view_axis = axis_by_target[resolved_view_axis_target]
    view_axis_position = next(
        idx
        for idx, axis in enumerate(sweep_source.axes)
        if axis.target_value_ref == resolved_view_axis_target
    )

    resolved_fixed_axis_indices: dict[str, int] = {}
    raw_fixed_indices = fixed_axis_indices if isinstance(fixed_axis_indices, Mapping) else {}
    for axis in sweep_source.axes:
        if axis.target_value_ref == resolved_view_axis_target:
            continue
        axis_index = _coerce_int_value(
            raw_fixed_indices.get(axis.target_value_ref),
            len(axis.values) // 2,
        )
        axis_index = max(0, min(len(axis.values) - 1, axis_index))
        resolved_fixed_axis_indices[axis.target_value_ref] = axis_index

    raw_trace_selections: list[Mapping[str, Any]] = []
    if isinstance(trace_selections, list) and trace_selections:
        raw_trace_selections = [entry for entry in trace_selections if isinstance(entry, Mapping)]
    elif isinstance(trace_selection, Mapping):
        raw_trace_selections = [trace_selection]
    if not raw_trace_selections:
        raw_trace_selections = [
            _default_result_trace_selection(
                representative,
                family,
                port_options=_result_port_options(representative),
            )
        ]

    figure = go.Figure()
    trace_labels: list[str] = []
    trace_details: list[dict[str, Any]] = []
    y_axis_title = ""
    resolved_points: list[tuple[Any, int, float]] = []
    for trace_index, resolved_trace_selection in enumerate(raw_trace_selections, start=1):
        requested_axis_index = _coerce_int_value(
            resolved_trace_selection.get("sweep_axis_index"),
            sweep_source.representative_point_index if len(view_axis.values) == 1 else 0,
        )
        requested_axis_index = max(0, min(len(view_axis.values) - 1, requested_axis_index))
        requested_point_indices = []
        for axis_position, axis in enumerate(sweep_source.axes):
            if axis_position == view_axis_position:
                requested_point_indices.append(requested_axis_index)
                continue
            requested_point_indices.append(
                int(
                    resolved_fixed_axis_indices.get(
                        axis.target_value_ref,
                        len(axis.values) // 2,
                    )
                )
            )
        matching_point = sweep_source.read_point(tuple(requested_point_indices))
        if matching_point is None:
            continue
        axis_value = float(
            matching_point.axis_values.get(
                view_axis.target_value_ref,
                view_axis.values[requested_axis_index],
            )
        )
        point_series, trace_label, axis_title = _sweep_metric_series_for_point(
            result=matching_point.result,
            family=family,
            metric=metric,
            trace_selection=resolved_trace_selection,
            z0=z0,
            dark_mode=dark_mode,
            port_label_by_index=port_label_by_index,
            build_simulation_result_figure_cb=_build_simulation_result_figure_cb,
        )
        if not point_series:
            continue
        if axis_title and not y_axis_title:
            y_axis_title = axis_title
        axis_value_token = _format_sweep_value_token(axis_value)
        axis_value_label = (
            f"{axis_value_token} {view_axis.unit}"
            if str(view_axis.unit).strip()
            else axis_value_token
        )
        base_label = trace_label or f"Trace {trace_index}"
        resolved_label = f"{base_label} | {view_axis.target_value_ref}={axis_value_label}"
        trace_labels.append(resolved_label)
        trace_details.append(
            {
                "trace_index": trace_index,
                "point_index": int(matching_point.point_index),
                "axis_index": requested_axis_index,
                "axis_value": axis_value,
                "axis_value_label": axis_value_label,
                "trace_label": resolved_label,
            }
        )
        figure.add_trace(
            go.Scatter(
                x=list(matching_point.result.frequencies_ghz),
                y=list(point_series),
                mode="lines",
                name=resolved_label,
                line={
                    "color": _RESULT_TRACE_COLORS[(trace_index - 1) % len(_RESULT_TRACE_COLORS)],
                    "width": 2,
                },
            )
        )
        resolved_points.append((matching_point, requested_axis_index, axis_value))

    if not figure.data:
        raise ValueError("No sweep points match current compare-axis selectors.")

    metric_label = _result_metric_options_for_family(family).get(metric, metric)
    axis_label = (
        f"{view_axis.target_value_ref} ({view_axis.unit})"
        if str(view_axis.unit).strip()
        else view_axis.target_value_ref
    )
    theme_layout = dict(get_plotly_layout(dark=dark_mode))
    figure.update_layout(theme_layout)
    figure.update_layout(
        title=f"{metric_label} vs Frequency",
        xaxis_title="Frequency (GHz)",
        yaxis_title=y_axis_title or metric_label,
    )
    return {
        "figure": figure,
        "axis_label": axis_label,
        "metric_label": metric_label,
        "trace_labels": trace_labels,
        "trace_details": trace_details,
        "view_axis_target_value_ref": view_axis.target_value_ref,
        "dimension": len(sweep_source.axes),
        "point_count": int(sweep_source.point_count),
        "slice_point_count": len(resolved_points),
        "fixed_axis_indices": resolved_fixed_axis_indices,
        "fixed_axis_details": [
            {
                "target_value_ref": axis.target_value_ref,
                "index": resolved_fixed_axis_indices[axis.target_value_ref],
                "value": float(axis.values[resolved_fixed_axis_indices[axis.target_value_ref]]),
                "unit": str(axis.unit),
            }
            for axis in sweep_source.axes
            if axis.target_value_ref in resolved_fixed_axis_indices
        ],
    }


def _render_sweep_result_view_container(
    *,
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
    _resolve_sweep_result_source_cb: Callable[..., Any],
    _build_sweep_metric_rows_cb: Callable[..., dict[str, Any]] | None = None,
) -> None:
    """Render one frequency-first sweep compare view from a canonical or adapted sweep payload."""
    build_rows = _build_sweep_metric_rows_cb or _build_sweep_metric_rows
    container.clear()
    if trace_store_bundle is None and not isinstance(sweep_payload, Mapping):
        with container:
            ui.label(empty_message).classes("text-sm text-muted")
        return
    try:
        sweep_source = _resolve_sweep_result_source_cb(
            sweep_payload=sweep_payload,
            trace_store_bundle=trace_store_bundle,
        )
    except Exception as exc:
        with container:
            ui.label(f"Sweep payload decode failed: {exc}").classes("text-sm text-warning")
        return
    if sweep_source.point_count <= 0:
        with container:
            ui.label("Sweep payload has no points to visualize.").classes("text-sm text-muted")
        return

    normalized_state = _normalize_sweep_result_view_state_from_source(
        view_state=view_state,
        sweep_source=sweep_source,
        family_options=family_options,
        port_options=sweep_source.port_options,
    )
    family = str(normalized_state["family"])
    metric = str(normalized_state["metric"])
    z0_value = float(normalized_state["z0"])
    view_axis_target_value_ref = str(normalized_state["view_axis_target_value_ref"])
    fixed_axis_indices = dict(normalized_state["fixed_axis_indices"])
    traces = list(normalized_state["traces"])
    representative = sweep_source.representative_result
    metric_options = _result_metric_options_for_family(family)
    mode_options = _result_mode_options(representative)
    port_options = dict(sweep_source.port_options)
    trace_options = _result_trace_options_for_family(family)
    axis_options = {
        axis.target_value_ref: _sweep_axis_display_label(axis) for axis in sweep_source.axes
    }
    try:
        payload = build_rows(
            sweep_payload=sweep_payload,
            trace_store_bundle=trace_store_bundle,
            family=family,
            metric=metric,
            trace_selections=traces,
            view_axis_target_value_ref=view_axis_target_value_ref,
            fixed_axis_indices=fixed_axis_indices,
            z0=z0_value,
            frequency_index=0,
            dark_mode=bool(_user_storage_get("dark_mode", True)),
            port_label_by_index=port_options,
            _resolve_sweep_result_source_cb=_resolve_sweep_result_source_cb,
        )
    except Exception as exc:
        with container:
            ui.label(f"Sweep view rendering failed: {exc}").classes("text-sm text-warning")
        return
    view_state["view_axis_target_value_ref"] = str(payload["view_axis_target_value_ref"])
    view_state["fixed_axis_indices"] = dict(payload["fixed_axis_indices"])
    axis_label = str(payload["axis_label"])
    fixed_axis_details = list(payload["fixed_axis_details"])
    fixed_axis_summary = (
        "; ".join(
            (
                f"{item['target_value_ref']}="
                f"{_format_sweep_value_token(float(item['value']))}"
                f"{(' ' + str(item['unit'])) if str(item['unit']).strip() else ''}"
            )
            for item in fixed_axis_details
        )
        if fixed_axis_details
        else "-"
    )
    summary_line = (f"{summary_prefix} | " if summary_prefix else "") + (
        f"dim={int(payload['dimension'])} | "
        f"total={int(payload['point_count'])} points | "
        f"compare={axis_label} | "
        f"selected={int(payload['slice_point_count'])} traces | "
        f"fixed={fixed_axis_summary}"
    )

    with container:
        with _with_test_id(ui.column().classes("w-full gap-3"), f"{testid_prefix}-results-view"):
            with ui.row().classes("w-full items-center justify-between gap-3 mb-2 flex-wrap"):
                with ui.column().classes("gap-1"):
                    ui.label(title).classes("text-sm font-bold text-fg")
                    if header_message:
                        ui.label(header_message).classes("text-xs text-muted")
                    for line in context_lines:
                        if line:
                            ui.label(line).classes("text-xs text-muted")
                    ui.label(summary_line).classes("text-xs text-muted")
                if save_button_label is not None and on_save_click is not None:
                    save_button = ui.button(
                        save_button_label,
                        icon="save",
                        on_click=on_save_click,
                    ).props("outline color=primary size=sm")
                    _with_test_id(save_button, f"{testid_prefix}-save-button")
                    if not save_enabled:
                        save_button.disable()

            with ui.row().classes("w-full items-end gap-3 flex-wrap mt-1"):
                family_select = (
                    ui.select(label="Family", options=dict(family_options), value=family)
                    .props("dense outlined options-dense")
                    .classes("w-44")
                )
                _with_test_id(family_select, f"{testid_prefix}-family-select")
                metric_select = (
                    ui.select(label="Metric", options=metric_options, value=metric)
                    .props("dense outlined options-dense")
                    .classes("w-56")
                )
                _with_test_id(metric_select, f"{testid_prefix}-metric-select")
                view_axis_select = (
                    ui.select(
                        label="Compare Axis",
                        options=axis_options,
                        value=str(payload["view_axis_target_value_ref"]),
                    )
                    .props("dense outlined options-dense")
                    .classes("w-56")
                )
                _with_test_id(view_axis_select, f"{testid_prefix}-view-axis-select")
                z0_input = (
                    ui.number("Z0 (Ohm)", value=z0_value, format="%.6g")
                    .props(_Z0_CONTROL_PROPS)
                    .classes(_Z0_CONTROL_CLASSES)
                )
                _with_test_id(z0_input, f"{testid_prefix}-z0-input")

            with ui.row().classes("w-full items-end gap-3 flex-wrap mt-1"):
                fixed_selects: list[tuple[str, Any]] = []
                fixed_position = 0
                for axis in sweep_source.axes:
                    if axis.target_value_ref == str(payload["view_axis_target_value_ref"]):
                        continue
                    fixed_position += 1
                    fixed_select = (
                        ui.select(
                            label=f"Fixed: {axis.target_value_ref}",
                            options=_sweep_axis_index_options(axis),
                            value=int(
                                payload["fixed_axis_indices"].get(
                                    axis.target_value_ref,
                                    len(axis.values) // 2,
                                )
                            ),
                        )
                        .props("dense outlined options-dense")
                        .classes("w-72")
                    )
                    _with_test_id(fixed_select, f"{testid_prefix}-fixed-axis-select-{fixed_position}")
                    fixed_selects.append((axis.target_value_ref, fixed_select))

        def _rerender() -> None:
            _render_sweep_result_view_container(
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
                _resolve_sweep_result_source_cb=_resolve_sweep_result_source_cb,
                _build_sweep_metric_rows_cb=build_rows,
            )

        def _on_sweep_family_change(selected_family: str) -> None:
            metric_choices = _result_metric_options_for_family(selected_family)
            view_state["family"] = selected_family
            view_state["metric"] = _first_option_key(metric_choices)
            view_state["traces"] = [
                _default_sweep_result_trace_selection(
                    representative,
                    selected_family,
                    port_options=port_options,
                    sweep_axis_index=_coerce_int_value(
                        view_state.get("representative_axis_index", 0),
                        0,
                    ),
                )
            ]
            view_state["trace_selection"] = dict(view_state["traces"][0])
            _rerender()

        family_select.on_value_change(lambda e: _on_sweep_family_change(str(e.value or "s")))
        metric_select.on_value_change(
            lambda e: (view_state.__setitem__("metric", str(e.value or metric)), _rerender())
        )
        view_axis_select.on_value_change(
            lambda e: (
                view_state.__setitem__(
                    "view_axis_target_value_ref",
                    str(e.value or payload["view_axis_target_value_ref"]),
                ),
                _rerender(),
            )
        )
        for target, fixed_select in fixed_selects:
            fixed_select.on_value_change(
                lambda e, target=target: (
                    view_state["fixed_axis_indices"].__setitem__(target, _coerce_int_value(e.value, 0)),
                    _rerender(),
                )
            )

        def _commit_sweep_z0(raw_value: Any) -> None:
            try:
                resolved = float(raw_value)
            except Exception:
                return
            if resolved <= 0:
                return
            if float(view_state.get("z0", 50.0)) == resolved:
                return
            view_state["z0"] = resolved
            _rerender()

        z0_input.on("keydown.enter", lambda _e: _commit_sweep_z0(z0_input.value))
        z0_input.on("blur", lambda _e: _commit_sweep_z0(z0_input.value))

        compare_axis = next(
            axis
            for axis in sweep_source.axes
            if axis.target_value_ref == str(payload["view_axis_target_value_ref"])
        )

        def _next_sweep_axis_index() -> int:
            existing = {
                _coerce_int_value(entry.get("sweep_axis_index"), 0)
                for entry in list(view_state.get("traces", []))
                if isinstance(entry, Mapping)
            }
            for axis_index in range(len(compare_axis.values)):
                if axis_index not in existing:
                    return axis_index
            if not compare_axis.values:
                return 0
            return max(0, min(len(compare_axis.values) - 1, len(existing) % len(compare_axis.values)))

        with ui.row().classes("w-full items-center gap-3 mt-2"):
            add_trace_button = ui.button(
                "Add Trace",
                icon="add",
                on_click=lambda: (
                    view_state["traces"].append(
                        _default_sweep_result_trace_selection(
                            representative,
                            family,
                            port_options=port_options,
                            sweep_axis_index=_next_sweep_axis_index(),
                        )
                    ),
                    _rerender(),
                ),
            ).props("outline color=primary")
            _with_test_id(add_trace_button, f"{testid_prefix}-add-trace-button")

        def _update_trace(trace_index: int, *, field: str, value: Any) -> None:
            traces_state = list(view_state.get("traces", []))
            if trace_index < 0 or trace_index >= len(traces_state):
                return
            traces_state[trace_index] = {**traces_state[trace_index], field: value}
            view_state["traces"] = traces_state
            view_state["trace_selection"] = dict(traces_state[0])
            _rerender()

        for trace_idx, selection in enumerate(list(view_state.get("traces", [])), start=1):
            with _with_test_id(
                ui.card().classes("w-full bg-elevated border border-border rounded-lg p-4 mt-2"),
                f"{testid_prefix}-trace-card-{trace_idx}",
            ):
                with ui.row().classes("w-full items-center gap-3 mb-2"):
                    ui.label(f"Trace {trace_idx}").classes("text-sm font-bold text-fg")
                    if len(list(view_state.get("traces", []))) > 1:
                        ui.button(
                            "",
                            icon="delete",
                            on_click=lambda _e, trace_index=trace_idx - 1: (
                                view_state["traces"].pop(trace_index),
                                view_state.__setitem__("trace_selection", dict(view_state["traces"][0])),
                                _rerender(),
                            ),
                        ).props("flat color=negative round").classes("ml-auto")
                with ui.row().classes("w-full gap-3 items-end flex-wrap"):
                    sweep_value_select = (
                        ui.select(
                            label="Sweep Value",
                            options=_sweep_axis_index_options(compare_axis),
                            value=_coerce_int_value(selection.get("sweep_axis_index"), 0),
                        )
                        .props("dense outlined options-dense")
                        .classes("w-56")
                    )
                    trace_select = (
                        ui.select(label="Trace", options=trace_options, value=selection["trace"])
                        .props("dense outlined options-dense")
                        .classes("w-56")
                    )
                    if trace_idx == 1:
                        _with_test_id(trace_select, f"{testid_prefix}-trace-select")
                    _with_test_id(sweep_value_select, f"{testid_prefix}-sweep-value-select-{trace_idx}")
                    _with_test_id(trace_select, f"{testid_prefix}-trace-select-{trace_idx}")
                    output_mode_select = (
                        ui.select(
                            label="Output Mode",
                            options=mode_options,
                            value=SimulationResult.mode_token(tuple(selection["output_mode"])),
                        )
                        .props("dense outlined options-dense")
                        .classes("w-52")
                    )
                    input_mode_select = (
                        ui.select(
                            label="Input Mode",
                            options=mode_options,
                            value=SimulationResult.mode_token(tuple(selection["input_mode"])),
                        )
                        .props("dense outlined options-dense")
                        .classes("w-52")
                    )
                    output_port_select = (
                        ui.select(label="Output Port", options=port_options, value=int(selection["output_port"]))
                        .props("dense outlined options-dense")
                        .classes("w-44")
                    )
                    input_port_select = (
                        ui.select(label="Input Port", options=port_options, value=int(selection["input_port"]))
                        .props("dense outlined options-dense")
                        .classes("w-44")
                    )

                sweep_value_select.on_value_change(
                    lambda e, trace_index=trace_idx - 1: _update_trace(
                        trace_index,
                        field="sweep_axis_index",
                        value=_coerce_int_value(e.value, 0),
                    )
                )
                trace_select.on_value_change(
                    lambda e, trace_index=trace_idx - 1: _update_trace(
                        trace_index,
                        field="trace",
                        value=str(e.value or _first_option_key(trace_options)),
                    )
                )
                output_mode_select.on_value_change(
                    lambda e, trace_index=trace_idx - 1: _update_trace(
                        trace_index,
                        field="output_mode",
                        value=tuple(SimulationResult.parse_mode_token(str(e.value or "0"))),
                    )
                )
                input_mode_select.on_value_change(
                    lambda e, trace_index=trace_idx - 1: _update_trace(
                        trace_index,
                        field="input_mode",
                        value=tuple(SimulationResult.parse_mode_token(str(e.value or "0"))),
                    )
                )
                output_port_select.on_value_change(
                    lambda e, trace_index=trace_idx - 1: _update_trace(
                        trace_index,
                        field="output_port",
                        value=_coerce_int_value(e.value, next(iter(port_options))),
                    )
                )
                input_port_select.on_value_change(
                    lambda e, trace_index=trace_idx - 1: _update_trace(
                        trace_index,
                        field="input_port",
                        value=_coerce_int_value(e.value, next(iter(port_options))),
                    )
                )

        if payload.get("trace_details"):
            with ui.row().classes("w-full gap-2 flex-wrap mt-3"):
                for detail in payload["trace_details"]:
                    ui.badge(
                        f"Trace {int(detail['trace_index'])}: {axis_label}={detail['axis_value_label']}",
                        color="primary",
                    ).props("outline")
        sweep_plot = ui.plotly(payload["figure"]).classes("w-full min-h-[340px] mt-3")
        _with_test_id(sweep_plot, f"{testid_prefix}-plot")
