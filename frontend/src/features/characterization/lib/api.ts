import { apiRequest, apiRequestEnvelope } from "@/lib/api/client";
import { traceListKey } from "@/lib/api/datasets";

import type {
  CharacterizationAnalysisRegistry,
  CharacterizationAnalysisRegistryRow,
  CharacterizationArtifactAxisRole,
  CharacterizationArtifactAxisSpec,
  CharacterizationArtifactManifestViewKind,
  CharacterizationArtifactPayload,
  CharacterizationArtifactPayloadViewKind,
  CharacterizationArtifactPreset,
  CharacterizationArtifactQueryField,
  CharacterizationArtifactQuerySpec,
  CharacterizationArtifactQueryStyle,
  CharacterizationArtifactRef,
  CharacterizationArtifactViewModeDefault,
  CharacterizationAppliedTag,
  CharacterizationAvailabilityState,
  CharacterizationCollectionMemberSummary,
  CharacterizationCollectionReadinessState,
  CharacterizationDataCollectionReview,
  CharacterizationDesignatedMetricOption,
  CharacterizationDiagnostic,
  CharacterizationIdentifySurface,
  CharacterizationInputCollectionAxis,
  CharacterizationInputCollectionPayload,
  CharacterizationInputCollectionTraceSummary,
  CharacterizationInputResultRef,
  CharacterizationPagedRows,
  CharacterizationPrerequisiteState,
  CharacterizationResultDetail,
  CharacterizationResultStatus,
  CharacterizationResultSummary,
  CharacterizationReviewAnalysisSummary,
  CharacterizationRunHistoryRow,
  CharacterizationSourceParameterOption,
  CharacterizationTaggingInput,
  CharacterizationTaggingResult,
  CharacterizationTraceCollectionProjection,
  CharacterizationTraceSelectionRow,
  CharacterizationUpstreamResultRequirement,
} from "@/features/characterization/lib/contracts";

type CharacterizationAnalysisRegistryRowResponse = Readonly<{
  analysis_id: string;
  label: string;
  availability_state: CharacterizationAvailabilityState;
  required_config_fields: readonly string[];
  trace_compatibility: Readonly<{
    matched_trace_count: number;
    selected_trace_count: number;
    recommended_trace_modes: readonly string[];
    summary: string;
  }>;
  prerequisite_state: CharacterizationPrerequisiteState;
  upstream_result_requirement:
    | Readonly<{
        required_upstream_analysis_ids: readonly string[];
        satisfied_result_refs: readonly CharacterizationInputResultRefResponse[];
        summary: string;
      }>
    | null;
  downstream_unlock_analysis_ids: readonly string[];
}>;

type CharacterizationRunHistoryRowResponse = Readonly<{
  run_id: string;
  dataset_id: string;
  design_id: string;
  analysis_id: string;
  label: string;
  status: CharacterizationResultStatus;
  scope: string;
  trace_count: number;
  sources_summary: string;
  provenance_summary: string;
  updated_at: string;
  result_id: string | null;
}>;

type CharacterizationResultSummaryResponse = Readonly<{
  result_id: string;
  dataset_id: string;
  design_id: string;
  analysis_id: string;
  title: string;
  status: CharacterizationResultStatus;
  freshness_summary: string;
  provenance_summary: string;
  trace_count: number;
  artifact_count: number;
  updated_at: string;
}>;

type CharacterizationDiagnosticResponse = Readonly<{
  severity: CharacterizationDiagnostic["severity"];
  code: string;
  message: string;
  blocking: boolean;
}>;

type CharacterizationInputCollectionAxisResponse = Readonly<{
  name: string;
  unit: string | null;
  length: number;
  values?: readonly number[] | null;
}>;

type CharacterizationInputCollectionTraceSummaryResponse = Readonly<{
  trace_id: string;
  family: string;
  parameter: string;
  representation: string;
  axis_signature: string;
  collection_key?: string | null;
}>;

type CharacterizationTraceCollectionProjectionResponse =
  | Readonly<{
      collection_id?: string | null;
      label: string;
      summary: string;
      trace_count?: number | null;
    }>
  | Readonly<{
      collection_key?: string | null;
      kind?: string | null;
      group_label?: string | null;
    }>;

type CharacterizationInputCollectionPayloadResponse = Readonly<{
  selected_trace_ids: readonly string[];
  trace_count: number;
  axis_signature: string | null;
  available_sweep_axes: readonly string[];
  shared_axes: readonly CharacterizationInputCollectionAxisResponse[];
  grouping_summary: string;
  collection_projection?: CharacterizationTraceCollectionProjectionResponse | null;
  traces?: readonly CharacterizationInputCollectionTraceSummaryResponse[] | null;
}>;

type CharacterizationCollectionMemberSummaryResponse = Readonly<{
  member_key: string;
  trace_id: string;
  label: string;
  source_kind: string;
  stage_kind: string;
  trace_mode_group: string;
  family: string;
  parameter: string;
  representation: string;
  provenance_summary: string;
  axis_signature: string;
  collection_key?: string | null;
}>;

type CharacterizationReviewAnalysisSummaryResponse = Readonly<{
  analysis_id: string;
  label: string;
  availability_state: CharacterizationAvailabilityState;
  prerequisite_state: CharacterizationPrerequisiteState;
  summary: string;
}>;

type CharacterizationDataCollectionReviewResponse = Readonly<{
  selected_trace_ids: readonly string[];
  selection_summary: string;
  shared_axes: readonly CharacterizationInputCollectionAxisResponse[];
  available_sweep_axes: readonly string[];
  collection_members: readonly CharacterizationCollectionMemberSummaryResponse[];
  source_coverage: Readonly<Record<string, number>>;
  grouping_summary: string;
  readiness_state: CharacterizationCollectionReadinessState;
  runnable_analyses: readonly CharacterizationReviewAnalysisSummaryResponse[];
  blocked_analyses: readonly CharacterizationReviewAnalysisSummaryResponse[];
  collection_projection?: CharacterizationTraceCollectionProjectionResponse | null;
}>;

type CharacterizationAnalysisRegistryResponse = Readonly<{
  rows: readonly CharacterizationAnalysisRegistryRowResponse[];
  input_collection_payload: CharacterizationInputCollectionPayloadResponse | null;
  data_collection_review: CharacterizationDataCollectionReviewResponse | null;
}>;

type CharacterizationInputResultRefResponse = Readonly<{
  analysis_id: string;
  result_id: string;
  run_id?: string | null;
  artifact_id?: string | null;
  contract_version?: string | null;
  title?: string | null;
}>;

type CharacterizationArtifactAxisSpecResponse = Readonly<{
  axis_key: string;
  label: string;
  role: CharacterizationArtifactAxisRole;
  unit: string | null;
  length: number;
}>;

type CharacterizationArtifactMetricSpecResponse = Readonly<{
  metric_key: string;
  label: string;
  unit: string | null;
}>;

type CharacterizationArtifactPresetResponse = Readonly<{
  preset_id: string;
  label: string;
  view_kind: "table" | "plot";
  rows_axis?: string | null;
  columns_axis?: string | null;
  cell_metric?: string | null;
  x_axis?: string | null;
  y_metric?: string | null;
  series_axis?: string | null;
  compare_axis?: string | null;
}>;

type CharacterizationArtifactQuerySpecResponse = Readonly<{
  query_style: CharacterizationArtifactQueryStyle;
  supported_query_fields: readonly CharacterizationArtifactQueryField[];
  supported_view_modes: readonly CharacterizationArtifactPayloadViewKind[];
  supported_preset_ids?: readonly string[] | null;
  default_preset_id?: string | null;
  default_presets_by_view_mode?: readonly Readonly<{
    view_mode: CharacterizationArtifactPayloadViewKind;
    preset_id: string;
  }>[] | null;
}>;

type CharacterizationArtifactRefResponse = Readonly<{
  artifact_id: string;
  category: string;
  view_kind: CharacterizationArtifactManifestViewKind;
  title: string;
  payload_format: "json" | "markdown" | "svg" | "csv";
  payload_locator: string | null;
  axes?: readonly CharacterizationArtifactAxisSpecResponse[] | null;
  metric?: CharacterizationArtifactMetricSpecResponse | null;
  presets?: readonly CharacterizationArtifactPresetResponse[] | null;
  default_preset_id?: string | null;
  query_spec?: CharacterizationArtifactQuerySpecResponse | null;
  identify_source?: boolean | null;
}>;

type CharacterizationResultDetailResponse = Readonly<{
  result_id: string;
  dataset_id: string;
  design_id: string;
  analysis_id: string;
  title: string;
  status: CharacterizationResultStatus;
  freshness_summary: string;
  provenance_summary: string;
  trace_count: number;
  updated_at: string;
  input_trace_ids: readonly string[];
  input_result_refs: readonly CharacterizationInputResultRefResponse[];
  payload: Readonly<Record<string, unknown>>;
  diagnostics: readonly CharacterizationDiagnosticResponse[];
  artifact_refs: readonly CharacterizationArtifactRefResponse[];
  identify_surface: Readonly<{
    source_parameters: readonly CharacterizationSourceParameterResponse[];
    designated_metrics: readonly CharacterizationDesignatedMetricOptionResponse[];
    applied_tags: readonly CharacterizationAppliedTagResponse[];
  }>;
  downstream_unlock_analysis_ids: readonly string[];
}>;

type CharacterizationSourceParameterResponse = Readonly<{
  artifact_id: string;
  source_parameter: string;
  label: string;
  artifact_title: string;
  current_designated_metric: string | null;
}>;

type CharacterizationDesignatedMetricOptionResponse = Readonly<{
  metric_key: string;
  label: string;
}>;

type CharacterizationAppliedTagResponse = Readonly<{
  artifact_id: string;
  source_parameter: string;
  designated_metric: string;
  designated_metric_label: string;
  tagged_at: string;
}>;

type CharacterizationTaggingResultResponse = Readonly<{
  tagging_status: CharacterizationTaggingResult["taggingStatus"];
  dataset_id: string;
  design_id: string;
  result_id: string;
  artifact_id: string;
  source_parameter: string;
  designated_metric: string;
  tagged_metric: Readonly<{
    metric_id: string;
    label: string;
    source_parameter: string;
    designated_metric: string;
    tagged_at: string;
  }>;
}>;

type CharacterizationCursorMeta = Readonly<{
  generated_at: string;
  limit: number;
  next_cursor: string | null;
  prev_cursor: string | null;
  has_more: boolean;
  filter_echo: Readonly<Record<string, unknown>>;
}>;

type CharacterizationResultsListQuery = Readonly<{
  search?: string | null;
  status?: CharacterizationResultStatus | null;
  analysisId?: string | null;
}>;

type CharacterizationAnalysisRegistryQuery = Readonly<{
  selectedTraceIds?: readonly string[] | null;
}>;

type CharacterizationRunHistoryQuery = Readonly<{
  analysisId?: string | null;
  cursor?: string | null;
}>;

type CharacterizationTraceSelectionRowResponse = Readonly<{
  trace_id: string;
  dataset_id: string;
  design_id: string;
  family: string;
  parameter: string;
  representation: string;
  trace_mode_group: string;
  source_kind: string;
  stage_kind: string;
  provenance_summary: string;
  allowed_actions: Readonly<{
    edit: boolean;
    delete: boolean;
  }>;
  mutation_policy_summary: string;
  axes_summary?:
    | string
    | Readonly<{
        rank?: number | null;
        axis_names?: readonly string[] | null;
        axis_units?: readonly (string | null)[] | null;
        axis_lengths?: readonly number[] | null;
      }>
    | null;
  axis_signature?: string | null;
  available_sweep_axes?: readonly string[] | null;
  collection_projection?: CharacterizationTraceCollectionProjectionResponse | null;
}>;

type CharacterizationArtifactPayloadResponse = Readonly<{
  artifact_id: string;
  title: string;
  preset_id: string;
  view_kind: CharacterizationArtifactPayloadViewKind;
  axes: readonly CharacterizationArtifactAxisSpecResponse[];
  metric?: CharacterizationArtifactMetricSpecResponse | null;
  payload: Readonly<Record<string, unknown>>;
  diagnostics?: readonly CharacterizationDiagnosticResponse[] | null;
}>;

export function characterizationResultsListKey(datasetId: string, designId: string) {
  return `/api/backend/datasets/${encodeURIComponent(datasetId)}/designs/${encodeURIComponent(
    designId,
  )}/characterization-results`;
}

export function characterizationResultDetailKey(
  datasetId: string,
  designId: string,
  resultId: string,
) {
  return `${characterizationResultsListKey(datasetId, designId)}/${encodeURIComponent(resultId)}`;
}

export function characterizationTaggingsKey(
  datasetId: string,
  designId: string,
  resultId: string,
) {
  return `${characterizationResultDetailKey(datasetId, designId, resultId)}/taggings`;
}

export function characterizationArtifactPayloadKey(
  datasetId: string,
  designId: string,
  resultId: string,
  artifactId: string,
  options: Readonly<{
    viewMode?: CharacterizationArtifactPayloadViewKind | null;
    presetId?: string | null;
  }>,
) {
  const params = new URLSearchParams();
  if (options.viewMode) {
    params.set("view_mode", options.viewMode);
  }
  if (options.presetId) {
    params.set("preset_id", options.presetId);
  }
  const search = params.toString();
  const path = `${characterizationResultDetailKey(
    datasetId,
    designId,
    resultId,
  )}/artifacts/${encodeURIComponent(artifactId)}`;
  return search ? `${path}?${search}` : path;
}

export function characterizationAnalysisRegistryKey(
  datasetId: string,
  designId: string,
  selectedTraceIds?: readonly string[] | null,
) {
  const params = new URLSearchParams();
  for (const traceId of selectedTraceIds ?? []) {
    params.append("selected_trace_ids", traceId);
  }
  const path = `/api/backend/datasets/${encodeURIComponent(datasetId)}/designs/${encodeURIComponent(
    designId,
  )}/characterization-analysis-registry`;
  const search = params.toString();
  return search ? `${path}?${search}` : path;
}

export function characterizationRunHistoryKey(
  datasetId: string,
  designId: string,
  options?: CharacterizationRunHistoryQuery,
) {
  const params = new URLSearchParams();
  if (options?.analysisId) {
    params.set("analysis_id", options.analysisId);
  }
  if (options?.cursor) {
    params.set("cursor", options.cursor);
  }
  const path = `/api/backend/datasets/${encodeURIComponent(datasetId)}/designs/${encodeURIComponent(
    designId,
  )}/characterization-run-history`;
  const search = params.toString();
  return search ? `${path}?${search}` : path;
}

function mapCharacterizationResultSummary(
  payload: CharacterizationResultSummaryResponse,
): CharacterizationResultSummary {
  return {
    resultId: payload.result_id,
    datasetId: payload.dataset_id,
    designId: payload.design_id,
    analysisId: payload.analysis_id,
    title: payload.title,
    status: payload.status,
    freshnessSummary: payload.freshness_summary,
    provenanceSummary: payload.provenance_summary,
    traceCount: payload.trace_count,
    artifactCount: payload.artifact_count,
    updatedAt: payload.updated_at,
  };
}

function mapCharacterizationDiagnostic(
  payload: CharacterizationDiagnosticResponse,
): CharacterizationDiagnostic {
  return {
    severity: payload.severity,
    code: payload.code,
    message: payload.message,
    blocking: payload.blocking,
  };
}

function mapCharacterizationInputCollectionAxis(
  payload: CharacterizationInputCollectionAxisResponse,
): CharacterizationInputCollectionAxis {
  return {
    name: payload.name,
    unit: payload.unit ?? null,
    length: payload.length,
    values: [...(payload.values ?? [])],
  };
}

function mapCharacterizationTraceCollectionProjection(
  payload: CharacterizationTraceCollectionProjectionResponse | null | undefined,
): CharacterizationTraceCollectionProjection | null {
  if (!payload) {
    return null;
  }

  if ("label" in payload && "summary" in payload) {
    return {
      collectionId: payload.collection_id ?? null,
      label: payload.label,
      summary: payload.summary,
      traceCount: payload.trace_count ?? 0,
    };
  }

  return {
    collectionId: payload.collection_key ?? null,
    label: payload.group_label?.trim() || payload.collection_key || "Collection",
    summary:
      payload.kind === "trace_structure_group"
        ? "Shared trace structure"
        : payload.kind?.replaceAll("_", " ") || "Sweep-aware grouping",
    traceCount: 0,
  };
}

function mapCharacterizationInputCollectionTraceSummary(
  payload: CharacterizationInputCollectionTraceSummaryResponse,
): CharacterizationInputCollectionTraceSummary {
  return {
    traceId: payload.trace_id,
    family: payload.family,
    parameter: payload.parameter,
    representation: payload.representation,
    axisSignature: payload.axis_signature,
    collectionKey: payload.collection_key ?? null,
  };
}

function mapCharacterizationInputCollectionPayload(
  payload: CharacterizationInputCollectionPayloadResponse | null,
): CharacterizationInputCollectionPayload | null {
  if (!payload) {
    return null;
  }

  return {
    selectedTraceIds: [...payload.selected_trace_ids],
    traceCount: payload.trace_count,
    axisSignature: payload.axis_signature ?? null,
    availableSweepAxes: [...payload.available_sweep_axes],
    sharedAxes: payload.shared_axes.map(mapCharacterizationInputCollectionAxis),
    groupingSummary: payload.grouping_summary,
    collectionProjection: mapCharacterizationTraceCollectionProjection(
      payload.collection_projection,
    ),
    traces: (payload.traces ?? []).map(mapCharacterizationInputCollectionTraceSummary),
  };
}

function mapCharacterizationInputResultRef(
  payload: CharacterizationInputResultRefResponse,
): CharacterizationInputResultRef {
  return {
    analysisId: payload.analysis_id,
    resultId: payload.result_id,
    runId: payload.run_id ?? null,
    artifactId: payload.artifact_id ?? null,
    contractVersion: payload.contract_version ?? null,
    title: payload.title ?? null,
  };
}

function mapCharacterizationUpstreamResultRequirement(
  payload: CharacterizationAnalysisRegistryRowResponse["upstream_result_requirement"],
): CharacterizationUpstreamResultRequirement | null {
  if (!payload) {
    return null;
  }

  return {
    requiredUpstreamAnalysisIds: [...payload.required_upstream_analysis_ids],
    satisfiedResultRefs: payload.satisfied_result_refs.map(mapCharacterizationInputResultRef),
    summary: payload.summary,
  };
}

function mapCharacterizationReviewAnalysisSummary(
  payload: CharacterizationReviewAnalysisSummaryResponse,
): CharacterizationReviewAnalysisSummary {
  return {
    analysisId: payload.analysis_id,
    label: payload.label,
    availabilityState: payload.availability_state,
    prerequisiteState: payload.prerequisite_state,
    summary: payload.summary,
  };
}

function mapCharacterizationCollectionMemberSummary(
  payload: CharacterizationCollectionMemberSummaryResponse,
): CharacterizationCollectionMemberSummary {
  return {
    memberKey: payload.member_key,
    traceId: payload.trace_id,
    label: payload.label,
    sourceKind: payload.source_kind,
    stageKind: payload.stage_kind,
    traceModeGroup: payload.trace_mode_group,
    family: payload.family,
    parameter: payload.parameter,
    representation: payload.representation,
    provenanceSummary: payload.provenance_summary,
    axisSignature: payload.axis_signature,
    collectionKey: payload.collection_key ?? null,
  };
}

function mapCharacterizationDataCollectionReview(
  payload: CharacterizationDataCollectionReviewResponse | null,
): CharacterizationDataCollectionReview | null {
  if (!payload) {
    return null;
  }

  return {
    selectedTraceIds: [...payload.selected_trace_ids],
    selectionSummary: payload.selection_summary,
    sharedAxes: payload.shared_axes.map(mapCharacterizationInputCollectionAxis),
    availableSweepAxes: [...payload.available_sweep_axes],
    collectionMembers: payload.collection_members.map(
      mapCharacterizationCollectionMemberSummary,
    ),
    sourceCoverage: payload.source_coverage,
    groupingSummary: payload.grouping_summary,
    readinessState: payload.readiness_state,
    runnableAnalyses: payload.runnable_analyses.map(mapCharacterizationReviewAnalysisSummary),
    blockedAnalyses: payload.blocked_analyses.map(mapCharacterizationReviewAnalysisSummary),
    collectionProjection: mapCharacterizationTraceCollectionProjection(
      payload.collection_projection,
    ),
  };
}

function mapCharacterizationAnalysisRegistryRow(
  payload: CharacterizationAnalysisRegistryRowResponse,
): CharacterizationAnalysisRegistryRow {
  return {
    analysisId: payload.analysis_id,
    label: payload.label,
    availabilityState: payload.availability_state,
    requiredConfigFields: [...payload.required_config_fields],
    traceCompatibility: {
      matchedTraceCount: payload.trace_compatibility.matched_trace_count,
      selectedTraceCount: payload.trace_compatibility.selected_trace_count,
      recommendedTraceModes: [...payload.trace_compatibility.recommended_trace_modes],
      summary: payload.trace_compatibility.summary,
    },
    prerequisiteState: payload.prerequisite_state,
    upstreamResultRequirement: mapCharacterizationUpstreamResultRequirement(
      payload.upstream_result_requirement,
    ),
    downstreamUnlockAnalysisIds: [...payload.downstream_unlock_analysis_ids],
  };
}

function mapCharacterizationRunHistoryRow(
  payload: CharacterizationRunHistoryRowResponse,
): CharacterizationRunHistoryRow {
  return {
    runId: payload.run_id,
    datasetId: payload.dataset_id,
    designId: payload.design_id,
    analysisId: payload.analysis_id,
    label: payload.label,
    status: payload.status,
    scope: payload.scope,
    traceCount: payload.trace_count,
    sourcesSummary: payload.sources_summary,
    provenanceSummary: payload.provenance_summary,
    updatedAt: payload.updated_at,
    resultId: payload.result_id,
  };
}

function mapCharacterizationArtifactAxisSpec(
  payload: CharacterizationArtifactAxisSpecResponse,
): CharacterizationArtifactAxisSpec {
  return {
    axisKey: payload.axis_key,
    label: payload.label,
    role: payload.role,
    unit: payload.unit,
    length: payload.length,
  };
}

function mapCharacterizationArtifactMetricSpec(
  payload: CharacterizationArtifactMetricSpecResponse | null | undefined,
) {
  if (!payload) {
    return null;
  }

  return {
    metricKey: payload.metric_key,
    label: payload.label,
    unit: payload.unit,
  };
}

function mapCharacterizationArtifactPreset(
  payload: CharacterizationArtifactPresetResponse,
): CharacterizationArtifactPreset {
  return {
    presetId: payload.preset_id,
    label: payload.label,
    viewKind: payload.view_kind,
    rowsAxis: payload.rows_axis ?? null,
    columnsAxis: payload.columns_axis ?? null,
    cellMetric: payload.cell_metric ?? null,
    xAxis: payload.x_axis ?? null,
    yMetric: payload.y_metric ?? null,
    seriesAxis: payload.series_axis ?? null,
    compareAxis: payload.compare_axis ?? null,
  };
}

function mapCharacterizationArtifactViewModeDefault(
  payload: Readonly<{
    view_mode: CharacterizationArtifactPayloadViewKind;
    preset_id: string;
  }>,
): CharacterizationArtifactViewModeDefault {
  return {
    viewMode: payload.view_mode,
    presetId: payload.preset_id,
  };
}

function mapCharacterizationArtifactQuerySpec(
  payload: CharacterizationArtifactQuerySpecResponse | null | undefined,
): CharacterizationArtifactQuerySpec | null {
  if (!payload) {
    return null;
  }

  return {
    queryStyle: payload.query_style,
    supportedQueryFields: [...payload.supported_query_fields],
    supportedViewModes: [...payload.supported_view_modes],
    supportedPresetIds: [...(payload.supported_preset_ids ?? [])],
    defaultPresetId: payload.default_preset_id ?? null,
    defaultPresetsByViewMode: (payload.default_presets_by_view_mode ?? []).map(
      mapCharacterizationArtifactViewModeDefault,
    ),
  };
}

function mapCharacterizationArtifactRef(
  payload: CharacterizationArtifactRefResponse,
): CharacterizationArtifactRef {
  return {
    artifactId: payload.artifact_id,
    category: payload.category,
    viewKind: payload.view_kind,
    title: payload.title,
    payloadFormat: payload.payload_format,
    payloadLocator: payload.payload_locator,
    axes: (payload.axes ?? []).map(mapCharacterizationArtifactAxisSpec),
    metric: mapCharacterizationArtifactMetricSpec(payload.metric),
    presets: (payload.presets ?? []).map(mapCharacterizationArtifactPreset),
    defaultPresetId: payload.default_preset_id ?? null,
    querySpec: mapCharacterizationArtifactQuerySpec(payload.query_spec),
    identifySource: payload.identify_source ?? false,
  };
}

function mapCharacterizationSourceParameterOption(
  payload: CharacterizationSourceParameterResponse,
): CharacterizationSourceParameterOption {
  return {
    artifactId: payload.artifact_id,
    sourceParameter: payload.source_parameter,
    label: payload.label,
    artifactTitle: payload.artifact_title,
    currentDesignatedMetric: payload.current_designated_metric,
  };
}

function mapCharacterizationDesignatedMetricOption(
  payload: CharacterizationDesignatedMetricOptionResponse,
): CharacterizationDesignatedMetricOption {
  return {
    metricKey: payload.metric_key,
    label: payload.label,
  };
}

function mapCharacterizationAppliedTag(
  payload: CharacterizationAppliedTagResponse,
): CharacterizationAppliedTag {
  return {
    artifactId: payload.artifact_id,
    sourceParameter: payload.source_parameter,
    designatedMetric: payload.designated_metric,
    designatedMetricLabel: payload.designated_metric_label,
    taggedAt: payload.tagged_at,
  };
}

function mapCharacterizationIdentifySurface(
  payload: CharacterizationResultDetailResponse["identify_surface"],
): CharacterizationIdentifySurface {
  return {
    sourceParameters: payload.source_parameters.map(mapCharacterizationSourceParameterOption),
    designatedMetrics: payload.designated_metrics.map(
      mapCharacterizationDesignatedMetricOption,
    ),
    appliedTags: payload.applied_tags.map(mapCharacterizationAppliedTag),
  };
}

function mapCharacterizationResultDetail(
  payload: CharacterizationResultDetailResponse,
): CharacterizationResultDetail {
  return {
    resultId: payload.result_id,
    datasetId: payload.dataset_id,
    designId: payload.design_id,
    analysisId: payload.analysis_id,
    title: payload.title,
    status: payload.status,
    freshnessSummary: payload.freshness_summary,
    provenanceSummary: payload.provenance_summary,
    traceCount: payload.trace_count,
    updatedAt: payload.updated_at,
    inputTraceIds: [...payload.input_trace_ids],
    inputResultRefs: payload.input_result_refs.map(mapCharacterizationInputResultRef),
    payload: payload.payload,
    diagnostics: payload.diagnostics.map(mapCharacterizationDiagnostic),
    artifactRefs: payload.artifact_refs.map(mapCharacterizationArtifactRef),
    identifySurface: mapCharacterizationIdentifySurface(payload.identify_surface),
    downstreamUnlockAnalysisIds: [...payload.downstream_unlock_analysis_ids],
  };
}

function mapCharacterizationTaggingResult(
  payload: CharacterizationTaggingResultResponse,
): CharacterizationTaggingResult {
  return {
    taggingStatus: payload.tagging_status,
    datasetId: payload.dataset_id,
    designId: payload.design_id,
    resultId: payload.result_id,
    artifactId: payload.artifact_id,
    sourceParameter: payload.source_parameter,
    designatedMetric: payload.designated_metric,
    taggedMetric: {
      metricId: payload.tagged_metric.metric_id,
      label: payload.tagged_metric.label,
      sourceParameter: payload.tagged_metric.source_parameter,
      designatedMetric: payload.tagged_metric.designated_metric,
      taggedAt: payload.tagged_metric.tagged_at,
    },
  };
}

export function formatCharacterizationTraceAxesSummary(
  payload: CharacterizationTraceSelectionRowResponse["axes_summary"],
) {
  if (typeof payload === "string") {
    return payload.trim().length > 0 ? payload : "Axis summary unavailable";
  }

  if (!payload) {
    return "Axis summary unavailable";
  }

  const axisNames = (payload.axis_names ?? []).filter(
    (axisName): axisName is string =>
      typeof axisName === "string" && axisName.trim().length > 0,
  );
  const axisUnits = payload.axis_units ?? [];
  const axisLengths = (payload.axis_lengths ?? []).filter(
    (axisLength): axisLength is number => Number.isFinite(axisLength),
  );

  if (axisNames.length === 0) {
    return typeof payload.rank === "number" && payload.rank > 0
      ? `${payload.rank}D trace`
      : "Axis summary unavailable";
  }

  const axisLabel = axisNames
    .map((axisName, index) => {
      const unit = axisUnits[index];
      return typeof unit === "string" && unit.trim().length > 0
        ? `${axisName} (${unit})`
        : axisName;
    })
    .join(" × ");
  const shapeLabel =
    axisLengths.length === axisNames.length ? ` · ${axisLengths.join(" × ")}` : "";
  return `${axisLabel}${shapeLabel}`;
}

function mapCharacterizationTraceSelectionRow(
  payload: CharacterizationTraceSelectionRowResponse,
): CharacterizationTraceSelectionRow {
  return {
    trace_id: payload.trace_id,
    dataset_id: payload.dataset_id,
    design_id: payload.design_id,
    family: payload.family as CharacterizationTraceSelectionRow["family"],
    parameter: payload.parameter,
    representation: payload.representation,
    trace_mode_group:
      payload.trace_mode_group as CharacterizationTraceSelectionRow["trace_mode_group"],
    source_kind: payload.source_kind as CharacterizationTraceSelectionRow["source_kind"],
    stage_kind: payload.stage_kind as CharacterizationTraceSelectionRow["stage_kind"],
    provenance_summary: payload.provenance_summary,
    allowed_actions: payload.allowed_actions,
    mutation_policy_summary: payload.mutation_policy_summary,
    axesSummary: formatCharacterizationTraceAxesSummary(payload.axes_summary),
    axisSignature: payload.axis_signature ?? "",
    availableSweepAxes: [...(payload.available_sweep_axes ?? [])],
    collectionProjection: mapCharacterizationTraceCollectionProjection(
      payload.collection_projection,
    ),
  };
}

function mapCharacterizationArtifactPayload(
  payload: CharacterizationArtifactPayloadResponse,
): CharacterizationArtifactPayload {
  return {
    artifactId: payload.artifact_id,
    title: payload.title,
    presetId: payload.preset_id,
    viewKind: payload.view_kind,
    axes: payload.axes.map(mapCharacterizationArtifactAxisSpec),
    metric: mapCharacterizationArtifactMetricSpec(payload.metric),
    payload: payload.payload,
    diagnostics: (payload.diagnostics ?? []).map(mapCharacterizationDiagnostic),
  };
}

export async function listCharacterizationTraceSelectionRows(
  datasetId: string,
  designId: string,
): Promise<CharacterizationPagedRows<CharacterizationTraceSelectionRow>> {
  const response = await apiRequestEnvelope<
    { rows: readonly CharacterizationTraceSelectionRowResponse[] },
    CharacterizationCursorMeta
  >(traceListKey(datasetId, designId));
  return {
    rows: response.data.rows.map(mapCharacterizationTraceSelectionRow),
    meta: {
      generatedAt: response.meta?.generated_at ?? "",
      limit: response.meta?.limit ?? response.data.rows.length,
      nextCursor: response.meta?.next_cursor ?? null,
      prevCursor: response.meta?.prev_cursor ?? null,
      hasMore: response.meta?.has_more ?? false,
      filterEcho: response.meta?.filter_echo ?? {},
    },
  };
}

export async function listCharacterizationResults(
  datasetId: string,
  designId: string,
  query?: CharacterizationResultsListQuery,
): Promise<CharacterizationPagedRows<CharacterizationResultSummary>> {
  const params = new URLSearchParams();
  if (query?.search) {
    params.set("search", query.search);
  }
  if (query?.status) {
    params.set("status", query.status);
  }
  if (query?.analysisId) {
    params.set("analysis_id", query.analysisId);
  }

  const search = params.toString();
  const response = await apiRequestEnvelope<
    { rows: readonly CharacterizationResultSummaryResponse[] },
    CharacterizationCursorMeta
  >(
    search
      ? `${characterizationResultsListKey(datasetId, designId)}?${search}`
      : characterizationResultsListKey(datasetId, designId),
  );

  return {
    rows: response.data.rows.map(mapCharacterizationResultSummary),
    meta: {
      generatedAt: response.meta?.generated_at ?? "",
      limit: response.meta?.limit ?? response.data.rows.length,
      nextCursor: response.meta?.next_cursor ?? null,
      prevCursor: response.meta?.prev_cursor ?? null,
      hasMore: response.meta?.has_more ?? false,
      filterEcho: response.meta?.filter_echo ?? {},
    },
  };
}

export async function listCharacterizationAnalysisRegistry(
  datasetId: string,
  designId: string,
  query?: CharacterizationAnalysisRegistryQuery,
): Promise<CharacterizationAnalysisRegistry> {
  const response = await apiRequestEnvelope<CharacterizationAnalysisRegistryResponse, unknown>(
    characterizationAnalysisRegistryKey(datasetId, designId, query?.selectedTraceIds),
  );
  return {
    rows: response.data.rows.map(mapCharacterizationAnalysisRegistryRow),
    inputCollectionPayload: mapCharacterizationInputCollectionPayload(
      response.data.input_collection_payload,
    ),
    dataCollectionReview: mapCharacterizationDataCollectionReview(
      response.data.data_collection_review,
    ),
  };
}

export async function listCharacterizationRunHistory(
  datasetId: string,
  designId: string,
  query?: CharacterizationRunHistoryQuery,
): Promise<CharacterizationPagedRows<CharacterizationRunHistoryRow>> {
  const response = await apiRequestEnvelope<
    { rows: readonly CharacterizationRunHistoryRowResponse[] },
    CharacterizationCursorMeta
  >(characterizationRunHistoryKey(datasetId, designId, query));
  return {
    rows: response.data.rows.map(mapCharacterizationRunHistoryRow),
    meta: {
      generatedAt: response.meta?.generated_at ?? "",
      limit: response.meta?.limit ?? response.data.rows.length,
      nextCursor: response.meta?.next_cursor ?? null,
      prevCursor: response.meta?.prev_cursor ?? null,
      hasMore: response.meta?.has_more ?? false,
      filterEcho: response.meta?.filter_echo ?? {},
    },
  };
}

export async function getCharacterizationResult(
  datasetId: string,
  designId: string,
  resultId: string,
) {
  const response = await apiRequest<CharacterizationResultDetailResponse>(
    characterizationResultDetailKey(datasetId, designId, resultId),
  );
  return mapCharacterizationResultDetail(response);
}

export async function getCharacterizationArtifactPayload(
  datasetId: string,
  designId: string,
  resultId: string,
  artifactId: string,
  options: Readonly<{
    viewMode?: CharacterizationArtifactPayloadViewKind | null;
    presetId?: string | null;
  }>,
) {
  const response = await apiRequest<CharacterizationArtifactPayloadResponse>(
    characterizationArtifactPayloadKey(datasetId, designId, resultId, artifactId, options),
  );
  return mapCharacterizationArtifactPayload(response);
}

export async function applyCharacterizationTagging(
  datasetId: string,
  designId: string,
  resultId: string,
  input: CharacterizationTaggingInput,
) {
  const response = await apiRequest<CharacterizationTaggingResultResponse>(
    characterizationTaggingsKey(datasetId, designId, resultId),
    {
      method: "POST",
      body: JSON.stringify({
        artifact_id: input.artifactId,
        source_parameter: input.sourceParameter,
        designated_metric: input.designatedMetric,
      }),
    },
  );
  return mapCharacterizationTaggingResult(response);
}
