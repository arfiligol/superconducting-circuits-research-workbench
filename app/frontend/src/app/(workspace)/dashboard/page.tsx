import { Suspense } from "react";

import { DashboardWorkspace } from "@/features/data-browser/components/dashboard-workspace";

export default function DashboardPage() {
  return (
    <Suspense
      fallback={
        <div className="rounded-[1rem] border border-border bg-card px-5 py-5 text-sm text-muted-foreground">
          Loading dashboard...
        </div>
      }
    >
      <DashboardWorkspace />
    </Suspense>
  );
}
