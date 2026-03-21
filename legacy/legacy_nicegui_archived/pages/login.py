"""Minimal login page for the WS5 local auth/session seam."""

from __future__ import annotations

import json

from fastapi import Request
from nicegui import ui


@ui.page("/login")
def login_page(request: Request) -> None:
    """Render a minimal login page that authenticates via `/api/v1/auth/login`."""
    next_path = str(request.query_params.get("next", "/dashboard") or "/dashboard")
    ui.query("body").classes("bg-bg text-fg")

    async def submit() -> None:
        message.text = ""
        result = await ui.run_javascript(
            f"""
            const response = await fetch('/api/v1/auth/login', {{
              method: 'POST',
              headers: {{ 'Content-Type': 'application/json' }},
              credentials: 'same-origin',
              body: JSON.stringify({{
                username: {json.dumps(username_input.value or "")},
                password: {json.dumps(password_input.value or "")},
              }}),
            }});
            let body = {{}};
            try {{
              body = await response.json();
            }} catch (_error) {{
              body = {{}};
            }}
            return {{ status: response.status, body }};
            """,
            timeout=10.0,
        )
        if isinstance(result, dict) and int(result.get("status", 500)) == 200:
            ui.navigate.to(next_path)
            return
        if isinstance(result, dict):
            body = result.get("body", {})
            if isinstance(body, dict):
                message.text = str(body.get("detail", "Login failed"))
                return
        message.text = "Login failed"

    with ui.column().classes("w-full min-h-screen items-center justify-center px-4 py-6"):
        with ui.column().classes("app-card w-full max-w-md gap-4 p-6 sm:p-8"):
            ui.label("Sign In").classes("app-section-title text-3xl font-bold text-center")
            ui.label(
                "Use the local phase-1 account to access the app and `/api/v1/*`."
            ).classes("text-sm text-muted text-center")

            username_input = (
                ui.input("Username")
                .props("outlined dense")
                .classes("w-full")
                .on("keydown.enter", submit)
            )
            password_input = (
                ui.input("Password", password=True, password_toggle_button=True)
                .props("outlined dense")
                .classes("w-full")
                .on("keydown.enter", submit)
            )
            message = ui.label("").classes("text-sm text-negative min-h-[1.5rem]")
            ui.button("Sign In", on_click=submit).props("color=primary").classes("w-full")
