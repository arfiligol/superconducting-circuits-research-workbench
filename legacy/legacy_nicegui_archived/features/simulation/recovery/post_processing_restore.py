"""Restore prompt rendering for persisted simulation recovery."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from nicegui import ui

from legacy.legacy_nicegui_archived.api.schemas import LatestTraceBatchResponse


def render_simulation_restore_prompt(
    *,
    latest_result: LatestTraceBatchResponse,
    simulation_results_container: Any | None,
    simulation_sweep_results_container: Any | None,
    post_processing_container: Any | None,
    on_load_latest: Callable[[], None],
) -> None:
    """Render the restore prompt for the latest persisted raw simulation result."""
    if simulation_results_container is None:
        return
    simulation_results_container.clear()
    with simulation_results_container:
        ui.icon("restore", size="lg").classes("text-primary mb-2")
        ui.label("Latest persisted simulation result is available.").classes("text-sm text-fg")
        ui.label(
            f"batch=#{latest_result.batch_id} | task={latest_result.task_id or 'n/a'}"
        ).classes("text-xs text-muted")
        ui.button(
            "Load Latest Persisted Result",
            on_click=on_load_latest,
            icon="download",
        ).props("outline color=primary").classes("mt-3")
    if simulation_sweep_results_container is not None:
        simulation_sweep_results_container.clear()
        with simulation_sweep_results_container:
            ui.label(
                "Sweep Result View is available after loading the latest persisted result."
            ).classes("text-sm text-muted")
    if post_processing_container is not None:
        post_processing_container.clear()
        with post_processing_container:
            ui.label(
                "Load the latest persisted simulation result to enable post-processing."
            ).classes("text-sm text-muted")


def render_post_processing_restore_prompt(
    *,
    latest_result: LatestTraceBatchResponse,
    post_processing_results_container: Any | None,
    post_processing_sweep_results_container: Any | None,
    on_load_latest: Callable[[], None],
) -> None:
    """Render the restore prompt for the latest persisted post-processing result."""
    if post_processing_results_container is not None:
        post_processing_results_container.clear()
        with post_processing_results_container:
            ui.icon("restore", size="lg").classes("text-primary mb-2")
            ui.label("Latest persisted post-processing result is available.").classes(
                "text-sm text-fg"
            )
            ui.label(
                "batch="
                f"#{latest_result.batch_id} | source-batch="
                f"#{latest_result.parent_batch_id or 'n/a'} | task="
                f"{latest_result.task_id or 'n/a'}"
            ).classes("text-xs text-muted")
            ui.button(
                "Load Latest Post-Processing Result",
                on_click=on_load_latest,
                icon="download",
            ).props("outline color=primary").classes("mt-3")
    if post_processing_sweep_results_container is not None:
        post_processing_sweep_results_container.clear()
        with post_processing_sweep_results_container:
            ui.label(
                "Post-processed sweep explorer is available after loading the latest "
                "persisted post-processing result."
            ).classes("text-sm text-muted")


def render_unavailable_authority_state(
    *,
    simulation_results_container: Any | None,
    simulation_sweep_results_container: Any | None,
    post_processing_container: Any | None,
    post_processing_results_container: Any | None,
    post_processing_sweep_results_container: Any | None,
) -> None:
    """Render placeholder state when no valid active dataset is available."""
    if simulation_results_container is not None:
        simulation_results_container.clear()
        with simulation_results_container:
            ui.icon("info", size="lg").classes("text-primary mb-2")
            ui.label(
                "Select a valid active dataset to load persisted simulation tasks."
            ).classes("text-sm text-muted")
    if simulation_sweep_results_container is not None:
        simulation_sweep_results_container.clear()
        with simulation_sweep_results_container:
            ui.label(
                "Sweep Result View is unavailable until an active dataset is selected."
            ).classes("text-sm text-muted")
    if post_processing_container is not None:
        post_processing_container.clear()
        with post_processing_container:
            ui.label(
                "Post Processing is unavailable until an active dataset is selected."
            ).classes("text-sm text-muted")
    if post_processing_results_container is not None:
        post_processing_results_container.clear()
        with post_processing_results_container:
            ui.label(
                "Post-processing results are unavailable until an active dataset is selected."
            ).classes("text-sm text-muted")
    if post_processing_sweep_results_container is not None:
        post_processing_sweep_results_container.clear()
        with post_processing_sweep_results_container:
            ui.label(
                "Post-processed sweep explorer is unavailable until an active dataset is selected."
            ).classes("text-sm text-muted")
