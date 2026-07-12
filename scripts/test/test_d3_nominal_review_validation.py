#!/usr/bin/env python3
"""Synthetic no-HB checks for the current D3 exact-six nominal contract."""

from __future__ import annotations

import copy
import importlib.util
import json
import math
import shutil
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
VALIDATOR_PATH = REPO_ROOT / "scripts/build/plot_d3_final_diagnostics.py"
LEGACY_RUN = REPO_ROOT / (
    "build/research/d3_coupled_optimizer_v1/"
    "20260710T213955009Z__d3-coupled-optimization-6ghz-design-target-v1__0c16418e6d15"
)

spec = importlib.util.spec_from_file_location("d3_nominal_review_validator", VALIDATOR_PATH)
if spec is None or spec.loader is None:
    raise ImportError(f"Could not load {VALIDATOR_PATH}")
validator = importlib.util.module_from_spec(spec)
spec.loader.exec_module(validator)


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, allow_nan=False, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )


def json3_roundtrip(value):
    """Shape persisted JSON values as JSON3 `Any` will read them."""
    return json.loads(
        json.dumps(value, allow_nan=False),
        parse_float=validator.json3_any_float,
    )


def workspace_file(workspace: Path, relative_path: str, contents: str) -> Path:
    path = workspace / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(contents, encoding="utf-8")
    return path


def current_optimizer_fixture(workspace: Path) -> Path:
    """Shape a current exact-eight optimizer run without loading Julia or HB."""
    optimizer_run = workspace / "workbench/build/research/synthetic-current-staging"
    shutil.copytree(LEGACY_RUN, optimizer_run)

    layout = read_json(optimizer_run / "layout_specs.json")
    layout["breakdown"]["metrics"].append(
        {
            "normalized_residual": 0.0,
            "name": "g_hz",
            "weight": 1.0,
            "contribution": 0.0,
            "target": 90.0e6,
            "observed": 90.0e6,
            "scale": 1.0e6,
        }
    )
    layout_metrics = {item["name"]: item for item in layout["breakdown"]["metrics"]}
    target = {
        "target_id": "synthetic-d3-target",
        "revision": "v1",
        "targets": {
            "filter_loaded_bare_offset": {"value": 1.0},
            "readout_loaded_bare_offset": {"value": -1.0},
            "interference_notch_frequency": {
                "value": layout_metrics["notch_hz"]["target"] / 1.0e9
            },
            "filter_loaded_bare_linewidth": {
                "value": layout_metrics["filter_loaded_linewidth_hz"]["target"] / 1.0e6
            },
            "readout_filter_exchange_coupling": {
                "value": layout_metrics["j_hz"]["target"] / 1.0e6
            },
            "qubit_readout_coupling": {"value": 90.0},
            "qubit_transition_frequency": {"value": 4.7, "unit": "GHz"},
            "qubit_junction_inductance": {
                "value": 23.0,
                "unit": "nH_per_junction",
                "parallel_junction_count": 2,
            },
        },
    }
    target_path = workspace / "docs/target.json"
    write_json(target_path, target)
    target_hash = validator.file_sha256(target_path)

    conditions = {
        "schema_version": "d3-optimizer-conditions.v1",
        "conditions_id": "synthetic-current-conditions",
        "metric_specs": {
            metric_id: {
                "scale": item["scale"],
                "weight": item["weight"],
            }
            for metric_id, item in layout_metrics.items()
        },
        "evaluator_settings": {
            "frequency_step_hz": 500.0e6,
            "min_notch_assignment_margin_hz": 1.0e6,
        },
        "sol_review": {
            "status": "synthetic-test-only",
            "hash_framing": validator.SEMANTIC_HASH_FRAMING,
        },
    }
    conditions_path = workspace / "workbench/config/conditions.json"
    write_json(conditions_path, conditions)
    conditions = validator.load_json(conditions_path.parent, conditions_path.name)
    conditions_file_hash = validator.file_sha256(conditions_path)
    conditions_contract_hash = validator.semantic_value_sha256(
        {key: value for key, value in conditions.items() if key != "sol_review"}
    )

    source_paths = {
        "target_contract": target_path,
        "optimizer_conditions": conditions_path,
        "seed_csv": workspace_file(workspace, "workbench/inputs/seed.csv", "id,value\nseed,1\n"),
        "orpen_case_json": workspace_file(workspace, "workbench/inputs/q2d.json", "{}\n"),
        "d3_purcell_common": workspace_file(workspace, "workbench/runtime/common.jl", "# common\n"),
        "d3_coupled_evaluator": workspace_file(workspace, "workbench/runtime/evaluator.jl", "# evaluator\n"),
        "d3_semantic_hash": workspace_file(workspace, "workbench/runtime/d3_semantic_hash.jl", "# semantic hash\n"),
        "floating_qubit_nominal": workspace_file(
            workspace,
            "workbench/private/floating-qubit.json",
            json.dumps({
                "schema_version": "d3-floating-qubit-maxwell.v1",
                "model_id": "synthetic-floating-qubit",
                "readout_self_capacitance_ownership": "distributed_resonator_owns_self_capacitance",
                "L_J_per_junction_nH": 23.0,
            }) + "\n",
        ),
        "d3_floating_qubit_input_loader": workspace_file(
            workspace, "workbench/runtime/floating_qubit_loader.jl", "# qubit loader\n"
        ),
    }
    inventory_rows = [
        {
            "id": source_id,
            "path": path.relative_to(workspace).as_posix(),
            "expected_sha256": validator.file_sha256(path),
            "observed_sha256": validator.file_sha256(path),
        }
        for source_id, path in source_paths.items()
    ]

    config = {
        "target_contract": {
            "workspace_relative_path": target_path.relative_to(workspace).as_posix(),
            "expected_target_id": target["target_id"],
            "expected_revision": target["revision"],
            "expected_sha256": target_hash,
        },
        "orpen_case_json_workspace_path": source_paths["orpen_case_json"].relative_to(workspace).as_posix(),
        "design_csv_workspace_root": source_paths["seed_csv"].parent.relative_to(workspace).as_posix(),
        "design_csv_filename": source_paths["seed_csv"].name,
        "floating_qubit_nominal_workspace_path": source_paths["floating_qubit_nominal"].relative_to(workspace).as_posix(),
    }
    write_json(optimizer_run / "config_snapshot.json", config)

    optimizer_id = "synthetic-current-optimizer"
    source_row = {"target_set_id": "d3", "row_id": "synthetic-row"}
    current_contract = {
        "manifest_id": optimizer_id,
        "target_contract": {
            "target_id": target["target_id"],
            "revision": target["revision"],
            "sha256": target_hash,
        },
        "optimizer_conditions": {
            "conditions_id": conditions["conditions_id"],
            "sha256": conditions_contract_hash,
            "hash_framing": validator.SEMANTIC_HASH_FRAMING,
        },
        "selection": {
            "case_id": "synthetic-case",
            "target_set_id": "d3",
            "slot_target_ghz": 6.0,
            "source_row": source_row,
            "source_row_sha256": validator.semantic_value_sha256(source_row),
        },
        "consumed_files": inventory_rows,
        "floating_qubit_nominal": {
            "schema_version": "d3-floating-qubit-maxwell.v1",
            "model_id": "synthetic-floating-qubit",
            "input_sha256": validator.file_sha256(source_paths["floating_qubit_nominal"]),
            "readout_self_capacitance_ownership": "distributed_resonator_owns_self_capacitance",
            "readout_diagonal_instantiated": False,
            "L_J_per_junction_nH": 23.0,
            "canonical_targets": {
                "target_contract_id": target["target_id"],
                "target_contract_sha256": target_hash,
                "qubit_transition_frequency": {"value": 4.7e9, "unit": "Hz"},
                "qubit_junction_inductance": {"value": 23.0, "unit": "nH_per_junction"},
            },
            "physics_diagnostics": {"human_target_f01_hz": 4.7e9},
        },
    }
    current_contract = json3_roundtrip(current_contract)
    execution_hash = validator.semantic_value_sha256(
        {
            "schema_version": validator.SLOT_EXECUTION_MANIFEST_SCHEMA,
            "semantic_hash_framing": validator.SEMANTIC_HASH_FRAMING,
            "contract": current_contract,
        }
    )
    current_manifest = {
        "schema_version": validator.SLOT_EXECUTION_MANIFEST_SCHEMA,
        "semantic_hash_framing": validator.SEMANTIC_HASH_FRAMING,
        "execution_sha256": execution_hash,
        "contract": current_contract,
    }
    final_optimizer_run = optimizer_run.parent / f"synthetic-current__{execution_hash[:12]}"
    optimizer_run.rename(final_optimizer_run)
    optimizer_run = final_optimizer_run
    write_json(optimizer_run / "condition_manifest.json", current_manifest)

    status = read_json(optimizer_run / "status.json")
    status.pop("contract_sha256", None)
    status["execution_sha256"] = execution_hash
    write_json(optimizer_run / "status.json", status)

    layout["condition_manifest_sha256"] = execution_hash
    write_json(optimizer_run / "layout_specs.json", layout)
    optimization = read_json(optimizer_run / "optimization_result.json")
    optimization["condition_manifest_sha256"] = execution_hash
    optimization["condition_manifest_id"] = optimizer_id
    selected_record = next(
        record for record in optimization["history"]
        if record["record_id"] == layout["candidate_record_id"]
    )
    selected_record["evaluation"]["metrics"]["g_hz"] = 90.0e6
    selected_record["breakdown"]["metrics"].append(copy.deepcopy(layout["breakdown"]["metrics"][-1]))
    write_json(optimizer_run / "optimization_result.json", optimization)

    final_diagnostics = read_json(optimizer_run / "final_diagnostics.json")
    final_diagnostics["analysis_kind"] = "optimizer_internal_final_reproduction"
    final_diagnostics["independent_validation"] = False
    record = final_diagnostics["record"]
    record["metrics"]["g_hz"] = 90.0e6
    loaded_grid = [5.5e9, 6.0e9, 6.5e9]
    pair_grid = [5.5e9, 6.0e9, 6.5e9]
    loaded_hash = validator.frequency_grid_sha256(loaded_grid)
    pair_hash = validator.frequency_grid_sha256(pair_grid)
    qubit_grid = [4.95e9, 5.05e9, 5.15e9]
    qubit_hash = validator.frequency_grid_sha256(qubit_grid)
    input_hash = validator.file_sha256(source_paths["floating_qubit_nominal"])
    record["diagnostics"]["qubit_frequency_grid_sha256"] = qubit_hash
    record["diagnostics"]["floating_qubit"] = {
        "model_id": "synthetic-floating-qubit",
        "input_sha256": input_hash,
        "coupling_off_frequency_hz": 5.0e9,
        "electrostatic_reduction": {
            "partition": {
                "floating_labels": ["pad-a", "pad-b", "pad-c", "pad-d"],
                "retained_labels": ["island-a", "island-b", "readout"],
                "reference_label": "ground",
            },
            "reduced_maxwell_matrix_fF": [
                [90.0, -30.0, -10.0],
                [-30.0, 101.0, -1.0],
                [-10.0, -1.0, 200.0],
            ],
            "readout_self_capacitance_ownership": "distributed_resonator_owns_self_capacitance",
            "readout_diagonal_instantiated": False,
            "physics_diagnostics": {
                "first_order_transmon_f01_hz": 4.7e9,
                "human_target_f01_hz": 4.7e9,
                "first_order_transmon_f01_residual_hz": 0.0,
            },
        },
    }
    notch_hz = record["metrics"]["notch_hz"]
    synthetic_root = {"frequency_hz": notch_hz, "sampled_abs_im_z21_ohm": 0.0}
    record["diagnostics"]["reference_notch"] = {
        **synthetic_root,
        "all_roots": [synthetic_root],
        "ownership": "unique_no_qubit_intrinsic_reference",
        "trace_id": "synthetic-reference-notch",
    }
    record["diagnostics"]["notch"] = {
        **synthetic_root,
        "all_roots": [synthetic_root],
        "ownership": "nearest_unique_no_qubit_intrinsic_reference",
        "reference_notch_hz": notch_hz,
        "assignment_margin_hz": 600.0e6,
        "trace_id": "synthetic-loaded-notch",
        "reference_trace_id": "synthetic-reference-notch",
    }
    frequency_fit = record["diagnostics"]["readout_zero_probe_frequency_fit"]
    x_values = frequency_fit["x_values"]
    common_readout_hz = record["metrics"]["readout_loaded_bare_hz"]
    coupling_off_frequencies = [
        common_readout_hz + 1.0e6 * value + 300.0e3 * value**2 for value in x_values
    ]
    coupling_on_frequencies = [value + 10.0e6 for value in coupling_off_frequencies]
    frequency_fit.update(
        {
            "y_values": coupling_on_frequencies,
            "fitted_y_values": coupling_on_frequencies,
            "intercept": common_readout_hz + 10.0e6,
            "coefficients": {
                "intercept": common_readout_hz + 10.0e6,
                "linear_per_fF": 1.0e6,
                "quadratic_per_fF2": 300.0e3,
            },
        }
    )
    g_values = [
        math.sqrt(10.0e6 * (frq_hz - 5.0e9)) for frq_hz in coupling_on_frequencies
    ]
    record["diagnostics"]["readout_coupling_off_zero_probe_frequency_fit"] = {
        "x_values": x_values,
        "y_values": coupling_off_frequencies,
        "fitted_y_values": coupling_off_frequencies,
        "intercept": common_readout_hz,
        "coefficients": {
            "intercept": common_readout_hz,
            "linear_per_fF": 1.0e6,
            "quadratic_per_fF2": 300.0e3,
        },
    }
    record["diagnostics"]["g_zero_probe_fit"] = {
        "x_values": x_values,
        "y_values": g_values,
        "fitted_y_values": g_values,
        "intercept": 90.0e6,
        "coefficients": {
            "intercept": 90.0e6,
            "linear_per_fF": 100.0,
            "quadratic_per_fF2": 1.0,
        },
    }
    predicted_qubit_zero_probe_hz = 5.0e9 + common_readout_hz - (common_readout_hz + 10.0e6)
    qubit_frequencies = [
        predicted_qubit_zero_probe_hz + 1.0e6 * value for value in x_values
    ]
    record["diagnostics"]["qubit_zero_probe_frequency_fit"] = {
        "x_values": x_values,
        "y_values": qubit_frequencies,
        "fitted_y_values": qubit_frequencies,
        "intercept": predicted_qubit_zero_probe_hz,
        "coefficients": {
            "intercept": predicted_qubit_zero_probe_hz,
            "linear_per_fF": 1.0e6,
            "quadratic_per_fF2": 0.0,
        },
    }
    record["diagnostics"]["zero_probe_lower_pole_crosscheck"] = {
        "status": "within_comparison_scale",
        "role": "finite_open_s21_diagnostic_not_gate",
        "fqLB_hz": 5.0e9,
        "frLB_zero_probe_hz": common_readout_hz,
        "fr_coupling_on_zero_probe_hz": common_readout_hz + 10.0e6,
        "observed_qubit_zero_probe_hz": predicted_qubit_zero_probe_hz,
        "predicted_qubit_zero_probe_hz": predicted_qubit_zero_probe_hz,
        "residual_hz": 0.0,
        "comparison_scale_hz": 1.0e6,
    }

    def complex_values(count: int, scale: float) -> list[dict[str, float]]:
        return [
            {"real": 1.0 + scale * index, "imag": scale * (index + 1)}
            for index in range(count)
        ]

    filter_trace = record["traces"]["filter"]
    filter_trace.update(
        {
            "frequency_grid_sha256": loaded_hash,
            "measured_trace_id": f"synthetic-filter|grid_sha256={loaded_hash}",
            "reference_trace_id": f"synthetic-loaded-reference|grid_sha256={loaded_hash}",
            "frequencies_hz": loaded_grid,
            "s21": complex_values(len(loaded_grid), 0.01),
            "reference_s21": complex_values(len(loaded_grid), 0.001),
        }
    )
    for index, probe in enumerate(record["traces"]["readout_probes"]):
        probe.update(
            {
                "frequency_grid_sha256": loaded_hash,
                "measured_trace_id": f"synthetic-readout-{index}|grid_sha256={loaded_hash}",
                "reference_trace_id": f"synthetic-loaded-reference|grid_sha256={loaded_hash}",
                "frequencies_hz": loaded_grid,
                "s21": complex_values(len(loaded_grid), 0.02 + index * 0.001),
                "reference_s21": complex_values(len(loaded_grid), 0.001),
                "diagonal_preserving_coupling_off_measured_trace_id": f"synthetic-readout-off-{index}|grid_sha256={loaded_hash}",
                "diagonal_preserving_coupling_off_s21": complex_values(len(loaded_grid), 0.015 + index * 0.001),
            }
        )
        probe.update(
            {
                "qubit_frequency_grid_sha256": qubit_hash,
                "qubit_measured_trace_id": f"synthetic-qubit-{index}|grid_sha256={qubit_hash}",
                "qubit_frequencies_hz": qubit_grid,
                "qubit_s21": complex_values(len(qubit_grid), 0.02 + index * 0.001),
                "qubit_reference_s21": complex_values(len(qubit_grid), 0.001),
            }
        )
        mode = record["diagnostics"]["readout_probe_modes"][index]
        frq_hz = coupling_on_frequencies[index]
        fr0_hz = coupling_off_frequencies[index]
        predicted_qubit_hz = 5.0e9 + fr0_hz - frq_hz
        fitted_qubit_hz = qubit_frequencies[index]
        mode["frequency_hz"] = frq_hz
        mode.pop("g_hz", None)
        mode["shift_derived_g_diagnostic"] = {
            "status": "real",
            "role": "finite_open_s21_diagnostic_not_gate",
            "fqLB_hz": 5.0e9,
            "frLB_hz": fr0_hz,
            "physical_readout_hz": frq_hz,
            "readout_shift_hz": frq_hz - fr0_hz,
            "radicand_hz2": (frq_hz - fr0_hz) * (frq_hz - 5.0e9),
            "g_hz": g_values[index],
        }
        mode["finite_probe_mode_assignment"] = (
            "finite_probe_mode_assignment_no_slot_ownership_gate"
        )
        mode["diagonal_preserving_coupling_off_mode"] = {
            "frequency_hz": fr0_hz,
            "frequency_grid_sha256": loaded_hash,
            "measured_trace_id": probe["diagonal_preserving_coupling_off_measured_trace_id"],
            "reference_trace_id": probe["reference_trace_id"],
            "finite_probe_mode_assignment": (
                "finite_probe_mode_assignment_no_slot_ownership_gate"
            ),
        }
        mode["readout_shift_hz"] = frq_hz - fr0_hz
        mode["predicted_qubit_pole_hz"] = predicted_qubit_hz
        mode["qubit_crosscheck_residual_hz"] = fitted_qubit_hz - predicted_qubit_hz
        mode["qubit_crosscheck_role"] = "finite_probe_diagnostic_not_gate"
        mode["qubit_mode"] = {
            "frequency_hz": fitted_qubit_hz,
            "frequency_grid_sha256": qubit_hash,
            "measured_trace_id": probe["qubit_measured_trace_id"],
        }
    pair_trace = record["traces"]["pair"]
    pair_trace.update(
        {
            "system": "B",
            "frequency_grid_sha256": pair_hash,
            "measured_trace_id": f"synthetic-pair|grid_sha256={pair_hash}",
            "reference_trace_id": f"synthetic-pair-reference|grid_sha256={pair_hash}",
            "frequencies_hz": pair_grid,
            "s21": complex_values(len(pair_grid), 0.03),
            "reference_s21": complex_values(len(pair_grid), 0.001),
        }
    )
    closure_observed = complex_values(len(pair_grid), 0.025)
    record["traces"]["system_c"] = {
        "closure_frequencies_hz": pair_grid,
        "closure_observed_s21": closure_observed,
        "closure_predicted_s21": closure_observed,
        "closure_residual_s21": [{"real": 0.0, "imag": 0.0} for _ in pair_grid],
    }
    intrinsic = record["traces"]["intrinsic"]
    intrinsic_hash = validator.frequency_grid_sha256(intrinsic["frequencies_hz"])
    intrinsic["frequency_grid_sha256"] = intrinsic_hash
    intrinsic["trace_id"] = f"synthetic-loaded-notch|grid_sha256={intrinsic_hash}"
    record["diagnostics"]["notch"]["trace_id"] = intrinsic["trace_id"]
    record["traces"]["intrinsic_reference"] = copy.deepcopy(intrinsic)
    record["traces"]["intrinsic_reference"]["trace_id"] = f"synthetic-reference-notch|grid_sha256={intrinsic_hash}"
    record["diagnostics"]["reference_notch"]["trace_id"] = record["traces"]["intrinsic_reference"]["trace_id"]
    record["diagnostics"]["notch"]["reference_trace_id"] = record["traces"]["intrinsic_reference"]["trace_id"]
    diagnostics = record["diagnostics"]
    diagnostics["loaded_frequency_grid_sha256"] = loaded_hash
    diagnostics["pair_frequency_grid_sha256"] = pair_hash
    diagnostics["filter_loaded_bare_reference_id"] = (
        f"synthetic-filter-reference|grid_sha256={loaded_hash}"
    )
    common_reference_id = f"synthetic-common-readout-reference|grid_sha256={loaded_hash}"
    diagnostics["extraction_contract"] = (
        validator.D3_EXTRACTION_CONTRACT
    )
    filter_loaded_bare_hz = record["metrics"]["filter_loaded_bare_hz"]
    diagnostics["frequency_layers"] = {
        "fqB_hz": 5.1e9,
        "frB_hz": 6.02e9,
        "fpB_hz": 6.03e9,
        "fqLB_hz": 5.0e9,
        "frLB_hz": common_readout_hz,
        "fpLB_hz": filter_loaded_bare_hz,
        "physical_qubit_like_hz": 4.99e9,
        "physical_readout_like_hz": common_readout_hz + 10.0e6,
    }
    system_b_observed_poles = sorted(diagnostics["vector_crosscheck_poles_hz"])
    frequency_row_values = {
        "fqB_hz": diagnostics["frequency_layers"]["fqB_hz"],
        "frB_hz": diagnostics["frequency_layers"]["frB_hz"],
        "fpB_hz": diagnostics["frequency_layers"]["fpB_hz"],
        "fqLB_hz": diagnostics["frequency_layers"]["fqLB_hz"],
        "frLB_hz": diagnostics["frequency_layers"]["frLB_hz"],
        "fpLB_hz": diagnostics["frequency_layers"]["fpLB_hz"],
        "system_a_q_like_hz": diagnostics["frequency_layers"]["physical_qubit_like_hz"],
        "system_a_r_like_hz": diagnostics["frequency_layers"]["physical_readout_like_hz"],
        "system_b_lower_pole_hz": system_b_observed_poles[0],
        "system_b_upper_pole_hz": system_b_observed_poles[1],
        "system_c_q_window_pole_hz": 5.0e9,
        "system_c_pair_lower_pole_hz": 5.9e9,
        "system_c_pair_upper_pole_hz": 6.1e9,
    }
    diagnostics["final_validation_frequency_rows"] = [
        {
            "quantity_id": quantity_id,
            "layer": layer,
            "system_tag": system_tag,
            "frequency_hz": frequency_row_values[quantity_id],
            "source_method": source_method,
            "ownership_label": ownership_label,
            "cost_function_role": cost_role,
        }
        for quantity_id, layer, system_tag, source_method, ownership_label, cost_role
        in validator.FINAL_VALIDATION_FREQUENCY_ROWS
    ]
    diagnostics["closed_modal_projection"] = {
        "g_hz": 90.0e6,
        "projection": {
            "contract_id": "d3-closed-modal-projection-eligibility.v3",
            "full_basis_reconstruction": {
                "mode_count": 8,
                "maximum_bdg_residual_hz": 1.0e-3,
            },
            "two_mode_reduced_closure": {
                "status": "eligible",
                "reduced_model_eligible": True,
                "failure_reasons": [],
                "maximum_bdg_residual_hz": 0.5e6,
                "maximum_rwa_minus_bdg_hz": 0.4e6,
                "maximum_residual_gate_hz": 1.0e6,
            },
        },
        "reduced_model_eligibility": {
            "model": "system_a_two_mode_qubit_readout",
            "eligible": True,
            "failure_reasons": [],
            "threshold_hz": 1.0e6,
            "maximum_bdg_residual_hz": 0.5e6,
            "maximum_rwa_minus_bdg_hz": 0.4e6,
            "audit": {},
        },
    }
    diagnostics["common_readout_loaded_bare_reference_id"] = common_reference_id
    diagnostics["common_readout_loaded_bare"] = {
        "reference_contract_id": common_reference_id,
        "frequency_hz": common_readout_hz,
        "linewidth_hz": 0.0,
        "readout_endpoint_shunts": [
            {
                "id": "Cr_attachment_LB",
                "capacitance_fF": 10.076335877862595,
                "provenance": "Schur_reduction_of_qubit_common_coordinate",
            },
        ],
    }
    diagnostics["systems"] = {
        "A": {
            "id": "qubit-readout-feedline",
            "common_readout_reference_id": common_reference_id,
            "active_couplings": ["physical_Cr1", "physical_Cr2"],
            "off_couplings": ["J"],
            "metric_ownership": ["fqLB", "g_hz"],
        },
        "B": {
            "id": "readout-filter-feedline",
            "common_readout_reference_id": common_reference_id,
            "active_couplings": ["J", "filter_Cext"],
            "off_couplings": ["g"],
            "metric_ownership": ["fpLB", "j_hz", "notch_hz"],
        },
        "C": {
            "id": "qubit-readout-filter-feedline",
            "common_readout_reference_id": common_reference_id,
            "active_couplings": ["physical_Cr1", "physical_Cr2", "J", "filter_Cext"],
            "off_couplings": ["direct_qubit_filter_coupling"],
            "metric_ownership": ["three_mode_poles", "complex_s21_closure"],
        },
    }
    diagnostics["system_c_closure"] = {
        "physical_extraction_status": "valid",
        "reduced_model_eligible": True,
        "failure_reasons": [],
        "direct_qubit_filter_coupling_hz": 0.0,
        "physical_observed_poles": {
            "qubit_window_pole_hz": 5.0e9,
            "pair_window_poles_hz": [5.9e9, 6.1e9],
        },
        "pole_closure": {
            "status": "eligible",
            "reduced_model_eligible": True,
            "predicted_poles_hz": [5.0e9, 5.9e9, 6.1e9],
            "observed_poles_hz": [5.0e9, 5.9e9, 6.1e9],
            "residuals_hz": [0.0, 0.0, 0.0],
            "maximum_residual_hz": 0.0,
            "maximum_residual_threshold_hz": 1.0e6,
        },
        "response": {
            "status": "eligible",
            "reduced_model_eligible": True,
            "failure_reasons": [],
            "model": "fixed_primitive_g_J_three_mode_filter_response",
            "metrics": {
                "complex_r2": 1.0,
                "abs_r2": 1.0,
                "phase_rmse_rad": 0.0,
            },
            "thresholds": {
                "min_complex_r2": 0.99,
                "min_abs_r2": 0.99,
                "max_phase_rmse_rad": 0.1,
                "min_phase_magnitude": 0.0,
            },
        },
    }
    diagnostics["physical_evaluation_status"] = "valid"
    diagnostics["reduced_model_eligibility"] = {
        "status": "eligible",
        "eligible": True,
        "failure_reasons": [],
        "system_a": diagnostics["closed_modal_projection"]["reduced_model_eligibility"],
        "system_c": {"eligible": True, "failure_reasons": []},
    }
    record["physical_evaluation_status"] = "valid"
    record["reduced_model_eligibility"] = diagnostics["reduced_model_eligibility"]
    for index, mode in enumerate(diagnostics["readout_probe_modes"]):
        probe = record["traces"]["readout_probes"][index]
        mode["frequency_grid_sha256"] = loaded_hash
        mode["measured_trace_id"] = probe["measured_trace_id"]
        mode["reference_trace_id"] = probe["reference_trace_id"]
    j_provenance = diagnostics["j_fit"]["provenance"]
    j_provenance["measured_trace_id"] = pair_trace["measured_trace_id"]
    j_provenance["empty_feedline_trace_id"] = pair_trace["reference_trace_id"]
    j_provenance["readout_loaded_bare_reference_id"] = common_reference_id
    write_json(optimizer_run / "final_diagnostics.json", final_diagnostics)

    inventory = {
        "execution_sha256": execution_hash,
        "config_snapshot_sha256": validator.file_sha256(optimizer_run / "config_snapshot.json"),
        "files": inventory_rows,
    }
    write_json(optimizer_run / "hash_inventory.json", inventory)
    validator.validate_artifacts(optimizer_run, workspace)
    return optimizer_run


def nominal_payload(workspace: Path, optimizer_run: Path) -> dict[str, dict]:
    identity = validator.optimizer_candidate_identity(optimizer_run)
    optimizer_manifest = read_json(optimizer_run / "condition_manifest.json")
    optimizer_contract = optimizer_manifest["contract"]
    optimizer_inventory = read_json(optimizer_run / "hash_inventory.json")
    inventory_by_id = {item["id"]: item for item in optimizer_inventory["files"]}
    config = read_json(optimizer_run / "config_snapshot.json")
    source_paths = {
        "target": config["target_contract"]["workspace_relative_path"],
        "conditions": inventory_by_id["optimizer_conditions"]["path"],
        "config_snapshot": (optimizer_run / "config_snapshot.json").relative_to(workspace).as_posix(),
        "q2d": inventory_by_id["orpen_case_json"]["path"],
        "seed": inventory_by_id["seed_csv"]["path"],
        "common": inventory_by_id["d3_purcell_common"]["path"],
        "evaluator": inventory_by_id["d3_coupled_evaluator"]["path"],
        "semantic_hash": inventory_by_id["d3_semantic_hash"]["path"],
        "qubit_input": inventory_by_id["floating_qubit_nominal"]["path"],
        "qubit_input_loader": inventory_by_id["d3_floating_qubit_input_loader"]["path"],
        "runner": workspace_file(workspace, "workbench/runtime/runner.jl", "# runner\n").relative_to(workspace).as_posix(),
        "nominal_runtime": workspace_file(workspace, "workbench/runtime/nominal.jl", "# nominal\n").relative_to(workspace).as_posix(),
    }
    sources = [
        {"id": source_id, "path": path, "sha256": validator.file_sha256(workspace / path)}
        for source_id, path in sorted(source_paths.items())
    ]
    source_by_id = {item["id"]: item for item in sources}
    conditions_path = workspace / source_paths["conditions"]
    conditions = validator.load_json(conditions_path.parent, conditions_path.name)
    layout = identity["layout_specs"]
    layout_metrics = {
        item["name"]: item
        for item in layout["breakdown"]["metrics"]
        if item["weight"] > 0
    }
    record = copy.deepcopy(read_json(optimizer_run / "final_diagnostics.json")["record"])
    record_metrics = record["metrics"]
    operands = [
        {
            "id": metric_id,
            "unit": "Hz",
            "target": item["target"],
            "observed": record_metrics[metric_id],
            "scale": item["scale"],
            "normalized_residual": (record_metrics[metric_id] - item["target"]) / item["scale"],
        }
        for metric_id, item in sorted(layout_metrics.items())
    ]
    notch_target = layout_metrics["notch_hz"]["target"]
    filter_observed = record_metrics["filter_loaded_bare_hz"]
    declared_stop_ghz = 7.0
    contract = {
        "analysis_kind": "nominal",
        "source_optimizer": {
            "run_id": identity["run_id"],
            "run_directory": optimizer_run.relative_to(workspace).as_posix(),
            "optimizer_id": identity["optimizer_id"],
            "optimizer_contract_sha256": identity["optimizer_contract_sha256"],
            "optimizer_identity_sha256": identity["optimizer_identity_sha256"],
            "layout_specs_raw_sha256": identity["layout_specs_raw_sha256"],
            "candidate_id": identity["candidate_id"],
            "candidate_sha256": identity["candidate_sha256"],
        },
        "bound_identities": {
            "target_sha256": source_by_id["target"]["sha256"],
            "conditions_contract_sha256": validator.semantic_value_sha256(
                {key: value for key, value in conditions.items() if key != "sol_review"}
            ),
            "conditions_file_sha256": source_by_id["conditions"]["sha256"],
            "config_snapshot_sha256": source_by_id["config_snapshot"]["sha256"],
            "q2d_sha256": source_by_id["q2d"]["sha256"],
            "seed_sha256": source_by_id["seed"]["sha256"],
            "floating_qubit_input_sha256": source_by_id["qubit_input"]["sha256"],
            "floating_qubit_loader_sha256": source_by_id["qubit_input_loader"]["sha256"],
            "floating_qubit_model_id": "synthetic-floating-qubit",
            "layout_specs_raw_sha256": identity["layout_specs_raw_sha256"],
            "candidate_sha256": identity["candidate_sha256"],
            "optimizer_identity_sha256": identity["optimizer_identity_sha256"],
        },
        "selection": {
            key: optimizer_contract["selection"][key]
            for key in ("case_id", "target_set_id", "slot_target_ghz")
        },
        "execution": {
            "fresh_process": True,
            "fresh_evaluator": True,
            "capture_traces": True,
            "optimizer_cache_allowed": False,
            "evaluation_budget": 1,
        },
        "variation": {"kind": "none", "parameters": []},
        "source_hashes": sources,
    }
    validation_hash = validator.semantic_value_sha256(
        {
            "schema_version": validator.NOMINAL_MANIFEST_SCHEMA,
            "semantic_hash_framing": validator.SEMANTIC_HASH_FRAMING,
            "contract": contract,
        }
    )
    frequency_step_hz = 500.0e6
    wide_frequencies = [
        notch_target - 500.0e6 + index * frequency_step_hz
        for index in range(
            int(round((declared_stop_ghz * 1.0e9 - (notch_target - 500.0e6)) / frequency_step_hz)) + 1
        )
    ]
    record["traces"]["intrinsic_wide"] = {
        "frequency_grid_sha256": validator.frequency_grid_sha256(wide_frequencies),
        "frequencies_hz": wide_frequencies,
        "z21_ptc": [
            {"real": 0.0, "imag": float(index + 1)}
            for index in range(len(wide_frequencies))
        ],
        "range_provenance": {
            "contract_id": "d3-intrinsic-wide-final-capture-v1",
            "scope": "final_capture_only",
            "start_hz": notch_target - 500.0e6,
            "stop_hz": declared_stop_ghz * 1.0e9,
            "frequency_step_hz": frequency_step_hz,
            "notch_target_hz": notch_target,
            "start_margin_below_notch_hz": 500.0e6,
            "filter_loaded_bare_hz": filter_observed,
            "required_minimum_stop_hz": filter_observed + 500.0e6,
            "declared_design_scan_stop_ghz": declared_stop_ghz,
            "stop_role": "conservative_no_cext_intrinsic_resonator_upper_bound",
        },
    }
    return {
        "validation_manifest.json": {
            "schema_version": validator.NOMINAL_MANIFEST_SCHEMA,
            "semantic_hash_framing": validator.SEMANTIC_HASH_FRAMING,
            "validation_contract_sha256": validation_hash,
            "contract": contract,
        },
        "layout_specs_snapshot.json": {
            "validation_contract_sha256": validation_hash,
            "layout_specs_raw_sha256": identity["layout_specs_raw_sha256"],
            "layout_specs": layout,
        },
        "hash_inventory.json": {"validation_contract_sha256": validation_hash, "files": sources},
        "nominal_evaluation.json": {
            "validation_contract_sha256": validation_hash,
            "analysis_kind": "nominal",
            "independent_validation": True,
            "evaluation_count": 1,
            "variation": {"kind": "none", "parameters": []},
            "record": record,
        },
        "validation_summary.json": {
            "validation_contract_sha256": validation_hash,
            "analysis_kind": "nominal",
            "human_acceptance_claim": None,
            "objective_operands": operands,
        },
        "status.json": {
            "validation_contract_sha256": validation_hash,
            "analysis_kind": "nominal",
            "state": "completed",
            "artifact_role": "view_only_validation",
        },
    }


def rehash_payload(payload: dict[str, dict]) -> None:
    manifest = payload["validation_manifest.json"]
    new_hash = validator.semantic_value_sha256(
        {
            "schema_version": validator.NOMINAL_MANIFEST_SCHEMA,
            "semantic_hash_framing": validator.SEMANTIC_HASH_FRAMING,
            "contract": manifest["contract"],
        }
    )
    for artifact in payload.values():
        artifact["validation_contract_sha256"] = new_hash


def write_exact_six(directory: Path, payload: dict[str, dict]) -> None:
    directory.mkdir(parents=True)
    for name, value in payload.items():
        write_json(directory / name, value)


class D3NominalReviewValidationTest(unittest.TestCase):
    def make_fixture(self, temporary: str) -> tuple[Path, Path, Path, dict[str, dict]]:
        workspace = Path(temporary) / "workspace"
        workspace.mkdir()
        optimizer = current_optimizer_fixture(workspace)
        payload = nominal_payload(workspace, optimizer)
        nominal = workspace / "workbench/build/research/d3_nominal_validation_v1/nominal-a"
        write_exact_six(nominal, payload)
        return workspace, optimizer, nominal, payload

    def test_cross_language_shaped_current_exact_six_is_accepted(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            workspace, optimizer, nominal, _ = self.make_fixture(temporary)
            validated = validator.validate_nominal_artifacts(nominal, optimizer, workspace)
            self.assertEqual(validated["record"]["status"], "valid")
            residuals = [
                mode["qubit_crosscheck_residual_hz"]
                for mode in validated["record"]["diagnostics"]["readout_probe_modes"]
            ]
            self.assertTrue(all(abs(value) > 1.0e6 for value in residuals))
            self.assertEqual(
                validated["record"]["diagnostics"]["zero_probe_lower_pole_crosscheck"]["residual_hz"],
                0.0,
            )
            diagnostics = validated["record"]["diagnostics"]
            zero_probe_readout_hz = diagnostics["common_readout_loaded_bare"]["frequency_hz"]
            finite_probe_readout_hz = [
                mode["diagonal_preserving_coupling_off_mode"]["frequency_hz"]
                for mode in diagnostics["readout_probe_modes"]
            ]
            self.assertGreater(
                max(abs(value - zero_probe_readout_hz) for value in finite_probe_readout_hz),
                115.0e6,
            )

    def test_legacy_optimizer_cannot_back_independent_nominal_validation(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            workspace, _, nominal, _ = self.make_fixture(temporary)
            with self.assertRaisesRegex(validator.ArtifactContractError, "incompatible historical"):
                validator.validate_nominal_artifacts(nominal, LEGACY_RUN, workspace)

    def test_ineligible_reduced_models_preserve_valid_physical_records(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            workspace, optimizer, nominal, payload = self.make_fixture(temporary)
            record = payload["nominal_evaluation.json"]["record"]
            diagnostics = record["diagnostics"]
            two_mode = diagnostics["closed_modal_projection"]["projection"]["two_mode_reduced_closure"]
            two_mode.update(
                {
                    "status": "ineligible",
                    "reduced_model_eligible": False,
                    "failure_reasons": [
                        "two_mode_bdg_poles_disagree_with_exact_physical_poles",
                        "two_mode_rwa_disagrees_with_two_mode_bdg",
                    ],
                    "maximum_bdg_residual_hz": 75.0e6,
                    "maximum_rwa_minus_bdg_hz": 1.54e6,
                }
            )
            system_a = diagnostics["closed_modal_projection"]["reduced_model_eligibility"]
            system_a.update(
                {
                    "eligible": False,
                    "failure_reasons": list(two_mode["failure_reasons"]),
                    "maximum_bdg_residual_hz": 75.0e6,
                    "maximum_rwa_minus_bdg_hz": 1.54e6,
                }
            )
            reduced = diagnostics["reduced_model_eligibility"]
            reduced.update(
                {
                    "status": "ineligible",
                    "eligible": False,
                    "failure_reasons": [f"system_a:{reason}" for reason in two_mode["failure_reasons"]],
                    "system_a": system_a,
                }
            )
            record["reduced_model_eligibility"] = copy.deepcopy(reduced)
            for name, value in payload.items():
                write_json(nominal / name, value)
            validated = validator.validate_nominal_artifacts(nominal, optimizer, workspace)
            self.assertEqual(validated["record"]["physical_evaluation_status"], "valid")
            self.assertFalse(validated["record"]["reduced_model_eligibility"]["eligible"])
            self.assertEqual(validated["record"]["metrics"]["g_hz"], 90.0e6)

        with tempfile.TemporaryDirectory() as temporary:
            workspace, optimizer, nominal, payload = self.make_fixture(temporary)
            record = payload["nominal_evaluation.json"]["record"]
            diagnostics = record["diagnostics"]
            response = diagnostics["system_c_closure"]["response"]
            response.update(
                {
                    "status": "ineligible",
                    "reduced_model_eligible": False,
                    "failure_reasons": ["complex_r2_undefined", "magnitude_r2_undefined"],
                }
            )
            response["metrics"]["complex_r2"] = None
            response["metrics"]["abs_r2"] = None
            system_c_closure = diagnostics["system_c_closure"]
            system_c_closure.update(
                {
                    "reduced_model_eligible": False,
                    "failure_reasons": [
                        "three_mode_response:complex_r2_undefined",
                        "three_mode_response:magnitude_r2_undefined",
                    ],
                }
            )
            reduced = diagnostics["reduced_model_eligibility"]
            reduced.update(
                {
                    "status": "ineligible",
                    "eligible": False,
                    "failure_reasons": [
                        "system_c:three_mode_response:complex_r2_undefined",
                        "system_c:three_mode_response:magnitude_r2_undefined",
                    ],
                    "system_c": {
                        "eligible": False,
                        "failure_reasons": list(system_c_closure["failure_reasons"]),
                    },
                }
            )
            record["reduced_model_eligibility"] = copy.deepcopy(reduced)
            for name, value in payload.items():
                write_json(nominal / name, value)
            validated = validator.validate_nominal_artifacts(nominal, optimizer, workspace)
            self.assertEqual(validated["record"]["physical_evaluation_status"], "valid")
            self.assertIsNone(
                validated["record"]["diagnostics"]["system_c_closure"]["response"]["metrics"]["complex_r2"]
            )

    def test_selection_unit_source_and_wide_provenance_tampering_fail(self) -> None:
        mutators = {
            "nominal semantic framing": lambda payload, workspace, optimizer: payload["validation_manifest.json"].update({"semantic_hash_framing": "wrong-framing"}),
            "selection": lambda payload, workspace, optimizer: payload["validation_manifest.json"]["contract"]["selection"].update({"slot_target_ghz": 6.24}),
            "objective unit": lambda payload, workspace, optimizer: payload["validation_summary.json"]["objective_operands"][0].update({"unit": "MHz"}),
            "wide provenance": lambda payload, workspace, optimizer: payload["nominal_evaluation.json"]["record"]["traces"]["intrinsic_wide"]["range_provenance"].update({"start_margin_below_notch_hz": 400.0e6}),
            "wide missing point": lambda payload, workspace, optimizer: (
                payload["nominal_evaluation.json"]["record"]["traces"]["intrinsic_wide"]["frequencies_hz"].pop(1),
                payload["nominal_evaluation.json"]["record"]["traces"]["intrinsic_wide"]["z21_ptc"].pop(1),
            ),
            "wide wrong step": lambda payload, workspace, optimizer: payload["nominal_evaluation.json"]["record"]["traces"]["intrinsic_wide"]["range_provenance"].update({"frequency_step_hz": 250.0e6}),
            "wide wrong hash": lambda payload, workspace, optimizer: payload["nominal_evaluation.json"]["record"]["traces"]["intrinsic_wide"].update({"frequency_grid_sha256": "0" * 64}),
            "filter grid hash": lambda payload, workspace, optimizer: payload["nominal_evaluation.json"]["record"]["traces"]["filter"].update({"frequency_grid_sha256": "0" * 64}),
            "readout grid hash": lambda payload, workspace, optimizer: payload["nominal_evaluation.json"]["record"]["traces"]["readout_probes"][0].update({"frequency_grid_sha256": "0" * 64}),
            "pair grid hash": lambda payload, workspace, optimizer: payload["nominal_evaluation.json"]["record"]["traces"]["pair"].update({"frequency_grid_sha256": "0" * 64}),
            "diagnostics loaded grid hash": lambda payload, workspace, optimizer: payload["nominal_evaluation.json"]["record"]["diagnostics"].update({"loaded_frequency_grid_sha256": "0" * 64}),
            "diagnostics pair grid hash": lambda payload, workspace, optimizer: payload["nominal_evaluation.json"]["record"]["diagnostics"].update({"pair_frequency_grid_sha256": "0" * 64}),
            "historical extraction contract": lambda payload, workspace, optimizer: payload["nominal_evaluation.json"]["record"]["diagnostics"].update({"extraction_contract": "legacy"}),
            "missing final-validation frequency rows": lambda payload, workspace, optimizer: payload["nominal_evaluation.json"]["record"]["diagnostics"].pop("final_validation_frequency_rows"),
            "false System B pole ownership": lambda payload, workspace, optimizer: payload["nominal_evaluation.json"]["record"]["diagnostics"]["final_validation_frequency_rows"][8].update({"ownership_label": "readout_like"}),
            "System C pair observation mismatch": lambda payload, workspace, optimizer: payload["nominal_evaluation.json"]["record"]["diagnostics"]["system_c_closure"]["physical_observed_poles"].update({"pair_window_poles_hz": [5.8e9, 6.1e9]}),
            "System B common reference mismatch": lambda payload, workspace, optimizer: payload["nominal_evaluation.json"]["record"]["diagnostics"]["systems"]["B"].update({"common_readout_reference_id": "different"}),
            "System C pole residual": lambda payload, workspace, optimizer: payload["nominal_evaluation.json"]["record"]["diagnostics"]["system_c_closure"]["pole_closure"].update({"residuals_hz": [0.0, 0.0, 2.0e6]}),
            "System C complex response residual": lambda payload, workspace, optimizer: payload["nominal_evaluation.json"]["record"]["traces"]["system_c"]["closure_residual_s21"][0].update({"real": 1.0}),
            "modal RWA closure": lambda payload, workspace, optimizer: payload["nominal_evaluation.json"]["record"]["diagnostics"]["closed_modal_projection"]["projection"]["two_mode_reduced_closure"].update({"maximum_rwa_minus_bdg_hz": 2.0e6}),
            "missing diagnostics": lambda payload, workspace, optimizer: payload["nominal_evaluation.json"]["record"].pop("diagnostics"),
            "missing filter trace": lambda payload, workspace, optimizer: payload["nominal_evaluation.json"]["record"]["traces"].pop("filter"),
            "missing pair trace": lambda payload, workspace, optimizer: payload["nominal_evaluation.json"]["record"]["traces"].pop("pair"),
            "missing readout probes": lambda payload, workspace, optimizer: payload["nominal_evaluation.json"]["record"]["traces"].pop("readout_probes"),
        }
        for label, mutate in mutators.items():
            with self.subTest(label=label), tempfile.TemporaryDirectory() as temporary:
                workspace, optimizer, nominal, payload = self.make_fixture(temporary)
                mutate(payload, workspace, optimizer)
                rehash_payload(payload)
                shutil.rmtree(nominal)
                write_exact_six(nominal, payload)
                with self.assertRaises(validator.ArtifactContractError):
                    validator.validate_nominal_artifacts(nominal, optimizer, workspace)

        with tempfile.TemporaryDirectory() as temporary:
            workspace, optimizer, nominal, _ = self.make_fixture(temporary)
            layout = read_json(optimizer / "layout_specs.json")
            layout["variables"][0]["unit"] = "fF"
            write_json(optimizer / "layout_specs.json", layout)
            with self.assertRaisesRegex(validator.ArtifactContractError, "must use 'um'"):
                validator.validate_nominal_artifacts(nominal, optimizer, workspace)

        with tempfile.TemporaryDirectory() as temporary:
            workspace, optimizer, nominal, payload = self.make_fixture(temporary)
            alternate_target = workspace / "docs/alternate-target.json"
            shutil.copy2(workspace / "docs/target.json", alternate_target)
            target_row = next(
                item for item in payload["validation_manifest.json"]["contract"]["source_hashes"]
                if item["id"] == "target"
            )
            target_row["path"] = alternate_target.relative_to(workspace).as_posix()
            payload["hash_inventory.json"]["files"] = payload["validation_manifest.json"]["contract"]["source_hashes"]
            rehash_payload(payload)
            shutil.rmtree(nominal)
            write_exact_six(nominal, payload)
            with self.assertRaisesRegex(validator.ArtifactContractError, "source 'target'"):
                validator.validate_nominal_artifacts(nominal, optimizer, workspace)

    def test_discovery_separates_unrelated_slots_from_matching_rejections(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            workspace, optimizer, nominal, payload = self.make_fixture(temporary)
            output_root = nominal.parent
            unrelated = copy.deepcopy(payload)
            unrelated["validation_manifest.json"]["contract"]["source_optimizer"]["run_id"] = "other-slot-run"
            rehash_payload(unrelated)
            write_exact_six(output_root / "nominal-other-slot", unrelated)
            rejected = copy.deepcopy(payload)
            rejected["status.json"]["state"] = "failed"
            write_exact_six(output_root / "nominal-matching-failed", rejected)
            report = validator.discover_nominal_validations(output_root, optimizer, workspace)
            self.assertEqual(len(report["valid"]), 1)
            self.assertEqual(len(report["rejected"]), 1)
            self.assertEqual(len(report["unrelated"]), 1)


if __name__ == "__main__":
    unittest.main()
