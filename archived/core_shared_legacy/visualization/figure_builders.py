"""Shared Plotly figure builders for the SC Data Browser."""

import numpy as np
import plotly.graph_objects as go

from core.shared.persistence import DataRecord, DerivedParameter
from core.shared.visualization.plotly_theme import get_plotly_layout


def build_line_chart(record: DataRecord, dark: bool = True) -> go.Figure:
    """Build a 1D line chart from a DataRecord."""
    fig = go.Figure()

    if not record.axes or len(record.axes) == 0:
        fig.update_layout(title="No axes defined", **get_plotly_layout(dark))
        return fig

    x_axis = record.axes[0]
    x_vals = x_axis.get("values", [])
    x_name = x_axis.get("name", "X")
    x_unit = x_axis.get("unit", "")
    x_label = f"{x_name} ({x_unit})" if x_unit else x_name

    # Check dimensionality
    if len(record.axes) == 1:
        # Simple 1D
        fig.add_trace(go.Scatter(x=x_vals, y=record.values, mode="lines", name=record.parameter))
    elif len(record.axes) == 2:
        # 2D data (e.g. Admittance vs Freq & L_jun)
        # We plot a slice of lines for the second axis
        y_axis = record.axes[1]
        y_vals = y_axis.get("values", [])
        y_name = y_axis.get("name", "Y")

        matrix = np.asarray(record.values, dtype=float)

        # Determine how to slice based on matrix shape
        if matrix.shape == (len(x_vals), len(y_vals)):
            # Plot lines for each column
            max_lines = 10
            step = max(1, len(y_vals) // max_lines)
            for i in range(0, len(y_vals), step):
                fig.add_trace(
                    go.Scatter(x=x_vals, y=matrix[:, i], mode="lines", name=f"{y_name}={y_vals[i]}")
                )
        else:
            fig.add_annotation(text="Shape mismatch", showarrow=False)

    title = f"{record.parameter} ({record.representation})"

    layout = get_plotly_layout(dark)
    layout.update(
        {
            "title": title,
            "xaxis_title": x_label,
            "yaxis_title": f"{record.parameter}",
            "margin": dict(l=50, r=20, t=50, b=50),
        }
    )

    fig.update_layout(**layout)
    return fig


def build_heatmap(record: DataRecord, dark: bool = True) -> go.Figure:
    """Build a 2D heatmap from a DataRecord."""
    fig = go.Figure()

    if len(record.axes) < 2:
        return build_line_chart(record, dark)

    x_axis = record.axes[0]
    y_axis = record.axes[1]

    x_vals = x_axis.get("values", [])
    y_vals = y_axis.get("values", [])

    matrix = np.asarray(record.values, dtype=float)
    # go.Heatmap expects z[y_idx, x_idx]. If matrix was stored as (x, y),
    # transpose to align with Plotly's convention.
    z_data = matrix.T if matrix.shape == (len(x_vals), len(y_vals)) else matrix

    fig.add_trace(
        go.Heatmap(
            x=x_vals,
            y=y_vals,
            z=z_data,
            colorscale="Viridis",
            colorbar={"title": record.representation},
        )
    )

    x_unit = x_axis.get("unit", "")
    y_unit = y_axis.get("unit", "")

    layout = get_plotly_layout(dark)
    layout.update(
        {
            "title": f"{record.parameter} {record.representation} Heatmap",
            "xaxis_title": f"{x_axis.get('name', 'X')} ({x_unit})"
            if x_unit
            else x_axis.get("name", "X"),
            "yaxis_title": f"{y_axis.get('name', 'Y')} ({y_unit})"
            if y_unit
            else y_axis.get("name", "Y"),
            "margin": dict(l=60, r=20, t=50, b=50),
        }
    )

    fig.update_layout(**layout)
    return fig


def build_parameter_table(params: list[DerivedParameter], dark: bool = True) -> go.Figure:
    """Build a Plotly table for derived parameters."""
    fig = go.Figure()

    if not params:
        fig.update_layout(title="No parameters", **get_plotly_layout(dark))
        return fig

    headers = ["Name", "Value", "Unit", "Method", "Device"]
    cells = [
        [p.name for p in params],
        [round(p.value, 6) for p in params],
        [p.unit or "" for p in params],
        [p.method or "" for p in params],
        [p.device_type.value for p in params],
    ]

    layout_theme = get_plotly_layout(dark)

    # Extract colors from theme
    bg_color = layout_theme.get("paper_bgcolor", "white")
    fg_color = layout_theme.get("font", {}).get("color", "black")
    header_bg = "rgb(51, 65, 85)" if dark else "rgb(241, 245, 249)"

    fig.add_trace(
        go.Table(
            header=dict(
                values=headers,
                fill_color=header_bg,
                font=dict(color=fg_color, size=12, family="Inter, Arial, sans-serif"),
                align="left",
            ),
            cells=dict(
                values=cells,
                fill_color=bg_color,
                font=dict(color=fg_color, size=12, family="Inter, Arial, sans-serif"),
                align="left",
                height=30,
            ),
        )
    )

    layout_theme.update(
        {
            "title": "Derived Parameters",
            "margin": dict(l=10, r=10, t=40, b=10),
        }
    )

    fig.update_layout(**layout_theme)
    return fig
