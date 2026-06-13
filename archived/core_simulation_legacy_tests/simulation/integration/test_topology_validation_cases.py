"""Optional Julia-backed integration tests for representative topology cases."""

from __future__ import annotations

import os

import pytest
from core.simulation.application.run_simulation import run_simulation
from core.simulation.domain.circuit import (
    DriveSourceConfig,
    FrequencyRange,
    SimulationConfig,
    parse_circuit_definition_source,
)


def _legacy_circuit(*, name: str, parameters: dict, topology: list[tuple]):
    components: list[dict[str, object]] = []
    seen_component_refs: set[str] = set()
    normalized_topology: list[tuple[str, str, str, str | int]] = []

    for element_name, node1, node2, value_ref in topology:
        element_name_text = str(element_name)
        if element_name_text.lower().startswith("p"):
            normalized_topology.append((element_name_text, str(node1), str(node2), int(value_ref)))
            continue

        component_ref = str(value_ref)
        if component_ref not in seen_component_refs:
            parameter = parameters[component_ref]
            components.append(
                {
                    "name": component_ref,
                    "default": float(parameter["default"]),
                    "unit": str(parameter["unit"]),
                }
            )
            seen_component_refs.add(component_ref)
        normalized_topology.append((element_name_text, str(node1), str(node2), component_ref))

    return parse_circuit_definition_source(
        {
            "name": name,
            "components": components,
            "topology": normalized_topology,
        }
    )


_RUN_JULIA_INTEGRATION = os.getenv("RUN_JULIA_SIM_TESTS") == "1"


pytestmark = pytest.mark.skipif(
    not _RUN_JULIA_INTEGRATION,
    reason="Set RUN_JULIA_SIM_TESTS=1 to run Julia-backed topology integration tests.",
)


def test_series_lc_with_port_shunt_resistor_runs_successfully():
    circuit = _legacy_circuit(
        name="Series LC with R50",
        parameters={
            "R50": {"default": 50.0, "unit": "Ohm"},
            "L1": {"default": 10.0, "unit": "nH"},
            "C1": {"default": 1.0, "unit": "pF"},
        },
        topology=[
            ("P1", "1", "0", 1),
            ("R50", "1", "0", "R50"),
            ("L1", "1", "2", "L1"),
            ("C1", "2", "0", "C1"),
        ],
    )

    # 1-5 GHz is stable in current solver defaults; wider sweep may hit singular regions.
    result = run_simulation(circuit, FrequencyRange(start_ghz=1.0, stop_ghz=5.0, points=301))
    assert len(result.frequencies_ghz) == 301


def test_two_stage_ladder_runs_successfully():
    circuit = _legacy_circuit(
        name="Two-stage ladder",
        parameters={
            "R50": {"default": 50.0, "unit": "Ohm"},
            "L1": {"default": 8.0, "unit": "nH"},
            "C1": {"default": 0.8, "unit": "pF"},
            "L2": {"default": 12.0, "unit": "nH"},
            "C2": {"default": 0.6, "unit": "pF"},
        },
        topology=[
            ("P1", "1", "0", 1),
            ("R50", "1", "0", "R50"),
            ("L1", "1", "2", "L1"),
            ("C1", "2", "0", "C1"),
            ("L2", "2", "3", "L2"),
            ("C2", "3", "0", "C2"),
        ],
    )

    result = run_simulation(circuit, FrequencyRange(start_ghz=1.0, stop_ghz=5.0, points=301))
    assert len(result.s11_real) == 301


def test_parallel_single_node_rlc_maps_to_numerical_error():
    circuit = _legacy_circuit(
        name="Parallel RLC at one node",
        parameters={
            "R1": {"default": 1.0, "unit": "Ohm"},
            "L1": {"default": 10.0, "unit": "nH"},
            "C1": {"default": 1.0, "unit": "pF"},
        },
        topology=[
            ("P1", "1", "0", 1),
            ("R1", "1", "0", "R1"),
            ("L1", "1", "0", "L1"),
            ("C1", "1", "0", "C1"),
        ],
    )

    with pytest.raises(RuntimeError, match="SimulationNumericalError:"):
        run_simulation(circuit, FrequencyRange(start_ghz=1.0, stop_ghz=10.0, points=1001))


def test_multi_source_multi_pump_configuration_runs_successfully():
    circuit = _legacy_circuit(
        name="Two-pump smoke case",
        parameters={
            "R1": {"default": 50.0, "unit": "Ohm"},
            "Lj": {"default": 1000.0, "unit": "pH"},
            "Cc": {"default": 100.0, "unit": "fF"},
            "Cj": {"default": 1000.0, "unit": "fF"},
        },
        topology=[
            ("P1", "1", "0", 1),
            ("R1", "1", "0", "R1"),
            ("C1", "1", "2", "Cc"),
            ("Lj1", "2", "0", "Lj"),
            ("C2", "2", "0", "Cj"),
        ],
    )

    ip = 0.00565e-6 * 1.7
    config = SimulationConfig(
        n_modulation_harmonics=8,
        n_pump_harmonics=8,
        include_dc=False,
        enable_three_wave_mixing=False,
        enable_four_wave_mixing=True,
        sources=[
            DriveSourceConfig(pump_freq_ghz=4.65001, port=1, current_amp=ip),
            DriveSourceConfig(pump_freq_ghz=4.85001, port=1, current_amp=ip),
        ],
    )

    result = run_simulation(
        circuit,
        FrequencyRange(start_ghz=4.5, stop_ghz=5.0, points=201),
        config,
    )
    assert len(result.frequencies_ghz) == 201
