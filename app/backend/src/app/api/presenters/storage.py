from src.app.api.schemas.storage import (
    MetadataRecordRefResponse,
    ResultHandleRefResponse,
    ResultProvenanceRefResponse,
    TracePayloadRefResponse,
)
from src.app.domain.storage import (
    MetadataRecordRef,
    ResultHandleRef,
    ResultProvenanceRef,
    TracePayloadRef,
)


def build_metadata_record_ref_response(
    record: MetadataRecordRef,
) -> MetadataRecordRefResponse:
    return MetadataRecordRefResponse(
        backend=record.backend,
        record_type=record.record_type,
        record_id=record.record_id,
        version=record.version,
        schema_version=record.schema_version,
    )


def build_trace_payload_ref_response(
    trace_payload: TracePayloadRef | None,
) -> TracePayloadRefResponse | None:
    if trace_payload is None:
        return None
    return TracePayloadRefResponse(
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
    )


def build_result_provenance_ref_response(
    provenance: ResultProvenanceRef,
) -> ResultProvenanceRefResponse:
    return ResultProvenanceRefResponse(
        source_dataset_id=provenance.source_dataset_id,
        source_task_id=provenance.source_task_id,
        trace_batch_record=build_metadata_record_ref_response(provenance.trace_batch_record)
        if provenance.trace_batch_record is not None
        else None,
        analysis_run_record=build_metadata_record_ref_response(provenance.analysis_run_record)
        if provenance.analysis_run_record is not None
        else None,
    )


def build_result_handle_ref_response(
    handle: ResultHandleRef,
) -> ResultHandleRefResponse:
    return ResultHandleRefResponse(
        contract_version=handle.contract_version,
        handle_id=handle.handle_id,
        kind=handle.kind,
        status=handle.status,
        label=handle.label,
        metadata_record=build_metadata_record_ref_response(handle.metadata_record),
        payload_backend=handle.payload_backend,
        payload_format=handle.payload_format,
        payload_role=handle.payload_role,
        payload_locator=handle.payload_locator,
        provenance_task_id=handle.provenance_task_id,
        provenance=build_result_provenance_ref_response(handle.provenance),
    )
