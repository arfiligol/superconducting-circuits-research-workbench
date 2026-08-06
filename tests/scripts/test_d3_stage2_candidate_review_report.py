from __future__ import annotations

import copy
import importlib
import sys
from pathlib import Path
from typing import Any

import pytest

WORKBENCH_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(WORKBENCH_ROOT / "notebooks" / "python"))

report: Any = importlib.import_module("d3_stage2_candidate_review_report")


def _fixture() -> tuple[dict[str, Any], dict[str, float], dict[str, str]]:
    candidate = {
        "lr_open_m": 1.5e-3,
        "lr_short_m": 2.5e-3,
        "lc_m": 0.2e-3,
        "lp_open_m": 1.6e-3,
        "lp_short_m": 2.6e-3,
        "u_IDC": 55.0,
    }
    q2d = {"artifact_sha256": "a" * 64}
    receipt = {
        "schema_version": report._LC_QUALIFICATION_SCHEMA,
        "evidence_id": "candidate-receipt",
        "receipt_sha256": "b" * 64,
        "contract_id": report._LC_QUALIFICATION_CONTRACT,
        "policy_sha256": "c" * 64,
        "candidate_id": "candidate",
        "candidate": {
            "id": "candidate",
            "lengths": {key: candidate[key] for key in candidate if key != "u_IDC"},
            "u_IDC": candidate["u_IDC"],
        },
        "source": {
            "runner_sha256": "d" * 64,
            "spatial_receipt_sha256": "e" * 64,
            "convergence_runner_sha256": "f" * 64,
            "extractor_sha256": "1" * 64,
            "q2d_artifact_sha256": q2d["artifact_sha256"],
        },
        "frequency_deltas": {"f_r": 1.0e-3, "f_p": 1.0e-3, "f_n": 1.0e-2},
    }
    return receipt, candidate, q2d


def test_lc_qualification_binding_is_fail_closed() -> None:
    receipt, candidate, q2d = _fixture()
    assert (
        report._validate_lc_qualification_binding(receipt, receipt["policy_sha256"], candidate, q2d)
        == receipt
    )

    changed = copy.deepcopy(receipt)
    changed["candidate"]["u_IDC"] = 56.0
    with pytest.raises(ValueError, match="u_IDC disagrees"):
        report._validate_lc_qualification_binding(changed, changed["policy_sha256"], candidate, q2d)

    changed = copy.deepcopy(receipt)
    changed["frequency_deltas"]["f_n"] = 1.0001e-2
    with pytest.raises(ValueError, match="f_n delta exceeds"):
        report._validate_lc_qualification_binding(changed, changed["policy_sha256"], candidate, q2d)


def test_response_match_reuses_the_same_lc_receipt(monkeypatch: pytest.MonkeyPatch) -> None:
    receipt, _, _ = _fixture()
    q2d = {
        "artifact_id": "artifact",
        "artifact_sha256": receipt["source"]["q2d_artifact_sha256"],
        "topology_id": "continuous_upper_ground",
        "section_length_m": 1.0e-6,
        "mtl_section_length_m": 2.0e-6,
    }
    monkeypatch.setattr(report, "_fixed_line_q2d_snapshot", lambda _: q2d)
    qualification_fields = {
        "schema_version",
        "evidence_id",
        "receipt_sha256",
        "policy_sha256",
        "candidate_id",
        "source",
        "frequency_deltas",
    }
    response_match = {
        "mapping_id": "d3-frequency-priority-lc-qualification-receipt",
        "mapping_sha256": receipt["receipt_sha256"],
        "match_contract_id": receipt["contract_id"],
        "q2d_artifact_id": q2d["artifact_id"],
        "q2d_artifact_sha256": q2d["artifact_sha256"],
        "fixed_line_input_sha256": "2" * 64,
        "fixed_line_input_identity": {},
        "fixed_line_input_identity_canonical_json": "{}",
        "topology_id": q2d["topology_id"],
        "match_evidence": {
            "reference_model": {
                "role": "receipt_qualified_physical_length_to_equivalent_lc",
                "final_stage2_hb_model": "resolved_lumped_equivalent_circuit",
                "topology": ("two_grounded_head_open_tail_quarter_wave_resonators_with_mtl_window"),
                "terminal_coordinates": ["readout_open_tail", "filter_open_tail"],
                "diagonal_match_state": "mtl_mutual_terms_disabled_diagonal_loading_preserved",
                "bridge_match_state": "full_mtl_mutual_terms_preserved",
                "internal_coordinate_elimination": "frequency_dependent_dynamic_schur_complement",
                "section_length_m": q2d["section_length_m"],
                "mtl_section_length_m": q2d["mtl_section_length_m"],
            },
            "qualification_receipt": {field: receipt[field] for field in qualification_fields},
        },
    }
    report._validate_response_match_audit(response_match, q2d, receipt)

    changed = copy.deepcopy(response_match)
    changed["match_evidence"]["qualification_receipt"]["receipt_sha256"] = "3" * 64
    with pytest.raises(ValueError, match="disagrees with summary authority"):
        report._validate_response_match_audit(changed, q2d, receipt)
