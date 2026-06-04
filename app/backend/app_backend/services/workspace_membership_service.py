from __future__ import annotations

import logging

from app_backend.domain.audit import AuditOutcome
from app_backend.domain.authorization import AuthorizationResourceEnvelope
from app_backend.domain.session import SessionState
from app_backend.domain.workspace_collaboration import (
    WorkspaceMemberAllowedActions,
    WorkspaceMemberRecord,
    WorkspaceMemberRow,
    WorkspaceMembershipListView,
)
from app_backend.infrastructure.audit_records import build_audit_record
from app_backend.services.authorization_service import AuthorizationService
from app_backend.services.service_errors import service_error
from app_backend.services.session_service import SessionService
from app_backend.services.workspace_collaboration_contracts import (
    CollaborationAuditRepository,
    CollaborationRepository,
)

logger = logging.getLogger(__name__)


class WorkspaceMembershipService:
    def __init__(
        self,
        repository: CollaborationRepository,
        session_service: SessionService,
        authorization_service: AuthorizationService,
        audit_repository: CollaborationAuditRepository | None = None,
    ) -> None:
        self._repository = repository
        self._session_service = session_service
        self._authorization_service = authorization_service
        self._audit_repository = audit_repository

    def list_memberships(
        self,
        session_token: str | None,
        workspace_id: str | None = None,
    ) -> WorkspaceMembershipListView:
        state = self._session_service.require_authenticated_session_state(session_token)
        resolved_workspace_id = workspace_id or state.workspace_id
        self._require_workspace_membership(state, resolved_workspace_id)
        memberships = self._repository.list_workspace_memberships(resolved_workspace_id)
        workspace_name = next(
            (
                membership.display_name
                for membership in state.memberships
                if membership.workspace_id == resolved_workspace_id
            ),
            resolved_workspace_id,
        )
        return WorkspaceMembershipListView(
            workspace_id=resolved_workspace_id,
            workspace_name=workspace_name,
            memberships=self._materialize_member_rows(
                memberships,
                state=state,
                workspace_id=resolved_workspace_id,
            ),
        )

    def leave_workspace(
        self,
        session_token: str | None,
        workspace_id: str | None = None,
    ) -> WorkspaceMembershipListView:
        state = self._session_service.require_authenticated_session_state(session_token)
        resolved_workspace_id = workspace_id or state.workspace_id
        active_membership = next(
            (
                membership
                for membership in state.memberships
                if membership.workspace_id == resolved_workspace_id
            ),
            None,
        )
        if active_membership is None:
            raise service_error(
                403,
                code="workspace_membership_required",
                category="permission_denied",
                message="The current session does not belong to the selected workspace.",
            )
        self._authorization_service.authorize(
            state,
            "leave_workspace",
            resource=workspace_resource(resolved_workspace_id),
            denied_code="workspace_leave_denied",
            denied_message="The current session cannot leave this workspace.",
        )
        if active_membership.role == "owner":
            raise service_error(
                409,
                code="workspace_owner_leave_blocked",
                category="conflict",
                message="Transfer workspace ownership before leaving the workspace.",
            )
        removed = self._repository.remove_workspace_member(
            resolved_workspace_id,
            state.user.user_id if state.user is not None else "",
        )
        if not removed:
            raise service_error(
                404,
                code="workspace_membership_not_found",
                category="not_found",
                message="The workspace membership was not found.",
            )
        result = WorkspaceMembershipListView(
            workspace_id=resolved_workspace_id,
            workspace_name=active_membership.display_name,
            memberships=self._materialize_member_rows(
                self._repository.list_workspace_memberships(resolved_workspace_id),
                state=state,
                workspace_id=resolved_workspace_id,
            ),
        )
        logger.info(
            "Workspace left workspace_id=%s user_id=%s",
            resolved_workspace_id,
            state.user.user_id if state.user is not None else "anonymous",
        )
        self._append_audit_record(
            state,
            action_kind="workspace.left",
            resource_kind="workspace_membership",
            resource_id=state.user.user_id if state.user is not None else "anonymous",
            outcome="completed",
            payload={"workspace_id": resolved_workspace_id},
            workspace_id=resolved_workspace_id,
        )
        return result

    def remove_member(
        self,
        session_token: str | None,
        *,
        workspace_id: str | None,
        user_id: str,
    ) -> WorkspaceMembershipListView:
        state = self._session_service.require_authenticated_session_state(session_token)
        resolved_workspace_id = workspace_id or state.workspace_id
        self._authorization_service.authorize(
            state,
            "remove_member",
            resource=membership_resource(resolved_workspace_id, user_id),
            denied_code="workspace_membership_remove_denied",
            denied_message="The current session cannot remove members from this workspace.",
        )
        if not self._repository.remove_workspace_member(resolved_workspace_id, user_id):
            raise service_error(
                404,
                code="workspace_membership_not_found",
                category="not_found",
                message="The workspace membership was not found.",
            )
        workspace_name = next(
            (
                membership.display_name
                for membership in state.memberships
                if membership.workspace_id == resolved_workspace_id
            ),
            resolved_workspace_id,
        )
        result = WorkspaceMembershipListView(
            workspace_id=resolved_workspace_id,
            workspace_name=workspace_name,
            memberships=self._materialize_member_rows(
                self._repository.list_workspace_memberships(resolved_workspace_id),
                state=state,
                workspace_id=resolved_workspace_id,
            ),
        )
        logger.info(
            "Workspace member removed workspace_id=%s user_id=%s",
            resolved_workspace_id,
            user_id,
        )
        self._append_audit_record(
            state,
            action_kind="workspace.member_removed",
            resource_kind="workspace_membership",
            resource_id=user_id,
            outcome="completed",
            payload={"workspace_id": resolved_workspace_id},
            workspace_id=resolved_workspace_id,
        )
        return result

    def transfer_ownership(
        self,
        session_token: str | None,
        *,
        workspace_id: str | None,
        new_owner_user_id: str,
    ) -> WorkspaceMembershipListView:
        state = self._session_service.require_authenticated_session_state(session_token)
        resolved_workspace_id = workspace_id or state.workspace_id
        self._authorization_service.authorize(
            state,
            "transfer_workspace_owner",
            resource=membership_resource(resolved_workspace_id, new_owner_user_id),
            denied_code="workspace_transfer_owner_denied",
            denied_message="The current session cannot transfer workspace ownership.",
        )
        if state.user is None:
            raise service_error(
                401,
                code="auth_required",
                category="auth_required",
                message="The current request requires an authenticated session.",
            )
        transferred = self._repository.transfer_workspace_owner(
            resolved_workspace_id,
            new_owner_user_id=new_owner_user_id,
            current_owner_user_id=state.user.user_id,
        )
        if not transferred:
            raise service_error(
                404,
                code="workspace_membership_not_found",
                category="not_found",
                message="The new workspace owner membership was not found.",
            )
        workspace_name = next(
            (
                membership.display_name
                for membership in state.memberships
                if membership.workspace_id == resolved_workspace_id
            ),
            resolved_workspace_id,
        )
        result = WorkspaceMembershipListView(
            workspace_id=resolved_workspace_id,
            workspace_name=workspace_name,
            memberships=self._materialize_member_rows(
                self._repository.list_workspace_memberships(resolved_workspace_id),
                state=state,
                workspace_id=resolved_workspace_id,
            ),
        )
        logger.info(
            "Workspace ownership transferred workspace_id=%s new_owner_user_id=%s",
            resolved_workspace_id,
            new_owner_user_id,
        )
        self._append_audit_record(
            state,
            action_kind="workspace.ownership_transferred",
            resource_kind="workspace_membership",
            resource_id=new_owner_user_id,
            outcome="completed",
            payload={"workspace_id": resolved_workspace_id},
            workspace_id=resolved_workspace_id,
        )
        return result

    def _materialize_member_rows(
        self,
        memberships: tuple[WorkspaceMemberRecord, ...],
        *,
        state: SessionState,
        workspace_id: str,
    ) -> tuple[WorkspaceMemberRow, ...]:
        rows: list[WorkspaceMemberRow] = []
        current_user_id = state.user.user_id if state.user is not None else None
        for membership in memberships:
            is_current_user = membership.user.user_id == current_user_id
            can_remove = (not is_current_user) and self._authorization_service.is_allowed(
                state,
                "remove_member",
                resource=membership_resource(workspace_id, membership.user.user_id),
            )
            can_transfer_owner = (
                not is_current_user
                and membership.workspace_role != "owner"
                and self._authorization_service.is_allowed(
                    state,
                    "transfer_workspace_owner",
                    resource=membership_resource(workspace_id, membership.user.user_id),
                )
            )
            can_leave = (
                is_current_user
                and membership.workspace_role != "owner"
                and self._authorization_service.is_allowed(
                    state,
                    "leave_workspace",
                    resource=workspace_resource(workspace_id),
                )
            )
            rows.append(
                WorkspaceMemberRow(
                    user=membership.user,
                    workspace_role=membership.workspace_role,
                    is_current_user=is_current_user,
                    allowed_actions=WorkspaceMemberAllowedActions(
                        remove=can_remove,
                        transfer_owner=can_transfer_owner,
                        leave=can_leave,
                    ),
                )
            )
        return tuple(rows)

    def _require_workspace_membership(
        self,
        state: SessionState,
        workspace_id: str,
    ) -> None:
        if any(membership.workspace_id == workspace_id for membership in state.memberships):
            return
        raise service_error(
            403,
            code="workspace_membership_required",
            category="permission_denied",
            message="The current session does not belong to the selected workspace.",
        )

    def _append_audit_record(
        self,
        state: SessionState | None,
        *,
        action_kind: str,
        resource_kind: str,
        resource_id: str,
        outcome: AuditOutcome,
        payload: dict[str, object],
        workspace_id: str | None = None,
    ) -> None:
        if self._audit_repository is None:
            return
        self._audit_repository.append(
            build_audit_record(
                state=state,
                action_kind=action_kind,
                resource_kind=resource_kind,
                resource_id=resource_id,
                outcome=outcome,
                payload=payload,
                workspace_id=workspace_id,
            )
        )


def workspace_resource(workspace_id: str) -> AuthorizationResourceEnvelope:
    return AuthorizationResourceEnvelope(
        resource_kind="workspace",
        workspace_id=workspace_id,
        owner_user_id=None,
        visibility_scope="workspace",
        lifecycle_state="active",
    )


def membership_resource(workspace_id: str, user_id: str) -> AuthorizationResourceEnvelope:
    return AuthorizationResourceEnvelope(
        resource_kind="workspace_membership",
        workspace_id=workspace_id,
        owner_user_id=user_id,
        visibility_scope="workspace",
        lifecycle_state="active",
    )
