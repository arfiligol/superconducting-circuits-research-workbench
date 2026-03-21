"""Validation and preparation helpers for simulation submit flows."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from legacy.legacy_nicegui_archived.features.simulation.setup.parameter_sweep import (
    _SWEEP_MAX_CARTESIAN_POINTS,
    _estimate_sweep_cartesian_point_count,
    _extract_sweep_target_units,
    _normalize_sweep_setup_payload,
)
from legacy.legacy_nicegui_archived.features.simulation.setup.sources import (
    _detect_harmonic_grid_coincidences,
    _estimate_mode_lattice_size,
    _extract_available_port_indices,
    _normalize_source_mode_components,
    _parse_source_mode_text,
)
from legacy.legacy_nicegui_archived.features.simulation.setup.frequency_sweep import _normalized_simulation_setup_snapshot
from legacy.legacy_nicegui_archived.features.simulation.submit.request_builders import hash_schema_source, hash_stable_json
from core.shared.persistence.models import CircuitRecord
from core.simulation.application.run_simulation import (
    SimulationSweepAxis,
    SimulationSweepPlan,
    build_linear_sweep_values,
    build_simulation_sweep_plan,
    simulation_sweep_setup_snapshot,
)
from core.simulation.domain.circuit import (
    CircuitDefinition,
    DriveSourceConfig,
    FrequencyRange,
    SimulationConfig,
)


@dataclass(frozen=True)
class SourceFormPayload:
    """Normalized one-row source form payload for simulation submit."""

    pump_freq_ghz: float | None
    port: int | None
    current_amp: float | None
    mode_text: str | None


@dataclass(frozen=True)
class PreparedSimulationRun:
    """Validated simulation submit payload assembled from the UI form state."""

    freq_range: FrequencyRange
    sources: list[DriveSourceConfig]
    config: SimulationConfig
    sweep_setup_payload: dict[str, Any]
    sweep_plan: SimulationSweepPlan | None
    sweep_mode: str
    sweep_snapshot: dict[str, Any] | None
    sweep_setup_hash: str | None
    harmonic_grid_hits: list[Any]
    estimated_mode_lattice: int
    setup_snapshot: dict[str, Any]
    schema_source_hash: str
    simulation_setup_hash: str
    warnings: list[str]


def prepare_simulation_run(
    *,
    latest_record: CircuitRecord,
    latest_circuit_def: CircuitDefinition,
    start_ghz: float | None,
    stop_ghz: float | None,
    points: int | None,
    n_modulation_harmonics: int | None,
    n_pump_harmonics: int | None,
    include_dc: bool,
    enable_three_wave_mixing: bool,
    enable_four_wave_mixing: bool,
    max_intermod_order_raw: int | None,
    max_iterations: int | None,
    f_tol: float | None,
    line_search_switch_tol: float | None,
    alpha_min: float | None,
    source_rows: Sequence[SourceFormPayload],
    raw_sweep_setup_payload: Mapping[str, Any] | None,
) -> PreparedSimulationRun:
    """Validate one simulation run form and build the canonical submit inputs."""
    required_values = [
        start_ghz,
        stop_ghz,
        points,
        n_modulation_harmonics,
        n_pump_harmonics,
        max_intermod_order_raw,
        max_iterations,
        f_tol,
        line_search_switch_tol,
        alpha_min,
    ]
    if any(value is None for value in required_values):
        raise ValueError("Please fill all simulation parameters.")

    freq_range = FrequencyRange(
        start_ghz=float(start_ghz),
        stop_ghz=float(stop_ghz),
        points=int(points),
    )
    if freq_range.points < 2:
        raise ValueError("Points must be >= 2.")

    if not source_rows:
        raise ValueError("At least one source is required.")

    sources: list[DriveSourceConfig] = []
    for idx, source_row in enumerate(source_rows, start=1):
        if (
            source_row.pump_freq_ghz is None
            or source_row.port is None
            or source_row.current_amp is None
        ):
            raise ValueError(f"Source {idx} has missing parameters.")
        try:
            parsed_mode = _parse_source_mode_text(source_row.mode_text)
        except ValueError as exc:
            raise ValueError(
                f"Source {idx} has an invalid mode tuple. Use comma-separated integers."
            ) from exc
        normalized_mode = _normalize_source_mode_components(
            parsed_mode,
            source_index=idx - 1,
            source_count=len(source_rows),
        )
        sources.append(
            DriveSourceConfig(
                pump_freq_ghz=float(source_row.pump_freq_ghz),
                port=int(source_row.port),
                current_amp=float(source_row.current_amp),
                mode_components=normalized_mode,
            )
        )

    available_ports = _extract_available_port_indices(latest_circuit_def)
    if available_ports:
        invalid_sources = [source for source in sources if source.port not in available_ports]
        if invalid_sources:
            valid_ports = ", ".join(str(p) for p in sorted(available_ports))
            raise ValueError(f"Source port mismatch. Schema ports: {valid_ports}.")

    max_intermod_order = (
        None
        if int(max_intermod_order_raw or 0) < 0
        else int(max_intermod_order_raw)
    )
    config = SimulationConfig(
        pump_freq_ghz=float(sources[0].pump_freq_ghz),
        sources=sources,
        pump_current_amp=float(sources[0].current_amp),
        pump_port=int(sources[0].port),
        pump_mode_index=1,
        n_modulation_harmonics=int(n_modulation_harmonics),
        n_pump_harmonics=int(n_pump_harmonics),
        include_dc=bool(include_dc),
        enable_three_wave_mixing=bool(enable_three_wave_mixing),
        enable_four_wave_mixing=bool(enable_four_wave_mixing),
        max_intermod_order=max_intermod_order,
        max_iterations=int(max_iterations),
        f_tol=float(f_tol),
        line_search_switch_tol=float(line_search_switch_tol),
        alpha_min=float(alpha_min),
    )

    sweep_target_units_latest = _extract_sweep_target_units(
        latest_circuit_def,
        config=config,
    )
    if raw_sweep_setup_payload is None:
        raise ValueError("Sweep setup is invalid. Please check axis inputs.")
    sweep_setup_payload = _normalize_sweep_setup_payload(
        raw_sweep_setup_payload,
        available_target_units=sweep_target_units_latest,
    )
    sweep_enabled = bool(sweep_setup_payload.get("enabled", False))
    sweep_plan: SimulationSweepPlan | None = None
    sweep_snapshot: dict[str, Any] | None = None
    sweep_setup_hash: str | None = None
    warnings: list[str] = []
    sweep_mode = str(sweep_setup_payload.get("mode", "cartesian"))

    if sweep_enabled:
        if sweep_mode != "cartesian":
            warnings.append(
                "Sweep mode 'paired' is reserved. Current run falls back to cartesian expansion."
            )
            sweep_mode = "cartesian"
        axes_payload = [
            axis for axis in list(sweep_setup_payload.get("axes", [])) if isinstance(axis, Mapping)
        ]
        if not axes_payload:
            raise ValueError("Sweep setup has no axis definitions.")
        total_sweep_points = _estimate_sweep_cartesian_point_count(axes_payload)
        if sweep_mode == "cartesian" and total_sweep_points > _SWEEP_MAX_CARTESIAN_POINTS:
            raise ValueError(
                "Cartesian sweep point count exceeds limit "
                f"({_SWEEP_MAX_CARTESIAN_POINTS}). Current total: {total_sweep_points}."
            )
        sweep_axes: list[SimulationSweepAxis] = []
        for axis_payload in axes_payload:
            target_value_ref = str(axis_payload.get("target_value_ref", "")).strip()
            if target_value_ref not in sweep_target_units_latest:
                raise ValueError(
                    "Sweep target is invalid for the latest schema/setup: "
                    f"{target_value_ref}."
                )
            sweep_axes.append(
                SimulationSweepAxis(
                    target_value_ref=target_value_ref,
                    values=build_linear_sweep_values(
                        start=float(axis_payload.get("start", 0.0)),
                        stop=float(axis_payload.get("stop", 0.0)),
                        points=max(1, int(axis_payload.get("points", 1))),
                    ),
                    unit=str(sweep_target_units_latest.get(target_value_ref, "")),
                )
            )
        sweep_plan = build_simulation_sweep_plan(
            circuit=latest_circuit_def,
            axes=sweep_axes,
            config=config,
        )
        sweep_snapshot = simulation_sweep_setup_snapshot(sweep_plan)
        sweep_snapshot["mode"] = sweep_mode
        sweep_setup_hash = hash_stable_json(sweep_snapshot)

    harmonic_grid_hits = _detect_harmonic_grid_coincidences(
        freq_range=freq_range,
        sources=sources,
        max_pump_harmonic=config.n_pump_harmonics,
    )
    estimated_mode_lattice = _estimate_mode_lattice_size(
        sources,
        config.n_modulation_harmonics,
    )
    setup_snapshot = _normalized_simulation_setup_snapshot(freq_range, config)
    if sweep_plan is not None and sweep_snapshot is not None:
        setup_snapshot["sweep"] = {
            **sweep_snapshot,
            "setup_hash": sweep_setup_hash,
        }
    schema_source_hash = hash_schema_source(latest_record.definition_json)
    simulation_setup_hash = hash_stable_json(setup_snapshot)

    return PreparedSimulationRun(
        freq_range=freq_range,
        sources=sources,
        config=config,
        sweep_setup_payload=dict(sweep_setup_payload),
        sweep_plan=sweep_plan,
        sweep_mode=sweep_mode,
        sweep_snapshot=sweep_snapshot,
        sweep_setup_hash=sweep_setup_hash,
        harmonic_grid_hits=list(harmonic_grid_hits),
        estimated_mode_lattice=estimated_mode_lattice,
        setup_snapshot=setup_snapshot,
        schema_source_hash=schema_source_hash,
        simulation_setup_hash=simulation_setup_hash,
        warnings=warnings,
    )
