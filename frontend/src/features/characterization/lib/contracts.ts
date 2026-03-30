import type { DesignBrowseRow, TraceMetadataRow } from "@/lib/api/datasets";

export type CharacterizationResultStatus = "completed" | "failed" | "blocked";
export type CharacterizationAvailabilityState =
  | "recommended"
  | "available"
  | "unavailable";

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

export type CharacterizationArtifactViewMode = "table" | "plot" | "text" | "json";
export type CharacterizationArtifactManifestViewKind =
  | CharacterizationArtifactViewMode
  | "preset_query";
export type CharacterizationArtifactQueryStyle = "preset_driven" | "static";
export type CharacterizationArtifactQueryField = "view_mode" | "preset_id";

export type CharacterizationArtifactAxisDescriptor = Readonly<{
  key: string;
  label: string;
  unit: string | null;
  family: "input_axis" | "derived_axis" | "metric";
}>;

export type CharacterizationArtifactAxisSummary = Readonly<{
  inputAxes: readonly CharacterizationArtifactAxisDescriptor[];
  derivedAxes: readonly CharacterizationArtifactAxisDescriptor[];
  metrics: readonly CharacterizationArtifactAxisDescriptor[];
}>;

export type CharacterizationArtifactAxisContract = Readonly<{
  rowAxis: string | null;
  columnAxis: string | null;
  xAxis: string | null;
  yAxis: string | null;
  seriesAxis: string | null;
  metric: string | null;
}>;

export type CharacterizationArtifactPresetView = Readonly<{
  presetId: string;
  label: string;
  description: string;
  viewMode: CharacterizationArtifactViewMode;
  isDefault: boolean;
  axisContract: CharacterizationArtifactAxisContract;
}>;

export type CharacterizationArtifactViewModeDefault = Readonly<{
  viewMode: CharacterizationArtifactViewMode;
  presetId: string;
}>;

export type CharacterizationArtifactQuerySpec = Readonly<{
  queryStyle: CharacterizationArtifactQueryStyle;
  supportedQueryFields: readonly CharacterizationArtifactQueryField[];
  supportedViewModes: readonly CharacterizationArtifactViewMode[];
  supportedPresetIds: readonly string[];
  defaultPresetId: string | null;
  defaultPresetsByViewMode: readonly CharacterizationArtifactViewModeDefault[];
}>;

export type CharacterizationArtifactManifestEntry = Readonly<{
  artifactId: string;
  category: string;
  viewKind: CharacterizationArtifactManifestViewKind;
  title: string;
  summary: string;
  payloadFormat: "json" | "markdown" | "svg" | "csv";
  payloadLocator: string | null;
  supportedViewModes: readonly CharacterizationArtifactViewMode[];
  supportedPresetIds: readonly string[];
  defaultPresetId: string | null;
  axisSummary: CharacterizationArtifactAxisSummary;
  presetViews: readonly CharacterizationArtifactPresetView[];
  querySpec: CharacterizationArtifactQuerySpec;
}>;

export type CharacterizationInputCollectionPayload = Readonly<{
  sourceTraceIds: readonly string[];
  availableSweepAxes: readonly string[];
  sharedAxes: readonly CharacterizationArtifactAxisDescriptor[];
  groupingSummary: string;
  readinessState: "ready" | "inspect_only" | "blocked";
  collectionCount: number;
}>;

export type CharacterizationArtifactPayloadColumn = Readonly<{
  key: string;
  label: string;
  role:
    | "row_axis"
    | "column_axis"
    | "x_axis"
    | "y_axis"
    | "series_axis"
    | "metric";
}>;

export type CharacterizationArtifactPayloadSeries = Readonly<{
  seriesId: string;
  label: string;
  values: readonly (number | null)[];
}>;

export type CharacterizationArtifactPayload = Readonly<{
  resultId: string;
  artifactId: string;
  title: string;
  summary: string;
  viewMode: CharacterizationArtifactViewMode;
  presetId: string | null;
  axisContract: CharacterizationArtifactAxisContract;
  presetViews: readonly CharacterizationArtifactPresetView[];
  warnings: readonly string[];
  table:
    | Readonly<{
        columns: readonly CharacterizationArtifactPayloadColumn[];
        rows: readonly Readonly<Record<string, string | number | null>>[];
      }>
    | null;
  plot:
    | Readonly<{
        xAxis: Readonly<{
          key: string;
          label: string;
          values: readonly (string | number)[];
        }>;
        yAxis: Readonly<{
          key: string;
          label: string;
        }>;
        series: readonly CharacterizationArtifactPayloadSeries[];
      }>
    | null;
  textPayload: string | null;
  jsonPayload: Readonly<Record<string, unknown>> | readonly unknown[] | null;
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
  inputCollectionPayload: CharacterizationInputCollectionPayload | null;
  payload: Readonly<Record<string, unknown>>;
  diagnostics: readonly CharacterizationDiagnostic[];
  artifactManifest: readonly CharacterizationArtifactManifestEntry[];
  identifySurface: CharacterizationIdentifySurface;
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

export type CharacterizationAnalysisRegistryRow = Readonly<{
  analysisId: string;
  label: string;
  availabilityState: CharacterizationAvailabilityState;
  requiredConfigFields: readonly string[];
  traceCompatibility: CharacterizationAnalysisTraceCompatibility;
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
