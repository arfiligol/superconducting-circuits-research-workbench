"""Persistence layer for SQLite database access."""

from app_backend.infrastructure.local_store.database import DATABASE_PATH, get_engine, get_session
from app_backend.infrastructure.local_store.models import (
    DataRecord,
    DatasetRecord,
    DatasetTagLink,
    DerivedParameter,
    DeviceType,
    ResultBundleDataLink,
    ResultBundleRecord,
    Tag,
)
from app_backend.infrastructure.local_store.trace_store import (
    TRACE_STORE_PATH,
    TRACE_STORE_SCHEMA_VERSION,
    LocalZarrTraceStore,
    LocalZarrTraceStoreBackend,
    S3ZarrTraceStoreBackend,
    TraceAxisMetadata,
    TraceStore,
    TraceStoreBackend,
    TraceStoreBackendBinding,
    TraceStoreRef,
    TraceStoreRuntimeConfig,
    TraceWriteResult,
    coerce_trace_store_ref,
    get_trace_store_backend_binding,
    get_trace_store_path,
    get_trace_store_runtime_config,
    resolve_trace_store_path,
)
from app_backend.infrastructure.local_store.unit_of_work import SqliteUnitOfWork, get_unit_of_work

__all__ = [  # noqa: RUF022
    # Database
    "DATABASE_PATH",
    "get_engine",
    "get_session",
    # Models
    "DataRecord",
    "DatasetRecord",
    "DatasetTagLink",
    "DerivedParameter",
    "DeviceType",
    "ResultBundleDataLink",
    "ResultBundleRecord",
    "Tag",
    # TraceStore
    "LocalZarrTraceStore",
    "LocalZarrTraceStoreBackend",
    "S3ZarrTraceStoreBackend",
    "TRACE_STORE_PATH",
    "TRACE_STORE_SCHEMA_VERSION",
    "TraceAxisMetadata",
    "TraceStore",
    "TraceStoreBackend",
    "TraceStoreBackendBinding",
    "TraceStoreRef",
    "TraceStoreRuntimeConfig",
    "TraceWriteResult",
    "coerce_trace_store_ref",
    "get_trace_store_backend_binding",
    "get_trace_store_path",
    "get_trace_store_runtime_config",
    "resolve_trace_store_path",
    # Unit of Work
    "SqliteUnitOfWork",
    "get_unit_of_work",
]
