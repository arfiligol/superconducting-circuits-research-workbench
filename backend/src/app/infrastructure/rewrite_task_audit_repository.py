from __future__ import annotations

from src.app.domain.audit import AuditListQuery, AuditRecord

_AUDIT_RECORDS: list[AuditRecord] = []


class InMemoryTaskAuditRepository:
    def append(self, record: AuditRecord) -> AuditRecord:
        _AUDIT_RECORDS.append(record)
        return record

    def clear(self) -> None:
        _AUDIT_RECORDS.clear()

    def list_records(self) -> tuple[AuditRecord, ...]:
        return tuple(_sort_records(_AUDIT_RECORDS))

    def list_records_for_resource(
        self,
        *,
        resource_kind: str,
        resource_id: str,
    ) -> tuple[AuditRecord, ...]:
        return tuple(
            record
            for record in _sort_records(_AUDIT_RECORDS)
            if record.resource_kind == resource_kind and record.resource_id == resource_id
        )

    def get_record(self, audit_id: str) -> AuditRecord | None:
        for record in _AUDIT_RECORDS:
            if record.audit_id == audit_id:
                return record
        return None

    def query_records(self, query: AuditListQuery) -> tuple[AuditRecord, ...]:
        records = [
            record
            for record in _sort_records(_AUDIT_RECORDS)
            if _matches_query(record, query)
        ]
        if query.after is not None:
            after_index = _find_record_index(records, query.after)
            if after_index is None:
                return ()
            records = records[after_index + 1 :]
        if query.before is not None:
            before_index = _find_record_index(records, query.before)
            if before_index is None:
                return ()
            records = records[:before_index]
        return tuple(records)


def _matches_query(record: AuditRecord, query: AuditListQuery) -> bool:
    if query.workspace_id is not None and record.workspace_id != query.workspace_id:
        return False
    if query.actor_user_id is not None and record.actor_user_id != query.actor_user_id:
        return False
    if query.action_kind is not None and record.action_kind != query.action_kind:
        return False
    if query.resource_kind is not None and record.resource_kind != query.resource_kind:
        return False
    return query.outcome is None or record.outcome == query.outcome


def _sort_records(records: list[AuditRecord]) -> list[AuditRecord]:
    return sorted(
        records,
        key=lambda record: (record.occurred_at, record.audit_id),
        reverse=True,
    )


def _find_record_index(records: list[AuditRecord], audit_id: str) -> int | None:
    for index, record in enumerate(records):
        if record.audit_id == audit_id:
            return index
    return None
