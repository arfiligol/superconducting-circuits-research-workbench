export type DatasetVisibilityScope = "local" | "private" | "workspace";
export type DatasetLifecycleState = "active" | "archived" | "deleted";
export type DatasetStatus = "Ready" | "Queued" | "Review";
export type CompareReadiness = "ready" | "inspect_only" | "blocked";
export type TraceFamily = "s_matrix" | "y_matrix" | "z_matrix";
export type TraceModeGroup = "base" | "sideband" | "all";
export type TraceSourceKind = "circuit_simulation" | "layout_simulation" | "measurement";
export type TraceStageKind = "raw" | "preprocess" | "postprocess";

export type DatasetAllowedActions = Readonly<{
  select: boolean;
  update_profile: boolean;
  publish: boolean;
  archive: boolean;
  delete?: boolean;
  ingest_raw_data?: boolean;
}>;

export type CursorMeta = Readonly<{
  generated_at?: string;
  limit: number;
  next_cursor: string | null;
  prev_cursor: string | null;
  has_more: boolean;
  filter_echo?: Record<string, unknown>;
}>;

export type DatasetCatalogRow = Readonly<{
  dataset_id: string;
  name: string;
  visibility_scope: DatasetVisibilityScope;
  lifecycle_state: DatasetLifecycleState;
  device_type: string;
  updated_at: string;
  allowed_actions: DatasetAllowedActions;
  family: string;
  owner_display_name: string;
}>;

export type DatasetProfile = Readonly<{
  dataset_id: string;
  name: string;
  family: string;
  owner_display_name: string;
  owner_user_id: string;
  workspace_id: string;
  visibility_scope: DatasetVisibilityScope;
  lifecycle_state: DatasetLifecycleState;
  updated_at: string;
  device_type: string;
  capabilities: string[];
  source: string;
  status: DatasetStatus;
  allowed_actions: DatasetAllowedActions;
}>;

export type DatasetProfileUpdate = Readonly<{
  device_type: string;
  capabilities: string[];
  source: string;
}>;

export type DatasetProfileUpdateResult = Readonly<{
  dataset: DatasetProfile;
  updated_fields: Array<"device_type" | "capabilities" | "source">;
}>;

export type DatasetCreateDraft = Readonly<{
  name: string;
  family: string;
  device_type: string;
  source: string;
}>;

export type DatasetLifecycleOperation = "created" | "archived" | "deleted";

export type DatasetLifecycleMutationResult = Readonly<{
  operation: DatasetLifecycleOperation;
  dataset: DatasetProfile;
  catalog_row: DatasetCatalogRow;
  catalog_rows: DatasetCatalogRow[];
}>;

export type TaggedCoreMetricSummary = Readonly<{
  metric_id: string;
  label: string;
  source_parameter: string;
  designated_metric: string;
  tagged_at: string;
}>;

export type DesignBrowseRow = Readonly<{
  design_id: string;
  dataset_id: string;
  name: string;
  source_coverage: Record<string, number>;
  compare_readiness: CompareReadiness;
  trace_count: number;
  updated_at: string;
}>;

export type TraceMetadataRow = Readonly<{
  trace_id: string;
  dataset_id: string;
  design_id: string;
  family: TraceFamily;
  parameter: string;
  representation: string;
  trace_mode_group: TraceModeGroup;
  source_kind: TraceSourceKind;
  stage_kind: TraceStageKind;
  provenance_summary: string;
}>;

export type TraceAxis = Readonly<{
  name: string;
  unit: string;
  length: number;
}>;

export type RawDataIngestionKind = "measurement" | "layout_simulation";

export type RawDataTraceDraft = Readonly<{
  trace_id?: string | null;
  family: TraceFamily;
  parameter: string;
  representation: string;
  trace_mode_group: TraceModeGroup;
  stage_kind: TraceStageKind;
  provenance_summary: string;
  axes: TraceAxis[];
  preview_payload: Record<string, unknown>;
}>;

export type RawDataIngestionDraft = Readonly<{
  kind: RawDataIngestionKind;
  design_name: string;
  design_id?: string | null;
  provenance_label: string;
  traces: RawDataTraceDraft[];
}>;

export type RawDataIngestionResult = Readonly<{
  operation: "materialized";
  dataset: DatasetProfile;
  design: DesignBrowseRow;
  traces: TraceMetadataRow[];
}>;

export type TracePayloadRef = Readonly<{
  contract_version: string;
  backend: string;
  payload_role: string;
  store_key: string;
  store_uri: string;
  group_path: string;
  array_path: string;
  dtype: string;
  shape: number[];
  chunk_shape: number[];
  schema_version: string;
}>;

export type ResultHandleRef = Readonly<{
  contract_version: string;
  handle_id: string;
  kind: string;
  status: string;
  label: string;
  payload_backend: string | null;
  payload_format: string | null;
  payload_role: string | null;
  payload_locator: string | null;
  provenance_task_id: number | null;
  provenance: Readonly<{
    source_dataset_id: string | null;
    source_task_id: number | null;
    trace_batch_record: Record<string, unknown> | null;
    analysis_run_record: Record<string, unknown> | null;
  }>;
}>;

export type TraceDetail = Readonly<{
  trace_id: string;
  dataset_id: string;
  design_id: string;
  axes: TraceAxis[];
  preview_payload: Readonly<{
    kind: string;
    points?: number[][];
  }>;
  payload_ref: TracePayloadRef | null;
  result_handles: ResultHandleRef[];
}>;

export type PagedRows<TRow> = Readonly<{
  rows: TRow[];
  meta: CursorMeta | undefined;
}>;
