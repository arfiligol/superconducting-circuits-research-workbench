import { Suspense } from "react";

import { CharacterizationWorkspace } from "@/features/characterization/components/characterization-workspace";

export default function CharacterizationPage() {
  return (
    <Suspense
      fallback={
        <div className="rounded-[1rem] border border-border bg-card px-5 py-5 text-sm text-muted-foreground">
          Loading characterization workspace...
        </div>
      }
    >
      <CharacterizationWorkspace />
    </Suspense>
  );
}
