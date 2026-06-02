from __future__ import annotations

from collections.abc import Callable

from fastapi import FastAPI, Request

from src.app.infrastructure.app_state_repository import AppStateRepository
from src.app.infrastructure.session_jwt_transport import (
    APP_CONTEXT_COOKIE_NAME,
    SESSION_COOKIE_NAME,
    SessionJwtTransport,
)


def install_request_session_middleware(
    app: FastAPI,
    *,
    session_repository_factory: Callable[[], AppStateRepository],
    token_transport_factory: Callable[[], SessionJwtTransport],
) -> None:
    @app.middleware("http")
    async def request_session_context_middleware(request: Request, call_next):
        session_repository = session_repository_factory()
        app_context_id = session_repository.ensure_app_context(
            request.cookies.get(APP_CONTEXT_COOKIE_NAME)
        )
        app_context_binding = session_repository.bind_request_app_context_id(app_context_id)
        try:
            app_context_state = session_repository.get_app_context_state(app_context_id)
            if app_context_state.runtime_mode == "online":
                session_state = _resolve_request_session_state(
                    session_token=request.cookies.get(SESSION_COOKIE_NAME),
                    session_repository=session_repository,
                    token_transport=token_transport_factory(),
                )
            else:
                session_state = app_context_state
            session_binding = session_repository.bind_request_session_state(session_state)
            try:
                response = await call_next(request)
            finally:
                session_repository.reset_request_session_state(session_binding)
            response.set_cookie(
                APP_CONTEXT_COOKIE_NAME,
                app_context_id,
                httponly=True,
                path="/",
            )
            return response
        finally:
            session_repository.reset_request_app_context_id(app_context_binding)


def _resolve_request_session_state(
    *,
    session_token: str | None,
    session_repository: AppStateRepository,
    token_transport: SessionJwtTransport,
):
    if session_token is None or len(session_token.strip()) == 0:
        return session_repository.build_public_request_session_state("anonymous")
    verified = token_transport.verify_token(session_token)
    if verified.status == "valid" and verified.session_id is not None:
        session_state = session_repository.get_authenticated_session_state(verified.session_id)
        if session_state is not None:
            return session_state
        return session_repository.build_public_request_session_state("degraded")

    if verified.status == "expired":
        return session_repository.build_public_request_session_state("degraded")
    return session_repository.build_public_request_session_state("anonymous")
