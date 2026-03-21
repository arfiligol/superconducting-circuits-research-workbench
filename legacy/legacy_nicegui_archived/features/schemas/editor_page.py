"""Schema Editor page for simple circuit netlist definitions."""

from __future__ import annotations

from typing import Any

from nicegui import app, ui

from legacy.legacy_nicegui_archived.services.browser_tooling import (
    build_schema_formatter_hotkey_js,
    build_schema_formatter_js,
)
from core.shared.persistence import get_unit_of_work
from core.shared.persistence.models import CircuitRecord
from core.simulation.domain.circuit import (
    format_expanded_circuit_definition,
    parse_circuit_definition_source,
)

_DEFAULT_CIRCUIT_STR = """{
    "name": "SmokeStableSeriesLC",
    "components": [
        {"name": "R1", "default": 50.0, "unit": "Ohm"},
        {"name": "L1", "default": 10.0, "unit": "nH"},
        {"name": "C1", "default": 1.0, "unit": "pF"}
    ],
    "topology": [
        ("P1", "1", "0", 1),
        ("R1", "1", "0", "R1"),
        ("L1", "1", "2", "L1"),
        ("C1", "2", "0", "C1")
    ]
}"""

_COMPONENT_REF_COLUMNS = [
    {"name": "kind", "label": "Component", "field": "kind", "align": "left"},
    {"name": "prefix", "label": "Name Prefix", "field": "prefix", "align": "left"},
    {"name": "units", "label": "Allowed Units", "field": "units", "align": "left"},
    {"name": "example", "label": "Example", "field": "example", "align": "left"},
    {"name": "notes", "label": "Notes", "field": "notes", "align": "left"},
]

_COMPONENT_REF_ROWS = [
    {
        "kind": "Port",
        "prefix": "P*",
        "units": "-",
        "example": '("P1", "1", "0", 1)',
        "notes": "Declare ports only in topology. The last value is the integer port index.",
    },
    {
        "kind": "Resistor",
        "prefix": "R*",
        "units": "Ohm, kOhm, MOhm",
        "example": '{"name": "R1", "default": 50.0, "unit": "Ohm"}',
        "notes": 'Add the component in components, then reference it from topology as "R1".',
    },
    {
        "kind": "Inductor",
        "prefix": "L*",
        "units": "H, mH, uH, nH, pH",
        "example": '{"name": "L1", "default": 10.0, "unit": "nH"}',
        "notes": "Two-pin linear inductor.",
    },
    {
        "kind": "Capacitor",
        "prefix": "C*",
        "units": "F, mF, uF, nF, pF, fF",
        "example": '{"name": "C1", "default": 1.0, "unit": "pF"}',
        "notes": "Use the same component name as the topology value reference.",
    },
    {
        "kind": "Josephson Junction",
        "prefix": "Lj*",
        "units": "H, mH, uH, nH, pH",
        "example": '{"name": "Lj1", "default": 300.0, "unit": "pH"}',
        "notes": "Josephson junctions are inferred from the Lj prefix in the simple netlist.",
    },
]


def _stored_schema_text_from_editor(editor_text: str) -> str:
    """Persist the exact editor text so formatting remains user-controlled."""
    return editor_text


def _editor_text_from_record(definition_json: str) -> str:
    """Return the exact stored source text for existing records."""
    return definition_json


def build_page(schema_id: str) -> None:
    def content():
        circuit_record = None
        if schema_id != "new":
            try:
                with get_unit_of_work() as uow:
                    circuit_record = uow.circuits.get(int(schema_id))
            except Exception as exc:
                ui.label(f"Error loading circuit: {exc}").classes("text-danger")
                return

            if not circuit_record:
                ui.label("Circuit not found").classes("text-danger")
                return

        with ui.row().classes("w-full items-center gap-4 mb-6"):
            ui.button(icon="arrow_back", on_click=lambda: ui.navigate.to("/schemas")).props(
                "flat round"
            ).classes("text-muted")
            title_label = ui.label(
                f"Edit Schema: {circuit_record.name}" if circuit_record else "New Circuit Schema"
            ).classes("text-2xl font-bold text-fg")

        with ui.card().classes("w-full bg-surface rounded-xl p-6 min-h-[400px]"):
            with ui.row().classes("items-center w-full justify-between mb-4"):
                with ui.row().classes("gap-2 items-center"):
                    ui.icon("science", size="sm").classes("text-primary")
                    ui.label("Circuit Definition").classes("text-lg font-bold text-fg")

                def save_schema() -> None:
                    try:
                        circuit_def = parse_circuit_definition_source(json_input.value)
                        name = circuit_def.name
                    except Exception as exc:
                        ui.notify(
                            "Invalid Circuit Definition. Required fields: "
                            f"name, components, topology. Details: {exc}",
                            type="negative",
                        )
                        return

                    if not name:
                        ui.notify("Name cannot be empty in the dictionary.", type="negative")
                        return

                    stored_definition = _stored_schema_text_from_editor(json_input.value)
                    try:
                        with get_unit_of_work() as uow:
                            if circuit_record and circuit_record.id is not None:
                                db_circuit = uow.circuits.get(circuit_record.id)
                                if db_circuit is None:
                                    raise ValueError("Circuit record no longer exists.")
                                db_circuit.name = name
                                db_circuit.definition_json = stored_definition
                                uow.commit()
                                json_input.value = stored_definition
                                ui.notify("Schema updated.", type="positive")
                            else:
                                new_circuit = CircuitRecord(
                                    name=name,
                                    definition_json=stored_definition,
                                )
                                uow.circuits.add(new_circuit)
                                uow.commit()
                                json_input.value = stored_definition
                                ui.notify("New schema created.", type="positive")
                                ui.navigate.to(f"/schemas/{new_circuit.id}")
                    except Exception as exc:
                        ui.notify(f"Database Error: {exc}", type="negative")

                async def format_schema() -> None:
                    format_status.classes(add="hidden", remove="block")
                    format_status.text = "Formatting..."

                    try:
                        format_result = await ui.run_javascript(
                            build_schema_formatter_js(json_input.value),
                        )
                    except Exception as exc:
                        message = str(exc)
                        format_status.text = f"Format failed: {message}"
                        format_status.classes(add="block", remove="hidden")
                        ui.notify(f"Format failed: {message}", type="negative")
                        return

                    if not isinstance(format_result, dict):
                        message = "Ruff WebAssembly formatter is unavailable."
                        format_status.text = message
                        format_status.classes(add="block", remove="hidden")
                        ui.notify(message, type="negative")
                        return

                    if not bool(format_result.get("ok")):
                        message = str(format_result.get("error", "Unknown formatter error."))
                        format_status.text = f"Format failed: {message}"
                        format_status.classes(add="block", remove="hidden")
                        ui.notify(f"Format failed: {message}", type="negative")
                        return

                    formatted_text = str(format_result.get("text", ""))
                    if formatted_text != json_input.value:
                        json_input.set_value(formatted_text)
                    format_status.text = "Formatted with Ruff WebAssembly."
                    format_status.classes(add="block", remove="hidden")
                    ui.notify("Schema formatted.", type="positive")

                format_button = ui.button(
                    "Format",
                    icon="auto_fix_high",
                    on_click=format_schema,
                ).props("outline size=sm")
                ui.button("Save Schema", icon="save", on_click=save_schema).props(
                    "color=primary size=sm"
                )

            error_label = ui.label("").classes("text-danger text-sm hidden mb-2")
            format_status = ui.label("").classes("text-xs text-muted hidden mb-2")

            if circuit_record:
                try:
                    def_val = _editor_text_from_record(circuit_record.definition_json)
                except Exception:
                    def_val = circuit_record.definition_json
            else:
                def_val = _DEFAULT_CIRCUIT_STR

            ui.label("Circuit Netlist").classes("text-sm text-muted mb-2")
            editor_theme = (
                "vscodeDark" if app.storage.user.get("dark_mode", True) else "vscodeLight"
            )
            json_input = ui.codemirror(
                value=def_val,
                language="Python",
                theme=editor_theme,
                indent=" " * 4,
            ).classes("w-full app-netlist-editor")
            ui.label("Tip: Use Tab / Shift+Tab for indentation.").classes("text-xs text-muted mt-2")
            ui.label("Shortcut: Ctrl/Cmd + Shift + F").classes("text-xs text-muted mt-1")
            ui.label(
                "Live Preview is currently disabled. "
                "Focus on stable netlist editing and simulation."
            ).classes("text-xs text-muted mt-4")

        with ui.card().classes("w-full bg-surface rounded-xl p-6 mt-2"):
            with ui.row().classes("items-center gap-2 mb-3"):
                ui.icon("rule", size="sm").classes("text-primary")
                ui.label("Expanded Netlist Preview").classes("text-lg font-bold text-fg")
            ui.label(
                "Read-only compiled view. This uses the same repeat-expansion pipeline as "
                "Simulation and is never written back to the database."
            ).classes("text-sm text-muted mb-3")
            preview_container = ui.column().classes("w-full")

        with ui.card().classes("w-full bg-surface rounded-xl p-6 mt-2"):
            with ui.row().classes("items-center gap-2 mb-3"):
                ui.icon("table_chart", size="sm").classes("text-primary")
                ui.label("Component & Unit Reference").classes("text-lg font-bold text-fg")
            ui.table(
                columns=_COMPONENT_REF_COLUMNS,
                rows=_COMPONENT_REF_ROWS,
                row_key="kind",
            ).props("dense wrap-cells").classes("w-full")
            ui.label(
                "Declare parts in components, then reference those names from topology tuples. "
                "Ground token: 0 (required)."
            ).classes("text-xs text-muted mt-3")

        def render_expanded_preview(
            *, preview_text: str | None = None, error_text: str | None = None
        ) -> None:
            preview_container.clear()
            with preview_container:
                if error_text is not None:
                    ui.label(error_text).classes("text-sm text-danger")
                    return
                ui.markdown(f"```python\n{preview_text or ''}\n```").classes("w-full")

        def on_editor_change(_event: Any = None) -> None:
            try:
                circuit = parse_circuit_definition_source(json_input.value)
                error_label.classes(add="hidden", remove="block")
                render_expanded_preview(
                    preview_text=format_expanded_circuit_definition(circuit),
                )
                if circuit.name:
                    title_label.text = (
                        f"Edit Schema: {circuit.name}"
                        if circuit_record
                        else f"New Schema: {circuit.name}"
                    )
            except Exception as exc:
                error_label.text = (
                    f"Error Parsing Definition (required: name + components + topology): {exc!s}"
                )
                error_label.classes(add="block", remove="hidden")
                render_expanded_preview(
                    error_text=(
                        "Expanded preview is unavailable until the Circuit Definition validates."
                    ),
                )

        on_editor_change()
        ui.run_javascript(
            build_schema_formatter_hotkey_js(
                button_id=format_button.html_id,
                scope_id=json_input.html_id,
            )
        )
        json_input.on_value_change(on_editor_change)

    content()
