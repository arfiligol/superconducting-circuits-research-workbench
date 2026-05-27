from src.app.domain.storage import (
    DEFAULT_STORAGE_CONTRACT_VERSION,
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

REWRITE_METADATA_SCHEMA_VERSION = "sqlite_metadata.v1"
REWRITE_TRACE_SCHEMA_VERSION = "1.0"


def build_metadata_record_ref(
    record_type: MetadataRecordType,
    record_id: str,
    *,
    version: int,
) -> MetadataRecordRef:
    return MetadataRecordRef(
        backend="sqlite_metadata",
        record_type=record_type,
        record_id=record_id,
        version=version,
        schema_version=REWRITE_METADATA_SCHEMA_VERSION,
    )


def build_trace_payload_ref(
    *,
    payload_role: TracePayloadRole,
    store_key: str,
    store_uri: str,
    group_path: str,
    array_path: str,
    dtype: str,
    shape: tuple[int, ...],
    chunk_shape: tuple[int, ...],
    backend: TracePayloadBackend = "local_zarr",
    schema_version: str = REWRITE_TRACE_SCHEMA_VERSION,
) -> TracePayloadRef:
    return TracePayloadRef(
        contract_version=DEFAULT_STORAGE_CONTRACT_VERSION,
        backend=backend,
        payload_role=payload_role,
        store_key=store_key,
        store_uri=store_uri,
        group_path=group_path,
        array_path=array_path,
        dtype=dtype,
        shape=shape,
        chunk_shape=chunk_shape,
        schema_version=schema_version,
    )


def build_result_provenance_ref(
    *,
    source_dataset_id: str | None,
    source_task_id: int | None,
    trace_batch_record: MetadataRecordRef | None = None,
    analysis_run_record: MetadataRecordRef | None = None,
) -> ResultProvenanceRef:
    return ResultProvenanceRef(
        source_dataset_id=source_dataset_id,
        source_task_id=source_task_id,
        trace_batch_record=trace_batch_record,
        analysis_run_record=analysis_run_record,
    )


def build_result_handle_ref(
    *,
    handle_id: str,
    kind: ResultHandleKind,
    status: ResultHandleStatus,
    label: str,
    metadata_record: MetadataRecordRef,
    payload_backend: ResultPayloadBackend | None,
    payload_format: ResultPayloadFormat | None,
    payload_role: ResultPayloadRole | None,
    payload_locator: str | None,
    provenance_task_id: int | None,
    provenance: ResultProvenanceRef,
) -> ResultHandleRef:
    return ResultHandleRef(
        contract_version=DEFAULT_STORAGE_CONTRACT_VERSION,
        handle_id=handle_id,
        kind=kind,
        status=status,
        label=label,
        metadata_record=metadata_record,
        payload_backend=payload_backend,
        payload_format=payload_format,
        payload_role=payload_role,
        payload_locator=payload_locator,
        provenance_task_id=provenance_task_id,
        provenance=provenance,
    )
