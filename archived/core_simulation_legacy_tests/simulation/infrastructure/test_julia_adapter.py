"""Tests for Julia adapter validation and error mapping."""

import pytest
from core.simulation.domain.circuit import (
    DriveSourceConfig,
    FrequencyRange,
    SimulationConfig,
    parse_circuit_definition_source,
)
from core.simulation.infrastructure.julia_adapter import JuliaSimulator


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


class _FakeJuliaMain:
    def __init__(self, behavior):
        self._behavior = behavior

    def run_custom_simulation(self, *args):
        return self._behavior(*args)


def _build_simulator(fake_behavior) -> JuliaSimulator:
    simulator = JuliaSimulator()
    simulator._initialized = True
    simulator._jl = _FakeJuliaMain(fake_behavior)
    return simulator


def _default_config() -> SimulationConfig:
    return SimulationConfig(pump_freq_ghz=5.0, n_modulation_harmonics=10, n_pump_harmonics=20)


def test_run_hbsolve_raises_input_error_when_port_has_no_shunt_resistor():
    circuit = _legacy_circuit(
        name="no-port-r",
        parameters={
            "L1": {"default": 10.0, "unit": "nH"},
            "C1": {"default": 1.0, "unit": "pF"},
        },
        topology=[("P1", "1", "0", 1), ("L1", "1", "2", "L1"), ("C1", "2", "0", "C1")],
    )
    simulator = _build_simulator(lambda *_: pytest.fail("Julia should not be called"))

    with pytest.raises(
        ValueError,
        match="SimulationInputError: each port node needs a shunt resistor",
    ):
        simulator.run_hbsolve(
            circuit,
            FrequencyRange(start_ghz=1.0, stop_ghz=5.0, points=101),
            _default_config(),
        )


def test_run_hbsolve_maps_singular_exception_to_numerical_error():
    circuit = _legacy_circuit(
        name="singular",
        parameters={
            "R50": {"default": 50.0, "unit": "Ohm"},
            "L1": {"default": 10.0, "unit": "nH"},
            "C1": {"default": 1.0, "unit": "pF"},
        },
        topology=[
            ("P1", "1", "0", 1),
            ("R50", "1", "0", "R50"),
            ("L1", "1", "0", "L1"),
            ("C1", "1", "0", "C1"),
        ],
    )

    def _raise_singular(*_):
        raise Exception(
            "TaskFailedException nested task error: LinearAlgebra.SingularException(11)"
        )

    simulator = _build_simulator(_raise_singular)

    with pytest.raises(
        RuntimeError,
        match="SimulationNumericalError: solver matrix became singular",
    ):
        simulator.run_hbsolve(
            circuit,
            FrequencyRange(start_ghz=1.0, stop_ghz=10.0, points=1001),
            _default_config(),
        )


def test_run_hbsolve_raises_input_error_for_unsupported_unit():
    circuit = _legacy_circuit(
        name="bad-unit",
        parameters={"R1": {"default": 50.0, "unit": "ohms"}},
        topology=[("P1", "1", "0", 1), ("R1", "1", "0", "R1")],
    )
    simulator = _build_simulator(lambda *_: pytest.fail("Julia should not be called"))

    with pytest.raises(ValueError, match="SimulationInputError: unsupported unit"):
        simulator.run_hbsolve(
            circuit,
            FrequencyRange(start_ghz=1.0, stop_ghz=3.0, points=51),
            _default_config(),
        )


def test_run_hbsolve_returns_result_when_julia_succeeds():
    circuit = _legacy_circuit(
        name="ok",
        parameters={"R50": {"default": 50.0, "unit": "Ohm"}},
        topology=[("P1", "1", "0", 1), ("R50", "1", "0", "R50")],
    )

    def _ok(*_):
        return {
            "frequencies_ghz": [1.0, 2.0],
            "s11_real": [0.1, 0.2],
            "s11_imag": [-0.1, -0.2],
            "port_indices": [1, 2],
            "mode_indices": [(0,), (1,)],
            "s_parameter_real": {"S11": [0.1, 0.2], "S21": [0.3, 0.4]},
            "s_parameter_imag": {"S11": [-0.1, -0.2], "S21": [0.0, 0.1]},
            "s_parameter_mode_real": {
                "om=0|op=1|im=0|ip=1": [0.1, 0.2],
                "om=1|op=2|im=0|ip=1": [0.5, 0.6],
            },
            "s_parameter_mode_imag": {
                "om=0|op=1|im=0|ip=1": [-0.1, -0.2],
                "om=1|op=2|im=0|ip=1": [0.0, 0.1],
            },
            "z_parameter_mode_real": {"om=0|op=1|im=0|ip=1": [50.0, 51.0]},
            "z_parameter_mode_imag": {"om=0|op=1|im=0|ip=1": [0.0, 1.0]},
            "y_parameter_mode_real": {"om=0|op=1|im=0|ip=1": [0.02, 0.03]},
            "y_parameter_mode_imag": {"om=0|op=1|im=0|ip=1": [0.0, 0.0]},
            "qe_parameter_mode": {"om=1|op=2|im=0|ip=1": [0.8, 0.85]},
            "qe_ideal_parameter_mode": {"om=1|op=2|im=0|ip=1": [0.9, 0.95]},
            "cm_parameter_mode": {"om=1|op=2": [1.0, 1.0]},
        }

    simulator = _build_simulator(_ok)
    result = simulator.run_hbsolve(
        circuit,
        FrequencyRange(start_ghz=1.0, stop_ghz=2.0, points=2),
        _default_config(),
    )

    assert result.frequencies_ghz == [1.0, 2.0]
    assert result.s11_real == [0.1, 0.2]
    assert result.s11_imag == [-0.1, -0.2]
    assert result.available_port_indices == [1, 2]
    assert result.available_mode_indices == [(0,), (1,)]
    assert result.get_s_parameter_real(2, 1) == [0.3, 0.4]
    assert result.get_s_parameter_imag(2, 1) == [0.0, 0.1]
    assert result.get_mode_s_parameter_real((1,), 2, (0,), 1) == [0.5, 0.6]
    assert result.get_mode_qe((1,), 2, (0,), 1) == [0.8, 0.85]
    assert result.get_mode_cm((1,), 2) == [1.0, 1.0]


def test_run_hbsolve_rejects_source_port_not_declared_in_schema():
    circuit = _legacy_circuit(
        name="port-mismatch",
        parameters={"R50": {"default": 50.0, "unit": "Ohm"}},
        topology=[("P1", "1", "0", 1), ("R50", "1", "0", "R50")],
    )
    simulator = _build_simulator(lambda *_: pytest.fail("Julia should not be called"))
    config = SimulationConfig(
        pump_freq_ghz=5.0,
        sources=[DriveSourceConfig(pump_freq_ghz=5.0, port=2, current_amp=0.0)],
    )

    with pytest.raises(
        ValueError,
        match="SimulationInputError: source #1 targets port 2, but schema only defines ports: 1",
    ):
        simulator.run_hbsolve(
            circuit,
            FrequencyRange(start_ghz=1.0, stop_ghz=2.0, points=2),
            config,
        )


def test_run_hbsolve_forwards_hbsolve_config_parameters():
    circuit = _legacy_circuit(
        name="forward-config",
        parameters={"R50": {"default": 50.0, "unit": "Ohm"}},
        topology=[("P1", "1", "0", 1), ("R50", "1", "0", "R50")],
    )
    captured = {}

    def _capture(*args):
        captured["args"] = args
        return {
            "frequencies_ghz": [1.0],
            "s11_real": [0.1],
            "s11_imag": [0.0],
        }

    simulator = _build_simulator(_capture)
    config = SimulationConfig(
        pump_freq_ghz=6.5,
        n_modulation_harmonics=4,
        n_pump_harmonics=7,
        include_dc=True,
        enable_three_wave_mixing=True,
        enable_four_wave_mixing=False,
        max_intermod_order=9,
        max_iterations=200,
        f_tol=1e-9,
        line_search_switch_tol=1e-6,
        alpha_min=1e-5,
        sources=[
            DriveSourceConfig(pump_freq_ghz=4.65001, port=1, current_amp=2.5e-6),
            DriveSourceConfig(pump_freq_ghz=4.85001, port=1, current_amp=-1.2e-6),
        ],
    )

    simulator.run_hbsolve(
        circuit,
        FrequencyRange(start_ghz=1.0, stop_ghz=2.0, points=2),
        config,
    )

    args = captured["args"]
    assert args[5] == pytest.approx([4.65001, 4.85001])
    assert args[6] == pytest.approx([2.5e-6, -1.2e-6])
    assert args[7] == [1, 1]
    assert args[8] == [[1, 0], [0, 1]]
    assert args[9] == 4
    assert args[10] == 7
    assert args[11] is True
    assert args[12] is True
    assert args[13] is False
    assert args[14] == 9
    assert args[15] == 200
    assert args[16] == pytest.approx(1e-9)
    assert args[17] == pytest.approx(1e-6)
    assert args[18] == pytest.approx(1e-5)
    assert args[19] == [1]


def test_run_hbsolve_supports_explicit_dc_and_pump_sources_on_same_port() -> None:
    circuit = _legacy_circuit(
        name="explicit-modes",
        parameters={"R50": {"default": 50.0, "unit": "Ohm"}},
        topology=[
            ("P1", "1", "0", 1),
            ("P2", "2", "0", 2),
            ("R50_1", "1", "0", "R50"),
            ("R50_2", "2", "0", "R50"),
        ],
    )
    captured = {}

    def _capture(*args):
        captured["args"] = args
        return {
            "frequencies_ghz": [1.0],
            "s11_real": [0.0],
            "s11_imag": [0.0],
        }

    simulator = _build_simulator(_capture)
    config = SimulationConfig(
        sources=[
            DriveSourceConfig(
                pump_freq_ghz=16.0,
                port=2,
                current_amp=1.59e-4,
                mode_components=(0,),
            ),
            DriveSourceConfig(
                pump_freq_ghz=16.0,
                port=2,
                current_amp=4.4e-6,
                mode_components=(1,),
            ),
        ],
        n_modulation_harmonics=8,
        n_pump_harmonics=16,
        include_dc=True,
        enable_three_wave_mixing=True,
    )

    simulator.run_hbsolve(
        circuit,
        FrequencyRange(start_ghz=7.8, stop_ghz=8.2, points=401),
        config,
    )

    args = captured["args"]
    assert args[5] == pytest.approx([16.0])
    assert args[6] == pytest.approx([1.59e-4, 4.4e-6])
    assert args[7] == [2, 2]
    assert args[8] == [[0], [1]]


def test_run_hbsolve_compresses_unused_explicit_mode_slots() -> None:
    circuit = _legacy_circuit(
        name="compressed-modes",
        parameters={"R50": {"default": 50.0, "unit": "Ohm"}},
        topology=[
            ("P1", "1", "0", 1),
            ("P2", "2", "0", 2),
            ("R50_1", "1", "0", "R50"),
            ("R50_2", "2", "0", "R50"),
        ],
    )
    captured = {}

    def _capture(*args):
        captured["args"] = args
        return {
            "frequencies_ghz": [1.0],
            "s11_real": [0.0],
            "s11_imag": [0.0],
        }

    simulator = _build_simulator(_capture)
    config = SimulationConfig(
        sources=[
            DriveSourceConfig(
                pump_freq_ghz=16.0,
                port=2,
                current_amp=1.59e-4,
                mode_components=(0, 0),
            ),
            DriveSourceConfig(
                pump_freq_ghz=16.0,
                port=2,
                current_amp=4.4e-6,
                mode_components=(1, 0),
            ),
        ]
    )

    simulator.run_hbsolve(
        circuit,
        FrequencyRange(start_ghz=7.8, stop_ghz=8.2, points=401),
        config,
    )

    args = captured["args"]
    assert args[5] == pytest.approx([16.0])
    assert args[8] == [[0], [1]]


def test_run_hbsolve_compresses_second_slot_single_pump_to_one_active_tone() -> None:
    circuit = _legacy_circuit(
        name="compressed-second-slot",
        parameters={"R50": {"default": 50.0, "unit": "Ohm"}},
        topology=[("P1", "1", "0", 1), ("R50", "1", "0", "R50")],
    )
    captured = {}

    def _capture(*args):
        captured["args"] = args
        return {
            "frequencies_ghz": [1.0],
            "s11_real": [0.0],
            "s11_imag": [0.0],
        }

    simulator = _build_simulator(_capture)
    config = SimulationConfig(
        sources=[
            DriveSourceConfig(
                pump_freq_ghz=4.2,
                port=1,
                current_amp=1.0e-6,
                mode_components=(0, 1),
            )
        ]
    )

    simulator.run_hbsolve(
        circuit,
        FrequencyRange(start_ghz=1.0, stop_ghz=2.0, points=11),
        config,
    )

    args = captured["args"]
    assert args[5] == pytest.approx([4.2])
    assert args[8] == [[1]]


def test_run_hbsolve_rejects_mixed_implicit_and_explicit_source_modes() -> None:
    circuit = _legacy_circuit(
        name="mixed-modes",
        parameters={"R50": {"default": 50.0, "unit": "Ohm"}},
        topology=[("P1", "1", "0", 1), ("R50", "1", "0", "R50")],
    )
    simulator = _build_simulator(lambda *_: pytest.fail("Julia should not be called"))
    config = SimulationConfig(
        sources=[
            DriveSourceConfig(pump_freq_ghz=5.0, port=1, current_amp=0.0, mode_components=(1,)),
            DriveSourceConfig(pump_freq_ghz=6.0, port=1, current_amp=0.0),
        ]
    )

    with pytest.raises(
        ValueError,
        match="SimulationInputError: once any source uses an explicit mode tuple",
    ):
        simulator.run_hbsolve(
            circuit,
            FrequencyRange(start_ghz=1.0, stop_ghz=2.0, points=2),
            config,
        )


class _FakeSymbolKey:
    def __init__(self, text: str) -> None:
        self.text = text

    def __str__(self) -> str:
        return self.text


def test_build_simulation_result_accepts_julia_symbol_style_keys() -> None:
    raw_payload = {
        _FakeSymbolKey("Julia: :frequencies_ghz"): [1.0],
        _FakeSymbolKey("Julia: :s11_real"): [0.1],
        _FakeSymbolKey("Julia: :s11_imag"): [0.0],
        _FakeSymbolKey("Julia: :port_indices"): [1],
        _FakeSymbolKey("Julia: :mode_indices"): [[0], [1]],
        _FakeSymbolKey("Julia: :s_parameter_real"): {"S11": [0.1]},
        _FakeSymbolKey("Julia: :s_parameter_imag"): {"S11": [0.0]},
        _FakeSymbolKey("Julia: :s_parameter_mode_real"): {"om=1|op=1|im=0|ip=1": [0.5]},
        _FakeSymbolKey("Julia: :s_parameter_mode_imag"): {"om=1|op=1|im=0|ip=1": [0.0]},
    }

    result = JuliaSimulator._build_simulation_result(raw_payload)

    assert result.frequencies_ghz == [1.0]
    assert result.available_mode_indices == [(0,), (1,)]
    assert result.get_mode_s_parameter_real((1,), 1, (0,), 1) == [0.5]
