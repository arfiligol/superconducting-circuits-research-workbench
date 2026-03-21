"""`/api/v1/tasks/*` routes for phase-1 persisted task orchestration."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, status

from legacy.legacy_nicegui_archived.api.dependencies import current_user
from legacy.legacy_nicegui_archived.api.schemas import (
    CharacterizationTaskCreateRequest,
    DesignTasksResponse,
    PostProcessingTaskCreateRequest,
    SimulationTaskCreateRequest,
    TaskDispatchResponse,
    TaskResponse,
)
from legacy.legacy_nicegui_archived.services.execution_context import ActorContext
from legacy.legacy_nicegui_archived.services.latest_result_lookup import list_design_tasks, require_task
from legacy.legacy_nicegui_archived.services.task_submission import SubmittedTask, create_api_task
from core.shared.persistence.models import TaskRecord

router = APIRouter(tags=["tasks"])


def _task_response(task: TaskRecord) -> TaskResponse:
    if task.id is None:
        raise ValueError("Persisted task must expose an ID.")
    return TaskResponse(
        id=int(task.id),
        task_kind=str(task.task_kind),
        status=str(task.status),
        design_id=int(task.design_id),
        trace_batch_id=task.trace_batch_id,
        analysis_run_id=task.analysis_run_id,
        requested_by=str(task.requested_by),
        actor_id=task.actor_id,
        dedupe_key=task.dedupe_key,
        request_payload=dict(task.request_payload),
        progress_payload=dict(task.progress_payload),
        result_summary_payload=dict(task.result_summary_payload),
        error_payload=dict(task.error_payload),
        created_at=task.created_at,
        started_at=task.started_at,
        heartbeat_at=task.heartbeat_at,
        completed_at=task.completed_at,
    )


def _task_dispatch_response(submitted: SubmittedTask) -> TaskDispatchResponse:
    return TaskDispatchResponse(
        task=_task_response(submitted.task),
        dedupe_hit=submitted.dedupe_hit,
        dispatched_lane=submitted.dispatch.lane,
        worker_task_name=submitted.dispatch.worker_task_name,
    )


def _actor_from_request(request: Request) -> ActorContext:
    user = current_user(request)
    return ActorContext(
        actor_id=user.id,
        requested_by="api",
        role=user.role,
        auth_source="session_cookie",
        metadata={"username": user.username},
    )


@router.post(
    "/tasks/simulation",
    response_model=TaskDispatchResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def create_simulation_task(
    payload: SimulationTaskCreateRequest,
    request: Request,
) -> TaskDispatchResponse:
    """Create and enqueue one simulation task."""
    try:
        submitted = create_api_task(
            task_kind="simulation",
            design_id=payload.design_id,
            request_payload=payload.model_dump(mode="json", exclude={"force_rerun"}),
            actor=_actor_from_request(request),
            force_rerun=payload.force_rerun,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return _task_dispatch_response(submitted)


@router.post(
    "/tasks/post-processing",
    response_model=TaskDispatchResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def create_post_processing_task(
    payload: PostProcessingTaskCreateRequest,
    request: Request,
) -> TaskDispatchResponse:
    """Create and enqueue one post-processing task."""
    try:
        submitted = create_api_task(
            task_kind="post_processing",
            design_id=payload.design_id,
            request_payload=payload.model_dump(mode="json", exclude={"force_rerun"}),
            actor=_actor_from_request(request),
            force_rerun=payload.force_rerun,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return _task_dispatch_response(submitted)


@router.post(
    "/tasks/characterization",
    response_model=TaskDispatchResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def create_characterization_task(
    payload: CharacterizationTaskCreateRequest,
    request: Request,
) -> TaskDispatchResponse:
    """Create and enqueue one characterization task."""
    try:
        submitted = create_api_task(
            task_kind="characterization",
            design_id=payload.design_id,
            request_payload=payload.model_dump(mode="json", exclude={"force_rerun"}),
            actor=_actor_from_request(request),
            force_rerun=payload.force_rerun,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return _task_dispatch_response(submitted)


@router.get("/tasks/{task_id}", response_model=TaskResponse)
def get_task(task_id: int, request: Request) -> TaskResponse:
    """Fetch one persisted task by ID."""
    _actor = current_user(request)
    try:
        return _task_response(require_task(task_id))
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.get("/designs/{design_id}/tasks", response_model=DesignTasksResponse)
def get_design_tasks(design_id: int, request: Request) -> DesignTasksResponse:
    """List persisted tasks for one design."""
    _actor = current_user(request)
    try:
        tasks = list_design_tasks(design_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return DesignTasksResponse(tasks=[_task_response(task) for task in tasks])
