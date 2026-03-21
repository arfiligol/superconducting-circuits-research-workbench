"""Shared simulation plotting and result-selection helpers."""

from __future__ import annotations

from typing import Any, TypedDict

import plotly.graph_objects as go

from core.shared.visualization import get_plotly_layout
from core.simulation.domain.circuit import SimulationResult

_RESULT_FAMILY_OPTIONS = {
    "s": "S",
    "gain": "Gain",
    "impedance": "Impedance (Z)",
    "admittance": "Admittance (Y)",
    "qe": "Quantum Efficiency (QE)",
    "cm": "Commutation (CM)",
    "complex": "Complex Plane",
}
_POST_PROCESSED_RESULT_FAMILY_OPTIONS = {
    "s": "S",
    "gain": "Gain",
    "impedance": "Impedance (Z)",
    "admittance": "Admittance (Y)",
    "complex": "Complex Plane",
}
_POST_PROCESSED_SWEEP_COMPARE_FAMILY_OPTIONS = {
    "s": "S",
    "gain": "Gain",
    "impedance": "Impedance (Z)",
    "admittance": "Admittance (Y)",
}
_SWEEP_RESULT_FAMILY_OPTIONS = {
    "s": "S",
    "gain": "Gain",
    "impedance": "Impedance (Z)",
    "admittance": "Admittance (Y)",
    "qe": "Quantum Efficiency (QE)",
    "cm": "Commutation (CM)",
}
_RESULT_METRIC_OPTIONS = {
    "s": {
        "magnitude_linear": "Magnitude (linear)",
        "magnitude_db": "Magnitude (dB)",
        "phase_deg": "Phase (deg)",
        "real": "Real",
        "imag": "Imaginary",
    },
    "gain": {
        "gain_db": "Gain (dB)",
        "gain_linear": "Gain (linear)",
    },
    "impedance": {
        "real": "Real(Z)",
        "imag": "Imag(Z)",
        "magnitude": "|Z|",
    },
    "admittance": {
        "real": "Real(Y)",
        "imag": "Imag(Y)",
        "magnitude": "|Y|",
    },
    "qe": {
        "linear": "QE",
    },
    "cm": {
        "value": "Value",
    },
    "complex": {
        "trajectory": "Trajectory",
    },
}
_RESULT_TRACE_OPTIONS = {
    "s": {"s_param": "S-Parameter"},
    "gain": {"gain_from_s": "Power Gain from S"},
    "impedance": {"impedance": "Impedance"},
    "admittance": {"admittance": "Admittance"},
    "qe": {
        "qe": "QE",
        "qe_ideal": "QE (Ideal)",
    },
    "cm": {"cm": "CM"},
    "complex": {
        "s": "S",
        "z": "Z",
        "y": "Y",
    },
}
_RESULT_TRACE_COLORS = [
    "rgb(99, 102, 241)",
    "rgb(14, 165, 233)",
    "rgb(16, 185, 129)",
    "rgb(245, 158, 11)",
    "rgb(239, 68, 68)",
    "rgb(168, 85, 247)",
]


class _ResultTraceSelection(TypedDict):
    trace: str
    output_mode: tuple[int, ...]
    output_port: int
    input_mode: tuple[int, ...]
    input_port: int


def _result_metric_options_for_family(view_family: str) -> dict[str, str]:
    """Return metric selector options for a result-view family."""
    return dict(_RESULT_METRIC_OPTIONS.get(view_family, _RESULT_METRIC_OPTIONS["s"]))


def _result_trace_options_for_family(view_family: str) -> dict[str, str]:
    """Return trace selector options for a result-view family."""
    return dict(_RESULT_TRACE_OPTIONS.get(view_family, _RESULT_TRACE_OPTIONS["s"]))


def _result_port_options(result: SimulationResult) -> dict[int, str]:
    """Return available output/input port options for the current result bundle."""
    return {port: str(port) for port in result.available_port_indices}


def _format_mode_label(mode: tuple[int, ...]) -> str:
    """Return a readable label for one signal/idler mode tuple."""
    values = ", ".join(str(value) for value in mode)
    if all(value == 0 for value in mode):
        return f"Signal ({values})"
    return f"Sideband ({values})"


def _result_mode_options(result: SimulationResult) -> dict[str, str]:
    """Return mode selector options for the current result bundle."""
    return {
        SimulationResult.mode_token(mode): _format_mode_label(mode)
        for mode in result.available_mode_indices
    }


def _first_option_key(options: dict[str, str]) -> str:
    """Return the first key from a non-empty options dict."""
    return next(iter(options))


def _resolve_option_key(options: dict[str, str], value: object) -> str:
    """Resolve a select value to one option key, accepting either key or label."""
    if not options:
        return ""
    first_key = _first_option_key(options)
    if value is None:
        return first_key
    text = str(value).strip()
    if text in options:
        return text
    normalized = text.casefold()
    for key, label in options.items():
        if normalized == str(label).strip().casefold():
            return key
    return first_key


def _coerce_int_value(value: object, default: int) -> int:
    """Convert a dynamic UI value to int with a safe fallback."""
    try:
        return int(float(str(value)))
    except Exception:
        return default


def _finite_float_or_none(value: float) -> float | None:
    """Return value only when finite, otherwise None for Plotly gaps."""
    import math

    return value if math.isfinite(value) else None


def _complex_component_series(
    values: list[complex],
    component: str,
) -> list[float | None]:
    """Project complex values to the requested scalar component."""
    import math

    if component == "real":
        return [_finite_float_or_none(value.real) for value in values]
    if component == "imag":
        return [_finite_float_or_none(value.imag) for value in values]
    if component == "magnitude":
        return [_finite_float_or_none(abs(value)) for value in values]
    if component == "phase_deg":
        return [
            _finite_float_or_none(math.degrees(math.atan2(value.imag, value.real)))
            for value in values
        ]
    raise ValueError(f"Unsupported complex component: {component}")


def _format_complex_scalar(value: complex) -> str:
    """Format one complex value into a compact string."""
    return f"{value.real:.4e}{value.imag:+.4e}j"


def _format_export_suffix(
    output_mode: tuple[int, ...],
    input_mode: tuple[int, ...] | None = None,
) -> str:
    """Build a concise mode suffix for exported dataset parameter names."""
    if input_mode is None:
        if all(value == 0 for value in output_mode):
            return ""
        return f" [om={output_mode}]"

    if all(value == 0 for value in output_mode) and all(value == 0 for value in input_mode):
        return ""
    return f" [om={output_mode}, im={input_mode}]"


def _port_label_token(label: str) -> str:
    """Convert one port label into a stable matrix-name token."""
    import re

    normalized = str(label).strip()
    if not normalized:
        return "x"
    head = normalized.split("(", maxsplit=1)[0].strip()
    candidate = head or normalized
    if candidate.isdigit():
        return candidate
    sanitized = re.sub(r"[^0-9a-zA-Z]+", "_", candidate).strip("_")
    return (sanitized or "x").lower()


def _matrix_element_name(
    *,
    matrix_symbol: str,
    output_port: int,
    input_port: int,
    port_label_by_index: dict[int, str] | None,
) -> str:
    """Build one matrix element name aligned with trace-card port labels."""
    output_label = (
        str(port_label_by_index.get(output_port, output_port))
        if port_label_by_index
        else str(output_port)
    )
    input_label = (
        str(port_label_by_index.get(input_port, input_port))
        if port_label_by_index
        else str(input_port)
    )
    output_token = _port_label_token(output_label)
    input_token = _port_label_token(input_label)

    labels_are_plain_numeric = (not port_label_by_index) or all(
        str(label).strip().isdigit() for label in port_label_by_index.values()
    )
    if labels_are_plain_numeric and output_token.isdigit() and input_token.isdigit():
        return f"{matrix_symbol}{output_token}{input_token}"
    return f"{matrix_symbol}_{output_token}_{input_token}"


def _result_axis_titles_for_family_metric(
    *,
    view_family: str,
    metric: str,
) -> tuple[str, str]:
    """Return deterministic axis titles from the current family+metric selection."""
    if view_family == "complex":
        return ("Real", "Imaginary")

    x_axis_title = "Frequency (GHz)"
    if view_family == "impedance":
        if metric == "real":
            return (x_axis_title, "Real (Ohm)")
        if metric == "imag":
            return (x_axis_title, "Imaginary (Ohm)")
        return (x_axis_title, "Magnitude (Ohm)")
    if view_family == "admittance":
        if metric == "real":
            return (x_axis_title, "Real (S)")
        if metric == "imag":
            return (x_axis_title, "Imaginary (S)")
        return (x_axis_title, "Magnitude (S)")
    if view_family == "gain":
        if metric == "gain_linear":
            return (x_axis_title, "Gain (linear)")
        return (x_axis_title, "Gain (dB)")
    if view_family == "s":
        if metric == "magnitude_db":
            return (x_axis_title, "Magnitude (dB)")
        if metric == "phase_deg":
            return (x_axis_title, "Phase (deg)")
        if metric == "real":
            return (x_axis_title, "Real")
        if metric == "imag":
            return (x_axis_title, "Imaginary")
        return (x_axis_title, "Magnitude (linear)")
    if view_family == "qe":
        return (x_axis_title, "Quantum Efficiency")
    if view_family == "cm":
        return (x_axis_title, "Commutation")
    return (x_axis_title, "Value")


def _build_simulation_result_figure(
    result: SimulationResult,
    view_family: str,
    metric: str,
    trace: str,
    output_mode: tuple[int, ...],
    output_port: int,
    input_mode: tuple[int, ...],
    input_port: int,
    reference_impedance_ohm: float,
    dark_mode: bool,
    trace_selections: list[_ResultTraceSelection] | None = None,
    port_label_by_index: dict[int, str] | None = None,
) -> go.Figure:
    """Build the selected simulation result figure from the cached result bundle."""
    freq_values = result.frequencies_ghz
    fig = go.Figure()
    title = "Simulation Result"
    single_selection: _ResultTraceSelection = {
        "trace": trace,
        "output_mode": output_mode,
        "output_port": output_port,
        "input_mode": input_mode,
        "input_port": input_port,
    }
    resolved_selections = trace_selections or [single_selection]
    trace_titles: list[str] = []

    def add_trace_for_selection(
        *,
        trace_index: int,
        selected_trace: str,
        selected_output_mode: tuple[int, ...],
        selected_output_port: int,
        selected_input_mode: tuple[int, ...],
        selected_input_port: int,
    ) -> str:
        mode_suffix = _format_export_suffix(selected_output_mode, selected_input_mode)
        s_name = _matrix_element_name(
            matrix_symbol="S",
            output_port=selected_output_port,
            input_port=selected_input_port,
            port_label_by_index=port_label_by_index,
        )
        z_name = _matrix_element_name(
            matrix_symbol="Z",
            output_port=selected_output_port,
            input_port=selected_input_port,
            port_label_by_index=port_label_by_index,
        )
        y_name = _matrix_element_name(
            matrix_symbol="Y",
            output_port=selected_output_port,
            input_port=selected_input_port,
            port_label_by_index=port_label_by_index,
        )
        gain_name = _matrix_element_name(
            matrix_symbol="Gain",
            output_port=selected_output_port,
            input_port=selected_input_port,
            port_label_by_index=port_label_by_index,
        )
        s_label = f"{s_name}{mode_suffix}"
        z_label = f"{z_name}{mode_suffix}"
        y_label = f"{y_name}{mode_suffix}"
        gain_label = f"{gain_name}{mode_suffix}"
        line_style = {
            "color": _RESULT_TRACE_COLORS[trace_index % len(_RESULT_TRACE_COLORS)],
            "width": 2,
        }

        if view_family == "s":
            if metric == "magnitude_db":
                y_values = result.get_mode_s_parameter_db(
                    selected_output_mode,
                    selected_output_port,
                    selected_input_mode,
                    selected_input_port,
                )
                trace_title = f"{s_label} Magnitude (dB)"
            elif metric == "phase_deg":
                y_values = result.get_mode_s_parameter_phase_deg(
                    selected_output_mode,
                    selected_output_port,
                    selected_input_mode,
                    selected_input_port,
                )
                trace_title = f"{s_label} Phase"
            elif metric == "real":
                y_values = result.get_mode_s_parameter_real(
                    selected_output_mode,
                    selected_output_port,
                    selected_input_mode,
                    selected_input_port,
                )
                trace_title = f"{s_label} Real Part"
            elif metric == "imag":
                y_values = result.get_mode_s_parameter_imag(
                    selected_output_mode,
                    selected_output_port,
                    selected_input_mode,
                    selected_input_port,
                )
                trace_title = f"{s_label} Imaginary Part"
            else:
                y_values = result.get_mode_s_parameter_magnitude(
                    selected_output_mode,
                    selected_output_port,
                    selected_input_mode,
                    selected_input_port,
                )
                trace_title = f"{s_label} Magnitude"

            fig.add_trace(go.Scatter(x=freq_values, y=y_values, mode="lines", name=s_label, line=line_style))
            return trace_title

        if view_family == "gain":
            if metric == "gain_linear":
                y_values = result.get_mode_gain_linear(
                    selected_output_mode,
                    selected_output_port,
                    selected_input_mode,
                    selected_input_port,
                )
                trace_title = f"{gain_label} (linear)"
            else:
                y_values = result.get_mode_gain_db(
                    selected_output_mode,
                    selected_output_port,
                    selected_input_mode,
                    selected_input_port,
                )
                trace_title = f"{gain_label} (dB)"

            fig.add_trace(go.Scatter(x=freq_values, y=y_values, mode="lines", name=gain_label, line=line_style))
            return trace_title

        if view_family == "impedance":
            try:
                z_values = result.get_mode_z_parameter_complex(
                    selected_output_mode,
                    selected_output_port,
                    selected_input_mode,
                    selected_input_port,
                )
            except KeyError:
                z_values = result.calculate_input_impedance_ohm(
                    reference_impedance_ohm,
                    port=selected_output_port,
                )
            y_values = _complex_component_series(z_values, metric)
            trace_title = (
                f"{z_label} Real Part"
                if metric == "real"
                else f"{z_label} Imaginary Part"
                if metric == "imag"
                else f"{z_label} Magnitude"
            )
            fig.add_trace(go.Scatter(x=freq_values, y=y_values, mode="lines", name=z_label, line=line_style))
            return trace_title

        if view_family == "admittance":
            try:
                y_values_complex = result.get_mode_y_parameter_complex(
                    selected_output_mode,
                    selected_output_port,
                    selected_input_mode,
                    selected_input_port,
                )
            except KeyError:
                y_values_complex = result.calculate_input_admittance_s(
                    reference_impedance_ohm,
                    port=selected_output_port,
                )
            y_values = _complex_component_series(y_values_complex, metric)
            trace_title = (
                f"{y_label} Real Part"
                if metric == "real"
                else f"{y_label} Imaginary Part"
                if metric == "imag"
                else f"{y_label} Magnitude"
            )
            fig.add_trace(go.Scatter(x=freq_values, y=y_values, mode="lines", name=y_label, line=line_style))
            return trace_title

        if view_family == "qe":
            if selected_trace == "qe_ideal":
                y_values = result.get_mode_qe_ideal(
                    selected_output_mode,
                    selected_output_port,
                    selected_input_mode,
                    selected_input_port,
                )
                trace_title = f"QE Ideal {selected_output_port}{selected_input_port}{mode_suffix}"
            else:
                y_values = result.get_mode_qe(
                    selected_output_mode,
                    selected_output_port,
                    selected_input_mode,
                    selected_input_port,
                )
                trace_title = f"QE {selected_output_port}{selected_input_port}{mode_suffix}"
            fig.add_trace(go.Scatter(x=freq_values, y=y_values, mode="lines", name=trace_title, line=line_style))
            return trace_title

        if view_family == "cm":
            y_values = result.get_mode_cm(selected_output_mode, selected_output_port)
            trace_title = f"CM{selected_output_port}{_format_export_suffix(selected_output_mode)}"
            fig.add_trace(go.Scatter(x=freq_values, y=y_values, mode="lines", name=trace_title, line=line_style))
            return trace_title

        if view_family == "complex":
            if selected_trace == "z":
                try:
                    complex_values = result.get_mode_z_parameter_complex(
                        selected_output_mode,
                        selected_output_port,
                        selected_input_mode,
                        selected_input_port,
                    )
                except KeyError:
                    complex_values = result.calculate_input_impedance_ohm(
                        reference_impedance_ohm,
                        port=selected_output_port,
                    )
                trace_name = z_label
                trace_title = f"{z_label} Complex Plane"
            elif selected_trace == "y":
                try:
                    complex_values = result.get_mode_y_parameter_complex(
                        selected_output_mode,
                        selected_output_port,
                        selected_input_mode,
                        selected_input_port,
                    )
                except KeyError:
                    complex_values = result.calculate_input_admittance_s(
                        reference_impedance_ohm,
                        port=selected_output_port,
                    )
                trace_name = y_label
                trace_title = f"{y_label} Complex Plane"
            else:
                complex_values = result.get_mode_s_parameter_complex(
                    selected_output_mode,
                    selected_output_port,
                    selected_input_mode,
                    selected_input_port,
                )
                trace_name = s_label
                trace_title = f"{s_label} Complex Plane"

            fig.add_trace(
                go.Scatter(
                    x=[_finite_float_or_none(value.real) for value in complex_values],
                    y=[_finite_float_or_none(value.imag) for value in complex_values],
                    mode="lines+markers",
                    name=trace_name,
                    line=line_style,
                    marker={"size": 5, "color": line_style["color"]},
                    customdata=freq_values,
                    hovertemplate=(
                        "Re=%{x}<br>Im=%{y}<br>f=%{customdata:.6f} GHz"
                        f"<extra>{trace_name}</extra>"
                    ),
                )
            )
            return trace_title

        raise ValueError(f"Unsupported result view family: {view_family}")

    for idx, selection in enumerate(resolved_selections):
        trace_titles.append(
            add_trace_for_selection(
                trace_index=idx,
                selected_trace=selection["trace"],
                selected_output_mode=selection["output_mode"],
                selected_output_port=selection["output_port"],
                selected_input_mode=selection["input_mode"],
                selected_input_port=selection["input_port"],
            )
        )

    title_suffix = ""
    if len(trace_titles) > 1:
        preview_titles = ", ".join(trace_titles[:3])
        if len(trace_titles) > 3:
            preview_titles = f"{preview_titles}, +{len(trace_titles) - 3} more"
        title_suffix = f": {preview_titles}"

    if len(trace_titles) == 1:
        title = trace_titles[0]
    elif view_family == "complex":
        title = f"Complex Plane Comparison{title_suffix}"
    elif view_family == "gain":
        title = (
            f"Gain Comparison{title_suffix}"
            if metric == "gain_linear"
            else f"Gain (dB) Comparison{title_suffix}"
        )
    elif view_family == "impedance":
        title = f"Impedance Comparison{title_suffix}"
    elif view_family == "admittance":
        title = f"Admittance Comparison{title_suffix}"
    elif view_family == "qe":
        title = f"Quantum Efficiency Comparison{title_suffix}"
    elif view_family == "cm":
        title = f"Commutation Comparison{title_suffix}"
    elif view_family == "s":
        if metric == "magnitude_db":
            title = f"S-Parameter Magnitude (dB){title_suffix}"
        elif metric == "phase_deg":
            title = f"S-Parameter Phase{title_suffix}"
        elif metric == "real":
            title = f"S-Parameter Real Part{title_suffix}"
        elif metric == "imag":
            title = f"S-Parameter Imaginary Part{title_suffix}"
        else:
            title = f"S-Parameter Magnitude{title_suffix}"
    else:
        raise ValueError(f"Unsupported result view family: {view_family}")

    x_axis_title, y_axis_title = _result_axis_titles_for_family_metric(
        view_family=view_family,
        metric=metric,
    )
    theme_layout = dict(get_plotly_layout(dark=dark_mode))
    xaxis_theme = dict(theme_layout.pop("xaxis", {}))
    yaxis_theme = dict(theme_layout.pop("yaxis", {}))
    fig.update_layout(
        title=title,
        xaxis={**xaxis_theme, "title": {"text": x_axis_title}},
        yaxis={**yaxis_theme, "title": {"text": y_axis_title}},
        margin={"l": 40, "r": 20, "t": 40, "b": 40},
        showlegend=True,
        hovermode="closest" if view_family == "complex" else "x unified",
        **theme_layout,
    )
    return fig
