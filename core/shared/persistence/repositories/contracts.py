"""Repository contracts used by page/application orchestration layers."""

from __future__ import annotations

from typing import Any, Protocol, TypedDict, runtime_checkable

from sc_core.execution import (
    ExecutionEventLog,
    TaskCreationSpec,
    TaskExecutionOperation,
    TaskExecutionTransition,
    TaskLifecycleMutation,
)
from sc_core.storage import TraceResultLinkage

from core.shared.persistence.models import AnalysisRunRecord, AuditLogRecord, TaskRecord, UserRecord
from core.shared.persistence.repositories.query_objects import TraceIndexPageQuery

TraceIndexRow = dict[str, str | int]


class AnalysisRunSummary(TypedDict):
    """Primitive-only summary row for one analysis run."""

    analysis_run_id: int
    dataset_id: int
    design_id: int
    analysis_id: str
    analysis_label: str
    status: str


@runtime_checkable
class AnalysisRunPersistenceContract(Protocol):
    """Logical analysis-run persistence API used by Characterization history flows."""

    def add(self, analysis_run: AnalysisRunRecord) -> AnalysisRunRecord: ...

    def save(self, analysis_run: AnalysisRunRecord) -> AnalysisRunRecord: ...

    def get(self, id: int) -> AnalysisRunRecord | None: ...

    def list_by_design(self, design_id: int) -> list[AnalysisRunRecord]: ...

    def list_summaries_by_design(self, design_id: int) -> list[AnalysisRunSummary]: ...


@runtime_checkable
class TaskPersistenceContract(Protocol):
    """Task lifecycle persistence API for persisted orchestration flows."""

    def create_task_from_spec(self, spec: TaskCreationSpec) -> TaskRecord: ...

    def create_task(
        self,
        task_kind: str,
        design_id: int,
        request_payload: dict[str, Any],
        requested_by: str,
        *,
        actor_id: int | None = None,
        dedupe_key: str | None = None,
        trace_batch_id: int | None = None,
        analysis_run_id: int | None = None,
    ) -> TaskRecord: ...

    def apply_lifecycle_mutation(self, task_id: int, mutation: TaskLifecycleMutation) -> None: ...

    def apply_execution_transition(
        self,
        task_id: int,
        transition: TaskExecutionTransition,
    ) -> None: ...

    def apply_execution_operation(self, operation: TaskExecutionOperation) -> None: ...

    def mark_running(self, task_id: int) -> None: ...

    def heartbeat(self, task_id: int, progress_payload: dict[str, Any]) -> None: ...

    def mark_completed(
        self,
        task_id: int,
        result_linkage: TraceResultLinkage | int | None,
        result_summary_payload: dict[str, Any],
        *,
        analysis_run_id: int | None = None,
    ) -> None: ...

    def mark_failed(self, task_id: int, error_payload: dict[str, Any]) -> None: ...

    def get_task(self, task_id: int) -> TaskRecord | None: ...

    def list_tasks_by_design(
        self,
        design_id: int,
        status_filter: str | list[str] | tuple[str, ...] | None = None,
    ) -> list[TaskRecord]: ...

    def get_latest_task_by_kind(self, design_id: int, task_kind: str) -> TaskRecord | None: ...

    def find_active_by_dedupe_key(self, dedupe_key: str) -> TaskRecord | None: ...

    def list_stale_running_tasks(self, before_heartbeat_at: Any) -> list[TaskRecord]: ...


@runtime_checkable
class UserPersistenceContract(Protocol):
    """Local-user persistence API for session and admin flows."""

    def get_by_username(self, username: str) -> UserRecord | None: ...

    def get_by_id(self, user_id: int) -> UserRecord | None: ...

    def create_user(
        self,
        username: str,
        password_hash: str,
        role: str,
        *,
        is_active: bool = True,
    ) -> UserRecord: ...

    def list_users(self) -> list[UserRecord]: ...

    def set_password(self, user_id: int, password_hash: str) -> UserRecord: ...

    def set_role(self, user_id: int, role: str) -> UserRecord: ...

    def set_active(self, user_id: int, is_active: bool) -> UserRecord: ...

    def mark_login(self, user_id: int, *, logged_in_at: Any) -> UserRecord: ...


@runtime_checkable
class AuditLogPersistenceContract(Protocol):
    """Audit-log persistence API for actor-traceable actions."""

    def append_execution_event(
        self,
        *,
        actor_id: int | None,
        event: ExecutionEventLog,
    ) -> AuditLogRecord: ...

    def append_execution_operation(
        self,
        operation: TaskExecutionOperation,
    ) -> AuditLogRecord | None: ...

    def append_log(
        self,
        *,
        actor_id: int | None,
        action_kind: str,
        resource_kind: str,
        resource_id: str | int,
        summary: str,
        payload: dict[str, Any] | None = None,
    ) -> AuditLogRecord: ...

    def list_logs(self) -> list[AuditLogRecord]: ...

    def list_logs_by_actor(self, actor_id: int) -> list[AuditLogRecord]: ...


class TraceBatchSnapshot(TypedDict):
    """Canonical trace-batch snapshot DTO for lineage/provenance lookups."""

    id: int
    dataset_id: int
    design_id: int
    source_kind: str
    stage_kind: str
    status: str
    parent_batch_id: int | None
    setup_kind: str | None
    setup_version: str | None
    provenance_payload: dict[str, Any]
    setup_payload: dict[str, Any]
    summary_payload: dict[str, Any]


class ResultBundleAnalysisRunSummary(TypedDict):
    """Legacy primitive-only summary row for one characterization bundle."""

    bundle_id: int
    dataset_id: int
    design_id: int
    analysis_id: str
    analysis_label: str
    status: str


class ResultBundleSnapshot(TypedDict):
    """Legacy snapshot DTO for result-bundle provenance lookups."""

    id: int
    dataset_id: int
    design_id: int
    bundle_type: str
    role: str
    status: str
    schema_source_hash: str | None
    simulation_setup_hash: str | None
    source_meta: dict[str, Any]
    config_snapshot: dict[str, Any]
    result_payload: dict[str, Any]


@runtime_checkable
class TraceCharacterizationContract(Protocol):
    """Minimal Trace repository API required by trace-first characterization flows."""

    def count_by_design(self, design_id: int) -> int: ...

    def list_distinct_index_for_profile(self, design_id: int) -> list[dict[str, str]]: ...

    def list_index_page_by_design(
        self,
        design_id: int,
        *,
        query: TraceIndexPageQuery | None = None,
        **kwargs: object,
    ) -> tuple[list[TraceIndexRow], int]: ...


@runtime_checkable
class TraceBatchCharacterizationContract(Protocol):
    """Minimal TraceBatch repository API required by trace-selection flows."""

    def count_traces(self, batch_id: int) -> int: ...

    def list_trace_index_page(
        self,
        batch_id: int,
        *,
        query: TraceIndexPageQuery | None = None,
        **kwargs: object,
    ) -> tuple[list[TraceIndexRow], int]: ...


@runtime_checkable
class TraceBatchDesignSummaryContract(Protocol):
    """TraceBatch summary API used by design-scoped UI summaries."""

    def count_by_design(
        self,
        design_id: int,
        *,
        bundle_type: str | None = None,
        role: str | None = None,
        include_cache: bool = True,
    ) -> int: ...

    def list_analysis_run_summaries_by_design(
        self,
        design_id: int,
    ) -> list[AnalysisRunSummary]: ...


@runtime_checkable
class TraceBatchSnapshotContract(Protocol):
    """TraceBatch provenance lookup API that returns canonical DTO snapshots only."""

    def get_trace_batch_snapshot(self, id: int) -> TraceBatchSnapshot | None: ...


@runtime_checkable
class DataRecordCharacterizationContract(Protocol):
    """Legacy DataRecord repository API required by characterization/runtime flows."""

    def count_by_dataset(self, dataset_id: int) -> int: ...

    def list_distinct_index_for_profile(self, dataset_id: int) -> list[dict[str, str]]: ...

    def list_index_page_by_dataset(
        self,
        dataset_id: int,
        *,
        query: TraceIndexPageQuery | None = None,
        **kwargs: object,
    ) -> tuple[list[TraceIndexRow], int]: ...


@runtime_checkable
class ResultBundleCharacterizationContract(Protocol):
    """Legacy ResultBundle repository API required by characterization/runtime flows."""

    def count_data_records(self, bundle_id: int) -> int: ...

    def list_data_record_index_page(
        self,
        bundle_id: int,
        *,
        query: TraceIndexPageQuery | None = None,
        **kwargs: object,
    ) -> tuple[list[TraceIndexRow], int]: ...


@runtime_checkable
class ResultBundleDatasetSummaryContract(Protocol):
    """Legacy ResultBundle summary API used by dataset-scoped UI summaries."""

    def count_by_dataset(
        self,
        dataset_id: int,
        *,
        bundle_type: str | None = None,
        role: str | None = None,
        include_cache: bool = True,
    ) -> int: ...

    def list_analysis_run_summaries_by_dataset(
        self,
        dataset_id: int,
    ) -> list[ResultBundleAnalysisRunSummary]: ...


@runtime_checkable
class ResultBundleSnapshotContract(Protocol):
    """Legacy ResultBundle provenance lookup API that returns DTO snapshots only."""

    def get_snapshot(self, id: int) -> ResultBundleSnapshot | None: ...
