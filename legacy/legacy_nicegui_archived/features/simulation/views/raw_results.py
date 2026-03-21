"""Raw simulation result view composition helpers."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, cast

from nicegui import ui

from legacy.legacy_nicegui_archived.features.simulation.views.common import (
    _Z0_CONTROL_CLASSES,
    _Z0_CONTROL_PROPS,
    _user_storage_get,
    _with_test_id,
)
from legacy.legacy_nicegui_archived.features.simulation.views.plots import (
    _ResultTraceSelection,
    _build_simulation_result_figure,
    _coerce_int_value,
    _first_option_key,
    _resolve_option_key,
    _result_metric_options_for_family,
    _result_mode_options,
    _result_port_options,
    _result_trace_options_for_family,
)
from core.simulation.domain.circuit import SimulationResult

_RAW_RESULT_MATRIX_SOURCE_OPTIONS_BY_FAMILY = {
    "admittance": {"raw": "Raw Y", "ptc": "PTC Y"},
    "impedance": {"raw": "Raw Z", "ptc": "PTC Z"},
}
_RAW_RESULT_MATRIX_SOURCE_LABEL_BY_FAMILY = {
    "admittance": "Y Source",
    "impedance": "Z Source",
}


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


def _render_result_family_explorer(
    *,
    container: Any,
    view_state: dict[str, Any],
    family_options: dict[str, str],
    result_provider: Callable[[float, str, str], tuple[SimulationResult, dict[int, str]] | None],
    header_message: str,
    empty_message: str,
    save_button_label: str | None = None,
    on_save_click: Callable[[], None] | None = None,
    save_enabled: bool = True,
    context_line: str | None = None,
    context_lines: tuple[str, ...] = (),
    family_source_options: dict[str, dict[str, str]] | None = None,
    family_source_labels: dict[str, str] | None = None,
    testid_prefix: str | None = None,
) -> None:
    """Render one family/metric/trace-card result explorer into a container."""

    def render() -> None:
        container.clear()
        with container:
            with ui.row().classes("w-full items-center justify-between gap-3 mb-3 flex-wrap"):
                ui.label(header_message).classes("text-xs text-muted")
                if save_button_label is not None and on_save_click is not None:
                    save_button = ui.button(
                        save_button_label,
                        icon="save",
                        on_click=on_save_click,
                    ).props("outline color=primary size=sm")
                    if testid_prefix:
                        _with_test_id(save_button, f"{testid_prefix}-save-button")
                    if not save_enabled:
                        save_button.disable()

            resolved_context_lines = [
                line for line in ((context_line,) if context_line else ()) + context_lines if line
            ]
            for line in resolved_context_lines:
                ui.label(line).classes("text-xs text-muted mb-1")

            family_tabs = list(family_options.items())
            family_keys = {family for family, _ in family_tabs}
            family_label_to_key = {label.casefold(): family for family, label in family_tabs}
            fallback_family = family_tabs[0][0] if family_tabs else "s"
            view_family = str(view_state.get("family", fallback_family))
            if view_family not in family_keys:
                view_family = fallback_family
                view_state["family"] = view_family

            source_options_by_family = (
                dict(family_source_options) if isinstance(family_source_options, dict) else {}
            )
            source_labels_by_family = (
                dict(family_source_labels) if isinstance(family_source_labels, dict) else {}
            )
            source_options = dict(source_options_by_family.get(view_family, {}))
            selected_source = ""
            if source_options:
                family_sources_state = view_state.get("family_sources")
                if not isinstance(family_sources_state, dict):
                    family_sources_state = {}
                    view_state["family_sources"] = family_sources_state
                selected_source = _resolve_option_key(
                    source_options,
                    family_sources_state.get(view_family, _first_option_key(source_options)),
                )
                if selected_source not in source_options:
                    selected_source = _first_option_key(source_options)
                    family_sources_state[view_family] = selected_source

            metric_options = _result_metric_options_for_family(view_family)
            metric_key = str(view_state.get("metric", ""))
            if metric_key not in metric_options:
                metric_key = _first_option_key(metric_options)
                view_state["metric"] = metric_key

            z0_value = float(view_state.get("z0", 50.0) or 50.0)
            try:
                resolved_payload = result_provider(
                    z0_value,
                    view_family,
                    selected_source,
                )
            except Exception as exc:
                with ui.column().classes("w-full items-center justify-center py-10"):
                    ui.icon("error", size="lg").classes("text-danger mb-3")
                    ui.label(f"Result View rendering failed: {exc}").classes("text-sm text-danger")
                return
            if resolved_payload is None:
                with ui.column().classes("w-full items-center justify-center py-10"):
                    ui.icon("show_chart", size="xl").classes("text-muted mb-3 opacity-50")
                    ui.label(empty_message).classes("text-sm text-muted")
                return

            result_to_render, port_options = resolved_payload
            mode_options = _result_mode_options(result_to_render)
            if not port_options:
                port_options = _result_port_options(result_to_render)
            if not mode_options or not port_options:
                ui.label("Result bundle does not contain selectable mode/port entries.").classes(
                    "text-sm text-warning"
                )
                return

            trace_options = _result_trace_options_for_family(view_family)
            normalized_traces: list[_ResultTraceSelection] = []
            for trace in list(view_state.get("traces") or []):
                trace_key = str(trace.get("trace", _first_option_key(trace_options)))
                if trace_key not in trace_options:
                    trace_key = _first_option_key(trace_options)
                output_mode = trace.get("output_mode", (0,))
                input_mode = trace.get("input_mode", (0,))
                output_port = _coerce_int_value(trace.get("output_port"), next(iter(port_options)))
                input_port = _coerce_int_value(trace.get("input_port"), next(iter(port_options)))
                output_mode_token = SimulationResult.mode_token(tuple(output_mode))
                input_mode_token = SimulationResult.mode_token(tuple(input_mode))
                if output_mode_token not in mode_options:
                    output_mode = SimulationResult.parse_mode_token(_first_option_key(mode_options))
                if input_mode_token not in mode_options:
                    input_mode = SimulationResult.parse_mode_token(_first_option_key(mode_options))
                if output_port not in port_options:
                    output_port = next(iter(port_options))
                if input_port not in port_options:
                    input_port = next(iter(port_options))
                normalized_traces.append(
                    {
                        "trace": trace_key,
                        "output_mode": tuple(output_mode),
                        "output_port": output_port,
                        "input_mode": tuple(input_mode),
                        "input_port": input_port,
                    }
                )
            if not normalized_traces:
                normalized_traces = [
                    _default_result_trace_selection(
                        result_to_render,
                        view_family,
                        port_options=port_options,
                    )
                ]
            view_state["traces"] = normalized_traces

            with ui.row().classes("w-full items-end justify-between gap-3 flex-wrap"):
                with ui.tabs(value=cast(Any, view_family)).classes("mb-1") as family_switch:
                    for family_key, family_label in family_tabs:
                        ui.tab(family_key, label=family_label)
                if testid_prefix:
                    _with_test_id(family_switch, f"{testid_prefix}-family-tabs")
                source_select = None
                if source_options:
                    source_select = (
                        ui.select(
                            label=source_labels_by_family.get(view_family, "Source"),
                            options=source_options,
                            value=selected_source,
                        )
                        .props("dense outlined options-dense")
                        .classes("w-52")
                    )
                    if testid_prefix:
                        _with_test_id(source_select, f"{testid_prefix}-matrix-source-select")
                metric_select = (
                    ui.select(label="Metric", options=metric_options, value=metric_key)
                    .props("dense outlined options-dense")
                    .classes("w-64")
                )
                if testid_prefix:
                    _with_test_id(metric_select, f"{testid_prefix}-metric-select")
                z0_input = (
                    ui.number(
                        "Z0 (Ohm)",
                        value=float(view_state.get("z0", 50.0) or 50.0),
                        format="%.6g",
                    )
                    .props(_Z0_CONTROL_PROPS)
                    .classes(_Z0_CONTROL_CLASSES)
                )
                if testid_prefix:
                    _with_test_id(z0_input, f"{testid_prefix}-z0-input")

            def _on_family_change(e: Any) -> None:
                selected_family = str(e.value or fallback_family).strip()
                if selected_family not in family_keys:
                    selected_family = family_label_to_key.get(
                        selected_family.casefold(),
                        fallback_family,
                    )
                view_state["family"] = selected_family
                view_state["metric"] = _first_option_key(
                    _result_metric_options_for_family(selected_family)
                )
                view_state["traces"] = [
                    _default_result_trace_selection(
                        result_to_render,
                        selected_family,
                        port_options=port_options,
                    )
                ]
                render()

            def _on_metric_change(e: Any) -> None:
                view_state["metric"] = str(e.value or _first_option_key(metric_options))
                render()

            def _on_source_change(e: Any) -> None:
                if not source_options:
                    return
                family_sources_state = view_state.get("family_sources")
                if not isinstance(family_sources_state, dict):
                    family_sources_state = {}
                    view_state["family_sources"] = family_sources_state
                selected = _resolve_option_key(source_options, e.value)
                family_sources_state[view_family] = selected
                render()

            def _commit_z0(raw_value: Any) -> None:
                try:
                    resolved = float(raw_value)
                except Exception:
                    return
                if resolved <= 0:
                    return
                if float(view_state.get("z0", 50.0) or 50.0) == resolved:
                    return
                view_state["z0"] = resolved
                render()

            family_switch.on_value_change(_on_family_change)
            metric_select.on_value_change(_on_metric_change)
            if source_select is not None:
                source_select.on_value_change(_on_source_change)
            z0_input.on("keydown.enter", lambda _e: _commit_z0(z0_input.value))
            z0_input.on("blur", lambda _e: _commit_z0(z0_input.value))

            with ui.row().classes("w-full items-center gap-3 mt-1"):
                add_trace_button = ui.button(
                    "Add Trace",
                    icon="add",
                    on_click=lambda: (
                        view_state["traces"].append(
                            _default_result_trace_selection(
                                result_to_render,
                                view_family,
                                port_options=port_options,
                            )
                        ),
                        render(),
                    ),
                ).props("outline color=primary")
                if testid_prefix:
                    _with_test_id(add_trace_button, f"{testid_prefix}-add-trace-button")

            trace_cards = list(view_state["traces"])
            for idx, selection in enumerate(trace_cards, start=1):
                with _with_test_id(
                    ui.card().classes(
                        "w-full bg-elevated border border-border rounded-lg p-4 mt-3"
                    ),
                    f"{testid_prefix}-trace-card-{idx}" if testid_prefix else f"trace-card-{idx}",
                ):
                    with ui.row().classes("w-full items-center gap-3 mb-2"):
                        ui.label(f"Trace {idx}").classes("text-sm font-bold text-fg")
                        if len(trace_cards) > 1:
                            ui.button(
                                "",
                                icon="delete",
                                on_click=lambda _e, target=idx - 1: (
                                    view_state["traces"].pop(target),
                                    render(),
                                ),
                            ).props("flat color=negative round").classes("ml-auto")
                    with ui.row().classes("w-full gap-3 items-end flex-wrap"):
                        trace_select = (
                            ui.select(
                                label="Trace",
                                options=trace_options,
                                value=selection["trace"],
                            )
                            .props("dense outlined options-dense")
                            .classes("w-56")
                        )
                        output_mode_select = (
                            ui.select(
                                label="Output Mode",
                                options=mode_options,
                                value=SimulationResult.mode_token(selection["output_mode"]),
                            )
                            .props("dense outlined options-dense")
                            .classes("w-52")
                        )
                        input_mode_select = (
                            ui.select(
                                label="Input Mode",
                                options=mode_options,
                                value=SimulationResult.mode_token(selection["input_mode"]),
                            )
                            .props("dense outlined options-dense")
                            .classes("w-52")
                        )
                        output_port_select = (
                            ui.select(
                                label="Output Port",
                                options=port_options,
                                value=selection["output_port"],
                            )
                            .props("dense outlined")
                            .classes("w-40")
                        )
                        input_port_select = (
                            ui.select(
                                label="Input Port",
                                options=port_options,
                                value=selection["input_port"],
                            )
                            .props("dense outlined")
                            .classes("w-40")
                        )

                    def _update_trace_config(
                        *,
                        trace_index: int,
                        field: str,
                        value: Any,
                    ) -> None:
                        target = view_state["traces"][trace_index]
                        target[field] = value
                        render()

                    trace_select.on_value_change(
                        lambda e, trace_index=idx - 1: _update_trace_config(
                            trace_index=trace_index,
                            field="trace",
                            value=str(e.value or _first_option_key(trace_options)),
                        )
                    )
                    output_mode_select.on_value_change(
                        lambda e, trace_index=idx - 1: _update_trace_config(
                            trace_index=trace_index,
                            field="output_mode",
                            value=SimulationResult.parse_mode_token(str(e.value or "0")),
                        )
                    )
                    input_mode_select.on_value_change(
                        lambda e, trace_index=idx - 1: _update_trace_config(
                            trace_index=trace_index,
                            field="input_mode",
                            value=SimulationResult.parse_mode_token(str(e.value or "0")),
                        )
                    )
                    output_port_select.on_value_change(
                        lambda e, trace_index=idx - 1: _update_trace_config(
                            trace_index=trace_index,
                            field="output_port",
                            value=_coerce_int_value(e.value, next(iter(port_options))),
                        )
                    )
                    input_port_select.on_value_change(
                        lambda e, trace_index=idx - 1: _update_trace_config(
                            trace_index=trace_index,
                            field="input_port",
                            value=_coerce_int_value(e.value, next(iter(port_options))),
                        )
                    )

            selections = list(view_state["traces"])
            lead = selections[0]
            figure = _build_simulation_result_figure(
                result=result_to_render,
                view_family=view_family,
                metric=str(view_state.get("metric", metric_key)),
                trace=str(lead["trace"]),
                output_mode=tuple(lead["output_mode"]),
                output_port=int(lead["output_port"]),
                input_mode=tuple(lead["input_mode"]),
                input_port=int(lead["input_port"]),
                reference_impedance_ohm=float(view_state.get("z0", 50.0)),
                dark_mode=bool(_user_storage_get("dark_mode", True)),
                trace_selections=selections,
                port_label_by_index=port_options,
            )
            plot = ui.plotly(figure).classes("w-full min-h-[420px] mt-3")
            if testid_prefix:
                _with_test_id(plot, f"{testid_prefix}-plot")

    render()
