"""Result-artifact registry for Characterization Result View."""

from __future__ import annotations

from collections.abc import Callable

import pandas as pd

from legacy.legacy_nicegui_archived.features.characterization.state import ResultArtifact

METHOD_LABELS: dict[str, str] = {
    "admittance_zero_crossing": "Admittance Zero-Crossing",
    "lc_squid_fit": "SQUID Fitting",
    "y11_fit": "Y11 Response Fit",
    "complex_notch_fit_S21": "Complex Notch Fit (S21)",
    "complex_notch_fit_S11": "Complex Notch Fit (S11)",
    "transmission_fit_S21": "Transmission Fit (S21)",
    "transmission_fit_S11": "Transmission Fit (S11)",
    "vector_fit_S21": "Vector Fit (S21)",
    "vector_fit_S11": "Vector Fit (S11)",
}

RESULT_CATEGORY_LABELS: dict[str, str] = {
    "resonance": "Resonance",
    "fit": "Fitting",
    "summary": "Summary",
    "qa": "QA",
}
_CATEGORY_ORDER: dict[str, int] = {name: idx for idx, name in enumerate(RESULT_CATEGORY_LABELS)}
_ANALYSIS_CATEGORY_DEFAULTS: dict[str, str] = {
    "admittance_extraction": "resonance",
    "s21_resonance_fit": "fit",
    "squid_fitting": "fit",
    "y11_fit": "fit",
}


def _default_analysis_category(analysis_id: str) -> str:
    return _ANALYSIS_CATEGORY_DEFAULTS.get(analysis_id, "summary")


def build_result_artifacts_for_analysis(
    *,
    analysis_id: str,
    method_groups: dict[str, list],
    build_mode_vs_ljun_dataframe: Callable[[list], pd.DataFrame | None],
    build_resonator_table: Callable[[list], pd.DataFrame | None],
    build_fit_parameter_table: Callable[[list], pd.DataFrame | None],
    is_summary_scalar: Callable[[object], bool],
) -> list[ResultArtifact]:
    """Build declarative artifact manifest for one analysis."""
    method_keys = sorted(method_groups)
    if not method_keys:
        return []

    artifacts: list[ResultArtifact] = []
    default_category = _default_analysis_category(analysis_id)
    method_count = len(method_keys)

    for method_key in method_keys:
        method_params = list(method_groups[method_key])
        method_label = METHOD_LABELS.get(method_key, method_key)

        mode_vs_ljun_df = build_mode_vs_ljun_dataframe(method_params)
        if mode_vs_ljun_df is not None and not mode_vs_ljun_df.empty:
            sweep_axis_label = str(mode_vs_ljun_df.attrs.get("sweep_axis_label") or "L_jun")
            sweep_axis_title = f"Mode vs {sweep_axis_label}"
            artifact_shape = "mode_vs_ljun" if sweep_axis_label == "L_jun" else "mode_vs_sweep_axis"
            artifacts.append(
                ResultArtifact(
                    artifact_id=(
                        f"{analysis_id}.{method_key}.mode_vs_ljun"
                        if artifact_shape == "mode_vs_ljun"
                        else f"{analysis_id}.{method_key}.mode_vs_sweep_axis"
                    ),
                    analysis_id=analysis_id,
                    category=default_category,
                    view_kind="matrix_table_plot",
                    tab_label=(
                        sweep_axis_title
                        if method_count == 1
                        else f"{sweep_axis_title} ({method_label})"
                    ),
                    title=sweep_axis_title,
                    subtitle=method_label if method_count > 1 else None,
                    query_spec={
                        "method_key": method_key,
                        "dataset": "derived_parameters",
                        "shape": artifact_shape,
                    },
                    meta={
                        "row_count": int(mode_vs_ljun_df.shape[0]),
                        "col_count": int(mode_vs_ljun_df.shape[1]),
                        "is_sweep": int(mode_vs_ljun_df.shape[1]) > 1,
                        "sweep_axis_label": sweep_axis_label,
                    },
                )
            )

        resonator_df = build_resonator_table(method_params)
        if resonator_df is not None and not resonator_df.empty:
            artifacts.append(
                ResultArtifact(
                    artifact_id=f"{analysis_id}.{method_key}.resonator_summary",
                    analysis_id=analysis_id,
                    category=default_category,
                    view_kind="record_table",
                    tab_label=(
                        "Resonator Summary"
                        if method_count == 1
                        else f"Resonator Summary ({method_label})"
                    ),
                    title="Per-Resonator Summary",
                    subtitle=method_label if method_count > 1 else None,
                    query_spec={
                        "method_key": method_key,
                        "dataset": "derived_parameters",
                        "shape": "resonator_summary",
                    },
                    meta={
                        "row_count": int(resonator_df.shape[0]),
                        "col_count": int(resonator_df.shape[1]),
                    },
                )
            )

        fit_df = build_fit_parameter_table(method_params)
        if fit_df is not None and not fit_df.empty:
            artifacts.append(
                ResultArtifact(
                    artifact_id=f"{analysis_id}.{method_key}.fit_parameters",
                    analysis_id=analysis_id,
                    category=default_category,
                    view_kind="record_table",
                    tab_label=(
                        "Fit Parameters"
                        if method_count == 1
                        else f"Fit Parameters ({method_label})"
                    ),
                    title="Fit Parameters",
                    subtitle=method_label if method_count > 1 else None,
                    query_spec={
                        "method_key": method_key,
                        "dataset": "derived_parameters",
                        "shape": "fit_parameters",
                    },
                    meta={
                        "row_count": int(fit_df.shape[0]),
                        "col_count": int(fit_df.shape[1]),
                    },
                )
            )

        scalars = [param for param in method_params if is_summary_scalar(param)]
        if scalars:
            artifacts.append(
                ResultArtifact(
                    artifact_id=f"{analysis_id}.{method_key}.summary_metrics",
                    analysis_id=analysis_id,
                    category="summary",
                    view_kind="scalar_cards",
                    tab_label=(
                        "Summary Metrics"
                        if method_count == 1
                        else f"Summary Metrics ({method_label})"
                    ),
                    title="Summary Metrics",
                    subtitle=method_label if method_count > 1 else None,
                    query_spec={
                        "method_key": method_key,
                        "dataset": "derived_parameters",
                        "shape": "summary_metrics",
                    },
                    meta={"count": len(scalars)},
                )
            )

    artifacts.sort(
        key=lambda artifact: (
            _CATEGORY_ORDER.get(artifact.category, len(_CATEGORY_ORDER)),
            artifact.tab_label.lower(),
        )
    )
    return artifacts


def artifact_categories(artifacts: list[ResultArtifact]) -> list[str]:
    """Return sorted category keys from artifact manifest."""
    unique = {artifact.category for artifact in artifacts}
    return sorted(unique, key=lambda category: _CATEGORY_ORDER.get(category, len(_CATEGORY_ORDER)))


def artifacts_in_category(
    artifacts: list[ResultArtifact],
    *,
    category: str,
) -> list[ResultArtifact]:
    """Return artifacts belonging to one category."""
    return [artifact for artifact in artifacts if artifact.category == category]


__all__ = [
    "RESULT_CATEGORY_LABELS",
    "artifact_categories",
    "artifacts_in_category",
    "build_result_artifacts_for_analysis",
]
