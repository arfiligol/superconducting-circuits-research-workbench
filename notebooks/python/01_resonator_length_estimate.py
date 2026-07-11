# %% [markdown]
# # 01 Resonator Length Estimate
#
# This notebook is the design-math source of truth for the first D3 length
# table. It reads the legacy RLGC-named Q2D LC case export, applies the delay-form quarter-wave
# equations, chooses one candidate per target slot, and writes CSV files for
# the Pluto HB notebooks.
#
# Pluto notebooks should read the selected-design CSV and build circuits from
# it. They should not rederive the length formulas.
#
# Canonical knowledge:
#
# - [Multiconductor RLGC Matrices: Basis, Modes, and Physical Meaning](https://github.com/arfiligol/SCQ_Design/blob/main/docs/knowledge/transmission-lines/multiconductor-rlgc-matrix-semantics.qmd)
# - [Baseline Resonator Estimate](https://github.com/arfiligol/SCQ_Design/blob/main/docs/knowledge/transmission-lines/baseline-resonator-estimate.qmd)
# - [Resonator Length Correction Loop](https://github.com/arfiligol/SCQ_Design/blob/main/docs/knowledge/transmission-lines/resonator-length-correction-loop.qmd)
#
# Current Q2D matrix inputs are exploration-only until they pass the canonical
# artifact eligibility gate.

# %%
from __future__ import annotations

import json
from math import sqrt
from pathlib import Path

import numpy as np
import pandas as pd

try:
    from IPython.display import display as ipython_display
except ImportError:  # pragma: no cover - notebook display convenience only.
    ipython_display = None


WORKSPACE_ROOT = Path("/home/ili/Githubs/SCQ_Design")
OUTPUT_ROOT = (
    WORKSPACE_ROOT
    / "orpen_sc_pdk/build/simulation/circuit/intrinsic_purcell_filter/d3_intrinsic_purcell_filter_design"
)
DESIGN_INPUT_DIR = OUTPUT_ROOT / "design_inputs"
CASE_JSON = (
    WORKSPACE_ROOT
    / "orpen_sc_pdk/build/simulation/circuit/intrinsic_purcell_filter/orpen_q2d_rlgc_cases.json"
)
SELECTED_DESIGNS_CSV = DESIGN_INPUT_DIR / "d3_selected_resonator_lengths.csv"
LENGTH_CANDIDATES_CSV = DESIGN_INPUT_DIR / "d3_length_candidates.csv"

UM = 1.0e-6
GHz = 1.0e9


# %% [markdown]
# ## Design Inputs

# %%
SELECTED_CASE_ID = "height7"
TARGET_SET_ID = "d3"
TARGET_SET_NAME = "D3 5.76-6.24 GHz / 120 MHz spacing"
SLOT_TARGETS_GHZ = [5.76, 5.88, 6.0, 6.12, 6.24]
SCAN_START_GHZ = 5.4
SCAN_STOP_GHZ = 6.6

NOTCH_TARGET_GHZ = 4.5
LC_GRID_UM = np.arange(100.0, 320.0 + 1.0e-9, 20.0)
SHORT_SPLIT_GRID = np.arange(0.10, 0.90 + 1.0e-9, 0.05)
MIN_SECTION_LENGTH_UM = 300.0
TOTAL_LENGTH_BOUNDS_UM = (3500.0, 8000.0)


# %% [markdown]
# ## Helpers

# %%
def display_table(frame: pd.DataFrame, *, precision: int = 4) -> pd.DataFrame:
    table = frame.copy()
    numeric_columns = table.select_dtypes(include=[np.number]).columns
    table.loc[:, numeric_columns] = table.loc[:, numeric_columns].round(precision)
    if ipython_display is not None:
        ipython_display(table)
    else:
        print(table.to_string(index=False))
    return table


def load_case(path: Path, case_id: str) -> dict:
    if not path.is_file():
        raise FileNotFoundError(f"missing Q2D case export: {path}")
    cases = json.loads(path.read_text())["cases"]
    matches = [case for case in cases if case["id"] == case_id]
    if len(matches) != 1:
        raise ValueError(f"expected one case {case_id!r}, got {len(matches)}")
    return matches[0]


def solve_lengths_for_slot(case: dict, slot_ghz: float, lc_um: float, short_split: float) -> dict | None:
    single = case["single"]
    mtl = case["mtl"]
    v_single = 1.0 / sqrt(single["l_per_m_h"] * single["c_per_m_f"])
    v_mtl_diag = 1.0 / sqrt(mtl["l_matrix_h_per_m"][0][0] * mtl["c_matrix_f_per_m"][0][0])

    lc_delay_s = lc_um * UM / v_mtl_diag
    tr_s = 1.0 / (4.0 * slot_ghz * GHz)
    tp_s = tr_s
    tn_s = 1.0 / (4.0 * NOTCH_TARGET_GHZ * GHz)
    short_delay_sum_s = tn_s - lc_delay_s
    if short_delay_sum_s <= 0.0:
        return None

    lr_short_delay_s = short_split * short_delay_sum_s
    lp_short_delay_s = (1.0 - short_split) * short_delay_sum_s
    lr_open_delay_s = tr_s - lc_delay_s - lr_short_delay_s
    lp_open_delay_s = tp_s - lc_delay_s - lp_short_delay_s
    if min(lr_short_delay_s, lp_short_delay_s, lr_open_delay_s, lp_open_delay_s) <= 0.0:
        return None

    lr_short_um = lr_short_delay_s * v_single / UM
    lp_short_um = lp_short_delay_s * v_single / UM
    lr_open_um = lr_open_delay_s * v_single / UM
    lp_open_um = lp_open_delay_s * v_single / UM
    lr_total_um = lr_short_um + lc_um + lr_open_um
    lp_total_um = lp_short_um + lc_um + lp_open_um
    if min(lr_short_um, lp_short_um, lr_open_um, lp_open_um) < MIN_SECTION_LENGTH_UM:
        return None
    if not (TOTAL_LENGTH_BOUNDS_UM[0] <= lr_total_um <= TOTAL_LENGTH_BOUNDS_UM[1]):
        return None
    if not (TOTAL_LENGTH_BOUNDS_UM[0] <= lp_total_um <= TOTAL_LENGTH_BOUNDS_UM[1]):
        return None

    analytic_score = (
        abs(short_split - 0.5) / 0.5
        + 0.15 * abs(lc_um - 200.0) / 120.0
        + 0.05 * abs(slot_ghz - 6.0) / 0.5
    )
    return {
        "id": f"{TARGET_SET_ID}_h{round(case['flip_chip_gap_height_um'] * 10):.0f}_s{round(slot_ghz * 100):.0f}_lc{round(lc_um):.0f}_a{round(short_split * 100):.0f}",
        "case_id": case["id"],
        "target_set_id": TARGET_SET_ID,
        "target_set_name": TARGET_SET_NAME,
        "scan_start_ghz": SCAN_START_GHZ,
        "scan_stop_ghz": SCAN_STOP_GHZ,
        "slot_target_ghz": slot_ghz,
        "notch_target_ghz": NOTCH_TARGET_GHZ,
        "lr_open_um": lr_open_um,
        "lr_short_um": lr_short_um,
        "lc_um": lc_um,
        "lp_short_um": lp_short_um,
        "lp_open_um": lp_open_um,
        "lr_total_um": lr_total_um,
        "lp_total_um": lp_total_um,
        "notch_length_um": lr_short_um + lc_um + lp_short_um,
        "short_split": short_split,
        "lr_short_delay_ps": lr_short_delay_s / 1.0e-12,
        "lc_delay_ps": lc_delay_s / 1.0e-12,
        "lp_short_delay_ps": lp_short_delay_s / 1.0e-12,
        "lr_total_delay_ps": tr_s / 1.0e-12,
        "lp_total_delay_ps": tp_s / 1.0e-12,
        "notch_delay_ps": tn_s / 1.0e-12,
        "fr_est_ghz": 1.0 / (4.0 * tr_s) / GHz,
        "fp_est_ghz": 1.0 / (4.0 * tp_s) / GHz,
        "fn_est_ghz": 1.0 / (4.0 * tn_s) / GHz,
        "analytic_score": analytic_score,
    }


# %% [markdown]
# ## Generate Length Candidates

# %%
selected_case = load_case(CASE_JSON, SELECTED_CASE_ID)
candidate_rows = [
    candidate
    for slot_ghz in SLOT_TARGETS_GHZ
    for lc_um in LC_GRID_UM
    for short_split in SHORT_SPLIT_GRID
    if (candidate := solve_lengths_for_slot(selected_case, float(slot_ghz), float(lc_um), float(short_split)))
    is not None
]
candidates = pd.DataFrame(candidate_rows).sort_values(["analytic_score", "slot_target_ghz"])
selected_designs = (
    candidates.sort_values(["slot_target_ghz", "analytic_score"])
    .groupby("slot_target_ghz", as_index=False)
    .head(1)
    .sort_values("slot_target_ghz")
    .reset_index(drop=True)
)

_ = display_table(
    selected_designs[
        [
            "slot_target_ghz",
            "lr_open_um",
            "lr_short_um",
            "lc_um",
            "lp_short_um",
            "lp_open_um",
            "fr_est_ghz",
            "fp_est_ghz",
            "fn_est_ghz",
            "analytic_score",
        ]
    ],
    precision=4,
)


# %% [markdown]
# ## Write Design Inputs

# %%
DESIGN_INPUT_DIR.mkdir(parents=True, exist_ok=True)
candidates.to_csv(LENGTH_CANDIDATES_CSV, index=False)
selected_designs.to_csv(SELECTED_DESIGNS_CSV, index=False)
print(f"wrote {LENGTH_CANDIDATES_CSV}")
print(f"wrote {SELECTED_DESIGNS_CSV}")


# %%
assert len(selected_designs) == len(SLOT_TARGETS_GHZ)
assert set(selected_designs["case_id"]) == {SELECTED_CASE_ID}
assert selected_designs["slot_target_ghz"].tolist() == SLOT_TARGETS_GHZ
assert (selected_designs[["lr_open_um", "lr_short_um", "lc_um", "lp_short_um", "lp_open_um"]] > 0.0).all().all()
