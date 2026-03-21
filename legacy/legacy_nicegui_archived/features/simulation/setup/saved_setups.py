"""Saved setup storage and built-in setup seeds for simulation."""

from __future__ import annotations

from typing import Any, Callable

from .frequency_sweep import _build_setup_payload
from .sources import _build_source_payload

_SIM_SETUP_STORAGE_KEY = "simulation_saved_setups_by_schema"
_SIM_SETUP_SELECTED_KEY = "simulation_selected_setup_id_by_schema"
_JOSEPHSON_EXAMPLE_PREFIX = "JosephsonCircuits Examples: "

StorageGet = Callable[[str, Any], Any]
StorageSet = Callable[[str, Any], None]

_JOSEPHSON_BUILTIN_SETUP_PAYLOADS: dict[str, dict[str, Any]] = {
    "Josephson Parametric Amplifier (JPA)": _build_setup_payload(
        start_ghz=4.5,
        stop_ghz=5.0,
        points=501,
        n_modulation_harmonics=8,
        n_pump_harmonics=16,
        sources=[
            _build_source_payload(
                pump_freq_ghz=4.75001,
                port=1,
                current_amp=0.00565e-6,
                mode=(1,),
            )
        ],
    ),
    "Double-pumped Josephson Parametric Amplifier (JPA)": _build_setup_payload(
        start_ghz=4.5,
        stop_ghz=5.0,
        points=501,
        n_modulation_harmonics=8,
        n_pump_harmonics=8,
        sources=[
            _build_source_payload(
                pump_freq_ghz=4.65001,
                port=1,
                current_amp=0.00565e-6 * 1.7,
                mode=(1, 0),
            ),
            _build_source_payload(
                pump_freq_ghz=4.85001,
                port=1,
                current_amp=0.00565e-6 * 1.7,
                mode=(0, 1),
            ),
        ],
    ),
    "Flux-pumped Josephson Parametric Amplifier (JPA)": _build_setup_payload(
        start_ghz=9.7,
        stop_ghz=9.8,
        points=1001,
        n_modulation_harmonics=8,
        n_pump_harmonics=16,
        sources=[
            _build_source_payload(
                pump_freq_ghz=19.50,
                port=2,
                current_amp=140.3e-6,
                mode=(0,),
            ),
            _build_source_payload(
                pump_freq_ghz=19.50,
                port=2,
                current_amp=0.7e-6,
                mode=(1,),
            ),
        ],
        include_dc=True,
        enable_three_wave_mixing=True,
    ),
    "SNAIL Parametric Amplifier": _build_setup_payload(
        start_ghz=7.8,
        stop_ghz=8.2,
        points=401,
        n_modulation_harmonics=8,
        n_pump_harmonics=16,
        sources=[
            _build_source_payload(
                pump_freq_ghz=16.0,
                port=2,
                current_amp=0.000159,
                mode=(0,),
            ),
            _build_source_payload(
                pump_freq_ghz=16.0,
                port=2,
                current_amp=4.4e-6,
                mode=(1,),
            ),
        ],
        include_dc=True,
        enable_three_wave_mixing=True,
    ),
    "Josephson Traveling Wave Parametric Amplifier (JTWPA)": _build_setup_payload(
        start_ghz=1.0,
        stop_ghz=14.0,
        points=131,
        n_modulation_harmonics=10,
        n_pump_harmonics=20,
        sources=[
            _build_source_payload(
                pump_freq_ghz=7.12,
                port=1,
                current_amp=1.85e-6,
                mode=(1,),
            )
        ],
    ),
    "Floquet JTWPA": _build_setup_payload(
        start_ghz=1.0,
        stop_ghz=14.0,
        points=131,
        n_modulation_harmonics=10,
        n_pump_harmonics=20,
        sources=[
            _build_source_payload(
                pump_freq_ghz=7.9,
                port=1,
                current_amp=1.1e-6,
                mode=(1,),
            )
        ],
    ),
    "Floquet JTWPA with Dissipation": _build_setup_payload(
        start_ghz=1.0,
        stop_ghz=14.0,
        points=131,
        n_modulation_harmonics=10,
        n_pump_harmonics=20,
        sources=[
            _build_source_payload(
                pump_freq_ghz=7.9,
                port=1,
                current_amp=1.1e-6 * (1 + 125e-6),
                mode=(1,),
            )
        ],
    ),
    "Flux-Driven Josephson Traveling-Wave Parametric Amplifier (JTWPA)": _build_setup_payload(
        start_ghz=5.0,
        stop_ghz=25.0,
        points=500,
        n_modulation_harmonics=4,
        n_pump_harmonics=8,
        sources=[
            _build_source_payload(
                pump_freq_ghz=20.0,
                port=3,
                current_amp=0.00019921960989995077,
                mode=(0,),
            ),
            _build_source_payload(
                pump_freq_ghz=20.0,
                port=3,
                current_amp=1.1953176593997045e-05,
                mode=(1,),
            ),
        ],
        include_dc=True,
        enable_three_wave_mixing=True,
        max_iterations=200,
        line_search_switch_tol=1e-5,
        alpha_min=1e-7,
    ),
    "Impedance-engineered JPA": _build_setup_payload(
        start_ghz=4.0,
        stop_ghz=5.8,
        points=181,
        n_modulation_harmonics=4,
        n_pump_harmonics=8,
        sources=[
            _build_source_payload(
                pump_freq_ghz=9.8001,
                port=2,
                current_amp=0.686e-3,
                mode=(0,),
            ),
            _build_source_payload(
                pump_freq_ghz=9.8001,
                port=2,
                current_amp=0.247e-3,
                mode=(1,),
            ),
        ],
        include_dc=True,
        enable_three_wave_mixing=True,
        max_iterations=200,
        line_search_switch_tol=1e-5,
        alpha_min=1e-7,
    ),
}


def _builtin_saved_setups_for_schema(schema_name: str) -> list[dict[str, Any]]:
    """Return built-in saved setups for known JosephsonCircuits example schemas."""
    if not schema_name.startswith(_JOSEPHSON_EXAMPLE_PREFIX):
        return []

    example_name = schema_name.removeprefix(_JOSEPHSON_EXAMPLE_PREFIX).strip()
    payload = _JOSEPHSON_BUILTIN_SETUP_PAYLOADS.get(example_name)
    if payload is None:
        return []

    setup_slug = (
        example_name.lower().replace(" ", "-").replace("(", "").replace(")", "").replace(",", "")
    )
    return [
        {
            "id": f"builtin:{setup_slug}:official-example",
            "name": "Official Example",
            "saved_at": "builtin",
            "payload": payload,
        }
    ]


def _merge_saved_setups_with_builtin(
    existing_setups: list[dict[str, Any]],
    builtin_setups: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Merge built-in saved setups while preserving user-created setups."""
    if not builtin_setups:
        return existing_setups

    user_setups = [s for s in existing_setups if str(s.get("saved_at")) != "builtin"]
    return [*builtin_setups, *user_setups]


def _load_saved_setups_for_schema(
    schema_id: int,
    *,
    storage_get: StorageGet,
) -> list[dict[str, Any]]:
    """Load saved simulation setups for one schema from user storage."""
    raw_store = storage_get(_SIM_SETUP_STORAGE_KEY, {})
    if not isinstance(raw_store, dict):
        return []

    setups = raw_store.get(str(schema_id), [])
    if not isinstance(setups, list):
        return []
    return [setup for setup in setups if isinstance(setup, dict)]


def _save_saved_setups_for_schema(
    schema_id: int,
    setups: list[dict[str, Any]],
    *,
    storage_get: StorageGet,
    storage_set: StorageSet,
) -> None:
    """Persist saved simulation setups for one schema into user storage."""
    raw_store = storage_get(_SIM_SETUP_STORAGE_KEY, {})
    store_dict = dict(raw_store) if isinstance(raw_store, dict) else {}
    store_dict[str(schema_id)] = setups
    storage_set(_SIM_SETUP_STORAGE_KEY, store_dict)


def _load_selected_setup_id(
    schema_id: int,
    *,
    storage_get: StorageGet,
) -> str:
    """Load currently selected setup id for one schema from user storage."""
    raw_map = storage_get(_SIM_SETUP_SELECTED_KEY, {})
    if not isinstance(raw_map, dict):
        return ""

    selected = raw_map.get(str(schema_id), "")
    return selected if isinstance(selected, str) else ""


def _save_selected_setup_id(
    schema_id: int,
    setup_id: str,
    *,
    storage_get: StorageGet,
    storage_set: StorageSet,
) -> None:
    """Persist selected setup id for one schema into user storage."""
    raw_map = storage_get(_SIM_SETUP_SELECTED_KEY, {})
    selected_map = dict(raw_map) if isinstance(raw_map, dict) else {}
    selected_map[str(schema_id)] = setup_id
    storage_set(_SIM_SETUP_SELECTED_KEY, selected_map)


def _ensure_builtin_saved_setups(
    schema_id: int,
    schema_name: str,
    *,
    storage_get: StorageGet,
    storage_set: StorageSet,
) -> list[dict[str, Any]]:
    """Persist built-in example setups into user storage and return merged list."""
    existing_setups = _load_saved_setups_for_schema(schema_id, storage_get=storage_get)
    builtin_setups = _builtin_saved_setups_for_schema(schema_name)
    merged_setups = _merge_saved_setups_with_builtin(existing_setups, builtin_setups)
    if merged_setups != existing_setups:
        _save_saved_setups_for_schema(
            schema_id,
            merged_setups,
            storage_get=storage_get,
            storage_set=storage_set,
        )
    return merged_setups


def _has_selected_setup_entry(
    schema_id: int,
    *,
    storage_get: StorageGet,
) -> bool:
    """Return True when user storage already tracks a selected setup for this schema."""
    raw_map = storage_get(_SIM_SETUP_SELECTED_KEY, {})
    return isinstance(raw_map, dict) and str(schema_id) in raw_map
