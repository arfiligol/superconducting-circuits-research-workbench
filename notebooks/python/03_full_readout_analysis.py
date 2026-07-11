# %% [markdown]
# # 03 Full Readout Analysis
#
# This notebook analyzes the HB outputs from `01_bare_frequency_probe.jl` and
# `03_full_readout_hanging_pairs.jl`.
#
# It uses vector fitting to label MTL-coupled single-pair hybridized modes and
# inspect ownership in the full shared-readout response. It does not fit J.
#
# Filter `C_ext` loading analysis lives in `02_filter_frequency_loading_analysis.py`.
#
# Canonical knowledge:
#
# - [Multiconductor RLGC Matrices: Basis, Modes, and Physical Meaning](https://github.com/arfiligol/SCQ_Design/blob/main/docs/knowledge/transmission-lines/multiconductor-rlgc-matrix-semantics.qmd)
# - [Loaded-Bare Readout / Filter References](https://github.com/arfiligol/SCQ_Design/blob/main/docs/knowledge/readout/loaded-bare-readout-filter-references.qmd)
# - [Bare vs Hybridized Readout / Filter Modes](https://github.com/arfiligol/SCQ_Design/blob/main/docs/knowledge/readout/bare-vs-hybridized-readout-filter-modes.qmd)
# - [Readout-Filter S21 J Fit](https://github.com/arfiligol/SCQ_Design/blob/main/docs/knowledge/readout/readout-filter-s21-j-fit.qmd)
# - [Poles, Zeros, and Residues](https://github.com/arfiligol/SCQ_Design/blob/main/docs/knowledge/network-modeling/poles-zeros-residues.qmd)
# - [Vector Fitting and Passivity](https://github.com/arfiligol/SCQ_Design/blob/main/docs/knowledge/network-modeling/vector-fitting-passivity.qmd)
# - [Harmonic Balance: Periodic Steady State and Mode Semantics](https://github.com/arfiligol/SCQ_Design/blob/main/docs/knowledge/numerical-methods/harmonic-balance-periodic-steady-state.qmd)
# - [Port Reference Impedance Semantics](https://github.com/arfiligol/SCQ_Design/blob/main/docs/knowledge/simulation/port-reference-impedance-semantics.qmd)
# - [Port-Termination Compensation (PTC)](https://github.com/arfiligol/SCQ_Design/blob/main/docs/knowledge/simulation/port-termination-compensation.qmd)
#
# Current Q2D matrix inputs are exploration-only until they pass the canonical
# artifact eligibility gate.

# %%
from __future__ import annotations

import os
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import skrf as rf
try:
    from IPython.display import Image as IPythonImage
    from IPython.display import display as ipython_display
except ImportError:  # pragma: no cover - notebook display convenience only.
    IPythonImage = None
    ipython_display = None

from scipy.signal import find_peaks
from skrf.vectorFitting import VectorFitting

from d3_design_config import load_d3_design_config, variant_suffix


def path_slug(value: object) -> str:
    return str(value).replace(".", "p").replace("-", "m").replace("/", "_").replace(" ", "_")


OUTPUT_ROOT = Path(
    "/home/ili/Githubs/SCQ_Design/orpen_sc_pdk/build/simulation/circuit/"
    "intrinsic_purcell_filter"
)
D3_ROOT = OUTPUT_ROOT / "d3_intrinsic_purcell_filter_design"
D3_CONFIG = load_d3_design_config()
DESIGN_VARIANT_ID = str(D3_CONFIG["active_design_variant_id"])
VARIANT_SUFFIX = variant_suffix(DESIGN_VARIANT_ID)
SINGLE_SLOT_GHZ_TEXT = os.environ.get("D3_SINGLE_SLOT_GHZ", "").strip()
SINGLE_SLOT_GHZ = float(SINGLE_SLOT_GHZ_TEXT) if SINGLE_SLOT_GHZ_TEXT else None
FULL_VARIANT_SUFFIX = (
    f"{VARIANT_SUFFIX}__single_slot_{path_slug(SINGLE_SLOT_GHZ_TEXT)}"
    if SINGLE_SLOT_GHZ is not None
    else VARIANT_SUFFIX
)
ANALYSIS_SUFFIX = FULL_VARIANT_SUFFIX
BARE_ROOT = D3_ROOT / f"bare_frequency_probe{VARIANT_SUFFIX}"
FULL_ROOT = D3_ROOT / f"full_readout_hanging_pairs{FULL_VARIANT_SUFFIX}"
PLOT_DIR = D3_ROOT / "plots" / path_slug(
    f"{DESIGN_VARIANT_ID}__single_slot_{SINGLE_SLOT_GHZ_TEXT}"
    if SINGLE_SLOT_GHZ is not None
    else DESIGN_VARIANT_ID
)

DESIGN_CSV = D3_ROOT / f"design_inputs/d3_selected_resonator_lengths{VARIANT_SUFFIX}.csv"
BARE_MANIFEST_CSV = BARE_ROOT / "d3_bare_probe_manifest.csv"
INTRINSIC_Z21_MANIFEST_CSV = BARE_ROOT / "d3_intrinsic_z21_manifest.csv"
FULL_MANIFEST_CSV = FULL_ROOT / "d3_full_shared_readout_manifest.csv"

BARE_MODES_CSV = D3_ROOT / f"d3_bare_vector_fit_ownership_modes{ANALYSIS_SUFFIX}.csv"
INTRINSIC_Z21_CSV = D3_ROOT / f"d3_intrinsic_z21_notch_modes{ANALYSIS_SUFFIX}.csv"
INTRINSIC_Z21_PAIR_SUMMARY_CSV = D3_ROOT / f"d3_intrinsic_z21_pair_summary{ANALYSIS_SUFFIX}.csv"
FULL_VF_SUMMARY_CSV = D3_ROOT / f"d3_full_s11_vector_fit_summary{ANALYSIS_SUFFIX}.csv"
FULL_VF_MODES_CSV = D3_ROOT / f"d3_full_s11_vector_fit_modes{ANALYSIS_SUFFIX}.csv"
FULL_S21_VF_SUMMARY_CSV = D3_ROOT / f"d3_full_s21_vector_fit_summary{ANALYSIS_SUFFIX}.csv"
FULL_S21_VF_MODES_CSV = D3_ROOT / f"d3_full_s21_vector_fit_modes{ANALYSIS_SUFFIX}.csv"
FULL_PAIR_ASSIGNMENT_CSV = D3_ROOT / f"d3_full_pair_assignment_evidence{ANALYSIS_SUFFIX}.csv"

GHz = 1.0e9
MHz = 1.0e6
OWNERSHIP_VARIANT_ORDER = (
    "baseline",
    "readout_open_minus",
    "readout_open_plus",
    "filter_open_minus",
    "filter_open_plus",
)

pd.set_option("display.max_columns", 80)
pd.set_option("display.width", 180)


# %% [markdown]
# ## Design Input Tables
#
# Keep the length and trace manifests visible in the notebook. The Pluto
# notebooks own data generation; this analysis notebook makes those generated
# numbers easy to audit before fitting.

# %%
def require_file(path: Path) -> Path:
    if not path.is_file():
        raise FileNotFoundError(f"required CSV is missing: {path}")
    return path


def slug(value: object) -> str:
    return path_slug(value)


def cext_label(cext_fF: float) -> str:
    return "per-design" if float(cext_fF) < 0.0 else f"{float(cext_fF):g} fF"


def display_table(frame: pd.DataFrame, *, precision: int = 4) -> pd.DataFrame:
    table = frame.copy()
    numeric_columns = table.select_dtypes(include=[np.number]).columns
    table.loc[:, numeric_columns] = table.loc[:, numeric_columns].round(precision)
    if ipython_display is not None:
        ipython_display(table)
    else:
        print(table.to_string(index=False))
    return table


def display_images(paths: list[Path]) -> pd.DataFrame:
    unique_paths = list(dict.fromkeys(Path(path) for path in paths))
    table = pd.DataFrame({"static_plot_png": [str(path) for path in unique_paths]})
    if ipython_display is not None:
        ipython_display(table)
    else:
        for path in unique_paths:
            print(f"static plot: {path}")
    return table


def write_plotly_png(fig: go.Figure, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    if ipython_display is not None:
        ipython_display(fig)
    fig.write_image(path, scale=1)
    return path


selected_designs = pd.read_csv(require_file(DESIGN_CSV))
bare_manifest = pd.read_csv(require_file(BARE_MANIFEST_CSV))
intrinsic_z21_manifest = pd.read_csv(require_file(INTRINSIC_Z21_MANIFEST_CSV))
full_manifest = pd.read_csv(require_file(FULL_MANIFEST_CSV))
if SINGLE_SLOT_GHZ is not None:
    selected_designs = selected_designs[np.isclose(selected_designs["slot_target_ghz"], SINGLE_SLOT_GHZ)].reset_index(drop=True)
    bare_manifest = bare_manifest[np.isclose(bare_manifest["slot_target_ghz"], SINGLE_SLOT_GHZ)].reset_index(drop=True)
    intrinsic_z21_manifest = intrinsic_z21_manifest[
        np.isclose(intrinsic_z21_manifest["slot_target_ghz"], SINGLE_SLOT_GHZ)
    ].reset_index(drop=True)
    if len(selected_designs) != 1:
        raise ValueError(f"D3_SINGLE_SLOT_GHZ={SINGLE_SLOT_GHZ_TEXT} matched {len(selected_designs)} selected designs.")

_ = display_table(selected_designs, precision=3)
_ = display_table(full_manifest, precision=3)


# %% [markdown]
# ## Peak Ownership
#
# A single coupled-pair spectrum shows hybrid modes, not pure resonators. To
# label a peak, use the coupled-pair perturbation traces:
#
# - `baseline`: original lengths
# - `readout_open_minus` / `readout_open_plus`: only the readout resonator
#   open-end section is shortened/lengthened
# - `filter_open_minus` / `filter_open_plus`: only the filter resonator
#   open-end section is shortened/lengthened
#
# The larger central-difference sensitivity identifies the mode owner. If both
# sensitivities are comparable, keep the row labeled as hybrid.

# %%
def complex_column(frame: pd.DataFrame, prefix: str) -> np.ndarray:
    return frame[f"{prefix}_re"].to_numpy() + 1j * frame[f"{prefix}_im"].to_numpy()


def z21_observable(frame: pd.DataFrame) -> tuple[np.ndarray, str]:
    if "z21_ptc_abs_im_ohm" in frame.columns:
        return frame["z21_ptc_abs_im_ohm"].to_numpy(), "|Im(Z21 PTC)|"
    raise KeyError("PTC Z21 column z21_ptc_abs_im_ohm is required for D3 primary evidence")


def fit_metrics(data: np.ndarray, fitted: np.ndarray) -> dict[str, float]:
    residual = fitted - data
    sse = float(np.sum(np.abs(residual) ** 2))
    centered_sse = float(np.sum(np.abs(data - np.mean(data)) ** 2))
    abs_residual = np.abs(fitted) - np.abs(data)
    abs_sse = float(np.sum(abs_residual**2))
    abs_centered_sse = float(np.sum((np.abs(data) - np.mean(np.abs(data))) ** 2))
    return {
        "complex_rmse": float(np.sqrt(np.mean(np.abs(residual) ** 2))),
        "complex_r2": 1.0 - sse / centered_sse,
        "abs_rmse": float(np.sqrt(np.mean(abs_residual**2))),
        "abs_r2": 1.0 - abs_sse / abs_centered_sse,
    }


def local_extrema(
    frequency_ghz: np.ndarray,
    values: np.ndarray,
    *,
    kind: str,
    prominence_fraction: float,
    distance_mhz: float,
    top_n: int,
) -> list[float]:
    span = float(np.max(values) - np.min(values))
    prominence = max(span * prominence_fraction, np.finfo(float).eps)
    step_mhz = float(np.median(np.diff(frequency_ghz)) * 1000.0)
    distance = max(1, int(round(distance_mhz / step_mhz)))
    signal = values if kind == "peak" else -values
    indexes, properties = find_peaks(signal, prominence=prominence, distance=distance)
    order = np.argsort(properties["prominences"])[::-1]
    return sorted(float(frequency_ghz[indexes[item]]) for item in order[:top_n])


def vector_fit_s11(path: Path, *, n_complex_poles: int, dip_count: int, feature_kind: str = "dip") -> dict[str, object]:
    frame = pd.read_csv(require_file(path))
    frequency_ghz = frame["frequency_ghz"].to_numpy()
    s11 = complex_column(frame, "s11")
    network = rf.Network(
        frequency=rf.Frequency.from_f(frequency_ghz, unit="ghz"),
        s=s11.reshape(-1, 1, 1),
        name=path.stem,
    )
    vector_fit = VectorFitting(network)
    vector_fit.vector_fit(
        n_poles_real=0,
        n_poles_cmplx=n_complex_poles,
        init_pole_spacing="lin",
        parameter_type="s",
        fit_constant=True,
        fit_proportional=False,
        enforce_dc=False,
    )
    fitted = vector_fit.get_model_response(0, 0, freqs=frequency_ghz * GHz)
    poles = np.asarray(vector_fit.poles)
    residues = np.asarray(vector_fit.residues)[0]
    pole_rows = []
    for pole_index, pole in enumerate(poles):
        if pole.imag <= 0.0:
            continue
        pole_frequency_ghz = float(pole.imag / (2.0 * np.pi * GHz))
        if 5.0 <= pole_frequency_ghz <= 7.0:
            pole_rows.append(
                {
                    "pole_frequency_ghz": pole_frequency_ghz,
                    "kappa_over_2pi_mhz": float(-2.0 * pole.real / (2.0 * np.pi * MHz)),
                    "residue_abs": float(abs(residues[pole_index])),
                }
            )
    pole_table = pd.DataFrame(pole_rows).sort_values("pole_frequency_ghz")
    dips = local_extrema(
        frequency_ghz,
        np.abs(fitted),
        kind=feature_kind,
        prominence_fraction=0.004,
        distance_mhz=6.0,
        top_n=dip_count,
    )
    return {
        "frequency_ghz": frequency_ghz,
        "s11": s11,
        "s11_vf": fitted,
        "dips_ghz": dips[:dip_count],
        "vf_rms_error": float(vector_fit.get_rms_error()),
        **fit_metrics(s11, fitted),
    }


def nearest_frequency_ghz(reference_ghz: float, moved_ghz: list[float]) -> float:
    return float(min(moved_ghz, key=lambda value: abs(value - reference_ghz)))


def mode_owner(readout_sensitivity: float, filter_sensitivity: float, *, ratio_threshold: float = 2.0) -> tuple[str, float]:
    smaller = max(min(readout_sensitivity, filter_sensitivity), np.finfo(float).eps)
    ratio = max(readout_sensitivity, filter_sensitivity) / smaller
    if ratio < ratio_threshold:
        return "hybrid", float(ratio)
    if readout_sensitivity > filter_sensitivity:
        return "readout_like", float(ratio)
    return "filter_like", float(ratio)


# %% [markdown]
# ## Coupled-Pair Probe Vector Fit

# %%
def plot_bare_ownership_slot(
    target_set_id: str,
    slot_target_ghz: float,
    by_variant: dict[str, object],
    fit_by_trace: dict[str, dict[str, object]],
) -> Path:
    PLOT_DIR.mkdir(parents=True, exist_ok=True)
    fig = go.Figure()
    variants = [variant_id for variant_id in OWNERSHIP_VARIANT_ORDER if variant_id in by_variant]
    for variant_id in variants:
        trace_csv = by_variant[variant_id].trace_csv
        fit = fit_by_trace[trace_csv]
        frequency = fit["frequency_ghz"]
        fig.add_trace(
            go.Scatter(
                x=frequency,
                y=np.abs(fit["s11"]),
                mode="markers",
                name=f"{variant_id} HB raw",
            )
        )
        fig.add_trace(
            go.Scatter(
                x=frequency,
                y=np.abs(fit["s11_vf"]),
                mode="lines",
                line={"dash": "dash"},
                name=f"{variant_id} vector fit",
            )
        )
    fig.update_layout(
        title=f"{target_set_id}: coupled-pair probe S11 fit, slot {slot_target_ghz:.3f} GHz",
        xaxis_title="Frequency (GHz)",
        yaxis_title="|S11|",
    )
    path = PLOT_DIR / f"{target_set_id}_slot_{slug(slot_target_ghz)}_coupled_pair_probe_vector_fit.png"
    return write_plotly_png(fig, path)


def analyze_bare_ownership() -> tuple[pd.DataFrame, list[Path]]:
    manifest = bare_manifest.copy()
    fit_by_trace: dict[str, dict[str, object]] = {}
    for row in manifest.itertuples(index=False):
        fit_by_trace[row.trace_csv] = vector_fit_s11(
            Path(row.trace_csv),
            n_complex_poles=4,
            dip_count=2,
            feature_kind="peak",
        )

    rows: list[dict[str, object]] = []
    plot_paths: list[Path] = []
    for (target_set_id, slot), group in manifest.groupby(["target_set_id", "slot_target_ghz"]):
        by_variant = {row.variant_id: row for row in group.itertuples(index=False)}
        required = set(OWNERSHIP_VARIANT_ORDER)
        missing = sorted(required - set(by_variant))
        if missing:
            raise ValueError(f"missing ownership variants for {target_set_id} {slot} GHz: {missing}")
        plot_paths.append(plot_bare_ownership_slot(target_set_id, slot, by_variant, fit_by_trace))
        baseline = fit_by_trace[by_variant["baseline"].trace_csv]["dips_ghz"]
        readout_minus = fit_by_trace[by_variant["readout_open_minus"].trace_csv]["dips_ghz"]
        readout_plus = fit_by_trace[by_variant["readout_open_plus"].trace_csv]["dips_ghz"]
        filter_minus = fit_by_trace[by_variant["filter_open_minus"].trace_csv]["dips_ghz"]
        filter_plus = fit_by_trace[by_variant["filter_open_plus"].trace_csv]["dips_ghz"]
        readout_delta_um = abs(float(by_variant["readout_open_plus"].readout_open_delta_um))
        filter_delta_um = abs(float(by_variant["filter_open_plus"].filter_open_delta_um))
        for mode_index, frequency in enumerate(baseline, start=1):
            readout_minus_ghz = nearest_frequency_ghz(frequency, readout_minus)
            readout_plus_ghz = nearest_frequency_ghz(frequency, readout_plus)
            filter_minus_ghz = nearest_frequency_ghz(frequency, filter_minus)
            filter_plus_ghz = nearest_frequency_ghz(frequency, filter_plus)
            readout_slope_mhz_per_um = 1000.0 * (readout_plus_ghz - readout_minus_ghz) / (2.0 * readout_delta_um)
            filter_slope_mhz_per_um = 1000.0 * (filter_plus_ghz - filter_minus_ghz) / (2.0 * filter_delta_um)
            owner, ratio = mode_owner(abs(readout_slope_mhz_per_um), abs(filter_slope_mhz_per_um))
            rows.append(
                {
                    "target_set_id": target_set_id,
                    "slot_target_ghz": slot,
                    "mode_index": mode_index,
                    "baseline_dip_ghz": frequency,
                    "readout_minus_dip_ghz": readout_minus_ghz,
                    "readout_plus_dip_ghz": readout_plus_ghz,
                    "filter_minus_dip_ghz": filter_minus_ghz,
                    "filter_plus_dip_ghz": filter_plus_ghz,
                    "readout_sensitivity_mhz_per_um": readout_slope_mhz_per_um,
                    "filter_sensitivity_mhz_per_um": filter_slope_mhz_per_um,
                    "ownership_ratio": ratio,
                    "owner": owner,
                    "baseline_trace_csv": by_variant["baseline"].trace_csv,
                }
            )
    modes = pd.DataFrame(rows).sort_values(["target_set_id", "slot_target_ghz", "mode_index"])
    return modes, plot_paths


bare_ownership_modes, bare_plot_paths = analyze_bare_ownership()
_ = display_table(
    bare_ownership_modes[
        [
            "target_set_id",
            "slot_target_ghz",
            "mode_index",
            "baseline_dip_ghz",
            "owner",
            "readout_minus_dip_ghz",
            "readout_plus_dip_ghz",
            "filter_minus_dip_ghz",
            "filter_plus_dip_ghz",
            "readout_sensitivity_mhz_per_um",
            "filter_sensitivity_mhz_per_um",
            "ownership_ratio",
        ]
    ],
    precision=4,
)
_ = display_images(bare_plot_paths)


# %% [markdown]
# ## Broad Intrinsic Z21 Notch Check
#
# These traces are intrinsic pair runs without the feedline. The broad
# `4.0-6.6 GHz` sweep is intentionally wide enough to show both the notch near
# `4.5 GHz` and resonator features near the readout band.

# %%
def window_minimum(frequency_ghz: np.ndarray, values: np.ndarray, center_ghz: float, half_width_ghz: float) -> tuple[float, float]:
    mask = np.abs(frequency_ghz - center_ghz) <= half_width_ghz
    if not np.any(mask):
        raise ValueError(f"empty window around {center_ghz} GHz")
    local_frequency = frequency_ghz[mask]
    local_values = values[mask]
    index = int(np.argmin(local_values))
    return float(local_frequency[index]), float(local_values[index])


def plot_intrinsic_z21(row: object) -> Path:
    PLOT_DIR.mkdir(parents=True, exist_ok=True)
    frame = pd.read_csv(require_file(Path(row.trace_csv)))
    frequency = frame["frequency_ghz"].to_numpy()
    z21_abs, z21_label = z21_observable(frame)
    notch_ghz, notch_abs = window_minimum(frequency, z21_abs, float(row.notch_target_ghz), 0.45)
    y_floor = float(np.min(z21_abs[z21_abs > 0.0]))
    y_ceiling = float(np.max(z21_abs))

    def add_marker_line(x_ghz: float, name: str, *, color: str, dash: str) -> None:
        fig.add_trace(
            go.Scatter(
                x=[x_ghz, x_ghz],
                y=[y_floor, y_ceiling],
                mode="lines",
                line={"color": color, "dash": dash, "width": 2},
                name=name,
                hoverinfo="skip",
            )
        )

    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=frequency,
            y=z21_abs,
            mode="markers",
            marker={"size": 4},
            name=f"intrinsic {z21_label}",
        )
    )
    add_marker_line(float(row.notch_target_ghz), f"notch target {float(row.notch_target_ghz):.4f} GHz", color="#111111", dash="dot")
    add_marker_line(notch_ghz, f"extracted notch {notch_ghz:.4f} GHz", color="#EF553B", dash="solid")
    add_marker_line(float(row.slot_target_ghz), f"slot target {float(row.slot_target_ghz):.4f} GHz", color="#00CC96", dash="dash")
    slot_modes = bare_ownership_modes[np.isclose(bare_ownership_modes["slot_target_ghz"], float(row.slot_target_ghz))]
    mode_colors = {"filter_like": "#AB63FA", "readout_like": "#FFA15A", "hybrid": "#19D3F3"}
    for mode_row in slot_modes.itertuples(index=False):
        owner = str(mode_row.owner)
        add_marker_line(
            float(mode_row.baseline_dip_ghz),
            f"{owner.replace('_', '-')} mode {float(mode_row.baseline_dip_ghz):.4f} GHz",
            color=mode_colors.get(owner, "#888888"),
            dash="longdash",
        )
    fig.update_layout(
        title=f"Intrinsic broad {z21_label}, slot {float(row.slot_target_ghz):.2f} GHz",
        xaxis_title="Frequency (GHz)",
        yaxis_title=f"{z21_label} (ohm)",
        yaxis={
            "type": "log",
            "dtick": 1,
            "exponentformat": "power",
            "range": [np.log10(y_floor * 0.8), np.log10(y_ceiling * 1.2)],
        },
    )
    path = PLOT_DIR / f"d3_slot_{slug(row.slot_target_ghz)}_broad_intrinsic_z21.png"
    return write_plotly_png(fig, path)


z21_rows: list[dict[str, object]] = []
z21_plot_paths: list[Path] = []
for row in intrinsic_z21_manifest.itertuples(index=False):
    frame = pd.read_csv(require_file(Path(row.trace_csv)))
    frequency = frame["frequency_ghz"].to_numpy()
    z21_abs, z21_label = z21_observable(frame)
    notch_ghz, notch_abs = window_minimum(frequency, z21_abs, float(row.notch_target_ghz), 0.45)
    resonator_peaks = local_extrema(
        frequency,
        z21_abs,
        kind="peak",
        prominence_fraction=0.002,
        distance_mhz=20.0,
        top_n=4,
    )
    z21_rows.append(
        {
            "slot_target_ghz": row.slot_target_ghz,
            "notch_target_ghz": row.notch_target_ghz,
            "z21_notch_ghz": notch_ghz,
            "z21_notch_error_mhz": 1000.0 * (notch_ghz - float(row.notch_target_ghz)),
            "z21_notch_abs_ohm": notch_abs,
            "z21_observable": z21_label,
            "z21_peak_candidates_ghz": ", ".join(f"{peak:.4f}" for peak in resonator_peaks),
            "trace_csv": row.trace_csv,
        }
    )
    z21_plot_paths.append(plot_intrinsic_z21(row))

intrinsic_z21_modes = pd.DataFrame(z21_rows).sort_values("slot_target_ghz")
_ = display_table(intrinsic_z21_modes.drop(columns=["trace_csv"]), precision=6)
_ = display_images(z21_plot_paths)


def parse_peak_candidates_ghz(value: object) -> list[float]:
    if pd.isna(value):
        return []
    return [float(item.strip()) for item in str(value).split(",") if item.strip()]


def build_z21_pair_summary(modes: pd.DataFrame) -> pd.DataFrame:
    evidence_label = (
        "This PTC Z21 comes from the selected intrinsic two-resonator probe circuit; "
        "pair isolation follows from that source topology, not from PTC alone. The high peak is "
        "before filter-to-feedline C_ext loading and must be shifted before comparing "
        "to feedline-loaded S-parameter modes. Half of the raw Z21 peak split is a "
        "screening diagnostic only; it is not J extraction or promotion evidence."
    )
    rows: list[dict[str, object]] = []
    for row in modes.itertuples(index=False):
        peaks = parse_peak_candidates_ghz(row.z21_peak_candidates_ghz)
        lower = upper = center = center_error = splitting = np.nan
        half_z21_peak_split_mhz = np.nan
        if len(peaks) >= 2:
            lower, upper = sorted(peaks)[:2]
            center = 0.5 * (lower + upper)
            center_error = 1000.0 * (center - float(row.slot_target_ghz))
            splitting = 1000.0 * (upper - lower)
            half_z21_peak_split_mhz = 0.5 * splitting
        rows.append(
            {
                "slot_target_ghz": row.slot_target_ghz,
                "lower_peak_ghz": lower,
                "upper_peak_ghz": upper,
                "center_ghz": center,
                "center_error_mhz": center_error,
                "splitting_mhz": splitting,
                "half_z21_peak_split_mhz": half_z21_peak_split_mhz,
                "mode_count_ok": len(peaks) >= 2,
                "notch_target_ghz": row.notch_target_ghz,
                "z21_notch_ghz": row.z21_notch_ghz,
                "z21_notch_error_mhz": row.z21_notch_error_mhz,
                "z21_notch_abs_ohm": row.z21_notch_abs_ohm,
                "z21_observable": row.z21_observable,
                "z21_peak_candidates_ghz": row.z21_peak_candidates_ghz,
                "trace_csv": row.trace_csv,
                "evidence_label": evidence_label,
            }
        )
    return pd.DataFrame(rows).sort_values("slot_target_ghz")


intrinsic_z21_pair_summary = build_z21_pair_summary(intrinsic_z21_modes)
_ = display_table(intrinsic_z21_pair_summary.drop(columns=["trace_csv"]), precision=6)


# %% [markdown]
# ## Full Shared-Readout Vector Fit

# %%
def plot_vector_fit(target_set_id: str, cext_fF: float, fit: dict[str, object]) -> Path:
    PLOT_DIR.mkdir(parents=True, exist_ok=True)
    frequency = fit["frequency_ghz"]
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=frequency,
            y=np.abs(fit["s11"]),
            mode="markers",
            name="HB raw |S11|",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=frequency,
            y=np.abs(fit["s11_vf"]),
            mode="lines",
            line={"dash": "dash"},
            name="vector fit |S11|",
        )
    )
    fig.update_layout(
        title=f"{target_set_id}, Cext {cext_label(cext_fF)}: S11 vector-fit frequency pre-pass",
        xaxis_title="Frequency (GHz)",
        yaxis_title="|S11|",
    )
    path = PLOT_DIR / f"{target_set_id}_c_{slug(cext_fF)}fF_s11_vector_fit.png"
    return write_plotly_png(fig, path)


def analyze_full_vector_fit() -> tuple[pd.DataFrame, pd.DataFrame, list[Path]]:
    manifest = full_manifest.copy()
    summaries: list[dict[str, object]] = []
    modes: list[dict[str, object]] = []
    plot_paths: list[Path] = []
    for row in manifest.itertuples(index=False):
        fit = vector_fit_s11(Path(row.trace_csv), n_complex_poles=14, dip_count=10)
        summaries.append(
            {
                "target_set_id": row.target_set_id,
                "target_set_name": row.target_set_name,
                "filter_to_line_capacitance_fF": row.filter_to_line_capacitance_fF,
                "trace_csv": row.trace_csv,
                "n_complex_poles": 14,
                "vf_rms_error": fit["vf_rms_error"],
                "complex_rmse": fit["complex_rmse"],
                "complex_r2": fit["complex_r2"],
                "abs_rmse": fit["abs_rmse"],
                "abs_r2": fit["abs_r2"],
            }
        )
        for index, frequency in enumerate(fit["dips_ghz"], start=1):
            modes.append(
                {
                    "target_set_id": row.target_set_id,
                    "filter_to_line_capacitance_fF": row.filter_to_line_capacitance_fF,
                    "mode_index": index,
                    "s11_vf_dip_ghz": frequency,
                    "trace_csv": row.trace_csv,
                }
            )
        plot_paths.append(plot_vector_fit(row.target_set_id, row.filter_to_line_capacitance_fF, fit))
    return pd.DataFrame(summaries), pd.DataFrame(modes), plot_paths


full_vf_summary, full_vf_modes, full_vf_plot_paths = analyze_full_vector_fit()
_ = display_table(full_vf_summary.drop(columns=["trace_csv"]), precision=6)
_ = display_table(full_vf_modes.drop(columns=["trace_csv"]), precision=6)
_ = display_images(full_vf_plot_paths)


# %% [markdown]
# ## Full Shared-Readout S21 Vector Fit

# %%
def vector_fit_s21(path: Path, *, n_complex_poles: int) -> dict[str, object]:
    frame = pd.read_csv(require_file(path))
    frequency_ghz = frame["frequency_ghz"].to_numpy()
    s21 = complex_column(frame, "s21")
    network = rf.Network(
        frequency=rf.Frequency.from_f(frequency_ghz, unit="ghz"),
        s=s21.reshape(-1, 1, 1),
        name=path.stem,
    )
    vector_fit = VectorFitting(network)
    vector_fit.vector_fit(
        n_poles_real=0,
        n_poles_cmplx=n_complex_poles,
        init_pole_spacing="lin",
        parameter_type="s",
        fit_constant=True,
        fit_proportional=False,
        enforce_dc=False,
    )
    fitted = vector_fit.get_model_response(0, 0, freqs=frequency_ghz * GHz)
    poles = np.asarray(vector_fit.poles)
    residues = np.asarray(vector_fit.residues)[0]
    pole_rows = []
    for pole_index, pole in enumerate(poles):
        if pole.imag <= 0.0:
            continue
        pole_frequency_ghz = float(pole.imag / (2.0 * np.pi * GHz))
        if 5.0 <= pole_frequency_ghz <= 7.0:
            pole_rows.append(
                {
                    "pole_frequency_ghz": pole_frequency_ghz,
                    "kappa_over_2pi_mhz": float(-2.0 * pole.real / (2.0 * np.pi * MHz)),
                    "residue_abs": float(abs(residues[pole_index])),
                }
            )
    pole_table = pd.DataFrame(pole_rows).sort_values("pole_frequency_ghz")
    dips = local_extrema(
        frequency_ghz,
        np.abs(fitted),
        kind="dip",
        prominence_fraction=0.004,
        distance_mhz=6.0,
        top_n=10,
    )
    return {
        "frequency_ghz": frequency_ghz,
        "s21": s21,
        "s21_vf": fitted,
        "dips_ghz": dips,
        "pole_table": pole_table,
        "vf_rms_error": float(vector_fit.get_rms_error()),
        **fit_metrics(s21, fitted),
    }


def plot_s21_vector_fit(target_set_id: str, cext_fF: float, fit: dict[str, object]) -> Path:
    PLOT_DIR.mkdir(parents=True, exist_ok=True)
    frequency = fit["frequency_ghz"]
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=frequency,
            y=np.abs(fit["s21"]),
            mode="markers",
            name="HB raw |S21|",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=frequency,
            y=np.abs(fit["s21_vf"]),
            mode="lines",
            line={"dash": "dash"},
            name="vector fit |S21|",
        )
    )
    fig.update_layout(
        title=f"{target_set_id}, Cext {cext_label(cext_fF)}: S21 vector-fit check",
        xaxis_title="Frequency (GHz)",
        yaxis_title="|S21|",
    )
    path = PLOT_DIR / f"{target_set_id}_c_{slug(cext_fF)}fF_s21_vector_fit.png"
    return write_plotly_png(fig, path)


full_s21_vf_rows: list[dict[str, object]] = []
full_s21_vf_mode_rows: list[dict[str, object]] = []
full_s21_vf_plot_paths: list[Path] = []
for row in full_manifest.itertuples(index=False):
    fit = vector_fit_s21(Path(row.trace_csv), n_complex_poles=14)
    full_s21_vf_rows.append(
        {
            "target_set_id": row.target_set_id,
            "filter_to_line_capacitance_fF": row.filter_to_line_capacitance_fF,
            "vf_rms_error": fit["vf_rms_error"],
            "complex_rmse": fit["complex_rmse"],
            "complex_r2": fit["complex_r2"],
            "abs_rmse": fit["abs_rmse"],
            "abs_r2": fit["abs_r2"],
            "trace_csv": row.trace_csv,
        }
    )
    for index, frequency in enumerate(fit["dips_ghz"], start=1):
        pole_table = fit["pole_table"]
        nearest_pole = pole_table.loc[(pole_table["pole_frequency_ghz"] - frequency).abs().idxmin()]
        full_s21_vf_mode_rows.append(
            {
                "target_set_id": row.target_set_id,
                "filter_to_line_capacitance_fF": row.filter_to_line_capacitance_fF,
                "mode_index": index,
                "s21_vf_dip_ghz": frequency,
                "s21_vf_pole_ghz": float(nearest_pole["pole_frequency_ghz"]),
                "s21_vf_kappa_over_2pi_mhz": float(nearest_pole["kappa_over_2pi_mhz"]),
                "s21_vf_pole_residue_abs": float(nearest_pole["residue_abs"]),
                "trace_csv": row.trace_csv,
            }
        )
    full_s21_vf_plot_paths.append(plot_s21_vector_fit(row.target_set_id, row.filter_to_line_capacitance_fF, fit))

full_s21_vf_summary = pd.DataFrame(full_s21_vf_rows)
full_s21_vf_modes = pd.DataFrame(full_s21_vf_mode_rows)
_ = display_table(full_s21_vf_summary.drop(columns=["trace_csv"]), precision=6)
_ = display_table(full_s21_vf_modes.drop(columns=["trace_csv"]), precision=6)
_ = display_images(full_s21_vf_plot_paths)


# %% [markdown]
# ## Coupled-Pair Assignment Evidence
#
# `Z21` is not used here to estimate `$J$`. Once the MTL coupling section is
# present, the single-pair peaks are hybridized coupled-pair modes, not
# uncoupled bare resonator modes. The perturbation traces are used only to label
# which physical resonator each hybridized mode is closer to. This audit table
# explains whether the coupled-pair modes leave enough guard band for the full
# shared-readout spectrum. The full S21/S11 dips are diagnostic; they should not
# be blindly paired by sorted order when a mode is weak or missing.

# %%
def bare_pair_rows() -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    lengths = selected_designs.set_index("slot_target_ghz")
    for slot, group in bare_ownership_modes.groupby("slot_target_ghz"):
        filter_rows = group[group["owner"] == "filter_like"]
        readout_rows = group[group["owner"] == "readout_like"]
        assignment_note = "pure owner from length sensitivity"
        if filter_rows.empty or readout_rows.empty:
            nearest = group.assign(
                slot_distance=lambda frame: np.abs(frame["baseline_dip_ghz"] - float(slot))
            ).nsmallest(2, "slot_distance")
            if len(nearest) < 2:
                length_row = lengths.loc[slot]
                rows.append(
                    {
                        "slot_target_ghz": float(slot),
                        "bare_filter_like_ghz": np.nan,
                        "bare_readout_like_ghz": np.nan,
                        "bare_center_ghz": np.nan,
                        "bare_lower_owner": "missing",
                        "bare_owner_order_ok": False,
                        "bare_assignment_note": "missing coupled-pair mode in bare probe VF diagnostics",
                        "lr_short_um": float(length_row["lr_short_um"]),
                        "lc_um": float(length_row["lc_um"]),
                        "lr_open_um": float(length_row["lr_open_um"]),
                        "lp_short_um": float(length_row["lp_short_um"]),
                        "lp_open_um": float(length_row["lp_open_um"]),
                        "filter_to_line_capacitance_fF": float(length_row["filter_to_line_capacitance_fF"]),
                    }
                )
                continue
            nearest = nearest.sort_values("baseline_dip_ghz")
            filter_row = nearest.iloc[0]
            readout_row = nearest.iloc[1]
            assignment_note = "hybrid fallback: nearest two baseline modes because pure ownership is not separable"
        else:
            filter_row = filter_rows.sort_values("baseline_dip_ghz").iloc[0]
            readout_row = readout_rows.sort_values("baseline_dip_ghz").iloc[0]
        length_row = lengths.loc[slot]
        bare_lower_owner = "filter_like" if filter_row["baseline_dip_ghz"] < readout_row["baseline_dip_ghz"] else "readout_like"
        rows.append(
            {
                "slot_target_ghz": float(slot),
                "bare_filter_like_ghz": float(filter_row["baseline_dip_ghz"]),
                "bare_readout_like_ghz": float(readout_row["baseline_dip_ghz"]),
                "bare_center_ghz": 0.5 * (float(filter_row["baseline_dip_ghz"]) + float(readout_row["baseline_dip_ghz"])),
                "bare_lower_owner": bare_lower_owner,
                "bare_owner_order_ok": bare_lower_owner == "filter_like",
                "bare_assignment_note": assignment_note,
                "lr_short_um": float(length_row["lr_short_um"]),
                "lc_um": float(length_row["lc_um"]),
                "lr_open_um": float(length_row["lr_open_um"]),
                "lp_short_um": float(length_row["lp_short_um"]),
                "lp_open_um": float(length_row["lp_open_um"]),
                "filter_to_line_capacitance_fF": float(length_row["filter_to_line_capacitance_fF"]),
            }
        )
    return pd.DataFrame(rows).sort_values("slot_target_ghz").reset_index(drop=True)


def two_by_two_modes(modes: pd.DataFrame, frequency_column: str, output_prefix: str) -> pd.DataFrame:
    if SINGLE_SLOT_GHZ is not None:
        ordered = (
            modes.assign(_slot_distance=lambda frame: np.abs(frame[frequency_column] - SINGLE_SLOT_GHZ))
            .nsmallest(2, "_slot_distance")
            .sort_values(frequency_column)
            .drop(columns=["_slot_distance"])
            .reset_index(drop=True)
        )
    else:
        ordered = modes.sort_values(frequency_column).reset_index(drop=True)
    rows: list[dict[str, object]] = []
    for pair_index in range((len(ordered) + 1) // 2):
        lower_index = 2 * pair_index
        upper_index = lower_index + 1
        lower = float(ordered.iloc[lower_index][frequency_column]) if lower_index < len(ordered) else np.nan
        upper = float(ordered.iloc[upper_index][frequency_column]) if upper_index < len(ordered) else np.nan
        rows.append(
            {
                "pair_index": pair_index + 1,
                f"{output_prefix}_lower_ghz": lower,
                f"{output_prefix}_upper_ghz": upper,
                f"{output_prefix}_center_ghz": 0.5 * (lower + upper) if np.isfinite(lower) and np.isfinite(upper) else np.nan,
                f"{output_prefix}_split_mhz": 1000.0 * (upper - lower) if np.isfinite(lower) and np.isfinite(upper) else np.nan,
            }
        )
    return pd.DataFrame(rows)


bare_pairs = bare_pair_rows()
s21_pairs = two_by_two_modes(full_s21_vf_modes, "s21_vf_dip_ghz", "s21")
s11_pairs = two_by_two_modes(full_vf_modes, "s11_vf_dip_ghz", "s11")
full_pair_assignment = pd.concat(
    [
        pd.Series(np.arange(1, len(bare_pairs) + 1), name="pair_index"),
        bare_pairs,
        s21_pairs.drop(columns=["pair_index"]).reindex(range(len(bare_pairs))),
        s11_pairs.drop(columns=["pair_index"]).reindex(range(len(bare_pairs))),
    ],
    axis=1,
)
full_pair_assignment["s21_center_error_vs_slot_mhz"] = 1000.0 * (
    full_pair_assignment["s21_center_ghz"] - full_pair_assignment["slot_target_ghz"]
)
full_pair_assignment["s11_center_error_vs_slot_mhz"] = 1000.0 * (
    full_pair_assignment["s11_center_ghz"] - full_pair_assignment["slot_target_ghz"]
)
full_pair_assignment["bare_pair_low_ghz"] = full_pair_assignment[
    ["bare_filter_like_ghz", "bare_readout_like_ghz"]
].min(axis=1)
full_pair_assignment["bare_pair_high_ghz"] = full_pair_assignment[
    ["bare_filter_like_ghz", "bare_readout_like_ghz"]
].max(axis=1)
full_pair_assignment["bare_pair_width_mhz"] = 1000.0 * (
    full_pair_assignment["bare_pair_high_ghz"] - full_pair_assignment["bare_pair_low_ghz"]
)
full_pair_assignment["bare_gap_to_previous_mhz"] = 1000.0 * (
    full_pair_assignment["bare_pair_low_ghz"] - full_pair_assignment["bare_pair_high_ghz"].shift(1)
)
full_pair_assignment["bare_gap_to_next_mhz"] = 1000.0 * (
    full_pair_assignment["bare_pair_low_ghz"].shift(-1) - full_pair_assignment["bare_pair_high_ghz"]
)
full_pair_assignment["bare_range_overlap_with_previous"] = (
    full_pair_assignment["bare_gap_to_previous_mhz"] <= 0.0
).fillna(False)
full_pair_assignment["bare_range_overlap_with_next"] = (
    full_pair_assignment["bare_gap_to_next_mhz"] <= 0.0
).fillna(False)
full_pair_assignment["bare_range_isolated_ok"] = ~(
    full_pair_assignment["bare_range_overlap_with_previous"]
    | full_pair_assignment["bare_range_overlap_with_next"]
)
assignment_valid = bool(full_pair_assignment["bare_range_isolated_ok"].all())
full_pair_assignment["pair_assignment_basis"] = (
    "valid: hybridized coupled-pair intervals are isolated; use intervals as ownership guard bands, not blind sorted full-mode pairing"
    if assignment_valid
    else "invalid: adjacent hybridized coupled-pair intervals overlap; redesign before fitting full shared-readout modes"
)
_ = display_table(full_pair_assignment, precision=5)


def plot_pair_assignment_overlay() -> Path:
    row = full_manifest.iloc[0]
    fit = vector_fit_s21(Path(row["trace_csv"]), n_complex_poles=14)
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=fit["frequency_ghz"],
            y=np.abs(fit["s21"]),
            mode="markers",
            marker={"size": 4, "color": "#636EFA"},
            name="HB raw |S21|",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=fit["frequency_ghz"],
            y=np.abs(fit["s21_vf"]),
            mode="lines",
            line={"dash": "dash", "color": "#EF553B"},
            name="VF |S21|",
        )
    )
    fig.update_layout(
        title="Full shared-readout S21 vector-fit check",
        xaxis_title="Frequency (GHz)",
        yaxis_title="|S21|",
    )
    return write_plotly_png(fig, PLOT_DIR / "d3_full_s21_pair_assignment_overlay.png")


pair_assignment_plot = plot_pair_assignment_overlay()
_ = display_images([pair_assignment_plot])


# %% [markdown]
# ## Calibrated J-Fit Handoff
#
# This notebook stops after shared-readout vector-fit and mode-ownership
# diagnostics. It does not run a local `$J$` fit or publish `$J$` evidence. The
# reusable calibrated complex-`$S_{21}$` API remains available to a future D3
# evaluator only after its Human-owned condition manifest is approved.


# %%
bare_ownership_modes.to_csv(BARE_MODES_CSV, index=False)
intrinsic_z21_modes.to_csv(INTRINSIC_Z21_CSV, index=False)
intrinsic_z21_pair_summary.to_csv(INTRINSIC_Z21_PAIR_SUMMARY_CSV, index=False)
full_vf_summary.to_csv(FULL_VF_SUMMARY_CSV, index=False)
full_vf_modes.to_csv(FULL_VF_MODES_CSV, index=False)
full_s21_vf_summary.to_csv(FULL_S21_VF_SUMMARY_CSV, index=False)
full_s21_vf_modes.to_csv(FULL_S21_VF_MODES_CSV, index=False)
full_pair_assignment.to_csv(FULL_PAIR_ASSIGNMENT_CSV, index=False)

print(f"wrote {BARE_MODES_CSV}")
print(f"wrote {INTRINSIC_Z21_CSV}")
print(f"wrote {INTRINSIC_Z21_PAIR_SUMMARY_CSV}")
print(f"wrote {FULL_VF_SUMMARY_CSV}")
print(f"wrote {FULL_VF_MODES_CSV}")
print(f"wrote {FULL_S21_VF_SUMMARY_CSV}")
print(f"wrote {FULL_S21_VF_MODES_CSV}")
print(f"wrote {FULL_PAIR_ASSIGNMENT_CSV}")


# %%
assert not bare_ownership_modes.empty
assert not intrinsic_z21_modes.empty
assert not intrinsic_z21_pair_summary.empty
assert set(full_vf_summary["target_set_id"]) == {"d3"}
assert not full_vf_modes.empty
assert not full_s21_vf_summary.empty
assert not full_s21_vf_modes.empty
assert len(full_pair_assignment) == len(selected_designs)
assert full_pair_assignment["bare_range_isolated_ok"].notna().all()
