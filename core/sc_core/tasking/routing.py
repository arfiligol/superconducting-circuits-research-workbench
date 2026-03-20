from collections.abc import Mapping
from dataclasses import dataclass
from typing import Literal

LaneName = Literal["simulation", "characterization", "post_processing"]
TaskSubmissionKind = Literal["simulation", "post_processing", "characterization"]
TaskExecutionMode = Literal["run", "smoke"]
TaskDispatchStatus = Literal[
    "accepted",
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
TaskSubmissionSource = Literal["active_dataset", "explicit_dataset", "definition_only"]
TaskDispatchLifecycleStatus = Literal[
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
TASKING_CONTRACT_VERSION = "sc_tasking.v1"
WorkerTaskName = Literal[
    "simulation_run_task",
    "simulation_smoke_task",
    "simulation_failure_task",
    "simulation_crash_task",
    "post_processing_run_task",
    "post_processing_smoke_task",
    "characterization_run_task",
    "characterization_smoke_task",
    "characterization_failure_task",
    "characterization_crash_task",
]


@dataclass(frozen=True)
class WorkerTaskRoute:
    """Canonical route metadata for one persisted task submission."""

    task_kind: TaskSubmissionKind
    lane: LaneName
    worker_task_name: WorkerTaskName
    execution_mode: TaskExecutionMode
    request_ready: bool
    requires_trace_batch: bool


@dataclass(frozen=True)
class WorkerDispatchPlan:
    """Canonical queue-dispatch plan for one persisted task submission."""

    lane: LaneName
    queue_name: str
    worker_task_name: WorkerTaskName
    execution_mode: TaskExecutionMode
    request_ready: bool
    requires_trace_batch: bool
    job_timeout: int = -1
    failure_ttl: int = 86400
    result_ttl: int = 3600


@dataclass(frozen=True)
class TaskDispatchRecord:
    """Canonical dispatch snapshot for one submitted task."""

    dispatch_key: str
    status: TaskDispatchStatus
    submission_source: TaskSubmissionSource
    accepted_at: str
    last_updated_at: str


def extract_parameters_payload(request_payload: Mapping[str, object] | None) -> dict[str, object]:
    """Return a shallow parameters payload from one task request body."""
    if request_payload is None:
        return {}

    raw_parameters = request_payload.get("parameters")
    if not isinstance(raw_parameters, Mapping):
        return {}

    return {key: value for key, value in raw_parameters.items() if isinstance(key, str)}


def resolve_worker_task_route(
    task_kind: TaskSubmissionKind,
    *,
    request_is_valid: bool,
    has_trace_batch_id: bool,
) -> WorkerTaskRoute:
    """Resolve the canonical worker lane and callable name for one task submission."""
    if task_kind == "simulation":
        return _build_route(
            task_kind=task_kind,
            lane="simulation",
            run_task_name="simulation_run_task",
            smoke_task_name="simulation_smoke_task",
            request_is_valid=request_is_valid,
            has_trace_batch_id=has_trace_batch_id,
            requires_trace_batch=True,
        )

    if task_kind == "post_processing":
        return _build_route(
            task_kind=task_kind,
            lane="post_processing",
            run_task_name="post_processing_run_task",
            smoke_task_name="post_processing_smoke_task",
            request_is_valid=request_is_valid,
            has_trace_batch_id=has_trace_batch_id,
            requires_trace_batch=True,
        )

    if task_kind == "characterization":
        return _build_route(
            task_kind=task_kind,
            lane="characterization",
            run_task_name="characterization_run_task",
            smoke_task_name="characterization_smoke_task",
            request_is_valid=request_is_valid,
            has_trace_batch_id=has_trace_batch_id,
            requires_trace_batch=False,
        )

    raise ValueError(f"Unsupported task kind '{task_kind}'.")


def build_worker_dispatch_plan(
    route: WorkerTaskRoute,
    *,
    queue_name: str | None = None,
    job_timeout: int = -1,
    failure_ttl: int = 86400,
    result_ttl: int = 3600,
) -> WorkerDispatchPlan:
    """Build the canonical queue-dispatch plan for one resolved worker route."""
    return WorkerDispatchPlan(
        lane=route.lane,
        queue_name=route.lane if queue_name is None else queue_name,
        worker_task_name=route.worker_task_name,
        execution_mode=route.execution_mode,
        request_ready=route.request_ready,
        requires_trace_batch=route.requires_trace_batch,
        job_timeout=job_timeout,
        failure_ttl=failure_ttl,
        result_ttl=result_ttl,
    )


def task_submission_source_for(
    *,
    submitted_from_active_dataset: bool,
    dataset_id: str | None,
) -> TaskSubmissionSource:
    """Resolve the canonical submission source for one task request."""
    if submitted_from_active_dataset:
        return "active_dataset"
    if dataset_id is not None:
        return "explicit_dataset"
    return "definition_only"


def task_dispatch_status_for(task_status: TaskDispatchLifecycleStatus) -> TaskDispatchStatus:
    """Resolve the canonical dispatch status for one persisted task lifecycle status."""
    if task_status == "queued":
        return "accepted"
    return task_status


def build_task_dispatch_record(
    *,
    task_id: int,
    worker_task_name: WorkerTaskName,
    task_status: TaskDispatchLifecycleStatus,
    submitted_from_active_dataset: bool,
    dataset_id: str | None,
    accepted_at: str,
    last_updated_at: str,
    submission_source: TaskSubmissionSource | None = None,
    current_dispatch: TaskDispatchRecord | None = None,
) -> TaskDispatchRecord:
    """Build the canonical dispatch snapshot for one task detail/read model."""
    return TaskDispatchRecord(
        dispatch_key=(
            current_dispatch.dispatch_key
            if current_dispatch is not None
            else f"dispatch:{task_id}:{worker_task_name}"
        ),
        status=task_dispatch_status_for(task_status),
        submission_source=(
            current_dispatch.submission_source
            if current_dispatch is not None
            else submission_source
            or task_submission_source_for(
                submitted_from_active_dataset=submitted_from_active_dataset,
                dataset_id=dataset_id,
            )
        ),
        accepted_at=current_dispatch.accepted_at if current_dispatch is not None else accepted_at,
        last_updated_at=last_updated_at,
    )


def build_worker_dispatch_payload(dispatch: WorkerDispatchPlan) -> dict[str, object]:
    """Build canonical dispatch metadata for one resolved worker enqueue plan."""
    return {
        "contract_version": TASKING_CONTRACT_VERSION,
        "lane": dispatch.lane,
        "queue_name": dispatch.queue_name,
        "worker_task_name": dispatch.worker_task_name,
        "execution_mode": dispatch.execution_mode,
        "request_ready": dispatch.request_ready,
        "requires_trace_batch": dispatch.requires_trace_batch,
    }


def build_worker_enqueue_kwargs(dispatch: WorkerDispatchPlan) -> dict[str, int]:
    """Build canonical queue-enqueue kwargs for one resolved worker plan."""
    return {
        "job_timeout": dispatch.job_timeout,
        "failure_ttl": dispatch.failure_ttl,
        "result_ttl": dispatch.result_ttl,
    }


def _build_route(
    *,
    task_kind: TaskSubmissionKind,
    lane: LaneName,
    run_task_name: WorkerTaskName,
    smoke_task_name: WorkerTaskName,
    request_is_valid: bool,
    has_trace_batch_id: bool,
    requires_trace_batch: bool,
) -> WorkerTaskRoute:
    request_ready = request_is_valid and (has_trace_batch_id or not requires_trace_batch)
    return WorkerTaskRoute(
        task_kind=task_kind,
        lane=lane,
        worker_task_name=run_task_name if request_ready else smoke_task_name,
        execution_mode="run" if request_ready else "smoke",
        request_ready=request_ready,
        requires_trace_batch=requires_trace_batch,
    )
