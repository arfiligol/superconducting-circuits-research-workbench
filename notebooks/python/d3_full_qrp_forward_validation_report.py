"""Build source-backed D3 exact-six forward-validation report evidence.

This companion module owns strict loading, cross-artifact linkage, static
figure rendering, and the machine-readable evidence register for the public
Q2D CPW extraction route plus local circuit evidence. The exact six-coordinate
open response is authoritative; the constant-kappa three-mode views are
diagnostics only. This module does not run Q2D, circuit simulation, or Vector
Fitting, and it never promotes physical mode identity. Missing or inconsistent
source evidence fails before output begins.
"""

from __future__ import annotations

import hashlib
import json
import math
import shutil
import tempfile
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from numbers import Integral, Real
from pathlib import Path, PurePosixPath
from typing import Any, cast

import matplotlib
import numpy as np

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.figure import Figure
from matplotlib.patches import Patch, Rectangle

EXPECTED_SLOTS_HZ = (5.52e9, 5.76e9, 6.00e9, 6.24e9, 6.48e9)
PUBLIC_Q2D_ROUTE = "public_q2d_cpw_spec_simulation_only"
REPORT_SCHEMA = "d3-full-qrp-forward-validation-evidence-register.v2"
FIGURE_DATA_SCHEMA = "d3-full-qrp-vf-figure-data.v2"
Q2D_ARTIFACT_SCHEMA = "orpen-q2d-intrinsic-purcell-maxwell-lc-cases.v3"
CROSS_SECTION_SCHEMA = "q2d-semantic-cross-section.v1"
_SHA256_LENGTH = 64
_EXACT_SIX_KEYS = {
    "contract_id",
    "response_authority",
    "model_role",
    "coordinate_order",
    "frequency_hz",
    "raw_s21",
    "calibrated_s21",
    "open_poles",
    "reference_impedance_ohm",
    "port_selector",
    "hashes",
    "calibration",
    "residual_vs_existing_equivalent",
    "provenance",
}
_GRID_POLICY_KEYS = {
    "contract_id",
    "requested_samples_per_linewidth",
    "linewidth_floor_hz",
    "open_pole_center_sampling_policy",
    "closed_pole_exclusion_policy",
    "maximum_local_intervals_per_open_pole",
    "open_poles",
    "closed_pole_exclusions",
}
_GRID_OPEN_KEYS = {
    "source_index",
    "pole_frequency_hz",
    "pole_linewidth_hz",
    "effective_linewidth_hz",
    "planned_local_step_hz",
    "planned_samples_per_physical_linewidth",
    "planned_samples_per_effective_linewidth",
    "planned_local_sample_count",
    "retained_planned_local_sample_count",
    "center_sampled",
    "minimum_center_detuning_hz",
}
_GRID_CLOSED_KEYS = {
    "model_role",
    "section_length_m",
    "source_index",
    "pole_frequency_hz",
    "mode_residual",
    "exclusion_half_width_hz",
    "exclusion_scale_steps",
    "negative_boundary_max_normalized_closure_ratio",
    "positive_boundary_max_normalized_closure_ratio",
    "center_sampled",
    "minimum_center_detuning_hz",
    "source_sha256",
    "node_order_sha256",
    "capacitance_sha256",
    "inverse_inductance_sha256",
    "reduced_capacitance_sha256",
    "reduced_inverse_inductance_sha256",
}
_FULL_QRP_SUBSET_KEYS = {
    "contract_id",
    "source_grid_role",
    "subset_policy",
    "interpolation_used",
    "maximum_allowed_normalized_spectral_backward_bound",
    "source_sample_count",
    "source_frequency_semantic_sha256",
    "retained_source_indices",
    "retained_frequency_hz",
    "retained_frequency_semantic_sha256",
    "retained_sample_count",
    "retained_fraction",
    "excluded_unique_source_sample_count",
    "excluded_sample_owner_rows",
    "owner_diagnostics",
    "physical_mode_identity_claim",
}
_FULL_QRP_EXCLUSION_KEYS = {
    "source_index",
    "frequency_hz",
    "owner_model",
    "normalized_spectral_backward_bound",
    "maximum_allowed_normalized_spectral_backward_bound",
    "conditioning_reason",
    "nearest_pole_array_index_for_numerical_reference_only",
    "nearest_pole_frequency_hz",
    "nearest_pole_detuning_hz",
    "nearest_pole_linewidth_hz",
    "nearest_pole_residue_abs_hz",
    "physical_mode_identity_claim",
}


@dataclass(frozen=True, slots=True)
class EvidenceInputPaths:
    """Name every source artifact required by the evidence report.

    Attributes:
        analysis_json: Complete path-backed exact-six/three-mode/VF analyzer output.
        primary_run_json: Raw primary five-slot circuit-forward run.
        spring_initializer_json: Paper-backed Spring initializer artifact.
        q2d_pair_json: Public coupled-pair Maxwell L/C artifact.
        q2d_single_json: Public single-reference Maxwell L/C artifact.
        cross_section_json: Public semantic cross-section for the selected pair.
    """

    analysis_json: Path
    primary_run_json: Path
    spring_initializer_json: Path
    q2d_pair_json: Path
    q2d_single_json: Path
    cross_section_json: Path

    def as_mapping(self) -> dict[str, Path]:
        """Return stable source labels and paths for loading and registration."""

        return {
            "analysis": self.analysis_json,
            "primary_run": self.primary_run_json,
            "spring_initializer": self.spring_initializer_json,
            "q2d_pair": self.q2d_pair_json,
            "q2d_single": self.q2d_single_json,
            "cross_section": self.cross_section_json,
        }


@dataclass(frozen=True, slots=True)
class EvidenceBundle:
    """Retain six verified sources and their selected public Q2D cases."""

    paths: EvidenceInputPaths
    payloads: dict[str, dict[str, Any]]
    raw_sha256: dict[str, str]
    raw_sizes: dict[str, int]
    selected_pair_case: dict[str, Any]
    selected_single_case: dict[str, Any]


@dataclass(frozen=True, slots=True)
class _FigureDefinition:
    figure_id: str
    filename: str
    title: str
    source_contracts: tuple[str, ...]
    semantics: str
    renderer: Callable[[EvidenceBundle], Figure]


def load_evidence_bundle(paths: EvidenceInputPaths) -> EvidenceBundle:
    """Load six explicit paths and validate their schemas and linkages.

    Args:
        paths: Explicit paths for every required source contract.

    Returns:
        A bundle that is safe to pass to the report renderer.

    Raises:
        FileNotFoundError: If any required source path is absent.
        ValueError: If a schema, semantic invariant, or cryptographic linkage
            is missing or inconsistent.
    """

    payloads: dict[str, dict[str, Any]] = {}
    raw_sha256: dict[str, str] = {}
    raw_sizes: dict[str, int] = {}
    for label, path in paths.as_mapping().items():
        payload, raw = _load_json_object(path, label)
        payloads[label] = payload
        raw_sha256[label] = hashlib.sha256(raw).hexdigest()
        raw_sizes[label] = len(raw)

    _validate_analysis(payloads["analysis"])
    primary_identity = _validate_primary_run(payloads["primary_run"])
    _validate_initializer(payloads["spring_initializer"])
    pair_cases = _validate_q2d_artifact(payloads["q2d_pair"], role="coupled_pair")
    single_cases = _validate_q2d_artifact(payloads["q2d_single"], role="single_reference")

    if raw_sha256["q2d_pair"] != primary_identity["q2d_pair_artifact_sha256"]:
        raise ValueError("Public Q2D pair raw-byte SHA-256 does not match the primary run.")
    if raw_sha256["q2d_single"] != primary_identity["q2d_single_artifact_sha256"]:
        raise ValueError("Public Q2D single raw-byte SHA-256 does not match the primary run.")

    selected_pair, selected_single = _select_q2d_cases(
        cast(str, primary_identity["case_id"]), pair_cases, single_cases
    )
    _validate_cross_section(
        payloads["cross_section"],
        paths.cross_section_json,
        raw_sha256["cross_section"],
        raw_sizes["cross_section"],
        payloads["q2d_pair"],
        selected_pair,
    )
    _validate_cross_source_links(
        analysis=payloads["analysis"],
        primary=payloads["primary_run"],
        initializer=payloads["spring_initializer"],
        primary_sha256=_canonical_sha256(payloads["primary_run"]),
    )
    return EvidenceBundle(
        paths=paths,
        payloads=payloads,
        raw_sha256=raw_sha256,
        raw_sizes=raw_sizes,
        selected_pair_case=selected_pair,
        selected_single_case=selected_single,
    )


def summarize_evidence(bundle: EvidenceBundle) -> dict[str, Any]:
    """Return a compact notebook-facing summary without claiming promotion."""

    analysis = bundle.payloads["analysis"]
    initializer = bundle.payloads["spring_initializer"]
    figure_data = _mapping(analysis["figure_data"], "analysis.figure_data")
    return {
        "analysis_status": analysis["status"],
        "public_q2d_route": analysis["source"]["q2d_route"],
        "slots_hz": [slot["slot_hz"] for slot in analysis["slots"]],
        "selected_q2d_pair_case_id": bundle.selected_pair_case["id"],
        "selected_q2d_single_case_id": bundle.selected_single_case["id"],
        "initializer_status": initializer["status"],
        "frequency_grid_policy_count": len(
            _sequence(figure_data["frequency_grid_policies"], "frequency_grid_policies")
        ),
        "closed_pole_exclusion_row_count": len(
            _sequence(
                figure_data["frequency_grid_policy_closed_pole_exclusion_rows"],
                "frequency_grid_policy_closed_pole_exclusion_rows",
            )
        ),
        "three_mode_conditioning_exclusion_row_count": len(
            _sequence(
                figure_data["three_mode_conditioning_exclusion_rows"],
                "three_mode_conditioning_exclusion_rows",
            )
        ),
        "physical_promotion_claim": False,
    }


def build_evidence_report(paths: EvidenceInputPaths, output_directory: Path) -> Path:
    """Render eight figures and atomically publish a non-overwriting register.

    Args:
        paths: Explicit paths for the six required source artifacts.
        output_directory: New directory that will own figures and the register.

    Returns:
        Path to ``evidence_register.json`` in the completed output directory.

    Raises:
        FileExistsError: If ``output_directory`` already exists.
        ValueError: If any source evidence is incomplete or inconsistent.
    """

    destination = output_directory.resolve()
    if destination.exists():
        raise FileExistsError(f"Output directory already exists: {destination}")
    bundle = load_evidence_bundle(paths)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(
        tempfile.mkdtemp(prefix=f".{destination.name}.building-", dir=destination.parent)
    )
    try:
        figure_records = []
        for definition in _figure_definitions():
            figure = definition.renderer(bundle)
            figure_path = temporary / definition.filename
            figure.savefig(figure_path, dpi=180, bbox_inches="tight")
            plt.close(figure)
            figure_records.append(
                {
                    "figure_id": definition.figure_id,
                    "filename": definition.filename,
                    "title": definition.title,
                    "source_contracts": list(definition.source_contracts),
                    "semantics": definition.semantics,
                    "physical_promotion_claim": False,
                    "sha256": _file_sha256(figure_path),
                }
            )
        register = _build_register(bundle, figure_records)
        register_path = temporary / "evidence_register.json"
        register_path.write_text(
            json.dumps(register, indent=2, allow_nan=False, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        if destination.exists():
            raise FileExistsError(f"Output directory appeared during rendering: {destination}")
        temporary.rename(destination)
    except Exception:
        shutil.rmtree(temporary, ignore_errors=True)
        raise
    return destination / "evidence_register.json"


def _load_json_object(path: Path, label: str) -> tuple[dict[str, Any], bytes]:
    source = path.resolve()
    raw = source.read_bytes()

    def reject_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"{label} JSON contains duplicate key {key!r}.")
            result[key] = value
        return result

    try:
        value = json.loads(raw, object_pairs_hook=reject_duplicates)
    except json.JSONDecodeError as exc:
        raise ValueError(f"{label} is not valid JSON: {source}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be a top-level JSON object: {source}")
    return cast(dict[str, Any], value), raw


def _validate_analysis(analysis: dict[str, Any]) -> None:
    path = "analysis"
    _require_string(analysis.get("schema_version"), "d3-full-qrp-vf-analysis.v2", path)
    _require_string(analysis.get("status"), "complete", f"{path}.status")
    _require_string(
        analysis.get("bare_fit_node_state"),
        "disabled_not_implemented",
        f"{path}.bare_fit_node_state",
    )
    source = _mapping(analysis.get("source"), f"{path}.source")
    _require_string(source.get("q2d_route"), PUBLIC_Q2D_ROUTE, f"{path}.source.q2d_route")
    _sha256(source.get("source_payload_sha256"), f"{path}.source.source_payload_sha256")
    verification = _mapping(
        source.get("design_search_sidecar_verification"),
        f"{path}.source.design_search_sidecar_verification",
    )
    _require_string(
        verification.get("state"),
        "verified_from_sibling_path",
        f"{path}.source.design_search_sidecar_verification.state",
    )
    _sha256(
        verification.get("raw_byte_sha256"),
        f"{path}.source.design_search_sidecar_verification.raw_byte_sha256",
    )
    semantics = _mapping(analysis.get("semantics"), f"{path}.semantics")
    bridge = _mapping(
        semantics.get("vf_fourier_convention_bridge"),
        f"{path}.semantics.vf_fourier_convention_bridge",
    )
    expected_bridge = {
        "source_time_convention": "exp(-i*2*pi*f*t)",
        "engine_laplace_convention": "s = j*2*pi*f",
        "engine_input_trace": "conjugate(calibrated_distributed_s21)",
        "reported_model_trace": "conjugate(engine_model_trace)",
        "error_norm_invariance": (
            "complex RMSE and maximum absolute error are unchanged by conjugation"
        ),
    }
    if bridge != expected_bridge:
        raise ValueError("analysis must declare the exact VF Fourier-convention bridge.")
    _require_string(
        semantics.get("response_authority"),
        "canonical exact six-coordinate q,r,p,f1,fc,f2 matched-port open response",
        f"{path}.semantics.response_authority",
    )
    _require_string(
        semantics.get("three_mode_role"),
        "target-substitution and circuit constant-kappa ideal-hanger comparison only",
        f"{path}.semantics.three_mode_role",
    )
    slots = _five_slots(analysis.get("slots"), f"{path}.slots")
    for index, slot in enumerate(slots):
        slot_path = f"{path}.slots[{index}]"
        _require_string(
            slot.get("response_authority"),
            "exact_six_coordinate_response",
            f"{slot_path}.response_authority",
        )
        input_evidence = _mapping(slot.get("input_evidence"), f"{slot_path}.input_evidence")
        input_response = _mapping(
            input_evidence.get("response"), f"{slot_path}.input_evidence.response"
        )
        input_frequency = _frequency_grid(
            input_response.get("frequency_hz"),
            f"{slot_path}.input_evidence.response.frequency_hz",
        )
        _validate_exact_six_response(
            input_evidence.get("exact_six_coordinate_response"),
            input_frequency,
            f"{slot_path}.input_evidence.exact_six_coordinate_response",
        )
        target = _mapping(
            slot.get("target_substitution_three_mode_approximation"),
            f"{slot_path}.target_substitution_three_mode_approximation",
        )
        circuit = _mapping(
            slot.get("circuit_three_mode_approximation"),
            f"{slot_path}.circuit_three_mode_approximation",
        )
        _validate_three_mode_view(
            target, f"{slot_path}.target_substitution_three_mode_approximation"
        )
        _validate_three_mode_view(circuit, f"{slot_path}.circuit_three_mode_approximation")
        vf = _mapping(slot.get("vf"), f"{slot_path}.vf")
        for key, expected in (
            ("source_trace", "calibrated_distributed_s21"),
            ("engine_input_trace", "conjugate(calibrated_distributed_s21)"),
            ("engine_model_trace_convention", "s = j*2*pi*f"),
            ("reported_best_trace", "conjugate(engine_model_trace)"),
            ("reported_best_trace_time_convention", "exp(-i*2*pi*f*t)"),
        ):
            _require_string(vf.get(key), expected, f"{slot_path}.vf.{key}")
        order_evidence = _mapping(
            vf.get("order_and_resolution_evidence"),
            f"{slot_path}.vf.order_and_resolution_evidence",
        )
        exact_cardinality = order_evidence.get("exact_three_resonance_cardinality_in_every_run")
        if not isinstance(exact_cardinality, bool):
            raise ValueError(
                f"{slot_path}.vf.order_and_resolution_evidence exact-cardinality state "
                "must be boolean."
            )
        expected_ambiguity_state = (
            "structurally_complete_but_physical_identity_unreviewed"
            if exact_cardinality
            else "ambiguous_or_incomplete_resonance_cardinality"
        )
        _require_string(
            order_evidence.get("ambiguity_state"),
            expected_ambiguity_state,
            f"{slot_path}.vf.order_and_resolution_evidence.ambiguity_state",
        )
        best = _mapping(vf.get("best_reconstruction"), f"{slot_path}.vf.best_reconstruction")
        if best.get("physical_promotion") is not False:
            raise ValueError(f"{slot_path}.vf.best_reconstruction must not claim promotion.")
        eligibility = _mapping(
            vf.get("promotion_eligibility"), f"{slot_path}.vf.promotion_eligibility"
        )
        _require_string(
            eligibility.get("state"),
            "pending_human_review",
            f"{slot_path}.vf.promotion_eligibility.state",
        )

    tables = _mapping(analysis.get("tables"), f"{path}.tables")
    figure_data = _mapping(analysis.get("figure_data"), f"{path}.figure_data")
    _require_string(
        figure_data.get("schema_version"), FIGURE_DATA_SCHEMA, f"{path}.figure_data.schema_version"
    )
    required_figure_keys = {
        "trace_panels",
        "exact_six_vf_pole_comparison_rows",
        "exact_six_open_pole_delta_rows",
        "residual_metric_rows",
        "section_refinement_rows",
        "frequency_grid_refinement_rows",
        "frequency_grid_policies",
        "frequency_grid_policy_open_pole_rows",
        "frequency_grid_policy_closed_pole_exclusion_rows",
        "three_mode_shared_subset_evidence",
        "three_mode_shared_subset_summary_rows",
        "three_mode_conditioning_exclusion_rows",
    }
    missing = required_figure_keys - set(figure_data)
    if missing:
        raise ValueError(
            "analysis.figure_data lacks required stable semantics: " + ", ".join(sorted(missing))
        )
    table_links = {
        "exact_six_vf_pole_comparison_rows": "exact_six_vf_pole_comparison",
        "exact_six_open_pole_delta_rows": "exact_six_open_pole_deltas",
        "residual_metric_rows": "complex_residuals",
        "section_refinement_rows": "section_refinement",
        "frequency_grid_refinement_rows": "frequency_grid_refinement",
        "frequency_grid_policy_open_pole_rows": "frequency_grid_policy_open_poles",
        "frequency_grid_policy_closed_pole_exclusion_rows": (
            "frequency_grid_policy_closed_pole_exclusions"
        ),
        "three_mode_shared_subset_summary_rows": "three_mode_shared_subset_summary",
        "three_mode_conditioning_exclusion_rows": "three_mode_conditioning_exclusions",
    }
    for figure_key, table_key in table_links.items():
        if figure_data[figure_key] != tables.get(table_key):
            raise ValueError(
                f"analysis.figure_data.{figure_key} must equal analysis.tables.{table_key}."
            )
    panels = _five_slots(figure_data.get("trace_panels"), "analysis.figure_data.trace_panels")
    for index, panel in enumerate(panels):
        panel_path = f"analysis.figure_data.trace_panels[{index}]"
        frequency = _frequency_grid(panel.get("frequency_hz"), f"{panel_path}.frequency_hz")
        for key in (
            "distributed_s21",
            "equivalent_s21",
            "exact_six_s21",
            "vf_best_s21",
            "distributed_minus_equivalent_s21",
            "exact_six_minus_distributed_s21",
            "exact_six_minus_equivalent_s21",
            "vf_best_minus_distributed_s21",
        ):
            _complex_trace(panel.get(key), len(frequency), f"{panel_path}.{key}")
        three_mode_frequency = _frequency_grid(
            panel.get("three_mode_frequency_hz"), f"{panel_path}.three_mode_frequency_hz"
        )
        for key in (
            "target_three_mode_approximation_s21",
            "circuit_three_mode_approximation_s21",
            "circuit_three_mode_approximation_minus_exact_six_s21",
            "target_three_mode_approximation_minus_exact_six_s21",
        ):
            _complex_trace(panel.get(key), len(three_mode_frequency), f"{panel_path}.{key}")
        input_evidence = _mapping(
            slots[index].get("input_evidence"), f"analysis.slots[{index}].input_evidence"
        )
        exact_six = _mapping(
            input_evidence.get("exact_six_coordinate_response"),
            f"analysis.slots[{index}].input_evidence.exact_six_coordinate_response",
        )
        if panel.get("frequency_hz") != exact_six.get("frequency_hz"):
            raise ValueError(f"{panel_path} frequency grid disagrees with exact-six authority.")
        if panel.get("exact_six_s21") != exact_six.get("calibrated_s21"):
            raise ValueError(f"{panel_path}.exact_six_s21 disagrees with exact-six authority.")
    policies = _five_slots(
        figure_data.get("frequency_grid_policies"),
        "analysis.figure_data.frequency_grid_policies",
    )
    expected_open_policy_rows: list[dict[str, Any]] = []
    expected_closed_policy_rows: list[dict[str, Any]] = []
    for index, (slot, policy, panel) in enumerate(zip(slots, policies, panels, strict=True)):
        policy_without_slot = dict(policy)
        del policy_without_slot["slot_hz"]
        frequency = _frequency_grid(
            panel.get("frequency_hz"),
            f"analysis.figure_data.trace_panels[{index}].frequency_hz",
        )
        _validate_grid_policy(
            policy_without_slot,
            frequency,
            f"analysis.figure_data.frequency_grid_policies[{index}]",
        )
        input_evidence = _mapping(
            slot.get("input_evidence"), f"analysis.slots[{index}].input_evidence"
        )
        input_response = _mapping(
            input_evidence.get("response"),
            f"analysis.slots[{index}].input_evidence.response",
        )
        if input_response.get("frequency_grid_policy") != policy_without_slot:
            raise ValueError(
                f"analysis.figure_data.frequency_grid_policies[{index}] disagrees with "
                "the slot input evidence."
            )
        expected_open_policy_rows.extend(
            {"slot_hz": policy["slot_hz"], **dict(_mapping(row, "open_pole_row"))}
            for row in _sequence(policy_without_slot["open_poles"], "open_poles")
        )
        expected_closed_policy_rows.extend(
            {"slot_hz": policy["slot_hz"], **dict(_mapping(row, "closed_pole_row"))}
            for row in _sequence(
                policy_without_slot["closed_pole_exclusions"], "closed_pole_exclusions"
            )
        )
    if figure_data["frequency_grid_policy_open_pole_rows"] != expected_open_policy_rows:
        raise ValueError("analysis.figure_data open-pole policy rows disagree with whole policies.")
    if (
        figure_data["frequency_grid_policy_closed_pole_exclusion_rows"]
        != expected_closed_policy_rows
    ):
        raise ValueError("analysis.figure_data closed-pole rows disagree with whole policies.")

    subset_evidence = _five_slots(
        figure_data.get("three_mode_shared_subset_evidence"),
        "analysis.figure_data.three_mode_shared_subset_evidence",
    )
    expected_subset_summary_rows: list[dict[str, Any]] = []
    expected_subset_exclusion_rows: list[dict[str, Any]] = []
    for index, (slot, evidence, panel) in enumerate(
        zip(slots, subset_evidence, panels, strict=True)
    ):
        raw_frequency = _frequency_grid(
            panel["frequency_hz"], f"analysis.figure_data.trace_panels[{index}].frequency_hz"
        )
        evidence_without_slot = dict(evidence)
        del evidence_without_slot["slot_hz"]
        summary, exclusions = _validate_full_qrp_shared_subset(
            evidence_without_slot,
            raw_frequency,
            f"analysis.figure_data.three_mode_shared_subset_evidence[{index}]",
        )
        input_subset = slot.get("three_mode_shared_primary_grid_subset")
        if input_subset != evidence_without_slot:
            raise ValueError(
                f"analysis.figure_data.three_mode_shared_subset_evidence[{index}] "
                "disagrees with the slot evidence."
            )
        if panel["three_mode_frequency_hz"] != evidence_without_slot["retained_frequency_hz"]:
            raise ValueError(
                f"analysis.figure_data.trace_panels[{index}] three-mode grid disagrees "
                "with the shared subset."
            )
        expected_subset_summary_rows.append({"slot_hz": evidence["slot_hz"], **summary})
        expected_subset_exclusion_rows.extend(
            {"slot_hz": evidence["slot_hz"], **row} for row in exclusions
        )
    if figure_data["three_mode_shared_subset_summary_rows"] != expected_subset_summary_rows:
        raise ValueError("analysis.figure_data three-mode subset summaries disagree with evidence.")
    if figure_data["three_mode_conditioning_exclusion_rows"] != expected_subset_exclusion_rows:
        raise ValueError("analysis.figure_data three-mode exclusions disagree with evidence.")
    for key in (
        "section_refinement_rows",
        "frequency_grid_refinement_rows",
        "frequency_grid_policy_open_pole_rows",
        "frequency_grid_policy_closed_pole_exclusion_rows",
        "three_mode_shared_subset_summary_rows",
    ):
        _require_all_slots_tagged(figure_data[key], f"analysis.figure_data.{key}")


def _validate_primary_run(primary: dict[str, Any]) -> dict[str, str]:
    path = "primary_run"
    _require_string(primary.get("schema_version"), "d3-forward-circuit-run.v2", path)
    _require_string(primary.get("status"), "complete", f"{path}.status")
    _require_string(
        primary.get("bare_fit_node_state"),
        "disabled_not_implemented",
        f"{path}.bare_fit_node_state",
    )
    provenance = _mapping(primary.get("provenance"), f"{path}.provenance")
    _require_string(provenance.get("q2d_route"), PUBLIC_Q2D_ROUTE, f"{path}.provenance.q2d_route")
    slots = _five_slots(primary.get("slots"), f"{path}.slots")
    identities: list[tuple[str, str, str]] = []
    for index, slot in enumerate(slots):
        slot_path = f"{path}.slots[{index}]"
        response = _mapping(slot.get("response"), f"{slot_path}.response")
        _require_string(
            response.get("contract_id"),
            "d3-conservative-forward-response-v1",
            f"{slot_path}.response.contract_id",
        )
        frequency = _frequency_grid(
            response.get("frequency_hz"), f"{slot_path}.response.frequency_hz"
        )
        _validate_exact_six_response(
            slot.get("exact_six_coordinate_response"),
            frequency,
            f"{slot_path}.exact_six_coordinate_response",
        )
        _validate_grid_policy(
            response.get("frequency_grid_policy"),
            frequency,
            f"{slot_path}.response.frequency_grid_policy",
        )
        for key in (
            "calibrated_distributed_s21",
            "calibrated_equivalent_s21",
            "raw_distributed_s21",
            "raw_equivalent_s21",
            "feedline_reference_s21",
            "distributed_z21_ohm",
            "equivalent_z21_ohm",
        ):
            _complex_trace(response.get(key), len(frequency), f"{slot_path}.response.{key}")
        slot_provenance = _mapping(slot.get("provenance"), f"{slot_path}.provenance")
        identity = (
            _nonempty_string(slot_provenance.get("case_id"), f"{slot_path}.provenance.case_id"),
            _sha256(
                slot_provenance.get("q2d_pair_artifact_sha256"),
                f"{slot_path}.provenance.q2d_pair_artifact_sha256",
            ),
            _sha256(
                slot_provenance.get("q2d_single_artifact_sha256"),
                f"{slot_path}.provenance.q2d_single_artifact_sha256",
            ),
        )
        identities.append(identity)
    if any(identity != identities[0] for identity in identities[1:]):
        raise ValueError("primary_run five slots do not share one public Q2D identity.")
    return dict(
        zip(
            ("case_id", "q2d_pair_artifact_sha256", "q2d_single_artifact_sha256"),
            identities[0],
            strict=True,
        )
    )


def _validate_grid_policy(value: Any, frequency_hz: np.ndarray, path: str) -> None:
    policy = _mapping(value, path)
    _require_exact_keys(policy, _GRID_POLICY_KEYS, path)
    _require_string(
        policy["contract_id"], "d3-open-closed-pole-aware-frequency-grid.v2", f"{path}.contract_id"
    )
    _require_string(
        policy["open_pole_center_sampling_policy"],
        "resolved_center__subfloor_symmetric_half_step__closed_exclusion_union_may_override",
        f"{path}.open_pole_center_sampling_policy",
    )
    _require_string(
        policy["closed_pole_exclusion_policy"],
        "lossless_closed_z_pole__symmetric_adaptive_power_of_two_ordinary_closure_exclusion",
        f"{path}.closed_pole_exclusion_policy",
    )
    _positive_real(
        policy["requested_samples_per_linewidth"],
        f"{path}.requested_samples_per_linewidth",
    )
    linewidth_floor_hz = _positive_real(policy["linewidth_floor_hz"], f"{path}.linewidth_floor_hz")
    maximum_intervals = _positive_int(
        policy["maximum_local_intervals_per_open_pole"],
        f"{path}.maximum_local_intervals_per_open_pole",
    )
    open_rows = _sequence(policy["open_poles"], f"{path}.open_poles")
    if len(open_rows) != 3:
        raise ValueError(f"{path}.open_poles must contain exactly three rows.")
    open_source_indices = set()
    for index, raw_row in enumerate(open_rows):
        row_path = f"{path}.open_poles[{index}]"
        row = _mapping(raw_row, row_path)
        _require_exact_keys(row, _GRID_OPEN_KEYS, row_path)
        source_index = _nonnegative_int(row["source_index"], f"{row_path}.source_index")
        open_source_indices.add(source_index)
        center_hz = _positive_real(row["pole_frequency_hz"], f"{row_path}.pole_frequency_hz")
        linewidth_hz = _nonnegative_real(row["pole_linewidth_hz"], f"{row_path}.pole_linewidth_hz")
        effective_hz = _positive_real(
            row["effective_linewidth_hz"], f"{row_path}.effective_linewidth_hz"
        )
        if effective_hz != max(linewidth_hz, linewidth_floor_hz):
            raise ValueError(f"{row_path}.effective_linewidth_hz is inconsistent.")
        planned_step_hz = _positive_real(
            row["planned_local_step_hz"], f"{row_path}.planned_local_step_hz"
        )
        planned_count = _positive_int(
            row["planned_local_sample_count"], f"{row_path}.planned_local_sample_count"
        )
        retained_count = _nonnegative_int(
            row["retained_planned_local_sample_count"],
            f"{row_path}.retained_planned_local_sample_count",
        )
        if planned_count > maximum_intervals + 1 or retained_count > planned_count:
            raise ValueError(f"{row_path} local sample counts are inconsistent.")
        _require_numeric_close(
            _nonnegative_real(
                row["planned_samples_per_physical_linewidth"],
                f"{row_path}.planned_samples_per_physical_linewidth",
            ),
            linewidth_hz / planned_step_hz,
            f"{row_path}.planned_samples_per_physical_linewidth",
        )
        _require_numeric_close(
            _positive_real(
                row["planned_samples_per_effective_linewidth"],
                f"{row_path}.planned_samples_per_effective_linewidth",
            ),
            effective_hz / planned_step_hz,
            f"{row_path}.planned_samples_per_effective_linewidth",
        )
        center_sampled = row["center_sampled"]
        if not isinstance(center_sampled, bool):
            raise ValueError(f"{row_path}.center_sampled must be Boolean.")
        actual_center_sampled = _report_grid_contains(frequency_hz, center_hz)
        if center_sampled != actual_center_sampled:
            raise ValueError(f"{row_path}.center_sampled disagrees with the actual grid.")
        _require_numeric_close(
            _nonnegative_real(
                row["minimum_center_detuning_hz"],
                f"{row_path}.minimum_center_detuning_hz",
            ),
            float(np.min(np.abs(frequency_hz - center_hz))),
            f"{row_path}.minimum_center_detuning_hz",
        )
    if len(open_source_indices) != 3:
        raise ValueError(f"{path}.open_poles source indices must be unique.")

    closed_rows = _sequence(policy["closed_pole_exclusions"], f"{path}.closed_pole_exclusions")
    if len(closed_rows) != 12:
        raise ValueError(f"{path}.closed_pole_exclusions must contain exactly twelve rows.")
    identities = set()
    for index, raw_row in enumerate(closed_rows):
        row_path = f"{path}.closed_pole_exclusions[{index}]"
        row = _mapping(raw_row, row_path)
        _require_exact_keys(row, _GRID_CLOSED_KEYS, row_path)
        role = _nonempty_string(row["model_role"], f"{row_path}.model_role")
        if role not in {"distributed", "equivalent"}:
            raise ValueError(f"{row_path}.model_role must exclude feedline_reference.")
        section = _positive_real(row["section_length_m"], f"{row_path}.section_length_m")
        if section not in {40.0e-6, 80.0e-6}:
            raise ValueError(f"{row_path}.section_length_m must be 40 or 80 um.")
        source_index = _nonnegative_int(row["source_index"], f"{row_path}.source_index")
        identities.add((role, section, source_index))
        scale_steps = _nonnegative_int(
            row["exclusion_scale_steps"], f"{row_path}.exclusion_scale_steps"
        )
        if scale_steps > 6:
            raise ValueError(f"{row_path}.exclusion_scale_steps exceeds the finite cap.")
        radius_hz = _positive_real(
            row["exclusion_half_width_hz"], f"{row_path}.exclusion_half_width_hz"
        )
        if radius_hz != linewidth_floor_hz * (2.0**scale_steps):
            raise ValueError(f"{row_path}.exclusion_half_width_hz is inconsistent.")
        center_hz = _positive_real(row["pole_frequency_hz"], f"{row_path}.pole_frequency_hz")
        if row["center_sampled"] is not False:
            raise ValueError(f"{row_path}.center_sampled must be false.")
        actual_minimum = float(np.min(np.abs(frequency_hz - center_hz)))
        declared_minimum = _nonnegative_real(
            row["minimum_center_detuning_hz"], f"{row_path}.minimum_center_detuning_hz"
        )
        _require_numeric_close(
            declared_minimum, actual_minimum, f"{row_path}.minimum_center_detuning_hz"
        )
        if actual_minimum + 16.0 * math.ulp(max(abs(center_hz), linewidth_floor_hz)) < radius_hz:
            raise ValueError(f"{row_path} violates its adaptive exclusion radius.")
        mode_residual = _nonnegative_real(row["mode_residual"], f"{row_path}.mode_residual")
        if mode_residual > 1.0e-9:
            raise ValueError(f"{row_path}.mode_residual exceeds its bound.")
        for key in (
            "negative_boundary_max_normalized_closure_ratio",
            "positive_boundary_max_normalized_closure_ratio",
        ):
            ratio = _nonnegative_real(row[key], f"{row_path}.{key}")
            if ratio > 1.0:
                raise ValueError(f"{row_path}.{key} must be within [0, 1].")
        for key in _GRID_CLOSED_KEYS:
            if key.endswith("_sha256"):
                _sha256(row[key], f"{row_path}.{key}")
    expected_identities = {
        (role, section, source_index)
        for role in ("distributed", "equivalent")
        for section in (40.0e-6, 80.0e-6)
        for source_index in range(3)
    }
    if identities != expected_identities:
        raise ValueError(
            f"{path}.closed_pole_exclusions must cover dist/equiv modes 0..2 at 40/80 um."
        )


def _require_numeric_close(actual: float, expected: float, path: str) -> None:
    tolerance = 256.0 * np.finfo(float).eps * max(abs(actual), abs(expected), 1.0)
    if abs(actual - expected) > tolerance:
        raise ValueError(f"{path} disagrees with its arithmetic source.")


def _report_grid_contains(frequency_hz: np.ndarray, value_hz: float) -> bool:
    tolerance = 16.0 * math.ulp(max(abs(value_hz), float(np.max(np.abs(frequency_hz))), 1.0))
    return bool(np.any(np.abs(frequency_hz - value_hz) <= tolerance))


def _validate_full_qrp_shared_subset(
    value: Any,
    source_frequency_hz: np.ndarray,
    path: str,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    evidence = _mapping(value, path)
    _require_exact_keys(evidence, _FULL_QRP_SUBSET_KEYS, path)
    _require_string(
        evidence["contract_id"],
        "d3-three-mode-shared-primary-grid-conditioning-subset.v1",
        f"{path}.contract_id",
    )
    _require_string(
        evidence["source_grid_role"],
        "raw_distributed_response_and_vf_full_grid",
        f"{path}.source_grid_role",
    )
    _require_string(
        evidence["subset_policy"],
        (
            "retain_exact_primary_samples_only_when_target_and_circuit_normalized_"
            "spectral_backward_bounds_are_at_or_below_the_immutable_domain_limit"
        ),
        f"{path}.subset_policy",
    )
    if evidence["interpolation_used"] is not False:
        raise ValueError(f"{path}.interpolation_used must be false.")
    if evidence["physical_mode_identity_claim"] is not False:
        raise ValueError(f"{path}.physical_mode_identity_claim must be false.")
    limit = _positive_real(
        evidence["maximum_allowed_normalized_spectral_backward_bound"],
        f"{path}.maximum_allowed_normalized_spectral_backward_bound",
    )
    if limit != 1.0e-8:
        raise ValueError(f"{path} must retain the immutable three-mode domain limit 1e-8.")
    source_count = _positive_int(evidence["source_sample_count"], f"{path}.source_sample_count")
    if source_count != len(source_frequency_hz):
        raise ValueError(f"{path}.source_sample_count disagrees with the raw primary grid.")
    _sha256(
        evidence["source_frequency_semantic_sha256"],
        f"{path}.source_frequency_semantic_sha256",
    )
    retained_indices = [
        _nonnegative_int(item, f"{path}.retained_source_indices[{index}]")
        for index, item in enumerate(
            _sequence(evidence["retained_source_indices"], f"{path}.retained_source_indices")
        )
    ]
    if (
        len(retained_indices) < 2
        or retained_indices != sorted(set(retained_indices))
        or retained_indices[-1] >= source_count
    ):
        raise ValueError(f"{path}.retained_source_indices must be sorted, unique, and in range.")
    retained_frequency_hz = _frequency_grid(
        evidence["retained_frequency_hz"], f"{path}.retained_frequency_hz"
    )
    if not np.array_equal(retained_frequency_hz, source_frequency_hz[retained_indices]):
        raise ValueError(f"{path}.retained_frequency_hz is not the exact indexed raw subset.")
    _sha256(
        evidence["retained_frequency_semantic_sha256"],
        f"{path}.retained_frequency_semantic_sha256",
    )
    retained_count = _positive_int(
        evidence["retained_sample_count"], f"{path}.retained_sample_count"
    )
    if retained_count != len(retained_indices):
        raise ValueError(f"{path}.retained_sample_count disagrees with retained indices.")
    retained_fraction = _positive_real(evidence["retained_fraction"], f"{path}.retained_fraction")
    if retained_fraction != retained_count / source_count:
        raise ValueError(f"{path}.retained_fraction disagrees with its exact counts.")

    owner_diagnostics = _mapping(evidence["owner_diagnostics"], f"{path}.owner_diagnostics")
    expected_owners = {
        "target_substitution_three_mode_approximation",
        "circuit_three_mode_approximation",
    }
    if set(owner_diagnostics) != expected_owners:
        raise ValueError(f"{path}.owner_diagnostics must contain target and circuit exactly.")
    observed_by_owner = {}
    for owner in sorted(expected_owners):
        owner_path = f"{path}.owner_diagnostics.{owner}"
        diagnostic = _mapping(owner_diagnostics[owner], owner_path)
        _require_exact_keys(
            diagnostic,
            {
                "spectral_backward_error_hz",
                "right_eigenvector_condition",
                "observed_maximum_normalized_spectral_backward_bound",
            },
            owner_path,
        )
        _nonnegative_real(
            diagnostic["spectral_backward_error_hz"],
            f"{owner_path}.spectral_backward_error_hz",
        )
        condition = _positive_real(
            diagnostic["right_eigenvector_condition"],
            f"{owner_path}.right_eigenvector_condition",
        )
        if condition < 1.0:
            raise ValueError(f"{owner_path}.right_eigenvector_condition must be at least one.")
        observed_by_owner[owner] = _nonnegative_real(
            diagnostic["observed_maximum_normalized_spectral_backward_bound"],
            f"{owner_path}.observed_maximum_normalized_spectral_backward_bound",
        )

    exclusions: list[dict[str, Any]] = []
    excluded_indices = set()
    observed_excluded_max = {owner: 0.0 for owner in expected_owners}
    for index, raw_row in enumerate(
        _sequence(evidence["excluded_sample_owner_rows"], f"{path}.excluded_sample_owner_rows")
    ):
        row_path = f"{path}.excluded_sample_owner_rows[{index}]"
        row = dict(_mapping(raw_row, row_path))
        _require_exact_keys(row, _FULL_QRP_EXCLUSION_KEYS, row_path)
        source_index = _nonnegative_int(row["source_index"], f"{row_path}.source_index")
        if source_index >= source_count or source_index in retained_indices:
            raise ValueError(f"{row_path}.source_index must identify an excluded raw sample.")
        frequency_hz = _positive_real(row["frequency_hz"], f"{row_path}.frequency_hz")
        if frequency_hz != float(source_frequency_hz[source_index]):
            raise ValueError(f"{row_path}.frequency_hz disagrees with its raw source index.")
        owner = _nonempty_string(row["owner_model"], f"{row_path}.owner_model")
        if owner not in expected_owners:
            raise ValueError(f"{row_path}.owner_model is invalid.")
        normalized_bound = _positive_real(
            row["normalized_spectral_backward_bound"],
            f"{row_path}.normalized_spectral_backward_bound",
        )
        if normalized_bound <= limit:
            raise ValueError(f"{row_path} must exceed the immutable domain limit.")
        if row["maximum_allowed_normalized_spectral_backward_bound"] != limit:
            raise ValueError(f"{row_path} has an inconsistent domain limit.")
        _require_string(
            row["conditioning_reason"],
            "normalized_spectral_backward_bound_exceeds_immutable_domain_limit",
            f"{row_path}.conditioning_reason",
        )
        nearest_index = _nonnegative_int(
            row["nearest_pole_array_index_for_numerical_reference_only"],
            f"{row_path}.nearest_pole_array_index_for_numerical_reference_only",
        )
        if nearest_index > 2:
            raise ValueError(f"{row_path} nearest pole array index must be 0, 1, or 2.")
        nearest_frequency_hz = _positive_real(
            row["nearest_pole_frequency_hz"], f"{row_path}.nearest_pole_frequency_hz"
        )
        detuning_hz = _finite_real(
            row["nearest_pole_detuning_hz"], f"{row_path}.nearest_pole_detuning_hz"
        )
        _require_numeric_close(
            detuning_hz,
            frequency_hz - nearest_frequency_hz,
            f"{row_path}.nearest_pole_detuning_hz",
        )
        _nonnegative_real(row["nearest_pole_linewidth_hz"], f"{row_path}.nearest_pole_linewidth_hz")
        _nonnegative_real(
            row["nearest_pole_residue_abs_hz"], f"{row_path}.nearest_pole_residue_abs_hz"
        )
        if row["physical_mode_identity_claim"] is not False:
            raise ValueError(f"{row_path}.physical_mode_identity_claim must be false.")
        excluded_indices.add(source_index)
        observed_excluded_max[owner] = max(observed_excluded_max[owner], normalized_bound)
        exclusions.append(row)
    if excluded_indices != set(range(source_count)) - set(retained_indices):
        raise ValueError(f"{path} exclusions must exactly explain the shared subset complement.")
    excluded_unique_count = _nonnegative_int(
        evidence["excluded_unique_source_sample_count"],
        f"{path}.excluded_unique_source_sample_count",
    )
    if excluded_unique_count != len(excluded_indices):
        raise ValueError(f"{path}.excluded_unique_source_sample_count is inconsistent.")
    for owner, maximum in observed_excluded_max.items():
        if maximum > observed_by_owner[owner]:
            raise ValueError(f"{path} excluded owner rows exceed the owner diagnostic maximum.")
    summary = {
        "source_sample_count": source_count,
        "retained_sample_count": retained_count,
        "retained_fraction": retained_fraction,
        "excluded_unique_source_sample_count": excluded_unique_count,
        "excluded_owner_row_count": len(exclusions),
        "target_observed_maximum_normalized_spectral_backward_bound": observed_by_owner[
            "target_substitution_three_mode_approximation"
        ],
        "circuit_observed_maximum_normalized_spectral_backward_bound": observed_by_owner[
            "circuit_three_mode_approximation"
        ],
    }
    return summary, exclusions


def _validate_initializer(initializer: dict[str, Any]) -> None:
    path = "spring_initializer"
    _require_string(initializer.get("schema_version"), "purcell.spring2025-initial-spec.v1", path)
    _require_string(initializer.get("status"), "initializer_only", f"{path}.status")
    source = _mapping(initializer.get("source"), f"{path}.source")
    if "Spring" not in _nonempty_string(
        source.get("paper_identity"), f"{path}.source.paper_identity"
    ):
        raise ValueError("spring_initializer.source.paper_identity must identify Spring et al.")
    if "initializer only" not in _nonempty_string(
        source.get("provenance"), f"{path}.source.provenance"
    ):
        raise ValueError("spring_initializer source must remain initializer-only evidence.")
    slots = _five_slots(initializer.get("slots"), f"{path}.slots")
    for index, slot in enumerate(slots):
        _require_string(slot.get("status"), "initializer_only", f"{path}.slots[{index}].status")
        targets = _mapping(
            slot.get("target_frequencies_hz"), f"{path}.slots[{index}].target_frequencies_hz"
        )
        for key in (
            "readout_loaded_bare_hz",
            "filter_loaded_bare_hz",
            "intrinsic_notch_hz",
        ):
            _positive_real(targets.get(key), f"{path}.slots[{index}].{key}")


def _validate_q2d_artifact(artifact: dict[str, Any], *, role: str) -> list[dict[str, Any]]:
    path = f"q2d_{role}"
    _require_exact_keys(
        artifact,
        {"schema_version", "artifact_status", "metadata", "cases"},
        path,
    )
    _require_string(artifact["schema_version"], Q2D_ARTIFACT_SCHEMA, f"{path}.schema_version")
    _require_string(artifact["artifact_status"], "complete", f"{path}.artifact_status")
    metadata = _mapping(artifact["metadata"], f"{path}.metadata")
    expected = {
        "coupled_pair": {
            "case_schema": "orpen-q2d-coupled-pair-maxwell-lc.v1",
            "topology": "q2d-same-face-upper-ground-clearance.v1",
            "conductors": ["T1", "T2"],
            "count": 9,
            "dimension": 2,
        },
        "single_reference": {
            "case_schema": "orpen-q2d-single-reference-maxwell-lc.v1",
            "topology": "q2d-single-reference-upper-ground-clearance.v1",
            "conductors": ["T1"],
            "count": 3,
            "dimension": 1,
        },
    }.get(role)
    if expected is None:
        raise ValueError(f"Unsupported public Q2D role {role!r}.")
    _require_string(metadata.get("case_role"), role, f"{path}.metadata.case_role")
    _require_string(
        metadata.get("case_schema_version"),
        cast(str, expected["case_schema"]),
        f"{path}.metadata.case_schema_version",
    )
    _require_string(
        metadata.get("topology_contract"),
        cast(str, expected["topology"]),
        f"{path}.metadata.topology_contract",
    )
    if metadata.get("conductor_order") != expected["conductors"]:
        raise ValueError(f"{path}.metadata.conductor_order is incompatible.")
    _require_string(metadata.get("reference_group"), "Ground", f"{path}.metadata.reference_group")
    run_provenance = _mapping(metadata.get("run_provenance"), f"{path}.metadata.run_provenance")
    _require_string(
        run_provenance.get("selected_case_status"),
        "solve_complete",
        f"{path}.metadata.run_provenance.selected_case_status",
    )
    _nonempty_string(run_provenance.get("run_id"), f"{path}.metadata.run_provenance.run_id")
    source_integrity = _mapping(
        metadata.get("source_integrity"), f"{path}.metadata.source_integrity"
    )
    _require_string(
        source_integrity.get("algorithm"), "sha256", f"{path}.metadata.source_integrity.algorithm"
    )
    if source_integrity.get("all_sources_hashed") is not True:
        raise ValueError(f"{path}.metadata.source_integrity.all_sources_hashed must be true.")
    integrity_cases = _mapping(
        source_integrity.get("cases"), f"{path}.metadata.source_integrity.cases"
    )

    raw_cases = _sequence(artifact["cases"], f"{path}.cases")
    if len(raw_cases) != expected["count"]:
        raise ValueError(f"{path}.cases must contain exactly {expected['count']} cases.")
    cases = [
        dict(_mapping(value, f"{path}.cases[{index}]")) for index, value in enumerate(raw_cases)
    ]
    case_ids: list[str] = []
    for index, case in enumerate(cases):
        case_path = f"{path}.cases[{index}]"
        case_id = _nonempty_string(case.get("id"), f"{case_path}.id")
        case_ids.append(case_id)
        _require_string(
            case.get("schema_version"),
            cast(str, expected["case_schema"]),
            f"{case_path}.schema_version",
        )
        _require_string(case.get("case_role"), role, f"{case_path}.case_role")
        parameters = _mapping(case.get("parameters"), f"{case_path}.parameters")
        _require_string(parameters.get("case_role"), role, f"{case_path}.parameters.case_role")
        for key in (
            "trace_width_um",
            "trace_gap_um",
            "upper_ground_clearance_width_um",
            "flip_chip_gap_height_um",
            "d0_die_thickness_um",
            "d1_die_thickness_um",
            "air_height_um",
            "ground_width_um",
            "metal_thickness_um",
        ):
            _positive_real(parameters.get(key), f"{case_path}.parameters.{key}")
        if role == "coupled_pair":
            _positive_real(
                parameters.get("inter_trace_ground_width_um"),
                f"{case_path}.parameters.inter_trace_ground_width_um",
            )
        elif parameters.get("inter_trace_ground_width_um") is not None:
            raise ValueError(f"{case_path}.parameters.inter_trace_ground_width_um must be null.")
        _nonempty_string(
            parameters.get("adaptive_frequency"), f"{case_path}.parameters.adaptive_frequency"
        )
        topology = _mapping(case.get("topology"), f"{case_path}.topology")
        _validate_q2d_topology(
            topology,
            path=f"{case_path}.topology",
            schema=cast(str, expected["topology"]),
            trace_names=cast(list[str], expected["conductors"]),
            clearance_um=_positive_real(
                parameters["upper_ground_clearance_width_um"],
                f"{case_path}.parameters.upper_ground_clearance_width_um",
            ),
        )
        dimension = cast(int, expected["dimension"])
        _matrix(case.get("l_matrix_h_per_m"), dimension, f"{case_path}.l_matrix_h_per_m")
        capacitance = _matrix(
            case.get("c_matrix_f_per_m"), dimension, f"{case_path}.c_matrix_f_per_m"
        )
        if np.any(np.sum(capacitance, axis=1) <= 0.0):
            raise ValueError(f"{case_path}.c_matrix_f_per_m Maxwell row sums must be positive.")
        integrity_rows = _sequence(integrity_cases.get(case_id), f"{path}.integrity.{case_id}")
        if not integrity_rows:
            raise ValueError(f"{path} source integrity is empty for {case_id}.")
        for row_index, raw_record in enumerate(integrity_rows):
            record_path = f"{path}.integrity.{case_id}[{row_index}]"
            record = _mapping(raw_record, record_path)
            _nonempty_string(record.get("path"), f"{record_path}.path")
            _positive_int(record.get("size_bytes"), f"{record_path}.size_bytes")
            _sha256(record.get("sha256"), f"{record_path}.sha256")
    if len(set(case_ids)) != len(case_ids):
        raise ValueError(f"{path}.cases IDs must be unique.")
    if run_provenance.get("case_ids") != case_ids:
        raise ValueError(f"{path}.metadata.run_provenance.case_ids must match case order.")
    if set(integrity_cases) != set(case_ids):
        raise ValueError(f"{path}.metadata.source_integrity.cases must cover the case IDs exactly.")
    return cases


def _validate_q2d_topology(
    topology: Mapping[str, Any],
    *,
    path: str,
    schema: str,
    trace_names: list[str],
    clearance_um: float,
) -> None:
    _require_string(topology.get("schema_version"), schema, f"{path}.schema_version")
    _require_string(topology.get("resonator_die"), "D0", f"{path}.resonator_die")
    _require_string(topology.get("resonator_face"), "top", f"{path}.resonator_face")
    if topology.get("trace_names") != trace_names:
        raise ValueError(f"{path}.trace_names must be {trace_names!r}.")
    _require_string(topology.get("upper_die"), "D1", f"{path}.upper_die")
    if topology.get("upper_die_substrate_present") is not True:
        raise ValueError(f"{path}.upper_die_substrate_present must be true.")
    _require_string(topology.get("upper_ground_face"), "bottom", f"{path}.upper_ground_face")
    declared_clearance = _positive_real(
        topology.get("upper_ground_clearance_width_um"),
        f"{path}.upper_ground_clearance_width_um",
    )
    if declared_clearance != clearance_um:
        raise ValueError(f"{path} clearance disagrees with the case parameters.")
    _require_string(
        topology.get("upper_ground_metal_policy"),
        "removed_only_within_local_clearance",
        f"{path}.upper_ground_metal_policy",
    )
    _require_string(topology.get("reference_group"), "Ground", f"{path}.reference_group")


def _select_q2d_cases(
    combined_case_id: str,
    pair_cases: Sequence[dict[str, Any]],
    single_cases: Sequence[dict[str, Any]],
) -> tuple[dict[str, Any], dict[str, Any]]:
    matches = [
        (pair, single)
        for pair in pair_cases
        for single in single_cases
        if f"{pair['id']}__{single['id']}" == combined_case_id
    ]
    if len(matches) != 1:
        raise ValueError(
            "Primary case_id must identify exactly one public Q2D pair/single combination."
        )
    pair, single = matches[0]
    pair_parameters = _mapping(pair["parameters"], "selected_pair.parameters")
    single_parameters = _mapping(single["parameters"], "selected_single.parameters")
    for key in (
        "trace_width_um",
        "trace_gap_um",
        "upper_ground_clearance_width_um",
        "flip_chip_gap_height_um",
        "d0_die_thickness_um",
        "d1_die_thickness_um",
        "air_height_um",
        "ground_width_um",
        "metal_thickness_um",
        "adaptive_frequency",
    ):
        if pair_parameters.get(key) != single_parameters.get(key):
            raise ValueError(f"Selected public Q2D pair/single cases disagree on {key}.")
    return pair, single


def _validate_cross_section(
    cross_section: dict[str, Any],
    cross_section_path: Path,
    cross_section_sha256: str,
    cross_section_size: int,
    pair_artifact: dict[str, Any],
    selected_pair: dict[str, Any],
) -> None:
    path = "cross_section"
    _require_exact_keys(cross_section, {"schema_version", "stack", "face_patterns", "region"}, path)
    _require_string(cross_section["schema_version"], CROSS_SECTION_SCHEMA, f"{path}.schema_version")
    region = _mapping(cross_section["region"], f"{path}.region")
    _require_string(region.get("name"), "Vacuum", f"{path}.region.name")
    _require_string(region.get("material"), "Vacuum", f"{path}.region.material")
    parameters = _mapping(selected_pair["parameters"], "selected_pair.parameters")

    stack = _sequence(cross_section["stack"], f"{path}.stack")
    if len(stack) != 5:
        raise ValueError("cross_section.stack must retain air/D0/gap/D1/air exactly.")
    expected_stack = (
        ("air", None, "height_um", parameters["air_height_um"]),
        ("die", "D0", "thickness_um", parameters["d0_die_thickness_um"]),
        ("die_gap", None, "height_um", parameters["flip_chip_gap_height_um"]),
        ("die", "D1", "thickness_um", parameters["d1_die_thickness_um"]),
        ("air", None, "height_um", parameters["air_height_um"]),
    )
    for index, (kind, die_id, size_key, expected_size) in enumerate(expected_stack):
        layer = _mapping(stack[index], f"{path}.stack[{index}]")
        _require_string(layer.get("kind"), kind, f"{path}.stack[{index}].kind")
        if die_id is not None:
            _require_string(layer.get("id"), die_id, f"{path}.stack[{index}].id")
            _nonempty_string(layer.get("material"), f"{path}.stack[{index}].material")
        size = _positive_real(layer.get(size_key), f"{path}.stack[{index}].{size_key}")
        if size != expected_size:
            raise ValueError(f"cross_section.stack[{index}] disagrees with selected Q2D geometry.")

    patterns = _sequence(cross_section["face_patterns"], f"{path}.face_patterns")
    if len(patterns) != 2:
        raise ValueError("cross_section.face_patterns must contain exactly D0 top and D1 bottom.")
    by_face: dict[tuple[str, str], Mapping[str, Any]] = {}
    for index, raw_pattern in enumerate(patterns):
        pattern = _mapping(raw_pattern, f"{path}.face_patterns[{index}]")
        key = (
            _nonempty_string(pattern.get("die"), f"{path}.face_patterns[{index}].die"),
            _nonempty_string(pattern.get("face"), f"{path}.face_patterns[{index}].face"),
        )
        if key in by_face:
            raise ValueError(f"cross_section has duplicate face pattern {key}.")
        by_face[key] = pattern
        _require_string(
            pattern.get("ground_assignment_name"),
            "Ground",
            f"{path}.face_patterns[{index}].ground_assignment_name",
        )
        _positive_real(
            pattern.get("metal_thickness_um"),
            f"{path}.face_patterns[{index}].metal_thickness_um",
        )
    if set(by_face) != {("D0", "top"), ("D1", "bottom")}:
        raise ValueError("cross_section must retain D0 top and D1 bottom face semantics.")
    d0_segments = _validate_segments(
        by_face[("D0", "top")],
        "cross_section.D0.top",
        ("ground", "gap", "trace", "gap", "ground", "gap", "trace", "gap", "ground"),
    )
    if [segment.get("name") for segment in d0_segments if segment["kind"] == "trace"] != [
        "T1",
        "T2",
    ]:
        raise ValueError("cross_section D0 top traces must be exactly T1 and T2.")
    expected_d0_widths = (
        parameters["ground_width_um"],
        parameters["trace_gap_um"],
        parameters["trace_width_um"],
        parameters["trace_gap_um"],
        parameters["inter_trace_ground_width_um"],
        parameters["trace_gap_um"],
        parameters["trace_width_um"],
        parameters["trace_gap_um"],
        parameters["ground_width_um"],
    )
    if tuple(segment["width_um"] for segment in d0_segments) != expected_d0_widths:
        raise ValueError("cross_section D0 top pattern disagrees with selected Q2D geometry.")
    d1_segments = _validate_segments(
        by_face[("D1", "bottom")],
        "cross_section.D1.bottom",
        ("ground", "gap", "ground"),
    )
    clearance = d1_segments[1]
    _require_string(
        clearance.get("role"),
        "upper_ground_clearance",
        "cross_section.D1.bottom.segments[1].role",
    )
    if clearance["width_um"] != parameters["upper_ground_clearance_width_um"]:
        raise ValueError("cross_section upper-ground clearance width disagrees with Q2D.")
    total_width = sum(float(segment["width_um"]) for segment in d0_segments)
    if not math.isclose(
        sum(float(segment["width_um"]) for segment in d1_segments),
        total_width,
        rel_tol=0.0,
        abs_tol=1.0e-12,
    ):
        raise ValueError("cross_section D0 and D1 face patterns must span the same width.")

    metadata = _mapping(pair_artifact["metadata"], "q2d_pair.metadata")
    integrity = _mapping(metadata["source_integrity"], "q2d_pair.metadata.source_integrity")
    integrity_cases = _mapping(integrity["cases"], "q2d_pair.metadata.source_integrity.cases")
    records = _sequence(
        integrity_cases[selected_pair["id"]],
        f"q2d_pair.metadata.source_integrity.cases.{selected_pair['id']}",
    )
    matching_records = []
    for raw_record in records:
        record = _mapping(raw_record, "selected_pair.source_integrity")
        record_path = PurePosixPath(
            _nonempty_string(record.get("path"), "selected_pair.source_integrity.path")
        )
        if record_path.name == cross_section_path.name:
            matching_records.append(record)
    if len(matching_records) != 1:
        raise ValueError("Selected pair source integrity must identify this cross-section once.")
    record = matching_records[0]
    if _sha256(record.get("sha256"), "selected_pair.cross_section.sha256") != cross_section_sha256:
        raise ValueError("Cross-section raw-byte SHA-256 disagrees with pair source integrity.")
    if _positive_int(record.get("size_bytes"), "selected_pair.cross_section.size_bytes") != (
        cross_section_size
    ):
        raise ValueError("Cross-section byte size disagrees with pair source integrity.")


def _validate_segments(
    pattern: Mapping[str, Any], path: str, expected_kinds: tuple[str, ...]
) -> list[dict[str, Any]]:
    rows = _sequence(pattern.get("segments"), f"{path}.segments")
    if len(rows) != len(expected_kinds):
        raise ValueError(f"{path}.segments must have kinds {expected_kinds!r}.")
    result = []
    for index, (raw_segment, expected_kind) in enumerate(zip(rows, expected_kinds, strict=True)):
        segment = dict(_mapping(raw_segment, f"{path}.segments[{index}]"))
        _require_string(segment.get("kind"), expected_kind, f"{path}.segments[{index}].kind")
        segment["width_um"] = _positive_real(
            segment.get("width_um"), f"{path}.segments[{index}].width_um"
        )
        result.append(segment)
    return result


def _validate_cross_source_links(
    *,
    analysis: dict[str, Any],
    primary: dict[str, Any],
    initializer: dict[str, Any],
    primary_sha256: str,
) -> None:
    source = _mapping(analysis["source"], "analysis.source")
    if source["source_payload_sha256"] != primary_sha256:
        raise ValueError("Analyzer source_payload_sha256 does not match the raw primary mapping.")
    primary_provenance = _mapping(primary["provenance"], "primary_run.provenance")
    if source.get("source_artifact_id") != primary_provenance.get("source_artifact_id"):
        raise ValueError("Analyzer source_artifact_id does not match the primary run.")
    analysis_slots = _five_slots(analysis["slots"], "analysis.slots")
    primary_slots = _five_slots(primary["slots"], "primary_run.slots")
    initializer_slots = _five_slots(initializer["slots"], "spring_initializer.slots")
    for index, (analyzed, raw, initialized) in enumerate(
        zip(analysis_slots, primary_slots, initializer_slots, strict=True)
    ):
        evidence = _mapping(
            analyzed.get("input_evidence"), f"analysis.slots[{index}].input_evidence"
        )
        if evidence.get("provenance") != raw.get("provenance"):
            raise ValueError(f"analysis.slots[{index}] provenance disagrees with the primary run.")
        if evidence.get("exact_six_coordinate_response") != raw.get(
            "exact_six_coordinate_response"
        ):
            raise ValueError(
                f"analysis.slots[{index}] exact-six authority disagrees with the primary run."
            )
        analyzed_response = _mapping(
            evidence.get("response"), f"analysis.slots[{index}].input_evidence.response"
        )
        raw_response = _mapping(raw.get("response"), f"primary_run.slots[{index}].response")
        if analyzed_response.get("hashes") != raw_response.get("hashes"):
            raise ValueError(f"analysis.slots[{index}] response hashes disagree with primary.")
        if analyzed_response.get("frequency_grid_policy") != raw_response.get(
            "frequency_grid_policy"
        ):
            raise ValueError(
                f"analysis.slots[{index}] frequency-grid policy disagrees with primary."
            )
        targets = _mapping(
            initialized.get("target_frequencies_hz"),
            f"spring_initializer.slots[{index}].target_frequencies_hz",
        )
        target_three_mode = _mapping(
            analyzed.get("target_substitution_three_mode_approximation"),
            f"analysis.slots[{index}].target_substitution_three_mode_approximation",
        )
        if target_three_mode.get("fr_hz") != targets.get("readout_loaded_bare_hz"):
            raise ValueError(
                f"analysis.slots[{index}] target readout frequency is not initialized."
            )
        if target_three_mode.get("fp_hz") != targets.get("filter_loaded_bare_hz"):
            raise ValueError(f"analysis.slots[{index}] target filter frequency is not initialized.")


def _figure_definitions() -> tuple[_FigureDefinition, ...]:
    return (
        _FigureDefinition(
            "full_qrp_complex_s21",
            "01_full_qrp_complex_s21.png",
            "Diagnostic target and circuit constant-kappa three-mode complex S21",
            ("d3-full-qrp-vf-analysis.v2", "purcell.spring2025-initial-spec.v1"),
            (
                "The target and circuit constant-kappa three-mode approximations use their "
                "shared conditioning-qualified exact subset and are not response authority."
            ),
            _render_full_qrp_complex_s21,
        ),
        _FigureDefinition(
            "full_qrp_three_pole_map",
            "02_full_qrp_three_pole_map.png",
            "Diagnostic constant-kappa three-mode pole map",
            ("d3-full-qrp-vf-analysis.v2",),
            (
                "Three-mode frequency rank is display-only; this diagnostic does not replace "
                "the exact six-coordinate open poles."
            ),
            _render_three_pole_map,
        ),
        _FigureDefinition(
            "public_q2d_cross_section",
            "03_public_q2d_cross_section.png",
            "Public Q2D retained-D1-substrate cross-section",
            (Q2D_ARTIFACT_SCHEMA, CROSS_SECTION_SCHEMA),
            (
                "D1 substrate is retained; only the local bottom-face upper-ground "
                "clearance is removed."
            ),
            _render_cross_section,
        ),
        _FigureDefinition(
            "selected_q2d_lc_matrices",
            "04_selected_q2d_lc_matrices.png",
            "Selected public Q2D Maxwell L/C matrices",
            (Q2D_ARTIFACT_SCHEMA,),
            "Raw selected coupled-pair and single-reference per-unit-length matrices.",
            _render_q2d_heatmaps,
        ),
        _FigureDefinition(
            "distributed_equivalent_complex_response",
            "05_distributed_equivalent_complex_response.png",
            "Exact-six/distributed/equivalent complex S21 and circuit Z21 overlay",
            ("d3-forward-circuit-run.v2",),
            (
                "The exact six-coordinate calibrated S21 is authoritative; Z21 remains the "
                "distributed/equivalent circuit comparison."
            ),
            _render_distributed_equivalent_overlay,
        ),
        _FigureDefinition(
            "section_grid_refinement",
            "06_section_grid_refinement.png",
            "Section and frequency-grid refinement",
            (FIGURE_DATA_SCHEMA,),
            (
                "Slot-tagged refinement plus open/closed-pole-aware policy evidence; "
                "closed source indices do not claim physical identity."
            ),
            _render_refinement,
        ),
        _FigureDefinition(
            "vf_reconstruction_residual",
            "07_vf_reconstruction_residual.png",
            "VF reconstruction and complex residual",
            (FIGURE_DATA_SCHEMA,),
            (
                "The exp(-i2πft) source is conjugated into the s=j2πf VF engine and the "
                "model is conjugated back; complex error norms are invariant and this is not "
                "physical promotion."
            ),
            _render_vf_reconstruction,
        ),
        _FigureDefinition(
            "pole_linewidth_deltas",
            "08_pole_linewidth_deltas.png",
            "Exact-six pole deltas and VF association evidence",
            (FIGURE_DATA_SCHEMA,),
            (
                "Exact-six/VF deltas appear only when cardinality is stable; exact-six versus "
                "distributed deltas occupy the right panels. All rank associations are "
                "display-only."
            ),
            _render_pole_deltas,
        ),
    )


def _render_full_qrp_complex_s21(bundle: EvidenceBundle) -> Figure:
    panels = _figure_panels(bundle)
    figure, axes = plt.subplots(5, 2, figsize=(11.0, 13.0), sharex=False)
    for row_index, panel in enumerate(panels):
        frequency = np.asarray(panel["three_mode_frequency_hz"], dtype=float) / 1.0e9
        target = _complex_trace(
            panel["target_three_mode_approximation_s21"], len(frequency), "target"
        )
        circuit = _complex_trace(
            panel["circuit_three_mode_approximation_s21"], len(frequency), "circuit"
        )
        slot_ghz = float(panel["slot_hz"]) / 1.0e9
        for column, (component, label) in enumerate(((np.real, "Real"), (np.imag, "Imag"))):
            axis = axes[row_index, column]
            axis.plot(frequency, component(target), color="#0072B2", label="Target diagnostic")
            axis.plot(
                frequency,
                component(circuit),
                color="#D55E00",
                linestyle="--",
                label="Circuit diagnostic",
            )
            axis.set_ylabel(f"{slot_ghz:.2f} GHz\n{label}(S21)")
            _style_axis(axis)
    axes[0, 0].legend(loc="best", ncol=2)
    for axis in axes[-1, :]:
        axis.set_xlabel("Frequency (GHz)")
    figure.suptitle(
        "Constant-kappa three-mode diagnostic comparison (not response authority)",
        y=0.995,
    )
    figure.tight_layout()
    return figure


def _render_three_pole_map(bundle: EvidenceBundle) -> Figure:
    slots = _analysis_slots(bundle)
    figure, axes = plt.subplots(1, 2, figsize=(11.0, 4.5))
    styles = {
        "Target": ("#0072B2", "o", "-"),
        "Circuit": ("#D55E00", "x", "--"),
    }
    for view_label, view_key in (
        ("Target", "target_substitution_three_mode_approximation"),
        ("Circuit", "circuit_three_mode_approximation"),
    ):
        color, marker, linestyle = styles[view_label]
        for rank in range(3):
            slot_values = np.asarray([float(slot["slot_hz"]) for slot in slots]) / 1.0e9
            poles = [_mapping(slot[view_key], view_key)["poles"][rank] for slot in slots]
            frequency = np.asarray([float(pole["frequency_hz"]) for pole in poles]) / 1.0e9
            linewidth = np.asarray([float(pole["linewidth_hz"]) for pole in poles]) / 1.0e6
            label = f"{view_label}, rank {rank}"
            axes[0].plot(
                slot_values,
                frequency,
                color=color,
                marker=marker,
                linestyle=linestyle,
                alpha=0.65 + rank * 0.15,
                label=label,
            )
            axes[1].plot(
                slot_values,
                linewidth,
                color=color,
                marker=marker,
                linestyle=linestyle,
                alpha=0.65 + rank * 0.15,
                label=label,
            )
    axes[0].set(xlabel="Slot (GHz)", ylabel="Pole frequency (GHz)")
    axes[1].set(xlabel="Slot (GHz)", ylabel="Linewidth (MHz)")
    axes[1].set_yscale("symlog", linthresh=1.0e-6)
    for axis in axes:
        _style_axis(axis)
    axes[1].legend(loc="best", fontsize=7, ncol=2)
    figure.suptitle("Diagnostic constant-kappa three-mode poles; rank is display-only")
    figure.tight_layout()
    return figure


def _render_cross_section(bundle: EvidenceBundle) -> Figure:
    cross = bundle.payloads["cross_section"]
    patterns = {(pattern["die"], pattern["face"]): pattern for pattern in cross["face_patterns"]}
    d0 = patterns[("D0", "top")]
    d1 = patterns[("D1", "bottom")]
    total_width = sum(float(segment["width_um"]) for segment in d0["segments"])
    x_min = float(d0["x0_um"])
    x_max = x_min + total_width
    figure, axis = plt.subplots(figsize=(12.0, 5.0))
    axis.add_patch(Rectangle((x_min, 0.0), total_width, 1.0, color="#B3D7FF", alpha=0.85))
    axis.add_patch(Rectangle((x_min, 2.0), total_width, 1.0, color="#F6D7A7", alpha=0.9))
    axis.text((x_min + x_max) / 2.0, 0.5, "D0 substrate retained", ha="center", va="center")
    axis.text((x_min + x_max) / 2.0, 2.5, "D1 substrate retained", ha="center", va="center")
    _draw_face_pattern(axis, d0, y=1.0, thickness=0.12, downward=False)
    _draw_face_pattern(axis, d1, y=2.0, thickness=0.12, downward=True)
    clearance = next(
        segment for segment in d1["segments"] if segment.get("role") == "upper_ground_clearance"
    )
    cursor = float(d1["x0_um"])
    for segment in d1["segments"]:
        if segment is clearance:
            center = cursor + float(segment["width_um"]) / 2.0
            axis.annotate(
                "Local upper-ground clearance\n(substrate remains)",
                xy=(center, 1.94),
                xytext=(center, 1.45),
                ha="center",
                arrowprops={"arrowstyle": "->", "color": "#7A3E00"},
            )
            break
        cursor += float(segment["width_um"])
    axis.text(x_min, 1.5, "Vacuum die gap", ha="left", va="center", color="#555555")
    axis.set_xlim(x_min - total_width * 0.02, x_max + total_width * 0.02)
    axis.set_ylim(-0.1, 3.1)
    axis.set_xlabel("Cross-section coordinate (µm; horizontal scale from public metadata)")
    axis.set_yticks([])
    axis.set_title("Public Q2D semantic cross-section (vertical schematic not to scale)")
    axis.legend(
        handles=[
            Patch(color="#6B6B6B", label="Ground metal"),
            Patch(color="#009E73", label="Signal trace"),
            Patch(color="#B3D7FF", label="D0 substrate"),
            Patch(color="#F6D7A7", label="D1 substrate"),
        ],
        loc="upper right",
        ncol=2,
    )
    _style_axis(axis)
    figure.tight_layout()
    return figure


def _draw_face_pattern(
    axis: Any,
    pattern: Mapping[str, Any],
    *,
    y: float,
    thickness: float,
    downward: bool,
) -> None:
    cursor = float(pattern["x0_um"])
    bottom = y - thickness if downward else y
    for segment in pattern["segments"]:
        width = float(segment["width_um"])
        if segment["kind"] in {"ground", "trace"}:
            color = "#6B6B6B" if segment["kind"] == "ground" else "#009E73"
            axis.add_patch(Rectangle((cursor, bottom), width, thickness, color=color))
            if segment["kind"] == "trace":
                axis.text(
                    cursor + width / 2.0,
                    bottom + thickness / 2.0,
                    segment["name"],
                    ha="center",
                    va="center",
                    fontsize=7,
                )
        cursor += width


def _render_q2d_heatmaps(bundle: EvidenceBundle) -> Figure:
    pair = bundle.selected_pair_case
    single = bundle.selected_single_case
    matrices = (
        (np.asarray(pair["l_matrix_h_per_m"]) * 1.0e9, "Pair L (nH/m)", ["T1", "T2"]),
        (np.asarray(pair["c_matrix_f_per_m"]) * 1.0e12, "Pair C (pF/m)", ["T1", "T2"]),
        (np.asarray(single["l_matrix_h_per_m"]) * 1.0e9, "Single L (nH/m)", ["T1"]),
        (np.asarray(single["c_matrix_f_per_m"]) * 1.0e12, "Single C (pF/m)", ["T1"]),
    )
    figure, axes = plt.subplots(2, 2, figsize=(9.0, 7.5))
    for axis, (matrix, title, labels) in zip(axes.flat, matrices, strict=True):
        image = axis.imshow(matrix, cmap="coolwarm", aspect="equal")
        for row in range(matrix.shape[0]):
            for column in range(matrix.shape[1]):
                axis.text(column, row, f"{matrix[row, column]:.5g}", ha="center", va="center")
        axis.set_xticks(range(len(labels)), labels)
        axis.set_yticks(range(len(labels)), labels)
        axis.set_title(title)
        figure.colorbar(image, ax=axis, fraction=0.046, pad=0.04)
    figure.suptitle(
        f"Selected public Q2D cases: {pair['id']} / {single['id']}",
        fontsize=10,
    )
    figure.tight_layout()
    return figure


def _render_distributed_equivalent_overlay(bundle: EvidenceBundle) -> Figure:
    slots = _primary_slots(bundle)
    figure, axes = plt.subplots(5, 4, figsize=(15.0, 13.0))
    components = ((np.real, "Real"), (np.imag, "Imag"))
    for row_index, slot in enumerate(slots):
        response = slot["response"]
        frequency = np.asarray(response["frequency_hz"], dtype=float) / 1.0e9
        traces = {
            "Exact-six S21": _complex_trace(
                slot["exact_six_coordinate_response"]["calibrated_s21"],
                len(frequency),
                "exact_six_s21",
            ),
            "Distributed S21": _complex_trace(
                response["calibrated_distributed_s21"], len(frequency), "distributed_s21"
            ),
            "Equivalent S21": _complex_trace(
                response["calibrated_equivalent_s21"], len(frequency), "equivalent_s21"
            ),
            "Distributed Z21": _complex_trace(
                response["distributed_z21_ohm"], len(frequency), "distributed_z21"
            ),
            "Equivalent Z21": _complex_trace(
                response["equivalent_z21_ohm"], len(frequency), "equivalent_z21"
            ),
        }
        slot_ghz = float(slot["slot_hz"]) / 1.0e9
        for column, (component, component_name) in enumerate(components):
            s_axis = axes[row_index, column]
            z_axis = axes[row_index, column + 2]
            s_axis.plot(
                frequency,
                component(traces["Exact-six S21"]),
                color="#111111",
                linewidth=2.0,
                zorder=2,
                label="Exact-six authority",
            )
            s_axis.plot(
                frequency,
                component(traces["Distributed S21"]),
                color="#0072B2",
                zorder=3,
                label="Distributed",
            )
            s_axis.plot(
                frequency,
                component(traces["Equivalent S21"]),
                color="#D55E00",
                linestyle="--",
                linewidth=1.5,
                zorder=4,
                label="Equivalent",
            )
            z_axis.plot(frequency, component(traces["Distributed Z21"]), label="Distributed")
            z_axis.plot(
                frequency,
                component(traces["Equivalent Z21"]),
                linestyle="--",
                label="Equivalent",
            )
            s_axis.set_ylabel(f"{slot_ghz:.2f} GHz\n{component_name}(S21)")
            z_axis.set_ylabel(f"{component_name}(Z21) (Ω)")
            _style_axis(s_axis)
            _style_axis(z_axis)
    axes[0, 0].legend(loc="best")
    axes[0, 2].legend(loc="best")
    for axis in axes[-1, :]:
        axis.set_xlabel("Frequency (GHz)")
    figure.suptitle("Exact-six response authority and circuit comparisons", y=0.995)
    figure.tight_layout()
    return figure


def _render_refinement(bundle: EvidenceBundle) -> Figure:
    figure_data = _mapping(bundle.payloads["analysis"]["figure_data"], "analysis.figure_data")
    section_rows = cast(list[dict[str, Any]], figure_data["section_refinement_rows"])
    grid_rows = cast(list[dict[str, Any]], figure_data["frequency_grid_refinement_rows"])
    open_policy_rows = cast(
        list[dict[str, Any]], figure_data["frequency_grid_policy_open_pole_rows"]
    )
    closed_policy_rows = cast(
        list[dict[str, Any]],
        figure_data["frequency_grid_policy_closed_pole_exclusion_rows"],
    )
    metrics = (
        ("distributed_s21_complex_rmse_to_finest", "Complex S21 RMSE"),
        ("max_open_pole_frequency_delta_hz_to_finest", "Max pole Δf (Hz)"),
        ("max_open_pole_linewidth_delta_hz_to_finest", "Max linewidth Δ (Hz)"),
    )
    figure, axes = plt.subplots(3, 3, figsize=(14.0, 11.0))
    for slot_hz in EXPECTED_SLOTS_HZ:
        slot_label = f"{slot_hz / 1.0e9:.2f} GHz"
        section = sorted(
            (row for row in section_rows if float(row["slot_hz"]) == slot_hz),
            key=lambda row: float(row["section_length_m"]),
        )
        grid = sorted(
            (row for row in grid_rows if float(row["slot_hz"]) == slot_hz),
            key=lambda row: int(row["sample_count"]),
        )
        for column, (key, title) in enumerate(metrics):
            axes[0, column].plot(
                [float(row["section_length_m"]) * 1.0e6 for row in section],
                [float(row[key]) for row in section],
                marker="o",
                label=slot_label,
            )
            axes[1, column].plot(
                [int(row["sample_count"]) for row in grid],
                [float(row[key]) for row in grid],
                marker="o",
                label=slot_label,
            )
            axes[0, column].set_title(f"Section: {title}")
            axes[1, column].set_title(f"Grid: {title}")
    for axis in axes[0, :]:
        axis.set_xlabel("Section length (µm)")
    for axis in axes[1, :]:
        axis.set_xlabel("Frequency sample count")
    for source_index in range(3):
        selected = [row for row in open_policy_rows if int(row["source_index"]) == source_index]
        axes[2, 0].scatter(
            [float(row["slot_hz"]) / 1.0e9 + (source_index - 1) * 0.006 for row in selected],
            [float(row["planned_samples_per_physical_linewidth"]) for row in selected],
            label=f"open source {source_index}",
        )
    role_colors = {"distributed": "#0072B2", "equivalent": "#D55E00"}
    section_markers = {40.0e-6: "o", 80.0e-6: "x"}
    for role in ("distributed", "equivalent"):
        for section_m in (40.0e-6, 80.0e-6):
            selected = [
                row
                for row in closed_policy_rows
                if row["model_role"] == role and float(row["section_length_m"]) == section_m
            ]
            label = f"{role}, {section_m * 1.0e6:.0f} µm"
            x_values = [float(row["slot_hz"]) / 1.0e9 for row in selected]
            axes[2, 1].scatter(
                x_values,
                [float(row["exclusion_half_width_hz"]) * 1.0e-3 for row in selected],
                color=role_colors[role],
                marker=section_markers[section_m],
                label=label,
            )
            axes[2, 2].scatter(
                x_values,
                [
                    max(
                        float(row["negative_boundary_max_normalized_closure_ratio"]),
                        float(row["positive_boundary_max_normalized_closure_ratio"]),
                    )
                    for row in selected
                ],
                color=role_colors[role],
                marker=section_markers[section_m],
                label=label,
            )
    axes[2, 0].set_title("Open-pole planned physical resolution")
    axes[2, 0].set_ylabel("Samples / physical linewidth")
    axes[2, 1].set_title("Adaptive closed-pole exclusion radius")
    axes[2, 1].set_ylabel("Half-width (kHz)")
    axes[2, 2].set_title("Closed-boundary ordinary-closure proof")
    axes[2, 2].set_ylabel("Max normalized ratio")
    for axis in axes[2, :]:
        axis.set_xlabel("Slot (GHz); source index is not physical identity")
    for axis in axes.flat:
        axis.set_yscale("symlog", linthresh=_symlog_threshold(axis))
        _style_axis(axis)
    axes[0, 0].legend(loc="best", fontsize=7)
    axes[2, 0].legend(loc="best", fontsize=7)
    axes[2, 1].legend(loc="best", fontsize=6)
    figure.suptitle("Refinement and adaptive open/closed-pole grid evidence")
    figure.tight_layout()
    return figure


def _render_vf_reconstruction(bundle: EvidenceBundle) -> Figure:
    panels = _figure_panels(bundle)
    figure, axes = plt.subplots(5, 2, figsize=(12.0, 13.0))
    for row_index, panel in enumerate(panels):
        frequency = np.asarray(panel["frequency_hz"], dtype=float) / 1.0e9
        distributed = _complex_trace(panel["distributed_s21"], len(frequency), "distributed")
        vf = _complex_trace(panel["vf_best_s21"], len(frequency), "vf")
        residual = _complex_trace(
            panel["vf_best_minus_distributed_s21"], len(frequency), "vf_residual"
        )
        slot_ghz = float(panel["slot_hz"]) / 1.0e9
        axes[row_index, 0].plot(frequency, np.real(distributed), label="Distributed Re")
        axes[row_index, 0].plot(frequency, np.imag(distributed), label="Distributed Im")
        axes[row_index, 0].plot(frequency, np.real(vf), linestyle="--", label="VF Re", alpha=0.8)
        axes[row_index, 0].plot(frequency, np.imag(vf), linestyle="--", label="VF Im", alpha=0.8)
        axes[row_index, 1].plot(frequency, np.real(residual), label="Residual Re")
        axes[row_index, 1].plot(frequency, np.imag(residual), label="Residual Im")
        axes[row_index, 0].set_ylabel(f"{slot_ghz:.2f} GHz\nS21")
        axes[row_index, 1].set_ylabel("VF - distributed")
        _style_axis(axes[row_index, 0])
        _style_axis(axes[row_index, 1])
    axes[0, 0].legend(loc="best", fontsize=7, ncol=2)
    axes[0, 1].legend(loc="best", fontsize=7)
    for axis in axes[-1, :]:
        axis.set_xlabel("Frequency (GHz)")
    figure.suptitle("Vector-Fit reconstruction and complex residual", y=0.995)
    figure.tight_layout()
    return figure


def _render_pole_deltas(bundle: EvidenceBundle) -> Figure:
    figure_data = _mapping(bundle.payloads["analysis"]["figure_data"], "analysis.figure_data")
    exact_vf_rows = cast(list[dict[str, Any]], figure_data["exact_six_vf_pole_comparison_rows"])
    exact_open_rows = cast(list[dict[str, Any]], figure_data["exact_six_open_pole_delta_rows"])
    figure, axes = plt.subplots(2, 2, figsize=(12.0, 8.0), sharex="col")
    analysis_slots = _analysis_slots(bundle)
    cardinality_stable = _all_vf_background_order_cardinality_stable(analysis_slots)
    matched_exact_vf = [
        row
        for row in exact_vf_rows
        if row.get("cardinality_state") == "matched_frequency_rank_display_only"
    ]
    if cardinality_stable and matched_exact_vf and len(matched_exact_vf) == len(exact_vf_rows):
        _plot_ranked_delta(
            axes[0, 0],
            matched_exact_vf,
            "vf_minus_exact_six_frequency_hz",
            "VF - exact-six Δf (MHz)",
            scale=1.0e-6,
        )
        _plot_ranked_delta(
            axes[1, 0],
            matched_exact_vf,
            "vf_minus_exact_six_linewidth_hz",
            "VF - exact-six linewidth Δ (MHz)",
            scale=1.0e-6,
        )
        title = "Display-only pole/linewidth comparisons; physical identity pending"
    elif not cardinality_stable:
        _render_vf_ambiguity_evidence(
            axes[:, 0],
            analysis_slots,
            display_only_delta_row_count=len(exact_vf_rows),
        )
        title = "Pole evidence: VF cardinality ambiguity; physical identity pending"
    else:
        for axis, label in zip(
            axes[:, 0],
            ("Exact-six/VF frequency", "Exact-six/VF linewidth"),
            strict=True,
        ):
            axis.text(0.5, 0.5, f"{label} association withheld: cardinality mismatch", ha="center")
        title = "Pole evidence: exact-six/VF cardinality mismatch; physical identity pending"
    matched_distributed = [
        row
        for row in exact_open_rows
        if row.get("cardinality_state") == "matched_frequency_rank_display_only"
    ]
    _plot_ranked_delta(
        axes[0, 1],
        matched_distributed,
        "exact_six_minus_distributed_frequency_hz",
        "Exact-six - distributed Δf (MHz)",
        scale=1.0e-6,
    )
    _plot_ranked_delta(
        axes[1, 1],
        matched_distributed,
        "exact_six_minus_distributed_linewidth_hz",
        "Exact-six - distributed linewidth Δ (MHz)",
        scale=1.0e-6,
    )
    mismatch_count = len(exact_open_rows) - len(matched_distributed)
    if mismatch_count:
        axes[0, 1].text(
            0.02,
            0.98,
            f"{mismatch_count} cardinality-mismatch rows remain unassociated",
            transform=axes[0, 1].transAxes,
            va="top",
            fontsize=8,
        )
    axes[1, 0].set_xlabel("Slot (GHz)")
    axes[1, 1].set_xlabel("Slot (GHz) with rank jitter")
    for axis in axes.flat:
        axis.axhline(0.0, color="#555555", linewidth=0.8)
        _style_axis(axis)
    axes[0, 0].legend(loc="best", fontsize=7)
    figure.suptitle(title)
    figure.tight_layout()
    return figure


def _all_vf_background_order_cardinality_stable(
    slots: Sequence[Mapping[str, Any]],
) -> bool:
    states = []
    for slot_index, slot in enumerate(slots):
        slot_path = f"analysis.slots[{slot_index}]"
        vf = _mapping(slot.get("vf"), f"{slot_path}.vf")
        evidence = _mapping(
            vf.get("order_and_resolution_evidence"),
            f"{slot_path}.vf.order_and_resolution_evidence",
        )
        state = evidence.get("exact_three_resonance_cardinality_in_every_run")
        if not isinstance(state, bool):
            raise ValueError(f"{slot_path} VF exact-cardinality state must be boolean.")
        states.append(state)
    return all(states)


def _render_vf_ambiguity_evidence(
    axes: Sequence[Any],
    slots: Sequence[Mapping[str, Any]],
    *,
    display_only_delta_row_count: int,
) -> None:
    """Render measured VF cardinality and RMSE when global cardinality is unstable."""

    by_order: dict[int, list[tuple[float, int, float, bool]]] = {}
    for slot_index, slot in enumerate(slots):
        slot_path = f"analysis.slots[{slot_index}]"
        slot_hz = _positive_real(slot.get("slot_hz"), f"{slot_path}.slot_hz")
        vf = _mapping(slot.get("vf"), f"{slot_path}.vf")
        evidence = _mapping(
            vf.get("order_and_resolution_evidence"),
            f"{slot_path}.vf.order_and_resolution_evidence",
        )
        exact_cardinality = evidence.get("exact_three_resonance_cardinality_in_every_run")
        if not isinstance(exact_cardinality, bool):
            raise ValueError(f"{slot_path} VF exact-cardinality state must be boolean.")
        _require_string(
            evidence.get("ambiguity_state"),
            (
                "structurally_complete_but_physical_identity_unreviewed"
                if exact_cardinality
                else "ambiguous_or_incomplete_resonance_cardinality"
            ),
            f"{slot_path}.vf.order_and_resolution_evidence.ambiguity_state",
        )
        runs = _sequence(
            evidence.get("background_order_runs"),
            f"{slot_path}.vf.order_and_resolution_evidence.background_order_runs",
        )
        if not runs:
            raise ValueError(f"{slot_path} VF ambiguity evidence has no background-order runs.")
        for run_index, raw_run in enumerate(runs):
            run_path = (
                f"{slot_path}.vf.order_and_resolution_evidence.background_order_runs[{run_index}]"
            )
            run = _mapping(raw_run, run_path)
            order = _nonnegative_int(run.get("background_poles"), f"{run_path}.background_poles")
            count = _nonnegative_int(
                run.get("retained_resonance_count"),
                f"{run_path}.retained_resonance_count",
            )
            rmse = _nonnegative_real(run.get("complex_rmse"), f"{run_path}.complex_rmse")
            converged = run.get("converged")
            if not isinstance(converged, bool):
                raise ValueError(f"{run_path}.converged must be boolean.")
            by_order.setdefault(order, []).append((slot_hz, count, rmse, converged))

    expected_slot_count = len(slots)
    nonconverged_count = 0
    for order, rows in sorted(by_order.items()):
        if len(rows) != expected_slot_count:
            raise ValueError(f"VF background order {order} does not cover all five slots exactly.")
        ordered = sorted(rows)
        x_values = [row[0] / 1.0e9 for row in ordered]
        axes[0].plot(
            x_values,
            [row[1] for row in ordered],
            marker="o",
            label=f"background order {order}",
        )
        axes[1].plot(x_values, [row[2] for row in ordered], marker="o")
        nonconverged_count += sum(not row[3] for row in ordered)
    axes[0].axhline(3.0, color="#CC79A7", linestyle=":", label="required cardinality 3")
    axes[0].set_ylabel("VF retained resonance count")
    axes[1].set_ylabel("VF complex RMSE")
    axes[0].text(
        0.02,
        0.04,
        (
            "Exact-six/VF delta panel withheld: three-resonance cardinality is not stable\n"
            f"across background orders; {display_only_delta_row_count} best-run display-only "
            f"row(s) remain tabulated; {nonconverged_count} run(s) report non-convergence."
        ),
        transform=axes[0].transAxes,
        va="bottom",
        fontsize=8,
    )


def _plot_ranked_delta(
    axis: Any,
    rows: Sequence[Mapping[str, Any]],
    value_key: str,
    ylabel: str,
    *,
    scale: float,
) -> None:
    for rank in range(3):
        selected = [row for row in rows if row.get("frequency_rank_for_display_only") == rank]
        x_values = [float(row["slot_hz"]) / 1.0e9 + (rank - 1) * 0.006 for row in selected]
        y_values = [
            float(row[value_key]) * scale for row in selected if row.get(value_key) is not None
        ]
        if len(x_values) != len(y_values):
            raise ValueError(f"Pole delta rows have incomplete {value_key} semantics.")
        axis.plot(x_values, y_values, marker="o", linestyle="none", label=f"rank {rank}")
    axis.set_ylabel(ylabel)


def _build_register(bundle: EvidenceBundle, figure_records: list[dict[str, Any]]) -> dict[str, Any]:
    sources = {}
    for label, path in bundle.paths.as_mapping().items():
        payload = bundle.payloads[label]
        sources[label] = {
            "path": str(path.resolve()),
            "sha256": bundle.raw_sha256[label],
            "size_bytes": bundle.raw_sizes[label],
            "schema_version": payload["schema_version"],
            "status": payload.get("status", payload.get("artifact_status")),
        }
    analysis = bundle.payloads["analysis"]
    figure_data = _mapping(analysis["figure_data"], "analysis.figure_data")
    exact_six = _mapping(
        _primary_slots(bundle)[0]["exact_six_coordinate_response"],
        "primary_run.slots[0].exact_six_coordinate_response",
    )
    return {
        "schema_version": REPORT_SCHEMA,
        "status": "complete",
        "route": PUBLIC_Q2D_ROUTE,
        "physical_promotion_claim": False,
        "promotion_state": "pending_human_review",
        "source_files": sources,
        "selected_public_q2d": {
            "combined_case_id": _primary_slots(bundle)[0]["provenance"]["case_id"],
            "pair_case_id": bundle.selected_pair_case["id"],
            "single_case_id": bundle.selected_single_case["id"],
            "upper_die_substrate_present": True,
            "upper_ground_metal_policy": "removed_only_within_local_clearance",
        },
        "slot_hz": [slot["slot_hz"] for slot in analysis["slots"]],
        "figure_data_schema_version": analysis["figure_data"]["schema_version"],
        "response_authority": {
            "contract_id": exact_six["contract_id"],
            "response_authority": exact_six["response_authority"],
            "coordinate_order": exact_six["coordinate_order"],
            "source": "primary_run.slots[*].exact_six_coordinate_response",
            "all_five_primary_analysis_links_verified": True,
            "three_mode_role": "comparison_only_not_response_authority",
            "physical_promotion_claim": False,
        },
        "frequency_grid_policy_evidence": {
            "contract_id": "d3-open-closed-pole-aware-frequency-grid.v2",
            "closed_frequency_rank_physical_identity_claim": False,
            "policies": figure_data["frequency_grid_policies"],
            "open_pole_rows": figure_data["frequency_grid_policy_open_pole_rows"],
            "closed_pole_exclusion_rows": figure_data[
                "frequency_grid_policy_closed_pole_exclusion_rows"
            ],
        },
        "vf_fourier_convention_bridge": _mapping(analysis["semantics"], "analysis.semantics")[
            "vf_fourier_convention_bridge"
        ],
        "three_mode_shared_subset_evidence": {
            "contract_id": "d3-three-mode-shared-primary-grid-conditioning-subset.v1",
            "interpolation_used": False,
            "physical_mode_identity_claim": False,
            "slots": figure_data["three_mode_shared_subset_evidence"],
            "summary_rows": figure_data["three_mode_shared_subset_summary_rows"],
            "conditioning_exclusion_rows": figure_data["three_mode_conditioning_exclusion_rows"],
        },
        "figures": figure_records,
    }


def _analysis_slots(bundle: EvidenceBundle) -> list[dict[str, Any]]:
    return cast(list[dict[str, Any]], bundle.payloads["analysis"]["slots"])


def _primary_slots(bundle: EvidenceBundle) -> list[dict[str, Any]]:
    return cast(list[dict[str, Any]], bundle.payloads["primary_run"]["slots"])


def _figure_panels(bundle: EvidenceBundle) -> list[dict[str, Any]]:
    figure_data = cast(dict[str, Any], bundle.payloads["analysis"]["figure_data"])
    return cast(list[dict[str, Any]], figure_data["trace_panels"])


def _style_axis(axis: Any) -> None:
    axis.grid(True, alpha=0.22)
    axis.spines["top"].set_visible(False)
    axis.spines["right"].set_visible(False)


def _symlog_threshold(axis: Any) -> float:
    positive = [
        abs(float(value))
        for line in axis.lines
        for value in line.get_ydata()
        if math.isfinite(float(value)) and float(value) != 0.0
    ]
    return min(positive) / 10.0 if positive else 1.0


def _validate_exact_six_response(
    value: Any,
    expected_frequency_hz: np.ndarray,
    path: str,
) -> None:
    response = _mapping(value, path)
    _require_exact_keys(response, _EXACT_SIX_KEYS, path)
    _require_string(
        response["contract_id"],
        "d3-exact-six-coordinate-open-response.v1",
        f"{path}.contract_id",
    )
    _require_string(
        response["response_authority"],
        "canonical_exact_six_coordinate_open_response",
        f"{path}.response_authority",
    )
    _require_string(
        response["model_role"],
        "response_matched_two_pi_full_coordinate_equivalent",
        f"{path}.model_role",
    )
    if response["coordinate_order"] != ["q", "r", "p", "f1", "fc", "f2"]:
        raise ValueError(f"{path}.coordinate_order must retain all six physical coordinates.")
    frequency_hz = _frequency_grid(response["frequency_hz"], f"{path}.frequency_hz")
    if not np.array_equal(frequency_hz, expected_frequency_hz):
        raise ValueError(f"{path}.frequency_hz must equal the primary response grid exactly.")
    raw_s21 = _complex_trace(response["raw_s21"], len(frequency_hz), f"{path}.raw_s21")
    calibrated_s21 = _complex_trace(
        response["calibrated_s21"], len(frequency_hz), f"{path}.calibrated_s21"
    )

    poles = _sequence(response["open_poles"], f"{path}.open_poles")
    if len(poles) != 5:
        raise ValueError(f"{path}.open_poles must contain five positive poles.")
    pole_frequencies = []
    source_indices = set()
    for index, raw_pole in enumerate(poles):
        pole_path = f"{path}.open_poles[{index}]"
        pole = _mapping(raw_pole, pole_path)
        _require_exact_keys(
            pole,
            {"source_index", "frequency_hz", "imaginary_frequency_hz", "linewidth_hz"},
            pole_path,
        )
        source_indices.add(_nonnegative_int(pole["source_index"], f"{pole_path}.source_index"))
        pole_frequencies.append(_positive_real(pole["frequency_hz"], f"{pole_path}.frequency_hz"))
        imaginary_hz = _finite_real(
            pole["imaginary_frequency_hz"], f"{pole_path}.imaginary_frequency_hz"
        )
        if imaginary_hz > 0.0:
            raise ValueError(f"{pole_path} must be passive.")
        linewidth_hz = _nonnegative_real(pole["linewidth_hz"], f"{pole_path}.linewidth_hz")
        _require_numeric_close(linewidth_hz, -2.0 * imaginary_hz, f"{pole_path}.linewidth_hz")
    if len(source_indices) != 5 or pole_frequencies != sorted(pole_frequencies):
        raise ValueError(f"{path}.open_poles must have unique indices and ordered frequencies.")

    _positive_real(response["reference_impedance_ohm"], f"{path}.reference_impedance_ohm")
    selector = _mapping(response["port_selector"], f"{path}.port_selector")
    if selector.get("port_coordinates") != ["f1", "f2"] or selector.get(
        "coordinate_indices_zero_based"
    ) != [3, 5]:
        raise ValueError(f"{path}.port_selector must select physical f1 and f2 coordinates.")
    selector_matrix = np.asarray(selector.get("matrix"), dtype=float)
    expected_selector = np.zeros((6, 2))
    expected_selector[3, 0] = expected_selector[5, 1] = 1.0
    if selector_matrix.shape != (6, 2) or not np.array_equal(selector_matrix, expected_selector):
        raise ValueError(f"{path}.port_selector.matrix must be the canonical 6x2 selector.")

    calibration = _mapping(response["calibration"], f"{path}.calibration")
    reference_s21 = _complex_trace(
        calibration.get("reference_s21"), len(frequency_hz), f"{path}.calibration.reference_s21"
    )
    if not np.allclose(calibrated_s21, raw_s21 / reference_s21, rtol=0.0, atol=1.0e-12):
        raise ValueError(f"{path}.calibrated_s21 disagrees with its reference division.")
    provenance = _mapping(response["provenance"], f"{path}.provenance")
    if (
        provenance.get("qrp_projection_applied") is not False
        or provenance.get("fixed_kappa_applied") is not False
    ):
        raise ValueError(f"{path}.provenance must retain the unreduced exact-six authority.")
    _require_string(
        provenance.get("three_mode_role"),
        "comparison_only_not_response_authority",
        f"{path}.provenance.three_mode_role",
    )
    residual = _mapping(
        response["residual_vs_existing_equivalent"],
        f"{path}.residual_vs_existing_equivalent",
    )
    if residual.get("formula_identity_claimed") is not False:
        raise ValueError(f"{path} must not claim exact formula identity with the finer ladder.")


def _validate_three_mode_view(view: Mapping[str, Any], path: str) -> None:
    _require_string(
        view.get("model_role"),
        "comparison_only_three_mode_constant_kappa_approximation",
        f"{path}.model_role",
    )
    _require_string(
        view.get("response_authority"),
        "none_comparison_only_exact_six_coordinate_response_is_authority",
        f"{path}.response_authority",
    )
    if view.get("mode_order") != ["q", "r", "p"]:
        raise ValueError(f"{path}.mode_order must be exactly ['q', 'r', 'p'].")
    poles = _sequence(view.get("poles"), f"{path}.poles")
    if len(poles) != 3:
        raise ValueError(f"{path}.poles must contain exactly three poles.")
    for index, raw_pole in enumerate(poles):
        pole = _mapping(raw_pole, f"{path}.poles[{index}]")
        if pole.get("frequency_rank") != index:
            raise ValueError(f"{path}.poles[{index}] has the wrong frequency rank.")
        _positive_real(pole.get("frequency_hz"), f"{path}.poles[{index}].frequency_hz")
        _nonnegative_real(pole.get("linewidth_hz"), f"{path}.poles[{index}].linewidth_hz")
        _require_string(
            pole.get("promotion_visibility"),
            "pending_human_residue_floor",
            f"{path}.poles[{index}].promotion_visibility",
        )


def _five_slots(value: Any, path: str) -> list[dict[str, Any]]:
    rows = _sequence(value, path)
    if len(rows) != len(EXPECTED_SLOTS_HZ):
        raise ValueError(f"{path} must contain exactly five slots.")
    result = [dict(_mapping(row, f"{path}[{index}]")) for index, row in enumerate(rows)]
    actual = tuple(
        _positive_real(row.get("slot_hz"), f"{path}[{index}].slot_hz")
        for index, row in enumerate(result)
    )
    if actual != EXPECTED_SLOTS_HZ:
        raise ValueError(f"{path} must be ordered exactly as {list(EXPECTED_SLOTS_HZ)} Hz.")
    return result


def _require_all_slots_tagged(value: Any, path: str) -> None:
    rows = _sequence(value, path)
    observed = {
        _positive_real(_mapping(row, f"{path}[{index}]").get("slot_hz"), f"{path}[{index}].slot_hz")
        for index, row in enumerate(rows)
    }
    if observed != set(EXPECTED_SLOTS_HZ):
        raise ValueError(f"{path} must retain rows tagged for all five D3 slots.")


def _complex_trace(value: Any, expected_length: int, path: str) -> np.ndarray:
    row = _mapping(value, path)
    _require_exact_keys(row, {"real", "imag"}, path)
    real = _real_array(row["real"], f"{path}.real")
    imag = _real_array(row["imag"], f"{path}.imag")
    if len(real) != expected_length or len(imag) != expected_length:
        raise ValueError(f"{path} must match its frequency-grid length.")
    return real + 1j * imag


def _frequency_grid(value: Any, path: str) -> np.ndarray:
    result = _real_array(value, path)
    if len(result) < 2 or np.any(result <= 0.0) or np.any(np.diff(result) <= 0.0):
        raise ValueError(f"{path} must be a strictly increasing positive grid.")
    return result


def _matrix(value: Any, dimension: int, path: str) -> np.ndarray:
    rows = _sequence(value, path)
    if len(rows) != dimension:
        raise ValueError(f"{path} must be {dimension}x{dimension}.")
    matrix = np.asarray(
        [
            [
                _finite_real(item, f"{path}[{row_index}][{column_index}]")
                for column_index, item in enumerate(_sequence(row, f"{path}[{row_index}]"))
            ]
            for row_index, row in enumerate(rows)
        ],
        dtype=float,
    )
    if matrix.shape != (dimension, dimension):
        raise ValueError(f"{path} must be {dimension}x{dimension}.")
    if not np.allclose(matrix, matrix.T, rtol=1.0e-12, atol=0.0):
        raise ValueError(f"{path} must be symmetric.")
    if np.any(np.diag(matrix) <= 0.0):
        raise ValueError(f"{path} diagonal must be positive.")
    return matrix


def _real_array(value: Any, path: str) -> np.ndarray:
    rows = _sequence(value, path)
    return np.asarray([_finite_real(item, f"{path}[{index}]") for index, item in enumerate(rows)])


def _mapping(value: Any, path: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{path} must be a JSON object.")
    if any(not isinstance(key, str) for key in value):
        raise ValueError(f"{path} keys must be strings.")
    return cast(Mapping[str, Any], value)


def _sequence(value: Any, path: str) -> Sequence[Any]:
    if isinstance(value, (str, bytes, bytearray)) or not isinstance(value, Sequence):
        raise ValueError(f"{path} must be a JSON array.")
    return cast(Sequence[Any], value)


def _require_exact_keys(value: Mapping[str, Any], expected: set[str], path: str) -> None:
    actual = set(value)
    if actual != expected:
        raise ValueError(
            f"{path} keys do not match; missing={sorted(expected - actual)}, "
            f"unknown={sorted(actual - expected)}."
        )


def _require_string(value: Any, expected: str, path: str) -> None:
    if value != expected:
        raise ValueError(f"{path} must be exactly {expected!r}.")


def _nonempty_string(value: Any, path: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{path} must be a nonempty string.")
    return value


def _sha256(value: Any, path: str) -> str:
    digest = _nonempty_string(value, path)
    if len(digest) != _SHA256_LENGTH or any(
        character not in "0123456789abcdef" for character in digest
    ):
        raise ValueError(f"{path} must be a lowercase SHA-256 digest.")
    return digest


def _finite_real(value: Any, path: str) -> float:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise ValueError(f"{path} must be an explicit real number.")
    converted = float(value)
    if not math.isfinite(converted):
        raise ValueError(f"{path} must be finite.")
    return converted


def _positive_real(value: Any, path: str) -> float:
    converted = _finite_real(value, path)
    if converted <= 0.0:
        raise ValueError(f"{path} must be positive.")
    return converted


def _nonnegative_real(value: Any, path: str) -> float:
    converted = _finite_real(value, path)
    if converted < 0.0:
        raise ValueError(f"{path} must be nonnegative.")
    return converted


def _positive_int(value: Any, path: str) -> int:
    converted = _nonnegative_int(value, path)
    if converted <= 0:
        raise ValueError(f"{path} must be positive.")
    return converted


def _nonnegative_int(value: Any, path: str) -> int:
    if isinstance(value, bool) or not isinstance(value, Integral):
        raise ValueError(f"{path} must be an integer.")
    converted = int(value)
    if converted < 0:
        raise ValueError(f"{path} must be nonnegative.")
    return converted


def _canonical_sha256(value: Mapping[str, Any]) -> str:
    encoded = json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode()
    return hashlib.sha256(encoded).hexdigest()


def _file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


__all__ = [
    "REPORT_SCHEMA",
    "EvidenceBundle",
    "EvidenceInputPaths",
    "build_evidence_report",
    "load_evidence_bundle",
    "summarize_evidence",
]
