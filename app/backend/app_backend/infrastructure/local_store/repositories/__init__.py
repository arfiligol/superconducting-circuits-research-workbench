"""Repositories for the persistence layer."""

from app_backend.infrastructure.local_store.repositories.analysis_run_repository import (
    AnalysisRunRepository,
)
from app_backend.infrastructure.local_store.repositories.audit_log_repository import (
    AuditLogRepository,
)
from app_backend.infrastructure.local_store.repositories.circuit_repository import CircuitRepository
from app_backend.infrastructure.local_store.repositories.contracts import (
    AnalysisRunPersistenceContract,
    AnalysisRunSummary,
    AuditLogPersistenceContract,
    DataRecordCharacterizationContract,
    ResultBundleAnalysisRunSummary,
    ResultBundleCharacterizationContract,
    ResultBundleDatasetSummaryContract,
    ResultBundleSnapshotContract,
    TaskPersistenceContract,
    TraceBatchCharacterizationContract,
    TraceBatchDesignSummaryContract,
    TraceBatchSnapshotContract,
    TraceCharacterizationContract,
    UserPersistenceContract,
)
from app_backend.infrastructure.local_store.repositories.data_record_repository import (
    DataRecordRepository,
    TraceRepository,
)
from app_backend.infrastructure.local_store.repositories.dataset_repository import (
    DatasetRepository,
    DesignRepository,
)
from app_backend.infrastructure.local_store.repositories.derived_parameter_repository import (
    DerivedParameterRepository,
)
from app_backend.infrastructure.local_store.repositories.parameter_designation_repository import (
    ParameterDesignationRepository,
)
from app_backend.infrastructure.local_store.repositories.query_objects import TraceIndexPageQuery
from app_backend.infrastructure.local_store.repositories.result_bundle_repository import (
    ResultBundleRepository,
    TraceBatchRepository,
)
from app_backend.infrastructure.local_store.repositories.tag_repository import TagRepository
from app_backend.infrastructure.local_store.repositories.task_repository import TaskRepository
from app_backend.infrastructure.local_store.repositories.user_repository import UserRepository

__all__ = [
    "AnalysisRunPersistenceContract",
    "AnalysisRunRepository",
    "AnalysisRunSummary",
    "AuditLogPersistenceContract",
    "AuditLogRepository",
    "CircuitRepository",
    "DataRecordCharacterizationContract",
    "DataRecordRepository",
    "DatasetRepository",
    "DerivedParameterRepository",
    "DesignRepository",
    "ParameterDesignationRepository",
    "ResultBundleAnalysisRunSummary",
    "ResultBundleCharacterizationContract",
    "ResultBundleDatasetSummaryContract",
    "ResultBundleRepository",
    "ResultBundleSnapshotContract",
    "TagRepository",
    "TaskPersistenceContract",
    "TaskRepository",
    "TraceBatchCharacterizationContract",
    "TraceBatchDesignSummaryContract",
    "TraceBatchRepository",
    "TraceBatchSnapshotContract",
    "TraceCharacterizationContract",
    "TraceIndexPageQuery",
    "TraceRepository",
    "UserPersistenceContract",
    "UserRepository",
]
