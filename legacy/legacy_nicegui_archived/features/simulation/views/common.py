"""Shared view helpers for simulation feature modules."""

from __future__ import annotations

from typing import Any

from nicegui import app
from legacy.legacy_nicegui_archived.ui.testing import with_test_id as _with_test_id

_Z0_CONTROL_PROPS = "dense outlined"
_Z0_CONTROL_CLASSES = "w-32"


def _user_storage_get(key: str, default: Any = None) -> Any:
    """Safely read one value from user storage with non-UI-context fallback."""
    try:
        return app.storage.user.get(key, default)
    except RuntimeError:
        return default


def _user_storage_set(key: str, value: Any) -> None:
    """Safely write one value into user storage when UI context is available."""
    try:
        app.storage.user[key] = value
    except RuntimeError:
        return
