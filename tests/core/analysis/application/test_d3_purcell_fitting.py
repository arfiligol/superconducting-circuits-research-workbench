"""Focused checks for D3 complex channel calibration and pair fitting."""

from __future__ import annotations

import hashlib
import json
from types import SimpleNamespace

import numpy as np
import pytest
import superconducting_circuits_analysis.application.analysis.fitting.d3_purcell as d3_purcell
from superconducting_circuits_analysis.application.analysis.fitting.d3_purcell import (
    calibrate_d3_channel_residue_s21,
    fit_d3_through_line_s21,
)


def _synthetic_traces(
    phasor_convention: str = "exp_plus_iomega_t",
    *,
    deep_filter_zero: bool = False,
    fp_hz: float = 6.02e9,
    fr_hz: float = 5.98e9,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, dict[str, object]]:
    frequency = np.linspace(1.0e9, 11.0e9, 10_001)
    filter_loaded_linewidth_hz = 12.0e6
    readout_loaded_linewidth_hz = 0.0
    j_hz = 25.0e6
    residue_hz = -4.5e6 + 2.0e6j
    phasor_sign = 1.0 if phasor_convention == "exp_plus_iomega_t" else -1.0
    x = (frequency - 6.0e9) / 10.0e9
    direct_path = (0.96 + 0.08j) + (-0.06 + 0.04j) * x
    if deep_filter_zero:
        fp_x = (fp_hz - 6.0e9) / 10.0e9
        direct_path_at_fp = (0.96 + 0.08j) + (-0.06 + 0.04j) * fp_x
        residue_hz = -direct_path_at_fp * filter_loaded_linewidth_hz / 2.0
    bare_a_p = (
        filter_loaded_linewidth_hz / 2.0 + 1j * phasor_sign * (frequency - fp_hz)
    )
    filter_only = direct_path + residue_hz / bare_a_p
    if deep_filter_zero:
        filter_only[int(np.argmin(np.abs(frequency - fp_hz)))] = 1.0e-5 * np.exp(2.6j)
    pair_a_p = (
        filter_loaded_linewidth_hz / 2.0 + 1j * phasor_sign * (frequency - fp_hz)
    )
    pair_a_r = (
        readout_loaded_linewidth_hz / 2.0 + 1j * phasor_sign * (frequency - fr_hz)
    )
    pair = direct_path + residue_hz * pair_a_r / (pair_a_p * pair_a_r + j_hz**2)
    empty_feedline = (0.72 + 0.13j) * np.exp(
        -2j * np.pi * phasor_sign * (frequency - 6.0e9) * 2.3e-9
    )
    contract: dict[str, object] = {
        "phasor_convention": phasor_convention,
        "fit_window_hz": [5.70e9, 6.25e9],
        "background_windows_hz": [[1.0e9, 2.0e9], [10.0e9, 11.0e9]],
        "fp_hz": fp_hz,
        "fr_hz": fr_hz,
        "filter_loaded_linewidth_hz": filter_loaded_linewidth_hz,
        "readout_loaded_linewidth_hz": readout_loaded_linewidth_hz,
        "j_bounds_hz": [5.0e6, 60.0e6],
        "j_seeds_hz": [10.0e6, 20.0e6, 24.0e6, 25.0e6, 40.0e6],
        "linear_ls_rcond": 1.0e-12,
        "min_reference_magnitude": 0.5,
        "min_complex_r2": 0.99,
        "min_abs_r2": 0.99,
        "max_phase_rmse_rad": 0.03,
        "min_phase_magnitude": 0.0,
        "min_normalized_bound_margin": 0.05,
        "least_squares_max_nfev": 200,
        "least_squares_ftol": 1.0e-8,
        "least_squares_xtol": 1.0e-8,
        "least_squares_gtol": 1.0e-8,
        "least_squares_diff_step": 1.0e-6,
        "min_successful_seed_count": 3,
        "min_successful_seed_fraction": 0.8,
        "near_optimal_mse_ratio": 1.05,
        "near_optimal_mse_absolute_tolerance": 1.0e-12,
        "min_winning_seed_count": 2,
        "max_seed_spread_hz": 1.0e5,
        "provenance": {
            "reference_contract_id": "synthetic-reference-contract",
            "measured_trace_id": "synthetic-full-feedline",
            "empty_feedline_trace_id": "synthetic-empty-feedline",
            "filter_loaded_bare_reference_id": "synthetic-loaded-bare-filter",
            "readout_loaded_bare_reference_id": "synthetic-loaded-bare-readout",
            "pair_assignment_id": "slot-6ghz",
            "port_plane": "synthetic-device-feedline-plane",
        },
    }
    return (
        frequency,
        empty_feedline * filter_only,
        empty_feedline * pair,
        empty_feedline,
        contract,
    )


def _calibrate(
    frequency: np.ndarray,
    filter_only: np.ndarray,
    empty_feedline: np.ndarray,
    contract: dict[str, object],
) -> dict[str, object]:
    return calibrate_d3_channel_residue_s21(
        frequency,
        filter_only.real,
        filter_only.imag,
        empty_feedline.real,
        empty_feedline.imag,
        phasor_convention=contract["phasor_convention"],
        fit_window_hz=contract["fit_window_hz"],
        background_windows_hz=contract["background_windows_hz"],
        fp_hz=contract["fp_hz"],
        filter_loaded_linewidth_hz=contract["filter_loaded_linewidth_hz"],
        linear_ls_rcond=contract["linear_ls_rcond"],
        min_reference_magnitude=contract["min_reference_magnitude"],
        min_complex_r2=contract["min_complex_r2"],
        min_abs_r2=contract["min_abs_r2"],
        max_phase_rmse_rad=contract["max_phase_rmse_rad"],
        min_phase_magnitude=contract["min_phase_magnitude"],
        provenance={
            "calibration_id": "synthetic-channel-calibration",
            "reference_contract_id": "synthetic-reference-contract",
            "filter_only_trace_id": "synthetic-filter-only",
            "empty_feedline_trace_id": "synthetic-empty-feedline",
            "filter_loaded_bare_reference_id": "synthetic-loaded-bare-filter",
            "port_plane": "synthetic-device-feedline-plane",
        },
    )


def _fit(
    frequency: np.ndarray,
    measured: np.ndarray,
    empty_feedline: np.ndarray,
    contract: dict[str, object],
    calibration: dict[str, object],
) -> dict[str, object]:
    return fit_d3_through_line_s21(
        frequency,
        measured.real,
        measured.imag,
        empty_feedline.real,
        empty_feedline.imag,
        channel_calibration=calibration,
        **contract,
    )


def _canonical_calibration_hash(calibration: dict[str, object]) -> str:
    summary = {
        key: value
        for key, value in calibration.items()
        if key not in {"fit_trace", "calibration_summary_sha256"}
    }
    canonical_json = json.dumps(
        summary,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )
    return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()


def _mock_seed_fits(
    monkeypatch: pytest.MonkeyPatch,
    outcomes: list[tuple[float, float, bool]],
) -> None:
    iterator = iter(outcomes)

    def fake_least_squares(*args: object, max_nfev: int, **kwargs: object) -> object:
        del args
        assert max_nfev == 200
        assert kwargs["method"] == "trf"
        assert kwargs["loss"] == "linear"
        assert kwargs["jac"] == "2-point"
        assert kwargs["ftol"] == 1.0e-8
        assert kwargs["xtol"] == 1.0e-8
        assert kwargs["gtol"] == 1.0e-8
        assert kwargs["diff_step"] == 1.0e-6
        j_hz, cost, success = next(iterator)
        return SimpleNamespace(
            x=np.asarray([j_hz]),
            cost=cost,
            success=success,
            status=1 if success else 0,
            message="mock convergence" if success else "maximum evaluations exceeded",
            nfev=6 if success else max_nfev,
            njev=5 if success else max_nfev - 1,
            optimality=1.0e-10 if success else 1.0,
            active_mask=np.asarray([0]),
        )

    monkeypatch.setattr(d3_purcell, "least_squares", fake_least_squares)


def _seed_outcomes() -> list[tuple[float, float, bool]]:
    return [(45.0e6, 10.0, True) for _ in range(5)]


@pytest.mark.parametrize(
    ("phasor_convention", "pole_sign"),
    [("exp_plus_iomega_t", 1.0), ("exp_minus_iomega_t", -1.0)],
)
def test_calibration_and_pair_fit_recover_complex_residue_and_j(
    phasor_convention: str, pole_sign: float
) -> None:
    frequency, filter_only, pair, empty_feedline, contract = _synthetic_traces(phasor_convention)

    calibration = _calibrate(frequency, filter_only, empty_feedline, contract)
    result = _fit(frequency, pair, empty_feedline, contract, calibration)

    assert calibration["status"] == "success"
    assert abs(calibration["params"]["channel_residue_real_hz"] + 4.5e6) < 1.0e5
    assert abs(calibration["params"]["channel_residue_imag_hz"] - 2.0e6) < 1.0e5
    assert calibration["diagnostics"]["linear_ls_rank"] == 3
    assert result["status"] == "success"
    assert abs(result["params"]["j_hz"] - 25.0e6) < 1.0e5
    assert set(result["params"]) == {"j_hz"}
    assert result["metrics"]["complex_r2"] > 0.99
    assert result["metrics"]["abs_r2"] > 0.99
    assert result["model_convention"]["simultaneous_j_residue_fit"] is False
    assert result["model_convention"]["loaded_bare_diagonal_frequencies_fixed"] is True
    assert calibration["schema"] == "d3_channel_calibration"
    assert result["schema"] == "d3_through_line_j_fit"
    assert result["fit_method"] == "d3_through_line_complex_s21_fixed_calibrated_residue"
    assert "loaded_linewidth_p_hz" in calibration["model_convention"]["denominator_term"]
    assert "loaded_linewidth_x_hz" in result["model_convention"]["denominator_term"]
    assert result["channel_calibration"]["calibration_id"] == calibration["calibration_id"]
    assert calibration["calibration_summary_sha256"] == _canonical_calibration_hash(calibration)
    assert (
        result["channel_calibration"]["calibration_summary_sha256"]
        == calibration["calibration_summary_sha256"]
    )
    assert result["channel_calibration"]["fit_window_hz"] == calibration["fit_window_hz"]
    assert result["channel_calibration"]["gates"] == calibration["gates"]
    assert result["algorithm"]["linear_least_squares"]["rcond"] == 1.0e-12
    assert result["algorithm"]["nonlinear_least_squares"]["diff_step"] == 1.0e-6
    assert result["search"] == {
        "j_bounds_hz": contract["j_bounds_hz"],
        "j_seeds_hz": contract["j_seeds_hz"],
    }
    assert "effective_references" not in result
    assert np.mean([pole["frequency_hz"] for pole in result["derived_poles"]]) == pytest.approx(
        6.0e9
    )
    assert all(pole_sign * pole["imaginary_hz"] > 0.0 for pole in result["derived_poles"])
    assert all(pole["linewidth_hz"] > 0.0 for pole in result["derived_poles"])
    json.dumps(calibration)
    json.dumps(result)


@pytest.mark.parametrize(
    ("fp_hz", "fr_hz"),
    [(5.98e9, 6.02e9), (6.0e9, 6.0e9)],
)
def test_pair_fit_allows_either_frequency_order_and_degeneracy(
    fp_hz: float,
    fr_hz: float,
) -> None:
    frequency, filter_only, pair, empty_feedline, contract = _synthetic_traces(
        fp_hz=fp_hz,
        fr_hz=fr_hz,
    )
    calibration = _calibrate(frequency, filter_only, empty_feedline, contract)

    result = _fit(frequency, pair, empty_feedline, contract, calibration)

    assert result["status"] == "success"
    assert result["fixed_references"]["fp_hz"] == fp_hz
    assert result["fixed_references"]["fr_hz"] == fr_hz


def test_calibration_and_pair_fit_replay_from_json_persisted_contract() -> None:
    frequency, filter_only, pair, empty_feedline, contract = _synthetic_traces()
    calibration = _calibrate(frequency, filter_only, empty_feedline, contract)
    result = _fit(frequency, pair, empty_feedline, contract, calibration)
    persisted = json.loads(
        json.dumps(
            {
                "contract": contract,
                "traces": {
                    "frequency_hz": frequency.tolist(),
                    "filter_only_s21_real": filter_only.real.tolist(),
                    "filter_only_s21_imag": filter_only.imag.tolist(),
                    "pair_s21_real": pair.real.tolist(),
                    "pair_s21_imag": pair.imag.tolist(),
                    "empty_feedline_s21_real": empty_feedline.real.tolist(),
                    "empty_feedline_s21_imag": empty_feedline.imag.tolist(),
                },
                "channel_calibration": calibration,
            }
        )
    )
    replay_contract = persisted["contract"]
    replay_traces = persisted["traces"]
    replay_frequency = np.asarray(replay_traces["frequency_hz"], dtype=float)
    replay_filter = np.asarray(
        replay_traces["filter_only_s21_real"], dtype=float
    ) + 1j * np.asarray(replay_traces["filter_only_s21_imag"], dtype=float)
    replay_pair = np.asarray(replay_traces["pair_s21_real"], dtype=float) + 1j * np.asarray(
        replay_traces["pair_s21_imag"], dtype=float
    )
    replay_reference = np.asarray(
        replay_traces["empty_feedline_s21_real"], dtype=float
    ) + 1j * np.asarray(replay_traces["empty_feedline_s21_imag"], dtype=float)

    replay_calibration = _calibrate(
        replay_frequency,
        replay_filter,
        replay_reference,
        replay_contract,
    )
    persisted_calibration_result = _fit(
        replay_frequency,
        replay_pair,
        replay_reference,
        replay_contract,
        persisted["channel_calibration"],
    )
    replay_result = _fit(
        replay_frequency,
        replay_pair,
        replay_reference,
        replay_contract,
        replay_calibration,
    )

    assert replay_calibration["schema"] == calibration["schema"]
    assert set(replay_calibration) == set(calibration)
    assert (
        replay_calibration["calibration_summary_sha256"]
        == calibration["calibration_summary_sha256"]
    )
    assert replay_calibration["params"] == pytest.approx(calibration["params"])
    assert replay_calibration["metrics"] == pytest.approx(calibration["metrics"])
    assert replay_result["schema"] == result["schema"]
    assert set(replay_result) == set(result)
    assert replay_result["params"] == pytest.approx(result["params"])
    assert replay_result["metrics"] == pytest.approx(result["metrics"])
    assert persisted_calibration_result["params"] == pytest.approx(result["params"])
    assert persisted_calibration_result["metrics"] == pytest.approx(result["metrics"])
    for replay_pole, expected_pole in zip(
        replay_result["derived_poles"], result["derived_poles"], strict=True
    ):
        assert replay_pole == pytest.approx(expected_pole)
    for persisted_pole, expected_pole in zip(
        persisted_calibration_result["derived_poles"], result["derived_poles"], strict=True
    ):
        assert persisted_pole == pytest.approx(expected_pole)
    validated_calibration = replay_result["channel_calibration"]
    assert validated_calibration == persisted_calibration_result["channel_calibration"]
    assert (
        validated_calibration["calibration_summary_sha256"]
        == calibration["calibration_summary_sha256"]
    )
    assert validated_calibration == {
        key: calibration[key] for key in validated_calibration
    }
    assert replay_result["search"] == result["search"]
    assert persisted_calibration_result["search"] == result["search"]
    assert result["search"] == {
        "j_bounds_hz": contract["j_bounds_hz"],
        "j_seeds_hz": contract["j_seeds_hz"],
    }


def test_pair_fit_fails_fast_on_mutated_fixed_residue_hash() -> None:
    frequency, filter_only, pair, empty_feedline, contract = _synthetic_traces()
    calibration = _calibrate(frequency, filter_only, empty_feedline, contract)
    calibration["params"]["channel_residue_imag_hz"] *= -1.0

    with pytest.raises(ValueError, match="summary hash"):
        _fit(frequency, pair, empty_feedline, contract, calibration)


def test_pair_fit_rejects_j_at_bound() -> None:
    frequency, filter_only, pair, empty_feedline, contract = _synthetic_traces()
    calibration = _calibrate(frequency, filter_only, empty_feedline, contract)
    contract["j_bounds_hz"] = [5.0e6, 25.0e6]
    contract["j_seeds_hz"] = [10.0e6, 15.0e6, 20.0e6, 24.0e6, 25.0e6]

    result = _fit(frequency, pair, empty_feedline, contract, calibration)

    assert result["status"] == "rejected"
    assert "bound_margin_failure" in result["failure_codes"]


def test_pair_fit_rejects_seed_instability() -> None:
    frequency, filter_only, pair, empty_feedline, contract = _synthetic_traces()
    calibration = _calibrate(frequency, filter_only, empty_feedline, contract)
    contract["max_seed_spread_hz"] = 0.0

    result = _fit(frequency, pair, empty_feedline, contract, calibration)

    assert result["status"] == "rejected"
    assert "ambiguous_near_optimal_basin" in result["failure_codes"]


def test_pair_fit_accepts_far_high_cost_nonconvergence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    frequency, filter_only, pair, empty_feedline, contract = _synthetic_traces()
    calibration = _calibrate(frequency, filter_only, empty_feedline, contract)
    outcomes = _seed_outcomes()
    outcomes[0] = (25.0e6, 1.0, True)
    outcomes[2] = (25.0e6, 1.001, True)
    outcomes[4] = (11.8e6, 10.0, False)
    _mock_seed_fits(monkeypatch, outcomes)

    result = _fit(frequency, pair, empty_feedline, contract, calibration)

    assert result["status"] == "success"
    assert result["diagnostics"]["successful_seed_count"] == 4
    assert result["diagnostics"]["nonconverged_seed_count"] == 1
    assert result["diagnostics"]["winning_seed_count"] == 2
    assert result["diagnostics"]["unresolved_near_optimal_seed_count"] == 0
    assert result["diagnostics"]["next_best_noncompetitive_mse_ratio"] == pytest.approx(10.0)
    failed_start = result["diagnostics"]["seed_results"][4]
    assert failed_start["near_optimal"] is False
    assert failed_start["nfev"] == 200
    assert failed_start["njev"] == 199
    assert failed_start["optimality"] == 1.0
    assert failed_start["active_mask"] == [0]


def test_pair_fit_rejects_near_optimal_parameter_ambiguity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    frequency, filter_only, pair, empty_feedline, contract = _synthetic_traces()
    calibration = _calibrate(frequency, filter_only, empty_feedline, contract)
    outcomes = _seed_outcomes()
    outcomes[0] = (25.0e6, 1.0, True)
    outcomes[2] = (25.0e6, 1.001, True)
    outcomes[4] = (40.0e6, 1.02, True)
    _mock_seed_fits(monkeypatch, outcomes)

    result = _fit(frequency, pair, empty_feedline, contract, calibration)

    assert result["status"] == "rejected"
    assert "ambiguous_near_optimal_basin" in result["failure_codes"]
    assert result["diagnostics"]["near_optimal_seed_count"] == 3


def test_pair_fit_rejects_single_winning_seed_support(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    frequency, filter_only, pair, empty_feedline, contract = _synthetic_traces()
    calibration = _calibrate(frequency, filter_only, empty_feedline, contract)
    outcomes = _seed_outcomes()
    outcomes[0] = (25.0e6, 1.0, True)
    _mock_seed_fits(monkeypatch, outcomes)

    result = _fit(frequency, pair, empty_feedline, contract, calibration)

    assert result["status"] == "rejected"
    assert "insufficient_winning_seed_support" in result["failure_codes"]
    assert result["diagnostics"]["winning_seed_count"] == 1


def test_pair_fit_accepts_caller_declared_single_winning_seed_support(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    frequency, filter_only, pair, empty_feedline, contract = _synthetic_traces()
    calibration = _calibrate(frequency, filter_only, empty_feedline, contract)
    contract["min_winning_seed_count"] = 1
    outcomes = _seed_outcomes()
    outcomes[0] = (25.0e6, 1.0, True)
    _mock_seed_fits(monkeypatch, outcomes)

    result = _fit(frequency, pair, empty_feedline, contract, calibration)

    assert result["status"] == "success"
    assert result["gates"]["min_winning_seed_count"] == 1


def test_pair_fit_rejects_near_optimal_nonconvergence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    frequency, filter_only, pair, empty_feedline, contract = _synthetic_traces()
    calibration = _calibrate(frequency, filter_only, empty_feedline, contract)
    outcomes = _seed_outcomes()
    outcomes[0] = (25.0e6, 1.0, True)
    outcomes[2] = (25.0e6, 1.001, True)
    outcomes[4] = (40.0e6, 1.02, False)
    _mock_seed_fits(monkeypatch, outcomes)

    result = _fit(frequency, pair, empty_feedline, contract, calibration)

    assert result["status"] == "rejected"
    assert "unresolved_near_optimal_start" in result["failure_codes"]
    assert result["diagnostics"]["unresolved_near_optimal_seed_count"] == 1


def test_pair_fit_rejects_insufficient_successful_seed_coverage(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    frequency, filter_only, pair, empty_feedline, contract = _synthetic_traces()
    calibration = _calibrate(frequency, filter_only, empty_feedline, contract)
    outcomes = [(45.0e6, 10.0, False) for _ in range(5)]
    outcomes[0] = (25.0e6, 1.0, True)
    outcomes[2] = (25.0e6, 1.001, True)
    _mock_seed_fits(monkeypatch, outcomes)

    result = _fit(frequency, pair, empty_feedline, contract, calibration)

    assert result["status"] == "rejected"
    assert "seed_coverage_failure" in result["failure_codes"]
    assert result["diagnostics"]["successful_seed_count"] == 2
    assert result["diagnostics"]["required_successful_seed_count"] == 4


def test_calibration_raises_on_near_zero_reference() -> None:
    frequency, filter_only, _, empty_feedline, contract = _synthetic_traces()
    empty_feedline[100] = 1.0e-12 + 0.0j

    with pytest.raises(ValueError, match="min_reference_magnitude"):
        _calibrate(frequency, filter_only, empty_feedline, contract)


def test_calibration_excludes_deep_zero_from_phase_metric_only_when_explicit() -> None:
    frequency, filter_only, _, empty_feedline, contract = _synthetic_traces(deep_filter_zero=True)
    contract["min_phase_magnitude"] = 0.02

    result = _calibrate(frequency, filter_only, empty_feedline, contract)

    assert result["status"] == "success"
    assert result["metrics"]["phase_valid_sample_count"] < len(result["fit_trace"]["frequency_hz"])
    assert result["metrics"]["phase_valid_sample_fraction"] < 1.0
    assert result["gates"]["min_phase_magnitude"] == 0.02


def test_calibration_returns_rank_rejection() -> None:
    frequency, filter_only, _, empty_feedline, contract = _synthetic_traces()
    contract["filter_loaded_linewidth_hz"] = 1.0e30

    result = _calibrate(frequency, filter_only, empty_feedline, contract)

    assert result["status"] == "rejected"
    assert result["failure_codes"] == ["rank_failure"]


def test_calibration_rejects_when_phase_has_no_valid_samples() -> None:
    frequency, filter_only, _, empty_feedline, contract = _synthetic_traces()
    contract["min_phase_magnitude"] = 2.0

    result = _calibrate(frequency, filter_only, empty_feedline, contract)

    assert result["status"] == "rejected"
    assert "quality_failure" in result["failure_codes"]
    assert result["metrics"]["phase_rmse_rad"] is None
    assert result["metrics"]["phase_valid_sample_count"] == 0
    assert result["metrics"]["phase_valid_sample_fraction"] == 0.0


def test_pair_fit_fails_fast_on_mutated_calibration_id_hash() -> None:
    frequency, filter_only, pair, empty_feedline, contract = _synthetic_traces()
    calibration = _calibrate(frequency, filter_only, empty_feedline, contract)
    calibration["calibration_id"] = "wrong-id"

    with pytest.raises(ValueError, match="summary hash"):
        _fit(frequency, pair, empty_feedline, contract, calibration)


@pytest.mark.parametrize(
    "tamper",
    ["normalization_method", "complex_r2_below_gate"],
)
def test_pair_fit_fails_fast_on_tampered_successful_calibration(
    tamper: str,
) -> None:
    frequency, filter_only, pair, empty_feedline, contract = _synthetic_traces()
    calibration = _calibrate(frequency, filter_only, empty_feedline, contract)
    if tamper == "normalization_method":
        calibration["normalization"]["method"] = "tampered-normalization"
    else:
        gate = float(calibration["gates"]["min_complex_r2"])
        calibration["metrics"]["complex_r2"] = np.nextafter(gate, -np.inf)

    with pytest.raises(ValueError, match="summary hash"):
        _fit(frequency, pair, empty_feedline, contract, calibration)


@pytest.mark.parametrize(
    ("field", "expected_message"),
    [
        ("reference_contract_id", "reference_contract_id"),
        ("filter_loaded_bare_reference_id", "filter loaded-bare reference"),
    ],
)
def test_pair_fit_fails_fast_on_cross_stage_reference_mismatch(
    field: str,
    expected_message: str,
) -> None:
    frequency, filter_only, pair, empty_feedline, contract = _synthetic_traces()
    calibration = _calibrate(frequency, filter_only, empty_feedline, contract)
    contract["provenance"][field] = f"mismatched-{field}"

    with pytest.raises(ValueError, match=expected_message):
        _fit(frequency, pair, empty_feedline, contract, calibration)


def test_pair_fit_allows_distinct_empty_feedline_trace_ids_across_stage_grids() -> None:
    frequency, filter_only, pair, empty_feedline, contract = _synthetic_traces()
    calibration = _calibrate(frequency, filter_only, empty_feedline, contract)
    contract["provenance"]["empty_feedline_trace_id"] = "synthetic-pair-grid-empty-feedline"

    result = _fit(frequency, pair, empty_feedline, contract, calibration)

    assert result["status"] == "success"


def test_pair_background_rejection_preserves_search_contract(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    frequency, filter_only, pair, empty_feedline, contract = _synthetic_traces()
    calibration = _calibrate(frequency, filter_only, empty_feedline, contract)

    def raise_rank_failure(*args: object, **kwargs: object) -> object:
        del args, kwargs
        raise ValueError("synthetic rank failure")

    monkeypatch.setattr(d3_purcell, "_fit_affine_background", raise_rank_failure)

    result = _fit(frequency, pair, empty_feedline, contract, calibration)

    assert result["status"] == "rejected"
    assert result["failure_codes"] == ["rank_failure"]
    assert result["search"] == {
        "j_bounds_hz": contract["j_bounds_hz"],
        "j_seeds_hz": contract["j_seeds_hz"],
    }


@pytest.mark.parametrize("exception", [ValueError("contract bug"), RuntimeError("runtime bug")])
def test_pair_fit_propagates_unexpected_optimizer_exceptions(
    monkeypatch: pytest.MonkeyPatch,
    exception: Exception,
) -> None:
    frequency, filter_only, pair, empty_feedline, contract = _synthetic_traces()
    calibration = _calibrate(frequency, filter_only, empty_feedline, contract)

    def raise_unexpected(*args: object, **kwargs: object) -> object:
        del args, kwargs
        raise exception

    monkeypatch.setattr(d3_purcell, "least_squares", raise_unexpected)

    with pytest.raises(type(exception), match="bug"):
        _fit(frequency, pair, empty_feedline, contract, calibration)


def test_pair_fit_converts_expected_linear_algebra_failure_to_rejection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    frequency, filter_only, pair, empty_feedline, contract = _synthetic_traces()
    calibration = _calibrate(frequency, filter_only, empty_feedline, contract)

    def raise_linear_algebra_failure(*args: object, **kwargs: object) -> object:
        del args, kwargs
        raise np.linalg.LinAlgError("numerical factorization failure")

    monkeypatch.setattr(d3_purcell, "least_squares", raise_linear_algebra_failure)

    result = _fit(frequency, pair, empty_feedline, contract, calibration)

    assert result["status"] == "rejected"
    assert result["failure_codes"] == ["numerical_failure"]


@pytest.mark.parametrize("invalid_convention", [None, "hb_native"])
def test_calibration_raises_on_unknown_phasor_convention(
    invalid_convention: object,
) -> None:
    frequency, filter_only, _, empty_feedline, contract = _synthetic_traces()
    contract["phasor_convention"] = invalid_convention

    with pytest.raises(ValueError, match="phasor_convention"):
        _calibrate(frequency, filter_only, empty_feedline, contract)
