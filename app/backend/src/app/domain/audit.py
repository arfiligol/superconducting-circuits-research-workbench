from dataclasses import dataclass
from typing import Literal

AuditOutcome = Literal["accepted", "rejected", "completed", "failed"]
AuditExportStatus = Literal["queued", "running", "completed", "failed"]


@dataclass(frozen=True)
class AuditRecord:
    audit_id: str
    occurred_at: str
    actor_user_id: str
    actor_display_name: str | None
    session_id: str
    correlation_id: str
    workspace_id: str
    action_kind: str
    resource_kind: str
    resource_id: str
    outcome: AuditOutcome
    payload: dict[str, object]
    debug_ref: str


@dataclass(frozen=True)
class AuditActorSummary:
    user_id: str
    display_name: str | None


@dataclass(frozen=True)
class AuditListQuery:
    workspace_id: str | None = None
    actor_user_id: str | None = None
    action_kind: str | None = None
    resource_kind: str | None = None
    outcome: AuditOutcome | None = None
    after: str | None = None
    before: str | None = None
    limit: int = 50


@dataclass(frozen=True)
class AuditListRow:
    audit_id: str
    occurred_at: str
    workspace_id: str
    actor_summary: AuditActorSummary
    action_kind: str
    resource_kind: str
    resource_id: str
    outcome: AuditOutcome
    correlation_id: str


@dataclass(frozen=True)
class AuditListView:
    rows: tuple[AuditListRow, ...]
    total_count: int
    next_cursor: str | None
    prev_cursor: str | None
    has_more: bool
    filter_echo: AuditListQuery


@dataclass(frozen=True)
class AuditDetail:
    audit_id: str
    occurred_at: str
    actor_user_id: str
    session_id: str
    correlation_id: str
    workspace_id: str
    action_kind: str
    resource_kind: str
    resource_id: str
    outcome: AuditOutcome
    payload: dict[str, object]
    debug_ref: str


@dataclass(frozen=True)
class AuditArtifactRef:
    artifact_id: str
    backend: str
    format: str
    locator: str


@dataclass(frozen=True)
class AuditExportSummary:
    export_id: str
    status: AuditExportStatus
    workspace_id: str | None
    filter_echo: AuditListQuery
    artifact_ref: AuditArtifactRef | None
