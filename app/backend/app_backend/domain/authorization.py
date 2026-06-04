from dataclasses import dataclass
from typing import Literal

from app_backend.domain.datasets import DatasetLifecycleState, DatasetVisibilityScope
from app_backend.domain.session import PlatformRole, WorkspaceRole

AuthorizationAction = Literal[
    "switch_workspace",
    "switch_dataset",
    "switch_runtime_mode",
    "invite_member",
    "revoke_invite",
    "leave_workspace",
    "remove_member",
    "transfer_workspace_owner",
    "submit_task",
    "cancel_own_task",
    "cancel_workspace_task",
    "terminate_workspace_task",
    "retry_own_task",
    "retry_workspace_task",
    "manage_definition",
    "manage_dataset",
    "view_audit_log",
]
AuthorizationResourceKind = Literal[
    "workspace",
    "dataset",
    "definition",
    "task",
    "audit_log",
    "workspace_invitation",
    "workspace_membership",
]


@dataclass(frozen=True)
class AuthorizationSubject:
    user_id: str | None
    platform_role: PlatformRole | None
    workspace_role: WorkspaceRole | None
    workspace_id: str | None


@dataclass(frozen=True)
class AuthorizationResourceEnvelope:
    resource_kind: AuthorizationResourceKind
    workspace_id: str | None
    owner_user_id: str | None
    visibility_scope: DatasetVisibilityScope | Literal["workspace", "owned", "private"] | None
    lifecycle_state: DatasetLifecycleState | Literal["active", "archived", "deleted"] | None


@dataclass(frozen=True)
class AuthorizationDecision:
    allowed: bool
    action: AuthorizationAction
    reason: str | None = None
