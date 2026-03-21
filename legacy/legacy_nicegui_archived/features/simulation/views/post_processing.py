"""Post-processing panel and setup storage helpers."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Mapping
from datetime import datetime
from typing import Any

from nicegui import ui

from legacy.legacy_nicegui_archived.features.simulation.views.common import (
    _Z0_CONTROL_CLASSES,
    _Z0_CONTROL_PROPS,
    _with_test_id,
)
from legacy.legacy_nicegui_archived.features.simulation.views.plots import (
    _coerce_int_value,
    _format_mode_label,
    _resolve_option_key,
    _result_port_options,
)
from legacy.legacy_nicegui_archived.services.post_processing_step_registry import (
    POST_PROCESS_STEP_OPTIONS,
    build_default_step_config,
    normalize_saved_step_config,
    preview_pipeline_labels,
    serialize_post_processing_step,
)
from core.simulation.application.post_processing import filtered_modes
from core.simulation.domain.circuit import CircuitDefinition, SimulationResult
_POST_PROCESS_MODE_FILTER_OPTIONS = {
    "base": "Base",
    "sideband": "Sideband",
    "all": "All Modes",
}
_POST_PROCESS_INPUT_Y_SOURCE_OPTIONS = {
    "raw_y": "Raw Y",
    "ptc_y": "PTC Y",
}


def _post_process_mode_options(
    result: SimulationResult,
    mode_filter: str,
) -> dict[str, str]:
    """Return mode options constrained by one post-processing mode filter."""
    filter_key = str(mode_filter).strip().lower()
    if filter_key == "sideband":
        options = filtered_modes(result, "sideband")
    elif filter_key == "all":
        options = filtered_modes(result, "all")
    else:
        options = filtered_modes(result, "base")
    return {SimulationResult.mode_token(mode): _format_mode_label(mode) for mode in options}


def _coordinate_weight_fields_editable(weight_mode: str) -> bool:
    """Return whether coordinate-transform alpha/beta fields are editable."""
    return str(weight_mode).strip().lower() == "manual"


def _render_post_processing_panel(
    *,
    raw_result: SimulationResult,
    ptc_result: SimulationResult | None = None,
    design_id: int | None = None,
    initial_input_y_source: str = "raw_y",
    on_input_y_source_change: Callable[[str], None] | None = None,
    resolve_input_bundle: Callable[
        [str, float], tuple[SimulationResult, dict[str, Any] | None, int | None]
    ]
    | None = None,
    circuit_definition: CircuitDefinition | None = None,
    schema_id: int | None = None,
    schema_name: str | None = None,
    append_status: Callable[[str, str], None] | None = None,
    on_processing_start: Callable[[], None] | None = None,
    on_result: Callable[[Any | None], None] | None = None,
    on_source_bundle_resolved: Callable[[int | None], None] | None = None,
    resolve_termination_plan: Callable[[], dict[str, Any]] | None = None,
    on_task_submitted: Callable[[Any], None] | None = None,
    load_saved_setups_for_schema: Callable[[int], list[dict[str, Any]]] | None = None,
    save_saved_setups_for_schema: Callable[[int, list[dict[str, Any]]], None] | None = None,
    load_selected_setup_id: Callable[[int], str] | None = None,
    save_selected_setup_id: Callable[[int, str], None] | None = None,
    on_submit: Callable[[dict[str, Any]], Awaitable[Any]] | None = None,
) -> None:
    """Render one dynamic card-list style Port-Level post-processing pipeline."""

    def log_info(message: str) -> None:
        if append_status is not None:
            append_status("info", message)

    def emit_result(run_result: Any | None) -> None:
        if on_result is not None:
            on_result(run_result)

    def _active_input_result(source: str) -> SimulationResult:
        if source == "ptc_y" and isinstance(ptc_result, SimulationResult):
            return ptc_result
        return raw_result

    def _preview_input_result(source: str, reference_impedance_ohm: float) -> SimulationResult | None:
        if resolve_input_bundle is not None:
            try:
                preview_result, _preview_sweep_payload, _preview_bundle_id = resolve_input_bundle(
                    source,
                    reference_impedance_ohm,
                )
            except ValueError:
                preview_result = None
            if isinstance(preview_result, SimulationResult):
                return preview_result
        fallback = _active_input_result(source)
        return fallback if isinstance(fallback, SimulationResult) else None

    input_y_source_options = {"raw_y": _POST_PROCESS_INPUT_Y_SOURCE_OPTIONS["raw_y"]}
    if isinstance(_preview_input_result("ptc_y", 50.0), SimulationResult):
        input_y_source_options["ptc_y"] = _POST_PROCESS_INPUT_Y_SOURCE_OPTIONS["ptc_y"]
    resolved_input_y_source = _resolve_option_key(input_y_source_options, initial_input_y_source)

    def _active_input_bundle(
        source: str, reference_impedance_ohm: float
    ) -> tuple[SimulationResult, dict[str, Any] | None, int | None]:
        if resolve_input_bundle is not None:
            return resolve_input_bundle(source, reference_impedance_ohm)
        return (_active_input_result(source), None, None)

    preview_raw_result = _preview_input_result("raw_y", 50.0) or raw_result
    port_options = _result_port_options(preview_raw_result)
    default_ports = list(port_options)
    default_port_a = default_ports[0] if default_ports else None
    default_port_b = default_ports[1] if len(default_ports) > 1 else default_port_a
    saved_post_setups = (
        load_saved_setups_for_schema(schema_id)
        if callable(load_saved_setups_for_schema) and isinstance(schema_id, int) and schema_id > 0
        else []
    )
    saved_post_setup_by_id: dict[str, dict[str, Any]] = {
        str(setup.get("id")): setup
        for setup in saved_post_setups
        if setup.get("id") and setup.get("name")
    }
    selected_post_setup_id = (
        load_selected_setup_id(schema_id)
        if callable(load_selected_setup_id) and isinstance(schema_id, int) and schema_id > 0
        else ""
    )
    if selected_post_setup_id not in saved_post_setup_by_id:
        selected_post_setup_id = ""

    ui.label(
        "Port-Level only: Post Processing consumes simulated port-space Y(ω). "
        "Nodal/internal-node elimination is intentionally out of scope in M1. "
        "Auto alpha/beta currently uses schema capacitor-to-ground weights."
    ).classes("text-xs text-muted mb-3")

    with ui.column().classes("w-full gap-3"):
        with _with_test_id(
            ui.card().classes("w-full bg-elevated border border-border rounded-lg p-4"),
            "post-processing-input-card",
        ):
            ui.label("Input Node").classes("text-sm font-bold text-fg mb-2")
            with ui.row().classes("w-full items-end gap-3 mb-3 flex-wrap"):
                post_setup_options = {"": "Current (Unsaved)"}
                post_setup_options.update(
                    {
                        setup_id: str(setup.get("name"))
                        for setup_id, setup in saved_post_setup_by_id.items()
                    }
                )
                post_setup_select = (
                    ui.select(
                        label="Post-Processing Setup",
                        options=post_setup_options,
                        value=selected_post_setup_id,
                    )
                    .props("dense outlined options-dense")
                    .classes("w-80")
                )
                _with_test_id(post_setup_select, "post-processing-setup-select")
                save_post_setup_button = (
                    ui.button("Save Setup", icon="bookmark_add")
                    .props("outline color=primary")
                    .classes("shrink-0")
                )
                _with_test_id(save_post_setup_button, "post-processing-save-setup-button")
                delete_post_setup_button = (
                    ui.button("", icon="delete").props("outline color=negative round").classes("shrink-0")
                )
                _with_test_id(delete_post_setup_button, "post-processing-delete-setup-button")
                if not selected_post_setup_id:
                    delete_post_setup_button.disable()
            with ui.row().classes("w-full items-end gap-3 flex-wrap"):
                input_y_source_select = (
                    ui.select(
                        label="Input Y Source",
                        options=input_y_source_options,
                        value=resolved_input_y_source,
                    )
                    .props("dense outlined options-dense")
                    .classes("w-44")
                )
                _with_test_id(input_y_source_select, "post-processing-input-y-source-select")
                mode_filter_select = (
                    ui.select(label="Mode Filter", options=_POST_PROCESS_MODE_FILTER_OPTIONS, value="base")
                    .props("dense outlined options-dense")
                    .classes("w-40")
                )
                _with_test_id(mode_filter_select, "post-processing-mode-filter-select")
                mode_select = (
                    ui.select(
                        label="Mode",
                        options=_post_process_mode_options(
                            _preview_input_result(
                                _resolve_option_key(input_y_source_options, input_y_source_select.value),
                                50.0,
                            )
                            or preview_raw_result,
                            "base",
                        ),
                    )
                    .props("dense outlined options-dense")
                    .classes("w-52")
                )
                _with_test_id(mode_select, "post-processing-mode-select")
                z0_input = (
                    ui.number("Z0 (Ohm)", value=50.0, format="%.6g")
                    .props(_Z0_CONTROL_PROPS)
                    .classes(_Z0_CONTROL_CLASSES)
                )
                _with_test_id(z0_input, "post-processing-z0-input")
                step_type_select = (
                    ui.select(label="Step Type", options=POST_PROCESS_STEP_OPTIONS, value="coordinate_transform")
                    .props("dense outlined options-dense")
                    .classes("w-64")
                )
                _with_test_id(step_type_select, "post-processing-step-type-select")
                add_step_button = ui.button("Add Step", icon="add").props("outline color=primary").classes("shrink-0")
                _with_test_id(add_step_button, "post-processing-add-step-button")
                run_button = ui.button("Run Post Processing", icon="tune").props("color=primary").classes("ml-auto")
                _with_test_id(run_button, "post-processing-run-button")
            mode_hint = ui.label("").classes("text-xs text-muted mt-2")

        with ui.card().classes("w-full bg-elevated border border-border rounded-lg p-4"):
            ui.label("Output Node").classes("text-sm font-bold text-fg mb-2")
            output_container = ui.column().classes("w-full gap-2")

    step_sequence: list[dict[str, Any]] = []
    step_id_seed: dict[str, int] = {"value": 1}
    applying_saved_post_setup = False

    def _make_step_config(step_type: str) -> dict[str, Any]:
        return build_default_step_config(
            step_type,
            default_port_a=default_port_a or 1,
            default_port_b=default_port_b or default_port_a or 1,
        )

    def invalidate_processed_state() -> None:
        emit_result(None)

    def _serialized_post_step(step: dict[str, Any]) -> dict[str, Any]:
        return serialize_post_processing_step(step)

    def collect_current_post_setup_payload() -> dict[str, Any]:
        return {
            "input_y_source": _resolve_option_key(input_y_source_options, input_y_source_select.value),
            "mode_filter": str(mode_filter_select.value or "base"),
            "mode_token": str(mode_select.value or ""),
            "reference_impedance_ohm": float(z0_input.value or 50.0),
            "steps": [_serialized_post_step(step) for step in step_sequence],
        }

    def apply_saved_post_setup(setup_record: dict[str, Any]) -> None:
        nonlocal applying_saved_post_setup
        payload = setup_record.get("payload")
        if not isinstance(payload, dict):
            ui.notify("Selected post-processing setup payload is invalid.", type="warning")
            return
        applying_saved_post_setup = True
        try:
            desired_input_source = _resolve_option_key(
                input_y_source_options,
                payload.get("input_y_source", "raw_y"),
            )
            input_y_source_select.value = desired_input_source
            if on_input_y_source_change is not None:
                on_input_y_source_change(desired_input_source)
            mode_filter_select.value = str(payload.get("mode_filter", "base"))
            refresh_mode_selector()
            desired_mode_token = str(payload.get("mode_token", mode_select.value or ""))
            if desired_mode_token and isinstance(mode_select.options, dict) and desired_mode_token in mode_select.options:
                mode_select.value = desired_mode_token
            z0_input.value = float(payload.get("reference_impedance_ohm", 50.0))
            step_sequence.clear()
            step_id_seed["value"] = 1
            for raw_step in payload.get("steps", []):
                if not isinstance(raw_step, dict):
                    continue
                normalized = normalize_saved_step_config(
                    raw_step=raw_step,
                    step_id=step_id_seed["value"],
                    default_port_a=default_port_a or 1,
                    default_port_b=default_port_b or default_port_a or 1,
                )
                step_id_seed["value"] += 1
                step_sequence.append(normalized)
            invalidate_processed_state()
            render_step_cards.refresh()
        finally:
            applying_saved_post_setup = False

    def refresh_saved_post_setup_select(preferred_id: str | None = None) -> None:
        nonlocal saved_post_setups, saved_post_setup_by_id, selected_post_setup_id
        if (
            not callable(load_saved_setups_for_schema)
            or not callable(save_selected_setup_id)
            or not isinstance(schema_id, int)
            or schema_id <= 0
        ):
            return
        saved_post_setups = load_saved_setups_for_schema(schema_id)
        saved_post_setup_by_id = {
            str(setup.get("id")): setup for setup in saved_post_setups if setup.get("id") and setup.get("name")
        }
        options = {"": "Current (Unsaved)"}
        options.update({setup_id: str(setup.get("name")) for setup_id, setup in saved_post_setup_by_id.items()})
        post_setup_select.options = options
        selected_value = preferred_id if preferred_id in options else str(post_setup_select.value or "")
        if selected_value not in options:
            selected_value = ""
        selected_post_setup_id = selected_value
        post_setup_select.value = selected_value
        save_selected_setup_id(schema_id, selected_value)
        if selected_value:
            delete_post_setup_button.enable()
        else:
            delete_post_setup_button.disable()

    def on_post_setup_change(e: Any) -> None:
        nonlocal selected_post_setup_id
        if applying_saved_post_setup:
            return
        selected_value = str(e.value or "")
        selected_post_setup_id = selected_value
        if callable(save_selected_setup_id) and isinstance(schema_id, int) and schema_id > 0:
            save_selected_setup_id(schema_id, selected_value)
        if selected_value:
            delete_post_setup_button.enable()
        else:
            delete_post_setup_button.disable()
        setup_record = saved_post_setup_by_id.get(selected_value)
        if setup_record is None:
            return
        apply_saved_post_setup(setup_record)
        ui.notify(f"Loaded post-processing setup: {setup_record.get('name')}", type="positive")

    def on_save_post_setup_click() -> None:
        if (
            not callable(save_saved_setups_for_schema)
            or not isinstance(schema_id, int)
            or schema_id <= 0
        ):
            ui.notify("Save setup requires a selected schema.", type="warning")
            return
        with ui.dialog() as dialog, ui.card().classes("w-full max-w-md bg-surface p-4"):
            ui.label("Save Post-Processing Setup").classes("text-lg font-bold text-fg mb-3")
            default_name = f"{schema_name or 'Schema'} Post-Processing Setup {len(saved_post_setups) + 1}"
            name_input = ui.input("Setup Name", value=default_name).classes("w-full")

            def do_save() -> None:
                setup_name = str(name_input.value or "").strip()
                if not setup_name:
                    ui.notify("Setup name is required.", type="warning")
                    return
                payload = collect_current_post_setup_payload()
                existing = next((s for s in saved_post_setups if str(s.get("name")) == setup_name), None)
                setup_id = (
                    str(existing.get("id"))
                    if existing is not None and existing.get("id")
                    else datetime.now().strftime("%Y%m%d%H%M%S%f")
                )
                record = {
                    "id": setup_id,
                    "name": setup_name,
                    "saved_at": datetime.now().isoformat(),
                    "payload": payload,
                }
                updated = [s for s in saved_post_setups if str(s.get("id")) != setup_id]
                updated.append(record)
                if schema_id is None:
                    raise ValueError("Schema id is unavailable for post-processing setup save.")
                save_saved_setups_for_schema(int(schema_id), updated)
                refresh_saved_post_setup_select(preferred_id=setup_id)
                ui.notify(f"Saved post-processing setup: {setup_name}", type="positive")
                dialog.close()

            with ui.row().classes("w-full justify-end gap-2 mt-4"):
                ui.button("Cancel", on_click=dialog.close).props("flat")
                ui.button("Save", on_click=do_save).props("color=primary")

        dialog.open()

    def on_delete_post_setup_click() -> None:
        if (
            not callable(save_saved_setups_for_schema)
            or not isinstance(schema_id, int)
            or schema_id <= 0
        ):
            return
        setup_id = str(post_setup_select.value or "")
        if not setup_id:
            return
        updated = [s for s in saved_post_setups if str(s.get("id")) != setup_id]
        save_saved_setups_for_schema(schema_id, updated)
        refresh_saved_post_setup_select(preferred_id="")
        ui.notify("Deleted post-processing setup.", type="positive")

    def _pipeline_labels_before_step(step_id: int | None = None) -> tuple[str, ...]:
        initial_labels = tuple(str(port) for port in sorted(raw_result.available_port_indices))
        return preview_pipeline_labels(
            initial_labels=initial_labels,
            step_sequence=step_sequence,
            stop_before_step_id=step_id,
        )

    @ui.refreshable
    def render_step_cards() -> None:
        if not step_sequence:
            with ui.card().classes("w-full bg-elevated border border-dashed border-border rounded-lg p-4"):
                ui.label("No steps yet. Use Add Step to build a post-processing pipeline.").classes("text-sm text-muted")
            return

        for index, step in enumerate(list(step_sequence), start=1):
            step_id = int(step.get("id", -1))
            step_type = str(step.get("type", "coordinate_transform"))
            step_label = "Coordinate Transformation" if step_type == "coordinate_transform" else "Kron Reduction"
            with _with_test_id(
                ui.card().classes("w-full bg-elevated border border-border rounded-lg p-4"),
                f"post-processing-step-card-{index}",
            ):
                with ui.row().classes("w-full items-center gap-3 mb-2"):
                    ui.label(f"Step {index} · {step_label}").classes("text-sm font-bold text-fg")
                    step_type_select_local = (
                        ui.select(label="Type", options=POST_PROCESS_STEP_OPTIONS, value=step_type)
                        .props("dense outlined options-dense")
                        .classes("w-64")
                    )
                    enabled_switch_local = ui.switch("Enable", value=bool(step.get("enabled", True)))
                    delete_button = ui.button("", icon="delete").props("flat color=negative round").classes("ml-auto")

                def _on_step_type_change(e: Any, target_step: dict[str, Any], target_step_id: int) -> None:
                    replacement = _make_step_config(str(e.value or "coordinate_transform"))
                    replacement["id"] = target_step_id
                    target_step.clear()
                    target_step.update(replacement)
                    invalidate_processed_state()
                    render_step_cards.refresh()

                def _on_step_enable_change(e: Any, target_step: dict[str, Any]) -> None:
                    target_step["enabled"] = bool(e.value)
                    invalidate_processed_state()
                    render_step_cards.refresh()

                def _on_delete_step(target_step_id: int) -> None:
                    step_sequence[:] = [existing for existing in step_sequence if int(existing.get("id", -1)) != target_step_id]
                    invalidate_processed_state()
                    render_step_cards.refresh()

                step_type_select_local.on_value_change(
                    lambda e, target_step=step, target_step_id=step_id: _on_step_type_change(e, target_step, target_step_id)
                )
                enabled_switch_local.on_value_change(lambda e, target_step=step: _on_step_enable_change(e, target_step))
                delete_button.on_click(lambda _e, target_step_id=step_id: _on_delete_step(target_step_id))

                if step_type == "coordinate_transform":
                    is_weight_editable = _coordinate_weight_fields_editable(str(step.get("weight_mode", "auto")))
                    with ui.row().classes("w-full gap-3 items-end flex-wrap"):
                        template_select_local = (
                            ui.select(
                                label="Template",
                                options={"identity": "Identity", "cm_dm": "Common/Differential (2 ports)"},
                                value=str(step.get("template", "cm_dm")),
                            )
                            .props("dense outlined options-dense")
                            .classes("w-56")
                        )
                        weight_mode_local = (
                            ui.select(
                                label="Weight Mode",
                                options={"auto": "Auto (from schema C-to-ground)", "manual": "Manual"},
                                value=str(step.get("weight_mode", "auto")),
                            )
                            .props("dense outlined options-dense")
                            .classes("w-64")
                        )
                        alpha_local = ui.number("alpha", value=float(step.get("alpha", 0.5)), format="%.6g").classes("w-24")
                        beta_local = ui.number("beta", value=float(step.get("beta", 0.5)), format="%.6g").classes("w-24")
                        if not is_weight_editable:
                            alpha_local.disable()
                            beta_local.disable()
                    with ui.row().classes("w-full gap-3 items-end flex-wrap mt-2"):
                        port_a_local = ui.select(label="Port A", options=port_options, value=step.get("port_a")).props("dense outlined").classes("w-28")
                        port_b_local = ui.select(label="Port B", options=port_options, value=step.get("port_b")).props("dense outlined").classes("w-28")

                    def _on_coord_change(*, target_step: dict[str, Any], field: str, value: Any, refresh: bool) -> None:
                        target_step[field] = value
                        invalidate_processed_state()
                        if refresh:
                            render_step_cards.refresh()

                    template_select_local.on_value_change(lambda e, target_step=step: _on_coord_change(target_step=target_step, field="template", value=str(e.value or "identity"), refresh=True))
                    weight_mode_local.on_value_change(lambda e, target_step=step: _on_coord_change(target_step=target_step, field="weight_mode", value=str(e.value or "auto"), refresh=True))
                    alpha_local.on_value_change(lambda e, target_step=step: _on_coord_change(target_step=target_step, field="alpha", value=float(e.value or 0.0), refresh=False))
                    beta_local.on_value_change(lambda e, target_step=step: _on_coord_change(target_step=target_step, field="beta", value=float(e.value or 0.0), refresh=False))
                    port_a_local.on_value_change(lambda e, target_step=step: _on_coord_change(target_step=target_step, field="port_a", value=e.value, refresh=True))
                    port_b_local.on_value_change(lambda e, target_step=step: _on_coord_change(target_step=target_step, field="port_b", value=e.value, refresh=True))
                else:
                    current_labels = _pipeline_labels_before_step(step_id)
                    selected_keep = {str(label) for label in (step.get("keep_labels") or [])}
                    normalized_keep = [label for label in current_labels if label in selected_keep]
                    if not normalized_keep and current_labels:
                        normalized_keep = list(current_labels)
                    step["keep_labels"] = normalized_keep

                    def _toggle_kron_keep(target_step: dict[str, Any], keep_label: str, available_labels: tuple[str, ...]) -> None:
                        selected = {str(value) for value in (target_step.get("keep_labels") or [])}
                        if keep_label in selected:
                            selected.remove(keep_label)
                        else:
                            selected.add(keep_label)
                        target_step["keep_labels"] = [label for label in available_labels if label in selected]
                        invalidate_processed_state()
                        render_step_cards.refresh()

                    def _select_all_kron_keep(target_step: dict[str, Any], available_labels: tuple[str, ...]) -> None:
                        target_step["keep_labels"] = list(available_labels)
                        invalidate_processed_state()
                        render_step_cards.refresh()

                    def _clear_kron_keep(target_step: dict[str, Any]) -> None:
                        target_step["keep_labels"] = []
                        invalidate_processed_state()
                        render_step_cards.refresh()

                    with ui.column().classes("w-full gap-2"):
                        ui.label("Keep Basis Labels").classes("text-xs text-muted")
                        available_labels_snapshot = current_labels

                        def _on_select_all(_e: Any, target_step: dict[str, Any] = step, labels: tuple[str, ...] = available_labels_snapshot) -> None:
                            _select_all_kron_keep(target_step, labels)

                        with ui.row().classes("w-full gap-2 flex-wrap"):
                            for label in available_labels_snapshot:
                                selected = label in set(normalized_keep)
                                button_classes = (
                                    "px-3 py-1 rounded-md text-xs border border-primary bg-primary/10 text-primary"
                                    if selected
                                    else "px-3 py-1 rounded-md text-xs border border-border text-fg"
                                )
                                ui.button(
                                    label,
                                    on_click=lambda _e, keep_label=label, target_step=step, labels=available_labels_snapshot: _toggle_kron_keep(target_step, keep_label, labels),
                                ).props("no-caps dense flat").classes(button_classes)
                        with ui.row().classes("w-full gap-2 items-center flex-wrap"):
                            ui.button("Select All", on_click=_on_select_all).props("dense flat no-caps")
                            ui.button("Clear", on_click=lambda _e, target_step=step: _clear_kron_keep(target_step)).props("dense flat no-caps")
                            ui.label("Current basis: " + (", ".join(current_labels) if current_labels else "(empty)")).classes("text-xs text-muted")

    def refresh_mode_selector() -> None:
        preview_result = _preview_input_result(
            _resolve_option_key(input_y_source_options, input_y_source_select.value),
            float(z0_input.value or 50.0),
        )
        options = _post_process_mode_options(preview_result, str(mode_filter_select.value or "base")) if isinstance(preview_result, SimulationResult) else {}
        mode_select.options = options
        if not options:
            mode_select.value = None
            mode_select.disable()
            run_button.disable()
            mode_hint.text = "No compatible modes for this filter."
            invalidate_processed_state()
            return
        if mode_select.value not in options:
            mode_select.value = next(iter(options))
        mode_select.enable()
        run_button.enable()
        mode_hint.text = f"{len(options)} mode(s) available."

    def add_step() -> None:
        step_type = str(step_type_select.value or "coordinate_transform")
        step_config = _make_step_config(step_type)
        step_config["id"] = step_id_seed["value"]
        step_id_seed["value"] += 1
        if step_type == "kron_reduction":
            step_config["keep_labels"] = list(_pipeline_labels_before_step())
        step_sequence.append(step_config)
        invalidate_processed_state()
        render_step_cards.refresh()

    async def run_post_processing() -> None:
        output_container.clear()
        run_button.disable()
        run_button.props("loading")
        if on_processing_start is not None:
            on_processing_start()
        with output_container:
            ui.spinner(size="2em").classes("text-primary")
            ui.label("Running post-processing pipeline...").classes("text-sm text-muted mt-2")
        await asyncio.sleep(0)
        try:
            input_source = _resolve_option_key(input_y_source_options, input_y_source_select.value)
            input_y_source_select.value = input_source
            _active_result, active_sweep_payload, source_simulation_bundle_id = _active_input_bundle(input_source, float(z0_input.value or 50.0))
            reference_impedance_ohm = float(z0_input.value or 50.0)
            resolved_source_bundle_id = source_simulation_bundle_id
            if on_source_bundle_resolved is not None:
                on_source_bundle_resolved(resolved_source_bundle_id)
            if resolved_source_bundle_id is None:
                raise ValueError("Post-processing requires one persisted raw simulation batch.")
            if design_id is None:
                raise ValueError("Select at least one active dataset before running post-processing.")
            if on_submit is None:
                raise ValueError("Post-processing submit action is unavailable.")
            resolved_run_kind = "single_result"
            if isinstance(active_sweep_payload, Mapping):
                resolved_run_kind = "parameter_sweep"
            resolved_mode = str(mode_select.value or "") or "auto"
            log_info(
                "Starting Post Processing: "
                f"input={input_source}, run_kind={resolved_run_kind}, "
                f"mode_filter={mode_filter_select.value or 'base'!s}, "
                f"mode={resolved_mode}."
            )
            dispatch = await on_submit(
                {
                    "design_id": int(design_id or 0),
                    "source_batch_id": int(resolved_source_bundle_id),
                    "input_source": input_source,
                    "mode_filter": str(mode_filter_select.value or "base"),
                    "mode_token": str(mode_select.value or ""),
                    "reference_impedance_ohm": reference_impedance_ohm,
                    "step_sequence": [dict(step) for step in step_sequence],
                    "termination_plan_payload": (
                        dict(resolve_termination_plan())
                        if resolve_termination_plan is not None
                        else None
                    ),
                    "circuit_definition": circuit_definition,
                    "schema_id": (
                        int(schema_id) if isinstance(schema_id, int) and schema_id > 0 else None
                    ),
                    "run_kind": resolved_run_kind,
                }
            )
            if on_task_submitted is not None:
                on_task_submitted(dispatch)
            emit_result(None)
            render_step_cards.refresh()
            log_info(
                "Post Processing queued: "
                f"task=#{dispatch.task.id}, batch=#{dispatch.task.trace_batch_id}, "
                f"input={input_source}, run_kind={resolved_run_kind}, "
                f"worker={dispatch.worker_task_name}."
            )
            output_container.clear()
            with output_container:
                ui.label("Post-processing task submitted. Result view will refresh from persisted data.").classes("text-sm text-positive")
                ui.label(f"task=#{dispatch.task.id} | batch={dispatch.task.trace_batch_id}").classes("text-xs text-muted")
                ui.label(f"worker={dispatch.worker_task_name} | lane={dispatch.dispatched_lane}").classes("text-xs text-muted")
                ui.label("Long-running tasks remain visible through persisted heartbeat polling.").classes("text-xs text-muted")
        except Exception as exc:
            invalidate_processed_state()
            log_info(f"Post Processing failed: {exc}")
            output_container.clear()
            with output_container:
                ui.label(f"Post Processing failed: {exc}").classes("text-sm text-danger")
        finally:
            run_button.props(remove="loading")
            refresh_mode_selector()

    post_setup_select.on_value_change(on_post_setup_change)
    save_post_setup_button.on_click(lambda _e: on_save_post_setup_click())
    delete_post_setup_button.on_click(lambda _e: on_delete_post_setup_click())
    if isinstance(schema_id, int) and schema_id > 0:
        refresh_saved_post_setup_select(preferred_id=selected_post_setup_id)
        selected_setup_record = saved_post_setup_by_id.get(str(post_setup_select.value or ""))
        if isinstance(selected_setup_record, dict):
            apply_saved_post_setup(selected_setup_record)

    def _on_input_y_source_change() -> None:
        resolved_source = _resolve_option_key(input_y_source_options, input_y_source_select.value)
        input_y_source_select.value = resolved_source
        if on_input_y_source_change is not None:
            on_input_y_source_change(resolved_source)
        invalidate_processed_state()
        refresh_mode_selector()

    input_y_source_select.on_value_change(lambda _e: _on_input_y_source_change())
    mode_filter_select.on_value_change(lambda _e: (invalidate_processed_state(), refresh_mode_selector()))
    mode_select.on_value_change(lambda _e: invalidate_processed_state())
    z0_input.on("keydown.enter", lambda _e: invalidate_processed_state())
    z0_input.on("blur", lambda _e: invalidate_processed_state())
    add_step_button.on_click(lambda _e: add_step())
    run_button.on("click", lambda _e: asyncio.create_task(run_post_processing()))

    render_step_cards()
    refresh_mode_selector()
