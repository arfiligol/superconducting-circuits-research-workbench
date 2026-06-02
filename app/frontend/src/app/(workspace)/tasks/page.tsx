import { Suspense } from "react";

import { TasksWorkspace } from "@/features/tasks/components/tasks-workspace";

export default function TasksPage() {
  return (
    <Suspense
      fallback={
        <div className="rounded-[1rem] border border-border bg-card px-5 py-5 text-sm text-muted-foreground">
          Loading tasks workspace...
        </div>
      }
    >
      <TasksWorkspace />
    </Suspense>
  );
}
