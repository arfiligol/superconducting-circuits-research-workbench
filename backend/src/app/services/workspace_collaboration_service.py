from __future__ import annotations

from datetime import datetime, timezone
from typing import Protocol

from src.app.domain.audit import AuditRecord
from src.app.domain.authorization import AuthorizationResourceEnvelope
from src.app.domain.session import WorkspaceMembership
from src.app.domain.workspace_collaboration import (
    WorkspaceInvitation,
    WorkspaceInvitationAcceptance,
    WorkspaceInvitationListView,
    WorkspaceMembershipListView,
)
from src.app.services.authorization_service import AuthorizationService
from src.app.services.service_errors import service_error
from src.app.services.session_service import SessionService


class CollaborationRepository(Protocol):
    def list_workspace_invitations(self, workspace_id: str) -> tuple[WorkspaceInvitation, ...]: ...

    def create_workspace_invitation(
        self,
        *,
        workspace_id: str,
        workspace_name: str,
        email: str,
        role: str,
        created_by_user_id: str,
    ) -> WorkspaceInvitation: ...

    def get_workspace_invitation(self, invite_id: str) -> WorkspaceInvitation | None: ...

    def get_workspace_invitation_by_token(self, invite_token: str) -> WorkspaceInvitation | None: ...

    def revoke_workspace_invitation(self, invite_id: str) -> WorkspaceInvitation | None: ...

    def accept_workspace_invitation(
        self,
        *,
        invite_token: str,
        user_email: str,
    ) -> WorkspaceInvitation | None: ...

    def list_workspace_memberships(self, workspace_id: str) -> tuple[WorkspaceMembership, ...]: ...

    def remove_workspace_member(self, workspace_id: str, user_id: str) -> bool: ...

    def transfer_workspace_owner(
        self,
        workspace_id: str,
        new_owner_user_id: str,
        current_owner_user_id: str,
    ) -> bool: ...


class CollaborationAuditRepository(Protocol):
    def append(self, record: AuditRecord) -> None: ...


class WorkspaceCollaborationService:
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

    def list_invitations(
        self,
        session_token: str | None,
        workspace_id: str | None = None,
    ) -> WorkspaceInvitationListView:
        state = self._session_service.require_authenticated_session_state(session_token)
        resolved_workspace_id = workspace_id or state.workspace_id
        self._authorization_service.authorize(
            state,
            "invite_member",
            resource=self._workspace_resource(resolved_workspace_id),
            denied_code="workspace_invitation_denied",
            denied_message="The current session cannot list invitations for this workspace.",
        )
        rows = self._repository.list_workspace_invitations(resolved_workspace_id)
        return WorkspaceInvitationListView(rows=rows, total_count=len(rows))

    def create_invitation(
        self,
        session_token: str | None,
        *,
        workspace_id: str | None,
        email: str,
        role: str,
    ) -> WorkspaceInvitation:
        state = self._session_service.require_authenticated_session_state(session_token)
        resolved_workspace_id = workspace_id or state.workspace_id
        self._authorization_service.authorize(
            state,
            "invite_member",
            resource=self._workspace_resource(resolved_workspace_id),
            denied_code="workspace_invitation_denied",
            denied_message="The current session cannot invite members to this workspace.",
        )
        membership = next(
            membership
            for membership in state.memberships
            if membership.workspace_id == resolved_workspace_id
        )
        invitation = self._repository.create_workspace_invitation(
            workspace_id=resolved_workspace_id,
            workspace_name=membership.display_name,
            email=email.strip().lower(),
            role=role,
            created_by_user_id=state.user.user_id if state.user is not None else "anonymous",
        )
        self._append_audit_record(
            state,
            action_kind="workspace.invite_created",
            resource_id=invitation.invite_id,
            outcome="accepted",
            payload={"email": invitation.email, "role": invitation.role, "workspace_id": invitation.workspace_id},
        )
        return invitation

    def get_invitation_detail(
        self,
        session_token: str | None,
        invite_id: str,
    ) -> WorkspaceInvitation:
        state = self._session_service.require_authenticated_session_state(session_token)
        invitation = self._repository.get_workspace_invitation(invite_id)
        if invitation is None:
            raise service_error(
                404,
                code="workspace_invitation_not_found",
                category="not_found",
                message="The requested workspace invitation was not found.",
            )
        self._authorization_service.authorize(
            state,
            "invite_member",
            resource=self._workspace_resource(invitation.workspace_id),
            denied_code="workspace_invitation_denied",
            denied_message="The current session cannot view this workspace invitation.",
        )
        return invitation

    def revoke_invitation(
        self,
        session_token: str | None,
        invite_id: str,
    ) -> WorkspaceInvitation:
        state = self._session_service.require_authenticated_session_state(session_token)
        invitation = self._repository.get_workspace_invitation(invite_id)
        if invitation is None:
            raise service_error(
                404,
                code="workspace_invitation_not_found",
                category="not_found",
                message="The requested workspace invitation was not found.",
            )
        self._authorization_service.authorize(
            state,
            "revoke_invite",
            resource=self._workspace_resource(invitation.workspace_id),
            denied_code="workspace_invitation_denied",
            denied_message="The current session cannot revoke this workspace invitation.",
        )
        revoked = self._repository.revoke_workspace_invitation(invite_id)
        if revoked is None:
            raise service_error(
                404,
                code="workspace_invitation_not_found",
                category="not_found",
                message="The requested workspace invitation was not found.",
            )
        self._append_audit_record(
            state,
            action_kind="workspace.invite_revoked",
            resource_id=revoked.invite_id,
            outcome="completed",
            payload={"workspace_id": revoked.workspace_id},
        )
        return revoked

    def accept_invitation(
        self,
        session_token: str | None,
        invite_token: str,
    ) -> WorkspaceInvitationAcceptance:
        state = self._session_service.require_authenticated_session_state(session_token)
        invitation = self._repository.get_workspace_invitation_by_token(invite_token)
        if invitation is None:
            raise service_error(
                404,
                code="workspace_invitation_not_found",
                category="not_found",
                message="The requested workspace invitation was not found.",
            )
        if invitation.state in {"revoked", "expired"}:
            raise service_error(
                409,
                code="workspace_invitation_unavailable",
                category="conflict",
                message="The workspace invitation is no longer available.",
            )
        if state.user is None or state.user.email is None:
            raise service_error(
                401,
                code="auth_required",
                category="auth_required",
                message="Accepting an invitation requires an authenticated session.",
            )
        if state.user.email.casefold() != invitation.email.casefold():
            raise service_error(
                409,
                code="workspace_invitation_account_mismatch",
                category="conflict",
                message="The current account does not match the invitation email.",
            )
        accepted = self._repository.accept_workspace_invitation(
            invite_token=invite_token,
            user_email=state.user.email.casefold(),
        )
        if accepted is None:
            raise service_error(
                404,
                code="workspace_invitation_not_found",
                category="not_found",
                message="The requested workspace invitation was not found.",
            )
        memberships = self._repository.list_workspace_memberships(accepted.workspace_id)
        switch_available = state.workspace_id != accepted.workspace_id
        result = WorkspaceInvitationAcceptance(
            invitation=accepted,
            memberships=memberships,
            switch_available=switch_available,
            post_accept_context="switch_available" if switch_available else "already_active",
        )
        self._append_audit_record(
            state,
            action_kind="workspace.invite_accepted",
            resource_id=accepted.invite_id,
            outcome="completed",
            payload={"workspace_id": accepted.workspace_id, "email": accepted.email},
        )
        return result

    def list_memberships(
        self,
        session_token: str | None,
        workspace_id: str | None = None,
    ) -> WorkspaceMembershipListView:
        state = self._session_service.require_authenticated_session_state(session_token)
        resolved_workspace_id = workspace_id or state.workspace_id
        memberships = self._repository.list_workspace_memberships(resolved_workspace_id)
        workspace_name = next(
            (membership.display_name for membership in state.memberships if membership.workspace_id == resolved_workspace_id),
            resolved_workspace_id,
        )
        return WorkspaceMembershipListView(
            workspace_id=resolved_workspace_id,
            workspace_name=workspace_name,
            memberships=memberships,
        )

    def leave_workspace(
        self,
        session_token: str | None,
        workspace_id: str | None = None,
    ) -> WorkspaceMembershipListView:
        state = self._session_service.require_authenticated_session_state(session_token)
        resolved_workspace_id = workspace_id or state.workspace_id
        active_membership = next(
            (membership for membership in state.memberships if membership.workspace_id == resolved_workspace_id),
            None,
        )
        if active_membership is None:
            raise service_error(
                403,
                code="workspace_membership_required",
                category="permission_denied",
                message="The current session does not belong to the selected workspace.",
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
            memberships=self._repository.list_workspace_memberships(resolved_workspace_id),
        )
        self._append_audit_record(
            state,
            action_kind="workspace.left",
            resource_id=state.user.user_id if state.user is not None else "anonymous",
            outcome="completed",
            payload={"workspace_id": resolved_workspace_id},
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
            resource=self._workspace_resource(resolved_workspace_id),
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
            (membership.display_name for membership in state.memberships if membership.workspace_id == resolved_workspace_id),
            resolved_workspace_id,
        )
        result = WorkspaceMembershipListView(
            workspace_id=resolved_workspace_id,
            workspace_name=workspace_name,
            memberships=self._repository.list_workspace_memberships(resolved_workspace_id),
        )
        self._append_audit_record(
            state,
            action_kind="workspace.member_removed",
            resource_id=user_id,
            outcome="completed",
            payload={"workspace_id": resolved_workspace_id},
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
            resource=self._workspace_resource(resolved_workspace_id),
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
            (membership.display_name for membership in state.memberships if membership.workspace_id == resolved_workspace_id),
            resolved_workspace_id,
        )
        result = WorkspaceMembershipListView(
            workspace_id=resolved_workspace_id,
            workspace_name=workspace_name,
            memberships=self._repository.list_workspace_memberships(resolved_workspace_id),
        )
        self._append_audit_record(
            state,
            action_kind="workspace.ownership_transferred",
            resource_id=new_owner_user_id,
            outcome="completed",
            payload={"workspace_id": resolved_workspace_id},
        )
        return result

    def _workspace_resource(self, workspace_id: str) -> AuthorizationResourceEnvelope:
        return AuthorizationResourceEnvelope(
            resource_kind="workspace",
            workspace_id=workspace_id,
            owner_user_id=None,
            visibility_scope="workspace",
            lifecycle_state="active",
        )

    def _append_audit_record(
        self,
        state,
        *,
        action_kind: str,
        resource_id: str,
        outcome: str,
        payload: dict[str, object],
    ) -> None:
        if self._audit_repository is None:
            return
        self._audit_repository.append(
            AuditRecord(
                audit_id=f"audit:{action_kind}:{resource_id}",
                occurred_at=datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
                actor_user_id=state.user.user_id if state.user is not None else "anonymous",
                actor_display_name=state.user.display_name if state.user is not None else "anonymous",
                session_id=state.session_id,
                correlation_id=f"corr:{action_kind}:{resource_id}",
                workspace_id=state.workspace_id,
                action_kind=action_kind,
                resource_kind="workspace",
                resource_id=resource_id,
                outcome=outcome,  # type: ignore[arg-type]
                payload=payload,
                debug_ref=f"debug:{action_kind}:{resource_id}",
            )
        )
