from __future__ import annotations

import json

import numpy as np
from superconducting_circuits_analysis.application.analysis.fitting.s_parameters import (
    fit_complex_s21_notch,
    fit_complex_s21_transmission,
    fit_complex_s21_vector,
)
from superconducting_circuits_analysis.domain.math.s_parameters import (
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
    assert result["params"]["fr_hz"] == 5.0e9
    assert result["params"]["ql"] == 3000.0
    assert result["metrics"]["rmse"] == 0.0
    assert len(result["fit_curve"]["frequency_hz"]) == len(frequencies_hz)


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
    assert result["metrics"]["rmse"] < 5.0e-4


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
    assert len(result["model_trace"]["frequency_hz"]) == len(frequencies_hz)
    assert [round(item["fr_hz"] / 1e9, 2) for item in result["resonances"]] == [6.05, 6.3]
    assert all(item["bandwidth_hz"] is not None for item in result["resonances"])
    json.dumps(result)
