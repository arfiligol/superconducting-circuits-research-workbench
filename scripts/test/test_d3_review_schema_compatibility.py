#!/usr/bin/env python3
"""No-HB rejection and identity checks for current D3 review artifacts."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

from scripts.test.test_d3_nominal_review_validation import current_optimizer_fixture


REPO_ROOT = Path(__file__).resolve().parents[2]
WORKSPACE_ROOT = REPO_ROOT.parent
VALIDATOR_PATH = REPO_ROOT / "scripts/build/plot_d3_final_diagnostics.py"
LEGACY_RUN = REPO_ROOT / (
    "build/research/d3_coupled_optimizer_v1/"
    "20260710T213955009Z__d3-coupled-optimization-6ghz-design-target-v1__0c16418e6d15"
)

spec = importlib.util.spec_from_file_location("d3_review_validator", VALIDATOR_PATH)
if spec is None or spec.loader is None:
    raise ImportError(f"Could not load {VALIDATOR_PATH}")
validator = importlib.util.module_from_spec(spec)
spec.loader.exec_module(validator)


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, separators=(",", ":")) + "\n", encoding="utf-8")


class D3ReviewSchemaCompatibilityTest(unittest.TestCase):
    def test_validator_rejects_legacy_and_accepts_current_schema(self) -> None:
        with self.assertRaises(validator.ArtifactContractError):
            validator.validate_artifacts(LEGACY_RUN)

        with tempfile.TemporaryDirectory() as temporary:
            workspace = Path(temporary) / "workspace"
            workspace.mkdir()
            synthetic_run = current_optimizer_fixture(workspace)
            current = validator.validate_artifacts(synthetic_run)
            self.assertEqual(current["manifest_schema"], validator.SLOT_EXECUTION_MANIFEST_SCHEMA)
            manifest = read_json(synthetic_run / "condition_manifest.json")
            self.assertEqual(current["artifact_hash"], manifest["execution_sha256"])
            self.assertEqual(current["artifact_hash_label"], "execution")

    def test_current_optimizer_identity_and_wrapper_tampering_fail(self) -> None:
        def mutate_manifest_contract(run: Path) -> None:
            manifest = read_json(run / "condition_manifest.json")
            manifest["contract"]["tampered"] = True
            write_json(run / "condition_manifest.json", manifest)

        def mutate_semantic_framing(run: Path) -> None:
            manifest = read_json(run / "condition_manifest.json")
            manifest["semantic_hash_framing"] = "wrong-framing"
            write_json(run / "condition_manifest.json", manifest)

        def mutate_inventory_identity(run: Path) -> None:
            inventory = read_json(run / "hash_inventory.json")
            inventory["execution_sha256"] = "0" * 64
            write_json(run / "hash_inventory.json", inventory)

        def mutate_config_snapshot(run: Path) -> None:
            config = read_json(run / "config_snapshot.json")
            config["tampered"] = True
            write_json(run / "config_snapshot.json", config)

        def mutate_consumed_files(run: Path) -> None:
            inventory = read_json(run / "hash_inventory.json")
            inventory["files"][0]["path"] = "different/source.json"
            write_json(run / "hash_inventory.json", inventory)

        def mutate_final_wrapper(run: Path) -> None:
            final = read_json(run / "final_diagnostics.json")
            final["independent_validation"] = True
            write_json(run / "final_diagnostics.json", final)

        cases = {
            "canonical execution identity": mutate_manifest_contract,
            "semantic framing": mutate_semantic_framing,
            "inventory top identity": mutate_inventory_identity,
            "config snapshot raw hash": mutate_config_snapshot,
            "consumed files exact equality": mutate_consumed_files,
            "optimizer final wrapper": mutate_final_wrapper,
        }
        for label, mutate in cases.items():
            with self.subTest(label=label), tempfile.TemporaryDirectory() as temporary:
                workspace = Path(temporary) / "workspace"
                workspace.mkdir()
                run = current_optimizer_fixture(workspace)
                mutate(run)
                with self.assertRaises(validator.ArtifactContractError):
                    validator.validate_artifacts(run)

    def test_notebook_adapter_normalizes_current_schema(self) -> None:
        target_path = WORKSPACE_ROOT / (
            "docs/design-targets/contracts/d3-intrinsic-interferometric-purcell-filter.v1.json"
        )
        target = read_json(target_path)
        target_hash = hashlib.sha256(target_path.read_bytes()).hexdigest()
        conditions = read_json(
            REPO_ROOT
            / "notebooks/pluto/D3 Intrinsic Purcell Filter Design/d3_optimizer_conditions.json"
        )
        config = read_json(LEGACY_RUN / "config_snapshot.json")
        conditions_hash = validator.semantic_value_sha256(
            {key: value for key, value in conditions.items() if key != "sol_review"}
        )
        metric_specs = [
            {"id": metric_id, **metric}
            for metric_id, metric in conditions["metric_specs"].items()
        ]
        variables = [
            {
                "id": variable_id,
                "value": 1.0,
                "unit": "test",
                "lower_bound": 0.5,
                "upper_bound": 1.5,
            }
            for variable_id in conditions["variable_order"]
        ]
        manifest = {
            "schema_version": validator.SLOT_EXECUTION_MANIFEST_SCHEMA,
            "semantic_hash_framing": validator.SEMANTIC_HASH_FRAMING,
            "execution_sha256": "c" * 64,
            "contract": {
                "manifest_id": "synthetic-current-slot",
                "purpose": "single_slot_layout_search_exploration",
                "target_contract": {
                    "target_id": target["target_id"],
                    "revision": target["revision"],
                    "sha256": target_hash,
                },
                "optimizer_conditions": {
                    "conditions_id": conditions["conditions_id"],
                    "sha256": conditions_hash,
                    "hash_framing": validator.SEMANTIC_HASH_FRAMING,
                    "sol_review": conditions["sol_review"],
                },
                "selection": {
                    "case_id": config["selected_case_id"],
                    "target_set_id": config["target_set_id"],
                    "slot_target_ghz": 6.0,
                    "source_row": {"target_set_id": config["target_set_id"]},
                    "source_row_sha256": validator.semantic_value_sha256(
                        {"target_set_id": config["target_set_id"]}
                    ),
                },
                "derived_metrics": metric_specs,
                "derived_variables": variables,
            },
        }
        normalized = validator.normalize_review_contract(
            manifest,
            config,
            target,
            target_hash,
            conditions,
        )
        self.assertEqual(normalized["selected_slot_ghz"], 6.0)
        self.assertEqual(normalized["selected_case_id"], config["selected_case_id"])
        self.assertEqual(
            [item["id"] for item in normalized["metric_specs"]],
            list(conditions["metric_specs"]),
        )
        self.assertEqual(len(normalized["variable_specs"]), len(conditions["variable_order"]))
        self.assertGreater(normalized["feedline"]["actual_return_loss_db"], 0.0)


if __name__ == "__main__":
    unittest.main()
