from typing import Literal

from pydantic import BaseModel


class MetadataRecordRefResponse(BaseModel):
    backend: Literal["sqlite_metadata"]
    record_type: Literal["dataset", "trace_batch", "analysis_run", "result_handle"]
    record_id: str
    version: int
    schema_version: str


class TracePayloadRefResponse(BaseModel):
    contract_version: str
    backend: Literal["local_zarr", "s3_zarr"]
    payload_role: Literal["dataset_primary", "task_output", "analysis_projection"]
    store_key: str
    store_uri: str
    group_path: str
    array_path: str
    dtype: str
    shape: list[int]
    chunk_shape: list[int]
    schema_version: str


class ResultProvenanceRefResponse(BaseModel):
    source_dataset_id: str | None
    source_task_id: int | None
    trace_batch_record: MetadataRecordRefResponse | None
    analysis_run_record: MetadataRecordRefResponse | None


class ResultHandleRefResponse(BaseModel):
    contract_version: str
    handle_id: str
    kind: Literal["simulation_trace", "fit_summary", "characterization_report", "plot_bundle"]
    status: Literal["pending", "materialized"]
    label: str
    metadata_record: MetadataRecordRefResponse
    payload_backend: (
        Literal["local_zarr", "json_artifact", "markdown_artifact", "bundle_archive"] | None
    )
    payload_format: Literal["zarr", "json", "markdown", "zip"] | None
    payload_role: Literal["trace_payload", "report_artifact", "bundle_artifact"] | None
    payload_locator: str | None
    provenance_task_id: int | None
    provenance: ResultProvenanceRefResponse
