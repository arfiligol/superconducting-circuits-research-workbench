"""Shared section-level UI wrappers."""

from __future__ import annotations

from nicegui import ui

_DEFAULT_SECTION_CARD_CLASSES = "w-full bg-surface rounded-xl p-6"


def section_card(*, classes: str = _DEFAULT_SECTION_CARD_CLASSES):
    """Return the standard surface card used for app sections."""
    return ui.card().classes(classes)
