from __future__ import annotations

from typing import cast

import numpy as np
import pandas as pd
from lmfit import Model

from core.analysis.application.analysis.physics.admittance import calculate_y11_imaginary
from core.analysis.domain.schemas.fitting import (
    Y11FitFailure,
    Y11FitMetrics,
    Y11FitParams,
    Y11FitResult,
    Y11FitSeries,
    Y11FitSuccess,
)


def _prepare_dataframe(df_raw: pd.DataFrame) -> pd.DataFrame:
    required_cols = {
        "L_jun [nH]": "L_jun",
        "Freq [GHz]": "Freq",
        "im(Yt(Rectangle1_T1,Rectangle1_T1)) []": "ImY",
    }
    alias_cols = {
        "im(Y) []": "ImY",
        "im(y) []": "ImY",
    }
    # Check if renamed columns already exist (if pre-processed)
    if all(col in df_raw.columns for col in required_cols.values()):
        return df_raw.dropna()

    missing = [col for col in required_cols if col not in df_raw.columns]
    if missing:
        if all(col in df_raw.columns for col in ("L_jun [nH]", "Freq [GHz]")):
            for source_name, target_name in alias_cols.items():
                if source_name in df_raw.columns:
                    return (
                        df_raw.rename(columns={source_name: target_name})[
                            ["L_jun [nH]", "Freq [GHz]", target_name]
                        ]
                        .rename(
                            columns={
                                "L_jun [nH]": "L_jun",
                                "Freq [GHz]": "Freq",
                                target_name: "ImY",
                            }
                        )
                        .dropna()
                    )
        # Fallback: check if we just have standard names
        alt_required = {"L_jun", "Freq", "ImY"}
        if all(c in df_raw.columns for c in alt_required):
            return df_raw[list(alt_required)].dropna()
        raise ValueError(f"Missing columns: {missing}")

    df = df_raw.rename(columns=required_cols)
    df = df[list(required_cols.values())]
    return df.dropna()


def fit_y11_response(
    df_raw: pd.DataFrame,
    *,
    ls1_init_nh: float = 0.01,
    ls2_init_nh: float = 0.01,
    c_init_pf: float = 0.885,
    c_max_pf: float = 3.0,
) -> Y11FitResult:
    try:
        df = _prepare_dataframe(df_raw)
    except ValueError as e:
        return Y11FitFailure(status="failed", reason=str(e))

    if df.empty:
        return Y11FitFailure(status="failed", reason="No valid samples")

    l_jun = df["L_jun"].to_numpy(dtype=float)
    freq = df["Freq"].to_numpy(dtype=float)
    imag_y = df["ImY"].to_numpy(dtype=float)

    model = Model(calculate_y11_imaginary, independent_vars=["L_jun", "freq_ghz"])
    params = model.make_params(
        Ls1_nH=float(ls1_init_nh),
        Ls2_nH=float(ls2_init_nh),
        C_pF=float(c_init_pf),
    )
    params["Ls1_nH"].min = 0.0
    params["Ls2_nH"].min = 0.0
    params["C_pF"].min = 0.0
    params["C_pF"].max = float(c_max_pf)

    try:
        result = model.fit(imag_y, params=params, L_jun=l_jun, freq_ghz=freq)
        if not result.success:
            raise RuntimeError(result.message)

        predictions = cast(
            np.ndarray, result.eval(params=result.params, L_jun=l_jun, freq_ghz=freq)
        )
        rmse = float(np.sqrt(np.mean((imag_y - predictions) ** 2)))

        success = Y11FitSuccess(
            status="success",
            params=Y11FitParams(
                Ls1_nH=float(result.params["Ls1_nH"].value),
                Ls2_nH=float(result.params["Ls2_nH"].value),
                C_pF=float(result.params["C_pF"].value),
            ),
            metrics=Y11FitMetrics(RMSE=rmse),
            raw_data=Y11FitSeries(
                freq_ghz=freq.tolist(),
                imag_y=imag_y.tolist(),
                L_jun=l_jun.tolist(),
            ),
            fit_curve=Y11FitSeries(
                freq_ghz=freq.tolist(),
                imag_y=predictions.tolist(),
                L_jun=l_jun.tolist(),
            ),
        )
        return success
    except Exception as exc:
        return Y11FitFailure(status="failed", reason=str(exc))
