from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Body, Depends, Request
from fastapi.responses import JSONResponse

from src.app.domain.session import (
    ActiveDatasetContext,
    AppSession,
    WorkspaceMembership,
    WorkspaceSwitchResult,
)
from src.app.domain.workspace_collaboration import (
    CollaborationUserSummary,
    WorkspaceInvitation,
    WorkspaceInvitationAcceptance,
    WorkspaceMemberRow,
    WorkspaceMembershipListView,
)
from src.app.infrastructure.request_debug import current_debug_ref
from src.app.infrastructure.runtime import (
    get_session_service,
    get_workspace_collaboration_service,
)
from src.app.infrastructure.session_jwt_transport import (
    DEFAULT_SESSION_TOKEN_LIFETIME_SECONDS,
    REFRESH_COOKIE_NAME,
    SESSION_COOKIE_NAME,
)
from src.app.services.service_errors import ServiceError, service_error
from src.app.services.session_service import SessionService
from src.app.services.workspace_collaboration_service import WorkspaceCollaborationService
from src.app.settings import get_settings

router = APIRouter(prefix="/session", tags=["session"])
PENDING_INVITATION_CONTINUATION_COOKIE_NAME = "sc_pending_invitation"


@router.get("")
def get_session(
    request: Request,
    session_service: Annotated[SessionService, Depends(get_session_service)],
) -> JSONResponse:
    try:
        session = session_service.get_session(_session_token_from_request(request))
    except ServiceError as exc:
        return _service_error_response(exc)
    return _success_response(
        data=_serialize_session(session),
        meta={"generated_at": _generated_at(), "memberships_count": len(session.memberships)},
    )


@router.post("/login")
def login(
    payload: Annotated[object, Body(...)],
    session_service: Annotated[SessionService, Depends(get_session_service)],
) -> JSONResponse:
    try:
        email, password = _parse_login_payload(payload)
        result = session_service.login(email=email, password=password)
    except ServiceError as exc:
        return _service_error_response(exc)

    response = _success_response(
        data=_serialize_session(result.session),
        meta={
            "generated_at": _generated_at(),
            "memberships_count": len(result.session.memberships),
        },
    )
    _set_session_cookies(response, result.access_token, result.refresh_token)
    return response


@router.post("/logout")
def logout(
    request: Request,
    session_service: Annotated[SessionService, Depends(get_session_service)],
) -> JSONResponse:
    session = session_service.logout(_session_token_from_request(request))
    response = _success_response(
        data=_serialize_session(session),
        meta={"generated_at": _generated_at(), "memberships_count": len(session.memberships)},
    )
    response.delete_cookie(SESSION_COOKIE_NAME, path="/")
    response.delete_cookie(REFRESH_COOKIE_NAME, path="/")
    return response


@router.post("/refresh")
def refresh_session(
    request: Request,
    session_service: Annotated[SessionService, Depends(get_session_service)],
) -> JSONResponse:
    try:
        result = session_service.refresh(_refresh_token_from_request(request))
    except ServiceError as exc:
        return _service_error_response(exc)
    response = _success_response(
        data=_serialize_session(result.session),
        meta={
            "generated_at": _generated_at(),
            "memberships_count": len(result.session.memberships),
        },
    )
    _set_session_cookies(response, result.access_token, result.refresh_token)
    return response


@router.patch("/active-workspace")
def switch_active_workspace(
    request: Request,
    payload: Annotated[object, Body(...)],
    session_service: Annotated[SessionService, Depends(get_session_service)],
) -> JSONResponse:
    try:
        workspace_id = _parse_workspace_switch_payload(payload)
        result = session_service.switch_active_workspace(
            _session_token_from_request(request),
            workspace_id,
        )
    except ServiceError as exc:
        return _service_error_response(exc)
    return _success_response(
        data=_serialize_workspace_switch_result(result),
        meta={
            "generated_at": _generated_at(),
            "memberships_count": len(result.session.memberships),
        },
    )


@router.patch("/active-dataset")
def update_active_dataset(
    request: Request,
    payload: Annotated[object, Body(...)],
    session_service: Annotated[SessionService, Depends(get_session_service)],
) -> JSONResponse:
    try:
        dataset_id = _parse_dataset_activation_payload(payload)
        session = session_service.set_active_dataset(
            _session_token_from_request(request),
            dataset_id,
        )
    except ServiceError as exc:
        return _service_error_response(exc)
    return _success_response(
        data=_serialize_session(session),
        meta={"generated_at": _generated_at(), "memberships_count": len(session.memberships)},
    )


@router.get("/workspace-invitations")
def list_workspace_invitations(
    request: Request,
    collaboration_service: Annotated[
        WorkspaceCollaborationService,
        Depends(get_workspace_collaboration_service),
    ],
    workspace_id: str | None = None,
) -> JSONResponse:
    try:
        view = collaboration_service.list_invitations(
            _session_token_from_request(request),
            workspace_id=workspace_id,
        )
    except ServiceError as exc:
        return _service_error_response(exc)
    return _success_response(
        data={"rows": [_serialize_workspace_invitation(row) for row in view.rows]},
        meta={"generated_at": _generated_at(), "total_count": view.total_count},
    )


@router.post("/workspace-invitations")
def create_workspace_invitation(
    request: Request,
    payload: Annotated[object, Body(...)],
    collaboration_service: Annotated[
        WorkspaceCollaborationService,
        Depends(get_workspace_collaboration_service),
    ],
) -> JSONResponse:
    try:
        workspace_id, email, role = _parse_workspace_invitation_payload(payload)
        invitation = collaboration_service.create_invitation(
            _session_token_from_request(request),
            workspace_id=workspace_id,
            email=email,
            role=role,
        )
    except ServiceError as exc:
        return _service_error_response(exc)
    return _success_response(
        data={"operation": "created", "invitation": _serialize_workspace_invitation(invitation)},
        status_code=201,
        meta={"generated_at": _generated_at()},
    )


@router.get("/workspace-invitations/{invite_id}")
def get_workspace_invitation(
    invite_id: str,
    request: Request,
    collaboration_service: Annotated[
        WorkspaceCollaborationService,
        Depends(get_workspace_collaboration_service),
    ],
) -> JSONResponse:
    try:
        invitation = collaboration_service.get_invitation_detail(
            _session_token_from_request(request),
            invite_id,
        )
    except ServiceError as exc:
        return _service_error_response(exc)
    return _success_response(
        data=_serialize_workspace_invitation(invitation),
        meta={"generated_at": _generated_at()},
    )


@router.post("/workspace-invitations/{invite_id}/revoke")
def revoke_workspace_invitation(
    invite_id: str,
    request: Request,
    collaboration_service: Annotated[
        WorkspaceCollaborationService,
        Depends(get_workspace_collaboration_service),
    ],
) -> JSONResponse:
    try:
        invitation = collaboration_service.revoke_invitation(
            _session_token_from_request(request),
            invite_id,
        )
    except ServiceError as exc:
        return _service_error_response(exc)
    return _success_response(
        data={"operation": "revoked", "invitation": _serialize_workspace_invitation(invitation)},
        meta={"generated_at": _generated_at()},
    )


@router.post("/workspace-invitations/accept")
def accept_workspace_invitation(
    request: Request,
    collaboration_service: Annotated[
        WorkspaceCollaborationService,
        Depends(get_workspace_collaboration_service),
    ],
    payload: Annotated[object | None, Body()] = None,
) -> JSONResponse:
    try:
        invite_token = _parse_invite_accept_payload(payload)
        result, continuation_token = collaboration_service.accept_invitation(
            _session_token_from_request(request),
            invite_token=invite_token,
            continuation_token=_pending_invitation_continuation_from_request(request),
        )
    except ServiceError as exc:
        return _service_error_response(exc)
    response = _success_response(
        data=_serialize_workspace_invitation_acceptance(result),
        meta={"generated_at": _generated_at()},
    )
    if result.requires_authentication and continuation_token is not None:
        response.set_cookie(
            key=PENDING_INVITATION_CONTINUATION_COOKIE_NAME,
            value=continuation_token,
            httponly=True,
            samesite="lax",
            secure=get_settings().environment not in {"development", "test"},
            path="/",
        )
    else:
        response.delete_cookie(PENDING_INVITATION_CONTINUATION_COOKIE_NAME, path="/")
    return response


@router.get("/workspace-memberships")
def list_workspace_memberships(
    request: Request,
    collaboration_service: Annotated[
        WorkspaceCollaborationService,
        Depends(get_workspace_collaboration_service),
    ],
    workspace_id: str | None = None,
) -> JSONResponse:
    try:
        view = collaboration_service.list_memberships(
            _session_token_from_request(request),
            workspace_id=workspace_id,
        )
    except ServiceError as exc:
        return _service_error_response(exc)
    return _success_response(
        data=_serialize_workspace_membership_view(view),
        meta={"generated_at": _generated_at()},
    )


@router.post("/workspace-memberships/leave")
def leave_workspace(
    request: Request,
    collaboration_service: Annotated[
        WorkspaceCollaborationService,
        Depends(get_workspace_collaboration_service),
    ],
    payload: Annotated[object | None, Body()] = None,
) -> JSONResponse:
    try:
        workspace_id = _optional_workspace_id(payload)
        view = collaboration_service.leave_workspace(
            _session_token_from_request(request),
            workspace_id=workspace_id,
        )
    except ServiceError as exc:
        return _service_error_response(exc)
    return _success_response(
        data={"operation": "left", **_serialize_workspace_membership_view(view)},
        meta={"generated_at": _generated_at()},
    )


@router.post("/workspace-memberships/{user_id}/remove")
def remove_workspace_member(
    user_id: str,
    request: Request,
    collaboration_service: Annotated[
        WorkspaceCollaborationService,
        Depends(get_workspace_collaboration_service),
    ],
    payload: Annotated[object | None, Body()] = None,
) -> JSONResponse:
    try:
        workspace_id = _optional_workspace_id(payload)
        view = collaboration_service.remove_member(
            _session_token_from_request(request),
            workspace_id=workspace_id,
            user_id=user_id,
        )
    except ServiceError as exc:
        return _service_error_response(exc)
    return _success_response(
        data={"operation": "removed", **_serialize_workspace_membership_view(view)},
        meta={"generated_at": _generated_at()},
    )


@router.post("/workspace-memberships/transfer-ownership")
def transfer_workspace_ownership(
    request: Request,
    payload: Annotated[object, Body(...)],
    collaboration_service: Annotated[
        WorkspaceCollaborationService,
        Depends(get_workspace_collaboration_service),
    ],
) -> JSONResponse:
    try:
        workspace_id, new_owner_user_id = _parse_transfer_ownership_payload(payload)
        view = collaboration_service.transfer_ownership(
            _session_token_from_request(request),
            workspace_id=workspace_id,
            new_owner_user_id=new_owner_user_id,
        )
    except ServiceError as exc:
        return _service_error_response(exc)
    return _success_response(
        data={"operation": "ownership_transferred", **_serialize_workspace_membership_view(view)},
        meta={"generated_at": _generated_at()},
    )


def _parse_login_payload(payload: object) -> tuple[str, str]:
    body = _as_mapping(payload)
    email = body.get("email")
    password = body.get("password")
    if not isinstance(email, str) or len(email.strip()) == 0:
        raise service_error(
            400,
            code="request_validation_failed",
            category="validation_error",
            message="email must be a non-empty string.",
        )
    if not isinstance(password, str) or len(password) == 0:
        raise service_error(
            400,
            code="request_validation_failed",
            category="validation_error",
            message="password must be a non-empty string.",
        )
    return email.strip(), password


def _parse_workspace_switch_payload(payload: object) -> str:
    body = _as_mapping(payload)
    workspace_id = body.get("workspace_id")
    if not isinstance(workspace_id, str) or len(workspace_id.strip()) == 0:
        raise service_error(
            400,
            code="request_validation_failed",
            category="validation_error",
            message="workspace_id must be a non-empty string.",
        )
    return workspace_id.strip()


def _parse_dataset_activation_payload(payload: object) -> str | None:
    body = _as_mapping(payload)
    if "dataset_id" not in body:
        raise service_error(
            400,
            code="request_validation_failed",
            category="validation_error",
            message="dataset_id must be provided.",
        )
    dataset_id = body.get("dataset_id")
    if dataset_id is None:
        return None
    if not isinstance(dataset_id, str) or len(dataset_id.strip()) == 0:
        raise service_error(
            400,
            code="request_validation_failed",
            category="validation_error",
            message="dataset_id must be a non-empty string or null.",
        )
    return dataset_id.strip()


def _parse_workspace_invitation_payload(payload: object) -> tuple[str | None, str, str]:
    body = _as_mapping(payload)
    workspace_id = _optional_string(body.get("workspace_id"), field_name="workspace_id")
    email = body.get("email")
    role = body.get("role")
    if not isinstance(email, str) or len(email.strip()) == 0:
        raise service_error(
            400,
            code="request_validation_failed",
            category="validation_error",
            message="email must be a non-empty string.",
        )
    if role not in {"member", "viewer"}:
        raise service_error(
            400,
            code="request_validation_failed",
            category="validation_error",
            message="role must be member or viewer.",
        )
    return workspace_id, email.strip().lower(), role


def _parse_invite_accept_payload(payload: object) -> str | None:
    if payload is None:
        return None
    body = _as_mapping(payload)
    invite_token = body.get("invite_token")
    if invite_token is None:
        return None
    if not isinstance(invite_token, str) or len(invite_token.strip()) == 0:
        raise service_error(
            400,
            code="request_validation_failed",
            category="validation_error",
            message="invite_token must be a non-empty string.",
        )
    return invite_token.strip()


def _parse_transfer_ownership_payload(payload: object) -> tuple[str | None, str]:
    body = _as_mapping(payload)
    workspace_id = _optional_string(body.get("workspace_id"), field_name="workspace_id")
    new_owner_user_id = body.get("new_owner_user_id")
    if not isinstance(new_owner_user_id, str) or len(new_owner_user_id.strip()) == 0:
        raise service_error(
            400,
            code="request_validation_failed",
            category="validation_error",
            message="new_owner_user_id must be a non-empty string.",
        )
    return workspace_id, new_owner_user_id.strip()


def _optional_workspace_id(payload: object | None) -> str | None:
    if payload is None:
        return None
    body = _as_mapping(payload)
    return _optional_string(body.get("workspace_id"), field_name="workspace_id")


def _optional_string(value: object, *, field_name: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or len(value.strip()) == 0:
        raise service_error(
            400,
            code="request_validation_failed",
            category="validation_error",
            message=f"{field_name} must be a non-empty string or null.",
        )
    return value.strip()


def _serialize_workspace_switch_result(result: WorkspaceSwitchResult) -> dict[str, object]:
    payload = _serialize_session(result.session)
    payload["active_dataset_resolution"] = result.active_dataset_resolution
    payload["detached_task_ids"] = list(result.detached_task_ids)
    return payload


def _serialize_session(session: AppSession) -> dict[str, object]:
    return {
        "session_id": session.session_id,
        "auth": {
            "state": session.auth.state,
            "mode": session.auth.mode,
            "reason": session.auth.reason,
        },
        "user": (
            {
                "id": session.user.user_id,
                "display_name": session.user.display_name,
                "email": session.user.email,
                "platform_role": session.user.platform_role,
            }
            if session.user is not None
            else None
        ),
        "workspace": {
            "id": session.workspace.workspace_id,
            "slug": session.workspace.slug,
            "name": session.workspace.display_name,
            "role": session.workspace.role,
            "default_task_scope": session.workspace.default_task_scope,
            "allowed_actions": {
                "switch_to": session.workspace.allowed_actions.switch_to,
                "activate_dataset": session.workspace.allowed_actions.activate_dataset,
                "invite_members": session.workspace.allowed_actions.invite_members,
                "remove_members": session.workspace.allowed_actions.remove_members,
                "transfer_owner": session.workspace.allowed_actions.transfer_owner,
                "leave_workspace": session.workspace.allowed_actions.leave_workspace,
                "view_audit_logs": session.workspace.allowed_actions.view_audit_logs,
                "manage_definitions": session.workspace.allowed_actions.manage_definitions,
                "manage_datasets": session.workspace.allowed_actions.manage_datasets,
                "manage_tasks": session.workspace.allowed_actions.manage_tasks,
            },
            "memberships": [_serialize_membership(item) for item in session.memberships],
        },
        "active_dataset": _serialize_active_dataset(session.active_dataset),
        "capabilities": {
            "can_switch_workspace": session.capabilities.can_switch_workspace,
            "can_switch_dataset": session.capabilities.can_switch_dataset,
            "can_invite_members": session.capabilities.can_invite_members,
            "can_remove_members": session.capabilities.can_remove_members,
            "can_transfer_workspace_owner": session.capabilities.can_transfer_workspace_owner,
            "can_leave_workspace": session.capabilities.can_leave_workspace,
            "can_submit_tasks": session.capabilities.can_submit_tasks,
            "can_manage_workspace_tasks": session.capabilities.can_manage_workspace_tasks,
            "can_cancel_own_tasks": session.capabilities.can_cancel_own_tasks,
            "can_cancel_workspace_tasks": session.capabilities.can_cancel_workspace_tasks,
            "can_terminate_workspace_tasks": session.capabilities.can_terminate_workspace_tasks,
            "can_retry_own_tasks": session.capabilities.can_retry_own_tasks,
            "can_retry_workspace_tasks": session.capabilities.can_retry_workspace_tasks,
            "can_manage_definitions": session.capabilities.can_manage_definitions,
            "can_manage_datasets": session.capabilities.can_manage_datasets,
            "can_view_audit_logs": session.capabilities.can_view_audit_logs,
        },
    }


def _serialize_membership(membership: WorkspaceMembership) -> dict[str, object]:
    return {
        "id": membership.workspace_id,
        "slug": membership.slug,
        "name": membership.display_name,
        "role": membership.role,
        "default_task_scope": membership.default_task_scope,
        "is_active": membership.is_active,
        "allowed_actions": {
            "switch_to": membership.allowed_actions.switch_to,
            "activate_dataset": membership.allowed_actions.activate_dataset,
            "invite_members": membership.allowed_actions.invite_members,
            "remove_members": membership.allowed_actions.remove_members,
            "transfer_owner": membership.allowed_actions.transfer_owner,
            "leave_workspace": membership.allowed_actions.leave_workspace,
            "view_audit_logs": membership.allowed_actions.view_audit_logs,
            "manage_definitions": membership.allowed_actions.manage_definitions,
            "manage_datasets": membership.allowed_actions.manage_datasets,
            "manage_tasks": membership.allowed_actions.manage_tasks,
        },
    }


def _serialize_workspace_invitation(invitation: WorkspaceInvitation) -> dict[str, object]:
    return {
        "invite_id": invitation.invite_id,
        "invite_token": invitation.invite_token,
        "workspace_id": invitation.workspace_id,
        "workspace_name": invitation.workspace_name,
        "email": invitation.email,
        "role": invitation.role,
        "state": invitation.state,
        "expires_at": invitation.expires_at,
        "created_at": invitation.created_at,
        "delivery_state": invitation.delivery.status,
        "delivery": {
            "status": invitation.delivery.status,
            "channel": invitation.delivery.channel,
            "invite_url": invitation.delivery.invite_url,
            "failure_reason": invitation.delivery.failure_reason,
        },
        "inviter": _serialize_user_summary(invitation.inviter),
        "allowed_actions": {
            "revoke": invitation.allowed_actions.revoke,
            "accept": invitation.allowed_actions.accept,
            "copy_link": invitation.allowed_actions.copy_link,
        },
        "created_by_user_id": invitation.created_by_user_id,
        "delivery_error": invitation.delivery_error,
    }


def _serialize_workspace_invitation_acceptance(
    result: WorkspaceInvitationAcceptance,
) -> dict[str, object]:
    return {
        "invitation": _serialize_workspace_invitation(result.invitation),
        "memberships": [_serialize_membership(item) for item in result.memberships],
        "switch_available": result.switch_available,
        "post_accept_context": result.post_accept_context,
        "recommended_next_action": result.post_accept_context,
        "requires_authentication": result.requires_authentication,
        "continuation_saved": result.continuation_saved,
    }


def _serialize_workspace_membership_view(
    view: WorkspaceMembershipListView,
) -> dict[str, object]:
    return {
        "workspace_id": view.workspace_id,
        "workspace_name": view.workspace_name,
        "memberships": [_serialize_workspace_member_row(item) for item in view.memberships],
    }


def _serialize_workspace_member_row(row: WorkspaceMemberRow) -> dict[str, object]:
    return {
        "user_id": row.user.user_id,
        "display_name": row.user.display_name,
        "email": row.user.email,
        "platform_role": row.user.platform_role,
        "workspace_role": row.workspace_role,
        "is_current_user": row.is_current_user,
        "user": _serialize_user_summary(row.user),
        "allowed_actions": {
            "remove": row.allowed_actions.remove,
            "transfer_owner": row.allowed_actions.transfer_owner,
            "leave": row.allowed_actions.leave,
        },
    }


def _serialize_user_summary(
    user: CollaborationUserSummary | None,
) -> dict[str, object] | None:
    if user is None:
        return None
    return {
        "user_id": user.user_id,
        "display_name": user.display_name,
        "email": user.email,
        "platform_role": user.platform_role,
    }


def _serialize_active_dataset(
    active_dataset: ActiveDatasetContext | None,
) -> dict[str, object] | None:
    if active_dataset is None:
        return None
    return {
        "id": active_dataset.dataset_id,
        "name": active_dataset.name,
        "family": active_dataset.family,
        "status": active_dataset.status,
        "owner_user_id": active_dataset.owner_user_id,
        "owner_display_name": active_dataset.owner_display_name,
        "workspace_id": active_dataset.workspace_id,
        "visibility_scope": active_dataset.visibility_scope,
        "lifecycle_state": active_dataset.lifecycle_state,
    }


def _success_response(
    *,
    data: dict[str, object],
    status_code: int = 200,
    meta: dict[str, object] | None = None,
) -> JSONResponse:
    content: dict[str, object] = {"ok": True, "data": data}
    if meta is not None:
        content["meta"] = meta
    return JSONResponse(status_code=status_code, content=content)


def _service_error_response(exc: ServiceError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "ok": False,
            "error": {
                "code": exc.code,
                "category": exc.category,
                "message": exc.message,
                "retryable": exc.category == "internal_error",
                "debug_ref": current_debug_ref(),
            },
        },
    )


def _generated_at() -> str:
    return datetime.now(UTC).isoformat()


def _as_mapping(payload: object) -> dict[str, object]:
    if not isinstance(payload, dict):
        raise service_error(
            400,
            code="request_validation_failed",
            category="validation_error",
            message="Request body must be an object.",
        )
    return payload


def _session_token_from_request(request: Request) -> str | None:
    token = request.cookies.get(SESSION_COOKIE_NAME)
    if token is None or len(token.strip()) == 0:
        return None
    return token


def _refresh_token_from_request(request: Request) -> str | None:
    token = request.cookies.get(REFRESH_COOKIE_NAME)
    if token is None or len(token.strip()) == 0:
        return None
    return token


def _pending_invitation_continuation_from_request(request: Request) -> str | None:
    token = request.cookies.get(PENDING_INVITATION_CONTINUATION_COOKIE_NAME)
    if token is None or len(token.strip()) == 0:
        return None
    return token


def _set_session_cookies(
    response: JSONResponse,
    access_token: str,
    refresh_token: str,
) -> None:
    settings = get_settings()
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=access_token,
        httponly=True,
        samesite="lax",
        secure=settings.environment not in {"development", "test"},
        max_age=DEFAULT_SESSION_TOKEN_LIFETIME_SECONDS,
        path="/",
    )
    response.set_cookie(
        key=REFRESH_COOKIE_NAME,
        value=refresh_token,
        httponly=True,
        samesite="lax",
        secure=settings.environment not in {"development", "test"},
        max_age=60 * 60 * 24 * 14,
        path="/",
    )
