"""Focused contract checks for the D3 Spring2025 initializer build helper."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

SCRIPT_PATH = (
    Path(__file__).resolve().parents[2] / "scripts" / "build" / "prepare_d3_forward_initial_spec.py"
)
SPEC = importlib.util.spec_from_file_location("prepare_d3_forward_initial_spec", SCRIPT_PATH)
if SPEC is None or SPEC.loader is None:
    raise ImportError(f"Could not load {SCRIPT_PATH}")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_initial_spec_is_strict_finite_source_first_four_slot_payload(tmp_path: Path) -> None:
    output = MODULE.write_initial_spec(tmp_path / "initial-spec.json")
    payload = json.loads(output.read_text(encoding="utf-8"), parse_constant=pytest.fail)

    assert set(payload) == {
        "schema_version",
        "status",
        "source",
        "assumptions",
        "reference_geometry",
        "slots",
    }
    assert payload["schema_version"] == "purcell.spring2025-initial-spec.v1"
    assert payload["status"] == "initializer_only"
    assert "process mismatch" in payload["source"]["provenance"]
    assert [slot["slot_hz"] for slot in payload["slots"]] == [
        5.9e9,
        6.0e9,
        6.1e9,
        6.2e9,
    ]
    for slot in payload["slots"]:
        assert slot["target_frequencies_hz"]["readout_loaded_bare_hz"] == pytest.approx(
            slot["slot_hz"] - 1.0e6
        )
        assert slot["target_frequencies_hz"]["filter_loaded_bare_hz"] == pytest.approx(
            slot["slot_hz"] + 1.0e6
        )
        assert slot["target_frequencies_hz"]["intrinsic_notch_hz"] == 5.0e9
        assert min(slot["lengths_um"].values()) > 0.0
        assert slot["round_trip_check_hz"]["fr_hz"] == pytest.approx(
            slot["target_frequencies_hz"]["readout_loaded_bare_hz"]
        )
        assert slot["round_trip_check_hz"]["fp_hz"] == pytest.approx(
            slot["target_frequencies_hz"]["filter_loaded_bare_hz"]
        )
        assert slot["round_trip_check_hz"]["fn_hz"] == pytest.approx(5.0e9)


def test_cli_requires_an_explicit_output_path() -> None:
    with pytest.raises(SystemExit, match="2"):
        MODULE.main([])
