"""FastAPI dependencies shared by the WS5 `/api/v1` routers."""

from __future__ import annotations

from fastapi import HTTPException, Request, status

from legacy.legacy_nicegui_archived.services.auth_service import SessionPrincipal, get_active_user
from core.shared.persistence.models import UserRecord

_SESSION_USER_KEY = "sc_user"


def session_user_key() -> str:
    """Return the stable session key used for the authenticated principal."""
    return _SESSION_USER_KEY


def get_session_principal(request: Request) -> SessionPrincipal | None:
    """Read the authenticated principal from the signed session cookie."""
    payload = request.session.get(_SESSION_USER_KEY)
    if not isinstance(payload, dict):
        return None
    raw_user_id = payload.get("user_id")
    raw_username = payload.get("username")
    raw_role = payload.get("role")
    if not isinstance(raw_user_id, int):
        return None
    if not isinstance(raw_username, str) or not raw_username.strip():
        return None
    if not isinstance(raw_role, str) or not raw_role.strip():
        return None
    return SessionPrincipal(
        user_id=int(raw_user_id),
        username=raw_username,
        role=raw_role,
    )


def current_user(request: Request) -> UserRecord:
    """Resolve the authenticated active user or raise `401`."""
    principal = get_session_principal(request)
    if principal is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unauthenticated",
        )
    user = get_active_user(principal.user_id)
    if user is None:
        request.session.pop(_SESSION_USER_KEY, None)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unauthenticated",
        )
    return user


def admin_user(request: Request) -> UserRecord:
    """Resolve the authenticated admin user or raise `403`."""
    user = current_user(request)
    if user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin role required",
        )
    return user
