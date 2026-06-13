"""
Simulation Use Cases.

This module orchestrates the simulation workflow.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from itertools import product
from typing import Any, Protocol

from core.simulation.domain.circuit import (
    CircuitDefinition,
    ComponentSpec,
    DriveSourceConfig,
    ExpandedCircuitDefinition,
    FrequencyRange,
    SimulationConfig,
    SimulationResult,
)


class _JuliaSimulationAdapter(Protocol):
    """Minimal protocol for the Julia-backed simulation adapter."""

    def run_hbsolve(
        self,
        circuit: CircuitDefinition,
        freq_range: FrequencyRange,
        config: SimulationConfig,
    ) -> SimulationResult: ...


JuliaSimulator: type[_JuliaSimulationAdapter] | None = None


def _build_julia_simulator() -> _JuliaSimulationAdapter:
    """Create the Julia-backed simulator only when execution is requested."""
    global JuliaSimulator

    if JuliaSimulator is None:
        from core.simulation.infrastructure.julia_adapter import JuliaSimulator as _JuliaSimulator

        JuliaSimulator = _JuliaSimulator

    return JuliaSimulator()


@dataclass(frozen=True)
class SimulationSweepTarget:
    """Sweepable target key discovered from netlist parameters and source setup."""

    value_ref: str
    unit: str


@dataclass(frozen=True)
class SimulationSweepAxis:
    """One sweep axis bound to one target key."""

    target_value_ref: str
    values: tuple[float, ...]
    unit: str

    @property
    def point_count(self) -> int:
        """Return number of grid points on this axis."""
        return len(self.values)


@dataclass(frozen=True)
class SimulationSweepPoint:
    """One concrete grid point in a sweep plan."""

    point_index: int
    axis_indices: tuple[int, ...]
    value_ref_overrides: dict[str, float]


@dataclass(frozen=True)
class SimulationSweepPlan:
    """Expanded sweep plan for one simulation run."""

    axes: tuple[SimulationSweepAxis, ...]
    points: tuple[SimulationSweepPoint, ...]

    @property
    def dimension(self) -> int:
        """Return sweep dimensionality."""
        return len(self.axes)

    @property
    def point_count(self) -> int:
        """Return total point count across all axes."""
        return len(self.points)


@dataclass(frozen=True)
class SimulationSweepPointResult:
    """One executed sweep point result."""

    point_index: int
    axis_indices: tuple[int, ...]
    axis_values: dict[str, float]
    result: SimulationResult


_SOURCE_SWEEP_TARGET_PATTERN = re.compile(
    r"^sources\[(?P<index>[1-9]\d*)\]\.(?P<field>current_amp|pump_freq_ghz)$"
)


def _parse_source_sweep_target(target_key: str) -> tuple[int, str] | None:
    """Parse one source-target key into zero-based source index + field."""
    matched = _SOURCE_SWEEP_TARGET_PATTERN.fullmatch(str(target_key).strip())
    if matched is None:
        return None
    return (int(matched.group("index")) - 1, str(matched.group("field")))


def _materialize_config_sources(config: SimulationConfig) -> list[DriveSourceConfig]:
    """Return concrete source list regardless of legacy/sources configuration path."""
    if config.sources:
        return [
            (
                source.model_copy(deep=True)
                if isinstance(source, DriveSourceConfig)
                else DriveSourceConfig.model_validate(source)
            )
            for source in config.sources
        ]
    return [
        DriveSourceConfig(
            pump_freq_ghz=float(config.pump_freq_ghz),
            port=int(config.pump_port),
            current_amp=float(config.pump_current_amp),
            mode_components=(int(config.pump_mode_index),),
        )
    ]


@dataclass(frozen=True)
class SimulationSweepRun:
    """Sweep execution output used by cache/provenance/export layers."""

    axes: tuple[SimulationSweepAxis, ...]
    points: tuple[SimulationSweepPointResult, ...]
    representative_point_index: int = 0

    @property
    def dimension(self) -> int:
        """Return sweep dimensionality."""
        return len(self.axes)

    @property
    def point_count(self) -> int:
        """Return total executed point count."""
        return len(self.points)

    @property
    def representative_result(self) -> SimulationResult:
        """Return one representative result used for quick-inspect views."""
        if not self.points:
            raise ValueError("Simulation sweep produced no points.")
        if self.representative_point_index < 0 or self.representative_point_index >= len(
            self.points
        ):
            raise ValueError("representative_point_index is out of range.")
        return self.points[self.representative_point_index].result


def run_simulation(
    circuit: CircuitDefinition,
    freq_range: FrequencyRange,
    config: SimulationConfig | None = None,
) -> SimulationResult:
    """
    Run a circuit simulation.

    This is the main entry point for simulation use cases.

    Args:
        circuit: Circuit definition.
        freq_range: Frequency sweep range.
        config: Optional simulation config. Defaults to sensible values.

    Returns:
        SimulationResult with S-parameter data.
    """
    if config is None:
        config = SimulationConfig()

    simulator = _build_julia_simulator()
    return simulator.run_hbsolve(circuit, freq_range, config)


def list_simulation_sweep_targets(
    circuit: CircuitDefinition,
    *,
    config: SimulationConfig | None = None,
) -> list[SimulationSweepTarget]:
    """List sweepable targets from netlist `value_ref` and source setup fields."""
    targets: dict[str, str] = {}
    parameter_specs = circuit.parameter_specs
    for component in circuit.expanded_definition.components:
        if component.value_ref is None:
            continue
        parameter = parameter_specs.get(component.value_ref)
        unit = parameter.unit if parameter is not None else component.unit
        if component.value_ref not in targets:
            targets[component.value_ref] = str(unit)

    if isinstance(config, SimulationConfig):
        for source_index, _source in enumerate(_materialize_config_sources(config), start=1):
            targets[f"sources[{source_index}].current_amp"] = "A"
            targets[f"sources[{source_index}].pump_freq_ghz"] = "GHz"

    return [
        SimulationSweepTarget(value_ref=value_ref, unit=targets[value_ref])
        for value_ref in sorted(targets)
    ]


def build_linear_sweep_values(*, start: float, stop: float, points: int) -> tuple[float, ...]:
    """Build an evenly spaced sweep axis."""
    if points < 1:
        raise ValueError("Sweep points must be >= 1.")
    if points == 1:
        return (float(start),)
    step = (float(stop) - float(start)) / float(points - 1)
    return tuple(float(float(start) + step * idx) for idx in range(points))


def build_simulation_sweep_plan(
    *,
    circuit: CircuitDefinition,
    axes: Sequence[SimulationSweepAxis],
    config: SimulationConfig | None = None,
) -> SimulationSweepPlan:
    """Expand one normalized sweep setup into Cartesian execution points."""
    if not axes:
        raise ValueError("At least one sweep axis is required.")

    available_targets = {
        target.value_ref: target for target in list_simulation_sweep_targets(circuit, config=config)
    }
    normalized_axes: list[SimulationSweepAxis] = []
    seen_targets: set[str] = set()
    for raw_axis in axes:
        target_value_ref = str(raw_axis.target_value_ref).strip()
        if not target_value_ref:
            raise ValueError("Sweep axis target_value_ref is required.")
        if target_value_ref in seen_targets:
            raise ValueError(f"Duplicate sweep target '{target_value_ref}' is not allowed.")
        if target_value_ref not in available_targets:
            raise ValueError(f"Sweep target '{target_value_ref}' is not available.")
        values = tuple(float(value) for value in raw_axis.values)
        if not values:
            raise ValueError(f"Sweep axis '{target_value_ref}' has no values.")
        seen_targets.add(target_value_ref)
        normalized_axes.append(
            SimulationSweepAxis(
                target_value_ref=target_value_ref,
                values=values,
                unit=str(raw_axis.unit or available_targets[target_value_ref].unit),
            )
        )

    axes_tuple = tuple(normalized_axes)
    grid_ranges = [range(len(axis.values)) for axis in axes_tuple]
    points: list[SimulationSweepPoint] = []
    for point_index, axis_indices in enumerate(product(*grid_ranges)):
        overrides = {
            axis.target_value_ref: float(axis.values[value_index])
            for axis, value_index in zip(axes_tuple, axis_indices, strict=True)
        }
        points.append(
            SimulationSweepPoint(
                point_index=point_index,
                axis_indices=tuple(int(value) for value in axis_indices),
                value_ref_overrides=overrides,
            )
        )
    if not points:
        raise ValueError("Sweep plan generated zero points.")
    return SimulationSweepPlan(axes=axes_tuple, points=tuple(points))


def simulation_sweep_setup_snapshot(plan: SimulationSweepPlan) -> dict[str, Any]:
    """Serialize one sweep plan into a stable setup snapshot payload."""
    return {
        "dimensions": int(plan.dimension),
        "point_count": int(plan.point_count),
        "axes": [
            {
                "target_value_ref": axis.target_value_ref,
                "unit": axis.unit,
                "values": [float(value) for value in axis.values],
            }
            for axis in plan.axes
        ],
    }


def apply_simulation_sweep_overrides(
    *,
    circuit: CircuitDefinition,
    value_ref_overrides: Mapping[str, float],
) -> CircuitDefinition:
    """Build one concrete circuit by overriding selected netlist `value_ref` defaults."""
    if not value_ref_overrides:
        return circuit

    available_targets = {target.value_ref for target in list_simulation_sweep_targets(circuit)}
    netlist_overrides = {
        str(target): float(value)
        for target, value in value_ref_overrides.items()
        if _parse_source_sweep_target(str(target)) is None
    }
    unknown_targets = sorted(set(netlist_overrides) - available_targets)
    if unknown_targets:
        raise ValueError(f"Unknown sweep target(s): {', '.join(unknown_targets)}.")
    if not netlist_overrides:
        return circuit

    expanded = circuit.expanded_definition
    source_payload = {
        "name": expanded.name,
        "components": [
            _resolved_component_payload(
                component=component,
                expanded=expanded,
                value_ref_overrides=netlist_overrides,
            )
            for component in expanded.components
        ],
        "topology": [row.as_tuple() for row in expanded.topology],
    }
    return CircuitDefinition.model_validate(source_payload)


def apply_simulation_sweep_config_overrides(
    *,
    config: SimulationConfig,
    target_overrides: Mapping[str, float],
) -> SimulationConfig:
    """Build one concrete simulation config by overriding selected source targets."""
    if not target_overrides:
        return config

    sources = _materialize_config_sources(config)
    has_source_override = False
    for target, value in target_overrides.items():
        parsed = _parse_source_sweep_target(str(target))
        if parsed is None:
            continue
        source_index, field_name = parsed
        if source_index < 0 or source_index >= len(sources):
            raise ValueError(
                f"Sweep target '{target}' is out of source range (configured={len(sources)})."
            )
        has_source_override = True
        if field_name == "current_amp":
            sources[source_index] = sources[source_index].model_copy(
                update={"current_amp": float(value)}
            )
        elif field_name == "pump_freq_ghz":
            sources[source_index] = sources[source_index].model_copy(
                update={"pump_freq_ghz": float(value)}
            )
        else:
            raise ValueError(f"Sweep target '{target}' has unsupported source field.")

    if not has_source_override:
        return config

    first_source = sources[0]
    return config.model_copy(
        update={
            "sources": sources,
            "pump_freq_ghz": float(first_source.pump_freq_ghz),
            "pump_current_amp": float(first_source.current_amp),
            "pump_port": int(first_source.port),
        }
    )


def run_parameter_sweep(
    *,
    circuit: CircuitDefinition,
    freq_range: FrequencyRange,
    config: SimulationConfig | None,
    plan: SimulationSweepPlan,
) -> SimulationSweepRun:
    """Execute one sweep plan sequentially and return structured point results."""
    if config is None:
        config = SimulationConfig()
    if plan.point_count < 1:
        raise ValueError("Sweep plan must include at least one point.")

    simulator = _build_julia_simulator()
    point_results: list[SimulationSweepPointResult] = []
    for point in plan.points:
        swept_circuit = apply_simulation_sweep_overrides(
            circuit=circuit,
            value_ref_overrides=point.value_ref_overrides,
        )
        swept_config = apply_simulation_sweep_config_overrides(
            config=config,
            target_overrides=point.value_ref_overrides,
        )
        result = simulator.run_hbsolve(swept_circuit, freq_range, swept_config)
        point_results.append(
            SimulationSweepPointResult(
                point_index=int(point.point_index),
                axis_indices=tuple(point.axis_indices),
                axis_values=dict(point.value_ref_overrides),
                result=result,
            )
        )
    return SimulationSweepRun(
        axes=plan.axes,
        points=tuple(point_results),
        representative_point_index=0,
    )


def simulation_sweep_run_to_payload(run: SimulationSweepRun) -> dict[str, Any]:
    """Serialize one sweep run into a JSON-compatible payload."""
    return {
        "run_kind": "parameter_sweep",
        "dimensions": int(run.dimension),
        "point_count": int(run.point_count),
        "representative_point_index": int(run.representative_point_index),
        "sweep_axes": [
            {
                "target_value_ref": axis.target_value_ref,
                "unit": axis.unit,
                "values": [float(value) for value in axis.values],
            }
            for axis in run.axes
        ],
        "points": [
            {
                "point_index": int(point.point_index),
                "axis_indices": [int(value) for value in point.axis_indices],
                "axis_values": {
                    str(target): float(value) for target, value in sorted(point.axis_values.items())
                },
                "result": point.result.model_dump(mode="json"),
            }
            for point in run.points
        ],
    }


def _legacy_sweep_axes_payload(payload: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Decode legacy single-axis payload shape into `sweep_axes` list."""
    axis_payload = payload.get("axis")
    if isinstance(axis_payload, Mapping):
        values = axis_payload.get("values")
        if not isinstance(values, list):
            values = payload.get("values", [])
        if isinstance(values, list) and values:
            return [
                {
                    "target_value_ref": axis_payload.get(
                        "target_value_ref",
                        payload.get("target_value_ref", ""),
                    ),
                    "unit": axis_payload.get("unit", payload.get("unit", "")),
                    "values": values,
                }
            ]
    target_value_ref = str(payload.get("target_value_ref", "")).strip()
    values = payload.get("values")
    if target_value_ref and isinstance(values, list) and values:
        return [
            {
                "target_value_ref": target_value_ref,
                "unit": payload.get("unit", ""),
                "values": values,
            }
        ]
    return []


def simulation_sweep_run_from_payload(payload: Mapping[str, Any]) -> SimulationSweepRun:
    """Deserialize one cached/persisted sweep payload."""
    if str(payload.get("run_kind", "")) != "parameter_sweep":
        raise ValueError("Payload is not a parameter sweep result.")

    raw_axes = payload.get("sweep_axes")
    if not isinstance(raw_axes, list) or not raw_axes:
        raw_axes = _legacy_sweep_axes_payload(payload)
    raw_points = payload.get("points")
    if not isinstance(raw_points, list) or not raw_points:
        raw_points = payload.get("point_results")
    if not isinstance(raw_points, list) or not raw_points:
        raw_points = payload.get("results")
    if not isinstance(raw_axes, list) or not raw_axes:
        raise ValueError("Sweep payload must include non-empty sweep_axes.")
    if not isinstance(raw_points, list) or not raw_points:
        raise ValueError("Sweep payload must include non-empty points.")

    axes: list[SimulationSweepAxis] = []
    for raw_axis in raw_axes:
        if not isinstance(raw_axis, Mapping):
            raise ValueError("Sweep axis payload is invalid.")
        target_value_ref = str(raw_axis.get("target_value_ref", "")).strip()
        if not target_value_ref:
            raise ValueError("Sweep axis target_value_ref is required.")
        values = raw_axis.get("values")
        if not isinstance(values, list) or not values:
            raise ValueError(f"Sweep axis '{target_value_ref}' has invalid values.")
        axes.append(
            SimulationSweepAxis(
                target_value_ref=target_value_ref,
                unit=str(raw_axis.get("unit", "")),
                values=tuple(float(value) for value in values),
            )
        )

    points: list[SimulationSweepPointResult] = []
    for raw_point in raw_points:
        if not isinstance(raw_point, Mapping):
            raise ValueError("Sweep point payload is invalid.")
        raw_result = raw_point.get("result")
        if not isinstance(raw_result, Mapping):
            raw_result = raw_point.get("payload")
        if not isinstance(raw_result, Mapping):
            raise ValueError("Sweep point result payload is invalid.")
        raw_axis_values = raw_point.get("axis_values", {})
        if not isinstance(raw_axis_values, Mapping):
            raw_axis_values = {}
        if not raw_axis_values and len(axes) == 1 and raw_point.get("axis_value") is not None:
            raw_axis_values = {
                axes[0].target_value_ref: float(raw_point.get("axis_value", axes[0].values[0]))
            }
        if not isinstance(raw_axis_values, Mapping):
            raise ValueError("Sweep point axis_values payload is invalid.")
        raw_axis_indices = raw_point.get("axis_indices", [])
        if not isinstance(raw_axis_indices, list):
            raw_axis_index = raw_point.get("axis_index")
            raw_axis_indices = [] if raw_axis_index is None else [int(raw_axis_index)]
        if isinstance(raw_axis_indices, list) and not raw_axis_indices:
            raw_axis_index = raw_point.get("axis_index")
            if raw_axis_index is not None:
                raw_axis_indices = [int(raw_axis_index)]
        points.append(
            SimulationSweepPointResult(
                point_index=int(raw_point.get("point_index", len(points))),
                axis_indices=tuple(int(value) for value in raw_axis_indices),
                axis_values={
                    str(target): float(value) for target, value in raw_axis_values.items()
                },
                result=SimulationResult.model_validate(raw_result),
            )
        )

    representative_point_index = int(payload.get("representative_point_index", 0))
    return SimulationSweepRun(
        axes=tuple(axes),
        points=tuple(points),
        representative_point_index=representative_point_index,
    )


def _resolved_component_payload(
    *,
    component: ComponentSpec,
    expanded: ExpandedCircuitDefinition,
    value_ref_overrides: Mapping[str, float],
) -> dict[str, Any]:
    """Resolve one expanded component row into a direct numeric component payload."""
    if component.default is not None:
        resolved_value = float(component.default)
    elif component.value_ref is not None:
        parameter = expanded.parameter_spec(component.value_ref)
        if parameter is None:
            raise ValueError(f"Undefined parameter '{component.value_ref}' in expanded circuit.")
        resolved_value = float(value_ref_overrides.get(component.value_ref, parameter.default))
    else:
        raise ValueError(f"Component '{component.name}' has neither default nor value_ref.")

    return {
        "name": component.name,
        "default": resolved_value,
        "unit": component.unit,
    }
