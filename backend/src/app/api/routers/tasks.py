from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Body, Depends, Query, status
from fastapi.responses import JSONResponse

from src.app.api.presenters.storage import (
    build_metadata_record_ref_response,
    build_result_handle_ref_response,
    build_trace_payload_ref_response,
)
from src.app.domain.tasks import (
    TaskDetail,
    TaskEvent,
    TaskEventHistoryQuery,
    TaskEventOrder,
    TaskEventType,
    TaskLane,
    TaskListQuery,
    TaskQueueRow,
    TaskStatus,
    TaskSubmissionDraft,
    TaskVisibilityScope,
)
from src.app.infrastructure.request_debug import current_debug_ref
from src.app.infrastructure.runtime import get_task_service
from src.app.services.service_errors import ServiceError, service_error
from src.app.services.task_service import TaskService

router = APIRouter(prefix="/tasks", tags=["tasks"])


@router.get("")
def list_tasks(
    task_service: Annotated[TaskService, Depends(get_task_service)],
    status_filter: Annotated[str | None, Query(alias="status")] = None,
    lane: Annotated[str | None, Query()] = None,
    scope: Annotated[str, Query()] = "workspace",
    dataset_id: Annotated[str | None, Query(min_length=1)] = None,
    search_query: Annotated[str | None, Query(alias="q", min_length=1)] = None,
    limit: Annotated[int, Query(ge=1, le=50)] = 20,
) -> JSONResponse:
    try:
        query = TaskListQuery(
            status=_parse_status_filter(status_filter),
            lane=_parse_lane_filter(lane),
            scope=_parse_scope(scope),
            dataset_id=dataset_id,
            search_query=search_query,
            limit=limit,
        )
        queue = task_service.get_queue_view(query)
    except ServiceError as exc:
        return _service_error_response(exc)
    return _success_response(
        data={
            "rows": [_serialize_queue_row(row) for row in queue.rows],
            "worker_summary": [
                {
                    "lane": summary.lane,
                    "healthy_processors": summary.healthy_processors,
                    "busy_processors": summary.busy_processors,
                    "degraded_processors": summary.degraded_processors,
                    "draining_processors": summary.draining_processors,
                    "offline_processors": summary.offline_processors,
                }
                for summary in queue.worker_summary
            ],
        },
        meta={
            "generated_at": _generated_at(),
            "limit": limit,
            "next_cursor": queue.next_cursor,
            "prev_cursor": queue.prev_cursor,
            "has_more": queue.has_more,
            "filter_echo": {
                "status": status_filter,
                "lane": lane,
                "scope": scope,
                "dataset_id": dataset_id,
                "q": search_query,
            },
            "total_count": queue.total_count,
        },
    )


@router.get("/{task_id}")
def get_task(
    task_id: int,
    task_service: Annotated[TaskService, Depends(get_task_service)],
) -> JSONResponse:
    try:
        task = task_service.get_task(task_id)
    except ServiceError as exc:
        return _service_error_response(exc)
    return _success_response(
        data=_serialize_task_detail(task, task_service),
        meta={"generated_at": _generated_at()},
    )


@router.get("/{task_id}/events")
def list_task_events(
    task_id: int,
    task_service: Annotated[TaskService, Depends(get_task_service)],
    order: Annotated[TaskEventOrder, Query()] = "desc",
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    event_type: Annotated[TaskEventType | None, Query()] = None,
) -> JSONResponse:
    try:
        history = task_service.get_task_history(
            task_id,
            TaskEventHistoryQuery(
                order=order,
                limit=limit,
                event_type=event_type,
            ),
        )
    except ServiceError as exc:
        return _service_error_response(exc)
    return _success_response(
        data={
            "task_id": history.task.task_id,
            "events": [_serialize_task_event(event) for event in history.task.events],
        },
        meta={
            "generated_at": _generated_at(),
            "limit": limit,
            "event_count": history.event_count,
            "filter_echo": {"order": order, "event_type": event_type},
        },
    )


@router.post("", status_code=status.HTTP_201_CREATED)
def submit_task(
    payload: Annotated[object, Body(...)],
    task_service: Annotated[TaskService, Depends(get_task_service)],
) -> JSONResponse:
    try:
        draft = _parse_submission_payload(payload)
        detail = task_service.submit_task(draft)
    except ServiceError as exc:
        return _service_error_response(exc)
    return _success_response(
        data={
            "operation": "submitted",
            "task": _serialize_task_detail(detail, task_service),
        },
        status_code=status.HTTP_201_CREATED,
        meta={"generated_at": _generated_at()},
    )


@router.post("/{task_id}/cancel")
def cancel_task(
    task_id: int,
    task_service: Annotated[TaskService, Depends(get_task_service)],
) -> JSONResponse:
    try:
        detail = task_service.cancel_task(task_id)
    except ServiceError as exc:
        return _service_error_response(exc)
    return _success_response(
        data={
            "operation": "cancel_requested",
            "task": _serialize_task_detail(detail, task_service),
        },
        meta={"generated_at": _generated_at()},
    )


@router.post("/{task_id}/terminate")
def terminate_task(
    task_id: int,
    task_service: Annotated[TaskService, Depends(get_task_service)],
) -> JSONResponse:
    try:
        detail = task_service.terminate_task(task_id)
    except ServiceError as exc:
        return _service_error_response(exc)
    return _success_response(
        data={
            "operation": "terminate_requested",
            "task": _serialize_task_detail(detail, task_service),
        },
        meta={"generated_at": _generated_at()},
    )


@router.post("/{task_id}/retry", status_code=status.HTTP_201_CREATED)
def retry_task(
    task_id: int,
    task_service: Annotated[TaskService, Depends(get_task_service)],
) -> JSONResponse:
    try:
        detail = task_service.retry_task(task_id)
    except ServiceError as exc:
        return _service_error_response(exc)
    return _success_response(
        data={"operation": "retried", "task": _serialize_task_detail(detail, task_service)},
        status_code=status.HTTP_201_CREATED,
        meta={"generated_at": _generated_at()},
    )


def _parse_submission_payload(payload: object) -> TaskSubmissionDraft:
    body = _as_mapping(payload)
    kind = body.get("kind")
    if kind not in {"simulation", "post_processing", "characterization"}:
        raise service_error(
            400,
            code="request_validation_failed",
            category="validation_error",
            message="kind must be one of simulation, post_processing, characterization.",
        )
    dataset_id = _optional_string(body.get("dataset_id"), field_name="dataset_id")
    summary = _optional_string(body.get("summary"), field_name="summary")
    raw_definition_id = body.get("definition_id")
    if raw_definition_id is None:
        definition_id = None
    elif isinstance(raw_definition_id, int):
        definition_id = raw_definition_id
    else:
        raise service_error(
            400,
            code="request_validation_failed",
            category="validation_error",
            message="definition_id must be an integer or null.",
        )
    return TaskSubmissionDraft(
        kind=kind,
        dataset_id=dataset_id,
        definition_id=definition_id,
        summary=summary,
    )


def _serialize_queue_row(queue_row: TaskQueueRow) -> dict[str, object]:
    return {
        "task_id": queue_row.task_id,
        "summary": queue_row.summary,
        "status": queue_row.status,
        "lane": queue_row.lane,
        "task_kind": queue_row.task_kind,
        "owner_display_name": queue_row.owner_display_name,
        "visibility_scope": queue_row.visibility_scope,
        "updated_at": queue_row.updated_at,
        "result_availability": queue_row.result_availability,
        "allowed_actions": {
            "attach": queue_row.allowed_actions.attach,
            "cancel": queue_row.allowed_actions.cancel,
            "terminate": queue_row.allowed_actions.terminate,
            "retry": queue_row.allowed_actions.retry,
            "rejection_reason": queue_row.allowed_actions.rejection_reason,
        },
        "control_state": queue_row.control_state,
    }


def _serialize_task_detail(task: TaskDetail, task_service: TaskService) -> dict[str, object]:
    result_handoff = task_service.get_task_result_handoff(task.task_id)
    allowed_actions = task_service.get_task_allowed_actions(task.task_id)
    return {
        "task_id": task.task_id,
        "task_kind": task.kind,
        "lane": task.lane,
        "execution_mode": task.execution_mode,
        "status": task.status,
        "submitted_at": task.submitted_at,
        "owner_user_id": task.owner_user_id,
        "owner_display_name": task.owner_display_name,
        "workspace_id": task.workspace_id,
        "workspace_slug": task.workspace_slug,
        "visibility_scope": task.visibility_scope,
        "dataset_id": task.dataset_id,
        "definition_id": task.definition_id,
        "summary": task.summary,
        "queue_backend": task.queue_backend,
        "worker_task_name": task.worker_task_name,
        "request_ready": task.request_ready,
        "submitted_from_active_dataset": task.submitted_from_active_dataset,
        "control_state": task.control_state,
        "retry_of_task_id": task.retry_of_task_id,
        "allowed_actions": {
            "attach": allowed_actions.attach,
            "cancel": allowed_actions.cancel,
            "terminate": allowed_actions.terminate,
            "retry": allowed_actions.retry,
            "rejection_reason": allowed_actions.rejection_reason,
        },
        "dispatch": (
            {
                "dispatch_key": task.dispatch.dispatch_key,
                "status": task.dispatch.status,
                "submission_source": task.dispatch.submission_source,
                "accepted_at": task.dispatch.accepted_at,
                "last_updated_at": task.dispatch.last_updated_at,
            }
            if task.dispatch is not None
            else None
        ),
        "progress": {
            "phase": task.progress.phase,
            "percent_complete": task.progress.percent_complete,
            "summary": task.progress.summary,
            "updated_at": task.progress.updated_at,
        },
        "result_handoff": {
            "availability": result_handoff.availability,
            "primary_result_handle_id": result_handoff.primary_result_handle_id,
            "result_handle_count": result_handoff.result_handle_count,
            "trace_payload_available": result_handoff.trace_payload_available,
        },
        "result_refs": {
            "trace_batch_id": task.result_refs.trace_batch_id,
            "analysis_run_id": task.result_refs.analysis_run_id,
            "metadata_records": [
                build_metadata_record_ref_response(record).model_dump()
                for record in task.result_refs.metadata_records
            ],
            "trace_payload": (
                build_trace_payload_ref_response(task.result_refs.trace_payload).model_dump()
                if task.result_refs.trace_payload is not None
                else None
            ),
            "result_handles": [
                build_result_handle_ref_response(handle).model_dump()
                for handle in task.result_refs.result_handles
            ],
        },
        "events": [_serialize_task_event(event) for event in task.events],
    }


def _serialize_task_event(event: TaskEvent) -> dict[str, object]:
    return {
        "event_key": event.event_key,
        "event_type": event.event_type,
        "level": event.level,
        "occurred_at": event.occurred_at,
        "message": event.message,
        "metadata": dict(event.metadata),
    }


def _success_response(
    *,
    data: dict[str, object],
    status_code: int = 200,
    meta: dict[str, object] | None = None,
) -> JSONResponse:
    content: dict[str, object] = {"ok": True, "data": data}
    if meta is not None:
        content["meta"] = meta
    return JSONResponse(status_code=status_code, content=content)


def _service_error_response(exc: ServiceError) -> JSONResponse:
    error: dict[str, object] = {
        "code": exc.code,
        "category": exc.category,
        "message": exc.message,
        "retryable": exc.category in {"internal_error", "persistence_error"},
        "debug_ref": current_debug_ref(),
    }
    if len(exc.field_errors) > 0:
        error["details"] = {
            "field_errors": [
                {"field": field_error.field, "message": field_error.message}
                for field_error in exc.field_errors
            ]
        }
    return JSONResponse(status_code=exc.status_code, content={"ok": False, "error": error})


def _generated_at() -> str:
    return datetime.now(UTC).isoformat()


def _as_mapping(payload: object) -> dict[str, object]:
    if not isinstance(payload, dict):
        raise service_error(
            400,
            code="request_validation_failed",
            category="validation_error",
            message="Request body must be an object.",
        )
    return payload


def _optional_string(value: object, *, field_name: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise service_error(
            400,
            code="request_validation_failed",
            category="validation_error",
            message=f"{field_name} must be a string or null.",
        )
    stripped = value.strip()
    if len(stripped) == 0:
        raise service_error(
            400,
            code="request_validation_failed",
            category="validation_error",
            message=f"{field_name} must not be empty when provided.",
        )
    return stripped


def _parse_status_filter(value: str | None) -> TaskStatus | None:
    if value is None:
        return None
    if value not in {
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
        raise service_error(
            400,
            code="request_validation_failed",
            category="validation_error",
            message=(
                "status must be one of queued, dispatching, running, "
                "cancellation_requested, cancelling, cancelled, "
                "termination_requested, terminated, completed, failed."
            ),
        )
    return value


def _parse_lane_filter(value: str | None) -> TaskLane | None:
    if value is None:
        return None
    if value not in {"simulation", "characterization"}:
        raise service_error(
            400,
            code="request_validation_failed",
            category="validation_error",
            message="lane must be simulation or characterization.",
        )
    return value


def _parse_scope(value: str) -> TaskVisibilityScope:
    if value not in {"local", "workspace", "owned"}:
        raise service_error(
            400,
            code="request_validation_failed",
            category="validation_error",
            message="scope must be local, workspace or owned.",
        )
    return value
