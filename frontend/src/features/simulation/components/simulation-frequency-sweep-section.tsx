"use client";

import type { UseFormReturn } from "react-hook-form";

import { CompactField, SetupSection } from "@/features/simulation/components/simulation-workbench-stage-kit";
import {
  FREQUENCY_WHEEL_STEP_GHZ,
  spacingSelectOptions,
} from "@/features/simulation/components/simulation-setup-stage-config";
import type { SimulationRequestValues } from "@/features/simulation/lib/request-form";
import { AppInlineSelect } from "@/features/shared/components/app-select";
import { AppNumberInput } from "@/features/shared/components/app-number-input";
import { SurfaceTag } from "@/features/shared/components/surface-kit";

export function SimulationFrequencySweepSection({
  form,
}: Readonly<{
  form: UseFormReturn<SimulationRequestValues>;
}>) {
  return (
    <SetupSection
      title="Signal Frequency Sweep Range"
      description="Set the main sweep window for this run."
      status={<SurfaceTag tone="primary">Persisted on task</SurfaceTag>}
    >
      <div className="rounded-[0.95rem] border border-border bg-background px-4 py-4">
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
          <CompactField
            label="Start Freq (GHz)"
            error={form.formState.errors.simulationStartGhz?.message}
          >
            <AppNumberInput
              {...form.register("simulationStartGhz", { valueAsNumber: true })}
              step={String(FREQUENCY_WHEEL_STEP_GHZ)}
              min={String(FREQUENCY_WHEEL_STEP_GHZ)}
            />
          </CompactField>
          <CompactField
            label="Stop Freq (GHz)"
            error={form.formState.errors.simulationStopGhz?.message}
          >
            <AppNumberInput
              {...form.register("simulationStopGhz", { valueAsNumber: true })}
              step={String(FREQUENCY_WHEEL_STEP_GHZ)}
              min={String(FREQUENCY_WHEEL_STEP_GHZ)}
            />
          </CompactField>
          <CompactField
            label="Points"
            error={form.formState.errors.simulationPointCount?.message}
          >
            <AppNumberInput
              {...form.register("simulationPointCount", { valueAsNumber: true })}
              min={1}
            />
          </CompactField>
          <CompactField label="Spacing">
            <AppInlineSelect
              ariaLabel="Signal sweep spacing"
              value={form.watch("simulationSpacing")}
              onChange={(nextValue) => {
                form.setValue("simulationSpacing", nextValue as "linear" | "log", {
                  shouldDirty: true,
                });
              }}
              options={spacingSelectOptions}
            />
          </CompactField>
        </div>
      </div>
    </SetupSection>
  );
}
