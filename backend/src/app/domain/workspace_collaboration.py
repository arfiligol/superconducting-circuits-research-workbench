from dataclasses import dataclass
from typing import Literal

from src.app.domain.session import PlatformRole, WorkspaceMembership, WorkspaceRole

InvitationState = Literal[
    "pending",
    "delivered",
    "accepted",
    "revoked",
    "expired",
    "delivery_failed",
]
DeliveryStatus = Literal["queued_for_delivery", "sent", "delivery_failed", "manual_link"]
DeliveryChannel = Literal["smtp", "manual_link"]
PostAcceptSuggestion = Literal["switch_available", "stay_current", "sign_in_to_accept"]


@dataclass(frozen=True)
class CollaborationUserSummary:
    user_id: str
    display_name: str
    email: str | None
    platform_role: PlatformRole | None


@dataclass(frozen=True)
class WorkspaceMemberAllowedActions:
    remove: bool
    transfer_owner: bool
    leave: bool


@dataclass(frozen=True)
class WorkspaceMemberRecord:
    user: CollaborationUserSummary
    workspace_role: WorkspaceRole


@dataclass(frozen=True)
class WorkspaceMemberRow:
    user: CollaborationUserSummary
    workspace_role: WorkspaceRole
    is_current_user: bool
    allowed_actions: WorkspaceMemberAllowedActions


@dataclass(frozen=True)
class WorkspaceInvitationAllowedActions:
    revoke: bool
    accept: bool
    copy_link: bool


@dataclass(frozen=True)
class WorkspaceInvitationDelivery:
    status: DeliveryStatus
    channel: DeliveryChannel
    invite_url: str | None
    failure_reason: str | None


@dataclass(frozen=True)
class WorkspaceInvitation:
    invite_id: str
    invite_token: str
    workspace_id: str
    workspace_name: str
    email: str
    role: WorkspaceRole
    state: InvitationState
    expires_at: str
    created_at: str
    delivery: WorkspaceInvitationDelivery
    inviter: CollaborationUserSummary | None
    allowed_actions: WorkspaceInvitationAllowedActions
    created_by_user_id: str
    delivery_error: str | None


@dataclass(frozen=True)
class WorkspaceInvitationListView:
    rows: tuple[WorkspaceInvitation, ...]
    total_count: int


@dataclass(frozen=True)
class WorkspaceInvitationAcceptance:
    invitation: WorkspaceInvitation
    memberships: tuple[WorkspaceMembership, ...]
    switch_available: bool
    post_accept_context: PostAcceptSuggestion
    requires_authentication: bool = False
    continuation_saved: bool = False


@dataclass(frozen=True)
class WorkspaceMembershipListView:
    workspace_id: str
    workspace_name: str
    memberships: tuple[WorkspaceMemberRow, ...]
