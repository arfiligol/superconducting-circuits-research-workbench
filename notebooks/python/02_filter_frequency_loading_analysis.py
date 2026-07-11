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
# # 02 Filter-Loading Notch-Fit Evidence
#
# This notebook owns the thin, review-facing analysis of the fine complex
# $S_{21}$ traces produced by `02_filter_frequency_loading_calibration.jl`. It
# validates the source manifest, calls the repository-owned notch fitter, and
# publishes fit and residual evidence. It does **not** own the fitting model,
# acceptance thresholds, bare-frequency regression, linewidth promotion, or
# resonator-length correction.
#
# Read the canonical model before reviewing the output:
#
# - [Notch Resonator Complex S21 Fit](https://github.com/arfiligol/SCQ_Design/blob/main/docs/knowledge/network-modeling/notch-resonator-complex-s21-fit.qmd)
# - [Network Trace Views](https://github.com/arfiligol/SCQ_Design/blob/main/docs/knowledge/network-modeling/network-trace-views.qmd)
# - [Vector Fitting and Passivity](https://github.com/arfiligol/SCQ_Design/blob/main/docs/knowledge/network-modeling/vector-fitting-passivity.qmd)
#
# A numerical solver result is evidence for Human review, not an acceptance
# decision. The sampled magnitude minimum is retained only as an initializer
# diagnostic and is never promoted as the resonant frequency.

# %%
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from d3_design_config import load_d3_design_config, variant_suffix
from plotly.subplots import make_subplots
from superconducting_circuits_analysis.application.analysis.fitting.s_parameters import (
    fit_complex_s21_notch,
)

try:
    from IPython import get_ipython
    from IPython.display import display as _ipython_display

    ipython_display = _ipython_display if get_ipython() is not None else None
except ImportError:  # pragma: no cover - notebook display convenience only.
    ipython_display = None


# %%
OUTPUT_ROOT = Path(
    "/home/ili/Githubs/SCQ_Design/orpen_sc_pdk/build/simulation/circuit/"
    "intrinsic_purcell_filter/d3_intrinsic_purcell_filter_design"
)
D3_CONFIG = load_d3_design_config()
DESIGN_VARIANT_ID = str(D3_CONFIG["active_design_variant_id"])
VARIANT_SUFFIX = variant_suffix(DESIGN_VARIANT_ID)
CALIBRATION_ROOT = OUTPUT_ROOT / f"filter_frequency_loading_calibration{VARIANT_SUFFIX}"

FINE_S21_MANIFEST_CSV = CALIBRATION_ROOT / "d3_filter_loading_fine_s21_manifest.csv"
FIT_EVIDENCE_CSV = CALIBRATION_ROOT / "d3_filter_loading_notch_fit_evidence.csv"
FIT_RESIDUALS_CSV = CALIBRATION_ROOT / "d3_filter_loading_notch_fit_residuals.csv"

EXPECTED_TRACE_COUNT = 90
GHz = 1.0e9

MANIFEST_REQUIRED_COLUMNS = {
    "id",
    "case_id",
    "model_case_id",
    "model_case_label",
    "target_set_id",
    "target_set_name",
    "slot_target_ghz",
    "filter_to_line_capacitance_fF",
    "lc_impedance_ohm",
    "lc_velocity_m_per_s",
    "lp_short_um",
    "lc_um",
    "lp_open_um",
    "lp_total_um",
    "trace_csv",
    "hb_intent_ok",
    "netlist_rows",
    "center_frequency_ghz",
    "kappa_loaded_over_2pi_mhz",
    "fine_half_width_mhz",
    "fine_step_mhz",
}
MANIFEST_TEXT_COLUMNS = (
    "id",
    "case_id",
    "model_case_id",
    "model_case_label",
    "target_set_id",
    "target_set_name",
    "trace_csv",
)
MANIFEST_NUMERIC_COLUMNS = (
    "slot_target_ghz",
    "filter_to_line_capacitance_fF",
    "lc_impedance_ohm",
    "lc_velocity_m_per_s",
    "lp_short_um",
    "lc_um",
    "lp_open_um",
    "lp_total_um",
    "netlist_rows",
    "center_frequency_ghz",
    "kappa_loaded_over_2pi_mhz",
    "fine_half_width_mhz",
    "fine_step_mhz",
)
MANIFEST_INTEGER_COLUMNS = ("netlist_rows",)
TRACE_NUMERIC_COLUMNS = (
    "frequency_ghz",
    "s21_re",
    "s21_im",
)
TRACE_REQUIRED_COLUMNS = set(TRACE_NUMERIC_COLUMNS)

PHYSICAL_PARAMETER_COLUMNS = (
    "fr_hz",
    "ql",
    "qc_real",
    "qc_imag",
    "qc_mag",
    "inverse_qi",
    "qi",
    "qi_status",
    "amplitude",
    "phase_rad",
    "delay_s",
    "phase_reference_hz",
    "phase_at_reference_rad",
)
# %% [markdown]
# ## Source Contract
#
# The current fine manifest is the complete input authority. The analysis does
# not discover additional files from the trace directory, so unreferenced old
# runs cannot silently enter the evidence set.

# %%
def require_file(path: Path) -> Path:
    if not path.is_file():
        raise FileNotFoundError(f"required file is missing: {path}")
    return path


def require_columns(frame: pd.DataFrame, required: set[str], *, source: Path) -> None:
    missing = sorted(required - set(frame.columns))
    if missing:
        raise ValueError(f"{source} is missing required columns: {missing}")


def validate_manifest_types(frame: pd.DataFrame, *, source: Path) -> None:
    hb_intent = frame["hb_intent_ok"]
    if (
        not pd.api.types.is_bool_dtype(hb_intent.dtype)
        or hb_intent.isna().any()
        or not bool(hb_intent.all())
    ):
        raise ValueError(
            f"{source} hb_intent_ok must have Boolean dtype and contain only true values"
        )

    for column in MANIFEST_TEXT_COLUMNS:
        values = frame[column]
        if not pd.api.types.is_string_dtype(values.dtype) or not values.map(
            lambda value: isinstance(value, str) and bool(value.strip())
        ).all():
            raise ValueError(f"{source} {column} must contain only nonempty strings")

    for column in MANIFEST_NUMERIC_COLUMNS:
        values = frame[column]
        if pd.api.types.is_bool_dtype(values.dtype) or not pd.api.types.is_numeric_dtype(
            values.dtype
        ):
            raise ValueError(f"{source} {column} must have non-Boolean numeric dtype")
        if not np.all(np.isfinite(values.to_numpy(dtype=float, na_value=np.nan))):
            raise ValueError(f"{source} {column} must contain only finite values")

    for column in MANIFEST_INTEGER_COLUMNS:
        if not pd.api.types.is_integer_dtype(frame[column].dtype):
            raise ValueError(f"{source} {column} must have exact integer dtype")


def read_trace(path: Path) -> tuple[np.ndarray, np.ndarray]:
    frame = pd.read_csv(require_file(path))
    require_columns(frame, TRACE_REQUIRED_COLUMNS, source=path)
    for column in TRACE_NUMERIC_COLUMNS:
        values = frame[column]
        if pd.api.types.is_bool_dtype(values.dtype) or not pd.api.types.is_numeric_dtype(
            values.dtype
        ):
            raise ValueError(f"{path} {column} must have non-Boolean numeric dtype")
    numeric = frame[list(TRACE_NUMERIC_COLUMNS)].to_numpy(dtype=float)
    if len(numeric) < 3 or not np.all(np.isfinite(numeric)):
        raise ValueError(f"{path} must contain at least three finite trace samples")
    frequency_hz = numeric[:, 0] * GHz
    if not np.all(frequency_hz > 0.0) or not np.all(np.diff(frequency_hz) > 0.0):
        raise ValueError(f"{path} frequency_ghz must be positive and strictly increasing")
    return frequency_hz, numeric[:, 1] + 1j * numeric[:, 2]


def atomic_write_csv(frame: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", newline="") as stream:
        frame.to_csv(stream, index=False)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)


def display_table(frame: pd.DataFrame, *, precision: int = 6) -> None:
    table = frame.copy()
    numeric_columns = table.select_dtypes(include=[np.number]).columns
    table.loc[:, numeric_columns] = table.loc[:, numeric_columns].round(precision)
    if ipython_display is not None:
        ipython_display(table)
    else:
        print(table.to_string(index=False))


# %%
manifest_path = require_file(FINE_S21_MANIFEST_CSV)
manifest_sha256 = hashlib.sha256(manifest_path.read_bytes()).hexdigest()
manifest = pd.read_csv(manifest_path)
require_columns(manifest, MANIFEST_REQUIRED_COLUMNS, source=manifest_path)

if len(manifest) != EXPECTED_TRACE_COUNT:
    raise ValueError(
        f"{manifest_path} must contain exactly {EXPECTED_TRACE_COUNT} rows; found {len(manifest)}"
    )
validate_manifest_types(manifest, source=manifest_path)
if manifest["trace_csv"].duplicated().any():
    raise ValueError(f"{manifest_path} contains duplicate trace_csv identities")
identity_columns = ["model_case_id", "slot_target_ghz", "filter_to_line_capacitance_fF"]
if manifest.duplicated(identity_columns).any():
    raise ValueError(f"{manifest_path} contains duplicate case/slot/Cext identities")

manifest = manifest.sort_values(identity_columns, kind="stable").reset_index(drop=False)
manifest = manifest.rename(columns={"index": "source_manifest_zero_based_row"})
manifest["source_manifest_row_number"] = manifest["source_manifest_zero_based_row"] + 2
manifest["fit_id"] = [f"nf{index:03d}" for index in range(1, len(manifest) + 1)]


# %% [markdown]
# ## Shared Complex-Notch Fits
#
# An endpoint magnitude minimum is an exact structural failure: the selected
# window did not bracket the candidate notch. Interior traces are passed once to
# the shared application API. No local estimator, fallback fitter, residual
# threshold, or acceptance flag exists here.

# %%
def evidence_base(row: Any, *, frequency_hz: np.ndarray, s21: np.ndarray) -> dict[str, object]:
    raw_minimum_index = int(np.argmin(np.abs(s21)))
    return {
        "fit_id": row.fit_id,
        "design_variant_id": DESIGN_VARIANT_ID,
        "source_manifest_csv": str(manifest_path),
        "source_manifest_sha256": manifest_sha256,
        "source_manifest_row_number": int(row.source_manifest_row_number),
        "source_design_id": row.id,
        "case_id": row.case_id,
        "model_case_id": row.model_case_id,
        "model_case_label": row.model_case_label,
        "target_set_id": row.target_set_id,
        "target_set_name": row.target_set_name,
        "slot_target_ghz": float(row.slot_target_ghz),
        "filter_to_line_capacitance_fF": float(row.filter_to_line_capacitance_fF),
        "lc_impedance_ohm": float(row.lc_impedance_ohm),
        "lc_velocity_m_per_s": float(row.lc_velocity_m_per_s),
        "lp_short_um": float(row.lp_short_um),
        "lc_um": float(row.lc_um),
        "lp_open_um": float(row.lp_open_um),
        "lp_total_um": float(row.lp_total_um),
        "hb_intent_ok": bool(row.hb_intent_ok),
        "netlist_rows": int(row.netlist_rows),
        "source_trace_csv": str(row.trace_csv),
        "source_phasor_convention": "undeclared",
        "source_reference_plane": "undeclared",
        "source_center_frequency_ghz": float(row.center_frequency_ghz),
        "source_bootstrap_kappa_over_2pi_mhz": float(row.kappa_loaded_over_2pi_mhz),
        "source_fine_half_width_mhz": float(row.fine_half_width_mhz),
        "source_fine_step_mhz": float(row.fine_step_mhz),
        "fit_window_start_hz": float(frequency_hz[0]),
        "fit_window_end_hz": float(frequency_hz[-1]),
        "trace_sample_count": len(frequency_hz),
        "raw_minimum_frequency_hz": float(frequency_hz[raw_minimum_index]),
        "raw_minimum_index": raw_minimum_index,
        "raw_minimum_is_endpoint": raw_minimum_index in (0, len(frequency_hz) - 1),
        "raw_minimum_s21_abs": float(abs(s21[raw_minimum_index])),
    }


def returned_evidence(result: dict[str, Any]) -> dict[str, object]:
    params = result["params"]
    optimizer = result["optimizer"]
    metrics = result["metrics"]
    return {
        **{name: params[name] for name in PHYSICAL_PARAMETER_COLUMNS},
        "initial_guess_json": json.dumps(result["initial_guess"], sort_keys=True),
        "fit_settings_json": json.dumps(result["fit_settings"], sort_keys=True),
        "optimizer_status": optimizer["status"],
        "optimizer_message": optimizer["message"],
        "optimizer_nfev": optimizer["nfev"],
        "optimizer_njev": optimizer["njev"],
        "optimizer_optimality": optimizer["optimality"],
        "optimizer_active_mask_json": json.dumps(optimizer["active_mask"]),
        "complex_s21_rmse": metrics["complex_s21_rmse"],
        "least_squares_cost": metrics["least_squares_cost"],
    }


evidence_rows: list[dict[str, object]] = []
residual_rows: list[dict[str, object]] = []
plot_inputs: dict[str, tuple[np.ndarray, np.ndarray, np.ndarray | None]] = {}

for row in manifest.itertuples(index=False):
    trace_path = Path(row.trace_csv)
    frequency_hz, s21 = read_trace(trace_path)
    evidence = evidence_base(row, frequency_hz=frequency_hz, s21=s21)
    plot_inputs[row.fit_id] = (frequency_hz, s21, None)

    if evidence["raw_minimum_is_endpoint"]:
        evidence.update(
            evidence_status="structural_reject",
            evidence_reason="sampled_s21_minimum_is_fit_window_endpoint",
            fr_inside_window=None,
        )
        evidence_rows.append(evidence)
        continue

    result = fit_complex_s21_notch(
        frequency_hz,
        s21.real,
        s21.imag,
        fit_window_hz=(float(frequency_hz[0]), float(frequency_hz[-1])),
    )
    if result["status"] != "success":
        if result["status"] != "failed":
            raise ValueError(
                f"shared notch fitter returned unsupported status: {result['status']!r}"
            )
        evidence.update(
            evidence_status="numerical_failed",
            evidence_reason=str(result["reason"]),
            fr_inside_window=None,
        )
        evidence_rows.append(evidence)
        continue

    returned = returned_evidence(result)
    returned_window = [float(value) for value in result["fit_window_hz"]]
    if returned_window != [float(frequency_hz[0]), float(frequency_hz[-1])]:
        raise ValueError(f"shared notch fitter changed the selected window for {trace_path}")
    fitted_frequency_hz = np.asarray(result["fit_curve"]["frequency_hz"], dtype=float)
    model_s21 = np.asarray(result["fit_curve"]["s21_real"], dtype=float) + 1j * np.asarray(
        result["fit_curve"]["s21_imag"], dtype=float
    )
    if not np.array_equal(fitted_frequency_hz, frequency_hz) or len(model_s21) != len(s21):
        raise ValueError(f"shared notch fit curve does not match source grid for {trace_path}")

    fr_hz = float(returned["fr_hz"])
    fr_inside_window = float(frequency_hz[0]) <= fr_hz <= float(frequency_hz[-1])
    evidence.update(returned)
    evidence.update(
        evidence_status="numerical_success" if fr_inside_window else "structural_reject",
        evidence_reason=(
            "shared_notch_fit_completed"
            if fr_inside_window
            else "fitted_resonance_frequency_is_outside_fit_window"
        ),
        fr_inside_window=fr_inside_window,
    )
    evidence_rows.append(evidence)
    plot_inputs[row.fit_id] = (frequency_hz, s21, model_s21)

    if not fr_inside_window:
        continue
    residual = model_s21 - s21
    for index in range(len(frequency_hz)):
        residual_rows.append(
            {
                "fit_id": row.fit_id,
                "frequency_hz": float(frequency_hz[index]),
                "data_s21_real": float(s21[index].real),
                "data_s21_imag": float(s21[index].imag),
                "data_s21_abs": float(abs(s21[index])),
                "model_s21_real": float(model_s21[index].real),
                "model_s21_imag": float(model_s21[index].imag),
                "model_s21_abs": float(abs(model_s21[index])),
                "residual_s21_real": float(residual[index].real),
                "residual_s21_imag": float(residual[index].imag),
                "residual_s21_abs": float(abs(residual[index])),
            }
        )

evidence = pd.DataFrame(evidence_rows).sort_values("fit_id", kind="stable")
residuals = pd.DataFrame(residual_rows)


# %% [markdown]
# ## Bounded Human Review Surface
#
# The table shows at most three deterministic rows from each evidence category.
# Numerical successes are separated by exact $Q_i$ interpretation status. The
# plots show the first `fit_id` in each category. Selection is categorical, not
# based on an agent-chosen quality cutoff.

# %%
review_surface = evidence.copy()
review_surface["review_category"] = review_surface["evidence_status"]
success_mask = review_surface["evidence_status"] == "numerical_success"
review_surface.loc[success_mask, "review_category"] = (
    "numerical_success/" + review_surface.loc[success_mask, "qi_status"].astype(str)
)
review_categories = [
    category
    for category in ("structural_reject", "numerical_failed")
    if category in set(review_surface["review_category"])
]
review_categories.extend(
    sorted(
        category
        for category in set(review_surface.loc[success_mask, "review_category"])
    )
)
print(review_surface["review_category"].value_counts().reindex(review_categories).to_string())

bounded_summary = pd.concat(
    [
        review_surface[review_surface["review_category"] == category].head(3)
        for category in review_categories
    ],
    ignore_index=True,
)
display_table(
    bounded_summary[
        [
            "fit_id",
            "model_case_id",
            "slot_target_ghz",
            "filter_to_line_capacitance_fF",
            "review_category",
            "evidence_status",
            "evidence_reason",
            "raw_minimum_frequency_hz",
            "fr_hz",
            "complex_s21_rmse",
            "qi_status",
        ]
    ]
)


# %%
def representative_figure(
    fit_id: str,
    category: str,
    frequency_hz: np.ndarray,
    data_s21: np.ndarray,
    model_s21: np.ndarray | None,
) -> go.Figure:
    figure = make_subplots(rows=1, cols=2, subplot_titles=("Magnitude", "Complex plane"))
    figure.add_trace(
        go.Scatter(x=frequency_hz / GHz, y=np.abs(data_s21), mode="markers", name="data"),
        row=1,
        col=1,
    )
    figure.add_trace(
        go.Scatter(x=data_s21.real, y=data_s21.imag, mode="markers", name="data IQ"),
        row=1,
        col=2,
    )
    if model_s21 is not None:
        figure.add_trace(
            go.Scatter(x=frequency_hz / GHz, y=np.abs(model_s21), mode="lines", name="model"),
            row=1,
            col=1,
        )
        figure.add_trace(
            go.Scatter(x=model_s21.real, y=model_s21.imag, mode="lines", name="model IQ"),
            row=1,
            col=2,
        )
    figure.update_layout(title=f"{fit_id}: {category}", width=1100, height=480)
    figure.update_xaxes(title_text="Frequency (GHz)", row=1, col=1)
    figure.update_yaxes(title_text="|S21|", row=1, col=1)
    figure.update_xaxes(title_text="Re(S21)", row=1, col=2)
    figure.update_yaxes(title_text="Im(S21)", row=1, col=2)
    return figure


for category in review_categories:
    candidates = review_surface[review_surface["review_category"] == category].sort_values(
        "fit_id"
    )
    if candidates.empty:
        continue
    representative_id = str(candidates.iloc[0]["fit_id"])
    figure = representative_figure(
        representative_id, category, *plot_inputs[representative_id]
    )
    if ipython_display is not None:
        ipython_display(figure)
    else:
        print(f"representative plot: {representative_id} ({category})")


# %% [markdown]
# ## Publish Candidate Evidence, Then Stop
#
# These files deliberately contain no acceptance field. The notebook verifies
# row identity and residual references after durable writes, then stops before
# any bare-frequency, $C_{ext}$, linewidth, or length-correction promotion.

# %%
if len(evidence) != EXPECTED_TRACE_COUNT or evidence["fit_id"].nunique() != EXPECTED_TRACE_COUNT:
    raise AssertionError("notch-fit evidence must contain exactly 90 unique fit identities")

numerical_success_ids = set(
    evidence.loc[evidence["evidence_status"] == "numerical_success", "fit_id"]
)
residual_ids = set(residuals["fit_id"]) if not residuals.empty else set()
if residual_ids != numerical_success_ids:
    raise AssertionError("residual fit_ids must exactly match numerical_success evidence rows")

expected_residual_counts = evidence.loc[
    evidence["evidence_status"] == "numerical_success", ["fit_id", "trace_sample_count"]
].set_index("fit_id")["trace_sample_count"]
actual_residual_counts = (
    residuals.groupby("fit_id").size() if not residuals.empty else pd.Series(dtype=int)
)
if not actual_residual_counts.equals(expected_residual_counts.astype(int)):
    raise AssertionError("residual row counts must match each successful source trace")

atomic_write_csv(evidence, FIT_EVIDENCE_CSV)
atomic_write_csv(residuals, FIT_RESIDUALS_CSV)

written_evidence = pd.read_csv(FIT_EVIDENCE_CSV)
written_residuals = pd.read_csv(FIT_RESIDUALS_CSV)
if len(written_evidence) != EXPECTED_TRACE_COUNT or set(written_evidence["fit_id"]) != set(
    evidence["fit_id"]
):
    raise AssertionError("written notch-fit evidence failed identity verification")
if set(written_residuals["fit_id"]) != numerical_success_ids:
    raise AssertionError("written residual evidence failed referential-integrity verification")

endpoint_reject_count = int(evidence["raw_minimum_is_endpoint"].sum())
print(f"wrote {FIT_EVIDENCE_CSV}")
print(f"wrote {FIT_RESIDUALS_CSV}")

raise NotImplementedError(
    "Notch-fit evidence was published, but promotion is blocked pending Human decisions on "
    f"the {endpoint_reject_count} endpoint-window rescans, isolated-notch ownership, source "
    "phasor/reference-plane metadata, the Cext regression subset, and any acceptance thresholds."
)
