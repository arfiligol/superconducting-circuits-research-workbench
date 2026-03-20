from __future__ import annotations

from typing import cast

import numpy as np
import pandas as pd
from lmfit import Model, Parameter

from core.analysis.application.analysis.physics.squid import calculate_squid_lc_frequency
from core.analysis.domain.schemas.fitting import (
    FitResultsByMode,
    ModeFitFailure,
    ModeFitMetrics,
    ModeFitParams,
    ModeFitSeries,
    ModeFitSuccess,
)
from core.shared.logging import get_logger

logger = get_logger(__name__)

ParameterBounds = dict[str, tuple[float | None, float | None]]


def fit_squid_model(
    df_modes: pd.DataFrame,
    parameter_bounds: ParameterBounds | None = None,
    fit_window: tuple[float | None, float | None] = (None, None),
) -> FitResultsByMode:
    return _fit_resonant_modes(
        df_modes,
        fixed_capacitance_pf=None,
        fixed_Ls_nH=0.0,
        parameter_bounds=parameter_bounds,
        fit_window=fit_window,
    )


def fit_squid_model_with_Ls(
    df_modes: pd.DataFrame,
    parameter_bounds: ParameterBounds | None = None,
    fit_window: tuple[float | None, float | None] = (None, None),
) -> FitResultsByMode:
    return _fit_resonant_modes(
        df_modes,
        fixed_capacitance_pf=None,
        fixed_Ls_nH=None,
        parameter_bounds=parameter_bounds,
        fit_window=fit_window,
    )


def fit_squid_model_with_Ls_fixed_C(
    df_modes: pd.DataFrame,
    capacitance_pf: float,
    parameter_bounds: ParameterBounds | None = None,
    fit_window: tuple[float | None, float | None] = (None, None),
) -> FitResultsByMode:
    return _fit_resonant_modes(
        df_modes,
        fixed_capacitance_pf=capacitance_pf,
        fixed_Ls_nH=None,
        parameter_bounds=parameter_bounds,
        fit_window=fit_window,
    )


# Legacy Aliases
fit_resonant_modes = fit_squid_model_with_Ls
fit_resonant_modes_fixed_capacitance = fit_squid_model_with_Ls_fixed_C


def _fit_resonant_modes(
    df_modes: pd.DataFrame,
    fixed_capacitance_pf: float | None,
    fixed_Ls_nH: float | None,
    parameter_bounds: ParameterBounds | None,
    fit_window: tuple[float | None, float | None] = (None, None),
) -> FitResultsByMode:
    if df_modes is None or df_modes.empty:
        logger.error("Input DataFrame is empty.")
        return {}

    results: FitResultsByMode = {}
    mode_cols: list[str] = [c for c in df_modes.columns if "Mode" in c]

    if not mode_cols:
        logger.warning("No Mode columns found.")
        return {}

    suffix_parts = []
    if fixed_capacitance_pf is not None:
        suffix_parts.append(f"C={fixed_capacitance_pf:.4f} pF")
    if fixed_Ls_nH is not None:
        suffix_parts.append(f"Ls={fixed_Ls_nH:.4f} nH")

    suffix = f" ({', '.join(suffix_parts)})" if suffix_parts else ""
    logger.info("Starting fitting analysis for %d modes%s...", len(mode_cols), suffix)

    min_l, max_l = fit_window
    if min_l is not None:
        logger.debug("Fit Window Min: %s nH", min_l)
    if max_l is not None:
        logger.debug("Fit Window Max: %s nH", max_l)

    for mode_name in mode_cols:
        # Base filtering: keep only valid L_jun (> 1 fH) and valid Freq (> 1 MHz)
        df_valid = df_modes[(df_modes["L_jun"] > 1e-6) & (df_modes[mode_name] > 0.001)]
        df_clean = df_valid[["L_jun", mode_name]].dropna()

        # Apply Fit Window Filtering
        mask = pd.Series([True] * len(df_clean), index=df_clean.index)
        if min_l is not None:
            mask &= df_clean["L_jun"] >= min_l
        if max_l is not None:
            mask &= df_clean["L_jun"] <= max_l

        df_fit = df_clean[mask]

        if len(df_fit) < 3:
            results[mode_name] = ModeFitFailure(
                status="failed",
                reason=f"Not enough points in window (found {len(df_fit)})",
            )
            continue

        x_fit = cast(np.ndarray, df_fit["L_jun"].values)
        y_fit = cast(np.ndarray, df_fit[mode_name].values)

        model = Model(calculate_squid_lc_frequency, independent_vars=["L_jun"])
        params = model.make_params(Ls_nH=0.1, C_pF=1.0)
        params["Ls_nH"].min = 0.0
        params["C_pF"].min = 0.0

        _apply_bounds(params["Ls_nH"], parameter_bounds, "Ls_nH")
        _apply_bounds(params["C_pF"], parameter_bounds, "C_pF")

        if fixed_capacitance_pf is not None:
            params["C_pF"].set(value=fixed_capacitance_pf, vary=False)

        if fixed_Ls_nH is not None:
            params["Ls_nH"].set(value=fixed_Ls_nH, vary=False)

        try:
            result = model.fit(y_fit, params=params, L_jun=x_fit)
            if not result.success:
                raise RuntimeError(result.message)

            Ls_fit = result.params["Ls_nH"].value
            C_fit = result.params["C_pF"].value

            # Evaluate at ALL raw sample points
            x_eval_all = cast(np.ndarray, df_valid["L_jun"].values)
            _ = result.eval(params=result.params, L_jun=x_eval_all)

            # Generate plotting grid
            if len(x_eval_all) >= 2:
                l_min = float(np.min(x_eval_all))
                l_max = float(np.max(x_eval_all))
                l_plot_min = max(l_min, 1e-12)
                x_curve = np.linspace(l_plot_min, l_max, 200)
            else:
                x_curve = x_eval_all
            y_curve = cast(np.ndarray, result.eval(params=result.params, L_jun=x_curve))

            y_fit_pred = result.eval(params=result.params, L_jun=x_fit)
            rmse = np.sqrt(np.mean((y_fit - y_fit_pred) ** 2))

            # Construct Success Result using Pydantic Models
            success_result = ModeFitSuccess(
                status="success",
                params=ModeFitParams(Ls_nH=float(Ls_fit), C_eff_pF=float(C_fit)),
                metrics=ModeFitMetrics(RMSE=float(rmse)),
                raw_data=ModeFitSeries(
                    L_jun=cast(list[float], df_valid["L_jun"].tolist()),
                    Freq=cast(list[float], df_valid[mode_name].tolist()),
                ),
                fit_curve=ModeFitSeries(
                    L_jun=x_curve.tolist(),
                    Freq=y_curve.tolist(),
                ),
            )
            results[mode_name] = success_result

            caption = f"  > {mode_name}: Ls={Ls_fit:.4f} nH, C={C_fit:.4f} pF, RMSE={rmse:.4f}"
            if fixed_capacitance_pf is not None:
                caption += " (C fixed)"
            if fixed_Ls_nH is not None:
                caption += " (Ls fixed)"
            logger.info(caption)

        except Exception as exc:
            results[mode_name] = ModeFitFailure(status="failed", reason=str(exc))
            logger.error("%s: Fitting failed (%s)", mode_name, exc)

    return results


def _apply_bounds(param: Parameter, bounds: ParameterBounds | None, name: str) -> None:
    if not bounds:
        return
    if name not in bounds:
        return
    lower, upper = bounds[name]
    if lower is not None:
        param.min = lower
    if upper is not None:
        param.max = upper
