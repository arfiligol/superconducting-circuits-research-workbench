"use client";

import type { UseFormReturn } from "react-hook-form";

import { CompactField, SetupSection } from "@/features/simulation/components/simulation-workbench-stage-kit";
import type { SimulationRequestValues } from "@/features/simulation/lib/request-form";
import { AppNumberInput } from "@/features/shared/components/app-number-input";
import { SurfaceTag } from "@/features/shared/components/surface-kit";

export function SimulationHbSolvingSection({
  form,
  harmonicBalanceEnabled,
}: Readonly<{
  form: UseFormReturn<SimulationRequestValues>;
  harmonicBalanceEnabled: boolean;
}>) {
  return (
    <SetupSection
      title="HB Solving"
      description="JosephsonCircuits harmonic controls only."
      status={<SurfaceTag tone="primary">Persisted on task</SurfaceTag>}
    >
      <div className="rounded-[0.95rem] border border-border bg-background px-4 py-4">
        <div className="grid gap-4 md:grid-cols-2">
          <CompactField
            label="Nmodulation Harmonics"
            error={form.formState.errors.simulationHarmonicCount?.message}
          >
            <AppNumberInput
              {...form.register("simulationHarmonicCount", { valueAsNumber: true })}
              min={1}
              disabled={!harmonicBalanceEnabled}
            />
          </CompactField>
          <CompactField
            label="Npump Harmonics"
            error={form.formState.errors.simulationOversampleFactor?.message}
          >
            <AppNumberInput
              {...form.register("simulationOversampleFactor", { valueAsNumber: true })}
              min={1}
              disabled={!harmonicBalanceEnabled}
            />
          </CompactField>
        </div>
      </div>
    </SetupSection>
  );
}
