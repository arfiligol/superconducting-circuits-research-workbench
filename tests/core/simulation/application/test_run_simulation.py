"""Tests for simulation sweep helpers in application layer."""

from __future__ import annotations

import core.simulation.application.run_simulation as run_sim_app
import pytest
from core.simulation.domain.circuit import (
    FrequencyRange,
    SimulationConfig,
    SimulationResult,
    parse_circuit_definition_source,
)


def _sample_circuit():
    return parse_circuit_definition_source(
        {
            "name": "SweepableCircuit",
            "parameters": [
                {"name": "Lj", "default": 1000.0, "unit": "pH"},
                {"name": "Cc", "default": 120.0, "unit": "fF"},
            ],
            "components": [
                {"name": "R50", "default": 50.0, "unit": "Ohm"},
                {"name": "Lj1", "value_ref": "Lj", "unit": "pH"},
                {"name": "C1", "value_ref": "Cc", "unit": "fF"},
            ],
            "topology": [
                ("P1", "1", "0", 1),
                ("R1", "1", "0", "R50"),
                ("Lj1", "1", "2", "Lj1"),
                ("C1", "2", "0", "C1"),
            ],
        }
    )


def test_list_simulation_sweep_targets_uses_component_value_refs() -> None:
    targets = run_sim_app.list_simulation_sweep_targets(_sample_circuit())

    assert [target.value_ref for target in targets] == ["Cc", "Lj"]
    assert {target.value_ref: target.unit for target in targets} == {"Cc": "fF", "Lj": "pH"}


def test_list_simulation_sweep_targets_includes_source_targets_from_config() -> None:
    circuit = _sample_circuit()
    config = SimulationConfig(
        pump_freq_ghz=4.75,
        pump_current_amp=1e-6,
        pump_port=1,
        sources=[
            {"pump_freq_ghz": 4.75, "port": 1, "current_amp": 1e-6, "mode_components": (1,)},
            {"pump_freq_ghz": 9.5, "port": 2, "current_amp": 2e-6, "mode_components": (0, 1)},
        ],
    )

    targets = run_sim_app.list_simulation_sweep_targets(circuit, config=config)
    target_units = {target.value_ref: target.unit for target in targets}

    assert target_units["Lj"] == "pH"
    assert target_units["sources[1].current_amp"] == "A"
    assert target_units["sources[2].pump_freq_ghz"] == "GHz"


def test_build_simulation_sweep_plan_single_axis() -> None:
    circuit = _sample_circuit()
    plan = run_sim_app.build_simulation_sweep_plan(
        circuit=circuit,
        axes=[
            run_sim_app.SimulationSweepAxis(
                target_value_ref="Lj",
                values=(900.0, 1000.0, 1100.0),
                unit="pH",
            )
        ],
    )

    assert plan.dimension == 1
    assert plan.point_count == 3
    assert plan.points[0].axis_indices == (0,)
    assert plan.points[2].value_ref_overrides == {"Lj": 1100.0}


def test_build_simulation_sweep_plan_multi_axis_cartesian() -> None:
    circuit = _sample_circuit()
    config = SimulationConfig(
        pump_freq_ghz=4.75,
        pump_current_amp=1e-6,
        pump_port=1,
        sources=[
            {"pump_freq_ghz": 4.75, "port": 1, "current_amp": 1e-6, "mode_components": (1,)},
        ],
    )
    plan = run_sim_app.build_simulation_sweep_plan(
        circuit=circuit,
        config=config,
        axes=[
            run_sim_app.SimulationSweepAxis(
                target_value_ref="Lj",
                values=(900.0, 1100.0),
                unit="pH",
            ),
            run_sim_app.SimulationSweepAxis(
                target_value_ref="sources[1].current_amp",
                values=(1.0e-6, 1.2e-6, 1.4e-6),
                unit="A",
            ),
        ],
    )

    assert plan.dimension == 2
    assert plan.point_count == 6
    assert plan.points[0].axis_indices == (0, 0)
    assert plan.points[-1].axis_indices == (1, 2)
    assert plan.points[-1].value_ref_overrides == {
        "Lj": pytest.approx(1100.0),
        "sources[1].current_amp": pytest.approx(1.4e-6),
    }


def test_apply_simulation_sweep_overrides_updates_resolved_values() -> None:
    circuit = _sample_circuit()

    swept = run_sim_app.apply_simulation_sweep_overrides(
        circuit=circuit,
        value_ref_overrides={"Lj": 1250.0},
    )

    assert swept.resolve_component_value("Lj1") == 1250.0
    assert swept.resolve_component_value("C1") == 120.0


def test_apply_simulation_sweep_config_overrides_updates_selected_source_field() -> None:
    config = SimulationConfig(
        pump_freq_ghz=4.75,
        pump_current_amp=1e-6,
        pump_port=1,
        sources=[
            {"pump_freq_ghz": 4.75, "port": 1, "current_amp": 1e-6, "mode_components": (1,)},
            {"pump_freq_ghz": 9.5, "port": 2, "current_amp": 2e-6, "mode_components": (0, 1)},
        ],
    )

    swept_config = run_sim_app.apply_simulation_sweep_config_overrides(
        config=config,
        target_overrides={"sources[2].current_amp": 3.2e-6},
    )

    assert swept_config.sources is not None
    assert swept_config.sources[0].current_amp == pytest.approx(1e-6)
    assert swept_config.sources[1].current_amp == pytest.approx(3.2e-6)


def test_simulation_sweep_payload_roundtrip_preserves_points() -> None:
    sample_result = SimulationResult(
        frequencies_ghz=[4.0, 5.0],
        s11_real=[0.0, 0.1],
        s11_imag=[0.0, -0.1],
    )
    run_payload = run_sim_app.SimulationSweepRun(
        axes=(
            run_sim_app.SimulationSweepAxis(
                target_value_ref="Lj",
                values=(900.0, 1000.0),
                unit="pH",
            ),
        ),
        points=(
            run_sim_app.SimulationSweepPointResult(
                point_index=0,
                axis_indices=(0,),
                axis_values={"Lj": 900.0},
                result=sample_result,
            ),
            run_sim_app.SimulationSweepPointResult(
                point_index=1,
                axis_indices=(1,),
                axis_values={"Lj": 1000.0},
                result=sample_result,
            ),
        ),
    )

    payload = run_sim_app.simulation_sweep_run_to_payload(run_payload)
    restored = run_sim_app.simulation_sweep_run_from_payload(payload)

    assert restored.dimension == 1
    assert restored.point_count == 2
    assert restored.points[1].axis_values == {"Lj": 1000.0}
    assert restored.representative_result.frequencies_ghz == [4.0, 5.0]


def test_simulation_sweep_payload_roundtrip_preserves_multi_axis_payload() -> None:
    sample_result = SimulationResult(
        frequencies_ghz=[4.0, 5.0],
        s11_real=[0.0, 0.1],
        s11_imag=[0.0, -0.1],
    )
    run_payload = run_sim_app.SimulationSweepRun(
        axes=(
            run_sim_app.SimulationSweepAxis(
                target_value_ref="Lj",
                values=(900.0, 1100.0),
                unit="pH",
            ),
            run_sim_app.SimulationSweepAxis(
                target_value_ref="sources[1].current_amp",
                values=(1.0e-6, 1.4e-6),
                unit="A",
            ),
        ),
        points=(
            run_sim_app.SimulationSweepPointResult(
                point_index=0,
                axis_indices=(0, 0),
                axis_values={"Lj": 900.0, "sources[1].current_amp": 1.0e-6},
                result=sample_result,
            ),
            run_sim_app.SimulationSweepPointResult(
                point_index=1,
                axis_indices=(0, 1),
                axis_values={"Lj": 900.0, "sources[1].current_amp": 1.4e-6},
                result=sample_result,
            ),
            run_sim_app.SimulationSweepPointResult(
                point_index=2,
                axis_indices=(1, 0),
                axis_values={"Lj": 1100.0, "sources[1].current_amp": 1.0e-6},
                result=sample_result,
            ),
            run_sim_app.SimulationSweepPointResult(
                point_index=3,
                axis_indices=(1, 1),
                axis_values={"Lj": 1100.0, "sources[1].current_amp": 1.4e-6},
                result=sample_result,
            ),
        ),
    )

    payload = run_sim_app.simulation_sweep_run_to_payload(run_payload)
    restored = run_sim_app.simulation_sweep_run_from_payload(payload)

    assert restored.dimension == 2
    assert restored.point_count == 4
    assert restored.points[3].axis_indices == (1, 1)
    assert restored.points[3].axis_values["Lj"] == pytest.approx(1100.0)
    assert restored.points[3].axis_values["sources[1].current_amp"] == pytest.approx(1.4e-6)


def test_simulation_sweep_payload_legacy_single_axis_shape_decodes() -> None:
    sample_result = SimulationResult(
        frequencies_ghz=[4.0, 5.0],
        s11_real=[0.0, 0.1],
        s11_imag=[0.0, -0.1],
    )
    payload = {
        "run_kind": "parameter_sweep",
        "target_value_ref": "Lj",
        "unit": "pH",
        "values": [900.0, 1100.0],
        "point_results": [
            {
                "point_index": 0,
                "axis_index": 0,
                "axis_value": 900.0,
                "payload": sample_result.model_dump(mode="json"),
            },
            {
                "point_index": 1,
                "axis_index": 1,
                "axis_value": 1100.0,
                "payload": sample_result.model_dump(mode="json"),
            },
        ],
    }

    restored = run_sim_app.simulation_sweep_run_from_payload(payload)

    assert restored.dimension == 1
    assert restored.point_count == 2
    assert restored.axes[0].target_value_ref == "Lj"
    assert restored.points[1].axis_indices == (1,)
    assert restored.points[1].axis_values["Lj"] == pytest.approx(1100.0)


def test_run_parameter_sweep_executes_each_point(monkeypatch) -> None:
    circuit = _sample_circuit()
    plan = run_sim_app.build_simulation_sweep_plan(
        circuit=circuit,
        axes=[
            run_sim_app.SimulationSweepAxis(
                target_value_ref="Lj",
                values=(900.0, 1100.0),
                unit="pH",
            )
        ],
    )

    calls: list[float] = []

    class _StubSimulator:
        def run_hbsolve(self, circuit_for_run, freq_range, config):
            calls.append(circuit_for_run.resolve_component_value("Lj1"))
            return SimulationResult(
                frequencies_ghz=[float(freq_range.start_ghz), float(freq_range.stop_ghz)],
                s11_real=[0.0, 0.0],
                s11_imag=[0.0, 0.0],
            )

    monkeypatch.setattr(run_sim_app, "JuliaSimulator", _StubSimulator)

    result = run_sim_app.run_parameter_sweep(
        circuit=circuit,
        freq_range=FrequencyRange(start_ghz=4.0, stop_ghz=5.0, points=11),
        config=SimulationConfig(),
        plan=plan,
    )

    assert calls == [900.0, 1100.0]
    assert result.point_count == 2
    assert result.representative_result.frequencies_ghz == [4.0, 5.0]


def test_run_parameter_sweep_applies_source_target_override(monkeypatch) -> None:
    circuit = _sample_circuit()
    config = SimulationConfig(
        pump_freq_ghz=4.75,
        pump_current_amp=1.0e-6,
        pump_port=1,
        sources=[
            {
                "pump_freq_ghz": 4.75,
                "port": 1,
                "current_amp": 1.0e-6,
                "mode_components": (1,),
            }
        ],
    )
    plan = run_sim_app.build_simulation_sweep_plan(
        circuit=circuit,
        config=config,
        axes=[
            run_sim_app.SimulationSweepAxis(
                target_value_ref="sources[1].current_amp",
                values=(1.0e-6, 1.5e-6),
                unit="A",
            )
        ],
    )

    calls: list[float] = []

    class _StubSimulator:
        def run_hbsolve(self, circuit_for_run, freq_range, config_for_run):
            assert config_for_run.sources is not None
            calls.append(float(config_for_run.sources[0].current_amp))
            return SimulationResult(
                frequencies_ghz=[float(freq_range.start_ghz), float(freq_range.stop_ghz)],
                s11_real=[0.0, 0.0],
                s11_imag=[0.0, 0.0],
            )

    monkeypatch.setattr(run_sim_app, "JuliaSimulator", _StubSimulator)
    result = run_sim_app.run_parameter_sweep(
        circuit=circuit,
        freq_range=FrequencyRange(start_ghz=4.0, stop_ghz=5.0, points=11),
        config=config,
        plan=plan,
    )

    assert calls == [1.0e-6, 1.5e-6]
    assert result.point_count == 2
