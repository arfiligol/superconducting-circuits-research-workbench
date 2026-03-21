from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Literal

from sc_core.tasking import (
    LaneName,
    TaskControlAction,
    TaskControlDecision,
    TaskControlOutcome,
    TaskControlRuntimeProjection,
    TaskDispatchRecord,
    TaskDispatchStatus as TaskExecutionHistoryDispatchStatus,
    TaskRetryLineage,
    TaskRuntimeState,
    TaskSubmissionSource as TaskExecutionHistorySubmissionSource,
    TERMINAL_TASK_STATES,
    WorkerTaskName,
    is_terminal_task_state,
    sanitize_processor_runtime_metadata,
)

ExecutionPhase = Literal[
    "running",
    "completed",
    "failed",
    "crashing",
    "cancel_requested",
    "terminate_requested",
    "retried",
]
TaskLifecycleStatus = TaskRuntimeState
ExecutionEventKind = Literal[
    "worker.task_started",
    "worker.task_completed",
    "worker.task_failed",
    "worker.task_crashing",
    "task.cancel_requested",
    "task.terminate_requested",
    "task.retried",
    "reconcile.task_failed",
    "reconcile.batch_failed",
]
ExecutionEventResourceKind = Literal["task", "trace_batch"]
TaskExecutionHistoryEventType = Literal[
    "task_submitted",
    "task_running",
    "task_completed",
    "task_failed",
    "task_cancel_requested",
    "task_terminate_requested",
    "task_retried",
]
TaskExecutionHistoryLevel = Literal["info", "warning", "error"]
TaskAuditActionKind = Literal[
    "worker.task_started",
    "worker.task_completed",
    "worker.task_failed",
    "worker.task_crashing",
]
TaskExecutionAuditActionKind = Literal[
    "worker.task_started",
    "worker.task_completed",
    "worker.task_failed",
    "worker.task_crashing",
    "task.cancel_requested",
    "task.terminate_requested",
    "task.retried",
    "reconcile.task_failed",
]
ExecutionAuditOutcome = Literal["accepted", "rejected", "completed", "failed"]
TaskHistoryControlPhase = Literal["requested", "acknowledged", "terminal"]

EXECUTION_CONTRACT_VERSION = "sc_execution.v1"
WORKER_TASK_FAILED_ERROR_CODE = "worker_task_failed"
STALE_TASK_TIMEOUT_ERROR_CODE = "stale_task_timeout"
TaskExecutionHistoryMetadataValue = str | int | bool | None | list[str]


@dataclass(frozen=True)
class TaskCreationSpec:
    """Canonical queued-task creation contract for persistence adapters."""

    task_kind: str
    design_id: int
    request_payload: dict[str, object] = field(default_factory=dict)
    requested_by: str = ""
    actor_id: int | None = None
    dedupe_key: str | None = None
    result_handle: TaskResultHandle = field(default_factory=lambda: TaskResultHandle())


@dataclass(frozen=True)
class TaskResultHandle:
    """Stable references to execution outputs created by one task."""

    trace_batch_id: int | None = None
    analysis_run_id: int | None = None

    @classmethod
    def from_mapping(cls, payload: Mapping[str, object]) -> TaskResultHandle:
        return cls(
            trace_batch_id=_optional_int(payload.get("trace_batch_id")),
            analysis_run_id=_optional_int(payload.get("analysis_run_id")),
        )

    def is_empty(self) -> bool:
        return self.trace_batch_id is None and self.analysis_run_id is None

    def to_payload(self) -> dict[str, int]:
        payload: dict[str, int] = {}
        if self.trace_batch_id is not None:
            payload["trace_batch_id"] = self.trace_batch_id
        if self.analysis_run_id is not None:
            payload["analysis_run_id"] = self.analysis_run_id
        return payload


@dataclass(frozen=True)
class TaskExecutionResult:
    """Framework-agnostic execution result summary returned by worker operations."""

    result_summary_payload: dict[str, object] = field(default_factory=dict)
    trace_batch_id: int | None = None
    analysis_run_id: int | None = None

    def result_handle(self) -> TaskResultHandle:
        return TaskResultHandle(
            trace_batch_id=self.trace_batch_id,
            analysis_run_id=self.analysis_run_id,
        )


@dataclass(frozen=True)
class TaskLifecycleMutation:
    """Canonical persistence-layer mutation for one task lifecycle transition."""

    status: TaskLifecycleStatus | None = None
    started_at: datetime | None = None
    heartbeat_at: datetime | None = None
    completed_at: datetime | None = None
    progress_payload: dict[str, object] | None = None
    result_summary_payload: dict[str, object] | None = None
    error_payload: dict[str, object] | None = None
    result_handle: TaskResultHandle | None = None


@dataclass(frozen=True)
class ExecutionEventLog:
    """Canonical persisted execution-event envelope for audit/history adapters."""

    action_kind: ExecutionEventKind
    resource_kind: ExecutionEventResourceKind
    resource_id: str
    summary: str
    payload: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class TaskExecutionHistoryEvent:
    """Canonical task-history entry suitable for API/read-model adapters."""

    event_key: str
    event_type: TaskExecutionHistoryEventType
    level: TaskExecutionHistoryLevel
    occurred_at: str
    message: str
    metadata: dict[str, TaskExecutionHistoryMetadataValue] = field(default_factory=dict)

    @classmethod
    def from_mapping(
        cls,
        *,
        event_key: str,
        event_type: TaskExecutionHistoryEventType,
        level: TaskExecutionHistoryLevel,
        occurred_at: str,
        message: str,
        metadata: Mapping[str, object] | None = None,
    ) -> TaskExecutionHistoryEvent:
        """Build one canonical task-history entry from primitive mapping data."""
        return cls(
            event_key=event_key,
            event_type=event_type,
            level=level,
            occurred_at=canonicalize_execution_timestamp(occurred_at),
            message=message,
            metadata=coerce_task_execution_history_metadata(metadata),
        )


@dataclass(frozen=True)
class TaskExecutionHistoryContext:
    """Framework-agnostic snapshot used to assemble task event history."""

    task_status: TaskLifecycleStatus
    submitted_at: str
    progress_updated_at: str
    progress_percent_complete: int
    dispatch: TaskDispatchRecord
    worker_task_name: WorkerTaskName
    dataset_id: str | None
    definition_id: int | None
    result_handle_ids: tuple[str, ...] = ()

    @property
    def dispatch_key(self) -> str:
        return self.dispatch.dispatch_key

    @property
    def dispatch_status(self) -> TaskExecutionHistoryDispatchStatus:
        return self.dispatch.status

    @property
    def submission_source(self) -> TaskExecutionHistorySubmissionSource:
        return self.dispatch.submission_source


@dataclass(frozen=True)
class TaskControlHistoryPair:
    """Canonical pairing of task-history and audit artifacts for one control request."""

    history_event: TaskExecutionHistoryEvent
    event_log: ExecutionEventLog


@dataclass(frozen=True)
class TaskHistoryEventMetadataNormalization:
    """Canonical normalization result for one task-history metadata payload."""

    metadata: dict[str, TaskExecutionHistoryMetadataValue]
    missing_fields: tuple[str, ...] = ()
    normalized_fields: tuple[str, ...] = ()

    @property
    def is_complete(self) -> bool:
        return not self.missing_fields

    @property
    def is_canonical(self) -> bool:
        return self.is_complete and not self.normalized_fields


@dataclass(frozen=True)
class TaskExecutionTransition:
    """Canonical orchestration transition tying persistence mutation to audit metadata."""

    mutation: TaskLifecycleMutation
    event_log: ExecutionEventLog | None = None

    @property
    def audit_action_kind(self) -> ExecutionEventKind | None:
        if self.event_log is None:
            return None
        return self.event_log.action_kind

    @property
    def audit_summary(self) -> str | None:
        if self.event_log is None:
            return None
        return self.event_log.summary

    @property
    def audit_payload(self) -> dict[str, object] | None:
        if self.event_log is None:
            return None
        return dict(self.event_log.payload)


@dataclass(frozen=True)
class TaskExecutionOperation:
    """Canonical persisted-task operation combining identity and one transition."""

    task_id: int
    actor_id: int | None
    transition: TaskExecutionTransition

    @property
    def event_log(self) -> ExecutionEventLog | None:
        return self.transition.event_log

    @property
    def audit_action_kind(self) -> ExecutionEventKind | None:
        return self.transition.audit_action_kind

    @property
    def audit_summary(self) -> str | None:
        return self.transition.audit_summary

    @property
    def audit_payload(self) -> dict[str, object] | None:
        return self.transition.audit_payload


@dataclass(frozen=True)
class WorkerExecutionContext:
    """Stable worker execution identity used across dispatch-adjacent lifecycle phases."""

    lane: LaneName
    worker_task_name: WorkerTaskName
    worker_pid: int | None = None


@dataclass(frozen=True)
class WorkerExecutionProvenance:
    """Provenance fields attached to persisted execution payloads and logs."""

    lane: LaneName
    worker_task_name: WorkerTaskName
    worker_pid: int | None = None
    started_at: str | None = None
    completed_at: str | None = None
    crash_requested_at: str | None = None

    def to_payload(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "lane": self.lane,
            "worker_task_name": self.worker_task_name,
        }
        if self.worker_pid is not None:
            payload["worker_pid"] = self.worker_pid
        if self.started_at is not None:
            payload["started_at"] = self.started_at
        if self.completed_at is not None:
            payload["completed_at"] = self.completed_at
        if self.crash_requested_at is not None:
            payload["crash_requested_at"] = self.crash_requested_at
        return payload


def build_worker_execution_provenance(
    *,
    lane: LaneName,
    worker_task_name: WorkerTaskName,
    worker_pid: int | None = None,
    started_at: datetime | None = None,
    completed_at: datetime | None = None,
    crash_requested_at: datetime | None = None,
) -> WorkerExecutionProvenance:
    """Build canonical worker provenance while normalizing timestamp encoding."""
    return WorkerExecutionProvenance(
        lane=lane,
        worker_task_name=worker_task_name,
        worker_pid=worker_pid,
        started_at=_optional_isoformat(started_at),
        completed_at=_optional_isoformat(completed_at),
        crash_requested_at=_optional_isoformat(crash_requested_at),
    )


def build_worker_execution_context(
    *,
    lane: LaneName,
    worker_task_name: WorkerTaskName,
    worker_pid: int | None = None,
) -> WorkerExecutionContext:
    """Build canonical worker execution context for runtime orchestration flows."""
    return WorkerExecutionContext(
        lane=lane,
        worker_task_name=worker_task_name,
        worker_pid=worker_pid,
    )


def _lane_task_label(lane: LaneName) -> str:
    if lane == "simulation":
        return "Simulation task"
    if lane == "post_processing":
        return "Post-processing task"
    return "Characterization task"


def _first_failure_line(message: str) -> str:
    for line in message.splitlines():
        stripped = line.strip()
        if stripped:
            return stripped
    return ""


def build_task_start_payload(
    *,
    provenance: WorkerExecutionProvenance,
    stale_after_seconds: int = 300,
) -> dict[str, object]:
    """Build the persisted progress payload for a task entering running state."""
    details = provenance.to_payload()
    return {
        "contract_version": EXECUTION_CONTRACT_VERSION,
        "phase": "running",
        "summary": f"{_lane_task_label(provenance.lane)} started.",
        "recorded_at": provenance.started_at,
        "stage_label": provenance.worker_task_name,
        "stale_after_seconds": stale_after_seconds,
        "details": details,
        "lane": provenance.lane,
        "worker_task_name": provenance.worker_task_name,
    }


def build_task_creation_spec(
    *,
    task_kind: str,
    design_id: int,
    request_payload: Mapping[str, object] | None,
    requested_by: str,
    actor_id: int | None = None,
    dedupe_key: str | None = None,
    result_handle: TaskResultHandle | None = None,
) -> TaskCreationSpec:
    """Build the canonical queued-task creation contract for one persisted task."""
    return TaskCreationSpec(
        task_kind=task_kind.strip(),
        design_id=design_id,
        request_payload=_copy_payload(request_payload) or {},
        requested_by=requested_by.strip(),
        actor_id=actor_id,
        dedupe_key=normalize_task_dedupe_key(dedupe_key),
        result_handle=result_handle or TaskResultHandle(),
    )


def normalize_task_dedupe_key(dedupe_key: str | None) -> str | None:
    """Normalize optional dedupe keys so create/read paths share the same contract."""
    if dedupe_key is None:
        return None
    normalized = dedupe_key.strip()
    return normalized or None


def build_task_queued_payload(
    *,
    creation_spec: TaskCreationSpec,
) -> dict[str, object]:
    """Build the canonical persisted payload for one queued task."""
    payload: dict[str, object] = {
        "contract_version": EXECUTION_CONTRACT_VERSION,
        "phase": "queued",
        "summary": f"{creation_spec.task_kind} queued by {creation_spec.requested_by}.",
        "task_kind": creation_spec.task_kind,
        "requested_by": creation_spec.requested_by,
    }
    if creation_spec.actor_id is not None:
        payload["actor_id"] = creation_spec.actor_id
    if creation_spec.dedupe_key is not None:
        payload["dedupe_key"] = creation_spec.dedupe_key
    if not creation_spec.result_handle.is_empty():
        payload["result_refs"] = creation_spec.result_handle.to_payload()
    return payload


def build_task_queued_mutation(
    *,
    creation_spec: TaskCreationSpec,
) -> TaskLifecycleMutation:
    """Build the canonical queued-state mutation for one newly created task."""
    return TaskLifecycleMutation(
        status="queued",
        progress_payload=build_task_queued_payload(creation_spec=creation_spec),
        result_handle=creation_spec.result_handle,
    )


def build_task_queued_transition(
    *,
    creation_spec: TaskCreationSpec,
) -> TaskExecutionTransition:
    """Build the canonical orchestration transition for one newly queued task."""
    return TaskExecutionTransition(
        mutation=build_task_queued_mutation(creation_spec=creation_spec),
    )


def build_task_execution_operation(
    *,
    task_id: int,
    transition: TaskExecutionTransition,
    actor_id: int | None = None,
) -> TaskExecutionOperation:
    """Build the canonical persisted-task operation for one transition."""
    return TaskExecutionOperation(
        task_id=task_id,
        actor_id=actor_id,
        transition=transition,
    )


def build_task_running_mutation(
    *,
    recorded_at: datetime,
    progress_payload: Mapping[str, object] | None = None,
) -> TaskLifecycleMutation:
    """Build the canonical running-state mutation for one task."""
    return TaskLifecycleMutation(
        status="running",
        started_at=recorded_at,
        heartbeat_at=recorded_at,
        progress_payload=_copy_payload(progress_payload),
    )


def build_task_heartbeat_payload(
    *,
    summary: str,
    recorded_at: datetime,
    stage_label: str | None = None,
    phase: str = "running",
    current_step: int | None = None,
    total_steps: int | None = None,
    warning: str | None = None,
    stale_after_seconds: int | None = None,
    details: Mapping[str, object] | None = None,
    extra_payload: Mapping[str, object] | None = None,
) -> dict[str, object]:
    """Build the canonical persisted heartbeat payload shape for one task."""
    payload: dict[str, object] = {
        "phase": phase,
        "summary": summary,
        "recorded_at": recorded_at.isoformat(),
    }
    if stage_label is not None:
        payload["stage_label"] = stage_label
    if current_step is not None:
        payload["current_step"] = current_step
    if total_steps is not None:
        payload["total_steps"] = total_steps
    if warning is not None:
        payload["warning"] = warning
    if stale_after_seconds is not None:
        payload["stale_after_seconds"] = stale_after_seconds
    if details:
        payload["details"] = dict(details)
    if extra_payload:
        payload.update(dict(extra_payload))
    return payload


def build_task_heartbeat_transition(
    *,
    recorded_at: datetime,
    progress_payload: Mapping[str, object],
) -> TaskExecutionTransition:
    """Build the canonical orchestration transition for one task heartbeat."""
    return TaskExecutionTransition(
        mutation=build_task_heartbeat_mutation(
            recorded_at=recorded_at,
            progress_payload=progress_payload,
        ),
    )


def build_task_heartbeat_operation(
    *,
    task_id: int,
    recorded_at: datetime,
    progress_payload: Mapping[str, object],
    actor_id: int | None = None,
) -> TaskExecutionOperation:
    """Build the canonical persisted-task operation for one heartbeat update."""
    return build_task_execution_operation(
        task_id=task_id,
        actor_id=actor_id,
        transition=build_task_heartbeat_transition(
            recorded_at=recorded_at,
            progress_payload=progress_payload,
        ),
    )


def build_worker_running_transition(
    *,
    task_id: int,
    recorded_at: datetime,
    context: WorkerExecutionContext,
    stale_after_seconds: int = 300,
) -> TaskExecutionTransition:
    """Build the running transition for one worker-managed task execution."""
    provenance = build_worker_execution_provenance(
        lane=context.lane,
        worker_task_name=context.worker_task_name,
        worker_pid=context.worker_pid,
        started_at=recorded_at,
    )
    return _build_worker_transition(
        phase="running",
        task_id=task_id,
        worker_task_name=context.worker_task_name,
        mutation=build_task_running_mutation(
            recorded_at=recorded_at,
            progress_payload=build_task_start_payload(
                provenance=provenance,
                stale_after_seconds=stale_after_seconds,
            ),
        ),
        audit_payload=build_worker_audit_payload(
            phase="running",
            provenance=provenance,
            recorded_at=recorded_at,
        ),
    )


def build_worker_running_operation(
    *,
    task_id: int,
    recorded_at: datetime,
    context: WorkerExecutionContext,
    actor_id: int | None = None,
    stale_after_seconds: int = 300,
) -> TaskExecutionOperation:
    """Build the persisted-task operation for one worker-managed running transition."""
    return build_task_execution_operation(
        task_id=task_id,
        actor_id=actor_id,
        transition=build_worker_running_transition(
            task_id=task_id,
            recorded_at=recorded_at,
            context=context,
            stale_after_seconds=stale_after_seconds,
        ),
    )


def build_task_heartbeat_mutation(
    *,
    recorded_at: datetime,
    progress_payload: Mapping[str, object],
) -> TaskLifecycleMutation:
    """Build the canonical heartbeat mutation for one already-running task."""
    return TaskLifecycleMutation(
        heartbeat_at=recorded_at,
        progress_payload=_copy_payload(progress_payload),
    )


def build_task_completed_mutation(
    *,
    recorded_at: datetime,
    result_summary_payload: Mapping[str, object],
    result_handle: TaskResultHandle,
) -> TaskLifecycleMutation:
    """Build the canonical completion mutation for one finished task."""
    return TaskLifecycleMutation(
        status="completed",
        heartbeat_at=recorded_at,
        completed_at=recorded_at,
        result_summary_payload=_copy_payload(result_summary_payload),
        error_payload={},
        result_handle=result_handle,
    )


def build_worker_completed_transition(
    *,
    task_id: int,
    recorded_at: datetime,
    context: WorkerExecutionContext,
    result: TaskExecutionResult,
) -> TaskExecutionTransition:
    """Build the completion transition for one worker-managed task execution."""
    provenance = build_worker_execution_provenance(
        lane=context.lane,
        worker_task_name=context.worker_task_name,
        worker_pid=context.worker_pid,
        completed_at=recorded_at,
    )
    completed_payload = build_task_success_payload(
        provenance=provenance,
        summary_payload=dict(result.result_summary_payload),
        result_handle=result.result_handle(),
    )
    return _build_worker_transition(
        phase="completed",
        task_id=task_id,
        worker_task_name=context.worker_task_name,
        mutation=build_task_completed_mutation(
            recorded_at=recorded_at,
            result_summary_payload=completed_payload,
            result_handle=result.result_handle(),
        ),
        audit_payload={
            **build_worker_audit_payload(
                phase="completed",
                provenance=provenance,
                recorded_at=recorded_at,
                result_handle=result.result_handle(),
            ),
            "summary": completed_payload["summary"],
        },
    )


def build_worker_completed_operation(
    *,
    task_id: int,
    recorded_at: datetime,
    context: WorkerExecutionContext,
    result: TaskExecutionResult,
    actor_id: int | None = None,
) -> TaskExecutionOperation:
    """Build the persisted-task operation for one worker-managed completion."""
    return build_task_execution_operation(
        task_id=task_id,
        actor_id=actor_id,
        transition=build_worker_completed_transition(
            task_id=task_id,
            recorded_at=recorded_at,
            context=context,
            result=result,
        ),
    )


def build_task_failed_mutation(
    *,
    recorded_at: datetime,
    error_payload: Mapping[str, object],
) -> TaskLifecycleMutation:
    """Build the canonical failure mutation for one task."""
    return TaskLifecycleMutation(
        status="failed",
        heartbeat_at=recorded_at,
        completed_at=recorded_at,
        error_payload=_copy_payload(error_payload),
    )


def build_worker_failed_transition(
    *,
    task_id: int,
    recorded_at: datetime,
    context: WorkerExecutionContext,
    exc_type: str,
    message: str,
) -> TaskExecutionTransition:
    """Build the failure transition for one worker-managed task execution."""
    provenance = build_worker_execution_provenance(
        lane=context.lane,
        worker_task_name=context.worker_task_name,
        worker_pid=context.worker_pid,
    )
    error_payload = build_task_failure_payload(
        provenance=provenance,
        exc_type=exc_type,
        message=message,
    )
    return _build_worker_transition(
        phase="failed",
        task_id=task_id,
        worker_task_name=context.worker_task_name,
        mutation=build_task_failed_mutation(
            recorded_at=recorded_at,
            error_payload=error_payload,
        ),
        audit_payload={
            **build_worker_audit_payload(
                phase="failed",
                provenance=provenance,
                recorded_at=recorded_at,
            ),
            "error_code": WORKER_TASK_FAILED_ERROR_CODE,
            "exception_type": exc_type,
            "message": message,
            "summary": error_payload["summary"],
        },
    )


def build_worker_failed_operation(
    *,
    task_id: int,
    recorded_at: datetime,
    context: WorkerExecutionContext,
    exc_type: str,
    message: str,
    actor_id: int | None = None,
) -> TaskExecutionOperation:
    """Build the persisted-task operation for one worker-managed failure."""
    return build_task_execution_operation(
        task_id=task_id,
        actor_id=actor_id,
        transition=build_worker_failed_transition(
            task_id=task_id,
            recorded_at=recorded_at,
            context=context,
            exc_type=exc_type,
            message=message,
        ),
    )


def build_task_success_payload(
    *,
    provenance: WorkerExecutionProvenance,
    summary_payload: dict[str, object],
    result_handle: TaskResultHandle,
) -> dict[str, object]:
    """Build the persisted progress payload for a successfully completed task."""
    details: dict[str, object] = {
        **summary_payload,
        **provenance.to_payload(),
    }
    payload: dict[str, object] = {
        "contract_version": EXECUTION_CONTRACT_VERSION,
        "phase": "completed",
        "summary": f"{_lane_task_label(provenance.lane)} completed.",
        "recorded_at": provenance.completed_at,
        "stage_label": provenance.worker_task_name,
        "details": details,
        "lane": provenance.lane,
        "worker_task_name": provenance.worker_task_name,
        **summary_payload,
    }
    if not result_handle.is_empty():
        payload["result_refs"] = result_handle.to_payload()
    return payload


def build_task_failure_payload(
    *,
    provenance: WorkerExecutionProvenance,
    exc_type: str,
    message: str,
) -> dict[str, object]:
    """Build the persisted error payload for a failed task."""
    summary = f"{_lane_task_label(provenance.lane)} failed."
    failure_excerpt = _first_failure_line(message)
    if failure_excerpt:
        summary = f"{summary} {failure_excerpt}"
    return {
        "contract_version": EXECUTION_CONTRACT_VERSION,
        "phase": "failed",
        "error_code": WORKER_TASK_FAILED_ERROR_CODE,
        "summary": summary,
        "details": {
            **provenance.to_payload(),
            "exception_type": exc_type,
            "message": message,
        },
    }


def build_task_crash_payload(
    *,
    provenance: WorkerExecutionProvenance,
) -> dict[str, object]:
    """Build the persisted heartbeat payload for an intentional worker crash."""
    return {
        "contract_version": EXECUTION_CONTRACT_VERSION,
        "phase": "crashing",
        **provenance.to_payload(),
    }


def build_worker_audit_payload(
    *,
    phase: ExecutionPhase,
    provenance: WorkerExecutionProvenance,
    recorded_at: datetime | None = None,
    result_handle: TaskResultHandle | None = None,
) -> dict[str, object]:
    """Build canonical audit payload metadata for one worker lifecycle event."""
    payload: dict[str, object] = {
        "contract_version": EXECUTION_CONTRACT_VERSION,
        "phase": phase,
        **provenance.to_payload(),
    }
    if recorded_at is not None:
        payload["recorded_at"] = recorded_at.isoformat()
    if result_handle is not None and not result_handle.is_empty():
        payload["result_refs"] = result_handle.to_payload()
    return payload


def build_execution_event_log(
    *,
    action_kind: ExecutionEventKind,
    resource_kind: ExecutionEventResourceKind,
    resource_id: int | str,
    summary: str,
    payload: Mapping[str, object] | None = None,
) -> ExecutionEventLog:
    """Build the canonical persisted execution-event envelope."""
    return ExecutionEventLog(
        action_kind=action_kind,
        resource_kind=resource_kind,
        resource_id=str(resource_id),
        summary=summary,
        payload=_copy_payload(payload) or {},
    )


def coerce_task_execution_history_metadata(
    metadata: Mapping[str, object] | None,
) -> dict[str, TaskExecutionHistoryMetadataValue]:
    """Coerce persisted event metadata into the primitive-safe history contract."""
    if metadata is None:
        return {}
    coerced: dict[str, TaskExecutionHistoryMetadataValue] = {}
    for key, value in metadata.items():
        if isinstance(value, list):
            coerced[key] = [str(item) for item in value]
        elif isinstance(value, (str, int, bool)) or value is None:
            coerced[key] = value
        else:
            coerced[key] = str(value)
    return coerced


def build_task_submission_history_metadata(
    context: TaskExecutionHistoryContext,
) -> dict[str, TaskExecutionHistoryMetadataValue]:
    """Build canonical metadata for one task submission event."""
    return {
        "task_status": "queued",
        "dispatch_status": context.dispatch_status,
        "dispatch_key": context.dispatch_key,
        "submission_source": context.submission_source,
        "worker_task_name": context.worker_task_name,
        "dataset_id": context.dataset_id,
        "definition_id": context.definition_id,
    }


def build_task_lifecycle_history_metadata(
    context: TaskExecutionHistoryContext,
) -> dict[str, TaskExecutionHistoryMetadataValue]:
    """Build canonical metadata for one lifecycle projection event."""
    metadata: dict[str, TaskExecutionHistoryMetadataValue] = {
        "task_status": context.task_status,
        "dispatch_status": context.dispatch_status,
        "dispatch_key": context.dispatch_key,
        "progress_percent_complete": context.progress_percent_complete,
        "worker_task_name": context.worker_task_name,
        "result_handle_ids": list(context.result_handle_ids),
    }
    if context.task_status in {"cancellation_requested", "cancelling", "cancelled"}:
        metadata["control_action"] = "cancel"
        metadata["requested_state"] = "cancellation_requested"
        metadata["control_phase"] = _control_phase_for_state(context.task_status)
        if context.task_status == "cancelled":
            metadata["terminal_state"] = "cancelled"
    elif context.task_status in {"termination_requested", "terminated"}:
        metadata["control_action"] = "terminate"
        metadata["requested_state"] = "termination_requested"
        metadata["control_phase"] = _control_phase_for_state(context.task_status)
        if context.task_status == "terminated":
            metadata["terminal_state"] = "terminated"
    return metadata


def build_task_control_history_metadata(
    *,
    decision: TaskControlDecision,
    lineage: TaskRetryLineage | None = None,
) -> dict[str, TaskExecutionHistoryMetadataValue]:
    """Build canonical metadata for one task control request event."""
    metadata = coerce_task_execution_history_metadata(decision.to_payload())
    metadata["control_action"] = decision.action
    if decision.accepted and decision.action == "cancel":
        metadata["requested_state"] = "cancellation_requested"
        metadata["control_phase"] = "requested"
    elif decision.accepted and decision.action == "terminate":
        metadata["requested_state"] = "termination_requested"
        metadata["control_phase"] = "requested"
    elif decision.accepted and decision.action == "retry":
        metadata["control_phase"] = "requested"
    if lineage is not None:
        metadata.update(_build_retry_lineage_history_metadata(lineage))
    return metadata


def build_task_submission_history_event(
    context: TaskExecutionHistoryContext,
) -> TaskExecutionHistoryEvent:
    """Build the canonical task-submission history entry."""
    return TaskExecutionHistoryEvent(
        event_key=f"task_submitted:{context.submitted_at}",
        event_type="task_submitted",
        level="info",
        occurred_at=context.submitted_at,
        message="Task submission accepted by local runtime.",
        metadata=build_task_submission_history_metadata(context),
    )


def build_task_execution_history_context(
    *,
    task_status: TaskLifecycleStatus,
    submitted_at: str,
    progress_updated_at: str,
    progress_percent_complete: int,
    dispatch: TaskDispatchRecord,
    worker_task_name: WorkerTaskName,
    dataset_id: str | None,
    definition_id: int | None,
    result_handle_ids: Sequence[str] = (),
) -> TaskExecutionHistoryContext:
    """Build the canonical task-history context from one task snapshot."""
    return TaskExecutionHistoryContext(
        task_status=task_status,
        submitted_at=canonicalize_execution_timestamp(submitted_at),
        progress_updated_at=canonicalize_execution_timestamp(progress_updated_at),
        progress_percent_complete=progress_percent_complete,
        dispatch=dispatch,
        worker_task_name=worker_task_name,
        dataset_id=dataset_id,
        definition_id=definition_id,
        result_handle_ids=tuple(str(handle_id) for handle_id in result_handle_ids),
    )


def build_task_lifecycle_history_event(
    context: TaskExecutionHistoryContext,
) -> TaskExecutionHistoryEvent | None:
    """Build one lifecycle history entry from the current persisted task state."""
    if context.task_status in {"queued", "dispatching"}:
        return None
    if context.task_status == "running":
        event_type: TaskExecutionHistoryEventType = "task_running"
        level: TaskExecutionHistoryLevel = "info"
        message = "Task entered the running state."
    elif context.task_status in {"cancellation_requested", "cancelling", "cancelled"}:
        event_type = "task_cancel_requested"
        level = "warning"
        message = "Task entered the cancel-control path."
    elif context.task_status in {"termination_requested", "terminated"}:
        event_type = "task_terminate_requested"
        level = "warning"
        message = "Task entered the terminate-control path."
    elif context.task_status == "completed":
        event_type = "task_completed"
        level = "info"
        message = "Task completed and persisted result metadata."
    else:
        event_type = "task_failed"
        level = "error"
        message = "Task entered the failed state."
    return TaskExecutionHistoryEvent(
        event_key=f"{event_type}:{context.progress_updated_at}",
        event_type=event_type,
        level=level,
        occurred_at=context.progress_updated_at,
        message=message,
        metadata=build_task_lifecycle_history_metadata(context),
    )


def build_task_execution_history(
    context: TaskExecutionHistoryContext,
) -> tuple[TaskExecutionHistoryEvent, ...]:
    """Build the canonical task-history list for one persisted task snapshot."""
    events = [build_task_submission_history_event(context)]
    lifecycle_event = build_task_lifecycle_history_event(context)
    if lifecycle_event is not None:
        events.append(lifecycle_event)
    return tuple(events)


def normalize_task_history_event_metadata(
    event_type: TaskExecutionHistoryEventType,
    metadata: Mapping[str, object] | None,
) -> TaskHistoryEventMetadataNormalization:
    """Normalize one task-history metadata payload into the canonical core shape."""
    normalized = coerce_task_execution_history_metadata(metadata)
    missing_fields: list[str] = []
    normalized_fields: list[str] = []

    if event_type == "task_submitted":
        _normalize_history_field(
            normalized,
            "task_status",
            fallback="queued",
            normalized_fields=normalized_fields,
        )
        _extend_missing_fields(
            normalized,
            missing_fields,
            "dispatch_status",
            "dispatch_key",
            "submission_source",
            "worker_task_name",
        )
    elif event_type in {"task_running", "task_completed", "task_failed"}:
        _normalize_history_field(
            normalized,
            "task_status",
            fallback=_task_status_for_history_event_type(event_type),
            normalized_fields=normalized_fields,
        )
        _normalize_history_field(
            normalized,
            "result_handle_ids",
            fallback=[],
            normalized_fields=normalized_fields,
        )
        _extend_missing_fields(
            normalized,
            missing_fields,
            "dispatch_status",
            "dispatch_key",
            "progress_percent_complete",
            "worker_task_name",
        )
    elif event_type in {"task_cancel_requested", "task_terminate_requested"}:
        action = "cancel" if event_type == "task_cancel_requested" else "terminate"
        requested_state = (
            "cancellation_requested"
            if action == "cancel"
            else "termination_requested"
        )
        _normalize_history_field(
            normalized,
            "control_action",
            fallback=action,
            normalized_fields=normalized_fields,
        )
        _normalize_history_field(
            normalized,
            "requested_state",
            fallback=requested_state,
            normalized_fields=normalized_fields,
        )
        inferred_phase = _infer_control_phase_from_history_metadata(
            event_type=event_type,
            metadata=normalized,
        )
        if inferred_phase is not None and "control_phase" not in normalized:
            normalized["control_phase"] = inferred_phase
            normalized_fields.append("control_phase")
        if normalized.get("task_status") in {"cancelled", "terminated"} and "terminal_state" not in normalized:
            normalized["terminal_state"] = normalized["task_status"]
            normalized_fields.append("terminal_state")
        if "control_phase" not in normalized:
            missing_fields.append("control_phase")
    elif event_type == "task_retried":
        _normalize_history_field(
            normalized,
            "control_action",
            fallback="retry",
            normalized_fields=normalized_fields,
        )
        _normalize_history_field(
            normalized,
            "creates_new_task_lineage",
            fallback=True,
            normalized_fields=normalized_fields,
        )
        _normalize_history_field(
            normalized,
            "control_phase",
            fallback="requested",
            normalized_fields=normalized_fields,
        )
        _extend_missing_fields(
            normalized,
            missing_fields,
            "retry_source_task_id",
            "retry_root_task_id",
            "retry_parent_task_id",
            "retry_attempt",
            "retry_source_terminal_state",
        )

    return TaskHistoryEventMetadataNormalization(
        metadata=normalized,
        missing_fields=tuple(sorted(set(missing_fields))),
        normalized_fields=tuple(sorted(set(normalized_fields))),
    )


def validate_task_history_event_metadata(
    event_type: TaskExecutionHistoryEventType,
    metadata: Mapping[str, object] | None,
) -> dict[str, TaskExecutionHistoryMetadataValue]:
    """Validate one task-history metadata payload and return its canonical form."""
    return canonicalize_task_history_event_metadata(
        event_type,
        metadata,
        require_complete=True,
    )


def canonicalize_task_history_event_metadata(
    event_type: TaskExecutionHistoryEventType,
    metadata: Mapping[str, object] | None,
    *,
    require_complete: bool = False,
) -> dict[str, TaskExecutionHistoryMetadataValue]:
    """Normalize one task-history metadata payload and optionally require completeness."""
    normalized = normalize_task_history_event_metadata(event_type, metadata)
    if require_complete and not normalized.is_complete:
        missing = ", ".join(normalized.missing_fields)
        raise ValueError(
            f"Task history metadata for '{event_type}' is missing required fields: {missing}"
        )
    return dict(normalized.metadata)


def project_task_runtime_state_from_history(
    history_events: Sequence[TaskExecutionHistoryEvent],
    *,
    initial_state: TaskRuntimeState = "queued",
) -> TaskRuntimeState:
    """Project the canonical runtime state from persisted task-history events."""
    projected_state = initial_state
    for event in _sort_task_history_events(history_events):
        next_state = _task_runtime_state_from_normalized_metadata(
            event_type=event.event_type,
            metadata=canonicalize_task_history_event_metadata(
                event.event_type,
                event.metadata,
            ),
        )
        if next_state is None:
            continue
        if is_terminal_task_state(projected_state) and next_state != projected_state:
            continue
        projected_state = next_state
    return projected_state


def project_task_control_transition(
    history_events: Sequence[TaskExecutionHistoryEvent],
    *,
    runtime_state: TaskRuntimeState | None = None,
) -> TaskControlRuntimeProjection | None:
    """Project one accepted control request into a stable runtime control view."""
    ordered_events = _sort_task_history_events(history_events)
    projected_runtime_state = (
        runtime_state
        if runtime_state is not None
        else project_task_runtime_state_from_history(ordered_events)
    )
    accepted_control_event: TaskExecutionHistoryEvent | None = None
    for event in reversed(ordered_events):
        if event.event_type not in {
            "task_cancel_requested",
            "task_terminate_requested",
            "task_retried",
        }:
            continue
        normalized_event = canonicalize_task_history_event_metadata(
            event.event_type,
            event.metadata,
        )
        if _optional_task_control_outcome(normalized_event.get("outcome")) == "accepted" and (
            _control_event_matches_runtime_state(
                event_type=event.event_type,
                metadata=normalized_event,
                runtime_state=projected_runtime_state,
            )
        ):
            accepted_control_event = event
            break
    if accepted_control_event is None:
        return None

    normalized_control_event = canonicalize_task_history_event_metadata(
        accepted_control_event.event_type,
        accepted_control_event.metadata,
    )
    action = _control_action_from_normalized_metadata(
        event_type=accepted_control_event.event_type,
        metadata=normalized_control_event,
    )
    requested_state = _requested_state_from_normalized_metadata(
        metadata=normalized_control_event,
        action=action,
    )

    acknowledged_at: str | None = None
    terminal_at: str | None = None
    for event in ordered_events:
        if _event_precedes(event, accepted_control_event):
            continue
        normalized_event = canonicalize_task_history_event_metadata(
            event.event_type,
            event.metadata,
        )
        event_state = _task_runtime_state_from_normalized_metadata(
            event_type=event.event_type,
            metadata=normalized_event,
        )
        if event_state is None:
            continue
        if action == "cancel":
            if acknowledged_at is None and event_state in {"cancelling", "cancelled"}:
                acknowledged_at = event.occurred_at
            if terminal_at is None and event_state == "cancelled":
                terminal_at = event.occurred_at
        elif action == "terminate":
            if acknowledged_at is None and event_state == "terminated":
                acknowledged_at = event.occurred_at
            if terminal_at is None and event_state == "terminated":
                terminal_at = event.occurred_at
        else:
            acknowledged_at = accepted_control_event.occurred_at
            if projected_runtime_state in TERMINAL_TASK_STATES:
                terminal_at = accepted_control_event.occurred_at
            break

    if action == "cancel" and projected_runtime_state in {"cancelling", "cancelled"}:
        acknowledged_at = acknowledged_at or accepted_control_event.occurred_at
    if action == "cancel" and projected_runtime_state == "cancelled":
        terminal_at = terminal_at or acknowledged_at or accepted_control_event.occurred_at
    if action == "terminate" and projected_runtime_state == "terminated":
        acknowledged_at = acknowledged_at or accepted_control_event.occurred_at
        terminal_at = terminal_at or accepted_control_event.occurred_at

    return TaskControlRuntimeProjection(
        action=action,
        runtime_state=projected_runtime_state,
        requested_state=requested_state,
        requested_at=accepted_control_event.occurred_at,
        acknowledged_at=acknowledged_at,
        terminal_at=terminal_at,
        creates_new_task_lineage=bool(
            normalized_control_event.get("creates_new_task_lineage", False)
        ),
    )


def build_task_control_history_event(
    *,
    decision: TaskControlDecision,
    occurred_at: datetime,
    lineage: TaskRetryLineage | None = None,
) -> TaskExecutionHistoryEvent:
    """Build the canonical task-history entry for one control request."""
    event_type: TaskExecutionHistoryEventType
    message: str
    if decision.action == "cancel":
        event_type = "task_cancel_requested"
        message = (
            "Task cancel request accepted."
            if decision.accepted
            else "Task cancel request rejected."
        )
    elif decision.action == "terminate":
        event_type = "task_terminate_requested"
        message = (
            "Task terminate request accepted."
            if decision.accepted
            else "Task terminate request rejected."
        )
    else:
        event_type = "task_retried"
        message = "Task retry accepted." if decision.accepted else "Task retry rejected."

    return TaskExecutionHistoryEvent(
        event_key=f"{event_type}:{occurred_at.isoformat()}",
        event_type=event_type,
        level="info" if decision.accepted else "warning",
        occurred_at=occurred_at.isoformat(),
        message=message,
        metadata=build_task_control_history_metadata(
            decision=decision,
            lineage=lineage,
        ),
    )


def build_task_control_history_pair(
    *,
    task_id: int,
    decision: TaskControlDecision,
    occurred_at: datetime,
    lineage: TaskRetryLineage | None = None,
    runtime_metadata: Mapping[str, object] | None = None,
) -> TaskControlHistoryPair:
    """Build paired history and audit artifacts for one control request."""
    return TaskControlHistoryPair(
        history_event=build_task_control_history_event(
            decision=decision,
            occurred_at=occurred_at,
            lineage=lineage,
        ),
        event_log=build_task_control_event_log(
            task_id=task_id,
            decision=decision,
            recorded_at=occurred_at,
            lineage=lineage,
            runtime_metadata=runtime_metadata,
        ),
    )


def audit_action_for_phase(phase: ExecutionPhase) -> TaskExecutionAuditActionKind:
    """Map one execution phase to the canonical worker audit action kind."""
    if phase == "running":
        return "worker.task_started"
    if phase == "completed":
        return "worker.task_completed"
    if phase == "failed":
        return "worker.task_failed"
    if phase == "cancel_requested":
        return "task.cancel_requested"
    if phase == "terminate_requested":
        return "task.terminate_requested"
    if phase == "retried":
        return "task.retried"
    return "worker.task_crashing"


def build_worker_audit_summary(
    *,
    phase: ExecutionPhase,
    worker_task_name: WorkerTaskName,
    task_id: int,
) -> str:
    """Build the canonical worker audit summary line for one task phase."""
    if phase == "running":
        return f"Worker started {worker_task_name} for task {task_id}"
    if phase == "completed":
        return f"Worker completed {worker_task_name} for task {task_id}"
    if phase == "failed":
        return f"Worker failed {worker_task_name} for task {task_id}"
    return f"Worker is about to crash while running {worker_task_name} for task {task_id}"


def build_task_control_audit_payload(
    *,
    decision: TaskControlDecision,
    recorded_at: datetime,
    lineage: TaskRetryLineage | None = None,
    runtime_metadata: Mapping[str, object] | None = None,
) -> dict[str, object]:
    """Build a redaction-safe audit payload for one task control request."""
    decision_payload = dict(decision.to_payload())
    decision_payload.pop("contract_version", None)
    payload: dict[str, object] = {
        "contract_version": EXECUTION_CONTRACT_VERSION,
        "recorded_at": recorded_at.isoformat(),
        "outcome": decision.outcome,
        **decision_payload,
    }
    sanitized_runtime_metadata = sanitize_processor_runtime_metadata(runtime_metadata)
    if sanitized_runtime_metadata:
        payload["runtime_metadata"] = sanitized_runtime_metadata
    if lineage is not None:
        payload["retry_lineage"] = lineage.to_payload()
    return payload


def build_task_control_event_log(
    *,
    task_id: int,
    decision: TaskControlDecision,
    recorded_at: datetime,
    lineage: TaskRetryLineage | None = None,
    runtime_metadata: Mapping[str, object] | None = None,
) -> ExecutionEventLog:
    """Build the canonical execution-event envelope for one task control action."""
    phase: ExecutionPhase
    summary: str
    if decision.action == "cancel":
        phase = "cancel_requested"
        summary = (
            f"Cancel request accepted for task {task_id}"
            if decision.accepted
            else f"Cancel request rejected for task {task_id}"
        )
    elif decision.action == "terminate":
        phase = "terminate_requested"
        summary = (
            f"Terminate request accepted for task {task_id}"
            if decision.accepted
            else f"Terminate request rejected for task {task_id}"
        )
    else:
        phase = "retried"
        summary = (
            f"Retry accepted for task {task_id}"
            if decision.accepted
            else f"Retry rejected for task {task_id}"
        )
    return build_execution_event_log(
        action_kind=audit_action_for_phase(phase),
        resource_kind="task",
        resource_id=task_id,
        summary=summary,
        payload=build_task_control_audit_payload(
            decision=decision,
            recorded_at=recorded_at,
            lineage=lineage,
            runtime_metadata=runtime_metadata,
        ),
    )


def build_reconcile_stale_task_transition(
    *,
    task_id: int,
    recorded_at: datetime,
    stale_before: datetime,
) -> TaskExecutionTransition:
    """Build the reconcile transition for one stale running task."""
    stale_before_iso = stale_before.isoformat()
    return TaskExecutionTransition(
        mutation=build_task_failed_mutation(
            recorded_at=recorded_at,
            error_payload={
                "error_code": STALE_TASK_TIMEOUT_ERROR_CODE,
                "summary": "Task marked failed during reconcile.",
                "details": {
                    "stale_before": stale_before_iso,
                },
            },
        ),
        event_log=build_execution_event_log(
            action_kind="reconcile.task_failed",
            resource_kind="task",
            resource_id=task_id,
            summary=f"Reconciled stale task {task_id}",
            payload={
                "contract_version": EXECUTION_CONTRACT_VERSION,
                "phase": "failed",
                "error_code": STALE_TASK_TIMEOUT_ERROR_CODE,
                "recorded_at": recorded_at.isoformat(),
                "stale_before": stale_before_iso,
            },
        ),
    )


def build_reconcile_stale_task_operation(
    *,
    task_id: int,
    recorded_at: datetime,
    stale_before: datetime,
    actor_id: int | None = None,
) -> TaskExecutionOperation:
    """Build the persisted-task operation for one stale-task reconcile failure."""
    return build_task_execution_operation(
        task_id=task_id,
        actor_id=actor_id,
        transition=build_reconcile_stale_task_transition(
            task_id=task_id,
            recorded_at=recorded_at,
            stale_before=stale_before,
        ),
    )


def build_reconcile_batch_failed_event(
    *,
    batch_id: int,
    recorded_at: datetime,
    stale_before: datetime,
) -> ExecutionEventLog:
    """Build the canonical execution-event log for one reconciled orphan batch."""
    return build_execution_event_log(
        action_kind="reconcile.batch_failed",
        resource_kind="trace_batch",
        resource_id=batch_id,
        summary=f"Reconciled orphan batch {batch_id}",
        payload={
            "contract_version": EXECUTION_CONTRACT_VERSION,
            "phase": "failed",
            "recorded_at": recorded_at.isoformat(),
            "stale_before": stale_before.isoformat(),
        },
    )


def build_worker_crashing_transition(
    *,
    task_id: int,
    recorded_at: datetime,
    context: WorkerExecutionContext,
) -> TaskExecutionTransition:
    """Build the crashing transition for one worker-managed task execution."""
    provenance = build_worker_execution_provenance(
        lane=context.lane,
        worker_task_name=context.worker_task_name,
        worker_pid=context.worker_pid,
        crash_requested_at=recorded_at,
    )
    return _build_worker_transition(
        phase="crashing",
        task_id=task_id,
        worker_task_name=context.worker_task_name,
        mutation=build_task_running_mutation(
            recorded_at=recorded_at,
            progress_payload=build_task_crash_payload(provenance=provenance),
        ),
        audit_payload=build_worker_audit_payload(
            phase="crashing",
            provenance=provenance,
            recorded_at=recorded_at,
        ),
    )


def build_worker_crashing_operation(
    *,
    task_id: int,
    recorded_at: datetime,
    context: WorkerExecutionContext,
    actor_id: int | None = None,
) -> TaskExecutionOperation:
    """Build the persisted-task operation for one worker crash-prep transition."""
    return build_task_execution_operation(
        task_id=task_id,
        actor_id=actor_id,
        transition=build_worker_crashing_transition(
            task_id=task_id,
            recorded_at=recorded_at,
            context=context,
        ),
    )


def _build_worker_transition(
    *,
    phase: ExecutionPhase,
    task_id: int,
    worker_task_name: WorkerTaskName,
    mutation: TaskLifecycleMutation,
    audit_payload: Mapping[str, object],
) -> TaskExecutionTransition:
    return TaskExecutionTransition(
        mutation=mutation,
        event_log=build_execution_event_log(
            action_kind=audit_action_for_phase(phase),
            resource_kind="task",
            resource_id=task_id,
            summary=build_worker_audit_summary(
                phase=phase,
                worker_task_name=worker_task_name,
                task_id=task_id,
            ),
            payload=audit_payload,
        ),
    )


def _optional_int(value: object) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool):
        raise ValueError("Expected integer-compatible value.")
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        text = value.strip()
        if text:
            return int(text)
    raise ValueError("Expected integer-compatible value.")


def canonicalize_utc_datetime(value: datetime) -> datetime:
    """Normalize one datetime into a timezone-aware UTC instant."""
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def canonicalize_execution_timestamp(value: datetime | str) -> str:
    """Normalize one execution timestamp into a canonical UTC ISO-8601 string."""
    if isinstance(value, datetime):
        return canonicalize_utc_datetime(value).isoformat()
    text = str(value).strip()
    if not text:
        raise ValueError("Execution timestamps must not be empty.")
    normalized_text = text[:-1] + "+00:00" if text.endswith("Z") else text
    return canonicalize_utc_datetime(datetime.fromisoformat(normalized_text)).isoformat()


def _optional_isoformat(value: datetime | None) -> str | None:
    if value is None:
        return None
    return canonicalize_execution_timestamp(value)


def _copy_payload(payload: Mapping[str, object] | None) -> dict[str, object] | None:
    if payload is None:
        return None
    return dict(payload)


def _build_retry_lineage_history_metadata(
    lineage: TaskRetryLineage,
) -> dict[str, TaskExecutionHistoryMetadataValue]:
    return {
        "retry_source_task_id": lineage.source_task_id,
        "retry_root_task_id": lineage.root_task_id,
        "retry_parent_task_id": lineage.parent_task_id,
        "retry_attempt": lineage.retry_attempt,
        "retry_source_terminal_state": lineage.source_terminal_state,
    }


def _control_phase_for_state(state: TaskRuntimeState) -> TaskHistoryControlPhase:
    if state in {"cancellation_requested", "termination_requested"}:
        return "requested"
    if state == "cancelling":
        return "acknowledged"
    return "terminal"


def _infer_control_phase_from_history_metadata(
    *,
    event_type: TaskExecutionHistoryEventType,
    metadata: Mapping[str, TaskExecutionHistoryMetadataValue],
) -> TaskHistoryControlPhase | None:
    task_status = metadata.get("task_status")
    if task_status in {
        "cancellation_requested",
        "cancelling",
        "cancelled",
        "termination_requested",
        "terminated",
    }:
        return _control_phase_for_state(task_status)
    if _optional_task_control_outcome(metadata.get("outcome")) == "accepted" and event_type in {
        "task_cancel_requested",
        "task_terminate_requested",
        "task_retried",
    }:
        return "requested"
    return None


def _normalize_history_field(
    metadata: dict[str, TaskExecutionHistoryMetadataValue],
    field_name: str,
    *,
    fallback: TaskExecutionHistoryMetadataValue,
    normalized_fields: list[str],
) -> None:
    if field_name in metadata:
        return
    metadata[field_name] = fallback
    normalized_fields.append(field_name)


def _extend_missing_fields(
    metadata: Mapping[str, TaskExecutionHistoryMetadataValue],
    missing_fields: list[str],
    *field_names: str,
) -> None:
    for field_name in field_names:
        if field_name not in metadata:
            missing_fields.append(field_name)


def _task_status_for_history_event_type(
    event_type: TaskExecutionHistoryEventType,
) -> TaskRuntimeState:
    if event_type == "task_submitted":
        return "queued"
    if event_type == "task_running":
        return "running"
    if event_type == "task_completed":
        return "completed"
    if event_type == "task_failed":
        return "failed"
    raise ValueError(f"Event type '{event_type}' does not map to one task status.")


def _sort_task_history_events(
    history_events: Sequence[TaskExecutionHistoryEvent],
) -> tuple[TaskExecutionHistoryEvent, ...]:
    return tuple(sorted(history_events, key=lambda event: (event.occurred_at, event.event_key)))


def _event_precedes(
    event: TaskExecutionHistoryEvent,
    anchor: TaskExecutionHistoryEvent,
) -> bool:
    return (event.occurred_at, event.event_key) < (anchor.occurred_at, anchor.event_key)


def _task_runtime_state_from_normalized_metadata(
    *,
    event_type: TaskExecutionHistoryEventType,
    metadata: Mapping[str, object],
) -> TaskRuntimeState | None:
    task_status = metadata.get("task_status")
    if task_status in {
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
    }:
        return task_status
    requested_state = metadata.get("requested_state")
    if requested_state in {
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
    }:
        return requested_state
    if event_type == "task_submitted":
        return "queued"
    if event_type == "task_running":
        return "running"
    if event_type == "task_completed":
        return "completed"
    if event_type == "task_failed":
        return "failed"
    return None


def _optional_task_control_outcome(value: object) -> TaskControlOutcome | None:
    if value in {"accepted", "rejected"}:
        return value
    return None


def _control_action_from_normalized_metadata(
    *,
    event_type: TaskExecutionHistoryEventType,
    metadata: Mapping[str, object],
) -> TaskControlAction:
    control_action = metadata.get("control_action")
    if control_action in {"cancel", "terminate", "retry"}:
        return control_action
    if event_type == "task_cancel_requested":
        return "cancel"
    if event_type == "task_terminate_requested":
        return "terminate"
    return "retry"


def _requested_state_from_normalized_metadata(
    *,
    metadata: Mapping[str, object],
    action: TaskControlAction,
) -> TaskRuntimeState | None:
    requested_state = metadata.get("requested_state")
    if requested_state in {
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
    }:
        return requested_state
    if action == "cancel":
        return "cancellation_requested"
    if action == "terminate":
        return "termination_requested"
    return None


def _control_event_matches_runtime_state(
    *,
    event_type: TaskExecutionHistoryEventType,
    metadata: Mapping[str, object],
    runtime_state: TaskRuntimeState,
) -> bool:
    action = _control_action_from_normalized_metadata(
        event_type=event_type,
        metadata=metadata,
    )
    if action == "cancel":
        return runtime_state in {"cancellation_requested", "cancelling", "cancelled"}
    if action == "terminate":
        return runtime_state in {"termination_requested", "terminated"}
    return runtime_state in TERMINAL_TASK_STATES
