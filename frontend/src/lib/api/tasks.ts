import { apiRequest, apiRequestEnvelope } from "@/lib/api/client";

import { components } from "./generated/schema";

type TaskSummaryResponseShape = components["schemas"]["TaskSummaryResponse"];
type TaskDetailResponseShape = components["schemas"]["TaskDetailResponse"];
type TaskAllowedActionsResponse = Readonly<{
  attach: boolean;
  cancel: boolean;
  terminate: boolean;
  retry: boolean;
  rejection_reason?: string | null;
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
    dispatch: TaskDispatch;
    events: readonly TaskEvent[];
    progress: Readonly<{
      phase: "queued" | "running" | "completed" | "failed";
      percentComplete: number;
      summary: string;
      updatedAt: string;
    }>;
    resultRefs: Readonly<{
      traceBatchId: number | null;
      analysisRunId: number | null;
      metadataRecords: readonly TaskMetadataRecordRef[];
      tracePayload: TaskTracePayloadRef | null;
      resultHandles: readonly TaskResultHandleRef[];
    }>;
  }>;

export type TaskSubmissionDraft = components["schemas"]["TaskSubmissionRequest"];
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
export type TaskQueueReadModel = Readonly<{
  rows: readonly TaskSummary[];
  workerSummary: readonly WorkerLaneSummary[];
  generatedAt: string | null;
  totalCount: number | null;
}>;

export const tasksListKey = "/api/backend/tasks";

const emptyTaskAllowedActions: TaskAllowedActions = {
  attach: false,
  cancel: false,
  terminate: false,
  retry: false,
  rejectionReason: null,
};

export function taskDetailKey(taskId: number) {
  return `/api/backend/tasks/${encodeURIComponent(taskId)}`;
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
  return {
    eventKey: payload.event_key,
    eventType: payload.event_type,
    level: payload.level,
    occurredAt: payload.occurred_at,
    message: payload.message,
    metadata: Object.fromEntries(
      Object.entries(payload.metadata).map(([key, value]) => [
        key,
        Array.isArray(value) ? [...value] : value,
      ]),
    ),
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

export function mapTaskQueueResponse(
  payload: TaskQueueResponseShape,
  meta?: TaskQueueMetaResponseShape,
): TaskQueueReadModel {
  return {
    rows: payload.rows.map(mapTaskSummaryResponse),
    workerSummary: payload.worker_summary.map(mapWorkerLaneSummaryResponse),
    generatedAt: meta?.generated_at ?? null,
    totalCount: meta?.total_count ?? null,
  };
}

export async function listTasks() {
  const response = await apiRequestEnvelope<TaskQueueResponseShape | TaskSummaryResponseShape[]>(
    tasksListKey,
  );

  if (Array.isArray(response.data)) {
    return {
      rows: response.data.map(mapTaskSummaryResponse),
      workerSummary: [],
      generatedAt: null,
      totalCount: response.data.length,
    } satisfies TaskQueueReadModel;
  }

  return mapTaskQueueResponse(response.data, response.meta as TaskQueueMetaResponseShape | undefined);
}

export function mapTaskDetailResponse(payload: TaskDetailResponseShape): TaskDetail {
  return {
    ...mapTaskSummaryResponse(payload),
    queueBackend: payload.queue_backend,
    workerTaskName: payload.worker_task_name,
    requestReady: payload.request_ready,
    submittedFromActiveDataset: payload.submitted_from_active_dataset,
    dispatch: mapTaskDispatch(payload.dispatch),
    events: payload.events.map(mapTaskEvent),
    progress: {
      phase: payload.progress.phase,
      percentComplete: payload.progress.percent_complete,
      summary: payload.progress.summary,
      updatedAt: payload.progress.updated_at,
    },
    resultRefs: {
      traceBatchId: payload.result_refs.trace_batch_id,
      analysisRunId: payload.result_refs.analysis_run_id,
      metadataRecords: payload.result_refs.metadata_records.map(mapMetadataRecordRef),
      tracePayload: payload.result_refs.trace_payload
        ? mapTracePayloadRef(payload.result_refs.trace_payload)
        : null,
      resultHandles: payload.result_refs.result_handles.map(mapResultHandleRef),
    },
  };
}

export async function getTask(taskId: number) {
  const response = await apiRequest<TaskDetailResponseShape>(taskDetailKey(taskId));
  return mapTaskDetailResponse(response);
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
