from __future__ import annotations

from hashlib import sha1
from typing import Protocol

from src.app.domain.audit import (
    AuditActorSummary,
    AuditArtifactRef,
    AuditDetail,
    AuditExportSummary,
    AuditListQuery,
    AuditListRow,
    AuditListView,
    AuditRecord,
)
from src.app.domain.session import SessionState
from src.app.infrastructure.casbin_authorization import CasbinAuthorizationAdapter
from src.app.services.authorization_service import AuthorizationService
from src.app.services.service_errors import service_error


class AuditLogRepository(Protocol):
    def get_record(self, audit_id: str) -> AuditRecord | None: ...

    def query_records(self, query: AuditListQuery) -> tuple[AuditRecord, ...]: ...


class AuditSessionRepository(Protocol):
    def get_session_state(self) -> SessionState: ...


class AuditLogService:
    def __init__(
        self,
        repository: AuditLogRepository,
        session_repository: AuditSessionRepository,
        authorization_service: AuthorizationService | None = None,
    ) -> None:
        self._repository = repository
        self._session_repository = session_repository
        self._authorization_service = authorization_service or AuthorizationService(
            CasbinAuthorizationAdapter()
        )

    def list_audit_logs(self, query: AuditListQuery) -> AuditListView:
        resolved_query = self._resolve_query(query, export=False)
        records = self._repository.query_records(resolved_query)
        rows = tuple(_to_list_row(record) for record in records[: resolved_query.limit])
        return AuditListView(
            rows=rows,
            total_count=len(records),
            next_cursor=rows[-1].audit_id if len(records) > resolved_query.limit and len(rows) > 0 else None,
            prev_cursor=resolved_query.before,
            has_more=len(records) > resolved_query.limit,
            filter_echo=resolved_query,
        )

    def get_audit_detail(self, audit_id: str) -> AuditDetail:
        record = self._repository.get_record(audit_id)
        if record is None:
            raise service_error(
                404,
                code="audit_record_not_found",
                category="not_found",
                message=f"Audit record {audit_id} was not found.",
            )
        workspace_id = self._resolve_workspace_access(record.workspace_id)
        if workspace_id != record.workspace_id:
            raise service_error(
                403,
                code="audit_access_denied",
                category="permission_denied",
                message="The current session cannot access this audit record.",
            )
        return AuditDetail(
            audit_id=record.audit_id,
            occurred_at=record.occurred_at,
            actor_user_id=record.actor_user_id,
            session_id=record.session_id,
            correlation_id=record.correlation_id,
            workspace_id=record.workspace_id,
            action_kind=record.action_kind,
            resource_kind=record.resource_kind,
            resource_id=record.resource_id,
            outcome=record.outcome,
            payload=_redact_payload(record.payload),
            debug_ref=record.debug_ref,
        )

    def get_export_summary(self, query: AuditListQuery) -> AuditExportSummary:
        resolved_query = self._resolve_query(query, export=True)
        export_id = _build_export_id(resolved_query)
        workspace_id = resolved_query.workspace_id
        return AuditExportSummary(
            export_id=export_id,
            status="completed",
            workspace_id=workspace_id,
            filter_echo=resolved_query,
            artifact_ref=AuditArtifactRef(
                artifact_id=f"artifact:{export_id}",
                backend="audit_export_preview",
                format="ndjson",
                locator=f"audit-exports/{workspace_id or 'global'}/{export_id}.ndjson",
            ),
        )

    def _resolve_query(self, query: AuditListQuery, *, export: bool) -> AuditListQuery:
        if query.after is not None and query.before is not None:
            raise service_error(
                400,
                code="audit_query_invalid" if not export else "audit_export_denied",
                category="validation_error",
                message="after and before cannot be used together.",
            )
        workspace_id = self._resolve_workspace_access(
            query.workspace_id,
            export=export,
        )
        return AuditListQuery(
            workspace_id=workspace_id,
            actor_user_id=query.actor_user_id,
            action_kind=query.action_kind,
            resource_kind=query.resource_kind,
            outcome=query.outcome,
            after=query.after,
            before=query.before,
            limit=query.limit,
        )

    def _resolve_workspace_access(
        self,
        workspace_id: str | None,
        *,
        export: bool = False,
    ) -> str | None:
        state = self._session_repository.get_session_state()
        if not self._authorization_service.is_allowed(
            state,
            "view_audit_log",
            resource=_workspace_resource(state.workspace_id),
        ):
            raise service_error(
                403,
                code="audit_export_denied" if export else "audit_access_denied",
                category="permission_denied",
                message="The current session cannot view audit logs.",
            )
        if workspace_id is None:
            return state.workspace_id if not _is_admin(state) else None
        if workspace_id == state.workspace_id:
            return workspace_id
        if _is_admin(state):
            return workspace_id
        raise service_error(
            403,
            code="audit_export_denied" if export else "audit_access_denied",
            category="permission_denied",
            message="The current session cannot query audit logs outside the active workspace.",
        )


def _to_list_row(record: AuditRecord) -> AuditListRow:
    return AuditListRow(
        audit_id=record.audit_id,
        occurred_at=record.occurred_at,
        workspace_id=record.workspace_id,
        actor_summary=AuditActorSummary(
            user_id=record.actor_user_id,
            display_name=record.actor_display_name,
        ),
        action_kind=record.action_kind,
        resource_kind=record.resource_kind,
        resource_id=record.resource_id,
        outcome=record.outcome,
        correlation_id=record.correlation_id,
    )


def _build_export_id(query: AuditListQuery) -> str:
    signature = sha1(
        "|".join(
            str(item)
            for item in (
                query.workspace_id,
                query.actor_user_id,
                query.action_kind,
                query.resource_kind,
                query.outcome,
            )
        ).encode("utf-8")
    ).hexdigest()[:12]
    return f"audit-export:{query.workspace_id or 'global'}:{signature}"


def _is_admin(state: SessionState) -> bool:
    return state.user is not None and state.user.platform_role == "admin"


def _workspace_resource(workspace_id: str):
    from src.app.domain.authorization import AuthorizationResourceEnvelope

    return AuthorizationResourceEnvelope(
        resource_kind="audit_log",
        workspace_id=workspace_id,
        owner_user_id=None,
        visibility_scope="workspace",
        lifecycle_state="active",
    )


def _redact_payload(payload: dict[str, object]) -> dict[str, object]:
    redacted: dict[str, object] = {}
    for key, value in payload.items():
        if _is_sensitive_field(key):
            redacted[key] = "[redacted]"
            continue
        if isinstance(value, dict):
            redacted[key] = _redact_payload(value)
            continue
        redacted[key] = value
    return redacted


def _is_sensitive_field(field_name: str) -> bool:
    normalized = field_name.casefold()
    return any(
        token in normalized
        for token in (
            "secret",
            "token",
            "password",
            "credential",
            "connection_string",
            "payload_body",
            "request_body",
            "store_uri",
        )
    )
