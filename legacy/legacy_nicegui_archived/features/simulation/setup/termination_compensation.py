"""Termination-compensation setup helpers for simulation."""

from __future__ import annotations

from typing import Any

_TERMINATION_MODE_OPTIONS = {
    "auto": "Auto (Schema infer)",
    "manual": "Manual",
}
_TERMINATION_DEFAULT_RESISTANCE_OHM = 50.0


def _normalize_termination_mode(mode: object) -> str:
    """Normalize termination compensation mode token."""
    normalized = str(mode or "auto").strip().lower()
    return normalized if normalized in _TERMINATION_MODE_OPTIONS else "auto"


def _normalize_termination_selected_ports(
    raw_ports: object,
    *,
    available_ports: list[int],
) -> list[int]:
    """Normalize one dynamic selected-port payload into sorted unique port indices."""
    if isinstance(raw_ports, int | float | str):
        candidates: list[object] = [raw_ports]
    elif isinstance(raw_ports, list | tuple | set):
        candidates = list(raw_ports)
    else:
        candidates = []
    normalized: set[int] = set()
    allowed = set(available_ports)
    for candidate in candidates:
        try:
            port = int(float(str(candidate)))
        except Exception:
            continue
        if port in allowed:
            normalized.add(port)
    return sorted(normalized)


def _normalize_manual_termination_resistance_map(
    raw_map: object,
    *,
    available_ports: list[int],
    default_ohm: float = _TERMINATION_DEFAULT_RESISTANCE_OHM,
) -> dict[int, float]:
    """Normalize one manual resistance mapping into positive Ohm values per available port."""
    normalized: dict[int, float] = {}
    source_map = raw_map if isinstance(raw_map, dict) else {}
    for port in available_ports:
        value = source_map.get(port, source_map.get(str(port), default_ohm))
        try:
            resistance = float(value)
        except Exception:
            resistance = float(default_ohm)
        if resistance <= 0:
            resistance = float(default_ohm)
        normalized[int(port)] = resistance
    return normalized


def _build_termination_compensation_plan(
    *,
    enabled: bool,
    mode: str,
    selected_ports: list[int],
    manual_resistance_ohm_by_port: dict[int, float],
    inferred_resistance_ohm_by_port: dict[int, float],
    inferred_source_by_port: dict[int, str],
    inferred_warning_by_port: dict[int, str],
    fallback_ohm: float = _TERMINATION_DEFAULT_RESISTANCE_OHM,
) -> dict[str, Any]:
    """Build one resolved termination-compensation execution plan."""
    normalized_mode = _normalize_termination_mode(mode)
    normalized_ports = sorted(set(int(port) for port in selected_ports))
    if not enabled or not normalized_ports:
        return {
            "enabled": False,
            "mode": normalized_mode,
            "selected_ports": normalized_ports,
            "resistance_ohm_by_port": {},
            "source_by_port": {},
            "warnings": [],
        }

    resolved_resistance: dict[int, float] = {}
    resolved_source: dict[int, str] = {}
    warnings: list[str] = []
    if normalized_mode == "manual":
        for port in normalized_ports:
            resistance = float(
                manual_resistance_ohm_by_port.get(port, _TERMINATION_DEFAULT_RESISTANCE_OHM)
            )
            if resistance <= 0:
                resistance = float(fallback_ohm)
                warnings.append(
                    f"Port {port}: invalid manual resistance; fallback to {fallback_ohm:g} Ohm."
                )
            resolved_resistance[port] = resistance
            resolved_source[port] = "manual"
    else:
        for port in normalized_ports:
            resistance = float(
                inferred_resistance_ohm_by_port.get(port, _TERMINATION_DEFAULT_RESISTANCE_OHM)
            )
            if resistance <= 0:
                resistance = float(fallback_ohm)
            resolved_resistance[port] = resistance
            resolved_source[port] = str(inferred_source_by_port.get(port, "fallback_default_50"))
            warning = inferred_warning_by_port.get(port)
            if warning:
                warnings.append(str(warning))

    return {
        "enabled": True,
        "mode": normalized_mode,
        "selected_ports": normalized_ports,
        "resistance_ohm_by_port": resolved_resistance,
        "source_by_port": resolved_source,
        "warnings": warnings,
    }
