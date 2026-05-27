"use client";

import { Plus, Trash2 } from "lucide-react";
import type { UseFieldArrayReturn, UseFormReturn } from "react-hook-form";

import { CompactField, SetupSection, SetupTextInput } from "@/features/simulation/components/simulation-workbench-stage-kit";
import {
  FREQUENCY_WHEEL_STEP_GHZ,
  SOURCE_CURRENT_WHEEL_STEP_AMP,
} from "@/features/simulation/components/simulation-setup-stage-config";
import type { SimulationRequestValues } from "@/features/simulation/lib/request-form";
import { AppInlineSelect, type AppSelectOption } from "@/features/shared/components/app-select";
import { AppNumberInput } from "@/features/shared/components/app-number-input";
import { SurfaceTag } from "@/features/shared/components/surface-kit";

export function SimulationSourcesSection({
  form,
  onAddSource,
  ptcPortOptions,
  sourceFieldArray,
  sourcePortSelectOptions,
}: Readonly<{
  form: UseFormReturn<SimulationRequestValues>;
  onAddSource: () => void;
  ptcPortOptions: readonly { value: string; label: string }[];
  sourceFieldArray: UseFieldArrayReturn<SimulationRequestValues, "simulationSources", "id">;
  sourcePortSelectOptions: readonly AppSelectOption[];
}>) {
  return (
    <SetupSection
      title="Sources"
      description="Pump-source inputs for JosephsonCircuits runs."
      status={<SurfaceTag tone="primary">Persisted on task</SurfaceTag>}
      actions={
        <button
          type="button"
          onClick={onAddSource}
          className="inline-flex cursor-pointer items-center gap-2 rounded-full border border-border bg-background px-3 py-2 text-xs font-medium text-foreground transition hover:border-primary/35 hover:bg-primary/10"
        >
          <Plus className="h-3.5 w-3.5" />
          Add Source
        </button>
      }
    >
      {sourceFieldArray.fields.length > 0 ? (
        <div className="space-y-3">
          {sourceFieldArray.fields.map((field, index) => {
            const sourceErrors = form.formState.errors.simulationSources?.[index];
            return (
              <div
                key={field.id}
                className="rounded-[0.95rem] border border-border bg-background px-4 py-4"
              >
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div>
                    <p className="text-sm font-semibold text-foreground">
                      Pump Source {index + 1}
                    </p>
                  </div>
                  <button
                    type="button"
                    onClick={() => {
                      sourceFieldArray.remove(index);
                    }}
                    className="inline-flex cursor-pointer items-center gap-2 rounded-full border border-border bg-surface px-3 py-2 text-xs font-medium text-foreground transition hover:border-rose-300 hover:bg-rose-50 dark:hover:border-rose-400/40 dark:hover:bg-rose-500/10"
                  >
                    <Trash2 className="h-3.5 w-3.5" />
                    Remove Source
                  </button>
                </div>

                <div className="mt-4 grid gap-4 md:grid-cols-2 xl:grid-cols-4">
                  <CompactField
                    label="Pump Freq (GHz)"
                    error={sourceErrors?.pumpFreqGhz?.message}
                  >
                    <AppNumberInput
                      {...form.register(`simulationSources.${index}.pumpFreqGhz`, {
                        valueAsNumber: true,
                      })}
                      min={String(FREQUENCY_WHEEL_STEP_GHZ)}
                      step={String(FREQUENCY_WHEEL_STEP_GHZ)}
                    />
                  </CompactField>
                  <CompactField label="Source Port" error={sourceErrors?.port?.message}>
                    {ptcPortOptions.length > 0 ? (
                      <AppInlineSelect
                        ariaLabel={`Simulation source ${index + 1} port`}
                        value={form.watch(`simulationSources.${index}.port`)}
                        onChange={(nextValue) => {
                          form.setValue(`simulationSources.${index}.port`, nextValue, {
                            shouldDirty: true,
                          });
                        }}
                        options={sourcePortSelectOptions}
                      />
                    ) : (
                      <SetupTextInput
                        {...form.register(`simulationSources.${index}.port`)}
                        placeholder="port_1"
                      />
                    )}
                  </CompactField>
                  <CompactField
                    label="Source Current Ip (A)"
                    error={sourceErrors?.currentAmp?.message}
                  >
                    <AppNumberInput
                      {...form.register(`simulationSources.${index}.currentAmp`, {
                        valueAsNumber: true,
                      })}
                      step={String(SOURCE_CURRENT_WHEEL_STEP_AMP)}
                    />
                  </CompactField>
                  <CompactField label="Source Mode" error={sourceErrors?.sourceMode?.message}>
                    <SetupTextInput
                      {...form.register(`simulationSources.${index}.sourceMode`)}
                      placeholder="1"
                    />
                  </CompactField>
                </div>
              </div>
            );
          })}
        </div>
      ) : (
        <div className="rounded-[0.95rem] border border-dashed border-border bg-background px-4 py-4 text-sm text-muted-foreground">
          No sources are configured for this run yet. Add a source to submit a persisted
          source spec.
        </div>
      )}
    </SetupSection>
  );
}
