"""Shared thesis Plotly display and export configuration."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

PLOTLY_FIGURE_WIDTH_PX: int | None = 1200
PLOTLY_FIGURE_HEIGHT_PX: int | None = 780
PLOTLY_THREE_PANEL_FIGURE_HEIGHT_PX = 1200
PLOTLY_THREE_PANEL_VERTICAL_SPACING = 0.15
PLOTLY_MARGIN_LEFT_PX = 95
PLOTLY_MARGIN_RIGHT_PX = 340
PLOTLY_MARGIN_TOP_PX = 110
PLOTLY_MARGIN_BOTTOM_PX = 85

PLOTLY_LEGEND_X = 1.02
PLOTLY_LEGEND_Y = 1.0

PLOTLY_FONT_FAMILY = "Arial, Helvetica, sans-serif"
PLOTLY_TITLE_FONT_SIZE = 30
PLOTLY_AXIS_TITLE_FONT_SIZE = 26
PLOTLY_AXIS_TITLE_STANDOFF_PX = 14
PLOTLY_TICK_FONT_SIZE = 21
PLOTLY_LEGEND_FONT_SIZE = 20
PLOTLY_SUBPLOT_TITLE_FONT_SIZE = 22
PLOTLY_TEXT_COLOR = "#111827"
PLOTLY_GRID_COLOR = "#E5E7EB"
PLOTLY_AXIS_LINE_COLOR = "#111827"
PLOTLY_BACKGROUND_COLOR = "#FFFFFF"
PLOTLY_LINE_WIDTH = 2.4
PLOTLY_MARKER_SIZE = 10
PLOTLY_REFERENCE_LINE_WIDTH = 1.5
PLOTLY_REFERENCE_LINE_COLOR = "#111827"
PLOTLY_ACCENT_COLOR = "#E69F00"

PLOTLY_QUBIT_COLORS = {
    "Q0": "#0072B2",
    "Q1": "#D55E00",
    "Q2": "#009E73",
}
PLOTLY_SOURCE_COLORS = {
    "Layout": "#009E73",
    "Circuit": "#0072B2",
}
PLOTLY_FALLBACK_TRACE_COLOR = "#4B5563"

PLOTLY_DOWNLOAD_FORMAT = "png"
PLOTLY_DOWNLOAD_WIDTH_PX = 1200
PLOTLY_DOWNLOAD_HEIGHT_PX = 780
PLOTLY_DOWNLOAD_SCALE = 3
PLOTLY_DOWNLOAD_SIZE_OVERRIDES = {
    "q3d_jc_reduced_admittance_trace_Q0_L24nH": {"height": 900},
}

PLOTLY_HTML_INCLUDE_PLOTLYJS = "cdn"

DEFAULT_L_JUN_EFFECTIVE_FACTOR = 0.5

_PLOTLY_BASE_CONFIG: dict[str, Any] = {
    "displayModeBar": True,
    "displaylogo": False,
    "responsive": True,
}


def plotly_figure_layout_kwargs() -> dict[str, int]:
    """Return notebook display dimensions matching the download logical size."""
    kwargs: dict[str, int] = {}
    if PLOTLY_FIGURE_WIDTH_PX is not None:
        kwargs["width"] = PLOTLY_FIGURE_WIDTH_PX
    if PLOTLY_FIGURE_HEIGHT_PX is not None:
        kwargs["height"] = PLOTLY_FIGURE_HEIGHT_PX
    return kwargs


def plotly_publication_layout_kwargs(title: str) -> dict[str, Any]:
    """Return shared thesis publication-style Plotly layout kwargs."""
    layout = {
        "title": {
            "text": title,
            "font": {
                "family": PLOTLY_FONT_FAMILY,
                "size": PLOTLY_TITLE_FONT_SIZE,
                "color": PLOTLY_TEXT_COLOR,
            },
            "x": 0.01,
            "xanchor": "left",
        },
        "template": "plotly_white",
        "hovermode": "closest",
        "font": {
            "family": PLOTLY_FONT_FAMILY,
            "size": PLOTLY_TICK_FONT_SIZE,
            "color": PLOTLY_TEXT_COLOR,
        },
        "legend": {
            "orientation": "v",
            "x": PLOTLY_LEGEND_X,
            "xanchor": "left",
            "y": PLOTLY_LEGEND_Y,
            "yanchor": "top",
            "font": {
                "family": PLOTLY_FONT_FAMILY,
                "size": PLOTLY_LEGEND_FONT_SIZE,
                "color": PLOTLY_TEXT_COLOR,
            },
        },
        "margin": {
            "l": PLOTLY_MARGIN_LEFT_PX,
            "r": PLOTLY_MARGIN_RIGHT_PX,
            "t": PLOTLY_MARGIN_TOP_PX,
            "b": PLOTLY_MARGIN_BOTTOM_PX,
        },
        "paper_bgcolor": PLOTLY_BACKGROUND_COLOR,
        "plot_bgcolor": PLOTLY_BACKGROUND_COLOR,
    }
    layout.update(plotly_figure_layout_kwargs())
    return layout


def plotly_publication_axis_kwargs(
    *,
    show_x_grid: bool = False,
    show_y_grid: bool = True,
) -> dict[str, dict[str, Any]]:
    """Return shared x/y axis kwargs for thesis publication-style figures."""
    common = {
        "title_font": {
            "family": PLOTLY_FONT_FAMILY,
            "size": PLOTLY_AXIS_TITLE_FONT_SIZE,
            "color": PLOTLY_TEXT_COLOR,
        },
        "title_standoff": PLOTLY_AXIS_TITLE_STANDOFF_PX,
        "tickfont": {
            "family": PLOTLY_FONT_FAMILY,
            "size": PLOTLY_TICK_FONT_SIZE,
            "color": PLOTLY_TEXT_COLOR,
        },
        "showline": True,
        "linecolor": PLOTLY_AXIS_LINE_COLOR,
        "linewidth": 1,
        "mirror": True,
        "ticks": "outside",
        "tickcolor": PLOTLY_AXIS_LINE_COLOR,
        "gridcolor": PLOTLY_GRID_COLOR,
        "gridwidth": 1,
        "zeroline": False,
    }
    return {
        "x": {**common, "showgrid": show_x_grid},
        "y": {**common, "showgrid": show_y_grid},
    }


def plotly_publication_annotation_kwargs() -> dict[str, Any]:
    """Return shared subplot annotation kwargs."""
    return {
        "font": {
            "family": PLOTLY_FONT_FAMILY,
            "size": PLOTLY_SUBPLOT_TITLE_FONT_SIZE,
            "color": PLOTLY_TEXT_COLOR,
        }
    }


def plotly_download_dimensions(filename: str = "thesis_plot") -> dict[str, int]:
    """Return logical download dimensions before Plotly applies export scale."""
    dimensions = {
        "width": PLOTLY_DOWNLOAD_WIDTH_PX,
        "height": PLOTLY_DOWNLOAD_HEIGHT_PX,
    }
    dimensions.update(PLOTLY_DOWNLOAD_SIZE_OVERRIDES.get(filename, {}))
    return dimensions


def plotly_show_config(filename: str = "thesis_plot") -> dict[str, Any]:
    """Return Plotly config for notebook display and modebar image download."""
    dimensions = plotly_download_dimensions(filename)
    config = deepcopy(_PLOTLY_BASE_CONFIG)
    config["toImageButtonOptions"] = {
        "format": PLOTLY_DOWNLOAD_FORMAT,
        "filename": filename,
        "height": dimensions["height"],
        "width": dimensions["width"],
        "scale": PLOTLY_DOWNLOAD_SCALE,
    }
    return config


def plotly_static_image_options(filename: str = "thesis_plot") -> dict[str, int | str]:
    """Return matching options for optional Kaleido PNG export."""
    dimensions = plotly_download_dimensions(filename)
    return {
        "format": PLOTLY_DOWNLOAD_FORMAT,
        "height": dimensions["height"],
        "width": dimensions["width"],
        "scale": PLOTLY_DOWNLOAD_SCALE,
    }
