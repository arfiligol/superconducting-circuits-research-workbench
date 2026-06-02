import { Suspense } from "react";

import { CircuitDefinitionEditorWorkspace } from "@/features/circuit-definition-editor/components/circuit-definition-editor-workspace";

export default function CircuitDefinitionEditorPage() {
  return (
    <Suspense
      fallback={
        <div className="rounded-[1rem] border border-border bg-card px-5 py-5 text-sm text-muted-foreground">
          Loading circuit definitions...
        </div>
      }
    >
      <CircuitDefinitionEditorWorkspace />
    </Suspense>
  );
}
