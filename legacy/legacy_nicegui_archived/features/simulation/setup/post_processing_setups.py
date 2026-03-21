"""Saved post-processing setup storage for simulation feature."""

from __future__ import annotations

from typing import Any, Callable

_POST_PROCESS_SETUP_STORAGE_KEY = "simulation_post_process_saved_setups_by_schema"
_POST_PROCESS_SELECTED_KEY = "simulation_post_process_selected_setup_id_by_schema"

StorageGet = Callable[[str, Any], Any]
StorageSet = Callable[[str, Any], None]


def _load_saved_post_process_setups_for_schema(
    schema_id: int,
    *,
    storage_get: StorageGet,
) -> list[dict[str, Any]]:
    """Load saved post-processing setups for one schema."""
    raw_store = storage_get(_POST_PROCESS_SETUP_STORAGE_KEY, {})
    if not isinstance(raw_store, dict):
        return []
    setups = raw_store.get(str(schema_id), [])
    if not isinstance(setups, list):
        return []
    return [entry for entry in setups if isinstance(entry, dict)]


def _save_saved_post_process_setups_for_schema(
    schema_id: int,
    setups: list[dict[str, Any]],
    *,
    storage_get: StorageGet,
    storage_set: StorageSet,
) -> None:
    """Persist saved post-processing setups for one schema."""
    raw_store = storage_get(_POST_PROCESS_SETUP_STORAGE_KEY, {})
    store_dict = dict(raw_store) if isinstance(raw_store, dict) else {}
    store_dict[str(schema_id)] = setups
    storage_set(_POST_PROCESS_SETUP_STORAGE_KEY, store_dict)


def _load_selected_post_process_setup_id(
    schema_id: int,
    *,
    storage_get: StorageGet,
) -> str:
    """Load currently selected post-processing setup id for one schema."""
    raw_map = storage_get(_POST_PROCESS_SELECTED_KEY, {})
    if not isinstance(raw_map, dict):
        return ""
    selected = raw_map.get(str(schema_id), "")
    return selected if isinstance(selected, str) else ""


def _save_selected_post_process_setup_id(
    schema_id: int,
    setup_id: str,
    *,
    storage_get: StorageGet,
    storage_set: StorageSet,
) -> None:
    """Persist selected post-processing setup id for one schema."""
    raw_map = storage_get(_POST_PROCESS_SELECTED_KEY, {})
    selected_map = dict(raw_map) if isinstance(raw_map, dict) else {}
    selected_map[str(schema_id)] = setup_id
    storage_set(_POST_PROCESS_SELECTED_KEY, selected_map)
