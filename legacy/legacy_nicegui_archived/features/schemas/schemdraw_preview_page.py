"""Standalone Schemdraw editor with live SVG preview for WebUI."""

from __future__ import annotations

import asyncio
import hashlib
import json
from collections.abc import Coroutine
from typing import Any
from uuid import uuid4

from nicegui import app, ui

from legacy.legacy_nicegui_archived.services.browser_tooling import (
    build_schema_formatter_hotkey_js,
    build_schema_formatter_js,
    build_schematic_preview_action_js,
    build_schematic_preview_render_js,
)
from legacy.legacy_nicegui_archived.services.schemdraw_live_preview import (
    build_relation_context,
    parse_relation_config_text,
    render_schemdraw_preview,
)
from core.shared.persistence import get_unit_of_work

_SOURCE_STORAGE_KEY = "schemdraw_live_preview_source"
_RELATION_STORAGE_KEY = "schemdraw_live_preview_relation"
_SCHEMA_ID_STORAGE_KEY = "schemdraw_live_preview_schema_id"

_DEFAULT_SOURCE = """import schemdraw
import schemdraw.elements as elm

# `relation` is injected by WebUI:
# {
#   "schema": {"id": int | null, "name": str | null},
#   "config": {...}
# }

def build_drawing(relation):
    schema_name = relation.get("schema", {}).get("name") or "No linked schema"
    relation_tag = relation.get("config", {}).get("tag", "draft")

    d = schemdraw.Drawing(canvas="svg", show=False)
    d += elm.SourceSin().label("P1")
    d += elm.Line().right().length(1.2)
    d += elm.Resistor().label("R1")
    d += elm.Line().right().length(1.2)
    d += elm.Capacitor().label("C1")
    d += elm.Line().right().length(0.8)
    d += elm.Ground()

    d += elm.Label().at((5.0, 1.6)).label(f"schema: {schema_name}")
    d += elm.Label().at((5.0, 1.2)).label(f"relation tag: {relation_tag}", fontsize=10)
    return d
"""

_DEFAULT_RELATION_CONFIG = json.dumps(
    {
        "tag": "draft",
        "labels": {
            "P1": "input",
            "R1": "series",
            "C1": "shunt",
        },
    },
    indent=2,
)


def build_page() -> None:
    """Render an isolated Schemdraw live-preview workspace."""

    def content() -> None:
        client = ui.context.client
        ui.label("Schemdraw Live Preview").classes("text-2xl font-bold text-fg")
        ui.label(
            "Write standalone Schemdraw code in WebUI and see SVG updates live. "
            "This workspace is isolated and does not modify existing schema/simulation pages."
        ).classes("text-sm text-muted")

        schema_options = _load_schema_options()
        preview_root_id = f"schemdraw-preview-{uuid4().hex}"
        zoom_label_id = f"schemdraw-zoom-{uuid4().hex}"

        saved_source = app.storage.user.get(_SOURCE_STORAGE_KEY, _DEFAULT_SOURCE)
        editor_source = saved_source if isinstance(saved_source, str) else _DEFAULT_SOURCE

        saved_relation = app.storage.user.get(_RELATION_STORAGE_KEY, _DEFAULT_RELATION_CONFIG)
        relation_source = (
            saved_relation if isinstance(saved_relation, str) else _DEFAULT_RELATION_CONFIG
        )

        stored_schema_id = app.storage.user.get(_SCHEMA_ID_STORAGE_KEY, 0)
        try:
            active_schema_id = int(stored_schema_id)
        except (TypeError, ValueError):
            active_schema_id = 0
        if active_schema_id not in schema_options:
            active_schema_id = 0

        pending_task: asyncio.Task[None] | None = None
        render_revision = 0

        def schedule_task(coro: Coroutine[Any, Any, None]) -> asyncio.Task[None]:
            """Run background tasks and consume exceptions to avoid task-leak warnings."""
            task = asyncio.create_task(coro)

            def _finalize(done: asyncio.Task[None]) -> None:
                try:
                    done.result()
                except asyncio.CancelledError:
                    return
                except Exception as exc:
                    render_error.text = str(exc)
                    render_error.classes(add="block", remove="hidden")
                    render_status.text = "Background render failed."

            task.add_done_callback(_finalize)
            return task

        with ui.row().classes("w-full gap-6 flex-wrap lg:flex-nowrap"):
            with ui.column().classes("app-card w-full lg:w-[45%] p-6 gap-4"):
                ui.label("Editor").classes("app-section-title mb-4")

                schema_select = (
                    ui.select(
                        label="Linked Schema (optional)",
                        options=schema_options,
                        value=active_schema_id,
                    )
                    .props("dense outlined options-dense")
                    .classes("w-full")
                )

                relation_input = ui.textarea(
                    label="Relation Config (JSON)",
                    value=relation_source,
                    placeholder='{"tag": "draft", "labels": {"P1": "input"}}',
                ).props("outlined autogrow")
                relation_input.classes("w-full")

                ui.label("Schemdraw Python Source").classes("text-sm text-muted")
                editor_theme = (
                    "vscodeDark" if app.storage.user.get("dark_mode", True) else "vscodeLight"
                )
                code_input = ui.codemirror(
                    value=editor_source,
                    language="Python",
                    theme=editor_theme,
                    indent=" " * 4,
                ).classes("w-full app-netlist-editor")

                with ui.row().classes("w-full items-center gap-2"):
                    format_button = ui.button(
                        "Format",
                        icon="auto_fix_high",
                    ).props("outline size=sm")
                    render_button = ui.button(
                        "Render Now",
                        icon="play_arrow",
                    ).props("color=primary size=sm")
                    reset_button = ui.button(
                        "Reset Template",
                        icon="restart_alt",
                    ).props("outline size=sm")

                ui.label("Shortcut: Ctrl/Cmd + Shift + F").classes("text-xs text-muted")
                ui.label(
                    'Tip: insert `probe_here(d, "name")` to record cursor coordinates at that line.'
                ).classes("text-xs text-muted")
                format_status = ui.label("").classes("text-xs text-muted hidden")

            with ui.column().classes("w-full lg:w-[55%] flex flex-col gap-6"):
                with ui.column().classes("app-card w-full p-6"):
                    with ui.row().classes("w-full items-center justify-between mb-4"):
                        with ui.row().classes("items-center gap-2"):
                            ui.label("Live Preview").classes("app-section-title")
                            ui.label("100%").classes("text-xs text-muted").props(
                                f"id={zoom_label_id}"
                            )
                        with ui.row().classes("items-center gap-2"):
                            zoom_in_button = ui.button(icon="zoom_in").props("flat dense round")
                            zoom_out_button = ui.button(icon="zoom_out").props("flat dense round")
                            zoom_reset_button = ui.button(icon="fit_screen").props(
                                "flat dense round"
                            )

                    ui.html(
                        f"<div id='{preview_root_id}' class='app-schematic-preview w-full'></div>"
                    ).classes("w-full app-schematic-preview")

                    render_status = ui.label("Live preview ready.").classes("text-xs text-muted")
                    render_error = ui.label("").classes("text-sm text-danger hidden")
                    pen_position_label = ui.label("Pen cursor: N/A").classes("text-xs text-muted")
                    probe_points_label = ui.label("Probe points: (none)").classes(
                        "text-xs text-muted whitespace-pre-wrap break-all"
                    )

                with ui.column().classes("app-card w-full p-6"):
                    ui.label("Relation Context Contract").classes("app-section-title mb-4")
                    ui.label(
                        "Use `relation['schema']` for linked schema metadata and "
                        "`relation['config']` for your manual labels/mappings."
                    ).classes("text-sm text-muted")

        def selected_schema_snapshot(selected_id: int) -> tuple[int | None, str | None]:
            if selected_id == 0:
                return None, None
            schema_name = schema_options.get(selected_id)
            if schema_name is None:
                return None, None
            return selected_id, schema_name

        async def run_render(live_trigger: bool = False) -> None:
            nonlocal render_revision

            if live_trigger:
                await asyncio.sleep(0.4)

            relation_id, relation_name = selected_schema_snapshot(int(schema_select.value or 0))

            try:
                relation_config = parse_relation_config_text(relation_input.value or "")
            except ValueError as exc:
                render_error.text = str(exc)
                render_error.classes(add="block", remove="hidden")
                render_status.text = "Preview kept from last successful render."
                return

            relation_context = build_relation_context(
                schema_id=relation_id,
                schema_name=relation_name,
                config=relation_config,
            )

            try:
                render_result = render_schemdraw_preview(
                    code_input.value,
                    relation_context=relation_context,
                )
            except ValueError as exc:
                render_error.text = str(exc)
                render_error.classes(add="block", remove="hidden")
                render_status.text = "Preview kept from last successful render."
                return

            render_error.text = ""
            render_error.classes(add="hidden", remove="block")
            app.storage.user[_SOURCE_STORAGE_KEY] = code_input.value
            app.storage.user[_RELATION_STORAGE_KEY] = relation_input.value
            app.storage.user[_SCHEMA_ID_STORAGE_KEY] = int(schema_select.value or 0)

            render_revision += 1
            source_hash = hashlib.sha256(code_input.value.encode("utf-8")).hexdigest()[:12]
            relation_hash = hashlib.sha256(
                json.dumps(relation_context, sort_keys=True).encode("utf-8")
            ).hexdigest()[:12]
            await client.run_javascript(
                build_schematic_preview_render_js(
                    root_id=preview_root_id,
                    label_id=zoom_label_id,
                    svg_content=render_result.svg_content,
                    schema_key=f"v{render_revision}:{source_hash}:{relation_hash}",
                    empty_html="<div class='text-muted text-sm'>No preview</div>",
                )
            )
            if render_result.pen_position is None:
                pen_position_label.text = "Pen cursor: N/A"
            else:
                pen_x, pen_y = render_result.pen_position
                pen_position_label.text = f"Pen cursor: ({pen_x:.4f}, {pen_y:.4f})"
            if not render_result.probe_points:
                probe_points_label.text = "Probe points: (none)"
            else:
                probe_lines = ["Probe points:"]
                for label, (probe_x, probe_y) in render_result.probe_points:
                    probe_lines.append(f"- {label}: ({probe_x:.4f}, {probe_y:.4f})")
                probe_points_label.text = "\n".join(probe_lines)
            render_status.text = "Live preview updated."

        def schedule_live_render(_event: Any = None) -> None:
            nonlocal pending_task
            if pending_task is not None and not pending_task.done():
                pending_task.cancel()
            pending_task = schedule_task(run_render(live_trigger=True))

        async def format_source() -> None:
            format_status.classes(add="block", remove="hidden")
            format_status.text = "Formatting..."
            try:
                result = await client.run_javascript(build_schema_formatter_js(code_input.value))
            except Exception as exc:
                format_status.text = f"Format failed: {exc}"
                return

            if not isinstance(result, dict) or not bool(result.get("ok")):
                message = "Formatter unavailable."
                if isinstance(result, dict):
                    message = str(result.get("error", message))
                format_status.text = f"Format failed: {message}"
                return

            formatted = str(result.get("text", ""))
            if formatted != code_input.value:
                code_input.set_value(formatted)
            format_status.text = "Formatted with Ruff WebAssembly."
            await run_render(live_trigger=False)

        schema_select.on_value_change(schedule_live_render)
        relation_input.on_value_change(schedule_live_render)
        code_input.on_value_change(schedule_live_render)

        format_button.on_click(lambda: schedule_task(format_source()))
        render_button.on_click(lambda: schedule_task(run_render(live_trigger=False)))
        reset_button.on_click(
            lambda: (
                code_input.set_value(_DEFAULT_SOURCE),
                relation_input.set_value(_DEFAULT_RELATION_CONFIG),
                schema_select.set_value(0),
                schedule_live_render(),
            )
        )
        zoom_in_button.on_click(
            lambda: ui.run_javascript(
                build_schematic_preview_action_js(
                    action="zoomIn",
                    root_id=preview_root_id,
                )
            )
        )
        zoom_out_button.on_click(
            lambda: ui.run_javascript(
                build_schematic_preview_action_js(
                    action="zoomOut",
                    root_id=preview_root_id,
                )
            )
        )
        zoom_reset_button.on_click(
            lambda: ui.run_javascript(
                build_schematic_preview_action_js(
                    action="reset",
                    root_id=preview_root_id,
                )
            )
        )
        ui.run_javascript(
            build_schema_formatter_hotkey_js(
                button_id=format_button.html_id,
                scope_id=code_input.html_id,
            )
        )
        pending_task = schedule_task(run_render(live_trigger=False))

    content()


def _load_schema_options() -> dict[int, str]:
    """Load schema options for optional relation linking."""
    options: dict[int, str] = {0: "No linked schema"}
    try:
        with get_unit_of_work() as uow:
            circuits = uow.circuits.list_all()
    except Exception:
        return options

    for circuit in circuits:
        circuit_id = circuit.id
        if circuit_id is None:
            continue
        options[int(circuit_id)] = str(circuit.name)
    return options
