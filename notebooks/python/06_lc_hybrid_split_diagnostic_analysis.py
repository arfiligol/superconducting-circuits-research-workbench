# ---
# jupyter:
#   jupytext:
#     cell_metadata_filter: -all
#     formats: ipynb,py:percent
#     text_representation:
#       extension: .py
#       format_name: percent
#       format_version: '1.3'
#       jupytext_version: 1.19.4
# ---

# %% [markdown]
# # 06 LC Hybrid Split Diagnostic
#
# This notebook analyzes `06_lc_hybrid_split_diagnostic_sweep.jl`.
#
# For each compensated `lc` point it extracts:
#
# - filter loaded bare frequency from a real `C_ext` sweep;
# - readout bare frequency from a weak-probe extrapolation;
# - intrinsic-pair Z21 peaks and notch;
# - corrected hybrid split after applying the measured filter loading shift;
# - half of that corrected hybrid split, reported only as a diagnostic.
#
# Canonical knowledge:
#
# - [Multiconductor RLGC Matrices: Basis, Modes, and Physical Meaning](https://github.com/arfiligol/SCQ_Design/blob/main/docs/knowledge/transmission-lines/multiconductor-rlgc-matrix-semantics.qmd)
# - [Resonator Length Correction Loop](https://github.com/arfiligol/SCQ_Design/blob/main/docs/knowledge/transmission-lines/resonator-length-correction-loop.qmd)
# - [Loaded-Bare Readout / Filter References](https://github.com/arfiligol/SCQ_Design/blob/main/docs/knowledge/readout/loaded-bare-readout-filter-references.qmd)
# - [Bare vs Hybridized Readout / Filter Modes](https://github.com/arfiligol/SCQ_Design/blob/main/docs/knowledge/readout/bare-vs-hybridized-readout-filter-modes.qmd)
# - [Readout-Filter S21 J Fit](https://github.com/arfiligol/SCQ_Design/blob/main/docs/knowledge/readout/readout-filter-s21-j-fit.qmd)
# - [Harmonic Balance: Periodic Steady State and Mode Semantics](https://github.com/arfiligol/SCQ_Design/blob/main/docs/knowledge/numerical-methods/harmonic-balance-periodic-steady-state.qmd)
# - [Port Reference Impedance Semantics](https://github.com/arfiligol/SCQ_Design/blob/main/docs/knowledge/simulation/port-reference-impedance-semantics.qmd)
# - [Port-Termination Compensation (PTC)](https://github.com/arfiligol/SCQ_Design/blob/main/docs/knowledge/simulation/port-termination-compensation.qmd)
#
# HB operating-point, mode, and convergence semantics are owned by the Harmonic
# Balance page above.
#
# Current Q2D matrix inputs are exploration-only until they pass the canonical
# artifact eligibility gate.

# %%
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from d3_design_config import load_d3_design_config, variant_suffix
from plotly.subplots import make_subplots
from scipy.signal import find_peaks

try:
    from IPython.display import display as ipython_display
except ImportError:  # pragma: no cover
    ipython_display = None


ROOT = Path(
    "/home/ili/Githubs/SCQ_Design/orpen_sc_pdk/build/simulation/circuit/"
    "intrinsic_purcell_filter/d3_intrinsic_purcell_filter_design"
)
D3_CONFIG = load_d3_design_config()
VARIANT = str(D3_CONFIG["active_design_variant_id"])
SUFFIX = variant_suffix(VARIANT)
SWEEP_ROOT = ROOT / f"lc_hybrid_split_diagnostic{SUFFIX}"
PLOT_DIR = ROOT / "plots" / VARIANT
CASE_JSON = ROOT.parent / "orpen_q2d_rlgc_cases.json"
DESIGN_LENGTHS_CSV = ROOT / "design_inputs" / str(D3_CONFIG["design_csv_filename"])

SETUP_CSV = SWEEP_ROOT / "d3_lc_hybrid_split_diagnostic_setup.csv"
DESIGNS_CSV = SWEEP_ROOT / "d3_lc_hybrid_split_diagnostic_designs.csv"
FILTER_MANIFEST_CSV = SWEEP_ROOT / "d3_controlled_filter_loading_manifest.csv"
READOUT_MANIFEST_CSV = SWEEP_ROOT / "d3_controlled_readout_probe_manifest.csv"
Z21_MANIFEST_CSV = SWEEP_ROOT / "d3_controlled_intrinsic_z21_manifest.csv"

FILTER_RESULTS_CSV = SWEEP_ROOT / "d3_controlled_filter_loading_results.csv"
READOUT_RESULTS_CSV = SWEEP_ROOT / "d3_controlled_readout_probe_results.csv"
SUMMARY_CSV = SWEEP_ROOT / "d3_lc_hybrid_split_diagnostic_summary.csv"
HYBRID_SHIFT_FIT_CSV = SWEEP_ROOT / "d3_controlled_hybrid_shift_linear_fits.csv"
CORRECTED_DESIGNS_CSV = SWEEP_ROOT / "d3_lc_hybrid_split_diagnostic_corrected_design_inputs.csv"

TARGET_NOTCH_GHZ = 4.5
Z21_PAIR_WINDOW_GHZ = 0.8
LOCK_TOLERANCE_MHZ = 1.0
GHz = 1.0e9
UM = 1.0e-6

pd.set_option("display.max_columns", 80)
pd.set_option("display.width", 180)


# %% [markdown]
# ## Helpers


# %%
def require_file(path: Path) -> Path:
    if not path.is_file():
        raise FileNotFoundError(f"required file is missing: {path}")
    return path


def display_table(frame: pd.DataFrame, *, precision: int = 4) -> pd.DataFrame:
    table = frame.copy()
    numeric_columns = table.select_dtypes(include=[np.number]).columns
    table.loc[:, numeric_columns] = table.loc[:, numeric_columns].round(precision)
    if ipython_display is not None:
        ipython_display(table)
    else:
        print(table.to_string(index=False))
    return table


def write_plot(fig: go.Figure, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    if ipython_display is not None:
        ipython_display(fig)
    fig.write_image(path, scale=1)
    return path


def complex_column(frame: pd.DataFrame, prefix: str) -> np.ndarray:
    return frame[f"{prefix}_re"].to_numpy() + 1j * frame[f"{prefix}_im"].to_numpy()


def quadratic_minimum(x: np.ndarray, y: np.ndarray, index: int | None = None) -> float:
    if index is None:
        index = int(np.argmin(y))
    if index == 0 or index == len(y) - 1:
        return float(x[index])
    xs = x[index - 1 : index + 2]
    ys = y[index - 1 : index + 2]
    a, b, _ = np.polyfit(xs, ys, 2)
    if abs(a) < np.finfo(float).eps:
        return float(x[index])
    candidate = -b / (2.0 * a)
    return float(candidate if xs[0] <= candidate <= xs[-1] else x[index])


def extract_s21_dip_ghz(trace_csv: str, *, center_ghz: float, half_width_ghz: float) -> float:
    frame = pd.read_csv(require_file(Path(trace_csv)))
    frequency = frame["frequency_ghz"].to_numpy()
    s21_abs = np.abs(complex_column(frame, "s21"))
    mask = np.abs(frequency - center_ghz) <= half_width_ghz
    if not np.any(mask):
        raise ValueError(f"empty S21 dip window around {center_ghz} GHz")
    local_frequency = frequency[mask]
    local_s21_abs = s21_abs[mask]
    minima, _ = find_peaks(-local_s21_abs, distance=10)
    if len(minima) == 0:
        return quadratic_minimum(local_frequency, local_s21_abs)
    index = int(minima[np.argmin(local_s21_abs[minima])])
    return quadratic_minimum(local_frequency, local_s21_abs, index)


def linear_fit(x: np.ndarray, y: np.ndarray) -> tuple[float, float, float]:
    slope, intercept = np.polyfit(x, y, 1)
    fitted = slope * x + intercept
    sse = float(np.sum((fitted - y) ** 2))
    centered = float(np.sum((y - np.mean(y)) ** 2))
    r2 = float(1.0 - sse / centered) if centered > 0.0 else 1.0
    return float(slope), float(intercept), r2


def selected_single_velocity_m_per_s(case_json: Path, case_id: str) -> float:
    import json

    payload = json.loads(require_file(case_json).read_text())
    for case in payload["cases"]:
        if case["id"] == case_id:
            single = case["single"]
            return float(1.0 / np.sqrt(single["l_per_m_h"] * single["c_per_m_f"]))
    raise KeyError(f"case_id={case_id!r} not found in {case_json}")


def open_length_delta_um(target_ghz: float, measured_ghz: float, velocity_m_per_s: float) -> float:
    return (
        velocity_m_per_s * (1.0 / (4.0 * target_ghz * GHz) - 1.0 / (4.0 * measured_ghz * GHz)) / UM
    )


def common_short_delta_um(target_ghz: float, measured_ghz: float, velocity_m_per_s: float) -> float:
    return (
        0.5
        * velocity_m_per_s
        * (1.0 / (4.0 * target_ghz * GHz) - 1.0 / (4.0 * measured_ghz * GHz))
        / UM
    )


def z21_observable(frame: pd.DataFrame) -> tuple[np.ndarray, str]:
    if "z21_ptc_abs_im_ohm" not in frame.columns:
        raise KeyError("PTC Z21 column z21_ptc_abs_im_ohm is required")
    return frame["z21_ptc_abs_im_ohm"].to_numpy(), "|Im(Z21 PTC)|"


def window_minimum(
    frequency_ghz: np.ndarray, values: np.ndarray, center_ghz: float, half_width_ghz: float
) -> tuple[float, float]:
    mask = np.abs(frequency_ghz - center_ghz) <= half_width_ghz
    if not np.any(mask):
        raise ValueError(f"empty window around {center_ghz} GHz")
    local_frequency = frequency_ghz[mask]
    local_values = values[mask]
    index = int(np.argmin(local_values))
    return float(local_frequency[index]), float(local_values[index])


def local_peaks(frequency_ghz: np.ndarray, values: np.ndarray, *, top_n: int = 6) -> list[float]:
    span = float(np.max(values) - np.min(values))
    prominence = max(span * 0.002, np.finfo(float).eps)
    step_mhz = float(np.median(np.diff(frequency_ghz)) * 1000.0)
    distance = max(1, round(5.0 / step_mhz))
    indexes, props = find_peaks(values, prominence=prominence, distance=distance)
    if len(indexes) == 0:
        return []
    order = np.argsort(props["prominences"])[::-1]
    return sorted(float(frequency_ghz[indexes[item]]) for item in order[:top_n])


def summarize_z21(row: object) -> dict[str, object]:
    frame = pd.read_csv(require_file(Path(row.trace_csv)))
    frequency = frame["frequency_ghz"].to_numpy()
    z21, label = z21_observable(frame)
    notch_ghz, notch_abs = window_minimum(frequency, z21, TARGET_NOTCH_GHZ, 0.45)
    peaks = local_peaks(frequency, z21)
    slot_peaks = [
        peak for peak in peaks if abs(peak - float(row.slot_target_ghz)) <= Z21_PAIR_WINDOW_GHZ
    ]
    low = high = np.nan
    if len(slot_peaks) >= 2:
        low, high = sorted(
            sorted(slot_peaks, key=lambda item: abs(item - float(row.slot_target_ghz)))[:2]
        )
    return {
        "sweep_id": row.sweep_id,
        "lc_um": float(row.lc_um),
        "notch_ghz": notch_ghz,
        "notch_error_mhz": 1000.0 * (notch_ghz - TARGET_NOTCH_GHZ),
        "notch_abs_ohm": notch_abs,
        "z21_low_peak_ghz": low,
        "z21_high_peak_ghz": high,
        "mode_count_ok": np.isfinite(low) and np.isfinite(high),
        "z21_observable": label,
        "z21_peak_candidates_ghz": ", ".join(f"{peak:.4f}" for peak in peaks),
        "trace_csv": row.trace_csv,
    }


# %% [markdown]
# ## Read Pluto Outputs

# %%
setup = pd.read_csv(require_file(SETUP_CSV))
designs = pd.read_csv(require_file(DESIGNS_CSV))
filter_manifest = pd.read_csv(require_file(FILTER_MANIFEST_CSV))
readout_manifest = pd.read_csv(require_file(READOUT_MANIFEST_CSV))
z21_manifest = pd.read_csv(require_file(Z21_MANIFEST_CSV))

_ = display_table(setup, precision=4)
_ = display_table(designs, precision=3)


# %% [markdown]
# ## Loaded Bare Frequency Extraction

# %%
filter_rows: list[dict[str, object]] = []
for row in filter_manifest.itertuples(index=False):
    filter_rows.append(
        {
            "sweep_id": row.sweep_id,
            "lc_um": float(row.lc_um),
            "filter_to_line_capacitance_fF": float(row.filter_to_line_capacitance_fF),
            "selected_filter_to_line_capacitance_fF": float(
                row.selected_filter_to_line_capacitance_fF
            ),
            "filter_frequency_ghz": extract_s21_dip_ghz(
                row.trace_csv,
                center_ghz=float(row.slot_target_ghz),
                half_width_ghz=0.70,
            ),
            "trace_csv": row.trace_csv,
        }
    )
filter_results = pd.DataFrame(filter_rows).sort_values(["lc_um", "filter_to_line_capacitance_fF"])

filter_fit_rows: list[dict[str, object]] = []
for lc_um, group in filter_results.groupby("lc_um"):
    x = group["filter_to_line_capacitance_fF"].to_numpy()
    y = group["filter_frequency_ghz"].to_numpy()
    slope_ghz_per_ff, intercept_ghz, r2 = linear_fit(x, y)
    selected_cext = float(group["selected_filter_to_line_capacitance_fF"].iloc[0])
    loaded_ghz = intercept_ghz + slope_ghz_per_ff * selected_cext
    filter_fit_rows.append(
        {
            "lc_um": float(lc_um),
            "filter_unloaded_intercept_ghz": intercept_ghz,
            "filter_loading_slope_mhz_per_fF": 1000.0 * slope_ghz_per_ff,
            "selected_filter_to_line_capacitance_fF": selected_cext,
            "filter_loaded_bare_ghz": loaded_ghz,
            "filter_loading_shift_mhz": 1000.0 * (loaded_ghz - intercept_ghz),
            "filter_loading_r2": r2,
        }
    )
filter_fits = pd.DataFrame(filter_fit_rows).sort_values("lc_um")

readout_rows: list[dict[str, object]] = []
for row in readout_manifest.itertuples(index=False):
    readout_rows.append(
        {
            "sweep_id": row.sweep_id,
            "lc_um": float(row.lc_um),
            "readout_probe_capacitance_fF": float(row.readout_probe_capacitance_fF),
            "readout_frequency_ghz": extract_s21_dip_ghz(
                row.trace_csv,
                center_ghz=float(row.slot_target_ghz),
                half_width_ghz=0.35,
            ),
            "trace_csv": row.trace_csv,
        }
    )
readout_results = pd.DataFrame(readout_rows).sort_values(["lc_um", "readout_probe_capacitance_fF"])

readout_fit_rows: list[dict[str, object]] = []
for lc_um, group in readout_results.groupby("lc_um"):
    x = group["readout_probe_capacitance_fF"].to_numpy()
    y = group["readout_frequency_ghz"].to_numpy()
    slope_ghz_per_ff, intercept_ghz, r2 = linear_fit(x, y)
    readout_fit_rows.append(
        {
            "lc_um": float(lc_um),
            "readout_bare_ghz": intercept_ghz,
            "readout_probe_slope_mhz_per_fF": 1000.0 * slope_ghz_per_ff,
            "readout_probe_r2": r2,
        }
    )
readout_fits = pd.DataFrame(readout_fit_rows).sort_values("lc_um")

filter_results.to_csv(FILTER_RESULTS_CSV, index=False)
readout_results.to_csv(READOUT_RESULTS_CSV, index=False)

_ = display_table(filter_fits, precision=6)
_ = display_table(readout_fits, precision=6)


# %% [markdown]
# ## Z21 And Half Corrected Hybrid Split Diagnostic

# %%
z21_summary = pd.DataFrame(summarize_z21(row) for row in z21_manifest.itertuples(index=False))
summary = (
    designs.merge(filter_fits, on="lc_um")
    .merge(readout_fits, on="lc_um")
    .merge(z21_summary, on=["sweep_id", "lc_um"])
    .sort_values("lc_um")
    .reset_index(drop=True)
)
summary["z21_high_after_cext_shift_ghz"] = (
    summary["z21_high_peak_ghz"] + summary["filter_loading_shift_mhz"] / 1000.0
)
summary["bare_detuning_mhz"] = 1000.0 * (
    summary["filter_loaded_bare_ghz"] - summary["readout_bare_ghz"]
)
summary["hybrid_split_mhz"] = 1000.0 * (
    summary["z21_high_after_cext_shift_ghz"] - summary["z21_low_peak_ghz"]
)
summary["readout_shift_mhz"] = 1000.0 * (summary["z21_low_peak_ghz"] - summary["readout_bare_ghz"])
summary["filter_shift_mhz"] = 1000.0 * (
    summary["z21_high_after_cext_shift_ghz"] - summary["filter_loaded_bare_ghz"]
)
summary["half_hybrid_split_mhz"] = 0.5 * summary["hybrid_split_mhz"]
summary["frequency_control_span_mhz"] = 1000.0 * (
    summary[["filter_loaded_bare_ghz", "readout_bare_ghz"]].max(axis=1)
    - summary[["filter_loaded_bare_ghz", "readout_bare_ghz"]].min(axis=1)
)

summary.to_csv(SUMMARY_CSV, index=False)

hybrid_shift_fit_rows: list[dict[str, object]] = []
for label, column in [
    ("readout", "readout_shift_mhz"),
    ("filter", "filter_shift_mhz"),
]:
    slope, intercept, r2 = linear_fit(summary["lc_um"].to_numpy(), summary[column].to_numpy())
    hybrid_shift_fit_rows.append(
        {
            "mode": label,
            "slope_mhz_per_um": slope,
            "intercept_mhz": intercept,
            "zero_crossing_lc_um": -intercept / slope,
            "r2": r2,
        }
    )
hybrid_shift_fits = pd.DataFrame(hybrid_shift_fit_rows)
hybrid_shift_fits.to_csv(HYBRID_SHIFT_FIT_CSV, index=False)

_ = display_table(
    summary[
        [
            "lc_um",
            "lr_short_um",
            "lr_open_um",
            "lp_short_um",
            "lp_open_um",
            "readout_bare_ghz",
            "filter_loaded_bare_ghz",
            "bare_detuning_mhz",
            "notch_ghz",
            "z21_low_peak_ghz",
            "z21_high_peak_ghz",
            "z21_high_after_cext_shift_ghz",
            "readout_shift_mhz",
            "filter_shift_mhz",
            "hybrid_split_mhz",
            "half_hybrid_split_mhz",
        ]
    ],
    precision=4,
)
_ = display_table(hybrid_shift_fits, precision=6)


# %% [markdown]
# ## Length Correction For Next Controlled Run


# %%
def build_corrected_design_inputs() -> pd.DataFrame:
    base_designs = pd.read_csv(require_file(DESIGN_LENGTHS_CSV))
    template = base_designs[
        np.isclose(base_designs["slot_target_ghz"], float(setup["slot_target_ghz"].iloc[0]))
    ].iloc[0]
    velocity = selected_single_velocity_m_per_s(CASE_JSON, str(setup["case_id"].iloc[0]))
    target_readout_ghz = float(setup["slot_target_ghz"].iloc[0])
    target_filter_ghz = float(setup["slot_target_ghz"].iloc[0])
    frequency_errors_mhz = pd.concat(
        [
            1000.0 * (summary["readout_bare_ghz"] - target_readout_ghz).abs(),
            1000.0 * (summary["filter_loaded_bare_ghz"] - target_filter_ghz).abs(),
            summary["notch_error_mhz"].abs(),
        ]
    )
    freeze_current_lengths = float(frequency_errors_mhz.max()) <= LOCK_TOLERANCE_MHZ
    rows: list[pd.Series] = []
    for row in summary.itertuples(index=False):
        row_values = row._asdict()
        selected_cext = row_values.get(
            "selected_filter_to_line_capacitance_fF",
            row_values.get(
                "selected_filter_to_line_capacitance_fF_y",
                row_values["selected_filter_to_line_capacitance_fF_x"],
            ),
        )
        corrected = template.copy()
        short_delta = (
            0.0
            if freeze_current_lengths
            else common_short_delta_um(TARGET_NOTCH_GHZ, float(row.notch_ghz), velocity)
        )
        readout_total_delta = (
            0.0
            if freeze_current_lengths
            else open_length_delta_um(target_readout_ghz, float(row.readout_bare_ghz), velocity)
        )
        filter_total_delta = (
            0.0
            if freeze_current_lengths
            else open_length_delta_um(
                target_filter_ghz, float(row.filter_loaded_bare_ghz), velocity
            )
        )
        lr_short_um = float(row.lr_short_um) + short_delta
        lp_short_um = float(row.lp_short_um) + short_delta
        lr_open_um = float(row.lr_open_um) + readout_total_delta - short_delta
        lp_open_um = float(row.lp_open_um) + filter_total_delta - short_delta
        corrected["id"] = f"controlled_lc{row.lc_um:g}_corrected"
        corrected["case_id"] = str(setup["case_id"].iloc[0])
        corrected["target_set_id"] = "d3_lc_hybrid_split_diagnostic"
        corrected["target_set_name"] = "D3 controlled lc loaded-bare zero-detuning diagnostic sweep"
        corrected["slot_target_ghz"] = float(template["slot_target_ghz"])
        corrected["notch_target_ghz"] = TARGET_NOTCH_GHZ
        corrected["lc_um"] = float(row.lc_um)
        corrected["lr_short_um"] = lr_short_um
        corrected["lp_short_um"] = lp_short_um
        corrected["lr_open_um"] = lr_open_um
        corrected["lp_open_um"] = lp_open_um
        corrected["lr_total_um"] = lr_short_um + float(row.lc_um) + lr_open_um
        corrected["lp_total_um"] = lp_short_um + float(row.lc_um) + lp_open_um
        corrected["notch_length_um"] = lr_short_um + float(row.lc_um) + lp_short_um
        corrected["filter_to_line_capacitance_fF"] = float(selected_cext)
        corrected["fr_est_ghz"] = target_readout_ghz
        corrected["fp_est_ghz"] = target_filter_ghz
        corrected["fn_est_ghz"] = TARGET_NOTCH_GHZ
        corrected["analytic_score"] = 0.0
        rows.append(corrected)
    corrected_designs = pd.DataFrame(rows)
    length_columns = ["lr_short_um", "lr_open_um", "lp_short_um", "lp_open_um", "lc_um"]
    if not (corrected_designs[length_columns] > 0.0).all().all():
        raise ValueError("controlled length correction produced a non-positive section")
    return corrected_designs


corrected_design_inputs = build_corrected_design_inputs()
corrected_design_inputs.to_csv(CORRECTED_DESIGNS_CSV, index=False)
_ = display_table(
    corrected_design_inputs[
        [
            "lc_um",
            "lr_short_um",
            "lr_open_um",
            "lp_short_um",
            "lp_open_um",
            "lr_total_um",
            "lp_total_um",
            "filter_to_line_capacitance_fF",
        ]
    ],
    precision=3,
)


# %% [markdown]
# ## Plots


# %%
def plot_bare_control() -> Path:
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=summary["lc_um"],
            y=summary["readout_bare_ghz"],
            mode="markers+lines",
            name="readout loaded bare",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=summary["lc_um"],
            y=summary["filter_loaded_bare_ghz"],
            mode="markers+lines",
            name="filter loaded bare",
        )
    )
    fig.update_layout(
        title="Controlled lc sweep: measured loaded bare frequencies",
        xaxis_title="MTL coupling length lc (um)",
        yaxis_title="Frequency (GHz)",
    )
    return write_plot(fig, PLOT_DIR / "d3_controlled_lc_bare_frequency_check.png")


def plot_half_hybrid_split_and_notch() -> Path:
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    fig.add_trace(
        go.Scatter(
            x=summary["lc_um"],
            y=summary["half_hybrid_split_mhz"],
            mode="markers+lines",
            name="half corrected hybrid split (diagnostic)",
        ),
        secondary_y=False,
    )
    fig.add_trace(
        go.Scatter(
            x=summary["lc_um"], y=summary["notch_ghz"], mode="markers+lines", name="Z21 notch"
        ),
        secondary_y=True,
    )
    fig.add_hline(y=TARGET_NOTCH_GHZ, line_dash="dot", secondary_y=True)
    fig.update_layout(title="Controlled lc sweep: half corrected hybrid split diagnostic and notch")
    fig.update_xaxes(title_text="MTL coupling length lc (um)")
    fig.update_yaxes(title_text="Half corrected hybrid split (MHz)", secondary_y=False)
    fig.update_yaxes(title_text="Notch frequency (GHz)", secondary_y=True)
    return write_plot(fig, PLOT_DIR / "d3_lc_hybrid_split_diagnostic_trend.png")


def plot_hybrid_shifts() -> Path:
    fig = go.Figure()
    colors = {"readout": "#636EFA", "filter": "#EF553B"}
    columns = {"readout": "readout_shift_mhz", "filter": "filter_shift_mhz"}
    x_line = np.linspace(0.0, float(summary["lc_um"].max()), 200)
    for label, column in columns.items():
        fit = hybrid_shift_fits.set_index("mode").loc[label]
        fig.add_trace(
            go.Scatter(
                x=summary["lc_um"],
                y=summary[column],
                mode="markers",
                marker={"color": colors[label], "size": 8},
                name=f"{label} data",
            )
        )
        fig.add_trace(
            go.Scatter(
                x=x_line,
                y=fit.slope_mhz_per_um * x_line + fit.intercept_mhz,
                mode="lines",
                line={"color": colors[label], "dash": "dash"},
                name=(
                    f"{label} fit: y={fit.slope_mhz_per_um:.4f}x"
                    f"{fit.intercept_mhz:+.3f}, R2={fit.r2:.5f}"
                ),
            )
        )
    fig.add_hline(y=0.0, line_dash="dot", line_color="#111111")
    fig.update_layout(
        title="Controlled lc sweep: hybridized shifts linear fit",
        xaxis_title="MTL coupling length lc (um)",
        yaxis_title="Hybridized shift (MHz)",
    )
    return write_plot(fig, PLOT_DIR / "d3_controlled_lc_hybrid_shifts.png")


def plot_z21_traces() -> Path:
    fig = go.Figure()
    for row in z21_summary.sort_values("lc_um").itertuples(index=False):
        frame = pd.read_csv(require_file(Path(row.trace_csv)))
        z21, _label = z21_observable(frame)
        fig.add_trace(
            go.Scatter(
                x=frame["frequency_ghz"],
                y=z21,
                mode="markers",
                marker={"size": 3},
                name=f"lc {row.lc_um:g} um",
            )
        )
    fig.add_vline(x=TARGET_NOTCH_GHZ, line_dash="dot", line_color="#111111")
    fig.update_layout(
        title="Controlled lc sweep: intrinsic |Im(Z21 PTC)| traces",
        xaxis_title="Frequency (GHz)",
        yaxis_title="|Im(Z21 PTC)| (ohm)",
        yaxis={"type": "log"},
    )
    return write_plot(fig, PLOT_DIR / "d3_controlled_lc_z21_traces.png")


plot_paths = [
    plot_bare_control(),
    plot_half_hybrid_split_and_notch(),
    plot_hybrid_shifts(),
    plot_z21_traces(),
]
_ = display_table(pd.DataFrame({"plot": [str(path) for path in plot_paths]}))


# %% [markdown]
# ## Output Summary

# %%
print(f"wrote {FILTER_RESULTS_CSV}")
print(f"wrote {READOUT_RESULTS_CSV}")
print(f"wrote {SUMMARY_CSV}")

assert not summary.empty
assert summary["mode_count_ok"].all()
assert summary["filter_loading_r2"].gt(0.99).all()
assert summary["readout_probe_r2"].gt(0.99).all()
