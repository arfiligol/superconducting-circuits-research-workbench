"use client";

import type { UseFormReturn } from "react-hook-form";

import { CompactField, SetupSection, SetupSlideToggle } from "@/features/simulation/components/simulation-workbench-stage-kit";
import { ptcModeOptions } from "@/features/simulation/components/simulation-setup-stage-config";
import type { SimulationRequestValues } from "@/features/simulation/lib/request-form";
import { AppInlineSelect } from "@/features/shared/components/app-select";
import { SurfaceTag, cx } from "@/features/shared/components/surface-kit";

export function SimulationPtcSection({
  form,
  ptcEnabled,
  ptcPortOptions,
  selectedPtcPorts,
}: Readonly<{
  form: UseFormReturn<SimulationRequestValues>;
  ptcEnabled: boolean;
  ptcPortOptions: readonly { value: string; label: string }[];
  selectedPtcPorts: ReadonlySet<string>;
}>) {
  return (
    <SetupSection
      title="PTC"
      description="Choose the schema-defined ports that should be included in the persisted PTC setup for this run."
      status={<SurfaceTag tone="primary">Persisted on task</SurfaceTag>}
      actions={
        <button
          type="button"
          onClick={() => {
            form.setValue("simulationPtcEnabled", false, { shouldDirty: true });
            form.setValue("simulationPtcMode", "auto", {
              shouldDirty: true,
            });
            form.setValue("simulationPtcCompensatePorts", "", { shouldDirty: true });
            form.setValue("simulationPtcManualNotes", "", { shouldDirty: true });
          }}
          className="inline-flex cursor-pointer items-center gap-2 rounded-full border border-border bg-background px-3 py-2 text-xs font-medium text-foreground transition hover:border-primary/35 hover:bg-primary/10"
        >
          Reset PTC
        </button>
      }
    >
      <div className="rounded-[0.95rem] border border-border bg-background px-4 py-4">
        <p className="text-xs leading-5 text-muted-foreground">
          PTC is submitted with the simulation setup and restored from persisted task detail.
        </p>

        <div className="grid gap-4 lg:grid-cols-[minmax(260px,1fr)_220px]">
          <SetupSlideToggle
            checked={ptcEnabled}
            label="Enable PTC"
            description={
              ptcPortOptions.length > 0
                ? "Schema-derived ports are persisted with the simulation run."
                : "No schema ports are available for PTC on this definition."
            }
            disabled={ptcPortOptions.length === 0}
            onCheckedChange={(nextChecked) => {
              form.setValue("simulationPtcEnabled", nextChecked, {
                shouldDirty: true,
              });
            }}
          />
          <CompactField label="Mode">
            <AppInlineSelect
              ariaLabel="PTC mode"
              value={form.watch("simulationPtcMode")}
              onChange={(nextValue) => {
                form.setValue("simulationPtcMode", nextValue as "auto" | "manual", {
                  shouldDirty: true,
                });
              }}
              options={ptcModeOptions}
              disabled={!ptcEnabled}
            />
          </CompactField>
        </div>

        <div className="mt-4">
          {ptcPortOptions.length > 0 ? (
            <div className="flex flex-wrap items-center gap-2">
              {ptcPortOptions.map((port) => {
                const isSelected = selectedPtcPorts.has(port.value);
                return (
                  <button
                    key={port.value}
                    type="button"
                    disabled={!ptcEnabled}
                    onClick={() => {
                      const nextSelection = new Set(selectedPtcPorts);
                      if (nextSelection.has(port.value)) {
                        nextSelection.delete(port.value);
                      } else {
                        nextSelection.add(port.value);
                      }
                      form.setValue(
                        "simulationPtcCompensatePorts",
                        [...nextSelection].join(", "),
                        { shouldDirty: true },
                      );
                    }}
                    className={cx(
                      "inline-flex cursor-pointer items-center gap-2 rounded-full border px-3 py-2 text-xs font-medium transition disabled:cursor-not-allowed disabled:opacity-60",
                      isSelected
                        ? "border-primary/35 bg-primary text-primary-foreground"
                        : "border-border bg-surface text-foreground hover:border-primary/35 hover:bg-primary/10",
                    )}
                  >
                    {port.label}
                  </button>
                );
              })}
            </div>
          ) : (
            <div className="rounded-[0.95rem] border border-dashed border-border bg-surface px-4 py-4 text-sm text-muted-foreground">
              This definition does not expose any schema ports for PTC selection.
            </div>
          )}
        </div>
      </div>
    </SetupSection>
  );
}
