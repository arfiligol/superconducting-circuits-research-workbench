from __future__ import annotations

import json

import numpy as np
from superconducting_circuits_analysis.application.analysis.fitting.s_parameters import (
    fit_complex_s21_notch,
    fit_complex_s21_transmission,
    fit_complex_s21_vector,
)
from superconducting_circuits_analysis.domain.math.s_parameters import (
    MultiResonanceVectorFitter,
    notch_s21,
    transmission_s21,
)


def _notch_initial_guess() -> dict[str, float]:
    return {
        "fr_hz": 5.0e9,
        "ql": 3000.0,
        "qc_real": 4500.0,
        "qc_imag": 300.0,
        "amplitude": 0.9,
        "phase_rad": 0.1,
        "delay_s": 1.0e-10,
    }


def test_fit_complex_s21_notch_recovers_synthetic_resonance(capsys) -> None:
    frequencies_hz = np.linspace(4.98e9, 5.02e9, 401)
    s21 = notch_s21(
        frequencies_hz,
        fr=5.0e9,
        Ql=3000.0,
        Qc_real=4500.0,
        Qc_imag=300.0,
        a=0.9,
        alpha=0.1,
        tau=1.0e-10,
    )

    result = fit_complex_s21_notch(
        frequencies_hz,
        s21.real,
        s21.imag,
        initial_guess=_notch_initial_guess(),
    )

    captured = capsys.readouterr()
    assert captured.out == ""
    assert result["status"] == "success"
    assert np.isclose(result["params"]["fr_hz"], 5.0e9, rtol=0.0, atol=1.0e-5)
    assert np.isclose(result["params"]["ql"], 3000.0, rtol=1.0e-12)
    assert result["params"]["qi_status"] == "finite"
    assert set(result["metrics"]) == {"complex_s21_rmse", "least_squares_cost"}
    assert result["metrics"]["complex_s21_rmse"] < 1.0e-12
    assert result["fit_settings"]["internal_parameterization"] == "centered_scaled_notch"
    assert result["fit_settings"]["loss"] == "linear"
    assert result["fit_window_hz"] == [frequencies_hz[0], frequencies_hz[-1]]
    assert result["requested_fit_window_hz"] is None
    assert result["initial_guess"] == _notch_initial_guess()
    assert result["optimizer"]["nfev"] >= 1
    assert len(result["fit_curve"]["frequency_hz"]) == len(frequencies_hz)
    json.dumps(result, allow_nan=False)


def test_fit_complex_s21_notch_handles_small_noise() -> None:
    rng = np.random.default_rng(1234)
    frequencies_hz = np.linspace(4.98e9, 5.02e9, 401)
    clean_s21 = notch_s21(
        frequencies_hz,
        fr=5.0e9,
        Ql=3000.0,
        Qc_real=4500.0,
        Qc_imag=300.0,
        a=0.9,
        alpha=0.1,
        tau=1.0e-10,
    )
    noisy_s21 = (
        clean_s21
        + rng.normal(0.0, 1.0e-4, len(frequencies_hz))
        + 1j * rng.normal(0.0, 1.0e-4, len(frequencies_hz))
    )

    result = fit_complex_s21_notch(
        frequencies_hz,
        noisy_s21.real,
        noisy_s21.imag,
        initial_guess=_notch_initial_guess(),
    )

    assert result["status"] == "success"
    assert abs(result["params"]["fr_hz"] - 5.0e9) < 1.0e6
    assert result["metrics"]["complex_s21_rmse"] < 5.0e-4


def test_fit_complex_s21_notch_recovers_independent_shunt_rlc() -> None:
    resonance_hz = 6.0e9
    angular_resonance = 2.0 * np.pi * resonance_hz
    reference_impedance_ohm = 50.0
    expected_qc = 500.0
    expected_qi = 10_000.0
    inductance_h = expected_qc * reference_impedance_ohm / (2.0 * angular_resonance)
    capacitance_f = 1.0 / (angular_resonance**2 * inductance_h)
    resistance_ohm = angular_resonance * inductance_h / expected_qi
    expected_ql = 1.0 / (1.0 / expected_qi + 1.0 / expected_qc)

    frequencies_hz = np.linspace(resonance_hz - 60.0e6, resonance_hz + 60.0e6, 1201)
    angular_frequency = 2.0 * np.pi * frequencies_hz
    series_impedance = resistance_ohm + 1j * (
        angular_frequency * inductance_h - 1.0 / (angular_frequency * capacitance_f)
    )
    s21 = 2.0 * series_impedance / (2.0 * series_impedance + reference_impedance_ohm)
    s21 *= 0.91 * np.exp(0.22j) * np.exp(-2j * np.pi * frequencies_hz * 83.0e-12)

    result = fit_complex_s21_notch(frequencies_hz, s21.real, s21.imag)

    assert result["status"] == "success"
    # These tolerances freeze numerical recovery of an independently derived
    # circuit response; they are not fit-acceptance thresholds.
    assert abs(result["params"]["fr_hz"] - resonance_hz) < 5.0e3
    assert np.isclose(result["params"]["ql"], expected_ql, rtol=1.0e-5)
    assert np.isclose(result["params"]["qc_real"], expected_qc, rtol=1.0e-5)
    assert np.isclose(result["params"]["qi"], expected_qi, rtol=1.0e-5)
    assert result["params"]["qi_status"] == "finite"
    assert result["metrics"]["complex_s21_rmse"] < 1.0e-8


def test_fit_complex_s21_notch_rejects_unbracketed_window() -> None:
    frequencies_hz = np.linspace(4.98e9, 5.0e9, 201)
    s21 = notch_s21(
        frequencies_hz,
        fr=5.0e9,
        Ql=3000.0,
        Qc_real=4500.0,
        Qc_imag=0.0,
        a=1.0,
        alpha=0.0,
        tau=0.0,
    )

    result = fit_complex_s21_notch(frequencies_hz, s21.real, s21.imag)

    assert result["status"] == "failed"
    assert "does not bracket" in result["reason"]


def test_fit_complex_s21_notch_rejects_unidentified_auto_initializer() -> None:
    result = fit_complex_s21_notch(
        [4.99e9, 5.0e9, 5.01e9],
        [1.0, 0.5, 1.0],
        [0.0, 0.0, 0.0],
    )

    assert result["status"] == "failed"
    assert "cannot identify a half-power span" in result["reason"]
    assert "explicit initial_guess" in result["reason"]


def test_fit_complex_s21_notch_enforces_canonical_initial_guess() -> None:
    frequencies_hz = np.linspace(4.98e9, 5.02e9, 401)
    s21 = notch_s21(
        frequencies_hz,
        fr=5.0e9,
        Ql=3000.0,
        Qc_real=4500.0,
        Qc_imag=300.0,
        a=0.9,
        alpha=0.1,
        tau=1.0e-10,
    )
    canonical = _notch_initial_guess()
    invalid_guesses = (
        {key: value for key, value in canonical.items() if key != "delay_s"},
        {**canonical, "fr": canonical["fr_hz"]},
        {**canonical, "ql": True},
        {**canonical, "ql": "3000"},
        {**canonical, "ql": np.inf},
        {**canonical, "ql": 0.0},
        {**canonical, "qc_real": 0.0, "qc_imag": 0.0},
        {**canonical, "fr_hz": frequencies_hz[0]},
    )

    for initial_guess in invalid_guesses:
        result = fit_complex_s21_notch(
            frequencies_hz,
            s21.real,
            s21.imag,
            initial_guess=initial_guess,
        )
        assert result["status"] == "failed"


def test_fit_complex_s21_notch_reports_exact_qi_status() -> None:
    frequencies_hz = np.linspace(4.99e9, 5.01e9, 401)
    cases = (
        (4500.0, "finite", False),
        (3000.0, "lossless_boundary", True),
        (3000.0 / 1.1, "nonphysical", True),
    )

    for qc_real, expected_status, expect_null_qi in cases:
        s21 = notch_s21(
            frequencies_hz,
            fr=5.0e9,
            Ql=3000.0,
            Qc_real=qc_real,
            Qc_imag=0.0,
            a=1.0,
            alpha=0.0,
            tau=0.0,
        )
        result = fit_complex_s21_notch(
            frequencies_hz,
            s21.real,
            s21.imag,
            initial_guess={
                "fr_hz": 5.0e9,
                "ql": 3000.0,
                "qc_real": qc_real,
                "qc_imag": 0.0,
                "amplitude": 1.0,
                "phase_rad": 0.0,
                "delay_s": 0.0,
            },
        )

        assert result["status"] == "success"
        assert result["params"]["qi_status"] == expected_status
        assert (result["params"]["qi"] is None) is expect_null_qi
        if expected_status == "lossless_boundary":
            assert result["params"]["inverse_qi"] == 0.0
        elif expected_status == "nonphysical":
            assert result["params"]["inverse_qi"] < 0.0
        else:
            assert result["params"]["inverse_qi"] > 0.0


def test_fit_complex_s21_notch_uses_stable_curve_for_huge_finite_delay() -> None:
    frequency_center_hz = 5.0e9
    frequency_scale_hz = 20.0e6
    frequencies_hz = np.linspace(
        frequency_center_hz - frequency_scale_hz,
        frequency_center_hz + frequency_scale_hz,
        401,
    )
    normalized_frequency = (frequencies_hz - frequency_center_hz) / frequency_scale_hz
    delay_s = 5.71e297
    phase_rad = 2.0 * np.pi * frequency_center_hz * delay_s
    ql = 3000.0
    qc = 4500.0 + 300.0j
    coupling = ql / qc
    delay_phase = 2.0 * np.pi * frequency_scale_hz * delay_s
    detuning = (frequencies_hz - frequency_center_hz) / frequency_center_hz
    s21 = np.exp(-1j * delay_phase * normalized_frequency) * (
        1.0 - coupling / (1.0 + 2j * ql * detuning)
    )

    with np.errstate(over="ignore", invalid="ignore"):
        result = fit_complex_s21_notch(
            frequencies_hz,
            s21.real,
            s21.imag,
            initial_guess={
                "fr_hz": frequency_center_hz,
                "ql": ql,
                "qc_real": qc.real,
                "qc_imag": qc.imag,
                "amplitude": 1.0,
                "phase_rad": phase_rad,
                "delay_s": delay_s,
            },
        )

    assert result["status"] == "success"
    assert all(value is not None for value in result["metrics"].values())
    assert all(
        value is not None
        for key in ("frequency_hz", "s21_real", "s21_imag")
        for value in result["fit_curve"][key]
    )
    json.dumps(result, allow_nan=False)


def test_fit_complex_s21_notch_distinguishes_requested_and_sampled_windows() -> None:
    frequencies_hz = np.linspace(4.98e9, 5.02e9, 401)
    s21 = notch_s21(
        frequencies_hz,
        fr=5.0e9,
        Ql=3000.0,
        Qc_real=4500.0,
        Qc_imag=300.0,
        a=0.9,
        alpha=0.1,
        tau=1.0e-10,
    )
    requested_window = (4.98505e9, 5.01495e9)
    selected = frequencies_hz[
        (frequencies_hz >= requested_window[0]) & (frequencies_hz <= requested_window[1])
    ]

    result = fit_complex_s21_notch(
        frequencies_hz,
        s21.real,
        s21.imag,
        fit_window_hz=requested_window,
    )

    assert result["status"] == "success"
    assert result["requested_fit_window_hz"] == list(requested_window)
    assert result["fit_window_hz"] == [selected[0], selected[-1]]
    assert result["fit_window_hz"] != result["requested_fit_window_hz"]
    assert result["fit_settings"]["resonance_frequency_bounds_hz"] == result["fit_window_hz"]


def test_fit_complex_s21_transmission_returns_plain_result() -> None:
    frequencies_hz = np.linspace(4.95e9, 5.05e9, 401)
    s21 = transmission_s21(
        frequencies_hz,
        fr=5.0e9,
        Ql=800.0,
        a=0.8,
        alpha=0.2,
        tau=2.0e-10,
    )

    result = fit_complex_s21_transmission(
        frequencies_hz,
        s21.real,
        s21.imag,
        initial_guess={
            "fr_hz": 5.0e9,
            "ql": 800.0,
            "amplitude": 0.8,
            "phase_rad": 0.2,
            "delay_s": 2.0e-10,
        },
    )

    assert result["status"] == "success"
    assert result["params"]["fr_hz"] == 5.0e9
    assert result["params"]["ql"] == 800.0
    json.dumps(result)


def test_fit_complex_s21_rejects_invalid_input() -> None:
    result = fit_complex_s21_notch([1.0, 2.0], [0.0], [0.0])

    assert result["status"] == "failed"
    assert "same length" in result["reason"]


def test_scalar_s21_vector_carrier_contains_exactly_the_input_response() -> None:
    frequencies_hz = np.array([1.0e9, 2.0e9, 3.0e9])
    s21 = np.array([0.1 + 0.2j, 0.3 - 0.4j, -0.5 + 0.6j])

    carrier = MultiResonanceVectorFitter(
        frequencies_hz,
        s21,
    )._create_scalar_response_carrier()

    assert carrier.s.shape == (len(frequencies_hz), 1, 1)
    np.testing.assert_array_equal(carrier.s[:, 0, 0], s21)


def test_fit_complex_s21_vector_recovers_two_resonances() -> None:
    frequencies_hz = np.linspace(5.7e9, 6.5e9, 401)
    s21 = (
        transmission_s21(
            frequencies_hz,
            fr=6.05e9,
            Ql=60.0,
            a=0.7,
            alpha=0.0,
            tau=0.0,
        )
        + 0.4
        * transmission_s21(
            frequencies_hz,
            fr=6.30e9,
            Ql=800.0,
            a=0.8,
            alpha=0.0,
            tau=0.0,
        )
        + 0.02
    )

    result = fit_complex_s21_vector(
        frequencies_hz,
        s21.real,
        s21.imag,
        n_resonators=2,
        bg_poles=2,
        min_q=2.0,
    )

    assert result["status"] == "success"
    assert result["model"] == "scalar_s21_vector"
    assert result["fit_settings"] == {
        "n_resonators": 2,
        "bg_poles": 2,
        "min_q": 2.0,
        "restrict_to_input_span": True,
    }
    assert len(result["model_trace"]["frequency_hz"]) == len(frequencies_hz)
    assert [round(item["fr_hz"] / 1e9, 2) for item in result["resonances"]] == [6.05, 6.3]
    assert all(item["bandwidth_hz"] is not None for item in result["resonances"])
    model_s21 = np.asarray(result["model_trace"]["s21_real"]) + 1j * np.asarray(
        result["model_trace"]["s21_imag"]
    )
    scalar_rmse = float(np.sqrt(np.mean(np.abs(model_s21 - s21) ** 2)))
    assert scalar_rmse > 0.0
    assert np.isclose(result["metrics"]["rms_error"], scalar_rmse, rtol=1.0e-13)
    assert not np.isclose(
        result["metrics"]["rms_error"],
        np.sqrt(2.0) * scalar_rmse,
        rtol=1.0e-6,
    )
    json.dumps(result)


def test_fit_complex_s21_vector_rejects_implicit_coercions_and_nonfinite_min_q() -> None:
    frequencies_hz = np.linspace(5.7e9, 6.5e9, 11)
    s21 = np.ones_like(frequencies_hz, dtype=complex)
    invalid_settings = (
        {"n_resonators": 1.9, "bg_poles": 2, "min_q": 2.0},
        {"n_resonators": True, "bg_poles": 2, "min_q": 2.0},
        {"n_resonators": 1, "bg_poles": 1.9, "min_q": 2.0},
        {"n_resonators": 1, "bg_poles": False, "min_q": 2.0},
        {"n_resonators": 1, "bg_poles": 2, "min_q": np.inf},
        {"n_resonators": 1, "bg_poles": 2, "min_q": True},
        {
            "n_resonators": 1,
            "bg_poles": 2,
            "min_q": 2.0,
            "restrict_to_input_span": "false",
        },
        {
            "n_resonators": 1,
            "bg_poles": 2,
            "min_q": 2.0,
            "restrict_to_input_span": 0,
        },
    )

    for settings in invalid_settings:
        result = fit_complex_s21_vector(
            frequencies_hz,
            s21.real,
            s21.imag,
            **settings,
        )
        assert result["status"] == "failed"
