"""Tests for simulation domain models."""

import pytest
from core.simulation.domain.circuit import (
    SimulationResult,
    expand_circuit_definition,
    format_circuit_definition,
    format_expanded_circuit_definition,
    parse_circuit_definition_source,
)
from core.simulation.domain.compiler import compile_simulation_topology
from core.simulation.domain.validators import CircuitValidationCode, CircuitValidationError


def _repeat_enabled_circuit():
    return parse_circuit_definition_source(
        {
            "name": "IR Compile",
            "parameters": [
                {
                    "repeat": {
                        "count": 2,
                        "index": "cell",
                        "start": 1,
                        "series": {
                            "cg": {"base": 1.0, "step": 0.5},
                        },
                        "emit": [
                            {"name": "Cg${index}", "default": "${cg}", "unit": "fF"},
                        ],
                    }
                }
            ],
            "components": [
                {"name": "R1", "default": 50.0, "unit": "Ohm"},
                {
                    "repeat": {
                        "count": 2,
                        "index": "cell",
                        "symbols": {
                            "n": {"base": 1, "step": 1},
                            "n2": {"base": 2, "step": 1},
                        },
                        "emit": [
                            {"name": "L${n}_${n2}", "default": 10.0, "unit": "nH"},
                            {"name": "C${n2}_0", "value_ref": "Cg${n}", "unit": "fF"},
                        ],
                    }
                },
            ],
            "topology": [
                ("P1", "1", "0", 1),
                ("R1", "1", "0", "R1"),
                {
                    "repeat": {
                        "count": 2,
                        "index": "cell",
                        "symbols": {
                            "n": {"base": 1, "step": 1},
                            "n2": {"base": 2, "step": 1},
                        },
                        "emit": [
                            ("L${n}_${n2}", "${n}", "${n2}", "L${n}_${n2}"),
                            ("C${n2}_0", "${n2}", "0", "C${n2}_0"),
                        ],
                    }
                },
            ],
        }
    )


def test_circuit_definition_compiles_to_explicit_ir() -> None:
    circuit = _repeat_enabled_circuit()

    compiled_ir = circuit.to_ir()

    assert compiled_ir.circuit_name == "IR Compile"
    assert compiled_ir.layout_direction == "lr"
    assert compiled_ir.layout_profile == "generic"
    assert compiled_ir.available_port_indices == (1,)
    assert [element.name for element in compiled_ir.elements] == [
        "P1",
        "R1",
        "L1_2",
        "C2_0",
        "L2_3",
        "C3_0",
    ]
    assert compile_simulation_topology(
        compiled_ir,
        is_ground_node=lambda node: circuit.is_ground_node(node),
    ) == [
        ("P1", "1", "0", 1),
        ("R1", "1", "0", "R1"),
        ("L1_2", "1", "2", "L1_2"),
        ("C2_0", "2", "0", "C2_0"),
        ("L2_3", "2", "3", "L2_3"),
        ("C3_0", "3", "0", "C3_0"),
    ]


def test_format_helpers_preserve_source_and_show_expanded_result() -> None:
    circuit = _repeat_enabled_circuit()

    source_text = format_circuit_definition(circuit)
    expanded_text = format_expanded_circuit_definition(circuit)
    expanded = expand_circuit_definition(circuit)

    assert "'repeat':" in source_text
    assert "L1_2" not in source_text
    assert "L1_2" in expanded_text
    assert [parameter.name for parameter in expanded.parameters] == ["Cg1", "Cg2"]
    assert expanded.resolve_component_value("C2_0") == pytest.approx(1.0)
    assert expanded.resolve_component_value("C3_0") == pytest.approx(1.5)


def test_simulation_result_derives_s11_views() -> None:
    result = SimulationResult(
        frequencies_ghz=[5.0, 5.1],
        s11_real=[1.0, 0.0],
        s11_imag=[0.0, 1.0],
        port_indices=[1, 2],
        mode_indices=[(0,), (1,)],
        s_parameter_real={"S11": [1.0, 0.0], "S21": [0.5, 0.25]},
        s_parameter_imag={"S11": [0.0, 1.0], "S21": [0.0, -0.25]},
        s_parameter_mode_real={
            "om=0|op=1|im=0|ip=1": [1.0, 0.0],
            "om=0|op=2|im=0|ip=1": [0.5, 0.25],
            "om=1|op=2|im=0|ip=1": [1.5, 1.25],
        },
        s_parameter_mode_imag={
            "om=0|op=1|im=0|ip=1": [0.0, 1.0],
            "om=0|op=2|im=0|ip=1": [0.0, -0.25],
            "om=1|op=2|im=0|ip=1": [0.0, 0.5],
        },
        z_parameter_mode_real={"om=0|op=2|im=0|ip=2": [150.0, 160.0]},
        z_parameter_mode_imag={"om=0|op=2|im=0|ip=2": [0.0, 5.0]},
        y_parameter_mode_real={"om=0|op=2|im=0|ip=2": [0.006, 0.005]},
        y_parameter_mode_imag={"om=0|op=2|im=0|ip=2": [0.0, -0.001]},
        qe_parameter_mode={"om=1|op=2|im=0|ip=1": [0.8, 0.9]},
        qe_ideal_parameter_mode={"om=1|op=2|im=0|ip=1": [0.95, 0.97]},
        cm_parameter_mode={"om=1|op=2": [1.0, 1.0]},
    )

    assert result.s11_complex == [complex(1.0, 0.0), complex(0.0, 1.0)]
    assert result.available_port_indices == [1, 2]
    assert result.available_mode_indices == [(0,), (1,)]
    assert result.available_s_parameter_labels == ["S11", "S21"]
    assert result.available_mode_s_parameter_labels == [
        "om=0|op=1|im=0|ip=1",
        "om=0|op=2|im=0|ip=1",
        "om=1|op=2|im=0|ip=1",
    ]
    assert result.get_s_parameter_complex(2, 1) == [complex(0.5, 0.0), complex(0.25, -0.25)]
    assert result.get_mode_s_parameter_complex((1,), 2, (0,), 1) == [
        complex(1.5, 0.0),
        complex(1.25, 0.5),
    ]
    assert result.s11_magnitude == [1.0, 1.0]
    assert result.return_gain_linear == [1.0, 1.0]
    assert result.s11_db == [0.0, 0.0]
    assert result.return_gain_db == [0.0, 0.0]
    assert result.s11_phase_deg == [0.0, 90.0]
    assert result.get_gain_linear(2, 1) == pytest.approx([0.25, 0.125])
    assert result.get_mode_gain_linear((1,), 2, (0,), 1) == pytest.approx([2.25, 1.8125])
    assert result.get_mode_z_parameter_complex((0,), 2, (0,), 2) == [
        complex(150.0, 0.0),
        complex(160.0, 5.0),
    ]
    assert result.get_mode_y_parameter_complex((0,), 2, (0,), 2) == [
        complex(0.006, 0.0),
        complex(0.005, -0.001),
    ]
    assert result.get_mode_qe((1,), 2, (0,), 1) == [0.8, 0.9]
    assert result.get_mode_qe_ideal((1,), 2, (0,), 1) == [0.95, 0.97]
    assert result.get_mode_cm((1,), 2) == [1.0, 1.0]


def test_simulation_result_converts_s11_to_impedance_and_admittance() -> None:
    result = SimulationResult(
        frequencies_ghz=[5.0],
        s11_real=[0.0],
        s11_imag=[0.0],
    )

    impedance = result.calculate_input_impedance_ohm(reference_impedance_ohm=50.0)
    admittance = result.calculate_input_admittance_s(reference_impedance_ohm=50.0)

    assert impedance == [complex(50.0, 0.0)]
    assert admittance == [complex(0.02, 0.0)]


def test_simulation_result_impedance_uses_selected_reflection_port() -> None:
    result = SimulationResult(
        frequencies_ghz=[5.0],
        s11_real=[0.0],
        s11_imag=[0.0],
        port_indices=[1, 2],
        s_parameter_real={"S11": [0.0], "S22": [0.5]},
        s_parameter_imag={"S11": [0.0], "S22": [0.0]},
        z_parameter_mode_real={"om=0|op=2|im=0|ip=2": [120.0]},
        z_parameter_mode_imag={"om=0|op=2|im=0|ip=2": [1.0]},
    )

    impedance_port_2 = result.calculate_input_impedance_ohm(
        reference_impedance_ohm=50.0,
        port=2,
    )

    assert impedance_port_2 == [complex(120.0, 1.0)]


def test_parse_circuit_rejects_gnd_alias_with_error_code() -> None:
    with pytest.raises(CircuitValidationError) as exc_info:
        parse_circuit_definition_source(
            {
                "name": "Invalid Ground",
                "components": [{"name": "R1", "default": 50.0, "unit": "Ohm"}],
                "topology": [("R1", "1", "gnd", "R1")],
            }
        )

    assert exc_info.value.code is CircuitValidationCode.UNSUPPORTED_GROUND_ALIAS


def test_parse_circuit_rejects_duplicate_port_index_with_error_code() -> None:
    with pytest.raises(CircuitValidationError) as exc_info:
        parse_circuit_definition_source(
            {
                "name": "Duplicate Port",
                "components": [{"name": "R1", "default": 50.0, "unit": "Ohm"}],
                "topology": [
                    ("P1", "1", "0", 1),
                    ("P2", "2", "0", 1),
                    ("R1", "1", "0", "R1"),
                ],
            }
        )

    assert exc_info.value.code is CircuitValidationCode.DUPLICATE_PORT_INDEX
