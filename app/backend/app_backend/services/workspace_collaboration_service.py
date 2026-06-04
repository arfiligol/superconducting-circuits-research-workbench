from __future__ import annotations

from app_backend.services.workspace_invitation_service import WorkspaceInvitationService
from app_backend.services.workspace_membership_service import WorkspaceMembershipService


class WorkspaceCollaborationService:
    def __init__(
        self,
        invitation_service: WorkspaceInvitationService,
        membership_service: WorkspaceMembershipService,
    ) -> None:
        self._invitation_service = invitation_service
        self._membership_service = membership_service

    def list_invitations(
        self,
        session_token: str | None,
        workspace_id: str | None = None,
    ):
        return self._invitation_service.list_invitations(session_token, workspace_id)

    def create_invitation(
        self,
        session_token: str | None,
        *,
        workspace_id: str | None,
        email: str,
        role: str,
    ):
        return self._invitation_service.create_invitation(
            session_token,
            workspace_id=workspace_id,
            email=email,
            role=role,
        )

    def get_invitation_detail(
        self,
        session_token: str | None,
        invite_id: str,
    ):
        return self._invitation_service.get_invitation_detail(session_token, invite_id)

    def revoke_invitation(
        self,
        session_token: str | None,
        invite_id: str,
    ):
        return self._invitation_service.revoke_invitation(session_token, invite_id)

    def accept_invitation(
        self,
        session_token: str | None,
        *,
        invite_token: str | None = None,
        continuation_token: str | None = None,
    ):
        return self._invitation_service.accept_invitation(
            session_token,
            invite_token=invite_token,
            continuation_token=continuation_token,
        )

    def list_memberships(
        self,
        session_token: str | None,
        workspace_id: str | None = None,
    ):
        return self._membership_service.list_memberships(session_token, workspace_id)

    def leave_workspace(
        self,
        session_token: str | None,
        workspace_id: str | None = None,
    ):
        return self._membership_service.leave_workspace(session_token, workspace_id)

    def remove_member(
        self,
        session_token: str | None,
        *,
        workspace_id: str | None,
        user_id: str,
    ):
        return self._membership_service.remove_member(
            session_token,
            workspace_id=workspace_id,
            user_id=user_id,
        )

    def transfer_ownership(
        self,
        session_token: str | None,
        *,
        workspace_id: str | None,
        new_owner_user_id: str,
    ):
        return self._membership_service.transfer_ownership(
            session_token,
            workspace_id=workspace_id,
            new_owner_user_id=new_owner_user_id,
        )
