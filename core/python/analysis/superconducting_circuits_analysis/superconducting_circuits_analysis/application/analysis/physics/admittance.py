from __future__ import annotations

from typing import Any

import numpy as np


def calculate_y11_imaginary(
    L_jun: float | np.ndarray[Any, np.dtype[np.float64]],
    freq_ghz: float | np.ndarray[Any, np.dtype[np.float64]],
    Ls1_nH: float,
    Ls2_nH: float,
    C_pF: float,
) -> float | np.ndarray[Any, np.dtype[np.float64]]:
    """
    Calculate the imaginary part of the Y11 admittance.

    Model:
    Y11(jω) = 1 / (jω(L_sq + Ls1)) + j ω C / (1 - ω^2 Ls2 C)

    Where L_sq = L_jun / 2.0 (SQUID inductance)

    Args:
        L_jun: Josephson inductance in nH
        freq_ghz: Frequency in GHz
        Ls1_nH: Series inductance 1 in nH
        Ls2_nH: Series inductance 2 in nH
        C_pF: Capacitance in pF

    Returns:
        Imaginary part of Y11 (Siemens)
    """
    l_jun_array = np.asarray(L_jun, dtype=float)
    freq_array = np.asarray(freq_ghz, dtype=float) * 1e9

    l_sq_h = (l_jun_array / 2.0) * 1e-9
    ls1_h = Ls1_nH * 1e-9
    ls2_h = Ls2_nH * 1e-9

    total_inductance = l_sq_h + ls1_h
    capacitance_f = C_pF * 1e-12

    omega = 2.0 * np.pi * freq_array
    # Avoid zero division stability
    omega = np.where(omega == 0.0, 1e-30, omega)

    # Pure inductive branch: 1 / (j * w * L) = -j / (w * L) -> Imag = -1 / (w * L)
    imaginary_inductive = -1.0 / (omega * total_inductance)

    # Resonant branch: j * w * C / (1 - w^2 * Ls2 * C) -> Imag = w * C / (1 - w^2 * Ls2 * C)
    denom = 1.0 - (omega**2) * ls2_h * capacitance_f
    # Avoid pole singularity
    denom = np.where(np.abs(denom) < 1e-21, np.sign(denom) * 1e-21, denom)

    imaginary_resonant = (omega * capacitance_f) / denom

    return imaginary_inductive + imaginary_resonant
