from __future__ import annotations

from typing import cast

from sqlalchemy import Select, or_, select
from sqlalchemy.orm import Session, sessionmaker

from app_backend.domain.storage import (
    MetadataRecordRef,
    MetadataRecordType,
    ResultHandleKind,
    ResultHandleRef,
    ResultHandleStatus,
    ResultPayloadBackend,
    ResultPayloadFormat,
    ResultPayloadRole,
    ResultProvenanceRef,
    TracePayloadBackend,
    TracePayloadRef,
    TracePayloadRole,
)
from app_backend.infrastructure.persistence.models import (
    RewriteResultHandleRecord,
    RewriteStorageRecord,
    RewriteTracePayloadRecord,
)


class SqliteRewriteStorageMetadataRepository:
    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    def save_storage_record(self, record: MetadataRecordRef) -> MetadataRecordRef:
        with self._session_factory() as session:
            row = self._upsert_storage_record(session, record)
            session.commit()
            return _to_metadata_record_ref(row)

    def get_storage_record(self, record_id: str) -> MetadataRecordRef | None:
        with self._session_factory() as session:
            row = self._get_storage_record(session, record_id)
            if row is None:
                return None
            return _to_metadata_record_ref(row)

    def save_trace_payload(
        self,
        owner_record: MetadataRecordRef,
        trace_payload: TracePayloadRef,
        *,
        writer_version: str | None = None,
    ) -> TracePayloadRef:
        with self._session_factory() as session:
            owner_row = self._upsert_storage_record(session, owner_record)
            row = session.scalar(
                select(RewriteTracePayloadRecord).where(
                    RewriteTracePayloadRecord.store_key == trace_payload.store_key
                )
            )
            if row is None:
                row = RewriteTracePayloadRecord(
                    owner_record_id=owner_row.id,
                    contract_version=trace_payload.contract_version,
                    backend=trace_payload.backend,
                    payload_role=trace_payload.payload_role,
                    store_key=trace_payload.store_key,
                    store_uri=trace_payload.store_uri,
                    group_path=trace_payload.group_path,
                    array_path=trace_payload.array_path,
                    dtype=trace_payload.dtype,
                    shape=list(trace_payload.shape),
                    chunk_shape=list(trace_payload.chunk_shape),
                    schema_version=trace_payload.schema_version,
                    writer_version=writer_version,
                )
                session.add(row)
            else:
                row.owner_record_id = owner_row.id
                row.contract_version = trace_payload.contract_version
                row.backend = trace_payload.backend
                row.payload_role = trace_payload.payload_role
                row.store_uri = trace_payload.store_uri
                row.group_path = trace_payload.group_path
                row.array_path = trace_payload.array_path
                row.dtype = trace_payload.dtype
                row.shape = list(trace_payload.shape)
                row.chunk_shape = list(trace_payload.chunk_shape)
                row.schema_version = trace_payload.schema_version
                row.writer_version = writer_version
            session.commit()
            return _to_trace_payload_ref(row)

    def get_trace_payload(self, store_key: str) -> TracePayloadRef | None:
        with self._session_factory() as session:
            row = session.scalar(_select_trace_payload_by_store_key(store_key))
            if row is None:
                return None
            return _to_trace_payload_ref(row)

    def get_trace_payload_for_owner_record(self, owner_record_id: str) -> TracePayloadRef | None:
        with self._session_factory() as session:
            owner_row = self._get_storage_record(session, owner_record_id)
            if owner_row is None:
                return None
            row = session.scalar(_select_trace_payload_by_owner_row_id(owner_row.id))
            if row is None:
                return None
            return _to_trace_payload_ref(row)

    def delete_trace_payload(self, store_key: str) -> bool:
        with self._session_factory() as session:
            row = session.scalar(_select_trace_payload_by_store_key(store_key))
            if row is None:
                return False
            owner_record_id = row.owner_record_id
            session.delete(row)
            session.flush()
            self._cleanup_storage_record_if_orphan(session, owner_record_id)
            session.commit()
            return True

    def save_result_handle(self, result_handle: ResultHandleRef) -> ResultHandleRef:
        with self._session_factory() as session:
            metadata_row = self._upsert_storage_record(session, result_handle.metadata_record)
            trace_batch_row = (
                self._upsert_storage_record(session, result_handle.provenance.trace_batch_record)
                if result_handle.provenance.trace_batch_record is not None
                else None
            )
            analysis_run_row = (
                self._upsert_storage_record(session, result_handle.provenance.analysis_run_record)
                if result_handle.provenance.analysis_run_record is not None
                else None
            )
            row = session.scalar(
                select(RewriteResultHandleRecord).where(
                    RewriteResultHandleRecord.handle_id == result_handle.handle_id
                )
            )
            if row is None:
                row = RewriteResultHandleRecord(
                    metadata_record_id=metadata_row.id,
                    handle_id=result_handle.handle_id,
                    contract_version=result_handle.contract_version,
                    kind=result_handle.kind,
                    status=result_handle.status,
                    label=result_handle.label,
                    payload_backend=result_handle.payload_backend,
                    payload_format=result_handle.payload_format,
                    payload_role=result_handle.payload_role,
                    payload_locator=result_handle.payload_locator,
                    provenance_task_id=result_handle.provenance_task_id,
                    source_dataset_id=result_handle.provenance.source_dataset_id,
                    source_task_id=result_handle.provenance.source_task_id,
                    trace_batch_record_id=_record_row_id(trace_batch_row),
                    analysis_run_record_id=_record_row_id(analysis_run_row),
                )
                session.add(row)
            else:
                row.metadata_record_id = metadata_row.id
                row.contract_version = result_handle.contract_version
                row.kind = result_handle.kind
                row.status = result_handle.status
                row.label = result_handle.label
                row.payload_backend = result_handle.payload_backend
                row.payload_format = result_handle.payload_format
                row.payload_role = result_handle.payload_role
                row.payload_locator = result_handle.payload_locator
                row.provenance_task_id = result_handle.provenance_task_id
                row.source_dataset_id = result_handle.provenance.source_dataset_id
                row.source_task_id = result_handle.provenance.source_task_id
                row.trace_batch_record_id = _record_row_id(trace_batch_row)
                row.analysis_run_record_id = _record_row_id(analysis_run_row)
            session.commit()
            session.refresh(row)
            return self._load_result_handle(session, row)

    def get_result_handle(self, handle_id: str) -> ResultHandleRef | None:
        with self._session_factory() as session:
            row = session.scalar(
                select(RewriteResultHandleRecord).where(
                    RewriteResultHandleRecord.handle_id == handle_id
                )
            )
            if row is None:
                return None
            return self._load_result_handle(session, row)

    def list_result_handles_for_task(self, task_id: int) -> tuple[ResultHandleRef, ...]:
        with self._session_factory() as session:
            rows = session.scalars(
                select(RewriteResultHandleRecord)
                .where(RewriteResultHandleRecord.provenance_task_id == task_id)
                .order_by(RewriteResultHandleRecord.id.asc())
            ).all()
            return tuple(self._load_result_handle(session, row) for row in rows)

    def delete_result_handle(self, handle_id: str) -> bool:
        with self._session_factory() as session:
            row = session.scalar(
                select(RewriteResultHandleRecord).where(
                    RewriteResultHandleRecord.handle_id == handle_id
                )
            )
            if row is None:
                return False
            metadata_record_id = row.metadata_record_id
            trace_batch_record_id = row.trace_batch_record_id
            analysis_run_record_id = row.analysis_run_record_id
            session.delete(row)
            session.flush()
            for record_id in (
                metadata_record_id,
                trace_batch_record_id,
                analysis_run_record_id,
            ):
                self._cleanup_storage_record_if_orphan(session, record_id)
            session.commit()
            return True

    def _upsert_storage_record(
        self,
        session: Session,
        record: MetadataRecordRef,
    ) -> RewriteStorageRecord:
        row = self._get_storage_record(session, record.record_id)
        if row is None:
            row = RewriteStorageRecord(
                record_type=record.record_type,
                record_id=record.record_id,
                schema_version=record.schema_version,
                version=record.version,
            )
            session.add(row)
            session.flush()
            return row

        row.record_type = record.record_type
        row.schema_version = record.schema_version
        row.version = record.version
        session.flush()
        return row

    def _get_storage_record(
        self,
        session: Session,
        record_id: str,
    ) -> RewriteStorageRecord | None:
        return session.scalar(
            select(RewriteStorageRecord).where(RewriteStorageRecord.record_id == record_id)
        )

    def _cleanup_storage_record_if_orphan(
        self,
        session: Session,
        storage_record_id: int | None,
    ) -> None:
        if storage_record_id is None:
            return
        row = session.get(RewriteStorageRecord, storage_record_id)
        if row is None:
            return
        has_trace_payload = session.scalar(
            select(RewriteTracePayloadRecord.id).where(
                RewriteTracePayloadRecord.owner_record_id == storage_record_id
            )
        )
        if has_trace_payload is not None:
            return
        has_result_handle = session.scalar(
            select(RewriteResultHandleRecord.id).where(
                or_(
                    RewriteResultHandleRecord.metadata_record_id == storage_record_id,
                    RewriteResultHandleRecord.trace_batch_record_id == storage_record_id,
                    RewriteResultHandleRecord.analysis_run_record_id == storage_record_id,
                )
            )
        )
        if has_result_handle is not None:
            return
        session.delete(row)
        session.flush()

    def _load_result_handle(
        self,
        session: Session,
        row: RewriteResultHandleRecord,
    ) -> ResultHandleRef:
        trace_batch_row = (
            session.get(RewriteStorageRecord, row.trace_batch_record_id)
            if row.trace_batch_record_id is not None
            else None
        )
        analysis_run_row = (
            session.get(RewriteStorageRecord, row.analysis_run_record_id)
            if row.analysis_run_record_id is not None
            else None
        )
        metadata_row = session.get(RewriteStorageRecord, row.metadata_record_id)
        if metadata_row is None:
            raise LookupError("Result handle metadata record is missing.")
        return ResultHandleRef(
            contract_version=row.contract_version,
            handle_id=row.handle_id,
            kind=cast(ResultHandleKind, row.kind),
            status=cast(ResultHandleStatus, row.status),
            label=row.label,
            metadata_record=_to_metadata_record_ref(metadata_row),
            payload_backend=cast(ResultPayloadBackend | None, row.payload_backend),
            payload_format=cast(ResultPayloadFormat | None, row.payload_format),
            payload_role=cast(ResultPayloadRole | None, row.payload_role),
            payload_locator=row.payload_locator,
            provenance_task_id=row.provenance_task_id,
            provenance=ResultProvenanceRef(
                source_dataset_id=row.source_dataset_id,
                source_task_id=row.source_task_id,
                trace_batch_record=(
                    _to_metadata_record_ref(trace_batch_row)
                    if trace_batch_row is not None
                    else None
                ),
                analysis_run_record=(
                    _to_metadata_record_ref(analysis_run_row)
                    if analysis_run_row is not None
                    else None
                ),
            ),
        )


def _record_row_id(row: RewriteStorageRecord | None) -> int | None:
    return row.id if row is not None else None


def _select_trace_payload_by_store_key(store_key: str) -> Select[tuple[RewriteTracePayloadRecord]]:
    return select(RewriteTracePayloadRecord).where(RewriteTracePayloadRecord.store_key == store_key)


def _select_trace_payload_by_owner_row_id(
    owner_row_id: int,
) -> Select[tuple[RewriteTracePayloadRecord]]:
    return (
        select(RewriteTracePayloadRecord)
        .where(RewriteTracePayloadRecord.owner_record_id == owner_row_id)
        .order_by(RewriteTracePayloadRecord.id.asc())
    )


def _to_metadata_record_ref(row: RewriteStorageRecord) -> MetadataRecordRef:
    return MetadataRecordRef(
        backend="sqlite_metadata",
        record_type=cast(MetadataRecordType, row.record_type),
        record_id=row.record_id,
        version=row.version,
        schema_version=row.schema_version,
    )


def _to_trace_payload_ref(row: RewriteTracePayloadRecord) -> TracePayloadRef:
    return TracePayloadRef(
        contract_version=row.contract_version,
        backend=cast(TracePayloadBackend, row.backend),
        payload_role=cast(TracePayloadRole, row.payload_role),
        store_key=row.store_key,
        store_uri=row.store_uri or "",
        group_path=row.group_path,
        array_path=row.array_path,
        dtype=row.dtype,
        shape=tuple(row.shape),
        chunk_shape=tuple(row.chunk_shape),
        schema_version=row.schema_version,
    )
