"""`/api/v1/auth/*` routes for local session authentication."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, status

from legacy.legacy_nicegui_archived.api.dependencies import current_user, session_user_key
from legacy.legacy_nicegui_archived.api.schemas import AuthResponse, LoginRequest, LogoutResponse, UserResponse
from legacy.legacy_nicegui_archived.services.auth_service import authenticate_user, build_session_principal
from core.shared.persistence import get_unit_of_work
from core.shared.persistence.models import UserRecord

router = APIRouter(prefix="/auth", tags=["auth"])


def _user_response(user: UserRecord) -> UserResponse:
    if user.id is None:
        raise ValueError("Persisted user must expose an ID.")
    return UserResponse(
        id=int(user.id),
        username=str(user.username),
        role=str(user.role),
        is_active=bool(user.is_active),
        created_at=user.created_at,
        last_login_at=user.last_login_at,
    )


@router.post("/login", response_model=AuthResponse)
def login(payload: LoginRequest, request: Request) -> AuthResponse:
    """Authenticate one local user and persist the signed session principal."""
    user = authenticate_user(payload.username, payload.password)
    if user is None:
        with get_unit_of_work() as uow:
            uow.audit_logs.append_log(
                actor_id=None,
                action_kind="auth.login_failed",
                resource_kind="session",
                resource_id=payload.username,
                summary=f"Failed login attempt for username '{payload.username}'.",
                payload={"username": payload.username},
            )
            uow.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )

    principal = build_session_principal(user)
    request.session[session_user_key()] = principal.to_session_payload()
    with get_unit_of_work() as uow:
        uow.audit_logs.append_log(
            actor_id=principal.user_id,
            action_kind="auth.login",
            resource_kind="session",
            resource_id=principal.user_id,
            summary=f"User '{principal.username}' logged in.",
            payload={"role": principal.role},
        )
        uow.commit()
    return AuthResponse(user=_user_response(user))


@router.post("/logout", response_model=LogoutResponse)
def logout(request: Request) -> LogoutResponse:
    """Clear the signed session cookie."""
    user = current_user(request)
    session_payload = request.session.pop(session_user_key(), None)
    with get_unit_of_work() as uow:
        uow.audit_logs.append_log(
            actor_id=user.id,
            action_kind="auth.logout",
            resource_kind="session",
            resource_id=user.id or "",
            summary=f"User '{user.username}' logged out.",
            payload={"cleared_session": isinstance(session_payload, dict)},
        )
        uow.commit()
    return LogoutResponse(message="Logged out")


@router.get("/me", response_model=AuthResponse)
def me(request: Request) -> AuthResponse:
    """Return the currently authenticated user."""
    user = current_user(request)
    return AuthResponse(user=_user_response(user))
