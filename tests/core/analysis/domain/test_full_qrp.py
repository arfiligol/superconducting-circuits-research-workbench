"""Regression tests for the explicit full-QRP forward-response boundary."""

from __future__ import annotations

import numpy as np
import pytest
from superconducting_circuits_analysis.domain.math.full_qrp import (
    FullQRPModel,
    ThroughPortCoupling,
    diagnose_full_qrp_through_conditioning,
    evaluate_full_qrp_through,
    ideal_symmetric_hanger_coupling,
)


def test_full_qrp_forward_reduces_and_uses_one_effective_matrix() -> None:
    """The disconnected limit and coupled poles share the declared H_eff."""

    frequencies = np.linspace(5.8e9, 6.2e9, 401)
    disconnected = FullQRPModel(
        fq_hz=4.9e9,
        fr_hz=5.5e9,
        fp_hz=6.0e9,
        g_hz=0.0,
        g_qp_signed_hz=0.0,
        j_hz=0.0,
        decay_matrix_hz=np.diag([1.0e6, 2.0e6, 24.0e6]),
    )
    hanger = ideal_symmetric_hanger_coupling(
        20.0e6,
        direct_s21=0.97 * np.exp(0.13j),
    )
    reduced = evaluate_full_qrp_through(
        frequencies,
        model=disconnected,
        coupling=hanger,
    )
    expected = hanger.direct_s21 - (20.0e6 / 2.0) / (24.0e6 / 2.0 + 1j * (6.0e9 - frequencies))
    np.testing.assert_allclose(reduced.s21, expected, rtol=2.0e-14, atol=2.0e-14)
    np.testing.assert_allclose(
        reduced.poles_hz,
        np.asarray([4.9e9 - 0.5j * 1.0e6, 5.5e9 - 0.5j * 2.0e6, 6.0e9 - 0.5j * 24.0e6]),
        rtol=0.0,
        atol=1.0e-6,
    )
    np.testing.assert_allclose(
        reduced.s21_residues_hz,
        np.asarray([0.0j, 0.0j, -0.5j * 20.0e6]),
        rtol=3.0e-16,
        atol=1.0e-12,
    )

    coupled = FullQRPModel(
        fq_hz=5.91e9,
        fr_hz=5.98e9,
        fp_hz=6.04e9,
        g_hz=42.0e6,
        g_qp_signed_hz=-7.0e6,
        j_hz=25.0e6,
        decay_matrix_hz=np.asarray(
            [
                [1.2e6, 0.15e6, 0.0],
                [0.15e6, 3.0e6, 0.2e6],
                [0.0, 0.2e6, 28.0e6],
            ]
        ),
    )
    explicit_ports = ThroughPortCoupling(
        input_drive_sqrt_hz=np.asarray([0.0, 0.0, np.sqrt(9.0e6)]),
        output_response_sqrt_hz=np.asarray([0.0, 0.0, -np.sqrt(8.0e6)]),
        direct_s21=0.93 - 0.04j,
    )
    result = evaluate_full_qrp_through(
        frequencies,
        model=coupled,
        coupling=explicit_ports,
    )

    np.testing.assert_allclose(result.effective_matrix_hz, coupled.effective_matrix_hz)
    for pole in result.poles_hz:
        characteristic = np.linalg.det(result.effective_matrix_hz - pole * np.eye(3, dtype=complex))
        scale = max(float(np.max(np.abs(result.effective_matrix_hz))), 1.0) ** 3
        assert abs(characteristic) / scale < 2.0e-14
    np.testing.assert_allclose(result.linewidths_hz, -2.0 * np.imag(result.poles_hz))

    sample_index = 173
    response_matrix = 1j * (
        result.effective_matrix_hz - frequencies[sample_index] * np.eye(3, dtype=complex)
    )
    expected_sample = explicit_ports.direct_s21 + (
        explicit_ports.output_response_sqrt_hz
        @ np.linalg.solve(response_matrix, explicit_ports.input_drive_sqrt_hz)
    )
    assert result.s21[sample_index] == pytest.approx(expected_sample, rel=2.0e-14, abs=2.0e-14)


def test_complex_ports_reconstruct_from_sorted_transpose_left_residues() -> None:
    """General complex ports close with non-conjugating transpose-left modes."""

    decay_matrix_hz = np.asarray(
        [
            [1.8e6, 0.20e6 + 0.08e6j, -0.04e6j],
            [0.20e6 - 0.08e6j, 3.2e6, 0.15e6 + 0.03e6j],
            [0.04e6j, 0.15e6 - 0.03e6j, 26.0e6],
        ]
    )
    model = FullQRPModel(
        fq_hz=5.87e9,
        fr_hz=5.99e9,
        fp_hz=6.08e9,
        g_hz=37.0e6,
        g_qp_signed_hz=-9.0e6,
        j_hz=28.0e6,
        decay_matrix_hz=decay_matrix_hz,
    )
    coupling = ThroughPortCoupling(
        input_drive_sqrt_hz=1.0e3 * np.asarray([0.4 + 0.2j, -0.3 + 0.5j, 2.1 - 0.1j]),
        output_response_sqrt_hz=1.0e3 * np.asarray([-0.2 + 0.6j, 0.7 - 0.4j, -1.8 - 0.3j]),
        direct_s21=0.91 + 0.07j,
    )
    result = evaluate_full_qrp_through(
        np.linspace(5.72e9, 6.22e9, 1001),
        model=model,
        coupling=coupling,
    )

    reconstructed = coupling.direct_s21 + np.sum(
        result.s21_residues_hz[None, :] / (result.frequency_hz[:, None] - result.poles_hz[None, :]),
        axis=1,
    )
    np.testing.assert_allclose(reconstructed, result.s21, rtol=3.0e-12, atol=3.0e-12)

    spectral_center_hz = np.trace(result.effective_matrix_hz) / 3
    raw_poles, right_eigenvectors = np.linalg.eig(
        result.effective_matrix_hz - spectral_center_hz * np.eye(3, dtype=complex)
    )
    raw_poles = raw_poles + spectral_center_hz
    order = np.lexsort((raw_poles.imag, raw_poles.real))
    sorted_poles = raw_poles[order]
    right_eigenvectors = right_eigenvectors[:, order]
    transpose_left_eigenvectors = np.linalg.inv(right_eigenvectors)
    expected_residues = (
        1j
        * (coupling.output_response_sqrt_hz @ right_eigenvectors)
        * (transpose_left_eigenvectors @ coupling.input_drive_sqrt_hz)
    )
    np.testing.assert_allclose(result.poles_hz, sorted_poles, rtol=0.0, atol=0.0)
    np.testing.assert_allclose(
        result.s21_residues_hz,
        expected_residues,
        rtol=3.0e-13,
        atol=1.0e-8,
    )


def test_narrow_q_like_pole_closes_after_common_carrier_centering() -> None:
    """GHz carrier removal preserves strict residues near a narrow pole."""

    model = FullQRPModel(
        fq_hz=5.370e9,
        fr_hz=5.518e9,
        fp_hz=5.522e9,
        g_hz=80.0e6,
        g_qp_signed_hz=-15.0e6,
        j_hz=18.0e6,
        decay_matrix_hz=np.diag([0.0, 0.0, 24.0e6]),
    )
    coupling = ideal_symmetric_hanger_coupling(24.0e6)
    result = evaluate_full_qrp_through(
        np.linspace(5.17e9, 5.87e9, 401),
        model=model,
        coupling=coupling,
    )

    reconstructed = coupling.direct_s21 + np.sum(
        result.s21_residues_hz[None, :] / (result.frequency_hz[:, None] - result.poles_hz[None, :]),
        axis=1,
    )
    np.testing.assert_allclose(reconstructed, result.s21, rtol=2.0e-12, atol=2.0e-12)
    assert np.min(result.linewidths_hz) < 0.5e6


@pytest.mark.parametrize("slot_hz", [5.9e9, 6.0e9, 6.1e9, 6.2e9])
def test_target_slot_direct_resolvent_uses_the_same_centered_frame(slot_hz: float) -> None:
    """Target substitution closes when a sample approaches its dark pole."""

    model = FullQRPModel(
        fq_hz=slot_hz - 150.0e6,
        fr_hz=slot_hz - 1.0e6,
        fp_hz=slot_hz + 1.0e6,
        g_hz=90.0e6,
        g_qp_signed_hz=-15.0e6,
        j_hz=20.0e6,
        decay_matrix_hz=np.diag([0.0, 0.0, 25.0e6]),
    )
    coupling = ideal_symmetric_hanger_coupling(25.0e6)
    result = evaluate_full_qrp_through(
        np.linspace(slot_hz - 347.0e6, slot_hz + 353.0e6, 401),
        model=model,
        coupling=coupling,
    )

    reconstructed = coupling.direct_s21 + np.sum(
        result.s21_residues_hz[None, :] / (result.frequency_hz[:, None] - result.poles_hz[None, :]),
        axis=1,
    )
    np.testing.assert_allclose(reconstructed, result.s21, rtol=2.0e-12, atol=2.0e-12)


def test_conditioning_evidence_exposes_pole_aware_subset_without_relaxing_limit() -> None:
    """The diagnostic exposes unsafe dark-pole samples that evaluation rejects."""

    model = FullQRPModel(
        fq_hz=4.681e9,
        fr_hz=5.999e9,
        fp_hz=6.001e9,
        g_hz=90.0e6,
        g_qp_signed_hz=1.573e6,
        j_hz=20.0e6,
        decay_matrix_hz=np.diag([0.0, 0.0, 25.0e6]),
    )
    coupling = ideal_symmetric_hanger_coupling(25.0e6)
    probe = diagnose_full_qrp_through_conditioning(
        np.asarray([4.0e9]),
        model=model,
        coupling=coupling,
    )
    dark_pole = probe.poles_hz[np.argmin(-2.0 * np.imag(probe.poles_hz))]
    frequencies = np.asarray([dark_pole.real - 50.0e3, dark_pole.real - 10.0e3])
    evidence = diagnose_full_qrp_through_conditioning(
        frequencies,
        model=model,
        coupling=coupling,
    )

    limit = evidence.maximum_allowed_normalized_spectral_backward_bound
    assert limit == 1.0e-8
    assert evidence.normalized_spectral_backward_bound[0] < limit
    assert evidence.normalized_spectral_backward_bound[1] > limit
    assert evidence.observed_maximum_normalized_spectral_backward_bound == pytest.approx(
        evidence.normalized_spectral_backward_bound[1]
    )
    for value in (
        evidence.frequency_hz,
        evidence.normalized_spectral_backward_bound,
        evidence.poles_hz,
        evidence.s21_residues_hz,
    ):
        assert not value.flags.writeable

    with pytest.raises(ValueError, match="numerically unresolved"):
        evaluate_full_qrp_through(frequencies, model=model, coupling=coupling)
    safe = evidence.normalized_spectral_backward_bound <= limit
    accepted = evaluate_full_qrp_through(
        evidence.frequency_hz[safe],
        model=model,
        coupling=coupling,
    )
    np.testing.assert_array_equal(accepted.frequency_hz, frequencies[:1])


def test_repeated_defective_pole_rejects_simple_pole_residues() -> None:
    """A PSD-decay exceptional point cannot emit non-unique simple residues."""

    coupling_hz = 1.0e6
    model = FullQRPModel(
        fq_hz=6.0e9,
        fr_hz=6.0e9,
        fp_hz=6.2e9,
        g_hz=coupling_hz,
        g_qp_signed_hz=0.0,
        j_hz=0.0,
        decay_matrix_hz=np.asarray(
            [
                [4.0e6, 2.0j * coupling_hz, 0.0],
                [-2.0j * coupling_hz, 4.0e6, 0.0],
                [0.0, 0.0, 20.0e6],
            ]
        ),
    )
    ports = ThroughPortCoupling(
        input_drive_sqrt_hz=np.asarray([1.0e3, -0.5e3j, 0.2e3]),
        output_response_sqrt_hz=np.asarray([0.3e3j, -0.8e3, 0.4e3]),
        direct_s21=1.0,
    )
    with pytest.raises(ValueError, match="simple-pole residues require"):
        evaluate_full_qrp_through(
            np.linspace(5.8e9, 6.3e9, 101),
            model=model,
            coupling=ports,
        )


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("g_hz", -1.0, "g_hz must be nonnegative"),
        ("g_qp_signed_hz", np.inf, "g_qp_signed_hz must be finite"),
    ],
)
def test_full_qrp_model_rejects_invalid_explicit_rates(
    field: str,
    value: float,
    message: str,
) -> None:
    """Invalid explicit rates fail before response evaluation."""

    values = {
        "fq_hz": 5.9e9,
        "fr_hz": 6.0e9,
        "fp_hz": 6.1e9,
        "g_hz": 20.0e6,
        "g_qp_signed_hz": -4.0e6,
        "j_hz": 25.0e6,
        "decay_matrix_hz": np.diag([1.0e6, 2.0e6, 20.0e6]),
    }
    values[field] = value
    with pytest.raises(ValueError, match=message):
        FullQRPModel(**values)


def test_full_qrp_rejects_nonphysical_decay_and_malformed_ports() -> None:
    """Decay and port-shape contracts reject ambiguous forward inputs."""

    with pytest.raises(ValueError, match="positive semidefinite"):
        FullQRPModel(
            fq_hz=5.9e9,
            fr_hz=6.0e9,
            fp_hz=6.1e9,
            g_hz=20.0e6,
            g_qp_signed_hz=-4.0e6,
            j_hz=25.0e6,
            decay_matrix_hz=np.diag([1.0e6, -2.0e6, 20.0e6]),
        )
    with pytest.raises(ValueError, match=r"input_drive_sqrt_hz must have shape \(3,\)"):
        ThroughPortCoupling(
            input_drive_sqrt_hz=np.ones(2),
            output_response_sqrt_hz=np.ones(3),
            direct_s21=1.0,
        )
