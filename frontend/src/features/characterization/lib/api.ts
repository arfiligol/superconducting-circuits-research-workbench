import { apiRequest, apiRequestEnvelope } from "@/lib/api/client";
import { traceListKey } from "@/lib/api/datasets";

import type {
  CharacterizationAnalysisRegistryRow,
  CharacterizationArtifactAxisContract,
  CharacterizationArtifactAxisDescriptor,
  CharacterizationArtifactAxisSummary,
  CharacterizationArtifactManifestEntry,
  CharacterizationArtifactManifestViewKind,
  CharacterizationArtifactPayload,
  CharacterizationArtifactPayloadColumn,
  CharacterizationArtifactPayloadSeries,
  CharacterizationArtifactPresetView,
  CharacterizationArtifactQueryField,
  CharacterizationArtifactQuerySpec,
  CharacterizationArtifactQueryStyle,
  CharacterizationArtifactViewMode,
  CharacterizationArtifactViewModeDefault,
  CharacterizationAppliedTag,
  CharacterizationAvailabilityState,
  CharacterizationDesignatedMetricOption,
  CharacterizationDiagnostic,
  CharacterizationIdentifySurface,
  CharacterizationInputCollectionPayload,
  CharacterizationPagedRows,
  CharacterizationResultDetail,
  CharacterizationResultStatus,
  CharacterizationResultSummary,
  CharacterizationRunHistoryRow,
  CharacterizationSourceParameterOption,
  CharacterizationTaggingInput,
  CharacterizationTaggingResult,
  CharacterizationTraceCollectionProjection,
  CharacterizationTraceSelectionRow,
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

type CharacterizationArtifactAxisDescriptorResponse = Readonly<{
  key: string;
  label: string;
  unit: string | null;
  family: CharacterizationArtifactAxisDescriptor["family"];
}>;

type CharacterizationArtifactAxisSummaryResponse = Readonly<{
  input_axes: readonly CharacterizationArtifactAxisDescriptorResponse[];
  derived_axes: readonly CharacterizationArtifactAxisDescriptorResponse[];
  metrics: readonly CharacterizationArtifactAxisDescriptorResponse[];
}>;

type CharacterizationArtifactAxisContractResponse = Readonly<{
  row_axis: string | null;
  column_axis: string | null;
  x_axis: string | null;
  y_axis: string | null;
  series_axis: string | null;
  metric: string | null;
}>;

type CharacterizationArtifactPresetViewResponse = Readonly<{
  preset_id: string;
  label: string;
  description: string;
  view_mode: CharacterizationArtifactViewMode;
  is_default: boolean;
  axis_contract: CharacterizationArtifactAxisContractResponse;
}>;

type CharacterizationArtifactQuerySpecResponse = Readonly<{
  query_style: CharacterizationArtifactQueryStyle;
  supported_query_fields: readonly CharacterizationArtifactQueryField[];
  supported_view_modes: readonly CharacterizationArtifactViewMode[];
  supported_preset_ids: readonly string[];
  default_preset_id: string | null;
  default_presets_by_view_mode: readonly Readonly<{
    view_mode: CharacterizationArtifactViewMode;
    preset_id: string;
  }>[];
}>;

type CharacterizationArtifactManifestEntryResponse = Readonly<{
  artifact_id: string;
  category: string;
  view_kind: CharacterizationArtifactManifestViewKind;
  title: string;
  summary: string;
  payload_format: "json" | "markdown" | "svg" | "csv";
  payload_locator: string | null;
  supported_view_modes: readonly CharacterizationArtifactViewMode[];
  supported_preset_ids: readonly string[];
  default_preset_id: string | null;
  axis_summary: CharacterizationArtifactAxisSummaryResponse;
  preset_views: readonly CharacterizationArtifactPresetViewResponse[];
  query_spec: CharacterizationArtifactQuerySpecResponse;
}>;

type CharacterizationInputCollectionPayloadResponse = Readonly<{
  source_trace_ids: readonly string[];
  available_sweep_axes: readonly string[];
  shared_axes: readonly CharacterizationArtifactAxisDescriptorResponse[];
  grouping_summary: string;
  readiness_state: CharacterizationInputCollectionPayload["readinessState"];
  collection_count: number;
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
  input_collection_payload: CharacterizationInputCollectionPayloadResponse | null;
  payload: Readonly<Record<string, unknown>>;
  diagnostics: readonly CharacterizationDiagnosticResponse[];
  artifact_manifest: readonly CharacterizationArtifactManifestEntryResponse[];
  identify_surface: Readonly<{
    source_parameters: readonly CharacterizationSourceParameterResponse[];
    designated_metrics: readonly CharacterizationDesignatedMetricOptionResponse[];
    applied_tags: readonly CharacterizationAppliedTagResponse[];
  }>;
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
  collection_projection?:
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
      }>
    | null;
}>;

type CharacterizationArtifactPayloadColumnResponse = Readonly<{
  key: string;
  label: string;
  role: CharacterizationArtifactPayloadColumn["role"];
}>;

type CharacterizationArtifactPayloadSeriesResponse = Readonly<{
  series_id: string;
  label: string;
  values: readonly (number | null)[];
}>;

type CharacterizationArtifactPayloadResponse = Readonly<{
  result_id?: string | null;
  run_id?: string | null;
  artifact_id: string;
  title: string;
  summary: string;
  view_mode: CharacterizationArtifactViewMode;
  preset_id: string | null;
  axis_contract: CharacterizationArtifactAxisContractResponse;
  preset_views: readonly CharacterizationArtifactPresetViewResponse[];
  warnings?: readonly string[] | null;
  columns?: readonly CharacterizationArtifactPayloadColumnResponse[] | null;
  rows?: readonly Readonly<Record<string, string | number | null>>[] | null;
  plot?:
    | Readonly<{
        x_axis: Readonly<{
          key: string;
          label: string;
          values: readonly (string | number)[];
        }>;
        y_axis: Readonly<{
          key: string;
          label: string;
        }>;
        series: readonly CharacterizationArtifactPayloadSeriesResponse[];
      }>
    | null;
  text_payload?: string | null;
  json_payload?: Readonly<Record<string, unknown>> | readonly unknown[] | null;
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
    viewMode: CharacterizationArtifactViewMode;
    presetId?: string | null;
  }>,
) {
  const params = new URLSearchParams();
  params.set("view_mode", options.viewMode);
  if (options.presetId) {
    params.set("preset_id", options.presetId);
  }
  return `${characterizationResultDetailKey(
    datasetId,
    designId,
    resultId,
  )}/artifacts/${encodeURIComponent(artifactId)}/payload?${params.toString()}`;
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

function mapCharacterizationArtifactAxisDescriptor(
  payload: CharacterizationArtifactAxisDescriptorResponse,
): CharacterizationArtifactAxisDescriptor {
  return {
    key: payload.key,
    label: payload.label,
    unit: payload.unit,
    family: payload.family,
  };
}

function mapCharacterizationArtifactAxisSummary(
  payload: CharacterizationArtifactAxisSummaryResponse,
): CharacterizationArtifactAxisSummary {
  return {
    inputAxes: payload.input_axes.map(mapCharacterizationArtifactAxisDescriptor),
    derivedAxes: payload.derived_axes.map(mapCharacterizationArtifactAxisDescriptor),
    metrics: payload.metrics.map(mapCharacterizationArtifactAxisDescriptor),
  };
}

function mapCharacterizationArtifactAxisContract(
  payload: CharacterizationArtifactAxisContractResponse,
): CharacterizationArtifactAxisContract {
  return {
    rowAxis: payload.row_axis,
    columnAxis: payload.column_axis,
    xAxis: payload.x_axis,
    yAxis: payload.y_axis,
    seriesAxis: payload.series_axis,
    metric: payload.metric,
  };
}

function mapCharacterizationArtifactPresetView(
  payload: CharacterizationArtifactPresetViewResponse,
): CharacterizationArtifactPresetView {
  return {
    presetId: payload.preset_id,
    label: payload.label,
    description: payload.description,
    viewMode: payload.view_mode,
    isDefault: payload.is_default,
    axisContract: mapCharacterizationArtifactAxisContract(payload.axis_contract),
  };
}

function mapCharacterizationArtifactQuerySpec(
  payload: CharacterizationArtifactQuerySpecResponse,
): CharacterizationArtifactQuerySpec {
  return {
    queryStyle: payload.query_style,
    supportedQueryFields: [...payload.supported_query_fields],
    supportedViewModes: [...payload.supported_view_modes],
    supportedPresetIds: [...payload.supported_preset_ids],
    defaultPresetId: payload.default_preset_id,
    defaultPresetsByViewMode: payload.default_presets_by_view_mode.map(
      mapCharacterizationArtifactViewModeDefault,
    ),
  };
}

function mapCharacterizationArtifactViewModeDefault(
  payload: CharacterizationArtifactQuerySpecResponse["default_presets_by_view_mode"][number],
): CharacterizationArtifactViewModeDefault {
  return {
    viewMode: payload.view_mode,
    presetId: payload.preset_id,
  };
}

function mapCharacterizationArtifactManifestEntry(
  payload: CharacterizationArtifactManifestEntryResponse,
): CharacterizationArtifactManifestEntry {
  return {
    artifactId: payload.artifact_id,
    category: payload.category,
    viewKind: payload.view_kind,
    title: payload.title,
    summary: payload.summary,
    payloadFormat: payload.payload_format,
    payloadLocator: payload.payload_locator,
    supportedViewModes: [...payload.supported_view_modes],
    supportedPresetIds: [...payload.supported_preset_ids],
    defaultPresetId: payload.default_preset_id,
    axisSummary: mapCharacterizationArtifactAxisSummary(payload.axis_summary),
    presetViews: payload.preset_views.map(mapCharacterizationArtifactPresetView),
    querySpec: mapCharacterizationArtifactQuerySpec(payload.query_spec),
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

function mapCharacterizationInputCollectionPayload(
  payload: CharacterizationInputCollectionPayloadResponse | null,
): CharacterizationInputCollectionPayload | null {
  if (!payload) {
    return null;
  }

  return {
    sourceTraceIds: [...payload.source_trace_ids],
    availableSweepAxes: [...payload.available_sweep_axes],
    sharedAxes: payload.shared_axes.map(mapCharacterizationArtifactAxisDescriptor),
    groupingSummary: payload.grouping_summary,
    readinessState: payload.readiness_state,
    collectionCount: payload.collection_count,
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
    inputCollectionPayload: mapCharacterizationInputCollectionPayload(
      payload.input_collection_payload,
    ),
    payload: payload.payload,
    diagnostics: payload.diagnostics.map(mapCharacterizationDiagnostic),
    artifactManifest: payload.artifact_manifest.map(mapCharacterizationArtifactManifestEntry),
    identifySurface: mapCharacterizationIdentifySurface(payload.identify_surface),
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

function mapCharacterizationTraceCollectionProjection(
  payload:
    | CharacterizationTraceSelectionRowResponse["collection_projection"]
    | null
    | undefined,
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
    trace_mode_group: payload.trace_mode_group as CharacterizationTraceSelectionRow["trace_mode_group"],
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

function mapCharacterizationArtifactPayloadColumn(
  payload: CharacterizationArtifactPayloadColumnResponse,
): CharacterizationArtifactPayloadColumn {
  return {
    key: payload.key,
    label: payload.label,
    role: payload.role,
  };
}

function mapCharacterizationArtifactPayloadSeries(
  payload: CharacterizationArtifactPayloadSeriesResponse,
): CharacterizationArtifactPayloadSeries {
  return {
    seriesId: payload.series_id,
    label: payload.label,
    values: [...payload.values],
  };
}

function mapCharacterizationArtifactPayload(
  payload: CharacterizationArtifactPayloadResponse,
): CharacterizationArtifactPayload {
  return {
    resultId: payload.result_id ?? payload.run_id ?? "",
    artifactId: payload.artifact_id,
    title: payload.title,
    summary: payload.summary,
    viewMode: payload.view_mode,
    presetId: payload.preset_id,
    axisContract: mapCharacterizationArtifactAxisContract(payload.axis_contract),
    presetViews: payload.preset_views.map(mapCharacterizationArtifactPresetView),
    warnings: [...(payload.warnings ?? [])],
    table:
      payload.columns && payload.rows
        ? {
            columns: payload.columns.map(mapCharacterizationArtifactPayloadColumn),
            rows: [...payload.rows],
          }
        : null,
    plot: payload.plot
      ? {
          xAxis: {
            key: payload.plot.x_axis.key,
            label: payload.plot.x_axis.label,
            values: [...payload.plot.x_axis.values],
          },
          yAxis: {
            key: payload.plot.y_axis.key,
            label: payload.plot.y_axis.label,
          },
          series: payload.plot.series.map(mapCharacterizationArtifactPayloadSeries),
        }
      : null,
    textPayload: payload.text_payload ?? null,
    jsonPayload: payload.json_payload ?? null,
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
): Promise<readonly CharacterizationAnalysisRegistryRow[]> {
  const response = await apiRequestEnvelope<
    { rows: readonly CharacterizationAnalysisRegistryRowResponse[] },
    unknown
  >(characterizationAnalysisRegistryKey(datasetId, designId, query?.selectedTraceIds));
  return response.data.rows.map(mapCharacterizationAnalysisRegistryRow);
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
    viewMode: CharacterizationArtifactViewMode;
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
  payload: CharacterizationTaggingInput,
) {
  const response = await apiRequest<CharacterizationTaggingResultResponse>(
    characterizationTaggingsKey(datasetId, designId, resultId),
    {
      method: "POST",
      body: {
        artifact_id: payload.artifactId,
        source_parameter: payload.sourceParameter,
        designated_metric: payload.designatedMetric,
      },
    },
  );
  return mapCharacterizationTaggingResult(response);
}
