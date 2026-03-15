"""SQLModel table definitions for the persistence layer.

Canonical naming follows the Design / Trace / TraceBatch / AnalysisRun
architecture. Physical table names remain legacy-shaped until a dedicated
schema migration workstream lands.
"""

from datetime import datetime
from dataclasses import dataclass
from enum import Enum
from typing import Optional

from sqlmodel import JSON, Column, Field, Relationship, SQLModel

ALLOWED_USER_ROLES = frozenset({"admin", "user"})


@dataclass(frozen=True)
class PersistedScopeIds:
    """Normalized dataset/design scope pair for persisted research records."""

    dataset_id: int
    design_id: int
    used_legacy_design_fallback: bool = False


def normalize_user_role(role: str) -> str:
    """Return one persisted user role or raise for unsupported values."""
    normalized = role.strip()
    if normalized not in ALLOWED_USER_ROLES:
        allowed = ", ".join(sorted(ALLOWED_USER_ROLES))
        raise ValueError(f"Unsupported user role '{role}'. Expected one of: {allowed}.")
    return normalized


def _resolve_scope_ids(
    record: object,
    *,
    allow_legacy_design_fallback: bool,
    mutate_record: bool,
) -> PersistedScopeIds:
    """Resolve persisted scope ids under one explicit read/write policy."""
    raw_dataset_id = getattr(record, "dataset_id", None)
    raw_design_id = getattr(record, "design_id", None)
    if raw_dataset_id is None:
        raise ValueError("Explicit dataset_id is required for canonical persistence writes.")
    used_legacy_design_fallback = raw_design_id is None
    if used_legacy_design_fallback and not allow_legacy_design_fallback:
        raise ValueError("Explicit design_id is required for canonical persistence writes.")
    scope_ids = PersistedScopeIds(
        dataset_id=int(raw_dataset_id),
        design_id=int(raw_dataset_id if raw_design_id is None else raw_design_id),
        used_legacy_design_fallback=used_legacy_design_fallback,
    )
    if mutate_record:
        setattr(record, "dataset_id", scope_ids.dataset_id)
        setattr(record, "design_id", scope_ids.design_id)
    return scope_ids


def require_explicit_scope_ids(record: object) -> PersistedScopeIds:
    """Return explicit persisted scope ids or raise when either side is missing."""
    return _resolve_scope_ids(
        record,
        allow_legacy_design_fallback=False,
        mutate_record=False,
    )


def resolve_scope_ids_for_write(
    record: object,
    *,
    allow_legacy_design_fallback: bool = False,
) -> PersistedScopeIds:
    """Normalize one write-boundary scope payload under the configured compatibility policy."""
    return _resolve_scope_ids(
        record,
        allow_legacy_design_fallback=allow_legacy_design_fallback,
        mutate_record=True,
    )


def ensure_scope_ids(record: object) -> PersistedScopeIds:
    """Apply the temporary write-time compatibility shim for missing design scope."""
    return resolve_scope_ids_for_write(record, allow_legacy_design_fallback=True)


class DeviceType(str, Enum):
    """Device type for derived parameters."""

    RESONATOR = "resonator"
    QUBIT = "qubit"
    JPA = "jpa"
    OTHER = "other"


class DesignTagLink(SQLModel, table=True):
    """Link table for DesignRecord <-> Tag many-to-many relationships."""

    __tablename__ = "dataset_tags"  # type: ignore[assignment]

    dataset_id: int = Field(foreign_key="dataset_records.id", primary_key=True)
    tag_id: int = Field(foreign_key="tags.id", primary_key=True)


class TraceBatchTraceLink(SQLModel, table=True):
    """Link table for TraceBatchRecord <-> TraceRecord membership."""

    __tablename__ = "result_bundle_data_links"  # type: ignore[assignment]

    result_bundle_id: int = Field(foreign_key="result_bundle_records.id", primary_key=True)
    data_record_id: int = Field(foreign_key="data_records.id", primary_key=True)


class Tag(SQLModel, table=True):
    """Tag for organizing and searching design-scoped records."""

    __tablename__ = "tags"  # type: ignore[assignment]

    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(unique=True, index=True)

    datasets: list["DesignRecord"] = Relationship(
        back_populates="tags",
        link_model=DesignTagLink,
    )


class DesignRecord(SQLModel, table=True):
    """Canonical design container for traces, batches, and derived results."""

    __tablename__ = "dataset_records"  # type: ignore[assignment]

    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(unique=True, index=True)

    # Legacy column layout is kept intact for now. `source_meta` is the current
    # storage location for design-scoped metadata until the schema migration lands.
    source_meta: dict = Field(default_factory=dict, sa_column=Column(JSON))
    parameters: dict = Field(default_factory=dict, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=datetime.utcnow)

    tags: list["Tag"] = Relationship(back_populates="datasets", link_model=DesignTagLink)
    data_records: list["TraceRecord"] = Relationship(
        back_populates="dataset",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"},
    )
    result_bundles: list["TraceBatchRecord"] = Relationship(
        back_populates="dataset",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"},
    )
    derived_params: list["DerivedParameter"] = Relationship(
        back_populates="dataset",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"},
    )
    designations: list["ParameterDesignation"] = Relationship(
        back_populates="dataset",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"},
    )

    @property
    def design_meta(self) -> dict:
        """Canonical alias for design-scoped metadata."""
        return self.source_meta

    @design_meta.setter
    def design_meta(self, value: dict) -> None:
        self.source_meta = dict(value)


class TraceRecord(SQLModel, table=True):
    """Canonical trace metadata record for one logical observable over axes."""

    __tablename__ = "data_records"  # type: ignore[assignment]

    id: int | None = Field(default=None, primary_key=True)
    dataset_id: int = Field(foreign_key="dataset_records.id", index=True)
    design_id: int | None = Field(default=None, index=True)

    data_type: str
    parameter: str
    representation: str
    axes: list = Field(default_factory=list, sa_column=Column(JSON))
    values: list = Field(default_factory=list, sa_column=Column(JSON))
    store_ref: dict = Field(default_factory=dict, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=datetime.utcnow)

    dataset: Optional["DesignRecord"] = Relationship(back_populates="data_records")
    result_bundles: list["TraceBatchRecord"] = Relationship(
        back_populates="data_records",
        link_model=TraceBatchTraceLink,
    )

    @property
    def family(self) -> str:
        """Canonical alias for the observable family."""
        return self.data_type

    def trace_shape(self) -> tuple[int, ...]:
        """Return shape metadata without forcing inline payload materialization."""
        if isinstance(self.store_ref, dict):
            raw_shape = self.store_ref.get("shape")
            if isinstance(raw_shape, list) and raw_shape:
                return tuple(int(dimension) for dimension in raw_shape)

        shape: list[int] = []
        current: object = self.values
        while isinstance(current, list):
            shape.append(len(current))
            if not current:
                break
            current = current[0]
        return tuple(shape)

    def axis_length(self, index: int) -> int:
        """Return one axis length from inline metadata or TraceStore-derived metadata."""
        if index >= len(self.axes):
            return 0
        axis = self.axes[index]
        if not isinstance(axis, dict):
            return 0
        raw_length = axis.get("length")
        if raw_length is not None:
            return int(raw_length)
        raw_values = axis.get("values")
        if isinstance(raw_values, list):
            return len(raw_values)
        shape = self.trace_shape()
        if index < len(shape):
            return int(shape[index])
        return 0

    @family.setter
    def family(self, value: str) -> None:
        self.data_type = value


class TraceBatchRecord(SQLModel, table=True):
    """Generalized batch/provenance boundary for imports, runs, and projections."""

    __tablename__ = "result_bundle_records"  # type: ignore[assignment]

    id: int | None = Field(default=None, primary_key=True)
    dataset_id: int = Field(foreign_key="dataset_records.id", index=True)
    design_id: int | None = Field(default=None, index=True)
    parent_batch_id: int | None = Field(
        default=None,
        foreign_key="result_bundle_records.id",
        index=True,
    )

    bundle_type: str = Field(index=True)
    role: str = Field(default="cache", index=True)
    status: str = Field(default="completed", index=True)

    schema_source_hash: str | None = Field(default=None, index=True)
    simulation_setup_hash: str | None = Field(default=None, index=True)

    source_meta: dict = Field(default_factory=dict, sa_column=Column(JSON))
    config_snapshot: dict = Field(default_factory=dict, sa_column=Column(JSON))
    result_payload: dict = Field(default_factory=dict, sa_column=Column(JSON))

    created_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: datetime | None = None

    dataset: Optional["DesignRecord"] = Relationship(back_populates="result_bundles")
    data_records: list["TraceRecord"] = Relationship(
        back_populates="result_bundles",
        link_model=TraceBatchTraceLink,
    )

    @property
    def provenance_payload(self) -> dict:
        """Canonical alias for provenance metadata."""
        return self.source_meta

    @provenance_payload.setter
    def provenance_payload(self, value: dict) -> None:
        self.source_meta = dict(value)

    @property
    def setup_payload(self) -> dict:
        """Canonical alias for setup/configuration metadata."""
        return self.config_snapshot

    @setup_payload.setter
    def setup_payload(self, value: dict) -> None:
        self.config_snapshot = dict(value)

    @property
    def summary_payload(self) -> dict:
        """Canonical alias for summary/result metadata."""
        return self.result_payload

    @summary_payload.setter
    def summary_payload(self, value: dict) -> None:
        self.result_payload = dict(value)

    @property
    def source_kind(self) -> str:
        """Best-effort canonical source kind derived from legacy storage."""
        raw_value = self.source_meta.get("source_kind", self.bundle_type)
        return str(raw_value).strip()

    @source_kind.setter
    def source_kind(self, value: str) -> None:
        payload = dict(self.source_meta)
        payload["source_kind"] = value
        self.source_meta = payload

    @property
    def stage_kind(self) -> str:
        """Best-effort canonical stage kind derived from legacy storage."""
        raw_value = self.source_meta.get("stage_kind", self.role)
        return str(raw_value).strip()

    @stage_kind.setter
    def stage_kind(self, value: str) -> None:
        payload = dict(self.source_meta)
        payload["stage_kind"] = value
        self.source_meta = payload


class AnalysisRunRecord(SQLModel, table=False):
    """Canonical analysis-run contract backed by characterization TraceBatch rows."""

    id: int | None = None
    dataset_id: int | None = None
    design_id: int
    analysis_id: str
    analysis_label: str = ""
    run_id: str = ""
    status: str
    input_trace_ids: list[int] = Field(default_factory=list)
    input_batch_ids: list[int] = Field(default_factory=list)
    input_scope: str = ""
    trace_mode_group: str = ""
    config_payload: dict = Field(default_factory=dict)
    summary_payload: dict = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: datetime | None = None


class UserRecord(SQLModel, table=True):
    """Local user account for multi-user app and API authentication."""

    __tablename__ = "user_records"  # type: ignore[assignment]

    id: int | None = Field(default=None, primary_key=True)
    username: str = Field(unique=True, index=True)
    password_hash: str
    role: str = Field(index=True)
    is_active: bool = Field(default=True, index=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    last_login_at: datetime | None = None


class AuditLogRecord(SQLModel, table=True):
    """Audit trail for actor-driven task and write operations."""

    __tablename__ = "audit_log_records"  # type: ignore[assignment]

    id: int | None = Field(default=None, primary_key=True)
    actor_id: int | None = Field(default=None, foreign_key="user_records.id", index=True)
    action_kind: str = Field(index=True)
    resource_kind: str = Field(index=True)
    resource_id: str = Field(index=True)
    summary: str
    payload: dict = Field(default_factory=dict, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=datetime.utcnow, index=True)


class TaskRecord(SQLModel, table=True):
    """Universal execution boundary for queued/running/completed task lifecycle."""

    __tablename__ = "task_records"  # type: ignore[assignment]

    id: int | None = Field(default=None, primary_key=True)
    task_kind: str = Field(index=True)
    status: str = Field(index=True)
    design_id: int = Field(foreign_key="dataset_records.id", index=True)
    trace_batch_id: int | None = Field(
        default=None,
        foreign_key="result_bundle_records.id",
        index=True,
    )
    analysis_run_id: int | None = Field(
        default=None,
        foreign_key="result_bundle_records.id",
        index=True,
    )
    requested_by: str
    actor_id: int | None = Field(default=None, foreign_key="user_records.id", index=True)
    dedupe_key: str | None = Field(default=None, index=True)
    request_payload: dict = Field(default_factory=dict, sa_column=Column(JSON))
    progress_payload: dict = Field(default_factory=dict, sa_column=Column(JSON))
    result_summary_payload: dict = Field(default_factory=dict, sa_column=Column(JSON))
    error_payload: dict = Field(default_factory=dict, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=datetime.utcnow, index=True)
    started_at: datetime | None = Field(default=None, index=True)
    heartbeat_at: datetime | None = Field(default=None, index=True)
    completed_at: datetime | None = Field(default=None, index=True)


class DerivedParameter(SQLModel, table=True):
    """Physical parameter derived from trace analysis."""

    __tablename__ = "derived_parameters"  # type: ignore[assignment]

    id: int | None = Field(default=None, primary_key=True)
    dataset_id: int = Field(foreign_key="dataset_records.id", index=True)
    design_id: int | None = Field(default=None, index=True)

    device_type: DeviceType
    name: str
    value: float
    unit: str | None = None
    method: str | None = None
    extra: dict = Field(default_factory=dict, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=datetime.utcnow)

    dataset: Optional["DesignRecord"] = Relationship(back_populates="derived_params")


class ParameterDesignation(SQLModel, table=True):
    """Semantic designation for an extracted parameter."""

    __tablename__ = "parameter_designations"  # type: ignore[assignment]

    id: int | None = Field(default=None, primary_key=True)
    dataset_id: int = Field(foreign_key="dataset_records.id", index=True)
    design_id: int | None = Field(default=None, index=True)

    designated_name: str = Field(index=True)
    source_analysis_type: str
    source_parameter_name: str
    created_at: datetime = Field(default_factory=datetime.utcnow)

    dataset: Optional["DesignRecord"] = Relationship(back_populates="designations")


class CircuitRecord(SQLModel, table=True):
    """Schema definition for a superconducting circuit."""

    __tablename__ = "circuit_records"  # type: ignore[assignment]

    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(unique=True, index=True)
    definition_json: str = Field(sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=datetime.utcnow)


# Legacy aliases retained until callers fully migrate to canonical names.
DatasetTagLink = DesignTagLink
ResultBundleDataLink = TraceBatchTraceLink
DatasetRecord = DesignRecord
DataRecord = TraceRecord
ResultBundleRecord = TraceBatchRecord
