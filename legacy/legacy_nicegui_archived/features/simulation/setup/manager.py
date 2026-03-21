"""Simulation setup CRUD helpers for the Simulation page UI."""

from __future__ import annotations

import copy
from datetime import datetime
from typing import Any
from uuid import uuid4


def is_builtin_setup(setup: dict[str, Any]) -> bool:
    """Return whether one setup record is built-in and immutable."""
    return str(setup.get("saved_at")) == "builtin"


def get_setup_by_id(setups: list[dict[str, Any]], setup_id: str) -> dict[str, Any] | None:
    """Resolve one setup record by id."""
    token = str(setup_id).strip()
    if not token:
        return None
    for setup in setups:
        if str(setup.get("id")) == token:
            return setup
    return None


def save_setup_as(
    setups: list[dict[str, Any]],
    *,
    name: str,
    payload: dict[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Create one new setup from current form values."""
    normalized_name = _normalize_setup_name(name)
    _raise_if_name_conflicts(setups, normalized_name)
    setup_record = {
        "id": f"user:{uuid4().hex}",
        "name": normalized_name,
        "saved_at": datetime.now().isoformat(),
        "payload": copy.deepcopy(payload),
    }
    return ([*setups, setup_record], setup_record)


def rename_setup(
    setups: list[dict[str, Any]],
    *,
    setup_id: str,
    new_name: str,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Rename one existing setup while preserving its payload."""
    setup_record = get_setup_by_id(setups, setup_id)
    if setup_record is None:
        raise ValueError("Setup not found.")
    if is_builtin_setup(setup_record):
        raise ValueError("Built-in setups cannot be renamed.")

    normalized_name = _normalize_setup_name(new_name)
    _raise_if_name_conflicts(
        setups,
        normalized_name,
        ignore_setup_id=str(setup_record.get("id") or ""),
    )

    updated_record = {**setup_record, "name": normalized_name}
    updated_setups = [
        updated_record if str(entry.get("id")) == str(updated_record.get("id")) else entry
        for entry in setups
    ]
    return (updated_setups, updated_record)


def delete_setup(setups: list[dict[str, Any]], *, setup_id: str) -> list[dict[str, Any]]:
    """Delete one mutable setup by id."""
    setup_record = get_setup_by_id(setups, setup_id)
    if setup_record is None:
        raise ValueError("Setup not found.")
    if is_builtin_setup(setup_record):
        raise ValueError("Built-in setups cannot be deleted.")
    return [entry for entry in setups if str(entry.get("id")) != str(setup_record.get("id"))]


def _normalize_setup_name(name: str) -> str:
    normalized = str(name or "").strip()
    if not normalized:
        raise ValueError("Setup name is required.")
    return normalized


def _raise_if_name_conflicts(
    setups: list[dict[str, Any]],
    name: str,
    *,
    ignore_setup_id: str | None = None,
) -> None:
    token = name.casefold()
    for setup in setups:
        setup_id = str(setup.get("id") or "")
        if ignore_setup_id and setup_id == ignore_setup_id:
            continue
        if str(setup.get("name", "")).strip().casefold() == token:
            raise ValueError("Setup name already exists.")
