import { apiRequest, apiRequestEnvelope } from "@/lib/api/client";

import type {
  DatasetCatalogRow,
  DatasetCreateDraft,
  DatasetDesignCreateDraft,
  DatasetDesignCreateResult,
  DatasetDesignLifecycleMutationResult,
  DatasetDesignRenameDraft,
  DatasetLifecycleMutationResult,
  DatasetProfile,
  DatasetProfileUpdate,
  DatasetProfileUpdateResult,
  DesignBrowseRow,
  PagedRows,
  RawDataIngestionDraft,
  RawDataIngestionResult,
  TaggedCoreMetricSummary,
  TraceDetail,
  TraceDeleteResult,
  TraceEditDetail,
  TraceMetadataRow,
  TraceUpdateDraft,
  TraceUpdateResult,
} from "@/features/data-browser/lib/contracts";
export {
  buildRawDataBrowseHref,
  parseRawDataBrowseState,
  type RawDataBrowseState,
} from "@/features/data-browser/lib/browse-state";

export const datasetCatalogKey = "/api/backend/datasets";

function datasetCatalogPageKey(cursor?: string | null, limit?: number | null) {
  const params = new URLSearchParams();
  if (cursor) {
    params.set("cursor", cursor);
  }
  if (typeof limit === "number") {
    params.set("limit", String(limit));
  }
  return withQuery(datasetCatalogKey, params);
}

export function datasetProfileKey(datasetId: string) {
  return `/api/backend/datasets/${encodeURIComponent(datasetId)}/profile`;
}

export function datasetArchiveKey(datasetId: string) {
  return `/api/backend/datasets/${encodeURIComponent(datasetId)}/archive`;
}

export function datasetIngestionsKey(datasetId: string) {
  return `/api/backend/datasets/${encodeURIComponent(datasetId)}/ingestions`;
}

export function datasetMetricsKey(datasetId: string) {
  return `/api/backend/datasets/${encodeURIComponent(datasetId)}/metrics-summary`;
}

export function datasetDesignsKey(
  datasetId: string,
  search?: string | null,
  cursor?: string | null,
  limit?: number | null,
) {
  const params = new URLSearchParams();
  if (search) {
    params.set("search", search);
  }
  if (cursor) {
    params.set("cursor", cursor);
  }
  if (typeof limit === "number") {
    params.set("limit", String(limit));
  }
  return withQuery(
    `/api/backend/datasets/${encodeURIComponent(datasetId)}/designs`,
    params,
  );
}

export function traceListKey(
  datasetId: string,
  designId: string,
  options?: Readonly<{
    cursor?: string | null;
    limit?: number | null;
    search?: string | null;
    family?: string | null;
    representation?: string | null;
    sourceKind?: string | null;
    traceModeGroup?: string | null;
  }>,
) {
  const params = new URLSearchParams();
  if (options?.cursor) {
    params.set("cursor", options.cursor);
  }
  if (typeof options?.limit === "number") {
    params.set("limit", String(options.limit));
  }
  if (options?.search) {
    params.set("search", options.search);
  }
  if (options?.family) {
    params.set("family", options.family);
  }
  if (options?.representation) {
    params.set("representation", options.representation);
  }
  if (options?.sourceKind) {
    params.set("source_kind", options.sourceKind);
  }
  if (options?.traceModeGroup) {
    params.set("trace_mode_group", options.traceModeGroup);
  }
  return withQuery(
    `/api/backend/datasets/${encodeURIComponent(datasetId)}/designs/${encodeURIComponent(
      designId,
    )}/traces`,
    params,
  );
}

export function traceDetailKey(datasetId: string, designId: string, traceId: string) {
  return `/api/backend/datasets/${encodeURIComponent(datasetId)}/designs/${encodeURIComponent(
    designId,
  )}/traces/${encodeURIComponent(traceId)}`;
}

export function traceEditDetailKey(datasetId: string, designId: string, traceId: string) {
  return `${traceDetailKey(datasetId, designId, traceId)}/edit`;
}

export function traceBatchDeleteKey(datasetId: string, designId: string) {
  return `/api/backend/datasets/${encodeURIComponent(datasetId)}/designs/${encodeURIComponent(
    designId,
  )}/traces/batch-delete`;
}

export function datasetDesignKey(datasetId: string, designId: string) {
  return `/api/backend/datasets/${encodeURIComponent(datasetId)}/designs/${encodeURIComponent(
    designId,
  )}`;
}

export function datasetDesignMergeKey(datasetId: string, sourceDesignId: string) {
  return `${datasetDesignKey(datasetId, sourceDesignId)}/merge`;
}

export function datasetDesignArchiveKey(datasetId: string, designId: string) {
  return `${datasetDesignKey(datasetId, designId)}/archive`;
}

export async function listDatasetCatalog(): Promise<PagedRows<DatasetCatalogRow>> {
  const rows: DatasetCatalogRow[] = [];
  let cursor: string | null = null;
  let meta: PagedRows<DatasetCatalogRow>["meta"];

  do {
    const response: Readonly<{
      data: { rows: DatasetCatalogRow[] };
      meta: PagedRows<DatasetCatalogRow>["meta"];
    }> = await apiRequestEnvelope<
      { rows: DatasetCatalogRow[] },
      PagedRows<DatasetCatalogRow>["meta"]
    >(datasetCatalogPageKey(cursor, 50));
    rows.push(...response.data.rows);
    meta = response.meta;
    cursor = response.meta?.next_cursor ?? null;
  } while (cursor);

  return {
    rows,
    meta,
  };
}

export async function getDatasetProfile(datasetId: string): Promise<DatasetProfile> {
  return apiRequest<DatasetProfile>(datasetProfileKey(datasetId));
}

export async function createDataset(
  payload: DatasetCreateDraft,
): Promise<DatasetLifecycleMutationResult> {
  return apiRequest<DatasetLifecycleMutationResult>(datasetCatalogKey, {
    method: "POST",
    body: payload,
  });
}

export async function updateDatasetProfile(
  datasetId: string,
  payload: DatasetProfileUpdate,
): Promise<DatasetProfileUpdateResult> {
  return apiRequest<DatasetProfileUpdateResult>(datasetProfileKey(datasetId), {
    method: "PATCH",
    body: payload,
  });
}

export async function listTaggedCoreMetrics(
  datasetId: string,
): Promise<TaggedCoreMetricSummary[]> {
  const response = await apiRequest<{ rows: TaggedCoreMetricSummary[] }>(datasetMetricsKey(datasetId));
  return response.rows;
}

export async function archiveDataset(
  datasetId: string,
): Promise<DatasetLifecycleMutationResult> {
  return apiRequest<DatasetLifecycleMutationResult>(datasetArchiveKey(datasetId), {
    method: "POST",
  });
}

export async function deleteDataset(
  datasetId: string,
): Promise<DatasetLifecycleMutationResult> {
  return apiRequest<DatasetLifecycleMutationResult>(`/api/backend/datasets/${encodeURIComponent(datasetId)}`, {
    method: "DELETE",
  });
}

export async function ingestRawData(
  datasetId: string,
  payload: RawDataIngestionDraft,
): Promise<RawDataIngestionResult> {
  return apiRequest<RawDataIngestionResult>(datasetIngestionsKey(datasetId), {
    method: "POST",
    body: payload,
  });
}

export async function createDatasetDesign(
  datasetId: string,
  payload: DatasetDesignCreateDraft,
): Promise<DatasetDesignCreateResult> {
  const response = await apiRequest<{
    operation: "created";
    design: DesignBrowseRow;
    design_rows?: readonly DesignBrowseRow[];
  }>(datasetDesignsKey(datasetId), {
    method: "POST",
    body: {
      name: payload.name,
    },
  });

  return {
    operation: response.operation,
    design: normalizeDesignBrowseRow(response.design),
    design_rows: (response.design_rows ?? [response.design]).map(normalizeDesignBrowseRow),
  };
}

export async function renameDatasetDesign(
  datasetId: string,
  designId: string,
  payload: DatasetDesignRenameDraft,
): Promise<DatasetDesignLifecycleMutationResult> {
  return normalizeDesignLifecycleMutationResult(
    await apiRequest<DatasetDesignLifecycleMutationResult>(
      datasetDesignKey(datasetId, designId),
      {
        method: "PATCH",
        body: {
          name: payload.name,
        },
      },
    ),
  );
}

export async function mergeDatasetDesign(
  datasetId: string,
  sourceDesignId: string,
  targetDesignId: string,
): Promise<DatasetDesignLifecycleMutationResult> {
  return normalizeDesignLifecycleMutationResult(
    await apiRequest<DatasetDesignLifecycleMutationResult>(
      datasetDesignMergeKey(datasetId, sourceDesignId),
      {
        method: "POST",
        body: {
          target_design_id: targetDesignId,
        },
      },
    ),
  );
}

export async function archiveDatasetDesign(
  datasetId: string,
  designId: string,
): Promise<DatasetDesignLifecycleMutationResult> {
  return normalizeDesignLifecycleMutationResult(
    await apiRequest<DatasetDesignLifecycleMutationResult>(
      datasetDesignArchiveKey(datasetId, designId),
      {
        method: "POST",
      },
    ),
  );
}

export async function deleteDatasetDesign(
  datasetId: string,
  designId: string,
): Promise<DatasetDesignLifecycleMutationResult> {
  return normalizeDesignLifecycleMutationResult(
    await apiRequest<DatasetDesignLifecycleMutationResult>(
      datasetDesignKey(datasetId, designId),
      {
        method: "DELETE",
      },
    ),
  );
}

export async function listDesignBrowseRows(
  datasetId: string,
  options?: Readonly<{
    search?: string | null;
    cursor?: string | null;
    limit?: number | null;
  }>,
): Promise<PagedRows<DesignBrowseRow>> {
  const response = await apiRequestEnvelope<
    { rows: DesignBrowseRow[] },
    PagedRows<DesignBrowseRow>["meta"]
  >(
    datasetDesignsKey(datasetId, options?.search, options?.cursor, options?.limit),
  );
  return {
    rows: response.data.rows.map(normalizeDesignBrowseRow),
    meta: response.meta,
  };
}

export async function listTraceMetadata(
  datasetId: string,
  designId: string,
  options?: Readonly<{
    cursor?: string | null;
    limit?: number | null;
    search?: string | null;
    family?: string | null;
    representation?: string | null;
    sourceKind?: string | null;
    traceModeGroup?: string | null;
  }>,
): Promise<PagedRows<TraceMetadataRow>> {
  const response = await apiRequestEnvelope<
    { rows: TraceMetadataRow[] },
    PagedRows<TraceMetadataRow>["meta"]
  >(
    traceListKey(datasetId, designId, options),
  );
  return {
    rows: response.data.rows,
    meta: response.meta,
  };
}

export async function getTraceDetail(
  datasetId: string,
  designId: string,
  traceId: string,
): Promise<TraceDetail> {
  return apiRequest<TraceDetail>(traceDetailKey(datasetId, designId, traceId));
}

export async function getTraceEditDetail(
  datasetId: string,
  designId: string,
  traceId: string,
): Promise<TraceEditDetail> {
  return apiRequest<TraceEditDetail>(traceEditDetailKey(datasetId, designId, traceId));
}

export async function updateTrace(
  datasetId: string,
  designId: string,
  traceId: string,
  payload: TraceUpdateDraft,
): Promise<TraceUpdateResult> {
  return apiRequest<TraceUpdateResult>(traceDetailKey(datasetId, designId, traceId), {
    method: "PATCH",
    body: {
      parameter: payload.parameter ?? undefined,
      representation: payload.representation ?? undefined,
      provenance_summary: payload.provenance_summary ?? undefined,
      numeric_payload: payload.numeric_payload ?? undefined,
    },
  });
}

export async function deleteTrace(
  datasetId: string,
  designId: string,
  traceId: string,
): Promise<TraceDeleteResult> {
  const result = await apiRequest<{
    design?: TraceDeleteResult["design"];
    deleted_trace_id?: string;
    deleted_trace_ids?: readonly string[];
  }>(traceDetailKey(datasetId, designId, traceId), {
    method: "DELETE",
  });

  return normalizeTraceDeleteResult(result);
}

export async function batchDeleteTraces(
  datasetId: string,
  designId: string,
  traceIds: readonly string[],
): Promise<TraceDeleteResult> {
  const result = await apiRequest<{
    design?: TraceDeleteResult["design"];
    deleted_trace_ids?: readonly string[];
  }>(traceBatchDeleteKey(datasetId, designId), {
    method: "POST",
    body: {
      trace_ids: [...traceIds],
    },
  });

  return normalizeTraceDeleteResult(result);
}

function withQuery(path: string, params: URLSearchParams) {
  const query = params.toString();
  return query ? `${path}?${query}` : path;
}

function normalizeTraceDeleteResult(result: {
  design?: TraceDeleteResult["design"];
  deleted_trace_id?: string;
  deleted_trace_ids?: readonly string[];
}): TraceDeleteResult {
  return {
    design: result.design ?? null,
    deleted_trace_ids: result.deleted_trace_ids
      ? [...result.deleted_trace_ids]
      : result.deleted_trace_id
        ? [result.deleted_trace_id]
        : [],
  };
}

export function normalizeDesignBrowseRow(row: DesignBrowseRow): DesignBrowseRow {
  return {
    ...row,
    lifecycle_state: row.lifecycle_state ?? "active",
    redirect_design_id: row.redirect_design_id ?? null,
    allowed_actions: {
      rename: row.allowed_actions?.rename ?? false,
      merge: row.allowed_actions?.merge ?? false,
      archive: row.allowed_actions?.archive ?? false,
      delete: row.allowed_actions?.delete ?? false,
    },
    mutation_policy_summary:
      row.mutation_policy_summary ??
      "Lifecycle availability is controlled by the backend for this design scope.",
  };
}

function normalizeDesignLifecycleMutationResult(
  result: DatasetDesignLifecycleMutationResult,
): DatasetDesignLifecycleMutationResult {
  return {
    ...result,
    design: result.design ? normalizeDesignBrowseRow(result.design) : null,
    source_design: result.source_design
      ? normalizeDesignBrowseRow(result.source_design)
      : result.source_design,
    target_design: result.target_design
      ? normalizeDesignBrowseRow(result.target_design)
      : result.target_design,
    design_rows: (result.design_rows ?? []).map(normalizeDesignBrowseRow),
  };
}
