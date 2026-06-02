import { Suspense } from "react";

import { DatasetWorkspace } from "@/features/data-browser/components/dataset-workspace";

export default function DatasetPage() {
  return (
    <Suspense
      fallback={
        <div className="rounded-[1rem] border border-border bg-card px-5 py-5 text-sm text-muted-foreground">
          Loading dataset workspace...
        </div>
      }
    >
      <DatasetWorkspace />
    </Suspense>
  );
}
