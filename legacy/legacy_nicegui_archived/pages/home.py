"""Dashboard for the SC Data Browser."""

from nicegui import ui

from legacy.legacy_nicegui_archived.layout import app_shell
from core.shared.persistence import get_unit_of_work


def _get_db_stats():
    """Get basic database stats for the dashboard."""
    try:
        with get_unit_of_work() as uow:
            datasets = len(uow.datasets.list_all())
            records = len(uow.data_records.list_all())
            return {"datasets": datasets, "records": records, "status": "Connected"}
    except Exception as e:
        return {"datasets": 0, "records": 0, "status": f"Error: {e}"}


@ui.page("/")
def home_page():
    """Home dashboard page."""

    def content():
        ui.label("Dashboard").classes("text-2xl font-bold text-fg mb-4")

        stats = _get_db_stats()

        # Top Stats Row
        with ui.row().classes("w-full gap-6 flex-wrap"):
            with ui.column().classes("app-card p-6 flex-1 min-w-[200px]"):
                ui.label("Database Status").classes(
                    "text-sm text-muted font-semibold uppercase tracking-wider"
                )
                status_class = "text-success" if stats["status"] == "Connected" else "text-danger"
                ui.label(stats["status"]).classes(f"text-xl font-bold {status_class} mt-2")

            with ui.column().classes("app-card p-6 flex-1 min-w-[200px]"):
                ui.label("Total Datasets").classes(
                    "text-sm text-muted font-semibold uppercase tracking-wider"
                )
                ui.label(str(stats["datasets"])).classes("text-3xl font-bold text-fg mt-2")

            with ui.column().classes("app-card p-6 flex-1 min-w-[200px]"):
                ui.label("Data Records").classes(
                    "text-sm text-muted font-semibold uppercase tracking-wider"
                )
                ui.label(str(stats["records"])).classes("text-3xl font-bold text-fg mt-2")

        ui.separator().classes("my-8 bg-border")

        # Quick Actions
        ui.label("Modules").classes("text-xl font-bold text-fg mb-4")
        with ui.row().classes("w-full gap-6 flex-wrap align-stretch"):
            with ui.column().classes(
                "app-card p-6 w-full md:w-[calc(50%-12px)] lg:w-[calc(33%-16px)] items-start"
            ):
                ui.icon("analytics", size="2rem").classes("text-primary mb-2")
                ui.label("Data Browser").classes("app-section-title")
                ui.label(
                    "Explore simulation and measurement data interactively with Plotly charts."
                ).classes("text-muted text-sm mt-1 mb-4 flex-grow")
                ui.button("Open Browser", on_click=lambda: ui.navigate.to("/data-browser")).classes(
                    "app-btn-primary w-full"
                )

            with ui.column().classes(
                "app-card p-6 w-full md:w-[calc(50%-12px)] lg:w-[calc(33%-16px)] "
                "items-start opacity-70"
            ):
                ui.icon("functions", size="2rem").classes("text-muted mb-2")
                ui.label("Analysis (Planned)").classes("app-section-title text-muted mb-4")
                ui.label("Perform Resonance and SQUID fits directly from the UI.").classes(
                    "text-muted text-sm mt-1 mb-4 flex-grow"
                )
                ui.button("Coming Soon").classes("app-btn-primary w-full").props("disable")

            with ui.column().classes(
                "app-card p-6 w-full md:w-[calc(50%-12px)] lg:w-[calc(33%-16px)] "
                "items-start opacity-70"
            ):
                ui.icon("science", size="2rem").classes("text-muted mb-2")
                ui.label("Simulation (Planned)").classes("app-section-title text-muted mb-4")
                ui.label("Run Julia-based Josephson Circuits simulations.").classes(
                    "text-muted text-sm mt-1 mb-4 flex-grow"
                )
                ui.button("Coming Soon").classes("app-btn-primary w-full").props("disable")

    # Apply app shell
    app_shell(content)()
