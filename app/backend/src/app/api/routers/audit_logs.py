from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse

from src.app.domain.audit import AuditListQuery
from src.app.infrastructure.request_debug import current_debug_ref
from src.app.infrastructure.runtime import get_audit_log_service
from src.app.services.audit_log_service import AuditLogService
from src.app.services.service_errors import ServiceError, service_error

router = APIRouter(prefix="/audit-logs", tags=["audit-logs"])


@router.get("")
def list_audit_logs(
    audit_log_service: Annotated[AuditLogService, Depends(get_audit_log_service)],
    workspace_id: Annotated[str | None, Query(min_length=1)] = None,
    actor_user_id: Annotated[str | None, Query(min_length=1)] = None,
    action_kind: Annotated[str | None, Query(min_length=1)] = None,
    resource_kind: Annotated[str | None, Query(min_length=1)] = None,
    outcome: Annotated[str | None, Query()] = None,
    after: Annotated[str | None, Query(min_length=1)] = None,
    before: Annotated[str | None, Query(min_length=1)] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> JSONResponse:
    try:
        query = _build_list_query(
            workspace_id=workspace_id,
            actor_user_id=actor_user_id,
            action_kind=action_kind,
            resource_kind=resource_kind,
            outcome=outcome,
            after=after,
            before=before,
            limit=limit,
        )
        view = audit_log_service.list_audit_logs(query)
    except ServiceError as exc:
        return _service_error_response(exc)
    return _success_response(
        data={
            "rows": [
                {
                    "audit_id": row.audit_id,
                    "occurred_at": row.occurred_at,
                    "workspace_id": row.workspace_id,
                    "actor_summary": {
                        "user_id": row.actor_summary.user_id,
                        "display_name": row.actor_summary.display_name,
                    },
                    "action_kind": row.action_kind,
                    "resource_kind": row.resource_kind,
                    "resource_id": row.resource_id,
                    "outcome": row.outcome,
                    "correlation_id": row.correlation_id,
                }
                for row in view.rows
            ]
        },
        meta={
            "generated_at": _generated_at(),
            "limit": query.limit,
            "next_cursor": view.next_cursor,
            "prev_cursor": view.prev_cursor,
            "has_more": view.has_more,
            "filter_echo": {
                "workspace_id": view.filter_echo.workspace_id,
                "actor_user_id": view.filter_echo.actor_user_id,
                "action_kind": view.filter_echo.action_kind,
                "resource_kind": view.filter_echo.resource_kind,
                "outcome": view.filter_echo.outcome,
                "after": view.filter_echo.after,
                "before": view.filter_echo.before,
            },
            "total_count": view.total_count,
        },
    )


@router.get("/export-summary")
def get_export_summary(
    audit_log_service: Annotated[AuditLogService, Depends(get_audit_log_service)],
    workspace_id: Annotated[str | None, Query(min_length=1)] = None,
    actor_user_id: Annotated[str | None, Query(min_length=1)] = None,
    action_kind: Annotated[str | None, Query(min_length=1)] = None,
    resource_kind: Annotated[str | None, Query(min_length=1)] = None,
    outcome: Annotated[str | None, Query()] = None,
) -> JSONResponse:
    try:
        query = _build_list_query(
            workspace_id=workspace_id,
            actor_user_id=actor_user_id,
            action_kind=action_kind,
            resource_kind=resource_kind,
            outcome=outcome,
            after=None,
            before=None,
            limit=50,
        )
        summary = audit_log_service.get_export_summary(query)
    except ServiceError as exc:
        return _service_error_response(exc)
    return _success_response(
        data={
            "export_id": summary.export_id,
            "status": summary.status,
            "workspace_id": summary.workspace_id,
            "filter_echo": {
                "workspace_id": summary.filter_echo.workspace_id,
                "actor_user_id": summary.filter_echo.actor_user_id,
                "action_kind": summary.filter_echo.action_kind,
                "resource_kind": summary.filter_echo.resource_kind,
                "outcome": summary.filter_echo.outcome,
            },
            "artifact_ref": (
                {
                    "artifact_id": summary.artifact_ref.artifact_id,
                    "backend": summary.artifact_ref.backend,
                    "format": summary.artifact_ref.format,
                    "locator": summary.artifact_ref.locator,
                }
                if summary.artifact_ref is not None
                else None
            ),
        },
        meta={"generated_at": _generated_at()},
    )


@router.get("/{audit_id}")
def get_audit_detail(
    audit_id: str,
    audit_log_service: Annotated[AuditLogService, Depends(get_audit_log_service)],
) -> JSONResponse:
    try:
        detail = audit_log_service.get_audit_detail(audit_id)
    except ServiceError as exc:
        return _service_error_response(exc)
    return _success_response(
        data={
            "audit_id": detail.audit_id,
            "occurred_at": detail.occurred_at,
            "actor_user_id": detail.actor_user_id,
            "session_id": detail.session_id,
            "correlation_id": detail.correlation_id,
            "workspace_id": detail.workspace_id,
            "action_kind": detail.action_kind,
            "resource_kind": detail.resource_kind,
            "resource_id": detail.resource_id,
            "outcome": detail.outcome,
            "payload": detail.payload,
            "debug_ref": detail.debug_ref,
        },
        meta={"generated_at": _generated_at()},
    )


def _build_list_query(
    *,
    workspace_id: str | None,
    actor_user_id: str | None,
    action_kind: str | None,
    resource_kind: str | None,
    outcome: str | None,
    after: str | None,
    before: str | None,
    limit: int,
) -> AuditListQuery:
    if outcome is not None and outcome not in {"accepted", "rejected", "completed", "failed"}:
        raise service_error(
            400,
            code="audit_query_invalid",
            category="validation_error",
            message="outcome must be accepted, rejected, completed, or failed.",
        )
    return AuditListQuery(
        workspace_id=workspace_id,
        actor_user_id=actor_user_id,
        action_kind=action_kind,
        resource_kind=resource_kind,
        outcome=outcome,  # type: ignore[arg-type]
        after=after,
        before=before,
        limit=limit,
    )


def _success_response(
    *,
    data: dict[str, object],
    meta: dict[str, object] | None = None,
    status_code: int = 200,
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
