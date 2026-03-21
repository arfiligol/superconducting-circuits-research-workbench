"""Central App Layout Shell for NiceGUI Data Browser."""

from __future__ import annotations

from typing import Any

from nicegui import app, ui


def _is_client_alive(client: Any) -> bool:
    """Return whether a NiceGUI client can still receive UI updates."""
    if client is None:
        return False
    client_id = getattr(client, "id", None)
    client_instances = getattr(type(client), "instances", {})
    return (
        client_id in client_instances
        and not getattr(client, "_deleted", False)
        and getattr(client, "has_socket_connection", False)
    )


def _prune_refreshable_targets(refreshable: Any, owner_client: Any) -> bool:
    """Keep only live targets that still belong to the owner client."""
    owner_client_id = getattr(owner_client, "id", None)
    live_targets = []
    for target in list(getattr(refreshable, "targets", [])):
        container = getattr(target, "container", None)
        if container is None or getattr(container, "is_deleted", False):
            continue
        target_client = getattr(container, "client", None)
        if getattr(target_client, "id", None) != owner_client_id:
            continue
        live_targets.append(target)
    refreshable.targets = live_targets
    return bool(live_targets)


def app_shell(content_builder):
    """
    App shell wrapper that provides the consistent header, drawer, and style.
    Can be used as a decorator or a function call.
    """
    # Load foundational CSS
    ui.add_css(
        """
        /* Temporary loading of our custom CSS */
        .nicegui-content {
            max-width: 100% !important;
            width: 100% !important;
            padding: 0 !important;
        }
    """,
        shared=True,
    )

    def wrapper(*args, **kwargs):
        owner_client = ui.context.client
        lifecycle_state = {
            "connected": _is_client_alive(owner_client),
            "deleted": False,
        }

        # Global body setup (Dark mode handled globally in ui.run(dark=True))
        ui.query("body").classes("bg-bg text-fg")

        # Refreshable content area — re-renders when Active Datasets change
        @ui.refreshable
        def content_area():
            content_builder(*args, **kwargs)

        def _mark_connected(_client: Any | None = None) -> None:
            lifecycle_state["connected"] = True
            lifecycle_state["deleted"] = False

        def _mark_disconnected(_client: Any | None = None) -> None:
            lifecycle_state["connected"] = False

        def _mark_deleted(_client: Any | None = None) -> None:
            lifecycle_state["connected"] = False
            lifecycle_state["deleted"] = True
            content_area.targets = []

        if owner_client is not None:
            owner_client.on_connect(_mark_connected)
            owner_client.on_disconnect(_mark_disconnected)
            owner_client.on_delete(_mark_deleted)

        def _safe_refresh_content_area() -> None:
            """Refresh content area only while its owner client is still alive."""
            if lifecycle_state["deleted"] or not lifecycle_state["connected"]:
                return
            if not _is_client_alive(owner_client):
                lifecycle_state["connected"] = False
                return
            if not _prune_refreshable_targets(content_area, owner_client):
                return
            try:
                content_area.refresh()
            except RuntimeError:
                # Ignore stale refresh attempts from deleted clients.
                return

        # Dataset Context Selector
        from core.shared.persistence import get_unit_of_work

        def fetch_dataset_options():
            try:
                with get_unit_of_work() as uow:
                    datasets = uow.datasets.list_all()
                    return {ds.id: ds.name for ds in datasets}
            except Exception:
                return {}

        def on_dataset_change(event):
            app.storage.user["selected_datasets"] = list(getattr(event, "value", []) or [])
            _safe_refresh_content_area()

        def build_dataset_selector(extra_classes: str = ""):
            selector = ui.select(
                options=fetch_dataset_options(),
                multiple=True,
                with_input=True,
                clearable=True,
                label="Active Datasets",
                on_change=on_dataset_change,
            )
            selector.classes(
                f"app-header-dataset-select w-full min-w-0 {extra_classes}".strip()
            ).bind_value(app.storage.user, "selected_datasets").props(
                "use-chips dense outlined options-dense"
            )
            return selector

        # App Header
        # Dark mode state management — syncs with global app storage & client-side Plotly
        if "dark_mode" not in app.storage.user or app.storage.user["dark_mode"] is None:
            app.storage.user["dark_mode"] = True

        dark = ui.dark_mode().bind_value(app.storage.user, "dark_mode")
        if "nav_left_drawer_open" not in app.storage.user:
            app.storage.user["nav_left_drawer_open"] = False

        with ui.header(elevated=False).classes(
            "bg-surface text-fg border-b border-border h-16 flex items-center "
            "no-wrap gap-3 px-4 overflow-hidden"
        ):
            ui.button(on_click=lambda: left_drawer.toggle(), icon="menu").props("flat").classes(
                "text-fg shrink-0"
            )
            with ui.row().classes("flex-1 min-w-0 items-center no-wrap gap-3"):
                ui.label("🔬 SC Tutorial App").classes(
                    "text-xl font-semibold text-fg truncate shrink min-w-0"
                )
                with ui.row().classes("flex-1 min-w-0 items-center no-wrap"):
                    build_dataset_selector()

            ui.button(on_click=dark.toggle).props("flat round tooltip='Toggle Dark Mode'").classes(
                "text-fg shrink-0"
            ).bind_icon_from(dark, "value", lambda v: "light_mode" if v else "dark_mode")

        # --- Client-side Plotly theme sync via MutationObserver ---
        # Watches Quasar's body.body--dark class and calls Plotly.relayout()
        # on every chart. Zero server round-trips, zero state loss.
        ui.add_head_html(
            """
        <script>
        document.addEventListener('DOMContentLoaded', function() {
          // Use flattened keys for Plotly.relayout to gracefully merge properties
          // rather than completely overwriting the server-generated layout
          // (which wipes titles/legends).
          const DARK_LAYOUT = {
            'paper_bgcolor': 'rgb(30, 41, 59)',
            'plot_bgcolor': 'rgb(15, 23, 42)',
            'font.color': 'rgb(226, 232, 240)',
            'font.family': 'Inter, Arial, sans-serif',
            'xaxis.gridcolor': 'rgb(51, 65, 85)',
            'xaxis.zerolinecolor': 'rgb(51, 65, 85)',
            'yaxis.gridcolor': 'rgb(51, 65, 85)',
            'yaxis.zerolinecolor': 'rgb(51, 65, 85)'
          };
          const LIGHT_LAYOUT = {
            'paper_bgcolor': 'rgb(255, 255, 255)',
            'plot_bgcolor': 'rgb(248, 250, 252)',
            'font.color': 'rgb(15, 23, 42)',
            'font.family': 'Inter, Arial, sans-serif',
            'xaxis.gridcolor': 'rgb(226, 232, 240)',
            'xaxis.zerolinecolor': 'rgb(226, 232, 240)',
            'yaxis.gridcolor': 'rgb(226, 232, 240)',
            'yaxis.zerolinecolor': 'rgb(226, 232, 240)'
          };

          function relayoutAll() {
            requestAnimationFrame(function() {
              const isDark = document.body.classList.contains('body--dark');
              const layoutUpdate = isDark ? DARK_LAYOUT : LIGHT_LAYOUT;
              document.querySelectorAll('.js-plotly-plot').forEach(function(el) {
                if (typeof Plotly !== 'undefined') {
                  Plotly.relayout(el, layoutUpdate);
                }
              });
            });
          }

          // Watch for Quasar dark-mode class toggle on <body>
          const observer = new MutationObserver(function(mutations) {
            for (const m of mutations) {
              if (m.attributeName === 'class') { relayoutAll(); return; }
            }
          });
          observer.observe(document.body, { attributes: true, attributeFilter: ['class'] });
        });
        </script>
        """,
            shared=True,
        )

        # Navigation Drawer
        left_drawer_state = bool(app.storage.user.get("nav_left_drawer_open", False))
        with (
            ui.left_drawer(value=left_drawer_state, elevated=False)
            .bind_value(app.storage.user, "nav_left_drawer_open")
            .classes("bg-surface text-fg flex flex-col pt-4 gap-2")
            .props("width=220") as left_drawer,
            ui.column().classes("w-full px-1"),
        ):

            def nav_btn(label: str, icon_name: str, route: str, disabled: bool = False):
                with (
                    ui.button(
                        on_click=lambda _e=None, r=route: (
                            ui.navigate.to(r) if not disabled else None
                        )
                    )
                    .classes("w-full px-4")
                    .props(f"flat no-caps dense {'disable' if disabled else ''}"),
                    ui.row().classes("items-center no-wrap w-full"),
                ):
                    with ui.row().classes("w-8 justify-start"):
                        ui.icon(icon_name, size="sm")
                    ui.label(label).classes("text-sm")

            ui.label("DASHBOARD").classes("text-xs text-muted font-bold tracking-wider mb-1 px-4")
            nav_btn("Home", "home", "/")

            ui.separator().classes("my-4 mx-4 bg-border")

            ui.label("PIPELINE").classes("text-xs text-muted font-bold tracking-wider mb-1 px-4")
            nav_btn("Dashboard", "dashboard", "/dashboard")
            nav_btn("Raw Data", "folder_zip", "/raw-data")
            nav_btn("Characterization", "analytics", "/characterization")

            ui.separator().classes("my-4 mx-4 bg-border")

            ui.label("CIRCUIT SIMULATION").classes(
                "text-xs text-muted font-bold tracking-wider mb-1 px-4"
            )
            nav_btn("Schemas", "account_tree", "/schemas")
            nav_btn("Simulation", "science", "/simulation")
            nav_btn("Schemdraw", "draw", "/schemdraw-live-preview")

        # Main Content Area
        with ui.column().classes("w-full px-4 py-3 gap-6"):
            content_area()

    return wrapper
