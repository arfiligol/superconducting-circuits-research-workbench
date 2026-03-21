"""Frequency-range setup payload helpers for simulation."""

from __future__ import annotations

from typing import Any

from core.simulation.domain.circuit import (
    DriveSourceConfig,
    FrequencyRange,
    SimulationConfig,
)

from .sources import _normalize_source_mode_components


def _build_setup_payload(
    *,
    start_ghz: float,
    stop_ghz: float,
    points: int,
    n_modulation_harmonics: int,
    n_pump_harmonics: int,
    sources: list[dict[str, Any]],
    include_dc: bool = False,
    enable_three_wave_mixing: bool = False,
    enable_four_wave_mixing: bool = True,
    max_intermod_order: int = -1,
    max_iterations: int = 1000,
    f_tol: float = 1e-8,
    line_search_switch_tol: float = 1e-5,
    alpha_min: float = 1e-4,
    sweep: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a saved-setup payload matching the UI save format."""
    payload = {
        "freq_range": {
            "start_ghz": start_ghz,
            "stop_ghz": stop_ghz,
            "points": points,
        },
        "harmonics": {
            "n_modulation_harmonics": n_modulation_harmonics,
            "n_pump_harmonics": n_pump_harmonics,
        },
        "sources": sources,
        "advanced": {
            "include_dc": include_dc,
            "enable_three_wave_mixing": enable_three_wave_mixing,
            "enable_four_wave_mixing": enable_four_wave_mixing,
            "max_intermod_order": max_intermod_order,
            "max_iterations": max_iterations,
            "f_tol": f_tol,
            "line_search_switch_tol": line_search_switch_tol,
            "alpha_min": alpha_min,
        },
    }
    if isinstance(sweep, dict):
        payload["sweep"] = dict(sweep)
    return payload


def _normalized_simulation_setup_snapshot(
    freq_range: FrequencyRange,
    config: SimulationConfig,
) -> dict[str, Any]:
    """Build the canonical setup snapshot used for cache identity."""
    if config.sources:
        resolved_sources = config.sources
    else:
        resolved_sources = [
            DriveSourceConfig(
                pump_freq_ghz=float(config.pump_freq_ghz),
                port=int(config.pump_port),
                current_amp=float(config.pump_current_amp),
                mode_components=(int(config.pump_mode_index),),
            )
        ]

    return {
        "freq_range": {
            "start_ghz": float(freq_range.start_ghz),
            "stop_ghz": float(freq_range.stop_ghz),
            "points": int(freq_range.points),
        },
        "sources": [
            {
                "pump_freq_ghz": float(source.pump_freq_ghz),
                "port": int(source.port),
                "current_amp": float(source.current_amp),
                "mode": [
                    int(value)
                    for value in (
                        source.mode_components
                        if source.mode_components is not None
                        else _normalize_source_mode_components(
                            None,
                            source_index=idx,
                            source_count=len(resolved_sources),
                        )
                    )
                ],
            }
            for idx, source in enumerate(resolved_sources)
        ],
        "harmonics": {
            "n_modulation_harmonics": int(config.n_modulation_harmonics),
            "n_pump_harmonics": int(config.n_pump_harmonics),
        },
        "advanced": {
            "include_dc": bool(config.include_dc),
            "enable_three_wave_mixing": bool(config.enable_three_wave_mixing),
            "enable_four_wave_mixing": bool(config.enable_four_wave_mixing),
            "max_intermod_order": (
                -1 if config.max_intermod_order is None else int(config.max_intermod_order)
            ),
            "max_iterations": int(config.max_iterations),
            "f_tol": float(config.f_tol),
            "line_search_switch_tol": float(config.line_search_switch_tol),
            "alpha_min": float(config.alpha_min),
        },
    }
