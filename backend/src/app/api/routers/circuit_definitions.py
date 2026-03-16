from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, Any, cast

from fastapi import APIRouter, Body, Depends, Query
from fastapi.responses import JSONResponse

from src.app.domain.circuit_definitions import (
    CircuitDefinitionCatalogPage,
    CircuitDefinitionCloneDraft,
    CircuitDefinitionDetail,
    CircuitDefinitionDraft,
    CircuitDefinitionListQuery,
    CircuitDefinitionSortBy,
    CircuitDefinitionSummary,
    CircuitDefinitionUpdate,
    SortOrder,
    ValidationNotice,
)
from src.app.domain.schemdraw_render import (
    SchemdrawDiagnostic,
    SchemdrawLinkedSchema,
    SchemdrawRenderRequest,
    SchemdrawRenderResult,
)
from src.app.infrastructure.request_debug import current_debug_ref
from src.app.infrastructure.runtime import (
    get_circuit_definition_service,
    get_schemdraw_render_service,
)
from src.app.services.circuit_definition_service import CircuitDefinitionService
from src.app.services.schemdraw_render_service import SchemdrawRenderService
from src.app.services.service_errors import ServiceError, service_error

router = APIRouter(tags=["definition-authoring"])
definitions_router = APIRouter(prefix="/circuit-definitions", tags=["circuit-definitions"])
schemdraw_router = APIRouter(prefix="/schemdraw", tags=["schemdraw"])


@definitions_router.get("")
def list_circuit_definitions(
    definition_service: Annotated[
        CircuitDefinitionService,
        Depends(get_circuit_definition_service),
    ],
    search_query: Annotated[str | None, Query()] = None,
    sort_by: Annotated[CircuitDefinitionSortBy, Query()] = "updated_at",
    sort_order: Annotated[SortOrder, Query()] = "desc",
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    after: Annotated[str | None, Query()] = None,
    before: Annotated[str | None, Query()] = None,
) -> JSONResponse:
    try:
        page = definition_service.list_circuit_definitions(
            CircuitDefinitionListQuery(
                search_query=_normalize_optional_string(search_query),
                sort_by=sort_by,
                sort_order=sort_order,
                limit=limit,
                after=after,
                before=before,
            )
        )
    except ServiceError as exc:
        return _service_error_response(exc)

    return _success_response(
        data={
            "rows": [_serialize_definition_summary(row) for row in page.rows],
            "total_count": page.total_count,
        },
        meta=_collection_meta(
            page=page,
            limit=limit,
            filter_echo={
                "search_query": _normalize_optional_string(search_query),
                "sort_by": sort_by,
                "sort_order": sort_order,
                "after": after,
                "before": before,
            },
        ),
    )


@definitions_router.get("/{definition_id}")
def get_circuit_definition(
    definition_id: int,
    definition_service: Annotated[
        CircuitDefinitionService,
        Depends(get_circuit_definition_service),
    ],
) -> JSONResponse:
    try:
        detail = definition_service.get_circuit_definition(definition_id)
    except ServiceError as exc:
        return _service_error_response(exc)
    return _success_response(data=_serialize_definition_detail(detail))


@definitions_router.post("")
def create_circuit_definition(
    payload: Annotated[object, Body(...)],
    definition_service: Annotated[
        CircuitDefinitionService,
        Depends(get_circuit_definition_service),
    ],
) -> JSONResponse:
    try:
        draft = _parse_definition_create_payload(payload)
        detail = definition_service.create_circuit_definition(draft)
    except ServiceError as exc:
        return _service_error_response(exc)
    return _success_response(
        data={
            "operation": "created",
            "definition": _serialize_definition_detail(detail),
        },
        status_code=201,
    )


@definitions_router.put("/{definition_id}")
def update_circuit_definition(
    definition_id: int,
    payload: Annotated[object, Body(...)],
    definition_service: Annotated[
        CircuitDefinitionService,
        Depends(get_circuit_definition_service),
    ],
) -> JSONResponse:
    try:
        update = _parse_definition_update_payload(payload)
        detail = definition_service.update_circuit_definition(definition_id, update)
    except ServiceError as exc:
        return _service_error_response(exc)
    return _success_response(
        data={
            "operation": "updated",
            "definition": _serialize_definition_detail(detail),
        }
    )


@definitions_router.post("/{definition_id}/publish")
def publish_circuit_definition(
    definition_id: int,
    definition_service: Annotated[
        CircuitDefinitionService,
        Depends(get_circuit_definition_service),
    ],
) -> JSONResponse:
    try:
        detail = definition_service.publish_circuit_definition(definition_id)
    except ServiceError as exc:
        return _service_error_response(exc)
    return _success_response(
        data={
            "operation": "published",
            "definition": _serialize_definition_detail(detail),
        }
    )


@definitions_router.post("/{definition_id}/clone")
def clone_circuit_definition(
    definition_id: int,
    definition_service: Annotated[
        CircuitDefinitionService,
        Depends(get_circuit_definition_service),
    ],
    payload: Annotated[object | None, Body()] = None,
) -> JSONResponse:
    try:
        draft = _parse_definition_clone_payload(payload)
        detail = definition_service.clone_circuit_definition(definition_id, draft)
    except ServiceError as exc:
        return _service_error_response(exc)
    return _success_response(
        data={
            "operation": "cloned",
            "definition": _serialize_definition_detail(detail),
        },
        status_code=201,
    )


@definitions_router.delete("/{definition_id}")
def delete_circuit_definition(
    definition_id: int,
    definition_service: Annotated[
        CircuitDefinitionService,
        Depends(get_circuit_definition_service),
    ],
) -> JSONResponse:
    try:
        definition_service.delete_circuit_definition(definition_id)
    except ServiceError as exc:
        return _service_error_response(exc)
    return _success_response(
        data={
            "operation": "deleted",
            "definition_id": definition_id,
        }
    )


@schemdraw_router.post("/render")
def render_schemdraw_preview(
    payload: Annotated[object, Body(...)],
    render_service: Annotated[
        SchemdrawRenderService,
        Depends(get_schemdraw_render_service),
    ],
) -> JSONResponse:
    try:
        request = _parse_schemdraw_request(payload)
        result = render_service.render(request)
    except ServiceError as exc:
        return _service_error_response(exc)
    return _success_response(data=_serialize_schemdraw_result(result))


def _parse_definition_create_payload(payload: object) -> CircuitDefinitionDraft:
    body = _as_mapping(payload)
    name = _required_string(body, "name")
    source_text = _required_string(body, "source_text")
    visibility_scope = body.get("visibility_scope", "private")
    if visibility_scope not in {"local", "private", "workspace"}:
        raise service_error(
            400,
            code="definition_source_invalid",
            category="validation_error",
            message="visibility_scope must be 'local', 'private' or 'workspace'.",
        )
    return CircuitDefinitionDraft(
        name=name,
        source_text=source_text,
        visibility_scope=cast(Any, visibility_scope),
    )


def _parse_definition_update_payload(payload: object) -> CircuitDefinitionUpdate:
    body = _as_mapping(payload)
    source_text = _required_string(body, "source_text")
    name = _optional_string(body.get("name"))
    concurrency_token = _optional_string(body.get("concurrency_token"))
    return CircuitDefinitionUpdate(
        source_text=source_text,
        name=name,
        concurrency_token=concurrency_token,
    )


def _parse_definition_clone_payload(payload: object | None) -> CircuitDefinitionCloneDraft:
    if payload is None:
        return CircuitDefinitionCloneDraft()
    body = _as_mapping(payload)
    return CircuitDefinitionCloneDraft(name=_optional_string(body.get("name")))


def _parse_schemdraw_request(payload: object) -> SchemdrawRenderRequest:
    body = _as_mapping(payload)
    relation_config = body.get("relation_config")
    if not isinstance(relation_config, dict):
        raise service_error(
            400,
            code="schemdraw_relation_invalid",
            category="validation_error",
            message="relation_config must be an object.",
        )
    linked_schema_payload = body.get("linked_schema")
    linked_schema = None
    if linked_schema_payload is not None:
        linked_schema_mapping = _as_mapping(linked_schema_payload)
        linked_schema = SchemdrawLinkedSchema(
            definition_id=_required_int(linked_schema_mapping, "definition_id"),
            workspace_id=_required_string(linked_schema_mapping, "workspace_id"),
            name=_required_string(linked_schema_mapping, "name"),
            source_hash=_optional_string(linked_schema_mapping.get("source_hash")),
        )
    render_mode = _optional_string(body.get("render_mode")) or "debounced"
    if render_mode not in {"debounced", "manual"}:
        raise service_error(
            400,
            code="schemdraw_relation_invalid",
            category="validation_error",
            message="render_mode must be 'debounced' or 'manual'.",
        )
    return SchemdrawRenderRequest(
        source_text=_required_string(body, "source_text"),
        relation_config=relation_config,
        linked_schema=linked_schema,
        document_version=_required_int(body, "document_version"),
        request_id=_required_string(body, "request_id"),
        render_mode=cast(Any, render_mode),
    )


def _serialize_definition_summary(summary: CircuitDefinitionSummary) -> dict[str, object]:
    return {
        "definition_id": summary.definition_id,
        "name": summary.name,
        "created_at": summary.created_at,
        "visibility_scope": summary.visibility_scope,
        "owner_display_name": summary.owner_display_name,
        "allowed_actions": _serialize_allowed_actions(summary.allowed_actions),
    }


def _serialize_definition_detail(detail: CircuitDefinitionDetail) -> dict[str, object]:
    return {
        "definition_id": detail.definition_id,
        "workspace_id": detail.workspace_id,
        "visibility_scope": detail.visibility_scope,
        "lifecycle_state": detail.lifecycle_state,
        "owner_user_id": detail.owner_user_id,
        "owner_display_name": detail.owner_display_name,
        "allowed_actions": _serialize_allowed_actions(detail.allowed_actions),
        "name": detail.name,
        "created_at": detail.created_at,
        "updated_at": detail.updated_at,
        "concurrency_token": detail.concurrency_token,
        "source_hash": detail.source_hash,
        "source_text": detail.source_text,
        "normalized_output": detail.normalized_output,
        "validation_notices": [
            _serialize_validation_notice(notice) for notice in detail.validation_notices
        ],
        "validation_summary": {
            "status": detail.validation_summary.status,
            "notice_count": detail.validation_summary.notice_count,
            "warning_count": detail.validation_summary.warning_count,
            "blocking_notice_count": detail.validation_summary.blocking_notice_count,
        },
        "preview_artifacts": list(detail.preview_artifacts),
        "lineage_parent_id": detail.lineage_parent_id,
    }


def _serialize_schemdraw_result(result: SchemdrawRenderResult) -> dict[str, object]:
    return {
        "request_id": result.request_id,
        "document_version": result.document_version,
        "status": result.status,
        "svg": result.svg,
        "diagnostics": [_serialize_schemdraw_diagnostic(item) for item in result.diagnostics],
        "cursor_position": (
            None
            if result.cursor_position is None
            else {
                "x": result.cursor_position.x,
                "y": result.cursor_position.y,
            }
        ),
        "probe_points": [
            {
                "name": item.name,
                "x": item.x,
                "y": item.y,
            }
            for item in result.probe_points
        ],
        "render_time_ms": result.render_time_ms,
        "preview_metadata": (
            None
            if result.preview_metadata is None
            else {
                "width": result.preview_metadata.width,
                "height": result.preview_metadata.height,
                "view_box": result.preview_metadata.view_box,
                "source_line_count": result.preview_metadata.source_line_count,
                "linked_definition_id": result.preview_metadata.linked_definition_id,
            }
        ),
    }


def _serialize_allowed_actions(allowed_actions: object) -> dict[str, bool]:
    return {
        "update": bool(allowed_actions.update),
        "delete": bool(allowed_actions.delete),
        "publish": bool(allowed_actions.publish),
        "clone": bool(allowed_actions.clone),
    }


def _serialize_validation_notice(notice: ValidationNotice) -> dict[str, object]:
    return {
        "severity": notice.severity,
        "code": notice.code,
        "message": notice.message,
        "source": notice.source,
        "blocking": notice.blocking,
    }


def _serialize_schemdraw_diagnostic(diagnostic: SchemdrawDiagnostic) -> dict[str, object]:
    return {
        "severity": diagnostic.severity,
        "code": diagnostic.code,
        "message": diagnostic.message,
        "source": diagnostic.source,
        "blocking": diagnostic.blocking,
        "line": diagnostic.line,
        "column": diagnostic.column,
    }


def _service_error_response(exc: ServiceError) -> JSONResponse:
    details: dict[str, object] = {}
    if len(exc.field_errors) > 0:
        details["field_errors"] = [
            {"field": field_error.field, "message": field_error.message}
            for field_error in exc.field_errors
        ]
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "ok": False,
            "error": {
                "code": exc.code,
                "category": exc.category,
                "message": exc.message,
                "retryable": False,
                "details": details or None,
                "debug_ref": current_debug_ref(),
            },
        },
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


def _collection_meta(
    *,
    page: CircuitDefinitionCatalogPage,
    limit: int,
    filter_echo: dict[str, object],
) -> dict[str, object]:
    return {
        "generated_at": _generated_at(),
        "limit": limit,
        "next_cursor": page.next_cursor,
        "prev_cursor": page.prev_cursor,
        "has_more": page.has_more,
        "filter_echo": filter_echo,
    }


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


def _required_string(payload: dict[str, object], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or len(value.strip()) == 0:
        raise service_error(
            400,
            code="request_validation_failed",
            category="validation_error",
            message=f"{key} must be a non-empty string.",
        )
    return value.strip()


def _required_int(payload: dict[str, object], key: str) -> int:
    value = payload.get(key)
    if not isinstance(value, int):
        raise service_error(
            400,
            code="request_validation_failed",
            category="validation_error",
            message=f"{key} must be an integer.",
        )
    return value


def _optional_string(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = value.strip()
    return normalized or None


def _normalize_optional_string(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    return normalized or None


router.include_router(definitions_router)
router.include_router(schemdraw_router)
