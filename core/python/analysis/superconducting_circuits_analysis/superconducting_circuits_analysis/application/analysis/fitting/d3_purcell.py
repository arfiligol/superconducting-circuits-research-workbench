"""Fit D3 initializer models from response data.

This module owns the response-frequency qubit/readout initializer, the
filter-off channel calibration, and the isolated readout/filter through-line
fit. It does not own the final Full-QRP Finite-Order Port-Response fit,
multi-pair propagation, or optimizer targets.

Canonical Knowledge:
https://github.com/arfiligol/SCQ_Design/blob/main/docs/knowledge/readout/readout-filter-s21-j-fit.qmd
https://github.com/arfiligol/SCQ_Design/blob/main/docs/knowledge/network-modeling/resonator-decay-linewidth-and-quality-factor.qmd
https://github.com/arfiligol/SCQ_Design/blob/main/docs/knowledge/readout/coupling-off-readout-filter-initial-references.qmd
https://github.com/arfiligol/SCQ_Design/blob/main/docs/knowledge/readout/bare-vs-hybridized-readout-filter-modes.qmd
https://github.com/arfiligol/SCQ_Design/blob/main/docs/knowledge/simulation/port-reference-impedance-semantics.qmd
"""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Mapping, Sequence
from numbers import Integral, Real
from typing import Never, cast

import numpy as np
from scipy.optimize import OptimizeResult, least_squares, lsq_linear

_CHANNEL_CALIBRATION_SCHEMA = "d3_channel_calibration"
_CHANNEL_CALIBRATION_FIT_METHOD = "d3_filter_off_reference_complex_channel_residue_linear_ls"
_PAIR_FIT_SCHEMA = "d3_through_line_j_fit"
_PAIR_FIT_METHOD = "d3_through_line_complex_s21_fixed_calibrated_residue"
_SYSTEM_A_FIT_SCHEMA = "d3_system_a_frequency_lj_sweep_fit.v1"
_SYSTEM_A_FIT_METHOD = "d3_system_a_response_frequency_lj_sweep"
_SYSTEM_A_PARAMETER_NAMES = (
    "c_q_eff_system_a_on_f",
    "f_r_lb_system_a_on_hz",
    "g_system_a_on_hz",
)


def fit_d3_system_a_lj_sweep(
    observations: Sequence[Mapping[str, object]],
    *,
    physical_bounds: Mapping[str, Sequence[float]],
    physical_seeds: Sequence[Mapping[str, float]],
    numerical_tolerances: Mapping[str, int | float],
    gates: Mapping[str, int | float],
    provenance: Mapping[str, object],
) -> dict[str, object]:
    """Fit the response-effective two-mode System-A ``L_J`` sweep.

    Each observation supplies the lower and upper hybridized frequencies that
    preceding S-, Y-, or Z-response extractions assigned to the two branches.
    The shared fit determines the effective qubit capacitance, the System-A
    coupling-on readout diagonal frequency, and the nonnegative q-r coupling
    magnitude. It does not consume a closed-circuit eigenmode or invert a
    one-point frequency shift.

    Malformed contracts raise ``ValueError``. Expected optimizer, quality, or
    identifiability failures return a structured rejected result that retains
    any successfully fitted evidence.
    """
    parsed = _system_a_observations(observations)
    bounds = _system_a_bounds(physical_bounds)
    seeds = _system_a_seeds(physical_seeds, bounds)
    tolerances = _system_a_numerical_tolerances(numerical_tolerances)
    fit_gates = _system_a_gates(gates)
    _require(
        int(fit_gates["min_successful_seed_count"]) <= len(seeds),
        "gates.min_successful_seed_count exceeds physical_seeds length.",
    )
    provenance_payload = _validated_provenance(
        provenance,
        frozenset(
            {
                "fit_id",
                "candidate_id",
                "reference_contract_id",
                "topology_id",
                "port_plane",
            }
        ),
        "provenance",
    )
    _validate_system_a_observation_identity(parsed, provenance_payload)

    lower = np.asarray([bounds[name][0] for name in _SYSTEM_A_PARAMETER_NAMES])
    upper = np.asarray([bounds[name][1] for name in _SYSTEM_A_PARAMETER_NAMES])
    widths = upper - lower
    seed_vectors = [
        (np.asarray([seed[name] for name in _SYSTEM_A_PARAMETER_NAMES]) - lower) / widths
        for seed in seeds
    ]
    base: dict[str, object] = {
        "schema": _SYSTEM_A_FIT_SCHEMA,
        "fit_method": _SYSTEM_A_FIT_METHOD,
        "fit_domain": "response_extracted_hybridized_frequencies",
        "model_convention": {
            "coordinate_order": ["q", "r"],
            "coherent_edges": ["q-r"],
            "qubit_tuning_law": "fq=1/(2*pi*sqrt((LJ_per_junction/2)*Cq_eff))",
            "g_parameter": "nonnegative_coupling_magnitude_hz",
            "observation_authority": "per_branch_caller_supplied_S_Y_or_Z_response_extraction",
            "closed_circuit_eigenmode_consumed": False,
            "one_point_shift_inversion_consumed": False,
        },
        "search": {
            "physical_bounds": {name: list(bounds[name]) for name in _SYSTEM_A_PARAMETER_NAMES},
            "physical_seeds": seeds,
        },
        "algorithm": {
            "optimizer": "scipy.optimize.least_squares_trf",
            "physical_parameterization": "unit_box",
            "frequency_residual_scale_hz": tolerances["frequency_residual_scale_hz"],
            "numerical_tolerances": tolerances,
        },
        "gates": fit_gates,
        "provenance": provenance_payload,
        "trace_provenance": [
            {
                "trace_id": item["trace_id"],
                "lj_per_junction_h": item["lj_per_junction_h"],
                "candidate_id": item["candidate_id"],
                "reference_contract_id": item["reference_contract_id"],
                "topology_id": item["topology_id"],
                "port_plane": item["port_plane"],
                "lower_branch": item["lower_branch"],
                "upper_branch": item["upper_branch"],
            }
            for item in parsed
        ],
    }
    if len(parsed) < int(fit_gates["min_trace_count"]):
        return _system_a_rejected(
            base,
            ["trace_count_failure"],
            ["observations contains fewer entries than gates.min_trace_count"],
            seed_evidence=[],
        )

    seed_evidence, successful = _run_system_a_seed_fits(
        parsed,
        lower,
        widths,
        seed_vectors,
        tolerances,
    )
    required_successes = max(
        int(fit_gates["min_successful_seed_count"]),
        math.ceil(float(fit_gates["min_successful_seed_fraction"]) * len(seeds)),
    )
    if len(successful) < required_successes:
        return _system_a_rejected(
            base,
            ["seed_coverage_failure"],
            [f"{len(successful)} successful seeds is below required {required_successes}."],
            seed_evidence=seed_evidence,
        )

    best, best_record = min(successful, key=lambda item: float(item[0].cost))
    best_u = np.asarray(best.x, dtype=float)
    best_params = lower + widths * best_u
    best_cost = float(best.cost)
    near_optimal = [
        (result, record)
        for result, record in successful
        if float(result.cost)
        <= float(fit_gates["near_optimal_cost_ratio"]) * best_cost
        + float(fit_gates["near_optimal_cost_absolute_tolerance"])
    ]
    near_optimal_ids = {id(result) for result, _ in near_optimal}
    for result, record in successful:
        record["near_optimal"] = id(result) in near_optimal_ids
        record["max_parameter_distance_from_best_normalized"] = float(
            np.max(np.abs(np.asarray(result.x, dtype=float) - best_u))
        )
    seed_spread = (
        float(
            np.max(
                np.ptp(
                    np.vstack([np.asarray(result.x, dtype=float) for result, _ in near_optimal]),
                    axis=0,
                )
            )
        )
        if len(near_optimal) > 1
        else 0.0
    )

    params = {
        name: float(best_params[index]) for index, name in enumerate(_SYSTEM_A_PARAMETER_NAMES)
    }
    per_lj, residual_hz = _system_a_predictions(parsed, params)
    metrics = _system_a_metrics(parsed, residual_hz)
    margins = {
        name: float(min(best_u[index], 1.0 - best_u[index]))
        for index, name in enumerate(_SYSTEM_A_PARAMETER_NAMES)
    }
    bound_margins = {"physical": margins, "minimum": min(margins.values())}
    identifiability = _system_a_identifiability(
        np.asarray(best.jac, dtype=float),
        float(tolerances["jacobian_rank_rtol"]),
    )

    failure_codes: list[str] = []
    failure_reasons: list[str] = []
    if len(near_optimal) < int(fit_gates["min_winning_seed_count"]):
        failure_codes.append("insufficient_winning_seed_support")
        failure_reasons.append("too few seeds reached the declared near-optimal basin")
    if seed_spread > float(fit_gates["max_seed_spread_normalized"]):
        failure_codes.append("ambiguous_near_optimal_basin")
        failure_reasons.append("near-optimal seeds disagree beyond the normalized spread gate")
    if float(bound_margins["minimum"]) < float(fit_gates["min_normalized_bound_margin"]):
        failure_codes.append("bound_margin_failure")
        failure_reasons.append("one or more physical parameters lie too close to a bound")
    frequency_rmse_hz = cast(float, metrics["frequency_rmse_hz"])
    max_frequency_error_hz = cast(float, metrics["max_abs_frequency_error_hz"])
    if frequency_rmse_hz > float(fit_gates["max_frequency_rmse_hz"]):
        failure_codes.append("quality_failure")
        failure_reasons.append("frequency RMSE exceeds max_frequency_rmse_hz")
    if max_frequency_error_hz > float(fit_gates["max_frequency_error_hz"]):
        failure_codes.append("quality_failure")
        failure_reasons.append("frequency error exceeds max_frequency_error_hz")
    frequency_r2 = cast(float | None, metrics["frequency_r2"])
    if frequency_r2 is None or frequency_r2 < float(fit_gates["min_frequency_r2"]):
        failure_codes.append("quality_failure")
        failure_reasons.append("frequency R2 is undefined or below min_frequency_r2")
    if cast(int, identifiability["rank"]) < int(fit_gates["min_jacobian_rank"]):
        failure_codes.append("identifiability_failure")
        failure_reasons.append("Jacobian rank is below min_jacobian_rank")
    if cast(float, identifiability["singular_value_ratio"]) < float(
        fit_gates["min_jacobian_singular_ratio"]
    ):
        failure_codes.append("identifiability_failure")
        failure_reasons.append("Jacobian singular-value ratio is below the gate")

    return {
        **base,
        "status": "rejected" if failure_codes else "success",
        "failure_codes": list(dict.fromkeys(failure_codes)),
        "failure_reasons": failure_reasons,
        "params": params,
        "per_lj": per_lj,
        "metrics": metrics,
        "seed_evidence": seed_evidence,
        "multi_start": {
            "seed_count": len(seeds),
            "required_successful_seed_count": required_successes,
            "successful_seed_count": len(successful),
            "near_optimal_seed_count": len(near_optimal),
            "max_near_optimal_parameter_spread_normalized": seed_spread,
        },
        "bound_margins": bound_margins,
        "identifiability": identifiability,
        "optimizer": {
            "best_seed_index": cast(int, best_record["seed_index"]),
            "cost": best_cost,
            "status": int(best.status),
            "message": str(best.message),
            "nfev": int(best.nfev),
            "njev": int(best.njev) if best.njev is not None else None,
            "optimality": float(best.optimality),
        },
    }


def calibrate_d3_channel_residue_s21(
    frequency_hz: Sequence[float],
    filter_off_reference_s21_real: Sequence[float],
    filter_off_reference_s21_imag: Sequence[float],
    empty_feedline_s21_real: Sequence[float],
    empty_feedline_s21_imag: Sequence[float],
    *,
    phasor_convention: str,
    fit_window_hz: Sequence[float],
    background_windows_hz: Sequence[Sequence[float]],
    fp_hz: float,
    filter_off_reference_linewidth_hz: float,
    linear_ls_rcond: float,
    min_reference_magnitude: float,
    min_complex_r2: float,
    min_abs_r2: float,
    max_phase_rmse_rad: float,
    min_phase_magnitude: float,
    provenance: Mapping[str, object],
) -> dict[str, object]:
    """Calibrate the fixed complex through-line residue from filter off-reference S21.

    The empty-feedline ratio removes the shared cable/feedline response. An
    affine complex direct path and ``residue_hz / a_p`` are identified by one
    rank-three complex linear least-squares fit over the union of the explicit
    fit and background windows. Quality is evaluated only on the fit window. A
    successful result hashes its canonical JSON summary to detect accidental or
    mismatched payload mutation; raw-trace replay remains the physical evidence.
    """
    frequency, filter_off_reference, reference = _prepare_traces(
        frequency_hz,
        filter_off_reference_s21_real,
        filter_off_reference_s21_imag,
        empty_feedline_s21_real,
        empty_feedline_s21_imag,
    )
    convention, phasor_sign = _phasor_convention(phasor_convention)
    fit_window = _window(fit_window_hz, "fit_window_hz")
    background_windows = _windows(background_windows_hz, "background_windows_hz")
    _require_windows_inside_trace(frequency, [fit_window, *background_windows])
    fp = _positive_finite(fp_hz, "fp_hz")
    filter_off_reference_linewidth = _positive_finite(
        filter_off_reference_linewidth_hz, "filter_off_reference_linewidth_hz"
    )
    ls_rcond = _nonnegative_finite(linear_ls_rcond, "linear_ls_rcond")
    reference_floor = _positive_finite(min_reference_magnitude, "min_reference_magnitude")
    complex_r2_gate = _r2_gate(min_complex_r2, "min_complex_r2")
    abs_r2_gate = _r2_gate(min_abs_r2, "min_abs_r2")
    phase_gate = _nonnegative_finite(max_phase_rmse_rad, "max_phase_rmse_rad")
    phase_magnitude_gate = _nonnegative_finite(min_phase_magnitude, "min_phase_magnitude")
    provenance_payload = _calibration_provenance(provenance)

    min_reference = float(np.min(np.abs(reference)))
    _require(
        min_reference >= reference_floor,
        "empty-feedline reference magnitude falls below min_reference_magnitude.",
    )
    fit_mask = _mask_for_windows(frequency, [fit_window])
    background_mask = _mask_for_windows(frequency, background_windows)
    _require(
        int(np.count_nonzero(fit_mask)) >= 3,
        "fit_window_hz must select at least three samples.",
    )
    _require(
        int(np.count_nonzero(background_mask)) >= 2,
        "background_windows_hz must select at least two samples.",
    )

    base = {
        "schema": _CHANNEL_CALIBRATION_SCHEMA,
        "fit_method": _CHANNEL_CALIBRATION_FIT_METHOD,
        "fit_domain": "complex_s21",
        "model_convention": {
            "phasor_convention": convention,
            "denominator_term": (
                "a_p = off_reference_linewidth_p_hz/2 + i*(f_hz - f_p_hz)"
                if phasor_sign > 0.0
                else "a_p = off_reference_linewidth_p_hz/2 + i*(f_p_hz - f_hz)"
            ),
            "model": "S21 = C21_affine + residue_hz / a_p",
            "linear_ls_basis": "[1, scaled_frequency, 1/a_p]",
            "input_s21_conjugated": False,
            "calibration_samples": "union_of_explicit_fit_and_background_windows",
            "free_cable_delay": False,
        },
        "normalization": {
            "method": "empty_through_s21_ratio_normalization",
            "port_plane": provenance_payload["port_plane"],
            "same_frequency_grid": True,
            "reference_plane_moved": False,
            "exact_two_port_deembedding": False,
            "min_reference_magnitude": min_reference,
            "required_min_reference_magnitude": reference_floor,
        },
        "fit_window_hz": list(fit_window),
        "background_windows_hz": [list(window) for window in background_windows],
        "fixed_references": {
            "fp_hz": fp,
            "filter_off_reference_linewidth_hz": filter_off_reference_linewidth,
        },
        "algorithm": {
            "linear_least_squares": {
                "driver": "numpy.linalg.lstsq",
                "rcond": ls_rcond,
            }
        },
        "gates": {
            "min_complex_r2": complex_r2_gate,
            "min_abs_r2": abs_r2_gate,
            "max_phase_rmse_rad": phase_gate,
            "min_phase_magnitude": phase_magnitude_gate,
        },
        "calibration_id": provenance_payload["calibration_id"],
        "provenance": provenance_payload,
    }

    try:
        with np.errstate(divide="raise", invalid="raise", over="raise"):
            normalized = filter_off_reference / reference
    except FloatingPointError as exc:
        return _rejected(base, "numerical_failure", str(exc))

    calibration_mask = fit_mask | background_mask
    calibration_frequency = frequency[calibration_mask]
    calibration_data = normalized[calibration_mask]
    background_center = float(np.mean(calibration_frequency))
    background_scale = float(np.ptp(calibration_frequency))
    _require(background_scale > 0.0, "Calibration windows must span more than one frequency.")
    scaled_frequency = (calibration_frequency - background_center) / background_scale
    calibration_a_p = filter_off_reference_linewidth / 2.0 + 1j * phasor_sign * (
        calibration_frequency - fp
    )
    basis = np.column_stack(
        (
            np.ones_like(scaled_frequency),
            scaled_frequency,
            1.0 / calibration_a_p,
        )
    ).astype(complex)
    try:
        coefficients, _, rank, singular_values = np.linalg.lstsq(
            basis, calibration_data, rcond=ls_rcond
        )
    except np.linalg.LinAlgError as exc:
        return _rejected(base, "numerical_failure", str(exc))
    if rank != 3:
        return _rejected(
            base,
            "rank_failure",
            f"filter off-reference affine-plus-residue basis has rank {rank}; expected 3",
        )
    if not np.all(np.isfinite(coefficients)):
        return _rejected(base, "numerical_failure", "calibration coefficients are non-finite")

    background = np.asarray(
        [background_center, background_scale, coefficients[0], coefficients[1]],
        dtype=complex,
    )
    residue = complex(coefficients[2])

    fit_frequency = frequency[fit_mask]
    fit_data = normalized[fit_mask]
    fit_background = _affine_background(fit_frequency, background)
    a_p = filter_off_reference_linewidth / 2.0 + 1j * phasor_sign * (fit_frequency - fp)
    fitted = fit_background + residue / a_p
    metrics, phase_residual = _metrics(fit_data, fitted, phase_magnitude_gate)
    failure_codes: list[str] = []
    failure_reasons: list[str] = []
    _quality_failure(
        metrics,
        complex_r2_gate,
        abs_r2_gate,
        phase_gate,
        failure_codes,
        failure_reasons,
    )
    residual_trace = fitted - fit_data
    result_payload: dict[str, object] = {
        **base,
        "status": "rejected" if failure_codes else "success",
        "failure_codes": failure_codes,
        "failure_reasons": failure_reasons,
        "params": {
            "channel_residue_real_hz": float(residue.real),
            "channel_residue_imag_hz": float(residue.imag),
        },
        "background": _background_payload(background),
        "metrics": metrics,
        "diagnostics": {
            "linear_ls_rank": int(rank),
            "linear_ls_sample_count": int(np.count_nonzero(calibration_mask)),
            "linear_ls_singular_values": _float_list(singular_values),
        },
        "fit_trace": {
            "frequency_hz": _float_list(fit_frequency),
            "normalized_s21_real": _float_list(fit_data.real),
            "normalized_s21_imag": _float_list(fit_data.imag),
            "fitted_s21_real": _float_list(fitted.real),
            "fitted_s21_imag": _float_list(fitted.imag),
            "residual_real": _float_list(residual_trace.real),
            "residual_imag": _float_list(residual_trace.imag),
            "phase_residual_rad": _nullable_float_list(phase_residual),
        },
    }
    if not failure_codes:
        result_payload["calibration_summary_sha256"] = _calibration_summary_sha256(result_payload)
    return result_payload


def fit_d3_through_line_s21(
    frequency_hz: Sequence[float],
    measured_s21_real: Sequence[float],
    measured_s21_imag: Sequence[float],
    empty_feedline_s21_real: Sequence[float],
    empty_feedline_s21_imag: Sequence[float],
    *,
    phasor_convention: str,
    fit_window_hz: Sequence[float],
    background_windows_hz: Sequence[Sequence[float]],
    fp_hz: float,
    fr_hz: float,
    filter_off_reference_linewidth_hz: float,
    readout_off_reference_linewidth_hz: float,
    channel_calibration: Mapping[str, object],
    j_bounds_hz: Sequence[float],
    j_seeds_hz: Sequence[float],
    linear_ls_rcond: float,
    min_reference_magnitude: float,
    min_complex_r2: float,
    min_abs_r2: float,
    max_phase_rmse_rad: float,
    min_phase_magnitude: float,
    min_normalized_bound_margin: float,
    least_squares_max_nfev: int,
    least_squares_ftol: float,
    least_squares_xtol: float,
    least_squares_gtol: float,
    least_squares_diff_step: float,
    min_successful_seed_count: int,
    min_successful_seed_fraction: float,
    near_optimal_mse_ratio: float,
    near_optimal_mse_absolute_tolerance: float,
    min_winning_seed_count: int,
    max_seed_spread_hz: float,
    provenance: Mapping[str, object],
) -> dict[str, object]:
    """Fit J with fixed coupling-off diagonal references and channel residue.

    Malformed inputs raise immediately. Numerical, bound, quality, or seed
    stability failures return a structured rejected result so an outer design
    optimizer can reject the candidate without inventing replacement metrics.
    The coupling-off fp/fr references are initializer frequencies and remain
    fixed throughout this fit; they are not final Full-QRP loaded-bare values.
    """
    frequency, measured, reference = _prepare_traces(
        frequency_hz,
        measured_s21_real,
        measured_s21_imag,
        empty_feedline_s21_real,
        empty_feedline_s21_imag,
    )
    convention, phasor_sign = _phasor_convention(phasor_convention)
    fit_window = _window(fit_window_hz, "fit_window_hz")
    background_windows = _windows(background_windows_hz, "background_windows_hz")
    _require_windows_inside_trace(frequency, [fit_window, *background_windows])

    fp = _positive_finite(fp_hz, "fp_hz")
    fr = _positive_finite(fr_hz, "fr_hz")
    filter_off_reference_linewidth = _positive_finite(
        filter_off_reference_linewidth_hz, "filter_off_reference_linewidth_hz"
    )
    readout_off_reference_linewidth = _nonnegative_finite(
        readout_off_reference_linewidth_hz, "readout_off_reference_linewidth_hz"
    )
    reference_floor = _positive_finite(min_reference_magnitude, "min_reference_magnitude")
    min_reference = float(np.min(np.abs(reference)))
    _require(
        min_reference >= reference_floor,
        "empty-feedline reference magnitude falls below min_reference_magnitude.",
    )
    provenance_payload = _provenance(provenance)
    current_port_plane = cast(str, provenance_payload["port_plane"])
    channel_calibration_snapshot, channel_residue = _validated_channel_calibration(
        channel_calibration,
        phasor_convention=convention,
        fp_hz=fp,
        filter_off_reference_linewidth_hz=filter_off_reference_linewidth,
        current_reference_contract_id=cast(str, provenance_payload["reference_contract_id"]),
        current_filter_off_reference_id=cast(str, provenance_payload["filter_off_reference_id"]),
        current_port_plane=current_port_plane,
        actual_reference_min_magnitude=min_reference,
    )

    j_bounds = _window(j_bounds_hz, "j_bounds_hz")
    _require(j_bounds[0] > 0.0, "j_bounds_hz must be strictly positive.")
    j_seeds = _finite_values(j_seeds_hz, "j_seeds_hz")
    _require(bool(j_seeds), "j_seeds_hz must contain at least one seed.")
    _require(
        all(j_bounds[0] <= seed <= j_bounds[1] for seed in j_seeds),
        "Every j_seeds_hz value must lie within j_bounds_hz.",
    )
    ls_rcond = _nonnegative_finite(linear_ls_rcond, "linear_ls_rcond")
    complex_r2_gate = _r2_gate(min_complex_r2, "min_complex_r2")
    abs_r2_gate = _r2_gate(min_abs_r2, "min_abs_r2")
    phase_gate = _nonnegative_finite(max_phase_rmse_rad, "max_phase_rmse_rad")
    phase_magnitude_gate = _nonnegative_finite(min_phase_magnitude, "min_phase_magnitude")
    bound_margin_gate = _nonnegative_finite(
        min_normalized_bound_margin, "min_normalized_bound_margin"
    )
    _require(
        bound_margin_gate < 0.5,
        "min_normalized_bound_margin must be less than 0.5.",
    )
    seed_spread_gate = _nonnegative_finite(max_seed_spread_hz, "max_seed_spread_hz")
    max_nfev = _positive_integer(least_squares_max_nfev, "least_squares_max_nfev")
    least_squares_ftol_value = _positive_finite(least_squares_ftol, "least_squares_ftol")
    least_squares_xtol_value = _positive_finite(least_squares_xtol, "least_squares_xtol")
    least_squares_gtol_value = _positive_finite(least_squares_gtol, "least_squares_gtol")
    least_squares_diff_step_value = _positive_finite(
        least_squares_diff_step, "least_squares_diff_step"
    )
    successful_seed_count_gate = _positive_integer(
        min_successful_seed_count, "min_successful_seed_count"
    )
    successful_seed_fraction_gate = _fraction(
        min_successful_seed_fraction, "min_successful_seed_fraction"
    )
    near_optimal_ratio_gate = _finite_at_least(
        near_optimal_mse_ratio, 1.0, "near_optimal_mse_ratio"
    )
    near_optimal_absolute_gate = _nonnegative_finite(
        near_optimal_mse_absolute_tolerance,
        "near_optimal_mse_absolute_tolerance",
    )
    winning_seed_count_gate = _positive_integer(min_winning_seed_count, "min_winning_seed_count")
    _require(
        successful_seed_count_gate >= winning_seed_count_gate,
        "min_successful_seed_count must be at least min_winning_seed_count.",
    )
    _require(
        len(set(j_seeds)) == len(j_seeds),
        "j_seeds_hz must not contain duplicate seeds.",
    )
    total_seed_count = len(j_seeds)
    _require(
        successful_seed_count_gate <= total_seed_count,
        "min_successful_seed_count exceeds the declared seed-grid size.",
    )
    _require(
        winning_seed_count_gate <= total_seed_count,
        "min_winning_seed_count exceeds the declared seed-grid size.",
    )
    fit_mask = _mask_for_windows(frequency, [fit_window])
    background_mask = _mask_for_windows(frequency, background_windows)
    _require(
        int(np.count_nonzero(fit_mask)) >= 3,
        "fit_window_hz must select at least three samples.",
    )
    _require(
        int(np.count_nonzero(background_mask)) >= 2,
        "background_windows_hz must select at least two samples.",
    )

    base = {
        "schema": _PAIR_FIT_SCHEMA,
        "fit_method": _PAIR_FIT_METHOD,
        "fit_domain": "complex_s21",
        "model_convention": {
            "phasor_convention": convention,
            "denominator_term": (
                "a_x = loaded_linewidth_x_hz/2 + i*(f_hz - f_x_hz)"
                if phasor_sign > 0.0
                else "a_x = loaded_linewidth_x_hz/2 + i*(f_x_hz - f_hz)"
            ),
            "input_s21_conjugated": False,
            "boundary": "fixed_matched_local_hanger_with_independent_channel_calibration",
            "background_gauge": "fixed_affine_direct_path_after_empty_feedline_ratio",
            "free_cable_delay": False,
            "free_complex_residue": False,
            "simultaneous_j_residue_fit": False,
            "channel_residue_source": "independent_filter_off_reference_complex_s21_calibration",
            "off_reference_diagonal_frequencies_fixed": True,
            "asymmetric_channel_identifiability": False,
        },
        "normalization": {
            "method": "empty_through_s21_ratio_normalization",
            "port_plane": provenance_payload["port_plane"],
            "same_frequency_grid": True,
            "common_through_normalized": True,
            "factorization_assumption": "matched_chain_local_loading",
            "reference_plane_moved": False,
            "exact_two_port_deembedding": False,
            "external_cable_or_gain_deembedding_claimed": False,
            "residual_port_mismatch_handling": "fixed_affine_wing_background_and_quality_gates",
            "min_reference_magnitude": min_reference,
            "required_min_reference_magnitude": reference_floor,
        },
        "fit_window_hz": list(fit_window),
        "background_windows_hz": [list(window) for window in background_windows],
        "fixed_references": {
            "fp_hz": fp,
            "fr_hz": fr,
            "filter_off_reference_linewidth_hz": filter_off_reference_linewidth,
            "readout_off_reference_linewidth_hz": readout_off_reference_linewidth,
        },
        "channel_calibration": channel_calibration_snapshot,
        "search": {
            "j_bounds_hz": list(j_bounds),
            "j_seeds_hz": list(j_seeds),
        },
        "algorithm": {
            "linear_least_squares": {
                "driver": "numpy.linalg.lstsq",
                "rcond": ls_rcond,
            },
            "nonlinear_least_squares": {
                "driver": "scipy.optimize.least_squares",
                "method": "trf",
                "loss": "linear",
                "jac": "2-point",
                "ftol": least_squares_ftol_value,
                "xtol": least_squares_xtol_value,
                "gtol": least_squares_gtol_value,
                "diff_step": least_squares_diff_step_value,
                "max_nfev": max_nfev,
                "x_scale_hz": j_bounds[1] - j_bounds[0],
            },
        },
        "gates": {
            "min_complex_r2": complex_r2_gate,
            "min_abs_r2": abs_r2_gate,
            "max_phase_rmse_rad": phase_gate,
            "min_phase_magnitude": phase_magnitude_gate,
            "min_normalized_bound_margin": bound_margin_gate,
            "min_successful_seed_count": successful_seed_count_gate,
            "min_successful_seed_fraction": successful_seed_fraction_gate,
            "near_optimal_mse_ratio": near_optimal_ratio_gate,
            "near_optimal_mse_absolute_tolerance": near_optimal_absolute_gate,
            "min_winning_seed_count": winning_seed_count_gate,
            "max_seed_spread_hz": seed_spread_gate,
        },
        "provenance": provenance_payload,
    }

    try:
        with np.errstate(divide="raise", invalid="raise", over="raise"):
            normalized = measured / reference
        background = _fit_affine_background(
            frequency[background_mask],
            normalized[background_mask],
            rcond=ls_rcond,
        )
    except ValueError as exc:
        return _rejected(
            base,
            "rank_failure",
            f"affine background fit failed: {exc}",
        )
    except (FloatingPointError, np.linalg.LinAlgError) as exc:
        return _rejected(
            base,
            "numerical_failure",
            f"empty-through normalization/background fit failed: {exc}",
        )

    fit_frequency = frequency[fit_mask]
    fit_data = normalized[fit_mask]
    fit_background = _affine_background(fit_frequency, background)
    seed_results: list[dict[str, object]] = []
    finite_results: list[tuple[OptimizeResult, dict[str, object]]] = []
    successful_results: list[tuple[OptimizeResult, dict[str, object]]] = []

    def residual(values: np.ndarray) -> np.ndarray:
        fitted = _physical_s21(
            fit_frequency,
            fit_background,
            j_hz=float(values[0]),
            fp_hz=fp,
            fr_hz=fr,
            filter_off_reference_linewidth_hz=filter_off_reference_linewidth,
            readout_off_reference_linewidth_hz=readout_off_reference_linewidth,
            channel_residue_hz=channel_residue,
            phasor_sign=phasor_sign,
        )
        error = fitted - fit_data
        if not np.all(np.isfinite(error)):
            raise FloatingPointError("physical model produced a non-finite residual")
        return np.concatenate((error.real, error.imag))

    for seed_index, j_seed in enumerate(j_seeds):
        try:
            result = least_squares(
                residual,
                np.asarray([j_seed], dtype=float),
                bounds=(
                    np.asarray([j_bounds[0]]),
                    np.asarray([j_bounds[1]]),
                ),
                x_scale=np.asarray([j_bounds[1] - j_bounds[0]]),
                method="trf",
                loss="linear",
                jac="2-point",
                ftol=least_squares_ftol_value,
                xtol=least_squares_xtol_value,
                gtol=least_squares_gtol_value,
                diff_step=least_squares_diff_step_value,
                max_nfev=max_nfev,
            )
            fitted_values = np.asarray(result.x, dtype=float)
            cost = float(result.cost)
            optimizer_status = int(result.status)
            terminal_finite = bool(
                fitted_values.shape == (1,)
                and np.all(np.isfinite(fitted_values))
                and np.isfinite(cost)
            )
            optimizer_success = bool(result.success) and optimizer_status > 0 and terminal_finite
            active_mask = np.asarray(getattr(result, "active_mask", []), dtype=int)
            record: dict[str, object] = {
                "seed_index": seed_index,
                "j_seed_hz": j_seed,
                "j_fit_hz": float(fitted_values[0]) if fitted_values.shape == (1,) else None,
                "cost": cost if np.isfinite(cost) else None,
                "objective_mse": (2.0 * cost / len(fit_frequency) if terminal_finite else None),
                "optimizer_success": optimizer_success,
                "optimizer_status": optimizer_status,
                "optimizer_message": str(result.message),
                "nfev": int(result.nfev),
                "njev": (int(result.njev) if getattr(result, "njev", None) is not None else None),
                "optimality": (
                    float(result.optimality)
                    if np.isfinite(float(getattr(result, "optimality", math.nan)))
                    else None
                ),
                "active_mask": [int(value) for value in active_mask],
                "terminal_finite": terminal_finite,
                "numerical_failure": not terminal_finite,
                "near_optimal": False,
                "j_distance_from_best_hz": None,
            }
            seed_results.append(record)
            if terminal_finite:
                finite_results.append((result, record))
            if optimizer_success:
                successful_results.append((result, record))
        except (FloatingPointError, np.linalg.LinAlgError) as exc:
            seed_results.append(
                {
                    "seed_index": seed_index,
                    "j_seed_hz": j_seed,
                    "j_fit_hz": None,
                    "cost": None,
                    "objective_mse": None,
                    "optimizer_success": False,
                    "optimizer_status": None,
                    "optimizer_message": str(exc),
                    "nfev": None,
                    "njev": None,
                    "optimality": None,
                    "active_mask": None,
                    "terminal_finite": False,
                    "numerical_failure": True,
                    "near_optimal": False,
                    "j_distance_from_best_hz": None,
                }
            )

    required_successful_seed_count = max(
        successful_seed_count_gate,
        math.ceil(successful_seed_fraction_gate * total_seed_count),
    )
    successful_seed_count = len(successful_results)
    successful_seed_fraction = successful_seed_count / total_seed_count
    numerical_failure_count = sum(bool(record["numerical_failure"]) for record in seed_results)
    nonconverged_seed_count = total_seed_count - successful_seed_count - numerical_failure_count

    if not successful_results:
        return _rejected(
            {
                **base,
                "background": _background_payload(background),
                "diagnostics": {
                    "total_seed_count": total_seed_count,
                    "successful_seed_count": successful_seed_count,
                    "successful_seed_fraction": successful_seed_fraction,
                    "required_successful_seed_count": required_successful_seed_count,
                    "numerical_failure_count": numerical_failure_count,
                    "nonconverged_seed_count": nonconverged_seed_count,
                    "seed_results": seed_results,
                },
            },
            "numerical_failure" if numerical_failure_count else "optimizer_nonconvergence",
            "no finite successful J seed fit",
        )

    best, best_record = min(successful_results, key=lambda item: float(item[0].cost))
    j_fit = float(best.x[0])
    fitted = _physical_s21(
        fit_frequency,
        fit_background,
        j_hz=j_fit,
        fp_hz=fp,
        fr_hz=fr,
        filter_off_reference_linewidth_hz=filter_off_reference_linewidth,
        readout_off_reference_linewidth_hz=readout_off_reference_linewidth,
        channel_residue_hz=channel_residue,
        phasor_sign=phasor_sign,
    )
    metrics, phase_residual = _metrics(fit_data, fitted, phase_magnitude_gate)
    best_mse = cast(float, best_record["objective_mse"])
    near_optimal_mse_cutoff = near_optimal_ratio_gate * best_mse + near_optimal_absolute_gate
    near_optimal_results = [
        (result, record)
        for result, record in successful_results
        if cast(float, record["objective_mse"]) <= near_optimal_mse_cutoff
    ]
    for result, record in finite_results:
        record["near_optimal"] = cast(float, record["objective_mse"]) <= near_optimal_mse_cutoff
        record["j_distance_from_best_hz"] = float(result.x[0]) - j_fit
    near_optimal_js = [float(result.x[0]) for result, _ in near_optimal_results]
    seed_spread = max(near_optimal_js) - min(near_optimal_js)
    winning_seed_results = near_optimal_results
    unresolved_near_optimal_results = [
        record
        for _, record in finite_results
        if not bool(record["optimizer_success"])
        and cast(float, record["objective_mse"]) <= near_optimal_mse_cutoff
    ]
    noncompetitive_mses = [
        cast(float, record["objective_mse"])
        for _, record in successful_results
        if cast(float, record["objective_mse"]) > near_optimal_mse_cutoff
    ]
    next_best_noncompetitive_mse = min(noncompetitive_mses) if noncompetitive_mses else None
    next_best_noncompetitive_mse_ratio = (
        next_best_noncompetitive_mse / best_mse
        if next_best_noncompetitive_mse is not None and best_mse > 0.0
        else None
    )
    j_normalized_bound_margin = min(
        (j_fit - j_bounds[0]) / (j_bounds[1] - j_bounds[0]),
        (j_bounds[1] - j_fit) / (j_bounds[1] - j_bounds[0]),
    )
    failure_codes: list[str] = []
    failure_reasons: list[str] = []

    if numerical_failure_count:
        failure_codes.append("numerical_failure")
        failure_reasons.append("one or more J seed fits failed numerically")
    if successful_seed_count < required_successful_seed_count:
        failure_codes.append("seed_coverage_failure")
        failure_reasons.append(
            f"{successful_seed_count} successful seed fits is below required "
            f"{required_successful_seed_count}"
        )
    if unresolved_near_optimal_results:
        failure_codes.append("unresolved_near_optimal_start")
        failure_reasons.append(
            f"{len(unresolved_near_optimal_results)} nonconverged seed fits terminate "
            "inside the near-optimal MSE cutoff"
        )
    if seed_spread > seed_spread_gate:
        failure_codes.append("ambiguous_near_optimal_basin")
        failure_reasons.append(
            f"near-optimal J span {seed_spread} Hz exceeds {seed_spread_gate} Hz"
        )
    if len(winning_seed_results) < winning_seed_count_gate:
        failure_codes.append("insufficient_winning_seed_support")
        failure_reasons.append(
            f"{len(winning_seed_results)} winning seed fits is below "
            f"required {winning_seed_count_gate}"
        )

    bound_reasons: list[str] = []
    if j_normalized_bound_margin < bound_margin_gate:
        bound_reasons.append("fitted J is closer to its bound than min_normalized_bound_margin")
    if bound_reasons:
        failure_codes.append("bound_margin_failure")
        failure_reasons.extend(bound_reasons)
    _quality_failure(
        metrics,
        complex_r2_gate,
        abs_r2_gate,
        phase_gate,
        failure_codes,
        failure_reasons,
    )

    residual_trace = fitted - fit_data
    result_payload = {
        **base,
        "status": "rejected" if failure_codes else "success",
        "failure_codes": failure_codes,
        "failure_reasons": failure_reasons,
        "params": {"j_hz": j_fit},
        "background": _background_payload(background),
        "metrics": {**metrics, "cost": float(best.cost)},
        "diagnostics": {
            "j_bounds_hz": list(j_bounds),
            "j_seeds_hz": j_seeds,
            "j_seed_spread_hz": seed_spread,
            "j_normalized_bound_margin": j_normalized_bound_margin,
            "least_squares_max_nfev": max_nfev,
            "total_seed_count": total_seed_count,
            "successful_seed_count": successful_seed_count,
            "successful_seed_fraction": successful_seed_fraction,
            "required_successful_seed_count": required_successful_seed_count,
            "numerical_failure_count": numerical_failure_count,
            "nonconverged_seed_count": nonconverged_seed_count,
            "best_seed_index": cast(int, best_record["seed_index"]),
            "best_objective_mse": best_mse,
            "near_optimal_mse_cutoff": near_optimal_mse_cutoff,
            "near_optimal_seed_count": len(near_optimal_results),
            "near_optimal_seed_indices": [
                cast(int, record["seed_index"]) for _, record in near_optimal_results
            ],
            "near_optimal_j_span_hz": seed_spread,
            "winning_seed_count": len(winning_seed_results),
            "winning_seed_indices": [
                cast(int, record["seed_index"]) for _, record in winning_seed_results
            ],
            "unresolved_near_optimal_seed_count": len(unresolved_near_optimal_results),
            "unresolved_near_optimal_seed_indices": [
                cast(int, record["seed_index"]) for record in unresolved_near_optimal_results
            ],
            "next_best_noncompetitive_mse": next_best_noncompetitive_mse,
            "next_best_noncompetitive_mse_ratio": next_best_noncompetitive_mse_ratio,
            "seed_results": seed_results,
        },
        "derived_poles": _poles(
            fp,
            fr,
            filter_off_reference_linewidth,
            readout_off_reference_linewidth,
            j_fit,
            phasor_sign,
        ),
        "fit_trace": {
            "frequency_hz": _float_list(fit_frequency),
            "normalized_s21_real": _float_list(fit_data.real),
            "normalized_s21_imag": _float_list(fit_data.imag),
            "fitted_s21_real": _float_list(np.real(fitted)),
            "fitted_s21_imag": _float_list(np.imag(fitted)),
            "residual_real": _float_list(residual_trace.real),
            "residual_imag": _float_list(residual_trace.imag),
            "phase_residual_rad": _nullable_float_list(phase_residual),
        },
    }
    return result_payload


def _validated_channel_calibration(
    values: Mapping[str, object],
    *,
    phasor_convention: str,
    fp_hz: float,
    filter_off_reference_linewidth_hz: float,
    current_reference_contract_id: str,
    current_filter_off_reference_id: str,
    current_port_plane: str,
    actual_reference_min_magnitude: float,
) -> tuple[dict[str, object], complex]:
    calibration = _required_mapping(values, "channel_calibration")
    summary_keys = {
        "schema",
        "fit_method",
        "fit_domain",
        "model_convention",
        "normalization",
        "fit_window_hz",
        "background_windows_hz",
        "fixed_references",
        "algorithm",
        "gates",
        "calibration_id",
        "provenance",
        "status",
        "failure_codes",
        "failure_reasons",
        "params",
        "background",
        "metrics",
        "diagnostics",
        "calibration_summary_sha256",
    }
    _require(
        set(calibration) == summary_keys or set(calibration) == summary_keys | {"fit_trace"},
        "channel_calibration must contain exactly the successful summary fields "
        "with an optional fit_trace.",
    )
    _require(
        calibration.get("schema") == _CHANNEL_CALIBRATION_SCHEMA,
        f"channel_calibration schema must be {_CHANNEL_CALIBRATION_SCHEMA!r}.",
    )
    _require(
        calibration.get("fit_method") == _CHANNEL_CALIBRATION_FIT_METHOD,
        f"channel_calibration fit_method must be {_CHANNEL_CALIBRATION_FIT_METHOD!r}.",
    )
    _require(
        calibration.get("fit_domain") == "complex_s21",
        "channel_calibration fit_domain must be 'complex_s21'.",
    )
    _require(
        calibration.get("status") == "success",
        "channel_calibration status must be 'success'.",
    )
    _require(
        _string_values(calibration.get("failure_codes"), "channel_calibration.failure_codes") == [],
        "channel_calibration.failure_codes must be empty for a successful calibration.",
    )
    _require(
        _string_values(calibration.get("failure_reasons"), "channel_calibration.failure_reasons")
        == [],
        "channel_calibration.failure_reasons must be empty for a successful calibration.",
    )
    calibration_hash = calibration.get("calibration_summary_sha256")
    _require(
        isinstance(calibration_hash, str)
        and len(calibration_hash) == 64
        and all(character in "0123456789abcdef" for character in calibration_hash),
        "channel_calibration.calibration_summary_sha256 must be a lowercase SHA-256 digest.",
    )
    _require(
        _calibration_summary_sha256(calibration) == calibration_hash,
        "channel_calibration summary hash does not match its payload.",
    )

    model = _plain_scalar_mapping(
        calibration.get("model_convention"), "channel_calibration.model_convention"
    )
    _require(
        model.get("phasor_convention") == phasor_convention,
        "channel_calibration phasor convention must match the pair fit.",
    )
    _require(
        model.get("model") == "S21 = C21_affine + residue_hz / a_p"
        and model.get("linear_ls_basis") == "[1, scaled_frequency, 1/a_p]"
        and model.get("denominator_term")
        == (
            "a_p = off_reference_linewidth_p_hz/2 + i*(f_hz - f_p_hz)"
            if phasor_convention == "exp_plus_iomega_t"
            else "a_p = off_reference_linewidth_p_hz/2 + i*(f_p_hz - f_hz)"
        )
        and model.get("input_s21_conjugated") is False
        and model.get("calibration_samples") == "union_of_explicit_fit_and_background_windows"
        and model.get("free_cable_delay") is False,
        "channel_calibration model convention does not match the current calibration schema.",
    )

    fit_window = _window(
        _required_sequence(calibration.get("fit_window_hz"), "channel_calibration.fit_window_hz"),
        "channel_calibration.fit_window_hz",
    )
    background_windows = _windows(
        _required_nested_sequence(
            calibration.get("background_windows_hz"),
            "channel_calibration.background_windows_hz",
        ),
        "channel_calibration.background_windows_hz",
    )
    fixed = _required_mapping(
        calibration.get("fixed_references"), "channel_calibration.fixed_references"
    )
    _require(
        set(fixed) == {"fp_hz", "filter_off_reference_linewidth_hz"},
        "channel_calibration fixed references do not match the current schema.",
    )
    calibration_fp = _mapping_float(fixed, "fp_hz", "channel_calibration.fixed_references")
    calibration_linewidth = _mapping_float(
        fixed,
        "filter_off_reference_linewidth_hz",
        "channel_calibration.fixed_references",
    )
    _require(
        calibration_fp == fp_hz,
        "channel_calibration fp_hz must match the pair fit fp_hz.",
    )
    _require(
        calibration_linewidth == filter_off_reference_linewidth_hz,
        "channel_calibration filter off-reference linewidth must match the pair fit.",
    )

    algorithm = _required_mapping(calibration.get("algorithm"), "channel_calibration.algorithm")
    _require(
        set(algorithm) == {"linear_least_squares"},
        "channel_calibration algorithm does not match the current schema.",
    )
    linear_algorithm = _plain_scalar_mapping(
        algorithm.get("linear_least_squares"),
        "channel_calibration.algorithm.linear_least_squares",
    )
    _require(
        set(linear_algorithm) == {"driver", "rcond"},
        "channel_calibration linear algorithm does not match the current schema.",
    )
    _require(
        linear_algorithm.get("driver") == "numpy.linalg.lstsq",
        "channel_calibration must declare numpy.linalg.lstsq.",
    )
    calibration_rcond = _nonnegative_finite(
        _mapping_float(
            linear_algorithm,
            "rcond",
            "channel_calibration.algorithm.linear_least_squares",
        ),
        "channel_calibration.algorithm.linear_least_squares.rcond",
    )

    gates = _required_mapping(calibration.get("gates"), "channel_calibration.gates")
    _require(
        set(gates)
        == {
            "min_complex_r2",
            "min_abs_r2",
            "max_phase_rmse_rad",
            "min_phase_magnitude",
        },
        "channel_calibration gates do not match the current schema.",
    )
    gates_snapshot = {
        "min_complex_r2": _r2_gate(
            _mapping_float(gates, "min_complex_r2", "channel_calibration.gates"),
            "channel_calibration.gates.min_complex_r2",
        ),
        "min_abs_r2": _r2_gate(
            _mapping_float(gates, "min_abs_r2", "channel_calibration.gates"),
            "channel_calibration.gates.min_abs_r2",
        ),
        "max_phase_rmse_rad": _nonnegative_finite(
            _mapping_float(gates, "max_phase_rmse_rad", "channel_calibration.gates"),
            "channel_calibration.gates.max_phase_rmse_rad",
        ),
        "min_phase_magnitude": _nonnegative_finite(
            _mapping_float(gates, "min_phase_magnitude", "channel_calibration.gates"),
            "channel_calibration.gates.min_phase_magnitude",
        ),
    }

    params = _required_mapping(calibration.get("params"), "channel_calibration.params")
    _require(
        set(params) == {"channel_residue_real_hz", "channel_residue_imag_hz"},
        "channel_calibration params do not match the current schema.",
    )
    residue = _finite_complex(
        _mapping_float(params, "channel_residue_real_hz", "channel_calibration.params"),
        _mapping_float(params, "channel_residue_imag_hz", "channel_calibration.params"),
        "channel_calibration.params.channel_residue_hz",
    )
    calibration_id = calibration.get("calibration_id")
    _require(
        isinstance(calibration_id, str) and bool(calibration_id.strip()),
        "channel_calibration.calibration_id must be a non-empty string.",
    )
    provenance = _calibration_provenance(
        _required_mapping(calibration.get("provenance"), "channel_calibration.provenance")
    )
    _require(
        provenance["calibration_id"] == calibration_id,
        "channel_calibration calibration id must match its provenance.",
    )
    _require(
        provenance["reference_contract_id"] == current_reference_contract_id,
        "channel_calibration reference_contract_id must match the pair fit.",
    )
    _require(
        provenance["filter_off_reference_id"] == current_filter_off_reference_id,
        "channel_calibration filter off-reference identity must match the pair fit.",
    )
    _require(
        provenance["port_plane"] == current_port_plane,
        "channel_calibration provenance port plane must match the pair fit.",
    )

    normalization = _plain_scalar_mapping(
        calibration.get("normalization"), "channel_calibration.normalization"
    )
    _require(
        set(normalization)
        == {
            "method",
            "port_plane",
            "same_frequency_grid",
            "reference_plane_moved",
            "exact_two_port_deembedding",
            "min_reference_magnitude",
            "required_min_reference_magnitude",
        },
        "channel_calibration normalization does not match the current schema.",
    )
    _require(
        normalization.get("method") == "empty_through_s21_ratio_normalization"
        and normalization.get("port_plane") == current_port_plane
        and normalization.get("same_frequency_grid") is True
        and normalization.get("reference_plane_moved") is False
        and normalization.get("exact_two_port_deembedding") is False,
        "channel_calibration normalization is incompatible with the pair fit.",
    )
    recorded_reference_min = _positive_finite(
        _mapping_float(
            normalization,
            "min_reference_magnitude",
            "channel_calibration.normalization",
        ),
        "channel_calibration.normalization.min_reference_magnitude",
    )
    recorded_reference_floor = _positive_finite(
        _mapping_float(
            normalization,
            "required_min_reference_magnitude",
            "channel_calibration.normalization",
        ),
        "channel_calibration.normalization.required_min_reference_magnitude",
    )
    _require(
        recorded_reference_min >= recorded_reference_floor,
        "channel_calibration recorded reference magnitude is below its required floor.",
    )
    _require(
        actual_reference_min_magnitude >= recorded_reference_floor,
        "pair empty-feedline reference is below the calibration's required floor.",
    )
    background = _finite_numeric_mapping(
        calibration.get("background"),
        "channel_calibration.background",
        expected_keys={
            "frequency_center_hz",
            "frequency_scale_hz",
            "c0_real",
            "c0_imag",
            "c1_real_per_scaled_frequency",
            "c1_imag_per_scaled_frequency",
        },
    )
    _require(
        background["frequency_scale_hz"] > 0.0,
        "channel_calibration background frequency scale must be positive.",
    )
    metrics = _finite_numeric_mapping(
        calibration.get("metrics"),
        "channel_calibration.metrics",
        expected_keys={
            "complex_rmse",
            "complex_r2",
            "abs_rmse",
            "abs_r2",
            "phase_rmse_rad",
            "phase_valid_sample_count",
            "phase_valid_sample_fraction",
        },
    )
    diagnostics = _required_mapping(
        calibration.get("diagnostics"), "channel_calibration.diagnostics"
    )
    _require(
        set(diagnostics)
        == {
            "linear_ls_rank",
            "linear_ls_sample_count",
            "linear_ls_singular_values",
        },
        "channel_calibration diagnostics do not match the current schema.",
    )
    rank = _mapping_integer(diagnostics, "linear_ls_rank", "channel_calibration.diagnostics")
    sample_count = _mapping_integer(
        diagnostics, "linear_ls_sample_count", "channel_calibration.diagnostics"
    )
    _require(rank == 3, "channel_calibration linear least-squares rank must be three.")
    _require(
        sample_count >= rank,
        "channel_calibration sample count must support its declared rank.",
    )
    singular_values = _finite_values(
        _required_sequence(
            diagnostics.get("linear_ls_singular_values"),
            "channel_calibration.diagnostics.linear_ls_singular_values",
        ),
        "channel_calibration.diagnostics.linear_ls_singular_values",
    )
    _require(
        len(singular_values) == 3,
        "channel_calibration must report three linear least-squares singular values.",
    )
    _require(
        all(value > 0.0 for value in singular_values),
        "channel_calibration full-rank singular values must be positive.",
    )

    complex_r2 = float(metrics["complex_r2"])
    abs_r2 = float(metrics["abs_r2"])
    phase_rmse = float(metrics["phase_rmse_rad"])
    phase_valid_count = metrics["phase_valid_sample_count"]
    phase_valid_fraction = float(metrics["phase_valid_sample_fraction"])
    _require(
        float(metrics["complex_rmse"]) >= 0.0
        and float(metrics["abs_rmse"]) >= 0.0
        and phase_rmse >= 0.0,
        "channel_calibration RMSE metrics must be non-negative.",
    )
    _require(
        gates_snapshot["min_complex_r2"] <= complex_r2 <= 1.0,
        "channel_calibration complex R2 does not satisfy its successful-result gate.",
    )
    _require(
        gates_snapshot["min_abs_r2"] <= abs_r2 <= 1.0,
        "channel_calibration absolute-value R2 does not satisfy its successful-result gate.",
    )
    _require(
        phase_rmse <= gates_snapshot["max_phase_rmse_rad"],
        "channel_calibration phase RMSE does not satisfy its successful-result gate.",
    )
    _require(
        isinstance(phase_valid_count, int)
        and 0 < phase_valid_count <= sample_count
        and 0.0 < phase_valid_fraction <= 1.0,
        "channel_calibration phase-valid sample evidence must be non-zero and reasonable.",
    )

    snapshot: dict[str, object] = {
        "schema": _CHANNEL_CALIBRATION_SCHEMA,
        "status": "success",
        "fit_method": _CHANNEL_CALIBRATION_FIT_METHOD,
        "fit_domain": "complex_s21",
        "model_convention": model,
        "normalization": normalization,
        "fit_window_hz": list(fit_window),
        "background_windows_hz": [list(window) for window in background_windows],
        "fixed_references": {
            "fp_hz": calibration_fp,
            "filter_off_reference_linewidth_hz": calibration_linewidth,
        },
        "algorithm": {
            "linear_least_squares": {
                "driver": "numpy.linalg.lstsq",
                "rcond": calibration_rcond,
            }
        },
        "gates": gates_snapshot,
        "calibration_id": calibration_id,
        "provenance": provenance,
        "failure_codes": [],
        "failure_reasons": [],
        "params": {
            "channel_residue_real_hz": float(residue.real),
            "channel_residue_imag_hz": float(residue.imag),
        },
        "background": background,
        "metrics": metrics,
        "diagnostics": {
            "linear_ls_rank": rank,
            "linear_ls_sample_count": sample_count,
            "linear_ls_singular_values": singular_values,
        },
        "calibration_summary_sha256": calibration_hash,
    }
    _require(
        _calibration_summary_sha256(snapshot) == calibration_hash,
        "validated channel_calibration snapshot does not preserve its hashed summary.",
    )
    return snapshot, residue


def _system_a_observations(
    values: Sequence[Mapping[str, object]],
) -> list[dict[str, object]]:
    _require(
        isinstance(values, Sequence) and not isinstance(values, (str, bytes)),
        "observations must be a sequence of mappings.",
    )
    required = {
        "trace_id",
        "lj_per_junction_h",
        "lower_frequency_hz",
        "upper_frequency_hz",
        "lower_response_parameter",
        "lower_extraction_method",
        "lower_source_trace_id",
        "upper_response_parameter",
        "upper_extraction_method",
        "upper_source_trace_id",
        "candidate_id",
        "reference_contract_id",
        "topology_id",
        "port_plane",
    }
    parsed: list[dict[str, object]] = []
    seen_trace_ids: set[str] = set()
    for index, raw in enumerate(values):
        mapping = _required_mapping(raw, f"observations[{index}]")
        _require(
            set(mapping) == required,
            f"observations[{index}] must contain exactly {sorted(required)}.",
        )
        trace_id = cast(str, mapping["trace_id"])
        _require(
            isinstance(trace_id, str) and bool(trace_id.strip()),
            f"observations[{index}].trace_id must be a non-empty string.",
        )
        _require(trace_id not in seen_trace_ids, "observations trace_id values must be unique.")
        seen_trace_ids.add(trace_id)
        lower_frequency = _positive_finite(
            _mapping_float(mapping, "lower_frequency_hz", f"observations[{index}]"),
            f"observations[{index}].lower_frequency_hz",
        )
        upper_frequency = _positive_finite(
            _mapping_float(mapping, "upper_frequency_hz", f"observations[{index}]"),
            f"observations[{index}].upper_frequency_hz",
        )
        _require(
            lower_frequency < upper_frequency,
            f"observations[{index}] frequencies must be strictly lower/high ordered.",
        )
        identity = _validated_provenance(
            {
                name: mapping[name]
                for name in (
                    "trace_id",
                    "candidate_id",
                    "reference_contract_id",
                    "topology_id",
                    "port_plane",
                )
            },
            frozenset(
                {
                    "trace_id",
                    "candidate_id",
                    "reference_contract_id",
                    "topology_id",
                    "port_plane",
                }
            ),
            f"observations[{index}] identity",
        )
        branch_provenance: dict[str, dict[str, str]] = {}
        for branch in ("lower", "upper"):
            response_parameter = mapping[f"{branch}_response_parameter"]
            extraction_method = mapping[f"{branch}_extraction_method"]
            source_trace_id = mapping[f"{branch}_source_trace_id"]
            _require(
                isinstance(response_parameter, str)
                and response_parameter.upper() in {"S", "Y", "Z"},
                f"observations[{index}].{branch}_response_parameter must be S, Y, or Z.",
            )
            _require(
                isinstance(extraction_method, str) and bool(extraction_method.strip()),
                f"observations[{index}].{branch}_extraction_method must be a non-empty string.",
            )
            _require(
                isinstance(source_trace_id, str) and bool(source_trace_id.strip()),
                f"observations[{index}].{branch}_source_trace_id must be a non-empty string.",
            )
            branch_provenance[branch] = {
                "response_parameter": cast(str, response_parameter).upper(),
                "extraction_method": cast(str, extraction_method),
                "source_trace_id": cast(str, source_trace_id),
            }
        parsed.append(
            {
                **identity,
                "lj_per_junction_h": _positive_finite(
                    _mapping_float(mapping, "lj_per_junction_h", f"observations[{index}]"),
                    f"observations[{index}].lj_per_junction_h",
                ),
                "lower_frequency_hz": lower_frequency,
                "upper_frequency_hz": upper_frequency,
                "lower_branch": branch_provenance["lower"],
                "upper_branch": branch_provenance["upper"],
            }
        )
    _require(bool(parsed), "observations must not be empty.")
    lj_values = np.asarray(
        [float(cast(float, observation["lj_per_junction_h"])) for observation in parsed]
    )
    _require(
        len(set(lj_values.tolist())) == len(lj_values),
        "observations L_J values must be unique.",
    )
    lj_differences = np.diff(lj_values)
    _require(
        bool(np.all(lj_differences > 0.0) or np.all(lj_differences < 0.0)),
        "observations L_J values must be strictly monotonic in supplied sweep order.",
    )
    return parsed


def _validate_system_a_observation_identity(
    observations: Sequence[Mapping[str, object]],
    provenance: Mapping[str, object],
) -> None:
    for index, observation in enumerate(observations):
        for name in ("candidate_id", "reference_contract_id", "topology_id", "port_plane"):
            _require(
                observation[name] == provenance[name],
                f"observations[{index}].{name} must match provenance.{name}.",
            )


def _system_a_bounds(
    values: Mapping[str, Sequence[float]],
) -> dict[str, tuple[float, float]]:
    mapping = _required_mapping(values, "physical_bounds")
    _require(
        set(mapping) == set(_SYSTEM_A_PARAMETER_NAMES),
        f"physical_bounds must contain exactly {sorted(_SYSTEM_A_PARAMETER_NAMES)}.",
    )
    bounds = {
        name: _window(cast(Sequence[float], mapping[name]), f"physical_bounds.{name}")
        for name in _SYSTEM_A_PARAMETER_NAMES
    }
    _require(
        bounds["c_q_eff_system_a_on_f"][0] > 0.0,
        "physical_bounds.c_q_eff_system_a_on_f must be positive.",
    )
    _require(
        bounds["f_r_lb_system_a_on_hz"][0] > 0.0,
        "physical_bounds.f_r_lb_system_a_on_hz must be positive.",
    )
    _require(
        bounds["g_system_a_on_hz"][0] >= 0.0,
        "physical_bounds.g_system_a_on_hz must be nonnegative.",
    )
    return bounds


def _system_a_seeds(
    values: Sequence[Mapping[str, float]],
    bounds: Mapping[str, tuple[float, float]],
) -> list[dict[str, float]]:
    _require(
        isinstance(values, Sequence) and not isinstance(values, (str, bytes)),
        "physical_seeds must be a sequence of mappings.",
    )
    converted: list[dict[str, float]] = []
    for index, raw in enumerate(values):
        mapping = _required_mapping(raw, f"physical_seeds[{index}]")
        _require(
            set(mapping) == set(_SYSTEM_A_PARAMETER_NAMES),
            f"physical_seeds[{index}] must contain exactly {sorted(_SYSTEM_A_PARAMETER_NAMES)}.",
        )
        seed = {
            name: _mapping_float(mapping, name, f"physical_seeds[{index}]")
            for name in _SYSTEM_A_PARAMETER_NAMES
        }
        _require(
            all(bounds[name][0] <= seed[name] <= bounds[name][1] for name in seed),
            f"physical_seeds[{index}] must lie within physical_bounds.",
        )
        _require(
            seed["g_system_a_on_hz"] >= 0.0,
            f"physical_seeds[{index}].g_system_a_on_hz must be nonnegative.",
        )
        converted.append(seed)
    _require(bool(converted), "physical_seeds must not be empty.")
    _require(
        len({tuple(seed[name] for name in _SYSTEM_A_PARAMETER_NAMES) for seed in converted})
        == len(converted),
        "physical_seeds must not contain duplicates.",
    )
    return converted


def _system_a_numerical_tolerances(
    values: Mapping[str, int | float],
) -> dict[str, int | float]:
    mapping = _required_mapping(values, "numerical_tolerances")
    required = {
        "frequency_residual_scale_hz",
        "least_squares_max_nfev",
        "least_squares_ftol",
        "least_squares_xtol",
        "least_squares_gtol",
        "least_squares_diff_step",
        "jacobian_rank_rtol",
    }
    _require(
        set(mapping) == required,
        f"numerical_tolerances must contain exactly {sorted(required)}.",
    )
    return {
        "frequency_residual_scale_hz": _positive_finite(
            _mapping_float(mapping, "frequency_residual_scale_hz", "numerical_tolerances"),
            "numerical_tolerances.frequency_residual_scale_hz",
        ),
        "least_squares_max_nfev": _positive_integer(
            _mapping_integer(mapping, "least_squares_max_nfev", "numerical_tolerances"),
            "numerical_tolerances.least_squares_max_nfev",
        ),
        "least_squares_ftol": _positive_finite(
            _mapping_float(mapping, "least_squares_ftol", "numerical_tolerances"),
            "numerical_tolerances.least_squares_ftol",
        ),
        "least_squares_xtol": _positive_finite(
            _mapping_float(mapping, "least_squares_xtol", "numerical_tolerances"),
            "numerical_tolerances.least_squares_xtol",
        ),
        "least_squares_gtol": _positive_finite(
            _mapping_float(mapping, "least_squares_gtol", "numerical_tolerances"),
            "numerical_tolerances.least_squares_gtol",
        ),
        "least_squares_diff_step": _positive_finite(
            _mapping_float(mapping, "least_squares_diff_step", "numerical_tolerances"),
            "numerical_tolerances.least_squares_diff_step",
        ),
        "jacobian_rank_rtol": _positive_finite(
            _mapping_float(mapping, "jacobian_rank_rtol", "numerical_tolerances"),
            "numerical_tolerances.jacobian_rank_rtol",
        ),
    }


def _system_a_gates(values: Mapping[str, int | float]) -> dict[str, int | float]:
    mapping = _required_mapping(values, "gates")
    integer_names = {
        "min_trace_count",
        "min_successful_seed_count",
        "min_winning_seed_count",
        "min_jacobian_rank",
    }
    float_names = {
        "max_frequency_rmse_hz",
        "max_frequency_error_hz",
        "min_frequency_r2",
        "min_normalized_bound_margin",
        "min_successful_seed_fraction",
        "near_optimal_cost_ratio",
        "near_optimal_cost_absolute_tolerance",
        "max_seed_spread_normalized",
        "min_jacobian_singular_ratio",
    }
    required = integer_names | float_names
    _require(set(mapping) == required, f"gates must contain exactly {sorted(required)}.")
    converted: dict[str, int | float] = {
        name: _positive_integer(_mapping_integer(mapping, name, "gates"), f"gates.{name}")
        for name in integer_names
    }
    for name in float_names:
        converted[name] = _mapping_float(mapping, name, "gates")
    for name in (
        "max_frequency_rmse_hz",
        "max_frequency_error_hz",
        "min_normalized_bound_margin",
        "near_optimal_cost_absolute_tolerance",
        "max_seed_spread_normalized",
        "min_jacobian_singular_ratio",
    ):
        converted[name] = _nonnegative_finite(cast(float, converted[name]), f"gates.{name}")
    converted["min_frequency_r2"] = _r2_gate(
        cast(float, converted["min_frequency_r2"]), "gates.min_frequency_r2"
    )
    converted["min_successful_seed_fraction"] = _fraction(
        cast(float, converted["min_successful_seed_fraction"]),
        "gates.min_successful_seed_fraction",
    )
    converted["near_optimal_cost_ratio"] = _finite_at_least(
        cast(float, converted["near_optimal_cost_ratio"]),
        1.0,
        "gates.near_optimal_cost_ratio",
    )
    _require(
        cast(float, converted["min_normalized_bound_margin"]) < 0.5,
        "gates.min_normalized_bound_margin must be less than 0.5.",
    )
    _require(
        cast(float, converted["min_jacobian_singular_ratio"]) <= 1.0,
        "gates.min_jacobian_singular_ratio must be at most 1.",
    )
    _require(
        int(converted["min_jacobian_rank"]) == len(_SYSTEM_A_PARAMETER_NAMES),
        "gates.min_jacobian_rank must equal the three-parameter System-A model rank.",
    )
    return converted


def _run_system_a_seed_fits(
    observations: Sequence[Mapping[str, object]],
    lower: np.ndarray,
    widths: np.ndarray,
    seeds: Sequence[np.ndarray],
    tolerances: Mapping[str, int | float],
) -> tuple[list[dict[str, object]], list[tuple[OptimizeResult, dict[str, object]]]]:
    evidence: list[dict[str, object]] = []
    successful: list[tuple[OptimizeResult, dict[str, object]]] = []
    for seed_index, seed in enumerate(seeds):
        try:
            result = least_squares(
                lambda value: _system_a_residual(
                    value,
                    observations,
                    lower,
                    widths,
                    float(tolerances["frequency_residual_scale_hz"]),
                ),
                seed,
                bounds=(np.zeros_like(seed), np.ones_like(seed)),
                x_scale=np.ones_like(seed),
                method="trf",
                loss="linear",
                jac="2-point",
                ftol=float(tolerances["least_squares_ftol"]),
                xtol=float(tolerances["least_squares_xtol"]),
                gtol=float(tolerances["least_squares_gtol"]),
                diff_step=float(tolerances["least_squares_diff_step"]),
                max_nfev=int(tolerances["least_squares_max_nfev"]),
            )
            terminal_finite = bool(
                np.asarray(result.x).shape == seed.shape
                and np.all(np.isfinite(result.x))
                and np.isfinite(float(result.cost))
                and np.all(np.isfinite(result.fun))
                and np.all(np.isfinite(result.jac))
            )
            success = bool(result.success and result.status > 0 and terminal_finite)
            record: dict[str, object] = {
                "seed_index": seed_index,
                "seed_normalized": _float_list(seed),
                "terminal_normalized": (
                    _float_list(np.asarray(result.x, dtype=float)) if terminal_finite else None
                ),
                "terminal_physical": (
                    {
                        name: float((lower + widths * np.asarray(result.x))[index])
                        for index, name in enumerate(_SYSTEM_A_PARAMETER_NAMES)
                    }
                    if terminal_finite
                    else None
                ),
                "cost": float(result.cost) if terminal_finite else None,
                "optimizer_success": success,
                "optimizer_status": int(result.status),
                "optimizer_message": str(result.message),
                "nfev": int(result.nfev),
                "njev": int(result.njev) if result.njev is not None else None,
                "optimality": (
                    float(result.optimality) if np.isfinite(float(result.optimality)) else None
                ),
                "near_optimal": False,
                "max_parameter_distance_from_best_normalized": None,
            }
            evidence.append(record)
            if success:
                successful.append((result, record))
        except (FloatingPointError, np.linalg.LinAlgError, ValueError) as exc:
            evidence.append(
                {
                    "seed_index": seed_index,
                    "seed_normalized": _float_list(seed),
                    "terminal_normalized": None,
                    "terminal_physical": None,
                    "cost": None,
                    "optimizer_success": False,
                    "optimizer_status": None,
                    "optimizer_message": str(exc),
                    "nfev": None,
                    "njev": None,
                    "optimality": None,
                    "near_optimal": False,
                    "max_parameter_distance_from_best_normalized": None,
                }
            )
    return evidence, successful


def _system_a_residual(
    normalized_parameters: np.ndarray,
    observations: Sequence[Mapping[str, object]],
    lower: np.ndarray,
    widths: np.ndarray,
    residual_scale_hz: float,
) -> np.ndarray:
    parameters = lower + widths * np.asarray(normalized_parameters, dtype=float)
    params = {
        name: float(parameters[index]) for index, name in enumerate(_SYSTEM_A_PARAMETER_NAMES)
    }
    _, residual_hz = _system_a_predictions(observations, params)
    scaled = residual_hz.reshape(-1) / residual_scale_hz
    if not np.all(np.isfinite(scaled)):
        raise FloatingPointError("System-A frequency residual is non-finite.")
    return scaled


def _system_a_predictions(
    observations: Sequence[Mapping[str, object]],
    params: Mapping[str, float],
) -> tuple[list[dict[str, object]], np.ndarray]:
    per_lj: list[dict[str, object]] = []
    residuals: list[tuple[float, float]] = []
    for observation in observations:
        fq_hz = _system_a_fq_hz(
            float(cast(float, observation["lj_per_junction_h"])),
            float(params["c_q_eff_system_a_on_f"]),
        )
        fr_hz = float(params["f_r_lb_system_a_on_hz"])
        g_hz = float(params["g_system_a_on_hz"])
        midpoint = 0.5 * (fq_hz + fr_hz)
        half_splitting = math.sqrt((0.5 * (fq_hz - fr_hz)) ** 2 + g_hz**2)
        predicted_lower = midpoint - half_splitting
        predicted_upper = midpoint + half_splitting
        observed_lower = float(cast(float, observation["lower_frequency_hz"]))
        observed_upper = float(cast(float, observation["upper_frequency_hz"]))
        lower_residual = predicted_lower - observed_lower
        upper_residual = predicted_upper - observed_upper
        residuals.append((lower_residual, upper_residual))
        per_lj.append(
            {
                "trace_id": observation["trace_id"],
                "lj_per_junction_h": observation["lj_per_junction_h"],
                "f_q_model_hz": fq_hz,
                "observed_lower_frequency_hz": observed_lower,
                "observed_upper_frequency_hz": observed_upper,
                "predicted_lower_frequency_hz": predicted_lower,
                "predicted_upper_frequency_hz": predicted_upper,
                "lower_frequency_residual_hz": lower_residual,
                "upper_frequency_residual_hz": upper_residual,
                "lower_branch_provenance": observation["lower_branch"],
                "upper_branch_provenance": observation["upper_branch"],
            }
        )
    return per_lj, np.asarray(residuals, dtype=float)


def _system_a_fq_hz(lj_per_junction_h: float, c_q_eff_f: float) -> float:
    return 1.0 / (2.0 * math.pi * math.sqrt((lj_per_junction_h / 2.0) * c_q_eff_f))


def _system_a_metrics(
    observations: Sequence[Mapping[str, object]],
    residual_hz: np.ndarray,
) -> dict[str, float | int | None]:
    observed = np.asarray(
        [
            [
                float(cast(float, item["lower_frequency_hz"])),
                float(cast(float, item["upper_frequency_hz"])),
            ]
            for item in observations
        ],
        dtype=float,
    )
    residual_flat = residual_hz.reshape(-1)
    observed_flat = observed.reshape(-1)
    sse = float(np.dot(residual_flat, residual_flat))
    centered = observed_flat - float(np.mean(observed_flat))
    centered_sse = float(np.dot(centered, centered))
    return {
        "frequency_rmse_hz": float(np.sqrt(np.mean(residual_flat**2))),
        "max_abs_frequency_error_hz": float(np.max(np.abs(residual_flat))),
        "frequency_r2": 1.0 - sse / centered_sse if centered_sse > 0.0 else None,
        "trace_count": len(observations),
        "frequency_observation_count": len(observed_flat),
    }


def _system_a_identifiability(
    jacobian: np.ndarray,
    relative_cutoff: float,
) -> dict[str, object]:
    singular_values = np.linalg.svd(jacobian, compute_uv=False)
    _require(
        bool(singular_values.size) and bool(np.all(np.isfinite(singular_values))),
        "System-A Jacobian singular values must be finite and non-empty.",
    )
    threshold = relative_cutoff * float(singular_values[0])
    rank = int(np.count_nonzero(singular_values > threshold))
    ratio = float(singular_values[-1] / singular_values[0]) if singular_values[0] > 0.0 else 0.0
    return {
        "parameter_order": list(_SYSTEM_A_PARAMETER_NAMES),
        "rank": rank,
        "rank_threshold": threshold,
        "svd_relative_cutoff": relative_cutoff,
        "singular_values": _float_list(singular_values),
        "singular_value_ratio": ratio,
    }


def _system_a_rejected(
    base: Mapping[str, object],
    codes: Sequence[str],
    reasons: Sequence[str],
    *,
    seed_evidence: Sequence[Mapping[str, object]],
) -> dict[str, object]:
    search = cast(Mapping[str, object], base["search"])
    seed_count = len(cast(Sequence[object], search["physical_seeds"]))
    successful_seed_count = sum(bool(item.get("optimizer_success")) for item in seed_evidence)
    return {
        **base,
        "status": "rejected",
        "failure_codes": list(codes),
        "failure_reasons": list(reasons),
        "params": None,
        "per_lj": None,
        "metrics": None,
        "seed_evidence": list(seed_evidence),
        "multi_start": {
            "fit_executed": bool(seed_evidence),
            "seed_count": seed_count,
            "successful_seed_count": successful_seed_count,
        },
        "bound_margins": None,
        "identifiability": None,
        "optimizer": None,
    }


def _prepare_traces(
    frequency_hz: Sequence[float],
    measured_real: Sequence[float],
    measured_imag: Sequence[float],
    reference_real: Sequence[float],
    reference_imag: Sequence[float],
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    arrays = [
        np.asarray(list(values), dtype=float)
        for values in (
            frequency_hz,
            measured_real,
            measured_imag,
            reference_real,
            reference_imag,
        )
    ]
    frequency, measured_re, measured_im, reference_re, reference_im = arrays
    _require(
        all(array.ndim == 1 for array in arrays),
        "All trace inputs must be one-dimensional.",
    )
    _require(
        len({len(array) for array in arrays}) == 1,
        "Frequency, measured S21, and empty-feedline S21 arrays must have the same length.",
    )
    _require(len(frequency) >= 3, "At least three trace samples are required.")
    _require(
        all(bool(np.all(np.isfinite(array))) for array in arrays),
        "Trace inputs must contain only finite values.",
    )
    _require(bool(np.all(frequency > 0.0)), "frequency_hz must be positive.")
    _require(
        bool(np.all(np.diff(frequency) > 0.0)),
        "frequency_hz must be strictly increasing.",
    )
    return frequency, measured_re + 1j * measured_im, reference_re + 1j * reference_im


def _fit_affine_background(
    frequency: np.ndarray,
    data: np.ndarray,
    *,
    rcond: float,
) -> np.ndarray:
    center = float(np.mean(frequency))
    scale = float(np.ptp(frequency))
    _require(scale > 0.0, "background_windows_hz must span more than one frequency.")
    x = (frequency - center) / scale
    basis = np.column_stack((np.ones_like(x), x))
    coefficients, _, rank, _ = np.linalg.lstsq(basis.astype(complex), data, rcond=rcond)
    _require(rank == 2, "background_windows_hz do not identify an affine background.")
    _require(
        bool(np.all(np.isfinite(coefficients))),
        "Affine background coefficients are non-finite.",
    )
    return np.asarray([center, scale, *coefficients], dtype=complex)


def _affine_background(frequency: np.ndarray, background: np.ndarray) -> np.ndarray:
    center = float(background[0].real)
    scale = float(background[1].real)
    return background[2] + background[3] * ((frequency - center) / scale)


def _physical_s21(
    frequency_hz: np.ndarray,
    background: np.ndarray,
    *,
    j_hz: float,
    fp_hz: float,
    fr_hz: float,
    filter_off_reference_linewidth_hz: float,
    readout_off_reference_linewidth_hz: float,
    channel_residue_hz: complex,
    phasor_sign: float,
) -> np.ndarray:
    a_p = filter_off_reference_linewidth_hz / 2.0 + 1j * phasor_sign * (frequency_hz - fp_hz)
    a_r = readout_off_reference_linewidth_hz / 2.0 + 1j * phasor_sign * (frequency_hz - fr_hz)
    denominator = a_p * a_r + j_hz**2
    return background + channel_residue_hz * a_r / denominator


def _metrics(
    data: np.ndarray,
    fitted: np.ndarray,
    min_phase_magnitude: float,
) -> tuple[dict[str, float | int | None], np.ndarray]:
    residual = fitted - data
    abs_residual = np.abs(fitted) - np.abs(data)
    complex_sse = float(np.sum(np.abs(residual) ** 2))
    abs_sse = float(np.sum(abs_residual**2))
    complex_centered = float(np.sum(np.abs(data - np.mean(data)) ** 2))
    abs_centered = float(np.sum((np.abs(data) - np.mean(np.abs(data))) ** 2))
    phase_residual = np.angle(fitted * np.conjugate(data))
    phase_valid = (np.abs(fitted) >= min_phase_magnitude) & (np.abs(data) >= min_phase_magnitude)
    phase_valid_count = int(np.count_nonzero(phase_valid))
    phase_rmse = (
        float(np.sqrt(np.mean(phase_residual[phase_valid] ** 2))) if phase_valid_count > 0 else None
    )
    return (
        {
            "complex_rmse": float(np.sqrt(np.mean(np.abs(residual) ** 2))),
            "complex_r2": 1.0 - complex_sse / complex_centered if complex_centered > 0.0 else None,
            "abs_rmse": float(np.sqrt(np.mean(abs_residual**2))),
            "abs_r2": 1.0 - abs_sse / abs_centered if abs_centered > 0.0 else None,
            "phase_rmse_rad": phase_rmse,
            "phase_valid_sample_count": phase_valid_count,
            "phase_valid_sample_fraction": phase_valid_count / len(data),
        },
        np.where(phase_valid, phase_residual, np.nan),
    )


def _quality_failure(
    metrics: Mapping[str, float | int | None],
    min_complex_r2: float,
    min_abs_r2: float,
    max_phase_rmse_rad: float,
    failure_codes: list[str],
    failure_reasons: list[str],
) -> None:
    complex_r2 = metrics["complex_r2"]
    abs_r2 = metrics["abs_r2"]
    phase_rmse = metrics["phase_rmse_rad"]
    failures = [
        (
            "complex R2 is undefined or non-finite",
            complex_r2 is None or not np.isfinite(complex_r2),
        ),
        (
            f"complex R2 is below {min_complex_r2}",
            complex_r2 is not None and np.isfinite(complex_r2) and complex_r2 < min_complex_r2,
        ),
        (
            "absolute-value R2 is undefined or non-finite",
            abs_r2 is None or not np.isfinite(abs_r2),
        ),
        (
            f"absolute-value R2 is below {min_abs_r2}",
            abs_r2 is not None and np.isfinite(abs_r2) and abs_r2 < min_abs_r2,
        ),
        (
            "phase RMSE is undefined or non-finite",
            phase_rmse is None or not np.isfinite(phase_rmse),
        ),
        (
            f"phase RMSE exceeds {max_phase_rmse_rad} rad",
            phase_rmse is not None and np.isfinite(phase_rmse) and phase_rmse > max_phase_rmse_rad,
        ),
    ]
    reasons = [reason for reason, failed in failures if failed]
    if reasons:
        failure_codes.append("quality_failure")
        failure_reasons.extend(reasons)


def _poles(
    fp_hz: float,
    fr_hz: float,
    filter_off_reference_linewidth_hz: float,
    readout_off_reference_linewidth_hz: float,
    j_hz: float,
    phasor_sign: float,
) -> list[dict[str, float]]:
    omega_p = complex(fp_hz, phasor_sign * filter_off_reference_linewidth_hz / 2.0)
    omega_r = complex(fr_hz, phasor_sign * readout_off_reference_linewidth_hz / 2.0)
    split = np.sqrt(j_hz**2 + ((omega_p - omega_r) / 2.0) ** 2)
    poles = [(omega_p + omega_r) / 2.0 - split, (omega_p + omega_r) / 2.0 + split]
    return [
        {
            "frequency_hz": float(pole.real),
            "imaginary_hz": float(pole.imag),
            "linewidth_hz": float(2.0 * phasor_sign * pole.imag),
        }
        for pole in sorted(poles, key=lambda value: value.real)
    ]


def _background_payload(background: np.ndarray) -> dict[str, float]:
    return {
        "frequency_center_hz": float(background[0].real),
        "frequency_scale_hz": float(background[1].real),
        "c0_real": float(background[2].real),
        "c0_imag": float(background[2].imag),
        "c1_real_per_scaled_frequency": float(background[3].real),
        "c1_imag_per_scaled_frequency": float(background[3].imag),
    }


def _calibration_summary_sha256(values: Mapping[str, object]) -> str:
    summary = {
        key: value
        for key, value in values.items()
        if key not in {"fit_trace", "calibration_summary_sha256"}
    }
    try:
        canonical_json = json.dumps(
            summary,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        )
    except (TypeError, ValueError) as exc:
        raise ValueError(
            "channel_calibration summary must be canonical-JSON serializable."
        ) from exc
    return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()


def _rejected(base: dict[str, object], code: str, reason: str) -> dict[str, object]:
    return {
        **base,
        "status": "rejected",
        "failure_codes": [code],
        "failure_reasons": [reason],
        "params": None,
        "metrics": None,
        "derived_poles": None,
        "fit_trace": None,
    }


def _phasor_convention(value: str) -> tuple[str, float]:
    if value == "exp_plus_iomega_t":
        return value, 1.0
    if value == "exp_minus_iomega_t":
        return value, -1.0
    raise ValueError("phasor_convention must be 'exp_plus_iomega_t' or 'exp_minus_iomega_t'.")


def _window(values: Sequence[float], name: str) -> tuple[float, float]:
    converted = tuple(float(value) for value in values)
    _require(len(converted) == 2, f"{name} must contain exactly two values.")
    _require(all(np.isfinite(value) for value in converted), f"{name} must be finite.")
    _require(
        converted[0] < converted[1],
        f"{name} lower bound must be less than upper bound.",
    )
    return converted[0], converted[1]


def _windows(values: Sequence[Sequence[float]], name: str) -> list[tuple[float, float]]:
    converted = [_window(value, f"{name}[{index}]") for index, value in enumerate(values)]
    _require(bool(converted), f"{name} must contain at least one window.")
    return converted


def _require_windows_inside_trace(
    frequency: np.ndarray, windows: Sequence[tuple[float, float]]
) -> None:
    _require(
        all(frequency[0] <= lower < upper <= frequency[-1] for lower, upper in windows),
        "All fit/background windows must lie inside the supplied frequency trace.",
    )


def _mask_for_windows(frequency: np.ndarray, windows: Sequence[tuple[float, float]]) -> np.ndarray:
    return np.logical_or.reduce(
        [(frequency >= lower) & (frequency <= upper) for lower, upper in windows]
    )


def _finite_values(values: Sequence[float], name: str) -> list[float]:
    converted = [float(value) for value in values]
    _require(all(np.isfinite(value) for value in converted), f"{name} must be finite.")
    return converted


def _positive_finite(value: float, name: str) -> float:
    converted = float(value)
    if not np.isfinite(converted) or converted <= 0.0:
        _raise(f"{name} must be finite and positive.")
    return converted


def _nonnegative_finite(value: float, name: str) -> float:
    converted = float(value)
    if not np.isfinite(converted) or converted < 0.0:
        _raise(f"{name} must be finite and non-negative.")
    return converted


def _positive_integer(value: int, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, Integral) or int(value) <= 0:
        _raise(f"{name} must be a positive integer.")
    return int(value)


def _fraction(value: float, name: str) -> float:
    converted = float(value)
    if not np.isfinite(converted) or not 0.0 < converted <= 1.0:
        _raise(f"{name} must be finite and in (0, 1].")
    return converted


def _finite_at_least(value: float, lower_bound: float, name: str) -> float:
    converted = float(value)
    if not np.isfinite(converted) or converted < lower_bound:
        _raise(f"{name} must be finite and at least {lower_bound}.")
    return converted


def _finite_complex(real_value: float, imag_value: float, name: str) -> complex:
    converted = complex(float(real_value), float(imag_value))
    _require(
        np.isfinite(converted.real) and np.isfinite(converted.imag),
        f"{name} must have finite real and imaginary parts.",
    )
    return converted


def _r2_gate(value: float, name: str) -> float:
    converted = float(value)
    if not np.isfinite(converted) or converted > 1.0:
        _raise(f"{name} must be finite and at most 1.0.")
    return converted


def _provenance(values: Mapping[str, object]) -> dict[str, str | bool | int | float]:
    required = frozenset(
        {
            "reference_contract_id",
            "measured_trace_id",
            "empty_feedline_trace_id",
            "filter_off_reference_id",
            "common_readout_off_reference_id",
            "pair_assignment_id",
            "port_plane",
        }
    )
    return _validated_provenance(values, required, "provenance")


def _calibration_provenance(
    values: Mapping[str, object],
) -> dict[str, str | bool | int | float]:
    required = frozenset(
        {
            "calibration_id",
            "reference_contract_id",
            "filter_off_reference_trace_id",
            "empty_feedline_trace_id",
            "filter_off_reference_id",
            "port_plane",
        }
    )
    return _validated_provenance(values, required, "calibration provenance")


def _validated_provenance(
    values: Mapping[str, object], required: frozenset[str], name: str
) -> dict[str, str | bool | int | float]:
    converted = _plain_scalar_mapping(values, name)
    _require(bool(converted), f"{name} must not be empty.")
    missing = sorted(required - set(converted))
    _require(not missing, f"{name} is missing required keys: {missing}.")
    for key in required:
        _require(
            isinstance(converted[key], str) and bool(str(converted[key]).strip()),
            f"{name}[{key!r}] must be a non-empty string.",
        )
    return converted


def _required_mapping(value: object, name: str) -> Mapping[str, object]:
    _require(isinstance(value, Mapping), f"{name} must be a mapping.")
    mapping = cast(Mapping[object, object], value)
    _require(
        all(isinstance(key, str) and bool(key.strip()) for key in mapping),
        f"{name} keys must be non-empty strings.",
    )
    return cast(Mapping[str, object], value)


def _required_sequence(value: object, name: str) -> list[float]:
    _require(
        isinstance(value, Sequence) and not isinstance(value, (str, bytes)),
        f"{name} must be a numeric sequence.",
    )
    return _finite_values(cast(Sequence[float], value), name)


def _required_nested_sequence(value: object, name: str) -> list[list[float]]:
    _require(
        isinstance(value, Sequence) and not isinstance(value, (str, bytes)),
        f"{name} must be a sequence of numeric sequences.",
    )
    return [
        _required_sequence(item, f"{name}[{index}]")
        for index, item in enumerate(cast(Sequence[object], value))
    ]


def _string_values(value: object, name: str) -> list[str]:
    _require(
        isinstance(value, Sequence) and not isinstance(value, (str, bytes)),
        f"{name} must be a sequence of strings.",
    )
    converted = list(cast(Sequence[object], value))
    _require(all(isinstance(item, str) for item in converted), f"{name} must contain strings.")
    return cast(list[str], converted)


def _plain_scalar_mapping(value: object, name: str) -> dict[str, str | bool | int | float]:
    mapping = _required_mapping(value, name)
    converted: dict[str, str | bool | int | float] = {}
    for key, item in mapping.items():
        if isinstance(item, str):
            _require(bool(item.strip()), f"{name}[{key!r}] must not be empty.")
            converted[key] = item
        elif isinstance(item, bool):
            converted[key] = item
        elif isinstance(item, Integral):
            converted[key] = int(item)
        elif isinstance(item, Real) and np.isfinite(float(item)):
            converted[key] = float(item)
        else:
            _raise(f"{name}[{key!r}] must be a finite scalar.")
    return converted


def _finite_numeric_mapping(
    value: object,
    name: str,
    *,
    expected_keys: set[str],
) -> dict[str, int | float]:
    mapping = _required_mapping(value, name)
    _require(set(mapping) == expected_keys, f"{name} must contain exactly {sorted(expected_keys)}.")
    converted: dict[str, int | float] = {}
    for key, item in mapping.items():
        if isinstance(item, bool) or not isinstance(item, Real) or not np.isfinite(float(item)):
            _raise(f"{name}[{key!r}] must be a finite number.")
        converted[key] = int(item) if isinstance(item, Integral) else float(item)
    return converted


def _mapping_float(values: Mapping[str, object], key: str, name: str) -> float:
    value = values.get(key)
    if isinstance(value, bool) or not isinstance(value, Real) or not np.isfinite(float(value)):
        _raise(f"{name}[{key!r}] must be a finite number.")
    return float(value)


def _mapping_integer(values: Mapping[str, object], key: str, name: str) -> int:
    value = values.get(key)
    if isinstance(value, bool) or not isinstance(value, Integral):
        _raise(f"{name}[{key!r}] must be an integer.")
    return int(value)


def _float_list(values: np.ndarray) -> list[float]:
    return [float(value) for value in values]


def _nullable_float_list(values: np.ndarray) -> list[float | None]:
    return [float(value) if np.isfinite(value) else None for value in values]


def _require(condition: bool, message: str) -> None:
    if not condition:
        _raise(message)


def _raise(message: str) -> Never:
    raise ValueError(message)
