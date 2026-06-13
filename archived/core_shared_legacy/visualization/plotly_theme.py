"""Plotly theme synchronization with UI design tokens."""

from typing import Any


def get_plotly_layout(dark: bool = True) -> dict[str, Any]:
    """
    Return Plotly layout kwargs matching the app design system tokens.

    Args:
        dark: Whether to use dark mode or light mode.

    Returns:
        A dictionary with Plotly layout parameters.
    """
    if dark:
        return {
            "template": "plotly_dark",
            "paper_bgcolor": "rgb(30, 41, 59)",  # --surface (dark)
            "plot_bgcolor": "rgb(15, 23, 42)",  # --bg (dark)
            "font": {"color": "rgb(226, 232, 240)", "family": "Inter, Arial, sans-serif"},
            "xaxis": {
                "gridcolor": "rgb(51, 65, 85)",  # --border (dark)
                "zerolinecolor": "rgb(51, 65, 85)",
            },
            "yaxis": {
                "gridcolor": "rgb(51, 65, 85)",  # --border (dark)
                "zerolinecolor": "rgb(51, 65, 85)",
            },
        }

    return {
        "template": "plotly_white",
        "paper_bgcolor": "rgb(255, 255, 255)",  # --surface (light)
        "plot_bgcolor": "rgb(248, 250, 252)",  # --bg (light)
        "font": {"color": "rgb(15, 23, 42)", "family": "Inter, Arial, sans-serif"},
        "xaxis": {
            "gridcolor": "rgb(226, 232, 240)",  # --border (light)
            "zerolinecolor": "rgb(226, 232, 240)",
        },
        "yaxis": {
            "gridcolor": "rgb(226, 232, 240)",  # --border (light)
            "zerolinecolor": "rgb(226, 232, 240)",
        },
    }
