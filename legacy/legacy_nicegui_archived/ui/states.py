"""Shared empty and unavailable state blocks."""

from __future__ import annotations

from collections.abc import Callable

from nicegui import ui

_DEFAULT_EMPTY_STATE_CLASSES = (
    "w-full p-12 items-center justify-center border-2 border-dashed border-border rounded-xl"
)


def render_empty_state(
    *,
    icon: str,
    title: str,
    message: str,
    action_label: str | None = None,
    on_action: Callable[[], None] | None = None,
    container_classes: str = _DEFAULT_EMPTY_STATE_CLASSES,
    icon_classes: str = "text-muted mb-4 opacity-50",
    title_classes: str = "text-xl text-fg font-bold",
    message_classes: str = "text-sm text-muted mt-2",
) -> None:
    """Render one consistent empty or unavailable state block."""
    with ui.column().classes(container_classes):
        ui.icon(icon, size="xl").classes(icon_classes)
        ui.label(title).classes(title_classes)
        ui.label(message).classes(message_classes)
        if action_label and on_action is not None:
            ui.button(action_label, on_click=on_action).props("outline color=primary mt-4")
