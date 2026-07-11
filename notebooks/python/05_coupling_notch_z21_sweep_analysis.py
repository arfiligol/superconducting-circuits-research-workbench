# %% [markdown]
# # 05 Coupling And Notch Z21 Sweep Analysis
#
# This notebook reads the Pluto `05` intrinsic-pair PTC Z21 sweep. PTC Z21 is
# used as notch and transfer-peak evidence. Half of its raw peak split is only
# a geometry-seed screening heuristic; it is not `$J$` extraction, promotion
# evidence, or a substitute for the complex-S21 fit.
#
# Canonical knowledge:
#
# - [Multiconductor RLGC Matrices: Basis, Modes, and Physical Meaning](https://github.com/arfiligol/SCQ_Design/blob/main/docs/knowledge/transmission-lines/multiconductor-rlgc-matrix-semantics.qmd)
# - [Bare vs Hybridized Readout / Filter Modes](https://github.com/arfiligol/SCQ_Design/blob/main/docs/knowledge/readout/bare-vs-hybridized-readout-filter-modes.qmd)
# - [Readout-Filter S21 J Fit](https://github.com/arfiligol/SCQ_Design/blob/main/docs/knowledge/readout/readout-filter-s21-j-fit.qmd)
# - [Harmonic Balance: Periodic Steady State and Mode Semantics](https://github.com/arfiligol/SCQ_Design/blob/main/docs/knowledge/numerical-methods/harmonic-balance-periodic-steady-state.qmd)
# - [Port Reference Impedance Semantics](https://github.com/arfiligol/SCQ_Design/blob/main/docs/knowledge/simulation/port-reference-impedance-semantics.qmd)
# - [Port-Termination Compensation (PTC)](https://github.com/arfiligol/SCQ_Design/blob/main/docs/knowledge/simulation/port-termination-compensation.qmd)
#
# Current Q2D matrix inputs are exploration-only until they pass the canonical
# artifact eligibility gate.

# %%
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from scipy.signal import find_peaks

from d3_design_config import load_d3_design_config, variant_suffix

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
SWEEP_ROOT = ROOT / f"coupling_notch_z21_sweep{SUFFIX}"
PLOT_DIR = ROOT / "plots" / VARIANT

SETUP_CSV = SWEEP_ROOT / "d3_coupling_notch_z21_sweep_setup.csv"
MANIFEST_CSV = SWEEP_ROOT / "d3_coupling_notch_z21_sweep_manifest.csv"
SUMMARY_CSV = SWEEP_ROOT / "d3_coupling_notch_z21_sweep_summary.csv"
RANKED_SEED_CANDIDATES_CSV = SWEEP_ROOT / "d3_coupling_notch_z21_ranked_candidates.csv"
SCREENING_CANDIDATES_CSV = SWEEP_ROOT / "d3_coupling_notch_z21_validated_candidates.csv"

# This value is derived from the Human J target but is reused here only as a
# geometry-seed screening reference. It is not an extracted-J acceptance target.
HALF_Z21_PEAK_SPLIT_SCREENING_REFERENCE_MHZ = 10.0
TARGET_NOTCH_GHZ = 4.5
REPRESENTATIVE_SLOT_GHZ = 6.0
Z21_PAIR_WINDOW_GHZ = 0.8

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


def z21_observable(frame: pd.DataFrame) -> tuple[np.ndarray, str]:
    if "z21_ptc_abs_im_ohm" not in frame.columns:
        raise KeyError("PTC Z21 column z21_ptc_abs_im_ohm is required")
    return frame["z21_ptc_abs_im_ohm"].to_numpy(), "|Im(Z21 PTC)|"


def window_minimum(frequency_ghz: np.ndarray, values: np.ndarray, center_ghz: float, half_width_ghz: float) -> tuple[float, float]:
    mask = np.abs(frequency_ghz - center_ghz) <= half_width_ghz
    if not np.any(mask):
        raise ValueError(f"empty window around {center_ghz} GHz")
    local_frequency = frequency_ghz[mask]
    local_values = values[mask]
    index = int(np.argmin(local_values))
    return float(local_frequency[index]), float(local_values[index])


def local_peaks(frequency_ghz: np.ndarray, values: np.ndarray, *, top_n: int = 4) -> list[float]:
    span = float(np.max(values) - np.min(values))
    prominence = max(span * 0.002, np.finfo(float).eps)
    step_mhz = float(np.median(np.diff(frequency_ghz)) * 1000.0)
    distance = max(1, int(round(5.0 / step_mhz)))
    indexes, props = find_peaks(values, prominence=prominence, distance=distance)
    if len(indexes) == 0:
        return []
    order = np.argsort(props["prominences"])[::-1]
    return sorted(float(frequency_ghz[indexes[item]]) for item in order[:top_n])


def summarize_trace(row: object) -> dict[str, object]:
    frame = pd.read_csv(require_file(Path(row.trace_csv)))
    frequency = frame["frequency_ghz"].to_numpy()
    z21, label = z21_observable(frame)
    notch, notch_abs = window_minimum(frequency, z21, TARGET_NOTCH_GHZ, 0.45)
    peaks = local_peaks(frequency, z21)
    lower = upper = center = split_mhz = center_error_mhz = np.nan
    half_z21_peak_split_mhz = np.nan
    slot_peaks = [peak for peak in peaks if abs(peak - float(row.slot_target_ghz)) <= Z21_PAIR_WINDOW_GHZ]
    if len(slot_peaks) >= 2:
        selected = sorted(sorted(slot_peaks, key=lambda item: abs(item - float(row.slot_target_ghz)))[:2])
        lower, upper = selected
        center = 0.5 * (lower + upper)
        split_mhz = 1000.0 * (upper - lower)
        half_z21_peak_split_mhz = 0.5 * split_mhz
        center_error_mhz = 1000.0 * (center - float(row.slot_target_ghz))
    return {
        "sweep_id": row.sweep_id,
        "slot_target_ghz": float(row.slot_target_ghz),
        "open_side_compensation_mode": getattr(row, "open_side_compensation_mode", "unknown"),
        "lc_um": float(row.lc_um),
        "short_side_delta_um": float(row.short_side_delta_um),
        "lr_short_um": float(row.lr_short_um),
        "lp_short_um": float(row.lp_short_um),
        "lr_open_um": float(row.lr_open_um),
        "lp_open_um": float(row.lp_open_um),
        "lr_total_um": float(row.lr_total_um),
        "lp_total_um": float(row.lp_total_um),
        "notch_length_um": float(row.notch_length_um),
        "notch_ghz": notch,
        "notch_error_mhz": 1000.0 * (notch - TARGET_NOTCH_GHZ),
        "notch_abs_ohm": notch_abs,
        "lower_peak_ghz": lower,
        "upper_peak_ghz": upper,
        "center_ghz": center,
        "center_error_mhz": center_error_mhz,
        "splitting_mhz": split_mhz,
        "half_z21_peak_split_mhz": half_z21_peak_split_mhz,
        "mode_count_ok": len(slot_peaks) >= 2,
        "z21_observable": label,
        "z21_peak_candidates_ghz": ", ".join(f"{peak:.4f}" for peak in peaks),
        "trace_csv": row.trace_csv,
    }


# %% [markdown]
# ## Sweep Setup

# %%
setup = pd.read_csv(require_file(SETUP_CSV))
manifest = pd.read_csv(require_file(MANIFEST_CSV))
_ = display_table(setup, precision=4)
_ = display_table(
    manifest[
        [
            "sweep_id",
            "slot_target_ghz",
            "open_side_compensation_mode",
            "lc_um",
            "short_side_delta_um",
            "lr_short_um",
            "lp_short_um",
            "lr_open_um",
            "lp_open_um",
            "notch_length_um",
        ]
    ].head(12),
    precision=3,
)


# %% [markdown]
# ## Z21 Peak Screening Diagnostics

# %%
summary = pd.DataFrame(summarize_trace(row) for row in manifest.itertuples(index=False))
summary = summary.sort_values(["slot_target_ghz", "lc_um", "short_side_delta_um"]).reset_index(drop=True)

summary["half_z21_peak_split_screening_error"] = (
    (
        summary["half_z21_peak_split_mhz"]
        - HALF_Z21_PEAK_SPLIT_SCREENING_REFERENCE_MHZ
    ).abs()
    / HALF_Z21_PEAK_SPLIT_SCREENING_REFERENCE_MHZ
)
summary["geometry_seed_screening_score"] = (
    summary["half_z21_peak_split_screening_error"]
    + summary["notch_error_mhz"].abs() / 10.0
    + summary["center_error_mhz"].abs() / 100.0
)
ranked_seed_candidates = (
    summary[summary["mode_count_ok"]]
    .sort_values("geometry_seed_screening_score")
    .reset_index(drop=True)
)

summary.to_csv(SUMMARY_CSV, index=False)
ranked_seed_candidates.to_csv(RANKED_SEED_CANDIDATES_CSV, index=False)

screening_candidates = summary[summary["sweep_id"].str.startswith("candidate_")].sort_values(
    ["lc_um", "slot_target_ghz"]
)
# Keep the historical artifact path stable; its rows are screening candidates,
# not validated promotion evidence.
screening_candidates.to_csv(SCREENING_CANDIDATES_CSV, index=False)

_ = display_table(
    ranked_seed_candidates[
        [
            "slot_target_ghz",
            "open_side_compensation_mode",
            "lc_um",
            "short_side_delta_um",
            "notch_ghz",
            "notch_error_mhz",
            "lower_peak_ghz",
            "upper_peak_ghz",
            "splitting_mhz",
            "half_z21_peak_split_mhz",
            "half_z21_peak_split_screening_error",
            "center_error_mhz",
            "geometry_seed_screening_score",
        ]
    ].head(20),
    precision=4,
)

_ = display_table(
    screening_candidates[
        [
            "sweep_id",
            "slot_target_ghz",
            "lc_um",
            "short_side_delta_um",
            "lr_short_um",
            "lr_open_um",
            "lp_short_um",
            "lp_open_um",
            "notch_ghz",
            "lower_peak_ghz",
            "upper_peak_ghz",
            "half_z21_peak_split_mhz",
        ]
    ],
    precision=4,
)


# %% [markdown]
# ## Trend Plots

# %%
def plot_lc_trend() -> Path:
    data = summary[
        np.isclose(summary["slot_target_ghz"], REPRESENTATIVE_SLOT_GHZ)
        & np.isclose(summary["short_side_delta_um"], 0.0)
    ].sort_values("lc_um")
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    fig.add_trace(
        go.Scatter(
            x=data["lc_um"],
            y=data["half_z21_peak_split_mhz"],
            mode="markers+lines",
            name="half Z21 peak split (seed-screening diagnostic)",
        ),
        secondary_y=False,
    )
    fig.add_trace(
        go.Scatter(
            x=data["lc_um"],
            y=data["notch_ghz"],
            mode="markers+lines",
            name="notch",
        ),
        secondary_y=True,
    )
    fig.add_hline(
        y=HALF_Z21_PEAK_SPLIT_SCREENING_REFERENCE_MHZ,
        line_dash="dash",
        annotation_text="Human-J-target-derived screening reference",
        secondary_y=False,
    )
    fig.add_hline(y=TARGET_NOTCH_GHZ, line_dash="dot", secondary_y=True)
    fig.update_layout(title="6.00 GHz slot: coupling length trend at fixed short side")
    fig.update_xaxes(title_text="MTL coupling length lc (um)")
    fig.update_yaxes(title_text="Half Z21 peak split diagnostic (MHz)", secondary_y=False)
    fig.update_yaxes(title_text="PTC Z21 notch frequency (GHz)", secondary_y=True)
    return write_plot(fig, PLOT_DIR / "d3_z21_lc_trend_slot_6p00.png")


def heatmap_table(value: str) -> pd.DataFrame:
    data = summary[np.isclose(summary["slot_target_ghz"], REPRESENTATIVE_SLOT_GHZ)]
    return data.pivot_table(index="short_side_delta_um", columns="lc_um", values=value, aggfunc="first")


def plot_heatmaps() -> Path:
    half_z21_peak_split_grid = heatmap_table("half_z21_peak_split_mhz")
    notch_grid = heatmap_table("notch_error_mhz")
    fig = make_subplots(
        rows=1,
        cols=2,
        subplot_titles=("Half Z21 peak split diagnostic (MHz)", "Notch error (MHz)"),
    )
    fig.add_trace(
        go.Heatmap(
            x=half_z21_peak_split_grid.columns,
            y=half_z21_peak_split_grid.index,
            z=half_z21_peak_split_grid.values,
            colorbar={"title": "MHz"},
        ),
        row=1,
        col=1,
    )
    fig.add_trace(
        go.Heatmap(x=notch_grid.columns, y=notch_grid.index, z=notch_grid.values, colorbar={"title": "MHz"}),
        row=1,
        col=2,
    )
    fig.update_xaxes(title_text="lc (um)", row=1, col=1)
    fig.update_xaxes(title_text="lc (um)", row=1, col=2)
    fig.update_yaxes(title_text="short-side delta (um)", row=1, col=1)
    fig.update_layout(title="6.00 GHz slot: PTC Z21 geometry sweep")
    return write_plot(fig, PLOT_DIR / "d3_z21_lc_short_side_heatmaps_slot_6p00.png")


def plot_top_seed_screening_z21_trace() -> Path:
    if ranked_seed_candidates.empty:
        fig = go.Figure()
        fig.update_layout(
            title="No slot-local two-peak Z21 seed-screening setup found",
            xaxis_title="Frequency (GHz)",
            yaxis_title="|Im(Z21 PTC)| (ohm)",
        )
        return write_plot(fig, PLOT_DIR / "d3_z21_best_coarse_trace_slot_6p00.png")
    row = ranked_seed_candidates.iloc[0]
    frame = pd.read_csv(require_file(Path(row.trace_csv)))
    freq = frame["frequency_ghz"].to_numpy()
    z21, label = z21_observable(frame)
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=freq, y=z21, mode="markers", marker={"size": 4}, name=label))
    for x, name, dash, color in [
        (TARGET_NOTCH_GHZ, "notch target", "dot", "#111111"),
        (row.notch_ghz, "extracted notch", "dash", "#EF553B"),
        (row.lower_peak_ghz, "lower Z21 peak", "longdash", "#636EFA"),
        (row.upper_peak_ghz, "upper Z21 peak", "longdash", "#636EFA"),
    ]:
        fig.add_vline(x=float(x), line_dash=dash, line_color=color, annotation_text=name)
    fig.update_layout(
        title=(
            f"Top seed-screening setup: lc={row.lc_um:g} um, "
            f"short delta={row.short_side_delta_um:g} um"
        ),
        xaxis_title="Frequency (GHz)",
        yaxis_title=f"{label} (ohm)",
        yaxis={"type": "log"},
    )
    return write_plot(fig, PLOT_DIR / "d3_z21_best_coarse_candidate_trace.png")


def plot_screening_candidate_all_slots(candidate_prefix: str) -> Path:
    data = screening_candidates[screening_candidates["sweep_id"].str.startswith(candidate_prefix)]
    if data.empty:
        raise ValueError(f"no candidate rows match {candidate_prefix!r}")
    fig = go.Figure()
    colors = ["#636EFA", "#EF553B", "#00CC96", "#AB63FA", "#FFA15A"]
    for color, row in zip(colors, data.itertuples(index=False), strict=False):
        frame = pd.read_csv(require_file(Path(row.trace_csv)))
        freq = frame["frequency_ghz"].to_numpy()
        z21, label = z21_observable(frame)
        slot_label = f"{row.slot_target_ghz:.2f} GHz"
        fig.add_trace(
            go.Scatter(
                x=freq,
                y=z21,
                mode="markers",
                marker={"size": 3, "color": color},
                name=f"{slot_label} {label}",
            )
        )
        for peak in [row.lower_peak_ghz, row.upper_peak_ghz]:
            peak_value = float(peak)
            if np.isfinite(peak_value):
                fig.add_vline(x=peak_value, line_dash="dash", line_color=color, opacity=0.55)
    fig.add_vline(x=TARGET_NOTCH_GHZ, line_dash="dot", line_color="#111111", annotation_text="notch target")
    fig.update_layout(
        title=(
            "Seed-screening candidate across slots: "
            f"lc={data.iloc[0].lc_um:g} um, short delta={data.iloc[0].short_side_delta_um:g} um"
        ),
        xaxis_title="Frequency (GHz)",
        yaxis_title="|Im(Z21 PTC)| (ohm)",
        yaxis={"type": "log"},
    )
    return write_plot(fig, PLOT_DIR / "d3_z21_candidate_lc200_all_slots.png")


plot_paths = [
    plot_lc_trend(),
    plot_heatmaps(),
    plot_top_seed_screening_z21_trace(),
    plot_screening_candidate_all_slots("candidate_lc200_notch4500_interp"),
]
_ = display_table(pd.DataFrame({"plot": [str(path) for path in plot_paths]}))


# %% [markdown]
# ## Output Summary

# %%
print(f"wrote {SUMMARY_CSV}")
print(f"wrote {RANKED_SEED_CANDIDATES_CSV}")
print(f"wrote screening candidates to historical path {SCREENING_CANDIDATES_CSV}")

assert not summary.empty
assert {"z21_ptc_abs_im_ohm"}.issubset(pd.read_csv(require_file(Path(manifest.iloc[0].trace_csv))).columns)
