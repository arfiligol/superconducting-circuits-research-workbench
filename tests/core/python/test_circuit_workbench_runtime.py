from __future__ import annotations

import hashlib
import json
import math
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from superconducting_circuits_runtime import (
    CircuitLibrary,
    CircuitPlan,
    CircuitSim,
    GateSpec,
    ObjectiveSpec,
    OptimizerSpec,
    ReductionSpec,
    VariableSpec,
    circuit_component,
)
from superconducting_circuits_runtime.catalog import parallel_lc_resonator
from superconducting_circuits_runtime.runtime import RuntimeContractError


def _objective() -> ObjectiveSpec:
    return ObjectiveSpec(
        cared_outputs={"mode": {"kind": "closed_mode_frequency_hz", "mode_index": 1}},
        residuals={
            "relative": {
                "op": "div",
                "args": [
                    {"op": "sub", "args": [{"output": "mode"}, {"const": 5.0e9}]},
                    {"const": 5.0e9},
                ],
            }
        },
        cost={"op": "sum_squares", "args": [{"output": "relative"}]},
    )


def _plan():
    plan = CircuitPlan("one_lc")
    resonator = plan.add(
        parallel_lc_resonator(id="resonator", capacitance_f=1.0e-12, inductance_h=1.0e-9)
    )
    return plan, resonator


def _sim(tmp_path: Path, run_id: str) -> CircuitSim:
    return CircuitSim(
        tmp_path,
        run_id,
        lifecycle_state="ACCEPTED",
        data_classification="project-internal",
    )


def test_sealed_direct_action_and_pure_analysis(tmp_path: Path) -> None:
    plan, resonator = _plan()
    drawing = plan.show()
    shown = drawing.circuit_workbench_plan
    assert shown["schema"] == "circuit-workbench-plan.v1"
    assert shown["schematic_intent"]["components"][0]["id"] == "resonator"
    assert [type(element).__name__ for element in drawing.elements] == ["GroundedLCResonator"]
    assert shown["canonical_sha256"] == plan.show().circuit_workbench_plan["canonical_sha256"]

    sim = _sim(tmp_path, "direct")
    sim.set_plan(plan)
    source = tmp_path / "sealed-input.json"
    source.write_text('{"sealed":true}', encoding="utf-8")
    with pytest.raises(RuntimeContractError):
        sim.bind_artifact(
            "missing_contract",
            {
                "path": str(source),
                "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
            },
        )
    sim.bind_artifact(
        "sealed_input",
        {
            "schema": "test-sealed-input.v1",
            "units": "dimensionless",
            "provenance": {"authority": "test-fixture"},
            "path": str(source),
            "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        },
    )
    sim.set_objective(_objective())
    sim.set_gates(
        [
            GateSpec(
                "accepted_gate",
                {"op": "less_equal", "args": [{"output": "mode"}, {"const": 1.0e9}]},
                "active",
                "human://accepted-gate",
            ),
            GateSpec(
                "inactive_diagnostic",
                {"op": "less_equal", "args": [{"output": "mode"}, {"const": 1.0e9}]},
                "inactive",
            ),
        ]
    )
    receipt = sim.evaluate()
    assert receipt["status"] == "REJECTED_BY_GATE"
    assert receipt["result"]["cared_outputs"]["mode"] > 0
    assert (
        receipt["result"]["validated_artifacts"]["sealed_input"]["source_sha256"]
        == hashlib.sha256(source.read_bytes()).hexdigest()
    )
    assert (tmp_path / "direct" / "circuit-workbench-run-request.v1.json").is_file()
    assert sim.analyze()["canonical_sha256"] == receipt["canonical_sha256"]
    assert receipt["lifecycle_state"] == "ACCEPTED"
    assert receipt["data_classification"] == "project-internal"

    hb_plan, hb_resonator = _plan()
    hb_plan.add_port("feed", hb_resonator.pin("signal"))
    hb = _sim(tmp_path, "hb")
    hb.set_plan(hb_plan)
    hb.set_objective(
        ObjectiveSpec(
            cared_outputs={
                "s11": {
                    "kind": "s_parameter",
                    "frequency_hz": 5.0e9,
                    "output_port": 1,
                    "input_port": 1,
                    "part": "abs",
                }
            },
            residuals={"identity": {"output": "s11"}},
            cost={"op": "sum_squares", "args": [{"output": "identity"}]},
        )
    )
    hb_receipt = hb.evaluate(backend="hb")
    assert hb_receipt["status"] == "PASS"
    assert 0.0 <= hb_receipt["result"]["cared_outputs"]["s11"] <= 1.0

    optimizer = _sim(tmp_path, "optimizer")
    optimizer.set_plan(plan)
    optimizer.set_objective(_objective())
    optimizer.set_variables(
        [
            VariableSpec(
                resonator.parameter("capacitance_f"),
                transform="log",
                lower=0.5e-12,
                upper=2.0e-12,
            )
        ]
    )
    optimizer.set_optimizer(
        OptimizerSpec(
            "cma_es",
            seed=4,
            human_authority="human://runtime-search",
            controls={"initial_sigma": 0.1, "maxiter": 1, "maxfevals": 3, "popsize": 3},
        )
    )
    optimized = optimizer.optimize()
    assert optimized["status"] == "PASS"
    assert optimized["result"]["candidate_count"] >= 3
    resumed = optimizer.optimize()
    assert resumed["result"]["candidate_count"] == optimized["result"]["candidate_count"]
    assert resumed["result"]["ledger_sha256"] == optimized["result"]["ledger_sha256"]

    parallel = _sim(tmp_path, "optimizer_parallel")
    parallel.set_plan(plan)
    parallel.set_objective(_objective())
    parallel.set_variables(
        [
            VariableSpec(
                resonator.parameter("capacitance_f"), transform="log", lower=0.5e-12, upper=2.0e-12
            )
        ]
    )
    parallel.set_optimizer(
        OptimizerSpec(
            "cma_es",
            seed=4,
            human_authority="human://runtime-search",
            resource_controls={"worker_count": 2},
            controls={"initial_sigma": 0.1, "maxiter": 1, "maxfevals": 3, "popsize": 3},
        )
    )
    parallel_result = parallel.optimize()
    serial_ledger = json.loads(Path(optimized["result"]["ledger_path"]).read_text(encoding="utf-8"))
    parallel_ledger = json.loads(
        Path(parallel_result["result"]["ledger_path"]).read_text(encoding="utf-8")
    )
    assert serial_ledger["entries"] == parallel_ledger["entries"]
    tampered = json.loads(Path(optimized["result"]["ledger_path"]).read_text(encoding="utf-8"))
    tampered["entries"][0]["outcome"]["cost"] = 0.0
    Path(optimized["result"]["ledger_path"]).write_text(json.dumps(tampered), encoding="utf-8")
    with pytest.raises(RuntimeContractError, match="Optimization ledger"):
        optimizer.optimize()


def test_invalid_contract_fails_before_julia(tmp_path: Path) -> None:
    plan, _ = _plan()
    sim = _sim(tmp_path, "bad")
    sim.set_plan(plan)
    with pytest.raises(RuntimeContractError):
        sim.set_objective(
            ObjectiveSpec(
                cared_outputs={"bad": {"kind": "not_a_runtime_output"}},
                residuals={"bad": {"output": "bad"}},
                cost={"op": "sum_squares", "args": [{"output": "bad"}]},
            )
        )


def test_composite_elaborates_internal_relations_and_complete_complement(tmp_path: Path) -> None:
    library = CircuitLibrary("test.composite", "1", "a" * 64)

    @circuit_component(
        type_id="test.parallel_lc_pair.v1",
        pins=("signal",),
        parameters=(),
        coordinates=({"name": "signal", "units": "node_flux", "role": "signal"},),
        lowerer="composite",
    )
    def pair(*, id: str):
        left = parallel_lc_resonator(id=f"{id}_left", capacitance_f=1.0e-12, inductance_h=1.0e-9)
        right = parallel_lc_resonator(id=f"{id}_right", capacitance_f=2.0e-12, inductance_h=1.0e-9)
        return library.component(
            "test.parallel_lc_pair.v1",
            id=id,
            parameters={},
            children=(left, right),
            pin_bindings={"signal": left.pin("signal")},
            coordinate_bindings={"signal": left.coord("signal")},
            internal_connections=((left.pin("signal"), right.pin("signal")),),
        )

    library.register(pair)
    plan = CircuitPlan("composite")
    component = plan.add(pair(id="pair"))
    sim = _sim(tmp_path, "reduced")
    sim.register_library(library)
    sim.set_plan(plan)
    sim.set_reduction(ReductionSpec((component.coord("signal"),)))
    sim.set_objective(
        ObjectiveSpec(
            cared_outputs={
                "schur": {
                    "kind": "schur_dynamic_stiffness_abs",
                    "frequency_hz": 5.0e9,
                    "row": 1,
                    "column": 1,
                }
            },
            residuals={"identity": {"output": "schur"}},
            cost={"op": "sum_squares", "args": [{"output": "identity"}]},
        )
    )
    receipt = sim.evaluate()
    assert receipt["status"] == "PASS"
    assert (
        receipt["plan_sha256"] == plan.show((library,)).circuit_workbench_plan["canonical_sha256"]
    )


def test_lossy_direct_ckg_and_failure_receipt(tmp_path: Path) -> None:
    plan = CircuitPlan("lossy")
    resonator = plan.add(
        parallel_lc_resonator(
            id="resonator",
            capacitance_f=1.0e-12,
            inductance_h=1.0e-9,
            conductance_s=1.0e-3,
        )
    )
    schur = _sim(tmp_path, "lossy_schur")
    schur.set_plan(plan)
    schur.set_reduction(ReductionSpec((resonator.coord("signal"),)))
    schur.set_objective(
        ObjectiveSpec(
            cared_outputs={
                "stiffness": {
                    "kind": "schur_dynamic_stiffness_abs",
                    "frequency_hz": 5.0e9,
                    "row": 1,
                    "column": 1,
                }
            },
            residuals={"identity": {"output": "stiffness"}},
            cost={"op": "sum_squares", "args": [{"output": "identity"}]},
        )
    )
    omega = 2 * math.pi * 5.0e9
    expected = abs(1 / 1.0e-9 - omega**2 * 1.0e-12 - 1j * omega * 1.0e-3)
    assert schur.evaluate()["result"]["cared_outputs"]["stiffness"] == pytest.approx(expected)

    closed = _sim(tmp_path, "lossy_closed")
    closed.set_plan(plan)
    closed.set_objective(_objective())
    with pytest.raises(RuntimeContractError, match="Julia action failed"):
        closed.evaluate()
    failure = closed.analyze()
    assert failure["status"] == "FAILED"
    assert failure["result"] is None


def test_runtime_sdist_installs_with_bundled_julia_and_schemdraw(tmp_path: Path) -> None:
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
            "from superconducting_circuits_runtime import CircuitPlan; "
            "from superconducting_circuits_runtime.catalog import parallel_lc_resonator; "
            "from superconducting_circuits_runtime.runtime import _JULIA_ROOT; "
            "plan = CircuitPlan('installed'); "
            "plan.add(parallel_lc_resonator(id='r', capacitance_f=1e-12, inductance_h=1e-9)); "
            "assert plan.show().elements; "
            "assert (_JULIA_ROOT / 'SuperconductingCircuitsCore/Project.toml').is_file(); "
            "assert (_JULIA_ROOT / 'SuperconductingCircuitsRunner/Project.toml').is_file()",
        ],
        check=True,
    )
