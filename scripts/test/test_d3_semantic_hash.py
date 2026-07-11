#!/usr/bin/env python3
"""Golden Python consumer tests for the Julia-owned D3 semantic framing."""

from __future__ import annotations

import importlib.util
import json
import struct
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
VALIDATOR_PATH = REPO_ROOT / "scripts/build/plot_d3_final_diagnostics.py"
VECTORS_PATH = REPO_ROOT / "scripts/test/fixtures/d3_semantic_hash_vectors.v1.json"
CONDITIONS_PATH = REPO_ROOT / (
    "notebooks/pluto/D3 Intrinsic Purcell Filter Design/d3_optimizer_conditions.json"
)
EXPECTED_ACTUAL_CONDITIONS_SHA256 = (
    "56d10e9f39d2a78b43a703411ef9c5793bd1aeb2b01ece7cf7007f4cabecea19"
)

spec = importlib.util.spec_from_file_location("d3_semantic_hash_consumer", VALIDATOR_PATH)
if spec is None or spec.loader is None:
    raise ImportError(f"Could not load {VALIDATOR_PATH}")
validator = importlib.util.module_from_spec(spec)
spec.loader.exec_module(validator)


class D3SemanticHashTest(unittest.TestCase):
    def test_every_julia_golden_vector(self) -> None:
        fixture = json.loads(VECTORS_PATH.read_text(encoding="utf-8"))
        self.assertEqual(
            fixture["semantic_hash_framing"], validator.SEMANTIC_HASH_FRAMING
        )
        for vector in fixture["vectors"]:
            if "float64_hex_bits" in vector:
                value = struct.unpack(
                    ">d", bytes.fromhex(vector["float64_hex_bits"])
                )[0]
            else:
                value = vector["value"]
            with self.subTest(vector=vector["name"]):
                self.assertEqual(
                    validator.semantic_value_sha256(value), vector["expected_sha256"]
                )

    def test_actual_conditions_matches_external_expected_identity(self) -> None:
        fixture = json.loads(VECTORS_PATH.read_text(encoding="utf-8"))
        self.assertEqual(
            fixture["actual_conditions_without_sol_review_expected_sha256"],
            EXPECTED_ACTUAL_CONDITIONS_SHA256,
        )
        conditions = validator.load_json(CONDITIONS_PATH.parent, CONDITIONS_PATH.name)
        payload = {key: value for key, value in conditions.items() if key != "sol_review"}
        self.assertEqual(
            validator.semantic_value_sha256(payload),
            EXPECTED_ACTUAL_CONDITIONS_SHA256,
        )

    def test_producer_write_read_rehash_preserves_identity(self) -> None:
        producer_value = {
            "one": 1.0,
            "exponent": 1.0e8,
            "negative_zero": -0.0,
            "fraction": 1.5,
            "nested": [2.0, -3.25],
        }
        producer_hash = validator.semantic_value_sha256(producer_value)
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "payload.json"
            path.write_text(
                json.dumps(producer_value, allow_nan=False, separators=(",", ":")) + "\n",
                encoding="utf-8",
            )
            persisted_value = validator.load_json(path.parent, path.name)
        self.assertEqual(
            validator.semantic_value_sha256(persisted_value), producer_hash
        )

    def test_rejects_unsupported_semantic_values(self) -> None:
        for value in ({"量": 1}, float("inf"), object()):
            with self.subTest(value=repr(value)), self.assertRaises(
                validator.ArtifactContractError
            ):
                validator.semantic_value_sha256(value)


if __name__ == "__main__":
    unittest.main()
