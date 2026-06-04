from dataclasses import dataclass
from typing import Literal

from app_backend.domain.datasets import DatasetLifecycleState, DatasetStatus, DatasetVisibilityScope

RuntimeMode = Literal["local", "online"]
AuthState = Literal["authenticated", "anonymous", "degraded", "local_bypass"]
AuthMode = Literal["jwt_refresh_cookie", "local_bypass"]
AuthReason = Literal[
    "session_expired",
    "session_invalid",
    "refresh_expired",
    "refresh_invalid",
]
PlatformRole = Literal["admin", "user"]
WorkspaceRole = Literal["owner", "member", "viewer"]
TaskScope = Literal["local", "workspace", "owned"]
DatasetResolution = Literal["preserved", "rebound", "cleared"]
RuntimeAuthTransition = Literal[
    "entered_local_bypass",
    "online_auth_required",
    "online_session_dropped",
]
RuntimeSwitchOutcome = Literal[
    "entered_local",
    "entered_online_auth_required",
]
ServerTargetValidationStatus = Literal[
    "validated",
    "target_validation_failed",
    "target_unreachable",
    "target_incompatible",
    "online_target_rejected",
]


@dataclass(frozen=True)
class SessionUser:
    user_id: str
    display_name: str
    email: str | None
    platform_role: PlatformRole


@dataclass(frozen=True)
class WorkspaceAllowedActions:
    switch_to: bool
    activate_dataset: bool
    invite_members: bool
    remove_members: bool
    transfer_owner: bool
    leave_workspace: bool
    view_audit_logs: bool
    manage_definitions: bool
    manage_datasets: bool
    manage_tasks: bool


@dataclass(frozen=True)
class WorkspaceMembership:
    workspace_id: str
    slug: str
    display_name: str
    role: WorkspaceRole
    default_task_scope: TaskScope
    is_active: bool
    allowed_actions: WorkspaceAllowedActions


@dataclass(frozen=True)
class SessionCapabilities:
    can_switch_runtime_mode: bool
    can_switch_workspace: bool
    can_switch_dataset: bool
    can_import_datasets: bool
    can_export_datasets: bool
    can_invite_members: bool
    can_remove_members: bool
    can_transfer_workspace_owner: bool
    can_leave_workspace: bool
    can_submit_tasks: bool
    can_cancel_local_tasks: bool
    can_terminate_local_tasks: bool
    can_retry_local_tasks: bool
    can_manage_workspace_tasks: bool
    can_cancel_own_tasks: bool
    can_cancel_workspace_tasks: bool
    can_terminate_workspace_tasks: bool
    can_retry_own_tasks: bool
    can_retry_workspace_tasks: bool
    can_manage_definitions: bool
    can_publish_definitions: bool
    can_manage_datasets: bool
    can_view_audit_logs: bool


@dataclass(frozen=True)
class SessionAuth:
    state: AuthState
    mode: AuthMode
    reason: AuthReason | None


@dataclass(frozen=True)
class SessionState:
    session_id: str
    runtime_mode: RuntimeMode
    auth_state: AuthState
    auth_mode: AuthMode
    user: SessionUser | None
    server_target_origin: str | None
    server_target_label: str | None
    workspace_id: str
    workspace_slug: str
    workspace_display_name: str
    workspace_role: WorkspaceRole
    default_task_scope: TaskScope
    memberships: tuple[WorkspaceMembership, ...]
    active_dataset_id: str | None


@dataclass(frozen=True)
class ActiveDatasetContext:
    dataset_id: str
    name: str
    family: str
    status: DatasetStatus
    owner_user_id: str
    owner_display_name: str
    workspace_id: str
    visibility_scope: DatasetVisibilityScope
    lifecycle_state: DatasetLifecycleState


@dataclass(frozen=True)
class WorkspaceContext:
    workspace_id: str | None
    slug: str | None
    display_name: str | None
    role: WorkspaceRole | None
    default_task_scope: TaskScope | None
    allowed_actions: WorkspaceAllowedActions


@dataclass(frozen=True)
class ServerTargetSummary:
    origin: str
    label: str
    is_active: bool
    validation_status: ServerTargetValidationStatus
    last_checked_at: str | None


@dataclass(frozen=True)
class SessionConnectionContext:
    target: ServerTargetSummary | None


@dataclass(frozen=True)
class AppSession:
    session_id: str | None
    runtime_mode: RuntimeMode
    auth: SessionAuth
    user: SessionUser | None
    memberships: tuple[WorkspaceMembership, ...]
    workspace: WorkspaceContext
    active_dataset: ActiveDatasetContext | None
    capabilities: SessionCapabilities
    connection: SessionConnectionContext


@dataclass(frozen=True)
class RuntimeModeSwitchResult:
    session: AppSession
    outcome: RuntimeSwitchOutcome
    auth_transition: RuntimeAuthTransition
    session_reset: bool
    detached_task_ids: tuple[int, ...]


@dataclass(frozen=True)
class WorkspaceSwitchResult:
    session: AppSession
    active_dataset_resolution: DatasetResolution
    detached_task_ids: tuple[int, ...]


@dataclass(frozen=True)
class SessionLoginResult:
    session: AppSession
    access_token: str
    refresh_token: str


@dataclass(frozen=True)
class SessionRefreshResult:
    session: AppSession
    access_token: str
    refresh_token: str


@dataclass(frozen=True)
class ServerTargetValidationResult:
    target: ServerTargetSummary
    status: ServerTargetValidationStatus
    message: str


@dataclass(frozen=True)
class ServerTargetListView:
    targets: tuple[ServerTargetSummary, ...]
    active_target_origin: str | None
