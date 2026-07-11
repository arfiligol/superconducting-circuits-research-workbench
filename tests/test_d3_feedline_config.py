"""Lock the D3 through-line to its explicit LC-only exploration contract."""

import json
import math
from pathlib import Path


def test_d3_feedline_is_independent_50_ohm_spec() -> None:
    config_path = (
        Path(__file__).parents[1]
        / "notebooks"
        / "pluto"
        / "D3 Intrinsic Purcell Filter Design"
        / "d3_design_config.json"
    )
    config = json.loads(config_path.read_text())
    feedline = config["feedline_rlgc"]

    assert feedline["l_per_m_h"] == 383.83846e-9
    assert feedline["c_per_m_f"] == 152.91443e-12
    assert feedline["r_per_m_ohm"] == feedline["g_per_m_s"] == 0.0
    assert feedline["r_status"] == feedline["g_status"] == "unavailable_in_source"
    assert feedline["loss_assumption"] == "r_and_g_assumed_zero_for_lossless_exploration_only"
    assert feedline["target_impedance_ohm"] == 50.0
    impedance = math.sqrt(feedline["l_per_m_h"] / feedline["c_per_m_f"])
    assert abs(impedance - 50.0) <= feedline["max_abs_impedance_error_ohm"]
    assert feedline["max_abs_impedance_error_role"] == "mismatch_screening_only"
    assert config["readout_minus_filter_detuning_mhz"] == -2.0
    assert "filter_minus_readout_detuning_mhz" not in config
    assert config["design_csv_role"] == "optimizer_seed_only"
    assert config["prior_simulation_evidence_status"] == "invalidated_by_50ohm_feedline_correction"
