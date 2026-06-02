import { Suspense } from "react";

import { RawDataBrowserWorkspace } from "@/features/data-browser/components/raw-data-browser-workspace";

export default function RawDataPage() {
  return (
    <Suspense
      fallback={
        <div className="rounded-[1rem] border border-border bg-card px-5 py-5 text-sm text-muted-foreground">
          Loading raw-data browser...
        </div>
      }
    >
      <RawDataBrowserWorkspace />
    </Suspense>
  );
}
