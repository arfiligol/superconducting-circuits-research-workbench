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
DeliveryStatus = Literal["queued_for_delivery", "sent", "delivery_failed", "manual_link"]
DeliveryChannel = Literal["smtp", "manual_link"]
PostAcceptSuggestion = Literal["switch_available", "stay_current", "sign_in_to_accept"]


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
    memberships: tuple[WorkspaceMembership, ...]
