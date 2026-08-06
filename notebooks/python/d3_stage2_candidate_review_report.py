"""Render one canonical-artifact-backed D3 Stage-2 candidate review report.

The producer strictly loads one canonical Stage-2 run directory and verifies
that its linear quantities and weighted floating-qubit admittance share the
same summary, objective authority, and model identity. It owns the D3-specific
three-panel review figure and table wording; the shared Human-reviewable report
composer owns publication, layout, and the evidence register.
"""

from __future__ import annotations

import argparse
import cmath
import csv
import hashlib
import json
import math
import tempfile
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import numpy as np
import plotly.graph_objects as go
from human_reviewable_simulation_report import (
    REPORT_RENDER_CONFIG,
    SCHEMA_VERSION,
    file_sha256,
    render_simulation_report,
)
from plotly.subplots import make_subplots
from superconducting_circuits_analysis.application.analysis.fitting.s_parameters import (
    fit_complex_s21_vector,
)

_SUMMARY_SCHEMA = "d3-stage2-physical-candidate-summary.v2"
_LINEAR_QUANTITIES_SCHEMA = "d3-stage2-linear-quantity-review.v4"
_QUBIT_RECEIPT_SCHEMA = "d3-stage2-qubit-admittance-receipt.v1"
_OBJECTIVE_CONTRACT_ID = "d3-stage2-stage3-full-qrp-objective.v2"
_TARGET_SLOTS_HZ = (5.9e9, 6.0e9, 6.1e9, 6.2e9)
_OBJECTIVE_AUTHORITY = {
    "approval_status": "human_approved",
    "target_id": "d3-same-face-resonators-opposite-face-qubit-j5-k20-gap8",
    "target_revision": 9,
    "target_contract_sha256": ("86eb2da65329df9059efeddccc9f479d1ef116e0eed4a0de0554cf8f02353b9d"),
    "notch_authority": "rp_on",
    "effective_diagonal_frequency_extraction": ("q_feedline_downfolded_rp_complex_operator"),
    "effective_exchange_extraction": ("q_feedline_downfolded_rp_complex_midpoint_residue"),
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
    if isinstance(value, bool) or not isinstance(value, int | float):
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


def _json_values_equal(left: Any, right: Any) -> bool:
    if type(left) is bool or type(right) is bool:
        return type(left) is bool and type(right) is bool and left is right
    if type(left) in (int, float) or type(right) in (int, float):
        return type(left) in (int, float) and type(right) in (int, float) and left == right
    if isinstance(left, Mapping) or isinstance(right, Mapping):
        if not isinstance(left, Mapping) or not isinstance(right, Mapping):
            return False
        if not all(type(key) is str for key in (*left.keys(), *right.keys())):
            return False
        if set(left) != set(right):
            return False
        return all(_json_values_equal(left[key], right[key]) for key in left)
    if isinstance(left, list) or isinstance(right, list):
        return (
            isinstance(left, list)
            and isinstance(right, list)
            and len(left) == len(right)
            and all(_json_values_equal(a, b) for a, b in zip(left, right, strict=True))
        )
    if type(left) is str or type(right) is str:
        return type(left) is str and type(right) is str and left == right
    if left is None or right is None:
        return left is None and right is None
    return False


def _complex_value(value: Any, label: str) -> complex:
    record = _mapping(value, label)
    if set(record) != {"real", "imag"}:
        raise ValueError(f"{label} must contain exactly real and imag.")
    return complex(
        _finite(record["real"], f"{label}.real"),
        _finite(record["imag"], f"{label}.imag"),
    )


def _close_complex(left: complex, right: complex, *, rel_tol: float = 1e-10) -> bool:
    return math.isclose(left.real, right.real, rel_tol=rel_tol, abs_tol=1e-9) and math.isclose(
        left.imag, right.imag, rel_tol=rel_tol, abs_tol=1e-9
    )


def _validate_effective_rp(value: Any, model_identity: Mapping[str, str]) -> dict[str, Any]:
    effective = dict(_mapping(value, "q+feedline-downfolded RP effective representation"))
    fields = {
        "contract_id",
        "coupling_state",
        "external_port_state",
        "retained_coordinates",
        "eliminated_coordinates",
        "coordinate_basis",
        "representation",
        "diagonal_root_extraction",
        "diagonal_roots",
        "residue_normalized_exchange",
        "determinant_closure",
        "gate_policy",
        "context_validation",
        "operator_diagnostics",
        "source_model_identity",
        "provenance",
    }
    if set(effective) != fields:
        raise ValueError("q+feedline-downfolded RP effective fields are incomplete.")
    expected = {
        "contract_id": "d3-q-feedline-downfolded-rp-effective-operator.v1",
        "coupling_state": "qrp_on",
        "external_port_state": "matched_open",
        "retained_coordinates": ["r", "p"],
        "eliminated_coordinates": ["q", "f1", "fc", "f2"],
        "coordinate_basis": "physically_anchored_rp_coordinates_no_retained_pair_rotation",
        "representation": "frequency_dependent_dynamic_effective_operator",
        "diagonal_root_extraction": ("principal_subsystem_matched_open_poles_in_declared_band"),
    }
    for name, expected_value in expected.items():
        if effective[name] != expected_value:
            raise ValueError(f"q+feedline-downfolded RP {name} is not the V1 authority.")
    if _model_identity(effective["source_model_identity"], "effective source identity") != dict(
        model_identity
    ):
        raise ValueError("q+feedline-downfolded RP source identity disagrees with the Run.")

    roots = _mapping(effective["diagonal_roots"], "effective diagonal roots")
    if set(roots) != {"r", "p"}:
        raise ValueError("effective diagonal roots must contain exactly r and p.")
    root_values: dict[str, complex] = {}
    gate = _mapping(effective["gate_policy"], "effective gate policy")
    gate_fields = {
        "maximum_elimination_condition_number",
        "maximum_relative_elimination_solve_residual",
        "maximum_relative_reciprocity_error",
        "maximum_relative_passivity_violation",
        "maximum_relative_root_residual",
        "maximum_root_growth_rate_hz",
        "minimum_normalized_residue_slope",
        "maximum_relative_coupling_spread",
        "maximum_relative_determinant_closure_error",
    }
    if set(gate) != gate_fields:
        raise ValueError("effective gate policy fields are incomplete.")
    gates = {name: _finite(gate[name], f"effective gate policy {name}") for name in gate_fields}
    if gates["maximum_elimination_condition_number"] < 1 or any(
        gates[name] < 0
        for name in gate_fields
        if name not in {"maximum_elimination_condition_number", "minimum_normalized_residue_slope"}
    ):
        raise ValueError("effective gate policy contains an invalid bound.")
    if gates["minimum_normalized_residue_slope"] <= 0:
        raise ValueError("effective minimum normalized residue slope must be positive.")

    operator_diagnostics = _mapping(
        effective["operator_diagnostics"], "effective operator diagnostics"
    )
    if set(operator_diagnostics) != {"readout", "midpoint", "filter"}:
        raise ValueError("effective operator diagnostics must contain exactly three samples.")
    diagnostic_fields = {
        "elimination_condition_number",
        "relative_elimination_solve_residual",
        "relative_derivative_solve_residual",
        "effective_reciprocity_error",
    }
    for sample_name in ("readout", "midpoint", "filter"):
        sample = _mapping(
            operator_diagnostics[sample_name], f"effective {sample_name} operator diagnostics"
        )
        if set(sample) != diagnostic_fields:
            raise ValueError(f"effective {sample_name} operator diagnostic fields are incomplete.")
        diagnostics = {
            name: _finite(sample[name], f"effective {sample_name} {name}")
            for name in diagnostic_fields
        }
        if any(value < 0 for value in diagnostics.values()):
            raise ValueError(f"effective {sample_name} operator diagnostics must be nonnegative.")
        if (
            diagnostics["elimination_condition_number"]
            > gates["maximum_elimination_condition_number"]
        ):
            raise ValueError(f"effective {sample_name} elimination conditioning exceeds its gate.")
        if (
            max(
                diagnostics["relative_elimination_solve_residual"],
                diagnostics["relative_derivative_solve_residual"],
            )
            > gates["maximum_relative_elimination_solve_residual"]
        ):
            raise ValueError(f"effective {sample_name} solve residual exceeds its gate.")
        if diagnostics["effective_reciprocity_error"] > gates["maximum_relative_reciprocity_error"]:
            raise ValueError(f"effective {sample_name} reciprocity error exceeds its gate.")

    for coordinate, subsystem in (
        ("r", ["r", "q", "f1", "fc", "f2"]),
        ("p", ["p", "q", "f1", "fc", "f2"]),
    ):
        root = _mapping(roots[coordinate], f"effective {coordinate} root")
        root_fields = {
            "coordinate",
            "complex_frequency_hz",
            "frequency_hz",
            "external_linewidth_hz",
            "frequency_band_hz",
            "principal_subsystem_coordinates",
            "principal_subsystem_pole_index",
            "relative_root_residual",
        }
        if set(root) != root_fields or root["coordinate"] != coordinate:
            raise ValueError(f"effective {coordinate} diagonal-root fields are incomplete.")
        complex_frequency = _complex_value(
            root["complex_frequency_hz"], f"effective {coordinate} complex root"
        )
        frequency_hz = _finite(root["frequency_hz"], f"effective {coordinate} frequency")
        linewidth_hz = _finite(root["external_linewidth_hz"], f"effective {coordinate} linewidth")
        if (
            frequency_hz <= 0
            or complex_frequency.real <= 0
            or complex_frequency.imag > gates["maximum_root_growth_rate_hz"]
        ):
            raise ValueError(f"effective {coordinate} diagonal root is not passive/positive.")
        if not math.isclose(frequency_hz, complex_frequency.real, rel_tol=1e-12, abs_tol=1e-6):
            raise ValueError(f"effective {coordinate} reported frequency disagrees with its root.")
        if not math.isclose(
            linewidth_hz,
            max(-2 * complex_frequency.imag, 0.0),
            rel_tol=1e-10,
            abs_tol=1e-6,
        ):
            raise ValueError(f"effective {coordinate} linewidth disagrees with -2 Im(root).")
        band = root["frequency_band_hz"]
        if (
            not isinstance(band, list)
            or len(band) != 2
            or not 0
            < _finite(band[0], f"effective {coordinate} band lower")
            <= complex_frequency.real
            <= _finite(band[1], f"effective {coordinate} band upper")
        ):
            raise ValueError(f"effective {coordinate} root is outside its declared band.")
        if root["principal_subsystem_coordinates"] != subsystem:
            raise ValueError(f"effective {coordinate} principal subsystem is incorrect.")
        pole_index = root["principal_subsystem_pole_index"]
        if isinstance(pole_index, bool) or not isinstance(pole_index, int) or pole_index < 1:
            raise ValueError(f"effective {coordinate} pole index must be positive.")
        root_residual = _finite(
            root["relative_root_residual"], f"effective {coordinate} root residual"
        )
        if not 0 <= root_residual <= gates["maximum_relative_root_residual"]:
            raise ValueError(f"effective {coordinate} root residual exceeds its gate.")
        root_values[coordinate] = complex_frequency

    exchange = _mapping(effective["residue_normalized_exchange"], "effective exchange")
    exchange_fields = {
        "midpoint_angular_frequency_rad_s",
        "residue_slopes",
        "residue_normalization",
        "square_root_branch",
        "coupling_samples_rad_s",
        "effective_exchange_rad_s",
        "coherent_exchange_hz",
        "total_exchange_hz",
        "dissipative_cross_coupling_hz",
        "maximum_pairwise_coupling_spread_rad_s",
        "relative_coupling_spread",
    }
    if set(exchange) != exchange_fields:
        raise ValueError("effective residue-normalized exchange fields are incomplete.")
    if exchange["square_root_branch"] != "principal_complex_square_root":
        raise ValueError("effective residue normalization must declare its principal branch.")
    midpoint = _complex_value(exchange["midpoint_angular_frequency_rad_s"], "effective midpoint")
    expected_midpoint = math.pi * (root_values["r"] + root_values["p"])
    if not _close_complex(midpoint, expected_midpoint):
        raise ValueError("effective midpoint disagrees with the two complex diagonal roots.")
    slopes = _mapping(exchange["residue_slopes"], "effective residue slopes")
    if set(slopes) != {"readout_s", "filter_s", "readout_normalized", "filter_normalized"}:
        raise ValueError("effective residue-slope fields are incomplete.")
    readout_slope = _complex_value(slopes["readout_s"], "effective readout residue slope")
    filter_slope = _complex_value(slopes["filter_s"], "effective filter residue slope")
    for name in ("readout_normalized", "filter_normalized"):
        normalized = _finite(slopes[name], f"effective {name}")
        if normalized < gates["minimum_normalized_residue_slope"]:
            raise ValueError(f"effective {name} is below its gate.")
    normalization = _complex_value(exchange["residue_normalization"], "effective normalization")
    if not _close_complex(normalization, cmath.sqrt(readout_slope * filter_slope)):
        raise ValueError(
            "effective residue normalization disagrees with the principal square root."
        )
    samples = _mapping(exchange["coupling_samples_rad_s"], "effective coupling samples")
    if set(samples) != {"readout", "midpoint", "filter"}:
        raise ValueError("effective coupling samples must contain readout, midpoint, and filter.")
    coupling_samples = {
        name: _complex_value(samples[name], f"effective {name} coupling sample") for name in samples
    }
    effective_exchange = _complex_value(exchange["effective_exchange_rad_s"], "effective exchange")
    if not _close_complex(effective_exchange, coupling_samples["midpoint"]):
        raise ValueError("effective exchange must equal the midpoint coupling sample.")
    coherent_hz = _finite(exchange["coherent_exchange_hz"], "effective coherent exchange")
    total_hz = _finite(exchange["total_exchange_hz"], "effective total exchange")
    dissipative_hz = _finite(
        exchange["dissipative_cross_coupling_hz"], "effective dissipative coupling"
    )
    if not (
        math.isclose(coherent_hz, abs(effective_exchange.real) / (2 * math.pi), rel_tol=1e-12)
        and math.isclose(total_hz, abs(effective_exchange) / (2 * math.pi), rel_tol=1e-12)
        and math.isclose(
            dissipative_hz, -2 * effective_exchange.imag / (2 * math.pi), rel_tol=1e-12
        )
    ):
        raise ValueError("effective exchange projections disagree with the complex exchange.")
    pairwise_spread = max(
        abs(left - right)
        for left in coupling_samples.values()
        for right in coupling_samples.values()
    )
    reported_spread = _finite(
        exchange["maximum_pairwise_coupling_spread_rad_s"], "effective coupling spread"
    )
    relative_spread = _finite(exchange["relative_coupling_spread"], "effective relative spread")
    exchange_magnitude = abs(effective_exchange)
    if exchange_magnitude <= 0:
        raise ValueError(
            "residue-normalized midpoint exchange magnitude must be positive "
            "for relative spread audit."
        )
    if not (
        math.isclose(reported_spread, pairwise_spread, rel_tol=1e-12, abs_tol=1e-6)
        and math.isclose(relative_spread, pairwise_spread / exchange_magnitude, rel_tol=1e-12)
        and relative_spread <= gates["maximum_relative_coupling_spread"]
    ):
        raise ValueError("effective coupling-spread diagnostics are inconsistent.")

    closure = _mapping(effective["determinant_closure"], "effective determinant closure")
    if set(closure) != {"schur_determinant", "effective_determinant", "relative_error"}:
        raise ValueError("effective determinant-closure fields are incomplete.")
    schur_determinant = _complex_value(closure["schur_determinant"], "Schur determinant")
    effective_determinant = _complex_value(
        closure["effective_determinant"], "effective determinant"
    )
    closure_error = _finite(closure["relative_error"], "determinant closure error")
    expected_error = abs(schur_determinant - effective_determinant) / max(
        abs(schur_determinant), abs(effective_determinant)
    )
    if not math.isclose(closure_error, expected_error, rel_tol=1e-10, abs_tol=1e-18) or (
        closure_error > gates["maximum_relative_determinant_closure_error"]
    ):
        raise ValueError("effective determinant closure disagrees with its gate.")

    context = _mapping(effective["context_validation"], "effective context validation")
    context_fields = {
        "capacitance_reciprocity_error",
        "stiffness_reciprocity_error",
        "conductance_reciprocity_error",
        "stiffness_relative_passivity_violation",
        "conductance_relative_passivity_violation",
    }
    if set(context) != context_fields:
        raise ValueError("effective context-validation fields are incomplete.")
    context_values = {name: _finite(context[name], f"effective context {name}") for name in context}
    if (
        any(value < 0 for value in context_values.values())
        or max(
            context_values["capacitance_reciprocity_error"],
            context_values["stiffness_reciprocity_error"],
            context_values["conductance_reciprocity_error"],
        )
        > gates["maximum_relative_reciprocity_error"]
        or max(
            context_values["stiffness_relative_passivity_violation"],
            context_values["conductance_relative_passivity_violation"],
        )
        > gates["maximum_relative_passivity_violation"]
    ):
        raise ValueError("effective context diagnostics exceed their gates.")

    provenance = _mapping(effective["provenance"], "effective provenance")
    provenance_fields = {
        "operator",
        "dynamic_stiffness",
        "retained_partition",
        "eliminated_partition",
        "frequency_rank_assignment",
        "capacitance_sha256",
        "inverse_inductance_sha256",
        "conductance_sha256",
    }
    if set(provenance) != provenance_fields or provenance != {
        **dict(provenance),
        "operator": "exact_open_dynamic_stiffness_schur",
        "dynamic_stiffness": "K-omega^2*C-i*omega*G",
        "retained_partition": ["r", "p"],
        "eliminated_partition": ["q", "f1", "fc", "f2"],
        "frequency_rank_assignment": "forbidden",
    }:
        raise ValueError("effective provenance does not retain the V1 operator convention.")
    for name in ("capacitance_sha256", "inverse_inductance_sha256", "conductance_sha256"):
        _sha256(provenance[name], f"effective provenance {name}")
    return effective


def _fixed_line_q2d_snapshot(response_match: Mapping[str, Any]) -> dict[str, Any]:
    identity = dict(
        _mapping(
            response_match["fixed_line_input_identity"],
            "summary.response_match.fixed_line_input_identity",
        )
    )
    identity_fields = {
        "contract_id",
        "q2d_artifact_id",
        "q2d_artifact_sha256",
        "q2d_topology_id",
        "q2d_geometry_um",
        "q2d_single_case_id",
        "q2d_pair_case_id",
        "q2d_solver",
        "q2d_loss_model",
        "q2d_authority",
        "section_length_m",
        "mtl_section_length_m",
        "readout_l_per_m_h",
        "readout_c_per_m_f",
        "filter_l_per_m_h",
        "filter_c_per_m_f",
        "l_matrix_per_m_h",
        "c_matrix_per_m_f",
        "coupling_orientation",
    }
    if set(identity) != identity_fields:
        raise ValueError("fixed-line identity fields do not match the normalized contract.")
    canonical = response_match["fixed_line_input_identity_canonical_json"]
    if not isinstance(canonical, str) or not canonical:
        raise ValueError("fixed-line canonical identity must be non-empty text.")
    try:
        decoded_identity = json.loads(canonical)
    except json.JSONDecodeError as error:
        raise ValueError("fixed-line canonical identity is not valid JSON.") from error
    if not _json_values_equal(decoded_identity, identity):
        raise ValueError("fixed-line canonical JSON disagrees elementwise with its identity.")
    computed_sha256 = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    if computed_sha256 != response_match["fixed_line_input_sha256"]:
        raise ValueError("fixed-line canonical JSON disagrees with its reported SHA-256.")
    if identity["contract_id"] != "d3-selected-continuous-ground-fixed-line.v2":
        raise ValueError("fixed-line identity uses the wrong contract.")

    geometry = dict(_mapping(identity["q2d_geometry_um"], "fixed-line Q2D geometry"))
    geometry_fields = {
        "w",
        "s",
        "d",
        "h",
        "upper_ground_clearance",
        "metal_thickness",
    }
    if set(geometry) != geometry_fields:
        raise ValueError("fixed-line Q2D geometry fields are incomplete.")
    normalized_geometry = {
        name: _finite(geometry[name], f"fixed-line geometry {name}") for name in geometry_fields
    }
    if any(normalized_geometry[name] <= 0 for name in geometry_fields - {"upper_ground_clearance"}):
        raise ValueError("fixed-line physical geometry values must be positive.")
    if normalized_geometry["upper_ground_clearance"] != 0:
        raise ValueError("continuous-upper-ground identity requires zero upper-ground clearance.")

    solver = dict(_mapping(identity["q2d_solver"], "fixed-line Q2D solver"))
    solver_fields = {
        "adaptive_frequency_hz",
        "aedt_version",
        "pyaedt_version",
    }
    if set(solver) != solver_fields:
        raise ValueError("fixed-line Q2D solver fields are incomplete.")
    normalized_solver = {
        "adaptive_frequency_hz": _finite(
            solver["adaptive_frequency_hz"], "fixed-line adaptive frequency"
        ),
        "aedt_version": solver["aedt_version"],
        "pyaedt_version": solver["pyaedt_version"],
    }
    if normalized_solver["adaptive_frequency_hz"] <= 0:
        raise ValueError("fixed-line adaptive frequency must be positive.")
    for name in ("aedt_version", "pyaedt_version"):
        if not isinstance(normalized_solver[name], str) or not normalized_solver[name].strip():
            raise ValueError(f"fixed-line {name} must be non-empty text.")

    authority = dict(_mapping(identity["q2d_authority"], "fixed-line Q2D authority"))
    authority_fields = {
        "payload_sha256",
        "single_result_id",
        "pair_result_id",
        "source_database_sha256",
        "material_profile_id",
        "material_profile_sha256",
        "material_authority_sha256",
        "single_evidence_sha256",
        "pair_evidence_sha256",
        "single_raw_sources_sha256",
        "pair_raw_sources_sha256",
        "basis",
        "orientation",
        "row_column_order",
        "l_matrix_unit",
        "c_matrix_unit",
        "data_class",
        "allowed_consumers",
        "publication_state",
        "promotion_eligible",
    }
    if set(authority) != authority_fields:
        raise ValueError("fixed-line Q2D authority fields are incomplete.")
    for name in (
        "payload_sha256",
        "single_result_id",
        "pair_result_id",
        "source_database_sha256",
        "material_profile_sha256",
        "material_authority_sha256",
        "single_evidence_sha256",
        "pair_evidence_sha256",
        "single_raw_sources_sha256",
        "pair_raw_sources_sha256",
    ):
        authority[name] = _sha256(authority[name], f"fixed-line authority {name}")
    for name in (
        "material_profile_id",
        "basis",
        "orientation",
        "row_column_order",
        "l_matrix_unit",
        "c_matrix_unit",
    ):
        if not isinstance(authority[name], str) or not authority[name].strip():
            raise ValueError(f"fixed-line authority {name} must be non-empty text.")
    consumers = authority["allowed_consumers"]
    if (
        not isinstance(consumers, list)
        or not consumers
        or any(not isinstance(value, str) or not value.strip() for value in consumers)
    ):
        raise ValueError("fixed-line authority allowed_consumers must be non-empty text.")
    if (
        authority["data_class"] != "project-internal"
        or authority["publication_state"] != "diagnostic"
        or authority["promotion_eligible"] is not False
    ):
        raise ValueError("fixed-line Q2D authority is not diagnostic project-internal evidence.")

    def matrix_rows(value: Any, label: str) -> list[list[float]]:
        if not isinstance(value, list) or len(value) != 2:
            raise ValueError(f"{label} must contain exactly two ordered rows.")
        rows: list[list[float]] = []
        for row_index, raw_row in enumerate(value):
            if not isinstance(raw_row, list) or len(raw_row) != 2:
                raise ValueError(f"{label}[{row_index}] must contain exactly two values.")
            rows.append(
                [
                    _finite(raw_value, f"{label}[{row_index}][{column_index}]")
                    for column_index, raw_value in enumerate(raw_row)
                ]
            )
        return rows

    l_matrix = matrix_rows(identity["l_matrix_per_m_h"], "fixed-line L matrix")
    c_matrix = matrix_rows(identity["c_matrix_per_m_f"], "fixed-line C matrix")
    readout_l = _finite(identity["readout_l_per_m_h"], "fixed-line readout L")
    readout_c = _finite(identity["readout_c_per_m_f"], "fixed-line readout C")
    filter_l = _finite(identity["filter_l_per_m_h"], "fixed-line filter L")
    filter_c = _finite(identity["filter_c_per_m_f"], "fixed-line filter C")
    if min(readout_l, readout_c, filter_l, filter_c) <= 0:
        raise ValueError("fixed-line single-line L/C values must be positive.")
    if readout_l != filter_l or readout_c != filter_c:
        raise ValueError("fixed-line identity must retain one artifact-owned single-line L/C pair.")
    section_length_m = _finite(identity["section_length_m"], "fixed-line CPW grid")
    mtl_section_length_m = _finite(identity["mtl_section_length_m"], "fixed-line MTL grid")
    if not 0 < section_length_m <= 50e-6 or not 0 < mtl_section_length_m <= 50e-6:
        raise ValueError("fixed-line CPW and MTL grids must each be positive and at most 50 um.")
    for name in ("q2d_artifact_id", "q2d_single_case_id", "q2d_pair_case_id"):
        if not isinstance(identity[name], str) or not identity[name].strip():
            raise ValueError(f"fixed-line {name} must be non-empty text.")
    _sha256(identity["q2d_artifact_sha256"], "fixed-line Q2D artifact SHA-256")
    if identity["q2d_topology_id"] != "continuous_upper_ground":
        raise ValueError("fixed-line Q2D topology must be continuous_upper_ground.")
    if identity["q2d_loss_model"] != "lossless_R_equals_G_equals_zero":
        raise ValueError("fixed-line Q2D loss model must be lossless.")
    if identity["coupling_orientation"] != "same_direction":
        raise ValueError("fixed-line Q2D coupling orientation must be same_direction.")

    return {
        "artifact_id": identity["q2d_artifact_id"],
        "artifact_sha256": identity["q2d_artifact_sha256"],
        "topology_id": identity["q2d_topology_id"],
        "single_case_id": identity["q2d_single_case_id"],
        "pair_case_id": identity["q2d_pair_case_id"],
        "geometry_um": normalized_geometry,
        "solver": normalized_solver,
        "loss_model": identity["q2d_loss_model"],
        "authority": authority,
        "single_l_per_m_h": readout_l,
        "single_c_per_m_f": readout_c,
        "l_matrix_per_m_h": [value for row in l_matrix for value in row],
        "c_matrix_per_m_f": [value for row in c_matrix for value in row],
        "coupling_orientation": identity["coupling_orientation"],
        "section_length_m": section_length_m,
        "mtl_section_length_m": mtl_section_length_m,
    }


def _validate_response_match_audit(
    response_match: Mapping[str, Any], q2d_spec: Mapping[str, Any]
) -> None:
    expected_response_match_fields = {
        "mapping_id",
        "mapping_sha256",
        "match_contract_id",
        "q2d_artifact_id",
        "q2d_artifact_sha256",
        "fixed_line_input_sha256",
        "fixed_line_input_identity",
        "fixed_line_input_identity_canonical_json",
        "topology_id",
        "match_evidence",
    }
    if set(response_match) != expected_response_match_fields:
        raise ValueError(
            "summary.response_match must contain the complete Length-to-LC audit record."
        )
    for field in ("mapping_sha256", "q2d_artifact_sha256", "fixed_line_input_sha256"):
        _sha256(response_match[field], f"summary.response_match.{field}")
    for field in ("mapping_id", "match_contract_id", "q2d_artifact_id", "topology_id"):
        if not isinstance(response_match[field], str) or not response_match[field].strip():
            raise ValueError(f"summary.response_match.{field} must be non-empty text.")
    expected_q2d_spec = _fixed_line_q2d_snapshot(response_match)
    if not _json_values_equal(q2d_spec, expected_q2d_spec):
        raise ValueError(
            "summary.q2d_spec disagrees elementwise with the artifact-derived fixed-line identity."
        )
    if response_match["q2d_artifact_id"] != expected_q2d_spec["artifact_id"]:
        raise ValueError("response-match artifact id disagrees with its fixed-line identity.")
    if response_match["q2d_artifact_sha256"] != expected_q2d_spec["artifact_sha256"]:
        raise ValueError("response-match artifact SHA disagrees with its fixed-line identity.")
    if response_match["topology_id"] != expected_q2d_spec["topology_id"]:
        raise ValueError("response-match topology disagrees with its fixed-line identity.")

    evidence = _mapping(
        response_match["match_evidence"],
        "summary.response_match.match_evidence",
    )
    if set(evidence) != {"reference_model", "readout", "filter", "bridge", "settings"}:
        raise ValueError("response-match evidence must contain the complete reference-model audit.")

    reference = _mapping(evidence["reference_model"], "response-match reference model")
    expected_reference = {
        "role": "physical_length_to_equivalent_lc_extraction_only",
        "final_stage2_hb_model": "resolved_lumped_equivalent_circuit",
        "topology": "two_grounded_head_open_tail_quarter_wave_resonators_with_mtl_window",
        "terminal_coordinates": ["readout_open_tail", "filter_open_tail"],
        "diagonal_match_state": "mtl_mutual_terms_disabled_diagonal_loading_preserved",
        "bridge_match_state": "full_mtl_mutual_terms_preserved",
        "internal_coordinate_elimination": "frequency_dependent_dynamic_schur_complement",
    }
    if set(reference) != {
        *expected_reference,
        "section_length_m",
        "mtl_section_length_m",
    }:
        raise ValueError("response-match reference-model fields are incomplete.")
    for field, expected in expected_reference.items():
        if reference[field] != expected:
            raise ValueError(f"response-match reference_model.{field} is not the V1 authority.")
    for name in ("section_length_m", "mtl_section_length_m"):
        section_length = _finite(reference[name], f"response-match {name}")
        if not 0 < section_length <= 50e-6:
            raise ValueError(f"D3 response-match {name} must be positive and at most 50 um.")
        if section_length != expected_q2d_spec[name]:
            raise ValueError(f"response-match {name} disagrees with its fixed-line identity.")

    parallel_fields = {
        "capacitance_f",
        "inductance_h",
        "angular_frequency_rad_s",
        "frequency_hz",
        "root_admittance_s",
        "admittance_derivative_s_per_rad_s",
        "derivative_step_rad_s",
    }
    for subsystem in ("readout", "filter"):
        record = _mapping(evidence[subsystem], f"response-match {subsystem}")
        if set(record) != parallel_fields:
            raise ValueError(f"response-match {subsystem} evidence is incomplete.")
        for field in (
            "capacitance_f",
            "inductance_h",
            "angular_frequency_rad_s",
            "frequency_hz",
            "derivative_step_rad_s",
        ):
            if _finite(record[field], f"response-match {subsystem}.{field}") <= 0:
                raise ValueError(f"response-match {subsystem}.{field} must be positive.")
        _complex_value(record["root_admittance_s"], f"response-match {subsystem} root Y")
        _complex_value(
            record["admittance_derivative_s_per_rad_s"],
            f"response-match {subsystem} dY/domega",
        )

    bridge = _mapping(evidence["bridge"], "response-match bridge")
    bridge_fields = {
        "capacitance_f",
        "inductance_h",
        "angular_frequency_rad_s",
        "frequency_hz",
        "root_transfer_impedance_ohm",
        "transfer_impedance_derivative_ohm_per_rad_s",
        "readout_admittance_s",
        "filter_admittance_s",
        "capacitance_imaginary_residual_f",
        "derivative_step_rad_s",
    }
    if set(bridge) != bridge_fields:
        raise ValueError("response-match bridge evidence is incomplete.")
    for field in (
        "capacitance_f",
        "inductance_h",
        "angular_frequency_rad_s",
        "frequency_hz",
        "derivative_step_rad_s",
    ):
        if _finite(bridge[field], f"response-match bridge.{field}") <= 0:
            raise ValueError(f"response-match bridge.{field} must be positive.")
    _finite(
        bridge["capacitance_imaginary_residual_f"],
        "response-match bridge capacitance residual",
    )
    for field in (
        "root_transfer_impedance_ohm",
        "transfer_impedance_derivative_ohm_per_rad_s",
        "readout_admittance_s",
        "filter_admittance_s",
    ):
        _complex_value(bridge[field], f"response-match bridge.{field}")

    settings = _mapping(evidence["settings"], "response-match settings")
    expected_settings = {
        "readout_root_bracket_hz",
        "filter_root_bracket_hz",
        "notch_root_bracket_hz",
        "parallel_derivative_step_rad_s",
        "bridge_derivative_step_rad_s",
        "bisection_absolute_tolerance_rad_s",
        "bisection_relative_tolerance",
        "bisection_max_iterations",
        "match_root_relative_tolerance",
        "derivative_relative_tolerance",
    }
    if set(settings) != expected_settings:
        raise ValueError("response-match settings are incomplete.")
    for field in ("readout_root_bracket_hz", "filter_root_bracket_hz", "notch_root_bracket_hz"):
        bracket = settings[field]
        if not isinstance(bracket, list) or len(bracket) != 2:
            raise ValueError(f"response-match {field} must be a two-value bracket.")
        lower = _finite(bracket[0], f"response-match {field}[0]")
        upper = _finite(bracket[1], f"response-match {field}[1]")
        if not 0 < lower < upper:
            raise ValueError(f"response-match {field} must be positive and increasing.")
    for field in (
        "parallel_derivative_step_rad_s",
        "bridge_derivative_step_rad_s",
        "bisection_absolute_tolerance_rad_s",
        "bisection_relative_tolerance",
        "match_root_relative_tolerance",
        "derivative_relative_tolerance",
    ):
        if _finite(settings[field], f"response-match {field}") <= 0:
            raise ValueError(f"response-match {field} must be positive.")
    iterations = settings["bisection_max_iterations"]
    if isinstance(iterations, bool) or not isinstance(iterations, int) or iterations < 1:
        raise ValueError("response-match bisection_max_iterations must be a positive integer.")
    if (
        not math.isclose(
            float(evidence["readout"]["derivative_step_rad_s"]),
            float(settings["parallel_derivative_step_rad_s"]),
            rel_tol=0.0,
            abs_tol=0.0,
        )
        or not math.isclose(
            float(evidence["filter"]["derivative_step_rad_s"]),
            float(settings["parallel_derivative_step_rad_s"]),
            rel_tol=0.0,
            abs_tol=0.0,
        )
        or not math.isclose(
            float(bridge["derivative_step_rad_s"]),
            float(settings["bridge_derivative_step_rad_s"]),
            rel_tol=0.0,
            abs_tol=0.0,
        )
    ):
        raise ValueError("response-match evidence derivative steps disagree with settings.")


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
        raise ValueError("summary.objective_authority does not equal revision-9 authority.")
    _model_identity(summary["model_identity"], "summary.model_identity")
    if _finite(summary["slot_hz"], "summary.slot_hz") not in _TARGET_SLOTS_HZ:
        raise ValueError(f"summary.slot_hz must be one of {_TARGET_SLOTS_HZ} Hz.")
    if summary["artifact_contract"] != list(_RUN_FILES):
        raise ValueError("summary artifact contract must name the exact six canonical files.")
    artifacts = _mapping(summary["artifacts"], "summary.artifacts")
    if set(artifacts) != set(_SUMMARY_HASHED_FILES):
        raise ValueError("summary artifacts must hash history, S21, and qubit admittance.")
    for name in _SUMMARY_HASHED_FILES:
        _sha256(artifacts[name], f"summary.artifacts.{name}")

    q2d_spec = _mapping(summary["q2d_spec"], "summary.q2d_spec")
    response_match = _mapping(summary["response_match"], "summary.response_match")
    _validate_response_match_audit(response_match, q2d_spec)

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
    initial_mean = _mapping(configuration["initial_mean"], "summary.cma.configuration.initial_mean")
    if set(initial_mean) != set(_CANDIDATE_KEYS):
        raise ValueError(
            "summary CMA initial mean must contain the physical candidate coordinates."
        )
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

    resolved = _mapping(summary["best_resolved_lc"], "summary.best_resolved_lc")
    expected_resolved_fields = {"Cr_f", "Lr_h", "Cp_f", "Lp_h", "Cn_f", "Ln_h", "u_IDC"}
    if set(resolved) != expected_resolved_fields:
        raise ValueError(
            "summary.best_resolved_lc must contain the six matched LC values and u_IDC."
        )
    evidence = _mapping(response_match["match_evidence"], "response-match evidence")
    evidence_fields = {
        "Cr_f": ("readout", "capacitance_f"),
        "Lr_h": ("readout", "inductance_h"),
        "Cp_f": ("filter", "capacitance_f"),
        "Lp_h": ("filter", "inductance_h"),
        "Cn_f": ("bridge", "capacitance_f"),
        "Ln_h": ("bridge", "inductance_h"),
    }
    for resolved_field, (group, evidence_field) in evidence_fields.items():
        resolved_value = _finite(
            resolved[resolved_field], f"summary.best_resolved_lc.{resolved_field}"
        )
        evidence_value = _finite(
            _mapping(evidence[group], f"response-match {group}")[evidence_field],
            f"response-match {group}.{evidence_field}",
        )
        if resolved_value <= 0 or not math.isclose(
            resolved_value,
            evidence_value,
            rel_tol=1e-14,
            abs_tol=0.0,
        ):
            raise ValueError(
                f"summary.best_resolved_lc.{resolved_field} disagrees with response-match evidence."
            )
    if not math.isclose(
        _finite(resolved["u_IDC"], "summary.best_resolved_lc.u_IDC"),
        _finite(candidate["u_IDC"], "summary.best_candidate.u_IDC"),
        rel_tol=0.0,
        abs_tol=0.0,
    ):
        raise ValueError("summary resolved u_IDC disagrees with the physical candidate.")

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
    if set(objective) != {"cost", "target_gates", "target_gates_pass", "normalized_residuals"}:
        raise ValueError("summary.best_objective fields do not match the revision-9 receipt.")
    reported_cost = _finite(objective["cost"], "summary.best_objective.cost")
    if reported_cost < 0:
        raise ValueError("summary.best_objective.cost must be non-negative.")
    if not isinstance(objective["target_gates_pass"], bool):
        raise ValueError("summary.best_objective.target_gates_pass must be boolean.")
    slot_hz = float(summary["slot_hz"])
    eta_r = float(metrics["eta_r_qrp_on"])
    eta_p = float(metrics["eta_p_qrp_on"])
    residuals = {
        "r_r": (float(metrics["fr_eff_q_feedline_downfolded_qrp_on_ext_on_hz"]) - slot_hz) / 0.5e6,
        "r_p": (float(metrics["fp_eff_q_feedline_downfolded_qrp_on_ext_on_hz"]) - slot_hz) / 0.5e6,
        "r_J": (float(metrics["J_rp_eff_q_feedline_downfolded_coherent_hz"]) - 5e6) / 2e6,
        "r_n": (float(metrics["notch_rp_on_hz"]) - 5.0e9) / 10e6,
        "r_kappa": (float(metrics["kappa_sum_qrp_on_ext_on_hz"]) - 20e6) / 1e6,
        "r_eta": (min(eta_r, eta_p) - 0.5) / 0.2,
    }
    reported_residuals = _mapping(
        objective["normalized_residuals"], "summary.best_objective.normalized_residuals"
    )
    if set(reported_residuals) != set(residuals) or any(
        not math.isclose(
            _finite(reported_residuals[name], f"objective residual {name}"),
            expected,
            rel_tol=1e-12,
            abs_tol=1e-12,
        )
        for name, expected in residuals.items()
    ):
        raise ValueError("summary objective residuals disagree with revision-9 operands.")
    computed_cost = sum(value * value for value in residuals.values())
    if not math.isclose(reported_cost, computed_cost, rel_tol=1e-12, abs_tol=1e-9):
        raise ValueError("summary.best_objective.cost disagrees with revision-9 residuals.")
    gates = _mapping(objective["target_gates"], "summary.best_objective.target_gates")
    expected_gates = {
        "readout_effective_diagonal_within_tolerance": (
            abs(float(metrics["fr_eff_q_feedline_downfolded_qrp_on_ext_on_hz"]) - slot_hz) <= 0.5e6
        ),
        "filter_effective_diagonal_within_tolerance": (
            abs(float(metrics["fp_eff_q_feedline_downfolded_qrp_on_ext_on_hz"]) - slot_hz) <= 0.5e6
        ),
        "linewidth_participation": 0.3 <= eta_r <= 0.7 and 0.3 <= eta_p <= 0.7,
    }
    if dict(gates) != expected_gates:
        raise ValueError("summary.best_objective.target_gates disagree with revision-9 gates.")
    if objective["target_gates_pass"] != all(expected_gates.values()):
        raise ValueError("summary.best_objective.target_gates_pass is inconsistent.")
    return summary


def _load_linear_quantities(path: Path) -> dict[str, Any]:
    quantities = dict(_mapping(_load_json(path, "linear quantities"), "linear quantities"))
    expected_fields = {
        "schema_version",
        "source_summary_sha256",
        "objective_contract_id",
        "objective_authority",
        "coordinate_foundation",
        "anchored_oscillator_representation",
        "matched_open_q_feedline_schur_downfolded_rp_effective_representation",
        "fully_hybridized_closed_normal_mode_spectrum",
        "matched_open_port_poles",
        "model_identity",
    }
    if set(quantities) != expected_fields:
        raise ValueError("linear quantities must contain exactly the V4 review projections.")
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
        raise ValueError("linear quantities do not carry revision-9 objective authority.")
    _sha256(
        quantities["source_summary_sha256"],
        "linear quantities source_summary_sha256",
    )
    identity = _model_identity(quantities["model_identity"], "linear quantities model identity")
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
    _validate_effective_rp(
        quantities["matched_open_q_feedline_schur_downfolded_rp_effective_representation"],
        identity,
    )
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
        normal_modes["construction"] != "generalized_eigenproblem_K_u_equals_omega2_C_u"
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
            "Stage-2 matched-open poles must use global normalized stored-energy "
            "identity continuation."
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
        if real_frequency <= 0 or imaginary_frequency > passivity_tolerance_hz or linewidth_hz < 0:
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
            raise ValueError(f"matched_open assigned {identity} display_index must be an integer.")
        if not 1 <= display_index <= len(frequencies):
            raise ValueError(f"matched_open assigned {identity} display_index is out of range.")
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


def _validate_summary_effective_consistency(
    summary: Mapping[str, Any], linear_quantities: Mapping[str, Any]
) -> None:
    metrics = _mapping(summary["best_metrics"], "summary.best_metrics")
    effective = _mapping(
        linear_quantities["matched_open_q_feedline_schur_downfolded_rp_effective_representation"],
        "effective representation",
    )
    roots = _mapping(effective["diagonal_roots"], "effective diagonal roots")
    exchange = _mapping(effective["residue_normalized_exchange"], "effective exchange")
    comparisons = {
        "fr_eff_q_feedline_downfolded_qrp_on_ext_on_hz": roots["r"]["frequency_hz"],
        "fp_eff_q_feedline_downfolded_qrp_on_ext_on_hz": roots["p"]["frequency_hz"],
        "J_rp_eff_q_feedline_downfolded_coherent_hz": exchange["coherent_exchange_hz"],
    }
    for metric_name, receipt_value in comparisons.items():
        if not math.isclose(
            _finite(metrics[metric_name], f"summary metric {metric_name}"),
            _finite(receipt_value, f"effective receipt {metric_name}"),
            rel_tol=1e-12,
            abs_tol=1e-6,
        ):
            raise ValueError(f"summary metric {metric_name} disagrees with the effective receipt.")

    open_poles = _mapping(linear_quantities["matched_open_port_poles"], "matched-open port poles")
    assigned = _mapping(open_poles["qrp_identity_assigned"], "matched-open q/r/p assignments")
    assigned_linewidth_hz = {
        identity: _finite(
            _mapping(assigned[identity], f"matched-open assigned {identity}")["linewidth_hz"],
            f"matched-open assigned {identity} linewidth",
        )
        for identity in ("q", "r", "p")
    }
    total_linewidth_hz = sum(assigned_linewidth_hz.values())
    if not math.isclose(
        _finite(
            metrics["kappa_sum_qrp_on_ext_on_hz"],
            "summary metric kappa_sum_qrp_on_ext_on_hz",
        ),
        total_linewidth_hz,
        rel_tol=1e-12,
        abs_tol=1e-6,
    ):
        raise ValueError("summary total q/r/p linewidth disagrees with the assigned open poles.")
    resonator_linewidth_hz = assigned_linewidth_hz["r"] + assigned_linewidth_hz["p"]
    if resonator_linewidth_hz <= 0:
        raise ValueError("assigned matched-open r+p linewidth must be positive.")
    for identity in ("r", "p"):
        expected_participation = assigned_linewidth_hz[identity] / resonator_linewidth_hz
        if not math.isclose(
            _finite(metrics[f"eta_{identity}_qrp_on"], f"summary eta_{identity}_qrp_on"),
            expected_participation,
            rel_tol=1e-12,
            abs_tol=1e-12,
        ):
            raise ValueError(
                f"summary eta_{identity}_qrp_on disagrees with assigned r/p linewidths."
            )


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
        raise ValueError("qubit receipt does not carry revision-9 objective authority.")
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
        pole for pole in result["rational_model"]["poles"] if pole["classification"] == "resonance"
    ]
    if len(poles) != 2:
        raise ValueError(
            f"Direct-S21 Vector Fitting must resolve two visible poles; got {len(poles)}."
        )
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
    palette = REPORT_RENDER_CONFIG["palette"]
    slot_ghz = float(summary["slot_hz"]) / 1e9
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
        "direct": ("Direct C/K", palette["authority"], "solid"),
        "exact": ("Exact-12", palette["analytic"], "dash"),
        "hb": ("HB solver", palette["solver"], "dot"),
        "vector_fit": ("VF of Direct S21", palette["diagnostic"], "dashdot"),
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
    figure.add_vline(
        x=slot_ghz,
        line={"color": palette["muted"], "dash": "dash", "width": 1.5},
        row=1,
        col=1,
    )
    for key, label, color in (
        ("exact", "|Exact-12 - Direct|", palette["analytic"]),
        ("hb", "|HB - Direct|", palette["solver"]),
        ("vector_fit", "|VF - Direct|", palette["diagnostic"]),
    ):
        residual = vector_fit["residual_s21"] if key == "vector_fit" else s21[key] - s21["direct"]
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
        ("hb", "HB Re(YQ,eff)", palette["response"], "solid"),
        ("direct", "Direct Re(YQ,eff)", palette["response"], "dash"),
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
        ("hb", "HB linearized T1 estimate", palette["lifetime"], "solid"),
        ("direct", "Direct linearized T1 estimate", palette["lifetime"], "dash"),
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
        width=REPORT_RENDER_CONFIG["width_px"],
        height=REPORT_RENDER_CONFIG["media_height_px"],
        margin={"l": 100, "r": 110, "t": 65, "b": 70},
        template="plotly_white",
        font={"family": REPORT_RENDER_CONFIG["font_family"], "size": 16},
        legend={"orientation": "h", "yanchor": "bottom", "y": 1.01, "x": 0.0},
    )
    figure.write_image(
        path,
        format="png",
        width=REPORT_RENDER_CONFIG["width_px"],
        height=REPORT_RENDER_CONFIG["media_height_px"],
        scale=1,
    )


def _gate(value: bool) -> str:
    return "PASS" if value else "FAIL"


def _format_complex(value: Any, label: str, unit: str) -> str:
    number = _complex_value(value, label)
    return f"({number.real:.9g}{number.imag:+.9g}j) {unit}"


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


def _single_line_q2d_readback(summary: Mapping[str, Any]) -> dict[str, float]:
    q2d = _mapping(summary["q2d_spec"], "summary.q2d_spec")
    single_l = _finite(q2d["single_l_per_m_h"], "q2d single L")
    single_c = _finite(q2d["single_c_per_m_f"], "q2d single C")
    if single_l <= 0 or single_c <= 0:
        raise ValueError("summary Q2D single-line L/C values must be positive.")
    velocity = 1 / math.sqrt(single_l * single_c)
    return {
        "z0": math.sqrt(single_l / single_c),
        "velocity": velocity,
        "epsilon_eff": (299_792_458.0 / velocity) ** 2,
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
            "locator": (f"run-directory/{path.name}"),
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
    response_match = _mapping(summary["response_match"], "summary.response_match")
    match_evidence = _mapping(
        response_match["match_evidence"],
        "summary.response_match.match_evidence",
    )
    reference_model = _mapping(
        match_evidence["reference_model"],
        "response-match reference model",
    )
    readout_match = _mapping(match_evidence["readout"], "response-match readout")
    filter_match = _mapping(match_evidence["filter"], "response-match filter")
    bridge_match = _mapping(match_evidence["bridge"], "response-match bridge")
    match_settings = _mapping(match_evidence["settings"], "response-match settings")
    q2d = _mapping(summary["q2d_spec"], "summary.q2d_spec")
    geometry = _mapping(q2d["geometry_um"], "summary.q2d_spec.geometry_um")
    solver = _mapping(q2d["solver"], "summary.q2d_spec.solver")
    q2d_readback = _single_line_q2d_readback(summary)
    l_matrix = np.asarray(q2d["l_matrix_per_m_h"], dtype=float).reshape(2, 2) * 1e9
    c_matrix = np.asarray(q2d["c_matrix_per_m_f"], dtype=float).reshape(2, 2) * 1e12

    anchored = _mapping(
        linear_quantities["anchored_oscillator_representation"],
        "linear quantities anchored oscillator representation",
    )
    anchored_frequency = _mapping(
        anchored["h_diagonal_frequency_hz"], "anchored h diagonal frequency"
    )
    anchored_coupling = _mapping(anchored["h_number_conserving_coupling_hz"], "anchored h coupling")
    anchored_pairing = _mapping(anchored["pairing_coupling_hz"], "anchored pairing")
    effective = _mapping(
        linear_quantities["matched_open_q_feedline_schur_downfolded_rp_effective_representation"],
        "linear quantities effective RP representation",
    )
    effective_roots = _mapping(effective["diagonal_roots"], "effective RP diagonal roots")
    effective_exchange = _mapping(effective["residue_normalized_exchange"], "effective RP exchange")
    readout_effective_root = _complex_value(
        effective_roots["r"]["complex_frequency_hz"], "effective readout root"
    )
    filter_effective_root = _complex_value(
        effective_roots["p"]["complex_frequency_hz"], "effective filter root"
    )
    complex_exchange = _complex_value(
        effective_exchange["effective_exchange_rad_s"], "effective RP exchange"
    )
    filter_effective_linewidth_hz = float(effective_roots["p"]["external_linewidth_hz"])
    total_qrp_linewidth_hz = float(metrics["kappa_sum_qrp_on_ext_on_hz"])
    headline = (
        f"S21, closure, and weighted-qubit Purcell response — cost "
        f"{float(objective['cost']):.6g}; gates "
        f"{_gate(bool(objective['target_gates_pass']))}; "
        f"fᵣ/fₚ {float(metrics['fr_eff_q_feedline_downfolded_qrp_on_ext_on_hz']) / 1e9:.6f}/"
        f"{float(metrics['fp_eff_q_feedline_downfolded_qrp_on_ext_on_hz']) / 1e9:.6f} GHz; "
        f"J {float(metrics['J_rp_eff_q_feedline_downfolded_coherent_hz']) / 1e6:.4f} MHz; "
        f"κΣ {total_qrp_linewidth_hz / 1e6:.4f} MHz"
    )
    primary_extraction_rows = [
        (
            "Schur-dressed anchored-coordinate dynamic-effective — QRP,on; matched-open",
            "q+feedline-downfolded r diagonal root",
            f"{float(metrics['fr_eff_q_feedline_downfolded_qrp_on_ext_on_hz']) / 1e9:.9f} GHz",
            f"Im = {readout_effective_root.imag / 1e6:.9g} MHz",
            f"target {slot_hz / 1e9:.9f} GHz; "
            f"κext = {float(effective_roots['r']['external_linewidth_hz']) / 1e6:.9g} MHz",
            _gate(bool(gates["readout_effective_diagonal_within_tolerance"])),
        ),
        (
            "Schur-dressed anchored-coordinate dynamic-effective — QRP,on; matched-open",
            "q+feedline-downfolded p diagonal root",
            f"{float(metrics['fp_eff_q_feedline_downfolded_qrp_on_ext_on_hz']) / 1e9:.9f} GHz",
            f"Im = {filter_effective_root.imag / 1e6:.9g} MHz",
            f"target {slot_hz / 1e9:.9f} GHz; "
            f"κext = {float(effective_roots['p']['external_linewidth_hz']) / 1e6:.9g} MHz",
            _gate(bool(gates["filter_effective_diagonal_within_tolerance"])),
        ),
        (
            "Schur-dressed anchored-coordinate dynamic-effective — QRP,on; matched-open",
            "residue-normalized coherent |Re Jrp|",
            f"{float(metrics['J_rp_eff_q_feedline_downfolded_coherent_hz']) / 1e6:.6f} MHz",
            f"J/2π = ({complex_exchange.real / (2 * math.pi * 1e6):.9g}"
            f"{complex_exchange.imag / (2 * math.pi * 1e6):+.9g}j) MHz",
            f"target 5.000000 MHz; |J| = "
            f"{float(effective_exchange['total_exchange_hz']) / 1e6:.9g} MHz",
            f"κcross = {float(effective_exchange['dissipative_cross_coupling_hz']) / 1e6:.9g} MHz",
        ),
    ]
    diagnostic_rows = [
        (
            "Report-only linewidth diagnostic — Schur-effective p root",
            "κp,eff - 20 MHz",
            f"{(filter_effective_linewidth_hz - 20e6) / 1e6:+.9g} MHz",
            f"κp,eff = {filter_effective_linewidth_hz / 1e6:.9g} MHz",
            "20.000000 MHz reference",
            "report-only; not an objective operand",
        ),
        (
            "Report-only linewidth diagnostic — cross-projection comparison",
            "κp,eff - κΣ,qrp",
            f"{(filter_effective_linewidth_hz - total_qrp_linewidth_hz) / 1e6:+.9g} MHz",
            f"κp,eff = {filter_effective_linewidth_hz / 1e6:.9g} MHz",
            f"κΣ,qrp = {total_qrp_linewidth_hz / 1e6:.9g} MHz",
            "report-only; effective diagonal root vs assigned q+r+p poles",
        ),
    ]
    impedance = _mapping(anchored["impedance_ohm"], "anchored impedance")
    pairing_diagonal = _mapping(anchored["pairing_diagonal_hz"], "anchored pairing diagonal")
    for coordinate in ("q", "r", "p"):
        diagnostic_rows.append(
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
        diagnostic_rows.append(
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
        diagnostic_rows.append(
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
        diagnostic_rows.append(
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
                    else "feedline-like pole, unassigned to q/r/p; not a Hamiltonian basis"
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
    vector_fit_rows = []
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
        vector_fit_rows.append(
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
    normalized_residuals = _mapping(
        objective["normalized_residuals"], "summary.best_objective.normalized_residuals"
    )
    objective_rows = [
        (
            "Objective residual — revision 9",
            "r_r: Schur-effective r diagonal root",
            f"{float(metrics['fr_eff_q_feedline_downfolded_qrp_on_ext_on_hz']) / 1e9:.9f} GHz",
            f"target = {slot_hz / 1e9:.9f} GHz",
            "scale = 0.500000 MHz",
            f"normalized = {float(normalized_residuals['r_r']):+.9g}; "
            f"{_gate(bool(gates['readout_effective_diagonal_within_tolerance']))}; "
            "retained r coordinate after q+feedline loading",
        ),
        (
            "Objective residual — revision 9",
            "r_p: Schur-effective p diagonal root",
            f"{float(metrics['fp_eff_q_feedline_downfolded_qrp_on_ext_on_hz']) / 1e9:.9f} GHz",
            f"target = {slot_hz / 1e9:.9f} GHz",
            "scale = 0.500000 MHz",
            f"normalized = {float(normalized_residuals['r_p']):+.9g}; "
            f"{_gate(bool(gates['filter_effective_diagonal_within_tolerance']))}; "
            "retained p coordinate after q+feedline loading",
        ),
        (
            "Objective residual — revision 9",
            "r_J: Schur-effective coherent |Re Jrp|",
            f"{float(metrics['J_rp_eff_q_feedline_downfolded_coherent_hz']) / 1e6:.9f} MHz",
            "target = 5.000000000 MHz",
            "scale = 2.000000 MHz",
            f"normalized = {float(normalized_residuals['r_J']):+.9g}; "
            "coherent retained r-p exchange; dissipative cross-coupling is report-only",
        ),
        (
            "Objective residual — revision 9",
            "r_n: intrinsic RP,on notch",
            f"{float(metrics['notch_rp_on_hz']) / 1e9:.9f} GHz",
            "target = 5.000000000 GHz",
            "scale = 10.000000 MHz",
            f"normalized = {float(normalized_residuals['r_n']):+.9g}; "
            "real-axis complex Z21 zero of the intrinsic RP,on circuit",
        ),
        (
            "Objective residual — revision 9",
            "r_kappa: matched-open q/r/p total linewidth",
            f"{float(metrics['kappa_sum_qrp_on_ext_on_hz']) / 1e6:.9f} MHz",
            "target = 20.000000000 MHz",
            "scale = 1.000000 MHz",
            f"normalized = {float(normalized_residuals['r_kappa']):+.9g}; "
            "sum of assigned q/r/p matched-open pole linewidths",
        ),
        (
            "Objective residual — revision 9",
            "r_eta: min(r,p) linewidth participation",
            f"{min(float(metrics['eta_r_qrp_on']), float(metrics['eta_p_qrp_on'])):.9f}",
            "target = 0.500000000",
            "scale = 0.200000",
            f"normalized = {float(normalized_residuals['r_eta']):+.9g}; "
            f"{_gate(bool(gates['linewidth_participation']))}; r/p linewidth sharing",
        ),
        (
            "Physical scalar-formula fit-back — Design Target requirement",
            "bounded recovery of cared reduced parameters",
            "NOT_AVAILABLE — no fit-back artifact is present in this canonical Run",
            "recover f_r, f_p, coherent J, and declared port-response parameters",
            "fixed basis, sparsity, ports, bounds, and response window",
            "implementation gap; the scalar VF rows below are a parallel pole cross-check, "
            "not a substitute",
        ),
    ]
    metric_rows = objective_rows + primary_extraction_rows + vector_fit_rows
    parameter_rows = [
        ("Fabrication — readout open-side length", f"{float(candidate['lr_open_m']) * 1e6:.6f} µm"),
        (
            "Fabrication — readout short-side length",
            f"{float(candidate['lr_short_m']) * 1e6:.6f} µm",
        ),
        ("Fabrication — MTL coupling length", f"{float(candidate['lc_m']) * 1e6:.6f} µm"),
        ("Fabrication — filter open-side length", f"{float(candidate['lp_open_m']) * 1e6:.6f} µm"),
        (
            "Fabrication — filter short-side length",
            f"{float(candidate['lp_short_m']) * 1e6:.6f} µm",
        ),
        ("Fabrication — IDC finger length", f"{float(candidate['u_IDC']):.6f} µm"),
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
            (
                f"Equivalent circuit — resolved {key}",
                f"{_finite(resolved[key], key) * scale:.9g} {unit}",
            )
        )
    parameter_rows.extend(
        (
            (
                "Qubit transform — effective capacitance Cq,eff",
                f"{qubit_meta['c_q_eff_f'] * 1e15:.9g} fF",
            ),
            ("Qubit transform — floating weight alpha", f"{qubit_meta['alpha']:.12g}"),
            ("Qubit transform — floating weight beta", f"{qubit_meta['beta']:.12g}"),
        )
    )

    readout_root_y = _format_complex(readout_match["root_admittance_s"], "readout root Y", "S")
    readout_dy = _format_complex(
        readout_match["admittance_derivative_s_per_rad_s"],
        "readout dY/domega",
        "S/(rad/s)",
    )
    filter_root_y = _format_complex(filter_match["root_admittance_s"], "filter root Y", "S")
    filter_dy = _format_complex(
        filter_match["admittance_derivative_s_per_rad_s"],
        "filter dY/domega",
        "S/(rad/s)",
    )
    bridge_root_z21 = _format_complex(
        bridge_match["root_transfer_impedance_ohm"], "bridge root Z21", "Ω"
    )
    bridge_dz21 = _format_complex(
        bridge_match["transfer_impedance_derivative_ohm_per_rad_s"],
        "bridge dZ21/domega",
        "Ω/(rad/s)",
    )
    bisection_atol = float(match_settings["bisection_absolute_tolerance_rad_s"])
    derivative_rtol = float(match_settings["derivative_relative_tolerance"])
    fixed_rows = [
        ("Q2D setup — cross-section", "continuous upper ground; no opening"),
        (
            "Q2D setup — geometry",
            "w = {w:g} µm, s = {s:g} µm, d = {d:g} µm, h = {h:g} µm, t = {t:g} µm".format(
                w=float(geometry["w"]),
                s=float(geometry["s"]),
                d=float(geometry["d"]),
                h=float(geometry["h"]),
                t=float(geometry["metal_thickness"]),
            ),
        ),
        (
            "Q2D setup — materials / dielectric",
            "NOT_AVAILABLE — the canonical Stage-2 Q2D artifact does not yet publish "
            "the material stack or dielectric constants",
        ),
        (
            "Single-line CPW — RLGC",
            f"R' = G' = 0; L' = {float(q2d['single_l_per_m_h']) * 1e9:.6f} nH/m; "
            f"C' = {float(q2d['single_c_per_m_f']) * 1e12:.6f} pF/m",
        ),
        (
            "Single-line CPW — propagation",
            f"Z0 = {q2d_readback['z0']:.6f} Ω; v = {q2d_readback['velocity']:.7g} m/s; "
            f"εeff = {q2d_readback['epsilon_eff']:.6f}",
        ),
        ("MTL section — L' matrix", np.array2string(l_matrix, precision=6) + " nH/m"),
        ("MTL section — C' matrix", np.array2string(c_matrix, precision=6) + " pF/m"),
        (
            "Q2D setup — solver convention",
            f"{float(solver['adaptive_frequency_hz']) / 1e9:g} GHz adaptive; lossless; "
            f"{q2d['coupling_orientation'].replace('_', '-')} MTL coupling",
        ),
        (
            "Length→LC extraction — reference model",
            "temporary extraction-only circuit: two grounded-head/open-tail quarter-wave "
            "resonators joined by one MTL window; final Stage-2 HB uses only the resolved "
            "lumped Equivalent Circuit",
        ),
        (
            "Length→LC extraction — reference-model reduction",
            "frequency-dependent dynamic Schur complement eliminates internal CPW/MTL nodes; "
            "terminals = readout_open_tail, filter_open_tail",
        ),
        (
            "Length→LC extraction — CPW/MTL discretization",
            f"section_length_m = {float(reference_model['section_length_m']):.17g} m "
            f"({float(reference_model['section_length_m']) * 1e6:.9g} µm); "
            f"mtl_section_length_m = "
            f"{float(reference_model['mtl_section_length_m']):.17g} m "
            f"({float(reference_model['mtl_section_length_m']) * 1e6:.9g} µm)",
        ),
        (
            "Length→LC extraction — readout/filter state",
            "MTL mutual terms disabled while diagonal loading is preserved; roots and slopes "
            "come from the two open-tail terminal admittances",
        ),
        (
            "Length→LC extraction — readout terminal-Y match",
            f"froot = {float(readout_match['frequency_hz']) / 1e9:.12g} GHz; "
            f"Y(root) = {readout_root_y}; dY/dω = {readout_dy}; "
            f"Cr = {float(readout_match['capacitance_f']) * 1e15:.12g} fF; "
            f"Lr = {float(readout_match['inductance_h']) * 1e9:.12g} nH",
        ),
        (
            "Length→LC extraction — filter terminal-Y match",
            f"froot = {float(filter_match['frequency_hz']) / 1e9:.12g} GHz; "
            f"Y(root) = {filter_root_y}; dY/dω = {filter_dy}; "
            f"Cp = {float(filter_match['capacitance_f']) * 1e15:.12g} fF; "
            f"Lp = {float(filter_match['inductance_h']) * 1e9:.12g} nH",
        ),
        (
            "Length→LC extraction — bridge state",
            "full MTL mutual terms preserved; the intrinsic bridge is matched at the physical "
            "open-tail Z21 notch",
        ),
        (
            "Length→LC extraction — bridge Z21 match",
            f"fnotch = {float(bridge_match['frequency_hz']) / 1e9:.12g} GHz; "
            f"Z21(root) = {bridge_root_z21}; dZ21/dω = {bridge_dz21}",
        ),
        (
            "Length→LC extraction — bridge terminal evidence",
            f"Yr = {_format_complex(bridge_match['readout_admittance_s'], 'bridge Yr', 'S')}; "
            f"Yp = {_format_complex(bridge_match['filter_admittance_s'], 'bridge Yp', 'S')}; "
            f"Im(Cn residual) = {float(bridge_match['capacitance_imaginary_residual_f']):.9g} F; "
            f"Cn = {float(bridge_match['capacitance_f']) * 1e15:.12g} fF; "
            f"Ln = {float(bridge_match['inductance_h']) * 1e9:.12g} nH",
        ),
        (
            "Length→LC extraction — root brackets",
            "readout = [{:.9g}, {:.9g}] GHz; filter = [{:.9g}, {:.9g}] GHz; "
            "notch = [{:.9g}, {:.9g}] GHz".format(
                *(float(value) / 1e9 for value in match_settings["readout_root_bracket_hz"]),
                *(float(value) / 1e9 for value in match_settings["filter_root_bracket_hz"]),
                *(float(value) / 1e9 for value in match_settings["notch_root_bracket_hz"]),
            ),
        ),
        (
            "Length→LC extraction — root/slope numerical settings",
            f"Δωparallel = {float(match_settings['parallel_derivative_step_rad_s']):.9g} rad/s; "
            f"Δωbridge = {float(match_settings['bridge_derivative_step_rad_s']):.9g} rad/s; "
            f"bisection atol = {bisection_atol:.9g} rad/s; "
            f"rtol = {float(match_settings['bisection_relative_tolerance']):.9g}; "
            f"maxiter = {int(match_settings['bisection_max_iterations'])}; "
            f"root residual rtol = {float(match_settings['match_root_relative_tolerance']):.9g}; "
            f"derivative residual rtol = {derivative_rtol:.9g}",
        ),
    ]
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
    objective_authority = _mapping(summary["objective_authority"], "summary.objective_authority")
    effective_provenance = _mapping(effective["provenance"], "effective RP provenance")
    effective_closure = _mapping(effective["determinant_closure"], "effective RP closure")
    effective_slopes = _mapping(effective_exchange["residue_slopes"], "effective RP slopes")
    effective_samples = _mapping(
        effective_exchange["coupling_samples_rad_s"], "effective RP coupling samples"
    )
    effective_operator_diagnostics = [
        _mapping(sample, f"effective {name} operator diagnostics")
        for name, sample in _mapping(
            effective["operator_diagnostics"], "effective RP operator diagnostics"
        ).items()
    ]
    maximum_operator_condition = max(
        float(sample["elimination_condition_number"]) for sample in effective_operator_diagnostics
    )
    maximum_operator_solve_residual = max(
        max(
            float(sample["relative_elimination_solve_residual"]),
            float(sample["relative_derivative_solve_residual"]),
        )
        for sample in effective_operator_diagnostics
    )
    maximum_operator_reciprocity_error = max(
        float(sample["effective_reciprocity_error"]) for sample in effective_operator_diagnostics
    )
    effective_normalization_text = _format_complex(
        effective_exchange["residue_normalization"],
        "effective normalization",
        "native operator units",
    )
    provenance_rows = (
        ("Run status", str(summary["status"])),
        ("Objective contract", str(summary["objective_contract_id"])),
        (
            "Target authority",
            f"revision {objective_authority['target_revision']}; "
            f"SHA {objective_authority['target_contract_sha256']}",
        ),
        ("Effective-operator contract", str(effective["contract_id"])),
        (
            "Effective-operator definition",
            f"{effective_provenance['dynamic_stiffness']}; exact Schur complement; "
            f"retain {effective_provenance['retained_partition']}; eliminate "
            f"{effective_provenance['eliminated_partition']}; matched ports enter G",
        ),
        (
            "Effective diagonal-root extraction",
            f"{effective['diagonal_root_extraction']}; r band = "
            f"{effective_roots['r']['frequency_band_hz']}; p band = "
            f"{effective_roots['p']['frequency_band_hz']}; frequency-rank assignment forbidden",
        ),
        (
            "Residue normalization / branch",
            f"sqrt(({_complex_value(effective_slopes['readout_s'], 'readout slope')})"
            f"x({_complex_value(effective_slopes['filter_s'], 'filter slope')})); "
            f"normalization = {effective_normalization_text}; "
            f"branch = {effective_exchange['square_root_branch']}; pointwise branch only—"
            "cross-candidate branch continuation is not claimed",
        ),
        (
            "Complex coupling samples",
            "readout/midpoint/filter = "
            + " / ".join(
                _format_complex(effective_samples[name], f"effective {name} J", "rad/s")
                for name in ("readout", "midpoint", "filter")
            ),
        ),
        (
            "Effective coupling/closure diagnostics",
            f"three-point relative spread = "
            f"{float(effective_exchange['relative_coupling_spread']):.9g}; "
            f"determinant relative closure = {float(effective_closure['relative_error']):.9g}",
        ),
        (
            "Effective operator sample diagnostics",
            f"max cond(D_EE) = {maximum_operator_condition:.9g}; "
            f"max solve residual = {maximum_operator_solve_residual:.9g}; "
            f"max reciprocity error = {maximum_operator_reciprocity_error:.9g} "
            "across readout/midpoint/filter",
        ),
        ("Effective C SHA", str(effective_provenance["capacitance_sha256"])),
        ("Effective K SHA", str(effective_provenance["inverse_inductance_sha256"])),
        ("Effective matched-port G SHA", str(effective_provenance["conductance_sha256"])),
        ("CircuitPlan SHA", model_identity["circuit_plan_sha256"]),
        ("Capacitance SHA", model_identity["capacitance_sha256"]),
        ("Inverse-inductance SHA", model_identity["inverse_inductance_sha256"]),
        ("Port-selector SHA", model_identity["selector_sha256"]),
        ("Q2D artifact", str(q2d["artifact_id"])),
        ("Q2D artifact SHA", str(q2d["artifact_sha256"])),
        ("Length→LC mapping", str(response_match["mapping_id"])),
        ("Length→LC mapping SHA", str(response_match["mapping_sha256"])),
        ("Length→LC match contract", str(response_match["match_contract_id"])),
        ("Length→LC topology", str(response_match["topology_id"])),
        ("Fixed Q2D line-input SHA", str(response_match["fixed_line_input_sha256"])),
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
            ", ".join(f"{name}={float(cma_initial_mean[name]):.9g}" for name in _CANDIDATE_KEYS),
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
                "title": headline,
                "path": str(media_path),
                "sha256": file_sha256(media_path),
                "source_ids": ["s21", "qubit", "qubit_receipt", "summary"],
            },
            {
                "type": "optimization_history",
                "id": "objective-history",
                "title": (
                    "Best objective cost by valid candidate evaluation (initial seed + CMA-ES): "
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
                "Stage-2 targets, optimized results, Schur extraction, and Vector Fitting",
                (
                    "Layer / authority",
                    "Quantity",
                    "Actual",
                    "Target / reference",
                    "Scale / companion",
                    "Gate / physical meaning",
                ),
                metric_rows,
                (1.25, 1.25, 1.05, 1.05, 1.15, 1.65),
                ("summary", "linear_quantities", "s21"),
            ),
            _table(
                "parameters",
                "parameters",
                "Fabrication candidate, resolved equivalent circuit, and qubit transform",
                ("Parameter", "Value"),
                parameter_rows,
                (1.5, 2.5),
                ("summary", "qubit", "qubit_receipt"),
            ),
            _table(
                "fixed-specifications",
                "fixed_specifications",
                "Q2D setup, single-line CPW, MTL section, and Length→LC extraction audit",
                ("Fixed input / extraction evidence", "Value used by this Stage-2 run"),
                fixed_rows,
                (1.0, 3.2),
                ("summary",),
            ),
            _table(
                "diagnostics",
                "diagnostics",
                "Report-only anchored-bare, fully hybridized closed, and matched-open views",
                (
                    "Layer / authority",
                    "Quantity",
                    "Actual",
                    "Reference / boundary",
                    "Companion quantity",
                    "Physical meaning",
                ),
                diagnostic_rows,
                (1.25, 1.25, 1.05, 1.05, 1.15, 1.65),
                ("summary", "linear_quantities"),
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
    _validate_summary_effective_consistency(summary, linear_quantities)
    qubit_receipt = _load_qubit_receipt(qubit_receipt_path)
    summary_sha256 = file_sha256(summary_path)
    if linear_quantities["source_summary_sha256"] != summary_sha256:
        raise ValueError("linear quantities were not produced from this Stage-2 summary.")
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
