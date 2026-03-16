from dataclasses import dataclass
from typing import Literal

CircuitDefinitionSortBy = Literal["created_at", "updated_at", "name"]
SortOrder = Literal["asc", "desc"]
VisibilityScope = Literal["local", "private", "workspace"]
LifecycleState = Literal["active", "archived", "deleted"]
ValidationSeverity = Literal["error", "warning", "info"]
ValidationStatus = Literal["valid", "warning", "invalid"]


@dataclass(frozen=True)
class AllowedActions:
    update: bool
    delete: bool
    publish: bool
    clone: bool


@dataclass(frozen=True)
class ValidationNotice:
    severity: ValidationSeverity
    code: str
    message: str
    source: str
    blocking: bool


@dataclass(frozen=True)
class ValidationSummary:
    status: ValidationStatus
    notice_count: int
    warning_count: int
    blocking_notice_count: int


@dataclass(frozen=True)
class CircuitDefinitionRecord:
    definition_id: int
    workspace_id: str
    visibility_scope: VisibilityScope
    lifecycle_state: LifecycleState
    owner_user_id: str
    owner_display_name: str
    name: str
    created_at: str
    updated_at: str
    concurrency_token: str
    source_hash: str
    source_text: str
    normalized_output: str
    validation_notices: tuple[ValidationNotice, ...]
    validation_summary: ValidationSummary
    preview_artifacts: tuple[str, ...]
    lineage_parent_id: int | None = None


@dataclass(frozen=True)
class CircuitDefinitionSummary:
    definition_id: int
    name: str
    created_at: str
    visibility_scope: VisibilityScope
    owner_display_name: str
    allowed_actions: AllowedActions


@dataclass(frozen=True)
class CircuitDefinitionDetail:
    definition_id: int
    workspace_id: str
    visibility_scope: VisibilityScope
    lifecycle_state: LifecycleState
    owner_user_id: str
    owner_display_name: str
    allowed_actions: AllowedActions
    name: str
    created_at: str
    updated_at: str
    concurrency_token: str
    source_hash: str
    source_text: str
    normalized_output: str
    validation_notices: tuple[ValidationNotice, ...]
    validation_summary: ValidationSummary
    preview_artifacts: tuple[str, ...]
    lineage_parent_id: int | None = None


@dataclass(frozen=True)
class CircuitDefinitionDraft:
    name: str
    source_text: str
    visibility_scope: VisibilityScope = "private"


@dataclass(frozen=True)
class CircuitDefinitionUpdate:
    source_text: str
    name: str | None = None
    concurrency_token: str | None = None


@dataclass(frozen=True)
class CircuitDefinitionCloneDraft:
    name: str | None = None


@dataclass(frozen=True)
class CircuitDefinitionListQuery:
    search_query: str | None = None
    sort_by: CircuitDefinitionSortBy = "updated_at"
    sort_order: SortOrder = "desc"
    limit: int = 20
    after: str | None = None
    before: str | None = None


@dataclass(frozen=True)
class CircuitDefinitionCatalogPage:
    rows: tuple[CircuitDefinitionSummary, ...]
    total_count: int
    next_cursor: str | None
    prev_cursor: str | None
    has_more: bool
