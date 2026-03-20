"""Repository for AuditLogRecord operations."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from copy import deepcopy
from typing import Any

from sc_core.execution import ExecutionEventLog, TaskExecutionOperation
from sqlalchemy import desc
from sqlmodel import Session, col, select

from core.shared.persistence.models import AuditLogRecord

_REDACTED_AUDIT_KEYS = frozenset(
    {
        "access_token",
        "api_key",
        "authorization",
        "cookie",
        "password",
        "password_hash",
        "refresh_token",
        "secret",
        "token",
    }
)
_OMITTED_AUDIT_KEYS = frozenset(
    {
        "axes_values",
        "axis_payload",
        "axis_values",
        "inline_values",
        "numeric_payload",
        "payload_values",
        "trace_values",
        "values",
    }
)


def _sanitize_audit_payload_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        return _sanitize_audit_payload(dict(value))
    if isinstance(value, Sequence) and not isinstance(value, str | bytes | bytearray):
        return [_sanitize_audit_payload_value(item) for item in value]
    return deepcopy(value)


def _sanitize_audit_payload(payload: dict[str, Any]) -> dict[str, Any]:
    sanitized: dict[str, Any] = {}
    for raw_key, raw_value in payload.items():
        key = str(raw_key)
        normalized_key = key.strip().casefold()
        if normalized_key in _REDACTED_AUDIT_KEYS:
            sanitized[key] = "[REDACTED]"
            continue
        if normalized_key in _OMITTED_AUDIT_KEYS:
            sanitized[key] = "[OMITTED]"
            continue
        sanitized[key] = _sanitize_audit_payload_value(raw_value)
    return sanitized


class AuditLogRepository:
    """Repository for actor-scoped audit log rows."""

    def __init__(self, session: Session):
        self._session = session

    def append_execution_event(
        self,
        *,
        actor_id: int | None,
        event: ExecutionEventLog,
    ) -> AuditLogRecord:
        """Append one canonical execution event to the audit log."""
        return self.append_log(
            actor_id=actor_id,
            action_kind=event.action_kind,
            resource_kind=event.resource_kind,
            resource_id=event.resource_id,
            summary=event.summary,
            payload=event.payload,
        )

    def append_execution_operation(
        self,
        operation: TaskExecutionOperation,
    ) -> AuditLogRecord | None:
        """Append the audit event carried by one canonical persisted-task operation."""
        if operation.event_log is None:
            return None
        return self.append_execution_event(
            actor_id=operation.actor_id,
            event=operation.event_log,
        )

    def append_log(
        self,
        *,
        actor_id: int | None,
        action_kind: str,
        resource_kind: str,
        resource_id: str | int,
        summary: str,
        payload: dict[str, Any] | None = None,
    ) -> AuditLogRecord:
        """Append and flush one redaction-safe audit log row."""
        log = AuditLogRecord(
            actor_id=actor_id,
            action_kind=action_kind,
            resource_kind=resource_kind,
            resource_id=str(resource_id),
            summary=summary,
            payload=_sanitize_audit_payload(dict(payload or {})),
        )
        self._session.add(log)
        self._session.flush()
        return log

    def list_logs(self) -> list[AuditLogRecord]:
        """List audit logs newest first."""
        statement = select(AuditLogRecord).order_by(
            desc(col(AuditLogRecord.created_at)),
            desc(col(AuditLogRecord.id)),
        )
        return list(self._session.exec(statement).all())

    def list_logs_by_actor(self, actor_id: int) -> list[AuditLogRecord]:
        """List audit logs for one actor, newest first."""
        statement = (
            select(AuditLogRecord)
            .where(col(AuditLogRecord.actor_id) == actor_id)
            .order_by(
                desc(col(AuditLogRecord.created_at)),
                desc(col(AuditLogRecord.id)),
            )
        )
        return list(self._session.exec(statement).all())
