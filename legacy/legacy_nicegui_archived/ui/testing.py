"""Shared UI testing helpers."""

from __future__ import annotations

from typing import Any


def with_test_id(element: Any, test_id: str) -> Any:
    """Attach one stable test id to a NiceGUI element."""
    try:
        element.props(f"data-testid={test_id}")
    except Exception:
        props = getattr(element, "_props", None)
        if isinstance(props, dict):
            props["data-testid"] = test_id
    return element
