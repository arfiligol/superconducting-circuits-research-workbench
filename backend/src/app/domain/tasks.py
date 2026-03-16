from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal, cast

from sc_core.execution import (
    TaskExecutionHistoryContext,
    TaskExecutionHistoryEvent,
    TaskExecutionHistoryEventType,
    TaskExecutionHistoryLevel,
    TaskExecutionHistoryMetadataValue,
    TaskResultHandle,
    build_task_execution_history,
    build_task_execution_history_context,
    build_task_lifecycle_history_event,
    build_task_submission_history_event,
)
from sc_core.storage import TraceResultLinkage
from sc_core.tasking import (
    TaskDispatchRecord,
    TaskExecutionMode,
    TaskSubmissionSource,
    WorkerTaskName,
    build_task_dispatch_record,
)
from sc_core.tasking import (
    TaskDispatchStatus as _TaskDispatchStatus,
)
from sc_core.tasking import (
    task_submission_source_for as _task_submission_source_for,
)

from src.app.domain.storage import MetadataRecordRef, ResultHandleRef, TracePayloadRef

TaskKind = Literal["simulation", "post_processing", "characterization"]
TaskLane = Literal["simulation", "characterization"]
TaskStatus = Literal[
    "queued",
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
TaskControlState = Literal["none", "cancellation_requested", "termination_requested"]
TaskQueueBackend = Literal["in_memory_scaffold"]
TaskVisibilityScope = Literal["local", "workspace", "owned"]
TaskResultAvailability = Literal["pending", "ready", "none"]
TaskEventType = Literal[
    "task_submitted",
    "task_running",
    "task_completed",
    "task_failed",
    "task_cancel_requested",
    "task_terminate_requested",
    "task_retried",
]
TaskEventLevel = TaskExecutionHistoryLevel
TaskEventMetadataValue = TaskExecutionHistoryMetadataValue
TaskEventOrder = Literal["asc", "desc"]
TaskDispatchStatus = _TaskDispatchStatus
task_submission_source_for = _task_submission_source_for


@dataclass(frozen=True)
class TaskProgress:
    phase: TaskStatus
    percent_complete: int
    summary: str
    updated_at: str


@dataclass(frozen=True)
class TaskResultRefs:
    result_handle: TaskResultHandle
    metadata_records: tuple[MetadataRecordRef, ...]
    trace_payload: TracePayloadRef | None
    result_handles: tuple[ResultHandleRef, ...]

    @property
    def trace_batch_id(self) -> int | None:
        return self.result_handle.trace_batch_id

    @property
    def analysis_run_id(self) -> int | None:
        return self.result_handle.analysis_run_id

    def storage_linkage(self) -> TraceResultLinkage:
        return TraceResultLinkage.from_result_handle(self.result_handle)


@dataclass(frozen=True)
class TaskSummary:
    task_id: int
    kind: TaskKind
    lane: TaskLane
    execution_mode: TaskExecutionMode
    status: TaskStatus
    submitted_at: str
    owner_user_id: str
    owner_display_name: str
    workspace_id: str
    workspace_slug: str
    visibility_scope: TaskVisibilityScope
    dataset_id: str | None
    definition_id: int | None
    summary: str


TaskDispatch = TaskDispatchRecord
TaskEvent = TaskExecutionHistoryEvent


@dataclass(frozen=True)
class TaskAllowedActions:
    attach: bool
    cancel: bool
    terminate: bool
    retry: bool
    rejection_reason: str | None = None


@dataclass(frozen=True)
class TaskResultHandoff:
    availability: TaskResultAvailability
    primary_result_handle_id: str | None
    result_handle_count: int
    trace_payload_available: bool


@dataclass(frozen=True)
class WorkerLaneSummary:
    lane: TaskLane
    healthy_processors: int
    busy_processors: int
    degraded_processors: int
    draining_processors: int
    offline_processors: int


@dataclass(frozen=True)
class TaskQueueRow:
    task_id: int
    summary: str
    status: TaskStatus
    control_state: TaskControlState
    lane: TaskLane
    task_kind: TaskKind
    owner_display_name: str
    visibility_scope: TaskVisibilityScope
    updated_at: str
    result_availability: TaskResultAvailability
    allowed_actions: TaskAllowedActions


@dataclass(frozen=True)
class TaskQueueView:
    rows: tuple[TaskQueueRow, ...]
    worker_summary: tuple[WorkerLaneSummary, ...]
    total_count: int
    next_cursor: str | None
    prev_cursor: str | None
    has_more: bool


@dataclass(frozen=True)
class TaskDetail(TaskSummary):
    queue_backend: TaskQueueBackend
    worker_task_name: WorkerTaskName
    request_ready: bool
    submitted_from_active_dataset: bool
    progress: TaskProgress
    result_refs: TaskResultRefs
    control_state: TaskControlState = "none"
    retry_of_task_id: int | None = None
    dispatch: TaskDispatch | None = None
    events: tuple[TaskEvent, ...] = ()


@dataclass(frozen=True)
class TaskListQuery:
    status: TaskStatus | None = None
    lane: TaskLane | None = None
    scope: TaskVisibilityScope = "workspace"
    dataset_id: str | None = None
    search_query: str | None = None
    limit: int = 20


@dataclass(frozen=True)
class TaskEventHistoryQuery:
    order: TaskEventOrder = "desc"
    limit: int = 20
    event_type: TaskEventType | None = None


@dataclass(frozen=True)
class TaskHistoryView:
    task: TaskDetail
    event_count: int
    latest_event: TaskEvent | None


@dataclass(frozen=True)
class TaskSubmissionDraft:
    kind: TaskKind
    dataset_id: str | None
    definition_id: int | None
    summary: str | None


@dataclass(frozen=True)
class TaskCreateDraft:
    kind: TaskKind
    lane: TaskLane
    execution_mode: TaskExecutionMode
    owner_user_id: str
    owner_display_name: str
    workspace_id: str
    workspace_slug: str
    visibility_scope: TaskVisibilityScope
    dataset_id: str | None
    definition_id: int | None
    summary: str
    worker_task_name: WorkerTaskName
    request_ready: bool
    submitted_from_active_dataset: bool
    submission_source: TaskSubmissionSource
    retry_of_task_id: int | None = None


@dataclass(frozen=True)
class TaskLifecycleUpdate:
    task_id: int
    status: TaskStatus
    progress_percent_complete: int
    progress_summary: str
    progress_updated_at: str
    summary: str | None = None
    result_refs: TaskResultRefs | None = None
    dispatch: TaskDispatch | None = None


def build_task_dispatch(
    *,
    task_id: int,
    worker_task_name: str,
    task_status: TaskStatus,
    submitted_from_active_dataset: bool,
    dataset_id: str | None,
    accepted_at: str,
    last_updated_at: str,
    submission_source: TaskSubmissionSource | None = None,
    current_dispatch: TaskDispatch | None = None,
) -> TaskDispatch:
    return build_task_dispatch_record(
        task_id=task_id,
        worker_task_name=cast(WorkerTaskName, worker_task_name),
        task_status=task_status,
        submitted_from_active_dataset=submitted_from_active_dataset,
        dataset_id=dataset_id,
        accepted_at=accepted_at,
        last_updated_at=last_updated_at,
        submission_source=submission_source,
        current_dispatch=current_dispatch,
    )


def build_task_submission_event(task: TaskDetail) -> TaskEvent:
    return build_task_submission_history_event(_build_task_history_context(task))


def _build_task_history_context(task: TaskDetail) -> TaskExecutionHistoryContext:
    dispatch = build_task_dispatch(
        task_id=task.task_id,
        worker_task_name=task.worker_task_name,
        task_status=task.status,
        submitted_from_active_dataset=task.submitted_from_active_dataset,
        dataset_id=task.dataset_id,
        accepted_at=task.submitted_at,
        last_updated_at=task.progress.updated_at,
        current_dispatch=task.dispatch,
    )
    return build_task_execution_history_context(
        task_status=task.status,
        submitted_at=task.submitted_at,
        progress_updated_at=task.progress.updated_at,
        progress_percent_complete=task.progress.percent_complete,
        dispatch=dispatch,
        worker_task_name=task.worker_task_name,
        dataset_id=task.dataset_id,
        definition_id=task.definition_id,
        result_handle_ids=tuple(
            str(handle.handle_id) for handle in task.result_refs.result_handles
        ),
    )


def build_task_lifecycle_event(task: TaskDetail) -> TaskEvent | None:
    return build_task_lifecycle_history_event(_build_task_history_context(task))


def build_task_event_history(task: TaskDetail) -> tuple[TaskEvent, ...]:
    return build_task_execution_history(_build_task_history_context(task))


def build_task_control_event(
    *,
    task: TaskDetail,
    control_state: TaskControlState,
    occurred_at: str,
    actor_user_id: str,
) -> TaskEvent:
    event_type: TaskEventType
    message: str
    audit_action: str
    if control_state == "cancellation_requested":
        event_type = "task_cancel_requested"
        message = "Cancellation was requested for the task."
        audit_action = "task.cancel_requested"
    else:
        event_type = "task_terminate_requested"
        message = "Force termination was requested for the task."
        audit_action = "task.terminate_requested"
    return TaskEvent(
        event_key=f"{event_type}:{occurred_at}",
        event_type=cast(TaskExecutionHistoryEventType, event_type),
        level="warning",
        occurred_at=occurred_at,
        message=message,
        metadata={
            "task_status": task.status,
            "dispatch_status": task.dispatch.status if task.dispatch is not None else None,
            "dispatch_key": task.dispatch.dispatch_key if task.dispatch is not None else None,
            "worker_task_name": task.worker_task_name,
            "actor_user_id": actor_user_id,
            "audit_action": audit_action,
        },
    )


def build_task_retry_event(
    *,
    source_task: TaskDetail,
    replacement_task_id: int,
    occurred_at: str,
    actor_user_id: str,
) -> TaskEvent:
    return TaskEvent(
        event_key=f"task_retried:{occurred_at}",
        event_type=cast(TaskExecutionHistoryEventType, "task_retried"),
        level="info",
        occurred_at=occurred_at,
        message="A retry task was created from the current task snapshot.",
        metadata={
            "task_status": source_task.status,
            "dispatch_status": (
                source_task.dispatch.status if source_task.dispatch is not None else None
            ),
            "dispatch_key": (
                source_task.dispatch.dispatch_key if source_task.dispatch is not None else None
            ),
            "replacement_task_id": replacement_task_id,
            "actor_user_id": actor_user_id,
            "audit_action": "task.retried",
        },
    )


def resolve_task_control_state(
    status: TaskStatus,
    events: Sequence[TaskEvent],
) -> TaskControlState:
    if status in {"cancellation_requested", "cancelling"}:
        return "cancellation_requested"
    if status == "termination_requested":
        return "termination_requested"
    if status in {"cancelled", "terminated", "completed", "failed"}:
        return "none"
    for event in reversed(tuple(events)):
        if event.event_type in {"task_completed", "task_failed"}:
            return "none"
        if event.event_type == "task_terminate_requested":
            return "termination_requested"
        if event.event_type == "task_cancel_requested":
            return "cancellation_requested"
    return "none"


def resolve_retry_of_task_id(events: Sequence[TaskEvent]) -> int | None:
    for event in events:
        retry_of_task_id = event.metadata.get("retry_of_task_id")
        if isinstance(retry_of_task_id, int):
            return retry_of_task_id
    return None
