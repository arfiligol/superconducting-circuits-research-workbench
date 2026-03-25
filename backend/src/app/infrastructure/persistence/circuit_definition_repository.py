from __future__ import annotations

import sys
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from pathlib import Path
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from src.app.domain.circuit_definitions import (
    CircuitDefinitionCloneDraft,
    CircuitDefinitionDraft,
    CircuitDefinitionRecord,
    CircuitDefinitionUpdate,
    DefinitionId,
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
                select(RewriteCircuitDefinitionRecord)
                .where(RewriteCircuitDefinitionRecord.lifecycle_state != "deleted")
                .order_by(
                    RewriteCircuitDefinitionRecord.created_at_iso.asc(),
                    RewriteCircuitDefinitionRecord.definition_id.asc(),
                )
            ).all()
            return tuple(_to_record(row) for row in rows)

    def list_circuit_definitions(self) -> tuple[CircuitDefinitionRecord, ...]:
        return self.list_all_circuit_definitions()

    def get_circuit_definition(
        self,
        definition_id: DefinitionId,
    ) -> CircuitDefinitionRecord | None:
        with self._session_factory() as session:
            row = session.scalar(
                select(RewriteCircuitDefinitionRecord).where(
                    RewriteCircuitDefinitionRecord.definition_id == definition_id,
                    RewriteCircuitDefinitionRecord.lifecycle_state != "deleted",
                )
            )
            if row is None:
                return None
            return _to_record(row)

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

    def create_circuit_definition(
        self,
        *,
        workspace_id: str,
        owner_user_id: str,
        owner_display_name: str,
        draft: CircuitDefinitionDraft,
    ) -> CircuitDefinitionRecord:
        definition_id = str(uuid4())
        created_at = _current_timestamp()
        record = _build_circuit_definition_record(
            definition_id=definition_id,
            workspace_id=workspace_id,
            visibility_scope=draft.visibility_scope,
            owner_user_id=owner_user_id,
            owner_display_name=owner_display_name,
            name=draft.name,
            created_at=created_at,
            updated_at=created_at,
            concurrency_token=f"etag_{definition_id}_1",
            source_text=draft.source_text,
        )
        self.save_circuit_definition(record)
        return record

    def update_circuit_definition(
        self,
        definition_id: DefinitionId,
        update: CircuitDefinitionUpdate,
    ) -> CircuitDefinitionRecord | None:
        current = self.get_circuit_definition(definition_id)
        if current is None:
            return None
        if (
            update.concurrency_token is not None
            and update.concurrency_token != current.concurrency_token
        ):
            return None
        inspection = _inspect_circuit_definition(update.source_text)
        updated = CircuitDefinitionRecord(
            definition_id=current.definition_id,
            workspace_id=current.workspace_id,
            visibility_scope=current.visibility_scope,
            lifecycle_state=current.lifecycle_state,
            owner_user_id=current.owner_user_id,
            owner_display_name=current.owner_display_name,
            name=update.name or current.name,
            created_at=current.created_at,
            updated_at=_advance_timestamp(current.updated_at, minutes=1),
            concurrency_token=_next_concurrency_token(current.concurrency_token),
            source_hash=_source_hash(update.source_text),
            source_text=update.source_text,
            normalized_output=inspection.normalized_output,
            validation_notices=inspection.validation_notices,
            validation_summary=inspection.validation_summary,
            preview_artifacts=current.preview_artifacts,
            lineage_parent_id=current.lineage_parent_id,
        )
        self.save_circuit_definition(updated)
        return updated

    def publish_circuit_definition(
        self,
        definition_id: DefinitionId,
    ) -> CircuitDefinitionRecord | None:
        current = self.get_circuit_definition(definition_id)
        if current is None:
            return None
        updated = CircuitDefinitionRecord(
            **{
                **current.__dict__,
                "visibility_scope": "workspace",
                "updated_at": _advance_timestamp(current.updated_at, minutes=2),
                "concurrency_token": _next_concurrency_token(current.concurrency_token),
            }
        )
        self.save_circuit_definition(updated)
        return updated

    def clone_circuit_definition(
        self,
        *,
        source_definition_id: DefinitionId,
        workspace_id: str,
        owner_user_id: str,
        owner_display_name: str,
        draft: CircuitDefinitionCloneDraft,
    ) -> CircuitDefinitionRecord | None:
        source = self.get_circuit_definition(source_definition_id)
        if source is None:
            return None
        definition_id = str(uuid4())
        created_at = _current_timestamp()
        cloned = _build_circuit_definition_record(
            definition_id=definition_id,
            workspace_id=workspace_id,
            visibility_scope="local" if workspace_id == "local-space" else "private",
            owner_user_id=owner_user_id,
            owner_display_name=owner_display_name,
            name=draft.name or f"{source.name} Copy",
            created_at=created_at,
            updated_at=created_at,
            concurrency_token=f"etag_{definition_id}_1",
            source_text=source.source_text,
            lineage_parent_id=source.definition_id,
        )
        self.save_circuit_definition(cloned)
        return cloned

    def delete_circuit_definition(self, definition_id: DefinitionId) -> bool:
        current = self.get_circuit_definition(definition_id)
        if current is None:
            return False
        deleted = CircuitDefinitionRecord(
            **{
                **current.__dict__,
                "lifecycle_state": "deleted",
                "updated_at": _advance_timestamp(current.updated_at, minutes=3),
                "concurrency_token": _next_concurrency_token(current.concurrency_token),
            }
        )
        self.save_circuit_definition(deleted)
        return True


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


class _CircuitInspectionResult:
    def __init__(
        self,
        *,
        normalized_output: str,
        validation_notices: tuple[ValidationNotice, ...],
        validation_summary: ValidationSummary,
    ) -> None:
        self.normalized_output = normalized_output
        self.validation_notices = validation_notices
        self.validation_summary = validation_summary


def _build_circuit_definition_record(
    *,
    definition_id: DefinitionId,
    workspace_id: str,
    visibility_scope: str,
    owner_user_id: str,
    owner_display_name: str,
    name: str,
    created_at: str,
    updated_at: str,
    concurrency_token: str,
    source_text: str,
    lineage_parent_id: DefinitionId | None = None,
) -> CircuitDefinitionRecord:
    inspection = _inspect_circuit_definition(source_text)
    return CircuitDefinitionRecord(
        definition_id=definition_id,
        workspace_id=workspace_id,
        visibility_scope=visibility_scope,
        lifecycle_state="active",
        owner_user_id=owner_user_id,
        owner_display_name=owner_display_name,
        name=name,
        created_at=created_at,
        updated_at=updated_at,
        concurrency_token=concurrency_token,
        source_hash=_source_hash(source_text),
        source_text=source_text,
        normalized_output=inspection.normalized_output,
        validation_notices=inspection.validation_notices,
        validation_summary=inspection.validation_summary,
        preview_artifacts=(
            "expanded-netlist.json",
            "validation-summary.json",
            "schemdraw-preview.svg",
        ),
        lineage_parent_id=lineage_parent_id,
    )


def _load_circuit_domain() -> tuple[object, object, object, object, type[Exception]]:
    workspace_src = Path(__file__).resolve().parents[5] / "src"
    if str(workspace_src) not in sys.path:
        sys.path.insert(0, str(workspace_src))

    from core.simulation.domain.circuit import (
        expand_circuit_definition,
        format_circuit_definition,
        format_expanded_circuit_definition,
        parse_circuit_definition_source,
    )
    from core.simulation.domain.validators import CircuitValidationError

    return (
        parse_circuit_definition_source,
        expand_circuit_definition,
        format_circuit_definition,
        format_expanded_circuit_definition,
        CircuitValidationError,
    )


def _inspect_circuit_definition(source_text: str) -> _CircuitInspectionResult:
    (
        parse_circuit_definition_source,
        expand_circuit_definition,
        format_circuit_definition,
        format_expanded_circuit_definition,
        validation_error_type,
    ) = _load_circuit_domain()
    try:
        parsed = parse_circuit_definition_source(source_text)
        expanded = expand_circuit_definition(parsed)
    except validation_error_type as exc:
        raise ValueError(str(exc)) from exc
    except (TypeError, ValueError) as exc:
        raise ValueError(str(exc)) from exc

    notices = (
        ValidationNotice(
            severity="info",
            code="definition_parsed",
            message="Circuit definition source was parsed successfully.",
            source="circuit_netlist",
            blocking=False,
        ),
        ValidationNotice(
            severity="info",
            code="definition_expanded",
            message=(
                f"Expanded netlist contains {len(expanded.components)} components and "
                f"{len(expanded.topology)} topology rows."
            ),
            source="circuit_netlist",
            blocking=False,
        ),
        ValidationNotice(
            severity="info",
            code="layout_profile_inferred",
            message=f"Preview layout profile: {parsed.effective_layout_profile}.",
            source="circuit_netlist",
            blocking=False,
        ),
    )
    return _CircuitInspectionResult(
        normalized_output=(
            "{\n"
            f'  "source": {format_circuit_definition(parsed)!r},\n'
            f'  "expanded": {format_expanded_circuit_definition(parsed)!r}\n'
            "}"
        ),
        validation_notices=notices,
        validation_summary=ValidationSummary(
            status="valid",
            notice_count=len(notices),
            warning_count=0,
            blocking_notice_count=0,
        ),
    )


def _current_timestamp() -> str:
    return datetime.now(UTC).replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%SZ")


def _advance_timestamp(current_timestamp: str, *, minutes: int) -> str:
    parsed = datetime.fromisoformat(current_timestamp.replace("Z", "+00:00"))
    return (parsed + timedelta(minutes=minutes)).astimezone(UTC).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )


def _next_concurrency_token(current_token: str) -> str:
    prefix, _, suffix = current_token.rpartition("_")
    if suffix.isdigit():
        return f"{prefix}_{int(suffix) + 1}"
    return f"{current_token}_next"


def _source_hash(source_text: str) -> str:
    return sha256(source_text.encode("utf-8")).hexdigest()[:12]
