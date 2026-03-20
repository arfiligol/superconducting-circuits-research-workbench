"""
Julia Adapter for JosephsonCircuits.jl via JuliaCall.

This module provides the Python-Julia interoperability layer.
"""

import sys
from collections.abc import Iterable
from pathlib import Path

from core.simulation.domain.circuit import (
    CircuitDefinition,
    DriveSourceConfig,
    FrequencyRange,
    SimulationConfig,
    SimulationResult,
)
from core.simulation.domain.compiler import compile_simulation_topology

# Path to the Julia bridge file
_JULIA_BRIDGE_PATH = Path(__file__).parent / "hbsolve.jl"
_REPO_ROOT = Path(__file__).resolve().parents[3]


class JuliaSimulator:
    """
    Adapter for calling JosephsonCircuits.jl from Python via JuliaCall.

    Usage:
        simulator = JuliaSimulator()
        result = simulator.run_hbsolve(circuit, freq_range, config)
    """

    def __init__(self) -> None:
        """Initialize the Julia environment and load JosephsonCircuits.jl."""
        self._jl = None
        self._initialized = False

    def _ensure_initialized(self) -> None:
        """Lazy initialization of Julia runtime."""
        if self._initialized:
            return

        try:
            # Ensure subprocess workers discover repository-level `juliapkg.json`.
            repo_root = str(_REPO_ROOT)
            if repo_root not in sys.path:
                sys.path.append(repo_root)

            from juliacall import Main as jl  # type: ignore

            self._jl = jl

            # Load the Julia bridge file
            if _JULIA_BRIDGE_PATH.exists():
                try:
                    jl.include(str(_JULIA_BRIDGE_PATH))
                except Exception as e:
                    if "Package JosephsonCircuits not found" not in str(e):
                        raise

                    # Fallback for fresh subprocesses where Juliapkg env is not yet materialized.
                    jl.seval("import Pkg; Pkg.instantiate()")
                    try:
                        jl.include(str(_JULIA_BRIDGE_PATH))
                    except Exception as e_retry:
                        if "Package JosephsonCircuits not found" not in str(e_retry):
                            raise
                        jl.seval('import Pkg; Pkg.add("JosephsonCircuits")')
                        jl.include(str(_JULIA_BRIDGE_PATH))
            else:
                # Fallback: load JosephsonCircuits directly
                jl.seval("using JosephsonCircuits")

            self._initialized = True
        except ImportError as e:
            msg = (
                "juliacall is not installed. "
                "Install it with: uv add juliacall\n"
                "Also ensure Julia and JosephsonCircuits.jl are installed."
            )
            raise ImportError(msg) from e

    def run_lc_simulation(
        self,
        inductance_nh: float,
        capacitance_pf: float,
        freq_range: FrequencyRange,
    ) -> SimulationResult:
        """
        Run a simple LC resonator simulation.

        Args:
            inductance_nh: Inductance in nanohenries.
            capacitance_pf: Capacitance in picofarads.
            freq_range: Frequency sweep configuration.

        Returns:
            SimulationResult with S11 data.
        """
        self._ensure_initialized()
        assert self._jl is not None  # Guaranteed by _ensure_initialized

        # Call Julia function
        result = self._jl.run_lc_simulation(
            float(inductance_nh),
            float(capacitance_pf),
            float(freq_range.start_ghz),
            float(freq_range.stop_ghz),
            int(freq_range.points),
        )

        return self._build_simulation_result(result)

    def run_hbsolve(
        self,
        circuit: CircuitDefinition,
        freq_range: FrequencyRange,
        config: SimulationConfig,
    ) -> SimulationResult:
        """
        Run harmonic balance simulation for a custom circuit.

        Args:
            circuit: Circuit definition with topology and parameter values.
            freq_range: Frequency sweep range.
            config: Simulation configuration (harmonics, pump, etc.).

        Returns:
            SimulationResult with S11 data.
        """
        self._ensure_initialized()
        assert self._jl is not None  # Guaranteed by _ensure_initialized

        self._validate_circuit_inputs(circuit)
        available_ports = self._extract_available_port_indices(circuit)
        sources = self._build_effective_sources(config)
        self._validate_solver_config(config, sources, available_ports)

        # Convert CircuitIR into Julia-compatible tuples at the compiler boundary.
        topology = compile_simulation_topology(
            circuit.to_ir(),
            is_ground_node=lambda node: circuit.is_ground_node(node),
        )

        component_values = {
            component_name: (
                circuit.resolve_component_value(component_name)
                * self._get_unit_multiplier(component_spec.unit)
            )
            for component_name, component_spec in circuit.component_specs.items()
        }

        max_intermod_order = (
            config.max_intermod_order if config.max_intermod_order is not None else -1
        )

        pump_freqs_ghz, source_mode_vectors = self._resolve_pump_frequencies_and_modes(sources)

        try:
            # Call Julia function
            result = self._jl.run_custom_simulation(
                topology,
                component_values,
                float(freq_range.start_ghz),
                float(freq_range.stop_ghz),
                int(freq_range.points),
                pump_freqs_ghz,
                [float(src.current_amp) for src in sources],
                [int(src.port) for src in sources],
                source_mode_vectors,
                int(config.n_modulation_harmonics),
                int(config.n_pump_harmonics),
                bool(config.include_dc),
                bool(config.enable_three_wave_mixing),
                bool(config.enable_four_wave_mixing),
                int(max_intermod_order),
                int(config.max_iterations),
                float(config.f_tol),
                float(config.line_search_switch_tol),
                float(config.alpha_min),
                sorted(available_ports) or [1],
            )
        except Exception as e:
            detail = str(e)
            if "Ports without resistors detected" in detail:
                raise ValueError(
                    "SimulationInputError: each port node must include a shunt resistor "
                    "to ground (for example 50 Ohm).\n\n"
                    f"Julia detail:\n{detail[:3000]}"
                ) from e
            if "SingularException" in detail:
                raise RuntimeError(
                    "SimulationNumericalError: solver matrix became singular. "
                    "This is usually due to ill-conditioned topology/value combinations "
                    "(for example floating nodes or problematic parallel branches).\n\n"
                    f"Julia detail:\n{detail[:3000]}"
                ) from e
            raise

        return self._build_simulation_result(result)

    @staticmethod
    def _as_python_mapping(value: object) -> dict[object, object]:
        """Convert Julia/Python mapping-like values into a plain Python dict."""
        if isinstance(value, dict):
            return value
        try:
            return dict(value)  # type: ignore[arg-type]
        except Exception:
            return {}

    @staticmethod
    def _as_python_list(value: object) -> list[object]:
        """Convert Julia/Python iterable-like values into a plain Python list."""
        if isinstance(value, list):
            return value
        if isinstance(value, str | bytes | bytearray):
            return []
        if isinstance(value, Iterable):
            return list(value)
        return []

    @staticmethod
    def _to_float(value: object, default: float = 0.0) -> float:
        """Best-effort numeric coercion for Julia bridge payloads."""
        try:
            return float(str(value))
        except Exception:
            return default

    @staticmethod
    def _to_int(value: object, default: int = 0) -> int:
        """Best-effort integer coercion for Julia bridge payloads."""
        try:
            return int(float(str(value)))
        except Exception:
            return default

    @staticmethod
    def _normalize_mapping_key(key: object) -> str:
        """Normalize Python and Julia Symbol-like keys into plain strings."""
        text = str(key)
        if text.startswith("Julia: :"):
            return text.removeprefix("Julia: :")
        if text.startswith(":"):
            return text[1:]
        return text

    @classmethod
    def _mapping_get(cls, mapping: dict[object, object], key: str, default: object) -> object:
        """Read a mapping entry by matching either Python strings or Julia Symbol keys."""
        for candidate_key, candidate_value in mapping.items():
            if cls._normalize_mapping_key(candidate_key) == key:
                return candidate_value
        return default

    @classmethod
    def _extract_trace_map(cls, result: object, *, key: str) -> dict[str, list[float]]:
        """Extract one trace map from the Julia bridge payload."""
        result_mapping = cls._as_python_mapping(result)
        raw_trace_map = cls._mapping_get(result_mapping, key, {})
        trace_map = cls._as_python_mapping(raw_trace_map)
        normalized: dict[str, list[float]] = {}

        for trace_label, values in trace_map.items():
            normalized[str(trace_label)] = [
                cls._to_float(value) for value in cls._as_python_list(values)
            ]
        return normalized

    @classmethod
    def _extract_scalar_trace_map(cls, result: object, *, key: str) -> dict[str, list[float]]:
        """Extract a scalar trace map from the Julia bridge payload."""
        return cls._extract_trace_map(result, key=key)

    @classmethod
    def _build_simulation_result(cls, result: object) -> SimulationResult:
        """Convert a Julia bridge payload into SimulationResult."""
        result_mapping = cls._as_python_mapping(result)
        raw_ports = cls._as_python_list(cls._mapping_get(result_mapping, "port_indices", [1]))
        port_indices = [cls._to_int(port, default=1) for port in raw_ports]
        raw_modes = cls._mapping_get(result_mapping, "mode_indices", [[0]])
        mode_indices = [
            tuple(cls._to_int(value) for value in cls._as_python_list(mode))
            for mode in cls._as_python_list(raw_modes)
        ] or [(0,)]

        return SimulationResult(
            frequencies_ghz=[
                cls._to_float(value)
                for value in cls._as_python_list(
                    cls._mapping_get(result_mapping, "frequencies_ghz", [])
                )
            ],
            s11_real=[
                cls._to_float(value)
                for value in cls._as_python_list(cls._mapping_get(result_mapping, "s11_real", []))
            ],
            s11_imag=[
                cls._to_float(value)
                for value in cls._as_python_list(cls._mapping_get(result_mapping, "s11_imag", []))
            ],
            port_indices=port_indices or [1],
            s_parameter_real=cls._extract_trace_map(result, key="s_parameter_real"),
            s_parameter_imag=cls._extract_trace_map(result, key="s_parameter_imag"),
            mode_indices=mode_indices,
            s_parameter_mode_real=cls._extract_trace_map(result, key="s_parameter_mode_real"),
            s_parameter_mode_imag=cls._extract_trace_map(result, key="s_parameter_mode_imag"),
            z_parameter_mode_real=cls._extract_trace_map(result, key="z_parameter_mode_real"),
            z_parameter_mode_imag=cls._extract_trace_map(result, key="z_parameter_mode_imag"),
            y_parameter_mode_real=cls._extract_trace_map(result, key="y_parameter_mode_real"),
            y_parameter_mode_imag=cls._extract_trace_map(result, key="y_parameter_mode_imag"),
            qe_parameter_mode=cls._extract_scalar_trace_map(result, key="qe_parameter_mode"),
            qe_ideal_parameter_mode=cls._extract_scalar_trace_map(
                result,
                key="qe_ideal_parameter_mode",
            ),
            cm_parameter_mode=cls._extract_scalar_trace_map(result, key="cm_parameter_mode"),
        )

    @staticmethod
    def _validate_circuit_inputs(circuit: CircuitDefinition) -> None:
        """Validate basic circuit integrity before invoking Julia."""
        component_names = set(circuit.component_specs)
        elements = circuit.lowered_elements()

        for element in elements:
            if element.is_port:
                continue
            if not isinstance(element.value_ref, str):
                raise ValueError(
                    "SimulationInputError: non-port elements must use string component references. "
                    f"Got '{element.value_ref}' in instance '{element.name}'."
                )
            if element.value_ref not in component_names:
                raise ValueError(
                    f"SimulationInputError: element '{element.name}' references undefined "
                    f"component '{element.value_ref}'."
                )

        for element in elements:
            if not element.is_port:
                continue
            port_node = element.node2 if circuit.is_ground_node(element.node1) else element.node1
            has_shunt_resistor = any(
                candidate.kind == "resistor"
                and (
                    (candidate.node1 == port_node and circuit.is_ground_node(candidate.node2))
                    or (candidate.node2 == port_node and circuit.is_ground_node(candidate.node1))
                )
                for candidate in elements
            )
            if not has_shunt_resistor:
                raise ValueError(
                    "SimulationInputError: each port node needs a shunt resistor to ground "
                    f"(missing at node '{port_node}')."
                )

    @staticmethod
    def _extract_available_port_indices(circuit: CircuitDefinition) -> set[int]:
        """Collect declared port indices from public port declarations."""
        return set(circuit.available_port_indices)

    @staticmethod
    def _build_effective_sources(config: SimulationConfig) -> list[DriveSourceConfig]:
        """Resolve sources list with fallback to legacy single-source fields."""
        if config.sources is not None:
            return list(config.sources)

        return [
            DriveSourceConfig(
                pump_freq_ghz=float(config.pump_freq_ghz),
                port=int(config.pump_port),
                current_amp=float(config.pump_current_amp),
            )
        ]

    @staticmethod
    def _build_source_mode_vectors(source_count: int) -> list[list[int]]:
        """Build one-hot mode vectors matching number of configured pump tones."""
        mode_vectors: list[list[int]] = []
        for idx in range(source_count):
            mode = [0] * source_count
            mode[idx] = 1
            mode_vectors.append(mode)
        return mode_vectors

    @classmethod
    def _resolve_pump_frequencies_and_modes(
        cls,
        sources: list[DriveSourceConfig],
    ) -> tuple[list[float], list[list[int]]]:
        """Resolve hbsolve pump-frequency tuple and source mode vectors from the source list."""
        if not sources:
            return ([5.0], [[1]])

        explicit_modes = [source.mode_components for source in sources]
        if all(mode is None for mode in explicit_modes):
            return (
                [float(source.pump_freq_ghz) for source in sources],
                cls._build_source_mode_vectors(len(sources)),
            )

        if any(mode is None for mode in explicit_modes):
            raise ValueError(
                "SimulationInputError: once any source uses an explicit mode tuple, "
                "all sources must define one."
            )

        normalized_modes = [tuple(int(value) for value in mode or ()) for mode in explicit_modes]
        mode_lengths = {len(mode) for mode in normalized_modes}
        if len(mode_lengths) != 1 or 0 in mode_lengths:
            raise ValueError(
                "SimulationInputError: all source mode tuples must have the same non-zero length."
            )

        _ = mode_lengths.pop()
        active_tone_indices = sorted(
            {idx for mode in normalized_modes for idx, value in enumerate(mode) if value != 0}
        )
        compressed_tone_count = len(active_tone_indices)
        active_index_map = {
            source_index: compressed_index
            for compressed_index, source_index in enumerate(active_tone_indices)
        }

        if compressed_tone_count == 0:
            return ([float(sources[0].pump_freq_ghz)], [[0] for _ in sources])

        pump_freqs_ghz: list[float | None] = [None] * compressed_tone_count
        compressed_modes: list[list[int]] = []

        for index, source in enumerate(sources, start=1):
            mode = normalized_modes[index - 1]
            nonzero_indices = [idx for idx, value in enumerate(mode) if value != 0]
            if not nonzero_indices:
                compressed_modes.append([0] * compressed_tone_count)
                continue

            if len(nonzero_indices) != 1 or mode[nonzero_indices[0]] < 0:
                raise ValueError(
                    "SimulationInputError: only DC sources (all zeros) and one-hot positive "
                    "source mode tuples are currently supported."
                )

            tone_index = active_index_map[nonzero_indices[0]]
            pump_freq = float(source.pump_freq_ghz)
            assigned = pump_freqs_ghz[tone_index]
            compressed_mode = [0] * compressed_tone_count
            compressed_mode[tone_index] = int(mode[nonzero_indices[0]])
            compressed_modes.append(compressed_mode)
            if assigned is None:
                pump_freqs_ghz[tone_index] = pump_freq
                continue

            if abs(assigned - pump_freq) > 1e-12:
                raise ValueError(
                    "SimulationInputError: conflicting pump frequencies were provided for "
                    f"mode slot {tone_index + 1}."
                )

        if any(freq is None for freq in pump_freqs_ghz):
            raise ValueError(
                "SimulationInputError: each non-zero mode slot needs at least one source "
                "to define its pump frequency."
            )

        return (
            [float(freq) for freq in pump_freqs_ghz if freq is not None],
            compressed_modes,
        )

    @staticmethod
    def _validate_solver_config(
        config: SimulationConfig,
        sources: list[DriveSourceConfig],
        available_ports: set[int],
    ) -> None:
        """Validate hbsolve controls before calling Julia."""
        JuliaSimulator._validate_solver_controls(config)
        if not sources:
            raise ValueError("SimulationInputError: at least one source is required.")

        for index, source in enumerate(sources, start=1):
            if source.pump_freq_ghz <= 0:
                raise ValueError(
                    f"SimulationInputError: source #{index} pump_freq_ghz must be > 0."
                )
            if source.port < 1:
                raise ValueError(f"SimulationInputError: source #{index} port must be >= 1.")
            if available_ports and source.port not in available_ports:
                ordered_ports = ", ".join(str(p) for p in sorted(available_ports))
                raise ValueError(
                    "SimulationInputError: source "
                    f"#{index} targets port {source.port}, but schema only defines ports: "
                    f"{ordered_ports}."
                )

    @staticmethod
    def _validate_solver_controls(config: SimulationConfig) -> None:
        """Validate shared (non-source) hbsolve controls."""
        if config.pump_freq_ghz <= 0:
            raise ValueError("SimulationInputError: pump_freq_ghz must be > 0.")
        if config.n_modulation_harmonics < 0:
            raise ValueError("SimulationInputError: n_modulation_harmonics must be >= 0.")
        if config.n_pump_harmonics < 0:
            raise ValueError("SimulationInputError: n_pump_harmonics must be >= 0.")
        if config.max_iterations < 1:
            raise ValueError("SimulationInputError: max_iterations must be >= 1.")
        if config.f_tol <= 0:
            raise ValueError("SimulationInputError: f_tol must be > 0.")
        if config.line_search_switch_tol <= 0:
            raise ValueError("SimulationInputError: line_search_switch_tol must be > 0.")
        if config.alpha_min <= 0:
            raise ValueError("SimulationInputError: alpha_min must be > 0.")
        if config.max_intermod_order is not None and config.max_intermod_order < 1:
            raise ValueError("SimulationInputError: max_intermod_order must be >= 1 or None.")

    @staticmethod
    def _get_unit_multiplier(unit: str) -> float:
        """Convert unit string to multiplier."""
        normalized = unit.strip().lower()
        unit_map = {
            "h": 1.0,
            "mh": 1e-3,
            "uh": 1e-6,
            "nh": 1e-9,
            "ph": 1e-12,
            "f": 1.0,
            "mf": 1e-3,
            "uf": 1e-6,
            "nf": 1e-9,
            "pf": 1e-12,
            "ff": 1e-15,
            "ohm": 1.0,
            "kohm": 1e3,
            "mohm": 1e6,
        }
        if normalized not in unit_map:
            allowed_units = ", ".join(sorted(unit_map.keys()))
            raise ValueError(
                f"SimulationInputError: unsupported unit '{unit}'. Allowed: {allowed_units}."
            )
        return unit_map[normalized]
