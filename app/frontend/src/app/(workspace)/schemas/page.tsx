import { Suspense } from "react";

import { CircuitDefinitionCatalogWorkspace } from "@/features/circuit-definition-editor/components/circuit-definition-catalog-workspace";

export default function SchemasPage() {
  return (
    <Suspense
      fallback={
        <div className="rounded-[1rem] border border-border bg-card px-5 py-5 text-sm text-muted-foreground">
          Loading schema catalog...
        </div>
      }
    >
      <CircuitDefinitionCatalogWorkspace />
    </Suspense>
  );
}
