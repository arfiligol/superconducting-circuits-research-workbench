"""Schema management page with paged/searchable circuit list."""

from __future__ import annotations

import math
from datetime import datetime
from typing import Any

from nicegui import ui

from legacy.legacy_nicegui_archived.ui.states import render_empty_state
from core.shared.persistence import get_unit_of_work


def _total_pages(total_rows: int, page_size: int) -> int:
    return max(1, math.ceil(total_rows / max(1, page_size)))


def _to_int(value: object, default: int = 0) -> int:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        try:
            return int(value)
        except ValueError:
            return default
    return default


def build_page() -> None:
    state: dict[str, Any] = {
        "search": "",
        "sort_by": "created_at",
        "descending": True,
        "page": 1,
        "page_size": 12,
        "total": 0,
    }

    def _load_page() -> list[dict[str, int | str | datetime]]:
        with get_unit_of_work() as uow:
            rows, total = uow.circuits.list_summary_page(
                search=str(state["search"]),
                sort_by=str(state["sort_by"]),
                descending=bool(state["descending"]),
                limit=int(state["page_size"]),
                offset=(int(state["page"]) - 1) * int(state["page_size"]),
            )
        state["total"] = total
        total_pages = _total_pages(total, int(state["page_size"]))
        if int(state["page"]) > total_pages:
            state["page"] = total_pages
            with get_unit_of_work() as uow:
                rows, total = uow.circuits.list_summary_page(
                    search=str(state["search"]),
                    sort_by=str(state["sort_by"]),
                    descending=bool(state["descending"]),
                    limit=int(state["page_size"]),
                    offset=(int(state["page"]) - 1) * int(state["page_size"]),
                )
            state["total"] = total
        return rows

    @ui.refreshable
    def render_list() -> None:
        rows = _load_page()
        if not rows and int(state["total"]) == 0:
            render_empty_state(
                icon="account_tree",
                title="No Circuit Schemas Found",
                message="Create a new circuit schema to get started.",
            )
            return

        with ui.column().classes("w-full gap-4"):
            for row in rows:
                circuit_id = _to_int(row.get("id"), 0)
                circuit_name = str(row.get("name", ""))
                created_at = row.get("created_at")
                created_label = (
                    created_at.strftime("%Y-%m-%d %H:%M:%S")
                    if isinstance(created_at, datetime)
                    else str(created_at)
                )

                with (
                    ui.card().classes("w-full bg-surface p-4"),
                    ui.element("div").classes(
                        "w-full grid grid-cols-[minmax(0,1fr)_120px] gap-x-4 gap-y-2 items-start"
                    ),
                ):
                    ui.label(circuit_name).classes(
                        "font-bold text-lg text-fg break-words leading-tight"
                    )
                    with ui.row().classes("w-full justify-end gap-2"):
                        ui.button(
                            icon="edit",
                            on_click=lambda c_id=circuit_id: ui.navigate.to(f"/schemas/{c_id}"),
                        ).props("flat round size=sm color=primary tooltip='Edit Schema'")

                        def _delete_handler(
                            row_id: int = circuit_id,
                            name: str = circuit_name,
                        ) -> None:
                            with get_unit_of_work() as uow:
                                deleted = uow.circuits.delete(row_id)
                                if deleted:
                                    uow.commit()
                                else:
                                    uow.rollback()
                            if deleted:
                                ui.notify(f"Deleted {name}", type="info")
                                render_list.refresh()
                            else:
                                ui.notify(
                                    f"Schema {name} not found",
                                    type="warning",
                                )

                        ui.button(icon="delete", on_click=_delete_handler).props(
                            "flat round size=sm color=negative tooltip='Delete Schema'"
                        )
                    ui.label(f"Created: {created_label}").classes("text-xs text-muted")
                    ui.element("div")

            total_pages = _total_pages(int(state["total"]), int(state["page_size"]))
            with ui.row().classes("w-full justify-between items-center flex-wrap gap-2"):
                ui.label(
                    f"{state['total']} schemas · Page {state['page']} / {total_pages}"
                ).classes("text-xs text-muted")
                with ui.row().classes("items-center gap-2"):
                    ui.select(
                        {12: "12 / page", 24: "24 / page", 48: "48 / page"},
                        value=int(state["page_size"]),
                        on_change=lambda e: (
                            state.__setitem__("page_size", int(e.value)),
                            state.__setitem__("page", 1),
                            render_list.refresh(),
                        ),
                    ).props("dense outlined options-dense").classes("w-28")
                    prev_button = ui.button(
                        "Prev",
                        on_click=lambda: (
                            state.__setitem__("page", max(1, int(state["page"]) - 1)),
                            render_list.refresh(),
                        ),
                    ).props("dense flat no-caps")
                    if int(state["page"]) <= 1:
                        prev_button.disable()
                    next_button = ui.button(
                        "Next",
                        on_click=lambda: (
                            state.__setitem__(
                                "page",
                                min(total_pages, int(state["page"]) + 1),
                            ),
                            render_list.refresh(),
                        ),
                    ).props("dense flat no-caps")
                    if int(state["page"]) >= total_pages:
                        next_button.disable()

    def content() -> None:
        with ui.row().classes("w-full justify-between items-center mb-6"):
            with ui.column().classes("gap-1"):
                ui.label("Circuit Schemas").classes("text-2xl font-bold text-fg")
                ui.label("Manage your superconducting circuit designs").classes(
                    "text-sm text-muted"
                )

            ui.button(
                "New Circuit",
                icon="add",
                on_click=lambda: ui.navigate.to("/schemas/new"),
            ).props("color=primary no-caps")

        with ui.row().classes("w-full gap-3 items-end flex-wrap mb-4"):
            search_input = (
                ui.input(
                    label="Search Schema",
                    value=str(state["search"]),
                )
                .props("dense outlined clearable")
                .classes("min-w-[220px] flex-1")
            )
            search_input.on_value_change(
                lambda e: (
                    state.__setitem__("search", str(e.value or "")),
                    state.__setitem__("page", 1),
                    render_list.refresh(),
                )
            )
            ui.select(
                {"created_at": "Created At", "name": "Name", "id": "ID"},
                value=str(state["sort_by"]),
                label="Sort By",
                on_change=lambda e: (
                    state.__setitem__("sort_by", str(e.value)),
                    state.__setitem__("page", 1),
                    render_list.refresh(),
                ),
            ).props("dense outlined options-dense").classes("w-44")
            ui.select(
                {False: "Ascending", True: "Descending"},
                value=bool(state["descending"]),
                label="Order",
                on_change=lambda e: (
                    state.__setitem__("descending", bool(e.value)),
                    state.__setitem__("page", 1),
                    render_list.refresh(),
                ),
            ).props("dense outlined options-dense").classes("w-40")

        render_list()

    content()
