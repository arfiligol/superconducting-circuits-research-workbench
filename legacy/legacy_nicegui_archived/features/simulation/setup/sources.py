"""Source-configuration helpers for simulation setup."""

from __future__ import annotations

from core.simulation.domain.circuit import (
    CircuitDefinition,
    DriveSourceConfig,
    FrequencyRange,
)


def _build_source_payload(
    *,
    pump_freq_ghz: float,
    port: int,
    current_amp: float,
    mode: tuple[int, ...] | list[int],
) -> dict[str, object]:
    """Build one saved-setup source payload entry."""
    return {
        "pump_freq_ghz": float(pump_freq_ghz),
        "port": int(port),
        "current_amp": float(current_amp),
        "mode": [int(value) for value in mode],
    }


def _compress_source_mode_components(
    mode: tuple[int, ...] | list[int] | None,
) -> tuple[int, ...]:
    """Compress internal mode vectors into the shortest user-facing tuple."""
    if mode is None:
        return ()

    values = tuple(int(value) for value in mode)
    if not values:
        return ()

    if all(value == 0 for value in values):
        return (0,)

    highest_nonzero_index = max(idx for idx, value in enumerate(values) if value != 0)
    return values[: highest_nonzero_index + 1]


def _format_source_mode_text(mode: tuple[int, ...] | list[int] | None) -> str:
    """Format one source mode tuple for the UI text field."""
    if mode is None:
        return ""
    values = tuple(int(value) for value in mode)
    if not values:
        return ""
    return ", ".join(str(value) for value in values)


def _parse_source_mode_text(raw_value: object) -> tuple[int, ...] | None:
    """Parse the UI/source-payload mode field into a normalized tuple."""
    if raw_value is None:
        return None
    if isinstance(raw_value, list | tuple):
        parsed = tuple(int(value) for value in raw_value)
        return parsed or None

    text = str(raw_value).strip()
    if not text:
        return None

    normalized = text.strip("()[]")
    normalized = normalized.replace(";", ",")
    if not normalized:
        return None

    parts = [part.strip() for part in normalized.split(",") if part.strip()]
    if not parts:
        return None

    return tuple(int(part) for part in parts)


def _normalize_source_mode_components(
    mode: tuple[int, ...] | list[int] | None,
    *,
    source_index: int,
    source_count: int,
) -> tuple[int, ...]:
    """Normalize one source mode tuple to the current source-count width."""
    width = max(int(source_count), 1)
    clamped_index = min(max(int(source_index), 0), width - 1)

    if mode is None:
        fallback = [0] * width
        fallback[clamped_index] = 1
        return tuple(fallback)

    normalized = tuple(int(value) for value in mode)
    if not normalized:
        fallback = [0] * width
        fallback[clamped_index] = 1
        return tuple(fallback)

    if all(value == 0 for value in normalized):
        return tuple(0 for _ in range(width))

    if len(normalized) == 1:
        single_value = normalized[0]
        if single_value <= 0:
            return tuple(0 for _ in range(width))
        fallback = [0] * width
        slot_index = min(single_value, width) - 1
        fallback[slot_index] = 1
        return tuple(fallback)

    nonzero_indices = [idx for idx, value in enumerate(normalized) if value != 0]
    if len(nonzero_indices) == 1 and normalized[nonzero_indices[0]] > 0:
        if len(normalized) == width:
            return normalized
        fallback = [0] * width
        fallback[clamped_index] = 1
        return tuple(fallback)

    return normalized


def _extract_available_port_indices(circuit: CircuitDefinition) -> set[int]:
    """Collect schema-declared port indices from public port declarations."""
    return set(circuit.available_port_indices)


def _detect_harmonic_grid_coincidences(
    freq_range: FrequencyRange,
    sources: list[DriveSourceConfig],
    max_pump_harmonic: int,
) -> list[tuple[int, int, float, int]]:
    """Find source harmonic frequencies that land exactly on a sweep grid point."""
    if freq_range.points < 2 or max_pump_harmonic < 1 or not sources:
        return []

    start = float(freq_range.start_ghz)
    stop = float(freq_range.stop_ghz)
    step = (stop - start) / float(freq_range.points - 1)
    if step <= 0:
        return []

    hits: list[tuple[int, int, float, int]] = []
    for source_index, source in enumerate(sources, start=1):
        if source.mode_components is not None and all(
            value == 0 for value in source.mode_components
        ):
            continue
        fp = float(source.pump_freq_ghz)
        if fp <= 0:
            continue

        for harmonic in range(1, max_pump_harmonic + 1):
            target = harmonic * fp
            if target < start or target > stop:
                continue

            grid_position = (target - start) / step
            nearest_index = round(grid_position)
            if nearest_index < 0 or nearest_index >= freq_range.points:
                continue

            grid_freq = start + nearest_index * step
            tolerance = max(abs(step) * 1e-6, abs(target) * 1e-12, 1e-12)
            if abs(grid_freq - target) <= tolerance:
                hits.append((source_index, harmonic, target, nearest_index))

    return hits


def _format_harmonic_grid_hint(hits: list[tuple[int, int, float, int]], limit: int = 3) -> str:
    """Build a concise user-facing hint for harmonic/grid coincidence hits."""
    if not hits:
        return ""

    shown = hits[:limit]
    parts = [
        (f"S{source_index}: {harmonic}*fp={freq_ghz:.6f} GHz (sweep index={grid_index})")
        for source_index, harmonic, freq_ghz, grid_index in shown
    ]
    suffix = "" if len(hits) <= limit else f"; +{len(hits) - limit} more"
    return (
        "Potential harmonic/grid coincidence detected (can trigger singular matrix): "
        + "; ".join(parts)
        + suffix
    )


def _estimate_mode_lattice_size(
    sources: list[DriveSourceConfig],
    n_modulation_harmonics: int,
) -> int:
    """Estimate the size of the mode lattice implied by the current source configuration."""
    if n_modulation_harmonics < 0:
        return 1

    tone_count = (
        max(
            1,
            max(
                len(source.mode_components) if source.mode_components is not None else 1
                for source in sources
            ),
        )
        if sources
        else 1
    )
    span_per_tone = max(1, 2 * n_modulation_harmonics + 1)
    lattice_size = 1
    for _ in range(tone_count):
        lattice_size *= span_per_tone
    return lattice_size


def _format_mode_lattice_hint(
    sources: list[DriveSourceConfig],
    n_modulation_harmonics: int,
) -> str:
    """Build a concise warning for potentially slow multi-tone hbsolve runs."""
    tone_count = (
        max(
            1,
            max(
                len(source.mode_components) if source.mode_components is not None else 1
                for source in sources
            ),
        )
        if sources
        else 1
    )
    lattice_size = _estimate_mode_lattice_size(sources, n_modulation_harmonics)
    return (
        "Estimated mode lattice: "
        f"{lattice_size} sideband states "
        f"({tone_count} tone(s), Nmod={n_modulation_harmonics}). "
        "Multi-pump runs can take significantly longer."
    )
