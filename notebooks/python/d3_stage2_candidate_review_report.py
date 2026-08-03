"""Render one canonical-artifact-backed D3 Stage-2 candidate review report.

The producer strictly loads one canonical Stage-2 run directory and verifies
that its linear quantities and weighted floating-qubit admittance share the
same summary, objective authority, and model identity. It owns the D3-specific
three-panel review figure and table wording; the shared Human-reviewable report
composer owns publication, layout, and the evidence register.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import tempfile
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import numpy as np
import plotly.graph_objects as go
from human_reviewable_simulation_report import (
    SCHEMA_VERSION,
    file_sha256,
    render_simulation_report,
)
from plotly.subplots import make_subplots
from superconducting_circuits_analysis.application.analysis.fitting.s_parameters import (
    fit_complex_s21_vector,
)

_SUMMARY_SCHEMA = "d3-stage2-physical-candidate-summary.v1"
_LINEAR_QUANTITIES_SCHEMA = "d3-stage2-linear-quantity-review.v3"
_QUBIT_RECEIPT_SCHEMA = "d3-stage2-qubit-admittance-receipt.v1"
_OBJECTIVE_CONTRACT_ID = "d3-stage2-stage3-full-qrp-objective.v2"
_OBJECTIVE_AUTHORITY = {
    "approval_status": "human_approved",
    "target_id": "d3-same-face-resonators-opposite-face-qubit-j5-k20-gap8",
    "target_revision": 7,
    "target_contract_sha256": (
        "2ec4014c5bd3ba5824c15d71c3ad1e03b2a0d1f7444a35dcd31b0a4fe99b7bf9"
    ),
    "notch_authority": "rp_on",
    "effective_diagonal_frequency_extraction": (
        "q_feedline_downfolded_rp_complex_operator"
    ),
    "effective_exchange_extraction": (
        "q_feedline_downfolded_rp_complex_midpoint_residue"
    ),
    "linewidth_pole_scope": "qrp_three",
    "primary_linewidth_extraction": "L_C",
}
_S21_COLUMNS = (
    "frequency_hz",
    "direct_real",
    "direct_imag",
    "exact_real",
    "exact_imag",
    "hb_real",
    "hb_imag",
)
_QUBIT_COLUMNS = (
    "frequency_hz",
    "hb_y_eff_real_s",
    "hb_y_eff_imag_s",
    "direct_y_eff_real_s",
    "direct_y_eff_imag_s",
    "hb_t1_s",
    "direct_t1_s",
    "c_q_eff_f",
    "alpha",
    "beta",
    "kron_condition_number",
    "hb_direct_abs_y_residual_s",
)
_CANDIDATE_KEYS = (
    "lr_open_m",
    "lr_short_m",
    "lc_m",
    "lp_open_m",
    "lp_short_m",
    "u_IDC",
)
_RUN_FILES = (
    "summary.json",
    "history.json",
    "s21.csv",
    "linear-quantities.json",
    "qubit-admittance.csv",
    "qubit-admittance-receipt.json",
)
_SUMMARY_HASHED_FILES = ("history.json", "s21.csv", "qubit-admittance.csv")


def _load_json(path: Path, label: str) -> Any:
    if not path.is_file():
        raise FileNotFoundError(f"Missing {label}: {path}")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise ValueError(f"Invalid {label} JSON: {path}") from error


def _mapping(value: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{label} must be a JSON object.")
    return value


def _finite(value: Any, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{label} must be numeric.")
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(f"{label} must be finite.")
    return number


def _require_keys(value: Mapping[str, Any], keys: Sequence[str], label: str) -> None:
    missing = set(keys) - set(value)
    if missing:
        raise ValueError(f"{label} is missing fields: {sorted(missing)}")


def _model_identity(value: Any, label: str) -> dict[str, str]:
    identity = _mapping(value, label)
    fields = (
        "circuit_plan_sha256",
        "capacitance_sha256",
        "inverse_inductance_sha256",
        "selector_sha256",
    )
    if set(identity) != set(fields):
        raise ValueError(f"{label} must contain exactly {list(fields)}.")
    normalized: dict[str, str] = {}
    for field in fields:
        raw = identity[field]
        if (
            not isinstance(raw, str)
            or len(raw) != 64
            or any(character not in "0123456789abcdef" for character in raw)
        ):
            raise ValueError(f"{label}.{field} must be lowercase SHA-256.")
        normalized[field] = raw
    return normalized


def _sha256(value: Any, label: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise ValueError(f"{label} must be lowercase SHA-256.")
    return value


def _load_summary(path: Path) -> dict[str, Any]:
    summary = dict(_mapping(_load_json(path, "summary"), "summary"))
    _require_keys(
        summary,
        (
            "schema_version",
            "status",
            "objective_contract_id",
            "objective_authority",
            "model_identity",
            "slot_hz",
            "q2d_spec",
            "bounds",
            "cma",
            "best_candidate",
            "best_resolved_lc",
            "best_metrics",
            "best_objective",
            "response_match",
            "artifact_contract",
            "artifacts",
        ),
        "summary",
    )
    if summary["schema_version"] != _SUMMARY_SCHEMA:
        raise ValueError(
            f"summary.schema_version must be {_SUMMARY_SCHEMA!r}, "
            f"got {summary['schema_version']!r}."
        )
    if summary["status"] != "converging_candidate_complete":
        raise ValueError("summary.status must be 'converging_candidate_complete'.")
    if summary["objective_contract_id"] != _OBJECTIVE_CONTRACT_ID:
        raise ValueError("summary uses the wrong Stage-2 objective contract.")
    authority = _mapping(summary["objective_authority"], "summary.objective_authority")
    if dict(authority) != _OBJECTIVE_AUTHORITY:
        raise ValueError("summary.objective_authority does not equal revision-7 authority.")
    _model_identity(summary["model_identity"], "summary.model_identity")
    if _finite(summary["slot_hz"], "summary.slot_hz") <= 0:
        raise ValueError("summary.slot_hz must be positive.")
    if summary["artifact_contract"] != list(_RUN_FILES):
        raise ValueError("summary artifact contract must name the exact six canonical files.")
    artifacts = _mapping(summary["artifacts"], "summary.artifacts")
    if set(artifacts) != set(_SUMMARY_HASHED_FILES):
        raise ValueError("summary artifacts must hash history, S21, and qubit admittance.")
    for name in _SUMMARY_HASHED_FILES:
        _sha256(artifacts[name], f"summary.artifacts.{name}")

    q2d_spec = _mapping(summary["q2d_spec"], "summary.q2d_spec")
    _require_keys(q2d_spec, ("artifact_id", "artifact_sha256"), "summary.q2d_spec")
    _sha256(q2d_spec["artifact_sha256"], "summary.q2d_spec.artifact_sha256")
    response_match = _mapping(summary["response_match"], "summary.response_match")
    _require_keys(
        response_match,
        ("q2d_artifact_id", "q2d_artifact_sha256"),
        "summary.response_match",
    )
    if response_match["q2d_artifact_id"] != q2d_spec["artifact_id"]:
        raise ValueError("summary Q2D artifact id disagrees with response-match provenance.")
    if response_match["q2d_artifact_sha256"] != q2d_spec["artifact_sha256"]:
        raise ValueError("summary Q2D artifact SHA disagrees with response-match provenance.")

    cma = _mapping(summary["cma"], "summary.cma")
    _require_keys(
        cma,
        (
            "evaluations",
            "valid_evaluations",
            "rejected_evaluations",
            "configuration",
        ),
        "summary.cma",
    )
    configuration = _mapping(cma["configuration"], "summary.cma.configuration")
    expected_configuration_fields = {
        "algorithm",
        "initial_mean",
        "seed",
        "sigma",
        "popsize",
        "maxiter",
        "maxfevals",
        "ftol",
        "xtol",
    }
    if set(configuration) != expected_configuration_fields:
        raise ValueError("summary.cma.configuration fields do not match the V1 contract.")
    if configuration["algorithm"] != "bounded_cma_es_only":
        raise ValueError("summary CMA algorithm must be bounded_cma_es_only.")
    for key in ("seed", "popsize", "maxiter", "maxfevals"):
        value = configuration[key]
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise ValueError(f"summary.cma.configuration.{key} must be a non-negative integer.")
    if configuration["popsize"] < 2 or configuration["maxiter"] < 1:
        raise ValueError("summary CMA population and iteration budget are invalid.")
    if configuration["maxfevals"] < configuration["popsize"]:
        raise ValueError("summary CMA evaluation budget must cover one population.")
    for key in ("sigma", "ftol", "xtol"):
        if _finite(configuration[key], f"summary.cma.configuration.{key}") <= 0:
            raise ValueError(f"summary.cma.configuration.{key} must be positive.")
    initial_mean = _mapping(
        configuration["initial_mean"], "summary.cma.configuration.initial_mean"
    )
    if set(initial_mean) != set(_CANDIDATE_KEYS):
        raise ValueError("summary CMA initial mean must contain the physical candidate coordinates.")
    bounds = _mapping(summary["bounds"], "summary.bounds")
    if set(bounds) != set(_CANDIDATE_KEYS):
        raise ValueError("summary bounds must contain the physical candidate coordinates.")
    normalized_bounds: dict[str, tuple[float, float]] = {}
    for key in _CANDIDATE_KEYS:
        interval = bounds[key]
        if not isinstance(interval, list) or len(interval) != 2:
            raise ValueError(f"summary.bounds.{key} must be a two-value array.")
        lower = _finite(interval[0], f"summary.bounds.{key}[0]")
        upper = _finite(interval[1], f"summary.bounds.{key}[1]")
        if not 0 <= lower < upper:
            raise ValueError(f"summary.bounds.{key} must satisfy 0 <= lower < upper.")
        normalized_bounds[key] = (lower, upper)
        initial_value = _finite(initial_mean[key], f"summary CMA initial mean {key}")
        if initial_value <= 0 or not lower <= initial_value <= upper:
            raise ValueError(f"summary CMA initial mean {key} is outside its bounds.")

    candidate = _mapping(summary["best_candidate"], "summary.best_candidate")
    _require_keys(candidate, _CANDIDATE_KEYS, "summary.best_candidate")
    for key in _CANDIDATE_KEYS:
        value = _finite(candidate[key], f"summary.best_candidate.{key}")
        if value <= 0 or not normalized_bounds[key][0] <= value <= normalized_bounds[key][1]:
            raise ValueError(f"summary.best_candidate.{key} must be positive and within bounds.")

    metrics = _mapping(summary["best_metrics"], "summary.best_metrics")
    _require_keys(
        metrics,
        (
            "fr_eff_q_feedline_downfolded_qrp_on_ext_on_hz",
            "fp_eff_q_feedline_downfolded_qrp_on_ext_on_hz",
            "J_rp_eff_q_feedline_downfolded_coherent_hz",
            "notch_rp_on_hz",
            "kappa_sum_qrp_on_ext_on_hz",
            "eta_r_qrp_on",
            "eta_p_qrp_on",
            "effective_diagonal_frequency_extraction",
            "effective_exchange_extraction",
            "notch_authority",
            "linewidth_pole_scope",
            "primary_linewidth_extraction",
        ),
        "summary.best_metrics",
    )
    for key in (
        "fr_eff_q_feedline_downfolded_qrp_on_ext_on_hz",
        "fp_eff_q_feedline_downfolded_qrp_on_ext_on_hz",
        "J_rp_eff_q_feedline_downfolded_coherent_hz",
        "notch_rp_on_hz",
        "kappa_sum_qrp_on_ext_on_hz",
        "eta_r_qrp_on",
        "eta_p_qrp_on",
    ):
        _finite(metrics[key], f"summary.best_metrics.{key}")
    expected_metric_authority = {
        "effective_diagonal_frequency_extraction": "q_feedline_downfolded_rp_complex_operator",
        "effective_exchange_extraction": "q_feedline_downfolded_rp_complex_midpoint_residue",
        "notch_authority": "rp_on",
        "linewidth_pole_scope": "qrp_three",
        "primary_linewidth_extraction": "L_C",
    }
    for key, expected in expected_metric_authority.items():
        if metrics[key] != expected:
            raise ValueError(f"summary.best_metrics.{key} must be {expected!r}.")
    if not math.isclose(
        float(metrics["eta_r_qrp_on"]) + float(metrics["eta_p_qrp_on"]),
        1.0,
        rel_tol=1e-9,
        abs_tol=1e-9,
    ):
        raise ValueError("summary linewidth participations must sum to one.")

    objective = _mapping(summary["best_objective"], "summary.best_objective")
    _require_keys(objective, ("cost", "target_gates", "target_gates_pass"), "best_objective")
    reported_cost = _finite(objective["cost"], "summary.best_objective.cost")
    if reported_cost < 0:
        raise ValueError("summary.best_objective.cost must be non-negative.")
    if not isinstance(objective["target_gates_pass"], bool):
        raise ValueError("summary.best_objective.target_gates_pass must be boolean.")
    slot_hz = float(summary["slot_hz"])
    eta_r = float(metrics["eta_r_qrp_on"])
    eta_p = float(metrics["eta_p_qrp_on"])
    residuals = (
        (float(metrics["fr_eff_q_feedline_downfolded_qrp_on_ext_on_hz"]) - slot_hz)
        / 0.5e6,
        (float(metrics["fp_eff_q_feedline_downfolded_qrp_on_ext_on_hz"]) - slot_hz)
        / 0.5e6,
        (float(metrics["notch_rp_on_hz"]) - 4.5e9) / 10e6,
        (float(metrics["J_rp_eff_q_feedline_downfolded_coherent_hz"]) - 5e6) / 2e6,
        (float(metrics["kappa_sum_qrp_on_ext_on_hz"]) - 20e6) / 1e6,
        (min(eta_r, eta_p) - 0.5) / 0.2,
    )
    computed_cost = sum(value * value for value in residuals)
    if not math.isclose(reported_cost, computed_cost, rel_tol=1e-12, abs_tol=1e-9):
        raise ValueError("summary.best_objective.cost disagrees with revision-7 residuals.")
    gates = _mapping(objective["target_gates"], "summary.best_objective.target_gates")
    expected_gates = {
        "readout_effective_diagonal_within_tolerance": (
            abs(float(metrics["fr_eff_q_feedline_downfolded_qrp_on_ext_on_hz"]) - slot_hz)
            <= 0.5e6
        ),
        "filter_effective_diagonal_within_tolerance": (
            abs(float(metrics["fp_eff_q_feedline_downfolded_qrp_on_ext_on_hz"]) - slot_hz)
            <= 0.5e6
        ),
        "linewidth_participation": 0.3 <= eta_r <= 0.7 and 0.3 <= eta_p <= 0.7,
    }
    if dict(gates) != expected_gates:
        raise ValueError("summary.best_objective.target_gates disagree with revision-7 gates.")
    if objective["target_gates_pass"] != all(expected_gates.values()):
        raise ValueError("summary.best_objective.target_gates_pass is inconsistent.")
    return summary


def _load_linear_quantities(path: Path) -> dict[str, Any]:
    quantities = dict(_mapping(_load_json(path, "linear quantities"), "linear quantities"))
    _require_keys(
        quantities,
        (
            "schema_version",
            "source_summary_sha256",
            "objective_contract_id",
            "objective_authority",
            "coordinate_foundation",
            "anchored_oscillator_representation",
            "fully_hybridized_closed_normal_mode_spectrum",
            "matched_open_port_poles",
            "model_identity",
        ),
        "linear quantities",
    )
    if quantities["schema_version"] != _LINEAR_QUANTITIES_SCHEMA:
        raise ValueError(
            f"linear quantities schema must be {_LINEAR_QUANTITIES_SCHEMA!r}, "
            f"got {quantities['schema_version']!r}."
        )
    if quantities["objective_contract_id"] != _OBJECTIVE_CONTRACT_ID:
        raise ValueError("linear quantities use the wrong objective contract.")
    authority = _mapping(
        quantities["objective_authority"],
        "linear objective authority",
    )
    if dict(authority) != _OBJECTIVE_AUTHORITY:
        raise ValueError("linear quantities do not carry revision-7 objective authority.")
    _sha256(
        quantities["source_summary_sha256"],
        "linear quantities source_summary_sha256",
    )
    _model_identity(quantities["model_identity"], "linear quantities model identity")
    anchored = _mapping(
        quantities["anchored_oscillator_representation"],
        "linear quantities anchored oscillator representation",
    )
    _require_keys(
        anchored,
        (
            "coupling_state",
            "boundary",
            "coordinate_basis",
            "representation",
            "coordinate_order",
            "coordinate_rotation",
            "normalization",
            "impedance_ohm",
            "h_diagonal_frequency_hz",
            "h_number_conserving_coupling_hz",
            "pairing_diagonal_hz",
            "pairing_coupling_hz",
        ),
        "linear quantities anchored oscillator representation",
    )
    if anchored["coordinate_basis"] != "reduced_physically_anchored_flux_charge_coordinates":
        raise ValueError("linear quantities declare the wrong anchored coordinate basis.")
    if (
        anchored["coupling_state"] != "qrp_on"
        or anchored["boundary"] != "closed_conservative_block"
    ):
        raise ValueError("anchored oscillator quantities must declare QRP-on closed boundary.")
    if anchored["representation"] != "anchored_bare_coordinate_oscillator":
        raise ValueError("linear quantities declare the wrong oscillator representation.")
    if anchored["coordinate_rotation"] != "none":
        raise ValueError("anchored oscillator quantities must not rotate coordinates.")
    if anchored["normalization"] != "Z_i_equals_sqrt_C_inverse_ii_over_K_ii":
        raise ValueError("anchored oscillator quantities declare the wrong normalization.")
    for group_name, keys in (
        ("impedance_ohm", ("q", "r", "p")),
        ("h_diagonal_frequency_hz", ("q", "r", "p")),
        ("h_number_conserving_coupling_hz", ("qr", "qp", "rp")),
        ("pairing_diagonal_hz", ("q", "r", "p")),
        ("pairing_coupling_hz", ("qr", "qp", "rp")),
    ):
        group = _mapping(anchored[group_name], f"anchored.{group_name}")
        _require_keys(group, keys, f"anchored.{group_name}")
        for key in keys:
            _finite(group[key], f"anchored.{group_name}.{key}")
    normal_modes = _mapping(
        quantities["fully_hybridized_closed_normal_mode_spectrum"],
        "linear quantities normal modes",
    )
    _require_keys(
        normal_modes,
        (
            "spectrum",
            "coupling_state",
            "boundary",
            "construction",
            "identity_assignment",
            "display_order",
            "frequencies_hz",
            "structural_free_mode_count",
        ),
        "linear quantities normal modes",
    )
    if normal_modes["spectrum"] != "fully_hybridized_closed_normal_modes":
        raise ValueError("linear quantities declare the wrong normal-mode spectrum.")
    if normal_modes["coupling_state"] != "qrp_on" or normal_modes["boundary"] != "closed":
        raise ValueError("closed normal-mode spectrum must declare QRP-on closed boundary.")
    if (
        normal_modes["construction"]
        != "generalized_eigenproblem_K_u_equals_omega2_C_u"
        or normal_modes["identity_assignment"] != "none"
        or normal_modes["display_order"] != "ascending_frequency_only"
    ):
        raise ValueError(
            "closed normal modes must be the frequency-sorted generalized-eigenproblem "
            "spectrum without subsystem identity assignment."
        )
    if not isinstance(normal_modes["frequencies_hz"], list) or not normal_modes["frequencies_hz"]:
        raise ValueError("linear quantities normal-mode frequencies must be non-empty.")
    for index, frequency in enumerate(normal_modes["frequencies_hz"]):
        if _finite(frequency, f"normal_modes.frequencies_hz[{index}]") <= 0:
            raise ValueError("normal-mode frequencies must be positive.")
    open_poles = _mapping(
        quantities["matched_open_port_poles"],
        "linear quantities matched-open port poles",
    )
    _require_keys(
        open_poles,
        (
            "response_class",
            "coupling_state",
            "external_port_state",
            "basis_claim",
            "identity_assignment",
            "frequencies_hz",
            "linewidths_hz",
            "passivity_roundoff_tolerance_hz",
            "qrp_identity_assigned",
        ),
        "linear quantities matched-open port poles",
    )
    if open_poles["response_class"] != "matched_open_port_response":
        raise ValueError("linear quantities declare the wrong open-response class.")
    if (
        open_poles["coupling_state"] != "qrp_on"
        or open_poles["external_port_state"] != "matched_open"
    ):
        raise ValueError("matched-open poles must declare QRP-on, external-port-on response.")
    if open_poles["basis_claim"] != "none":
        raise ValueError("matched-open poles must not claim a Hamiltonian basis.")
    if open_poles["identity_assignment"] != "global_normalized_stored_energy_overlap":
        raise ValueError(
            "Stage-2 matched-open poles must use global normalized stored-energy identity continuation."
        )
    frequencies = open_poles["frequencies_hz"]
    linewidths = open_poles["linewidths_hz"]
    passivity_tolerance_hz = _finite(
        open_poles["passivity_roundoff_tolerance_hz"],
        "matched_open.passivity_roundoff_tolerance_hz",
    )
    if passivity_tolerance_hz < 0:
        raise ValueError("matched-open passivity tolerance must be non-negative.")
    if not isinstance(frequencies, list) or not frequencies:
        raise ValueError("matched-open pole frequencies must be non-empty.")
    if not isinstance(linewidths, list) or len(linewidths) != len(frequencies):
        raise ValueError("matched-open pole frequencies and linewidths must align.")
    for index, (frequency, linewidth) in enumerate(zip(frequencies, linewidths, strict=True)):
        record = _mapping(frequency, f"matched_open.frequencies_hz[{index}]")
        _require_keys(record, ("real", "imag"), f"matched_open.frequencies_hz[{index}]")
        real_frequency = _finite(record["real"], f"matched_open frequency {index} real")
        imaginary_frequency = _finite(record["imag"], f"matched_open frequency {index} imag")
        linewidth_hz = _finite(linewidth, f"matched_open linewidth {index}")
        if (
            real_frequency <= 0
            or imaginary_frequency > passivity_tolerance_hz
            or linewidth_hz < 0
        ):
            raise ValueError("matched-open poles must be positive-frequency and passive.")
        if not math.isclose(
            linewidth_hz,
            max(-2 * imaginary_frequency, 0.0),
            rel_tol=1e-10,
            abs_tol=1e-6,
        ):
            raise ValueError("matched-open pole linewidth disagrees with -2 Im(f_pole).")
    assigned = _mapping(open_poles["qrp_identity_assigned"], "matched_open.qrp_identity_assigned")
    _require_keys(assigned, ("q", "r", "p"), "matched_open.qrp_identity_assigned")
    matched_indices: set[int] = set()
    for identity in ("q", "r", "p"):
        record = _mapping(assigned[identity], f"matched_open assigned {identity}")
        _require_keys(
            record,
            ("display_index", "frequency_hz", "linewidth_hz"),
            f"matched_open assigned {identity}",
        )
        display_index = record["display_index"]
        if isinstance(display_index, bool) or not isinstance(display_index, int):
            raise ValueError(
                f"matched_open assigned {identity} display_index must be an integer."
            )
        if not 1 <= display_index <= len(frequencies):
            raise ValueError(
                f"matched_open assigned {identity} display_index is out of range."
            )
        pole_index = display_index - 1
        frequency = _mapping(record["frequency_hz"], f"matched_open assigned {identity} frequency")
        _require_keys(frequency, ("real", "imag"), f"matched_open assigned {identity} frequency")
        assigned_real = _finite(frequency["real"], f"matched_open assigned {identity} real")
        assigned_imag = _finite(frequency["imag"], f"matched_open assigned {identity} imag")
        assigned_linewidth = _finite(
            record["linewidth_hz"], f"matched_open assigned {identity} linewidth"
        )
        reported_frequency = _mapping(
            frequencies[pole_index],
            f"matched_open.frequencies_hz[{pole_index}]",
        )
        if not (
            math.isclose(
                float(reported_frequency["real"]),
                assigned_real,
                rel_tol=1e-12,
                abs_tol=1e-6,
            )
            and math.isclose(
                float(reported_frequency["imag"]),
                assigned_imag,
                rel_tol=1e-12,
                abs_tol=1e-6,
            )
            and math.isclose(
                float(linewidths[pole_index]),
                assigned_linewidth,
                rel_tol=1e-12,
                abs_tol=1e-6,
            )
        ):
            raise ValueError(
                f"matched-open {identity} assignment disagrees with its display_index."
            )
        if pole_index in matched_indices:
            raise ValueError("q/r/p identity assignment must select three distinct reported poles.")
        matched_indices.add(pole_index)
    return quantities


def _load_qubit_receipt(path: Path) -> dict[str, Any]:
    receipt = dict(_mapping(_load_json(path, "qubit receipt"), "qubit receipt"))
    fields = (
        "schema_version",
        "source_summary_sha256",
        "qubit_admittance_csv_sha256",
        "objective_contract_id",
        "objective_authority",
        "model_identity",
    )
    if set(receipt) != set(fields):
        raise ValueError(f"qubit receipt must contain exactly {list(fields)}.")
    if receipt["schema_version"] != _QUBIT_RECEIPT_SCHEMA:
        raise ValueError(
            f"qubit receipt schema must be {_QUBIT_RECEIPT_SCHEMA!r}, "
            f"got {receipt['schema_version']!r}."
        )
    _sha256(receipt["source_summary_sha256"], "qubit receipt source_summary_sha256")
    _sha256(
        receipt["qubit_admittance_csv_sha256"],
        "qubit receipt qubit_admittance_csv_sha256",
    )
    if receipt["objective_contract_id"] != _OBJECTIVE_CONTRACT_ID:
        raise ValueError("qubit receipt uses the wrong objective contract.")
    authority = _mapping(receipt["objective_authority"], "qubit receipt authority")
    if dict(authority) != _OBJECTIVE_AUTHORITY:
        raise ValueError("qubit receipt does not carry revision-7 objective authority.")
    _model_identity(receipt["model_identity"], "qubit receipt model identity")
    return receipt


def _load_history(path: Path, summary: Mapping[str, Any]) -> tuple[list[float], list[float]]:
    history = _load_json(path, "history")
    if not isinstance(history, list) or not history:
        raise ValueError("history must be a non-empty JSON array.")
    costs: list[float] = []
    for index, raw_record in enumerate(history, start=1):
        record = _mapping(raw_record, f"history[{index - 1}]")
        _require_keys(record, ("evaluation", "cost", "candidate"), f"history[{index - 1}]")
        if record["evaluation"] != index:
            raise ValueError("history evaluation numbers must be contiguous and one-based.")
        candidate = _mapping(record["candidate"], f"history[{index - 1}].candidate")
        _require_keys(candidate, _CANDIDATE_KEYS, f"history[{index - 1}].candidate")
        for key in _CANDIDATE_KEYS:
            _finite(candidate[key], f"history[{index - 1}].candidate.{key}")
        if record["cost"] is None:
            if not isinstance(record.get("rejection"), str) or not record["rejection"].strip():
                raise ValueError(f"history[{index - 1}] rejected row needs a reason.")
        else:
            cost = _finite(record["cost"], f"history[{index - 1}].cost")
            if cost < 0:
                raise ValueError(f"history[{index - 1}].cost must be non-negative.")
            costs.append(cost)
    cma = _mapping(summary["cma"], "summary.cma")
    if len(history) != cma.get("evaluations"):
        raise ValueError("history length does not match summary.cma.evaluations.")
    if len(costs) != cma.get("valid_evaluations"):
        raise ValueError("valid history count does not match summary.cma.valid_evaluations.")
    if len(history) - len(costs) != cma.get("rejected_evaluations"):
        raise ValueError("rejected history count does not match summary.cma.rejected_evaluations.")
    best = np.minimum.accumulate(np.asarray(costs, dtype=float))
    return list(range(1, len(costs) + 1)), best.tolist()


def _load_numeric_csv(
    path: Path,
    expected_columns: Sequence[str],
    label: str,
    nullable_columns: frozenset[str] = frozenset(),
) -> dict[str, np.ndarray]:
    if not path.is_file():
        raise FileNotFoundError(f"Missing {label}: {path}")
    values = {column: [] for column in expected_columns}
    with path.open(newline="", encoding="utf-8") as stream:
        reader = csv.DictReader(stream)
        if tuple(reader.fieldnames or ()) != tuple(expected_columns):
            raise ValueError(
                f"{label} columns must be exactly {list(expected_columns)}, "
                f"got {reader.fieldnames}."
            )
        for row_index, row in enumerate(reader, start=2):
            for column in expected_columns:
                raw = (row[column] or "").strip()
                if not raw and column in nullable_columns:
                    number = math.nan
                else:
                    try:
                        number = float(raw)
                    except ValueError as error:
                        raise ValueError(
                            f"{label} row {row_index} {column} is not numeric."
                        ) from error
                if not math.isfinite(number) and not (
                    column in nullable_columns and math.isnan(number)
                ):
                    raise ValueError(f"{label} row {row_index} {column} must be finite.")
                values[column].append(number)
    if len(values[expected_columns[0]]) < 2:
        raise ValueError(f"{label} must contain at least two rows.")
    arrays = {key: np.asarray(value, dtype=float) for key, value in values.items()}
    frequency = arrays["frequency_hz"]
    if np.any(frequency <= 0) or np.any(np.diff(frequency) <= 0):
        raise ValueError(f"{label} frequency_hz must be positive and strictly increasing.")
    return arrays


def _load_s21(path: Path) -> dict[str, np.ndarray]:
    data = _load_numeric_csv(path, _S21_COLUMNS, "S21 CSV")
    return {
        "frequency_hz": data["frequency_hz"],
        **{
            name: data[f"{name}_real"] + 1j * data[f"{name}_imag"]
            for name in ("direct", "exact", "hb")
        },
    }


def _vector_fit_direct_s21(s21: Mapping[str, np.ndarray]) -> dict[str, Any]:
    frequency_hz = s21["frequency_hz"]
    direct = s21["direct"]
    result = fit_complex_s21_vector(
        frequency_hz,
        direct.real,
        -direct.imag,
        n_resonators=2,
        bg_poles=2,
        max_iterations=200,
        min_q=0.0,
        restrict_to_input_span=True,
    )
    if result.get("status") != "success":
        raise ValueError(f"Direct-S21 Vector Fitting failed: {result.get('reason')}")
    diagnostics = _mapping(result["fit_diagnostics"], "Vector-Fit diagnostics")
    if diagnostics.get("converged") is not True:
        raise ValueError("Direct-S21 Vector Fitting did not converge.")
    poles = [
        pole
        for pole in result["rational_model"]["poles"]
        if pole["classification"] == "resonance"
    ]
    if len(poles) != 2:
        raise ValueError(f"Direct-S21 Vector Fitting must resolve two visible poles; got {len(poles)}.")
    poles.sort(key=lambda pole: float(pole["fr_hz"]))
    model = result["model_trace"]
    model_frequency_hz = np.asarray(model["frequency_hz"], dtype=float)
    if not np.array_equal(model_frequency_hz, frequency_hz):
        raise ValueError("Vector-Fit model frequency grid disagrees with canonical S21.")
    model_s21 = np.asarray(model["s21_real"], dtype=float) - 1j * np.asarray(
        model["s21_imag"], dtype=float
    )
    residual = model_s21 - direct
    rms_error = float(np.sqrt(np.mean(np.abs(residual) ** 2)))
    max_abs_error = float(np.max(np.abs(residual)))
    metrics = _mapping(result["metrics"], "Vector-Fit metrics")
    if not (
        math.isclose(rms_error, float(metrics["rms_error"]), rel_tol=1e-12, abs_tol=1e-15)
        and math.isclose(
            max_abs_error,
            float(metrics["max_abs_error"]),
            rel_tol=1e-12,
            abs_tol=1e-15,
        )
    ):
        raise ValueError("Vector-Fit residual disagrees after the declared phasor translation.")
    return {
        "model_s21": model_s21,
        "residual_s21": residual,
        "poles": poles,
        "rms_error": rms_error,
        "max_abs_error": max_abs_error,
        "fit_settings": result["fit_settings"],
        "sampling": result["sampling"],
        "fit_diagnostics": diagnostics,
    }


def _constant(values: np.ndarray, label: str) -> float:
    reference = float(values[0])
    if not np.allclose(values, reference, rtol=1e-12, atol=max(abs(reference), 1.0) * 1e-15):
        raise ValueError(f"qubit CSV {label} must be constant across the sweep.")
    return reference


def _load_qubit(path: Path) -> tuple[dict[str, np.ndarray], dict[str, Any]]:
    data = _load_numeric_csv(
        path,
        _QUBIT_COLUMNS,
        "qubit admittance CSV",
        frozenset({"hb_t1_s", "direct_t1_s"}),
    )
    c_q_eff_f = _constant(data["c_q_eff_f"], "c_q_eff_f")
    alpha = _constant(data["alpha"], "alpha")
    beta = _constant(data["beta"], "beta")
    if c_q_eff_f <= 0:
        raise ValueError("qubit CSV c_q_eff_f must be positive.")
    if np.any(data["kron_condition_number"] <= 0):
        raise ValueError("qubit CSV kron_condition_number must be positive.")
    if np.any(data["hb_direct_abs_y_residual_s"] < 0):
        raise ValueError("qubit CSV hb_direct_abs_y_residual_s must be non-negative.")

    hb_y = data["hb_y_eff_real_s"] + 1j * data["hb_y_eff_imag_s"]
    direct_y = data["direct_y_eff_real_s"] + 1j * data["direct_y_eff_imag_s"]
    computed_residual = np.abs(hb_y - direct_y)
    if not np.allclose(
        computed_residual,
        data["hb_direct_abs_y_residual_s"],
        rtol=1e-8,
        atol=1e-18,
    ):
        raise ValueError("qubit CSV HB/direct admittance residual is inconsistent.")

    nonpositive: dict[str, int] = {}
    nan_t1: dict[str, int] = {}
    for prefix in ("hb", "direct"):
        real_y = data[f"{prefix}_y_eff_real_s"]
        t1 = data[f"{prefix}_t1_s"]
        invalid_nan = np.isnan(t1) & (real_y > 0)
        if np.any(invalid_nan):
            raise ValueError(f"qubit CSV {prefix}_t1_s may be NaN only where Re(Y)<=0.")
        if np.any(np.isfinite(t1) & (t1 <= 0)):
            raise ValueError(f"qubit CSV finite {prefix}_t1_s values must be positive.")
        if np.any((real_y <= 0) & np.isfinite(t1)):
            raise ValueError(f"qubit CSV {prefix}_t1_s must be NaN where Re(Y)<=0.")
        nonpositive[prefix] = int(np.count_nonzero(real_y <= 0))
        nan_t1[prefix] = int(np.count_nonzero(np.isnan(t1)))

    return data, {
        "c_q_eff_f": c_q_eff_f,
        "alpha": alpha,
        "beta": beta,
        "hb_nonpositive_count": nonpositive["hb"],
        "direct_nonpositive_count": nonpositive["direct"],
        "hb_nan_t1_count": nan_t1["hb"],
        "direct_nan_t1_count": nan_t1["direct"],
    }


def _render_media(
    path: Path,
    summary: Mapping[str, Any],
    s21: Mapping[str, np.ndarray],
    qubit: Mapping[str, np.ndarray],
    vector_fit: Mapping[str, Any],
) -> None:
    figure = make_subplots(
        rows=3,
        cols=1,
        specs=[[{}], [{}], [{"secondary_y": True}]],
        subplot_titles=(
            "Stage-2 Equivalent-Circuit S21",
            "Complex S21 residuals relative to Direct C/K (same colors as S21)",
            "Weighted qubit: |Re(YQ,eff)| and local-Cq Purcell T1; solid=HB, dashed=Direct, "
            "x=ReY<=0 (full supplied sweep)",
        ),
        vertical_spacing=0.10,
    )
    frequency_ghz = s21["frequency_hz"] / 1e9
    styles = {
        "direct": ("Direct C/K", "#1f77b4", "solid"),
        "exact": ("Exact-12", "#ff7f0e", "dash"),
        "hb": ("HB solver", "#2a9d8f", "dot"),
        "vector_fit": ("VF of Direct S21", "#7c3aed", "dashdot"),
    }
    for key, (label, color, dash) in styles.items():
        trace = vector_fit["model_s21"] if key == "vector_fit" else s21[key]
        figure.add_trace(
            go.Scatter(
                x=frequency_ghz,
                y=np.abs(trace),
                mode="lines",
                name=label,
                line={"color": color, "dash": dash, "width": 2.5},
            ),
            row=1,
            col=1,
        )
    slot_ghz = float(summary["slot_hz"]) / 1e9
    figure.add_vline(
        x=slot_ghz,
        line={"color": "#6b7280", "dash": "dash", "width": 1.5},
        row=1,
        col=1,
    )
    for key, label, color in (
        ("exact", "|Exact-12 - Direct|", "#ff7f0e"),
        ("hb", "|HB - Direct|", "#2a9d8f"),
        ("vector_fit", "|VF - Direct|", "#7c3aed"),
    ):
        residual = (
            vector_fit["residual_s21"]
            if key == "vector_fit"
            else s21[key] - s21["direct"]
        )
        figure.add_trace(
            go.Scatter(
                x=frequency_ghz,
                y=np.abs(residual),
                mode="lines",
                name=label,
                line={"color": color, "width": 2},
                showlegend=False,
            ),
            row=2,
            col=1,
        )

    qubit_frequency_ghz = qubit["frequency_hz"] / 1e9
    for prefix, label, color, dash in (
        ("hb", "HB Re(YQ,eff)", "#d62728", "solid"),
        ("direct", "Direct Re(YQ,eff)", "#d62728", "dash"),
    ):
        real_y = qubit[f"{prefix}_y_eff_real_s"]
        figure.add_trace(
            go.Scatter(
                x=qubit_frequency_ghz,
                y=np.abs(real_y),
                mode="lines",
                name=label,
                line={"color": color, "dash": dash, "width": 2.3},
                showlegend=False,
            ),
            row=3,
            col=1,
            secondary_y=False,
        )
        nonpositive = real_y <= 0
        if np.any(nonpositive):
            figure.add_trace(
                go.Scatter(
                    x=qubit_frequency_ghz[nonpositive],
                    y=np.abs(real_y[nonpositive]),
                    mode="markers",
                    name=f"{prefix} Re(Y)<=0",
                    marker={"color": color, "symbol": "x", "size": 9},
                    showlegend=False,
                ),
                row=3,
                col=1,
                secondary_y=False,
            )
    for prefix, label, color, dash in (
        ("hb", "HB linearized T1 estimate", "#1f77b4", "solid"),
        ("direct", "Direct linearized T1 estimate", "#1f77b4", "dash"),
    ):
        figure.add_trace(
            go.Scatter(
                x=qubit_frequency_ghz,
                y=qubit[f"{prefix}_t1_s"] * 1e6,
                mode="lines",
                name=label,
                line={"color": color, "dash": dash, "width": 2.3},
                showlegend=False,
            ),
            row=3,
            col=1,
            secondary_y=True,
        )

    figure.update_yaxes(title_text="|S21|", row=1, col=1)
    figure.update_yaxes(title_text="Complex |ΔS21|", type="log", row=2, col=1)
    figure.update_yaxes(title_text="|Re(YQ,eff)| (S)", type="log", row=3, col=1, secondary_y=False)
    figure.update_yaxes(
        title_text="linearized local-Cq Purcell T1 estimate (µs)",
        type="log",
        row=3,
        col=1,
        secondary_y=True,
    )
    figure.update_xaxes(title_text="Frequency (GHz)", row=3, col=1)
    figure.update_layout(
        width=1800,
        height=1000,
        margin={"l": 100, "r": 110, "t": 65, "b": 70},
        template="plotly_white",
        font={"family": "DejaVu Sans, Arial, sans-serif", "size": 16},
        legend={"orientation": "h", "yanchor": "bottom", "y": 1.01, "x": 0.0},
    )
    figure.write_image(path, format="png", width=1800, height=1000, scale=1)


def _gate(value: bool) -> str:
    return "PASS" if value else "FAIL"


def _table(
    block_id: str,
    role: str,
    title: str,
    columns: Sequence[str],
    rows: Sequence[Sequence[str]],
    widths: Sequence[float],
    source_ids: Sequence[str],
) -> dict[str, Any]:
    return {
        "type": "table",
        "id": block_id,
        "role": role,
        "title": title,
        "columns": list(columns),
        "rows": [list(row) for row in rows],
        "column_widths": list(widths),
        "source_ids": list(source_ids),
    }


def _q2d_values(summary: Mapping[str, Any]) -> dict[str, float]:
    q2d = _mapping(summary["q2d_spec"], "summary.q2d_spec")
    single_l = _finite(q2d["single_l_per_m_h"], "q2d single L")
    single_c = _finite(q2d["single_c_per_m_f"], "q2d single C")
    l_matrix = [_finite(value, "q2d L matrix") for value in q2d["l_matrix_per_m_h"]]
    c_matrix = [_finite(value, "q2d C matrix") for value in q2d["c_matrix_per_m_f"]]
    if len(l_matrix) != 4 or len(c_matrix) != 4 or single_l <= 0 or single_c <= 0:
        raise ValueError(
            "summary Q2D L/C data must contain positive single values and 2x2 matrices."
        )
    l_diag = (l_matrix[0] + l_matrix[3]) / 2
    l_mutual = (l_matrix[1] + l_matrix[2]) / 2
    c_diag = (c_matrix[0] + c_matrix[3]) / 2
    c_mutual = abs((c_matrix[1] + c_matrix[2]) / 2)
    if min(l_diag - l_mutual, c_diag - c_mutual, l_mutual, c_mutual) <= 0:
        raise ValueError("summary Q2D pair matrices are not valid for even/odd extraction.")
    velocity = 1 / math.sqrt(single_l * single_c)
    return {
        "z0": math.sqrt(single_l / single_c),
        "velocity": velocity,
        "epsilon_eff": (299_792_458.0 / velocity) ** 2,
        "zc": math.sqrt(l_diag / c_diag),
        "zm": math.sqrt(l_mutual / c_mutual),
        "ze": math.sqrt((l_diag + l_mutual) / (c_diag - c_mutual)),
        "zo": math.sqrt((l_diag - l_mutual) / (c_diag + c_mutual)),
    }


def _manifest(
    run_directory: Path,
    qubit_csv: Path,
    qubit_receipt_path: Path,
    linear_quantities_path: Path,
    media_path: Path,
    summary: Mapping[str, Any],
    linear_quantities: Mapping[str, Any],
    history_x: Sequence[float],
    history_y: Sequence[float],
    qubit: Mapping[str, np.ndarray],
    qubit_meta: Mapping[str, Any],
    vector_fit: Mapping[str, Any],
) -> dict[str, Any]:
    summary_path = run_directory / "summary.json"
    history_path = run_directory / "history.json"
    s21_path = run_directory / "s21.csv"
    source_paths = {
        "summary": summary_path,
        "history": history_path,
        "s21": s21_path,
        "qubit": qubit_csv,
        "qubit_receipt": qubit_receipt_path,
        "linear_quantities": linear_quantities_path,
    }
    sources = [
        {
            "id": source_id,
            "path": str(path),
            "locator": (
                f"run-directory/{path.name}"
            ),
            "sha256": file_sha256(path),
            "visibility": "private",
        }
        for source_id, path in source_paths.items()
    ]
    slot_hz = float(summary["slot_hz"])
    metrics = _mapping(summary["best_metrics"], "summary.best_metrics")
    objective = _mapping(summary["best_objective"], "summary.best_objective")
    gates = _mapping(objective["target_gates"], "summary.best_objective.target_gates")
    candidate = _mapping(summary["best_candidate"], "summary.best_candidate")
    resolved = _mapping(summary["best_resolved_lc"], "summary.best_resolved_lc")
    q2d = _mapping(summary["q2d_spec"], "summary.q2d_spec")
    geometry = _mapping(q2d["geometry_um"], "summary.q2d_spec.geometry_um")
    solver = _mapping(q2d["solver"], "summary.q2d_spec.solver")
    q2d_readback = _q2d_values(summary)
    l_matrix = np.asarray(q2d["l_matrix_per_m_h"], dtype=float).reshape(2, 2) * 1e9
    c_matrix = np.asarray(q2d["c_matrix_per_m_f"], dtype=float).reshape(2, 2) * 1e12

    anchored = _mapping(
        linear_quantities["anchored_oscillator_representation"],
        "linear quantities anchored oscillator representation",
    )
    anchored_frequency = _mapping(
        anchored["h_diagonal_frequency_hz"], "anchored h diagonal frequency"
    )
    anchored_coupling = _mapping(
        anchored["h_number_conserving_coupling_hz"], "anchored h coupling"
    )
    anchored_pairing = _mapping(anchored["pairing_coupling_hz"], "anchored pairing")
    metric_rows = [
        (
            "Stage-2 objective operator — QRP,on; ext,on",
            "q+feedline-downfolded r diagonal root",
            f"{float(metrics['fr_eff_q_feedline_downfolded_qrp_on_ext_on_hz']) / 1e9:.9f} GHz",
            "—",
            f"{slot_hz / 1e9:.9f} GHz",
            _gate(bool(gates["readout_effective_diagonal_within_tolerance"])),
        ),
        (
            "Stage-2 objective operator — QRP,on; ext,on",
            "q+feedline-downfolded p diagonal root",
            f"{float(metrics['fp_eff_q_feedline_downfolded_qrp_on_ext_on_hz']) / 1e9:.9f} GHz",
            "—",
            f"{slot_hz / 1e9:.9f} GHz",
            _gate(bool(gates["filter_effective_diagonal_within_tolerance"])),
        ),
        (
            "Stage-2 objective operator — QRP,on; ext,on",
            "q+feedline-downfolded coherent |Jrp|",
            f"{float(metrics['J_rp_eff_q_feedline_downfolded_coherent_hz']) / 1e6:.6f} MHz",
            "—",
            "5.000000 MHz",
            "—",
        ),
        (
            "Intrinsic RP,on response",
            "Intrinsic notch",
            f"{float(metrics['notch_rp_on_hz']) / 1e9:.9f} GHz",
            "—",
            "4.500000000 GHz",
            "—",
        ),
        (
            "Matched-open QRP,on; ext,on response",
            "Total QRP linewidth",
            f"{float(metrics['kappa_sum_qrp_on_ext_on_hz']) / 1e6:.6f} MHz",
            "—",
            "20.000000 MHz",
            "—",
        ),
        (
            "Matched-open QRP,on; ext,on response",
            "r/p linewidth participation",
            f"{100 * float(metrics['eta_r_qrp_on']):.4f}% / "
            f"{100 * float(metrics['eta_p_qrp_on']):.4f}%",
            "—",
            "30-70% hard gate",
            _gate(bool(gates["linewidth_participation"])),
        ),
    ]
    impedance = _mapping(anchored["impedance_ohm"], "anchored impedance")
    pairing_diagonal = _mapping(anchored["pairing_diagonal_hz"], "anchored pairing diagonal")
    for coordinate in ("q", "r", "p"):
        metric_rows.append(
            (
                "Anchored-bare QRP,on — closed conservative block",
                f"{coordinate}: h_{coordinate}{coordinate}/2π",
                f"{float(anchored_frequency[coordinate]) / 1e9:.9f} GHz",
                f"{float(pairing_diagonal[coordinate]) / 1e6:.6g} MHz",
                f"Z{coordinate} = {float(impedance[coordinate]):.9g} Ω",
                "same reduced anchored coordinate; no rotation",
            )
        )
    for pair in ("qr", "qp", "rp"):
        metric_rows.append(
            (
                "Anchored-bare QRP,on — closed conservative block",
                f"{pair}: h_ij/2π",
                f"{float(anchored_coupling[pair]) / 1e6:.9g} MHz",
                f"Δ_ij/2π = {float(anchored_pairing[pair]) / 1e6:.9g} MHz",
                "report-only",
                "same normalization as anchored diagonals",
            )
        )
    normal_modes = _mapping(
        linear_quantities["fully_hybridized_closed_normal_mode_spectrum"],
        "linear quantities normal modes",
    )
    for index, frequency in enumerate(normal_modes["frequencies_hz"], start=1):
        metric_rows.append(
            (
                "Fully hybridized QRP,on — closed spectrum",
                f"normal mode {index}",
                f"{float(frequency) / 1e9:.9f} GHz",
                "—",
                "closed boundary",
                "frequency-sorted; no subsystem identity assigned",
            )
        )
    open_poles = _mapping(
        linear_quantities["matched_open_port_poles"],
        "linear quantities matched-open port poles",
    )
    assigned_open_poles = _mapping(
        open_poles["qrp_identity_assigned"],
        "linear quantities matched-open q/r/p assignment",
    )
    identity_by_pole: dict[int, str] = {}
    for identity in ("q", "r", "p"):
        assigned_record = _mapping(assigned_open_poles[identity], f"assigned {identity} pole")
        identity_by_pole[int(assigned_record["display_index"]) - 1] = identity
    for index, (frequency, linewidth) in enumerate(
        zip(open_poles["frequencies_hz"], open_poles["linewidths_hz"], strict=True),
        start=1,
    ):
        metric_rows.append(
            (
                "Matched-open QRP,on; ext,on response",
                f"complex pole {index}",
                f"Re = {float(frequency['real']) / 1e9:.9f} GHz",
                f"Im = {float(frequency['imag']) / 1e6:.9g} MHz",
                f"κ/2π = {float(linewidth) / 1e6:.9g} MHz",
                (
                    f"{identity_by_pole[index - 1]}-like by stored-energy continuation; "
                    "not a Hamiltonian basis"
                    if index - 1 in identity_by_pole
                    else "unassigned response pole; not a Hamiltonian basis"
                ),
            )
        )
    assigned_rp = sorted(
        (
            (
                float(assigned_open_poles[identity]["frequency_hz"]["real"]),
                float(assigned_open_poles[identity]["linewidth_hz"]),
            )
            for identity in ("r", "p")
        ),
        key=lambda item: item[0],
    )
    for index, (pole, matched_open) in enumerate(
        zip(vector_fit["poles"], assigned_rp, strict=True),
        start=1,
    ):
        frequency_hz = float(pole["fr_hz"])
        linewidth_hz = float(pole["bandwidth_hz"])
        residue = complex(
            float(pole["residue_real_rad_per_s"]),
            float(pole["residue_imag_rad_per_s"]),
        )
        metric_rows.append(
            (
                "Scalar VF of Direct S21 — matched-open response cross-check",
                f"visible VF pole {index}",
                f"Re = {frequency_hz / 1e9:.9f} GHz",
                f"Im = {-linewidth_hz / 2e6:.9g} MHz",
                f"κ/2π = {linewidth_hz / 1e6:.9g} MHz",
                f"Δf(rank) = {(frequency_hz - matched_open[0]):.6g} Hz; "
                f"Δκ(rank) = {(linewidth_hz - matched_open[1]):.6g} Hz; "
                f"R_VF = ({residue.real:.6g}{residue.imag:+.6g}j) rad/s",
            )
        )
    parameter_rows = [
        ("Readout open-side length", f"{float(candidate['lr_open_m']) * 1e6:.6f} µm"),
        ("Readout short-side length", f"{float(candidate['lr_short_m']) * 1e6:.6f} µm"),
        ("MTL coupling length", f"{float(candidate['lc_m']) * 1e6:.6f} µm"),
        ("Filter open-side length", f"{float(candidate['lp_open_m']) * 1e6:.6f} µm"),
        ("Filter short-side length", f"{float(candidate['lp_short_m']) * 1e6:.6f} µm"),
        ("IDC finger length", f"{float(candidate['u_IDC']):.6f} µm"),
    ]
    for key, unit, scale in (
        ("Cr_f", "fF", 1e15),
        ("Lr_h", "nH", 1e9),
        ("Cp_f", "fF", 1e15),
        ("Lp_h", "nH", 1e9),
        ("Cn_f", "fF", 1e15),
        ("Ln_h", "nH", 1e9),
    ):
        parameter_rows.append(
            (f"Resolved {key}", f"{_finite(resolved[key], key) * scale:.9g} {unit}")
        )
    parameter_rows.extend(
        (
            ("Effective qubit capacitance Cq,eff", f"{qubit_meta['c_q_eff_f'] * 1e15:.9g} fF"),
            ("Floating-qubit weight alpha", f"{qubit_meta['alpha']:.12g}"),
            ("Floating-qubit weight beta", f"{qubit_meta['beta']:.12g}"),
        )
    )

    fixed_rows = (
        ("Cross-section", "continuous upper ground; no opening"),
        (
            "Geometry",
            "w = {w:g} µm, s = {s:g} µm, d = {d:g} µm, h = {h:g} µm, t = {t:g} µm".format(
                w=float(geometry["w"]),
                s=float(geometry["s"]),
                d=float(geometry["d"]),
                h=float(geometry["h"]),
                t=float(geometry["metal_thickness"]),
            ),
        ),
        (
            "Single-line RLGC",
            f"R' = G' = 0; L' = {float(q2d['single_l_per_m_h']) * 1e9:.6f} nH/m; "
            f"C' = {float(q2d['single_c_per_m_f']) * 1e12:.6f} pF/m",
        ),
        (
            "Single-line propagation",
            f"Z0 = {q2d_readback['z0']:.6f} Ω; v = {q2d_readback['velocity']:.7g} m/s; "
            f"εeff = {q2d_readback['epsilon_eff']:.6f}",
        ),
        ("MTL L' matrix", np.array2string(l_matrix, precision=6) + " nH/m"),
        ("MTL C' matrix", np.array2string(c_matrix, precision=6) + " pF/m"),
        (
            "MTL impedance",
            f"Zc = {q2d_readback['zc']:.6f} Ω; Zm = {q2d_readback['zm']:.6f} Ω; "
            f"Ze/Zo = {q2d_readback['ze']:.6f}/{q2d_readback['zo']:.6f} Ω",
        ),
        (
            "Q2D convention",
            f"{float(solver['adaptive_frequency_hz']) / 1e9:g} GHz adaptive; lossless; "
            f"{q2d['coupling_orientation'].replace('_', '-')} MTL coupling",
        ),
    )
    qubit_frequency = qubit["frequency_hz"]
    cma_configuration = _mapping(
        _mapping(summary["cma"], "summary.cma")["configuration"],
        "summary.cma.configuration",
    )
    cma_initial_mean = _mapping(
        cma_configuration["initial_mean"],
        "summary.cma.configuration.initial_mean",
    )
    model_identity = _model_identity(summary["model_identity"], "summary.model_identity")
    objective_authority = _mapping(
        summary["objective_authority"], "summary.objective_authority"
    )
    provenance_rows = (
        ("Run status", str(summary["status"])),
        ("Objective contract", str(summary["objective_contract_id"])),
        (
            "Target authority",
            f"revision {objective_authority['target_revision']}; "
            f"SHA {objective_authority['target_contract_sha256']}",
        ),
        ("CircuitPlan SHA", model_identity["circuit_plan_sha256"]),
        ("Capacitance SHA", model_identity["capacitance_sha256"]),
        ("Inverse-inductance SHA", model_identity["inverse_inductance_sha256"]),
        ("Port-selector SHA", model_identity["selector_sha256"]),
        ("Q2D artifact", str(q2d["artifact_id"])),
        ("Q2D artifact SHA", str(q2d["artifact_sha256"])),
        ("Q2D cases", f"{q2d['single_case_id']} / {q2d['pair_case_id']}"),
        ("Q2D solver", f"AEDT {solver['aedt_version']}; PyAEDT {solver['pyaedt_version']}"),
        (
            "PTC observation",
            "P3/P4 at qL/qR were compiler-lowered; evidence-authorized PTC then removed "
            "their termination branches before Y reduction",
        ),
        (
            "HB weighted transform / Kron",
            "Vsum = alpha VL + beta VR; Vq = VL - VR; Iq = beta IL - alpha IR; "
            "Kron eliminates P1, P2, and sum (internal nodes were already HB-eliminated)",
        ),
        (
            "Direct C/K closure reduction",
            "same weighted q coordinate; nodal Schur elimination removes sum, r, p, f1, fc, f2",
        ),
        (
            "Qubit sweep",
            f"{len(qubit_frequency)} samples; {qubit_frequency[0] / 1e9:.6f}-"
            f"{qubit_frequency[-1] / 1e9:.6f} GHz",
        ),
        (
            "Kron conditioning",
            f"max κ = {float(np.max(qubit['kron_condition_number'])):.6g}",
        ),
        (
            "HB/direct Y closure",
            f"max |ΔY| = {float(np.max(qubit['hb_direct_abs_y_residual_s'])):.6g} S",
        ),
        (
            "Nonpositive Re(Y) / NaN T1",
            f"HB {qubit_meta['hb_nonpositive_count']} / {qubit_meta['hb_nan_t1_count']}; "
            f"Direct {qubit_meta['direct_nonpositive_count']} / "
            f"{qubit_meta['direct_nan_t1_count']}",
        ),
        (
            "CMA-ES result",
            f"best cost = {float(objective['cost']):.9g}; "
            f"gates pass = {objective['target_gates_pass']}",
        ),
        (
            "CMA-ES configuration",
            f"seed={cma_configuration['seed']}; sigma={float(cma_configuration['sigma']):.9g}; "
            f"population={cma_configuration['popsize']}; maxiter={cma_configuration['maxiter']}; "
            f"maxfevals={cma_configuration['maxfevals']}; "
            f"ftol={float(cma_configuration['ftol']):.9g}; "
            f"xtol={float(cma_configuration['xtol']):.9g}",
        ),
        (
            "CMA initial mean",
            ", ".join(
                f"{name}={float(cma_initial_mean[name]):.9g}"
                for name in _CANDIDATE_KEYS
            ),
        ),
        (
            "Scalar VF convention",
            "source = Direct C/K S21; project exp(-iωt) trace conjugated into "
            "VF s=+i2πf convention; reconstructed trace conjugated back",
        ),
        (
            "Scalar VF settings",
            "2 complex pole pairs; 2 real background poles; constant fitted; "
            "proportional term fixed zero; 200 relocation iterations maximum",
        ),
        (
            "Scalar VF reconstruction",
            f"complex RMS = {float(vector_fit['rms_error']):.9g}; "
            f"max |residual| = {float(vector_fit['max_abs_error']):.9g}; "
            "diagnostic only—refinement/continuation promotion gates not evaluated",
        ),
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "report_id": f"d3-stage2-{slot_hz / 1e9:.2f}ghz-candidate-review".replace(".", "p"),
        "title": f"D3 Stage 2 — {slot_hz / 1e9:.2f} GHz Candidate Review",
        "producer_id": "d3-stage2-candidate-review-report.v1",
        "publication_visibility": "private",
        "source_files": sources,
        "blocks": [
            {
                "type": "media",
                "id": "response-review",
                "title": "S21 closure and weighted-qubit Purcell response",
                "path": str(media_path),
                "sha256": file_sha256(media_path),
                "source_ids": ["s21", "qubit", "qubit_receipt", "summary"],
            },
            {
                "type": "optimization_history",
                "id": "objective-history",
                "title": (
                    "Objective records (initial seed + CMA-ES): "
                    f"{summary['cma']['evaluations']} evaluations, "
                    f"{summary['cma']['valid_evaluations']} valid, "
                    f"{summary['cma']['rejected_evaluations']} rejected"
                ),
                "x_label": "Valid candidate evaluation",
                "y_label": "Best objective cost",
                "x_values": list(history_x),
                "y_values": list(history_y),
                "y_scale": "log" if all(value > 0 for value in history_y) else "linear",
                "source_ids": ["history", "summary"],
            },
            _table(
                "metrics",
                "metrics",
                "Revision-7 operands, three system-frequency views, and scalar VF poles",
                (
                    "Layer / authority",
                    "Quantity",
                    "Frequency / value",
                    "Im or pairing",
                    "Target / linewidth",
                    "Gate / meaning",
                ),
                metric_rows,
                (1.25, 1.25, 1.05, 1.05, 1.15, 1.65),
                ("summary", "linear_quantities", "s21"),
            ),
            _table(
                "parameters",
                "parameters",
                "Physical candidate, resolved equivalent values, and qubit transform",
                ("Parameter", "Value"),
                parameter_rows,
                (1.5, 2.5),
                ("summary", "qubit", "qubit_receipt"),
            ),
            _table(
                "fixed-specifications",
                "fixed_specifications",
                "Fixed CPW / MTL specification",
                ("Fixed CPW / MTL Spec", "Value used by this Stage-2 run"),
                fixed_rows,
                (1.0, 3.2),
                ("summary",),
            ),
            _table(
                "provenance",
                "provenance",
                "Source identity, PTC reduction, and numerical closure",
                ("Evidence", "Value"),
                provenance_rows,
                (1.0, 3.2),
                (
                    "summary",
                    "history",
                    "s21",
                    "qubit",
                    "qubit_receipt",
                    "linear_quantities",
                ),
            ),
        ],
    }


def build_report(
    run_directory: Path,
    output_directory: Path,
) -> Path:
    """Build and publish one D3 Stage-2 candidate review report."""

    run_directory = run_directory.resolve()
    output_directory = output_directory.resolve()
    if not run_directory.is_dir():
        raise FileNotFoundError(f"Run directory does not exist: {run_directory}")
    entries = {path.name for path in run_directory.iterdir()}
    if entries != set(_RUN_FILES):
        raise ValueError(
            "Run directory must contain exactly the six canonical Stage-2 files; "
            f"got {sorted(entries)}."
        )
    summary_path = run_directory / "summary.json"
    linear_quantities_path = run_directory / "linear-quantities.json"
    qubit_csv = run_directory / "qubit-admittance.csv"
    qubit_receipt_path = run_directory / "qubit-admittance-receipt.json"

    summary = _load_summary(summary_path)
    summary_hashes = _mapping(summary["artifacts"], "summary.artifacts")
    for filename in _SUMMARY_HASHED_FILES:
        if summary_hashes[filename] != file_sha256(run_directory / filename):
            raise ValueError(f"{filename} does not match its summary SHA-256.")
    linear_quantities = _load_linear_quantities(linear_quantities_path)
    qubit_receipt = _load_qubit_receipt(qubit_receipt_path)
    summary_sha256 = file_sha256(summary_path)
    if linear_quantities["source_summary_sha256"] != summary_sha256:
        raise ValueError(
            "linear quantities were not produced from this Stage-2 summary."
        )
    if qubit_receipt["source_summary_sha256"] != summary_sha256:
        raise ValueError("qubit admittance was not produced from this Stage-2 summary.")
    if qubit_receipt["qubit_admittance_csv_sha256"] != file_sha256(qubit_csv):
        raise ValueError("qubit admittance CSV does not match its canonical receipt.")

    summary_identity = _model_identity(summary["model_identity"], "summary.model_identity")
    linear_identity = _model_identity(
        linear_quantities["model_identity"],
        "linear quantities model identity",
    )
    qubit_identity = _model_identity(
        qubit_receipt["model_identity"],
        "qubit receipt model identity",
    )
    if linear_identity != summary_identity:
        raise ValueError("linear quantities do not match the Stage-2 winning model identity.")
    if qubit_identity != summary_identity:
        raise ValueError("qubit admittance does not match the Stage-2 winning model identity.")
    for artifact, label in (
        (linear_quantities, "linear quantities"),
        (qubit_receipt, "qubit receipt"),
    ):
        if artifact["objective_contract_id"] != summary["objective_contract_id"]:
            raise ValueError(f"{label} objective contract disagrees with the summary.")
        if dict(artifact["objective_authority"]) != dict(summary["objective_authority"]):
            raise ValueError(f"{label} objective authority disagrees with the summary.")
    history_x, history_y = _load_history(run_directory / "history.json", summary)
    s21 = _load_s21(run_directory / "s21.csv")
    vector_fit = _vector_fit_direct_s21(s21)
    qubit, qubit_meta = _load_qubit(qubit_csv)
    output_directory.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(
        prefix=f".{output_directory.name}.media-", dir=output_directory.parent
    ) as temporary:
        media_path = Path(temporary) / "d3-stage2-response-review.png"
        _render_media(media_path, summary, s21, qubit, vector_fit)
        manifest = _manifest(
            run_directory,
            qubit_csv,
            qubit_receipt_path,
            linear_quantities_path,
            media_path,
            summary,
            linear_quantities,
            history_x,
            history_y,
            qubit,
            qubit_meta,
            vector_fit,
        )
        return render_simulation_report(manifest, output_directory)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-directory", type=Path, required=True)
    parser.add_argument("--output-directory", type=Path, required=True)
    arguments = parser.parse_args()
    register = build_report(
        arguments.run_directory,
        arguments.output_directory,
    )
    print(register)


if __name__ == "__main__":
    main()
