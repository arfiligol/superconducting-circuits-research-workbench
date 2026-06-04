from __future__ import annotations

from typing import Protocol

from app_backend.domain.audit import AuditRecord
from app_backend.domain.workspace_collaboration import WorkspaceInvitation, WorkspaceMemberRecord


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

    def update_workspace_invitation_delivery(
        self,
        *,
        invite_id: str,
        state: str,
        delivery_status: str,
        delivery_channel: str,
        invite_url: str | None,
        delivery_error: str | None,
    ) -> WorkspaceInvitation | None: ...

    def get_workspace_invitation(self, invite_id: str) -> WorkspaceInvitation | None: ...

    def get_workspace_invitation_by_token(
        self, invite_token: str
    ) -> WorkspaceInvitation | None: ...

    def revoke_workspace_invitation(self, invite_id: str) -> WorkspaceInvitation | None: ...

    def accept_workspace_invitation(
        self,
        *,
        invite_token: str,
        user_email: str,
    ) -> WorkspaceInvitation | None: ...

    def create_pending_invitation_acceptance(self, invite_token: str) -> str: ...

    def consume_pending_invitation_acceptance(self, continuation_token: str) -> str | None: ...

    def list_workspace_memberships(
        self,
        workspace_id: str,
    ) -> tuple[WorkspaceMemberRecord, ...]: ...

    def remove_workspace_member(self, workspace_id: str, user_id: str) -> bool: ...

    def transfer_workspace_owner(
        self,
        workspace_id: str,
        new_owner_user_id: str,
        current_owner_user_id: str,
    ) -> bool: ...


class CollaborationAuditRepository(Protocol):
    def append(self, record: AuditRecord) -> None: ...
