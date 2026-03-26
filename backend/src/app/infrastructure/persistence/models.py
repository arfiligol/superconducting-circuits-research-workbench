from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, ForeignKey, Index, String, Text, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class RewriteMetadataBase(DeclarativeBase):
    pass


class RewriteStorageRecord(RewriteMetadataBase):
    __tablename__ = "rewrite_storage_records"
    __table_args__ = (
        Index("ix_rewrite_storage_records_record_type", "record_type"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    record_type: Mapped[str] = mapped_column(String(32), nullable=False)
    record_id: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    schema_version: Mapped[str] = mapped_column(String(32), nullable=False)
    version: Mapped[int] = mapped_column(nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        nullable=False,
        server_default=func.current_timestamp(),
    )


class RewriteTracePayloadRecord(RewriteMetadataBase):
    __tablename__ = "rewrite_trace_payloads"
    __table_args__ = (
        Index("ix_rewrite_trace_payloads_payload_role", "payload_role"),
        Index("ix_rewrite_trace_payloads_store_key", "store_key", unique=True),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    owner_record_id: Mapped[int] = mapped_column(
        ForeignKey("rewrite_storage_records.id", ondelete="CASCADE"),
        nullable=False,
    )
    contract_version: Mapped[str] = mapped_column(String(32), nullable=False)
    backend: Mapped[str] = mapped_column(String(32), nullable=False)
    payload_role: Mapped[str] = mapped_column(String(32), nullable=False)
    store_key: Mapped[str] = mapped_column(String(255), nullable=False)
    store_uri: Mapped[str | None] = mapped_column(String(255))
    group_path: Mapped[str] = mapped_column(String(255), nullable=False)
    array_path: Mapped[str] = mapped_column(String(255), nullable=False)
    dtype: Mapped[str] = mapped_column(String(32), nullable=False)
    shape: Mapped[list[int]] = mapped_column(JSON, nullable=False)
    chunk_shape: Mapped[list[int]] = mapped_column(JSON, nullable=False)
    schema_version: Mapped[str] = mapped_column(String(32), nullable=False)
    writer_version: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(
        nullable=False,
        server_default=func.current_timestamp(),
    )


class RewriteResultHandleRecord(RewriteMetadataBase):
    __tablename__ = "rewrite_result_handles"
    __table_args__ = (
        Index("ix_rewrite_result_handles_kind", "kind"),
        Index("ix_rewrite_result_handles_handle_id", "handle_id", unique=True),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    metadata_record_id: Mapped[int] = mapped_column(
        ForeignKey("rewrite_storage_records.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    handle_id: Mapped[str] = mapped_column(String(128), nullable=False)
    contract_version: Mapped[str] = mapped_column(String(32), nullable=False)
    kind: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    label: Mapped[str] = mapped_column(String(255), nullable=False)
    payload_backend: Mapped[str | None] = mapped_column(String(64))
    payload_format: Mapped[str | None] = mapped_column(String(32))
    payload_role: Mapped[str | None] = mapped_column(String(32))
    payload_locator: Mapped[str | None] = mapped_column(String(255))
    provenance_task_id: Mapped[int | None]
    source_dataset_id: Mapped[str | None] = mapped_column(String(128))
    source_task_id: Mapped[int | None]
    trace_batch_record_id: Mapped[int | None] = mapped_column(
        ForeignKey("rewrite_storage_records.id", ondelete="SET NULL"),
    )
    analysis_run_record_id: Mapped[int | None] = mapped_column(
        ForeignKey("rewrite_storage_records.id", ondelete="SET NULL"),
    )
    created_at: Mapped[datetime] = mapped_column(
        nullable=False,
        server_default=func.current_timestamp(),
    )


class RewritePublishedSimulationResultRecord(RewriteMetadataBase):
    __tablename__ = "rewrite_published_simulation_results"
    __table_args__ = (
        Index(
            "ix_rewrite_published_simulation_results_publication_key",
            "publication_key",
            unique=True,
        ),
        Index(
            "ix_rewrite_published_simulation_results_source_task_id",
            "source_task_id",
            unique=True,
        ),
        Index("ix_rewrite_published_simulation_results_target_dataset_id", "target_dataset_id"),
        Index("ix_rewrite_published_simulation_results_target_design_id", "target_design_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    publication_key: Mapped[str] = mapped_column(String(255), nullable=False)
    source_task_id: Mapped[int] = mapped_column(nullable=False)
    source_dataset_id: Mapped[str | None] = mapped_column(String(128))
    source_result_handle_ids: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    target_dataset_id: Mapped[str] = mapped_column(String(128), nullable=False)
    target_design_id: Mapped[str] = mapped_column(String(128), nullable=False)
    target_design_name: Mapped[str] = mapped_column(String(255), nullable=False)
    published_at: Mapped[str] = mapped_column(String(32), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        nullable=False,
        server_default=func.current_timestamp(),
    )


class RewriteDatasetRecord(RewriteMetadataBase):
    __tablename__ = "rewrite_dataset_records"
    __table_args__ = (
        Index("ix_rewrite_dataset_records_dataset_id", "dataset_id", unique=True),
        Index("ix_rewrite_dataset_records_workspace_id", "workspace_id"),
        Index("ix_rewrite_dataset_records_lifecycle_state", "lifecycle_state"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    dataset_id: Mapped[str] = mapped_column(String(128), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    family: Mapped[str] = mapped_column(String(64), nullable=False)
    owner_display_name: Mapped[str] = mapped_column(String(128), nullable=False)
    owner_user_id: Mapped[str] = mapped_column(String(64), nullable=False)
    workspace_id: Mapped[str] = mapped_column(String(64), nullable=False)
    visibility_scope: Mapped[str] = mapped_column(String(32), nullable=False)
    lifecycle_state: Mapped[str] = mapped_column(String(32), nullable=False)
    updated_at: Mapped[str] = mapped_column(String(32), nullable=False)
    device_type: Mapped[str] = mapped_column(String(64), nullable=False)
    capabilities_json: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    source: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        nullable=False,
        server_default=func.current_timestamp(),
    )


class RewriteDatasetDesignRecord(RewriteMetadataBase):
    __tablename__ = "rewrite_dataset_designs"
    __table_args__ = (
        Index(
            "ix_rewrite_dataset_designs_dataset_design",
            "dataset_id",
            "design_id",
            unique=True,
        ),
        Index(
            "ix_rewrite_dataset_designs_dataset_normalized_name",
            "dataset_id",
            "normalized_name",
            unique=True,
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    dataset_id: Mapped[str] = mapped_column(String(128), nullable=False)
    design_id: Mapped[str] = mapped_column(String(128), nullable=False)
    normalized_name: Mapped[str] = mapped_column(String(255), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    updated_at: Mapped[str] = mapped_column(String(32), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        nullable=False,
        server_default=func.current_timestamp(),
    )


class RewriteDatasetTraceRecord(RewriteMetadataBase):
    __tablename__ = "rewrite_dataset_traces"
    __table_args__ = (
        Index(
            "ix_rewrite_dataset_traces_dataset_design_trace",
            "dataset_id",
            "design_id",
            "trace_id",
            unique=True,
        ),
        Index(
            "ix_rewrite_dataset_traces_dataset_design",
            "dataset_id",
            "design_id",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    dataset_id: Mapped[str] = mapped_column(String(128), nullable=False)
    design_id: Mapped[str] = mapped_column(String(128), nullable=False)
    trace_id: Mapped[str] = mapped_column(String(128), nullable=False)
    family: Mapped[str] = mapped_column(String(32), nullable=False)
    parameter: Mapped[str] = mapped_column(String(128), nullable=False)
    representation: Mapped[str] = mapped_column(String(64), nullable=False)
    trace_mode_group: Mapped[str] = mapped_column(String(32), nullable=False)
    source_kind: Mapped[str] = mapped_column(String(64), nullable=False)
    stage_kind: Mapped[str] = mapped_column(String(32), nullable=False)
    provenance_summary: Mapped[str] = mapped_column(String(255), nullable=False)
    axes_json: Mapped[list[dict[str, object]]] = mapped_column(
        JSON,
        nullable=False,
        default=list,
    )
    preview_payload_json: Mapped[dict[str, object]] = mapped_column(
        JSON,
        nullable=False,
        default=dict,
    )
    numeric_payload_json: Mapped[dict[str, object]] = mapped_column(
        JSON,
        nullable=False,
        default=dict,
    )
    payload_store_key: Mapped[str] = mapped_column(String(255), nullable=False)
    result_handle_ids_json: Mapped[list[str]] = mapped_column(
        JSON,
        nullable=False,
        default=list,
    )
    editable: Mapped[bool] = mapped_column(nullable=False, default=False)
    mutation_policy_summary: Mapped[str] = mapped_column(String(255), nullable=False)
    updated_at: Mapped[str] = mapped_column(String(32), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        nullable=False,
        server_default=func.current_timestamp(),
    )


class RewriteTraceCapabilityRecord(RewriteMetadataBase):
    __tablename__ = "rewrite_trace_capability_records"
    __table_args__ = (
        Index(
            "ix_rewrite_trace_capability_dataset_design_trace_capability",
            "dataset_id",
            "design_id",
            "trace_id",
            "capability_id",
            unique=True,
        ),
        Index(
            "ix_rewrite_trace_capability_dataset_design_analysis",
            "dataset_id",
            "design_id",
            "analysis_id",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    dataset_id: Mapped[str] = mapped_column(String(128), nullable=False)
    design_id: Mapped[str] = mapped_column(String(128), nullable=False)
    trace_id: Mapped[str] = mapped_column(String(128), nullable=False)
    capability_id: Mapped[str] = mapped_column(String(128), nullable=False)
    analysis_id: Mapped[str] = mapped_column(String(128), nullable=False)
    analysis_label: Mapped[str] = mapped_column(String(255), nullable=False)
    input_role: Mapped[str] = mapped_column(String(128), nullable=False)
    input_role_label: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    summary: Mapped[str] = mapped_column(String(255), nullable=False)
    reasons_json: Mapped[list[dict[str, object]]] = mapped_column(
        JSON,
        nullable=False,
        default=list,
    )
    created_at: Mapped[datetime] = mapped_column(
        nullable=False,
        server_default=func.current_timestamp(),
    )


class RewriteCharacterizationRegistryRecord(RewriteMetadataBase):
    __tablename__ = "rewrite_characterization_registry_records"
    __table_args__ = (
        Index(
            "ix_rewrite_characterization_registry_dataset_design_analysis",
            "dataset_id",
            "design_id",
            "analysis_id",
            unique=True,
        ),
        Index(
            "ix_rewrite_characterization_registry_dataset_design_sort",
            "dataset_id",
            "design_id",
            "sort_order",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    dataset_id: Mapped[str] = mapped_column(String(128), nullable=False)
    design_id: Mapped[str] = mapped_column(String(128), nullable=False)
    analysis_id: Mapped[str] = mapped_column(String(128), nullable=False)
    label: Mapped[str] = mapped_column(String(255), nullable=False)
    availability_state: Mapped[str] = mapped_column(String(32), nullable=False)
    required_config_fields_json: Mapped[list[str]] = mapped_column(
        JSON,
        nullable=False,
        default=list,
    )
    matched_trace_count: Mapped[int] = mapped_column(nullable=False, default=0)
    recommended_trace_modes_json: Mapped[list[str]] = mapped_column(
        JSON,
        nullable=False,
        default=list,
    )
    summary: Mapped[str] = mapped_column(String(255), nullable=False)
    sort_order: Mapped[int] = mapped_column(nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        nullable=False,
        server_default=func.current_timestamp(),
    )


class RewriteCircuitDefinitionRecord(RewriteMetadataBase):
    __tablename__ = "rewrite_circuit_definitions"
    __table_args__ = (
        Index(
            "ix_rewrite_circuit_definitions_definition_id",
            "definition_id",
            unique=True,
        ),
        Index(
            "ix_rewrite_circuit_definitions_workspace_visibility",
            "workspace_id",
            "visibility_scope",
        ),
        Index(
            "ix_rewrite_circuit_definitions_lifecycle_state",
            "lifecycle_state",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    definition_id: Mapped[str] = mapped_column(String(36), nullable=False)
    workspace_id: Mapped[str] = mapped_column(String(64), nullable=False)
    visibility_scope: Mapped[str] = mapped_column(String(32), nullable=False)
    lifecycle_state: Mapped[str] = mapped_column(String(32), nullable=False)
    owner_user_id: Mapped[str] = mapped_column(String(64), nullable=False)
    owner_display_name: Mapped[str] = mapped_column(String(128), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at_iso: Mapped[str] = mapped_column(String(32), nullable=False)
    updated_at_iso: Mapped[str] = mapped_column(String(32), nullable=False)
    concurrency_token: Mapped[str] = mapped_column(String(64), nullable=False)
    source_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    source_text: Mapped[str] = mapped_column(Text, nullable=False)
    normalized_output: Mapped[str] = mapped_column(Text, nullable=False)
    validation_notices_json: Mapped[list[dict[str, object]]] = mapped_column(
        JSON,
        nullable=False,
        default=list,
    )
    validation_summary_json: Mapped[dict[str, object]] = mapped_column(
        JSON,
        nullable=False,
        default=dict,
    )
    preview_artifacts_json: Mapped[list[str]] = mapped_column(
        JSON,
        nullable=False,
        default=list,
    )
    lineage_parent_id: Mapped[str | None] = mapped_column(String(36))
    created_at: Mapped[datetime] = mapped_column(
        nullable=False,
        server_default=func.current_timestamp(),
    )


class RewritePublishedSimulationTraceRecord(RewriteMetadataBase):
    __tablename__ = "rewrite_published_simulation_traces"
    __table_args__ = (
        Index(
            "ix_rewrite_published_simulation_traces_dataset_design_trace",
            "dataset_id",
            "design_id",
            "trace_id",
            unique=True,
        ),
        Index(
            "ix_rewrite_published_simulation_traces_publication_id",
            "publication_id",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    publication_id: Mapped[int] = mapped_column(
        ForeignKey("rewrite_published_simulation_results.id", ondelete="CASCADE"),
        nullable=False,
    )
    dataset_id: Mapped[str] = mapped_column(String(128), nullable=False)
    design_id: Mapped[str] = mapped_column(String(128), nullable=False)
    trace_id: Mapped[str] = mapped_column(String(128), nullable=False)
    family: Mapped[str] = mapped_column(String(32), nullable=False)
    parameter: Mapped[str] = mapped_column(String(64), nullable=False)
    representation: Mapped[str] = mapped_column(String(64), nullable=False)
    trace_mode_group: Mapped[str] = mapped_column(String(32), nullable=False)
    source_kind: Mapped[str] = mapped_column(String(64), nullable=False)
    stage_kind: Mapped[str] = mapped_column(String(32), nullable=False)
    provenance_summary: Mapped[str] = mapped_column(String(255), nullable=False)
    axes_json: Mapped[list[dict[str, object]]] = mapped_column(
        JSON,
        nullable=False,
        default=list,
    )
    preview_payload_json: Mapped[dict[str, object]] = mapped_column(
        JSON,
        nullable=False,
        default=dict,
    )
    payload_store_key: Mapped[str] = mapped_column(String(255), nullable=False)
    result_handle_id: Mapped[str] = mapped_column(String(128), nullable=False)
    published_at: Mapped[str] = mapped_column(String(32), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        nullable=False,
        server_default=func.current_timestamp(),
    )


class RewriteTaskRecord(RewriteMetadataBase):
    __tablename__ = "rewrite_task_records"
    __table_args__ = (
        Index("ix_rewrite_task_records_task_id", "task_id", unique=True),
        Index("ix_rewrite_task_records_workspace_id", "workspace_id"),
        Index("ix_rewrite_task_records_status", "status"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    task_id: Mapped[int] = mapped_column(nullable=False)
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    lane: Mapped[str] = mapped_column(String(32), nullable=False)
    execution_mode: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    submitted_at: Mapped[str] = mapped_column(String(32), nullable=False)
    owner_user_id: Mapped[str] = mapped_column(String(64), nullable=False)
    owner_display_name: Mapped[str] = mapped_column(String(128), nullable=False)
    workspace_id: Mapped[str] = mapped_column(String(64), nullable=False)
    workspace_slug: Mapped[str] = mapped_column(String(64), nullable=False)
    visibility_scope: Mapped[str] = mapped_column(String(32), nullable=False)
    dataset_id: Mapped[str | None] = mapped_column(String(128))
    definition_id: Mapped[str | None] = mapped_column(String(36))
    summary: Mapped[str] = mapped_column(String(255), nullable=False)
    queue_backend: Mapped[str] = mapped_column(String(64), nullable=False)
    worker_task_name: Mapped[str] = mapped_column(String(64), nullable=False)
    request_ready: Mapped[bool] = mapped_column(nullable=False, default=False)
    submitted_from_active_dataset: Mapped[bool] = mapped_column(
        nullable=False,
        default=False,
    )
    progress_phase: Mapped[str] = mapped_column(String(32), nullable=False)
    progress_percent_complete: Mapped[int] = mapped_column(nullable=False)
    progress_summary: Mapped[str] = mapped_column(String(255), nullable=False)
    progress_updated_at: Mapped[str] = mapped_column(String(32), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        nullable=False,
        server_default=func.current_timestamp(),
    )


class RewriteTaskDispatchRecord(RewriteMetadataBase):
    __tablename__ = "rewrite_task_dispatch_records"
    __table_args__ = (
        Index("ix_rewrite_task_dispatch_records_task_id", "task_id", unique=True),
        Index("ix_rewrite_task_dispatch_records_dispatch_key", "dispatch_key", unique=True),
        Index("ix_rewrite_task_dispatch_records_status", "status"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    task_id: Mapped[int] = mapped_column(
        ForeignKey("rewrite_task_records.task_id", ondelete="CASCADE"),
        nullable=False,
    )
    dispatch_key: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    submission_source: Mapped[str] = mapped_column(String(32), nullable=False)
    accepted_at: Mapped[str] = mapped_column(String(32), nullable=False)
    last_updated_at: Mapped[str] = mapped_column(String(32), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        nullable=False,
        server_default=func.current_timestamp(),
    )


class RewriteTaskEventRecord(RewriteMetadataBase):
    __tablename__ = "rewrite_task_event_records"
    __table_args__ = (
        Index("ix_rewrite_task_event_records_task_id", "task_id"),
        Index("ix_rewrite_task_event_records_event_key", "task_id", "event_key", unique=True),
        Index("ix_rewrite_task_event_records_occurred_at", "occurred_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    task_id: Mapped[int] = mapped_column(
        ForeignKey("rewrite_task_records.task_id", ondelete="CASCADE"),
        nullable=False,
    )
    event_key: Mapped[str] = mapped_column(String(128), nullable=False)
    event_type: Mapped[str] = mapped_column(String(32), nullable=False)
    level: Mapped[str] = mapped_column(String(16), nullable=False)
    occurred_at: Mapped[str] = mapped_column(String(32), nullable=False)
    message: Mapped[str] = mapped_column(String(255), nullable=False)
    metadata_json: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        nullable=False,
        server_default=func.current_timestamp(),
    )


class RewriteAppContextRecord(RewriteMetadataBase):
    __tablename__ = "rewrite_app_context_records"
    __table_args__ = (
        Index("ix_rewrite_app_context_records_app_context_id", "app_context_id", unique=True),
        Index("ix_rewrite_app_context_records_bound_session_id", "bound_session_id"),
        Index("ix_rewrite_app_context_records_runtime_mode", "runtime_mode"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    app_context_id: Mapped[str] = mapped_column(String(128), nullable=False)
    bound_session_id: Mapped[str | None] = mapped_column(String(128))
    runtime_mode: Mapped[str] = mapped_column(String(32), nullable=False)
    state_json: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        nullable=False,
        server_default=func.current_timestamp(),
    )


class RewriteServerTargetRecord(RewriteMetadataBase):
    __tablename__ = "rewrite_server_target_records"
    __table_args__ = (
        Index("ix_rewrite_server_target_records_origin", "origin", unique=True),
        Index(
            "ix_rewrite_server_target_records_validation_status",
            "validation_status",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    origin: Mapped[str] = mapped_column(String(255), nullable=False)
    label: Mapped[str] = mapped_column(String(255), nullable=False)
    validation_status: Mapped[str] = mapped_column(String(32), nullable=False)
    last_checked_at: Mapped[str | None] = mapped_column(String(32))
    created_at: Mapped[datetime] = mapped_column(
        nullable=False,
        server_default=func.current_timestamp(),
    )


class RewriteAuthAccountRecord(RewriteMetadataBase):
    __tablename__ = "rewrite_auth_account_records"
    __table_args__ = (
        Index("ix_rewrite_auth_account_records_email", "email", unique=True),
        Index("ix_rewrite_auth_account_records_user_id", "user_id", unique=True),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    user_id: Mapped[str | None] = mapped_column(String(64))
    prototype_state_json: Mapped[dict[str, object]] = mapped_column(
        JSON,
        nullable=False,
        default=dict,
    )
    created_at: Mapped[datetime] = mapped_column(
        nullable=False,
        server_default=func.current_timestamp(),
    )


class RewriteAuthenticatedSessionRecord(RewriteMetadataBase):
    __tablename__ = "rewrite_authenticated_session_records"
    __table_args__ = (
        Index(
            "ix_rewrite_authenticated_session_records_session_id",
            "session_id",
            unique=True,
        ),
        Index("ix_rewrite_authenticated_session_records_user_id", "user_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(String(128), nullable=False)
    user_id: Mapped[str] = mapped_column(String(64), nullable=False)
    state_json: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False, default=dict)
    last_active_dataset_ids_json: Mapped[dict[str, str]] = mapped_column(
        JSON,
        nullable=False,
        default=dict,
    )
    created_at: Mapped[datetime] = mapped_column(
        nullable=False,
        server_default=func.current_timestamp(),
    )


class RewriteRefreshTokenRecord(RewriteMetadataBase):
    __tablename__ = "rewrite_refresh_token_records"
    __table_args__ = (
        Index("ix_rewrite_refresh_token_records_token", "token", unique=True),
        Index("ix_rewrite_refresh_token_records_session_id", "session_id"),
        Index("ix_rewrite_refresh_token_records_family_id", "family_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    token: Mapped[str] = mapped_column(String(255), nullable=False)
    session_id: Mapped[str] = mapped_column(String(128), nullable=False)
    family_id: Mapped[str] = mapped_column(String(128), nullable=False)
    expires_at: Mapped[str] = mapped_column(String(32), nullable=False)
    revoked: Mapped[bool] = mapped_column(nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        nullable=False,
        server_default=func.current_timestamp(),
    )


class RewriteWorkspaceInvitationRecord(RewriteMetadataBase):
    __tablename__ = "rewrite_workspace_invitation_records"
    __table_args__ = (
        Index("ix_rewrite_workspace_invitation_records_invite_id", "invite_id", unique=True),
        Index(
            "ix_rewrite_workspace_invitation_records_invite_token",
            "invite_token",
            unique=True,
        ),
        Index(
            "ix_rewrite_workspace_invitation_records_workspace_id",
            "workspace_id",
        ),
        Index("ix_rewrite_workspace_invitation_records_state", "state"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    invite_id: Mapped[str] = mapped_column(String(128), nullable=False)
    invite_token: Mapped[str] = mapped_column(String(255), nullable=False)
    workspace_id: Mapped[str] = mapped_column(String(64), nullable=False)
    workspace_name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(32), nullable=False)
    state: Mapped[str] = mapped_column(String(32), nullable=False)
    expires_at: Mapped[str] = mapped_column(String(32), nullable=False)
    created_at_iso: Mapped[str] = mapped_column(String(32), nullable=False)
    delivery_status: Mapped[str] = mapped_column(String(32), nullable=False)
    delivery_channel: Mapped[str] = mapped_column(String(32), nullable=False)
    invite_url: Mapped[str | None] = mapped_column(String(255))
    created_by_user_id: Mapped[str] = mapped_column(String(64), nullable=False)
    delivery_error: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(
        nullable=False,
        server_default=func.current_timestamp(),
    )


class RewritePendingInvitationAcceptanceRecord(RewriteMetadataBase):
    __tablename__ = "rewrite_pending_invitation_acceptance_records"
    __table_args__ = (
        Index(
            "ix_rewrite_pending_invitation_acceptance_records_continuation_token",
            "continuation_token",
            unique=True,
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    continuation_token: Mapped[str] = mapped_column(String(255), nullable=False)
    invite_token: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at_iso: Mapped[str] = mapped_column(String(32), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        nullable=False,
        server_default=func.current_timestamp(),
    )


class RewriteWorkspaceDefaultDatasetRecord(RewriteMetadataBase):
    __tablename__ = "rewrite_workspace_default_dataset_records"
    __table_args__ = (
        Index(
            "ix_rewrite_workspace_default_dataset_records_workspace_id",
            "workspace_id",
            unique=True,
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    workspace_id: Mapped[str] = mapped_column(String(64), nullable=False)
    default_dataset_id: Mapped[str] = mapped_column(String(128), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        nullable=False,
        server_default=func.current_timestamp(),
    )
