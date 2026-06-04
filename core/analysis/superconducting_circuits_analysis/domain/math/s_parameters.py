"""Mathematical models for S-parameter analysis and resonance fitting."""

from typing import Any, cast

import numpy as np


def notch_s21(
    f: np.ndarray,
    fr: float,
    Ql: float,
    Qc_real: float,
    Qc_imag: float,
    a: float,
    alpha: float,
    tau: float,
) -> np.ndarray:
    """
    Compute the complex S21 transmission of a notch-type resonator.

    This function uses the standard Closest Pole and Zero Method (CPZM) approximation
    combined with environmental baselines (delay, gain, phase, asymmetry).

    Arguments:
        f: Frequency array (Hz).
        fr: Resonance frequency (Hz).
        Ql: Loaded quality factor.
        Qc_real: Real part of the complex coupling quality factor.
        Qc_imag: Imaginary part of the complex coupling quality factor.
        a: Amplitude scaling factor.
        alpha: Constant phase shift (radians).
        tau: Electrical delay (seconds).

    Returns:
        Complex S21 array.
    """
    # Complex coupling quality factor
    Qc_complex = Qc_real + 1j * Qc_imag

    # Fractional detuning
    x = (f - fr) / fr

    # Environmental baseline: delay + complex gain
    baseline = a * np.exp(1j * alpha) * np.exp(-2j * np.pi * f * tau)

    # Resonance dip
    dip = 1 - (Ql / Qc_complex) / (1 + 2j * Ql * x)

    return baseline * dip


def estimate_notch_initial_guess(f: np.ndarray, s21_complex: np.ndarray) -> dict[str, float]:
    """
    Estimate the initial guess parameters for a notch-type resonator S21 fit.

    This provides a robust starting point for gradient-based optimization algorithms.

    Arguments:
        f: Frequency array (Hz).
        s21_complex: Complex S21 data array.

    Returns:
        Dictionary of initial parameter guesses: fr, Ql, Qc_real, Qc_imag, a, alpha, tau.
    """
    s21_mag = np.abs(s21_complex)
    s21_phase = np.unwrap(np.angle(s21_complex))

    # 1. Estimate resonance frequency (minimum amplitude)
    # Ignore DC components (f <= 0) which can artificially drop to 0 in simulations
    valid_f = f > 0
    if not np.any(valid_f):
        valid_f = np.ones_like(f, dtype=bool)

    min_idx_valid = np.argmin(s21_mag[valid_f])
    fr_guess = float(f[valid_f][min_idx_valid])
    min_mag = s21_mag[valid_f][min_idx_valid]

    # 2. Estimate baselines (using endpoints assuming they are far from resonance)
    # Average amplitude of the first and last few points
    num_bg_points = max(1, len(f) // 20)
    bg_mag_start = np.mean(s21_mag[:num_bg_points])
    bg_mag_end = np.mean(s21_mag[-num_bg_points:])
    a_guess = float(np.mean([bg_mag_start, bg_mag_end]))

    # Estimate phase slope (tau) and offset (alpha) from unwrapped phase endpoints
    phase_start = np.mean(s21_phase[:num_bg_points])
    phase_end = np.mean(s21_phase[-num_bg_points:])
    f_start = np.mean(f[:num_bg_points])
    f_end = np.mean(f[-num_bg_points:])

    df = f_end - f_start
    if df != 0:
        # Phase = -2 * pi * f * tau + alpha
        # Slope = -2 * pi * tau  =>  tau = -Slope / (2 * pi)
        phase_slope = (phase_end - phase_start) / df
        tau_guess = -phase_slope / (2 * np.pi)
        alpha_guess = phase_start - phase_slope * f_start
    else:
        tau_guess = 0.0
        alpha_guess = float(np.mean(s21_phase))

    # 3. Estimate Quality Factors
    # FWHM for Ql: find frequencies where mag approaches sqrt( (min_mag^2 + a_guess^2)/2 )
    # A simple heuristic for notch: width of points roughly 3dB above the minimum
    # (relative to the bottom of the dip)

    # 3dB threshold magnitude
    # For a deep notch, the 3dB point from the baseline is approx a_guess / sqrt(2)
    # However, if it's shallow, a better robust guess is halfway between baseline
    # and minimum (in power).
    threshold_power = (min_mag**2 + a_guess**2) / 2
    threshold_mag = np.sqrt(threshold_power)

    # find indices where mag < threshold_mag
    dip_indices = np.where(s21_mag < threshold_mag)[0]

    if len(dip_indices) > 1:
        f_low = f[dip_indices[0]]
        f_high = f[dip_indices[-1]]
        fwhm = f_high - f_low
        if fwhm == 0:
            fwhm = fr_guess * 1e-4  # fallback narrow bandwidth
    else:
        # Fallback if threshold is not crossed well
        fwhm = fr_guess * 1e-4

    Ql_guess = fr_guess / fwhm

    # Ensure strictly positive values for initial Q guesses to prevent zero-division
    if Ql_guess <= 0:
        Ql_guess = 100.0

    depth = 1.0 - (min_mag / a_guess)
    if depth <= 0:
        depth = 0.01  # avoid division by zero
    Qc_real_guess = Ql_guess / depth

    if Qc_real_guess <= 0:
        Qc_real_guess = Ql_guess * 10.0

    return {
        "fr": float(fr_guess),
        "Ql": float(Ql_guess),
        "Qc_real": float(Qc_real_guess),
        "Qc_imag": 0.0,
        "a": float(a_guess),
        "alpha": float(alpha_guess),
        "tau": float(tau_guess),
    }


def fit_notch_s21(
    f: np.ndarray, s21_complex: np.ndarray, initial_guess: dict[str, float] | None = None
) -> dict[str, float]:
    """
    Fits the Complex S21 notch resonator model to data using least squares.
    """
    from scipy.optimize import least_squares

    if initial_guess is None:
        initial_guess = estimate_notch_initial_guess(f, s21_complex)

    # Unpack guess into an array: [fr, Ql, Qc_real, Qc_imag, a, alpha, tau]
    print(f"DEBUG: initial_guess = {initial_guess}")
    p0 = [
        initial_guess["fr"],
        initial_guess["Ql"],
        initial_guess["Qc_real"],
        initial_guess["Qc_imag"],
        initial_guess["a"],
        initial_guess["alpha"],
        initial_guess["tau"],
    ]

    # Define residual function
    # return array of Re/Im flattened since least_squares expects real residuals,
    # or just abs() the complex diff. We'll use abs() for a real-valued absolute residual.
    # Alternatively, concat real and imag parts:
    def residual(p, f_data, s21_data):
        fr, Ql, Qc_real, Qc_imag, a, alpha, tau = p
        s21_model = notch_s21(f_data, fr, Ql, Qc_real, Qc_imag, a, alpha, tau)
        diff = s21_model - s21_data
        # Return a 1D real array of length 2*N (Re and Im stacked) for robust optimization
        return np.concatenate((np.real(diff), np.imag(diff)))

    # Bounds to prevent unphysical regimes
    # fr > 0, Ql > 0, a > 0
    bounds = (
        [0, 0, -np.inf, -np.inf, 0, -np.inf, -np.inf],
        [np.inf, np.inf, np.inf, np.inf, np.inf, np.inf, np.inf],
    )

    result = least_squares(residual, p0, args=(f, s21_complex), bounds=bounds, loss="soft_l1")

    if not result.success:
        raise ValueError(f"S21 Fit Failed: {result.message}")

    p_opt = result.x

    # Optional: Calculate Qi
    Ql_opt = p_opt[1]
    Qc_complex_opt = p_opt[2] + 1j * p_opt[3]

    # The actual coupling Q magnitude (often used)
    Qc_opt_mag = abs(Qc_complex_opt)

    # 1/Ql = 1/Qi + Re(1/Qc) is commonly used for asymmetric fits,
    # but the simplest derived scalar Qi uses the magnitude 1/Ql = 1/Qi + 1/|Qc|
    # Or specifically Re(1/Qc) as per some literature. Let's use Re(1/Qc):
    # 1/Qi = 1/Ql - Re(1/Qc)
    re_inv_qc = np.real(1.0 / Qc_complex_opt)
    inv_qi = 1.0 / Ql_opt - re_inv_qc
    qi_opt = 1.0 / inv_qi if inv_qi > 0 else np.inf

    return {
        "fr": p_opt[0],
        "Ql": Ql_opt,
        "Qc_real": p_opt[2],
        "Qc_imag": p_opt[3],
        "Qc_mag": Qc_opt_mag,
        "Qi": qi_opt,
        "a": p_opt[4],
        "alpha": p_opt[5],
        "tau": p_opt[6],
        "cost": result.cost,
    }


def transmission_s21(
    f: np.ndarray,
    fr: float,
    Ql: float,
    a: float,
    alpha: float,
    tau: float,
) -> np.ndarray:
    """
    Compute the complex S21 transmission of a Purcell filter or inline resonator.

    Arguments:
        f: Frequency array (Hz).
        fr: Resonance frequency (Hz).
        Ql: Loaded quality factor.
        a: Peak amplitude scaling factor.
        alpha: Constant phase shift (radians).
        tau: Electrical delay (seconds).

    Returns:
        Complex S21 array.
    """
    x = (f - fr) / fr
    baseline = np.exp(1j * alpha) * np.exp(-2j * np.pi * f * tau)
    peak = a / (1 + 2j * Ql * x)
    return baseline * peak


def estimate_transmission_initial_guess(f: np.ndarray, s21_complex: np.ndarray) -> dict[str, float]:
    """Estimate initial guess parameters for a transmission peak."""
    s21_mag = np.abs(s21_complex)
    s21_phase = np.unwrap(np.angle(s21_complex))

    valid_f = f > 0
    if not np.any(valid_f):
        valid_f = np.ones_like(f, dtype=bool)

    max_idx_valid = np.argmax(s21_mag[valid_f])
    fr_guess = float(f[valid_f][max_idx_valid])
    max_mag = s21_mag[valid_f][max_idx_valid]

    a_guess = float(max_mag)

    # Estimate phase slope (tau) and offset (alpha) from unwrapped phase
    # For a transmission peak, most of the phase is dominated by delay.
    num_bg_points = max(1, len(f) // 20)
    phase_start = np.mean(s21_phase[:num_bg_points])
    phase_end = np.mean(s21_phase[-num_bg_points:])
    f_start = np.mean(f[:num_bg_points])
    f_end = np.mean(f[-num_bg_points:])

    df = f_end - f_start
    if df != 0:
        phase_slope = (phase_end - phase_start) / df
        tau_guess = -phase_slope / (2 * np.pi)
        alpha_guess = phase_start - phase_slope * f_start
    else:
        tau_guess = 0.0
        alpha_guess = float(np.mean(s21_phase))

    # FWHM for Ql: find frequencies where mag approaches max_mag / sqrt(2)
    threshold_mag = max_mag / np.sqrt(2)
    peak_indices = np.where(s21_mag > threshold_mag)[0]

    if len(peak_indices) > 1:
        f_low = f[peak_indices[0]]
        f_high = f[peak_indices[-1]]
        fwhm = f_high - f_low
        if fwhm == 0:
            fwhm = fr_guess * 1e-4
    else:
        fwhm = fr_guess * 1e-4

    Ql_guess = fr_guess / fwhm
    if Ql_guess <= 0:
        Ql_guess = 100.0

    return {
        "fr": float(fr_guess),
        "Ql": float(Ql_guess),
        "a": float(a_guess),
        "alpha": float(alpha_guess),
        "tau": float(tau_guess),
    }


def fit_transmission_s21(
    f: np.ndarray, s21_complex: np.ndarray, initial_guess: dict[str, float] | None = None
) -> dict[str, float]:
    """Fits the transmission (inline resonator/peak) model to data using least squares."""
    from scipy.optimize import least_squares

    if initial_guess is None:
        initial_guess = estimate_transmission_initial_guess(f, s21_complex)

    print(f"DEBUG: initial_guess = {initial_guess}")
    p0 = [
        initial_guess["fr"],
        initial_guess["Ql"],
        initial_guess["a"],
        initial_guess["alpha"],
        initial_guess["tau"],
    ]

    def residual(p, f_data, s21_data):
        fr, Ql, a, alpha, tau = p
        s21_model = transmission_s21(f_data, fr, Ql, a, alpha, tau)
        diff = s21_model - s21_data
        return np.concatenate((np.real(diff), np.imag(diff)))

    bounds = (
        [0, 0, 0, -np.inf, -np.inf],
        [np.inf, np.inf, np.inf, np.inf, np.inf],
    )

    result = least_squares(residual, p0, args=(f, s21_complex), bounds=bounds, loss="soft_l1")

    if not result.success:
        raise ValueError(f"S21 Fit Failed: {result.message}")

    p_opt = result.x

    # Derive Qc and Qi Assuming a = Ql / Qc (standard symmetric transmission resonator)
    Ql_opt = p_opt[1]
    a_opt = p_opt[2]

    Qc_mag = Ql_opt / a_opt if a_opt > 0 else np.inf
    inv_qi = 1.0 / Ql_opt - 1.0 / Qc_mag
    qi_opt = 1.0 / inv_qi if inv_qi > 0 else np.inf

    return {
        "fr": p_opt[0],
        "Ql": Ql_opt,
        "Qc_real": Qc_mag,
        "Qc_imag": 0.0,
        "Qc_mag": Qc_mag,
        "Qi": qi_opt,
        "a": a_opt,
        "alpha": p_opt[3],
        "tau": p_opt[4],
        "cost": result.cost,
    }


class MultiResonanceVectorFitter:
    """
    Wrapper for scikit-rf VectorFitting algorithm to extract multiple physical
    resonances (poles and residues) from S-parameter data.
    """

    def __init__(self, f: np.ndarray, s21_complex: np.ndarray):
        """
        Initialize the fitter with frequency (Hz) and complex S21 data.
        """
        self.f = f
        self.s21_complex = s21_complex
        self.vf_engine = None

    def _create_skrf_network(self) -> Any:
        """Construct an skrf Network from numpy arrays."""
        import skrf

        # skrf Network expects frequencies in Hz
        freq = skrf.Frequency.from_f(self.f, unit="Hz")

        # S-parameter matrix for a 2-port network: shape (N_freq, 2, 2)
        # We only have S21, so we'll mock a 2-port network where S21 is populated
        # and others are zero to satisfy skrf data structures.
        s_matrix = np.zeros((len(self.f), 2, 2), dtype=complex)
        s_matrix[:, 1, 0] = self.s21_complex  # S21

        # Also put it in S11 just in case, though VF can fit individual responses
        s_matrix[:, 0, 0] = self.s21_complex

        ntwk = skrf.Network(frequency=freq, s=s_matrix)
        return ntwk

    def fit(self, n_resonators: int = 1, bg_poles: int = 2) -> dict:
        """
        Perform Vector Fitting to extract multi-modal resonances.

        Arguments:
            n_resonators: Expected number of physical resonance structures
                (e.g., Readout + Purcell).
            bg_poles: Number of real poles to dedicate to resolving background delay/slopes.

        Returns:
            A dictionary containing the extracted physical poles, residues,
            and the reconstructed model.
        """
        import skrf

        ntwk = self._create_skrf_network()

        self.vf_engine = skrf.VectorFitting(cast(Any, ntwk))

        # Fit the entire Network using Sanathanan-Koerner iterations
        # We target response (1, 0) which corresponds to S21
        self.vf_engine.vector_fit(n_poles_real=bg_poles, n_poles_cmplx=n_resonators)

        # Reconstruct the model
        # Pass the original frequency array self.f to ensure the model output array
        # exactly matches the length of the raw data for plotting.
        model_s21 = self.vf_engine.get_model_response(1, 0, self.f)

        extracted = self._extract_physics()

        return {
            "resonances": extracted["physical"],
            "artifacts": extracted["artifacts"],
            "model_s21": model_s21,
            "cost": self.vf_engine.get_rms_error(),
        }

    def _extract_physics(self) -> dict[str, list[dict[str, float]]]:
        """
        Extract fr and Ql from the VF poles, separating physical resonances
        from mathematical artifacts (low-Q poles used for background fitting).

        Note: Qc and Qi are NOT extracted here because VF residues are unreliable
        for multi-resonator scenarios (residues interfere when poles are close).
        Use notch/transmission single-peak fitting for precise Qc/Qi extraction.
        """
        physical = []
        artifacts = []

        if self.vf_engine is None:
            raise RuntimeError("Vector fitting has not been executed.")
        poles = self.vf_engine.poles or []

        for p in poles:
            # Physical resonances are complex conjugate pairs. Analyze only the
            # positive-frequency half.
            omega = np.imag(p)
            sigma = -np.real(p)  # skrf poles should be in Left-Half Plane (negative real part)

            # Skip real poles (omega == 0) and conjugate halves (omega < 0)
            if omega <= 0:
                continue

            # Filter unstable poles just in case
            if sigma <= 0:
                continue

            fr = omega / (2 * np.pi)
            Q_l = omega / (2 * sigma)

            item = {"fr": float(fr), "Ql": float(Q_l)}

            # Filter low-Q artifacts (math padding poles usually have very low Q)
            if Q_l > 2.0:
                physical.append(item)
            else:
                artifacts.append(item)

        # Sort by frequency
        physical.sort(key=lambda x: x["fr"])
        artifacts.sort(key=lambda x: x["fr"])

        return {
            "physical": physical,
            "artifacts": artifacts,
        }
