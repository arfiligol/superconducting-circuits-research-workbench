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
#   kernelspec:
#     display_name: Python 3 (ipykernel)
#     language: python
#     name: python3
# ---

# %% [markdown]
# # D3 five-slot $J=5$ MHz, $\kappa_p=20$ MHz theory first
#
# This notebook evaluates the canonical reduced readout--filter (RP)
# input--output formula before any CPW or physical-geometry calibration.  The
# five slots retain the established bare targets
# $f_r=f_{slot}-1$ MHz and $f_p=f_{slot}+1$ MHz, with $\kappa_r=0$.
#
# Under the $e^{-i\omega t}$ convention,
#
# $$
# \chi_{pp}(f)=\frac{\zeta_r}
# {\zeta_r\zeta_p+J^2},\qquad
# S_{21}(f)=1-\frac{\kappa_p}{2}\chi_{pp}(f),
# $$
#
# where $\zeta_m=\kappa_m/2+i(f_m-f)$.  A common factor of $2\pi$
# cancels because every frequency and rate is expressed in the same unit.

# %%
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


def find_workbench(start: Path) -> Path:
    """Return the Circuit Workbench root containing this notebook."""
    for candidate in (start, *start.parents):
        if (candidate / "notebooks/python/11_d3_five_slot_j5_k20_theory.py").is_file():
            return candidate
    raise FileNotFoundError("Open this notebook from inside Circuit Workbench.")


def ideal_hanger_s21(
    frequency_hz: np.ndarray,
    *,
    fr_hz: float,
    fp_hz: float,
    j_hz: float,
    kappa_r_hz: float,
    kappa_p_hz: float,
) -> np.ndarray:
    """Return the canonical two-mode ideal-hanger transmission."""
    zeta_r = kappa_r_hz / 2 + 1j * (fr_hz - frequency_hz)
    zeta_p = kappa_p_hz / 2 + 1j * (fp_hz - frequency_hz)
    chi_pp = zeta_r / (zeta_r * zeta_p + j_hz**2)
    return 1 - (kappa_p_hz / 2) * chi_pp


def rp_poles(
    *,
    fr_hz: float,
    fp_hz: float,
    j_hz: float,
    kappa_r_hz: float,
    kappa_p_hz: float,
) -> np.ndarray:
    """Return poles as complex frequencies, with linewidth = -2 Im(pole)."""
    effective_matrix = np.array(
        [
            [fr_hz - 0.5j * kappa_r_hz, j_hz],
            [j_hz, fp_hz - 0.5j * kappa_p_hz],
        ],
        dtype=complex,
    )
    poles = np.linalg.eigvals(effective_matrix)
    return poles[np.argsort(poles.real)]


WORKBENCH_ROOT = find_workbench(Path.cwd().resolve())
ARTIFACT_ROOT = WORKBENCH_ROOT / "build/research/d3_five_slot_j5_k20_theory"
FIGURE_ROOT = ARTIFACT_ROOT / "figures"
FIGURE_ROOT.mkdir(parents=True, exist_ok=True)

SLOTS_GHZ = np.array([5.76, 5.88, 6.00, 6.12, 6.24])
J_HZ = 5e6
KAPPA_R_HZ = 0.0
KAPPA_P_HZ = 20e6
FR_OFFSET_HZ = -1e6
FP_OFFSET_HZ = 1e6

# %% [markdown]
# ## Open-system poles
#
# At zero detuning the dissipative exceptional-point boundary is
# $J_{EP}=|\kappa_p-\kappa_r|/4=5$ MHz.  The requested target therefore sits
# exactly on that boundary before applying the retained 2 MHz bare detuning.

# %%
rows: list[dict[str, float]] = []
for slot_ghz in SLOTS_GHZ:
    center_hz = slot_ghz * 1e9
    fr_hz = center_hz + FR_OFFSET_HZ
    fp_hz = center_hz + FP_OFFSET_HZ
    pole_1, pole_2 = rp_poles(
        fr_hz=fr_hz,
        fp_hz=fp_hz,
        j_hz=J_HZ,
        kappa_r_hz=KAPPA_R_HZ,
        kappa_p_hz=KAPPA_P_HZ,
    )
    zero_1_hz, zero_2_hz = np.linalg.eigvalsh(
        np.array([[fr_hz, J_HZ], [J_HZ, fp_hz]], dtype=float)
    )
    linewidth_1_hz = -2 * pole_1.imag
    linewidth_2_hz = -2 * pole_2.imag
    rows.append(
        {
            "Slot (GHz)": slot_ghz,
            "f_r bare (GHz)": fr_hz / 1e9,
            "f_p bare (GHz)": fp_hz / 1e9,
            "Pole 1 (GHz)": pole_1.real / 1e9,
            "Pole 1 linewidth (MHz)": linewidth_1_hz / 1e6,
            "Pole 2 (GHz)": pole_2.real / 1e9,
            "Pole 2 linewidth (MHz)": linewidth_2_hz / 1e6,
            "Pole-frequency split (MHz)": (pole_2.real - pole_1.real) / 1e6,
            "Transmission zero 1 (GHz)": zero_1_hz / 1e9,
            "Transmission zero 2 (GHz)": zero_2_hz / 1e9,
            "Zero/dip split (MHz)": (zero_2_hz - zero_1_hz) / 1e6,
            "Linewidth sum (MHz)": (linewidth_1_hz + linewidth_2_hz) / 1e6,
        }
    )

pole_table = pd.DataFrame(rows)
pole_table_path = ARTIFACT_ROOT / "five_slot_rp_theory_poles.csv"
pole_table.to_csv(pole_table_path, index=False)

assert np.allclose(pole_table["Linewidth sum (MHz)"], KAPPA_P_HZ / 1e6, atol=1e-9)
assert np.all(pole_table["Pole-frequency split (MHz)"] > 0)
pole_table

# %% [markdown]
# ## Ideal-hanger response

# %%
plt.rcParams.update(
    {
        "figure.dpi": 120,
        "savefig.dpi": 180,
        "axes.grid": True,
        "grid.alpha": 0.22,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "font.size": 9,
    }
)

figure, axes = plt.subplots(len(SLOTS_GHZ), 1, figsize=(10.5, 12.5), constrained_layout=True)
for axis, row in zip(axes, rows, strict=True):
    slot_ghz = row["Slot (GHz)"]
    center_hz = slot_ghz * 1e9
    frequency_hz = np.linspace(center_hz - 50e6, center_hz + 50e6, 2401)
    s21 = ideal_hanger_s21(
        frequency_hz,
        fr_hz=center_hz + FR_OFFSET_HZ,
        fp_hz=center_hz + FP_OFFSET_HZ,
        j_hz=J_HZ,
        kappa_r_hz=KAPPA_R_HZ,
        kappa_p_hz=KAPPA_P_HZ,
    )
    assert np.all(np.isfinite(s21))
    axis.plot(frequency_hz / 1e9, np.abs(s21), color="#0072B2", linewidth=1.8)
    axis.axvline(
        row["Pole 1 (GHz)"], color="#D1495B", linestyle="--", linewidth=1,
        label="Re(open pole)" if axis is axes[0] else None,
    )
    axis.axvline(row["Pole 2 (GHz)"], color="#D1495B", linestyle="--", linewidth=1)
    axis.axvline(
        row["Transmission zero 1 (GHz)"], color="#4C566A", linestyle=":", linewidth=1,
        label="transmission zero" if axis is axes[0] else None,
    )
    axis.axvline(
        row["Transmission zero 2 (GHz)"], color="#4C566A", linestyle=":", linewidth=1
    )
    axis.set_title(
        f"{slot_ghz:.2f} GHz — theory poles "
        f"{row['Pole 1 (GHz)']:.6f} / {row['Pole 1 linewidth (MHz)']:.2f} MHz, "
        f"{row['Pole 2 (GHz)']:.6f} / {row['Pole 2 linewidth (MHz)']:.2f} MHz"
    )
    axis.set_ylabel(r"$|S_{21}|$")
    axis.set_xlim(slot_ghz - 0.05, slot_ghz + 0.05)

axes[-1].set_xlabel("Frequency (GHz)")
axes[0].legend(frameon=False, ncol=2, loc="lower left")
figure.suptitle(
    r"Canonical RP ideal hanger: $J=5$ MHz, $\kappa_p=20$ MHz, "
    r"$f_r=f_{slot}-1$ MHz, $f_p=f_{slot}+1$ MHz",
    fontsize=12,
)
figure_path = FIGURE_ROOT / "five_slot_rp_theory_s21.png"
figure.savefig(figure_path, bbox_inches="tight")
figure

# %% [markdown]
# The red dashed lines are the real parts of the two open-system poles.  The
# response is near the exceptional-point boundary, so the open-pole frequency
# split is only 4.70 MHz and the linewidths are highly unequal.  The two ideal
# transmission zeros remain 10.20 MHz apart.  The complex poles and the zeros
# must therefore be compared separately when calibrating the full geometry.
