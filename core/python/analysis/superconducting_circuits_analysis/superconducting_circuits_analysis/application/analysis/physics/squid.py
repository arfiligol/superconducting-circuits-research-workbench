"""Ideal symmetric two-junction small-signal SQUID-LC frequency model.

``L_jun`` is the inductance of each identical junction, so this implementation
uses ``L_sq = L_jun / 2``. It does not model external flux, junction asymmetry,
loop inductance, phase-dependent bias, or quantum dynamics.

Canonical Knowledge:
https://github.com/arfiligol/SCQ_Design/blob/main/docs/knowledge/josephson-physics/josephson-current-phase-energy-and-inductance.qmd
https://github.com/arfiligol/SCQ_Design/blob/main/docs/knowledge/josephson-physics/dc-squid-flux-tunability.qmd
"""

from typing import Any

import numpy as np


def calculate_squid_lc_frequency(
    L_jun: float | np.ndarray[Any, np.dtype[np.float64]], Ls_nH: float, C_pF: float
) -> float | np.ndarray[Any, np.dtype[np.float64]]:
    """Calculate an ideal symmetric SQUID-LC small-signal resonance.

    This is a classical LC approximation. ``L_jun`` is each junction's
    small-signal inductance; the two identical branches are placed in parallel.

    Args:
        L_jun: Per-junction small-signal inductance in nH (single value or array)
        Ls_nH: Series inductance in nH
        C_pF: Capacitance in pF

    Returns:
        Frequency in GHz
    """
    # Two identical small-signal junction inductances in parallel.
    L_sq = L_jun / 2.0
    L_tot_nH = L_sq + Ls_nH
    # Avoid division by zero or negative inductance (unphysical but stable for fitting)
    L_tot_nH = np.maximum(L_tot_nH, 1e-15)

    L_tot_H = L_tot_nH * 1e-9
    C_tot_F = C_pF * 1e-12

    f_Hz = 1.0 / (2.0 * np.pi * np.sqrt(L_tot_H * C_tot_F))
    return f_Hz / 1e9
