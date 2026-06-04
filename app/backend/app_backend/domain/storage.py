from dataclasses import dataclass
from typing import Literal

from sc_core.storage import STORAGE_CONTRACT_VERSION

MetadataBackend = Literal["sqlite_metadata"]
MetadataRecordType = Literal["dataset", "trace_batch", "analysis_run", "result_handle"]
TracePayloadBackend = Literal["local_zarr", "s3_zarr"]
TracePayloadRole = Literal["dataset_primary", "task_output", "analysis_projection"]
ResultPayloadBackend = Literal["local_zarr", "json_artifact", "markdown_artifact", "bundle_archive"]
ResultPayloadFormat = Literal["zarr", "json", "markdown", "zip"]
ResultPayloadRole = Literal["trace_payload", "report_artifact", "bundle_artifact"]
ResultHandleKind = Literal[
    "simulation_trace",
    "fit_summary",
    "characterization_report",
    "plot_bundle",
]
ResultHandleStatus = Literal["pending", "materialized"]


@dataclass(frozen=True)
class MetadataRecordRef:
    backend: MetadataBackend
    record_type: MetadataRecordType
    record_id: str
    version: int
    schema_version: str


@dataclass(frozen=True)
class TracePayloadRef:
    contract_version: str
    backend: TracePayloadBackend
    payload_role: TracePayloadRole
    store_key: str
    store_uri: str
    group_path: str
    array_path: str
    dtype: str
    shape: tuple[int, ...]
    chunk_shape: tuple[int, ...]
    schema_version: str


@dataclass(frozen=True)
class ResultProvenanceRef:
    source_dataset_id: str | None
    source_task_id: int | None
    trace_batch_record: MetadataRecordRef | None
    analysis_run_record: MetadataRecordRef | None


@dataclass(frozen=True)
class ResultHandleRef:
    contract_version: str
    handle_id: str
    kind: ResultHandleKind
    status: ResultHandleStatus
    label: str
    metadata_record: MetadataRecordRef
    payload_backend: ResultPayloadBackend | None
    payload_format: ResultPayloadFormat | None
    payload_role: ResultPayloadRole | None
    payload_locator: str | None
    provenance_task_id: int | None
    provenance: ResultProvenanceRef


DEFAULT_STORAGE_CONTRACT_VERSION = STORAGE_CONTRACT_VERSION
