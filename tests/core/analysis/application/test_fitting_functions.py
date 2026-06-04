"""Tests for pure analysis fitting functions."""

from __future__ import annotations

import numpy as np
import pandas as pd

from superconducting_circuits_analysis.application.analysis.extraction.admittance import (
    extract_modes_from_dataframe,
)
from superconducting_circuits_analysis.application.analysis.fitting.modes import (
    fit_squid_model_with_Ls,
)
from superconducting_circuits_analysis.application.analysis.fitting.y11 import (
    fit_y11_response,
)
from superconducting_circuits_analysis.application.analysis.physics.admittance import (
    calculate_y11_imaginary,
)
from superconducting_circuits_analysis.application.analysis.physics.squid import (
    calculate_squid_lc_frequency,
)


def _synthetic_squid_admittance_frame() -> pd.DataFrame:
    l_jun_values = np.linspace(0.8, 2.8, 9)
    rows: list[dict[str, float]] = []
    for l_jun in l_jun_values:
        target_freq = float(calculate_squid_lc_frequency(l_jun, Ls_nH=0.08, C_pF=1.05))
        for freq in np.linspace(target_freq - 0.35, target_freq + 0.35, 41):
            rows.append(
                {
                    "L_jun [nH]": float(l_jun),
                    "Freq [GHz]": float(freq),
                    "im(Y) []": float(freq - target_freq),
                }
            )
    return pd.DataFrame(rows)


def _synthetic_y11_frame() -> pd.DataFrame:
    rows: list[dict[str, float]] = []
    for l_jun in np.linspace(0.8, 2.8, 8):
        for freq in np.linspace(4.5, 7.5, 16):
            rows.append(
                {
                    "L_jun [nH]": float(l_jun),
                    "Freq [GHz]": float(freq),
                    "im(Y) []": float(
                        calculate_y11_imaginary(
                            float(l_jun),
                            float(freq),
                            Ls1_nH=0.02,
                            Ls2_nH=0.03,
                            C_pF=1.0,
                        )
                    ),
                }
            )
    return pd.DataFrame(rows)


def test_extract_modes_from_dataframe_and_fit_squid_model() -> None:
    modes = extract_modes_from_dataframe(_synthetic_squid_admittance_frame())

    assert modes is not None
    assert list(modes.columns) == ["L_jun", "Mode 1"]

    fit_results = fit_squid_model_with_Ls(
        modes,
        parameter_bounds={
            "Ls_nH": (0.0, None),
            "C_pF": (0.1, 3.0),
        },
    )

    mode_fit = fit_results["Mode 1"]
    assert mode_fit.status == "success"
    assert mode_fit.params.Ls_nH >= 0.0
    assert 0.1 <= mode_fit.params.C_eff_pF <= 3.0
    assert mode_fit.metrics.RMSE < 1e-3


def test_fit_y11_response_returns_parameter_summary() -> None:
    result = fit_y11_response(
        _synthetic_y11_frame(),
        ls1_init_nh=0.02,
        ls2_init_nh=0.03,
        c_init_pf=1.0,
        c_max_pf=3.0,
    )

    assert result.status == "success"
    assert result.params.Ls1_nH >= 0.0
    assert result.params.Ls2_nH >= 0.0
    assert 0.0 <= result.params.C_pF <= 3.0
    assert result.metrics.RMSE < 1e-6
