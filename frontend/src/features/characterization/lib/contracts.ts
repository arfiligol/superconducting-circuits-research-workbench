import type { DesignBrowseRow, TraceMetadataRow } from "@/lib/api/datasets";

export type CharacterizationResultStatus = "completed" | "failed" | "blocked";
export type CharacterizationAvailabilityState =
  | "recommended"
  | "available"
  | "unavailable";
export type CharacterizationPrerequisiteState =
  | "ready"
  | "blocked"
  | "requires_upstream_result";
export type CharacterizationCollectionReadinessState =
  | "ready"
  | "inspect_only"
  | "blocked";

export type CharacterizationAnalysisTraceCompatibility = Readonly<{
  matchedTraceCount: number;
  selectedTraceCount: number;
  recommendedTraceModes: readonly string[];
  summary: string;
}>;

export type CharacterizationTraceCollectionProjection = Readonly<{
  collectionId: string | null;
  label: string;
  summary: string;
  traceCount: number;
}>;

export type CharacterizationTraceSelectionRow = TraceMetadataRow &
  Readonly<{
    axesSummary: string;
    axisSignature: string;
    availableSweepAxes: readonly string[];
    collectionProjection: CharacterizationTraceCollectionProjection | null;
  }>;

export type CharacterizationInputCollectionAxis = Readonly<{
  name: string;
  unit: string | null;
  length: number;
  values: readonly number[];
}>;

export type CharacterizationInputCollectionTraceSummary = Readonly<{
  traceId: string;
  family: string;
  parameter: string;
  representation: string;
  axisSignature: string;
  collectionKey: string | null;
}>;

export type CharacterizationInputCollectionPayload = Readonly<{
  selectedTraceIds: readonly string[];
  traceCount: number;
  axisSignature: string | null;
  availableSweepAxes: readonly string[];
  sharedAxes: readonly CharacterizationInputCollectionAxis[];
  groupingSummary: string;
  collectionProjection: CharacterizationTraceCollectionProjection | null;
  traces: readonly CharacterizationInputCollectionTraceSummary[];
}>;

export type CharacterizationInputResultRef = Readonly<{
  analysisId: string;
  resultId: string;
  runId: string | null;
  artifactId: string | null;
  contractVersion: string | null;
  title: string | null;
}>;

export type CharacterizationUpstreamResultRequirement = Readonly<{
  requiredUpstreamAnalysisIds: readonly string[];
  satisfiedResultRefs: readonly CharacterizationInputResultRef[];
  summary: string;
}>;

export type CharacterizationReviewAnalysisSummary = Readonly<{
  analysisId: string;
  label: string;
  availabilityState: CharacterizationAvailabilityState;
  prerequisiteState: CharacterizationPrerequisiteState;
  summary: string;
}>;

export type CharacterizationCollectionMemberSummary = Readonly<{
  memberKey: string;
  traceId: string;
  label: string;
  sourceKind: string;
  stageKind: string;
  traceModeGroup: string;
  family: string;
  parameter: string;
  representation: string;
  provenanceSummary: string;
  axisSignature: string;
  collectionKey: string | null;
}>;

export type CharacterizationDataCollectionReview = Readonly<{
  selectedTraceIds: readonly string[];
  selectionSummary: string;
  sharedAxes: readonly CharacterizationInputCollectionAxis[];
  availableSweepAxes: readonly string[];
  collectionMembers: readonly CharacterizationCollectionMemberSummary[];
  sourceCoverage: Readonly<Record<string, number>>;
  groupingSummary: string;
  readinessState: CharacterizationCollectionReadinessState;
  runnableAnalyses: readonly CharacterizationReviewAnalysisSummary[];
  blockedAnalyses: readonly CharacterizationReviewAnalysisSummary[];
  collectionProjection: CharacterizationTraceCollectionProjection | null;
}>;

export type CharacterizationAnalysisRegistryRow = Readonly<{
  analysisId: string;
  label: string;
  availabilityState: CharacterizationAvailabilityState;
  requiredConfigFields: readonly string[];
  traceCompatibility: CharacterizationAnalysisTraceCompatibility;
  prerequisiteState: CharacterizationPrerequisiteState;
  upstreamResultRequirement: CharacterizationUpstreamResultRequirement | null;
  downstreamUnlockAnalysisIds: readonly string[];
}>;

export type CharacterizationAnalysisRegistry = Readonly<{
  rows: readonly CharacterizationAnalysisRegistryRow[];
  inputCollectionPayload: CharacterizationInputCollectionPayload | null;
  dataCollectionReview: CharacterizationDataCollectionReview | null;
}>;

export type CharacterizationResultSummary = Readonly<{
  resultId: string;
  datasetId: string;
  designId: string;
  analysisId: string;
  title: string;
  status: CharacterizationResultStatus;
  freshnessSummary: string;
  provenanceSummary: string;
  traceCount: number;
  artifactCount: number;
  updatedAt: string;
}>;

export type CharacterizationDiagnostic = Readonly<{
  severity: "error" | "warning" | "info";
  code: string;
  message: string;
  blocking: boolean;
}>;

export type CharacterizationArtifactPayloadViewKind =
  | "table"
  | "plot"
  | "text"
  | "json";
export type CharacterizationArtifactManifestViewKind =
  | CharacterizationArtifactPayloadViewKind
  | "preset_query";
export type CharacterizationArtifactQueryStyle = "preset_driven" | "static";
export type CharacterizationArtifactQueryField = "view_mode" | "preset_id";
export type CharacterizationArtifactAxisRole = "input" | "derived" | "member";

export type CharacterizationArtifactAxisSpec = Readonly<{
  axisKey: string;
  label: string;
  role: CharacterizationArtifactAxisRole;
  unit: string | null;
  length: number;
}>;

export type CharacterizationArtifactMetricSpec = Readonly<{
  metricKey: string;
  label: string;
  unit: string | null;
}>;

export type CharacterizationArtifactPreset = Readonly<{
  presetId: string;
  label: string;
  viewKind: "table" | "plot";
  rowsAxis: string | null;
  columnsAxis: string | null;
  cellMetric: string | null;
  xAxis: string | null;
  yMetric: string | null;
  seriesAxis: string | null;
  compareAxis: string | null;
}>;

export type CharacterizationArtifactViewModeDefault = Readonly<{
  viewMode: CharacterizationArtifactPayloadViewKind;
  presetId: string;
}>;

export type CharacterizationArtifactQuerySpec = Readonly<{
  queryStyle: CharacterizationArtifactQueryStyle;
  supportedQueryFields: readonly CharacterizationArtifactQueryField[];
  supportedViewModes: readonly CharacterizationArtifactPayloadViewKind[];
  supportedPresetIds: readonly string[];
  defaultPresetId: string | null;
  defaultPresetsByViewMode: readonly CharacterizationArtifactViewModeDefault[];
}>;

export type CharacterizationArtifactRef = Readonly<{
  artifactId: string;
  category: string;
  viewKind: CharacterizationArtifactManifestViewKind;
  title: string;
  payloadFormat: "json" | "markdown" | "svg" | "csv";
  payloadLocator: string | null;
  axes: readonly CharacterizationArtifactAxisSpec[];
  metric: CharacterizationArtifactMetricSpec | null;
  presets: readonly CharacterizationArtifactPreset[];
  defaultPresetId: string | null;
  querySpec: CharacterizationArtifactQuerySpec | null;
  identifySource: boolean;
}>;

export type CharacterizationArtifactMemberRef = Readonly<{
  memberKey: string;
  label: string;
  traceId: string;
  sourceKind: string;
  traceModeGroup: string;
  parameter: string;
  representation: string;
  provenanceSummary: string;
}>;

export type CharacterizationArtifactTableAxisValue = Readonly<{
  axisValue: string | number;
  label: string;
  unit: string | null;
}>;

export type CharacterizationArtifactPlotSeries = Readonly<{
  seriesKey: string;
  seriesLabel: string;
  seriesValue: string | number | null;
  xValues: readonly (string | number)[];
  yValues: readonly (number | null)[];
  mask: readonly boolean[];
  compareKey: string | null;
  compareLabel: string | null;
  member: CharacterizationArtifactMemberRef | null;
}>;

export type CharacterizationArtifactCompareGroup = Readonly<{
  compareKey: string;
  compareLabel: string;
  member: CharacterizationArtifactMemberRef | null;
  cells: readonly (readonly (number | null)[])[];
  mask: readonly (readonly boolean[])[];
  series: readonly CharacterizationArtifactPlotSeries[];
}>;

export type CharacterizationArtifactPayloadLayout = Readonly<{
  rowsAxis: string | null;
  columnsAxis: string | null;
  cellMetric: string | null;
  xAxis: string | null;
  yMetric: string | null;
  seriesAxis: string | null;
  compareAxis: string | null;
}>;

export type CharacterizationArtifactPayload = Readonly<{
  artifactId: string;
  title: string;
  presetId: string;
  viewKind: CharacterizationArtifactPayloadViewKind;
  axes: readonly CharacterizationArtifactAxisSpec[];
  metric: CharacterizationArtifactMetricSpec | null;
  payload: Readonly<Record<string, unknown>>;
  diagnostics: readonly CharacterizationDiagnostic[];
}>;

export type CharacterizationSourceParameterOption = Readonly<{
  artifactId: string;
  sourceParameter: string;
  label: string;
  artifactTitle: string;
  currentDesignatedMetric: string | null;
}>;

export type CharacterizationDesignatedMetricOption = Readonly<{
  metricKey: string;
  label: string;
}>;

export type CharacterizationAppliedTag = Readonly<{
  artifactId: string;
  sourceParameter: string;
  designatedMetric: string;
  designatedMetricLabel: string;
  taggedAt: string;
}>;

export type CharacterizationIdentifySurface = Readonly<{
  sourceParameters: readonly CharacterizationSourceParameterOption[];
  designatedMetrics: readonly CharacterizationDesignatedMetricOption[];
  appliedTags: readonly CharacterizationAppliedTag[];
}>;

export type CharacterizationResultDetail = Readonly<{
  resultId: string;
  datasetId: string;
  designId: string;
  analysisId: string;
  title: string;
  status: CharacterizationResultStatus;
  freshnessSummary: string;
  provenanceSummary: string;
  traceCount: number;
  updatedAt: string;
  inputTraceIds: readonly string[];
  inputResultRefs: readonly CharacterizationInputResultRef[];
  payload: Readonly<Record<string, unknown>>;
  diagnostics: readonly CharacterizationDiagnostic[];
  artifactRefs: readonly CharacterizationArtifactRef[];
  identifySurface: CharacterizationIdentifySurface;
  downstreamUnlockAnalysisIds: readonly string[];
}>;

export type CharacterizationTaggingInput = Readonly<{
  artifactId: string;
  sourceParameter: string;
  designatedMetric: string;
}>;

export type CharacterizationTaggingResult = Readonly<{
  taggingStatus: "applied" | "already_applied";
  datasetId: string;
  designId: string;
  resultId: string;
  artifactId: string;
  sourceParameter: string;
  designatedMetric: string;
  taggedMetric: Readonly<{
    metricId: string;
    label: string;
    sourceParameter: string;
    designatedMetric: string;
    taggedAt: string;
  }>;
}>;

export type CharacterizationRunHistoryRow = Readonly<{
  runId: string;
  datasetId: string;
  designId: string;
  analysisId: string;
  label: string;
  status: CharacterizationResultStatus;
  scope: string;
  traceCount: number;
  sourcesSummary: string;
  provenanceSummary: string;
  updatedAt: string;
  resultId: string | null;
}>;

export type CharacterizationPagedRows<T> = Readonly<{
  rows: readonly T[];
  meta: Readonly<{
    generatedAt: string;
    limit: number;
    nextCursor: string | null;
    prevCursor: string | null;
    hasMore: boolean;
    filterEcho: Readonly<Record<string, unknown>>;
  }>;
}>;

export type CharacterizationDesignBrowseRow = DesignBrowseRow;
