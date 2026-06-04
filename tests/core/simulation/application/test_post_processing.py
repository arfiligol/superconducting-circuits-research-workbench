"""Tests for port-level simulation post-processing helpers."""

from __future__ import annotations

import numpy as np
from core.simulation.application.post_processing import (
    apply_coordinate_transform,
    apply_shunt_termination_compensation,
    build_common_differential_transform,
    build_port_y_sweep,
    compensate_simulation_result_port_terminations,
    filtered_modes,
    infer_port_termination_resistance_ohm,
    kron_reduce,
)
from core.simulation.domain.circuit import SimulationResult, parse_circuit_definition_source


def _mode_label(mode: tuple[int, ...], op: int, ip: int) -> str:
    token = SimulationResult.mode_token(mode)
    return f"om={token}|op={op}|im={token}|ip={ip}"


def _base_result_with_y() -> SimulationResult:
    mode = (0,)
    y_real = {
        _mode_label(mode, 1, 1): [2.0, 2.0],
        _mode_label(mode, 1, 2): [-1.0, -1.0],
        _mode_label(mode, 2, 1): [-1.0, -1.0],
        _mode_label(mode, 2, 2): [2.0, 2.0],
    }
    y_imag = {label: [0.0, 0.0] for label in y_real}
    return SimulationResult(
        frequencies_ghz=[5.0, 6.0],
        s11_real=[0.0, 0.0],
        s11_imag=[0.0, 0.0],
        port_indices=[1, 2],
        mode_indices=[(0,), (1,)],
        y_parameter_mode_real=y_real,
        y_parameter_mode_imag=y_imag,
    )


def test_filtered_modes_supports_base_and_sideband() -> None:
    result = _base_result_with_y()

    assert filtered_modes(result, "base") == [(0,)]
    assert filtered_modes(result, "sideband") == [(1,)]
    assert filtered_modes(result, "all") == [(0,), (1,)]


def test_build_port_y_sweep_reads_native_y_matrix() -> None:
    result = _base_result_with_y()

    sweep = build_port_y_sweep(result=result, mode=(0,))

    assert sweep.source_kind == "y"
    assert sweep.labels == ("1", "2")
    assert np.allclose(sweep.y_matrices[0], np.array([[2.0, -1.0], [-1.0, 2.0]]))


def test_build_port_y_sweep_falls_back_to_z_then_inverse() -> None:
    mode = (0,)
    z_real = {
        _mode_label(mode, 1, 1): [50.0, 50.0],
        _mode_label(mode, 1, 2): [0.0, 0.0],
        _mode_label(mode, 2, 1): [0.0, 0.0],
        _mode_label(mode, 2, 2): [25.0, 25.0],
    }
    z_imag = {label: [0.0, 0.0] for label in z_real}
    result = SimulationResult(
        frequencies_ghz=[5.0, 6.0],
        s11_real=[0.0, 0.0],
        s11_imag=[0.0, 0.0],
        port_indices=[1, 2],
        mode_indices=[mode],
        z_parameter_mode_real=z_real,
        z_parameter_mode_imag=z_imag,
    )

    sweep = build_port_y_sweep(result=result, mode=mode)

    assert sweep.source_kind == "z"
    assert np.allclose(sweep.y_matrices[0], np.array([[0.02, 0.0], [0.0, 0.04]]))


def test_build_port_y_sweep_falls_back_to_s_then_converts() -> None:
    mode = (0,)
    s_real = {
        _mode_label(mode, 1, 1): [0.0, 0.0],
        _mode_label(mode, 1, 2): [0.0, 0.0],
        _mode_label(mode, 2, 1): [0.0, 0.0],
        _mode_label(mode, 2, 2): [0.0, 0.0],
    }
    s_imag = {label: [0.0, 0.0] for label in s_real}
    result = SimulationResult(
        frequencies_ghz=[5.0, 6.0],
        s11_real=[0.0, 0.0],
        s11_imag=[0.0, 0.0],
        port_indices=[1, 2],
        mode_indices=[mode],
        s_parameter_mode_real=s_real,
        s_parameter_mode_imag=s_imag,
    )

    sweep = build_port_y_sweep(result=result, mode=mode, reference_impedance_ohm=50.0)

    assert sweep.source_kind == "s"
    assert np.allclose(sweep.y_matrices[0], np.array([[0.02, 0.0], [0.0, 0.02]]))


def test_coordinate_transform_and_kron_reduction_pipeline() -> None:
    result = _base_result_with_y()
    sweep = build_port_y_sweep(result=result, mode=(0,))

    transform = build_common_differential_transform(
        dimension=2,
        first_index=0,
        second_index=1,
        alpha=0.5,
        beta=0.5,
    )
    transformed = apply_coordinate_transform(
        sweep,
        transform_matrix=transform,
        labels=("cm(1,2)", "dm(1,2)"),
    )
    reduced = kron_reduce(transformed, keep_indices=[1])

    assert transformed.labels == ("cm(1,2)", "dm(1,2)")
    assert reduced.labels == ("dm(1,2)",)

    expected_first = transformed.y_matrices[0]
    y_dd = expected_first[1:2, 1:2]
    y_do = expected_first[1:2, 0:1]
    y_od = expected_first[0:1, 1:2]
    y_oo = expected_first[0:1, 0:1]
    expected_reduced = y_dd - (y_do @ np.linalg.solve(y_oo, y_od))
    assert np.allclose(reduced.y_matrices[0], expected_reduced)


def test_infer_port_termination_resistance_from_schema_shunts() -> None:
    circuit = parse_circuit_definition_source(
        {
            "name": "Termination infer",
            "components": [
                {"name": "R50", "default": 50.0, "unit": "Ohm"},
                {"name": "R100", "default": 0.1, "unit": "kOhm"},
            ],
            "topology": [
                ("P1", "1", "0", 1),
                ("P2", "2", "0", 2),
                ("R1", "1", "0", "R50"),
                ("R2", "2", "0", "R100"),
            ],
        }
    )

    inferred = infer_port_termination_resistance_ohm(circuit)

    assert inferred.resistance_ohm_by_port == {1: 50.0, 2: 100.0}
    assert inferred.source_by_port == {1: "schema_infer", 2: "schema_infer"}
    assert inferred.warning_by_port == {}


def test_infer_port_termination_resistance_reports_fallback_warnings() -> None:
    circuit = parse_circuit_definition_source(
        {
            "name": "Termination fallback",
            "components": [
                {"name": "R50", "default": 50.0, "unit": "Ohm"},
                {"name": "R60", "default": 60.0, "unit": "Ohm"},
            ],
            "topology": [
                ("P1", "1", "0", 1),
                ("P2", "2", "0", 2),
                ("R1a", "1", "0", "R50"),
                ("R1b", "1", "0", "R60"),
            ],
        }
    )

    inferred = infer_port_termination_resistance_ohm(circuit)

    assert inferred.source_by_port[1] == "fallback_default_50"
    assert inferred.source_by_port[2] == "fallback_default_50"
    assert "multiple shunt resistors" in inferred.warning_by_port[1]
    assert "no shunt resistor to ground" in inferred.warning_by_port[2]
    assert inferred.resistance_ohm_by_port[1] == 50.0
    assert inferred.resistance_ohm_by_port[2] == 50.0


def test_apply_shunt_termination_compensation_subtracts_selected_port_conductance() -> None:
    base = _base_result_with_y()
    sweep = build_port_y_sweep(result=base, mode=(0,))

    compensated = apply_shunt_termination_compensation(
        sweep,
        resistance_ohm_by_port={1: 50.0, 2: 100.0},
    )

    assert np.allclose(compensated.y_matrices[0], np.array([[1.98, -1.0], [-1.0, 1.99]]))


def test_compensate_simulation_result_port_terminations_updates_mode_aware_y() -> None:
    base = _base_result_with_y()
    compensated = compensate_simulation_result_port_terminations(
        base,
        resistance_ohm_by_port={1: 50.0},
        reference_impedance_ohm=50.0,
    )

    label = _mode_label((0,), 1, 1)
    assert compensated.y_parameter_mode_real[label] == [1.98, 1.98]
    assert compensated.available_mode_indices == [(0,), (1,)]
