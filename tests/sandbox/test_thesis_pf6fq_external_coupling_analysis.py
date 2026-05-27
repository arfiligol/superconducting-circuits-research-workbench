from __future__ import annotations

import ast
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[2]
STUDY_DIR = REPO_ROOT / "sandbox/thesis_pf6fq_external_coupling_analysis"
if str(STUDY_DIR) not in sys.path:
    sys.path.insert(0, str(STUDY_DIR))
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import config as thesis_plot_config  # noqa: E402
from config import (  # noqa: E402
    PLOTLY_DOWNLOAD_HEIGHT_PX,
    PLOTLY_DOWNLOAD_SCALE,
    PLOTLY_DOWNLOAD_SIZE_OVERRIDES,
    PLOTLY_DOWNLOAD_WIDTH_PX,
    PLOTLY_FIGURE_HEIGHT_PX,
    PLOTLY_FIGURE_WIDTH_PX,
    PLOTLY_MARGIN_RIGHT_PX,
    plotly_show_config,
)
from q3d_xy_external_coupling import (  # noqa: E402
    FloatingXYCapacitances,
    build_q3d_xy_circuit_definition,
    build_synthetic_c_eff_xy_capacitance,
    synthetic_c_eff_xy_target_range_ff,
)
from thesis_comparison_analysis import (  # noqa: E402
    add_t1_from_ceff_references,
    build_c_eff_reference_table,
    build_c_eff_xy_t1_fit_parameter_summary,
    build_c_eff_xy_t1_result_display_tables,
    build_c_eff_xy_t1_trend_table,
    build_lc_frequency_fit_display_table,
    build_on_resonance_re_y_table,
    build_re_y_ratio_display_table,
    build_resonance_frequency_ratio_display_table,
    compute_floating_c_d_xy_ff,
    fit_c_eff_xy_t1_trend,
    fit_lc_frequency_sweeps,
    fit_t1_capacitance,
    lc_frequency_ghz,
    load_layout_xy_im_y_traces,
    load_layout_xy_re_y_points,
    make_c_eff_reference_diagnostic_figure,
    make_c_eff_xy_t1_trend_comparison_figure,
    make_c_eff_xy_t1_trend_figure,
    make_im_trace_comparison_figure,
    make_re_y_ratio_figure,
    make_resonance_frequency_ratio_figure,
    make_t1_comparison_figure,
    match_layout_re_y_to_resonances,
)


def test_q3d_xy_circuit_uses_two_parallel_l_jun_branches() -> None:
    capacitances = FloatingXYCapacitances(
        qubit="Q0",
        source_path=Path("Q0_XY_Q3D_C_Matrix.m"),
        source_unit="fF",
        terminal_order=("Ground", "Pad1", "Pad2", "XY_Line"),
        cap_matrix_f=np.zeros((4, 4)),
        c_g1_f=10e-15,
        c_g2_f=11e-15,
        c_q_f=90e-15,
        c_xy1_f=2e-15,
        c_xy2_f=3e-15,
        c_xy_ground_f=1e-15,
        alpha=0.5,
        beta=0.5,
        c_d_xy_f=0.1e-15,
        c_dd_f=95e-15,
        c_eff_q_f=110e-15,
    )

    circuit = build_q3d_xy_circuit_definition(capacitances, l_jun_nh=24.0)
    expanded = circuit.expanded_definition
    lq_rows = [row for row in expanded.topology if row.name.startswith("Lq")]

    assert [row.name for row in lq_rows] == ["Lq1", "Lq2"]
    assert {(row.node1, row.node2) for row in lq_rows} == {("1", "2")}
    assert {expanded.component_specs[row.value_ref].value_ref for row in lq_rows} == {"L_jun"}
    assert expanded.resolve_component_value("Lq1") == 24.0
    assert expanded.resolve_component_value("Lq2") == 24.0


def test_synthetic_c_eff_xy_capacitance_redistributes_xy_coupling_only() -> None:
    template = FloatingXYCapacitances(
        qubit="Q0",
        source_path=Path("Q0_XY_Q3D_C_Matrix.m"),
        source_unit="fF",
        terminal_order=("Ground", "Pad1", "Pad2", "XY_Line"),
        cap_matrix_f=np.zeros((4, 4)),
        c_g1_f=102.0e-15,
        c_g2_f=101.0e-15,
        c_q_f=58.0e-15,
        c_xy1_f=0.2e-15,
        c_xy2_f=0.7e-15,
        c_xy_ground_f=1.0e-15,
        alpha=0.5,
        beta=0.5,
        c_d_xy_f=0.25e-15,
        c_dd_f=109.0e-15,
        c_eff_q_f=109.0e-15,
    )

    min_ff, max_ff = synthetic_c_eff_xy_target_range_ff(template)
    synthetic = build_synthetic_c_eff_xy_capacitance(
        template,
        target_c_eff_xy_ff=0.3,
        synthetic_id="S00",
    )

    assert min_ff < 0.3 < max_ff
    assert synthetic.qubit == "S00"
    assert synthetic.c_g1_f == template.c_g1_f
    assert synthetic.c_g2_f == template.c_g2_f
    assert synthetic.c_q_f == template.c_q_f
    assert np.isclose(synthetic.c_xy1_f + synthetic.c_xy2_f, template.c_xy1_f + template.c_xy2_f)
    assert np.isclose(synthetic.c_d_xy_f / 1e-15, 0.3)
    assert synthetic.c_xy1_f > 0.0
    assert synthetic.c_xy2_f > 0.0


def test_layout_xy_parsers_read_im_and_re_y_files(tmp_path: Path) -> None:
    raw_dir = tmp_path / "PF6FQ"
    for qubit in ("Q0", "Q1", "Q2"):
        qubit_dir = raw_dir / qubit
        qubit_dir.mkdir(parents=True)
        pd.DataFrame(
            {
                "L_jun [nH]": [22.0, 22.0, 24.0, 24.0],
                "Freq [GHz]": [4.4, 4.5, 4.2, 4.3],
                "im(Yt(Rectangle_T1,Rectangle_T1)) []": [-1e-3, 1e-3, -2e-3, 2e-3],
            }
        ).to_csv(qubit_dir / f"PF6FQ_{qubit}_XY_Im_Y11.csv", index=False)
        pd.DataFrame(
            {
                "Freq [GHz]": [4.3, 4.5],
                "0.02 * (1 - mag(St(Rectangle_T1,Rectangle_T1))**2) []": [
                    1e-9,
                    2e-9,
                ],
            }
        ).to_csv(qubit_dir / f"PF6FQ_{qubit}_XY_Re_Yin.csv", index=False)

    im_df = load_layout_xy_im_y_traces(raw_dir)
    re_df = load_layout_xy_re_y_points(raw_dir)

    assert set(im_df["qubit"]) == {"Q0", "Q1", "Q2"}
    assert set(re_df["qubit"]) == {"Q0", "Q1", "Q2"}
    assert len(im_df) == 12
    assert len(re_df) == 6


def test_layout_re_y_match_marks_sparse_unmatched_points() -> None:
    layout_resonances = pd.DataFrame(
        {
            "source": ["Layout", "Layout"],
            "qubit": ["Q0", "Q0"],
            "l_jun_nh": [22.0, 24.0],
            "frequency_ghz": [4.501, 4.302],
            "fallback": [False, False],
            "crossed": [True, True],
        }
    )
    re_points = pd.DataFrame(
        {
            "source": ["Layout"],
            "qubit": ["Q0"],
            "re_y_frequency_ghz": [4.302],
            "re_y_s": [2.86e-9],
        }
    )

    matched = match_layout_re_y_to_resonances(
        layout_resonances_df=layout_resonances,
        layout_re_y_points_df=re_points,
        max_delta_mhz=30.0,
    )

    assert matched.loc[matched["l_jun_nh"] == 24.0, "re_y_matched"].item()
    assert not matched.loc[matched["l_jun_nh"] == 22.0, "re_y_matched"].item()
    assert np.isnan(matched.loc[matched["l_jun_nh"] == 22.0, "re_y_s"].item())


def test_lc_frequency_fit_uses_source_aware_l_s_policy() -> None:
    l_jun = np.array([10.0, 15.0, 20.0, 24.0, 28.0])
    circuit_frequencies = lc_frequency_ghz(
        l_jun,
        0.0,
        0.109,
    )
    layout_frequencies = lc_frequency_ghz(
        l_jun,
        0.42,
        0.111,
    )
    resonance_df = pd.concat(
        [
            pd.DataFrame(
                {
                    "source": "Circuit",
                    "qubit": "Q0",
                    "l_jun_nh": l_jun,
                    "frequency_ghz": circuit_frequencies,
                    "fallback": False,
                    "crossed": True,
                }
            ),
            pd.DataFrame(
                {
                    "source": "Layout",
                    "qubit": "Q0",
                    "l_jun_nh": l_jun,
                    "frequency_ghz": layout_frequencies,
                    "fallback": False,
                    "crossed": True,
                }
            ),
        ],
        ignore_index=True,
    )

    params_df, curve_df = fit_lc_frequency_sweeps(resonance_df)

    circuit_row = params_df[params_df["source"] == "Circuit"].iloc[0]
    layout_row = params_df[params_df["source"] == "Layout"].iloc[0]
    assert circuit_row["status"] == "success"
    assert circuit_row["fit_model"] == "fixed_Ls0"
    assert circuit_row["Ls_nH"] == 0.0
    assert np.isclose(circuit_row["C_eff_pF"], 0.109, rtol=1e-4)
    assert np.isclose(circuit_row["C_eff_lc_fit_pF"], 0.109, rtol=1e-4)
    assert layout_row["status"] == "success"
    assert layout_row["fit_model"] == "floating_Ls"
    assert np.isclose(layout_row["Ls_nH"], 0.42, rtol=1e-4)
    assert np.isclose(layout_row["C_eff_pF"], 0.111, rtol=1e-4)
    assert layout_row["l_jun_effective_factor"] == thesis_plot_config.DEFAULT_L_JUN_EFFECTIVE_FACTOR
    assert set(curve_df["fit_model"]) == {"fixed_Ls0", "floating_Ls"}
    assert not curve_df.empty


def test_lc_frequency_fit_display_table_exposes_source_aware_l_s_policy() -> None:
    fit_df = pd.DataFrame(
        {
            "source": ["Circuit", "Layout"],
            "qubit": ["Q0", "Q0"],
            "status": ["success", "success"],
            "reason": ["", ""],
            "Ls_nH": [0.0, 0.42],
            "C_eff_lc_fit_pF": [0.109, 0.111],
            "C_eff_lc_fit_fF": [109.0, 111.0],
            "RMSE_GHz": [0.0012, 0.0023],
            "l_jun_effective_factor": [0.5, 0.5],
            "fit_model": ["fixed_Ls0", "floating_Ls"],
            "n_points": [5, 5],
        }
    )

    display_table = build_lc_frequency_fit_display_table(
        fit_df,
        dataset="Q3D comparison",
    )

    circuit_row = display_table[display_table["source"] == "Circuit"].iloc[0]
    layout_row = display_table[display_table["source"] == "Layout"].iloc[0]
    assert circuit_row["dataset"] == "Q3D comparison"
    assert circuit_row["formula"] == "f = 1 / (2*pi*sqrt((0.5*L_jun) * C_eff))"
    assert circuit_row["Ls_policy"] == "fixed at 0 for reduced-circuit route"
    assert layout_row["formula"] == "f = 1 / (2*pi*sqrt((Ls + 0.5*L_jun) * C_eff))"
    assert (
        layout_row["Ls_policy"]
        == "fitted effective offset; not a separately identified parasitic inductance"
    )
    assert "Ls_interpretation" not in display_table.columns
    assert np.isclose(circuit_row["RMSE_MHz"], 1.2)
    assert np.isclose(layout_row["RMSE_MHz"], 2.3)


def test_resonance_frequency_ratio_display_table_exposes_ratio_and_delta() -> None:
    resonance_df = pd.DataFrame(
        {
            "source": ["Layout", "Circuit"],
            "qubit": ["Q0", "Q0"],
            "l_jun_nh": [24.0, 24.0],
            "frequency_ghz": [4.0, 4.2],
        }
    )

    display_table = build_resonance_frequency_ratio_display_table(resonance_df)

    assert display_table.columns.tolist() == [
        "qubit",
        "l_jun_nh",
        "Circuit_frequency_GHz",
        "Layout_frequency_GHz",
        "ratio_circuit_over_layout",
        "ratio_percent_offset",
        "delta_circuit_minus_layout_mhz",
    ]
    row = display_table.iloc[0]
    assert np.isclose(row["ratio_circuit_over_layout"], 1.05)
    assert np.isclose(row["ratio_percent_offset"], 5.0)
    assert np.isclose(row["delta_circuit_minus_layout_mhz"], 200.0)


def test_re_y_ratio_display_table_exposes_circuit_over_layout_ratio() -> None:
    re_y_df = pd.DataFrame(
        {
            "source": ["Layout", "Circuit"],
            "qubit": ["Q0", "Q0"],
            "l_jun_nh": [24.0, 24.0],
            "re_y_s": [2.0e-9, 5.0e-9],
        }
    )

    display_table = build_re_y_ratio_display_table(re_y_df)

    assert display_table.columns.tolist() == [
        "qubit",
        "l_jun_nh",
        "Circuit_re_y_s",
        "Layout_re_y_s",
        "ratio_circuit_over_layout",
    ]
    row = display_table.iloc[0]
    assert np.isclose(row["ratio_circuit_over_layout"], 2.5)
    assert np.isclose(row["Circuit_re_y_s"], 5.0e-9)
    assert np.isclose(row["Layout_re_y_s"], 2.0e-9)


def test_t1_from_ceff_references_uses_lc_fit_for_layout_and_circuit() -> None:
    on_resonance = pd.DataFrame(
        {
            "source": ["Layout", "Circuit"],
            "qubit": ["Q0", "Q0"],
            "l_jun_nh": [24.0, 24.0],
            "frequency_ghz": [4.3, 4.4],
            "re_y_s": [2.0e-9, 4.0e-9],
            "re_y_matched": [True, True],
            "C_eff_q3d_reduction_fF": [np.nan, 110.0],
            "t1_from_q3d_ceff_us": [np.nan, 27.5],
        }
    )
    lc_fit_params = pd.DataFrame(
        {
            "source": ["Layout", "Circuit"],
            "qubit": ["Q0", "Q0"],
            "status": ["success", "success"],
            "C_eff_lc_fit_pF": [0.055, 0.060],
            "C_eff_lc_fit_fF": [55.0, 60.0],
            "C_eff_pF": [0.055, 0.060],
            "C_eff_fF": [55.0, 60.0],
        }
    )

    t1_df = add_t1_from_ceff_references(
        on_resonance_re_y_df=on_resonance,
        lc_fit_params_df=lc_fit_params,
    )

    layout_t1 = t1_df.loc[t1_df["source"] == "Layout", "t1_from_lc_fit_us"].item()
    circuit_t1 = t1_df.loc[t1_df["source"] == "Circuit", "t1_from_lc_fit_us"].item()
    assert np.isclose(layout_t1, 27.5)
    assert np.isclose(circuit_t1, 15.0)
    assert np.isclose(t1_df.loc[t1_df["source"] == "Circuit", "t1_us"].item(), 15.0)
    assert np.isclose(
        t1_df.loc[t1_df["source"] == "Circuit", "t1_from_q3d_ceff_us"].item(),
        27.5,
    )
    assert np.isclose(t1_df.loc[t1_df["source"] == "Circuit", "ratio_q3d_over_lc"].item(), 110 / 60)


def test_c_eff_reference_table_separates_lc_fit_and_q3d_reduction() -> None:
    lc_fit_params = pd.DataFrame(
        {
            "source": ["Layout", "Circuit"],
            "qubit": ["Q0", "Q0"],
            "status": ["success", "success"],
            "Ls_nH": [0.1, 0.2],
            "C_eff_lc_fit_fF": [55.0, 60.0],
            "C_eff_fF": [55.0, 60.0],
            "RMSE_GHz": [0.0, 0.0],
            "l_jun_effective_factor": [0.5, 0.5],
            "n_points": [5, 5],
        }
    )
    circuit_observables = pd.DataFrame(
        {
            "qubit": ["Q0", "Q0"],
            "l_jun_nh": [20.0, 24.0],
            "c_eff_q_ff": [110.0, 110.0],
        }
    )

    table = build_c_eff_reference_table(
        lc_fit_params_df=lc_fit_params,
        circuit_observables_df=circuit_observables,
    )

    layout_row = table[table["source"] == "Layout"].iloc[0]
    circuit_row = table[table["source"] == "Circuit"].iloc[0]
    assert np.isnan(layout_row["C_eff_q3d_reduction_fF"])
    assert circuit_row["C_eff_lc_fit_fF"] == 60.0
    assert circuit_row["C_eff_q3d_reduction_fF"] == 110.0
    assert np.isclose(circuit_row["ratio_q3d_over_lc"], 110 / 60)


def test_t1_capacitance_fit_recovers_lc_fit_c_fit() -> None:
    c_fit_f = 60e-15
    re_y = np.array([1.0e-9, 1.5e-9, 2.0e-9])
    t1_us = c_fit_f / re_y * 1e6
    t1_df = pd.DataFrame(
        {
            "source": "Circuit",
            "qubit": "Q0",
            "l_jun_nh": [20.0, 22.0, 24.0],
            "frequency_ghz": [3.4, 3.2, 3.1],
            "re_y_s": re_y,
            "t1_us": t1_us,
            "t1_from_lc_fit_us": t1_us,
        }
    )
    lc_fit_params = pd.DataFrame(
        {
            "source": ["Circuit"],
            "qubit": ["Q0"],
            "status": ["success"],
            "C_eff_lc_fit_fF": [60.0],
            "C_eff_fF": [60.0],
        }
    )

    fit_df = fit_t1_capacitance(t1_df, lc_fit_params_df=lc_fit_params)

    assert fit_df.iloc[0]["status"] == "success"
    assert np.isclose(fit_df.iloc[0]["C_fit_fF"], 60.0, rtol=1e-10)
    assert np.isclose(fit_df.iloc[0]["delta_fit_minus_lc_fF"], 0.0, atol=1e-10)
    assert fit_df.iloc[0]["t1_column"] == "t1_from_lc_fit_us"


def test_floating_c_d_xy_formula_matches_thesis_expression() -> None:
    c_d_xy = compute_floating_c_d_xy_ff(
        c_g1_ff=10.0,
        c_g2_ff=14.0,
        c_xy1_ff=1.0,
        c_xy2_ff=3.0,
    )

    assert np.isclose(c_d_xy, (10.0 * 3.0 - 14.0 * 1.0) / (10.0 + 14.0 + 1.0 + 3.0))


def test_c_eff_xy_t1_trend_table_uses_raw_matrix_formula_and_squared_columns() -> None:
    cap_df = pd.DataFrame(
        {
            "qubit": ["Q0"],
            "c_g1_ff": [10.0],
            "c_g2_ff": [14.0],
            "c_xy1_ff": [1.0],
            "c_xy2_ff": [3.0],
            "c_d_xy_ff": [999.0],
        }
    )
    t1_df = pd.DataFrame(
        {
            "source": ["Circuit", "Layout"],
            "qubit": ["Q0", "Q0"],
            "l_jun_nh": [24.0, 24.0],
            "frequency_ghz": [4.0, 4.0],
            "C_eff_lc_fit_fF": [60.0, 60.0],
            "t1_from_lc_fit_us": [20.0, 21.0],
        }
    )

    trend = build_c_eff_xy_t1_trend_table(t1_df=t1_df, capacitance_df=cap_df)

    assert trend["source"].tolist() == ["Circuit"]
    row = trend.iloc[0]
    expected_cxy = (10.0 * 3.0 - 14.0 * 1.0) / (10.0 + 14.0 + 1.0 + 3.0)
    expected_gamma = 1.0 / (20.0e-6)
    expected_omega = 2.0 * np.pi * 4.0e9
    assert np.isclose(row["C_eff_xy_signed_fF"], expected_cxy)
    assert np.isclose(row["C_eff_xy_abs_fF"], abs(expected_cxy))
    assert np.isclose(row["C_eff_xy_abs_sq_fF2"], expected_cxy**2)
    assert np.isclose(row["inv_C_eff_xy_abs_sq_1_per_fF2"], 1.0 / expected_cxy**2)
    assert np.isclose(row["gamma_from_lc_fit_per_s"], expected_gamma)
    assert np.isclose(row["omega_rad_per_s"], expected_omega)
    assert np.isclose(row["normalized_gamma"], expected_gamma * 60.0e-15 / expected_omega**2)


def test_c_eff_xy_t1_trend_fit_recovers_synthetic_relations() -> None:
    cxy = np.array([0.2, 0.3, 0.4])
    coefficient = 3.2
    intercept = 1.5
    trend_df = pd.DataFrame(
        {
            "source": ["Circuit"] * len(cxy),
            "qubit": ["Q0", "Q1", "Q2"],
            "l_jun_nh": [24.0] * len(cxy),
            "frequency_ghz": [4.5, 4.3, 4.1],
            "t1_from_lc_fit_us": coefficient / cxy**2 + intercept,
            "gamma_from_lc_fit_per_s": [1.0] * len(cxy),
            "C_eff_lc_fit_fF": [60.0] * len(cxy),
            "C_eff_xy_signed_fF": cxy,
            "C_eff_xy_abs_fF": np.abs(cxy),
            "C_eff_xy_abs_sq_fF2": cxy**2,
            "inv_C_eff_xy_abs_sq_1_per_fF2": 1.0 / cxy**2,
            "omega_rad_per_s": [1.0] * len(cxy),
            "normalized_gamma": [1.0] * len(cxy),
        }
    )

    fit_df = fit_c_eff_xy_t1_trend(trend_df)

    row = fit_df.iloc[0]
    assert row["status"] == "success"
    assert row["l_jun_nh"] == 24.0
    assert row["fit_model"] == "T1 = A / Ceff,xy^2 + B"
    assert row["intercept_policy"] == "free"
    assert np.isclose(row["coefficient_A_us_fF2"], coefficient)
    assert np.isclose(row["intercept_B_us"], intercept)
    assert row["R2"] > 0.999999


def test_c_eff_xy_t1_trend_fit_includes_layout_source() -> None:
    cxy = np.array([0.2, 0.3, 0.4])
    coefficient = 4.1
    intercept = 2.0
    trend_df = pd.DataFrame(
        {
            "source": ["Layout"] * len(cxy),
            "qubit": ["Q0", "Q1", "Q2"],
            "l_jun_nh": [24.0] * len(cxy),
            "frequency_ghz": [4.5, 4.3, 4.1],
            "t1_from_lc_fit_us": coefficient / cxy**2 + intercept,
            "gamma_from_lc_fit_per_s": [1.0] * len(cxy),
            "C_eff_lc_fit_fF": [60.0] * len(cxy),
            "C_eff_xy_signed_fF": cxy,
            "C_eff_xy_abs_fF": np.abs(cxy),
            "C_eff_xy_abs_sq_fF2": cxy**2,
            "inv_C_eff_xy_abs_sq_1_per_fF2": 1.0 / cxy**2,
            "omega_rad_per_s": [1.0] * len(cxy),
            "normalized_gamma": [1.0] * len(cxy),
        }
    )

    fit_df = fit_c_eff_xy_t1_trend(trend_df)

    row = fit_df.iloc[0]
    assert row["source"] == "Layout"
    assert row["status"] == "success"
    assert np.isclose(row["coefficient_A_us_fF2"], coefficient)
    assert np.isclose(row["intercept_B_us"], intercept)


def test_c_eff_xy_t1_trend_fit_can_fix_intercept_to_zero() -> None:
    cxy = np.array([0.2, 0.3, 0.4])
    coefficient = 3.2
    trend_df = pd.DataFrame(
        {
            "source": ["Circuit"] * len(cxy),
            "qubit": ["Q0", "Q1", "Q2"],
            "l_jun_nh": [24.0] * len(cxy),
            "frequency_ghz": [4.5, 4.3, 4.1],
            "t1_from_lc_fit_us": coefficient / cxy**2,
            "gamma_from_lc_fit_per_s": [1.0] * len(cxy),
            "C_eff_lc_fit_fF": [60.0] * len(cxy),
            "C_eff_xy_signed_fF": cxy,
            "C_eff_xy_abs_fF": np.abs(cxy),
            "C_eff_xy_abs_sq_fF2": cxy**2,
            "inv_C_eff_xy_abs_sq_1_per_fF2": 1.0 / cxy**2,
            "omega_rad_per_s": [1.0] * len(cxy),
            "normalized_gamma": [1.0] * len(cxy),
        }
    )

    fit_df = fit_c_eff_xy_t1_trend(trend_df, intercept_policy="zero")

    row = fit_df.iloc[0]
    assert row["fit_model"] == "T1 = A / Ceff,xy^2"
    assert row["intercept_policy"] == "zero"
    assert np.isclose(row["coefficient_A_us_fF2"], coefficient)
    assert row["intercept_B_us"] == 0.0
    assert row["R2"] > 0.999999


def test_c_eff_xy_t1_fit_parameter_summary_prints_circuit_ab_only() -> None:
    fit_df = pd.DataFrame(
        {
            "source": ["Circuit", "Layout", "Circuit"],
            "l_jun_nh": [24.0, 24.0, 26.0],
            "status": ["success", "success", "failed"],
            "coefficient_A_us_fF2": [2.5, 3.5, np.nan],
            "intercept_B_us": [0.2, 0.3, np.nan],
            "RMSE_us": [0.01, 0.02, np.nan],
            "R2": [0.99, 0.98, np.nan],
            "n_points": [3, 3, 1],
            "qubits": ["Q0,Q1,Q2", "Q0,Q1,Q2", ""],
        }
    )

    summary = build_c_eff_xy_t1_fit_parameter_summary(
        fit_df,
        dataset="Q3D Circuit",
    )

    assert summary["dataset"].tolist() == ["Q3D Circuit"]
    assert summary["source"].tolist() == ["Circuit"]
    assert summary["formula"].tolist() == [
        "T1_us = A_us_fF2 / Ceff_xy_fF^2 + B_us"
    ]
    assert np.isclose(summary.iloc[0]["A_us_fF2"], 2.5)
    assert np.isclose(summary.iloc[0]["B_us"], 0.2)


def test_c_eff_xy_t1_fit_parameter_summary_marks_zero_intercept_formula() -> None:
    fit_df = pd.DataFrame(
        {
            "source": ["Circuit"],
            "l_jun_nh": [24.0],
            "status": ["success"],
            "coefficient_A_us_fF2": [2.5],
            "intercept_B_us": [0.0],
            "intercept_policy": ["zero"],
            "RMSE_us": [0.01],
            "R2": [0.99],
            "n_points": [3],
            "qubits": ["Q0,Q1,Q2"],
        }
    )

    summary = build_c_eff_xy_t1_fit_parameter_summary(fit_df)

    assert summary["formula"].tolist() == [
        "T1_us = A_us_fF2 / Ceff_xy_fF^2 (B_us fixed to 0)"
    ]
    assert summary["B_us"].tolist() == [0.0]


def test_c_eff_xy_t1_result_display_tables_filter_points_and_fit_rows() -> None:
    trend_df = pd.DataFrame(
        {
            "source": ["Circuit", "Circuit", "Circuit"],
            "qubit": ["Q0", "Q1", "Q0"],
            "l_jun_nh": [24.0, 24.0, 22.0],
            "frequency_ghz": [4.0, 4.1, 4.2],
            "C_eff_xy_signed_fF": [0.2, 0.3, 0.4],
            "C_eff_xy_abs_fF": [0.2, 0.3, 0.4],
            "t1_from_lc_fit_us": [81.5, 37.055, 21.5],
            "C_eff_lc_fit_fF": [60.0, 61.0, 62.0],
        }
    )
    fit_df = pd.DataFrame(
        {
            "source": ["Circuit"],
            "l_jun_nh": [24.0],
            "status": ["success"],
            "coefficient_A_us_fF2": [3.2],
            "intercept_B_us": [1.5],
            "intercept_policy": ["free"],
            "RMSE_us": [0.01],
            "R2": [0.99],
            "n_points": [2],
            "qubits": ["Q0,Q1"],
        }
    )
    no_offset_fit_df = fit_df.assign(
        coefficient_A_us_fF2=[3.5],
        intercept_B_us=[0.0],
        intercept_policy=["zero"],
        RMSE_us=[0.25],
        R2=[0.97],
    )

    display_tables = build_c_eff_xy_t1_result_display_tables(
        trend_df=trend_df,
        fit_df=fit_df,
        no_offset_fit_df=no_offset_fit_df,
        source="Circuit",
        l_jun_nh=24.0,
        dataset="Q3D Circuit",
    )

    points = display_tables["points"]
    fits = display_tables["fits"]
    assert points["dataset"].unique().tolist() == ["Q3D Circuit"]
    assert points["qubit"].tolist() == ["Q0", "Q1"]
    assert np.allclose(points["C_eff_xy_signed_fF"], [0.2, 0.3])
    assert fits["intercept_policy"].tolist() == ["free", "zero"]
    assert fits["formula"].tolist() == [
        "T1_us = A_us_fF2 / Ceff_xy_fF^2 + B_us",
        "T1_us = A_us_fF2 / Ceff_xy_fF^2 (B_us fixed to 0)",
    ]
    assert np.allclose(fits["RMSE_us"], [0.01, 0.25])


def test_c_eff_xy_t1_trend_figure_contains_single_l_jun_circuit_fit() -> None:
    cxy = np.array([0.2, 0.3, 0.4])
    trend_df = pd.DataFrame(
        {
            "source": ["Circuit", "Circuit", "Circuit"],
            "qubit": ["Q0", "Q1", "Q2"],
            "l_jun_nh": [24.0, 24.0, 24.0],
            "frequency_ghz": [4.0, 4.1, 4.2],
            "t1_from_lc_fit_us": 3.2 / cxy**2 + 1.5,
            "gamma_from_lc_fit_per_s": [5e4, 1e5, 2e5],
            "C_eff_lc_fit_fF": [60.0, 60.0, 60.0],
            "C_eff_xy_signed_fF": cxy,
            "C_eff_xy_abs_fF": np.abs(cxy),
            "C_eff_xy_abs_sq_fF2": cxy**2,
            "inv_C_eff_xy_abs_sq_1_per_fF2": 1.0 / cxy**2,
            "omega_rad_per_s": [2.0e10, 2.1e10, 2.2e10],
            "normalized_gamma": [1.0e-25, 2.25e-25, 4.0e-25],
        }
    )
    fit_df = fit_c_eff_xy_t1_trend(trend_df)

    fig = make_c_eff_xy_t1_trend_figure(
        trend_df=trend_df,
        trend_fit_df=fit_df,
        l_jun_nh=24.0,
    )

    assert "Circuit T1 vs Ceff,xy (Ljun=24 nH)" in fig.layout.title.text
    assert fig.layout.height == thesis_plot_config.PLOTLY_FIGURE_HEIGHT_PX
    assert fig.layout.xaxis.title.text == "Ceff,xy [fF]"
    assert fig.layout.yaxis.title.text == "T1 from LC-fit Ceff [us]"
    assert [trace.name for trace in fig.data] == [
        "Circuit data",
        "fit: T1 = A / Ceff,xy^2 + B<br>R2=1.0000",
    ]
    assert fig.layout.annotations == ()


def test_c_eff_xy_t1_trend_figure_can_overlay_zero_intercept_fit() -> None:
    cxy = np.array([0.2, 0.3, 0.4])
    trend_df = pd.DataFrame(
        {
            "source": ["Circuit", "Circuit", "Circuit"],
            "qubit": ["Q0", "Q1", "Q2"],
            "l_jun_nh": [24.0, 24.0, 24.0],
            "frequency_ghz": [4.0, 4.1, 4.2],
            "t1_from_lc_fit_us": 3.2 / cxy**2 + 1.5,
            "gamma_from_lc_fit_per_s": [5e4, 1e5, 2e5],
            "C_eff_lc_fit_fF": [60.0, 60.0, 60.0],
            "C_eff_xy_signed_fF": cxy,
            "C_eff_xy_abs_fF": np.abs(cxy),
            "C_eff_xy_abs_sq_fF2": cxy**2,
            "inv_C_eff_xy_abs_sq_1_per_fF2": 1.0 / cxy**2,
            "omega_rad_per_s": [2.0e10, 2.1e10, 2.2e10],
            "normalized_gamma": [1.0e-25, 2.25e-25, 4.0e-25],
        }
    )
    fit_df = fit_c_eff_xy_t1_trend(trend_df)
    no_offset_fit_df = fit_c_eff_xy_t1_trend(trend_df, intercept_policy="zero")

    fig = make_c_eff_xy_t1_trend_figure(
        trend_df=trend_df,
        trend_fit_df=fit_df,
        no_offset_fit_df=no_offset_fit_df,
        l_jun_nh=24.0,
    )

    assert len(fig.data) == 3
    assert fig.data[0].name == "Circuit data"
    assert fig.data[1].name == "B floating: A=3.200, B=1.500, RMSE=0.000, R2=1.0000"
    assert fig.data[2].name.startswith("B fixed 0: A=")
    assert "B=0.000" in fig.data[2].name
    assert "RMSE=" in fig.data[2].name
    assert "R2=" in fig.data[2].name
    assert fig.data[1].line.dash == "solid"
    assert fig.data[2].line.dash == "dash"
    assert fig.layout.annotations == ()


def test_c_eff_xy_t1_trend_comparison_figure_overlays_sources_with_solid_fits() -> None:
    cxy = np.array([0.2, 0.3, 0.4])
    rows = []
    for source, coefficient, intercept in (
        ("Circuit", 3.2, 1.5),
        ("Layout", 4.1, 2.0),
    ):
        for qubit, c_eff_xy in zip(("Q0", "Q1", "Q2"), cxy, strict=True):
            rows.append(
                {
                    "source": source,
                    "qubit": qubit,
                    "l_jun_nh": 24.0,
                    "frequency_ghz": 4.0,
                    "t1_from_lc_fit_us": coefficient / c_eff_xy**2 + intercept,
                    "gamma_from_lc_fit_per_s": 1.0,
                    "C_eff_lc_fit_fF": 60.0,
                    "C_eff_xy_signed_fF": c_eff_xy,
                    "C_eff_xy_abs_fF": abs(c_eff_xy),
                    "C_eff_xy_abs_sq_fF2": c_eff_xy**2,
                    "inv_C_eff_xy_abs_sq_1_per_fF2": 1.0 / c_eff_xy**2,
                    "omega_rad_per_s": 1.0,
                    "normalized_gamma": 1.0,
                }
            )
    trend_df = pd.DataFrame(rows)
    fit_df = fit_c_eff_xy_t1_trend(trend_df)

    fig = make_c_eff_xy_t1_trend_comparison_figure(
        trend_df=trend_df,
        trend_fit_df=fit_df,
        l_jun_nh=24.0,
    )

    assert "Layout vs Circuit T1 vs Ceff,xy (Ljun=24 nH)" in fig.layout.title.text
    assert [trace.name for trace in fig.data] == [
        "Circuit data",
        "Circuit fit<br>R2=1.0000",
        "Layout data",
        "Layout fit<br>R2=1.0000",
    ]
    assert all("markers" in trace.mode for trace in (fig.data[0], fig.data[2]))
    assert all(trace.mode == "lines" for trace in (fig.data[1], fig.data[3]))
    assert all(trace.line.dash == "solid" for trace in (fig.data[1], fig.data[3]))


def test_plotly_im_trace_figure_uses_legend_without_custom_buttons() -> None:
    rows = []
    for source in ("Layout", "Circuit"):
        for qubit in ("Q0", "Q1", "Q2"):
            for frequency in (4.0, 4.1, 4.2):
                rows.append(
                    {
                        "source": source,
                        "qubit": qubit,
                        "l_jun_nh": 24.0,
                        "frequency_ghz": frequency,
                        "im_y_s": frequency * 1e-9,
                    }
                )
    combined = pd.DataFrame(rows)
    layout = combined[combined["source"] == "Layout"].copy()
    circuit = combined[combined["source"] == "Circuit"].copy()

    fig = make_im_trace_comparison_figure(
        layout_trace_df=layout,
        circuit_trace_df=circuit,
        trace_l_jun_nh_values=[24.0],
        max_points_per_line=100,
    )

    assert len(fig.data) == 6
    assert fig.layout.updatemenus == ()
    assert PLOTLY_FIGURE_WIDTH_PX == PLOTLY_DOWNLOAD_WIDTH_PX
    assert PLOTLY_FIGURE_HEIGHT_PX == PLOTLY_DOWNLOAD_HEIGHT_PX
    assert fig.layout.width == PLOTLY_FIGURE_WIDTH_PX
    assert fig.layout.height == PLOTLY_FIGURE_HEIGHT_PX
    assert fig.layout.margin.r == PLOTLY_MARGIN_RIGHT_PX
    assert fig.layout.title.font.size == thesis_plot_config.PLOTLY_TITLE_FONT_SIZE
    assert fig.layout.font.family == thesis_plot_config.PLOTLY_FONT_FAMILY
    assert fig.layout.legend.font.size == thesis_plot_config.PLOTLY_LEGEND_FONT_SIZE
    assert fig.layout.xaxis.showgrid is False
    assert fig.layout.yaxis.showgrid is True
    assert fig.layout.xaxis.ticks == "outside"
    assert fig.layout.yaxis.linecolor == thesis_plot_config.PLOTLY_AXIS_LINE_COLOR
    assert fig.layout.yaxis.gridcolor == thesis_plot_config.PLOTLY_GRID_COLOR
    assert fig.layout.yaxis.title.standoff == thesis_plot_config.PLOTLY_AXIS_TITLE_STANDOFF_PX
    assert fig.data[0].line.width == thesis_plot_config.PLOTLY_LINE_WIDTH
    assert {trace.legendgroup for trace in fig.data} == {
        "Circuit-Q0",
        "Circuit-Q1",
        "Circuit-Q2",
        "Layout-Q0",
        "Layout-Q1",
        "Layout-Q2",
    }


def test_plotly_show_config_controls_download_png_quality() -> None:
    config = plotly_show_config("diagnostic_trace")

    image_options = config["toImageButtonOptions"]
    assert image_options["format"] == "png"
    assert image_options["filename"] == "diagnostic_trace"
    assert image_options["width"] == PLOTLY_DOWNLOAD_WIDTH_PX
    assert image_options["height"] == PLOTLY_DOWNLOAD_HEIGHT_PX
    assert image_options["scale"] == PLOTLY_DOWNLOAD_SCALE
    assert "font" not in config


def test_plotly_show_config_applies_per_figure_download_size_overrides() -> None:
    stem = "q3d_jc_reduced_admittance_trace_Q0_L24nH"
    config = plotly_show_config(stem)

    image_options = config["toImageButtonOptions"]
    assert image_options["width"] == PLOTLY_DOWNLOAD_WIDTH_PX
    assert image_options["height"] == PLOTLY_DOWNLOAD_SIZE_OVERRIDES[stem]["height"]
    assert image_options["scale"] == PLOTLY_DOWNLOAD_SCALE


def test_plotly_helpers_read_config_module_at_call_time(monkeypatch) -> None:
    monkeypatch.setattr(thesis_plot_config, "PLOTLY_MARGIN_RIGHT_PX", 444)
    monkeypatch.setattr(thesis_plot_config, "PLOTLY_TITLE_FONT_SIZE", 31)
    monkeypatch.setattr(thesis_plot_config, "PLOTLY_GRID_COLOR", "#ABCDEF")
    monkeypatch.setattr(thesis_plot_config, "PLOTLY_AXIS_LINE_COLOR", "#123456")
    monkeypatch.setattr(thesis_plot_config, "PLOTLY_LINE_WIDTH", 4.0)
    frame = pd.DataFrame(
        {
            "source": ["Layout", "Layout"],
            "qubit": ["Q0", "Q0"],
            "l_jun_nh": [24.0, 24.0],
            "frequency_ghz": [4.0, 4.1],
            "im_y_s": [0.0, 1.0e-9],
        }
    )

    fig = make_im_trace_comparison_figure(
        layout_trace_df=frame,
        circuit_trace_df=frame.iloc[0:0].copy(),
        trace_l_jun_nh_values=[24.0],
        max_points_per_line=100,
    )

    assert fig.layout.margin.r == 444
    assert fig.layout.title.font.size == 31
    assert fig.layout.yaxis.gridcolor == "#ABCDEF"
    assert fig.layout.xaxis.linecolor == "#123456"
    assert fig.data[0].line.width == 4.0


def test_thesis_notebooks_use_plotly_show_config_for_plotly_figures() -> None:
    failures: list[str] = []
    for notebook_path in sorted((STUDY_DIR / "notebooks").glob("*.ipynb")):
        notebook = json.loads(notebook_path.read_text())
        for cell_index, cell in enumerate(notebook["cells"], start=1):
            if cell.get("cell_type") != "code":
                continue
            source = "".join(cell.get("source", []))
            tree = ast.parse(source, filename=f"{notebook_path}:cell {cell_index}")
            for node in ast.walk(tree):
                if not _is_show_call(node):
                    continue
                if _is_matplotlib_show_call(node):
                    continue
                if not _has_config_keyword(node):
                    failures.append(f"{notebook_path.name}:cell {cell_index}:line {node.lineno}")

    assert failures == []


def test_q3d_jc_comparison_notebook_declares_result_registry_with_tables() -> None:
    notebook_path = STUDY_DIR / "notebooks/03_q3d_jc_comparison_figures.ipynb"
    notebook = json.loads(notebook_path.read_text())
    source = "\n".join("".join(cell.get("source", [])) for cell in notebook["cells"])

    assert "def show_result(result_key: str) -> None:" in source
    assert "RESULTS: dict[str, dict[str, object]] = {}" in source
    assert "build_c_eff_xy_t1_result_display_tables" in source
    assert "frequency_ratio_display_df = build_resonance_frequency_ratio_display_table" in source
    assert "re_y_ratio_display_df = build_re_y_ratio_display_table" in source
    assert 'raise ValueError(f"Result {result_key!r} has no figure object.")' in source
    assert 'raise ValueError(f"Result {result_key!r} has no table payload.")' in source


def test_q3d_jc_comparison_notebook_uses_one_result_per_visible_cell() -> None:
    notebook_path = STUDY_DIR / "notebooks/03_q3d_jc_comparison_figures.ipynb"
    notebook = json.loads(notebook_path.read_text())
    result_cells: list[tuple[int, str]] = []
    for cell_index, cell in enumerate(notebook["cells"]):
        if cell.get("cell_type") != "code":
            continue
        source = "".join(cell.get("source", [])).strip()
        if not source.startswith("show_result("):
            continue
        result_cells.append((cell_index, source))
        assert source.count("show_result(") == 1
        assert ".show(" not in source
        assert notebook["cells"][cell_index - 1]["cell_type"] == "markdown"
        markdown = "".join(notebook["cells"][cell_index - 1]["source"])
        assert markdown.startswith("### ")

    result_keys = [
        source.removeprefix('show_result("').removesuffix('")')
        for _, source in result_cells
    ]
    assert len(result_cells) == 32
    assert len(set(result_keys)) == len(result_keys)


def test_build_on_resonance_re_y_table_keeps_q3d_t1_as_reference_only() -> None:
    layout_re_y = pd.DataFrame(
        {
            "source": ["Layout"],
            "qubit": ["Q0"],
            "l_jun_nh": [24.0],
            "frequency_ghz": [4.3],
            "re_y_frequency_ghz": [4.302],
            "re_y_delta_mhz": [2.0],
            "re_y_s": [2.8e-9],
            "re_y_matched": [True],
            "t1_us": [np.nan],
            "t1_source": ["pending_lc_fit"],
        }
    )
    circuit_observables = pd.DataFrame(
        {
            "source": ["Circuit"],
            "qubit": ["Q0"],
            "l_jun_nh": [24.0],
            "frequency_ghz": [3.1],
            "re_y_s": [1.5e-9],
            "t1_us": [70.0],
            "c_eff_q_ff": [105.0],
        }
    )

    table = build_on_resonance_re_y_table(
        layout_re_y_df=layout_re_y,
        circuit_observables_df=circuit_observables,
    )

    assert set(table["source"]) == {"Layout", "Circuit"}
    circuit = table[table["source"] == "Circuit"].iloc[0]
    assert np.isnan(circuit["t1_us"])
    assert circuit["t1_from_q3d_ceff_us"] == 70.0
    assert circuit["C_eff_q3d_reduction_fF"] == 105.0


def test_plotly_diagnostic_figures_expose_ceff_and_re_y_ratio() -> None:
    c_eff_reference = pd.DataFrame(
        {
            "source": ["Layout", "Circuit"],
            "qubit": ["Q0", "Q0"],
            "status": ["success", "success"],
            "C_eff_lc_fit_fF": [55.0, 60.0],
            "C_eff_q3d_reduction_fF": [np.nan, 110.0],
            "ratio_q3d_over_lc": [np.nan, 110 / 60],
        }
    )
    re_y = pd.DataFrame(
        {
            "source": ["Layout", "Circuit"],
            "qubit": ["Q0", "Q0"],
            "l_jun_nh": [24.0, 24.0],
            "re_y_s": [2.0e-9, 4.0e-9],
        }
    )

    c_eff_fig = make_c_eff_reference_diagnostic_figure(c_eff_reference)
    ratio_fig = make_re_y_ratio_figure(re_y)
    t1_fig = make_t1_comparison_figure(
        pd.DataFrame(
            {
                "source": ["Layout", "Circuit"],
                "qubit": ["Q0", "Q0"],
                "l_jun_nh": [24.0, 24.0],
                "t1_from_lc_fit_us": [27.5, 15.0],
                "C_eff_lc_fit_fF": [55.0, 60.0],
                "t1_from_q3d_ceff_us": [np.nan, 27.5],
            }
        )
    )

    assert [trace.name for trace in c_eff_fig.data] == [
        "LC-fit Ceff",
        "Q3D reduction Ceff,q",
    ]
    assert ratio_fig.data[0].name == "Q0"
    assert np.isclose(ratio_fig.data[0].y[0], 2.0)
    assert "LC-Fit Ceff" in t1_fig.layout.title.text


def test_resonance_frequency_ratio_figure_shows_circuit_over_layout_ratio() -> None:
    resonance = pd.DataFrame(
        {
            "source": ["Layout", "Circuit", "Layout", "Circuit"],
            "qubit": ["Q0", "Q0", "Q0", "Q0"],
            "l_jun_nh": [20.0, 20.0, 24.0, 24.0],
            "frequency_ghz": [4.0, 4.2, 3.5, 3.675],
        }
    )
    fig = make_resonance_frequency_ratio_figure(
        resonance_df=resonance,
    )

    assert fig.layout.title.text == "Resonance Frequency Ratio"
    assert fig.layout.yaxis.title.text == "Frequency ratio: Circuit / Layout"
    assert [trace.name for trace in fig.data] == ["Q0 ratio"]
    assert np.allclose(fig.data[0].y, [1.05, 1.05])
    assert fig.data[0].mode == "markers+lines"
    assert fig.layout.shapes[0].y0 == 1.0


def _is_show_call(node: ast.AST) -> bool:
    return (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "show"
    )


def _is_matplotlib_show_call(node: ast.Call) -> bool:
    return isinstance(node.func.value, ast.Name) and node.func.value.id == "plt"


def _has_config_keyword(node: ast.Call) -> bool:
    return any(keyword.arg == "config" for keyword in node.keywords)
