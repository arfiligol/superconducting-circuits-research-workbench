from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
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
TaskQueueBackend = Literal["rq_redis"]
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
TaskBrowseStatusFilter = Literal["active", "recent", "all"]
TaskPublicationState = Literal["not_published", "published"]
TaskDispatchStatus = _TaskDispatchStatus
task_submission_source_for = _task_submission_source_for


@dataclass(frozen=True)
class SimulationFrequencySweep:
    start_ghz: float
    stop_ghz: float
    point_count: int
    spacing: Literal["linear", "log"] = "linear"

    def to_mapping(self) -> dict[str, object]:
        return {
            "start_ghz": self.start_ghz,
            "stop_ghz": self.stop_ghz,
            "point_count": self.point_count,
            "spacing": self.spacing,
        }

    @classmethod
    def from_mapping(cls, payload: Mapping[str, object]) -> SimulationFrequencySweep:
        return cls(
            start_ghz=float(payload["start_ghz"]),
            stop_ghz=float(payload["stop_ghz"]),
            point_count=int(payload["point_count"]),
            spacing=cast(Literal["linear", "log"], payload.get("spacing", "linear")),
        )


@dataclass(frozen=True)
class SimulationParameterSweep:
    parameter: str
    values: tuple[float, ...]
    unit: str | None = None

    def to_mapping(self) -> dict[str, object]:
        return {
            "parameter": self.parameter,
            "values": list(self.values),
            "unit": self.unit,
        }

    @classmethod
    def from_mapping(cls, payload: Mapping[str, object]) -> SimulationParameterSweep:
        raw_values = payload.get("values", ())
        values = tuple(float(value) for value in raw_values) if isinstance(raw_values, list) else ()
        return cls(
            parameter=str(payload["parameter"]),
            values=values,
            unit=str(payload["unit"]) if isinstance(payload.get("unit"), str) else None,
        )


@dataclass(frozen=True)
class SimulationHarmonicBalanceSettings:
    enabled: bool
    harmonic_count: int | None = None
    oversample_factor: int | None = None

    def to_mapping(self) -> dict[str, object]:
        return {
            "enabled": self.enabled,
            "harmonic_count": self.harmonic_count,
            "oversample_factor": self.oversample_factor,
        }

    @classmethod
    def from_mapping(
        cls,
        payload: Mapping[str, object],
    ) -> SimulationHarmonicBalanceSettings:
        harmonic_count = payload.get("harmonic_count")
        oversample_factor = payload.get("oversample_factor")
        return cls(
            enabled=bool(payload.get("enabled", False)),
            harmonic_count=int(harmonic_count) if isinstance(harmonic_count, int | float) else None,
            oversample_factor=(
                int(oversample_factor) if isinstance(oversample_factor, int | float) else None
            ),
        )


@dataclass(frozen=True)
class SimulationSolverSettings:
    solver_family: str
    max_iterations: int
    convergence_tolerance: float
    harmonic_balance: SimulationHarmonicBalanceSettings | None = None

    def to_mapping(self) -> dict[str, object]:
        return {
            "solver_family": self.solver_family,
            "max_iterations": self.max_iterations,
            "convergence_tolerance": self.convergence_tolerance,
            "harmonic_balance": (
                self.harmonic_balance.to_mapping()
                if self.harmonic_balance is not None
                else None
            ),
        }

    @classmethod
    def from_mapping(cls, payload: Mapping[str, object]) -> SimulationSolverSettings:
        harmonic_balance = payload.get("harmonic_balance")
        return cls(
            solver_family=str(payload["solver_family"]),
            max_iterations=int(payload["max_iterations"]),
            convergence_tolerance=float(payload["convergence_tolerance"]),
            harmonic_balance=(
                SimulationHarmonicBalanceSettings.from_mapping(harmonic_balance)
                if isinstance(harmonic_balance, Mapping)
                else None
            ),
        )


@dataclass(frozen=True)
class SimulationSourceSpec:
    source_id: str
    kind: str
    target: str
    amplitude: float
    frequency_ghz: float | None = None
    phase_deg: float | None = None

    def to_mapping(self) -> dict[str, object]:
        return {
            "source_id": self.source_id,
            "kind": self.kind,
            "target": self.target,
            "amplitude": self.amplitude,
            "frequency_ghz": self.frequency_ghz,
            "phase_deg": self.phase_deg,
        }

    @classmethod
    def from_mapping(cls, payload: Mapping[str, object]) -> SimulationSourceSpec:
        frequency_ghz = payload.get("frequency_ghz")
        phase_deg = payload.get("phase_deg")
        return cls(
            source_id=str(payload["source_id"]),
            kind=str(payload["kind"]),
            target=str(payload["target"]),
            amplitude=float(payload["amplitude"]),
            frequency_ghz=float(frequency_ghz)
            if isinstance(frequency_ghz, int | float)
            else None,
            phase_deg=float(phase_deg) if isinstance(phase_deg, int | float) else None,
        )


@dataclass(frozen=True)
class SimulationPtcSetup:
    enabled: bool
    mode: Literal["auto", "manual"]
    compensate_ports: tuple[str, ...]

    def to_mapping(self) -> dict[str, object]:
        return {
            "enabled": self.enabled,
            "mode": self.mode,
            "compensate_ports": list(self.compensate_ports),
        }

    @classmethod
    def from_mapping(cls, payload: Mapping[str, object]) -> SimulationPtcSetup:
        raw_ports = payload.get("compensate_ports", ())
        return cls(
            enabled=bool(payload["enabled"]),
            mode=cast(Literal["auto", "manual"], payload["mode"]),
            compensate_ports=tuple(
                str(port) for port in raw_ports if isinstance(port, str)
            ),
        )


@dataclass(frozen=True)
class SimulationSetup:
    frequency_sweep: SimulationFrequencySweep
    parameter_sweeps: tuple[SimulationParameterSweep, ...]
    solver: SimulationSolverSettings
    sources: tuple[SimulationSourceSpec, ...]
    ptc: SimulationPtcSetup | None = None

    def to_mapping(self) -> dict[str, object]:
        return {
            "frequency_sweep": self.frequency_sweep.to_mapping(),
            "parameter_sweeps": [sweep.to_mapping() for sweep in self.parameter_sweeps],
            "solver": self.solver.to_mapping(),
            "sources": [source.to_mapping() for source in self.sources],
            "ptc": self.ptc.to_mapping() if self.ptc is not None else None,
        }

    @classmethod
    def from_mapping(cls, payload: Mapping[str, object]) -> SimulationSetup:
        parameter_sweeps = payload.get("parameter_sweeps", ())
        sources = payload.get("sources", ())
        ptc = payload.get("ptc")
        return cls(
            frequency_sweep=SimulationFrequencySweep.from_mapping(
                cast(Mapping[str, object], payload["frequency_sweep"])
            ),
            parameter_sweeps=tuple(
                SimulationParameterSweep.from_mapping(cast(Mapping[str, object], sweep))
                for sweep in parameter_sweeps
                if isinstance(sweep, Mapping)
            ),
            solver=SimulationSolverSettings.from_mapping(
                cast(Mapping[str, object], payload["solver"])
            ),
            sources=tuple(
                SimulationSourceSpec.from_mapping(cast(Mapping[str, object], source))
                for source in sources
                if isinstance(source, Mapping)
            ),
            ptc=(
                SimulationPtcSetup.from_mapping(ptc)
                if isinstance(ptc, Mapping)
                else None
            ),
        )


@dataclass(frozen=True)
class PostProcessingTraceSelection:
    trace_family: str
    representation: str
    design_id: str | None = None
    trace_ids: tuple[str, ...] = ()

    def to_mapping(self) -> dict[str, object]:
        return {
            "trace_family": self.trace_family,
            "representation": self.representation,
            "design_id": self.design_id,
            "trace_ids": list(self.trace_ids),
        }

    @classmethod
    def from_mapping(cls, payload: Mapping[str, object]) -> PostProcessingTraceSelection:
        raw_trace_ids = payload.get("trace_ids", ())
        return cls(
            trace_family=str(payload["trace_family"]),
            representation=str(payload["representation"]),
            design_id=(
                str(payload["design_id"])
                if isinstance(payload.get("design_id"), str)
                else None
            ),
            trace_ids=(
                tuple(str(value) for value in raw_trace_ids)
                if isinstance(raw_trace_ids, list)
                else ()
            ),
        )


@dataclass(frozen=True)
class PostProcessingOperation:
    operation: str
    enabled: bool
    config: dict[str, object]

    def to_mapping(self) -> dict[str, object]:
        return {
            "operation": self.operation,
            "enabled": self.enabled,
            "config": dict(self.config),
        }

    @classmethod
    def from_mapping(cls, payload: Mapping[str, object]) -> PostProcessingOperation:
        config = payload.get("config")
        return cls(
            operation=str(payload["operation"]),
            enabled=bool(payload.get("enabled", True)),
            config=dict(config) if isinstance(config, Mapping) else {},
        )


@dataclass(frozen=True)
class PostProcessingSetup:
    selections: tuple[PostProcessingTraceSelection, ...] = ()
    operations: tuple[PostProcessingOperation, ...] = ()

    def to_mapping(self) -> dict[str, object]:
        return {
            "selections": [selection.to_mapping() for selection in self.selections],
            "operations": [operation.to_mapping() for operation in self.operations],
        }

    @classmethod
    def from_mapping(cls, payload: Mapping[str, object]) -> PostProcessingSetup:
        selections = payload.get("selections", ())
        operations = payload.get("operations", ())
        return cls(
            selections=tuple(
                PostProcessingTraceSelection.from_mapping(cast(Mapping[str, object], selection))
                for selection in selections
                if isinstance(selection, Mapping)
            ),
            operations=tuple(
                PostProcessingOperation.from_mapping(cast(Mapping[str, object], operation))
                for operation in operations
                if isinstance(operation, Mapping)
            ),
        )


@dataclass(frozen=True)
class CharacterizationSetup:
    design_id: str
    analysis_id: str
    selected_trace_ids: tuple[str, ...]
    analysis_config: dict[str, object]

    def to_mapping(self) -> dict[str, object]:
        return {
            "design_id": self.design_id,
            "analysis_id": self.analysis_id,
            "selected_trace_ids": list(self.selected_trace_ids),
            "analysis_config": dict(self.analysis_config),
        }

    @classmethod
    def from_mapping(cls, payload: Mapping[str, object]) -> CharacterizationSetup:
        raw_trace_ids = payload.get("selected_trace_ids", ())
        analysis_config = payload.get("analysis_config")
        return cls(
            design_id=str(payload["design_id"]),
            analysis_id=str(payload["analysis_id"]),
            selected_trace_ids=tuple(
                str(trace_id) for trace_id in raw_trace_ids if isinstance(trace_id, str)
            ),
            analysis_config=(
                dict(cast(Mapping[str, object], analysis_config))
                if isinstance(analysis_config, Mapping)
                else {}
            ),
        )


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
class TaskPublicationSummary:
    state: TaskPublicationState
    publish_allowed: bool
    publication_key: str | None = None
    target_dataset_id: str | None = None
    target_design_id: str | None = None
    target_design_name: str | None = None
    published_trace_ids: tuple[str, ...] = ()
    published_at: str | None = None
    source_task_id: int | None = None
    source_result_handle_ids: tuple[str, ...] = ()

    def to_mapping(self) -> dict[str, object]:
        return {
            "state": self.state,
            "publish_allowed": self.publish_allowed,
            "publication_key": self.publication_key,
            "target_dataset_id": self.target_dataset_id,
            "target_design_id": self.target_design_id,
            "target_design_name": self.target_design_name,
            "published_trace_ids": list(self.published_trace_ids),
            "published_at": self.published_at,
            "source_task_id": self.source_task_id,
            "source_result_handle_ids": list(self.source_result_handle_ids),
        }

    @classmethod
    def from_mapping(cls, payload: Mapping[str, object]) -> TaskPublicationSummary:
        raw_trace_ids = payload.get("published_trace_ids", ())
        raw_handle_ids = payload.get("source_result_handle_ids", ())
        return cls(
            state=cast(TaskPublicationState, payload["state"]),
            publish_allowed=bool(payload.get("publish_allowed", False)),
            publication_key=(
                str(payload["publication_key"])
                if isinstance(payload.get("publication_key"), str)
                else None
            ),
            target_dataset_id=(
                str(payload["target_dataset_id"])
                if isinstance(payload.get("target_dataset_id"), str)
                else None
            ),
            target_design_id=(
                str(payload["target_design_id"])
                if isinstance(payload.get("target_design_id"), str)
                else None
            ),
            target_design_name=(
                str(payload["target_design_name"])
                if isinstance(payload.get("target_design_name"), str)
                else None
            ),
            published_trace_ids=tuple(
                str(trace_id) for trace_id in raw_trace_ids if isinstance(trace_id, str)
            ),
            published_at=(
                str(payload["published_at"])
                if isinstance(payload.get("published_at"), str)
                else None
            ),
            source_task_id=(
                int(payload["source_task_id"])
                if isinstance(payload.get("source_task_id"), int)
                else None
            ),
            source_result_handle_ids=tuple(
                str(handle_id) for handle_id in raw_handle_ids if isinstance(handle_id, str)
            ),
        )


@dataclass(frozen=True)
class WorkerLaneSummary:
    lane: TaskLane
    healthy_processors: int
    busy_processors: int
    degraded_processors: int
    draining_processors: int
    offline_processors: int


@dataclass(frozen=True)
class TaskQueueAggregateSummary:
    total: int
    pending: int
    running: int
    completed: int
    failed: int
    cancelled: int
    terminated: int
    result_ready: int


@dataclass(frozen=True)
class TaskProcessorDetail:
    processor_id: str
    lane: TaskLane
    state: Literal["healthy", "busy", "degraded", "draining", "offline"]
    current_task_id: int | None
    last_heartbeat_at: str
    runtime_metadata: dict[str, object]


@dataclass(frozen=True)
class TaskProcessorRuntimeView:
    processors: tuple[TaskProcessorDetail, ...]
    worker_summary: tuple[WorkerLaneSummary, ...]


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
    dataset_id: str | None
    definition_id: int | None
    updated_at: str
    result_availability: TaskResultAvailability
    allowed_actions: TaskAllowedActions


@dataclass(frozen=True)
class TaskQueueView:
    rows: tuple[TaskQueueRow, ...]
    worker_summary: tuple[WorkerLaneSummary, ...]
    aggregate_summary: TaskQueueAggregateSummary
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
    simulation_setup: SimulationSetup | None = None
    publication_summary: TaskPublicationSummary | None = None
    post_processing_setup: PostProcessingSetup | None = None
    characterization_setup: CharacterizationSetup | None = None
    upstream_task_id: int | None = None
    downstream_task_ids: tuple[int, ...] = ()
    control_state: TaskControlState = "none"
    retry_of_task_id: int | None = None
    dispatch: TaskDispatch | None = None
    events: tuple[TaskEvent, ...] = ()


@dataclass(frozen=True)
class TaskListQuery:
    status: TaskStatus | None = None
    status_filter: TaskBrowseStatusFilter = "all"
    lane: TaskLane | None = None
    scope: TaskVisibilityScope = "workspace"
    dataset_id: str | None = None
    search_query: str | None = None
    after: str | None = None
    before: str | None = None
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
    simulation_setup: SimulationSetup | None = None
    post_processing_setup: PostProcessingSetup | None = None
    characterization_setup: CharacterizationSetup | None = None
    upstream_task_id: int | None = None


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
    simulation_setup: SimulationSetup | None = None
    post_processing_setup: PostProcessingSetup | None = None
    characterization_setup: CharacterizationSetup | None = None
    upstream_task_id: int | None = None
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


def resolve_upstream_task_id(events: Sequence[TaskEvent]) -> int | None:
    for event in events:
        upstream_task_id = event.metadata.get("upstream_task_id")
        if isinstance(upstream_task_id, int):
            return upstream_task_id
    return None


def resolve_downstream_task_ids(events: Sequence[TaskEvent]) -> tuple[int, ...]:
    for event in events:
        raw_downstream_task_ids = event.metadata.get("downstream_task_ids")
        if isinstance(raw_downstream_task_ids, list):
            return tuple(
                task_id for task_id in raw_downstream_task_ids if isinstance(task_id, int)
            )
        if isinstance(raw_downstream_task_ids, str):
            parsed = _parse_json_payload(raw_downstream_task_ids)
            if isinstance(parsed, list):
                return tuple(task_id for task_id in parsed if isinstance(task_id, int))
    return ()


def resolve_simulation_setup(events: Sequence[TaskEvent]) -> SimulationSetup | None:
    for event in events:
        payload = event.metadata.get("simulation_setup")
        if isinstance(payload, Mapping):
            return SimulationSetup.from_mapping(payload)
        if isinstance(payload, str):
            parsed = _parse_json_payload(payload)
            if isinstance(parsed, Mapping):
                return SimulationSetup.from_mapping(parsed)
    return None


def resolve_publication_summary(events: Sequence[TaskEvent]) -> TaskPublicationSummary | None:
    for event in events:
        payload = event.metadata.get("publication_summary")
        if isinstance(payload, Mapping):
            return TaskPublicationSummary.from_mapping(payload)
        if isinstance(payload, str):
            parsed = _parse_json_payload(payload)
            if isinstance(parsed, Mapping):
                return TaskPublicationSummary.from_mapping(parsed)
    return None


def resolve_post_processing_setup(events: Sequence[TaskEvent]) -> PostProcessingSetup | None:
    for event in events:
        payload = event.metadata.get("post_processing_setup")
        if isinstance(payload, Mapping):
            return PostProcessingSetup.from_mapping(payload)
        if isinstance(payload, str):
            parsed = _parse_json_payload(payload)
            if isinstance(parsed, Mapping):
                return PostProcessingSetup.from_mapping(parsed)
    return None


def resolve_characterization_setup(
    events: Sequence[TaskEvent],
) -> CharacterizationSetup | None:
    for event in events:
        payload = event.metadata.get("characterization_setup")
        if isinstance(payload, Mapping):
            return CharacterizationSetup.from_mapping(payload)
        if isinstance(payload, str):
            parsed = _parse_json_payload(payload)
            if isinstance(parsed, Mapping):
                return CharacterizationSetup.from_mapping(parsed)
    return None


def _parse_json_payload(payload: str) -> object | None:
    try:
        return json.loads(payload)
    except json.JSONDecodeError:
        return None
