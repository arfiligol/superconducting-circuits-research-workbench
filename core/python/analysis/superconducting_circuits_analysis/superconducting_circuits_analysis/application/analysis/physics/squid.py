from typing import Any

import numpy as np


def calculate_squid_lc_frequency(
    L_jun: float | np.ndarray[Any, np.dtype[np.float64]], Ls_nH: float, C_pF: float
) -> float | np.ndarray[Any, np.dtype[np.float64]]:
    """
    Calculate the resonant frequency of a SQUID-LC circuit.

    Args:
        L_jun: Josephson inductance in nH (single value or array)
        Ls_nH: Series inductance in nH
        C_pF: Capacitance in pF

    Returns:
        Frequency in GHz
    """
    # L_jun is the inductance of a single junction, but SQUID has 2 in parallel?
    # Original model used L_sq = L_jun / 2.0.
    # Assuming L_jun here refers to the total SQUID inductance or per-junction?
    # Based on original code: "L_sq = L_jun / 2.0" implies L_jun is per-junction inductance
    # and we have two in parallel (ideal symmetric SQUID).

    L_sq = L_jun / 2.0
    L_tot_nH = L_sq + Ls_nH
    # Avoid division by zero or negative inductance (unphysical but stable for fitting)
    L_tot_nH = np.maximum(L_tot_nH, 1e-15)

    L_tot_H = L_tot_nH * 1e-9
    C_tot_F = C_pF * 1e-12

    f_Hz = 1.0 / (2.0 * np.pi * np.sqrt(L_tot_H * C_tot_F))
    return f_Hz / 1e9
