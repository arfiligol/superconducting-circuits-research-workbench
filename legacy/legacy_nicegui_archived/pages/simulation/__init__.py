"""Simulation route wrapper delegating to the feature package."""

from __future__ import annotations

import importlib
from nicegui import ui

from legacy.legacy_nicegui_archived.layout import app_shell


def _feature_page():
    return importlib.import_module("legacy.legacy_nicegui_archived.features.simulation.page")


def __getattr__(name: str):
    return getattr(_feature_page(), name)


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(dir(_feature_page())))


@ui.page("/simulation")
def simulation_page() -> None:
    app_shell(_feature_page().build_page)()
