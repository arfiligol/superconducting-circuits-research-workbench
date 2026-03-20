from __future__ import annotations

import re
from collections.abc import Sequence

import plotly.graph_objects as go

from core.analysis.domain.schemas.fitting import AnalysisEntry


def plot_json_results(
    results_list: Sequence[AnalysisEntry],
    target_modes: list[str] | None = None,
    title: str = "SQUID JPA Fitting Results",
) -> None:
    """Plot fitting results using Plotly."""
    sorted_results = sorted(results_list, key=_analysis_sort_key)
    _plot_json_results_plotly(sorted_results, target_modes, title)


def _plot_json_results_plotly(
    results_list: Sequence[AnalysisEntry],
    target_modes: list[str] | None,
    title: str,
) -> None:
    traces: list[go.Scatter] = []
    colors: list[str] = [
        "#1f77b4",
        "#d62728",
        "#2ca02c",
        "#9467bd",
        "#ff7f0e",
        "#17becf",
        "#8c564b",
    ]
    color_idx = 0

    for res_obj in results_list:
        file_label = res_obj.filename
        for mode_name, mode_data in res_obj.fits.items():
            if target_modes and mode_name not in target_modes:
                continue

            # Check status
            if mode_data.status != "success":
                continue

            # It's a success, safe to access strict fields
            if hasattr(mode_data, "raw_data"):
                raw = mode_data.raw_data
                fit = mode_data.fit_curve
                params = mode_data.params

                color = colors[color_idx % len(colors)]
                color_idx += 1

                traces.append(
                    go.Scatter(
                        x=raw.L_jun,
                        y=raw.Freq,
                        mode="markers",
                        name=f"{file_label} - {mode_name}",
                        marker=dict(color=color, size=8),
                    )
                )
                traces.append(
                    go.Scatter(
                        x=fit.L_jun,
                        y=fit.Freq,
                        mode="lines",
                        name=(
                            f"Fit {mode_name} "
                            f"(Ls={params.Ls_nH:.3f} nH, C={params.C_eff_pF:.3f} pF)"
                        ),
                        line=dict(color=color, dash="dash", width=3),
                    )
                )

    fig = go.Figure(data=traces)
    fig = go.Figure(data=traces)

    # Use minimal layout as requested (sandbox style)
    fig.update_layout(
        title=title,
        xaxis_title="Junction Inductance L_jun [nH]",
        yaxis_title="Frequency [GHz]",
        legend_title="Datasets",
    )

    fig.show()


def _version_key(filename: str) -> tuple[int, str]:
    match = re.search(r"_v(\d+)", filename, flags=re.IGNORECASE)
    version = int(match.group(1)) if match else 10_000
    return (version, filename)


def _analysis_sort_key(entry: AnalysisEntry) -> tuple[int, str]:
    return _version_key(entry.filename)
