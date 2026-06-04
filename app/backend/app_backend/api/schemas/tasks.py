from typing import Literal

from pydantic import BaseModel, ConfigDict, Field
from sc_core.tasking import TaskExecutionMode, WorkerTaskName

from app_backend.api.schemas.storage import (
    MetadataRecordRefResponse,
    ResultHandleRefResponse,
    TracePayloadRefResponse,
)

TaskStatusResponse = Literal[
    "queued",
    "claimed",
    "dispatching",
    "running",
    "staging_result",
    "publishing",
    "cancellation_requested",
    "cancelling",
    "cancelled",
    "termination_requested",
    "terminated",
    "completed",
    "failed",
]


class TaskProgressResponse(BaseModel):
    phase: TaskStatusResponse
    percent_complete: int = Field(ge=0, le=100)
    summary: str
    updated_at: str


class TaskDispatchResponse(BaseModel):
    dispatch_key: str
    status: Literal[
        "accepted",
        "claimed",
        "dispatching",
        "running",
        "cancellation_requested",
        "cancelling",
        "cancelled",
        "termination_requested",
        "terminated",
        "completed",
        "failed",
    ]
    submission_source: Literal["active_dataset", "explicit_dataset", "definition_only"]
    accepted_at: str
    last_updated_at: str
    queue_name: str | None
    enqueued_at: str | None
    runtime_job_id: str | None
    dispatch_attempt_count: int = Field(ge=0)
    last_dispatch_outcome: str | None
    last_dispatch_error_code: str | None


class TaskReconcileResponse(BaseModel):
    required: bool
    reason: str | None = None


class TaskEventResponse(BaseModel):
    event_key: str
    event_type: Literal[
        "task_submitted",
        "task_dispatch_claimed",
        "task_running",
        "task_completed",
        "task_failed",
        "task_cancel_requested",
        "task_cancel_acknowledged",
        "task_terminate_requested",
        "task_terminate_acknowledged",
        "task_requeued",
        "task_retried",
    ]
    level: Literal["info", "warning", "error"]
    occurred_at: str
    message: str
    metadata: dict[str, str | int | bool | None | list[str]]


class TaskResultRefsResponse(BaseModel):
    trace_batch_id: int | None
    analysis_run_id: int | None
    metadata_records: list[MetadataRecordRefResponse]
    trace_payload: TracePayloadRefResponse | None
    result_handles: list[ResultHandleRefResponse]


class TaskAllowedActionsResponse(BaseModel):
    attach: bool
    cancel: bool
    terminate: bool
    retry: bool
    rejection_reason: str | None = None


class TaskResultHandoffResponse(BaseModel):
    availability: Literal["pending", "ready", "none"]
    primary_result_handle_id: str | None
    result_handle_count: int
    trace_payload_available: bool


class TaskSummaryResponse(BaseModel):
    task_id: int
    kind: Literal["simulation", "post_processing", "characterization"]
    lane: Literal["simulation", "characterization"]
    execution_mode: TaskExecutionMode
    status: TaskStatusResponse
    submitted_at: str
    owner_user_id: str
    owner_display_name: str
    workspace_id: str
    workspace_slug: str
    visibility_scope: Literal["local", "workspace", "owned"]
    dataset_id: str | None
    definition_id: str | None
    summary: str


class TaskDetailResponse(TaskSummaryResponse):
    worker_task_name: WorkerTaskName
    request_ready: bool
    submitted_from_active_dataset: bool
    dispatch: TaskDispatchResponse
    reconcile: TaskReconcileResponse
    progress: TaskProgressResponse
    result_handoff: TaskResultHandoffResponse
    result_refs: TaskResultRefsResponse
    allowed_actions: TaskAllowedActionsResponse
    events: list[TaskEventResponse]


class TaskSubmissionRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    kind: Literal["simulation", "post_processing", "characterization"]
    dataset_id: str | None = Field(default=None, min_length=1)
    definition_id: str | None = Field(default=None, min_length=1)
    summary: str | None = Field(default=None, min_length=1)


class TaskMutationResponse(BaseModel):
    operation: Literal["submitted"]
    task: TaskDetailResponse
