"""Framework-agnostic storage and provenance contracts shared across surfaces."""

from sc_core.storage.contracts import (
    STORAGE_CONTRACT_VERSION,
    AnalysisRunProvenance,
    StorageRecordHandle,
    StorageRecordKind,
    TraceBatchHandle,
    TraceBatchLifecyclePayload,
    TraceBatchProvenance,
    TraceResultLinkage,
    TraceStoreBackend,
    TraceStoreLocator,
    merge_trace_batch_summary_payload,
)
from sc_core.storage.evolution import (
    DATASET_IMPORT_TRACE_WRITER_VERSION,
    POSTPROCESS_SWEEP_TRACE_WRITER_VERSION,
    SIMULATION_RAW_SWEEP_TRACE_WRITER_VERSION,
    TRACE_STORE_EVOLUTION_CONTRACT_VERSION,
    TRACE_STORE_SCHEMA_BASELINE_VERSION,
    TraceStorePayloadLifecycle,
    TraceStorePayloadRole,
    TraceStoreVersionMarkers,
)

__all__ = [
    "DATASET_IMPORT_TRACE_WRITER_VERSION",
    "POSTPROCESS_SWEEP_TRACE_WRITER_VERSION",
    "SIMULATION_RAW_SWEEP_TRACE_WRITER_VERSION",
    "STORAGE_CONTRACT_VERSION",
    "TRACE_STORE_EVOLUTION_CONTRACT_VERSION",
    "TRACE_STORE_SCHEMA_BASELINE_VERSION",
    "AnalysisRunProvenance",
    "StorageRecordHandle",
    "StorageRecordKind",
    "TraceBatchHandle",
    "TraceBatchLifecyclePayload",
    "TraceBatchProvenance",
    "TraceResultLinkage",
    "TraceStoreBackend",
    "TraceStoreLocator",
    "TraceStorePayloadLifecycle",
    "TraceStorePayloadRole",
    "TraceStoreVersionMarkers",
    "merge_trace_batch_summary_payload",
]
