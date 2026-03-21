"""Dashboard page to view vital tagged metrics across datasets."""

import asyncio
from collections.abc import Mapping
from typing import Any

from nicegui import app, run, ui

from legacy.legacy_nicegui_archived.services.dataset_profile import (
    build_dataset_profile_payload,
    capability_option_labels,
    device_type_option_labels,
    merge_dataset_profile_into_source_meta,
    normalize_capabilities,
    normalize_dataset_profile,
    normalize_device_type,
    profile_summary_text,
    suggested_capabilities_for_device_type,
)
from legacy.legacy_nicegui_archived.ui.states import render_empty_state
from core.shared.persistence import get_unit_of_work

_DASHBOARD_DEVICE_TYPE_OPTIONS = device_type_option_labels()
_DASHBOARD_CAPABILITY_OPTIONS = capability_option_labels()


def build_page() -> None:
    def content():
        ui.label("Dashboard").classes("text-2xl font-bold text-fg mb-6")

        selected_dataset_ids = app.storage.user.get("selected_datasets", [])

        if not selected_dataset_ids:
            render_empty_state(
                icon="dashboard",
                title="No Datasets Selected",
                message="Select active datasets from the Raw Data page.",
            )
            return

        metadata_edit_state: dict[int, dict[str, Any]] = {}

        def _persist_dataset_profile(
            dataset_id: int,
            profile_payload: Mapping[str, object],
        ) -> None:
            with get_unit_of_work() as write_uow:
                dataset = write_uow.datasets.get(dataset_id)
                if dataset is None:
                    raise ValueError("Dataset not found.")
                updated_source_meta = merge_dataset_profile_into_source_meta(
                    dataset.source_meta,
                    profile_payload=profile_payload,
                )
                write_uow.datasets.update_source_meta(dataset_id, updated_source_meta)
                write_uow.commit()

        try:
            with get_unit_of_work() as uow:
                ds_options = {}
                for ds_id in selected_dataset_ids:
                    ds = uow.datasets.get(ds_id)
                    if ds:
                        ds_options[ds_id] = ds.name

                if not ds_options:
                    ui.label("Error: Active datasets not found.").classes("text-danger")
                    return

                # --- Layout: Header + Dataset Selector ---
                with ui.row().classes("w-full items-center gap-4 mb-4"):
                    ui.label("Dataset:").classes("text-sm font-bold text-fg")

                    # We can use the same state variable or a new one
                    current_ds_id = app.storage.user.get("dashboard_current_dataset")
                    if current_ds_id not in ds_options:
                        current_ds_id = next(iter(ds_options.keys()))
                        app.storage.user["dashboard_current_dataset"] = current_ds_id

                    def on_change(e):
                        app.storage.user["dashboard_current_dataset"] = e.value
                        render_dashboard.refresh()

                    ui.select(options=ds_options, value=current_ds_id, on_change=on_change).props(
                        "dense outlined options-dense"
                    ).classes("w-64")

                # --- Layout: Main Body ---
                @ui.refreshable
                def render_dashboard():
                    active_id = app.storage.user.get("dashboard_current_dataset")
                    if not active_id or active_id not in ds_options:
                        return

                    with get_unit_of_work() as render_uow:
                        dataset = render_uow.datasets.get(int(active_id))
                        if dataset is None:
                            ui.label("Dataset not found.").classes("text-danger")
                            return

                        designations = render_uow.designations.list_by_dataset(int(active_id))
                        metric_cards: list[dict[str, str | bool]] = []
                        for desig in designations:
                            resolved_param = (
                                render_uow.derived_params.get_by_dataset_method_and_name(
                                    int(active_id),
                                    str(desig.source_analysis_type),
                                    str(desig.source_parameter_name),
                                )
                            )

                            if not resolved_param:
                                resolved_param = (
                                    render_uow.derived_params.get_by_dataset_method_and_name(
                                        int(active_id),
                                        str(desig.source_analysis_type),
                                        f"{desig.source_parameter_name}_b0",
                                    )
                                )

                            if not resolved_param:
                                resolved_param = (
                                    render_uow.derived_params.get_first_by_dataset_method_name_prefix(
                                        int(active_id),
                                        str(desig.source_analysis_type),
                                        str(desig.source_parameter_name),
                                    )
                                )

                            if resolved_param:
                                value_text = (
                                    f"{resolved_param.value:.4g}"
                                    if isinstance(resolved_param.value, float)
                                    else str(resolved_param.value)
                                )
                                metric_cards.append(
                                    {
                                        "found": True,
                                        "designated_name": str(desig.designated_name),
                                        "source_analysis_type": str(desig.source_analysis_type),
                                        "value_text": value_text,
                                        "unit_text": str(resolved_param.unit or ""),
                                    }
                                )
                            else:
                                metric_cards.append(
                                    {
                                        "found": False,
                                        "designated_name": str(desig.designated_name),
                                        "source_analysis_type": str(desig.source_analysis_type),
                                        "expected_parameter_name": str(desig.source_parameter_name),
                                    }
                                )

                    persisted_profile = normalize_dataset_profile(dataset.source_meta)
                    state = metadata_edit_state.setdefault(
                        int(active_id),
                        {
                            "device_type": str(persisted_profile["device_type"]),
                            "capabilities": list(persisted_profile["capabilities"]),
                        },
                    )
                    state["device_type"] = normalize_device_type(state.get("device_type"))
                    state["capabilities"] = normalize_capabilities(state.get("capabilities", []))

                    with ui.column().classes(
                        "w-full gap-2 rounded-lg border border-border bg-bg p-4"
                    ):
                        ui.label("Dataset Metadata").classes("text-sm font-bold text-fg uppercase")
                        ui.label(
                            profile_summary_text(
                                {
                                    "device_type": persisted_profile["device_type"],
                                    "capabilities": persisted_profile["capabilities"],
                                    "source": persisted_profile["source"],
                                }
                            )
                        ).classes("text-xs text-muted")

                        capability_select: Any | None = None
                        save_metadata_button: Any | None = None
                        auto_suggest_button: Any | None = None

                        def _apply_auto_suggest() -> None:
                            suggested = suggested_capabilities_for_device_type(state["device_type"])
                            state["capabilities"] = list(suggested)
                            if capability_select is not None:
                                capability_select.value = list(suggested)
                            ui.notify(
                                "Capabilities suggested from selected device type.",
                                type="info",
                            )

                        async def _save_dataset_metadata() -> None:
                            if save_metadata_button is None or auto_suggest_button is None:
                                return
                            save_metadata_button.disable()
                            auto_suggest_button.disable()
                            save_metadata_button.props(add="loading")
                            await asyncio.sleep(0)
                            try:
                                payload = build_dataset_profile_payload(
                                    device_type=state["device_type"],
                                    capabilities=state["capabilities"],
                                    source="manual_override",
                                )
                                await run.io_bound(
                                    _persist_dataset_profile,
                                    int(active_id),
                                    payload,
                                )
                                state["device_type"] = payload["device_type"]
                                state["capabilities"] = list(payload["capabilities"])
                                ui.notify("Dataset metadata saved.", type="positive")
                                render_dashboard.refresh()
                            except Exception as exc:
                                ui.notify(f"Failed to save metadata: {exc}", type="negative")
                            finally:
                                save_metadata_button.props(remove="loading")
                                save_metadata_button.enable()
                                auto_suggest_button.enable()

                        with ui.row().classes("w-full items-end gap-3 flex-wrap"):
                            ui.select(
                                _DASHBOARD_DEVICE_TYPE_OPTIONS,
                                value=state["device_type"],
                                label="Device Type",
                                on_change=lambda e: state.__setitem__(
                                    "device_type",
                                    normalize_device_type(e.value),
                                ),
                            ).props("dense outlined options-dense").classes("w-56")
                            capability_select = (
                                ui.select(
                                    _DASHBOARD_CAPABILITY_OPTIONS,
                                    value=list(state["capabilities"]),
                                    label="Capabilities",
                                    on_change=lambda e: state.__setitem__(
                                        "capabilities",
                                        normalize_capabilities(e.value),
                                    ),
                                )
                                .props("dense outlined options-dense use-chips multiple")
                                .classes("min-w-[280px] flex-1")
                            )
                            auto_suggest_button = ui.button(
                                "Auto Suggest",
                                on_click=_apply_auto_suggest,
                            ).props("outline color=primary no-caps")
                            save_metadata_button = ui.button(
                                "Save Metadata",
                                on_click=_save_dataset_metadata,
                            ).props("unelevated color=primary no-caps")

                    ui.label("Tagged Core Metrics").classes(
                        "text-xs font-bold text-muted tracking-widest uppercase mb-4 mt-6"
                    )
                    if not metric_cards:
                        render_empty_state(
                            icon="sell",
                            title="No Metrics Tagged",
                            message=(
                                "Use the Identify Mode tool in the Characterization page "
                                "to tag key parameters."
                            ),
                            container_classes=(
                                "w-full p-8 mt-4 items-center justify-center bg-bg "
                                "rounded-xl border border-border"
                            ),
                            icon_classes="text-muted opacity-40 mb-2",
                            title_classes="text-lg font-bold text-muted",
                            message_classes="text-sm text-muted",
                        )
                        return

                    with ui.row().classes("w-full gap-4 flex-wrap"):
                        for card in metric_cards:
                            with ui.column().classes(
                                "app-card p-6 min-w-[240px] flex-grow flex-shrink bg-surface "
                                "border border-border rounded-xl hover:border-primary "
                                "transition-colors"
                            ):
                                with ui.row().classes("w-full items-center justify-between mb-2"):
                                    ui.label(str(card["designated_name"])).classes(
                                        "text-lg text-primary font-bold"
                                    )
                                    ui.icon("sell", size="sm").classes("text-primary opacity-80")

                                if bool(card["found"]):
                                    with ui.row().classes("items-baseline gap-1"):
                                        ui.label(str(card["value_text"])).classes(
                                            "text-3xl font-bold text-fg"
                                        )
                                        if str(card["unit_text"]):
                                            ui.label(str(card["unit_text"])).classes(
                                                "text-base text-muted"
                                            )
                                    ui.label(f"Source: {card['source_analysis_type']}").classes(
                                        "text-xs text-muted mt-4 uppercase tracking-wider"
                                    )
                                else:
                                    ui.label("Value not found").classes(
                                        "text-sm text-warning italic mt-1"
                                    )
                                    ui.label(
                                        f"Expected: {card['expected_parameter_name']}"
                                    ).classes("text-xs text-muted")

                render_dashboard()

        except Exception as e:
            ui.label(f"Error loading dashboard: {e}").classes("text-danger")

    content()
