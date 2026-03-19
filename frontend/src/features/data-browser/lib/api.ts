import { apiRequest, apiRequestEnvelope } from "@/lib/api/client";

import type {
  DatasetCatalogRow,
  DatasetCreateDraft,
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
  TraceMetadataRow,
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

export function datasetDesignsKey(datasetId: string, search?: string | null, cursor?: string | null) {
  const params = new URLSearchParams();
  if (search) {
    params.set("search", search);
  }
  if (cursor) {
    params.set("cursor", cursor);
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

export async function listDesignBrowseRows(
  datasetId: string,
  options?: Readonly<{
    search?: string | null;
    cursor?: string | null;
  }>,
): Promise<PagedRows<DesignBrowseRow>> {
  const response = await apiRequestEnvelope<
    { rows: DesignBrowseRow[] },
    PagedRows<DesignBrowseRow>["meta"]
  >(
    datasetDesignsKey(datasetId, options?.search, options?.cursor),
  );
  return {
    rows: response.data.rows,
    meta: response.meta,
  };
}

export async function listTraceMetadata(
  datasetId: string,
  designId: string,
  options?: Readonly<{
    cursor?: string | null;
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

function withQuery(path: string, params: URLSearchParams) {
  const query = params.toString();
  return query ? `${path}?${query}` : path;
}
