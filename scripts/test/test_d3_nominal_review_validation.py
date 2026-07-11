#!/usr/bin/env python3
"""Synthetic no-HB checks for the current D3 exact-six nominal contract."""

from __future__ import annotations

import copy
import importlib.util
import json
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
        "evaluator_settings": {"frequency_step_hz": 500.0e6},
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
    write_json(optimizer_run / "optimization_result.json", optimization)

    final_diagnostics = read_json(optimizer_run / "final_diagnostics.json")
    final_diagnostics["analysis_kind"] = "optimizer_internal_final_reproduction"
    final_diagnostics["independent_validation"] = False
    record = final_diagnostics["record"]
    loaded_grid = [5.5e9, 6.0e9, 6.5e9]
    pair_grid = [5.5e9, 6.0e9, 6.5e9]
    loaded_hash = validator.frequency_grid_sha256(loaded_grid)
    pair_hash = validator.frequency_grid_sha256(pair_grid)

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
            }
        )
    pair_trace = record["traces"]["pair"]
    pair_trace.update(
        {
            "frequency_grid_sha256": pair_hash,
            "measured_trace_id": f"synthetic-pair|grid_sha256={pair_hash}",
            "reference_trace_id": f"synthetic-pair-reference|grid_sha256={pair_hash}",
            "frequencies_hz": pair_grid,
            "s21": complex_values(len(pair_grid), 0.03),
            "reference_s21": complex_values(len(pair_grid), 0.001),
        }
    )
    diagnostics = record["diagnostics"]
    diagnostics["loaded_frequency_grid_sha256"] = loaded_hash
    diagnostics["pair_frequency_grid_sha256"] = pair_hash
    diagnostics["filter_loaded_bare_reference_id"] = (
        f"synthetic-filter-reference|grid_sha256={loaded_hash}"
    )
    diagnostics["readout_loaded_bare_reference_id"] = (
        f"synthetic-readout-reference|grid_sha256={loaded_hash}"
    )
    for index, mode in enumerate(diagnostics["readout_probe_modes"]):
        probe = record["traces"]["readout_probes"][index]
        mode["frequency_grid_sha256"] = loaded_hash
        mode["measured_trace_id"] = probe["measured_trace_id"]
        mode["reference_trace_id"] = probe["reference_trace_id"]
    j_provenance = diagnostics["j_fit"]["provenance"]
    j_provenance["measured_trace_id"] = pair_trace["measured_trace_id"]
    j_provenance["empty_feedline_trace_id"] = pair_trace["reference_trace_id"]
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

    def test_legacy_optimizer_cannot_back_independent_nominal_validation(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            workspace, _, nominal, _ = self.make_fixture(temporary)
            with self.assertRaisesRegex(validator.ArtifactContractError, "current per-Slot"):
                validator.validate_nominal_artifacts(nominal, LEGACY_RUN, workspace)

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
