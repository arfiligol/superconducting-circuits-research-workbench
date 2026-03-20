from typing import Literal

from pydantic import BaseModel, ConfigDict, Field
from sc_core.tasking import TaskExecutionMode, WorkerTaskName

from src.app.api.schemas.storage import (
    MetadataRecordRefResponse,
    ResultHandleRefResponse,
    TracePayloadRefResponse,
)


class TaskProgressResponse(BaseModel):
    phase: Literal["queued", "running", "completed", "failed"]
    percent_complete: int = Field(ge=0, le=100)
    summary: str
    updated_at: str


class TaskDispatchResponse(BaseModel):
    dispatch_key: str
    status: Literal["accepted", "running", "completed", "failed"]
    submission_source: Literal["active_dataset", "explicit_dataset", "definition_only"]
    accepted_at: str
    last_updated_at: str


class TaskEventResponse(BaseModel):
    event_key: str
    event_type: Literal["task_submitted", "task_running", "task_completed", "task_failed"]
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


class TaskSummaryResponse(BaseModel):
    task_id: int
    kind: Literal["simulation", "post_processing", "characterization"]
    lane: Literal["simulation", "characterization"]
    execution_mode: TaskExecutionMode
    status: Literal["queued", "running", "completed", "failed"]
    submitted_at: str
    owner_user_id: str
    owner_display_name: str
    workspace_id: str
    workspace_slug: str
    visibility_scope: Literal["workspace", "owned"]
    dataset_id: str | None
    definition_id: int | None
    summary: str


class TaskDetailResponse(TaskSummaryResponse):
    worker_task_name: WorkerTaskName
    request_ready: bool
    submitted_from_active_dataset: bool
    dispatch: TaskDispatchResponse
    progress: TaskProgressResponse
    result_refs: TaskResultRefsResponse
    events: list[TaskEventResponse]


class TaskSubmissionRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    kind: Literal["simulation", "post_processing", "characterization"]
    dataset_id: str | None = Field(default=None, min_length=1)
    definition_id: int | None = Field(default=None, ge=1)
    summary: str | None = Field(default=None, min_length=1)


class TaskMutationResponse(BaseModel):
    operation: Literal["submitted"]
    task: TaskDetailResponse
