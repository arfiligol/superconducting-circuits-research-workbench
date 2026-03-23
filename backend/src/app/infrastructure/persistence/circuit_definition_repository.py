from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from src.app.domain.circuit_definitions import (
    CircuitDefinitionRecord,
    ValidationNotice,
    ValidationSummary,
)
from src.app.infrastructure.persistence.models import RewriteCircuitDefinitionRecord


class SqliteCircuitDefinitionRepository:
    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    def list_all_circuit_definitions(self) -> tuple[CircuitDefinitionRecord, ...]:
        with self._session_factory() as session:
            rows = session.scalars(
                select(RewriteCircuitDefinitionRecord).order_by(
                    RewriteCircuitDefinitionRecord.created_at_iso.asc(),
                    RewriteCircuitDefinitionRecord.definition_id.asc(),
                )
            ).all()
            return tuple(_to_record(row) for row in rows)

    def save_circuit_definition(self, record: CircuitDefinitionRecord) -> None:
        with self._session_factory() as session:
            row = session.scalar(
                select(RewriteCircuitDefinitionRecord).where(
                    RewriteCircuitDefinitionRecord.definition_id == record.definition_id
                )
            )
            if row is None:
                row = RewriteCircuitDefinitionRecord(definition_id=record.definition_id)
                session.add(row)
            _apply_record(row, record)
            session.commit()


def _apply_record(
    row: RewriteCircuitDefinitionRecord,
    record: CircuitDefinitionRecord,
) -> None:
    row.workspace_id = record.workspace_id
    row.visibility_scope = record.visibility_scope
    row.lifecycle_state = record.lifecycle_state
    row.owner_user_id = record.owner_user_id
    row.owner_display_name = record.owner_display_name
    row.name = record.name
    row.created_at_iso = record.created_at
    row.updated_at_iso = record.updated_at
    row.concurrency_token = record.concurrency_token
    row.source_hash = record.source_hash
    row.source_text = record.source_text
    row.normalized_output = record.normalized_output
    row.validation_notices_json = [
        {
            "severity": notice.severity,
            "code": notice.code,
            "message": notice.message,
            "source": notice.source,
            "blocking": notice.blocking,
        }
        for notice in record.validation_notices
    ]
    row.validation_summary_json = {
        "status": record.validation_summary.status,
        "notice_count": record.validation_summary.notice_count,
        "warning_count": record.validation_summary.warning_count,
        "blocking_notice_count": record.validation_summary.blocking_notice_count,
    }
    row.preview_artifacts_json = list(record.preview_artifacts)
    row.lineage_parent_id = record.lineage_parent_id


def _to_record(row: RewriteCircuitDefinitionRecord) -> CircuitDefinitionRecord:
    validation_summary = row.validation_summary_json
    return CircuitDefinitionRecord(
        definition_id=row.definition_id,
        workspace_id=row.workspace_id,
        visibility_scope=row.visibility_scope,
        lifecycle_state=row.lifecycle_state,
        owner_user_id=row.owner_user_id,
        owner_display_name=row.owner_display_name,
        name=row.name,
        created_at=row.created_at_iso,
        updated_at=row.updated_at_iso,
        concurrency_token=row.concurrency_token,
        source_hash=row.source_hash,
        source_text=row.source_text,
        normalized_output=row.normalized_output,
        validation_notices=tuple(
            ValidationNotice(
                severity=str(notice.get("severity", "warning")),
                code=str(notice.get("code", "unknown")),
                message=str(notice.get("message", "")),
                source=str(notice.get("source", "definition")),
                blocking=bool(notice.get("blocking", False)),
            )
            for notice in row.validation_notices_json
        ),
        validation_summary=ValidationSummary(
            status=str(validation_summary.get("status", "warning")),
            notice_count=int(validation_summary.get("notice_count", 0)),
            warning_count=int(validation_summary.get("warning_count", 0)),
            blocking_notice_count=int(validation_summary.get("blocking_notice_count", 0)),
        ),
        preview_artifacts=tuple(str(artifact) for artifact in row.preview_artifacts_json),
        lineage_parent_id=row.lineage_parent_id,
    )
