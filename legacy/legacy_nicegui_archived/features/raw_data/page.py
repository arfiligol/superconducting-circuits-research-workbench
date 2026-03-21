"""Raw Data Browser with paged, filterable design and trace tables."""

from __future__ import annotations

import math
from typing import Any, cast

from nicegui import app, ui

from legacy.legacy_nicegui_archived.services.dataset_profile import (
    design_profile_summary_text,
    normalize_dataset_profile,
)
from legacy.legacy_nicegui_archived.services.design_trace_workflow import (
    DesignTraceWorkflowSummary,
    summarize_design_trace_workflow,
)
from core.analysis.application.services.trace_record_materializer import materialize_trace_record
from core.shared.persistence import get_unit_of_work
from core.shared.persistence.repositories import TraceIndexPageQuery
from core.shared.visualization.figure_builders import (
    build_heatmap,
    build_line_chart,
)

_DATA_TYPE_FILTER_OPTIONS = {
    "": "All Types",
    "s_params": "s_params",
    "y_params": "y_params",
    "z_params": "z_params",
}
_REPRESENTATION_FILTER_OPTIONS = {
    "": "All Reprs",
    "real": "real",
    "imaginary": "imaginary",
    "magnitude": "magnitude",
    "phase": "phase",
    "amplitude": "amplitude",
}
_DATASET_SORT_FIELDS = {"id", "name", "created_at"}
_RECORD_SORT_FIELDS = {"id", "data_type", "parameter", "representation"}
_HEADER_CLASSES = "text-primary text-weight-bold text-uppercase tracking-wide"


def _compare_status_badge(status: str) -> tuple[str, str]:
    normalized = str(status).strip().lower()
    if normalized == "ready":
        return ("Ready", "text-positive")
    if normalized == "inspect-only":
        return ("Inspect only", "text-warning")
    return ("Blocked", "text-danger")


def _augment_record_rows(
    rows: list[dict[str, Any]],
    workflow_summary: DesignTraceWorkflowSummary | None,
) -> list[dict[str, Any]]:
    if workflow_summary is None:
        return rows

    augmented_rows: list[dict[str, Any]] = []
    for row in rows:
        memberships = workflow_summary.trace_membership_by_id.get(int(row["id"]), ())
        augmented_rows.append(
            {
                **row,
                "source_kind": (
                    ", ".join(dict.fromkeys(item.source_kind for item in memberships))
                    or "unbatched"
                ),
                "stage_kind": (
                    ", ".join(dict.fromkeys(item.stage_kind for item in memberships)) or "-"
                ),
                "trace_batch": ", ".join(f"#{item.batch_id}" for item in memberships) or "-",
                "provenance_summary": (
                    memberships[-1].provenance_summary
                    if memberships
                    else "No TraceBatch provenance linked yet."
                ),
            }
        )
    return augmented_rows


def _total_pages(total_rows: int, page_size: int) -> int:
    return max(1, math.ceil(total_rows / max(1, page_size)))


def _safe_dark_mode() -> bool:
    try:
        return bool(ui.dark_mode().value)
    except RuntimeError:
        return bool(app.storage.user.get("dark_mode", True))


def _safe_sort_field(value: object, *, allowed: set[str], default: str) -> str:
    text = str(value or "")
    return text if text in allowed else default


def build_page() -> None:
    selected_dataset_id: int | None = None
    selected_record_id: int | None = None
    detail_container: ui.column | None = None
    plot_context_container: ui.column | None = None
    plot_container: ui.column | None = None
    active_workflow_summary: DesignTraceWorkflowSummary | None = None

    dataset_state: dict[str, Any] = {
        "search": "",
        "sort_by": "name",
        "descending": False,
        "page": 1,
        "page_size": 20,
        "total": 0,
    }
    record_state: dict[str, Any] = {
        "search": "",
        "sort_by": "id",
        "descending": False,
        "data_type": "",
        "representation": "",
        "page": 1,
        "page_size": 20,
        "total": 0,
    }
    record_search_input: ui.input | None = None
    record_type_select: ui.select | None = None
    record_repr_select: ui.select | None = None

    def _load_dataset_page() -> list[dict[str, Any]]:
        with get_unit_of_work() as uow:
            rows, total = uow.datasets.list_summary_page(
                search=str(dataset_state["search"]),
                sort_by=str(dataset_state["sort_by"]),
                descending=bool(dataset_state["descending"]),
                limit=int(dataset_state["page_size"]),
                offset=(int(dataset_state["page"]) - 1) * int(dataset_state["page_size"]),
            )

        dataset_state["total"] = total
        total_pages = _total_pages(total, int(dataset_state["page_size"]))
        if int(dataset_state["page"]) > total_pages:
            dataset_state["page"] = total_pages
            with get_unit_of_work() as uow:
                rows, total = uow.datasets.list_summary_page(
                    search=str(dataset_state["search"]),
                    sort_by=str(dataset_state["sort_by"]),
                    descending=bool(dataset_state["descending"]),
                    limit=int(dataset_state["page_size"]),
                    offset=(int(dataset_state["page"]) - 1) * int(dataset_state["page_size"]),
                )
            dataset_state["total"] = total
        return rows

    def _load_record_page(
        dataset_id: int,
        *,
        workflow_summary: DesignTraceWorkflowSummary | None = None,
    ) -> list[dict[str, Any]]:
        query = TraceIndexPageQuery(
            search=str(record_state["search"]),
            sort_by=str(record_state["sort_by"]),
            descending=bool(record_state["descending"]),
            data_type=str(record_state["data_type"]),
            representation=str(record_state["representation"]),
            limit=int(record_state["page_size"]),
            offset=(int(record_state["page"]) - 1) * int(record_state["page_size"]),
        )
        with get_unit_of_work() as uow:
            rows, total = uow.data_records.list_index_page_by_dataset(
                dataset_id,
                query=query,
            )

        record_state["total"] = total
        total_pages = _total_pages(total, int(record_state["page_size"]))
        if int(record_state["page"]) > total_pages:
            record_state["page"] = total_pages
            query = TraceIndexPageQuery(
                search=str(record_state["search"]),
                sort_by=str(record_state["sort_by"]),
                descending=bool(record_state["descending"]),
                data_type=str(record_state["data_type"]),
                representation=str(record_state["representation"]),
                limit=int(record_state["page_size"]),
                offset=(int(record_state["page"]) - 1) * int(record_state["page_size"]),
            )
            with get_unit_of_work() as uow:
                rows, total = uow.data_records.list_index_page_by_dataset(
                    dataset_id,
                    query=query,
                )
            record_state["total"] = total
        return _augment_record_rows(rows, workflow_summary)

    def _selected_record_visible(rows: list[dict[str, Any]]) -> bool:
        if selected_record_id is None:
            return False
        return any(int(row["id"]) == selected_record_id for row in rows)

    def _toggle_record_controls(enabled: bool) -> None:
        for control in (record_search_input, record_type_select, record_repr_select):
            if control is None:
                continue
            if enabled:
                control.enable()
            else:
                control.disable()

    def render_plot() -> None:
        nonlocal active_workflow_summary
        if plot_context_container is not None:
            plot_context_container.clear()
        if plot_container is None:
            return
        plot_container.clear()

        if selected_record_id is None:
            with plot_container:
                ui.label("Select a trace from the table to view visualization.").classes(
                    "text-muted p-4"
                )
            return

        try:
            with get_unit_of_work() as uow:
                record = uow.data_records.get(selected_record_id)
                if not record:
                    with plot_container:
                        ui.label("Trace not found.").classes("text-danger")
                    return
                materialized_record = materialize_trace_record(record)

                if (
                    len(materialized_record.axes) == 2
                    and materialized_record.data_type == "s_params"
                ):
                    fig = build_heatmap(cast(Any, materialized_record), dark=_safe_dark_mode())
                else:
                    fig = build_line_chart(cast(Any, materialized_record), dark=_safe_dark_mode())

            memberships = (
                active_workflow_summary.trace_membership_by_id.get(selected_record_id, ())
                if active_workflow_summary is not None
                else ()
            )
            if plot_context_container is not None:
                with (
                    plot_context_container,
                    ui.column().classes(
                        "w-full gap-2 rounded-lg border border-border bg-bg p-3 mb-3"
                    ),
                ):
                    ui.label("Selected Trace Provenance").classes(
                        "text-sm font-bold text-fg uppercase"
                    )
                    if memberships:
                        latest = memberships[-1]
                        ui.label(
                            f"Trace Source Kind: {latest.source_kind} | "
                            f"Trace Stage: {latest.stage_kind} | "
                            f"Trace Batch: #{latest.batch_id}"
                        ).classes("text-xs text-muted")
                        ui.label(latest.provenance_summary).classes("text-xs text-muted")
                    else:
                        ui.label(
                            "No TraceBatch provenance is linked to the selected trace yet."
                        ).classes("text-xs text-warning")

            with plot_container:
                ui.plotly(fig).classes("w-full h-full").style("min-height: 400px;")
        except Exception as exc:
            with plot_container:
                ui.label(f"Error rendering plot: {exc}").classes("text-danger p-4")

    @ui.refreshable
    def render_dataset_list() -> None:
        nonlocal selected_dataset_id, selected_record_id
        dataset_rows = _load_dataset_page()

        dataset_columns = [
            {"name": "id", "label": "ID", "field": "id", "sortable": True, "align": "left"},
            {"name": "name", "label": "Name", "field": "name", "sortable": True, "align": "left"},
            {
                "name": "created_at",
                "label": "Created At",
                "field": "created_at",
                "sortable": True,
                "align": "left",
                "headerClasses": _HEADER_CLASSES,
            },
        ]
        dataset_columns[0]["headerClasses"] = _HEADER_CLASSES
        dataset_columns[1]["headerClasses"] = _HEADER_CLASSES

        with ui.column().classes("w-full gap-3"):
            dataset_table = (
                ui.table(
                    columns=dataset_columns,
                    rows=[
                        {
                            **row,
                            "created_at": row["created_at"].strftime("%Y-%m-%d %H:%M:%S"),
                        }
                        for row in dataset_rows
                    ],
                    row_key="id",
                    pagination={
                        "sortBy": str(dataset_state["sort_by"]),
                        "descending": bool(dataset_state["descending"]),
                        "rowsPerPage": 0,
                    },
                    on_pagination_change=lambda e: _on_dataset_table_pagination(e.value),
                )
                .classes("w-full cursor-pointer")
                .props("dense flat bordered separator=horizontal hide-bottom")
            )

            def on_dataset_click(event: Any) -> None:
                nonlocal selected_dataset_id, selected_record_id
                row_data = event.args[1] if len(event.args) > 1 else {}
                if not isinstance(row_data, dict):
                    return
                row_id = row_data.get("id")
                if not isinstance(row_id, int):
                    return
                selected_dataset_id = row_id
                selected_record_id = None
                record_state["page"] = 1
                _toggle_record_controls(True)
                render_dataset_detail.refresh()

            dataset_table.on("rowClick", on_dataset_click)

            total_pages = _total_pages(int(dataset_state["total"]), int(dataset_state["page_size"]))
            with ui.row().classes("w-full justify-between items-center flex-wrap gap-2"):
                ui.label(
                    f"{dataset_state['total']} designs · "
                    f"Page {dataset_state['page']} / {total_pages}"
                ).classes("text-xs text-muted")
                with ui.row().classes("items-center gap-2"):
                    ui.select(
                        {20: "20 / page", 50: "50 / page", 100: "100 / page"},
                        value=int(dataset_state["page_size"]),
                        on_change=lambda e: (
                            dataset_state.__setitem__("page_size", int(e.value)),
                            dataset_state.__setitem__("page", 1),
                            render_dataset_list.refresh(),
                        ),
                    ).props("dense outlined options-dense").classes("w-28")
                    dataset_prev_button = ui.button(
                        "Prev",
                        on_click=lambda: (
                            dataset_state.__setitem__(
                                "page",
                                max(1, int(dataset_state["page"]) - 1),
                            ),
                            render_dataset_list.refresh(),
                        ),
                    ).props("dense flat no-caps")
                    if int(dataset_state["page"]) <= 1:
                        dataset_prev_button.disable()
                    dataset_next_button = ui.button(
                        "Next",
                        on_click=lambda: (
                            dataset_state.__setitem__(
                                "page",
                                min(total_pages, int(dataset_state["page"]) + 1),
                            ),
                            render_dataset_list.refresh(),
                        ),
                    ).props("dense flat no-caps")
                    if int(dataset_state["page"]) >= total_pages:
                        dataset_next_button.disable()

            if selected_dataset_id is not None and not any(
                int(row["id"]) == selected_dataset_id for row in dataset_rows
            ):
                selected_record_id = None

    def _on_dataset_table_pagination(pagination: Any) -> None:
        if not isinstance(pagination, dict):
            return
        new_sort = _safe_sort_field(
            pagination.get("sortBy"),
            allowed=_DATASET_SORT_FIELDS,
            default=str(dataset_state["sort_by"]),
        )
        new_desc = bool(pagination.get("descending", False))
        if new_sort == str(dataset_state["sort_by"]) and new_desc == bool(
            dataset_state["descending"]
        ):
            return
        dataset_state["sort_by"] = new_sort
        dataset_state["descending"] = new_desc
        dataset_state["page"] = 1
        render_dataset_list.refresh()

    @ui.refreshable
    def render_dataset_detail() -> None:
        nonlocal active_workflow_summary, selected_record_id
        if detail_container is None:
            return
        detail_container.clear()

        if selected_dataset_id is None:
            with detail_container:
                ui.label("Select a design from the list to preview.").classes(
                    "text-muted italic text-center w-full mt-10"
                )
            return

        with get_unit_of_work() as uow:
            dataset = uow.datasets.get(selected_dataset_id)
            workflow_summary = (
                summarize_design_trace_workflow(
                    design_id=int(dataset.id),
                    design_name=str(dataset.name),
                    trace_repo=uow.data_records,
                    trace_batch_repo=cast(Any, uow.result_bundles),
                )
                if dataset is not None and dataset.id is not None
                else None
            )
        if dataset is None:
            with detail_container:
                ui.label("Design not found.").classes("text-danger")
            return
        active_workflow_summary = workflow_summary

        record_rows = _load_record_page(selected_dataset_id, workflow_summary=workflow_summary)
        if not _selected_record_visible(record_rows):
            selected_record_id = None

        persisted_profile = normalize_dataset_profile(dataset.source_meta)
        compare_status_label, compare_status_classes = _compare_status_badge(
            workflow_summary.compare_status if workflow_summary is not None else "blocked"
        )

        with detail_container:
            with ui.row().classes("w-full justify-between items-center mb-3 flex-wrap gap-3"):
                with ui.column().classes("gap-1"):
                    ui.label(dataset.name).classes("text-xl font-bold text-fg")
                    ui.label(f"{record_state['total']} traces available.").classes(
                        "text-sm text-muted"
                    )
                ui.button(
                    "Analyze This Design",
                    on_click=lambda: _navigate_to_characterization(selected_dataset_id),
                    icon="science",
                ).props("unelevated color=primary no-caps")

            with ui.column().classes("w-full gap-2 rounded-lg border border-border bg-bg p-3 mb-3"):
                ui.label("Design Summary").classes("text-sm font-bold text-fg uppercase")
                ui.label(
                    f"Current Design Scope: {dataset.name} (Design #{int(dataset.id or 0)})"
                ).classes("text-xs text-muted")
                ui.label(
                    design_profile_summary_text(
                        {
                            "device_type": persisted_profile["device_type"],
                            "capabilities": persisted_profile["capabilities"],
                            "source": persisted_profile["source"],
                        }
                    )
                ).classes("text-xs text-muted")
                with ui.row().classes("w-full items-center justify-between gap-3 flex-wrap"):
                    ui.label(f"Compare Readiness: {compare_status_label}").classes(
                        f"text-xs {compare_status_classes}"
                    )
                    ui.label(
                        workflow_summary.compare_message
                        if workflow_summary is not None
                        else "No design workflow summary is available."
                    ).classes("text-xs text-muted")
                ui.label(
                    workflow_summary.trace_store_read_path
                    if workflow_summary is not None
                    else "TraceStore-first read path summary unavailable."
                ).classes("text-xs text-muted")
                with ui.row().classes("w-full items-center justify-between gap-3 flex-wrap"):
                    ui.label(
                        "Design profile editing moved to Pipeline Dashboard "
                        "for single-entry consistency."
                    ).classes("text-xs text-muted")
                    ui.button(
                        "Edit Design Profile",
                        icon="dashboard",
                        on_click=lambda: ui.navigate.to("/dashboard"),
                    ).props("outline color=primary no-caps")

            with ui.column().classes("w-full gap-2 rounded-lg border border-border bg-bg p-3 mb-3"):
                ui.label("Trace Source Summary").classes("text-sm font-bold text-fg uppercase")
                if workflow_summary is None or not workflow_summary.source_summaries:
                    ui.label(
                        "Blocked: this design does not have persisted TraceBatch provenance yet."
                    ).classes("text-xs text-warning")
                else:
                    for source_summary in workflow_summary.source_summaries:
                        with ui.row().classes(
                            "w-full items-start justify-between gap-3 "
                            "rounded-md border border-border/60 p-2 flex-wrap"
                        ):
                            with ui.column().classes("gap-1"):
                                ui.label(source_summary.source_kind).classes(
                                    "text-sm font-semibold text-fg"
                                )
                                ui.label(
                                    f"Stages: {', '.join(source_summary.stage_kinds)}"
                                ).classes("text-xs text-muted")
                                ui.label(source_summary.latest_provenance_summary).classes(
                                    "text-xs text-muted"
                                )
                            ui.label(
                                f"{source_summary.trace_count} traces across "
                                f"{source_summary.batch_count} batches"
                            ).classes("text-xs text-muted")

            record_columns = [
                {
                    "name": "id",
                    "label": "ID",
                    "field": "id",
                    "sortable": True,
                    "align": "left",
                    "headerClasses": _HEADER_CLASSES,
                },
                {
                    "name": "data_type",
                    "label": "Type",
                    "field": "data_type",
                    "sortable": True,
                    "align": "left",
                    "headerClasses": _HEADER_CLASSES,
                },
                {
                    "name": "parameter",
                    "label": "Param",
                    "field": "parameter",
                    "sortable": True,
                    "align": "left",
                    "headerClasses": _HEADER_CLASSES,
                },
                {
                    "name": "representation",
                    "label": "Repr",
                    "field": "representation",
                    "sortable": True,
                    "align": "left",
                    "headerClasses": _HEADER_CLASSES,
                },
                {
                    "name": "source_kind",
                    "label": "Source",
                    "field": "source_kind",
                    "sortable": False,
                    "align": "left",
                    "headerClasses": _HEADER_CLASSES,
                },
                {
                    "name": "stage_kind",
                    "label": "Stage",
                    "field": "stage_kind",
                    "sortable": False,
                    "align": "left",
                    "headerClasses": _HEADER_CLASSES,
                },
                {
                    "name": "trace_batch",
                    "label": "Trace Batch",
                    "field": "trace_batch",
                    "sortable": False,
                    "align": "left",
                    "headerClasses": _HEADER_CLASSES,
                },
            ]
            record_table = (
                ui.table(
                    columns=record_columns,
                    rows=record_rows,
                    row_key="id",
                    pagination={
                        "sortBy": str(record_state["sort_by"]),
                        "descending": bool(record_state["descending"]),
                        "rowsPerPage": 0,
                    },
                    on_pagination_change=lambda e: _on_record_table_pagination(e.value),
                )
                .classes("w-full cursor-pointer mb-2")
                .props("dense flat bordered separator=horizontal hide-bottom")
            )

            def on_record_click(event: Any) -> None:
                nonlocal selected_record_id
                row_data = event.args[1] if len(event.args) > 1 else {}
                if not isinstance(row_data, dict):
                    return
                row_id = row_data.get("id")
                if not isinstance(row_id, int):
                    return
                selected_record_id = row_id
                render_plot()

            record_table.on("rowClick", on_record_click)

            total_pages = _total_pages(int(record_state["total"]), int(record_state["page_size"]))
            with ui.row().classes("w-full justify-between items-center flex-wrap gap-2"):
                ui.label(
                    f"{record_state['total']} traces · Page {record_state['page']} / {total_pages}"
                ).classes("text-xs text-muted")
                with ui.row().classes("items-center gap-2"):
                    ui.select(
                        {20: "20 / page", 50: "50 / page", 100: "100 / page"},
                        value=int(record_state["page_size"]),
                        on_change=lambda e: (
                            record_state.__setitem__("page_size", int(e.value)),
                            record_state.__setitem__("page", 1),
                            render_dataset_detail.refresh(),
                        ),
                    ).props("dense outlined options-dense").classes("w-28")
                    record_prev_button = ui.button(
                        "Prev",
                        on_click=lambda: (
                            record_state.__setitem__(
                                "page",
                                max(1, int(record_state["page"]) - 1),
                            ),
                            render_dataset_detail.refresh(),
                        ),
                    ).props("dense flat no-caps")
                    if int(record_state["page"]) <= 1:
                        record_prev_button.disable()
                    record_next_button = ui.button(
                        "Next",
                        on_click=lambda: (
                            record_state.__setitem__(
                                "page",
                                min(total_pages, int(record_state["page"]) + 1),
                            ),
                            render_dataset_detail.refresh(),
                        ),
                    ).props("dense flat no-caps")
                    if int(record_state["page"]) >= total_pages:
                        record_next_button.disable()

            ui.label("Visualization Preview").classes(
                "text-sm font-semibold text-muted tracking-wider mt-3 mb-2 uppercase"
            )
            nonlocal plot_context_container
            plot_context_container = ui.column().classes("w-full")
            nonlocal plot_container
            plot_container = ui.column().classes(
                "w-full app-plotly-container min-h-[400px] flex items-center justify-center"
            )
            render_plot()

    def _on_record_table_pagination(pagination: Any) -> None:
        if not isinstance(pagination, dict):
            return
        new_sort = _safe_sort_field(
            pagination.get("sortBy"),
            allowed=_RECORD_SORT_FIELDS,
            default=str(record_state["sort_by"]),
        )
        new_desc = bool(pagination.get("descending", False))
        if new_sort == str(record_state["sort_by"]) and new_desc == bool(
            record_state["descending"]
        ):
            return
        record_state["sort_by"] = new_sort
        record_state["descending"] = new_desc
        record_state["page"] = 1
        render_dataset_detail.refresh()

    def content() -> None:
        nonlocal \
            detail_container, \
            plot_context_container, \
            record_search_input, \
            record_type_select, \
            record_repr_select
        ui.label("Raw Data Browser").classes("text-2xl font-bold text-fg mb-4")

        with ui.column().classes("w-full gap-6"):
            with ui.column().classes("app-card w-full p-4 flex flex-col gap-3"):
                ui.label("Designs").classes("app-section-title")
                dataset_search = (
                    ui.input(
                        label="Search Design",
                        value=str(dataset_state["search"]),
                    )
                    .props("dense outlined clearable")
                    .classes("min-w-[240px] w-full")
                )

                dataset_search.on_value_change(
                    lambda e: (
                        dataset_state.__setitem__("search", str(e.value or "")),
                        dataset_state.__setitem__("page", 1),
                        render_dataset_list.refresh(),
                    )
                )
                render_dataset_list()

            with ui.column().classes("app-card w-full p-4 flex flex-col gap-3"):
                ui.label("Design Summary + Trace Preview").classes("app-section-title")
                with ui.row().classes("w-full gap-3 flex-wrap"):
                    record_search_input = (
                        ui.input(
                            label="Filter Traces",
                            value=str(record_state["search"]),
                        )
                        .props("dense outlined clearable")
                        .classes("min-w-[240px] flex-1")
                    )
                    record_search_input.on_value_change(
                        lambda e: (
                            record_state.__setitem__("search", str(e.value or "")),
                            record_state.__setitem__("page", 1),
                            render_dataset_detail.refresh(),
                        )
                    )
                    record_type_select = (
                        ui.select(
                            _DATA_TYPE_FILTER_OPTIONS,
                            value=str(record_state["data_type"]),
                            label="Type",
                            on_change=lambda e: (
                                record_state.__setitem__("data_type", str(e.value)),
                                record_state.__setitem__("page", 1),
                                render_dataset_detail.refresh(),
                            ),
                        )
                        .props("dense outlined options-dense")
                        .classes("w-44")
                    )
                    record_repr_select = (
                        ui.select(
                            _REPRESENTATION_FILTER_OPTIONS,
                            value=str(record_state["representation"]),
                            label="Repr",
                            on_change=lambda e: (
                                record_state.__setitem__("representation", str(e.value)),
                                record_state.__setitem__("page", 1),
                                render_dataset_detail.refresh(),
                            ),
                        )
                        .props("dense outlined options-dense")
                        .classes("w-44")
                    )
                    _toggle_record_controls(False)
                detail_container = ui.column().classes("w-full")
                render_dataset_detail()

    content()


def _navigate_to_characterization(dataset_id: int | None) -> None:
    if dataset_id is None:
        return
    current_selection = app.storage.user.get("selected_datasets", [])
    if dataset_id not in current_selection:
        current_selection.append(dataset_id)
        app.storage.user["selected_datasets"] = current_selection
    ui.navigate.to("/characterization")
