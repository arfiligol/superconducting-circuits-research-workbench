"""Parameter-sweep setup helpers for simulation."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from core.simulation.application.run_simulation import list_simulation_sweep_targets
from core.simulation.domain.circuit import CircuitDefinition, SimulationConfig

_SWEEP_MAX_AXIS_COUNT = 4
_SWEEP_MAX_CARTESIAN_POINTS = 625
_SWEEP_MODE_OPTIONS = {
    "cartesian": "Cartesian",
    "paired": "Paired (reserved)",
}


def _default_sweep_axis_payload() -> dict[str, Any]:
    """Return one default sweep axis payload."""
    return {
        "target_value_ref": "",
        "start": 0.0,
        "stop": 0.0,
        "points": 11,
        "unit": "",
    }


def _default_sweep_setup_payload() -> dict[str, Any]:
    """Return one default multi-axis sweep setup payload."""
    return {
        "enabled": False,
        "mode": "cartesian",
        "axes": [_default_sweep_axis_payload()],
    }


def _legacy_sweep_axes_from_payload(payload: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    """Decode legacy single-axis setup payload shapes into one `axes[]` list."""
    raw_axes = payload.get("axes")
    if isinstance(raw_axes, list):
        return [axis for axis in raw_axes if isinstance(axis, Mapping)]
    axis_1 = payload.get("axis_1")
    if isinstance(axis_1, Mapping):
        return [axis_1]
    if payload.get("target_value_ref") is not None:
        return [
            {
                "target_value_ref": payload.get("target_value_ref", ""),
                "start": payload.get("start", 0.0),
                "stop": payload.get("stop", payload.get("start", 0.0)),
                "points": payload.get("points", 11),
                "unit": payload.get("unit", ""),
            }
        ]
    return []


def _normalize_sweep_setup_payload(
    payload: Mapping[str, Any] | None,
    *,
    available_target_units: Mapping[str, str],
) -> dict[str, Any]:
    """Normalize one persisted sweep setup payload against current schema targets."""
    normalized = _default_sweep_setup_payload()
    if isinstance(payload, Mapping):
        normalized["enabled"] = bool(payload.get("enabled", False))
        mode = str(payload.get("mode", "cartesian")).strip().lower()
        normalized["mode"] = mode if mode in _SWEEP_MODE_OPTIONS else "cartesian"
        raw_axes = _legacy_sweep_axes_from_payload(payload)
        axes: list[dict[str, Any]] = []
        for raw_axis in raw_axes[:_SWEEP_MAX_AXIS_COUNT]:
            if not isinstance(raw_axis, Mapping):
                continue
            target = str(raw_axis.get("target_value_ref", "")).strip()
            start = float(raw_axis.get("start", 0.0) or 0.0)
            stop = float(raw_axis.get("stop", start) or start)
            points = max(1, int(raw_axis.get("points", 11) or 11))
            unit_hint = str(raw_axis.get("unit", "")).strip()
            if target in available_target_units:
                unit_hint = str(available_target_units[target])
            axes.append(
                {
                    "target_value_ref": target,
                    "start": start,
                    "stop": stop,
                    "points": points,
                    "unit": unit_hint,
                }
            )
        if axes:
            normalized["axes"] = axes
    if not normalized["axes"]:
        normalized["axes"] = [_default_sweep_axis_payload()]

    fallback_target = next(iter(available_target_units), "")
    for axis in normalized["axes"]:
        target = str(axis.get("target_value_ref", "")).strip()
        if target not in available_target_units:
            target = fallback_target
            axis["target_value_ref"] = target
        axis["unit"] = str(available_target_units.get(target, ""))

    if not normalized["axes"]:
        normalized["axes"] = [_default_sweep_axis_payload()]

    return normalized


def _estimate_sweep_cartesian_point_count(axes_payload: list[Mapping[str, Any]]) -> int:
    """Estimate total Cartesian point count from normalized axis payload entries."""
    total = 1
    for raw_axis in axes_payload:
        try:
            axis_points = max(1, int(raw_axis.get("points", 1) or 1))
        except Exception:
            axis_points = 1
        total *= axis_points
    return max(total, 0)


def _extract_sweep_target_units(
    circuit: CircuitDefinition,
    *,
    config: SimulationConfig | None = None,
) -> dict[str, str]:
    """Collect sweep target unit hints keyed by target key."""
    return {
        target.value_ref: target.unit
        for target in list_simulation_sweep_targets(circuit, config=config)
    }
