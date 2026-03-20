from __future__ import annotations

from typing import Any

import plotly.graph_objects as go

# Matplotlib defaults removed


def create_plotly_default_config(filename: str) -> dict[str, Any]:
    """Return standard Plotly config with screenshot export enabled."""
    return {
        "toImageButtonOptions": {
            "format": "png",
            "filename": filename,
            "height": 800,
            "width": 1200,
            "scale": 2,
        },
        "scrollZoom": True,
        "displaylogo": False,
    }


def apply_plotly_layout(
    fig: go.Figure,
    title: str,
    xaxis_title: str,
    yaxis_title: str,
    legend_title: str | None = None,
) -> go.Figure:
    """Apply standard styling to a Plotly figure."""
    fig.update_layout(
        title={
            "text": title,
            "y": 0.95,
            "x": 0.5,
            "xanchor": "center",
            "yanchor": "top",
        },
        xaxis_title=xaxis_title,
        yaxis_title=yaxis_title,
        template="plotly_white",
        font=dict(family="Arial", size=14, color="black"),
        xaxis=dict(
            showgrid=True,
            gridwidth=1,
            gridcolor="lightgray",
            zeroline=True,
            zerolinewidth=2,
            zerolinecolor="gray",
        ),
        yaxis=dict(
            showgrid=True,
            gridwidth=1,
            gridcolor="lightgray",
            zeroline=True,
            zerolinewidth=2,
            zerolinecolor="gray",
        ),
        legend=dict(
            title_text=legend_title,
            yanchor="top",
            y=0.99,
            xanchor="left",
            x=1.02,
            bordercolor="Black",
            borderwidth=1,
        ),
        margin=dict(l=80, r=150, t=100, b=80),
        width=1200,
        height=800,
        hovermode="closest",
    )
    return fig
