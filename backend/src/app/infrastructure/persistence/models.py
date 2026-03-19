from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, ForeignKey, Index, String, func
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
    definition_id: Mapped[int | None]
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
