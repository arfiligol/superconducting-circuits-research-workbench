"""Thesis-local Layout vs Q3D+JC comparison and Plotly figure helpers."""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import config as thesis_plot_config
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from scipy.optimize import curve_fit

FEMTO = 1e-15
PICO = 1e-12
NANO = 1e-9
DEFAULT_QUBITS = ("Q0", "Q1", "Q2")
SOURCE_DASHES = {
    "Layout": "solid",
    "Circuit": "dash",
}
SOURCE_MARKER_SYMBOLS = {
    "Layout": "circle",
    "Circuit": "diamond",
}


def _qubit_color(qubit: object) -> str:
    return thesis_plot_config.PLOTLY_QUBIT_COLORS.get(
        str(qubit),
        thesis_plot_config.PLOTLY_FALLBACK_TRACE_COLOR,
    )


def _source_color(source: object) -> str:
    return thesis_plot_config.PLOTLY_SOURCE_COLORS.get(
        str(source),
        thesis_plot_config.PLOTLY_FALLBACK_TRACE_COLOR,
    )


def _source_marker_symbol(source: object) -> str:
    return SOURCE_MARKER_SYMBOLS.get(str(source), "circle")


def compute_floating_c_d_xy_ff(
    *,
    c_g1_ff: float,
    c_g2_ff: float,
    c_xy1_ff: float,
    c_xy2_ff: float,
) -> float:
    """Compute thesis floating-side Cd,xy directly from raw capacitance elements."""
    denominator = c_g1_ff + c_g2_ff + c_xy1_ff + c_xy2_ff
    if denominator == 0.0:
        return math.nan
    return (c_g1_ff * c_xy2_ff - c_g2_ff * c_xy1_ff) / denominator


def load_layout_xy_im_y_traces(
    raw_layout_dir: str | Path,
    *,
    qubits: Sequence[str] = DEFAULT_QUBITS,
) -> pd.DataFrame:
    """Load Layout XY Im(Y) traces into a normalized long dataframe."""
    raw_dir = Path(raw_layout_dir)
    rows: list[pd.DataFrame] = []
    for qubit in qubits:
        path = raw_dir / qubit / f"PF6FQ_{qubit}_XY_Im_Y11.csv"
        if not path.exists():
            continue
        raw = pd.read_csv(path)
        freq_col = _find_column(raw, "Freq")
        l_jun_col = _find_column(raw, "L_jun")
        value_col = _first_value_column(raw, excluded={freq_col, l_jun_col})
        frame = pd.DataFrame(
            {
                "source": "Layout",
                "qubit": qubit,
                "l_jun_nh": pd.to_numeric(raw[l_jun_col], errors="coerce"),
                "frequency_ghz": pd.to_numeric(raw[freq_col], errors="coerce"),
                "im_y_s": pd.to_numeric(raw[value_col], errors="coerce"),
                "source_file": path.name,
                "source_column": value_col,
            }
        )
        rows.append(frame)
    if not rows:
        return _empty_dataframe(
            [
                "source",
                "qubit",
                "l_jun_nh",
                "frequency_ghz",
                "im_y_s",
                "source_file",
                "source_column",
            ]
        )
    return pd.concat(rows, ignore_index=True).dropna(subset=["l_jun_nh", "frequency_ghz", "im_y_s"])


def load_layout_xy_resonances(
    selected_resonances_path: str | Path,
    *,
    qubits: Sequence[str] = DEFAULT_QUBITS,
    include_zero_l_jun: bool = False,
) -> pd.DataFrame:
    """Load selected Layout XY resonances into the common resonance schema."""
    path = Path(selected_resonances_path)
    if not path.exists():
        return _empty_resonance_dataframe()
    raw = pd.read_csv(path)
    if raw.empty:
        return _empty_resonance_dataframe()
    frame = raw[
        (raw["condition"].astype(str) == "XY") & (raw["qubit"].astype(str).isin(tuple(qubits)))
    ].copy()
    if not include_zero_l_jun:
        frame = frame[pd.to_numeric(frame["L_jun_nH"], errors="coerce") > 0.0]
    if frame.empty:
        return _empty_resonance_dataframe()
    out = pd.DataFrame(
        {
            "source": "Layout",
            "qubit": frame["qubit"].astype(str),
            "l_jun_nh": pd.to_numeric(frame["L_jun_nH"], errors="coerce"),
            "frequency_ghz": pd.to_numeric(frame["frequency_ghz"], errors="coerce"),
            "fallback": False,
            "crossed": True,
        }
    )
    return out.dropna(subset=["l_jun_nh", "frequency_ghz"]).sort_values(
        ["source", "qubit", "l_jun_nh"]
    )


def load_layout_xy_re_y_points(
    raw_layout_dir: str | Path,
    *,
    qubits: Sequence[str] = DEFAULT_QUBITS,
) -> pd.DataFrame:
    """Load sparse Layout XY Re(Yin) samples."""
    raw_dir = Path(raw_layout_dir)
    rows: list[pd.DataFrame] = []
    for qubit in qubits:
        path = raw_dir / qubit / f"PF6FQ_{qubit}_XY_Re_Yin.csv"
        if not path.exists():
            continue
        raw = pd.read_csv(path)
        freq_col = _find_column(raw, "Freq")
        value_col = _first_value_column(raw, excluded={freq_col})
        rows.append(
            pd.DataFrame(
                {
                    "source": "Layout",
                    "qubit": qubit,
                    "re_y_frequency_ghz": pd.to_numeric(raw[freq_col], errors="coerce"),
                    "re_y_s": pd.to_numeric(raw[value_col], errors="coerce"),
                    "source_file": path.name,
                    "source_column": value_col,
                }
            )
        )
    if not rows:
        return _empty_dataframe(
            [
                "source",
                "qubit",
                "re_y_frequency_ghz",
                "re_y_s",
                "source_file",
                "source_column",
            ]
        )
    return pd.concat(rows, ignore_index=True).dropna(subset=["re_y_frequency_ghz", "re_y_s"])


def match_layout_re_y_to_resonances(
    *,
    layout_resonances_df: pd.DataFrame,
    layout_re_y_points_df: pd.DataFrame,
    max_delta_mhz: float = 30.0,
) -> pd.DataFrame:
    """Nearest-match sparse Layout Re(Y) samples to selected Layout XY resonances."""
    rows: list[dict[str, Any]] = []
    for resonance in layout_resonances_df.itertuples(index=False):
        points = layout_re_y_points_df[layout_re_y_points_df["qubit"] == resonance.qubit]
        row = {
            "source": "Layout",
            "qubit": str(resonance.qubit),
            "l_jun_nh": float(resonance.l_jun_nh),
            "frequency_ghz": float(resonance.frequency_ghz),
            "re_y_frequency_ghz": math.nan,
            "re_y_delta_mhz": math.nan,
            "re_y_s": math.nan,
            "re_y_matched": False,
            "t1_us": math.nan,
            "t1_source": "missing_layout_re_y",
        }
        if not points.empty:
            deltas_mhz = (
                points["re_y_frequency_ghz"].astype(float) - float(resonance.frequency_ghz)
            ).abs() * 1000.0
            nearest_index = deltas_mhz.idxmin()
            nearest = points.loc[nearest_index]
            delta_mhz = float(deltas_mhz.loc[nearest_index])
            row.update(
                {
                    "re_y_frequency_ghz": float(nearest["re_y_frequency_ghz"]),
                    "re_y_delta_mhz": delta_mhz,
                    "re_y_matched": delta_mhz <= float(max_delta_mhz),
                    "t1_source": "pending_lc_fit"
                    if delta_mhz <= float(max_delta_mhz)
                    else "missing",
                }
            )
            if delta_mhz <= float(max_delta_mhz):
                row["re_y_s"] = float(nearest["re_y_s"])
        rows.append(row)
    return pd.DataFrame(rows)


def load_circuit_reduced_traces(q3d_jc_trace_path: str | Path) -> pd.DataFrame:
    """Load Circuit reduced admittance traces."""
    path = Path(q3d_jc_trace_path)
    if not path.exists():
        return _empty_dataframe(
            ["source", "qubit", "l_jun_nh", "frequency_ghz", "re_y_s", "im_y_s"]
        )
    raw = pd.read_csv(path)
    if raw.empty:
        return _empty_dataframe(
            ["source", "qubit", "l_jun_nh", "frequency_ghz", "re_y_s", "im_y_s"]
        )
    out = pd.DataFrame(
        {
            "source": "Circuit",
            "qubit": raw["qubit"].astype(str),
            "l_jun_nh": pd.to_numeric(raw["l_jun_nh"], errors="coerce"),
            "frequency_ghz": pd.to_numeric(raw["frequency_ghz"], errors="coerce"),
            "re_y_s": pd.to_numeric(raw["re_y_eff_s"], errors="coerce"),
            "im_y_s": pd.to_numeric(raw["im_y_eff_s"], errors="coerce"),
        }
    )
    return out.dropna(subset=["l_jun_nh", "frequency_ghz"])


def load_circuit_observables(
    q3d_jc_observables_path: str | Path,
    *,
    include_fallback_resonances: bool = False,
) -> pd.DataFrame:
    """Load Circuit reduced observables into a normalized long dataframe."""
    path = Path(q3d_jc_observables_path)
    if not path.exists():
        return _empty_dataframe(
            [
                "source",
                "qubit",
                "l_jun_nh",
                "frequency_ghz",
                "re_y_s",
                "t1_us",
                "c_eff_q_ff",
                "fallback",
                "crossed",
            ]
        )
    raw = pd.read_csv(path)
    if raw.empty:
        return _empty_dataframe(
            [
                "source",
                "qubit",
                "l_jun_nh",
                "frequency_ghz",
                "re_y_s",
                "t1_us",
                "c_eff_q_ff",
                "fallback",
                "crossed",
            ]
        )
    frame = raw.copy()
    if not include_fallback_resonances and "fallback" in frame.columns:
        frame = frame[~frame["fallback"].astype(bool)]
    out = pd.DataFrame(
        {
            "source": "Circuit",
            "qubit": frame["qubit"].astype(str),
            "l_jun_nh": pd.to_numeric(frame["l_jun_nh"], errors="coerce"),
            "frequency_ghz": pd.to_numeric(frame["frequency_ghz"], errors="coerce"),
            "re_y_s": pd.to_numeric(frame["re_y_eff_s"], errors="coerce"),
            "t1_us": pd.to_numeric(frame["t1_xy_us"], errors="coerce"),
            "c_eff_q_ff": pd.to_numeric(frame["c_eff_q_ff"], errors="coerce"),
            "fallback": frame.get("fallback", False),
            "crossed": frame.get("crossed", True),
        }
    )
    for column in (
        "selected_index",
        "selected_crossing_index",
        "bracket_f0_ghz",
        "bracket_f1_ghz",
        "bracket_im_y0",
        "bracket_im_y1",
        "slope_im_y_per_ghz",
    ):
        out[column] = (
            pd.to_numeric(frame[column], errors="coerce") if column in frame.columns else math.nan
        )
    if "slope_sign" in frame.columns:
        out["slope_sign"] = frame["slope_sign"].astype(str)
    else:
        out["slope_sign"] = ""
    return out.dropna(subset=["l_jun_nh", "frequency_ghz"]).sort_values(
        ["source", "qubit", "l_jun_nh"]
    )


def build_resonance_dataset(
    *,
    layout_resonances_df: pd.DataFrame,
    circuit_observables_df: pd.DataFrame,
) -> pd.DataFrame:
    """Build long source/qubit/L_jun resonance-frequency data."""
    layout = layout_resonances_df[
        ["source", "qubit", "l_jun_nh", "frequency_ghz", "fallback", "crossed"]
    ].copy()
    circuit = circuit_observables_df[
        ["source", "qubit", "l_jun_nh", "frequency_ghz", "fallback", "crossed"]
    ].copy()
    return pd.concat([layout, circuit], ignore_index=True).sort_values(
        ["source", "qubit", "l_jun_nh"]
    )


def build_resonance_frequency_comparison(resonance_df: pd.DataFrame) -> pd.DataFrame:
    """Build a Layout vs Circuit wide resonance-frequency comparison table."""
    wide = resonance_df.pivot_table(
        index=["qubit", "l_jun_nh"],
        columns="source",
        values="frequency_ghz",
        aggfunc="first",
    ).reset_index()
    wide.columns.name = None
    if "Layout" in wide.columns and "Circuit" in wide.columns:
        wide["delta_circuit_minus_layout_mhz"] = (wide["Circuit"] - wide["Layout"]) * 1000.0
    return wide.sort_values(["qubit", "l_jun_nh"])


def build_on_resonance_re_y_table(
    *,
    layout_re_y_df: pd.DataFrame,
    circuit_observables_df: pd.DataFrame,
) -> pd.DataFrame:
    """Combine Layout and Circuit on-resonance Re(Y) rows."""
    circuit = pd.DataFrame(
        {
            "source": "Circuit",
            "qubit": circuit_observables_df["qubit"].astype(str),
            "l_jun_nh": pd.to_numeric(circuit_observables_df["l_jun_nh"], errors="coerce"),
            "frequency_ghz": pd.to_numeric(
                circuit_observables_df["frequency_ghz"], errors="coerce"
            ),
            "re_y_frequency_ghz": pd.to_numeric(
                circuit_observables_df["frequency_ghz"], errors="coerce"
            ),
            "re_y_delta_mhz": 0.0,
            "re_y_s": pd.to_numeric(circuit_observables_df["re_y_s"], errors="coerce"),
            "re_y_matched": True,
            "C_eff_q3d_reduction_fF": pd.to_numeric(
                circuit_observables_df["c_eff_q_ff"], errors="coerce"
            )
            if "c_eff_q_ff" in circuit_observables_df.columns
            else math.nan,
            "t1_from_q3d_ceff_us": pd.to_numeric(
                circuit_observables_df["t1_us"], errors="coerce"
            )
            if "t1_us" in circuit_observables_df.columns
            else math.nan,
            "t1_us": math.nan,
            "t1_source": "pending_lc_fit",
        }
    )
    combined = pd.concat([layout_re_y_df.copy(), circuit], ignore_index=True)
    return combined.sort_values(["source", "qubit", "l_jun_nh"])


def lc_frequency_ghz(
    l_jun_nh: float | np.ndarray[Any, np.dtype[np.float64]],
    ls_nh: float,
    c_eff_pf: float,
    *,
    l_jun_effective_factor: float = thesis_plot_config.DEFAULT_L_JUN_EFFECTIVE_FACTOR,
) -> float | np.ndarray[Any, np.dtype[np.float64]]:
    """LC frequency model with explicit per-junction-to-effective-L factor."""
    l_jun_array = np.asarray(l_jun_nh, dtype=np.float64)
    l_total_h = (float(ls_nh) + float(l_jun_effective_factor) * l_jun_array) * NANO
    l_total_h = np.maximum(l_total_h, 1e-24)
    c_eff_f = max(float(c_eff_pf), 1e-24) * PICO
    frequency_hz = 1.0 / (2.0 * np.pi * np.sqrt(l_total_h * c_eff_f))
    frequency_ghz = frequency_hz / 1e9
    if np.isscalar(l_jun_nh):
        return float(frequency_ghz)
    return frequency_ghz


def fit_lc_frequency_sweeps(
    resonance_df: pd.DataFrame,
    *,
    l_jun_effective_factor: float = thesis_plot_config.DEFAULT_L_JUN_EFFECTIVE_FACTOR,
    min_points: int = 3,
    fixed_ls_sources: Sequence[str] = ("Circuit",),
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Fit source-aware LC resonance curves per source/qubit.

    Circuit rows come from the reduced circuit, where the only explicit qubit
    inductance is already represented by the effective per-junction Ljun term.
    For those sources, Ls is fixed to zero and only Ceff is fitted.
    """
    fit_rows: list[dict[str, Any]] = []
    curve_rows: list[dict[str, Any]] = []
    fixed_ls_source_set = {str(source) for source in fixed_ls_sources}
    for (source, qubit), group in resonance_df.groupby(["source", "qubit"], sort=True):
        source_name = str(source)
        fit_model = "fixed_Ls0" if source_name in fixed_ls_source_set else "floating_Ls"
        fit_group = group.dropna(subset=["l_jun_nh", "frequency_ghz"]).sort_values("l_jun_nh")
        fit_group = fit_group[np.isfinite(fit_group["frequency_ghz"])]
        if len(fit_group) < min_points:
            fit_rows.append(
                {
                    "source": source,
                    "qubit": qubit,
                    "status": "failed",
                    "reason": f"not enough points ({len(fit_group)} < {min_points})",
                    "Ls_nH": math.nan,
                    "C_eff_pF": math.nan,
                    "C_eff_fF": math.nan,
                    "C_eff_lc_fit_pF": math.nan,
                    "C_eff_lc_fit_fF": math.nan,
                    "RMSE_GHz": math.nan,
                    "l_jun_effective_factor": float(l_jun_effective_factor),
                    "fit_model": fit_model,
                    "n_points": len(fit_group),
                }
            )
            continue

        x = fit_group["l_jun_nh"].to_numpy(dtype=np.float64)
        y = fit_group["frequency_ghz"].to_numpy(dtype=np.float64)
        c_init_pf = _estimate_initial_capacitance_pf(x, y, l_jun_effective_factor)

        def floating_ls_model(
            l_jun: np.ndarray[Any, np.dtype[np.float64]],
            ls_nh: float,
            c_eff_pf: float,
        ):
            return lc_frequency_ghz(
                l_jun,
                ls_nh,
                c_eff_pf,
                l_jun_effective_factor=l_jun_effective_factor,
            )

        def fixed_ls_model(l_jun: np.ndarray[Any, np.dtype[np.float64]], c_eff_pf: float):
            return lc_frequency_ghz(
                l_jun,
                0.0,
                c_eff_pf,
                l_jun_effective_factor=l_jun_effective_factor,
            )

        try:
            if fit_model == "fixed_Ls0":
                params, _ = curve_fit(
                    fixed_ls_model,
                    x,
                    y,
                    p0=(c_init_pf,),
                    bounds=([1e-9], [10_000.0]),
                    maxfev=20_000,
                )
                ls_nh = 0.0
                c_eff_pf = float(params[0])
                y_fit = fixed_ls_model(x, c_eff_pf)
            else:
                params, _ = curve_fit(
                    floating_ls_model,
                    x,
                    y,
                    p0=(0.1, c_init_pf),
                    bounds=([0.0, 1e-9], [10_000.0, 10_000.0]),
                    maxfev=20_000,
                )
                ls_nh = float(params[0])
                c_eff_pf = float(params[1])
                y_fit = floating_ls_model(x, ls_nh, c_eff_pf)
            rmse = float(np.sqrt(np.mean((y - y_fit) ** 2)))
            fit_rows.append(
                {
                    "source": source,
                    "qubit": qubit,
                    "status": "success",
                    "reason": "",
                    "Ls_nH": ls_nh,
                    "C_eff_pF": c_eff_pf,
                    "C_eff_fF": c_eff_pf * 1000.0,
                    "C_eff_lc_fit_pF": c_eff_pf,
                    "C_eff_lc_fit_fF": c_eff_pf * 1000.0,
                    "RMSE_GHz": rmse,
                    "l_jun_effective_factor": float(l_jun_effective_factor),
                    "fit_model": fit_model,
                    "n_points": len(fit_group),
                }
            )
            x_curve = np.linspace(float(np.min(x)), float(np.max(x)), 240)
            y_curve = (
                fixed_ls_model(x_curve, c_eff_pf)
                if fit_model == "fixed_Ls0"
                else floating_ls_model(x_curve, ls_nh, c_eff_pf)
            )
            curve_rows.extend(
                {
                    "source": source,
                    "qubit": qubit,
                    "l_jun_nh": float(l_value),
                    "frequency_ghz": float(freq_value),
                    "Ls_nH": ls_nh,
                    "C_eff_pF": c_eff_pf,
                    "C_eff_fF": c_eff_pf * 1000.0,
                    "C_eff_lc_fit_pF": c_eff_pf,
                    "C_eff_lc_fit_fF": c_eff_pf * 1000.0,
                    "fit_model": fit_model,
                }
                for l_value, freq_value in zip(x_curve, y_curve, strict=True)
            )
        except Exception as exc:
            fit_rows.append(
                {
                    "source": source,
                    "qubit": qubit,
                    "status": "failed",
                    "reason": str(exc),
                    "Ls_nH": math.nan,
                    "C_eff_pF": math.nan,
                    "C_eff_fF": math.nan,
                    "C_eff_lc_fit_pF": math.nan,
                    "C_eff_lc_fit_fF": math.nan,
                    "RMSE_GHz": math.nan,
                    "l_jun_effective_factor": float(l_jun_effective_factor),
                    "fit_model": fit_model,
                    "n_points": len(fit_group),
                }
            )
    return pd.DataFrame(fit_rows), pd.DataFrame(curve_rows)


def add_t1_from_ceff_references(
    *,
    on_resonance_re_y_df: pd.DataFrame,
    lc_fit_params_df: pd.DataFrame,
) -> pd.DataFrame:
    """Fill comparison T1 from LC-fit Ceff and keep Q3D Ceff as a reference."""
    frame = on_resonance_re_y_df.copy()
    c_eff_by_group = {
        (row.source, row.qubit): float(_row_value(row, "C_eff_lc_fit_pF", "C_eff_pF"))
        for row in lc_fit_params_df[lc_fit_params_df["status"] == "success"].itertuples(index=False)
    }
    if "C_eff_q3d_reduction_fF" not in frame.columns:
        frame["C_eff_q3d_reduction_fF"] = math.nan
    if "t1_from_q3d_ceff_us" not in frame.columns:
        frame["t1_from_q3d_ceff_us"] = math.nan
    frame["C_eff_lc_fit_pF"] = math.nan
    frame["C_eff_lc_fit_fF"] = math.nan
    frame["ratio_q3d_over_lc"] = math.nan
    frame["t1_from_lc_fit_us"] = math.nan
    frame["t1_us"] = math.nan
    frame["t1_source"] = "missing_lc_fit_or_re_y"
    for idx, row in frame.iterrows():
        if not bool(row.get("re_y_matched", True)):
            continue
        source = str(row["source"])
        qubit = str(row["qubit"])
        c_eff_pf = c_eff_by_group.get((source, qubit))
        re_y_s = float(row["re_y_s"])
        if c_eff_pf is None or not np.isfinite(re_y_s) or re_y_s <= 0.0:
            continue
        c_eff_lc_fit_ff = c_eff_pf * 1000.0
        frame.loc[idx, "C_eff_lc_fit_pF"] = c_eff_pf
        frame.loc[idx, "C_eff_lc_fit_fF"] = c_eff_lc_fit_ff
        frame.loc[idx, "t1_from_lc_fit_us"] = (c_eff_pf * PICO / re_y_s) * 1e6
        frame.loc[idx, "t1_us"] = frame.loc[idx, "t1_from_lc_fit_us"]
        frame.loc[idx, "t1_source"] = "derived_from_lc_fit"
        c_eff_q3d_ff = float(row.get("C_eff_q3d_reduction_fF", math.nan))
        if np.isfinite(c_eff_q3d_ff):
            frame.loc[idx, "ratio_q3d_over_lc"] = c_eff_q3d_ff / c_eff_lc_fit_ff
            frame.loc[idx, "t1_from_q3d_ceff_us"] = (c_eff_q3d_ff * FEMTO / re_y_s) * 1e6
    return frame


def add_layout_t1_from_lc_fit(
    *,
    on_resonance_re_y_df: pd.DataFrame,
    lc_fit_params_df: pd.DataFrame,
) -> pd.DataFrame:
    """Backward-compatible wrapper for the unified LC-fit T1 helper."""
    return add_t1_from_ceff_references(
        on_resonance_re_y_df=on_resonance_re_y_df,
        lc_fit_params_df=lc_fit_params_df,
    )


def build_c_eff_reference_table(
    *,
    lc_fit_params_df: pd.DataFrame,
    circuit_observables_df: pd.DataFrame,
) -> pd.DataFrame:
    """Compare resonance-fit Ceff with Q3D capacitance-reduction Ceff references."""
    q3d_reference: dict[tuple[str, str], float] = {}
    if "c_eff_q_ff" in circuit_observables_df.columns:
        q3d_values = circuit_observables_df.dropna(subset=["c_eff_q_ff"])
        for qubit, group in q3d_values.groupby("qubit", sort=True):
            q3d_reference[("Circuit", str(qubit))] = float(group["c_eff_q_ff"].iloc[0])

    rows: list[dict[str, Any]] = []
    for row in lc_fit_params_df.itertuples(index=False):
        source = str(row.source)
        qubit = str(row.qubit)
        c_eff_lc_fit_ff = float(_row_value(row, "C_eff_lc_fit_fF", "C_eff_fF"))
        c_eff_q3d_ff = q3d_reference.get((source, qubit), math.nan)
        has_q3d_ratio = (
            np.isfinite(c_eff_lc_fit_ff)
            and c_eff_lc_fit_ff > 0.0
            and np.isfinite(c_eff_q3d_ff)
        )
        rows.append(
            {
                "source": source,
                "qubit": qubit,
                "status": str(row.status),
                "Ls_nH": float(row.Ls_nH),
                "C_eff_lc_fit_fF": c_eff_lc_fit_ff,
                "C_eff_q3d_reduction_fF": c_eff_q3d_ff,
                "ratio_q3d_over_lc": c_eff_q3d_ff / c_eff_lc_fit_ff
                if has_q3d_ratio
                else math.nan,
                "RMSE_GHz": float(row.RMSE_GHz),
                "l_jun_effective_factor": float(row.l_jun_effective_factor),
                "n_points": int(row.n_points),
            }
        )
    return pd.DataFrame(rows).sort_values(["source", "qubit"])


def fit_t1_capacitance(
    t1_df: pd.DataFrame,
    *,
    lc_fit_params_df: pd.DataFrame,
    min_points: int = 2,
) -> pd.DataFrame:
    """Fit T1 = C_fit / Re(Y) per source/qubit and compare against LC-fit Ceff."""
    lc_c_eff = {
        (row.source, row.qubit): float(_row_value(row, "C_eff_lc_fit_fF", "C_eff_fF"))
        for row in lc_fit_params_df[lc_fit_params_df["status"] == "success"].itertuples(index=False)
    }
    rows: list[dict[str, Any]] = []
    t1_column = "t1_from_lc_fit_us" if "t1_from_lc_fit_us" in t1_df.columns else "t1_us"
    valid = t1_df.dropna(subset=["re_y_s", t1_column]).copy()
    valid = valid[(valid["re_y_s"] > 0.0) & (valid[t1_column] > 0.0)]
    for (source, qubit), group in valid.groupby(["source", "qubit"], sort=True):
        if len(group) < min_points:
            rows.append(
                {
                    "source": source,
                    "qubit": qubit,
                    "status": "failed",
                    "reason": f"not enough points ({len(group)} < {min_points})",
                    "C_fit_fF": math.nan,
                    "C_eff_lc_fit_fF": lc_c_eff.get((source, qubit), math.nan),
                    "delta_fit_minus_lc_fF": math.nan,
                    "RMSE_us": math.nan,
                    "t1_column": t1_column,
                    "n_points": len(group),
                }
            )
            continue
        x = 1.0 / group["re_y_s"].to_numpy(dtype=np.float64)
        y = group[t1_column].to_numpy(dtype=np.float64) / 1e6
        c_fit_f = float(np.dot(x, y) / np.dot(x, x))
        t1_fit_us = c_fit_f * x * 1e6
        rmse_us = float(
            np.sqrt(np.mean((group[t1_column].to_numpy(dtype=np.float64) - t1_fit_us) ** 2))
        )
        c_fit_ff = c_fit_f / FEMTO
        c_eff_lc_ff = lc_c_eff.get((source, qubit), math.nan)
        rows.append(
            {
                "source": source,
                "qubit": qubit,
                "status": "success",
                "reason": "",
                "C_fit_fF": c_fit_ff,
                "C_eff_lc_fit_fF": c_eff_lc_ff,
                "delta_fit_minus_lc_fF": c_fit_ff - c_eff_lc_ff
                if np.isfinite(c_eff_lc_ff)
                else math.nan,
                "RMSE_us": rmse_us,
                "t1_column": t1_column,
                "n_points": len(group),
            }
        )
    return pd.DataFrame(rows)


def build_c_eff_xy_t1_trend_table(
    *,
    t1_df: pd.DataFrame,
    capacitance_df: pd.DataFrame,
    sources: Sequence[str] = ("Circuit",),
) -> pd.DataFrame:
    """Build the Ceff,xy-vs-T1 trend table from raw-matrix coupling values."""
    t1_column = "t1_from_lc_fit_us" if "t1_from_lc_fit_us" in t1_df.columns else "t1_us"
    raw_coupling = _raw_xy_coupling_reference(capacitance_df)
    rows: list[dict[str, Any]] = []
    valid = t1_df.dropna(subset=["frequency_ghz", "C_eff_lc_fit_fF", t1_column]).copy()
    valid = valid[valid["source"].astype(str).isin(tuple(str(source) for source in sources))]
    valid = valid[
        (valid["frequency_ghz"] > 0.0)
        & (valid["C_eff_lc_fit_fF"] > 0.0)
        & (valid[t1_column] > 0.0)
    ]
    for row in valid.itertuples(index=False):
        raw_reference = raw_coupling.get(str(row.qubit), {})
        c_eff_xy_signed_ff = raw_reference.get("signed_fF", math.nan)
        c_eff_xy_abs_ff = raw_reference.get("magnitude_fF", math.nan)
        if not np.isfinite(c_eff_xy_abs_ff) or c_eff_xy_abs_ff <= 0.0:
            continue

        t1_us = float(getattr(row, t1_column))
        gamma = 1.0 / (t1_us * 1e-6)
        omega = 2.0 * np.pi * float(row.frequency_ghz) * 1e9
        c_eff_xy_abs_sq = c_eff_xy_abs_ff**2
        rows.append(
            {
                "source": str(row.source),
                "qubit": str(row.qubit),
                "l_jun_nh": float(row.l_jun_nh),
                "frequency_ghz": float(row.frequency_ghz),
                "t1_from_lc_fit_us": t1_us,
                "gamma_from_lc_fit_per_s": gamma,
                "C_eff_lc_fit_fF": float(row.C_eff_lc_fit_fF),
                "C_eff_xy_signed_fF": c_eff_xy_signed_ff,
                "C_eff_xy_abs_fF": c_eff_xy_abs_ff,
                "C_eff_xy_abs_sq_fF2": c_eff_xy_abs_sq,
                "inv_C_eff_xy_abs_sq_1_per_fF2": 1.0 / c_eff_xy_abs_sq,
                "omega_rad_per_s": omega,
                "normalized_gamma": gamma * float(row.C_eff_lc_fit_fF) * FEMTO / omega**2,
            }
        )
    if not rows:
        return _empty_dataframe(
            [
                "source",
                "qubit",
                "l_jun_nh",
                "frequency_ghz",
                "t1_from_lc_fit_us",
                "gamma_from_lc_fit_per_s",
                "C_eff_lc_fit_fF",
                "C_eff_xy_signed_fF",
                "C_eff_xy_abs_fF",
                "C_eff_xy_abs_sq_fF2",
                "inv_C_eff_xy_abs_sq_1_per_fF2",
                "omega_rad_per_s",
                "normalized_gamma",
            ]
        )
    return pd.DataFrame(rows).sort_values(["source", "qubit", "l_jun_nh"])


def fit_c_eff_xy_t1_trend(
    trend_df: pd.DataFrame,
    *,
    min_points: int = 3,
    intercept_policy: str = "free",
) -> pd.DataFrame:
    """Fit fixed-Ljun T1 against raw-matrix Ceff,xy with inverse-square model."""
    if intercept_policy not in {"free", "zero"}:
        raise ValueError("intercept_policy must be 'free' or 'zero'.")
    rows: list[dict[str, Any]] = []
    fit_model = (
        "T1 = A / Ceff,xy^2 + B"
        if intercept_policy == "free"
        else "T1 = A / Ceff,xy^2"
    )
    for (source, l_jun_nh), source_group in trend_df.groupby(["source", "l_jun_nh"], sort=True):
        group = source_group.dropna(subset=["C_eff_xy_signed_fF", "t1_from_lc_fit_us"]).copy()
        group = group[
            (group["C_eff_xy_abs_fF"] > 0.0)
            & (group["t1_from_lc_fit_us"] > 0.0)
        ]
        if len(group) < min_points:
            rows.append(
                _failed_c_eff_xy_l_jun_fit_row(
                    source=str(source),
                    l_jun_nh=float(l_jun_nh),
                    fit_model=fit_model,
                    reason=f"not enough {source} points ({len(group)} < {min_points})",
                    n_points=len(group),
                    intercept_policy=intercept_policy,
                )
            )
            continue
        x = group["C_eff_xy_signed_fF"].to_numpy(dtype=np.float64)
        y = group["t1_from_lc_fit_us"].to_numpy(dtype=np.float64)
        fit = (
            _fit_inverse_square_with_intercept(x, y)
            if intercept_policy == "free"
            else _fit_inverse_square_zero_intercept(x, y)
        )
        rows.append(
            {
                "source": str(source),
                "l_jun_nh": float(l_jun_nh),
                "status": "success",
                "reason": "",
                "fit_model": fit_model,
                "coefficient_A_us_fF2": fit["coefficient"],
                "intercept_B_us": fit["intercept"],
                "intercept_policy": intercept_policy,
                "RMSE_us": fit["rmse"],
                "R2": fit["r2"],
                "n_points": len(group),
                "qubits": ",".join(group["qubit"].astype(str).tolist()),
            }
        )
    if not rows:
        return _empty_dataframe(
            [
                "source",
                "l_jun_nh",
                "status",
                "reason",
                "fit_model",
                "coefficient_A_us_fF2",
                "intercept_B_us",
                "intercept_policy",
                "RMSE_us",
                "R2",
                "n_points",
                "qubits",
            ]
        )
    return pd.DataFrame(rows).sort_values(["source", "l_jun_nh"])


def build_c_eff_xy_t1_fit_parameter_summary(
    fit_df: pd.DataFrame,
    *,
    dataset: str = "Circuit",
    source: str = "Circuit",
) -> pd.DataFrame:
    """Return printable A/B parameters for T1 = A / Ceff,xy^2 + B fits."""
    columns = [
        "dataset",
        "source",
        "l_jun_nh",
        "formula",
        "A_us_fF2",
        "B_us",
        "R2",
        "RMSE_us",
        "n_points",
        "qubits",
    ]
    if fit_df.empty:
        return _empty_dataframe(columns)

    successful = fit_df[
        (fit_df["source"].astype(str) == str(source))
        & (fit_df["status"].astype(str) == "success")
    ].copy()
    if successful.empty:
        return _empty_dataframe(columns)

    intercept_policy = (
        successful["intercept_policy"].astype(str)
        if "intercept_policy" in successful.columns
        else pd.Series("free", index=successful.index)
    )
    formula = np.where(
        intercept_policy == "zero",
        "T1_us = A_us_fF2 / Ceff_xy_fF^2 (B_us fixed to 0)",
        "T1_us = A_us_fF2 / Ceff_xy_fF^2 + B_us",
    )
    return pd.DataFrame(
        {
            "dataset": dataset,
            "source": successful["source"].astype(str),
            "l_jun_nh": pd.to_numeric(successful["l_jun_nh"], errors="coerce"),
            "formula": formula,
            "A_us_fF2": pd.to_numeric(
                successful["coefficient_A_us_fF2"],
                errors="coerce",
            ),
            "B_us": pd.to_numeric(successful["intercept_B_us"], errors="coerce"),
            "R2": pd.to_numeric(successful["R2"], errors="coerce"),
            "RMSE_us": pd.to_numeric(successful["RMSE_us"], errors="coerce"),
            "n_points": pd.to_numeric(successful["n_points"], errors="coerce"),
            "qubits": successful["qubits"].astype(str),
        }
    ).sort_values(["dataset", "source", "l_jun_nh"])


def build_lc_frequency_fit_display_table(
    fit_df: pd.DataFrame,
    *,
    dataset: str = "Layout/Circuit",
    l_jun_effective_factor: float = thesis_plot_config.DEFAULT_L_JUN_EFFECTIVE_FACTOR,
) -> pd.DataFrame:
    """Return a notebook-facing table for LC resonance frequency fit results."""
    columns = [
        "dataset",
        "source",
        "qubit",
        "status",
        "formula",
        "L_jun_effective_factor",
        "Ls_nH",
        "Ls_policy",
        "C_eff_lc_fit_pF",
        "C_eff_lc_fit_fF",
        "RMSE_GHz",
        "RMSE_MHz",
        "n_points",
        "reason",
    ]
    if fit_df.empty:
        return _empty_dataframe(columns)

    if "l_jun_effective_factor" in fit_df.columns:
        l_jun_factor = pd.to_numeric(fit_df["l_jun_effective_factor"], errors="coerce").fillna(
            float(l_jun_effective_factor)
        )
    else:
        l_jun_factor = pd.Series(float(l_jun_effective_factor), index=fit_df.index)

    source = fit_df["source"].astype(str)
    if "fit_model" in fit_df.columns:
        fit_model = fit_df["fit_model"].fillna("").astype(str)
    else:
        fit_model = pd.Series("", index=fit_df.index)
    fixed_ls = (fit_model == "fixed_Ls0") | (source == "Circuit")
    formula = np.where(
        fixed_ls,
        "f = 1 / (2*pi*sqrt(("
        f"{float(l_jun_effective_factor):.3g}*L_jun) * C_eff))",
        "f = 1 / (2*pi*sqrt((Ls + "
        f"{float(l_jun_effective_factor):.3g}*L_jun) * C_eff))",
    )
    ls_policy = np.where(
        fixed_ls,
        "fixed at 0 for reduced-circuit route",
        "fitted effective offset; not a separately identified parasitic inductance",
    )
    display = pd.DataFrame(
        {
            "dataset": dataset,
            "source": source,
            "qubit": fit_df["qubit"].astype(str),
            "status": fit_df["status"].astype(str),
            "formula": formula,
            "L_jun_effective_factor": l_jun_factor,
            "Ls_nH": pd.to_numeric(fit_df["Ls_nH"], errors="coerce"),
            "Ls_policy": ls_policy,
            "C_eff_lc_fit_pF": pd.to_numeric(
                fit_df["C_eff_lc_fit_pF"],
                errors="coerce",
            ),
            "C_eff_lc_fit_fF": pd.to_numeric(
                fit_df["C_eff_lc_fit_fF"],
                errors="coerce",
            ),
            "RMSE_GHz": pd.to_numeric(fit_df["RMSE_GHz"], errors="coerce"),
            "RMSE_MHz": pd.to_numeric(fit_df["RMSE_GHz"], errors="coerce") * 1000.0,
            "n_points": pd.to_numeric(fit_df["n_points"], errors="coerce"),
            "reason": fit_df["reason"].fillna("").astype(str),
        }
    )
    return display[columns].sort_values(["dataset", "source", "qubit"])


def build_resonance_frequency_ratio_display_table(resonance_df: pd.DataFrame) -> pd.DataFrame:
    """Return compact Circuit/Layout resonance frequency ratio rows for notebooks."""
    columns = [
        "qubit",
        "l_jun_nh",
        "Circuit_frequency_GHz",
        "Layout_frequency_GHz",
        "ratio_circuit_over_layout",
        "ratio_percent_offset",
        "delta_circuit_minus_layout_mhz",
    ]
    ratio_df = _build_circuit_over_layout_frequency_ratio(resonance_df, ratio_kind="data")
    if ratio_df.empty:
        return _empty_dataframe(columns)

    display = pd.DataFrame(
        {
            "qubit": ratio_df["qubit"].astype(str),
            "l_jun_nh": pd.to_numeric(ratio_df["l_jun_nh"], errors="coerce"),
            "Circuit_frequency_GHz": pd.to_numeric(ratio_df["Circuit"], errors="coerce"),
            "Layout_frequency_GHz": pd.to_numeric(ratio_df["Layout"], errors="coerce"),
            "ratio_circuit_over_layout": pd.to_numeric(
                ratio_df["ratio_circuit_over_layout"],
                errors="coerce",
            ),
            "ratio_percent_offset": pd.to_numeric(
                ratio_df["ratio_percent_offset"],
                errors="coerce",
            ),
            "delta_circuit_minus_layout_mhz": pd.to_numeric(
                ratio_df["delta_circuit_minus_layout_mhz"],
                errors="coerce",
            ),
        }
    )
    return display[columns].sort_values(["qubit", "l_jun_nh"])


def build_re_y_ratio_display_table(on_resonance_re_y_df: pd.DataFrame) -> pd.DataFrame:
    """Return compact Circuit/Layout on-resonance Re(Y) ratio rows for notebooks."""
    columns = [
        "qubit",
        "l_jun_nh",
        "Circuit_re_y_s",
        "Layout_re_y_s",
        "ratio_circuit_over_layout",
    ]
    required_columns = {"source", "qubit", "l_jun_nh", "re_y_s"}
    if on_resonance_re_y_df.empty or not required_columns.issubset(on_resonance_re_y_df.columns):
        return _empty_dataframe(columns)

    plot_df = on_resonance_re_y_df.dropna(subset=["re_y_s"]).copy()
    if plot_df.empty:
        return _empty_dataframe(columns)

    wide = plot_df.pivot_table(
        index=["qubit", "l_jun_nh"],
        columns="source",
        values="re_y_s",
        aggfunc="first",
    ).reset_index()
    wide.columns.name = None
    if "Circuit" not in wide.columns or "Layout" not in wide.columns:
        return _empty_dataframe(columns)

    ratio_df = wide.dropna(subset=["Circuit", "Layout"]).copy()
    ratio_df = ratio_df[ratio_df["Layout"].astype(float) > 0.0]
    if ratio_df.empty:
        return _empty_dataframe(columns)

    display = pd.DataFrame(
        {
            "qubit": ratio_df["qubit"].astype(str),
            "l_jun_nh": pd.to_numeric(ratio_df["l_jun_nh"], errors="coerce"),
            "Circuit_re_y_s": pd.to_numeric(ratio_df["Circuit"], errors="coerce"),
            "Layout_re_y_s": pd.to_numeric(ratio_df["Layout"], errors="coerce"),
            "ratio_circuit_over_layout": (
                pd.to_numeric(ratio_df["Circuit"], errors="coerce")
                / pd.to_numeric(ratio_df["Layout"], errors="coerce")
            ),
        }
    )
    return display[columns].sort_values(["qubit", "l_jun_nh"])


def build_c_eff_xy_t1_result_display_tables(
    *,
    trend_df: pd.DataFrame,
    fit_df: pd.DataFrame,
    source: str,
    l_jun_nh: float,
    dataset: str = "Q3D",
    no_offset_fit_df: pd.DataFrame | None = None,
) -> dict[str, pd.DataFrame]:
    """Return notebook-facing point and fit tables for one Ceff,xy/T1 figure."""
    point_columns = [
        "dataset",
        "source",
        "qubit",
        "l_jun_nh",
        "frequency_ghz",
        "C_eff_xy_signed_fF",
        "C_eff_xy_abs_fF",
        "t1_from_lc_fit_us",
        "C_eff_lc_fit_fF",
    ]
    fit_columns = [
        "dataset",
        "source",
        "l_jun_nh",
        "intercept_policy",
        "formula",
        "A_us_fF2",
        "B_us",
        "RMSE_us",
        "R2",
        "n_points",
        "qubits",
    ]
    required_point_columns = {
        "source",
        "qubit",
        "l_jun_nh",
        "frequency_ghz",
        "C_eff_xy_signed_fF",
        "C_eff_xy_abs_fF",
        "t1_from_lc_fit_us",
        "C_eff_lc_fit_fF",
    }
    if trend_df.empty or not required_point_columns.issubset(trend_df.columns):
        points = _empty_dataframe(point_columns)
    else:
        focus = trend_df[
            (trend_df["source"].astype(str) == str(source))
            & np.isclose(
                pd.to_numeric(trend_df["l_jun_nh"], errors="coerce"),
                float(l_jun_nh),
            )
        ].copy()
        if focus.empty:
            points = _empty_dataframe(point_columns)
        else:
            points = pd.DataFrame(
                {
                    "dataset": dataset,
                    "source": focus["source"].astype(str),
                    "qubit": focus["qubit"].astype(str),
                    "l_jun_nh": pd.to_numeric(focus["l_jun_nh"], errors="coerce"),
                    "frequency_ghz": pd.to_numeric(focus["frequency_ghz"], errors="coerce"),
                    "C_eff_xy_signed_fF": pd.to_numeric(
                        focus["C_eff_xy_signed_fF"],
                        errors="coerce",
                    ),
                    "C_eff_xy_abs_fF": pd.to_numeric(
                        focus["C_eff_xy_abs_fF"],
                        errors="coerce",
                    ),
                    "t1_from_lc_fit_us": pd.to_numeric(
                        focus["t1_from_lc_fit_us"],
                        errors="coerce",
                    ),
                    "C_eff_lc_fit_fF": pd.to_numeric(
                        focus["C_eff_lc_fit_fF"],
                        errors="coerce",
                    ),
                }
            )[point_columns].sort_values(["source", "l_jun_nh", "C_eff_xy_signed_fF"])

    fit_frames = [
        _build_c_eff_xy_fit_display_rows(
            fit_df,
            dataset=dataset,
            source=source,
            l_jun_nh=l_jun_nh,
        )
    ]
    if no_offset_fit_df is not None:
        fit_frames.append(
            _build_c_eff_xy_fit_display_rows(
                no_offset_fit_df,
                dataset=dataset,
                source=source,
                l_jun_nh=l_jun_nh,
            )
        )
    fits = pd.concat(fit_frames, ignore_index=True) if fit_frames else _empty_dataframe(fit_columns)
    if fits.empty:
        fits = _empty_dataframe(fit_columns)
    else:
        fits = fits[fit_columns].sort_values(["source", "l_jun_nh", "intercept_policy"])
    return {"points": points, "fits": fits}


def make_c_eff_xy_t1_trend_figure(
    *,
    trend_df: pd.DataFrame,
    trend_fit_df: pd.DataFrame,
    no_offset_fit_df: pd.DataFrame | None = None,
    l_jun_nh: float,
    source: str = "Circuit",
    title: str | None = None,
    show_point_labels: bool = True,
) -> go.Figure:
    """Build single-Ljun T1-vs-Ceff,xy inverse-square diagnostic."""
    focus = trend_df[
        (trend_df["source"].astype(str) == str(source))
        & np.isclose(trend_df["l_jun_nh"].astype(float), float(l_jun_nh))
    ].copy()
    focus = focus.sort_values("C_eff_xy_signed_fF")
    if focus.empty:
        raise ValueError(f"Missing {source} Ceff,xy trend rows for L_jun={l_jun_nh:g} nH.")
    fit = _select_c_eff_xy_l_jun_fit(trend_fit_df, source=source, l_jun_nh=l_jun_nh)
    marker_color: str | list[str] = [_qubit_color(qubit) for qubit in focus["qubit"]]
    if all(color == thesis_plot_config.PLOTLY_FALLBACK_TRACE_COLOR for color in marker_color):
        marker_color = _source_color(source)
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=focus["C_eff_xy_signed_fF"],
            y=focus["t1_from_lc_fit_us"],
            mode="markers+text" if show_point_labels else "markers",
            text=focus["qubit"].astype(str) if show_point_labels else None,
            textposition="top center",
            name=f"{source} data",
            marker={
                "color": marker_color,
                "size": thesis_plot_config.PLOTLY_MARKER_SIZE,
                "symbol": "circle",
            },
            customdata=focus[
                ["qubit", "frequency_ghz", "C_eff_xy_abs_fF", "C_eff_lc_fit_fF"]
            ].to_numpy(dtype=object),
            hovertemplate=(
                "%{customdata[0]}<br>"
                "Ceff,xy=%{x:.6f} fF<br>"
                "T1=%{y:.6g} us<br>"
                "fq=%{customdata[1]:.6f} GHz<br>"
                "|Ceff,xy|=%{customdata[2]:.6f} fF<br>"
                "LC-fit Ceff,q=%{customdata[3]:.3f} fF<extra></extra>"
            ),
        )
    )
    if fit is not None:
        if no_offset_fit_df is None:
            x_min = float(focus["C_eff_xy_signed_fF"].min())
            x_max = float(focus["C_eff_xy_signed_fF"].max())
            x_line = np.linspace(x_min, x_max, 240)
            y_line = _inverse_square_with_intercept(
                x_line,
                float(fit["coefficient_A_us_fF2"]),
                float(fit["intercept_B_us"]),
            )
            fig.add_trace(
                go.Scatter(
                    x=x_line,
                    y=y_line,
                    mode="lines",
                    name=(
                        "fit: T1 = A / Ceff,xy^2 + B"
                        f"<br>R2={float(fit['R2']):.4f}"
                    ),
                    line={
                        "color": thesis_plot_config.PLOTLY_ACCENT_COLOR,
                        "width": thesis_plot_config.PLOTLY_LINE_WIDTH,
                    },
                    hovertemplate=(
                        "Ceff,xy=%{x:.6f} fF<br>fit T1=%{y:.6g} us<extra></extra>"
                    ),
                )
            )
        else:
            _add_c_eff_xy_fit_trace(
                fig,
                fit=fit,
                focus=focus,
                name_prefix="B floating",
                line_color=thesis_plot_config.PLOTLY_ACCENT_COLOR,
                line_dash="solid",
            )
    if no_offset_fit_df is not None:
        no_offset_fit = _select_c_eff_xy_l_jun_fit(
            no_offset_fit_df,
            source=source,
            l_jun_nh=l_jun_nh,
        )
        if no_offset_fit is not None:
            _add_c_eff_xy_fit_trace(
                fig,
                fit=no_offset_fit,
                focus=focus,
                name_prefix="B fixed 0",
                line_color=thesis_plot_config.PLOTLY_FALLBACK_TRACE_COLOR,
                line_dash="dash",
            )
    fig.update_xaxes(title_text="Ceff,xy [fF]")
    fig.update_yaxes(title_text="T1 from LC-fit Ceff [us]")
    _apply_common_layout(
        fig,
        title=title or f"{source} T1 vs Ceff,xy (Ljun={l_jun_nh:g} nH)",
    )
    return fig


def make_c_eff_xy_t1_trend_comparison_figure(
    *,
    trend_df: pd.DataFrame,
    trend_fit_df: pd.DataFrame,
    l_jun_nh: float,
    sources: Sequence[str] = ("Circuit", "Layout"),
    title: str | None = None,
    show_point_labels: bool = True,
) -> go.Figure:
    """Build single-Ljun Layout-vs-Circuit Ceff,xy/T1 comparison."""
    fig = go.Figure()
    added_sources: list[str] = []
    text_positions = {
        "Circuit": "top center",
        "Layout": "bottom center",
    }
    for source in sources:
        focus = trend_df[
            (trend_df["source"].astype(str) == str(source))
            & np.isclose(trend_df["l_jun_nh"].astype(float), float(l_jun_nh))
        ].copy()
        focus = focus.sort_values("C_eff_xy_signed_fF")
        fit = _select_c_eff_xy_l_jun_fit(trend_fit_df, source=source, l_jun_nh=l_jun_nh)
        if focus.empty or fit is None:
            continue

        source_color = _source_color(source)
        fig.add_trace(
            go.Scatter(
                x=focus["C_eff_xy_signed_fF"],
                y=focus["t1_from_lc_fit_us"],
                mode="markers+text" if show_point_labels else "markers",
                text=focus["qubit"].astype(str) if show_point_labels else None,
                textposition=text_positions.get(str(source), "top center"),
                name=f"{source} data",
                marker={
                    "color": source_color,
                    "size": thesis_plot_config.PLOTLY_MARKER_SIZE,
                    "symbol": _source_marker_symbol(source),
                },
                customdata=focus[
                    ["qubit", "frequency_ghz", "C_eff_xy_abs_fF", "C_eff_lc_fit_fF"]
                ].to_numpy(dtype=object),
                hovertemplate=(
                    f"{source} "
                    "%{customdata[0]}<br>"
                    "Ceff,xy=%{x:.6f} fF<br>"
                    "T1=%{y:.6g} us<br>"
                    "fq=%{customdata[1]:.6f} GHz<br>"
                    "|Ceff,xy|=%{customdata[2]:.6f} fF<br>"
                    "LC-fit Ceff,q=%{customdata[3]:.3f} fF<extra></extra>"
                ),
            )
        )
        x_line = np.linspace(
            float(focus["C_eff_xy_signed_fF"].min()),
            float(focus["C_eff_xy_signed_fF"].max()),
            240,
        )
        y_line = _inverse_square_with_intercept(
            x_line,
            float(fit["coefficient_A_us_fF2"]),
            float(fit["intercept_B_us"]),
        )
        fig.add_trace(
            go.Scatter(
                x=x_line,
                y=y_line,
                mode="lines",
                name=f"{source} fit<br>R2={float(fit['R2']):.4f}",
                line={
                    "color": source_color,
                    "dash": "solid",
                    "width": thesis_plot_config.PLOTLY_LINE_WIDTH,
                },
                hovertemplate=(
                    f"{source} fit<br>"
                    "Ceff,xy=%{x:.6f} fF<br>"
                    "fit T1=%{y:.6g} us<extra></extra>"
                ),
            )
        )
        added_sources.append(str(source))

    if len(added_sources) < 2:
        raise ValueError(
            f"Need at least two successful sources for Ceff,xy comparison at "
            f"L_jun={l_jun_nh:g} nH."
        )

    fig.update_xaxes(title_text="Ceff,xy [fF]")
    fig.update_yaxes(title_text="T1 from LC-fit Ceff [us]")
    _apply_common_layout(
        fig,
        title=title or f"Layout vs Circuit T1 vs Ceff,xy (Ljun={l_jun_nh:g} nH)",
    )
    return fig


def make_focus_admittance_trace_figure(
    *,
    circuit_trace_df: pd.DataFrame,
    focus_qubit: str,
    focus_l_jun_nh: float,
) -> go.Figure:
    """Build Plotly Re/Im reduced admittance focus trace."""
    focus = _select_focus_trace(circuit_trace_df, focus_qubit, focus_l_jun_nh)
    fig = make_subplots(
        rows=2,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.08,
        subplot_titles=("Re[Yeff]", "Im[Yeff]"),
    )
    fig.add_trace(
        go.Scatter(
            x=focus["frequency_ghz"],
            y=focus["re_y_s"],
            mode="lines",
            name="Re[Yeff]",
            line={"color": _qubit_color("Q0"), "width": thesis_plot_config.PLOTLY_LINE_WIDTH},
        ),
        row=1,
        col=1,
    )
    fig.add_trace(
        go.Scatter(
            x=focus["frequency_ghz"],
            y=focus["im_y_s"],
            mode="lines",
            name="Im[Yeff]",
            line={"color": _qubit_color("Q1"), "width": thesis_plot_config.PLOTLY_LINE_WIDTH},
        ),
        row=2,
        col=1,
    )
    fig.update_xaxes(title_text="Frequency [GHz]", row=2, col=1)
    fig.update_yaxes(title_text="Re[Yeff] [S]", row=1, col=1)
    fig.update_yaxes(title_text="Im[Yeff] [S]", row=2, col=1)
    _apply_common_layout(
        fig,
        title=(
            "Circuit Reduced Admittance After PTC + CT + Kron "
            f"({focus_qubit}, Ljun={focus_l_jun_nh:g} nH)"
        ),
    )
    return fig


def make_focus_resonance_extraction_figure(
    *,
    circuit_trace_df: pd.DataFrame,
    circuit_observables_df: pd.DataFrame,
    focus_qubit: str,
    focus_l_jun_nh: float,
) -> go.Figure:
    """Build Plotly focus resonance extraction diagnostic."""
    focus = _select_focus_trace(circuit_trace_df, focus_qubit, focus_l_jun_nh)
    obs = _select_focus_observable(circuit_observables_df, focus_qubit, focus_l_jun_nh)
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=focus["frequency_ghz"],
            y=focus["im_y_s"],
            mode="lines",
            name="Im[Yeff]",
            line={"color": _qubit_color("Q1"), "width": thesis_plot_config.PLOTLY_LINE_WIDTH},
        )
    )
    fig.add_hline(
        y=0.0,
        line={
            "color": thesis_plot_config.PLOTLY_REFERENCE_LINE_COLOR,
            "dash": "dot",
            "width": thesis_plot_config.PLOTLY_REFERENCE_LINE_WIDTH,
        },
    )
    bracket_x = [obs.get("bracket_f0_ghz"), obs.get("bracket_f1_ghz")]
    bracket_y = [obs.get("bracket_im_y0"), obs.get("bracket_im_y1")]
    if all(_is_finite_number(value) for value in bracket_x + bracket_y):
        fig.add_trace(
            go.Scatter(
                x=bracket_x,
                y=bracket_y,
                mode="markers+lines",
                name="Bracket",
                marker={
                    "color": thesis_plot_config.PLOTLY_ACCENT_COLOR,
                    "size": thesis_plot_config.PLOTLY_MARKER_SIZE,
                },
                line={"color": thesis_plot_config.PLOTLY_ACCENT_COLOR, "dash": "dash"},
            )
        )
    resonance_frequency = float(obs["frequency_ghz"])
    fig.add_vline(
        x=resonance_frequency,
        line={
            "color": _qubit_color("Q2"),
            "dash": "dash",
            "width": thesis_plot_config.PLOTLY_LINE_WIDTH,
        },
    )
    annotation = (
        f"fq={resonance_frequency:.6f} GHz<br>"
        f"Re[Yeff(fq)]={float(obs['re_y_s']):.3e} S<br>"
        f"Ceff,q(Q3D)={float(obs.get('c_eff_q_ff', math.nan)):.3f} fF<br>"
        f"T1_XY(Q3D Ceff)={float(obs.get('t1_us', math.nan)):.3f} us"
    )
    fig.add_annotation(
        x=resonance_frequency,
        y=0.95,
        xref="x",
        yref="paper",
        text=annotation,
        showarrow=True,
        arrowhead=2,
        ax=40,
        ay=-40,
        bgcolor="rgba(255,255,255,0.85)",
        bordercolor=_qubit_color("Q2"),
    )
    fig.update_xaxes(title_text="Frequency [GHz]")
    fig.update_yaxes(title_text="Im[Yeff] [S]")
    _apply_common_layout(
        fig,
        title=f"Resonance Extraction ({focus_qubit}, Ljun={focus_l_jun_nh:g} nH)",
    )
    return fig


def make_im_trace_comparison_figure(
    *,
    layout_trace_df: pd.DataFrame,
    circuit_trace_df: pd.DataFrame,
    trace_l_jun_nh_values: Sequence[float],
    max_points_per_line: int,
) -> go.Figure:
    """Build Layout vs Circuit Im(Y) trace comparison."""
    combined = pd.concat(
        [
            layout_trace_df[["source", "qubit", "l_jun_nh", "frequency_ghz", "im_y_s"]],
            circuit_trace_df[["source", "qubit", "l_jun_nh", "frequency_ghz", "im_y_s"]],
        ],
        ignore_index=True,
    )
    allowed_l = {float(value) for value in trace_l_jun_nh_values}
    combined = combined[combined["l_jun_nh"].astype(float).isin(allowed_l)]
    fig = go.Figure()
    for (source, qubit, l_jun), group in combined.groupby(
        ["source", "qubit", "l_jun_nh"],
        sort=True,
    ):
        group = _downsample_line(group.sort_values("frequency_ghz"), max_points_per_line)
        fig.add_trace(
            go.Scatter(
                x=group["frequency_ghz"],
                y=group["im_y_s"],
                mode="lines",
                name=f"{source} {qubit} L={float(l_jun):g} nH",
                legendgroup=f"{source}-{qubit}",
                line={
                    "color": _qubit_color(qubit),
                    "dash": SOURCE_DASHES.get(str(source), "solid"),
                    "width": thesis_plot_config.PLOTLY_LINE_WIDTH,
                },
                hovertemplate=(
                    f"{source} {qubit}, L={float(l_jun):g} nH<br>"
                    "f=%{x:.6f} GHz<br>Im(Y)=%{y:.3e} S<extra></extra>"
                ),
            )
        )
    fig.add_hline(
        y=0.0,
        line={
            "color": thesis_plot_config.PLOTLY_REFERENCE_LINE_COLOR,
            "dash": "dot",
            "width": thesis_plot_config.PLOTLY_REFERENCE_LINE_WIDTH,
        },
    )
    fig.update_xaxes(title_text="Frequency [GHz]")
    fig.update_yaxes(title_text="Im(Y) [S]")
    _apply_common_layout(fig, title="Layout vs Circuit Im(Y) Trace Comparison")
    return fig


def make_resonance_frequency_sweep_figure(
    *,
    resonance_df: pd.DataFrame,
    lc_fit_curve_df: pd.DataFrame,
) -> go.Figure:
    """Build L_jun vs resonance frequency comparison with LC fit curves."""
    fig = go.Figure()
    for (source, qubit), group in resonance_df.groupby(["source", "qubit"], sort=True):
        fig.add_trace(
            go.Scatter(
                x=group["l_jun_nh"],
                y=group["frequency_ghz"],
                mode="markers",
                name=f"{source} {qubit} data",
                marker={
                    "color": _qubit_color(qubit),
                    "size": thesis_plot_config.PLOTLY_MARKER_SIZE,
                    "symbol": "circle" if source == "Layout" else "diamond",
                },
                legendgroup=f"{source}-{qubit}",
            )
        )
    for (source, qubit), group in lc_fit_curve_df.groupby(["source", "qubit"], sort=True):
        fig.add_trace(
            go.Scatter(
                x=group["l_jun_nh"],
                y=group["frequency_ghz"],
                mode="lines",
                name=f"{source} {qubit} LC fit",
                line={
                    "color": _qubit_color(qubit),
                    "dash": SOURCE_DASHES.get(str(source), "solid"),
                    "width": thesis_plot_config.PLOTLY_LINE_WIDTH,
                },
                legendgroup=f"{source}-{qubit}",
            )
        )
    fig.update_xaxes(title_text="Per-junction L_jun [nH]")
    fig.update_yaxes(title_text="Resonance frequency [GHz]")
    _apply_common_layout(fig, title="Resonance Frequency Sweep And LC Fit")
    return fig


def make_resonance_frequency_ratio_figure(
    *,
    resonance_df: pd.DataFrame,
) -> go.Figure:
    """Build one Circuit/Layout resonance-frequency ratio point per qubit and Ljun."""
    data_ratio = _build_circuit_over_layout_frequency_ratio(resonance_df, ratio_kind="data")
    fig = go.Figure()
    for qubit, group in data_ratio.groupby("qubit", sort=True):
        fig.add_trace(
            go.Scatter(
                x=group["l_jun_nh"],
                y=group["ratio_circuit_over_layout"],
                mode="markers+lines",
                name=f"{qubit} ratio",
                legendgroup=str(qubit),
                line={
                    "color": _qubit_color(qubit),
                    "width": thesis_plot_config.PLOTLY_LINE_WIDTH,
                },
                marker={
                    "color": _qubit_color(qubit),
                    "size": thesis_plot_config.PLOTLY_MARKER_SIZE,
                    "symbol": "diamond",
                },
                customdata=group[
                    [
                        "Circuit",
                        "Layout",
                        "delta_circuit_minus_layout_mhz",
                        "ratio_percent_offset",
                    ]
                ].to_numpy(dtype=float),
                hovertemplate=(
                    f"{qubit} data<br>"
                    "Ljun=%{x:.3f} nH<br>"
                    "Circuit/Layout=%{y:.6f}<br>"
                    "offset=%{customdata[3]:+.3f}%<br>"
                    "Circuit=%{customdata[0]:.6f} GHz<br>"
                    "Layout=%{customdata[1]:.6f} GHz<br>"
                    "Delta=%{customdata[2]:+.3f} MHz<extra></extra>"
                ),
            )
        )
    fig.add_hline(
        y=1.0,
        line={
            "color": thesis_plot_config.PLOTLY_REFERENCE_LINE_COLOR,
            "dash": "dot",
            "width": thesis_plot_config.PLOTLY_REFERENCE_LINE_WIDTH,
        },
    )
    fig.update_xaxes(title_text="Per-junction L_jun [nH]")
    fig.update_yaxes(title_text="Frequency ratio: Circuit / Layout")
    _apply_common_layout(fig, title="Resonance Frequency Ratio")
    return fig


def make_on_resonance_re_y_figure(on_resonance_re_y_df: pd.DataFrame) -> go.Figure:
    """Build on-resonance Re(Y) comparison."""
    fig = go.Figure()
    plot_df = on_resonance_re_y_df.dropna(subset=["re_y_s"]).copy()
    for (source, qubit), group in plot_df.groupby(["source", "qubit"], sort=True):
        fig.add_trace(
            go.Scatter(
                x=group["l_jun_nh"],
                y=group["re_y_s"],
                mode="markers+lines",
                name=f"{source} {qubit}",
                line={
                    "color": _qubit_color(qubit),
                    "dash": SOURCE_DASHES.get(str(source), "solid"),
                },
                marker={"size": thesis_plot_config.PLOTLY_MARKER_SIZE},
                legendgroup=f"{source}-{qubit}",
            )
        )
    fig.update_xaxes(title_text="Per-junction L_jun [nH]")
    fig.update_yaxes(title_text="On-resonance Re(Y) [S]", type="log")
    _apply_common_layout(fig, title="On-Resonance Re(Y) Comparison")
    return fig


def make_t1_comparison_figure(t1_df: pd.DataFrame) -> go.Figure:
    """Build default T1 comparison from resonance-fit Ceff."""
    fig = go.Figure()
    y_column = "t1_from_lc_fit_us" if "t1_from_lc_fit_us" in t1_df.columns else "t1_us"
    plot_df = t1_df.dropna(subset=[y_column]).copy()
    for (source, qubit), group in plot_df.groupby(["source", "qubit"], sort=True):
        customdata = np.stack(
            [
                group.get("C_eff_lc_fit_fF", pd.Series(math.nan, index=group.index)).to_numpy(
                    dtype=float
                ),
                group.get(
                    "t1_from_q3d_ceff_us", pd.Series(math.nan, index=group.index)
                ).to_numpy(dtype=float),
            ],
            axis=-1,
        )
        fig.add_trace(
            go.Scatter(
                x=group["l_jun_nh"],
                y=group[y_column],
                mode="markers+lines",
                name=f"{source} {qubit}",
                line={
                    "color": _qubit_color(qubit),
                    "dash": SOURCE_DASHES.get(str(source), "solid"),
                },
                marker={"size": thesis_plot_config.PLOTLY_MARKER_SIZE},
                legendgroup=f"{source}-{qubit}",
                customdata=customdata,
                hovertemplate=(
                    f"{source} {qubit}<br>"
                    "Ljun=%{x:.3f} nH<br>"
                    "T1(LC fit Ceff)=%{y:.6g} us<br>"
                    "Ceff LC fit=%{customdata[0]:.3f} fF<br>"
                    "T1(Q3D Ceff ref)=%{customdata[1]:.6g} us<extra></extra>"
                ),
            )
        )
    fig.update_xaxes(title_text="Per-junction L_jun [nH]")
    fig.update_yaxes(title_text="T1 from LC-fit Ceff [us]", type="log")
    _apply_common_layout(fig, title="T1 Comparison From LC-Fit Ceff")
    return fig


def make_c_eff_overview_figure(lc_fit_params_df: pd.DataFrame) -> go.Figure:
    """Build resonance-fit Ceff overview for Layout/Circuit and Q0-Q2."""
    fig = go.Figure()
    plot_df = lc_fit_params_df[lc_fit_params_df["status"] == "success"].copy()
    c_eff_column = "C_eff_lc_fit_fF" if "C_eff_lc_fit_fF" in plot_df.columns else "C_eff_fF"
    for source, group in plot_df.groupby("source", sort=True):
        fig.add_trace(
            go.Bar(
                x=group["qubit"],
                y=group[c_eff_column],
                name=f"{source} Ceff",
                marker={
                    "color": [_qubit_color(qubit) for qubit in group["qubit"]],
                    "pattern": {"shape": "" if source == "Layout" else "/"},
                },
                customdata=np.stack(
                    [
                        group["Ls_nH"].to_numpy(dtype=float),
                        group["RMSE_GHz"].to_numpy(dtype=float),
                    ],
                    axis=-1,
                ),
                hovertemplate=(
                    f"{source} " + "%{x}<br>"
                    "Ceff=%{y:.3f} fF<br>"
                    "Ls=%{customdata[0]:.4f} nH<br>"
                    "RMSE=%{customdata[1]:.4e} GHz<extra></extra>"
                ),
            )
        )
    fig.update_layout(barmode="group")
    fig.update_xaxes(title_text="Qubit")
    fig.update_yaxes(title_text="LC-fit Ceff [fF]")
    _apply_common_layout(fig, title="Effective Capacitance Fit Overview")
    return fig


def make_c_eff_reference_diagnostic_figure(c_eff_reference_df: pd.DataFrame) -> go.Figure:
    """Build LC-fit vs Q3D-reduction Ceff diagnostic bars."""
    fig = go.Figure()
    plot_df = c_eff_reference_df[c_eff_reference_df["status"] == "success"].copy()
    plot_df["label"] = plot_df["source"].astype(str) + " " + plot_df["qubit"].astype(str)
    fig.add_trace(
        go.Bar(
            x=plot_df["label"],
            y=plot_df["C_eff_lc_fit_fF"],
            name="LC-fit Ceff",
            marker={"color": _source_color("Circuit")},
            hovertemplate="%{x}<br>LC-fit Ceff=%{y:.3f} fF<extra></extra>",
        )
    )
    q3d = plot_df.dropna(subset=["C_eff_q3d_reduction_fF"])
    fig.add_trace(
        go.Bar(
            x=q3d["label"],
            y=q3d["C_eff_q3d_reduction_fF"],
            name="Q3D reduction Ceff,q",
            marker={"color": thesis_plot_config.PLOTLY_ACCENT_COLOR},
            customdata=q3d["ratio_q3d_over_lc"],
            hovertemplate=(
                "%{x}<br>Q3D Ceff,q=%{y:.3f} fF<br>"
                "Q3D/LC=%{customdata:.4f}<extra></extra>"
            ),
        )
    )
    fig.update_layout(barmode="group")
    fig.update_xaxes(title_text="Source / qubit")
    fig.update_yaxes(title_text="Ceff [fF]")
    _apply_common_layout(fig, title="LC-Fit Ceff vs Q3D Reduction Reference")
    return fig


def make_re_y_ratio_figure(on_resonance_re_y_df: pd.DataFrame) -> go.Figure:
    """Build Circuit/Layout on-resonance Re(Y) ratio by qubit and Ljun."""
    plot_df = on_resonance_re_y_df.dropna(subset=["re_y_s"]).copy()
    wide = plot_df.pivot_table(
        index=["qubit", "l_jun_nh"],
        columns="source",
        values="re_y_s",
        aggfunc="first",
    ).reset_index()
    wide.columns.name = None
    if "Circuit" not in wide.columns or "Layout" not in wide.columns:
        wide["ratio_circuit_over_layout"] = math.nan
    else:
        wide["ratio_circuit_over_layout"] = wide["Circuit"] / wide["Layout"]
    fig = go.Figure()
    ratio_df = wide.dropna(subset=["ratio_circuit_over_layout"]).copy()
    for qubit, group in ratio_df.groupby("qubit", sort=True):
        fig.add_trace(
            go.Scatter(
                x=group["l_jun_nh"],
                y=group["ratio_circuit_over_layout"],
                mode="markers+lines",
                name=str(qubit),
                line={"color": _qubit_color(qubit)},
                marker={"size": thesis_plot_config.PLOTLY_MARKER_SIZE},
                hovertemplate=(
                    f"{qubit}<br>Ljun=%{{x:.3f}} nH<br>"
                    "Re(Y) Circuit/Layout=%{y:.6g}<extra></extra>"
                ),
            )
        )
    fig.add_hline(
        y=1.0,
        line={
            "color": thesis_plot_config.PLOTLY_REFERENCE_LINE_COLOR,
            "dash": "dot",
            "width": thesis_plot_config.PLOTLY_REFERENCE_LINE_WIDTH,
        },
    )
    fig.update_xaxes(title_text="Per-junction L_jun [nH]")
    fig.update_yaxes(title_text="Re(Y) ratio: Circuit / Layout")
    _apply_common_layout(fig, title="On-Resonance Re(Y) Ratio")
    return fig


def write_plotly_artifacts(
    figures: Mapping[str, go.Figure],
    *,
    figure_dir: str | Path,
    write_html: bool = True,
    write_png: bool | None = None,
) -> list[Path]:
    """Write interactive HTML and optional PNG artifacts."""
    output_dir = Path(figure_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    if write_png is None:
        write_png = _plotly_png_export_available()
    written: list[Path] = []
    for stem, fig in figures.items():
        if write_html:
            html_path = output_dir / f"{stem}.html"
            fig.write_html(
                html_path,
                include_plotlyjs=thesis_plot_config.PLOTLY_HTML_INCLUDE_PLOTLYJS,
                config=thesis_plot_config.plotly_show_config(stem),
            )
            written.append(html_path)
        if write_png:
            png_path = output_dir / f"{stem}.png"
            fig.write_image(png_path, **thesis_plot_config.plotly_static_image_options(stem))
            written.append(png_path)
    return written


def _find_column(df: pd.DataFrame, token: str) -> str:
    for column in df.columns:
        if token in str(column):
            return str(column)
    raise ValueError(f"Could not find column containing {token!r}.")


def _first_value_column(df: pd.DataFrame, *, excluded: set[str]) -> str:
    for column in df.columns:
        if str(column) not in excluded:
            return str(column)
    raise ValueError("Could not find a value column.")


def _empty_dataframe(columns: Sequence[str]) -> pd.DataFrame:
    return pd.DataFrame(columns=list(columns))


def _build_c_eff_xy_fit_display_rows(
    fit_df: pd.DataFrame,
    *,
    dataset: str,
    source: str,
    l_jun_nh: float,
) -> pd.DataFrame:
    columns = [
        "dataset",
        "source",
        "l_jun_nh",
        "intercept_policy",
        "formula",
        "A_us_fF2",
        "B_us",
        "RMSE_us",
        "R2",
        "n_points",
        "qubits",
    ]
    required_columns = {
        "source",
        "l_jun_nh",
        "status",
        "coefficient_A_us_fF2",
        "intercept_B_us",
        "RMSE_us",
        "R2",
        "n_points",
        "qubits",
    }
    if fit_df.empty or not required_columns.issubset(fit_df.columns):
        return _empty_dataframe(columns)

    focus = fit_df[
        (fit_df["source"].astype(str) == str(source))
        & (fit_df["status"].astype(str) == "success")
        & np.isclose(
            pd.to_numeric(fit_df["l_jun_nh"], errors="coerce"),
            float(l_jun_nh),
        )
    ].copy()
    if focus.empty:
        return _empty_dataframe(columns)

    if "intercept_policy" in focus.columns:
        intercept_policy = focus["intercept_policy"].fillna("free").astype(str)
    else:
        intercept_policy = pd.Series("free", index=focus.index)
    formula = np.where(
        intercept_policy == "zero",
        "T1_us = A_us_fF2 / Ceff_xy_fF^2 (B_us fixed to 0)",
        "T1_us = A_us_fF2 / Ceff_xy_fF^2 + B_us",
    )
    return pd.DataFrame(
        {
            "dataset": dataset,
            "source": focus["source"].astype(str),
            "l_jun_nh": pd.to_numeric(focus["l_jun_nh"], errors="coerce"),
            "intercept_policy": intercept_policy,
            "formula": formula,
            "A_us_fF2": pd.to_numeric(
                focus["coefficient_A_us_fF2"],
                errors="coerce",
            ),
            "B_us": pd.to_numeric(focus["intercept_B_us"], errors="coerce"),
            "RMSE_us": pd.to_numeric(focus["RMSE_us"], errors="coerce"),
            "R2": pd.to_numeric(focus["R2"], errors="coerce"),
            "n_points": pd.to_numeric(focus["n_points"], errors="coerce"),
            "qubits": focus["qubits"].astype(str),
        }
    )[columns]


def _empty_resonance_dataframe() -> pd.DataFrame:
    return _empty_dataframe(["source", "qubit", "l_jun_nh", "frequency_ghz", "fallback", "crossed"])


def _estimate_initial_capacitance_pf(
    l_jun_nh: np.ndarray[Any, np.dtype[np.float64]],
    frequency_ghz: np.ndarray[Any, np.dtype[np.float64]],
    l_jun_effective_factor: float = thesis_plot_config.DEFAULT_L_JUN_EFFECTIVE_FACTOR,
) -> float:
    l_eff_h = np.maximum(float(l_jun_effective_factor) * l_jun_nh * NANO, 1e-24)
    omega = 2.0 * np.pi * frequency_ghz * 1e9
    c_pf = 1.0 / ((omega**2) * l_eff_h) / PICO
    finite = c_pf[np.isfinite(c_pf) & (c_pf > 0.0)]
    if len(finite) == 0:
        return 0.1
    return float(np.clip(np.median(finite), 1e-6, 10_000.0))


def _raw_xy_coupling_reference(capacitance_df: pd.DataFrame) -> dict[str, dict[str, float]]:
    references: dict[str, dict[str, float]] = {}
    formula_columns = {"c_g1_ff", "c_g2_ff", "c_xy1_ff", "c_xy2_ff"}
    use_formula = formula_columns.issubset(capacitance_df.columns)
    if not use_formula and "c_d_xy_ff" not in capacitance_df.columns:
        return references
    for row in capacitance_df.itertuples(index=False):
        if use_formula:
            signed = compute_floating_c_d_xy_ff(
                c_g1_ff=float(row.c_g1_ff),
                c_g2_ff=float(row.c_g2_ff),
                c_xy1_ff=float(row.c_xy1_ff),
                c_xy2_ff=float(row.c_xy2_ff),
            )
        else:
            signed = float(row.c_d_xy_ff)
        if not np.isfinite(signed):
            continue
        references[str(row.qubit)] = {
            "signed_fF": signed,
            "magnitude_fF": abs(signed),
        }
    return references


def _build_circuit_over_layout_frequency_ratio(
    frame: pd.DataFrame,
    *,
    ratio_kind: str,
) -> pd.DataFrame:
    if frame.empty:
        return _empty_dataframe(
            [
                "qubit",
                "l_jun_nh",
                "Circuit",
                "Layout",
                "ratio_circuit_over_layout",
                "ratio_percent_offset",
                "delta_circuit_minus_layout_mhz",
                "ratio_kind",
            ]
        )
    wide = frame.pivot_table(
        index=["qubit", "l_jun_nh"],
        columns="source",
        values="frequency_ghz",
        aggfunc="first",
    ).reset_index()
    wide.columns.name = None
    if "Circuit" not in wide.columns or "Layout" not in wide.columns:
        return _empty_dataframe(
            [
                "qubit",
                "l_jun_nh",
                "Circuit",
                "Layout",
                "ratio_circuit_over_layout",
                "ratio_percent_offset",
                "delta_circuit_minus_layout_mhz",
                "ratio_kind",
            ]
        )
    out = wide.dropna(subset=["Circuit", "Layout"]).copy()
    out = out[out["Layout"].astype(float) > 0.0]
    out["ratio_circuit_over_layout"] = out["Circuit"].astype(float) / out["Layout"].astype(float)
    out["ratio_percent_offset"] = (out["ratio_circuit_over_layout"] - 1.0) * 100.0
    out["delta_circuit_minus_layout_mhz"] = (
        out["Circuit"].astype(float) - out["Layout"].astype(float)
    ) * 1000.0
    out["ratio_kind"] = ratio_kind
    return out.sort_values(["qubit", "l_jun_nh"])


def _failed_c_eff_xy_l_jun_fit_row(
    *,
    source: str,
    l_jun_nh: float,
    fit_model: str,
    reason: str,
    n_points: int,
    intercept_policy: str = "free",
) -> dict[str, Any]:
    return {
        "source": source,
        "l_jun_nh": l_jun_nh,
        "status": "failed",
        "reason": reason,
        "fit_model": fit_model,
        "coefficient_A_us_fF2": math.nan,
        "intercept_B_us": math.nan,
        "intercept_policy": intercept_policy,
        "RMSE_us": math.nan,
        "R2": math.nan,
        "n_points": n_points,
        "qubits": "",
    }


def _fit_inverse_square_with_intercept(
    x: np.ndarray[Any, np.dtype[np.float64]],
    y: np.ndarray[Any, np.dtype[np.float64]],
) -> dict[str, float]:
    basis = 1.0 / np.maximum(x**2, 1e-24)
    design = np.column_stack([basis, np.ones_like(basis)])
    coefficient, intercept = np.linalg.lstsq(design, y, rcond=None)[0]
    fitted = _inverse_square_with_intercept(x, float(coefficient), float(intercept))
    residual = y - fitted
    rmse = float(np.sqrt(np.mean(residual**2)))
    ss_res = float(np.sum(residual**2))
    ss_tot = float(np.sum((y - np.mean(y)) ** 2))
    r2 = math.nan if ss_tot == 0.0 else 1.0 - ss_res / ss_tot
    return {
        "coefficient": float(coefficient),
        "intercept": float(intercept),
        "rmse": rmse,
        "r2": r2,
    }


def _fit_inverse_square_zero_intercept(
    x: np.ndarray[Any, np.dtype[np.float64]],
    y: np.ndarray[Any, np.dtype[np.float64]],
) -> dict[str, float]:
    basis = 1.0 / np.maximum(x**2, 1e-24)
    coefficient = float(np.dot(basis, y) / np.dot(basis, basis))
    fitted = coefficient * basis
    residual = y - fitted
    rmse = float(np.sqrt(np.mean(residual**2)))
    ss_res = float(np.sum(residual**2))
    ss_tot = float(np.sum((y - np.mean(y)) ** 2))
    r2 = math.nan if ss_tot == 0.0 else 1.0 - ss_res / ss_tot
    return {
        "coefficient": coefficient,
        "intercept": 0.0,
        "rmse": rmse,
        "r2": r2,
    }


def _inverse_square_with_intercept(
    x: np.ndarray[Any, np.dtype[np.float64]] | Sequence[float],
    coefficient_us_f_f2: float,
    intercept_us: float,
) -> np.ndarray[Any, np.dtype[np.float64]]:
    values = np.asarray(x, dtype=np.float64)
    return coefficient_us_f_f2 / np.maximum(values**2, 1e-24) + intercept_us


def _select_c_eff_xy_l_jun_fit(
    trend_fit_df: pd.DataFrame,
    *,
    source: str,
    l_jun_nh: float,
) -> pd.Series | None:
    if trend_fit_df.empty:
        return None
    rows = trend_fit_df[
        (trend_fit_df["status"].astype(str) == "success")
        & (trend_fit_df["source"].astype(str) == str(source))
        & np.isclose(trend_fit_df["l_jun_nh"].astype(float), float(l_jun_nh))
    ]
    if rows.empty:
        return None
    return rows.iloc[0]


def _format_fit_value(value: object) -> str:
    numeric = float(value)
    if not np.isfinite(numeric):
        return "nan"
    return f"{numeric:.3f}"


def _format_r2_value(value: object) -> str:
    numeric = float(value)
    if not np.isfinite(numeric):
        return "nan"
    return f"{numeric:.4f}"


def _format_c_eff_xy_fit_label(prefix: str, fit: pd.Series) -> str:
    return (
        f"{prefix}: "
        f"A={_format_fit_value(fit['coefficient_A_us_fF2'])}, "
        f"B={_format_fit_value(fit['intercept_B_us'])}, "
        f"RMSE={_format_fit_value(fit['RMSE_us'])}, "
        f"R2={_format_r2_value(fit['R2'])}"
    )


def _add_c_eff_xy_fit_trace(
    fig: go.Figure,
    *,
    fit: pd.Series,
    focus: pd.DataFrame,
    name_prefix: str,
    line_color: str,
    line_dash: str,
) -> None:
    x_min = float(focus["C_eff_xy_signed_fF"].min())
    x_max = float(focus["C_eff_xy_signed_fF"].max())
    x_line = np.linspace(x_min, x_max, 240)
    y_line = _inverse_square_with_intercept(
        x_line,
        float(fit["coefficient_A_us_fF2"]),
        float(fit["intercept_B_us"]),
    )
    label = _format_c_eff_xy_fit_label(name_prefix, fit)
    fig.add_trace(
        go.Scatter(
            x=x_line,
            y=y_line,
            mode="lines",
            name=label,
            line={
                "color": line_color,
                "dash": line_dash,
                "width": thesis_plot_config.PLOTLY_LINE_WIDTH,
            },
            hovertemplate=(
                f"{name_prefix}<br>"
                "Ceff,xy=%{x:.6f} fF<br>"
                "fit T1=%{y:.6g} us<br>"
                f"{label}<extra></extra>"
            ),
        )
    )

def _row_value(row: object, preferred: str, fallback: str) -> object:
    if hasattr(row, preferred):
        return getattr(row, preferred)
    return getattr(row, fallback)


def _select_focus_trace(
    circuit_trace_df: pd.DataFrame,
    focus_qubit: str,
    focus_l_jun_nh: float,
) -> pd.DataFrame:
    focus = circuit_trace_df[
        (circuit_trace_df["qubit"].astype(str) == str(focus_qubit))
        & np.isclose(circuit_trace_df["l_jun_nh"].astype(float), float(focus_l_jun_nh))
    ].copy()
    if focus.empty:
        raise ValueError(f"Missing focus trace for {focus_qubit}, L_jun={focus_l_jun_nh} nH.")
    return focus.sort_values("frequency_ghz")


def _select_focus_observable(
    circuit_observables_df: pd.DataFrame,
    focus_qubit: str,
    focus_l_jun_nh: float,
) -> pd.Series:
    focus = circuit_observables_df[
        (circuit_observables_df["qubit"].astype(str) == str(focus_qubit))
        & np.isclose(circuit_observables_df["l_jun_nh"].astype(float), float(focus_l_jun_nh))
    ].copy()
    if focus.empty:
        raise ValueError(f"Missing focus observable for {focus_qubit}, L_jun={focus_l_jun_nh} nH.")
    return focus.iloc[0]


def _downsample_line(df: pd.DataFrame, max_points: int) -> pd.DataFrame:
    if max_points <= 0 or len(df) <= max_points:
        return df
    indices = np.linspace(0, len(df) - 1, max_points, dtype=int)
    return df.iloc[np.unique(indices)].copy()


def _apply_common_layout(fig: go.Figure, *, title: str) -> None:
    axis_kwargs = thesis_plot_config.plotly_publication_axis_kwargs()
    fig.update_layout(**thesis_plot_config.plotly_publication_layout_kwargs(title))
    fig.update_xaxes(**axis_kwargs["x"])
    fig.update_yaxes(**axis_kwargs["y"])
    fig.update_annotations(**thesis_plot_config.plotly_publication_annotation_kwargs())


def _plotly_png_export_available() -> bool:
    try:
        import kaleido  # noqa: F401
    except Exception:
        return False
    return True


def _is_finite_number(value: object) -> bool:
    try:
        return bool(np.isfinite(float(value)))
    except Exception:
        return False
