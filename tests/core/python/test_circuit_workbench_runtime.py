from __future__ import annotations

import json
import shutil
import subprocess
import sys
from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest
import superconducting_circuits_runtime as runtime_api
from superconducting_circuits_runtime import (
    CircuitLibrary,
    CircuitObjective,
    CircuitPlan,
    CircuitSim,
    GateSpec,
    OptimizationProgress,
    OptimizerSpec,
    ReductionSpec,
    ResponseSpec,
    T1Spec,
    VariableSpec,
    circuit_component,
    resolve_circuit_campaign,
    resolve_circuit_result,
    runtime,
)
from superconducting_circuits_runtime.catalog import parallel_lc_resonator, transmission_line
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
        plan.add_port(f"port_{index}", resonator.pin("signal"))
    return plan, resonators


def _configured_sim(tmp_path: Path, *, maximum_generations: int = 1) -> tuple[CircuitSim, Path]:
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
    sim.set_responses(ResponseSpec((4.5e9, 5.0e9, 5.5e9), "port_0", "port_1", 5.0e9))
    sim.set_t1(
        T1Spec(
            (4.5e9, 5.0e9, 5.5e9),
            ("port_0", "port_1"),
            ("port_2", "port_3"),
            (0.5, 0.5),
            5.0e9,
        )
    )
    return sim, source


def test_staged_actions_seal_then_resolve_and_fail_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    sim, source = _configured_sim(tmp_path)
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
    assert (sealed["fit_c11"].result or {})["fit_input"] == "pump_off_hb_s21"
    t1_result = sealed["evaluate_t1"].result or {}
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

    def no_subprocess(*args: object, **kwargs: object) -> object:
        raise AssertionError("resolve must not start Julia")

    monkeypatch.setattr(runtime.subprocess, "run", no_subprocess)
    resolved = {name: action(action="resolve") for name, action in stages}
    assert {name: stage.canonical_sha256 for name, stage in resolved.items()} == {
        name: stage.canonical_sha256 for name, stage in sealed.items()
    }
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

    response_path = sealed["evaluate_responses"].path.parent / "response.csv"
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


def test_optimization_progress_is_transient_after_ledger_write(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    sim, _ = _configured_sim(tmp_path, maximum_generations=2)
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
