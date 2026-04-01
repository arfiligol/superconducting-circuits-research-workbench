"use client";

import { Plus, Trash2 } from "lucide-react";
import type { UseFieldArrayReturn, UseFormReturn } from "react-hook-form";

import { CompactField, SetupSection, SetupSlideToggle, SetupTextInput } from "@/features/simulation/components/simulation-workbench-stage-kit";
import {
  FREQUENCY_WHEEL_STEP_GHZ,
  parameterSweepModeOptions,
} from "@/features/simulation/components/simulation-setup-stage-config";
import type { SimulationRequestValues } from "@/features/simulation/lib/request-form";
import { AppInlineSelect, type AppSelectOption } from "@/features/shared/components/app-select";
import { AppNumberInput } from "@/features/shared/components/app-number-input";
import { SurfaceTag, cx } from "@/features/shared/components/surface-kit";

export function SimulationParameterSweepSection({
  form,
  onAddAxis,
  parameterSweepEnabled,
  parameterSweepFieldArray,
  sweepTargetOptions,
  sweepTargetOptionsByValue,
  sweepTargetSelectOptions,
}: Readonly<{
  form: UseFormReturn<SimulationRequestValues>;
  onAddAxis: () => void;
  parameterSweepEnabled: boolean;
  parameterSweepFieldArray: UseFieldArrayReturn<
    SimulationRequestValues,
    "simulationParameterSweepAxes",
    "id"
  >;
  sweepTargetOptions: readonly { value: string; unit: string | null }[];
  sweepTargetOptionsByValue: ReadonlyMap<string, { value: string; unit: string | null }>;
  sweepTargetSelectOptions: readonly AppSelectOption[];
}>) {
  return (
    <SetupSection
      title="Parameter Sweep Setup"
      description="Choose sweep targets from the schema or source controls, then add only the axes needed for this run."
      status={<SurfaceTag tone="primary">Persisted on task</SurfaceTag>}
    >
      <div className="flex flex-wrap items-center justify-between gap-3 rounded-[0.95rem] border border-border bg-background px-4 py-3">
        <div className="min-w-[260px] flex-1">
          <SetupSlideToggle
            checked={parameterSweepEnabled}
            label="Enable parameter sweeps"
            className="min-h-[52px]"
            description={
              sweepTargetOptions.length === 0
                ? "No schema parameters or source controls are available for sweeping on this definition."
                : undefined
            }
            disabled={sweepTargetOptions.length === 0}
            onCheckedChange={(nextChecked) => {
              form.setValue("simulationParameterSweepEnabled", nextChecked, {
                shouldDirty: true,
              });
              if (nextChecked && parameterSweepFieldArray.fields.length === 0) {
                onAddAxis();
              }
            }}
          />
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <button
            type="button"
            onClick={onAddAxis}
            disabled={!parameterSweepEnabled || sweepTargetOptions.length === 0}
            className="inline-flex cursor-pointer items-center gap-2 rounded-full border border-border bg-background px-3 py-2 text-xs font-medium text-foreground transition hover:border-primary/35 hover:bg-primary/10 disabled:cursor-not-allowed disabled:opacity-60"
          >
            <Plus className="h-3.5 w-3.5" />
            Add Axis
          </button>
        </div>
      </div>

      {sweepTargetOptions.length === 0 ? (
        <div className="rounded-[0.95rem] border border-dashed border-border bg-background px-4 py-4 text-sm text-muted-foreground">
          No sweep targets are currently available from the circuit schema or simulation
          sources, so parameter sweeps stay disabled.
        </div>
      ) : parameterSweepEnabled ? (
        <div className="space-y-3">
          {parameterSweepFieldArray.fields.map((field, index) => {
            const axisErrors = form.formState.errors.simulationParameterSweepAxes?.[index];
            const axisMode = form.watch(`simulationParameterSweepAxes.${index}.mode`);
            const axisParameter = form.watch(`simulationParameterSweepAxes.${index}.parameter`);
            const axisOption =
              sweepTargetOptionsByValue.get(axisParameter) ?? sweepTargetOptions[0] ?? null;
            const axisDerivedUnit = axisOption?.unit ?? null;

            return (
              <div
                key={field.id}
                className="rounded-[0.95rem] border border-border bg-background px-4 py-4"
              >
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div className="min-w-0">
                    <p className="text-sm font-semibold text-foreground">Axis {index + 1}</p>
                  </div>
                  <button
                    type="button"
                    onClick={() => {
                      parameterSweepFieldArray.remove(index);
                    }}
                    className="inline-flex cursor-pointer items-center gap-2 rounded-full border border-border bg-surface px-3 py-2 text-xs font-medium text-foreground transition hover:border-rose-300 hover:bg-rose-50 dark:hover:border-rose-400/40 dark:hover:bg-rose-500/10"
                  >
                    <Trash2 className="h-3.5 w-3.5" />
                    Remove Axis
                  </button>
                </div>

                <div
                  className={cx(
                    "mt-4 grid gap-4",
                    axisMode === "explicit"
                      ? "xl:grid-cols-[minmax(260px,1.25fr)_190px_minmax(300px,1.2fr)]"
                      : "xl:grid-cols-[minmax(260px,1.25fr)_190px_minmax(0,1.4fr)]",
                  )}
                >
                  <CompactField
                    label="Target / Parameter"
                    error={axisErrors?.parameter?.message}
                    headerAside={
                      axisDerivedUnit
                        ? `Schema unit · ${axisDerivedUnit}`
                        : "Schema unit unavailable"
                    }
                  >
                    <AppInlineSelect
                      ariaLabel={`Simulation parameter sweep axis ${index + 1} target`}
                      value={axisParameter}
                      options={sweepTargetSelectOptions}
                      placeholder="Select a sweep target"
                      disabled={sweepTargetOptions.length === 0}
                      onChange={(nextValue) => {
                        const nextOption = sweepTargetOptionsByValue.get(nextValue) ?? null;
                        form.setValue(
                          `simulationParameterSweepAxes.${index}.parameter`,
                          nextValue,
                          { shouldDirty: true },
                        );
                        form.setValue(
                          `simulationParameterSweepAxes.${index}.unit`,
                          nextOption?.unit ?? "",
                          { shouldDirty: false },
                        );
                      }}
                    />
                  </CompactField>
                  <CompactField label="Axis Mode">
                    <AppInlineSelect
                      ariaLabel={`Simulation parameter sweep axis ${index + 1} mode`}
                      value={axisMode}
                      onChange={(nextValue) => {
                        form.setValue(
                          `simulationParameterSweepAxes.${index}.mode`,
                          nextValue as "range" | "explicit",
                          { shouldDirty: true },
                        );
                      }}
                      options={parameterSweepModeOptions}
                    />
                  </CompactField>
                  {axisMode === "explicit" ? (
                    <CompactField
                      label="Explicit Values"
                      detail="Comma-separated values submitted directly to the persisted sweep array."
                      error={axisErrors?.explicitValues?.message}
                    >
                      <SetupTextInput
                        {...form.register(`simulationParameterSweepAxes.${index}.explicitValues`)}
                        placeholder="1.0, 1.1, 1.2"
                      />
                    </CompactField>
                  ) : (
                    <div className="grid gap-4 md:grid-cols-3">
                      <CompactField label="Start" error={axisErrors?.start?.message}>
                        <AppNumberInput
                          {...form.register(`simulationParameterSweepAxes.${index}.start`, {
                            valueAsNumber: true,
                          })}
                          step={
                            axisDerivedUnit === "GHz" ? String(FREQUENCY_WHEEL_STEP_GHZ) : "any"
                          }
                          min={
                            axisDerivedUnit === "GHz"
                              ? String(FREQUENCY_WHEEL_STEP_GHZ)
                              : undefined
                          }
                        />
                      </CompactField>
                      <CompactField label="Stop" error={axisErrors?.stop?.message}>
                        <AppNumberInput
                          {...form.register(`simulationParameterSweepAxes.${index}.stop`, {
                            valueAsNumber: true,
                          })}
                          step={
                            axisDerivedUnit === "GHz" ? String(FREQUENCY_WHEEL_STEP_GHZ) : "any"
                          }
                          min={
                            axisDerivedUnit === "GHz"
                              ? String(FREQUENCY_WHEEL_STEP_GHZ)
                              : undefined
                          }
                        />
                      </CompactField>
                      <CompactField label="Points" error={axisErrors?.pointCount?.message}>
                        <AppNumberInput
                          {...form.register(`simulationParameterSweepAxes.${index}.pointCount`, {
                            valueAsNumber: true,
                          })}
                          min={1}
                        />
                      </CompactField>
                    </div>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      ) : (
        <div className="rounded-[0.95rem] border border-dashed border-border bg-background px-4 py-4 text-sm text-muted-foreground">
          Parameter sweeps are disabled for this run. Turn them on to add one or more axes.
        </div>
      )}
    </SetupSection>
  );
}
