"""Thesis-local Q3D capacitance to core simulation external-coupling workflow."""

from __future__ import annotations

import math
import re
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
from core.simulation.application.post_processing import (
    PortMatrixSweep,
    apply_coordinate_transform,
    apply_shunt_termination_compensation,
    build_common_differential_transform,
    build_port_y_sweep,
    kron_reduce,
)
from core.simulation.application.run_simulation import (
    run_simulation,
)
from core.simulation.domain.circuit import (
    CircuitDefinition,
    DriveSourceConfig,
    FrequencyRange,
    SimulationConfig,
    SimulationResult,
)

FEMTO = 1e-15
PICO = 1e-12
DEFAULT_TERMINAL_ORDER = ("Ground", "Pad1", "Pad2", "XY_Line")
DEFAULT_QUBITS = ("Q0", "Q1", "Q2")
DEFAULT_L_JUN_NH_VALUES = (5.0, 10.0, 15.0, 18.0, 20.0, 22.0, 24.0, 26.0, 28.0)
DEFAULT_SYNTHETIC_C_EFF_XY_FF_VALUES = (
    0.10,
    0.14,
    0.18,
    0.22,
    0.26,
    0.30,
    0.34,
    0.38,
    0.42,
)


@dataclass(frozen=True)
class Q3DCapacitanceMatrix:
    """Parsed Q3D Maxwell capacitance matrix in SI units."""

    source_path: Path
    source_unit: str
    terminal_order: tuple[str, ...]
    matrix_f: np.ndarray


@dataclass(frozen=True)
class FloatingXYCapacitances:
    """Capacitance quantities used by the floating-qubit XY model."""

    qubit: str
    source_path: Path
    source_unit: str
    terminal_order: tuple[str, ...]
    cap_matrix_f: np.ndarray
    c_g1_f: float
    c_g2_f: float
    c_q_f: float
    c_xy1_f: float
    c_xy2_f: float
    c_xy_ground_f: float
    alpha: float
    beta: float
    c_d_xy_f: float
    c_dd_f: float
    c_eff_q_f: float

    def summary_row(self, *, repo_root: Path | None = None) -> dict[str, Any]:
        """Return the thesis capacitance-table row."""
        source_path = self.source_path
        if repo_root is not None:
            try:
                source_path = source_path.relative_to(repo_root)
            except ValueError:
                source_path = Path(source_path)
        return {
            "qubit": self.qubit,
            "source_unit": self.source_unit,
            "c_g1_ff": self.c_g1_f / FEMTO,
            "c_g2_ff": self.c_g2_f / FEMTO,
            "c_q_ff": self.c_q_f / FEMTO,
            "c_xy1_ff": self.c_xy1_f / FEMTO,
            "c_xy2_ff": self.c_xy2_f / FEMTO,
            "c_xy_ground_ff": self.c_xy_ground_f / FEMTO,
            "alpha": self.alpha,
            "beta": self.beta,
            "c_d_xy_ff": self.c_d_xy_f / FEMTO,
            "c_dd_ff": self.c_dd_f / FEMTO,
            "c_eff_q_ff": self.c_eff_q_f / FEMTO,
            "source_path": source_path.as_posix(),
        }


@dataclass(frozen=True)
class ResonanceExtraction:
    """Zero-crossing extraction result with thesis diagnostics."""

    frequency_ghz: float
    re_y: float
    crossed: bool
    fallback: bool
    selected_index: int
    selected_crossing_index: int
    bracket_f0_ghz: float
    bracket_f1_ghz: float
    bracket_im_y0: float
    bracket_im_y1: float
    slope_im_y_per_ghz: float
    slope_sign: str


@dataclass(frozen=True)
class SweepProgressEvent:
    """Progress event emitted by the thesis-local Q3D+JC sweep runner."""

    stage: str
    message: str
    case_index: int
    case_total: int
    completed_cases: int
    qubit: str | None = None
    l_jun_nh: float | None = None

    @property
    def fraction(self) -> float:
        """Return completed case fraction."""
        if self.case_total <= 0:
            return 0.0
        return min(1.0, max(0.0, self.completed_cases / self.case_total))


@dataclass(frozen=True)
class Q3DXYReductionResult:
    """Post-processed admittance reduction output for one simulated case."""

    port_y_sweep: PortMatrixSweep
    compensated_sweep: PortMatrixSweep
    modal_sweep: PortMatrixSweep
    reduced_sweep: PortMatrixSweep
    y_eff_trace: np.ndarray
    resonance: ResonanceExtraction


@dataclass(frozen=True)
class Q3DXYSimulationCaseResult:
    """Full Q3D+JC result for one qubit and one Josephson inductance."""

    qubit: str
    l_jun_nh: float
    capacitances: FloatingXYCapacitances
    circuit: CircuitDefinition
    simulation_result: SimulationResult
    reduction: Q3DXYReductionResult
    sweep_start_ghz: float
    sweep_stop_ghz: float
    sweep_step_ghz: float

    @property
    def gamma_xy_per_s(self) -> float:
        """Return Gamma_XY = Re[Yeff] / Ceff,q."""
        return float(self.reduction.resonance.re_y / self.capacitances.c_eff_q_f)

    @property
    def t1_xy_s(self) -> float:
        """Return T1_XY in seconds, or NaN when the extracted decay rate is non-positive."""
        gamma = self.gamma_xy_per_s
        return float(1.0 / gamma) if gamma > 0 else float("nan")

    def observable_row(self) -> dict[str, Any]:
        """Return the thesis reduced-observable row."""
        resonance = self.reduction.resonance
        t1_xy_s = self.t1_xy_s
        return {
            "qubit": self.qubit,
            "l_jun_nh": self.l_jun_nh,
            "frequency_ghz": resonance.frequency_ghz,
            "re_y_eff_s": resonance.re_y,
            "c_eff_q_ff": self.capacitances.c_eff_q_f / FEMTO,
            "gamma_xy_per_s": self.gamma_xy_per_s,
            "t1_xy_s": t1_xy_s,
            "t1_xy_us": t1_xy_s * 1e6,
            "crossed": resonance.crossed,
            "fallback": resonance.fallback,
            "selected_index": resonance.selected_index,
            "selected_crossing_index": resonance.selected_crossing_index,
            "bracket_f0_ghz": resonance.bracket_f0_ghz,
            "bracket_f1_ghz": resonance.bracket_f1_ghz,
            "bracket_im_y0": resonance.bracket_im_y0,
            "bracket_im_y1": resonance.bracket_im_y1,
            "slope_im_y_per_ghz": resonance.slope_im_y_per_ghz,
            "slope_sign": resonance.slope_sign,
            "sweep_start_ghz": self.sweep_start_ghz,
            "sweep_stop_ghz": self.sweep_stop_ghz,
            "sweep_step_ghz": self.sweep_step_ghz,
        }

    def trace_rows(self) -> list[dict[str, Any]]:
        """Return reduced Yeff trace rows for this case."""
        return [
            {
                "qubit": self.qubit,
                "l_jun_nh": self.l_jun_nh,
                "frequency_ghz": float(freq_ghz),
                "re_y_eff_s": float(y_value.real),
                "im_y_eff_s": float(y_value.imag),
            }
            for freq_ghz, y_value in zip(
                self.reduction.reduced_sweep.frequencies_ghz,
                self.reduction.y_eff_trace,
                strict=True,
            )
        ]


@dataclass(frozen=True)
class Q3DXYSimulationSweepResult:
    """Rows and case outputs from a Q3D+JC parameter sweep."""

    capacitance_rows: list[dict[str, Any]]
    observable_rows: list[dict[str, Any]]
    trace_rows: list[dict[str, Any]]
    case_results: tuple[Q3DXYSimulationCaseResult, ...]


def parse_q3d_capacitance_matrix(
    path: str | Path,
    *,
    terminal_order: Sequence[str] = DEFAULT_TERMINAL_ORDER,
) -> Q3DCapacitanceMatrix:
    """Parse an Ansys Q3D ``capMatrix`` export into farads."""
    source_path = Path(path)
    text = source_path.read_text()
    unit_match = re.search(r"%C Units:\s*([^,\r\n]+)", text)
    if unit_match is None:
        raise ValueError(f"Missing Q3D C Units header in {source_path}.")

    source_unit = unit_match.group(1).strip()
    scale = _capacitance_unit_scale(source_unit)
    matrix_match = re.search(r"capMatrix\s*=\s*\[((?:.|\n)*?)\];", text)
    if matrix_match is None:
        raise ValueError(f"Missing capMatrix block in {source_path}.")

    rows: list[list[float]] = []
    for raw_line in matrix_match.group(1).splitlines():
        line = raw_line.strip().replace(";", "")
        if not line:
            continue
        row = [float(value.strip()) for value in line.split(",") if value.strip()]
        if row:
            rows.append(row)

    if not rows:
        raise ValueError(f"capMatrix block is empty in {source_path}.")
    expected_size = len(tuple(terminal_order))
    if any(len(row) != expected_size for row in rows) or len(rows) != expected_size:
        raise ValueError(
            f"Expected {expected_size}x{expected_size} capMatrix in {source_path}, "
            f"got {len(rows)}x{len(rows[0]) if rows else 0}."
        )

    matrix_f = np.asarray(rows, dtype=np.float64) * scale
    if not np.allclose(matrix_f, matrix_f.T, rtol=1e-8, atol=1e-21):
        raise ValueError(f"capMatrix is not symmetric within tolerance: {source_path}.")

    return Q3DCapacitanceMatrix(
        source_path=source_path,
        source_unit=source_unit,
        terminal_order=tuple(str(value) for value in terminal_order),
        matrix_f=matrix_f,
    )


def derive_floating_xy_capacitances(
    parsed: Q3DCapacitanceMatrix,
    *,
    qubit: str,
) -> FloatingXYCapacitances:
    """Derive floating-qubit branch capacitances from a Q3D Maxwell matrix."""
    index_by_terminal = {terminal: idx for idx, terminal in enumerate(parsed.terminal_order)}
    try:
        ground = index_by_terminal["Ground"]
        pad1 = index_by_terminal["Pad1"]
        pad2 = index_by_terminal["Pad2"]
        xy_line = index_by_terminal["XY_Line"]
    except KeyError as exc:
        raise ValueError(
            "Q3D terminal_order must include Ground, Pad1, Pad2, and XY_Line."
        ) from exc

    c = np.asarray(parsed.matrix_f, dtype=np.float64)
    c_g1 = _positive_branch(c, pad1, ground, "C_g1", qubit)
    c_g2 = _positive_branch(c, pad2, ground, "C_g2", qubit)
    c_q = _positive_branch(c, pad1, pad2, "C_q", qubit)
    c_xy1 = _positive_branch(c, pad1, xy_line, "C_xy1", qubit)
    c_xy2 = _positive_branch(c, pad2, xy_line, "C_xy2", qubit)
    c_xy_ground = -float(c[xy_line, ground])

    w1 = c_g1 + c_xy1
    w2 = c_g2 + c_xy2
    if w1 <= 0 or w2 <= 0:
        raise ValueError(f"Non-positive floating XY common-mode weights for {qubit}.")

    alpha = w1 / (w1 + w2)
    beta = w2 / (w1 + w2)
    c_d_xy = (c_g1 * c_xy2 - c_g2 * c_xy1) / (w1 + w2)
    c_dd = c_q + (w1 * w2) / (w1 + w2)
    c_eff_q = c_q + (c_g1 * c_g2) / (c_g1 + c_g2) + (c_xy1 * c_xy2) / (c_xy1 + c_xy2)

    return FloatingXYCapacitances(
        qubit=str(qubit),
        source_path=parsed.source_path,
        source_unit=parsed.source_unit,
        terminal_order=parsed.terminal_order,
        cap_matrix_f=c,
        c_g1_f=float(c_g1),
        c_g2_f=float(c_g2),
        c_q_f=float(c_q),
        c_xy1_f=float(c_xy1),
        c_xy2_f=float(c_xy2),
        c_xy_ground_f=float(c_xy_ground),
        alpha=float(alpha),
        beta=float(beta),
        c_d_xy_f=float(c_d_xy),
        c_dd_f=float(c_dd),
        c_eff_q_f=float(c_eff_q),
    )


def q3d_capacitance_path(raw_layout_dir: str | Path, qubit: str) -> Path:
    """Return the canonical PF6FQ Q3D capacitance-matrix path for one qubit."""
    return Path(raw_layout_dir) / str(qubit) / f"{qubit}_XY_Q3D_C_Matrix.m"


def load_floating_xy_capacitances(
    raw_layout_dir: str | Path,
    qubit: str,
    *,
    terminal_order: Sequence[str] = DEFAULT_TERMINAL_ORDER,
) -> FloatingXYCapacitances:
    """Load and derive the floating XY capacitance quantities for one qubit."""
    parsed = parse_q3d_capacitance_matrix(
        q3d_capacitance_path(raw_layout_dir, qubit),
        terminal_order=terminal_order,
    )
    return derive_floating_xy_capacitances(parsed, qubit=qubit)


def capacitance_summary_rows(
    raw_layout_dir: str | Path,
    qubits: Iterable[str] = DEFAULT_QUBITS,
    *,
    repo_root: str | Path | None = None,
    terminal_order: Sequence[str] = DEFAULT_TERMINAL_ORDER,
) -> list[dict[str, Any]]:
    """Build thesis capacitance-summary rows for the requested qubits."""
    resolved_repo_root = Path(repo_root) if repo_root is not None else None
    return [
        load_floating_xy_capacitances(
            raw_layout_dir,
            qubit,
            terminal_order=terminal_order,
        ).summary_row(repo_root=resolved_repo_root)
        for qubit in qubits
    ]


def build_q3d_xy_circuit_definition(
    capacitances: FloatingXYCapacitances,
    *,
    l_jun_nh: float = 24.0,
    reference_resistance_ohm: float = 50.0,
) -> CircuitDefinition:
    """Build the floating-qubit + XY-line circuit using the canonical core netlist."""
    return CircuitDefinition.model_validate(
        {
            "name": f"{capacitances.qubit} Q3D floating XY external coupling",
            "parameters": [
                {"name": "L_jun", "default": float(l_jun_nh), "unit": "nH"},
            ],
            "components": [
                {"name": "R50", "default": float(reference_resistance_ohm), "unit": "Ohm"},
                {"name": "Cg1", "default": capacitances.c_g1_f, "unit": "F"},
                {"name": "Cg2", "default": capacitances.c_g2_f, "unit": "F"},
                {"name": "Cq", "default": capacitances.c_q_f, "unit": "F"},
                {"name": "Cxy1", "default": capacitances.c_xy1_f, "unit": "F"},
                {"name": "Cxy2", "default": capacitances.c_xy2_f, "unit": "F"},
                {"name": "Lq1", "value_ref": "L_jun", "unit": "nH"},
                {"name": "Lq2", "value_ref": "L_jun", "unit": "nH"},
            ],
            "topology": [
                ("Cg1", "1", "0", "Cg1"),
                ("Cg2", "2", "0", "Cg2"),
                ("Cq", "1", "2", "Cq"),
                ("Lq1", "1", "2", "Lq1"),
                ("Lq2", "1", "2", "Lq2"),
                ("Cxy1", "1", "3", "Cxy1"),
                ("Cxy2", "2", "3", "Cxy2"),
                ("P1", "1", "0", 1),
                ("R1", "1", "0", "R50"),
                ("P2", "2", "0", 2),
                ("R2", "2", "0", "R50"),
                ("P3", "3", "0", 3),
                ("R3", "3", "0", "R50"),
            ],
        }
    )


def synthetic_c_eff_xy_target_range_ff(
    template: FloatingXYCapacitances,
    *,
    endpoint_margin_ff: float = 1e-6,
) -> tuple[float, float]:
    """Return feasible signed Ceff,xy range when only Cxy1/Cxy2 are redistributed."""
    c_xy_sum_f = template.c_xy1_f + template.c_xy2_f
    denominator = template.c_g1_f + template.c_g2_f + c_xy_sum_f
    min_f = -template.c_g2_f * c_xy_sum_f / denominator
    max_f = template.c_g1_f * c_xy_sum_f / denominator
    margin_f = abs(float(endpoint_margin_ff)) * FEMTO
    return (float((min_f + margin_f) / FEMTO), float((max_f - margin_f) / FEMTO))


def build_synthetic_c_eff_xy_capacitances(
    template: FloatingXYCapacitances,
    *,
    target_c_eff_xy_ff_values: Sequence[float],
    synthetic_prefix: str = "S",
) -> list[FloatingXYCapacitances]:
    """Build synthetic capacitance definitions by sweeping the floating XY coupling."""
    synthetic_capacitances: list[FloatingXYCapacitances] = []
    for index, target_ff in enumerate(target_c_eff_xy_ff_values):
        synthetic_id = f"{synthetic_prefix}{index:02d}"
        synthetic_capacitances.append(
            build_synthetic_c_eff_xy_capacitance(
                template,
                target_c_eff_xy_ff=float(target_ff),
                synthetic_id=synthetic_id,
            )
        )
    return synthetic_capacitances


def build_synthetic_c_eff_xy_capacitance(
    template: FloatingXYCapacitances,
    *,
    target_c_eff_xy_ff: float,
    synthetic_id: str,
) -> FloatingXYCapacitances:
    """Redistribute Cxy1/Cxy2 to realize one target signed floating Ceff,xy."""
    c_d_xy_f = float(target_c_eff_xy_ff) * FEMTO
    c_xy_sum_f = template.c_xy1_f + template.c_xy2_f
    denominator = template.c_g1_f + template.c_g2_f + c_xy_sum_f
    c_xy1_f = (
        template.c_g1_f * c_xy_sum_f - c_d_xy_f * denominator
    ) / (template.c_g1_f + template.c_g2_f)
    c_xy2_f = c_xy_sum_f - c_xy1_f
    if c_xy1_f <= 0.0 or c_xy2_f <= 0.0:
        min_ff, max_ff = synthetic_c_eff_xy_target_range_ff(template)
        raise ValueError(
            f"Target Ceff,xy={target_c_eff_xy_ff:g} fF is outside the positive "
            f"Cxy1/Cxy2 range ({min_ff:g}, {max_ff:g}) fF."
        )
    return _clone_capacitances_with_xy_coupling(
        template,
        qubit=str(synthetic_id),
        c_xy1_f=float(c_xy1_f),
        c_xy2_f=float(c_xy2_f),
    )


def build_frequency_range_from_step(
    *,
    start_ghz: float,
    stop_ghz: float,
    step_ghz: float,
) -> FrequencyRange:
    """Build a FrequencyRange whose inclusive grid matches a requested step."""
    if step_ghz <= 0:
        raise ValueError("step_ghz must be positive.")
    if stop_ghz <= start_ghz:
        raise ValueError("stop_ghz must be greater than start_ghz.")

    intervals = (float(stop_ghz) - float(start_ghz)) / float(step_ghz)
    rounded_intervals = round(intervals)
    if not math.isclose(intervals, rounded_intervals, rel_tol=1e-9, abs_tol=1e-9):
        raise ValueError("Frequency span must be an integer multiple of step_ghz.")
    return FrequencyRange(
        start_ghz=float(start_ghz),
        stop_ghz=float(stop_ghz),
        points=int(rounded_intervals) + 1,
    )


def build_q3d_xy_simulation_config(
    *,
    pump_freq_ghz: float = 8.001,
    source_port: int = 1,
    source_current_amp: float = 0.0,
    source_mode: tuple[int, ...] = (1,),
    n_modulation_harmonics: int = 10,
    n_pump_harmonics: int = 20,
) -> SimulationConfig:
    """Build the JosephsonCircuits solver config used by the thesis XY workflow."""
    return SimulationConfig(
        pump_freq_ghz=float(pump_freq_ghz),
        pump_port=int(source_port),
        pump_current_amp=float(source_current_amp),
        n_modulation_harmonics=int(n_modulation_harmonics),
        n_pump_harmonics=int(n_pump_harmonics),
        sources=[
            DriveSourceConfig(
                pump_freq_ghz=float(pump_freq_ghz),
                port=int(source_port),
                current_amp=float(source_current_amp),
                mode_components=tuple(int(value) for value in source_mode),
            )
        ],
    )


def reduce_q3d_xy_admittance(
    *,
    result: SimulationResult,
    capacitances: FloatingXYCapacitances,
    mode: tuple[int, ...] = (0,),
    ports: Sequence[int] = (1, 2, 3),
    ptc_resistance_ohm_by_port: dict[int, float] | None = None,
    reference_impedance_ohm: float = 50.0,
) -> Q3DXYReductionResult:
    """Apply PTC, weighted common/differential CT, and Kron reduction to Yeff."""
    selected_ports = [int(port) for port in ports]
    port_y_sweep = build_port_y_sweep(
        result=result,
        mode=mode,
        ports=selected_ports,
        reference_impedance_ohm=reference_impedance_ohm,
    )
    compensated = apply_shunt_termination_compensation(
        port_y_sweep,
        resistance_ohm_by_port=ptc_resistance_ohm_by_port or {1: 50.0, 2: 50.0},
    )

    labels = list(compensated.labels)
    pad1_index = labels.index("1")
    pad2_index = labels.index("2")
    xy_index = labels.index("3")
    transform = build_common_differential_transform(
        dimension=compensated.dimension,
        first_index=pad1_index,
        second_index=pad2_index,
        alpha=capacitances.alpha,
        beta=capacitances.beta,
    )
    transformed_labels = list(labels)
    transformed_labels[pad1_index] = "cm(Pad1,Pad2)"
    transformed_labels[pad2_index] = "dm(Pad1,Pad2)"
    transformed_labels[xy_index] = "XY_Line"
    modal = apply_coordinate_transform(
        compensated,
        transform_matrix=transform,
        labels=tuple(transformed_labels),
    )
    reduced = kron_reduce(modal, keep_indices=[pad2_index])
    y_eff_trace = np.asarray([matrix[0, 0] for matrix in reduced.y_matrices], dtype=np.complex128)
    resonance = extract_reduced_admittance_resonance(
        reduced.frequencies_ghz,
        y_eff_trace,
    )
    return Q3DXYReductionResult(
        port_y_sweep=port_y_sweep,
        compensated_sweep=compensated,
        modal_sweep=modal,
        reduced_sweep=reduced,
        y_eff_trace=y_eff_trace,
        resonance=resonance,
    )


def extract_reduced_admittance_resonance(
    frequencies_ghz: Sequence[float],
    y_eff_trace: Sequence[complex],
) -> ResonanceExtraction:
    """Extract the first robust Im[Yeff]=0 crossing with diagnostics."""
    freqs = np.asarray(frequencies_ghz, dtype=np.float64)
    y_values = np.asarray(y_eff_trace, dtype=np.complex128)
    if freqs.ndim != 1 or y_values.ndim != 1 or len(freqs) != len(y_values):
        raise ValueError("frequencies_ghz and y_eff_trace must be one-dimensional peers.")
    if len(freqs) < 2:
        raise ValueError("At least two frequency samples are required.")

    imag_y = np.imag(y_values)
    real_y = np.real(y_values)
    crossing_pairs: list[tuple[int, int]] = []

    for idx in range(len(freqs) - 1):
        im0 = float(imag_y[idx])
        im1 = float(imag_y[idx + 1])
        if not (np.isfinite(im0) and np.isfinite(im1)):
            continue
        if im0 == 0.0:
            return ResonanceExtraction(
                frequency_ghz=float(freqs[idx]),
                re_y=float(real_y[idx]),
                crossed=True,
                fallback=False,
                selected_index=idx + 1,
                selected_crossing_index=1,
                bracket_f0_ghz=float(freqs[idx]),
                bracket_f1_ghz=float(freqs[idx]),
                bracket_im_y0=im0,
                bracket_im_y1=im0,
                slope_im_y_per_ghz=float("nan"),
                slope_sign="zero_sample",
            )
        if im0 * im1 < 0.0:
            crossing_pairs.append((idx, idx + 1))

    if crossing_pairs:
        scores = [abs(imag_y[left]) + abs(imag_y[right]) for left, right in crossing_pairs]
        selected_zero_based = int(np.argmin(scores))
        left, right = crossing_pairs[selected_zero_based]
        f0 = float(freqs[left])
        f1 = float(freqs[right])
        im0 = float(imag_y[left])
        im1 = float(imag_y[right])
        re0 = float(real_y[left])
        re1 = float(real_y[right])
        t = -im0 / (im1 - im0)
        slope = (im1 - im0) / (f1 - f0)
        return ResonanceExtraction(
            frequency_ghz=float(f0 + t * (f1 - f0)),
            re_y=float(re0 + t * (re1 - re0)),
            crossed=True,
            fallback=False,
            selected_index=left + 1,
            selected_crossing_index=selected_zero_based + 1,
            bracket_f0_ghz=f0,
            bracket_f1_ghz=f1,
            bracket_im_y0=im0,
            bracket_im_y1=im1,
            slope_im_y_per_ghz=float(slope),
            slope_sign="positive" if slope > 0 else "negative",
        )

    finite_indices = np.flatnonzero(np.isfinite(imag_y))
    if len(finite_indices) == 0:
        raise ValueError("No finite Im[Yeff] samples are available for extraction.")
    selected = int(finite_indices[np.argmin(np.abs(imag_y[finite_indices]))])
    return ResonanceExtraction(
        frequency_ghz=float(freqs[selected]),
        re_y=float(real_y[selected]),
        crossed=False,
        fallback=True,
        selected_index=selected + 1,
        selected_crossing_index=0,
        bracket_f0_ghz=float("nan"),
        bracket_f1_ghz=float("nan"),
        bracket_im_y0=float("nan"),
        bracket_im_y1=float("nan"),
        slope_im_y_per_ghz=float("nan"),
        slope_sign="fallback_min_abs_im",
    )


def run_q3d_xy_simulation_case(
    *,
    capacitances: FloatingXYCapacitances,
    l_jun_nh: float,
    sweep_start_ghz: float,
    sweep_stop_ghz: float,
    sweep_step_ghz: float,
    pump_freq_ghz: float = 8.001,
    source_current_amp: float = 0.0,
    n_modulation_harmonics: int = 10,
    n_pump_harmonics: int = 20,
    ptc_resistance_ohm_by_port: dict[int, float] | None = None,
    reference_impedance_ohm: float = 50.0,
) -> Q3DXYSimulationCaseResult:
    """Run one Q3D+JosephsonCircuits XY external-coupling case."""
    circuit = build_q3d_xy_circuit_definition(
        capacitances,
        l_jun_nh=float(l_jun_nh),
        reference_resistance_ohm=reference_impedance_ohm,
    )
    freq_range = build_frequency_range_from_step(
        start_ghz=sweep_start_ghz,
        stop_ghz=sweep_stop_ghz,
        step_ghz=sweep_step_ghz,
    )
    config = build_q3d_xy_simulation_config(
        pump_freq_ghz=pump_freq_ghz,
        source_current_amp=source_current_amp,
        n_modulation_harmonics=n_modulation_harmonics,
        n_pump_harmonics=n_pump_harmonics,
    )
    simulation_result = run_simulation(circuit, freq_range, config)
    reduction = reduce_q3d_xy_admittance(
        result=simulation_result,
        capacitances=capacitances,
        ptc_resistance_ohm_by_port=ptc_resistance_ohm_by_port,
        reference_impedance_ohm=reference_impedance_ohm,
    )
    return Q3DXYSimulationCaseResult(
        qubit=capacitances.qubit,
        l_jun_nh=float(l_jun_nh),
        capacitances=capacitances,
        circuit=circuit,
        simulation_result=simulation_result,
        reduction=reduction,
        sweep_start_ghz=float(sweep_start_ghz),
        sweep_stop_ghz=float(sweep_stop_ghz),
        sweep_step_ghz=float(sweep_step_ghz),
    )


def run_q3d_xy_simulation_sweep(
    *,
    raw_layout_dir: str | Path,
    qubits: Sequence[str],
    l_jun_nh_values: Sequence[float],
    sweep_start_ghz: float,
    sweep_stop_ghz: float,
    sweep_step_ghz: float,
    capacitance_summary_qubits: Sequence[str] | None = DEFAULT_QUBITS,
    repo_root: str | Path | None = None,
    pump_freq_ghz: float = 8.001,
    source_current_amp: float = 0.0,
    n_modulation_harmonics: int = 10,
    n_pump_harmonics: int = 20,
    ptc_resistance_ohm_by_port: dict[int, float] | None = None,
    reference_impedance_ohm: float = 50.0,
    progress: Callable[[SweepProgressEvent], None] | None = None,
) -> Q3DXYSimulationSweepResult:
    """Run a Q3D+JC sweep over qubits and Josephson inductance values."""
    if not l_jun_nh_values:
        raise ValueError("l_jun_nh_values must contain at least one value.")

    raw_dir = Path(raw_layout_dir)
    resolved_repo_root = Path(repo_root) if repo_root is not None else None
    cap_qubits = tuple(capacitance_summary_qubits or qubits)
    l_jun_values = tuple(float(value) for value in l_jun_nh_values)
    case_total = len(qubits) * len(l_jun_values)
    capacitance_rows_result = capacitance_summary_rows(
        raw_dir,
        cap_qubits,
        repo_root=resolved_repo_root,
    )

    observable_rows: list[dict[str, Any]] = []
    trace_rows: list[dict[str, Any]] = []
    case_results: list[Q3DXYSimulationCaseResult] = []
    freq_range = build_frequency_range_from_step(
        start_ghz=sweep_start_ghz,
        stop_ghz=sweep_stop_ghz,
        step_ghz=sweep_step_ghz,
    )
    config = build_q3d_xy_simulation_config(
        pump_freq_ghz=pump_freq_ghz,
        source_current_amp=source_current_amp,
        n_modulation_harmonics=n_modulation_harmonics,
        n_pump_harmonics=n_pump_harmonics,
    )

    case_index = 0
    for qubit in qubits:
        _emit_progress(
            progress,
            SweepProgressEvent(
                stage="load_capacitance",
                message=f"Loading Q3D capacitance for {qubit}",
                case_index=min(case_index + 1, case_total),
                case_total=case_total,
                completed_cases=case_index,
                qubit=qubit,
            ),
        )
        capacitances = load_floating_xy_capacitances(raw_dir, qubit)
        for l_jun_nh in l_jun_values:
            case_index += 1
            _emit_progress(
                progress,
                SweepProgressEvent(
                    stage="build_circuit",
                    message=f"Building circuit for {qubit}, L_jun={l_jun_nh:.1f} nH",
                    case_index=case_index,
                    case_total=case_total,
                    completed_cases=case_index - 1,
                    qubit=qubit,
                    l_jun_nh=l_jun_nh,
                ),
            )
            circuit = build_q3d_xy_circuit_definition(
                capacitances,
                l_jun_nh=l_jun_nh,
                reference_resistance_ohm=reference_impedance_ohm,
            )
            _emit_progress(
                progress,
                SweepProgressEvent(
                    stage="simulate",
                    message=f"Simulating {qubit}, L_jun={l_jun_nh:.1f} nH",
                    case_index=case_index,
                    case_total=case_total,
                    completed_cases=case_index - 1,
                    qubit=qubit,
                    l_jun_nh=l_jun_nh,
                ),
            )
            simulation_result = run_simulation(circuit, freq_range, config)
            _emit_progress(
                progress,
                SweepProgressEvent(
                    stage="reduce_admittance",
                    message=f"Reducing admittance for {qubit}, L_jun={l_jun_nh:.1f} nH",
                    case_index=case_index,
                    case_total=case_total,
                    completed_cases=case_index - 1,
                    qubit=qubit,
                    l_jun_nh=l_jun_nh,
                ),
            )
            reduction = reduce_q3d_xy_admittance(
                result=simulation_result,
                capacitances=capacitances,
                ptc_resistance_ohm_by_port=ptc_resistance_ohm_by_port,
                reference_impedance_ohm=reference_impedance_ohm,
            )
            _emit_progress(
                progress,
                SweepProgressEvent(
                    stage="collect_rows",
                    message=f"Collecting rows for {qubit}, L_jun={l_jun_nh:.1f} nH",
                    case_index=case_index,
                    case_total=case_total,
                    completed_cases=case_index,
                    qubit=qubit,
                    l_jun_nh=l_jun_nh,
                ),
            )
            case_result = Q3DXYSimulationCaseResult(
                qubit=qubit,
                l_jun_nh=l_jun_nh,
                capacitances=capacitances,
                circuit=circuit,
                simulation_result=simulation_result,
                reduction=reduction,
                sweep_start_ghz=float(sweep_start_ghz),
                sweep_stop_ghz=float(sweep_stop_ghz),
                sweep_step_ghz=float(sweep_step_ghz),
            )
            case_results.append(case_result)
            observable_rows.append(case_result.observable_row())
            trace_rows.extend(case_result.trace_rows())

    return Q3DXYSimulationSweepResult(
        capacitance_rows=capacitance_rows_result,
        observable_rows=observable_rows,
        trace_rows=trace_rows,
        case_results=tuple(case_results),
    )


def run_synthetic_c_eff_xy_simulation_sweep(
    *,
    template: FloatingXYCapacitances,
    target_c_eff_xy_ff_values: Sequence[float],
    l_jun_nh_values: Sequence[float],
    sweep_start_ghz: float,
    sweep_stop_ghz: float,
    sweep_step_ghz: float,
    pump_freq_ghz: float = 8.001,
    source_current_amp: float = 0.0,
    n_modulation_harmonics: int = 10,
    n_pump_harmonics: int = 20,
    ptc_resistance_ohm_by_port: dict[int, float] | None = None,
    reference_impedance_ohm: float = 50.0,
    progress: Callable[[SweepProgressEvent], None] | None = None,
) -> Q3DXYSimulationSweepResult:
    """Run a synthetic Circuit-only Ceff,xy sweep through the same Q3D+JC pipeline."""
    if len(target_c_eff_xy_ff_values) == 0:
        raise ValueError("target_c_eff_xy_ff_values must contain at least one value.")
    if len(l_jun_nh_values) == 0:
        raise ValueError("l_jun_nh_values must contain at least one value.")

    synthetic_capacitances = build_synthetic_c_eff_xy_capacitances(
        template,
        target_c_eff_xy_ff_values=target_c_eff_xy_ff_values,
    )
    l_jun_values = tuple(float(value) for value in l_jun_nh_values)
    case_total = len(synthetic_capacitances) * len(l_jun_values)
    capacitance_rows_result = [
        _synthetic_capacitance_summary_row(
            capacitances,
            template_qubit=template.qubit,
            target_c_eff_xy_ff=float(target_value),
        )
        for capacitances, target_value in zip(
            synthetic_capacitances,
            target_c_eff_xy_ff_values,
            strict=True,
        )
    ]

    observable_rows: list[dict[str, Any]] = []
    trace_rows: list[dict[str, Any]] = []
    case_results: list[Q3DXYSimulationCaseResult] = []
    case_index = 0
    for capacitances, target_value in zip(
        synthetic_capacitances,
        target_c_eff_xy_ff_values,
        strict=True,
    ):
        for l_jun_nh in l_jun_values:
            case_index += 1
            _emit_progress(
                progress,
                SweepProgressEvent(
                    stage="simulate_synthetic",
                    message=(
                        f"Simulating {capacitances.qubit}, "
                        f"Ceff,xy={float(target_value):.3f} fF, "
                        f"L_jun={l_jun_nh:.1f} nH"
                    ),
                    case_index=case_index,
                    case_total=case_total,
                    completed_cases=case_index - 1,
                    qubit=capacitances.qubit,
                    l_jun_nh=l_jun_nh,
                ),
            )
            case_result = run_q3d_xy_simulation_case(
                capacitances=capacitances,
                l_jun_nh=l_jun_nh,
                sweep_start_ghz=sweep_start_ghz,
                sweep_stop_ghz=sweep_stop_ghz,
                sweep_step_ghz=sweep_step_ghz,
                pump_freq_ghz=pump_freq_ghz,
                source_current_amp=source_current_amp,
                n_modulation_harmonics=n_modulation_harmonics,
                n_pump_harmonics=n_pump_harmonics,
                ptc_resistance_ohm_by_port=ptc_resistance_ohm_by_port,
                reference_impedance_ohm=reference_impedance_ohm,
            )
            case_results.append(case_result)
            metadata = _synthetic_case_metadata(
                capacitances,
                template_qubit=template.qubit,
                target_c_eff_xy_ff=float(target_value),
            )
            observable_row = case_result.observable_row()
            observable_row.update(metadata)
            observable_rows.append(observable_row)
            for trace_row in case_result.trace_rows():
                trace_row.update(metadata)
                trace_rows.append(trace_row)
            _emit_progress(
                progress,
                SweepProgressEvent(
                    stage="collect_synthetic_rows",
                    message=f"Collected {capacitances.qubit}, L_jun={l_jun_nh:.1f} nH",
                    case_index=case_index,
                    case_total=case_total,
                    completed_cases=case_index,
                    qubit=capacitances.qubit,
                    l_jun_nh=l_jun_nh,
                ),
            )

    return Q3DXYSimulationSweepResult(
        capacitance_rows=capacitance_rows_result,
        observable_rows=observable_rows,
        trace_rows=trace_rows,
        case_results=tuple(case_results),
    )


def _capacitance_unit_scale(unit: str) -> float:
    normalized = unit.strip().lower()
    if normalized == "ff":
        return FEMTO
    if normalized == "pf":
        return PICO
    if normalized == "f":
        return 1.0
    raise ValueError(f"Unsupported Q3D capacitance unit: {unit}")


def _emit_progress(
    progress: Callable[[SweepProgressEvent], None] | None,
    event: SweepProgressEvent,
) -> None:
    if progress is not None:
        progress(event)


def _positive_branch(
    matrix_f: np.ndarray,
    row: int,
    col: int,
    name: str,
    qubit: str,
) -> float:
    value = -float(matrix_f[row, col])
    if value <= 0:
        raise ValueError(f"Non-positive {name} for {qubit}.")
    return value


def _clone_capacitances_with_xy_coupling(
    template: FloatingXYCapacitances,
    *,
    qubit: str,
    c_xy1_f: float,
    c_xy2_f: float,
) -> FloatingXYCapacitances:
    w1 = template.c_g1_f + c_xy1_f
    w2 = template.c_g2_f + c_xy2_f
    if w1 <= 0.0 or w2 <= 0.0:
        raise ValueError(f"Non-positive synthetic floating XY common-mode weights for {qubit}.")
    alpha = w1 / (w1 + w2)
    beta = w2 / (w1 + w2)
    c_d_xy = (template.c_g1_f * c_xy2_f - template.c_g2_f * c_xy1_f) / (w1 + w2)
    c_dd = template.c_q_f + (w1 * w2) / (w1 + w2)
    c_eff_q = (
        template.c_q_f
        + (template.c_g1_f * template.c_g2_f) / (template.c_g1_f + template.c_g2_f)
        + (c_xy1_f * c_xy2_f) / (c_xy1_f + c_xy2_f)
    )
    cap_matrix_f = _synthetic_cap_matrix(template, c_xy1_f=c_xy1_f, c_xy2_f=c_xy2_f)
    return FloatingXYCapacitances(
        qubit=qubit,
        source_path=template.source_path,
        source_unit=template.source_unit,
        terminal_order=template.terminal_order,
        cap_matrix_f=cap_matrix_f,
        c_g1_f=template.c_g1_f,
        c_g2_f=template.c_g2_f,
        c_q_f=template.c_q_f,
        c_xy1_f=float(c_xy1_f),
        c_xy2_f=float(c_xy2_f),
        c_xy_ground_f=template.c_xy_ground_f,
        alpha=float(alpha),
        beta=float(beta),
        c_d_xy_f=float(c_d_xy),
        c_dd_f=float(c_dd),
        c_eff_q_f=float(c_eff_q),
    )


def _synthetic_cap_matrix(
    template: FloatingXYCapacitances,
    *,
    c_xy1_f: float,
    c_xy2_f: float,
) -> np.ndarray:
    matrix = np.asarray(template.cap_matrix_f, dtype=np.float64).copy()
    index_by_terminal = {terminal: idx for idx, terminal in enumerate(template.terminal_order)}
    pad1 = index_by_terminal["Pad1"]
    pad2 = index_by_terminal["Pad2"]
    xy_line = index_by_terminal["XY_Line"]
    matrix[pad1, xy_line] = -float(c_xy1_f)
    matrix[xy_line, pad1] = -float(c_xy1_f)
    matrix[pad2, xy_line] = -float(c_xy2_f)
    matrix[xy_line, pad2] = -float(c_xy2_f)
    return matrix


def _synthetic_capacitance_summary_row(
    capacitances: FloatingXYCapacitances,
    *,
    template_qubit: str,
    target_c_eff_xy_ff: float,
) -> dict[str, Any]:
    row = capacitances.summary_row()
    row.update(
        _synthetic_case_metadata(
            capacitances,
            template_qubit=template_qubit,
            target_c_eff_xy_ff=target_c_eff_xy_ff,
        )
    )
    return row


def _synthetic_case_metadata(
    capacitances: FloatingXYCapacitances,
    *,
    template_qubit: str,
    target_c_eff_xy_ff: float,
) -> dict[str, Any]:
    return {
        "template_qubit": str(template_qubit),
        "target_c_eff_xy_ff": float(target_c_eff_xy_ff),
        "synthetic_c_eff_xy_ff": capacitances.c_d_xy_f / FEMTO,
        "synthetic_c_xy_sum_ff": (capacitances.c_xy1_f + capacitances.c_xy2_f) / FEMTO,
    }
