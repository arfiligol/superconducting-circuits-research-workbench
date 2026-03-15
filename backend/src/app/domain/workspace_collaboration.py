from dataclasses import dataclass
from typing import Literal

from src.app.domain.session import WorkspaceMembership, WorkspaceRole

InvitationState = Literal[
    "pending",
    "delivered",
    "accepted",
    "revoked",
    "expired",
    "delivery_failed",
]
DeliveryState = Literal["manual_link_ready", "delivered", "delivery_failed"]
PostAcceptSuggestion = Literal["switch_available", "already_active"]


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
    delivery_state: DeliveryState
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


@dataclass(frozen=True)
class WorkspaceMembershipListView:
    workspace_id: str
    workspace_name: str
    memberships: tuple[WorkspaceMembership, ...]
