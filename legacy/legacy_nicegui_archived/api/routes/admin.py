"""`/api/v1/admin/*` routes for phase-1 local administration."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, status

from legacy.legacy_nicegui_archived.api.dependencies import admin_user
from legacy.legacy_nicegui_archived.api.routes.auth import _user_response
from legacy.legacy_nicegui_archived.api.schemas import (
    AuditLogResponse,
    AuditLogsListResponse,
    CreateUserRequest,
    PasswordResetRequest,
    UpdateUserRequest,
    UserResponse,
    UsersListResponse,
)
from legacy.legacy_nicegui_archived.services.auth_service import hash_password
from core.shared.persistence import get_unit_of_work

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/users", response_model=UsersListResponse)
def list_users(request: Request) -> UsersListResponse:
    """List local users for phase-1 admin management."""
    _actor = admin_user(request)
    with get_unit_of_work() as uow:
        return UsersListResponse(users=[_user_response(user) for user in uow.users.list_users()])


@router.post(
    "/users",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_user(payload: CreateUserRequest, request: Request) -> UserResponse:
    """Create one local phase-1 user."""
    actor = admin_user(request)
    with get_unit_of_work() as uow:
        if uow.users.get_by_username(payload.username) is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Username '{payload.username}' already exists",
            )
        created = uow.users.create_user(
            username=payload.username,
            password_hash=hash_password(payload.password),
            role=payload.role,
            is_active=payload.is_active,
        )
        uow.audit_logs.append_log(
            actor_id=actor.id,
            action_kind="admin.user_created",
            resource_kind="user",
            resource_id=created.id or payload.username,
            summary=f"Created user '{payload.username}'.",
            payload={"role": payload.role, "is_active": payload.is_active},
        )
        uow.commit()
        return _user_response(created)


@router.patch("/users/{user_id}", response_model=UserResponse)
def update_user(user_id: int, payload: UpdateUserRequest, request: Request) -> UserResponse:
    """Update one local user's role and/or active state."""
    actor = admin_user(request)
    with get_unit_of_work() as uow:
        user = uow.users.get_by_id(user_id)
        if user is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
        if payload.role is not None:
            user = uow.users.set_role(user_id, payload.role)
        if payload.is_active is not None:
            user = uow.users.set_active(user_id, payload.is_active)
        uow.audit_logs.append_log(
            actor_id=actor.id,
            action_kind="admin.user_updated",
            resource_kind="user",
            resource_id=user_id,
            summary=f"Updated user '{user.username}'.",
            payload=payload.model_dump(mode="json", exclude_none=True),
        )
        uow.commit()
        return _user_response(user)


@router.post("/users/{user_id}/password-reset", response_model=UserResponse)
def reset_password(
    user_id: int,
    payload: PasswordResetRequest,
    request: Request,
) -> UserResponse:
    """Replace one local user's password."""
    actor = admin_user(request)
    with get_unit_of_work() as uow:
        user = uow.users.get_by_id(user_id)
        if user is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
        updated = uow.users.set_password(user_id, hash_password(payload.new_password))
        uow.audit_logs.append_log(
            actor_id=actor.id,
            action_kind="admin.user_password_reset",
            resource_kind="user",
            resource_id=user_id,
            summary=f"Reset password for user '{updated.username}'.",
            payload={},
        )
        uow.commit()
        return _user_response(updated)


@router.get("/audit-logs", response_model=AuditLogsListResponse)
def list_audit_logs(
    request: Request,
    limit: int = 100,
) -> AuditLogsListResponse:
    """List audit logs newest first for admin inspection."""
    _actor = admin_user(request)
    with get_unit_of_work() as uow:
        logs = uow.audit_logs.list_logs()[: max(1, min(limit, 500))]
    return AuditLogsListResponse(
        logs=[
            AuditLogResponse(
                id=int(log.id or 0),
                actor_id=log.actor_id,
                action_kind=str(log.action_kind),
                resource_kind=str(log.resource_kind),
                resource_id=str(log.resource_id),
                summary=str(log.summary),
                payload=dict(log.payload),
                created_at=log.created_at,
            )
            for log in logs
        ]
    )
