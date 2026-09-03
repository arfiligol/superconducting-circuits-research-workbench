from __future__ import annotations

import csv
import json
import shutil
import subprocess
import sys
from dataclasses import FrozenInstanceError
from pathlib import Path
from typing import Any

import pytest
import superconducting_circuits_runtime as runtime_api
from superconducting_circuits_runtime import (
    CircuitLibrary,
    CircuitObjective,
    CircuitPlan,
    CircuitSim,
    DirectEvaluationSpec,
    DirectSolveSpec,
    GateSpec,
    OptimizationProgress,
    OptimizerSpec,
    ReductionSpec,
    ResponseSpec,
    StandaloneDirectEvaluationSpec,
    T1Spec,
    VariableSpec,
    circuit_component,
    resolve_circuit_campaign,
    resolve_circuit_result,
    runtime,
)
from superconducting_circuits_runtime.catalog import (
    intrinsic_interferometric_purcell_filter,
    linearized_floating_qubit,
    parallel_lc_resonator,
    transmission_line,
)
from superconducting_circuits_runtime.runtime import RuntimeContractError


def _objective() -> CircuitObjective:
    return CircuitObjective.from_targets(
        {
            "outputs": {
                "stiffness": {
                    "kind": "schur_dynamic_stiffness_abs",
                    "frequency_hz": 5.0e9,
                    "row": 1,
                    "column": 1,
                }
            },
            "values": {"stiffness": 1.0e6},
            "weights": {"stiffness": 1.0},
        }
    )


def _plan(*, sections: int) -> tuple[CircuitPlan, list[object]]:
    plan = CircuitPlan("staged_pipeline")
    resonators = [
        plan.add(
            parallel_lc_resonator(
                id=f"resonator_{index}",
                capacitance_f=1.0e-12,
                inductance_h=1.0e-9,
            )
        )
        for index in range(4)
    ]
    for index in range(3):
        line = plan.add(
            transmission_line(
                id=f"line_{index}",
                length_m=1.0e-3,
                n_sections=sections,
                l_per_m_h=4.0e-7,
                c_per_m_f=1.6e-10,
            )
        )
        plan.connect(resonators[index].pin("signal"), line.pin("head"))
        plan.connect(line.pin("tail"), resonators[index + 1].pin("signal"))
    for index, resonator in enumerate(resonators):
        plan.add_port(
            f"port_{index}",
            resonator.pin("signal"),
            role="terminated" if index < 2 else "nonloading_probe",
        )
    return plan, resonators


def _targeted_plan(*, sections: int = 1) -> tuple[CircuitPlan, Any]:
    plan = CircuitPlan("targeted")
    ipf = plan.add(
        intrinsic_interferometric_purcell_filter(
            id="ipf",
            readout_open_length_m=5.0e-3,
            shared_short_length_m=5.0e-3,
            coupled_length_m=5.0e-3,
            filter_open_length_m=5.0e-3,
            readout_short_sections=sections,
            readout_open_sections=sections,
            coupled_sections=sections,
            filter_short_sections=sections,
            filter_open_sections=sections,
            readout_l_per_m_h=4.0e-7,
            readout_c_per_m_f=1.6e-10,
            filter_l_per_m_h=4.0e-7,
            filter_c_per_m_f=1.6e-10,
            mtl_l11_per_m_h=4.0e-7,
            mtl_l12_per_m_h=5.0e-8,
            mtl_l21_per_m_h=5.0e-8,
            mtl_l22_per_m_h=4.0e-7,
            mtl_c11_per_m_f=1.6e-10,
            mtl_c12_per_m_f=-2.0e-11,
            mtl_c21_per_m_f=-2.0e-11,
            mtl_c22_per_m_f=1.6e-10,
            idc_finger_length_um=100.0,
            idc_source_min_um=50.0,
            idc_source_max_um=150.0,
            idc_filter_ground_slope_f_per_um=2.0e-16,
            idc_filter_ground_intercept_f=2.0e-14,
            idc_feedline_ground_slope_f_per_um=2.0e-16,
            idc_feedline_ground_intercept_f=2.0e-14,
            idc_mutual_slope_f_per_um=2.0e-16,
            idc_mutual_intercept_f=2.0e-14,
            c0r_f=1.0e-14,
        )
    )
    feedlines = [
        plan.add(
            transmission_line(
                id=f"feedline_{index}",
                length_m=1.0e-3,
                n_sections=sections,
                l_per_m_h=4.0e-7,
                c_per_m_f=1.6e-10,
            )
        )
        for index in range(2)
    ]
    qubit = plan.add(
        linearized_floating_qubit(
            id="qubit",
            c01_f=5.0e-14,
            c02_f=5.0e-14,
            c12_f=5.0e-14,
            cr1_f=5.0e-15,
            cr2_f=5.0e-15,
            l_j_per_junction_h=1.0e-8,
        )
    )
    for feedline in feedlines:
        plan.connect(feedline.pin("tail"), ipf.pin("feedline_attachment"))
    plan.connect(qubit.pin("readout_attachment"), ipf.pin("readout_attachment"))
    plan.add_port("port_0", feedlines[0].pin("head"), role="terminated")
    plan.add_port("port_1", feedlines[1].pin("head"), role="terminated")
    plan.add_port("port_2", qubit.pin("island_1"), role="nonloading_probe")
    plan.add_port("port_3", qubit.pin("island_2"), role="nonloading_probe")
    return plan, ipf


def _configured_sim(
    tmp_path: Path, *, maximum_generations: int = 1
) -> tuple[CircuitSim, Path, DirectSolveSpec]:
    plan, resonators = _plan(sections=1)
    refinement, _ = _plan(sections=2)
    source = tmp_path / "bound-input.json"
    source.write_text('{"fixture":"public"}', encoding="utf-8")
    sim = CircuitSim(tmp_path, "staged", lifecycle_state="ACCEPTED", data_classification="public")
    sim.set_plan(plan)
    sim.bind_artifact(
        "fixture_input",
        source,
        schema="test-public-input.v1",
        units="dimensionless",
        provenance={"authority": "test <fixture>"},
    )
    sim.set_objective(_objective())
    sim.set_reduction(ReductionSpec((resonators[0].coord("signal"),)))
    sim.set_gates(
        [
            GateSpec(
                "nonnegative_stiffness",
                {"op": "greater_equal", "args": [{"output": "stiffness"}, {"const": 0.0}]},
                "active",
                "human://accepted-runtime-test-fixture",
            )
        ]
    )
    sim.set_variables(
        [
            VariableSpec(
                resonators[0].parameter("capacitance_f"),
                transform="log",
                lower=0.9e-12,
                upper=1.1e-12,
            )
        ]
    )
    sim.set_optimizer(
        OptimizerSpec(
            "cma_es",
            seed=0,
            human_authority="human://accepted-runtime-test-fixture",
            controls={
                "initial_sigma": 0.01,
                "maxiter": maximum_generations,
                "maxfevals": maximum_generations * 3,
                "popsize": 3,
            },
        )
    )
    sim.set_refinement(plan=refinement, relative_tolerance=1.0e9)
    sim.set_responses(
        ResponseSpec(
            direct_frequency_hz=(4.5e9, 5.0e9, 5.5e9),
            hb_frequency_hz=(4.5e9, 4.75e9, 5.0e9, 5.25e9, 5.5e9),
            input_port="port_0",
            output_port="port_1",
            pump_frequency_hz=5.0e9,
        )
    )
    sim.set_t1(
        T1Spec(
            (4.5e9, 5.0e9, 5.5e9),
            ("port_0", "port_1"),
            ("port_2", "port_3"),
            (0.5, 0.5),
            5.0e9,
        )
    )
    return (
        sim,
        source,
        DirectSolveSpec(
            ReductionSpec((resonators[0].coord("signal"),)),
            ("root",),
            "root",
            5.0e9,
        ),
    )


def test_c11_fit_uses_off_anchor_hb_extrema_for_its_coupled_start(tmp_path: Path) -> None:
    import numpy as np

    frequency = np.linspace(4.0e9, 8.0e9, 1001)
    expected = np.asarray([4.45e9, 4.70e9, 50.0e6, 60.0e6])
    omega = 2 * np.pi * frequency
    delta_a = 2 * np.pi * expected[0] - omega
    delta_b = 2 * np.pi * expected[1] - omega
    hb = 1 - (2 * np.pi * expected[3]) * (2j * delta_b) / (
        4 * (2 * np.pi * expected[2]) ** 2
        + (2j * delta_a + 2 * np.pi * expected[3]) * (2j * delta_b)
    )

    response_dir = tmp_path / "responses"
    response_dir.mkdir()
    response_path = response_dir / "hb_response.csv"
    with response_path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream)
        writer.writerow(("frequency_hz", "hb_s21_real", "hb_s21_imag"))
        writer.writerows(zip(frequency, hb.real, hb.imag, strict=True))
    responses = runtime.ResolvedCircuitStage(
        "evaluate_responses",
        response_dir / "receipt.json",
        {"produced_artifacts": {"hb_response": {"path": response_path.name}}},
        "PASS",
    )
    fit_dir = tmp_path / "fit"
    fit_dir.mkdir()

    result = runtime._fit_c11_stage(fit_dir, responses)

    parameters = result["parameters_hz"]
    assert parameters["fa_hz"] == pytest.approx(expected[0], rel=0.01)
    assert parameters["fb_hz"] == pytest.approx(expected[1], rel=0.01)
    assert parameters["coupling_hz"] == pytest.approx(expected[2], rel=0.05)
    assert parameters["kappa_hz"] == pytest.approx(expected[3], rel=0.05)
    assert result["start_count"] == 30


def test_staged_actions_seal_then_resolve_and_fail_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    sim, source, direct_spec = _configured_sim(tmp_path)
    subprocess_run = runtime.subprocess.run
    calls: list[object] = []

    def counted_run(*args: object, **kwargs: object) -> object:
        calls.append(args[0])
        return subprocess_run(*args, **kwargs)

    monkeypatch.setattr(runtime.subprocess, "run", counted_run)
    stages = [
        ("optimize", lambda *, action: sim.optimize(action=action, on_progress=None)),
        ("refine_winner", sim.refine_winner),
        ("evaluate_responses", sim.evaluate_responses),
        ("fit_c11", sim.fit_c11),
        ("evaluate_t1", sim.evaluate_t1),
        ("build_report", sim.build_report),
    ]
    sealed = {name: action(action="execute") for name, action in stages}
    assert [stage.status for stage in sealed.values()] == ["PASS"] * 6
    assert len(calls) == 4
    request = json.loads(
        (sealed["optimize"].path.parent / "circuit-workbench-run-request.v1.json").read_text(
            encoding="utf-8"
        )
    )
    assert request["reduction"] == {
        "retained": [{"component_id": "resonator_0", "coordinate_name": "signal"}],
        "transforms": [],
        "eliminated": "complete_complement",
    }
    assert request["plan"]["ports"] == [
        {
            "id": f"port_{index}",
            "endpoint": {"component_id": f"resonator_{index}", "pin_name": "signal"},
            "role": "terminated" if index < 2 else "nonloading_probe",
            "resistance_ohm": 50.0,
        }
        for index in range(4)
    ]
    expected_roles = {
        "port_0": "terminated",
        "port_1": "terminated",
        "port_2": "nonloading_probe",
        "port_3": "nonloading_probe",
    }
    assert all(stage.receipt["port_roles"] == expected_roles for stage in sealed.values())
    assert request["gates"] == [
        {
            "id": "nonnegative_stiffness",
            "expression": {
                "op": "greater_equal",
                "args": [{"output": "stiffness"}, {"const": 0.0}],
            },
            "state": "active",
            "human_authority": "human://accepted-runtime-test-fixture",
        }
    ]
    winner = (sealed["optimize"].result or {})["best"]
    assert winner["rejecting_gate_ids"] == []
    assert winner["gates"] == [{"id": "nonnegative_stiffness", "state": "active", "value": 1.0}]
    refinement = sealed["refine_winner"].result or {}
    assert set(refinement) >= {
        "coarse_outputs",
        "fine_outputs",
        "relative_changes",
    }
    assert sealed["refine_winner"].status == "PASS"
    assert refinement["maximum_relative_change"] == max(refinement["relative_changes"].values())
    assert refinement["maximum_relative_change"] <= refinement["relative_tolerance"]
    responses = sealed["evaluate_responses"]
    response_result = responses.result or {}
    assert response_result["active_terminated_ports"] == ["port_0", "port_1"]
    assert response_result["grids"]["direct"]["points"] == 3
    assert response_result["grids"]["hb"]["points"] == 5
    direct_path = responses.path.parent / "direct_response.csv"
    hb_path = responses.path.parent / "hb_response.csv"
    assert set(runtime._read_numeric_csv(direct_path)) == {
        "frequency_hz",
        "direct_s21_real",
        "direct_s21_imag",
    }
    assert set(runtime._read_numeric_csv(hb_path)) == {
        "frequency_hz",
        "hb_s21_real",
        "hb_s21_imag",
    }
    c11_path = sealed["fit_c11"].path.parent / "c11_fit.csv"
    assert len(runtime._read_numeric_csv(c11_path)["frequency_hz"]) == 5
    assert set(runtime._read_numeric_csv(c11_path)) == {
        "frequency_hz",
        "c11_s21_real",
        "c11_s21_imag",
    }
    assert (sealed["fit_c11"].result or {})["fit_input"] == "pump_off_hb_s21"
    t1_result = sealed["evaluate_t1"].result or {}
    assert t1_result["port_roles"] == expected_roles
    assert t1_result["method"].startswith("pump-off HB Z")
    assert t1_result["finite_sample_count"] == t1_result["sample_count"]
    assert t1_result["not_evaluable_sample_count"] == 0
    assert t1_result["minimum_finite_t1_s"] is not None
    report_html = (sealed["build_report"].path.parent / "report.html").read_text(encoding="utf-8")
    assert "Objective targets" in report_html
    assert "stiffness" in report_html and "1000000.0" in report_html
    assert "Sealed objective declaration" in report_html
    assert "Bound consumer artifacts" in report_html
    assert "fixture_input" in report_html and "test-public-input.v1" in report_html
    assert "dimensionless" in report_html
    assert request["artifacts"]["fixture_input"]["source_sha256"] in report_html
    assert "test &lt;fixture&gt;" in report_html and "test <fixture>" not in report_html
    response_html = resolve_circuit_result(tmp_path / "staged").show_responses().html_text
    assert "Direct response" in response_html
    assert "Pump-off HB and C11 fit" in response_html
    assert response_html.count("<svg") == 2
    direct = sim.direct_solve(direct_spec, action="execute")
    assert direct.status == "PASS"
    assert direct.receipt["candidate"]["source"] == "optimizer_winner"
    direct_request = json.loads(
        direct.path.with_name("circuit-workbench-run-request.v1.json").read_text(encoding="utf-8")
    )
    assert direct_request["objective"] is None
    assert direct_request["gates"] == []
    assert set(direct_request["upstream_receipts"]) == {"optimize", "refine_winner"}
    assert len(calls) == 5
    assert "direct_solve" not in resolve_circuit_result(tmp_path / "staged").stages

    def no_subprocess(*args: object, **kwargs: object) -> object:
        raise AssertionError("resolve must not start Julia")

    monkeypatch.setattr(runtime.subprocess, "run", no_subprocess)
    resolved = {name: action(action="resolve") for name, action in stages}
    assert {name: stage.canonical_sha256 for name, stage in resolved.items()} == {
        name: stage.canonical_sha256 for name, stage in sealed.items()
    }
    assert sim.direct_solve(direct_spec, action="resolve").canonical_sha256 == (
        direct.canonical_sha256
    )
    assert sim.build_report(action="resolve").status == "PASS"
    run_dir = tmp_path / "staged"
    assert resolve_circuit_result(run_dir).status == "PASS"
    assert resolve_circuit_campaign([run_dir]).status == "PASS"
    with pytest.raises(RuntimeContractError, match="durable bytes"):
        sim.optimize(action="execute")

    source.write_text('{"fixture":"changed"}', encoding="utf-8")
    assert sim.optimize(action="resolve").status == "NOT_EVALUABLE"
    source.write_text('{"fixture":"public"}', encoding="utf-8")
    assert sim.optimize(action="resolve").status == "PASS"

    for response_path in (direct_path, hb_path):
        original_response = response_path.read_bytes()
        response_path.write_bytes(original_response + b"\ncorrupt")
        assert sim.evaluate_responses(action="resolve").status == "NOT_EVALUABLE"
        response_path.write_bytes(original_response)

    receipt_path = sealed["evaluate_responses"].path
    original_receipt = receipt_path.read_text(encoding="utf-8")
    tampered = json.loads(original_receipt)
    tampered["status"] = "FAILED"
    receipt_path.write_text(json.dumps(tampered), encoding="utf-8")
    assert sim.fit_c11(action="resolve").status == "NOT_EVALUABLE"
    receipt_path.write_text(original_receipt, encoding="utf-8")

    result = resolve_circuit_result(run_dir)
    assert result.stage("build_report").status == "PASS"
    assert resolve_circuit_campaign([run_dir]).status == "PASS"

    tampered = json.loads(original_receipt)
    tampered["canonical_sha256"] = "0" * 64
    receipt_path.write_text(json.dumps(tampered), encoding="utf-8")
    assert resolve_circuit_result(run_dir).stage("evaluate_responses").status == "NOT_EVALUABLE"
    receipt_path.write_text("{", encoding="utf-8")
    assert resolve_circuit_result(run_dir).stage("evaluate_responses").status == "NOT_EVALUABLE"

    optimize_receipt = sealed["optimize"].path
    tampered = json.loads(optimize_receipt.read_text(encoding="utf-8"))
    tampered["status"] = "NOT_EVALUABLE"
    tampered["failure"] = None
    tampered.pop("canonical_sha256")
    tampered["canonical_sha256"] = runtime._fingerprint(tampered)
    optimize_receipt.write_text(json.dumps(tampered), encoding="utf-8")
    assert sim.optimize(action="resolve").failure is None
    with pytest.raises(RuntimeContractError) as error:
        sim.refine_winner(action="execute")
    assert "dependency: NOT_EVALUABLE" in str(error.value)
    assert "dependency: None" not in str(error.value)


def test_explicit_candidate_runs_downstream_stages_without_optimization(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    sim, source, _ = _configured_sim(tmp_path)
    candidate = {"resonator_0.capacitance_f": 1.0e-12}
    with pytest.raises(RuntimeContractError, match="do not match"):
        sim.set_explicit_candidate({"foreign.parameter": 1.0}, provenance={"source": "user"})
    with pytest.raises(RuntimeContractError, match="above its bound"):
        sim.set_explicit_candidate(
            {"resonator_0.capacitance_f": 2.0e-12}, provenance={"source": "user"}
        )
    sim.set_explicit_candidate(candidate, provenance={"source": "public fixture"})
    with pytest.raises(RuntimeContractError, match="derives Direct outputs"):
        sim.evaluate_responses(
            action="execute",
            direct_evaluation=DirectEvaluationSpec(5.0e9, 5.0e9, 5.0e9),
        )

    subprocess_run = runtime.subprocess.run
    calls: list[object] = []

    def counted_run(*args: object, **kwargs: object) -> object:
        calls.append(args[0])
        return subprocess_run(*args, **kwargs)

    monkeypatch.setattr(runtime.subprocess, "run", counted_run)
    stages = {
        "evaluate_responses": sim.evaluate_responses(action="execute"),
        "fit_c11": sim.fit_c11(action="execute"),
        "evaluate_t1": sim.evaluate_t1(action="execute"),
        "build_report": sim.build_report(action="execute"),
    }
    assert [stage.status for stage in stages.values()] == ["PASS"] * 4
    assert len(calls) == 2
    assert not (tmp_path / "staged" / "stages" / "optimize").exists()
    assert not (tmp_path / "staged" / "stages" / "refine_winner").exists()

    binding = stages["evaluate_responses"].receipt["candidate"]
    assert binding["source"] == "externally_selected_candidate"
    assert binding["physical_parameters"] == candidate
    assert all(stage.receipt["candidate"] == binding for stage in stages.values())
    response_request = json.loads(
        (
            stages["evaluate_responses"].path.parent / "circuit-workbench-run-request.v1.json"
        ).read_text(encoding="utf-8")
    )
    report_request = json.loads(
        (stages["build_report"].path.parent / "circuit-workbench-run-request.v1.json").read_text(
            encoding="utf-8"
        )
    )
    assert response_request["upstream_receipts"] == {}
    assert set(report_request["upstream_receipts"]) == {
        "evaluate_responses",
        "fit_c11",
        "evaluate_t1",
    }
    assert all(
        "candidate was not optimized or refined under this sealed plan"
        in stage.receipt["nonclaims"]
        for stage in stages.values()
    )

    run_dir = tmp_path / "staged"
    resolved = resolve_circuit_result(run_dir)
    assert resolved.status == "PASS"
    assert resolve_circuit_campaign([run_dir]).status == "PASS"
    assert "Not run or claimed" in resolved.show_winner_refinement().html_text
    report = (stages["build_report"].path.parent / "report.html").read_text(encoding="utf-8")
    assert "externally_selected_candidate" in report
    assert "Not run or claimed" in report

    def no_subprocess(*args: object, **kwargs: object) -> object:
        raise AssertionError("resolve must not start Julia")

    monkeypatch.setattr(runtime.subprocess, "run", no_subprocess)
    assert sim.evaluate_responses(action="resolve").status == "PASS"
    assert sim.fit_c11(action="resolve").status == "PASS"
    assert sim.evaluate_t1(action="resolve").status == "PASS"
    assert sim.build_report(action="resolve").status == "PASS"

    original_source = source.read_text(encoding="utf-8")
    source.write_text('{"fixture":"changed"}', encoding="utf-8")
    assert resolve_circuit_result(run_dir).status == "NOT_EVALUABLE"
    source.write_text(original_source, encoding="utf-8")

    response_receipt = stages["evaluate_responses"].path
    tampered = json.loads(response_receipt.read_text(encoding="utf-8"))
    tampered["candidate"]["canonical_sha256"] = "0" * 64
    tampered.pop("canonical_sha256")
    tampered["canonical_sha256"] = runtime._fingerprint(tampered)
    response_receipt.write_text(json.dumps(tampered), encoding="utf-8")
    assert resolve_circuit_result(run_dir).status == "NOT_EVALUABLE"


def test_targetless_direct_evaluation_binds_full_explicit_candidate_chain(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    plan, ipf = _targeted_plan()
    source = tmp_path / "targetless-input.json"
    source.write_text('{"fixture":"public"}', encoding="utf-8")
    sim = CircuitSim(
        tmp_path,
        "targetless",
        lifecycle_state="ACCEPTED",
        data_classification="public",
    )
    sim.set_plan(plan)
    sim.bind_artifact(
        "fixture_input",
        source,
        schema="test-public-input.v1",
        units="dimensionless",
        provenance={"authority": "public test fixture"},
    )
    sim.set_reduction(
        ReductionSpec((ipf.coord("readout_attachment"), ipf.coord("filter_open_tail")))
    )
    sim.set_variables(
        [
            VariableSpec(
                ipf.parameter("readout_open_length_m"),
                transform="log",
                lower=4.5e-3,
                upper=5.5e-3,
            )
        ]
    )
    candidate = {"ipf.readout_open_length_m": 5.0e-3}
    sim.set_explicit_candidate(candidate, provenance={"source": "public test fixture"})
    sim.set_responses(
        ResponseSpec(
            direct_frequency_hz=None,
            hb_frequency_hz=(2.5e9, 2.75e9, 3.0e9, 3.25e9, 3.5e9),
            input_port="port_0",
            output_port="port_1",
            pump_frequency_hz=3.0e9,
        )
    )
    sim.set_t1(
        T1Spec(
            (2.5e9, 3.0e9, 3.5e9),
            ("port_0", "port_1"),
            ("port_2", "port_3"),
            (0.5, 0.5),
            3.0e9,
        )
    )
    spec = DirectEvaluationSpec(3.0e9, 3.0e9, 3.0e9)

    for values in ((0.0, 3.0e9, 3.0e9), (float("nan"), 3.0e9, 3.0e9)):
        with pytest.raises(RuntimeContractError, match="finite and positive"):
            DirectEvaluationSpec(*values)
    with pytest.raises(RuntimeContractError, match="requires DirectEvaluationSpec"):
        sim.evaluate_responses(action="execute")

    stages = {
        "evaluate_responses": sim.evaluate_responses(action="execute", direct_evaluation=spec),
        "fit_c11": sim.fit_c11(action="execute"),
        "evaluate_t1": sim.evaluate_t1(action="execute"),
        "build_report": sim.build_report(action="execute"),
    }
    assert [stage.status for stage in stages.values()] == ["PASS"] * 4
    assert not (tmp_path / "targetless" / "stages" / "optimize").exists()
    assert not (tmp_path / "targetless" / "stages" / "refine_winner").exists()
    assert not (stages["evaluate_responses"].path.parent / "direct_response.csv").exists()

    response_result = stages["evaluate_responses"].result or {}
    declaration = response_result["direct_physical_evaluation"]["declaration"]
    assert set(response_result["direct_physical_evaluation"]["cared_outputs"]) == {
        "readout_diagonal_root_hz",
        "filter_diagonal_root_hz",
        "transfer_cofactor_zero_hz",
        "residue_normalized_midpoint_exchange_abs_real_hz",
        "diagonal_root_linewidth_sum_hz",
    }
    assert response_result["direct_s21"] == {"executed": False}
    assert all(
        stage.receipt["direct_physical_evaluation"] == declaration for stage in stages.values()
    )
    assert all(stage.receipt["objective_status"] == "NOT_REQUESTED" for stage in stages.values())
    assert all(stage.receipt["optimization_status"] == "NOT_REQUESTED" for stage in stages.values())
    assert all(
        stage.receipt["candidate"]["physical_parameters"] == candidate for stage in stages.values()
    )

    response_request = json.loads(
        stages["evaluate_responses"]
        .path.with_name("circuit-workbench-run-request.v1.json")
        .read_text(encoding="utf-8")
    )
    assert response_request["objective"] is None
    assert response_request["optimizer"] is None
    assert response_request["gates"] == []
    assert response_request["direct_physical_evaluation"] == declaration
    manifest = json.loads(
        (stages["build_report"].path.parent / "report.json").read_text(encoding="utf-8")
    )
    assert manifest["direct_physical_evaluation"] == declaration
    assert manifest["objective_status"] == "NOT_REQUESTED"
    assert manifest["optimization_status"] == "NOT_REQUESTED"

    def no_subprocess(*args: object, **kwargs: object) -> object:
        raise AssertionError("resolve must not start Julia")

    monkeypatch.setattr(runtime.subprocess, "run", no_subprocess)
    assert (
        sim.evaluate_responses(action="resolve", direct_evaluation=spec).canonical_sha256
        == stages["evaluate_responses"].canonical_sha256
    )
    assert sim.fit_c11(action="resolve").canonical_sha256 == stages["fit_c11"].canonical_sha256
    assert (
        sim.evaluate_t1(action="resolve").canonical_sha256 == stages["evaluate_t1"].canonical_sha256
    )
    assert (
        sim.build_report(action="resolve").canonical_sha256
        == stages["build_report"].canonical_sha256
    )
    with pytest.raises(RuntimeContractError, match="requires DirectEvaluationSpec"):
        sim.evaluate_responses(action="resolve")
    with pytest.raises(RuntimeContractError, match="stale or mismatched"):
        sim.evaluate_responses(
            action="resolve",
            direct_evaluation=DirectEvaluationSpec(3.1e9, 3.0e9, 3.0e9),
        )

    receipt_path = stages["evaluate_responses"].path
    original_receipt = receipt_path.read_text(encoding="utf-8")
    tampered = json.loads(original_receipt)
    tampered["direct_physical_evaluation"]["cared_outputs"].pop("readout_diagonal_root_hz")
    tampered.pop("canonical_sha256")
    tampered["canonical_sha256"] = runtime._fingerprint(tampered)
    receipt_path.write_text(json.dumps(tampered), encoding="utf-8")
    assert (
        resolve_circuit_result(tmp_path / "targetless").stage("evaluate_responses").status
        == "NOT_EVALUABLE"
    )
    receipt_path.write_text(original_receipt, encoding="utf-8")

    sim.set_explicit_candidate(
        {"ipf.readout_open_length_m": 5.1e-3},
        provenance={"source": "public test fixture"},
    )
    with pytest.raises(RuntimeContractError, match="stale or mismatched"):
        sim.evaluate_responses(action="resolve", direct_evaluation=spec)


def test_direct_solve_binds_explicit_candidate_plan_and_spec(tmp_path: Path) -> None:
    plan, resonators = _plan(sections=1)
    variable = VariableSpec(
        resonators[0].parameter("capacitance_f"),
        transform="log",
        lower=0.9e-12,
        upper=1.1e-12,
    )
    spec = DirectSolveSpec(
        ReductionSpec((resonators[0].coord("signal"),)),
        ("root",),
        "root",
        5.0e9,
    )
    sim = CircuitSim(tmp_path, "direct-explicit", data_classification="public")
    sim.set_plan(plan)
    sim.set_variables([variable])
    sim.set_explicit_candidate(
        {"resonator_0.capacitance_f": 1.0e-12},
        provenance={"source": "public test fixture"},
    )

    sealed = sim.direct_solve(spec, action="execute")
    assert sealed.status == "PASS"
    assert sim.direct_solve(spec, action="resolve").canonical_sha256 == sealed.canonical_sha256
    result = sealed.result or {}
    assert result["retained_labels"] == ["root"]
    assert result["selected_label"] == "root"
    assert result["selected_index"] == 0
    assert result["root_anchor_hz"] == 5.0e9
    assert set(result["root_angular_frequency_rad_s"]) == {"real", "imag"}
    assert result["frequency_hz"] > 0
    assert result["linewidth_hz"] >= 0
    assert result["validation"]["scaled_residual"] >= 0
    request = json.loads(
        sealed.path.with_name("circuit-workbench-run-request.v1.json").read_text(encoding="utf-8")
    )
    assert request["objective"] is None
    assert request["gates"] == []
    assert request["upstream_receipts"] == {}
    assert request["candidate"]["source"] == "externally_selected_candidate"
    assert result["reduction"] == request["reduction"]
    assert not (tmp_path / "direct-explicit" / "stages" / "optimize").exists()

    with pytest.raises(RuntimeContractError, match="spec mismatches"):
        sim.direct_solve(
            DirectSolveSpec(spec.reduction, spec.retained_labels, spec.root_label, 5.1e9),
            action="resolve",
        )
    sim.set_explicit_candidate(
        {"resonator_0.capacitance_f": 1.01e-12},
        provenance={"source": "public test fixture"},
    )
    with pytest.raises(RuntimeContractError, match="candidate mismatches"):
        sim.direct_solve(spec, action="resolve")

    missing = CircuitSim(tmp_path, "direct-explicit", data_classification="public")
    missing.set_plan(plan)
    missing.set_variables([variable])
    with pytest.raises(RuntimeContractError, match="candidate mismatches"):
        missing.direct_solve(spec, action="resolve")


def test_standalone_direct_evaluation_binds_exactly_five_quantities(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    plan, ipf = _targeted_plan()
    source = tmp_path / "standalone-input.json"
    source.write_text('{"fixture":"public"}', encoding="utf-8")
    sim = CircuitSim(tmp_path, "standalone-direct", data_classification="public")
    sim.set_plan(plan)
    sim.bind_artifact(
        "fixture_input",
        source,
        schema="test-public-input.v1",
        units="dimensionless",
        provenance={"authority": "public test fixture"},
    )
    sim.set_reduction(
        ReductionSpec((ipf.coord("readout_attachment"), ipf.coord("filter_open_tail")))
    )
    sim.set_variables(
        [
            VariableSpec(
                ipf.parameter("readout_open_length_m"),
                transform="log",
                lower=4.5e-3,
                upper=5.5e-3,
            )
        ]
    )
    candidate = {"ipf.readout_open_length_m": 5.0e-3}
    sim.set_explicit_candidate(candidate, provenance={"source": "public test fixture"})
    spec = StandaloneDirectEvaluationSpec(3.0e9, 3.0e9, 3.0e9)

    sealed = sim.evaluate_direct(spec, action="execute")
    assert sealed.status == "PASS"
    result = sealed.result or {}
    expected = {
        "readout_diagonal_root_hz",
        "filter_diagonal_root_hz",
        "transfer_cofactor_zero_hz",
        "residue_normalized_midpoint_exchange_abs_real_hz",
        "diagonal_root_linewidth_sum_hz",
    }
    assert set(result["cared_outputs"]) == expected
    assert set(result["validation"]) == {
        "readout_root",
        "filter_root",
        "transfer_zero",
        "residue_normalization_abs",
    }
    assert result["applied_parameter_bindings"] == candidate
    request_path = sealed.path.with_name("circuit-workbench-run-request.v1.json")
    request = json.loads(request_path.read_text(encoding="utf-8"))
    assert request["objective"] is None
    assert request["optimizer"] is None
    assert request["gates"] == []
    assert request["upstream_receipts"] == {}
    assert request["standalone_direct_evaluation"] == result["standalone_direct_evaluation"]
    assert sealed.receipt["standalone_direct_evaluation"] == result["standalone_direct_evaluation"]
    assert all("transfer cofactor zero" not in nonclaim for nonclaim in sealed.receipt["nonclaims"])
    assert result["cared_outputs"]["transfer_cofactor_zero_hz"] >= 0.0
    assert result["validation"]["transfer_zero"]["simple_root"] is True
    assert result["validation"]["transfer_zero"]["passive_half_plane"] is True
    assert not (tmp_path / "standalone-direct" / "stages" / "evaluate_responses").exists()

    def no_subprocess(*args: object, **kwargs: object) -> object:
        raise AssertionError("resolve must not start Julia")

    monkeypatch.setattr(runtime.subprocess, "run", no_subprocess)
    monkeypatch.setattr(runtime.subprocess, "Popen", no_subprocess)
    assert sim.evaluate_direct(spec, action="resolve").canonical_sha256 == sealed.canonical_sha256
    original_receipt = sealed.path.read_text(encoding="utf-8")
    tampered = json.loads(original_receipt)
    tampered["result"]["cared_outputs"].pop("transfer_cofactor_zero_hz")
    tampered["output_sha256"] = runtime._fingerprint(tampered["result"])
    tampered.pop("canonical_sha256")
    tampered["canonical_sha256"] = runtime._fingerprint(tampered)
    sealed.path.write_text(json.dumps(tampered), encoding="utf-8")
    assert sim.evaluate_direct(spec, action="resolve").status == "NOT_EVALUABLE"
    sealed.path.write_text(original_receipt, encoding="utf-8")
    with pytest.raises(RuntimeContractError, match="stale or mismatched"):
        sim.evaluate_direct(
            StandaloneDirectEvaluationSpec(3.0e9, 3.0e9, 3.1e9),
            action="resolve",
        )
    with pytest.raises(RuntimeContractError, match="transfer_zero_anchor_hz"):
        StandaloneDirectEvaluationSpec(3.0e9, 3.0e9, 0.0)
    with pytest.raises(RuntimeContractError, match="transfer_zero_anchor_hz"):
        StandaloneDirectEvaluationSpec(3.0e9, 3.0e9, float("nan"))
    sim.set_explicit_candidate(
        {"ipf.readout_open_length_m": 5.1e-3},
        provenance={"source": "public test fixture"},
    )
    with pytest.raises(RuntimeContractError, match="candidate mismatches"):
        sim.evaluate_direct(spec, action="resolve")

    sim.set_explicit_candidate(candidate, provenance={"source": "public test fixture"})
    source.write_text('{"fixture":"changed"}', encoding="utf-8")
    assert sim.evaluate_direct(spec, action="resolve").status == "NOT_EVALUABLE"


def test_standalone_direct_evaluation_seals_root_failure_as_not_evaluable(
    tmp_path: Path,
) -> None:
    plan, ipf = _targeted_plan()
    sim = CircuitSim(tmp_path, "standalone-direct-root-failure", data_classification="public")
    sim.set_plan(plan)
    sim.set_reduction(
        ReductionSpec((ipf.coord("readout_attachment"), ipf.coord("filter_open_tail")))
    )
    sim.set_variables(
        [
            VariableSpec(
                ipf.parameter("readout_open_length_m"),
                transform="log",
                lower=4.5e-3,
                upper=5.5e-3,
            )
        ]
    )
    sim.set_explicit_candidate(
        {"ipf.readout_open_length_m": 5.0e-3},
        provenance={"source": "public test fixture"},
    )
    spec = StandaloneDirectEvaluationSpec(1.0e308, 3.0e9, 3.0e9)

    sealed = sim.evaluate_direct(spec, action="execute")
    assert sealed.status == "NOT_EVALUABLE"
    assert sealed.failure is None
    assert (sealed.result or {})["reason"]["message"]
    assert sim.evaluate_direct(spec, action="resolve").canonical_sha256 == sealed.canonical_sha256


def test_standalone_direct_evaluation_preserves_failed_receipt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    plan, ipf = _targeted_plan()
    sim = CircuitSim(tmp_path, "standalone-direct-failed", data_classification="public")
    sim.set_plan(plan)
    sim.set_reduction(
        ReductionSpec((ipf.coord("readout_attachment"), ipf.coord("filter_open_tail")))
    )
    sim.set_variables(
        [
            VariableSpec(
                ipf.parameter("readout_open_length_m"),
                transform="log",
                lower=4.5e-3,
                upper=5.5e-3,
            )
        ]
    )
    sim.set_explicit_candidate(
        {"ipf.readout_open_length_m": 5.0e-3},
        provenance={"source": "public test fixture"},
    )
    spec = StandaloneDirectEvaluationSpec(3.0e9, 3.0e9, 3.0e9)
    failure = {
        "error_code": "public_synthetic_runner_failure",
        "category": "task_execution_failed",
        "retryable": False,
        "type": "PublicSyntheticRunnerError",
        "message": "public synthetic standalone Direct failure",
    }

    def seal_failed_receipt(command: list[str], **_: object) -> subprocess.CompletedProcess[str]:
        request_path = Path(command[-2])
        receipt_path = Path(command[-1])
        request = json.loads(request_path.read_text(encoding="utf-8"))
        receipt = runtime._python_stage_receipt(
            request,
            request_path,
            None,
            durable_request_path=request_path,
            durable_stage_dir=receipt_path.parent,
            failure=failure,
        )
        receipt["standalone_direct_evaluation"] = request["standalone_direct_evaluation"]
        receipt.pop("canonical_sha256")
        receipt["canonical_sha256"] = runtime._fingerprint(receipt)
        receipt_path.write_text(json.dumps(receipt), encoding="utf-8")
        return subprocess.CompletedProcess(command, 1)

    monkeypatch.setattr(runtime.subprocess, "run", seal_failed_receipt)
    with pytest.raises(RuntimeContractError) as error:
        sim.evaluate_direct(spec, action="execute")
    assert error.value.error_code == failure["error_code"]
    assert error.value.category == failure["category"]
    assert failure["message"] in str(error.value)

    resolved = sim.evaluate_direct(spec, action="resolve")
    assert resolved.status == "FAILED"
    assert resolved.result is None
    assert resolved.receipt["failure"] == failure
    assert failure["message"] in (resolved.failure or "")
    original_receipt = resolved.path.read_text(encoding="utf-8")

    tampered = json.loads(original_receipt)
    tampered["failure"]["retryable"] = "false"
    tampered.pop("canonical_sha256")
    tampered["canonical_sha256"] = runtime._fingerprint(tampered)
    resolved.path.write_text(json.dumps(tampered), encoding="utf-8")
    assert sim.evaluate_direct(spec, action="resolve").status == "NOT_EVALUABLE"

    tampered = json.loads(original_receipt)
    tampered["result"] = {}
    tampered["output_sha256"] = runtime._fingerprint(tampered["result"])
    tampered.pop("canonical_sha256")
    tampered["canonical_sha256"] = runtime._fingerprint(tampered)
    resolved.path.write_text(json.dumps(tampered), encoding="utf-8")
    assert sim.evaluate_direct(spec, action="resolve").status == "NOT_EVALUABLE"


def test_standalone_direct_evaluation_binds_optimizer_winner(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    plan, ipf = _targeted_plan()
    refinement, _ = _targeted_plan(sections=2)
    sim = CircuitSim(tmp_path, "standalone-direct-winner", data_classification="public")
    sim.set_plan(plan)
    sim.set_reduction(
        ReductionSpec((ipf.coord("readout_attachment"), ipf.coord("filter_open_tail")))
    )
    sim.set_variables(
        [
            VariableSpec(
                ipf.parameter("readout_open_length_m"),
                transform="log",
                lower=4.5e-3,
                upper=5.5e-3,
            )
        ]
    )
    cared_outputs = runtime._direct_evaluation_declaration(
        DirectEvaluationSpec(3.0e9, 3.0e9, 3.0e9)
    )["cared_outputs"]
    sim.set_objective(
        CircuitObjective.from_targets(
            {
                "outputs": cared_outputs,
                "values": {
                    "readout_diagonal_root_hz": 3.0e9,
                    "filter_diagonal_root_hz": 3.0e9,
                    "transfer_cofactor_zero_hz": 3.0e9,
                    "residue_normalized_midpoint_exchange_abs_real_hz": 1.0e6,
                    "diagonal_root_linewidth_sum_hz": 1.0e6,
                },
                "weights": {name: 1.0 for name in cared_outputs},
            }
        )
    )
    sim.set_optimizer(
        OptimizerSpec(
            "cma_es",
            seed=0,
            human_authority="human://accepted-runtime-test-fixture",
            controls={
                "initial_sigma": 0.01,
                "maxiter": 1,
                "maxfevals": 3,
                "popsize": 3,
            },
        )
    )
    sim.set_refinement(plan=refinement, relative_tolerance=1.0e9)

    optimization = sim.optimize(action="execute")
    refinement_stage = sim.refine_winner(action="execute")
    assert optimization.status == refinement_stage.status == "PASS"
    spec = StandaloneDirectEvaluationSpec(3.0e9, 3.0e9, 3.0e9)
    sealed = sim.evaluate_direct(spec, action="execute")
    assert sealed.status == "PASS"
    result = sealed.result or {}
    assert set(result["cared_outputs"]) == {
        "readout_diagonal_root_hz",
        "filter_diagonal_root_hz",
        "transfer_cofactor_zero_hz",
        "residue_normalized_midpoint_exchange_abs_real_hz",
        "diagonal_root_linewidth_sum_hz",
    }
    assert "transfer_zero" in result["validation"]
    assert sealed.receipt["candidate"]["source"] == "optimizer_winner"
    request = json.loads(
        sealed.path.with_name("circuit-workbench-run-request.v1.json").read_text(encoding="utf-8")
    )
    assert request["objective"] is None
    assert request["optimizer"] is None
    assert request["gates"] == []
    assert request["upstream_receipts"] == {
        "optimize": optimization.canonical_sha256,
        "refine_winner": refinement_stage.canonical_sha256,
    }

    def no_subprocess(*args: object, **kwargs: object) -> object:
        raise AssertionError("resolve must not start Julia")

    monkeypatch.setattr(runtime.subprocess, "run", no_subprocess)
    monkeypatch.setattr(runtime.subprocess, "Popen", no_subprocess)
    assert sim.evaluate_direct(spec, action="resolve").canonical_sha256 == sealed.canonical_sha256

    original = refinement_stage.path.read_text(encoding="utf-8")
    tampered = json.loads(original)
    tampered["status"] = "NOT_EVALUABLE"
    tampered.pop("canonical_sha256")
    tampered["canonical_sha256"] = runtime._fingerprint(tampered)
    refinement_stage.path.write_text(json.dumps(tampered), encoding="utf-8")
    assert sim.evaluate_direct(spec, action="resolve").status == "NOT_EVALUABLE"
    refinement_stage.path.write_text(original, encoding="utf-8")


def test_direct_solve_seals_expected_numerical_failure_as_not_evaluable(
    tmp_path: Path,
) -> None:
    capacitance_f = 1.0e-12
    inductance_h = 1.0e-9
    plan = CircuitPlan("direct-critical-root")
    resonator = plan.add(
        parallel_lc_resonator(
            id="resonator",
            capacitance_f=capacitance_f,
            inductance_h=inductance_h,
        )
    )
    plan.add_port(
        "terminated",
        resonator.pin("signal"),
        role="terminated",
        resistance_ohm=0.5 * (inductance_h / capacitance_f) ** 0.5,
    )
    sim = CircuitSim(tmp_path, "direct-critical-root", data_classification="public")
    sim.set_plan(plan)
    sim.set_variables(
        [
            VariableSpec(
                resonator.parameter("capacitance_f"),
                transform="log",
                lower=0.9e-12,
                upper=1.1e-12,
            )
        ]
    )
    sim.set_explicit_candidate(
        {"resonator.capacitance_f": capacitance_f},
        provenance={"source": "public critically damped fixture"},
    )
    spec = DirectSolveSpec(
        ReductionSpec((resonator.coord("signal"),)),
        ("root",),
        "root",
        5.0e9,
    )

    sealed = sim.direct_solve(spec, action="execute")
    assert sealed.status == "NOT_EVALUABLE"
    assert sealed.failure is None
    assert (sealed.result or {})["status"] == "NOT_EVALUABLE"
    assert (sealed.result or {})["reason"]["message"]
    assert sim.direct_solve(spec, action="resolve").canonical_sha256 == sealed.canonical_sha256


def test_optimization_progress_is_transient_after_ledger_write(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    sim, _, _ = _configured_sim(tmp_path, maximum_generations=2)
    ledger_path = (
        tmp_path
        / "staged"
        / "stages"
        / "optimize"
        / "circuit-workbench-optimization-ledger.v1.json"
    )
    observed: list[OptimizationProgress] = []

    def failing_observer(progress: OptimizationProgress) -> None:
        assert ledger_path.is_file()
        assert json.loads(ledger_path.read_text(encoding="utf-8"))["entries"]
        with pytest.raises(FrozenInstanceError):
            progress.__setattr__("generation", 0)
        observed.append(progress)
        raise RuntimeError("public-fixture observer failure")

    with pytest.warns(RuntimeWarning, match="observer disabled") as warnings:
        sealed = sim.optimize(action="execute", on_progress=failing_observer)
    assert len(warnings) == 1
    assert observed == [OptimizationProgress(generation=1, maximum_generations=2)]
    assert sealed.status == "PASS"

    stage_dir = sealed.path.parent
    for path in (
        stage_dir / "circuit-workbench-run-request.v1.json",
        ledger_path,
        sealed.path,
    ):
        assert '"on_progress":' not in path.read_text(encoding="utf-8")

    def no_subprocess(*args: object, **kwargs: object) -> object:
        raise AssertionError("resolve must not start Julia")

    monkeypatch.setattr(runtime.subprocess, "run", no_subprocess)
    monkeypatch.setattr(runtime.subprocess, "Popen", no_subprocess)
    assert sim.optimize(action="resolve", on_progress=observed.append).status == "PASS"
    assert observed == [OptimizationProgress(generation=1, maximum_generations=2)]


def test_composite_winner_key_resolves_to_selected_leaf_binding(tmp_path: Path) -> None:
    library = CircuitLibrary("test.composite", "1", "a" * 64)

    @circuit_component(
        type_id="test.variable_lc.v1",
        pins=("signal",),
        parameters=({"name": "capacitance_f", "units": "F", "role": "capacitance"},),
        coordinates=({"name": "signal", "units": "node_flux", "role": "signal"},),
        lowerer="composite",
    )
    def variable_lc(*, id: str, capacitance_f: float):
        leaf = parallel_lc_resonator(
            id=f"{id}_leaf", capacitance_f=capacitance_f, inductance_h=1.0e-9
        )
        return library.component(
            "test.variable_lc.v1",
            id=id,
            parameters={"capacitance_f": capacitance_f},
            children=(leaf,),
            pin_bindings={"signal": leaf.pin("signal")},
            coordinate_bindings={"signal": leaf.coord("signal")},
            parameter_bindings={"capacitance_f": leaf.parameter("capacitance_f")},
        )

    library.register(variable_lc)
    plan = CircuitPlan("composite")
    composite = plan.add(variable_lc(id="composite", capacitance_f=1.0e-12))
    sim = CircuitSim(
        tmp_path, "composite", lifecycle_state="ACCEPTED", data_classification="public"
    )
    sim.register_library(library)
    sim.set_plan(plan)
    sim.set_variables([VariableSpec(composite.parameter("capacitance_f"), transform="log")])
    assert sim._winner_overrides(
        {"winner_physical_parameters": {"composite.capacitance_f": 1.2e-12}}, plan
    ) == {"composite_leaf.capacitance_f": 1.2e-12}


def test_removed_compatibility_surface_is_not_public() -> None:
    assert not hasattr(runtime_api, "ObjectiveSpec")
    assert not hasattr(CircuitSim, "evaluate")
    assert not hasattr(CircuitSim, "analyze")
    assert not hasattr(CircuitPlan, "show")


def test_plan_port_role_is_explicit_and_closed() -> None:
    plan, resonators = _plan(sections=1)
    with pytest.raises(RuntimeContractError, match=r"terminated.*nonloading_probe"):
        plan.add_port("invalid", resonators[0].pin("signal"), role="probe")  # type: ignore[arg-type]


def test_response_spec_requires_two_independent_grids() -> None:
    valid = {
        "direct_frequency_hz": (1.0, 2.0, 3.0),
        "hb_frequency_hz": (1.0, 1.5, 2.0, 2.5, 3.0),
        "input_port": "input",
        "output_port": "output",
        "pump_frequency_hz": 2.0,
    }
    spec = ResponseSpec(**valid)
    assert len(spec.direct_frequency_hz) == 3
    assert len(spec.hb_frequency_hz) == 5
    for field_name in ("direct_frequency_hz", "hb_frequency_hz"):
        invalid = dict(valid)
        invalid[field_name] = (1.0, 1.0, 2.0)
        with pytest.raises(RuntimeContractError, match=field_name):
            ResponseSpec(**invalid)
    with pytest.raises(TypeError):
        ResponseSpec(
            frequency_hz=(1.0, 2.0, 3.0),
            input_port="input",
            output_port="output",
            pump_frequency_hz=2.0,
        )


def test_runtime_sdist_installs_with_bundled_julia(tmp_path: Path) -> None:
    root = Path(__file__).parents[3]
    dist = tmp_path / "dist"
    uv = shutil.which("uv")
    assert uv is not None
    subprocess.run(
        [uv, "build", root / "core/python/runtime", "--sdist", "--out-dir", dist],
        check=True,
    )
    sdist = next(dist.glob("*.tar.gz"))
    subprocess.run([uv, "build", sdist, "--wheel", "--out-dir", dist], check=True)
    wheel = next(dist.glob("*.whl"))
    venv = tmp_path / "venv"
    subprocess.run([uv, "venv", "--clear", venv], check=True)
    python = venv / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")
    subprocess.run([uv, "pip", "install", "--python", python, wheel], check=True)
    subprocess.run(
        [
            python,
            "-c",
            "from superconducting_circuits_runtime.runtime import _JULIA_ROOT; "
            "assert (_JULIA_ROOT / 'SuperconductingCircuitsCore/Project.toml').is_file(); "
            "assert (_JULIA_ROOT / 'SuperconductingCircuitsRunner/Project.toml').is_file()",
        ],
        check=True,
    )
