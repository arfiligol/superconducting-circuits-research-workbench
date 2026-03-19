import { apiRequest } from "@/lib/api/client";
export {
  archiveDataset,
  createDataset,
  datasetArchiveKey,
  datasetCatalogKey,
  datasetDesignsKey,
  datasetIngestionsKey,
  datasetMetricsKey,
  datasetProfileKey,
  deleteDataset,
  getDatasetProfile,
  ingestRawData,
  getTraceDetail,
  listDatasetCatalog,
  listDesignBrowseRows,
  listTaggedCoreMetrics,
  listTraceMetadata,
  traceDetailKey,
  traceListKey,
  updateDatasetProfile,
} from "@/features/data-browser/lib/api";

export type {
  DatasetCatalogRow,
  DatasetCreateDraft,
  DatasetLifecycleMutationResult,
  DatasetProfile,
  DatasetProfileUpdate,
  DatasetProfileUpdateResult,
  DesignBrowseRow,
  PagedRows,
  RawDataIngestionDraft,
  RawDataIngestionKind,
  RawDataIngestionResult,
  RawDataTraceDraft,
  TaggedCoreMetricSummary,
  TraceDetail,
  TraceMetadataRow,
} from "@/features/data-browser/lib/contracts";

import type { DesignBrowseRow } from "@/features/data-browser/lib/contracts";

export type DatasetDesignCreateDraft = Readonly<{
  name: string;
}>;

export type DatasetDesignCreateResult = Readonly<{
  operation: "created";
  design: DesignBrowseRow;
}>;

export async function createDatasetDesign(
  datasetId: string,
  payload: DatasetDesignCreateDraft,
): Promise<DatasetDesignCreateResult> {
  return apiRequest<DatasetDesignCreateResult>(
    `/api/backend/datasets/${encodeURIComponent(datasetId)}/designs`,
    {
      method: "POST",
      body: {
        name: payload.name,
      },
    },
  );
}
