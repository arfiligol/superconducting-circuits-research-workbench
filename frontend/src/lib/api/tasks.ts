import { apiRequest, apiRequestEnvelope } from "@/lib/api/client";

import { components } from "./generated/schema";

type TaskSummaryResponseShape = components["schemas"]["TaskSummaryResponse"];
type TaskAllowedActionsResponse = Readonly<{
  attach: boolean;
  cancel: boolean;
  terminate: boolean;
  retry: boolean;
  rejection_reason?: string | null;
}>;
type SimulationFrequencySweepResponseShape = Readonly<{
  start_ghz: number;
  stop_ghz: number;
  point_count: number;
  spacing: "linear" | "log";
}>;
type SimulationParameterSweepResponseShape = Readonly<{
  parameter: string;
  values: readonly number[];
  unit?: string | null;
}>;
type SimulationHarmonicBalanceResponseShape = Readonly<{
  enabled: boolean;
  harmonic_count?: number | null;
  oversample_factor?: number | null;
}>;
type SimulationSolverSettingsResponseShape = Readonly<{
  solver_family: string;
  max_iterations: number;
  convergence_tolerance: number;
  harmonic_balance?: SimulationHarmonicBalanceResponseShape | null;
}>;
type SimulationSourceSpecResponseShape = Readonly<{
  source_id: string;
  kind: string;
  target: string;
  amplitude: number;
  frequency_ghz?: number | null;
  phase_deg?: number | null;
}>;
type SimulationPtcSetupResponseShape = Readonly<{
  enabled: boolean;
  mode: string;
  compensate_ports: readonly string[];
}>;
type SimulationSetupResponseShape = Readonly<{
  frequency_sweep: SimulationFrequencySweepResponseShape;
  parameter_sweeps: readonly SimulationParameterSweepResponseShape[];
  solver: SimulationSolverSettingsResponseShape;
  sources: readonly SimulationSourceSpecResponseShape[];
  ptc?: SimulationPtcSetupResponseShape | null;
}>;
type DownstreamSourceCapabilityResponseShape = Readonly<{
  available: boolean;
  enabled?: boolean | null;
  mode?: string | null;
  compensate_ports?: readonly string[];
}>;
type DownstreamSourceCapabilitiesResponseShape = Readonly<{
  raw: DownstreamSourceCapabilityResponseShape;
  ptc: DownstreamSourceCapabilityResponseShape;
}>;
type PostProcessingTraceSelectionResponseShape = Readonly<{
  trace_family: string;
  representation: string;
  design_id?: string | null;
  trace_ids: readonly string[];
}>;
type PostProcessingOperationResponseShape = Readonly<{
  operation: string;
  enabled: boolean;
  config: Record<string, unknown>;
}>;
type PostProcessingSetupResponseShape = Readonly<{
  output_view: string;
  selections: readonly PostProcessingTraceSelectionResponseShape[];
  operations: readonly PostProcessingOperationResponseShape[];
}>;
type CharacterizationSetupResponseShape = Readonly<{
  design_id: string;
  analysis_id: string;
  selected_trace_ids: readonly string[];
  analysis_config?: Record<string, unknown> | null;
}>;
type TaskResultHandoffResponseShape = Readonly<{
  availability: TaskResultAvailability;
  primary_result_handle_id: string | null;
  result_handle_count: number;
  trace_payload_available: boolean;
}>;
type TaskPublicationSummaryResponseShape = Readonly<{
  state: "not_published" | "published";
  publish_allowed: boolean;
  publication_key?: string | null;
  target_dataset_id?: string | null;
  target_design_id?: string | null;
  target_design_name?: string | null;
  published_trace_ids?: readonly string[];
  published_at?: string | null;
  source_task_id: number;
  source_result_handle_ids?: readonly string[];
}>;
type TaskDetailResponseShape = components["schemas"]["TaskDetailResponse"] &
  Readonly<{
    simulation_setup?: SimulationSetupResponseShape | null;
    publication_summary?: TaskPublicationSummaryResponseShape | null;
    downstream_source_capabilities?: DownstreamSourceCapabilitiesResponseShape | null;
    post_processing_setup?: PostProcessingSetupResponseShape | null;
    characterization_setup?: CharacterizationSetupResponseShape | null;
    upstream_task_id?: number | null;
    downstream_task_ids?: readonly number[];
    retry_of_task_id?: number | null;
    control_state?: TaskControlState;
    dispatch?: components["schemas"]["TaskDispatchResponse"] | null;
    result_handoff?: TaskResultHandoffResponseShape;
  }>;
type LiveTaskQueueRowResponseShape = Readonly<{
  task_id: number;
  summary: string;
  status: TaskExecutionStatus;
  lane: TaskLane;
  task_kind: TaskKind;
  owner_display_name: string;
  visibility_scope: TaskVisibilityScope;
  updated_at: string;
  result_availability: TaskResultAvailability;
  allowed_actions: TaskAllowedActionsResponse;
  control_state: TaskControlState;
}>;
type WorkerLaneSummaryResponseShape = Readonly<{
  lane: string;
  healthy_processors: number;
  busy_processors: number;
  degraded_processors: number;
  draining_processors: number;
  offline_processors: number;
}>;
type TaskQueueResponseShape = Readonly<{
  rows: readonly LiveTaskQueueRowResponseShape[];
  worker_summary: readonly WorkerLaneSummaryResponseShape[];
}>;
type TaskQueueMetaResponseShape = Readonly<{
  generated_at?: string;
  total_count?: number;
  next_cursor?: string | null;
  prev_cursor?: string | null;
  has_more?: boolean;
}>;
type TaskEventsResponseShape = Readonly<{
  task_id: number;
  events: readonly components["schemas"]["TaskEventResponse"][];
}>;
type TaskEventsMetaResponseShape = Readonly<{
  generated_at?: string;
  limit?: number;
  event_count?: number;
}>;
type SimulationResultExplorerSourceResponseShape = Readonly<{
  key: string;
  label: string;
}>;
type SimulationResultExplorerMetricResponseShape = Readonly<{
  key: string;
  label: string;
  unit: string;
}>;
type SimulationResultExplorerFamilyResponseShape = Readonly<{
  key: string;
  label: string;
  available_sources: readonly SimulationResultExplorerSourceResponseShape[];
  available_metrics: readonly SimulationResultExplorerMetricResponseShape[];
}>;
type SimulationResultExplorerPortResponseShape = Readonly<{
  port: number;
  label: string;
}>;
type SimulationResultExplorerModeResponseShape = Readonly<{
  key: string;
  label: string;
}>;
type SimulationResultExplorerSelectionResponseShape = Readonly<{
  family: string;
  source: string;
  metric: string;
  z0_ohm: number;
  output_port: number;
  input_port: number;
  output_port_label?: string;
  input_port_label?: string;
  output_mode?: string;
  input_mode?: string;
}>;
type SimulationResultExplorerPlotAxisResponseShape = Readonly<{
  label: string;
  unit: string;
  values?: readonly number[];
}>;
type SimulationResultExplorerPlotSeriesResponseShape = Readonly<{
  series_id: string;
  label: string;
  values: readonly number[];
  unit: string;
}>;
type SimulationResultExplorerPlotResponseShape = Readonly<{
  x_axis: SimulationResultExplorerPlotAxisResponseShape;
  y_axis: SimulationResultExplorerPlotAxisResponseShape;
  series: readonly SimulationResultExplorerPlotSeriesResponseShape[];
  metadata: Readonly<{
    family: string;
    source: string;
    metric: string;
    z0_ohm: number;
    output_port: number;
    input_port: number;
    output_port_label?: string;
    input_port_label?: string;
    trace_payload_store_key?: string | null;
  }>;
}>;
type SimulationResultExplorerBootstrapResponseShape = Readonly<{
  families: readonly SimulationResultExplorerFamilyResponseShape[];
  trace_selector: Readonly<{
    output_ports: readonly SimulationResultExplorerPortResponseShape[];
    input_ports: readonly SimulationResultExplorerPortResponseShape[];
    output_modes: readonly SimulationResultExplorerModeResponseShape[];
    input_modes: readonly SimulationResultExplorerModeResponseShape[];
  }>;
  default_selection: SimulationResultExplorerSelectionResponseShape;
}>;
type SimulationResultExplorerResultBasisResponseShape = Readonly<{
  trace_payload_available: boolean;
  primary_result_handle_id: string | null;
  trace_batch_id: number | null;
}>;
type SimulationResultExplorerResponseShape = Readonly<{
  task_id: number;
  task_status: TaskExecutionStatus;
  runtime_mode: "local" | "online";
  bootstrap: SimulationResultExplorerBootstrapResponseShape;
  selection: SimulationResultExplorerSelectionResponseShape;
  plot: SimulationResultExplorerPlotResponseShape;
  result_basis: SimulationResultExplorerResultBasisResponseShape;
}>;
type PublishedSimulationResultDatasetResponseShape = Readonly<{
  dataset_id: string;
  name: string;
  visibility_scope: TaskVisibilityScope;
  lifecycle_state: string;
}>;
type PublishedSimulationResultDesignResponseShape = Readonly<{
  design_id: string;
  dataset_id: string;
  name: string;
  source_coverage: Record<string, number>;
  compare_readiness: string;
  trace_count: number;
  updated_at: string;
}>;
type PublishedSimulationTraceResponseShape = Readonly<{
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
}>;
type SimulationResultPublicationResponseShape = Readonly<{
  operation: "published" | "already_published";
  publication_summary: TaskPublicationSummaryResponseShape;
  task: TaskDetailResponseShape;
  dataset: PublishedSimulationResultDatasetResponseShape;
  design: PublishedSimulationResultDesignResponseShape;
  traces: readonly PublishedSimulationTraceResponseShape[];
}>;

export type TaskKind = "simulation" | "post_processing" | "characterization";
export type TaskLane = "simulation" | "characterization";
export type TaskExecutionMode = "run" | "smoke";
export type TaskExecutionStatus =
  | "queued"
  | "dispatching"
  | "running"
  | "cancellation_requested"
  | "cancelling"
  | "cancelled"
  | "termination_requested"
  | "terminated"
  | "completed"
  | "failed";
export type TaskVisibilityScope = "local" | "private" | "workspace" | "owned";
export type TaskResultAvailability = "pending" | "ready" | "none";
export type TaskControlState = "none" | "cancellation_requested" | "termination_requested";

export type SimulationFrequencySweep = Readonly<{
  startGhz: number;
  stopGhz: number;
  pointCount: number;
  spacing: "linear" | "log";
}>;

export type SimulationParameterSweep = Readonly<{
  parameter: string;
  values: readonly number[];
  unit: string | null;
}>;

export type SimulationHarmonicBalanceSettings = Readonly<{
  enabled: boolean;
  harmonicCount: number | null;
  oversampleFactor: number | null;
}>;

export type SimulationSolverSettings = Readonly<{
  solverFamily: string;
  maxIterations: number;
  convergenceTolerance: number;
  harmonicBalance: SimulationHarmonicBalanceSettings | null;
}>;

export type SimulationSourceSpec = Readonly<{
  sourceId: string;
  kind: string;
  target: string;
  amplitude: number;
  frequencyGhz: number | null;
  phaseDeg: number | null;
}>;
export type SimulationPtcSetup = Readonly<{
  enabled: boolean;
  mode: string;
  compensatePorts: readonly string[];
}>;

export type SimulationSetup = Readonly<{
  frequencySweep: SimulationFrequencySweep;
  parameterSweeps: readonly SimulationParameterSweep[];
  solver: SimulationSolverSettings;
  sources: readonly SimulationSourceSpec[];
  ptc?: SimulationPtcSetup | null;
}>;

export type DownstreamSourceCapability = Readonly<{
  available: boolean;
  enabled: boolean;
  mode: string | null;
  compensatePorts: readonly string[];
}>;

export type DownstreamSourceCapabilities = Readonly<{
  raw: DownstreamSourceCapability;
  ptc: DownstreamSourceCapability;
}>;

export type PostProcessingTraceSelection = Readonly<{
  traceFamily: string;
  representation: string;
  designId: string | null;
  traceIds: readonly string[];
}>;

export type PostProcessingOperation = Readonly<{
  operation: string;
  enabled: boolean;
  config: Record<string, unknown>;
}>;

export type PostProcessingSetup = Readonly<{
  outputView: string;
  selections: readonly PostProcessingTraceSelection[];
  operations: readonly PostProcessingOperation[];
}>;

export type SimulationFrequencySweepDraft = Readonly<{
  start_ghz: number;
  stop_ghz: number;
  point_count: number;
  spacing?: "linear" | "log";
}>;

export type SimulationParameterSweepDraft = Readonly<{
  parameter: string;
  values: readonly number[];
  unit?: string | null;
}>;

export type SimulationHarmonicBalanceSettingsDraft = Readonly<{
  enabled: boolean;
  harmonic_count?: number | null;
  oversample_factor?: number | null;
}>;

export type SimulationSolverSettingsDraft = Readonly<{
  solver_family: string;
  max_iterations: number;
  convergence_tolerance: number;
  harmonic_balance?: SimulationHarmonicBalanceSettingsDraft | null;
}>;

export type SimulationSourceSpecDraft = Readonly<{
  source_id: string;
  kind: string;
  target: string;
  amplitude: number;
  frequency_ghz?: number | null;
  phase_deg?: number | null;
}>;
export type SimulationPtcSetupDraft = Readonly<{
  enabled: boolean;
  mode: string;
  compensate_ports: readonly string[];
}>;

export type SimulationSetupDraft = Readonly<{
  frequency_sweep: SimulationFrequencySweepDraft;
  parameter_sweeps?: readonly SimulationParameterSweepDraft[];
  solver: SimulationSolverSettingsDraft;
  sources: readonly SimulationSourceSpecDraft[];
  ptc?: SimulationPtcSetupDraft | null;
}>;

export type PostProcessingTraceSelectionDraft = Readonly<{
  trace_family: string;
  representation: string;
  design_id?: string | null;
  trace_ids?: readonly string[];
}>;

export type PostProcessingOperationDraft = Readonly<{
  operation: string;
  enabled: boolean;
  config?: Record<string, unknown>;
}>;

export type PostProcessingSetupDraft = Readonly<{
  output_view: string;
  selections: readonly PostProcessingTraceSelectionDraft[];
  operations: readonly PostProcessingOperationDraft[];
}>;

export type CharacterizationAnalysisConfigDraft = Readonly<Record<string, unknown>>;

export type CharacterizationSetupDraft = Readonly<{
  design_id: string;
  analysis_id: string;
  selected_trace_ids: readonly string[];
  analysis_config?: CharacterizationAnalysisConfigDraft | null;
}>;

export type TaskMetadataRecordRef = Readonly<{
  backend: "sqlite_metadata";
  recordType: "dataset" | "trace_batch" | "analysis_run" | "result_handle";
  recordId: string;
  version: number;
  schemaVersion: string;
}>;

export type TaskTracePayloadRef = Readonly<{
  contractVersion: string;
  backend: "local_zarr" | "s3_zarr";
  payloadRole: "dataset_primary" | "task_output" | "analysis_projection";
  storeKey: string;
  storeUri: string;
  groupPath: string;
  arrayPath: string;
  dtype: string;
  shape: readonly number[];
  chunkShape: readonly number[];
  schemaVersion: string;
}>;

export type TaskResultHandleRef = Readonly<{
  contractVersion: string;
  handleId: string;
  kind: "simulation_trace" | "fit_summary" | "characterization_report" | "plot_bundle";
  status: "pending" | "materialized";
  label: string;
  metadataRecord: TaskMetadataRecordRef;
  payloadBackend:
    | "local_zarr"
    | "json_artifact"
    | "markdown_artifact"
    | "bundle_archive"
    | null;
  payloadFormat: "zarr" | "json" | "markdown" | "zip" | null;
  payloadRole: "trace_payload" | "report_artifact" | "bundle_artifact" | null;
  payloadLocator: string | null;
  provenanceTaskId: number | null;
  provenance: Readonly<{
    sourceDatasetId: string | null;
    sourceTaskId: number | null;
    traceBatchRecord: TaskMetadataRecordRef | null;
    analysisRunRecord: TaskMetadataRecordRef | null;
  }>;
}>;

export type TaskDispatch = Readonly<{
  dispatchKey: string;
  status: "accepted" | "running" | "completed" | "failed";
  submissionSource: "active_dataset" | "explicit_dataset" | "definition_only";
  acceptedAt: string;
  lastUpdatedAt: string;
}>;

export type TaskEvent = Readonly<{
  eventKey: string;
  eventType: "task_submitted" | "task_running" | "task_completed" | "task_failed";
  level: "info" | "warning" | "error";
  occurredAt: string;
  message: string;
  metadata: Readonly<Record<string, string | number | boolean | readonly string[] | null>>;
}>;

export type TaskResultHandoff = Readonly<{
  availability: TaskResultAvailability;
  primaryResultHandleId: string | null;
  resultHandleCount: number;
  tracePayloadAvailable: boolean;
}>;
export type TaskPublicationState = "not_published" | "published";
export type TaskPublicationSummary = Readonly<{
  state: TaskPublicationState;
  publishAllowed: boolean;
  publicationKey: string | null;
  targetDatasetId: string | null;
  targetDesignId: string | null;
  targetDesignName: string | null;
  publishedTraceIds: readonly string[];
  publishedAt: string | null;
  sourceTaskId: number;
  sourceResultHandleIds: readonly string[];
}>;

export type TaskAllowedActions = Readonly<{
  attach: boolean;
  cancel: boolean;
  terminate: boolean;
  retry: boolean;
  rejectionReason?: string | null;
}>;

export type TaskSummary = Readonly<{
  taskId: number;
  kind: TaskKind;
  lane: TaskLane;
  executionMode: TaskExecutionMode | null;
  status: TaskExecutionStatus;
  submittedAt: string | null;
  updatedAt?: string | null;
  ownerUserId: string | null;
  ownerDisplayName: string;
  workspaceId: string | null;
  workspaceSlug: string | null;
  visibilityScope: TaskVisibilityScope;
  datasetId: string | null;
  definitionId: number | null;
  summary: string;
  resultAvailability?: TaskResultAvailability | null;
  controlState?: TaskControlState | null;
  hasActionAuthority: boolean;
  allowedActions: TaskAllowedActions;
}>;

export type TaskDetail = TaskSummary &
  Readonly<{
    queueBackend: "in_memory_scaffold";
    workerTaskName:
      | "simulation_run_task"
      | "simulation_smoke_task"
      | "simulation_failure_task"
      | "simulation_crash_task"
      | "post_processing_run_task"
      | "post_processing_smoke_task"
      | "characterization_run_task"
      | "characterization_smoke_task"
      | "characterization_failure_task"
      | "characterization_crash_task";
    requestReady: boolean;
    submittedFromActiveDataset: boolean;
    simulationSetup?: SimulationSetup | null;
    downstreamSourceCapabilities?: DownstreamSourceCapabilities | null;
    postProcessingSetup?: PostProcessingSetup | null;
    characterizationSetup?: CharacterizationSetupDraft | null;
    upstreamTaskId?: number | null;
    downstreamTaskIds?: readonly number[];
    retryOfTaskId?: number | null;
    dispatch: TaskDispatch;
    events: readonly TaskEvent[];
    progress: Readonly<{
      phase: "queued" | "running" | "completed" | "failed";
      percentComplete: number;
      summary: string;
      updatedAt: string;
    }>;
    resultHandoff?: TaskResultHandoff;
    publicationSummary?: TaskPublicationSummary;
    resultRefs: Readonly<{
      traceBatchId: number | null;
      analysisRunId: number | null;
      metadataRecords: readonly TaskMetadataRecordRef[];
      tracePayload: TaskTracePayloadRef | null;
      resultHandles: readonly TaskResultHandleRef[];
    }>;
  }>;

export type TaskSubmissionDraft = Readonly<{
  kind: TaskKind;
  dataset_id?: string | null;
  definition_id?: number | null;
  summary?: string | null;
  simulation_setup?: SimulationSetupDraft | null;
  post_processing_setup?: PostProcessingSetupDraft | null;
  characterization_setup?: CharacterizationSetupDraft | null;
  upstream_task_id?: number | null;
}>;
export type TaskMutationResponse = components["schemas"]["TaskMutationResponse"];
export type TaskSummaryLike = Omit<TaskSummary, "hasActionAuthority" | "allowedActions"> &
  Readonly<
    Partial<
      Pick<TaskSummary, "hasActionAuthority" | "allowedActions">
    >
  >;
export type WorkerLaneSummary = Readonly<{
  lane: string;
  healthyProcessors: number;
  busyProcessors: number;
  degradedProcessors: number;
  drainingProcessors: number;
  offlineProcessors: number;
}>;
export type SimulationResultExplorerSource = Readonly<{
  key: string;
  label: string;
}>;
export type SimulationResultExplorerMetric = Readonly<{
  key: string;
  label: string;
  unit: string;
}>;
export type SimulationResultExplorerFamily = Readonly<{
  key: string;
  label: string;
  availableSources: readonly SimulationResultExplorerSource[];
  availableMetrics: readonly SimulationResultExplorerMetric[];
}>;
export type SimulationResultExplorerPort = Readonly<{
  port: number;
  label: string;
}>;
export type SimulationResultExplorerMode = Readonly<{
  key: string;
  label: string;
}>;
export type SimulationResultExplorerSelection = Readonly<{
  family: string;
  source: string;
  metric: string;
  z0Ohm: number;
  outputPort: number;
  inputPort: number;
  outputPortLabel: string | null;
  inputPortLabel: string | null;
  outputMode: string | null;
  inputMode: string | null;
}>;
export type SimulationResultExplorerPlotAxis = Readonly<{
  label: string;
  unit: string;
  values: readonly number[];
}>;
export type SimulationResultExplorerSeries = Readonly<{
  seriesId: string;
  label: string;
  values: readonly number[];
  unit: string;
}>;
export type SimulationResultExplorerPlot = Readonly<{
  xAxis: SimulationResultExplorerPlotAxis;
  yAxis: SimulationResultExplorerPlotAxis;
  series: readonly SimulationResultExplorerSeries[];
  metadata: Readonly<{
    family: string;
    source: string;
    metric: string;
    z0Ohm: number;
    outputPort: number;
    inputPort: number;
    outputPortLabel: string | null;
    inputPortLabel: string | null;
    tracePayloadStoreKey: string | null;
  }>;
}>;
export type SimulationResultExplorerPayload = Readonly<{
  taskId: number;
  taskStatus: TaskExecutionStatus;
  runtimeMode: "local" | "online";
  bootstrap: Readonly<{
    families: readonly SimulationResultExplorerFamily[];
    traceSelector: Readonly<{
      outputPorts: readonly SimulationResultExplorerPort[];
      inputPorts: readonly SimulationResultExplorerPort[];
      outputModes: readonly SimulationResultExplorerMode[];
      inputModes: readonly SimulationResultExplorerMode[];
    }>;
    defaultSelection: SimulationResultExplorerSelection;
  }>;
  selection: SimulationResultExplorerSelection;
  plot: SimulationResultExplorerPlot;
  resultBasis: Readonly<{
    tracePayloadAvailable: boolean;
    primaryResultHandleId: string | null;
    traceBatchId: number | null;
  }>;
}>;
export type SimulationResultExplorerQuery = Readonly<{
  family?: string;
  source?: string;
  metric?: string;
  z0?: number;
  outputPort?: number;
  inputPort?: number;
}>;
export type SimulationResultPublicationDraft = Readonly<{
  datasetId?: string | null;
  designName?: string | null;
  designId?: string | null;
}>;
export type PublishedSimulationResultDataset = Readonly<{
  datasetId: string;
  name: string;
  visibilityScope: TaskVisibilityScope;
  lifecycleState: string;
}>;
export type PublishedSimulationResultDesign = Readonly<{
  designId: string;
  datasetId: string;
  name: string;
  sourceCoverage: Record<string, number>;
  compareReadiness: string;
  traceCount: number;
  updatedAt: string;
}>;
export type PublishedSimulationTrace = Readonly<{
  traceId: string;
  datasetId: string;
  designId: string;
  family: string;
  parameter: string;
  representation: string;
  traceModeGroup: string;
  sourceKind: string;
  stageKind: string;
  provenanceSummary: string;
}>;
export type SimulationResultPublicationResult = Readonly<{
  operation: "published" | "already_published";
  publicationSummary: TaskPublicationSummary;
  task: TaskDetail;
  dataset: PublishedSimulationResultDataset;
  design: PublishedSimulationResultDesign;
  traces: readonly PublishedSimulationTrace[];
}>;
export type TaskQueueReadModel = Readonly<{
  rows: readonly TaskSummary[];
  workerSummary: readonly WorkerLaneSummary[];
  generatedAt: string | null;
  totalCount: number | null;
  nextCursor: string | null;
  prevCursor: string | null;
  hasMore: boolean;
}>;
export type TaskListQuery = Readonly<{
  scope?: "local" | "workspace" | "owned";
  status?: TaskExecutionStatus;
  lane?: TaskLane;
  datasetId?: string | null;
  searchQuery?: string | null;
  limit?: number;
}>;
export type TaskEventHistoryQuery = Readonly<{
  order?: "asc" | "desc";
  limit?: number;
  eventType?: TaskEvent["eventType"] | null;
}>;
export type TaskEventHistoryReadModel = Readonly<{
  taskId: number;
  events: readonly TaskEvent[];
  generatedAt: string | null;
  eventCount: number;
}>;

export const tasksListKey = "/api/backend/tasks";

const emptyTaskAllowedActions: TaskAllowedActions = {
  attach: false,
  cancel: false,
  terminate: false,
  retry: false,
  rejectionReason: null,
};
const defaultTaskResultHandoff: TaskResultHandoff = {
  availability: "pending",
  primaryResultHandleId: null,
  resultHandleCount: 0,
  tracePayloadAvailable: false,
};
const defaultTaskPublicationSummary = (
  taskId: number,
  sourceResultHandleIds: readonly string[] = [],
): TaskPublicationSummary => ({
  state: "not_published",
  publishAllowed: false,
  publicationKey: null,
  targetDatasetId: null,
  targetDesignId: null,
  targetDesignName: null,
  publishedTraceIds: [],
  publishedAt: null,
  sourceTaskId: taskId,
  sourceResultHandleIds,
});
const defaultDownstreamSourceCapability: DownstreamSourceCapability = {
  available: false,
  enabled: false,
  mode: null,
  compensatePorts: [],
};
const defaultDownstreamSourceCapabilities: DownstreamSourceCapabilities = {
  raw: defaultDownstreamSourceCapability,
  ptc: defaultDownstreamSourceCapability,
};

export function taskDetailKey(taskId: number) {
  return `/api/backend/tasks/${encodeURIComponent(taskId)}`;
}

export function buildTasksListKey(query?: TaskListQuery) {
  if (!query) {
    return tasksListKey;
  }

  const params = new URLSearchParams();
  if (query.scope) {
    params.set("scope", query.scope);
  }
  if (query.status) {
    params.set("status", query.status);
  }
  if (query.lane) {
    params.set("lane", query.lane);
  }
  if (query.datasetId) {
    params.set("dataset_id", query.datasetId);
  }
  if (query.searchQuery) {
    params.set("q", query.searchQuery);
  }
  if (typeof query.limit === "number") {
    params.set("limit", String(query.limit));
  }

  const search = params.toString();
  return search ? `${tasksListKey}?${search}` : tasksListKey;
}

export function taskEventsKey(taskId: number, query?: TaskEventHistoryQuery) {
  const params = new URLSearchParams();

  if (query?.order) {
    params.set("order", query.order);
  }
  if (typeof query?.limit === "number") {
    params.set("limit", String(query.limit));
  }
  if (query?.eventType) {
    params.set("event_type", query.eventType);
  }

  const basePath = `/api/backend/tasks/${encodeURIComponent(taskId)}/events`;
  const search = params.toString();
  return search ? `${basePath}?${search}` : basePath;
}

export function simulationResultExplorerKey(
  taskId: number,
  query?: SimulationResultExplorerQuery,
) {
  const params = new URLSearchParams();

  if (query?.family) {
    params.set("family", query.family);
  }
  if (query?.source) {
    params.set("source", query.source);
  }
  if (query?.metric) {
    params.set("metric", query.metric);
  }
  if (typeof query?.z0 === "number") {
    params.set("z0", String(query.z0));
  }
  if (typeof query?.outputPort === "number") {
    params.set("output_port", String(query.outputPort));
  }
  if (typeof query?.inputPort === "number") {
    params.set("input_port", String(query.inputPort));
  }

  const basePath = `/api/backend/tasks/${encodeURIComponent(taskId)}/simulation-results/explorer`;
  const search = params.toString();
  return search ? `${basePath}?${search}` : basePath;
}

function mapMetadataRecordRef(
  payload: components["schemas"]["MetadataRecordRefResponse"],
): TaskMetadataRecordRef {
  return {
    backend: payload.backend,
    recordType: payload.record_type,
    recordId: payload.record_id,
    version: payload.version,
    schemaVersion: payload.schema_version,
  };
}

function mapTracePayloadRef(
  payload: components["schemas"]["TracePayloadRefResponse"],
): TaskTracePayloadRef {
  return {
    contractVersion: payload.contract_version,
    backend: payload.backend,
    payloadRole: payload.payload_role,
    storeKey: payload.store_key,
    storeUri: payload.store_uri,
    groupPath: payload.group_path,
    arrayPath: payload.array_path,
    dtype: payload.dtype,
    shape: [...payload.shape],
    chunkShape: [...payload.chunk_shape],
    schemaVersion: payload.schema_version,
  };
}

function mapResultHandleRef(
  payload: components["schemas"]["ResultHandleRefResponse"],
): TaskResultHandleRef {
  return {
    contractVersion: payload.contract_version,
    handleId: payload.handle_id,
    kind: payload.kind,
    status: payload.status,
    label: payload.label,
    metadataRecord: mapMetadataRecordRef(payload.metadata_record),
    payloadBackend: payload.payload_backend,
    payloadFormat: payload.payload_format,
    payloadRole: payload.payload_role,
    payloadLocator: payload.payload_locator,
    provenanceTaskId: payload.provenance_task_id,
    provenance: {
      sourceDatasetId: payload.provenance.source_dataset_id,
      sourceTaskId: payload.provenance.source_task_id,
      traceBatchRecord: payload.provenance.trace_batch_record
        ? mapMetadataRecordRef(payload.provenance.trace_batch_record)
        : null,
      analysisRunRecord: payload.provenance.analysis_run_record
        ? mapMetadataRecordRef(payload.provenance.analysis_run_record)
        : null,
    },
  };
}

function mapTaskDispatch(payload: components["schemas"]["TaskDispatchResponse"]): TaskDispatch {
  return {
    dispatchKey: payload.dispatch_key,
    status: payload.status,
    submissionSource: payload.submission_source,
    acceptedAt: payload.accepted_at,
    lastUpdatedAt: payload.last_updated_at,
  };
}

function mapTaskEvent(payload: components["schemas"]["TaskEventResponse"]): TaskEvent {
  function normalizeMetadataValue(
    value: unknown,
  ): string | number | boolean | readonly string[] | null {
    if (value === null || typeof value === "string" || typeof value === "number" || typeof value === "boolean") {
      return value;
    }
    if (Array.isArray(value)) {
      return value.filter((item): item is string => typeof item === "string");
    }
    try {
      return JSON.stringify(value);
    } catch {
      return null;
    }
  }

  return {
    eventKey: payload.event_key,
    eventType: payload.event_type,
    level: payload.level,
    occurredAt: payload.occurred_at,
    message: payload.message,
    metadata: Object.fromEntries(
      Object.entries(payload.metadata).map(([key, value]) => [
        key,
        normalizeMetadataValue(value),
      ]),
    ),
  };
}

function mapSimulationSetupResponse(
  payload: SimulationSetupResponseShape | null | undefined,
): SimulationSetup | null {
  if (!payload) {
    return null;
  }

  return {
    frequencySweep: {
      startGhz: payload.frequency_sweep.start_ghz,
      stopGhz: payload.frequency_sweep.stop_ghz,
      pointCount: payload.frequency_sweep.point_count,
      spacing: payload.frequency_sweep.spacing,
    },
    parameterSweeps: payload.parameter_sweeps.map((sweep) => ({
      parameter: sweep.parameter,
      values: [...sweep.values],
      unit: sweep.unit ?? null,
    })),
    solver: {
      solverFamily: payload.solver.solver_family,
      maxIterations: payload.solver.max_iterations,
      convergenceTolerance: payload.solver.convergence_tolerance,
      harmonicBalance: payload.solver.harmonic_balance
        ? {
            enabled: payload.solver.harmonic_balance.enabled,
            harmonicCount: payload.solver.harmonic_balance.harmonic_count ?? null,
            oversampleFactor: payload.solver.harmonic_balance.oversample_factor ?? null,
          }
        : null,
    },
    sources: payload.sources.map((source) => ({
      sourceId: source.source_id,
      kind: source.kind,
      target: source.target,
      amplitude: source.amplitude,
      frequencyGhz: source.frequency_ghz ?? null,
      phaseDeg: source.phase_deg ?? null,
    })),
    ptc: payload.ptc
      ? {
          enabled: payload.ptc.enabled,
          mode: payload.ptc.mode,
          compensatePorts: [...payload.ptc.compensate_ports],
        }
      : null,
  };
}

function mapDownstreamSourceCapability(
  payload: DownstreamSourceCapabilityResponseShape | null | undefined,
  fallback: DownstreamSourceCapability = defaultDownstreamSourceCapability,
): DownstreamSourceCapability {
  if (!payload) {
    return fallback;
  }

  return {
    available: payload.available,
    enabled: payload.enabled ?? payload.available,
    mode: payload.mode ?? null,
    compensatePorts: [...(payload.compensate_ports ?? [])],
  };
}

function mapDownstreamSourceCapabilities(
  payload: DownstreamSourceCapabilitiesResponseShape | null | undefined,
): DownstreamSourceCapabilities {
  if (!payload) {
    return defaultDownstreamSourceCapabilities;
  }

  return {
    raw: mapDownstreamSourceCapability(payload.raw, defaultDownstreamSourceCapabilities.raw),
    ptc: mapDownstreamSourceCapability(payload.ptc, defaultDownstreamSourceCapabilities.ptc),
  };
}

function mapPostProcessingSetupResponse(
  payload: PostProcessingSetupResponseShape | null | undefined,
): PostProcessingSetup | null {
  if (!payload) {
    return null;
  }

  return {
    outputView: payload.output_view,
    selections: payload.selections.map((selection) => ({
      traceFamily: selection.trace_family,
      representation: selection.representation,
      designId: selection.design_id ?? null,
      traceIds: [...selection.trace_ids],
    })),
    operations: payload.operations.map((operation) => ({
      operation: operation.operation,
      enabled: operation.enabled,
      config: { ...operation.config },
    })),
  };
}

function mapCharacterizationSetupResponse(
  payload: CharacterizationSetupResponseShape | null | undefined,
): CharacterizationSetupDraft | null {
  if (!payload) {
    return null;
  }

  return {
    design_id: payload.design_id,
    analysis_id: payload.analysis_id,
    selected_trace_ids: [...payload.selected_trace_ids],
    analysis_config: payload.analysis_config ?? null,
  };
}

function mapTaskResultHandoff(
  payload: TaskResultHandoffResponseShape | undefined,
): TaskResultHandoff {
  if (!payload) {
    return defaultTaskResultHandoff;
  }

  return {
    availability: payload.availability,
    primaryResultHandleId: payload.primary_result_handle_id,
    resultHandleCount: payload.result_handle_count,
    tracePayloadAvailable: payload.trace_payload_available,
  };
}

function mapTaskPublicationSummary(
  payload: TaskPublicationSummaryResponseShape | null | undefined,
  input: Readonly<{
    taskId: number;
    sourceResultHandleIds?: readonly string[];
  }>,
): TaskPublicationSummary {
  if (!payload) {
    return defaultTaskPublicationSummary(input.taskId, input.sourceResultHandleIds ?? []);
  }

  return {
    state: payload.state,
    publishAllowed: payload.publish_allowed,
    publicationKey: payload.publication_key ?? null,
    targetDatasetId: payload.target_dataset_id ?? null,
    targetDesignId: payload.target_design_id ?? null,
    targetDesignName: payload.target_design_name ?? null,
    publishedTraceIds: [...(payload.published_trace_ids ?? [])],
    publishedAt: payload.published_at ?? null,
    sourceTaskId: payload.source_task_id,
    sourceResultHandleIds: [...(payload.source_result_handle_ids ?? [])],
  };
}

function mapTaskAllowedActions(
  payload: TaskAllowedActionsResponse | undefined,
): Readonly<{
  hasActionAuthority: boolean;
  allowedActions: TaskAllowedActions;
}> {
  if (!payload) {
    return {
      hasActionAuthority: false,
      allowedActions: emptyTaskAllowedActions,
    };
  }

  return {
    hasActionAuthority: true,
    allowedActions: {
      attach: payload.attach,
      cancel: payload.cancel,
      terminate: payload.terminate,
      retry: payload.retry,
      rejectionReason: payload.rejection_reason ?? null,
    },
  };
}

function resolveTaskKind(
  payload: TaskSummaryResponseShape | TaskDetailResponseShape | LiveTaskQueueRowResponseShape,
): TaskKind {
  if ("kind" in payload) {
    return payload.kind;
  }

  return payload.task_kind;
}

function resolveTaskAllowedActionsPayload(
  payload: TaskSummaryResponseShape | TaskDetailResponseShape | LiveTaskQueueRowResponseShape,
) {
  return ("allowed_actions" in payload ? payload.allowed_actions : undefined) as
    | TaskAllowedActionsResponse
    | undefined;
}

export function mapTaskSummaryResponse(
  payload: TaskSummaryResponseShape | TaskDetailResponseShape | LiveTaskQueueRowResponseShape,
): TaskSummary {
  const actionState = mapTaskAllowedActions(
    resolveTaskAllowedActionsPayload(payload),
  );

  return {
    taskId: payload.task_id,
    kind: resolveTaskKind(payload),
    lane: payload.lane,
    executionMode: "execution_mode" in payload ? payload.execution_mode : null,
    status: payload.status,
    submittedAt: "submitted_at" in payload ? payload.submitted_at : null,
    updatedAt: "updated_at" in payload ? payload.updated_at : null,
    ownerUserId: "owner_user_id" in payload ? payload.owner_user_id : null,
    ownerDisplayName: payload.owner_display_name,
    workspaceId: "workspace_id" in payload ? payload.workspace_id : null,
    workspaceSlug: "workspace_slug" in payload ? payload.workspace_slug : null,
    visibilityScope: payload.visibility_scope,
    datasetId: "dataset_id" in payload ? payload.dataset_id : null,
    definitionId: "definition_id" in payload ? payload.definition_id : null,
    summary: payload.summary,
    resultAvailability:
      "result_availability" in payload ? payload.result_availability : null,
    controlState: "control_state" in payload ? payload.control_state : null,
    hasActionAuthority: actionState.hasActionAuthority,
    allowedActions: actionState.allowedActions,
  };
}

export function normalizeTaskSummary(task: TaskSummaryLike): TaskSummary {
  const actionState =
    task.hasActionAuthority && task.allowedActions
      ? {
          hasActionAuthority: true,
          allowedActions: {
            attach: task.allowedActions.attach,
            cancel: task.allowedActions.cancel,
            terminate: task.allowedActions.terminate,
            retry: task.allowedActions.retry,
            rejectionReason: task.allowedActions.rejectionReason ?? null,
          },
        }
      : {
          hasActionAuthority: false,
          allowedActions: emptyTaskAllowedActions,
        };

  return {
    ...task,
    hasActionAuthority: actionState.hasActionAuthority,
    allowedActions: actionState.allowedActions,
  };
}

export function mapWorkerLaneSummaryResponse(
  payload: WorkerLaneSummaryResponseShape,
): WorkerLaneSummary {
  return {
    lane: payload.lane,
    healthyProcessors: payload.healthy_processors,
    busyProcessors: payload.busy_processors,
    degradedProcessors: payload.degraded_processors,
    drainingProcessors: payload.draining_processors,
    offlineProcessors: payload.offline_processors,
  };
}

function mapSimulationResultExplorerSelection(
  payload: SimulationResultExplorerSelectionResponseShape,
): SimulationResultExplorerSelection {
  return {
    family: payload.family,
    source: payload.source,
    metric: payload.metric,
    z0Ohm: payload.z0_ohm,
    outputPort: payload.output_port,
    inputPort: payload.input_port,
    outputPortLabel: normalizeSimulationExplorerPortLabel(
      payload.output_port_label,
      payload.output_port,
    ),
    inputPortLabel: normalizeSimulationExplorerPortLabel(
      payload.input_port_label,
      payload.input_port,
    ),
    outputMode: payload.output_mode ?? null,
    inputMode: payload.input_mode ?? null,
  };
}

function normalizeSimulationExplorerPortLabel(label: string | undefined, port: number) {
  const normalized = label?.trim();
  if (!normalized) {
    return `Port ${port}`;
  }
  return normalized
    .replace(/^port_(\d+)$/i, "Port $1")
    .replace(/^P(\d+)$/i, "Port $1");
}

export function mapSimulationResultExplorerResponse(
  payload: SimulationResultExplorerResponseShape,
): SimulationResultExplorerPayload {
  return {
    taskId: payload.task_id,
    taskStatus: payload.task_status,
    runtimeMode: payload.runtime_mode,
    bootstrap: {
      families: payload.bootstrap.families.map((family) => ({
        key: family.key,
        label: family.label,
        availableSources: family.available_sources.map((source) => ({
          key: source.key,
          label: source.label,
        })),
        availableMetrics: family.available_metrics.map((metric) => ({
          key: metric.key,
          label: metric.label,
          unit: metric.unit,
        })),
      })),
      traceSelector: {
        outputPorts: payload.bootstrap.trace_selector.output_ports.map((port) => ({
          port: port.port,
          label: normalizeSimulationExplorerPortLabel(port.label, port.port),
        })),
        inputPorts: payload.bootstrap.trace_selector.input_ports.map((port) => ({
          port: port.port,
          label: normalizeSimulationExplorerPortLabel(port.label, port.port),
        })),
        outputModes: payload.bootstrap.trace_selector.output_modes.map((mode) => ({
          key: mode.key,
          label: mode.label,
        })),
        inputModes: payload.bootstrap.trace_selector.input_modes.map((mode) => ({
          key: mode.key,
          label: mode.label,
        })),
      },
      defaultSelection: mapSimulationResultExplorerSelection(
        payload.bootstrap.default_selection,
      ),
    },
    selection: mapSimulationResultExplorerSelection(payload.selection),
    plot: {
      xAxis: {
        label: payload.plot.x_axis.label,
        unit: payload.plot.x_axis.unit,
        values: [...(payload.plot.x_axis.values ?? [])],
      },
      yAxis: {
        label: payload.plot.y_axis.label,
        unit: payload.plot.y_axis.unit,
        values: [...(payload.plot.y_axis.values ?? [])],
      },
      series: payload.plot.series.map((series) => ({
        seriesId: series.series_id,
        label: series.label,
        values: [...series.values],
        unit: series.unit,
      })),
      metadata: {
        family: payload.plot.metadata.family,
        source: payload.plot.metadata.source,
        metric: payload.plot.metadata.metric,
        z0Ohm: payload.plot.metadata.z0_ohm,
        outputPort: payload.plot.metadata.output_port,
        inputPort: payload.plot.metadata.input_port,
        outputPortLabel: normalizeSimulationExplorerPortLabel(
          payload.plot.metadata.output_port_label,
          payload.plot.metadata.output_port,
        ),
        inputPortLabel: normalizeSimulationExplorerPortLabel(
          payload.plot.metadata.input_port_label,
          payload.plot.metadata.input_port,
        ),
        tracePayloadStoreKey: payload.plot.metadata.trace_payload_store_key ?? null,
      },
    },
    resultBasis: {
      tracePayloadAvailable: payload.result_basis.trace_payload_available,
      primaryResultHandleId: payload.result_basis.primary_result_handle_id,
      traceBatchId: payload.result_basis.trace_batch_id,
    },
  };
}

export function mapTaskQueueResponse(
  payload: TaskQueueResponseShape,
  meta?: TaskQueueMetaResponseShape,
): TaskQueueReadModel {
  return {
    rows: payload.rows.map(mapTaskSummaryResponse),
    workerSummary: payload.worker_summary.map(mapWorkerLaneSummaryResponse),
    generatedAt: meta?.generated_at ?? null,
    totalCount: meta?.total_count ?? null,
    nextCursor: meta?.next_cursor ?? null,
    prevCursor: meta?.prev_cursor ?? null,
    hasMore: meta?.has_more ?? false,
  };
}

export function mapTaskEventsResponse(
  payload: TaskEventsResponseShape,
  meta?: TaskEventsMetaResponseShape,
): TaskEventHistoryReadModel {
  return {
    taskId: payload.task_id,
    events: payload.events.map(mapTaskEvent),
    generatedAt: meta?.generated_at ?? null,
    eventCount: meta?.event_count ?? payload.events.length,
  };
}

export async function listTasks(query?: TaskListQuery) {
  const response = await apiRequestEnvelope<TaskQueueResponseShape | TaskSummaryResponseShape[]>(
    buildTasksListKey(query),
  );

  if (Array.isArray(response.data)) {
    return {
      rows: response.data.map(mapTaskSummaryResponse),
      workerSummary: [],
      generatedAt: null,
      totalCount: response.data.length,
      nextCursor: null,
      prevCursor: null,
      hasMore: false,
    } satisfies TaskQueueReadModel;
  }

  return mapTaskQueueResponse(response.data, response.meta as TaskQueueMetaResponseShape | undefined);
}

export function mapTaskDetailResponse(payload: TaskDetailResponseShape): TaskDetail {
  const fallbackDispatchStatus: TaskDispatch["status"] =
    payload.status === "completed"
      ? "completed"
      : payload.status === "failed"
        ? "failed"
        : "running";
  const mappedResultRefs = {
    traceBatchId: payload.result_refs.trace_batch_id,
    analysisRunId: payload.result_refs.analysis_run_id,
    metadataRecords: payload.result_refs.metadata_records.map(mapMetadataRecordRef),
    tracePayload: payload.result_refs.trace_payload
      ? mapTracePayloadRef(payload.result_refs.trace_payload)
      : null,
    resultHandles: payload.result_refs.result_handles.map(mapResultHandleRef),
  };

  return {
    ...mapTaskSummaryResponse(payload),
    queueBackend: payload.queue_backend,
    workerTaskName: payload.worker_task_name,
    requestReady: payload.request_ready,
    submittedFromActiveDataset: payload.submitted_from_active_dataset,
    simulationSetup: mapSimulationSetupResponse(payload.simulation_setup),
    downstreamSourceCapabilities: payload.downstream_source_capabilities
      ? mapDownstreamSourceCapabilities(payload.downstream_source_capabilities)
      : null,
    postProcessingSetup: mapPostProcessingSetupResponse(payload.post_processing_setup),
    characterizationSetup: mapCharacterizationSetupResponse(payload.characterization_setup),
    upstreamTaskId: payload.upstream_task_id ?? null,
    downstreamTaskIds: [...(payload.downstream_task_ids ?? [])],
    retryOfTaskId: payload.retry_of_task_id ?? null,
    dispatch: payload.dispatch
      ? mapTaskDispatch(payload.dispatch)
      : {
          dispatchKey: `task:${payload.task_id}`,
          status: fallbackDispatchStatus,
          submissionSource: "definition_only",
          acceptedAt: payload.submitted_at,
          lastUpdatedAt: payload.submitted_at,
        },
    events: payload.events.map(mapTaskEvent),
    progress: {
      phase: payload.progress.phase,
      percentComplete: payload.progress.percent_complete,
      summary: payload.progress.summary,
      updatedAt: payload.progress.updated_at,
    },
    resultHandoff: mapTaskResultHandoff(payload.result_handoff),
    publicationSummary: mapTaskPublicationSummary(payload.publication_summary, {
      taskId: payload.task_id,
      sourceResultHandleIds: mappedResultRefs.resultHandles.map((handle) => handle.handleId),
    }),
    resultRefs: mappedResultRefs,
  };
}

export async function getTask(taskId: number) {
  const response = await apiRequest<TaskDetailResponseShape>(taskDetailKey(taskId));
  return mapTaskDetailResponse(response);
}

export async function getTaskEvents(taskId: number, query?: TaskEventHistoryQuery) {
  const response = await apiRequestEnvelope<TaskEventsResponseShape>(
    taskEventsKey(taskId, query),
  );
  return mapTaskEventsResponse(response.data, response.meta as TaskEventsMetaResponseShape | undefined);
}

export async function getSimulationResultExplorer(
  taskId: number,
  query?: SimulationResultExplorerQuery,
) {
  const response = await apiRequest<SimulationResultExplorerResponseShape>(
    simulationResultExplorerKey(taskId, query),
  );
  return mapSimulationResultExplorerResponse(response);
}

function mapPublishedSimulationResultDataset(
  payload: PublishedSimulationResultDatasetResponseShape,
): PublishedSimulationResultDataset {
  return {
    datasetId: payload.dataset_id,
    name: payload.name,
    visibilityScope: payload.visibility_scope,
    lifecycleState: payload.lifecycle_state,
  };
}

function mapPublishedSimulationResultDesign(
  payload: PublishedSimulationResultDesignResponseShape,
): PublishedSimulationResultDesign {
  return {
    designId: payload.design_id,
    datasetId: payload.dataset_id,
    name: payload.name,
    sourceCoverage: { ...payload.source_coverage },
    compareReadiness: payload.compare_readiness,
    traceCount: payload.trace_count,
    updatedAt: payload.updated_at,
  };
}

function mapPublishedSimulationTrace(
  payload: PublishedSimulationTraceResponseShape,
): PublishedSimulationTrace {
  return {
    traceId: payload.trace_id,
    datasetId: payload.dataset_id,
    designId: payload.design_id,
    family: payload.family,
    parameter: payload.parameter,
    representation: payload.representation,
    traceModeGroup: payload.trace_mode_group,
    sourceKind: payload.source_kind,
    stageKind: payload.stage_kind,
    provenanceSummary: payload.provenance_summary,
  };
}

function mapSimulationResultPublicationResponse(
  payload: SimulationResultPublicationResponseShape,
): SimulationResultPublicationResult {
  return {
    operation: payload.operation,
    publicationSummary: mapTaskPublicationSummary(payload.publication_summary, {
      taskId: payload.task.task_id,
    }),
    task: mapTaskDetailResponse(payload.task),
    dataset: mapPublishedSimulationResultDataset(payload.dataset),
    design: mapPublishedSimulationResultDesign(payload.design),
    traces: payload.traces.map(mapPublishedSimulationTrace),
  };
}

export async function publishSimulationResult(
  taskId: number,
  payload: SimulationResultPublicationDraft,
) {
  const response = await apiRequest<SimulationResultPublicationResponseShape>(
    `/api/backend/tasks/${encodeURIComponent(taskId)}/simulation-results/publish`,
    {
      method: "POST",
      body: {
        dataset_id: payload.datasetId ?? null,
        design_name: payload.designName ?? null,
        design_id: payload.designId ?? null,
      },
    },
  );

  return mapSimulationResultPublicationResponse(response);
}

export function unwrapTaskMutation(response: TaskMutationResponse): TaskDetail {
  return mapTaskDetailResponse(response.task);
}

export async function submitTask(payload: TaskSubmissionDraft) {
  const response = await apiRequest<TaskMutationResponse>(tasksListKey, {
    method: "POST",
    body: payload,
  });

  return unwrapTaskMutation(response);
}

async function mutateTask(
  taskId: number,
  operation: "cancel" | "terminate" | "retry",
) {
  const response = await apiRequest<TaskMutationResponse>(
    `/api/backend/tasks/${encodeURIComponent(taskId)}/${operation}`,
    {
      method: "POST",
    },
  );

  return unwrapTaskMutation(response);
}

export function cancelTask(taskId: number) {
  return mutateTask(taskId, "cancel");
}

export function terminateTask(taskId: number) {
  return mutateTask(taskId, "terminate");
}

export function retryTask(taskId: number) {
  return mutateTask(taskId, "retry");
}
