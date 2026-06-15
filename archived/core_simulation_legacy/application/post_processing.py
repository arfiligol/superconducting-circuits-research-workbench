"""Port-level post-processing helpers for simulation matrix results."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import numpy as np

from core.simulation.application.run_simulation import SimulationSweepAxis
from core.simulation.domain.circuit import CircuitDefinition, SimulationResult

type ModeFilter = Literal["base", "sideband", "all"]
type PortTerminationSource = Literal["schema_infer", "fallback_default_50", "manual"]

_RESISTANCE_UNIT_MULTIPLIER = {
    "ohm": 1.0,
    "kohm": 1e3,
    "mohm": 1e6,
}


@dataclass(frozen=True)
class PortTerminationInference:
    """Resolved termination resistance inference snapshot."""

    resistance_ohm_by_port: dict[int, float]
    source_by_port: dict[int, PortTerminationSource]
    warning_by_port: dict[int, str]


@dataclass(frozen=True)
class PortMatrixSweep:
    """Complex Y-matrix sweep in one fixed mode and one fixed basis."""

    frequencies_ghz: tuple[float, ...]
    mode: tuple[int, ...]
    labels: tuple[str, ...]
    y_matrices: tuple[np.ndarray, ...]
    source_kind: Literal["y", "z", "s"]

    @property
    def dimension(self) -> int:
        """Return matrix dimension."""
        return len(self.labels)

    def trace(self, row: int, col: int) -> list[complex]:
        """Return one complex trace from all frequency slices."""
        if row < 0 or col < 0 or row >= self.dimension or col >= self.dimension:
            raise IndexError("Trace index out of range.")
        return [complex(matrix[row, col]) for matrix in self.y_matrices]


@dataclass(frozen=True)
class PortMatrixSweepPoint:
    """One post-processed sweep point that preserves original sweep provenance."""

    point_index: int
    axis_indices: tuple[int, ...]
    axis_values: dict[str, float]
    sweep: PortMatrixSweep


@dataclass(frozen=True)
class PortMatrixSweepRun:
    """Post-processing runtime output for one full parameter sweep."""

    axes: tuple[SimulationSweepAxis, ...]
    points: tuple[PortMatrixSweepPoint, ...]
    representative_point_index: int = 0

    @property
    def dimension(self) -> int:
        """Return sweep dimensionality."""
        return len(self.axes)

    @property
    def point_count(self) -> int:
        """Return total point count."""
        return len(self.points)

    @property
    def representative_sweep(self) -> PortMatrixSweep:
        """Return UI preview projection for the current canonical runtime payload."""
        if not self.points:
            raise ValueError("Post-processed sweep run produced no points.")
        if self.representative_point_index < 0 or self.representative_point_index >= len(
            self.points
        ):
            raise ValueError("representative_point_index is out of range.")
        return self.points[self.representative_point_index].sweep


def infer_port_termination_resistance_ohm(
    circuit_definition: CircuitDefinition,
    *,
    fallback_ohm: float = 50.0,
) -> PortTerminationInference:
    """Infer one shunt termination resistor value per port from expanded netlist topology."""
    if fallback_ohm <= 0:
        raise ValueError("fallback_ohm must be positive.")

    port_node_by_index: dict[int, str] = {}
    for row in circuit_definition.expanded_definition.topology:
        if not row.is_port:
            continue
        try:
            port_index = int(row.value_ref)
        except Exception:
            continue
        if circuit_definition.is_ground_node(row.node1) and not circuit_definition.is_ground_node(
            row.node2
        ):
            port_node_by_index[port_index] = str(row.node2)
            continue
        if circuit_definition.is_ground_node(row.node2) and not circuit_definition.is_ground_node(
            row.node1
        ):
            port_node_by_index[port_index] = str(row.node1)

    shunt_resistors_by_node: dict[str, list[tuple[str, float]]] = {}
    for element in circuit_definition.to_ir().elements:
        if element.kind != "resistor" or element.is_port or element.is_mutual_coupling:
            continue
        if not isinstance(element.value_ref, str):
            continue
        if circuit_definition.is_ground_node(element.node1):
            node = str(element.node2)
        elif circuit_definition.is_ground_node(element.node2):
            node = str(element.node1)
        else:
            continue
        try:
            resolved_value = circuit_definition.resolve_component_value(element.value_ref)
            component = circuit_definition.component_spec(element.value_ref)
            unit = component.unit if component is not None else "Ohm"
            value_ohm = _resistance_to_ohm(resolved_value, unit=unit)
        except Exception:
            continue
        shunt_resistors_by_node.setdefault(node, []).append((str(element.name), float(value_ohm)))

    inferred: dict[int, float] = {}
    sources: dict[int, PortTerminationSource] = {}
    warnings: dict[int, str] = {}
    for port in circuit_definition.available_port_indices:
        node = port_node_by_index.get(port)
        if node is None:
            inferred[port] = float(fallback_ohm)
            sources[port] = "fallback_default_50"
            warnings[port] = (
                f"Port {port}: cannot infer a unique signal node from topology; "
                f"fallback to {fallback_ohm:g} Ohm."
            )
            continue

        candidates = shunt_resistors_by_node.get(node, [])
        if len(candidates) != 1:
            inferred[port] = float(fallback_ohm)
            sources[port] = "fallback_default_50"
            if not candidates:
                warnings[port] = (
                    f"Port {port}: no shunt resistor to ground found at node '{node}'; "
                    f"fallback to {fallback_ohm:g} Ohm."
                )
            else:
                candidate_names = ", ".join(name for name, _ in candidates)
                warnings[port] = (
                    f"Port {port}: multiple shunt resistors to ground found at node '{node}' "
                    f"({candidate_names}); fallback to {fallback_ohm:g} Ohm."
                )
            continue

        _, value_ohm = candidates[0]
        if value_ohm <= 0:
            inferred[port] = float(fallback_ohm)
            sources[port] = "fallback_default_50"
            warnings[port] = (
                f"Port {port}: inferred non-positive resistance ({value_ohm:g} Ohm); "
                f"fallback to {fallback_ohm:g} Ohm."
            )
            continue

        inferred[port] = float(value_ohm)
        sources[port] = "schema_infer"

    return PortTerminationInference(
        resistance_ohm_by_port=inferred,
        source_by_port=sources,
        warning_by_port=warnings,
    )


def apply_shunt_termination_compensation(
    sweep: PortMatrixSweep,
    *,
    resistance_ohm_by_port: dict[int, float],
) -> PortMatrixSweep:
    """Apply Y_clean = Y_meas - diag(1/R_i) on selected sweep labels/ports."""
    if not resistance_ohm_by_port:
        return sweep

    diagonal = np.zeros((sweep.dimension, sweep.dimension), dtype=np.complex128)
    any_port_selected = False
    for idx, label in enumerate(sweep.labels):
        if not str(label).isdigit():
            continue
        port = int(label)
        if port not in resistance_ohm_by_port:
            continue
        resistance_ohm = float(resistance_ohm_by_port[port])
        if resistance_ohm <= 0:
            raise ValueError(f"Port {port} has non-positive termination resistance.")
        diagonal[idx, idx] = 1.0 / resistance_ohm
        any_port_selected = True

    if not any_port_selected:
        return sweep

    compensated = tuple(
        (np.asarray(matrix, dtype=np.complex128) - diagonal) for matrix in sweep.y_matrices
    )
    return PortMatrixSweep(
        frequencies_ghz=sweep.frequencies_ghz,
        mode=sweep.mode,
        labels=sweep.labels,
        y_matrices=compensated,
        source_kind=sweep.source_kind,
    )


def compensate_simulation_result_port_terminations(
    result: SimulationResult,
    *,
    resistance_ohm_by_port: dict[int, float],
    reference_impedance_ohm: float = 50.0,
) -> SimulationResult:
    """Return one SimulationResult where selected port terminations are removed in Y-domain."""
    if not resistance_ohm_by_port:
        return result
    if reference_impedance_ohm <= 0:
        raise ValueError("reference_impedance_ohm must be positive.")
    if not result.frequencies_ghz:
        return result

    port_indices = list(result.available_port_indices)
    if not port_indices:
        return result

    mode_indices = list(result.available_mode_indices)
    if not mode_indices:
        mode_indices = [(0,)]

    # Start from existing families so modes without resolvable matrix traces remain intact.
    s_mode_real: dict[str, list[float]] = dict(result.s_parameter_mode_real)
    s_mode_imag: dict[str, list[float]] = dict(result.s_parameter_mode_imag)
    z_mode_real: dict[str, list[float]] = dict(result.z_parameter_mode_real)
    z_mode_imag: dict[str, list[float]] = dict(result.z_parameter_mode_imag)
    y_mode_real: dict[str, list[float]] = dict(result.y_parameter_mode_real)
    y_mode_imag: dict[str, list[float]] = dict(result.y_parameter_mode_imag)
    s_zero_mode_real: dict[str, list[float]] = dict(result.s_parameter_real)
    s_zero_mode_imag: dict[str, list[float]] = dict(result.s_parameter_imag)

    for mode in mode_indices:
        try:
            sweep = build_port_y_sweep(
                result=result,
                mode=mode,
                ports=port_indices,
                reference_impedance_ohm=reference_impedance_ohm,
            )
        except ValueError:
            continue
        compensated = apply_shunt_termination_compensation(
            sweep,
            resistance_ohm_by_port=resistance_ohm_by_port,
        )
        dimension = compensated.dimension
        identity = np.eye(dimension, dtype=np.complex128)
        y_matrices = [np.asarray(matrix, dtype=np.complex128) for matrix in compensated.y_matrices]
        z_matrices = [
            _safe_matrix_inverse(matrix, context="termination compensation Y->Z conversion")
            for matrix in y_matrices
        ]
        s_matrices = [
            np.linalg.solve(
                (z_matrix + (reference_impedance_ohm * identity)).T,
                (z_matrix - (reference_impedance_ohm * identity)).T,
            ).T
            for z_matrix in z_matrices
        ]

        for output_idx, output_port in enumerate(port_indices):
            for input_idx, input_port in enumerate(port_indices):
                trace_label = SimulationResult._mode_trace_label(
                    mode,
                    output_port,
                    mode,
                    input_port,
                )
                zero_label = f"S{output_port}{input_port}"
                s_trace = [complex(matrix[output_idx, input_idx]) for matrix in s_matrices]
                z_trace = [complex(matrix[output_idx, input_idx]) for matrix in z_matrices]
                y_trace = [complex(matrix[output_idx, input_idx]) for matrix in y_matrices]

                s_mode_real[trace_label] = [float(value.real) for value in s_trace]
                s_mode_imag[trace_label] = [float(value.imag) for value in s_trace]
                z_mode_real[trace_label] = [float(value.real) for value in z_trace]
                z_mode_imag[trace_label] = [float(value.imag) for value in z_trace]
                y_mode_real[trace_label] = [float(value.real) for value in y_trace]
                y_mode_imag[trace_label] = [float(value.imag) for value in y_trace]

                if all(value == 0 for value in mode):
                    s_zero_mode_real[zero_label] = list(s_mode_real[trace_label])
                    s_zero_mode_imag[zero_label] = list(s_mode_imag[trace_label])

    base_mode = next(
        (mode for mode in mode_indices if all(value == 0 for value in mode)),
        mode_indices[0],
    )
    first_port = int(port_indices[0])
    s11_label = SimulationResult._mode_trace_label(base_mode, first_port, base_mode, first_port)
    s11_real = list(s_mode_real.get(s11_label, result.s11_real))
    s11_imag = list(s_mode_imag.get(s11_label, result.s11_imag))

    return SimulationResult(
        frequencies_ghz=[float(value) for value in result.frequencies_ghz],
        s11_real=s11_real,
        s11_imag=s11_imag,
        port_indices=port_indices,
        mode_indices=[SimulationResult.normalize_mode(mode) for mode in mode_indices],
        s_parameter_real=s_zero_mode_real,
        s_parameter_imag=s_zero_mode_imag,
        s_parameter_mode_real=s_mode_real,
        s_parameter_mode_imag=s_mode_imag,
        z_parameter_mode_real=z_mode_real,
        z_parameter_mode_imag=z_mode_imag,
        y_parameter_mode_real=y_mode_real,
        y_parameter_mode_imag=y_mode_imag,
        qe_parameter_mode=dict(result.qe_parameter_mode),
        qe_ideal_parameter_mode=dict(result.qe_ideal_parameter_mode),
        cm_parameter_mode=dict(result.cm_parameter_mode),
    )


def filtered_modes(result: SimulationResult, mode_filter: ModeFilter) -> list[tuple[int, ...]]:
    """Return available modes filtered by mode family."""
    modes = result.available_mode_indices
    if mode_filter == "all":
        return modes
    if mode_filter == "base":
        return [mode for mode in modes if _is_base_mode(mode)]
    return [mode for mode in modes if not _is_base_mode(mode)]


def build_port_y_sweep(
    *,
    result: SimulationResult,
    mode: tuple[int, ...],
    ports: list[int] | None = None,
    reference_impedance_ohm: float = 50.0,
) -> PortMatrixSweep:
    """Build one port-space Y-matrix sweep for one selected mode tuple."""
    selected_mode = SimulationResult.normalize_mode(mode)
    selected_ports = sorted(set(ports or result.available_port_indices))
    if not selected_ports:
        raise ValueError("No ports are available for post-processing.")
    if reference_impedance_ohm <= 0:
        raise ValueError("Reference impedance must be positive.")

    labels = tuple(str(port) for port in selected_ports)
    freq_count = len(result.frequencies_ghz)
    if freq_count == 0:
        raise ValueError("Simulation result has no frequency points.")

    y_traces = _try_mode_matrix_from_family(
        result=result,
        mode=selected_mode,
        ports=selected_ports,
        family="y",
    )
    if y_traces is not None:
        matrices = _matrix_stack_from_traces(
            traces=y_traces,
            ports=selected_ports,
            frequency_count=freq_count,
        )
        return PortMatrixSweep(
            frequencies_ghz=tuple(float(value) for value in result.frequencies_ghz),
            mode=selected_mode,
            labels=labels,
            y_matrices=tuple(matrices),
            source_kind="y",
        )

    z_traces = _try_mode_matrix_from_family(
        result=result,
        mode=selected_mode,
        ports=selected_ports,
        family="z",
    )
    if z_traces is not None:
        z_matrices = _matrix_stack_from_traces(
            traces=z_traces,
            ports=selected_ports,
            frequency_count=freq_count,
        )
        y_matrices = tuple(
            _safe_matrix_inverse(matrix, context="Z->Y conversion") for matrix in z_matrices
        )
        return PortMatrixSweep(
            frequencies_ghz=tuple(float(value) for value in result.frequencies_ghz),
            mode=selected_mode,
            labels=labels,
            y_matrices=y_matrices,
            source_kind="z",
        )

    s_traces = _try_mode_matrix_from_family(
        result=result,
        mode=selected_mode,
        ports=selected_ports,
        family="s",
    )
    if s_traces is None:
        raise ValueError(
            "Mode-aware Y/Z/S matrix traces are unavailable for this mode/port selection."
        )

    s_matrices = _matrix_stack_from_traces(
        traces=s_traces,
        ports=selected_ports,
        frequency_count=freq_count,
    )
    y_matrices = tuple(
        _safe_matrix_inverse(
            _z_from_s(matrix, reference_impedance_ohm=reference_impedance_ohm),
            context="S->Z->Y conversion",
        )
        for matrix in s_matrices
    )
    return PortMatrixSweep(
        frequencies_ghz=tuple(float(value) for value in result.frequencies_ghz),
        mode=selected_mode,
        labels=labels,
        y_matrices=y_matrices,
        source_kind="s",
    )


def apply_coordinate_transform(
    sweep: PortMatrixSweep,
    transform_matrix: np.ndarray,
    *,
    labels: tuple[str, ...] | None = None,
) -> PortMatrixSweep:
    """Apply Y_m = A^{-T} Y A^{-1} to all frequency slices."""
    matrix_a = np.asarray(transform_matrix, dtype=np.complex128)
    if matrix_a.shape != (sweep.dimension, sweep.dimension):
        raise ValueError("Transform matrix shape does not match sweep dimension.")
    a_inverse = _safe_matrix_inverse(matrix_a, context="coordinate transform matrix")

    transformed = tuple(
        (a_inverse.T @ np.asarray(matrix, dtype=np.complex128) @ a_inverse)
        for matrix in sweep.y_matrices
    )
    return PortMatrixSweep(
        frequencies_ghz=sweep.frequencies_ghz,
        mode=sweep.mode,
        labels=labels or sweep.labels,
        y_matrices=transformed,
        source_kind=sweep.source_kind,
    )


def kron_reduce(
    sweep: PortMatrixSweep,
    *,
    keep_indices: list[int],
) -> PortMatrixSweep:
    """Apply Schur-complement Kron reduction on every frequency slice."""
    if not keep_indices:
        raise ValueError("Kron reduction requires at least one kept index.")

    dim = sweep.dimension
    normalized_keep = sorted(set(int(index) for index in keep_indices))
    if any(index < 0 or index >= dim for index in normalized_keep):
        raise ValueError("Kron keep indices out of range.")

    drop = [index for index in range(dim) if index not in normalized_keep]
    if not drop:
        return sweep

    reduced_matrices: list[np.ndarray] = []
    keep_array = np.asarray(normalized_keep, dtype=int)
    drop_array = np.asarray(drop, dtype=int)
    for matrix in sweep.y_matrices:
        y = np.asarray(matrix, dtype=np.complex128)
        y_bb = y[np.ix_(keep_array, keep_array)]
        y_bi = y[np.ix_(keep_array, drop_array)]
        y_ib = y[np.ix_(drop_array, keep_array)]
        y_ii = y[np.ix_(drop_array, drop_array)]
        reduced = y_bb - (y_bi @ np.linalg.solve(y_ii, y_ib))
        reduced_matrices.append(reduced)

    reduced_labels = tuple(sweep.labels[index] for index in normalized_keep)
    return PortMatrixSweep(
        frequencies_ghz=sweep.frequencies_ghz,
        mode=sweep.mode,
        labels=reduced_labels,
        y_matrices=tuple(reduced_matrices),
        source_kind=sweep.source_kind,
    )


def build_common_differential_transform(
    *,
    dimension: int,
    first_index: int,
    second_index: int,
    alpha: float,
    beta: float,
) -> np.ndarray:
    """Build an in-place cm/dm basis transform matrix."""
    if dimension < 2:
        raise ValueError("Common/differential transform requires at least 2 dimensions.")
    if first_index == second_index:
        raise ValueError("Common/differential transform requires two distinct indices.")
    if first_index < 0 or second_index < 0 or first_index >= dimension or second_index >= dimension:
        raise ValueError("Transform indices out of range.")
    if abs((alpha + beta) - 1.0) > 1e-6:
        raise ValueError("alpha + beta must equal 1.")

    matrix = np.eye(dimension, dtype=np.complex128)
    matrix[first_index, :] = 0.0
    matrix[first_index, first_index] = float(alpha)
    matrix[first_index, second_index] = float(beta)

    matrix[second_index, :] = 0.0
    matrix[second_index, first_index] = 1.0
    matrix[second_index, second_index] = -1.0
    return matrix


def _is_base_mode(mode: tuple[int, ...]) -> bool:
    return all(value == 0 for value in mode)


def _resistance_to_ohm(value: float, *, unit: str) -> float:
    normalized = str(unit).strip().replace(" ", "").casefold()
    if normalized not in _RESISTANCE_UNIT_MULTIPLIER:
        raise ValueError(f"Unsupported resistance unit for inference: {unit}")
    return float(value) * _RESISTANCE_UNIT_MULTIPLIER[normalized]


def _try_mode_matrix_from_family(
    *,
    result: SimulationResult,
    mode: tuple[int, ...],
    ports: list[int],
    family: Literal["y", "z", "s"],
) -> dict[tuple[int, int], list[complex]] | None:
    traces: dict[tuple[int, int], list[complex]] = {}
    getter = {
        "y": result.get_mode_y_parameter_complex,
        "z": result.get_mode_z_parameter_complex,
        "s": result.get_mode_s_parameter_complex,
    }[family]
    try:
        for output_port in ports:
            for input_port in ports:
                traces[(output_port, input_port)] = getter(
                    mode,
                    output_port,
                    mode,
                    input_port,
                )
    except KeyError:
        return None
    return traces


def _matrix_stack_from_traces(
    *,
    traces: dict[tuple[int, int], list[complex]],
    ports: list[int],
    frequency_count: int,
) -> list[np.ndarray]:
    matrices: list[np.ndarray] = []
    port_count = len(ports)
    for frequency_index in range(frequency_count):
        matrix = np.zeros((port_count, port_count), dtype=np.complex128)
        for output_row, output_port in enumerate(ports):
            for input_col, input_port in enumerate(ports):
                values = traces[(output_port, input_port)]
                if len(values) != frequency_count:
                    raise ValueError("Inconsistent trace length across matrix entries.")
                matrix[output_row, input_col] = values[frequency_index]
        matrices.append(matrix)
    return matrices


def _safe_matrix_inverse(matrix: np.ndarray, *, context: str) -> np.ndarray:
    try:
        identity = np.eye(matrix.shape[0], dtype=np.complex128)
        return np.linalg.solve(matrix, identity)
    except np.linalg.LinAlgError as exc:
        raise ValueError(f"Matrix inversion failed in {context}: {exc}") from exc


def _z_from_s(matrix_s: np.ndarray, *, reference_impedance_ohm: float) -> np.ndarray:
    identity = np.eye(matrix_s.shape[0], dtype=np.complex128)
    right_inverse = _safe_matrix_inverse(identity - matrix_s, context="S to Z conversion")
    return float(reference_impedance_ohm) * ((identity + matrix_s) @ right_inverse)
