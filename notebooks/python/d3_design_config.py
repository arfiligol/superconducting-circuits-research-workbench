from __future__ import annotations

import hashlib
import json
from pathlib import Path


CONFIG_JSON = (
    Path(__file__).resolve().parents[1]
    / "pluto"
    / "D3 Intrinsic Purcell Filter Design"
    / "d3_design_config.json"
)
WORKSPACE_ROOT = Path(__file__).resolve().parents[3]


def load_d3_design_config() -> dict[str, object]:
    return json.loads(CONFIG_JSON.read_text())


def load_d3_target_contract() -> dict[str, object]:
    """Load and integrity-check the canonical Super Repo Design Target.

    The Workbench config owns only the workspace path and expected identity;
    target values remain in the Super Repo JSON.
    """
    config = load_d3_design_config()
    reference = config["target_contract"]
    if not isinstance(reference, dict):
        raise TypeError("target_contract must be a JSON object")
    path = WORKSPACE_ROOT / str(reference["workspace_relative_path"])
    payload = path.read_bytes()
    observed = hashlib.sha256(payload).hexdigest()
    if observed != reference["expected_sha256"]:
        raise ValueError("Canonical D3 target hash changed; request agent review instead of editing hashes")
    target = json.loads(payload)
    if target["target_id"] != reference["expected_target_id"] or target["revision"] != reference["expected_revision"]:
        raise ValueError("Canonical D3 target identity does not match the Workbench config")
    return target


def variant_suffix(variant_id: str) -> str:
    return "" if variant_id == "baseline" else f"__{variant_id}"
