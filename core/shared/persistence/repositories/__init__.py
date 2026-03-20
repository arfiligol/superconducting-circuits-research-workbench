"""Repositories for the persistence layer."""

from core.shared.persistence.repositories.analysis_run_repository import AnalysisRunRepository
from core.shared.persistence.repositories.audit_log_repository import AuditLogRepository
from core.shared.persistence.repositories.circuit_repository import CircuitRepository
from core.shared.persistence.repositories.contracts import (
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
from core.shared.persistence.repositories.data_record_repository import (
    DataRecordRepository,
    TraceRepository,
)
from core.shared.persistence.repositories.dataset_repository import (
    DatasetRepository,
    DesignRepository,
)
from core.shared.persistence.repositories.derived_parameter_repository import (
    DerivedParameterRepository,
)
from core.shared.persistence.repositories.parameter_designation_repository import (
    ParameterDesignationRepository,
)
from core.shared.persistence.repositories.query_objects import TraceIndexPageQuery
from core.shared.persistence.repositories.result_bundle_repository import (
    ResultBundleRepository,
    TraceBatchRepository,
)
from core.shared.persistence.repositories.tag_repository import TagRepository
from core.shared.persistence.repositories.task_repository import TaskRepository
from core.shared.persistence.repositories.user_repository import UserRepository

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
