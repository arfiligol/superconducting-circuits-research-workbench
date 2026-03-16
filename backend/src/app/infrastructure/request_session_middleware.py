from __future__ import annotations

from collections.abc import Callable

from fastapi import FastAPI, Request

from src.app.infrastructure.rewrite_app_state_repository import InMemoryRewriteAppStateRepository
from src.app.infrastructure.session_jwt_transport import SESSION_COOKIE_NAME, SessionJwtTransport


def install_request_session_middleware(
    app: FastAPI,
    *,
    session_repository_factory: Callable[[], InMemoryRewriteAppStateRepository],
    token_transport_factory: Callable[[], SessionJwtTransport],
) -> None:
    @app.middleware("http")
    async def request_session_context_middleware(request: Request, call_next):
        session_repository = session_repository_factory()
        if session_repository.get_runtime_mode() != "online":
            return await call_next(request)
        session_token = request.cookies.get(SESSION_COOKIE_NAME)
        if session_token is None or len(session_token.strip()) == 0:
            return await call_next(request)
        session_state = _resolve_request_session_state(
            session_token=session_token,
            session_repository=session_repository,
            token_transport=token_transport_factory(),
        )
        binding = session_repository.bind_request_session_state(session_state)
        try:
            return await call_next(request)
        finally:
            session_repository.reset_request_session_state(binding)


def _resolve_request_session_state(
    *,
    session_token: str | None,
    session_repository: InMemoryRewriteAppStateRepository,
    token_transport: SessionJwtTransport,
):
    verified = token_transport.verify_token(session_token)
    if verified.status == "valid" and verified.session_id is not None:
        session_state = session_repository.get_authenticated_session_state(verified.session_id)
        if session_state is not None:
            return session_state
        return session_repository.build_public_request_session_state("degraded")

    if verified.status == "expired":
        return session_repository.build_public_request_session_state("degraded")
    return session_repository.build_public_request_session_state("anonymous")
