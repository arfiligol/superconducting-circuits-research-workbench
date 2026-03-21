"""Typed request/response models for the WS5 `/api/v1/*` contract."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from core.shared.persistence.models import normalize_user_role


class ApiModel(BaseModel):
    """Base API model with a strict extra-field policy."""

    model_config = ConfigDict(extra="forbid")


class UserResponse(ApiModel):
    """Stable user summary returned by auth/admin endpoints."""

    id: int
    username: str
    role: str
    is_active: bool
    created_at: datetime
    last_login_at: datetime | None = None


class LoginRequest(ApiModel):
    """Credentials for the local phase-1 login endpoint."""

    username: str
    password: str


class AuthResponse(ApiModel):
    """Authenticated user payload returned by login and `/auth/me`."""

    authenticated: bool = True
    user: UserResponse


class LogoutResponse(ApiModel):
    """Logout acknowledgement payload."""

    authenticated: bool = False
    message: str


class CreateUserRequest(ApiModel):
    """Admin request payload for creating a local user."""

    username: str
    password: str
    role: str
    is_active: bool = True

    @field_validator("role")
    @classmethod
    def _validate_role(cls, value: str) -> str:
        return normalize_user_role(value)


class UpdateUserRequest(ApiModel):
    """Admin request payload for updating local-user state."""

    role: str | None = None
    is_active: bool | None = None

    @field_validator("role")
    @classmethod
    def _validate_role(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return normalize_user_role(value)

    @model_validator(mode="after")
    def _require_one_field(self) -> UpdateUserRequest:
        if self.role is None and self.is_active is None:
            raise ValueError("Provide at least one of: role, is_active.")
        return self


class PasswordResetRequest(ApiModel):
    """Admin request payload for replacing a local password."""

    new_password: str = Field(min_length=1)


class UsersListResponse(ApiModel):
    """Admin user-list response."""

    users: list[UserResponse]


class AuditLogResponse(ApiModel):
    """Stable audit-log row returned by admin endpoints."""

    id: int
    actor_id: int | None
    action_kind: str
    resource_kind: str
    resource_id: str
    summary: str
    payload: dict[str, Any]
    created_at: datetime


class AuditLogsListResponse(ApiModel):
    """Admin audit-log list response."""

    logs: list[AuditLogResponse]


class TaskResponse(ApiModel):
    """Stable persisted-task projection for v1 task endpoints."""

    id: int
    task_kind: str
    status: str
    design_id: int
    trace_batch_id: int | None
    analysis_run_id: int | None
    requested_by: str
    actor_id: int | None
    dedupe_key: str | None
    request_payload: dict[str, Any]
    progress_payload: dict[str, Any]
    result_summary_payload: dict[str, Any]
    error_payload: dict[str, Any]
    created_at: datetime
    started_at: datetime | None
    heartbeat_at: datetime | None
    completed_at: datetime | None


class TaskDispatchResponse(ApiModel):
    """Task-submission response with dispatch metadata."""

    task: TaskResponse
    dedupe_hit: bool
    dispatched_lane: str
    worker_task_name: str


class DesignTasksResponse(ApiModel):
    """Design-scoped task listing payload."""

    tasks: list[TaskResponse]


class SimulationTaskCreateRequest(ApiModel):
    """Typed request contract for `POST /api/v1/tasks/simulation`."""

    design_id: int
    schema_source_hash: str | None = None
    simulation_setup_hash: str | None = None
    request_payload: dict[str, Any] = Field(default_factory=dict)
    force_rerun: bool = False


class PostProcessingTaskCreateRequest(ApiModel):
    """Typed request contract for `POST /api/v1/tasks/post-processing`."""

    design_id: int
    source_batch_id: int | None = None
    input_source: str = "raw_y"
    request_payload: dict[str, Any] = Field(default_factory=dict)
    force_rerun: bool = False


class CharacterizationTaskCreateRequest(ApiModel):
    """Typed request contract for `POST /api/v1/tasks/characterization`."""

    design_id: int
    analysis_id: str
    analysis_label: str | None = None
    run_id: str = ""
    trace_record_ids: list[int] = Field(default_factory=list)
    selected_batch_ids: list[int] = Field(default_factory=list)
    selected_scope_token: str = ""
    trace_mode_group: str | None = None
    config_state: dict[str, str | float | int | None] = Field(default_factory=dict)
    summary_payload: dict[str, Any] = Field(default_factory=dict)
    request_payload: dict[str, Any] = Field(default_factory=dict)
    force_rerun: bool = False


class LatestTraceBatchResponse(ApiModel):
    """Stable latest-result payload for simulation/post-processing artifacts."""

    batch_id: int
    design_id: int
    source_kind: str
    stage_kind: str
    status: str
    parent_batch_id: int | None
    setup_kind: str | None
    setup_version: str | None
    provenance_payload: dict[str, Any]
    summary_payload: dict[str, Any]
    task_id: int | None = None


class LatestCharacterizationResponse(ApiModel):
    """Stable latest-result payload for characterization runs."""

    analysis_run_id: int
    design_id: int
    analysis_id: str
    analysis_label: str
    run_id: str
    status: str
    input_trace_ids: list[int]
    input_batch_ids: list[int]
    input_scope: str
    trace_mode_group: str
    config_payload: dict[str, Any]
    summary_payload: dict[str, Any]
    created_at: datetime
    completed_at: datetime | None
    task_id: int | None = None
