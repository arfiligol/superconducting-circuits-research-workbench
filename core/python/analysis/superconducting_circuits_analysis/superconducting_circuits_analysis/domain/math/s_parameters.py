"""Numerical S-parameter models and resonance-fitting implementations.

Knowledge:
    Notch resonator complex S21 fit:
    https://github.com/arfiligol/SCQ_Design/blob/main/docs/knowledge/network-modeling/notch-resonator-complex-s21-fit.qmd
    Network trace views:
    https://github.com/arfiligol/SCQ_Design/blob/main/docs/knowledge/network-modeling/network-trace-views.qmd
    Poles, zeros, and residues:
    https://github.com/arfiligol/SCQ_Design/blob/main/docs/knowledge/network-modeling/poles-zeros-residues.qmd
    Vector fitting and passivity:
    https://github.com/arfiligol/SCQ_Design/blob/main/docs/knowledge/network-modeling/vector-fitting-passivity.qmd

This module owns the repository's numerical S21 models, initial-guess
heuristics, least-squares fits, and vector-fitting wrapper. Reusable physics
and engineering explanations belong to the linked SCQ_Design knowledge base.
This module does not implement passivity checking or enforcement.
"""

from numbers import Real
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
    """Estimate physical notch parameters only when the trace identifies them.

    The estimator uses the sampled dip and deterministic endpoint samples. It
    fails instead of manufacturing a quality factor, depth, or coupling value
    when the selected trace cannot identify the required quantities.

    Args:
        f: Frequency array (Hz).
        s21_complex: Complex S21 data array.

    Returns:
        Dictionary of initial parameter guesses: fr, Ql, Qc_real, Qc_imag, a, alpha, tau.

    Raises:
        ValueError: If the automatic estimator cannot identify a positive
            baseline, phase span, half-power span, or notch depth. Callers may
            then provide the complete explicit initial guess.
    """
    s21_mag = np.abs(s21_complex)
    s21_phase = np.unwrap(np.angle(s21_complex))

    # 1. Estimate resonance frequency (minimum amplitude)
    # Ignore DC components (f <= 0) which can artificially drop to 0 in simulations
    valid_f = f > 0
    if not np.any(valid_f):
        raise ValueError("Automatic notch initialization requires positive frequencies.")

    min_idx_valid = np.argmin(s21_mag[valid_f])
    fr_guess = float(f[valid_f][min_idx_valid])
    min_mag = s21_mag[valid_f][min_idx_valid]

    # 2. Estimate baselines (using endpoints assuming they are far from resonance)
    # Average amplitude of the first and last few points
    num_bg_points = max(1, len(f) // 20)
    bg_mag_start = np.mean(s21_mag[:num_bg_points])
    bg_mag_end = np.mean(s21_mag[-num_bg_points:])
    a_guess = float(np.mean([bg_mag_start, bg_mag_end]))
    if not np.isfinite(a_guess) or a_guess <= 0.0:
        raise ValueError(
            "Automatic notch initialization requires a positive finite endpoint baseline; "
            "provide a complete explicit initial_guess."
        )

    # Estimate phase slope (tau) and offset (alpha) from unwrapped phase endpoints
    phase_start = np.mean(s21_phase[:num_bg_points])
    phase_end = np.mean(s21_phase[-num_bg_points:])
    f_start = np.mean(f[:num_bg_points])
    f_end = np.mean(f[-num_bg_points:])

    df = f_end - f_start
    if not np.isfinite(df) or df <= 0.0:
        raise ValueError(
            "Automatic notch initialization requires a positive endpoint frequency span; "
            "provide a complete explicit initial_guess."
        )
    # Phase = -2 * pi * f * tau + alpha
    # Slope = -2 * pi * tau  =>  tau = -Slope / (2 * pi)
    phase_slope = (phase_end - phase_start) / df
    tau_guess = -phase_slope / (2 * np.pi)
    alpha_guess = phase_start - phase_slope * f_start

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

    if len(dip_indices) <= 1:
        raise ValueError(
            "Automatic notch initialization cannot identify a half-power span; "
            "provide a complete explicit initial_guess."
        )
    f_low = f[dip_indices[0]]
    f_high = f[dip_indices[-1]]
    fwhm = f_high - f_low
    if not np.isfinite(fwhm) or fwhm <= 0.0:
        raise ValueError(
            "Automatic notch initialization requires a positive half-power span; "
            "provide a complete explicit initial_guess."
        )

    Ql_guess = fr_guess / fwhm
    if not np.isfinite(Ql_guess) or Ql_guess <= 0.0:
        raise ValueError(
            "Automatic notch initialization produced a nonpositive loaded Q; "
            "provide a complete explicit initial_guess."
        )

    depth = 1.0 - (min_mag / a_guess)
    if not np.isfinite(depth) or depth <= 0.0:
        raise ValueError(
            "Automatic notch initialization requires a positive notch depth; "
            "provide a complete explicit initial_guess."
        )
    Qc_real_guess = Ql_guess / depth
    if not np.isfinite(Qc_real_guess) or Qc_real_guess <= 0.0:
        raise ValueError(
            "Automatic notch initialization produced a nonpositive coupling Q; "
            "provide a complete explicit initial_guess."
        )

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
) -> dict[str, Any]:
    """Fit one bracketed complex notch without hiding physical interpretation.

    The optimizer uses centered, dimensionless coordinates so frequency, delay,
    gain, coupling, and quality factor contribute on numerically comparable
    scales. Numerical convergence is reported separately from the exact
    algebraic status of the derived internal quality factor.

    Args:
        f: Strictly increasing positive frequencies in hertz.
        s21_complex: Complex S21 samples on the same frequency grid.
        initial_guess: Optional physical-parameter guess using the domain keys
            ``fr``, ``Ql``, ``Qc_real``, ``Qc_imag``, ``a``, ``alpha``, and
            ``tau``.

    Returns:
        Fitted physical parameters, the effective initializer, numerical
        settings, and optimizer termination evidence.

    Raises:
        ValueError: If the trace does not bracket a notch, the initializer is
            invalid, the solver fails, or conversion back to physical
            parameters is mathematically degenerate.
    """
    from scipy.optimize import least_squares

    if f.ndim != 1 or s21_complex.ndim != 1 or len(f) != len(s21_complex):
        raise ValueError("f and s21_complex must be one-dimensional arrays of equal length.")
    if len(f) < 3:
        raise ValueError("At least three frequency samples are required.")
    if not np.all(np.isfinite(f)) or not np.all(np.isfinite(s21_complex)):
        raise ValueError("Notch-fit samples must be finite.")
    if not np.all(f > 0.0) or not np.all(np.diff(f) > 0.0):
        raise ValueError("Notch-fit frequencies must be positive and strictly increasing.")

    minimum_index = int(np.argmin(np.abs(s21_complex)))
    if minimum_index in (0, len(f) - 1):
        raise ValueError(
            "The selected fit window does not bracket the S21 notch: "
            "the sampled magnitude minimum is at a window endpoint."
        )

    if initial_guess is None:
        initial_guess = estimate_notch_initial_guess(f, s21_complex)

    required_guess_keys = {"fr", "Ql", "Qc_real", "Qc_imag", "a", "alpha", "tau"}
    if set(initial_guess) != required_guess_keys:
        raise ValueError(f"initial_guess must contain exactly {sorted(required_guess_keys)}.")
    if not all(np.isfinite(value) for value in initial_guess.values()):
        raise ValueError("initial_guess values must be finite.")

    fr_initial = float(initial_guess["fr"])
    ql_initial = float(initial_guess["Ql"])
    qc_initial = complex(initial_guess["Qc_real"], initial_guess["Qc_imag"])
    amplitude_initial = float(initial_guess["a"])
    alpha_initial = float(initial_guess["alpha"])
    tau_initial = float(initial_guess["tau"])
    if not f[0] < fr_initial < f[-1]:
        raise ValueError("initial_guess resonance frequency must lie inside the fit window.")
    if ql_initial <= 0.0 or amplitude_initial <= 0.0:
        raise ValueError("initial_guess Ql and amplitude must be positive.")
    if qc_initial == 0.0:
        raise ValueError("initial_guess complex Qc must be nonzero.")

    frequency_center = float((f[0] + f[-1]) / 2.0)
    frequency_scale = float((f[-1] - f[0]) / 2.0)
    if frequency_scale <= 0.0:
        raise ValueError("The fit window must span more than one frequency.")
    normalized_frequency = (f - frequency_center) / frequency_scale
    coupling_initial = ql_initial / qc_initial
    phase_at_reference_initial = alpha_initial - 2.0 * np.pi * frequency_center * tau_initial
    delay_phase_initial = 2.0 * np.pi * frequency_scale * tau_initial
    p0 = np.asarray(
        [
            (fr_initial - frequency_center) / frequency_scale,
            np.log(ql_initial),
            coupling_initial.real,
            coupling_initial.imag,
            np.log(amplitude_initial),
            phase_at_reference_initial,
            delay_phase_initial,
        ],
        dtype=float,
    )

    def scaled_model(parameters: np.ndarray) -> np.ndarray:
        resonance_scaled, log_ql, coupling_real, coupling_imag, log_a, phase, delay = (
            parameters
        )
        resonance_frequency = frequency_center + frequency_scale * resonance_scaled
        loaded_q = np.exp(log_ql)
        coupling = coupling_real + 1j * coupling_imag
        baseline = np.exp(log_a + 1j * (phase - delay * normalized_frequency))
        detuning = (f - resonance_frequency) / resonance_frequency
        return baseline * (1.0 - coupling / (1.0 + 2j * loaded_q * detuning))

    def residual(parameters: np.ndarray) -> np.ndarray:
        difference = scaled_model(parameters) - s21_complex
        return np.concatenate((np.real(difference), np.imag(difference)))

    result = least_squares(
        residual,
        p0,
        bounds=(
            [-1.0, -np.inf, -np.inf, -np.inf, -np.inf, -np.inf, -np.inf],
            [1.0, np.inf, np.inf, np.inf, np.inf, np.inf, np.inf],
        ),
        loss="linear",
    )

    if not result.success:
        raise ValueError(f"S21 Fit Failed: {result.message}")
    if not np.all(np.isfinite(result.x)):
        raise ValueError("S21 fit returned non-finite internal parameters.")
    if not np.isfinite(result.cost):
        raise ValueError("S21 fit returned a non-finite least-squares cost.")
    if not np.isfinite(result.optimality):
        raise ValueError("S21 fit returned non-finite optimizer optimality evidence.")
    if result.njev is None:
        raise ValueError("S21 fit did not report the required Jacobian evaluation count.")

    resonance_scaled, log_ql, coupling_real, coupling_imag, log_a, phase, delay = result.x
    fr_opt = float(frequency_center + frequency_scale * resonance_scaled)
    ql_opt = float(np.exp(log_ql))
    coupling_opt = complex(coupling_real, coupling_imag)
    amplitude_opt = float(np.exp(log_a))
    if not f[0] < fr_opt < f[-1]:
        raise ValueError("Fitted resonance frequency does not lie inside the fit window.")
    if not np.isfinite(ql_opt) or not np.isfinite(amplitude_opt):
        raise ValueError("S21 fit returned non-finite positive parameters.")
    if coupling_opt == 0.0:
        raise ValueError("Fitted coupling is exactly zero; complex Qc is undefined.")

    qc_opt = ql_opt / coupling_opt
    qc_magnitude = float(abs(qc_opt))
    tau_opt = float(delay / (2.0 * np.pi * frequency_scale))
    alpha_opt = float(phase + 2.0 * np.pi * frequency_center * tau_opt)
    if not all(
        np.isfinite(value)
        for value in (
            fr_opt,
            ql_opt,
            qc_opt.real,
            qc_opt.imag,
            qc_magnitude,
            amplitude_opt,
            tau_opt,
            alpha_opt,
            phase,
        )
    ):
        raise ValueError("S21 fit could not be converted to finite physical parameters.")

    inverse_qi = float((1.0 - coupling_opt.real) / ql_opt)
    if not np.isfinite(inverse_qi):
        raise ValueError("S21 fit returned a non-finite inverse Qi.")
    if inverse_qi > 0.0:
        qi_status = "finite"
        qi_opt: float | None = float(1.0 / inverse_qi)
        if not np.isfinite(qi_opt):
            raise ValueError("Finite inverse Qi could not be represented as a finite Qi.")
    elif inverse_qi == 0.0:
        qi_status = "lossless_boundary"
        qi_opt = None
    else:
        qi_status = "nonphysical"
        qi_opt = None

    fitted_s21 = np.asarray(scaled_model(result.x), dtype=complex)
    if fitted_s21.shape != s21_complex.shape or not np.all(np.isfinite(fitted_s21)):
        raise ValueError("S21 fit returned a non-finite or incomplete fitted complex trace.")

    return {
        "fr": fr_opt,
        "Ql": ql_opt,
        "Qc_real": float(qc_opt.real),
        "Qc_imag": float(qc_opt.imag),
        "Qc_mag": qc_magnitude,
        "Qi": qi_opt,
        "inverse_Qi": inverse_qi,
        "Qi_status": qi_status,
        "a": amplitude_opt,
        "alpha": alpha_opt,
        "tau": tau_opt,
        "phase_reference_hz": frequency_center,
        "phase_at_reference_rad": float(phase),
        "initial_guess": {
            "fr": fr_initial,
            "Ql": ql_initial,
            "Qc_real": float(qc_initial.real),
            "Qc_imag": float(qc_initial.imag),
            "a": amplitude_initial,
            "alpha": alpha_initial,
            "tau": tau_initial,
        },
        "fit_settings": {
            "optimizer": "scipy.optimize.least_squares",
            "residual": "stacked_real_imag",
            "loss": "linear",
            "time_phasor_convention": "exp(+i*omega*t)",
            "delay_factor": "exp(-i*2*pi*f*tau)",
            "frequency_center_hz": frequency_center,
            "frequency_scale_hz": frequency_scale,
            "resonance_frequency_bounds_hz": [float(f[0]), float(f[-1])],
            "internal_parameterization": "centered_scaled_notch",
        },
        "optimizer": {
            "status": int(result.status),
            "message": str(result.message),
            "nfev": int(result.nfev),
            "njev": int(result.njev),
            "optimality": float(result.optimality),
            "active_mask": [int(value) for value in result.active_mask],
        },
        "least_squares_cost": float(result.cost),
        "model_s21": fitted_s21,
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
    Compute the complex S21 transmission response of an inline resonator.

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
    """Fit one scalar complex S21 trace with scikit-rf VectorFitting.

    The one-response ``Network`` is only a library carrier for the scalar
    samples. It is not a physical one-port or multiport network model and does
    not establish passivity or reciprocity.
    """

    def __init__(self, f: np.ndarray, s21_complex: np.ndarray):
        """
        Initialize the fitter with frequency (Hz) and complex S21 data.
        """
        self.f = f
        self.s21_complex = s21_complex
        self.vf_engine = None

    def _create_scalar_response_carrier(self) -> Any:
        """Carry exactly one scalar S21 response through scikit-rf."""
        import skrf

        freq = skrf.Frequency.from_f(self.f, unit="Hz")
        response = np.asarray(self.s21_complex, dtype=complex).reshape(-1, 1, 1)
        return skrf.Network(frequency=freq, s=response)

    def fit(
        self,
        n_resonators: int,
        bg_poles: int,
        *,
        min_q: float,
        restrict_to_input_span: bool = True,
    ) -> dict:
        """Fit the scalar trace and classify stable positive-frequency poles.

        Arguments:
            n_resonators: Requested number of complex pole pairs.
            bg_poles: Requested number of real background poles.
            min_q: Caller-owned threshold separating reported resonances from
                the existing artifact bucket.
            restrict_to_input_span: Exclude poles outside the sampled span when
                true.

        Returns:
            Reported resonances, artifacts, reconstructed scalar S21, and its
            explicit complex-S21 root-mean-square error.
        """
        if isinstance(n_resonators, (bool, np.bool_)) or not isinstance(
            n_resonators, (int, np.integer)
        ):
            raise ValueError("n_resonators must be an integer.")
        if isinstance(bg_poles, (bool, np.bool_)) or not isinstance(bg_poles, (int, np.integer)):
            raise ValueError("bg_poles must be an integer.")
        n_resonators = int(n_resonators)
        bg_poles = int(bg_poles)
        if n_resonators < 1:
            raise ValueError("n_resonators must be at least 1.")
        if bg_poles < 0:
            raise ValueError("bg_poles must be non-negative.")
        if isinstance(min_q, (bool, np.bool_)) or not isinstance(min_q, Real):
            raise ValueError("min_q must be a real number.")
        min_q_value = float(min_q)
        if not np.isfinite(min_q_value) or min_q_value < 0:
            raise ValueError("min_q must be finite and non-negative.")
        if not isinstance(restrict_to_input_span, (bool, np.bool_)):
            raise ValueError("restrict_to_input_span must be a Boolean.")
        restrict_to_span = bool(restrict_to_input_span)

        ntwk = self._create_scalar_response_carrier()

        try:
            from skrf.vectorFitting import VectorFitting
        except ImportError:  # pragma: no cover - supports older scikit-rf releases.
            import skrf

            VectorFitting = skrf.VectorFitting

        self.vf_engine = VectorFitting(cast(Any, ntwk))

        self.vf_engine.vector_fit(n_poles_real=bg_poles, n_poles_cmplx=n_resonators)

        model_s21 = self.vf_engine.get_model_response(0, 0, self.f)
        rms_error = float(np.sqrt(np.mean(np.abs(model_s21 - self.s21_complex) ** 2)))

        frequency_span_hz = (
            (float(np.min(self.f)), float(np.max(self.f))) if restrict_to_span else None
        )
        extracted = self._classify_poles(
            min_q=min_q_value,
            frequency_span_hz=frequency_span_hz,
        )

        return {
            "resonances": extracted["resonances"],
            "artifacts": extracted["artifacts"],
            "model_s21": model_s21,
            "rms_error": rms_error,
        }

    def _classify_poles(
        self,
        *,
        min_q: float,
        frequency_span_hz: tuple[float, float] | None = None,
    ) -> dict[str, list[dict[str, float]]]:
        """Classify fitted poles using the caller-owned Q threshold.

        Note: Qc and Qi are NOT extracted here because VF residues are unreliable
        for multi-resonator scenarios (residues interfere when poles are close).
        Use notch/transmission single-peak fitting for precise Qc/Qi extraction.
        """
        resonances = []
        artifacts = []

        if self.vf_engine is None:
            raise RuntimeError("Vector fitting has not been executed.")
        poles = np.asarray(self.vf_engine.poles if self.vf_engine.poles is not None else [])

        for p in poles:
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
            if frequency_span_hz is not None:
                fmin_hz, fmax_hz = frequency_span_hz
                if fr < fmin_hz or fr > fmax_hz:
                    continue

            item = {
                "fr": float(fr),
                "Ql": float(Q_l),
                "pole_real": float(np.real(p)),
                "pole_imag": float(np.imag(p)),
            }

            if Q_l > min_q:
                resonances.append(item)
            else:
                artifacts.append(item)

        resonances.sort(key=lambda x: x["fr"])
        artifacts.sort(key=lambda x: x["fr"])

        return {
            "resonances": resonances,
            "artifacts": artifacts,
        }
