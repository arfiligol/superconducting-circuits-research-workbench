"""Tests for built-in simulation setup seeds on the simulation page."""

import importlib.util
from pathlib import Path

from legacy.legacy_nicegui_archived.pages.simulation import (
    _JOSEPHSON_BUILTIN_SETUP_PAYLOADS,
    _builtin_saved_setups_for_schema,
    _compress_source_mode_components,
    _extract_available_port_indices,
    _merge_saved_setups_with_builtin,
    _normalize_source_mode_components,
)
from core.simulation.domain.circuit import (
    DriveSourceConfig,
    SimulationConfig,
    parse_circuit_definition_source,
)


def _load_seed_module():
    module_path = (
        Path(__file__).resolve().parents[3] / "tmp" / "seed_josephson_circuits_examples.py"
    )
    spec = importlib.util.spec_from_file_location("seed_josephson_circuits_examples", module_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_builtin_saved_setups_for_jpa_returns_official_example() -> None:
    setups = _builtin_saved_setups_for_schema(
        "JosephsonCircuits Examples: Josephson Parametric Amplifier (JPA)"
    )

    assert len(setups) == 1
    setup = setups[0]
    assert setup["name"] == "Official Example"
    assert setup["saved_at"] == "builtin"
    assert setup["payload"]["freq_range"]["start_ghz"] == 4.5
    assert setup["payload"]["freq_range"]["stop_ghz"] == 5.0
    assert setup["payload"]["harmonics"]["n_modulation_harmonics"] == 8
    assert setup["payload"]["harmonics"]["n_pump_harmonics"] == 16


def test_builtin_saved_setups_for_double_pumped_jpa_has_two_sources() -> None:
    setups = _builtin_saved_setups_for_schema(
        "JosephsonCircuits Examples: Double-pumped Josephson Parametric Amplifier (JPA)"
    )

    assert len(setups) == 1
    sources = setups[0]["payload"]["sources"]
    assert len(sources) == 2
    assert sources[0]["pump_freq_ghz"] == 4.65001
    assert sources[1]["pump_freq_ghz"] == 4.85001
    assert sources[0]["mode"] == [1, 0]
    assert sources[1]["mode"] == [0, 1]


def test_builtin_saved_setups_for_snail_matches_official_dual_source_bias_example() -> None:
    setups = _builtin_saved_setups_for_schema(
        "JosephsonCircuits Examples: SNAIL Parametric Amplifier"
    )

    assert len(setups) == 1
    payload = setups[0]["payload"]
    assert payload["freq_range"] == {"start_ghz": 7.8, "stop_ghz": 8.2, "points": 401}
    assert payload["harmonics"] == {"n_modulation_harmonics": 8, "n_pump_harmonics": 16}
    assert payload["advanced"]["include_dc"] is True
    assert payload["advanced"]["enable_three_wave_mixing"] is True
    assert payload["sources"] == [
        {"pump_freq_ghz": 16.0, "port": 2, "current_amp": 0.000159, "mode": [0]},
        {"pump_freq_ghz": 16.0, "port": 2, "current_amp": 4.4e-6, "mode": [1]},
    ]


def test_all_builtin_saved_setups_target_ports_declared_by_seeded_examples() -> None:
    seed_module = _load_seed_module()
    definitions = {
        name: parse_circuit_definition_source(definition)
        for name, definition in seed_module.build_all()
    }

    for schema_name in definitions:
        setups = _builtin_saved_setups_for_schema(schema_name)
        assert len(setups) == 1

        payload = setups[0]["payload"]
        ports = _extract_available_port_indices(definitions[schema_name])
        for source in payload["sources"]:
            assert source["port"] in ports


def test_loop_generated_seeded_examples_use_repeat_source_form() -> None:
    seed_module = _load_seed_module()
    definitions = dict(seed_module.build_all())

    jtwpa_definition = definitions[
        "JosephsonCircuits Examples: Josephson Traveling Wave Parametric Amplifier (JTWPA)"
    ]
    floquet_definition = definitions["JosephsonCircuits Examples: Floquet JTWPA"]
    floquet_loss_definition = definitions[
        "JosephsonCircuits Examples: Floquet JTWPA with Dissipation"
    ]
    flux_definition = definitions[
        "JosephsonCircuits Examples: Flux-Driven Josephson Traveling-Wave Parametric Amplifier"
        " (JTWPA)"
    ]

    assert "repeat" in jtwpa_definition
    assert "repeat" in floquet_definition
    assert "repeat" in floquet_loss_definition
    assert "repeat" in flux_definition

    floquet_circuit = parse_circuit_definition_source(floquet_definition)
    jtwpa_circuit = parse_circuit_definition_source(jtwpa_definition)

    assert floquet_circuit.resolve_component_value(
        "Lj1_2"
    ) != floquet_circuit.resolve_component_value("Lj2_3")
    assert jtwpa_circuit.resolve_component_value("Lj1_2") == jtwpa_circuit.resolve_component_value(
        "Lj4_5"
    )


def test_flux_pumped_jpa_seed_uses_parameterized_source_form_for_sweep_targets() -> None:
    seed_module = _load_seed_module()
    definitions = dict(seed_module.build_all())
    flux_definition = definitions[
        "JosephsonCircuits Examples: Flux-pumped Josephson Parametric Amplifier (JPA)"
    ]
    flux_circuit = parse_circuit_definition_source(flux_definition)
    expanded = flux_circuit.expanded_definition

    assert any(component.value_ref == "Lj" for component in expanded.components)
    assert expanded.parameter_spec("Lj") is not None


def test_merge_saved_setups_with_builtin_keeps_user_setup() -> None:
    builtin = _builtin_saved_setups_for_schema(
        "JosephsonCircuits Examples: Josephson Parametric Amplifier (JPA)"
    )
    user_setup = {
        "id": "user:custom",
        "name": "My Sweep",
        "saved_at": "2026-03-01T00:00:00",
        "payload": {"freq_range": {"start_ghz": 4.4, "stop_ghz": 5.1, "points": 701}},
    }

    merged = _merge_saved_setups_with_builtin([user_setup], builtin)

    assert merged[0]["saved_at"] == "builtin"
    assert merged[1]["id"] == "user:custom"


def test_normalize_source_mode_components_expands_single_source_one_hot() -> None:
    assert _normalize_source_mode_components((1,), source_index=0, source_count=2) == (1, 0)
    assert _normalize_source_mode_components((1,), source_index=1, source_count=2) == (1, 0)
    assert _normalize_source_mode_components((2,), source_index=0, source_count=2) == (0, 1)
    assert _normalize_source_mode_components((0,), source_index=0, source_count=2) == (0, 0)


def test_compress_source_mode_components_hides_internal_padding() -> None:
    assert _compress_source_mode_components((0, 0)) == (0,)
    assert _compress_source_mode_components((1, 0)) == (1,)
    assert _compress_source_mode_components((0, 1)) == (0, 1)


def test_all_builtin_saved_setups_translate_to_valid_simulation_config() -> None:
    for payload in _JOSEPHSON_BUILTIN_SETUP_PAYLOADS.values():
        advanced = payload["advanced"]
        sources = [
            DriveSourceConfig(
                pump_freq_ghz=source["pump_freq_ghz"],
                port=source["port"],
                current_amp=source["current_amp"],
                mode_components=tuple(source.get("mode", [])) or None,
            )
            for source in payload["sources"]
        ]

        config = SimulationConfig(
            pump_freq_ghz=sources[0].pump_freq_ghz,
            sources=sources,
            pump_current_amp=sources[0].current_amp,
            pump_port=sources[0].port,
            pump_mode_index=1,
            n_modulation_harmonics=payload["harmonics"]["n_modulation_harmonics"],
            n_pump_harmonics=payload["harmonics"]["n_pump_harmonics"],
            include_dc=advanced["include_dc"],
            enable_three_wave_mixing=advanced["enable_three_wave_mixing"],
            enable_four_wave_mixing=advanced["enable_four_wave_mixing"],
            max_intermod_order=(
                None if int(advanced["max_intermod_order"]) < 0 else advanced["max_intermod_order"]
            ),
            max_iterations=advanced["max_iterations"],
            f_tol=advanced["f_tol"],
            line_search_switch_tol=advanced["line_search_switch_tol"],
            alpha_min=advanced["alpha_min"],
        )

        assert config.line_search_switch_tol > 0
