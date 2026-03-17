import { Suspense } from "react";

import { DataIngestionWorkspace } from "@/features/data-browser/components/data-ingestion-workspace";

export default function DataIngestionPage() {
  return (
    <Suspense
      fallback={
        <div className="rounded-[1rem] border border-border bg-card px-5 py-5 text-sm text-muted-foreground">
          Loading data-ingestion workspace...
        </div>
      }
    >
      <DataIngestionWorkspace />
    </Suspense>
  );
}
