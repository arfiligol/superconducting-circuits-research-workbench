from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, Literal, TypedDict, cast

from fastapi import APIRouter, Body, Depends, Query, status
from fastapi.responses import JSONResponse

from src.app.api.presenters.tasks import (
    build_explorer_filter_echo,
    build_processor_detail_response,
    build_publication_summary_response,
    build_published_trace_response,
    build_task_detail_response,
    build_task_event_response,
    build_task_queue_row_response,
    build_worker_summary_response,
)
from src.app.domain.datasets import (
    CharacterizationInputResultRef,
    ResultTracePublicationDraft,
    SimulationResultPublicationDraft,
)
from src.app.domain.tasks import (
    CharacterizationSetup,
    PostProcessingOperation,
    PostProcessingSetup,
    PostProcessingTraceSelection,
    SimulationFrequencySweep,
    SimulationHarmonicBalanceSettings,
    SimulationParameterSweep,
    SimulationPtcSetup,
    SimulationSetup,
    SimulationSolverSettings,
    SimulationSourceSpec,
    TaskBrowseStatusFilter,
    TaskEventHistoryQuery,
    TaskEventOrder,
    TaskEventType,
    TaskKind,
    TaskLane,
    TaskListQuery,
    TaskStatus,
    TaskSubmissionDraft,
    TaskVisibilityScope,
)
from src.app.infrastructure.request_debug import current_debug_ref
from src.app.infrastructure.runtime import (
    get_simulation_result_explorer_service,
    get_task_service,
)
from src.app.services.service_errors import ServiceError, service_error
from src.app.services.simulation_result_explorer_service import (
    ExplorerSelectionRequest,
    SimulationResultExplorerService,
)
from src.app.services.task_service import TaskService

router = APIRouter(prefix="/tasks", tags=["tasks"])


class _ResultTracePublicationPayload(TypedDict):
    design_id: str
    trace_keys: tuple[str, ...]
    metric: str
    parameter_name: str | None


@router.get("")
def list_tasks(
    task_service: Annotated[TaskService, Depends(get_task_service)],
    status: Annotated[str | None, Query()] = None,
    lane: Annotated[str | None, Query()] = None,
    scope: Annotated[str | None, Query()] = None,
    scope_filter: Annotated[str | None, Query()] = None,
    status_filter: Annotated[str | None, Query()] = None,
    lane_filter: Annotated[str | None, Query()] = None,
    dataset_id: Annotated[str | None, Query(min_length=1)] = None,
    search_query: Annotated[str | None, Query(alias="q", min_length=1)] = None,
    after: Annotated[str | None, Query(min_length=1)] = None,
    before: Annotated[str | None, Query(min_length=1)] = None,
    limit: Annotated[int, Query(ge=1, le=50)] = 20,
) -> JSONResponse:
    try:
        resolved_scope = _parse_scope_filter(scope_filter or scope or "workspace")
        query = TaskListQuery(
            status=_parse_exact_status_filter(status),
            status_filter=_parse_status_filter(status_filter),
            lane=_parse_lane_filter(lane_filter or lane),
            scope=resolved_scope,
            dataset_id=dataset_id,
            search_query=search_query,
            after=after,
            before=before,
            limit=limit,
        )
        queue = task_service.get_queue_view(query)
    except ServiceError as exc:
        return _service_error_response(exc)
    return _success_response(
        data={
            "rows": [build_task_queue_row_response(row) for row in queue.rows],
            "worker_summary": [
                build_worker_summary_response(summary) for summary in queue.worker_summary
            ],
            "aggregate_summary": {
                "total": queue.aggregate_summary.total,
                "pending": queue.aggregate_summary.pending,
                "running": queue.aggregate_summary.running,
                "completed": queue.aggregate_summary.completed,
                "failed": queue.aggregate_summary.failed,
                "cancelled": queue.aggregate_summary.cancelled,
                "terminated": queue.aggregate_summary.terminated,
                "result_ready": queue.aggregate_summary.result_ready,
            },
        },
        meta={
            "generated_at": _generated_at(),
            "limit": limit,
            "next_cursor": queue.next_cursor,
            "prev_cursor": queue.prev_cursor,
            "has_more": queue.has_more,
            "filter_echo": {
                "status": status,
                "lane": lane,
                "scope": scope,
                "scope_filter": scope_filter or resolved_scope,
                "status_filter": status_filter or "all",
                "lane_filter": lane_filter or lane,
                "dataset_id": dataset_id,
                "q": search_query,
                "after": after,
                "before": before,
            },
            "total_count": queue.total_count,
        },
    )


@router.get("/runtime/processors")
def list_runtime_processors(
    task_service: Annotated[TaskService, Depends(get_task_service)],
    lane_filter: Annotated[str | None, Query()] = None,
    lane: Annotated[str | None, Query()] = None,
) -> JSONResponse:
    try:
        resolved_lane = _parse_lane_filter(lane_filter or lane)
        runtime_view = task_service.get_processor_runtime_view(lane=resolved_lane)
    except ServiceError as exc:
        return _service_error_response(exc)
    return _success_response(
        data={
            "processors": [
                build_processor_detail_response(processor) for processor in runtime_view.processors
            ],
            "worker_summary": [
                build_worker_summary_response(summary) for summary in runtime_view.worker_summary
            ],
        },
        meta={
            "generated_at": _generated_at(),
            "filter_echo": {
                "lane": lane,
                "lane_filter": lane_filter or lane,
            },
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
        data=build_task_detail_response(task, task_service),
        meta={"generated_at": _generated_at()},
    )


@router.get("/{task_id}/simulation-results/bootstrap")
def get_simulation_result_bootstrap(
    task_id: int,
    explorer_service: Annotated[
        SimulationResultExplorerService,
        Depends(get_simulation_result_explorer_service),
    ],
) -> JSONResponse:
    try:
        payload = explorer_service.get_bootstrap_payload(task_id)
    except ServiceError as exc:
        return _service_error_response(exc)
    return _success_response(
        data=payload,
        meta={"generated_at": _generated_at()},
    )


@router.get("/{task_id}/simulation-results/view")
def get_simulation_result_view(
    task_id: int,
    explorer_service: Annotated[
        SimulationResultExplorerService,
        Depends(get_simulation_result_explorer_service),
    ],
    family: Annotated[str | None, Query()] = None,
    source: Annotated[str | None, Query()] = None,
    metric: Annotated[str | None, Query()] = None,
    sweep_index: Annotated[int | None, Query(ge=0)] = None,
    compare_axis_index: Annotated[int | None, Query(ge=0)] = None,
    z0: Annotated[float | None, Query(gt=0, alias="z0")] = None,
    output_port: Annotated[int | None, Query(ge=1)] = None,
    input_port: Annotated[int | None, Query(ge=1)] = None,
) -> JSONResponse:
    selection_request = _build_explorer_selection_request(
        family=family,
        source=source,
        metric=metric,
        sweep_index=sweep_index,
        compare_axis_index=compare_axis_index,
        z0=z0,
        output_port=output_port,
        input_port=input_port,
    )
    try:
        payload = explorer_service.get_view_payload(task_id, selection_request)
    except ServiceError as exc:
        return _service_error_response(exc)
    return _success_response(
        data=payload,
        meta={
            "generated_at": _generated_at(),
            "filter_echo": build_explorer_filter_echo(selection_request),
        },
    )


@router.get("/{task_id}/simulation-results/explorer")
def get_simulation_result_explorer(
    task_id: int,
    explorer_service: Annotated[
        SimulationResultExplorerService,
        Depends(get_simulation_result_explorer_service),
    ],
    family: Annotated[str | None, Query()] = None,
    source: Annotated[str | None, Query()] = None,
    metric: Annotated[str | None, Query()] = None,
    sweep_index: Annotated[int | None, Query(ge=0)] = None,
    compare_axis_index: Annotated[int | None, Query(ge=0)] = None,
    z0: Annotated[float | None, Query(gt=0, alias="z0")] = None,
    output_port: Annotated[int | None, Query(ge=1)] = None,
    input_port: Annotated[int | None, Query(ge=1)] = None,
) -> JSONResponse:
    selection_request = _build_explorer_selection_request(
        family=family,
        source=source,
        metric=metric,
        sweep_index=sweep_index,
        compare_axis_index=compare_axis_index,
        z0=z0,
        output_port=output_port,
        input_port=input_port,
    )
    try:
        payload = explorer_service.get_explorer_payload(task_id, selection_request)
    except ServiceError as exc:
        return _service_error_response(exc)
    return _success_response(
        data=payload,
        meta={
            "generated_at": _generated_at(),
            "filter_echo": build_explorer_filter_echo(selection_request),
        },
    )


@router.post("/{task_id}/simulation-results/publish")
def publish_simulation_result(
    task_id: int,
    payload: Annotated[object, Body(...)],
    task_service: Annotated[TaskService, Depends(get_task_service)],
) -> JSONResponse:
    try:
        parsed_payload = _parse_simulation_result_publication_payload(payload)
        result = task_service.publish_simulation_result(
            task_id,
            SimulationResultPublicationDraft(
                design_name=parsed_payload["design_name"],
                design_id=parsed_payload["design_id"],
            ),
            dataset_id=parsed_payload["dataset_id"],
        )
        task = task_service.get_task(task_id)
    except ServiceError as exc:
        return _service_error_response(exc)
    return _success_response(
        data={
            "operation": result.state,
            "publication_summary": build_publication_summary_response(
                task_service.get_task_publication_summary(task_id)
            ),
            "task": build_task_detail_response(task, task_service),
            "dataset": {
                "dataset_id": result.dataset.dataset_id,
                "name": result.dataset.name,
                "visibility_scope": result.dataset.visibility_scope,
                "lifecycle_state": result.dataset.lifecycle_state,
                "allowed_actions": {
                    "select": result.dataset.allowed_actions.select,
                    "update_profile": result.dataset.allowed_actions.update_profile,
                    "publish": result.dataset.allowed_actions.publish,
                    "archive": result.dataset.allowed_actions.archive,
                    "delete": result.dataset.allowed_actions.delete,
                    "ingest_raw_data": result.dataset.allowed_actions.ingest_raw_data,
                },
            },
            "design": {
                "design_id": result.design.design_id,
                "dataset_id": result.design.dataset_id,
                "name": result.design.name,
                "source_coverage": result.design.source_coverage,
                "compare_readiness": result.design.compare_readiness,
                "trace_count": result.design.trace_count,
                "updated_at": result.design.updated_at,
            },
            "traces": [build_published_trace_response(trace) for trace in result.traces],
        },
        meta={"generated_at": _generated_at()},
    )


@router.post("/{task_id}/result-traces/publish")
def publish_result_trace(
    task_id: int,
    payload: Annotated[object, Body(...)],
    task_service: Annotated[TaskService, Depends(get_task_service)],
) -> JSONResponse:
    try:
        parsed_payload = _parse_result_trace_publication_payload(payload)
        result = task_service.publish_result_trace(
            task_id,
            ResultTracePublicationDraft(
                design_id=parsed_payload["design_id"],
                trace_keys=parsed_payload["trace_keys"],
                metric=parsed_payload["metric"],
                parameter_name=parsed_payload["parameter_name"],
            ),
        )
        task = task_service.get_task(task_id)
    except ServiceError as exc:
        return _service_error_response(exc)
    return _success_response(
        data={
            "operation": result.state,
            "publication_summary": build_publication_summary_response(
                task_service.get_task_publication_summary(task_id)
            ),
            "task": build_task_detail_response(task, task_service),
            "dataset": {
                "dataset_id": result.dataset.dataset_id,
                "name": result.dataset.name,
                "visibility_scope": result.dataset.visibility_scope,
                "lifecycle_state": result.dataset.lifecycle_state,
                "allowed_actions": {
                    "select": result.dataset.allowed_actions.select,
                    "update_profile": result.dataset.allowed_actions.update_profile,
                    "publish": result.dataset.allowed_actions.publish,
                    "archive": result.dataset.allowed_actions.archive,
                    "delete": result.dataset.allowed_actions.delete,
                    "ingest_raw_data": result.dataset.allowed_actions.ingest_raw_data,
                },
            },
            "design": {
                "design_id": result.design.design_id,
                "dataset_id": result.design.dataset_id,
                "name": result.design.name,
                "source_coverage": result.design.source_coverage,
                "compare_readiness": result.design.compare_readiness,
                "trace_count": result.design.trace_count,
                "updated_at": result.design.updated_at,
            },
            "trace_key": result.trace_keys[0] if len(result.trace_keys) > 0 else None,
            "trace": (
                build_published_trace_response(result.traces[0]) if len(result.traces) > 0 else None
            ),
            "traces": [build_published_trace_response(trace) for trace in result.traces],
            "raw_data": {
                "dataset_id": result.design.dataset_id,
                "design_id": result.design.design_id,
                "trace_id": result.traces[0].trace_id if len(result.traces) == 1 else None,
            },
        },
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
            "events": [build_task_event_response(event) for event in history.task.events],
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
            "task": build_task_detail_response(detail, task_service),
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
            "task": build_task_detail_response(detail, task_service),
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
            "task": build_task_detail_response(detail, task_service),
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
        data={"operation": "retried", "task": build_task_detail_response(detail, task_service)},
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
    elif isinstance(raw_definition_id, str) and len(raw_definition_id.strip()) > 0:
        definition_id = raw_definition_id.strip()
    else:
        raise service_error(
            400,
            code="request_validation_failed",
            category="validation_error",
            message="definition_id must be a non-empty string or null.",
        )
    raw_upstream_task_id = body.get("upstream_task_id")
    if raw_upstream_task_id is None:
        upstream_task_id = None
    elif isinstance(raw_upstream_task_id, int):
        upstream_task_id = raw_upstream_task_id
    else:
        raise service_error(
            400,
            code="request_validation_failed",
            category="validation_error",
            message="upstream_task_id must be an integer or null.",
        )
    return TaskSubmissionDraft(
        kind=cast(TaskKind, kind),
        dataset_id=dataset_id,
        definition_id=definition_id,
        summary=summary,
        simulation_setup=_parse_simulation_setup(body.get("simulation_setup")),
        post_processing_setup=_parse_post_processing_setup(body.get("post_processing_setup")),
        characterization_setup=_parse_characterization_setup(body.get("characterization_setup")),
        upstream_task_id=upstream_task_id,
    )


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
    details = dict(exc.details)
    if len(exc.field_errors) > 0:
        details["field_errors"] = [
            {"field": field_error.field, "message": field_error.message}
            for field_error in exc.field_errors
        ]
    if len(details) > 0:
        error["details"] = details
    return JSONResponse(status_code=exc.status_code, content={"ok": False, "error": error})


def _generated_at() -> str:
    return datetime.now(UTC).isoformat()


def _build_explorer_selection_request(
    *,
    family: str | None,
    source: str | None,
    metric: str | None,
    sweep_index: int | None,
    compare_axis_index: int | None,
    z0: float | None,
    output_port: int | None,
    input_port: int | None,
) -> ExplorerSelectionRequest:
    return ExplorerSelectionRequest(
        family=family,
        source=source,
        metric=metric,
        sweep_index=sweep_index,
        compare_axis_index=compare_axis_index,
        z0_ohm=z0,
        output_port=output_port,
        input_port=input_port,
    )


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


def _optional_string_sequence(value: object, *, field_name: str) -> list[str] | None:
    if value is None:
        return None
    if not isinstance(value, list):
        raise service_error(
            400,
            code="request_validation_failed",
            category="validation_error",
            message=f"{field_name} must be an array of strings or null.",
        )
    return [
        _required_string(item, field_name=f"{field_name}[{index}]")
        for index, item in enumerate(value)
    ]


def _parse_simulation_setup(payload: object) -> SimulationSetup | None:
    if payload is None:
        return None
    body = _as_mapping(payload)
    frequency_sweep = _require_mapping(
        body.get("frequency_sweep"),
        field_name="simulation_setup.frequency_sweep",
    )
    return SimulationSetup(
        frequency_sweep=SimulationFrequencySweep(
            start_ghz=_required_number(
                frequency_sweep.get("start_ghz"),
                field_name="simulation_setup.frequency_sweep.start_ghz",
            ),
            stop_ghz=_required_number(
                frequency_sweep.get("stop_ghz"),
                field_name="simulation_setup.frequency_sweep.stop_ghz",
            ),
            point_count=_required_int(
                frequency_sweep.get("point_count"),
                field_name="simulation_setup.frequency_sweep.point_count",
                minimum=1,
            ),
            spacing=cast(
                Literal["linear", "log"],
                _required_literal(
                    frequency_sweep.get("spacing"),
                    field_name="simulation_setup.frequency_sweep.spacing",
                    allowed={"linear", "log"},
                    default="linear",
                ),
            ),
        ),
        parameter_sweeps=_parse_parameter_sweeps(body.get("parameter_sweeps")),
        solver=_parse_solver_settings(body.get("solver")),
        sources=_parse_source_specs(body.get("sources")),
        ptc=_parse_ptc_setup(body.get("ptc")),
    )


def _parse_post_processing_setup(payload: object) -> PostProcessingSetup | None:
    if payload is None:
        return None
    body = _as_mapping(payload)
    raw_selections = body.get("selections", [])
    raw_operations = body.get("operations")
    if not isinstance(raw_selections, list):
        raise service_error(
            400,
            code="request_validation_failed",
            category="validation_error",
            message="post_processing_setup.selections must be an array.",
        )
    if not isinstance(raw_operations, list):
        raise service_error(
            400,
            code="request_validation_failed",
            category="validation_error",
            message="post_processing_setup.operations must be an array.",
        )
    return PostProcessingSetup(
        selections=tuple(_parse_trace_selection(item) for item in raw_selections),
        operations=tuple(_parse_post_processing_operation(item) for item in raw_operations),
    )


def _parse_characterization_setup(payload: object) -> CharacterizationSetup | None:
    if payload is None:
        return None
    body = _as_mapping(payload)
    raw_selected_trace_ids = body.get("selected_trace_ids")
    raw_analysis_config = body.get("analysis_config")
    raw_input_result_refs = body.get("input_result_refs", [])
    if not isinstance(raw_selected_trace_ids, list):
        raise service_error(
            400,
            code="request_validation_failed",
            category="validation_error",
            message="characterization_setup.selected_trace_ids must be an array.",
        )
    if raw_analysis_config is not None and not isinstance(raw_analysis_config, dict):
        raise service_error(
            400,
            code="request_validation_failed",
            category="validation_error",
            message="characterization_setup.analysis_config must be an object.",
        )
    if not isinstance(raw_input_result_refs, list):
        raise service_error(
            400,
            code="request_validation_failed",
            category="validation_error",
            message="characterization_setup.input_result_refs must be an array.",
        )
    return CharacterizationSetup(
        design_id=_required_string(
            body.get("design_id"),
            field_name="characterization_setup.design_id",
        ),
        analysis_id=_required_string(
            body.get("analysis_id"),
            field_name="characterization_setup.analysis_id",
        ),
        selected_trace_ids=tuple(
            _required_string(
                trace_id,
                field_name=(f"characterization_setup.selected_trace_ids[{index}]"),
            )
            for index, trace_id in enumerate(raw_selected_trace_ids)
        ),
        analysis_config=dict(raw_analysis_config or {}),
        input_result_refs=tuple(
            _parse_characterization_input_result_ref(item, index=index)
            for index, item in enumerate(raw_input_result_refs)
        ),
    )


def _parse_characterization_input_result_ref(
    payload: object,
    *,
    index: int,
) -> CharacterizationInputResultRef:
    body = _require_mapping(
        payload,
        field_name=f"characterization_setup.input_result_refs[{index}]",
    )
    return CharacterizationInputResultRef(
        analysis_id=_required_string(
            body.get("analysis_id"),
            field_name=(f"characterization_setup.input_result_refs[{index}].analysis_id"),
        ),
        result_id=_required_string(
            body.get("result_id"),
            field_name=(f"characterization_setup.input_result_refs[{index}].result_id"),
        ),
        run_id=_optional_string(
            body.get("run_id"),
            field_name=f"characterization_setup.input_result_refs[{index}].run_id",
        ),
        artifact_id=_optional_string(
            body.get("artifact_id"),
            field_name=(f"characterization_setup.input_result_refs[{index}].artifact_id"),
        ),
        contract_version=_optional_string(
            body.get("contract_version"),
            field_name=(f"characterization_setup.input_result_refs[{index}].contract_version"),
        ),
        title=_optional_string(
            body.get("title"),
            field_name=f"characterization_setup.input_result_refs[{index}].title",
        ),
    )


def _parse_parameter_sweeps(payload: object) -> tuple[SimulationParameterSweep, ...]:
    if payload is None:
        return ()
    if not isinstance(payload, list):
        raise service_error(
            400,
            code="request_validation_failed",
            category="validation_error",
            message="simulation_setup.parameter_sweeps must be an array.",
        )
    sweeps: list[SimulationParameterSweep] = []
    for index, item in enumerate(payload):
        body = _require_mapping(
            item,
            field_name=f"simulation_setup.parameter_sweeps[{index}]",
        )
        raw_values = body.get("values")
        if not isinstance(raw_values, list) or len(raw_values) == 0:
            raise service_error(
                400,
                code="request_validation_failed",
                category="validation_error",
                message=(
                    f"simulation_setup.parameter_sweeps[{index}].values must be a non-empty array."
                ),
            )
        sweeps.append(
            SimulationParameterSweep(
                parameter=_required_string(
                    body.get("parameter"),
                    field_name=f"simulation_setup.parameter_sweeps[{index}].parameter",
                ),
                values=tuple(
                    _required_number(
                        value,
                        field_name=(
                            f"simulation_setup.parameter_sweeps[{index}].values[{value_index}]"
                        ),
                    )
                    for value_index, value in enumerate(raw_values)
                ),
                unit=_optional_string(
                    body.get("unit"),
                    field_name=f"simulation_setup.parameter_sweeps[{index}].unit",
                ),
            )
        )
    return tuple(sweeps)


def _parse_solver_settings(payload: object) -> SimulationSolverSettings:
    body = _require_mapping(payload, field_name="simulation_setup.solver")
    raw_harmonic_balance = body.get("harmonic_balance")
    harmonic_balance = None
    if raw_harmonic_balance is not None:
        hb_body = _require_mapping(
            raw_harmonic_balance,
            field_name="simulation_setup.solver.harmonic_balance",
        )
        harmonic_balance = SimulationHarmonicBalanceSettings(
            enabled=_required_bool(
                hb_body.get("enabled"),
                field_name="simulation_setup.solver.harmonic_balance.enabled",
            ),
            harmonic_count=_optional_int(
                hb_body.get("harmonic_count"),
                field_name="simulation_setup.solver.harmonic_balance.harmonic_count",
                minimum=1,
            ),
            oversample_factor=_optional_int(
                hb_body.get("oversample_factor"),
                field_name="simulation_setup.solver.harmonic_balance.oversample_factor",
                minimum=1,
            ),
        )
    return SimulationSolverSettings(
        solver_family=_required_string(
            body.get("solver_family"),
            field_name="simulation_setup.solver.solver_family",
        ),
        max_iterations=_required_int(
            body.get("max_iterations"),
            field_name="simulation_setup.solver.max_iterations",
            minimum=1,
        ),
        convergence_tolerance=_required_number(
            body.get("convergence_tolerance"),
            field_name="simulation_setup.solver.convergence_tolerance",
        ),
        harmonic_balance=harmonic_balance,
    )


def _parse_source_specs(payload: object) -> tuple[SimulationSourceSpec, ...]:
    if not isinstance(payload, list) or len(payload) == 0:
        raise service_error(
            400,
            code="request_validation_failed",
            category="validation_error",
            message="simulation_setup.sources must be a non-empty array.",
        )
    sources: list[SimulationSourceSpec] = []
    for index, item in enumerate(payload):
        body = _require_mapping(item, field_name=f"simulation_setup.sources[{index}]")
        sources.append(
            SimulationSourceSpec(
                source_id=_required_string(
                    body.get("source_id"),
                    field_name=f"simulation_setup.sources[{index}].source_id",
                ),
                kind=_required_string(
                    body.get("kind"),
                    field_name=f"simulation_setup.sources[{index}].kind",
                ),
                target=_required_string(
                    body.get("target"),
                    field_name=f"simulation_setup.sources[{index}].target",
                ),
                amplitude=_required_number(
                    body.get("amplitude"),
                    field_name=f"simulation_setup.sources[{index}].amplitude",
                ),
                frequency_ghz=_optional_number(
                    body.get("frequency_ghz"),
                    field_name=f"simulation_setup.sources[{index}].frequency_ghz",
                ),
                phase_deg=_optional_number(
                    body.get("phase_deg"),
                    field_name=f"simulation_setup.sources[{index}].phase_deg",
                ),
            )
        )
    return tuple(sources)


def _parse_ptc_setup(payload: object) -> SimulationPtcSetup | None:
    if payload is None:
        return None
    body = _require_mapping(payload, field_name="simulation_setup.ptc")
    raw_ports = body.get("compensate_ports")
    if not isinstance(raw_ports, list):
        raise service_error(
            400,
            code="request_validation_failed",
            category="validation_error",
            message="simulation_setup.ptc.compensate_ports must be an array.",
        )
    return SimulationPtcSetup(
        enabled=_required_bool(
            body.get("enabled"),
            field_name="simulation_setup.ptc.enabled",
        ),
        mode=cast(
            Literal["auto", "manual"],
            _required_literal(
                body.get("mode"),
                field_name="simulation_setup.ptc.mode",
                allowed={"auto", "manual"},
            ),
        ),
        compensate_ports=tuple(
            _required_string(
                value,
                field_name=f"simulation_setup.ptc.compensate_ports[{index}]",
            )
            for index, value in enumerate(raw_ports)
        ),
    )


def _parse_trace_selection(payload: object) -> PostProcessingTraceSelection:
    body = _require_mapping(payload, field_name="post_processing_setup.selections[]")
    raw_trace_ids = body.get("trace_ids")
    if raw_trace_ids is not None and not isinstance(raw_trace_ids, list):
        raise service_error(
            400,
            code="request_validation_failed",
            category="validation_error",
            message="post_processing_setup.selections[].trace_ids must be an array.",
        )
    return PostProcessingTraceSelection(
        trace_family=_required_string(
            body.get("trace_family"),
            field_name="post_processing_setup.selections[].trace_family",
        ),
        representation=_required_string(
            body.get("representation"),
            field_name="post_processing_setup.selections[].representation",
        ),
        design_id=_optional_string(
            body.get("design_id"),
            field_name="post_processing_setup.selections[].design_id",
        ),
        trace_ids=tuple(str(trace_id) for trace_id in raw_trace_ids or ()),
    )


def _parse_post_processing_operation(payload: object) -> PostProcessingOperation:
    body = _require_mapping(payload, field_name="post_processing_setup.operations[]")
    raw_config = body.get("config")
    if raw_config is not None and not isinstance(raw_config, dict):
        raise service_error(
            400,
            code="request_validation_failed",
            category="validation_error",
            message="post_processing_setup.operations[].config must be an object.",
        )
    return PostProcessingOperation(
        operation=_required_string(
            body.get("operation"),
            field_name="post_processing_setup.operations[].operation",
        ),
        enabled=_required_bool(
            body.get("enabled", True),
            field_name="post_processing_setup.operations[].enabled",
        ),
        config=dict(raw_config or {}),
    )


def _parse_simulation_result_publication_payload(payload: object) -> dict[str, str | None]:
    body = _as_mapping(payload)
    design_id = _optional_string(body.get("design_id"), field_name="design_id")
    design_name = _optional_string(body.get("design_name"), field_name="design_name")
    if design_id is None and design_name is None:
        raise service_error(
            400,
            code="request_validation_failed",
            category="validation_error",
            message="design_id or design_name is required.",
        )
    return {
        "dataset_id": _optional_string(body.get("dataset_id"), field_name="dataset_id"),
        "design_id": design_id,
        "design_name": design_name,
    }


def _parse_result_trace_publication_payload(
    payload: object,
) -> _ResultTracePublicationPayload:
    body = _require_mapping(payload, field_name="result_trace_publication")
    trace_keys = _optional_string_sequence(
        body.get("trace_keys"),
        field_name="result_trace_publication.trace_keys",
    )
    if trace_keys is None:
        trace_keys = [
            _required_string(
                body.get("trace_key"),
                field_name="result_trace_publication.trace_key",
            )
        ]
    if len(trace_keys) == 0:
        raise service_error(
            400,
            code="request_validation_failed",
            category="validation_error",
            message="result_trace_publication.trace_keys must not be empty.",
        )
    return {
        "design_id": _required_string(
            body.get("design_id"),
            field_name="result_trace_publication.design_id",
        ),
        "trace_keys": tuple(trace_keys),
        "metric": _required_string(
            body.get("metric"),
            field_name="result_trace_publication.metric",
        ),
        "parameter_name": _optional_string(
            body.get("parameter_name"),
            field_name="result_trace_publication.parameter_name",
        ),
    }


def _require_mapping(payload: object, *, field_name: str) -> dict[str, object]:
    if not isinstance(payload, dict):
        raise service_error(
            400,
            code="request_validation_failed",
            category="validation_error",
            message=f"{field_name} must be an object.",
        )
    return payload


def _required_string(value: object, *, field_name: str) -> str:
    resolved = _optional_string(value, field_name=field_name)
    if resolved is None:
        raise service_error(
            400,
            code="request_validation_failed",
            category="validation_error",
            message=f"{field_name} is required.",
        )
    return resolved


def _required_number(value: object, *, field_name: str) -> float:
    if not isinstance(value, int | float):
        raise service_error(
            400,
            code="request_validation_failed",
            category="validation_error",
            message=f"{field_name} must be a number.",
        )
    return float(value)


def _optional_number(value: object, *, field_name: str) -> float | None:
    if value is None:
        return None
    return _required_number(value, field_name=field_name)


def _required_int(value: object, *, field_name: str, minimum: int | None = None) -> int:
    if not isinstance(value, int):
        raise service_error(
            400,
            code="request_validation_failed",
            category="validation_error",
            message=f"{field_name} must be an integer.",
        )
    if minimum is not None and value < minimum:
        raise service_error(
            400,
            code="request_validation_failed",
            category="validation_error",
            message=f"{field_name} must be greater than or equal to {minimum}.",
        )
    return value


def _optional_int(value: object, *, field_name: str, minimum: int | None = None) -> int | None:
    if value is None:
        return None
    return _required_int(value, field_name=field_name, minimum=minimum)


def _required_bool(value: object, *, field_name: str) -> bool:
    if not isinstance(value, bool):
        raise service_error(
            400,
            code="request_validation_failed",
            category="validation_error",
            message=f"{field_name} must be a boolean.",
        )
    return value


def _required_literal(
    value: object,
    *,
    field_name: str,
    allowed: set[str],
    default: str | None = None,
) -> str:
    if value is None:
        if default is not None:
            return default
        raise service_error(
            400,
            code="request_validation_failed",
            category="validation_error",
            message=f"{field_name} is required.",
        )
    if not isinstance(value, str) or value not in allowed:
        raise service_error(
            400,
            code="request_validation_failed",
            category="validation_error",
            message=f"{field_name} must be one of {', '.join(sorted(allowed))}.",
        )
    return value


def _parse_exact_status_filter(value: str | None) -> TaskStatus | None:
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
    return cast(TaskStatus, value)


def _parse_status_filter(value: str | None) -> TaskBrowseStatusFilter:
    if value is None:
        return "all"
    if value not in {"active", "recent", "all"}:
        raise service_error(
            400,
            code="request_validation_failed",
            category="validation_error",
            message="status_filter must be active, recent or all.",
        )
    return cast(TaskBrowseStatusFilter, value)


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
    return cast(TaskLane, value)


def _parse_scope_filter(value: str) -> TaskVisibilityScope:
    normalized = "owned" if value == "mine" else value
    if normalized not in {"local", "workspace", "owned"}:
        raise service_error(
            400,
            code="request_validation_failed",
            category="validation_error",
            message="scope_filter must be local, workspace or mine.",
        )
    return cast(TaskVisibilityScope, normalized)
