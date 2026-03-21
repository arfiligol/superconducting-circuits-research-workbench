"""Archived NiceGUI composition root retained for legacy verification only."""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path
from urllib.parse import quote

from nicegui import app as ui_app
from nicegui import ui
from nicegui.storage import set_storage_secret
from starlette.middleware import Middleware
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import RedirectResponse, Response

from legacy.legacy_nicegui_archived.api.dependencies import get_session_principal, session_user_key
from legacy.legacy_nicegui_archived.api.router import api_v1_router
from legacy.legacy_nicegui_archived.services.auth_service import ensure_bootstrap_admin, get_active_user
from legacy.legacy_nicegui_archived.services.browser_tooling import shared_frontend_tooling_head_html
from core.shared.persistence.startup_reconcile import run_startup_reconcile

_STATIC_REGISTERED_ATTR = "_sc_static_registered"
_PAGES_REGISTERED_ATTR = "_sc_pages_registered"
_API_REGISTERED_ATTR = "_sc_api_registered"
_SESSION_REGISTERED_ATTR = "_sc_session_registered"
_PAGE_GUARD_REGISTERED_ATTR = "_sc_page_guard_registered"
_BOOTSTRAP_ADMIN_ATTR = "_sc_bootstrap_admin_ensured"
_RUN_CONFIG_REGISTERED_ATTR = "_sc_run_config_registered"

logger = logging.getLogger(__name__)

_PUBLIC_PAGE_PATHS = frozenset({"/login"})
_PUBLIC_PATH_PREFIXES = (
    "/_nicegui",
    "/styles",
    "/favicon.ico",
)


def _session_secret() -> str:
    """Return the signed-cookie secret used for NiceGUI and WS5 sessions."""
    return os.getenv("SC_SESSION_SECRET", "SC_DATA_BROWSER_SECRET")


def _app_host() -> str:
    """Return the host binding for the NiceGUI server."""
    return str(os.getenv("SC_APP_HOST", "127.0.0.1") or "127.0.0.1").strip() or "127.0.0.1"


def _next_target(request: Request) -> str:
    """Build the stable next-target path for login redirects."""
    path = request.url.path or "/"
    if request.url.query:
        return f"{path}?{request.url.query}"
    return path


class _PageAuthMiddleware(BaseHTTPMiddleware):
    """Redirect unauthenticated page requests to the WS5 login page."""

    async def dispatch(
        self,
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:
        path = request.url.path or "/"
        if path.startswith("/api/"):
            return await call_next(request)
        if any(path.startswith(prefix) for prefix in _PUBLIC_PATH_PREFIXES):
            return await call_next(request)

        principal = get_session_principal(request)
        user = get_active_user(principal.user_id) if principal is not None else None
        if path == "/login" and user is not None:
            next_target = str(request.query_params.get("next", "/dashboard") or "/dashboard")
            return RedirectResponse(url=next_target, status_code=307)
        if path in _PUBLIC_PAGE_PATHS:
            return await call_next(request)
        if user is None:
            request.session.pop(session_user_key(), None)
            next_target = quote(_next_target(request), safe="")
            return RedirectResponse(url=f"/login?next={next_target}", status_code=307)

        return await call_next(request)


def _env_flag(name: str, *, default: bool) -> bool:
    """Parse one boolean environment flag with a safe default."""
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _register_static_files() -> None:
    """Register the shared stylesheet mount once."""
    if getattr(ui_app.state, _STATIC_REGISTERED_ATTR, False):
        return
    styles_dir = Path(__file__).parent / "styles"
    ui_app.add_static_files("/styles", str(styles_dir))
    setattr(ui_app.state, _STATIC_REGISTERED_ATTR, True)


def _register_session_storage() -> None:
    """Enable NiceGUI user storage and WS5 signed session cookies once."""
    if getattr(ui_app.state, _SESSION_REGISTERED_ATTR, False):
        return
    set_storage_secret(_session_secret())
    setattr(ui_app.state, _SESSION_REGISTERED_ATTR, True)


def _register_page_guard() -> None:
    """Attach the authenticated-page middleware after session storage."""
    if getattr(ui_app.state, _PAGE_GUARD_REGISTERED_ATTR, False):
        return
    ui_app.user_middleware.append(Middleware(_PageAuthMiddleware))
    setattr(ui_app.state, _PAGE_GUARD_REGISTERED_ATTR, True)


def _register_api() -> None:
    """Include the public `/api/v1/*` router once."""
    if getattr(ui_app.state, _API_REGISTERED_ATTR, False):
        return
    ui_app.include_router(api_v1_router)
    setattr(ui_app.state, _API_REGISTERED_ATTR, True)


def _register_run_config() -> None:
    """Populate the minimal NiceGUI run config so lifespan startup works in tests."""
    if getattr(ui_app.state, _RUN_CONFIG_REGISTERED_ATTR, False):
        return
    ui_app.config.add_run_config(
        reload=_env_flag("SC_APP_RELOAD", default=False),
        title="SC Tutorial App",
        viewport="width=device-width, initial-scale=1",
        favicon=None,
        dark=True,
        language="en-US",
        binding_refresh_interval=0.1,
        reconnect_timeout=float(os.getenv("SC_APP_RECONNECT_TIMEOUT", "30.0")),
        message_history_length=int(os.getenv("SC_APP_MESSAGE_HISTORY_LENGTH", "5000")),
        tailwind=True,
        unocss=None,
        prod_js=True,
        show_welcome_message=False,
    )
    setattr(ui_app.state, _RUN_CONFIG_REGISTERED_ATTR, True)


def _register_pages() -> None:
    """Import NiceGUI page modules once so their routes register."""
    if getattr(ui_app.state, _PAGES_REGISTERED_ATTR, False):
        return
    from legacy.legacy_nicegui_archived.pages import (  # noqa: F401
        characterization,
        dashboard,
        home,
        login,
        raw_data,
        schema_editor,
        schemas,
        schemdraw_live_preview,
        simulation,
    )

    setattr(ui_app.state, _PAGES_REGISTERED_ATTR, True)


def _ensure_bootstrap_admin() -> None:
    """Ensure the phase-1 bootstrap admin exists once per process."""
    if getattr(ui_app.state, _BOOTSTRAP_ADMIN_ATTR, False):
        return
    ensure_bootstrap_admin()
    setattr(ui_app.state, _BOOTSTRAP_ADMIN_ATTR, True)


def configure_app() -> None:
    """Assemble the WS5 app composition root exactly once."""
    _register_run_config()
    _register_static_files()
    _register_session_storage()
    _register_page_guard()
    _register_api()
    _register_pages()
    _ensure_bootstrap_admin()


def start():
    """Launch the NiceGUI application."""
    # NiceGUI reload mode expects execution as a module/script (__main__/__mp_main__).
    # Console-script entry points import this module as
    # `legacy.legacy_nicegui_archived.main`, so re-exec once as a module.
    if __name__ not in {"__main__", "__mp_main__"}:
        os.execv(sys.executable, [sys.executable, "-m", "legacy.legacy_nicegui_archived.main"])

    configure_app()
    reconcile_summary = run_startup_reconcile(source="legacy_nicegui_archived")
    logger.info(
        "app startup reconcile stale_tasks=%s failed_batches=%s orphan_batches=%s",
        reconcile_summary.stale_task_ids,
        reconcile_summary.failed_batch_ids,
        reconcile_summary.orphan_batch_ids,
    )

    # Inject CSS globally via a head_html string
    # This guarantees the styles are loaded before content renders
    ui.add_head_html(
        (
            """
        <link href="/styles/theme.css" rel="stylesheet">
        <link href="/styles/components.css" rel="stylesheet">
        <style>
            /* NiceGUI Specific overrides to respect root tokens */
            body { background-color: rgb(var(--bg)); color: rgb(var(--fg)); }
        </style>
    """
            + shared_frontend_tooling_head_html()
        ),
        shared=True,
    )

    # Run the app
    # - dark=True: Default to dark mode
    # - show=True: Open browser automatically
    # - port=8080: Standard dev port
    # - reload=False by default to avoid unexpected refresh during long simulations
    #   (set SC_APP_RELOAD=1 for development hot reload)
    ui.run(
        title="SC Tutorial App",
        host=_app_host(),
        port=int(os.getenv("SC_APP_PORT", "8080")),
        dark=True,
        show=False,  # Wait until everything loads cleanly, user can click or we can show later
        reload=_env_flag("SC_APP_RELOAD", default=False),
        reconnect_timeout=float(os.getenv("SC_APP_RECONNECT_TIMEOUT", "30.0")),
        message_history_length=int(os.getenv("SC_APP_MESSAGE_HISTORY_LENGTH", "5000")),
    )


configure_app()


if __name__ in {"__main__", "__mp_main__"}:
    start()
