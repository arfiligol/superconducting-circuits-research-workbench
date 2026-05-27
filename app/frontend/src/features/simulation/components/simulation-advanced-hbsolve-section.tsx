"use client";

import { ChevronDown, ChevronRight } from "lucide-react";
import type { UseFormReturn } from "react-hook-form";

import { CompactField, DraftOnlyBadge, SetupSection, SetupSlideToggle, SetupTextInput } from "@/features/simulation/components/simulation-workbench-stage-kit";
import type { SimulationRequestValues } from "@/features/simulation/lib/request-form";
import { AppNumberInput } from "@/features/shared/components/app-number-input";
import { SurfaceTag } from "@/features/shared/components/surface-kit";

export function SimulationAdvancedHbsolveSection({
  form,
  harmonicBalanceEnabled,
  isAdvancedHbsolveExpanded,
  setIsAdvancedHbsolveExpanded,
}: Readonly<{
  form: UseFormReturn<SimulationRequestValues>;
  harmonicBalanceEnabled: boolean;
  isAdvancedHbsolveExpanded: boolean;
  setIsAdvancedHbsolveExpanded: React.Dispatch<React.SetStateAction<boolean>>;
}>) {
  return (
    <SetupSection
      title="Advanced hbsolve Options"
      description="Advanced hbsolve tuning stays collapsed until needed."
      status={
        <>
          <SurfaceTag tone="primary">Persisted on task</SurfaceTag>
          <DraftOnlyBadge />
        </>
      }
      actions={
        <button
          type="button"
          onClick={() => {
            setIsAdvancedHbsolveExpanded((current) => !current);
          }}
          aria-expanded={isAdvancedHbsolveExpanded}
          className="inline-flex cursor-pointer items-center gap-2 rounded-full border border-border bg-background px-3 py-2 text-xs font-medium text-foreground transition hover:border-primary/35 hover:bg-primary/10"
        >
          {isAdvancedHbsolveExpanded ? (
            <ChevronDown className="h-3.5 w-3.5" />
          ) : (
            <ChevronRight className="h-3.5 w-3.5" />
          )}
          {isAdvancedHbsolveExpanded ? "Hide options" : "Show options"}
        </button>
      }
    >
      {isAdvancedHbsolveExpanded ? (
        <div className="space-y-4">
          <div className="rounded-[0.95rem] border border-border bg-background px-4 py-4">
            <div className="grid gap-4 lg:grid-cols-2 xl:grid-cols-4">
              <CompactField
                label="Solver Family"
                error={form.formState.errors.simulationSolverFamily?.message}
              >
                <SetupTextInput
                  {...form.register("simulationSolverFamily")}
                  placeholder="harmonic_balance"
                />
              </CompactField>
              <CompactField
                label="Max Iterations"
                error={form.formState.errors.simulationMaxIterations?.message}
              >
                <AppNumberInput
                  {...form.register("simulationMaxIterations", { valueAsNumber: true })}
                  min={1}
                />
              </CompactField>
              <CompactField
                label="Convergence Tolerance"
                error={form.formState.errors.simulationConvergenceTolerance?.message}
              >
                <AppNumberInput
                  {...form.register("simulationConvergenceTolerance", {
                    valueAsNumber: true,
                  })}
                  step="any"
                />
              </CompactField>
              <SetupSlideToggle
                checked={harmonicBalanceEnabled}
                label="Enable harmonic balance"
                description="Persist whether hbsolve harmonic-balance mode is active for this run."
                onCheckedChange={(nextChecked) => {
                  form.setValue("simulationHarmonicBalanceEnabled", nextChecked, {
                    shouldDirty: true,
                  });
                }}
              />
            </div>
          </div>

          <div className="rounded-[0.95rem] border border-border bg-background px-4 py-4">
            <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
              <CompactField label="Damping Strategy">
                <SetupTextInput
                  {...form.register("simulationAdvancedDampingStrategy")}
                  placeholder="adaptive"
                />
              </CompactField>
              <SetupSlideToggle
                checked={form.watch("simulationAdvancedLineSearchEnabled")}
                label="Enable line search"
                onCheckedChange={(nextChecked) => {
                  form.setValue("simulationAdvancedLineSearchEnabled", nextChecked, {
                    shouldDirty: true,
                  });
                }}
              />
              <CompactField label="Residual Clamp">
                <SetupTextInput
                  {...form.register("simulationAdvancedResidualClamp")}
                  placeholder="1e-6"
                />
              </CompactField>
              <CompactField label="Newton Relaxation">
                <SetupTextInput
                  {...form.register("simulationAdvancedNewtonRelaxation")}
                  placeholder="0.85"
                />
              </CompactField>
              <CompactField label="Advanced Notes" className="md:col-span-2 xl:col-span-3">
                <textarea
                  {...form.register("simulationAdvancedNotes")}
                  rows={4}
                  placeholder="Optional advanced hbsolve notes."
                  className="w-full resize-none rounded-[0.8rem] border border-border bg-surface px-3 py-2.5 text-sm leading-6 text-foreground outline-none transition placeholder:text-muted-foreground focus:border-primary/45 focus:ring-2 focus:ring-primary/15"
                />
              </CompactField>
            </div>
          </div>
        </div>
      ) : (
        <div className="rounded-[0.95rem] border border-dashed border-border bg-background px-4 py-4 text-sm text-muted-foreground">
          Advanced hbsolve options stay collapsed until you need them.
        </div>
      )}
    </SetupSection>
  );
}
