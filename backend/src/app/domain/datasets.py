from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from src.app.domain.storage import ResultHandleRef, TracePayloadRef

DatasetStatus = Literal["Ready", "Queued", "Review"]
DatasetVisibilityScope = Literal["local", "private", "workspace"]
DatasetLifecycleState = Literal["active", "archived", "deleted"]
DatasetProfileField = Literal["device_type", "capabilities", "source"]
CompareReadiness = Literal["ready", "inspect_only", "blocked"]
TraceFamily = Literal["s_matrix", "y_matrix", "z_matrix"]
TraceModeGroup = Literal["base", "sideband", "all"]
TraceSourceKind = Literal["circuit_simulation", "layout_simulation", "measurement"]
TraceStageKind = Literal["raw", "preprocess", "postprocess"]
CharacterizationResultStatus = Literal["completed", "failed", "blocked"]
CharacterizationTaggingStatus = Literal["applied", "already_applied"]
CharacterizationAvailabilityState = Literal["recommended", "available", "unavailable"]
CharacterizationPrerequisiteState = Literal["ready", "requires_upstream_result", "blocked"]
CharacterizationCollectionReadinessState = Literal["ready", "inspect_only", "blocked"]
TraceCapabilityStatus = Literal["eligible", "ineligible"]
RawDataIngestionKind = Literal["measurement", "layout_simulation"]
SimulationResultPublicationState = Literal["published", "already_published"]
ResultTracePublicationState = SimulationResultPublicationState
CharacterizationArtifactViewKind = Literal["table", "plot", "text", "json", "preset_query"]
CharacterizationArtifactAxisRole = Literal["input", "derived", "member"]
CharacterizationArtifactQueryStyle = Literal["preset_driven", "static"]
CharacterizationArtifactQueryField = Literal["view_mode", "preset_id"]


@dataclass(frozen=True)
class DatasetAllowedActions:
    select: bool
    update_profile: bool
    publish: bool
    archive: bool
    delete: bool = False
    ingest_raw_data: bool = False


@dataclass(frozen=True)
class DatasetCatalogRow:
    dataset_id: str
    name: str
    visibility_scope: DatasetVisibilityScope
    lifecycle_state: DatasetLifecycleState
    device_type: str
    updated_at: str
    allowed_actions: DatasetAllowedActions
    family: str
    owner_display_name: str


@dataclass(frozen=True)
class DatasetDetail:
    dataset_id: str
    name: str
    family: str
    owner: str
    owner_user_id: str
    workspace_id: str
    visibility_scope: DatasetVisibilityScope
    lifecycle_state: DatasetLifecycleState
    updated_at: str
    device_type: str
    capabilities: tuple[str, ...]
    source: str
    status: DatasetStatus
    allowed_actions: DatasetAllowedActions


@dataclass(frozen=True)
class DatasetProfileUpdate:
    device_type: str
    capabilities: tuple[str, ...]
    source: str


@dataclass(frozen=True)
class DatasetProfileUpdateResult:
    dataset: DatasetDetail
    updated_fields: tuple[DatasetProfileField, ...]


@dataclass(frozen=True)
class DatasetCreateDraft:
    name: str
    family: str
    device_type: str
    source: str


@dataclass(frozen=True)
class DatasetLifecycleMutationResult:
    dataset: DatasetDetail
    catalog_row: DatasetCatalogRow


@dataclass(frozen=True)
class RawDataTraceDraft:
    trace_id: str | None
    family: TraceFamily
    parameter: str
    representation: str
    trace_mode_group: TraceModeGroup
    stage_kind: TraceStageKind
    provenance_summary: str
    axes: tuple[TraceAxis, ...]
    preview_payload: dict[str, object]


@dataclass(frozen=True)
class RawDataIngestionDraft:
    kind: RawDataIngestionKind
    design_name: str
    design_id: str | None
    provenance_label: str
    traces: tuple[RawDataTraceDraft, ...]


@dataclass(frozen=True)
class RawDataIngestionResult:
    dataset: DatasetDetail
    design: DesignBrowseRow
    traces: tuple[TraceMetadataSummary, ...]


@dataclass(frozen=True)
class DesignCreateDraft:
    name: str


@dataclass(frozen=True)
class DatasetDesignMutationResult:
    dataset: DatasetDetail
    design: DesignBrowseRow


@dataclass(frozen=True)
class SimulationResultPublicationDraft:
    design_name: str | None = None
    design_id: str | None = None


@dataclass(frozen=True)
class SimulationResultPublicationResult:
    state: SimulationResultPublicationState
    publication_key: str
    published_at: str
    dataset: DatasetDetail
    design: DesignBrowseRow
    traces: tuple[TraceMetadataSummary, ...]


@dataclass(frozen=True)
class ResultTracePublicationDraft:
    design_id: str
    trace_keys: tuple[str, ...]
    metric: str
    parameter_name: str | None = None


@dataclass(frozen=True)
class ResultTracePublicationResult:
    state: ResultTracePublicationState
    publication_key: str
    published_at: str
    dataset: DatasetDetail
    design: DesignBrowseRow
    trace_keys: tuple[str, ...]
    traces: tuple[TraceMetadataSummary, ...]


@dataclass(frozen=True)
class SimulationResultPublicationRecord:
    publication_key: str
    published_at: str
    source_task_id: int
    source_dataset_id: str | None
    source_result_handle_ids: tuple[str, ...]
    target_dataset_id: str
    target_design_id: str
    target_design_name: str
    published_trace_ids: tuple[str, ...]


@dataclass(frozen=True)
class TaggedCoreMetricSummary:
    metric_id: str
    label: str
    source_parameter: str
    designated_metric: str
    tagged_at: str


@dataclass(frozen=True)
class DesignBrowseRow:
    design_id: str
    dataset_id: str
    name: str
    source_coverage: dict[str, int]
    compare_readiness: CompareReadiness
    trace_count: int
    updated_at: str


@dataclass(frozen=True)
class DesignBrowseQuery:
    search: str | None = None


@dataclass(frozen=True)
class TraceAxesSummary:
    rank: int
    axis_names: tuple[str, ...]
    axis_units: tuple[str, ...]
    axis_lengths: tuple[int, ...]


@dataclass(frozen=True)
class TraceCollectionProjection:
    collection_key: str
    kind: str
    group_label: str


@dataclass(frozen=True)
class InputCollectionAxis:
    name: str
    unit: str
    length: int
    values: tuple[float, ...] = ()


@dataclass(frozen=True)
class InputCollectionTraceSummary:
    trace_id: str
    family: TraceFamily
    parameter: str
    representation: str
    axis_signature: str
    collection_key: str | None = None


@dataclass(frozen=True)
class CharacterizationInputCollectionPayload:
    selected_trace_ids: tuple[str, ...]
    trace_count: int
    axis_signature: str | None
    available_sweep_axes: tuple[str, ...]
    shared_axes: tuple[InputCollectionAxis, ...]
    grouping_summary: str
    collection_projection: TraceCollectionProjection | None = None
    traces: tuple[InputCollectionTraceSummary, ...] = ()


@dataclass(frozen=True)
class CharacterizationCollectionMemberSummary:
    member_key: str
    trace_id: str
    label: str
    source_kind: TraceSourceKind
    stage_kind: TraceStageKind
    trace_mode_group: TraceModeGroup
    family: TraceFamily
    parameter: str
    representation: str
    provenance_summary: str
    axis_signature: str
    collection_key: str | None = None


@dataclass(frozen=True)
class CharacterizationInputResultRef:
    analysis_id: str
    result_id: str
    run_id: str | None = None
    artifact_id: str | None = None
    contract_version: str | None = None
    title: str | None = None


@dataclass(frozen=True)
class CharacterizationUpstreamResultRequirement:
    required_upstream_analysis_ids: tuple[str, ...]
    satisfied_result_refs: tuple[CharacterizationInputResultRef, ...] = ()
    summary: str = ""


@dataclass(frozen=True)
class CharacterizationReviewAnalysisSummary:
    analysis_id: str
    label: str
    availability_state: CharacterizationAvailabilityState
    prerequisite_state: CharacterizationPrerequisiteState
    summary: str


@dataclass(frozen=True)
class CharacterizationDataCollectionReview:
    selected_trace_ids: tuple[str, ...]
    selection_summary: str
    shared_axes: tuple[InputCollectionAxis, ...]
    available_sweep_axes: tuple[str, ...]
    collection_members: tuple[CharacterizationCollectionMemberSummary, ...]
    source_coverage: dict[str, int]
    grouping_summary: str
    readiness_state: CharacterizationCollectionReadinessState
    runnable_analyses: tuple[CharacterizationReviewAnalysisSummary, ...]
    blocked_analyses: tuple[CharacterizationReviewAnalysisSummary, ...]
    collection_projection: TraceCollectionProjection | None = None


@dataclass(frozen=True)
class TraceMetadataSummary:
    trace_id: str
    dataset_id: str
    design_id: str
    family: TraceFamily
    parameter: str
    representation: str
    trace_mode_group: TraceModeGroup
    source_kind: TraceSourceKind
    stage_kind: TraceStageKind
    provenance_summary: str
    ndim: int = 0
    shape: tuple[int, ...] = ()
    axes_summary: TraceAxesSummary = TraceAxesSummary(0, (), (), ())
    axis_signature: str = ""
    available_sweep_axes: tuple[str, ...] = ()
    collection_projection: TraceCollectionProjection | None = None
    analysis_capabilities: tuple[TraceAnalysisCapability, ...] = ()


@dataclass(frozen=True)
class TraceCapabilityReason:
    code: str
    message: str
    evidence: dict[str, object]


@dataclass(frozen=True)
class TraceAnalysisCapability:
    capability_id: str
    analysis_id: str
    analysis_label: str
    input_role: str
    input_role_label: str
    status: TraceCapabilityStatus
    summary: str
    reasons: tuple[TraceCapabilityReason, ...]


@dataclass(frozen=True)
class TraceAllowedActions:
    edit: bool
    delete: bool


@dataclass(frozen=True)
class TraceBrowseRow:
    trace_id: str
    dataset_id: str
    design_id: str
    family: TraceFamily
    parameter: str
    representation: str
    trace_mode_group: TraceModeGroup
    source_kind: TraceSourceKind
    stage_kind: TraceStageKind
    ndim: int
    shape: tuple[int, ...]
    axes_summary: TraceAxesSummary
    axis_signature: str
    available_sweep_axes: tuple[str, ...]
    collection_projection: TraceCollectionProjection | None
    provenance_summary: str
    allowed_actions: TraceAllowedActions
    mutation_policy_summary: str
    analysis_capabilities: tuple[TraceAnalysisCapability, ...] = ()


@dataclass(frozen=True)
class TraceBrowseQuery:
    search: str | None = None
    family: TraceFamily | None = None
    representation: str | None = None
    source_kind: TraceSourceKind | None = None
    trace_mode_group: TraceModeGroup | None = None
    axis_name: str | None = None
    collection_key: str | None = None


@dataclass(frozen=True)
class TraceAxis:
    name: str
    unit: str
    length: int


@dataclass(frozen=True)
class TraceDetail:
    trace_id: str
    dataset_id: str
    design_id: str
    axes: tuple[TraceAxis, ...]
    preview_payload: dict[str, object]
    payload_ref: TracePayloadRef | None
    result_handles: tuple[ResultHandleRef, ...]
    family: TraceFamily = "y_matrix"
    parameter: str = ""
    representation: str = ""
    trace_mode_group: TraceModeGroup = "base"
    source_kind: TraceSourceKind = "measurement"
    stage_kind: TraceStageKind = "raw"
    ndim: int = 0
    shape: tuple[int, ...] = ()
    axes_summary: TraceAxesSummary = TraceAxesSummary(0, (), (), ())
    axis_signature: str = ""
    available_sweep_axes: tuple[str, ...] = ()
    collection_projection: TraceCollectionProjection | None = None
    analysis_capabilities: tuple[TraceAnalysisCapability, ...] = ()


@dataclass(frozen=True)
class TraceEditableMetadata:
    parameter: str
    representation: str
    provenance_summary: str


@dataclass(frozen=True)
class TraceImmutableSummary:
    family: TraceFamily
    trace_mode_group: TraceModeGroup
    source_kind: TraceSourceKind
    stage_kind: TraceStageKind


@dataclass(frozen=True)
class TraceEditDetail:
    trace_id: str
    dataset_id: str
    design_id: str
    editable_metadata: TraceEditableMetadata
    immutable_summary: TraceImmutableSummary
    editable_numeric_payload: dict[str, object]
    allowed_actions: TraceAllowedActions
    mutation_policy_summary: str
    analysis_capabilities: tuple[TraceAnalysisCapability, ...] = ()


@dataclass(frozen=True)
class TraceMutationPolicy:
    allowed_actions: TraceAllowedActions
    summary: str


@dataclass(frozen=True)
class TraceUpdateDraft:
    parameter: str | None = None
    representation: str | None = None
    provenance_summary: str | None = None
    numeric_payload: dict[str, object] | None = None


@dataclass(frozen=True)
class TraceUpdateResult:
    trace: TraceBrowseRow


@dataclass(frozen=True)
class TraceDeleteResult:
    design: DesignBrowseRow
    deleted_trace_ids: tuple[str, ...]


@dataclass(frozen=True)
class CharacterizationResultSummary:
    result_id: str
    dataset_id: str
    design_id: str
    analysis_id: str
    title: str
    status: CharacterizationResultStatus
    freshness_summary: str
    provenance_summary: str
    trace_count: int
    artifact_count: int
    updated_at: str


@dataclass(frozen=True)
class CharacterizationResultBrowseQuery:
    search: str | None = None
    status: CharacterizationResultStatus | None = None
    analysis_id: str | None = None


@dataclass(frozen=True)
class CharacterizationAnalysisTraceCompatibility:
    matched_trace_count: int
    selected_trace_count: int
    recommended_trace_modes: tuple[str, ...]
    summary: str


@dataclass(frozen=True)
class CharacterizationAnalysisRegistryRow:
    analysis_id: str
    label: str
    availability_state: CharacterizationAvailabilityState
    required_config_fields: tuple[str, ...]
    trace_compatibility: CharacterizationAnalysisTraceCompatibility
    prerequisite_state: CharacterizationPrerequisiteState = "ready"
    upstream_result_requirement: CharacterizationUpstreamResultRequirement | None = None
    downstream_unlock_analysis_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class CharacterizationAnalysisRegistryQuery:
    selected_trace_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class CharacterizationAnalysisRegistryResult:
    rows: tuple[CharacterizationAnalysisRegistryRow, ...]
    input_collection_payload: CharacterizationInputCollectionPayload | None = None
    data_collection_review: CharacterizationDataCollectionReview | None = None

    def __iter__(self):
        return iter(self.rows)

    def __len__(self) -> int:
        return len(self.rows)

    def __getitem__(self, index: int) -> CharacterizationAnalysisRegistryRow:
        return self.rows[index]


@dataclass(frozen=True)
class CharacterizationRunHistoryRow:
    run_id: str
    dataset_id: str
    design_id: str
    analysis_id: str
    label: str
    status: CharacterizationResultStatus
    scope: str
    trace_count: int
    sources_summary: str
    provenance_summary: str
    updated_at: str
    result_id: str | None = None
    input_result_refs: tuple[CharacterizationInputResultRef, ...] = ()


@dataclass(frozen=True)
class CharacterizationRunHistoryQuery:
    analysis_id: str | None = None


@dataclass(frozen=True)
class CharacterizationDiagnostic:
    severity: Literal["error", "warning", "info"]
    code: str
    message: str
    blocking: bool


@dataclass(frozen=True)
class CharacterizationArtifactAxisSpec:
    axis_key: str
    label: str
    role: CharacterizationArtifactAxisRole
    unit: str | None
    length: int


@dataclass(frozen=True)
class CharacterizationArtifactMetricSpec:
    metric_key: str
    label: str
    unit: str | None


@dataclass(frozen=True)
class CharacterizationArtifactPreset:
    preset_id: str
    label: str
    view_kind: Literal["table", "plot"]
    rows_axis: str | None = None
    columns_axis: str | None = None
    cell_metric: str | None = None
    x_axis: str | None = None
    y_metric: str | None = None
    series_axis: str | None = None
    compare_axis: str | None = None


@dataclass(frozen=True)
class CharacterizationArtifactViewModeDefault:
    view_mode: CharacterizationArtifactViewKind
    preset_id: str


@dataclass(frozen=True)
class CharacterizationArtifactQuerySpec:
    query_style: CharacterizationArtifactQueryStyle
    supported_query_fields: tuple[CharacterizationArtifactQueryField, ...]
    supported_view_modes: tuple[CharacterizationArtifactViewKind, ...]
    supported_preset_ids: tuple[str, ...] = ()
    default_preset_id: str | None = None
    default_presets_by_view_mode: tuple[CharacterizationArtifactViewModeDefault, ...] = ()


@dataclass(frozen=True)
class CharacterizationArtifactRef:
    artifact_id: str
    category: str
    view_kind: CharacterizationArtifactViewKind
    title: str
    payload_format: Literal["json", "markdown", "svg", "csv"]
    payload_locator: str | None
    axes: tuple[CharacterizationArtifactAxisSpec, ...] = ()
    metric: CharacterizationArtifactMetricSpec | None = None
    presets: tuple[CharacterizationArtifactPreset, ...] = ()
    default_preset_id: str | None = None
    query_spec: CharacterizationArtifactQuerySpec | None = None
    identify_source: bool = False


@dataclass(frozen=True)
class CharacterizationArtifactPayloadQuery:
    view_mode: CharacterizationArtifactViewKind | None = None
    preset_id: str | None = None


@dataclass(frozen=True)
class CharacterizationArtifactPayload:
    artifact_id: str
    title: str
    preset_id: str
    view_kind: CharacterizationArtifactViewKind
    axes: tuple[CharacterizationArtifactAxisSpec, ...]
    metric: CharacterizationArtifactMetricSpec | None
    payload: dict[str, object]
    diagnostics: tuple[CharacterizationDiagnostic, ...] = ()


@dataclass(frozen=True)
class CharacterizationSourceParameterOption:
    artifact_id: str
    source_parameter: str
    label: str
    artifact_title: str
    current_designated_metric: str | None


@dataclass(frozen=True)
class CharacterizationDesignatedMetricOption:
    metric_key: str
    label: str


@dataclass(frozen=True)
class CharacterizationAppliedTag:
    artifact_id: str
    source_parameter: str
    designated_metric: str
    designated_metric_label: str
    tagged_at: str


@dataclass(frozen=True)
class CharacterizationIdentifySurface:
    source_parameters: tuple[CharacterizationSourceParameterOption, ...]
    designated_metrics: tuple[CharacterizationDesignatedMetricOption, ...]
    applied_tags: tuple[CharacterizationAppliedTag, ...]


@dataclass(frozen=True)
class CharacterizationResultDetail:
    result_id: str
    dataset_id: str
    design_id: str
    analysis_id: str
    title: str
    status: CharacterizationResultStatus
    freshness_summary: str
    provenance_summary: str
    trace_count: int
    updated_at: str
    input_trace_ids: tuple[str, ...]
    payload: dict[str, object]
    diagnostics: tuple[CharacterizationDiagnostic, ...]
    artifact_refs: tuple[CharacterizationArtifactRef, ...]
    identify_surface: CharacterizationIdentifySurface
    input_result_refs: tuple[CharacterizationInputResultRef, ...] = ()
    downstream_unlock_analysis_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class CharacterizationTaggingRequest:
    artifact_id: str
    source_parameter: str
    designated_metric: str


@dataclass(frozen=True)
class CharacterizationTaggingResult:
    tagging_status: CharacterizationTaggingStatus
    dataset_id: str
    design_id: str
    result_id: str
    artifact_id: str
    source_parameter: str
    designated_metric: str
    tagged_metric: TaggedCoreMetricSummary
