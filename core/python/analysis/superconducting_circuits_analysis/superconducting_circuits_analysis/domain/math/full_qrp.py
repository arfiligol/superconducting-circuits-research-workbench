"""Forward-only full-QRP through-transmission response.

This module owns the numerical response boundary for an explicitly specified
open three-mode qubit/readout/Purcell model.  It evaluates complex through-S21
and hybridized poles from the same effective matrix under the
``exp(-i * 2*pi*f*t)`` convention.  Parameter inference, fitting, optimization,
and circuit-to-Hamiltonian extraction belong to other layers.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

_MODE_COUNT = 3
_P_MODE_INDEX = 2
_MAX_EIGENVECTOR_CONDITION = 1.0e8
_MIN_SIMPLE_POLE_SEPARATION_RELATIVE = 1.0e-8
_RECONSTRUCTION_ROUNDOFF_FACTOR = 4096.0
_MAX_SPECTRAL_BACKWARD_BOUND_RELATIVE = 1.0e-8


@dataclass(frozen=True, slots=True)
class FullQRPModel:
    """Describe one explicit open q-r-p model in frequency units.

    The conservative Hamiltonian uses coordinate order ``(q, r, p)``.  The
    q-p coupling is deliberately named ``g_qp_signed_hz`` because its sign is
    physically relevant once the signs of ``g_hz`` and ``j_hz`` are fixed.
    ``decay_matrix_hz`` is the total energy-decay/linewidth matrix ``Gamma``
    used in ``H_eff = H - i*Gamma/2``; the coherent-amplitude generator
    therefore contains ``-Gamma/2``. It may contain correlated decay terms.

    Args:
        fq_hz: Qubit-mode frequency in hertz.
        fr_hz: Readout-mode frequency in hertz.
        fp_hz: Purcell-filter-mode frequency in hertz.
        g_hz: Nonnegative q-r conservative coupling rate in hertz.
        g_qp_signed_hz: Signed q-p conservative coupling rate in hertz.
        j_hz: Nonnegative r-p conservative coupling rate in hertz.
        decay_matrix_hz: Hermitian positive-semidefinite 3-by-3 total
            energy-decay/linewidth matrix in hertz, ordered as ``(q, r, p)``.

    Raises:
        ValueError: If a frequency, coupling, or decay-matrix invariant is
            invalid.
    """

    fq_hz: float
    fr_hz: float
    fp_hz: float
    g_hz: float
    g_qp_signed_hz: float
    j_hz: float
    decay_matrix_hz: np.ndarray

    def __post_init__(self) -> None:
        for name in ("fq_hz", "fr_hz", "fp_hz"):
            value = _finite_real(getattr(self, name), name)
            if value <= 0.0:
                raise ValueError(f"{name} must be positive.")
            object.__setattr__(self, name, value)

        for name in ("g_hz", "j_hz"):
            value = _finite_real(getattr(self, name), name)
            if value < 0.0:
                raise ValueError(f"{name} must be nonnegative.")
            object.__setattr__(self, name, value)

        object.__setattr__(
            self,
            "g_qp_signed_hz",
            _finite_real(self.g_qp_signed_hz, "g_qp_signed_hz"),
        )
        object.__setattr__(
            self,
            "decay_matrix_hz",
            _validated_decay_matrix(self.decay_matrix_hz),
        )

    @property
    def hamiltonian_hz(self) -> np.ndarray:
        """Return the real symmetric conservative Hamiltonian in q-r-p order."""

        return np.asarray(
            [
                [self.fq_hz, self.g_hz, self.g_qp_signed_hz],
                [self.g_hz, self.fr_hz, self.j_hz],
                [self.g_qp_signed_hz, self.j_hz, self.fp_hz],
            ],
            dtype=complex,
        )

    @property
    def effective_matrix_hz(self) -> np.ndarray:
        """Return ``H_eff = H - i*Gamma/2`` for ``exp(-i*2*pi*f*t)``."""

        return self.hamiltonian_hz - 0.5j * self.decay_matrix_hz


@dataclass(frozen=True, slots=True)
class ThroughPortCoupling:
    """Describe the explicit input/output projection for through-S21.

    The response is
    ``S21 = direct_s21 + d2.T @ chi @ k1``.  The transpose is intentionally
    non-conjugating: callers supply the complex phase and sign of both port
    vectors.  This object does not infer port coupling from the total decay
    matrix.

    Args:
        input_drive_sqrt_hz: Three-element input vector ``k1`` in ``sqrt(Hz)``.
        output_response_sqrt_hz: Three-element output vector ``d2`` in
            ``sqrt(Hz)``.
        direct_s21: Explicit frequency-independent complex direct path.

    Raises:
        ValueError: If a vector has the wrong shape or any value is non-finite.
    """

    input_drive_sqrt_hz: np.ndarray
    output_response_sqrt_hz: np.ndarray
    direct_s21: complex

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "input_drive_sqrt_hz",
            _validated_port_vector(self.input_drive_sqrt_hz, "input_drive_sqrt_hz"),
        )
        object.__setattr__(
            self,
            "output_response_sqrt_hz",
            _validated_port_vector(
                self.output_response_sqrt_hz,
                "output_response_sqrt_hz",
            ),
        )
        object.__setattr__(self, "direct_s21", _finite_complex(self.direct_s21, "direct_s21"))


@dataclass(frozen=True, slots=True)
class FullQRPForwardResult:
    """Carry one evaluated trace and its same-matrix open-mode evidence."""

    frequency_hz: np.ndarray
    s21: np.ndarray
    poles_hz: np.ndarray
    s21_residues_hz: np.ndarray
    linewidths_hz: np.ndarray
    effective_matrix_hz: np.ndarray


@dataclass(frozen=True, slots=True)
class FullQRPConditioningEvidence:
    """Carry deterministic conditioning evidence for one Full-QRP grid.

    ``normalized_spectral_backward_bound`` is the spectral perturbation bound
    divided by the response scale at each frequency; it is not divided by the
    allowed limit.  Pole and residue arrays share the same frequency ordering.
    All array fields are immutable copies.
    """

    frequency_hz: np.ndarray
    normalized_spectral_backward_bound: np.ndarray
    poles_hz: np.ndarray
    s21_residues_hz: np.ndarray
    spectral_backward_error_hz: float
    right_eigenvector_condition: float

    def __post_init__(self) -> None:
        frequencies = _validated_frequency_grid(self.frequency_hz)
        normalized_bound = np.asarray(
            self.normalized_spectral_backward_bound,
            dtype=float,
        ).copy()
        poles = np.asarray(self.poles_hz, dtype=complex).copy()
        residues = np.asarray(self.s21_residues_hz, dtype=complex).copy()
        if normalized_bound.shape != frequencies.shape:
            raise ValueError(
                "normalized_spectral_backward_bound must align with frequency_hz."
            )
        if not np.all(np.isfinite(normalized_bound)) or np.any(normalized_bound < 0.0):
            raise ValueError(
                "normalized_spectral_backward_bound values must be finite and nonnegative."
            )
        if poles.shape != (_MODE_COUNT,) or not np.all(np.isfinite(poles)):
            raise ValueError("poles_hz must contain three finite Full-QRP poles.")
        if residues.shape != (_MODE_COUNT,) or not np.all(np.isfinite(residues)):
            raise ValueError("s21_residues_hz must contain three finite aligned residues.")
        spectral_backward_error_hz = _finite_real(
            self.spectral_backward_error_hz,
            "spectral_backward_error_hz",
        )
        if spectral_backward_error_hz < 0.0:
            raise ValueError("spectral_backward_error_hz must be nonnegative.")
        right_eigenvector_condition = _finite_real(
            self.right_eigenvector_condition,
            "right_eigenvector_condition",
        )
        if right_eigenvector_condition < 1.0:
            raise ValueError("right_eigenvector_condition must be at least one.")
        for value in (frequencies, normalized_bound, poles, residues):
            value.setflags(write=False)
        object.__setattr__(self, "frequency_hz", frequencies)
        object.__setattr__(self, "normalized_spectral_backward_bound", normalized_bound)
        object.__setattr__(self, "poles_hz", poles)
        object.__setattr__(self, "s21_residues_hz", residues)
        object.__setattr__(self, "spectral_backward_error_hz", spectral_backward_error_hz)
        object.__setattr__(self, "right_eigenvector_condition", right_eigenvector_condition)

    @property
    def maximum_allowed_normalized_spectral_backward_bound(self) -> float:
        """Return the immutable acceptance limit used by the evaluator."""

        return _MAX_SPECTRAL_BACKWARD_BOUND_RELATIVE

    @property
    def observed_maximum_normalized_spectral_backward_bound(self) -> float:
        """Return the largest normalized bound on the requested grid."""

        return float(np.max(self.normalized_spectral_backward_bound))


def ideal_symmetric_hanger_coupling(
    kappa_p_external_hz: float,
    *,
    direct_s21: complex = 1.0 + 0.0j,
) -> ThroughPortCoupling:
    """Build the declared ideal symmetric hanger through-port gauge.

    This gauge couples only to the Purcell coordinate and produces
    ``S21 = direct_s21 - (kappa_p_external_hz/2) * chi_pp``.  The supplied
    FullQRPModel must separately include this external rate, plus any internal
    loss, in its total decay matrix; this function does not alter the model.

    Args:
        kappa_p_external_hz: Total nonnegative external linewidth of the
            Purcell mode across the symmetric two-port through line.
        direct_s21: Explicit complex direct path, normally unity in this gauge.

    Returns:
        Explicit port vectors representing the ideal symmetric hanger gauge.

    Raises:
        ValueError: If the external linewidth or direct path is invalid.
    """

    external_rate = _finite_real(kappa_p_external_hz, "kappa_p_external_hz")
    if external_rate < 0.0:
        raise ValueError("kappa_p_external_hz must be nonnegative.")
    amplitude = np.sqrt(external_rate / 2.0)
    drive = np.zeros(_MODE_COUNT, dtype=complex)
    response = np.zeros(_MODE_COUNT, dtype=complex)
    drive[_P_MODE_INDEX] = amplitude
    response[_P_MODE_INDEX] = -amplitude
    return ThroughPortCoupling(
        input_drive_sqrt_hz=drive,
        output_response_sqrt_hz=response,
        direct_s21=direct_s21,
    )


def diagnose_full_qrp_through_conditioning(
    frequency_hz: np.ndarray,
    *,
    model: FullQRPModel,
    coupling: ThroughPortCoupling,
) -> FullQRPConditioningEvidence:
    """Return same-matrix Full-QRP numerical conditioning evidence.

    Unlike :func:`evaluate_full_qrp_through`, this diagnostic returns samples
    above the immutable backward-bound limit so a caller can construct and
    publish a pole-aware common subset.  All other model, grid, eigensystem,
    finiteness, and exact closure checks remain fail-fast.
    """

    _, conditioning = _evaluate_full_qrp_through_unchecked(
        frequency_hz,
        model=model,
        coupling=coupling,
    )
    return conditioning


def evaluate_full_qrp_through(
    frequency_hz: np.ndarray,
    *,
    model: FullQRPModel,
    coupling: ThroughPortCoupling,
) -> FullQRPForwardResult:
    """Evaluate Full-QRP through-S21 and same-matrix open poles without fitting.

    The response uses ``chi(f) = [i * (H_eff - f*I)]^-1``.  Poles and aligned
    scalar-S21 residues come from that exact ``H_eff`` under the
    ``exp(-i*2*pi*f*t)`` convention.  Samples whose normalized spectral
    backward bound exceeds the immutable ``1e-8`` limit are rejected.

    Args:
        frequency_hz: Positive, finite, strictly increasing frequency samples.
        model: Fully specified conservative and dissipative q-r-p model.
        coupling: Explicit through-port projection and direct path.

    Returns:
        Complex S21 samples and aligned pole, residue, and linewidth evidence.

    Raises:
        ValueError: If an input or physical invariant is invalid, a stable
            simple-pole decomposition is unavailable, exact closure fails, or
            any requested sample exceeds the backward-bound limit.
    """

    result, conditioning = _evaluate_full_qrp_through_unchecked(
        frequency_hz,
        model=model,
        coupling=coupling,
    )
    if np.any(
        conditioning.normalized_spectral_backward_bound
        > conditioning.maximum_allowed_normalized_spectral_backward_bound
    ):
        raise ValueError(
            "Full-QRP spectral decomposition is numerically unresolved at a sampled "
            "frequency under its backward-error bound."
        )
    return result


def _evaluate_full_qrp_through_unchecked(
    frequency_hz: np.ndarray,
    *,
    model: FullQRPModel,
    coupling: ThroughPortCoupling,
) -> tuple[FullQRPForwardResult, FullQRPConditioningEvidence]:
    """Run the shared response and conditioning path without enforcing its limit."""

    frequencies = _validated_frequency_grid(frequency_hz)
    effective_matrix = model.effective_matrix_hz
    identity = np.eye(_MODE_COUNT, dtype=complex)
    spectral_center_hz = np.trace(effective_matrix) / _MODE_COUNT
    centered_effective_matrix = effective_matrix - spectral_center_hz * identity
    s21 = np.empty(frequencies.shape, dtype=complex)

    for index, frequency in enumerate(frequencies):
        # Form the resolvent in the same carrier-centered frame used by the
        # pole solve.  Subtracting two GHz-scale diagonals directly loses
        # absolute accuracy precisely where a narrow pole needs it most.
        centered_frequency_hz = frequency - spectral_center_hz
        response_matrix = 1j * (centered_effective_matrix - centered_frequency_hz * identity)
        try:
            driven_state = np.linalg.solve(response_matrix, coupling.input_drive_sqrt_hz)
        except np.linalg.LinAlgError as exc:
            raise ValueError(
                f"Full-QRP response matrix is singular at frequency_hz[{index}]={frequency!r}."
            ) from exc
        s21[index] = coupling.direct_s21 + coupling.output_response_sqrt_hz @ driven_state

    if not np.all(np.isfinite(s21)):
        raise ValueError("Full-QRP through response contains non-finite S21 samples.")

    (
        poles,
        centered_poles,
        residues,
        eigenvector_condition,
        centered_spectral_matrix,
    ) = _sorted_poles_and_residues(effective_matrix, coupling)
    linewidths = -2.0 * np.imag(poles)
    numerical_tolerance = (
        128.0 * np.finfo(float).eps * max(float(np.max(np.abs(effective_matrix))), 1.0)
    )
    if np.any(linewidths < -numerical_tolerance):
        raise ValueError(
            "Full-QRP effective matrix produced a growing pole despite a "
            "positive-semidefinite decay matrix."
        )
    linewidths = np.maximum(linewidths, 0.0)
    conditioning = _validate_rational_reconstruction(
        frequencies=frequencies,
        direct_s21=coupling.direct_s21,
        poles_hz=poles,
        centered_poles_hz=centered_poles,
        residues_hz=residues,
        evaluated_s21=s21,
        eigenvector_condition=eigenvector_condition,
        effective_matrix_hz=effective_matrix,
        centered_spectral_matrix_hz=centered_spectral_matrix,
        coupling=coupling,
    )

    return (
        FullQRPForwardResult(
            frequency_hz=frequencies,
            s21=s21,
            poles_hz=poles,
            s21_residues_hz=residues,
            linewidths_hz=np.asarray(linewidths, dtype=float),
            effective_matrix_hz=effective_matrix,
        ),
        conditioning,
    )


def _sorted_poles_and_residues(
    effective_matrix_hz: np.ndarray,
    coupling: ThroughPortCoupling,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, float, np.ndarray]:
    # A common GHz carrier has no effect on the eigenvectors, but asking the
    # eigensolver to retain it degrades the absolute accuracy of a narrow pole.
    # Center the matrix before diagonalization and add the scalar carrier back
    # to the eigenvalues.  The direct response still uses the unshifted matrix,
    # so the pole/residue closure below independently checks this conditioning
    # step rather than weakening its tolerance.
    spectral_center_hz = np.trace(effective_matrix_hz) / _MODE_COUNT
    centered_matrix_hz = effective_matrix_hz - spectral_center_hz * np.eye(
        _MODE_COUNT,
        dtype=complex,
    )
    try:
        centered_poles, right_eigenvectors = np.linalg.eig(centered_matrix_hz)
    except np.linalg.LinAlgError as exc:
        raise ValueError("Full-QRP effective-matrix eigendecomposition failed.") from exc
    poles = centered_poles + spectral_center_hz
    if (
        poles.shape != (_MODE_COUNT,)
        or right_eigenvectors.shape != (_MODE_COUNT, _MODE_COUNT)
        or not np.all(np.isfinite(poles))
        or not np.all(np.isfinite(right_eigenvectors))
    ):
        raise ValueError("Full-QRP effective matrix did not produce finite simple-pole data.")

    matrix_scale_hz = max(float(np.linalg.norm(centered_matrix_hz, ord=2)), 1.0)
    separations_hz = np.abs(centered_poles[:, None] - centered_poles[None, :])
    minimum_separation_hz = float(np.min(separations_hz[np.triu_indices(_MODE_COUNT, k=1)]))
    separation_floor_hz = _MIN_SIMPLE_POLE_SEPARATION_RELATIVE * matrix_scale_hz
    if minimum_separation_hz <= separation_floor_hz:
        raise ValueError(
            "Full-QRP simple-pole residues require distinct poles separated by more than "
            f"{_MIN_SIMPLE_POLE_SEPARATION_RELATIVE:g} * "
            "||H_eff - trace(H_eff) I / 3||_2."
        )

    try:
        eigenvector_condition = float(np.linalg.cond(right_eigenvectors))
    except np.linalg.LinAlgError as exc:
        raise ValueError("Full-QRP right-eigenvector condition estimate failed.") from exc
    if not np.isfinite(eigenvector_condition) or eigenvector_condition > _MAX_EIGENVECTOR_CONDITION:
        raise ValueError(
            "Full-QRP simple-pole residues require an invertible right-eigenvector matrix "
            f"with condition number <= {_MAX_EIGENVECTOR_CONDITION:g}."
        )

    order = np.lexsort((poles.imag, poles.real))
    poles = poles[order]
    centered_poles = centered_poles[order]
    right_eigenvectors = right_eigenvectors[:, order]
    try:
        transpose_left_eigenvectors = np.linalg.inv(right_eigenvectors)
    except np.linalg.LinAlgError as exc:
        raise ValueError(
            "Full-QRP simple-pole residues require an invertible right-eigenvector matrix."
        ) from exc
    if not np.all(np.isfinite(transpose_left_eigenvectors)):
        raise ValueError("Full-QRP transpose-left eigenvectors contain non-finite values.")

    centered_spectral_matrix_hz = (
        right_eigenvectors @ np.diag(centered_poles) @ transpose_left_eigenvectors
    )
    if not np.all(np.isfinite(centered_spectral_matrix_hz)):
        raise ValueError(
            "Full-QRP centered spectral matrix reconstruction contains non-finite values."
        )

    residues_hz = (
        1j
        * (coupling.output_response_sqrt_hz @ right_eigenvectors)
        * (transpose_left_eigenvectors @ coupling.input_drive_sqrt_hz)
    )
    if residues_hz.shape != (_MODE_COUNT,) or not np.all(np.isfinite(residues_hz)):
        raise ValueError("Full-QRP scalar-S21 residues contain non-finite values.")
    return (
        poles,
        np.asarray(centered_poles, dtype=complex),
        np.asarray(residues_hz, dtype=complex),
        eigenvector_condition,
        np.asarray(centered_spectral_matrix_hz, dtype=complex),
    )


def _validate_rational_reconstruction(
    *,
    frequencies: np.ndarray,
    direct_s21: complex,
    poles_hz: np.ndarray,
    centered_poles_hz: np.ndarray,
    residues_hz: np.ndarray,
    evaluated_s21: np.ndarray,
    eigenvector_condition: float,
    effective_matrix_hz: np.ndarray,
    centered_spectral_matrix_hz: np.ndarray,
    coupling: ThroughPortCoupling,
) -> FullQRPConditioningEvidence:
    spectral_center_hz = np.trace(effective_matrix_hz) / _MODE_COUNT
    centered_frequencies_hz = frequencies - spectral_center_hz
    terms = residues_hz[None, :] / (centered_frequencies_hz[:, None] - centered_poles_hz[None, :])
    reconstructed_s21 = direct_s21 + np.sum(terms, axis=1)
    if not np.all(np.isfinite(reconstructed_s21)):
        raise ValueError("Full-QRP pole-residue reconstruction contains non-finite values.")

    scale = np.maximum(
        np.abs(direct_s21) + np.sum(np.abs(terms), axis=1),
        1.0,
    )
    tolerance = (
        _RECONSTRUCTION_ROUNDOFF_FACTOR
        * np.finfo(float).eps
        * max(eigenvector_condition, 1.0)
        * scale
    )
    identity = np.eye(_MODE_COUNT, dtype=complex)
    spectral_s21 = np.empty(frequencies.shape, dtype=complex)
    spectral_minimum_singular_values = np.empty(frequencies.shape, dtype=float)
    effective_minimum_singular_values = np.empty(frequencies.shape, dtype=float)
    centered_effective_matrix_hz = effective_matrix_hz - spectral_center_hz * identity
    for index, frequency in enumerate(frequencies):
        centered_frequency_hz = frequency - spectral_center_hz
        spectral_response_matrix = 1j * (
            centered_spectral_matrix_hz - centered_frequency_hz * identity
        )
        effective_response_matrix = 1j * (
            centered_effective_matrix_hz - centered_frequency_hz * identity
        )
        try:
            spectral_state = np.linalg.solve(
                spectral_response_matrix,
                coupling.input_drive_sqrt_hz,
            )
        except np.linalg.LinAlgError as exc:
            raise ValueError(
                "Full-QRP spectral response matrix is singular during residue closure."
            ) from exc
        spectral_s21[index] = direct_s21 + coupling.output_response_sqrt_hz @ spectral_state
        spectral_minimum_singular_values[index] = np.linalg.svd(
            spectral_response_matrix,
            compute_uv=False,
        )[-1]
        effective_minimum_singular_values[index] = np.linalg.svd(
            effective_response_matrix,
            compute_uv=False,
        )[-1]

    if not np.all(np.isfinite(spectral_s21)):
        raise ValueError("Full-QRP spectral response contains non-finite S21 samples.")
    if np.any(np.abs(reconstructed_s21 - spectral_s21) > tolerance):
        raise ValueError(
            "Full-QRP pole-residue reconstruction failed closure against the "
            "centered spectral evaluation."
        )

    minimum_singular_values = np.minimum(
        spectral_minimum_singular_values,
        effective_minimum_singular_values,
    )
    if np.any(~np.isfinite(minimum_singular_values)) or np.any(minimum_singular_values <= 0.0):
        raise ValueError("Full-QRP response conditioning is non-finite during spectral closure.")
    spectral_backward_error_hz = float(
        np.linalg.norm(
            centered_spectral_matrix_hz - centered_effective_matrix_hz,
            ord=2,
        )
    )
    port_norm_product_hz = float(
        np.linalg.norm(coupling.output_response_sqrt_hz)
        * np.linalg.norm(coupling.input_drive_sqrt_hz)
    )
    perturbation_bound = (
        port_norm_product_hz
        * spectral_backward_error_hz
        / (spectral_minimum_singular_values * effective_minimum_singular_values)
    )
    if not np.all(np.isfinite(perturbation_bound)):
        raise ValueError("Full-QRP spectral perturbation bound is non-finite.")
    if np.any(np.abs(spectral_s21 - evaluated_s21) > tolerance + perturbation_bound):
        raise ValueError(
            "Full-QRP centered spectral evaluation failed backward-error closure "
            "against the direct effective-matrix response."
        )
    return FullQRPConditioningEvidence(
        frequency_hz=frequencies,
        normalized_spectral_backward_bound=perturbation_bound / scale,
        poles_hz=poles_hz,
        s21_residues_hz=residues_hz,
        spectral_backward_error_hz=spectral_backward_error_hz,
        right_eigenvector_condition=eigenvector_condition,
    )


def _validated_frequency_grid(value: np.ndarray) -> np.ndarray:
    frequencies = np.asarray(value, dtype=float)
    if frequencies.ndim != 1 or frequencies.size == 0:
        raise ValueError("frequency_hz must be a nonempty one-dimensional array.")
    if not np.all(np.isfinite(frequencies)) or not np.all(frequencies > 0.0):
        raise ValueError("frequency_hz values must be positive and finite.")
    if frequencies.size > 1 and not np.all(np.diff(frequencies) > 0.0):
        raise ValueError("frequency_hz values must be strictly increasing.")
    return frequencies.copy()


def _validated_decay_matrix(value: np.ndarray) -> np.ndarray:
    matrix = np.asarray(value, dtype=complex)
    if matrix.shape != (_MODE_COUNT, _MODE_COUNT):
        raise ValueError("decay_matrix_hz must have shape (3, 3) in q-r-p order.")
    if not np.all(np.isfinite(matrix)):
        raise ValueError("decay_matrix_hz values must be finite.")
    scale = max(float(np.max(np.abs(matrix))), 1.0)
    tolerance = 128.0 * np.finfo(float).eps * scale
    if not np.allclose(matrix, matrix.conj().T, rtol=0.0, atol=tolerance):
        raise ValueError("decay_matrix_hz must be Hermitian.")
    hermitian = 0.5 * (matrix + matrix.conj().T)
    minimum_eigenvalue = float(np.min(np.linalg.eigvalsh(hermitian)))
    if minimum_eigenvalue < -tolerance:
        raise ValueError("decay_matrix_hz must be positive semidefinite.")
    validated = hermitian.copy()
    validated.setflags(write=False)
    return validated


def _validated_port_vector(value: np.ndarray, name: str) -> np.ndarray:
    vector = np.asarray(value, dtype=complex)
    if vector.shape != (_MODE_COUNT,):
        raise ValueError(f"{name} must have shape (3,) in q-r-p order.")
    if not np.all(np.isfinite(vector)):
        raise ValueError(f"{name} values must be finite.")
    validated = vector.copy()
    validated.setflags(write=False)
    return validated


def _finite_real(value: float, name: str) -> float:
    converted = float(value)
    if not np.isfinite(converted):
        raise ValueError(f"{name} must be finite.")
    return converted


def _finite_complex(value: complex, name: str) -> complex:
    converted = complex(value)
    if not np.isfinite(converted.real) or not np.isfinite(converted.imag):
        raise ValueError(f"{name} must be finite.")
    return converted


__all__ = [
    "FullQRPConditioningEvidence",
    "FullQRPForwardResult",
    "FullQRPModel",
    "ThroughPortCoupling",
    "diagnose_full_qrp_through_conditioning",
    "evaluate_full_qrp_through",
    "ideal_symmetric_hanger_coupling",
]
