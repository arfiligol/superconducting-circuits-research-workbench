"use client";

import { ChevronDown, ChevronRight, LoaderCircle, Play, Plus, RefreshCcw, Save, Settings2, Trash2, WandSparkles } from "lucide-react";
import type { UseFieldArrayReturn, UseFormReturn } from "react-hook-form";

import type { OfficialSimulationExamplePreset } from "@/features/simulation/lib/official-example";
import type { CircuitDefinitionId } from "@/features/circuit-definition-editor/lib/schema-identity";
import type { SimulationRequestValues } from "@/features/simulation/lib/request-form";
import {
  CompactField,
  DraftOnlyBadge,
  OverlayDialog,
  SetupInputField,
  SetupSection,
  SetupSlideToggle,
  SetupTextInput,
  StageTaskActions,
  SummaryCard,
  WorkflowStageSection,
} from "@/features/simulation/components/simulation-workbench-stage-kit";
import type { WorkflowStageState } from "@/features/simulation/lib/stage-state";
import { formatSimulationTaskStatusLabel } from "@/features/simulation/lib/workflow";
import { taskStatusTone } from "@/features/simulation/lib/stage-state";
import {
  AppInlineSelect,
  type AppSelectOption,
} from "@/features/shared/components/app-select";
import { AppNumberInput } from "@/features/shared/components/app-number-input";
import { SurfaceTag, cx } from "@/features/shared/components/surface-kit";
import type { SimulationTaskMutationStatus } from "@/features/simulation/hooks/use-simulation-task-submit-mutation";
import type {
  CircuitDefinitionSummary,
} from "@/features/circuit-definition-editor/lib/contracts";
import type {
  PostProcessingStepType,
} from "@/features/simulation/lib/post-processing-basis";
import type {
  TaskDetail,
  TaskSummary,
} from "@/lib/api/tasks";
import type { SavedSimulationSetupRecord } from "@/features/simulation/lib/saved-setups";

const FREQUENCY_WHEEL_STEP_GHZ = 0.001;
const SOURCE_CURRENT_WHEEL_STEP_AMP = 0.000001;

const spacingSelectOptions: readonly AppSelectOption[] = [
  { value: "linear", label: "Linear" },
  { value: "log", label: "Log" },
];

const parameterSweepModeOptions: readonly AppSelectOption[] = [
  { value: "range", label: "Range builder" },
  { value: "explicit", label: "Explicit values" },
];

const ptcModeOptions: readonly AppSelectOption[] = [
  { value: "auto", label: "Auto compensate" },
  { value: "manual", label: "Manual notes" },
];

type SimulationSetupAuthorityPresentation = Readonly<{
  primaryTag: Readonly<{ label: string; tone: "default" | "primary" | "success" | "warning" | "error" }>;
  secondaryTag?: Readonly<{ label: string; tone: "default" | "primary" | "success" | "warning" | "error" }> | null;
  message: string;
  restoreLabel: string | null;
}>;

function formatSavedSetupTimestamp(isoTimestamp: string) {
  const parsedTimestamp = new Date(isoTimestamp);
  if (Number.isNaN(parsedTimestamp.getTime())) {
    return isoTimestamp;
  }

  return parsedTimestamp.toLocaleString("en-US", {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

function SavedSetupDialogs({
  activeSavedSetup,
  isManageDialogOpen,
  isSaveDialogOpen,
  openSaveAsNewFromManage,
  resolvedDefinitionId,
  saveDialogMode,
  saveDialogOverwriteTargetId,
  saveSetupNameDraft,
  selectedDefinitionDisplay,
  setIsManageDialogOpen,
  setIsSaveDialogOpen,
  setSaveSetupNameDraft,
  submitSaveDialog,
  visibleSavedSetups,
  applySavedSetup,
  deleteSavedSetup,
}: Readonly<{
  activeSavedSetup: SavedSimulationSetupRecord | null;
  isManageDialogOpen: boolean;
  isSaveDialogOpen: boolean;
  openSaveAsNewFromManage: () => void;
  resolvedDefinitionId: CircuitDefinitionId | null;
  saveDialogMode: "new-only" | "choose";
  saveDialogOverwriteTargetId: string | null;
  saveSetupNameDraft: string;
  selectedDefinitionDisplay: CircuitDefinitionSummary | { name: string } | null;
  setIsManageDialogOpen: (open: boolean) => void;
  setIsSaveDialogOpen: (open: boolean) => void;
  setSaveSetupNameDraft: (value: string) => void;
  submitSaveDialog: (action: "create" | "overwrite") => void;
  visibleSavedSetups: readonly SavedSimulationSetupRecord[];
  applySavedSetup: (setup: SavedSimulationSetupRecord) => void;
  deleteSavedSetup: (recordId: string) => void;
}>) {
  return (
    <>
      <OverlayDialog
        open={isSaveDialogOpen}
        title="Save Simulation Setup"
        description="Store the current Simulation Setup locally in this browser for the selected definition. This does not create a backend resource."
        onClose={() => {
          setIsSaveDialogOpen(false);
        }}
      >
        <div className="space-y-4">
          {saveDialogMode === "choose" && activeSavedSetup ? (
            <div className="rounded-[0.95rem] border border-border bg-surface px-4 py-3 text-sm text-muted-foreground">
              Saving from <span className="font-medium text-foreground">{activeSavedSetup.name}</span>.
              Choose whether to overwrite the current saved setup or create a new one.
            </div>
          ) : null}
          <SetupInputField label="Setup Name">
            <SetupTextInput
              value={saveSetupNameDraft}
              onChange={(event) => {
                setSaveSetupNameDraft(event.target.value);
              }}
              placeholder={selectedDefinitionDisplay?.name ?? "Simulation Setup"}
            />
          </SetupInputField>
          <div className="flex flex-wrap justify-end gap-2">
            <button
              type="button"
              onClick={() => {
                setIsSaveDialogOpen(false);
              }}
              className="inline-flex cursor-pointer items-center gap-2 rounded-md border border-border px-3 py-2 text-sm text-foreground transition hover:border-primary/40 hover:bg-primary/10"
            >
              Cancel
            </button>
            {saveDialogMode === "choose" && saveDialogOverwriteTargetId ? (
              <>
                <button
                  type="button"
                  onClick={() => {
                    submitSaveDialog("create");
                  }}
                  className="inline-flex cursor-pointer items-center gap-2 rounded-md border border-border px-3 py-2 text-sm text-foreground transition hover:border-primary/40 hover:bg-primary/10"
                >
                  <Plus className="h-4 w-4" />
                  Save as New
                </button>
                <button
                  type="button"
                  onClick={() => {
                    submitSaveDialog("overwrite");
                  }}
                  className="inline-flex cursor-pointer items-center gap-2 rounded-md bg-primary px-3 py-2 text-sm font-medium text-primary-foreground transition hover:opacity-90"
                >
                  <Save className="h-4 w-4" />
                  Overwrite Current
                </button>
              </>
            ) : (
              <button
                type="button"
                onClick={() => {
                  submitSaveDialog("create");
                }}
                className="inline-flex cursor-pointer items-center gap-2 rounded-md bg-primary px-3 py-2 text-sm font-medium text-primary-foreground transition hover:opacity-90"
              >
                <Save className="h-4 w-4" />
                Save Setup
              </button>
            )}
          </div>
        </div>
      </OverlayDialog>

      <OverlayDialog
        open={isManageDialogOpen}
        title="Manage Saved Setups"
        description="Review browser-saved Simulation Setup drafts for the current definition, load one into Stage 2, or remove old drafts."
        onClose={() => {
          setIsManageDialogOpen(false);
        }}
      >
        <div className="space-y-4">
          {visibleSavedSetups.length > 0 ? (
            <div className="space-y-3">
              {visibleSavedSetups.map((setup) => {
                const isActive = setup.id === activeSavedSetup?.id;
                return (
                  <div
                    key={setup.id}
                    className="rounded-[0.95rem] border border-border bg-surface px-4 py-4"
                  >
                    <div className="flex flex-wrap items-start justify-between gap-3">
                      <div className="min-w-0">
                        <div className="flex flex-wrap items-center gap-2">
                          <p className="text-sm font-semibold text-foreground">{setup.name}</p>
                          {isActive ? <SurfaceTag tone="success">Current</SurfaceTag> : null}
                        </div>
                        <p className="mt-2 text-xs leading-5 text-muted-foreground">
                          {setup.definitionName ?? "Definition"} · Updated{" "}
                          {formatSavedSetupTimestamp(setup.updatedAt)}
                        </p>
                      </div>
                      <div className="flex flex-wrap gap-2">
                        <button
                          type="button"
                          onClick={() => {
                            applySavedSetup(setup);
                          }}
                          className="inline-flex cursor-pointer items-center gap-2 rounded-md border border-border px-3 py-2 text-sm text-foreground transition hover:border-primary/40 hover:bg-primary/10"
                        >
                          Load
                        </button>
                        <button
                          type="button"
                          onClick={() => {
                            deleteSavedSetup(setup.id);
                          }}
                          className="inline-flex cursor-pointer items-center gap-2 rounded-md border border-border px-3 py-2 text-sm text-foreground transition hover:border-rose-300 hover:bg-rose-50 dark:hover:border-rose-400/40 dark:hover:bg-rose-500/10"
                        >
                          <Trash2 className="h-4 w-4" />
                          Delete
                        </button>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          ) : (
            <div className="rounded-[0.95rem] border border-dashed border-border bg-surface px-4 py-5 text-sm text-muted-foreground">
              No saved setups exist for the current definition yet.
            </div>
          )}

          <div className="flex flex-wrap justify-between gap-2">
            <button
              type="button"
              onClick={openSaveAsNewFromManage}
              disabled={resolvedDefinitionId === null}
              className="inline-flex cursor-pointer items-center gap-2 rounded-md border border-border px-3 py-2 text-sm text-foreground transition hover:border-primary/40 hover:bg-primary/10 disabled:cursor-not-allowed disabled:opacity-60"
            >
              <Plus className="h-4 w-4" />
              Save Current as New
            </button>
            <button
              type="button"
              onClick={() => {
                setIsManageDialogOpen(false);
              }}
              className="inline-flex cursor-pointer items-center gap-2 rounded-md border border-border px-3 py-2 text-sm text-foreground transition hover:border-primary/40 hover:bg-primary/10"
            >
              Done
            </button>
          </div>
        </div>
      </OverlayDialog>
    </>
  );
}

export function SimulationSetupStage({
  activeSavedSetup,
  applyOfficialExamplePreset,
  applySavedSetup,
  deleteSavedSetup,
  displayedSimulationStageAuthority,
  displayedSimulationTaskDetail,
  form,
  harmonicBalanceEnabled,
  isAdvancedHbsolveExpanded,
  isManageDialogOpen,
  isSaveDialogOpen,
  officialExamplePreset,
  onAddAxis,
  onAddSource,
  onOpenManageDialog,
  onOpenSaveDialog,
  onSubmit,
  openSaveAsNewFromManage,
  parameterSweepEnabled,
  parameterSweepFieldArray,
  ptcEnabled,
  ptcPortOptions,
  resolvedDefinitionId,
  resolvedTaskId,
  restoreSimulationSetupFromCurrentSource,
  saveDialogMode,
  saveDialogOverwriteTargetId,
  saveSetupNameDraft,
  savedSetupFeedback,
  selectedDefinitionDisplay,
  selectedPtcPorts,
  setIsAdvancedHbsolveExpanded,
  setIsManageDialogOpen,
  setIsSaveDialogOpen,
  setSaveSetupNameDraft,
  simulationResultReady,
  simulationSetupAuthorityPresentation,
  simulationSetupBlockedReason,
  simulationSetupBuildError,
  sourceFieldArray,
  sourcePortSelectOptions,
  state,
  submitSaveDialog,
  sweepTargetOptions,
  sweepTargetOptionsByValue,
  sweepTargetSelectOptions,
  taskMutationStatus,
  attachTask,
  visibleSavedSetups,
}: Readonly<{
  activeSavedSetup: SavedSimulationSetupRecord | null;
  applyOfficialExamplePreset: () => void;
  applySavedSetup: (record: SavedSimulationSetupRecord) => void;
  deleteSavedSetup: (recordId: string) => void;
  displayedSimulationStageAuthority: TaskSummary | undefined;
  displayedSimulationTaskDetail: TaskDetail | undefined;
  form: UseFormReturn<SimulationRequestValues>;
  harmonicBalanceEnabled: boolean;
  isAdvancedHbsolveExpanded: boolean;
  isManageDialogOpen: boolean;
  isSaveDialogOpen: boolean;
  officialExamplePreset: OfficialSimulationExamplePreset | null;
  onAddAxis: () => void;
  onAddSource: () => void;
  onOpenManageDialog: () => void;
  onOpenSaveDialog: () => void;
  onSubmit: () => void;
  openSaveAsNewFromManage: () => void;
  parameterSweepEnabled: boolean;
  parameterSweepFieldArray: UseFieldArrayReturn<SimulationRequestValues, "simulationParameterSweepAxes", "id">;
  ptcEnabled: boolean;
  ptcPortOptions: readonly { value: string; label: string }[];
  resolvedDefinitionId: CircuitDefinitionId | null;
  resolvedTaskId: number | null;
  restoreSimulationSetupFromCurrentSource: () => void;
  saveDialogMode: "new-only" | "choose";
  saveDialogOverwriteTargetId: string | null;
  saveSetupNameDraft: string;
  savedSetupFeedback: string | null;
  selectedDefinitionDisplay: CircuitDefinitionSummary | { name: string } | null;
  selectedPtcPorts: ReadonlySet<string>;
  setIsAdvancedHbsolveExpanded: React.Dispatch<React.SetStateAction<boolean>>;
  setIsManageDialogOpen: (open: boolean) => void;
  setIsSaveDialogOpen: (open: boolean) => void;
  setSaveSetupNameDraft: (value: string) => void;
  simulationResultReady: boolean;
  simulationSetupAuthorityPresentation: SimulationSetupAuthorityPresentation;
  simulationSetupBlockedReason: string | null;
  simulationSetupBuildError: string | null;
  sourceFieldArray: UseFieldArrayReturn<SimulationRequestValues, "simulationSources", "id">;
  sourcePortSelectOptions: readonly AppSelectOption[];
  state: WorkflowStageState;
  submitSaveDialog: (action: "create" | "overwrite") => void;
  sweepTargetOptions: readonly { value: string; unit: string | null }[];
  sweepTargetOptionsByValue: ReadonlyMap<string, { value: string; unit: string | null }>;
  sweepTargetSelectOptions: readonly AppSelectOption[];
  taskMutationStatus: SimulationTaskMutationStatus;
  attachTask: (taskId: number) => void;
  visibleSavedSetups: readonly SavedSimulationSetupRecord[];
}>) {
  return (
    <>
      <WorkflowStageSection
        step={2}
        title="Simulation Setup"
        description="Configure the runnable simulation setup in six focused sections."
        status={state}
        actions={
          <div className="flex shrink-0 items-center gap-2 whitespace-nowrap">
            {officialExamplePreset ? (
              <button
                type="button"
                onClick={applyOfficialExamplePreset}
                className="inline-flex cursor-pointer items-center gap-2 rounded-full border border-primary/30 bg-primary/10 px-3 py-2 text-xs font-medium text-foreground transition hover:border-primary/45 hover:bg-primary/15"
              >
                <WandSparkles className="h-3.5 w-3.5" />
                Load Official Example
              </button>
            ) : null}
            <button
              type="button"
              onClick={onOpenManageDialog}
              disabled={resolvedDefinitionId === null}
              className="inline-flex cursor-pointer items-center gap-2 rounded-full border border-border bg-background px-3 py-2 text-xs font-medium text-foreground transition hover:border-primary/35 hover:bg-primary/10 disabled:cursor-not-allowed disabled:opacity-60"
            >
              <Settings2 className="h-3.5 w-3.5" />
              Manage
            </button>
            <button
              type="button"
              onClick={onOpenSaveDialog}
              disabled={resolvedDefinitionId === null}
              className="inline-flex cursor-pointer items-center gap-2 rounded-full border border-primary/30 bg-primary/10 px-3 py-2 text-xs font-medium text-foreground transition hover:border-primary/45 hover:bg-primary/15 disabled:cursor-not-allowed disabled:opacity-60"
            >
              <Save className="h-3.5 w-3.5" />
              Save
            </button>
          </div>
        }
      >
        <div className="flex flex-wrap items-center gap-2 rounded-[0.95rem] border border-border bg-surface px-4 py-3 text-xs">
          <SurfaceTag tone={simulationSetupAuthorityPresentation.primaryTag.tone}>
            {simulationSetupAuthorityPresentation.primaryTag.label}
          </SurfaceTag>
          {simulationSetupAuthorityPresentation.secondaryTag ? (
            <SurfaceTag tone={simulationSetupAuthorityPresentation.secondaryTag.tone}>
              {simulationSetupAuthorityPresentation.secondaryTag.label}
            </SurfaceTag>
          ) : null}
          <span className="leading-5 text-muted-foreground">
            {simulationSetupAuthorityPresentation.message}
          </span>
          {simulationSetupAuthorityPresentation.restoreLabel ? (
            <button
              type="button"
              onClick={restoreSimulationSetupFromCurrentSource}
              className="inline-flex cursor-pointer items-center gap-2 rounded-full border border-border bg-background px-2.5 py-1 text-[11px] font-medium text-foreground transition hover:border-primary/35 hover:bg-primary/10"
            >
              <RefreshCcw className="h-3 w-3" />
              {simulationSetupAuthorityPresentation.restoreLabel}
            </button>
          ) : null}
          {savedSetupFeedback ? (
            <span className="leading-5 text-foreground/80">{savedSetupFeedback}</span>
          ) : null}
        </div>

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
                            {...form.register(
                              `simulationParameterSweepAxes.${index}.explicitValues`,
                            )}
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
                                axisDerivedUnit === "GHz"
                                  ? String(FREQUENCY_WHEEL_STEP_GHZ)
                                  : "any"
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
                                axisDerivedUnit === "GHz"
                                  ? String(FREQUENCY_WHEEL_STEP_GHZ)
                                  : "any"
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
                              {...form.register(
                                `simulationParameterSweepAxes.${index}.pointCount`,
                                {
                                  valueAsNumber: true,
                                },
                              )}
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
                      <CompactField label="Pump Freq (GHz)" error={sourceErrors?.pumpFreqGhz?.message}>
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
                  <CompactField
                    label="Advanced Notes"
                    className="md:col-span-2 xl:col-span-3"
                  >
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

        <label className="block rounded-[0.95rem] border border-border bg-surface px-4 py-3">
          <span className="mb-2 block text-xs uppercase tracking-[0.16em] text-muted-foreground">
            Simulation Run Note
          </span>
          <textarea
            {...form.register("simulationNote")}
            rows={4}
            placeholder="Optional context for this run, for example frequency sweep check or cache verification."
            className="w-full resize-none bg-transparent text-sm leading-6 text-foreground outline-none placeholder:text-muted-foreground"
          />
        </label>

        {form.formState.errors.simulationNote ? (
          <p className="text-sm text-rose-700 dark:text-rose-300">
            {form.formState.errors.simulationNote.message}
          </p>
        ) : null}
        {simulationSetupBuildError ? (
          <p className="text-sm text-rose-700 dark:text-rose-300">
            {simulationSetupBuildError}
          </p>
        ) : null}

        <button
          type="button"
          onClick={onSubmit}
          disabled={taskMutationStatus.state === "submitting" || simulationSetupBlockedReason !== null}
          className="inline-flex min-h-11 w-full cursor-pointer items-center justify-center gap-2 rounded-full bg-primary px-4 py-3 text-sm font-medium text-primary-foreground transition hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-60"
        >
          {taskMutationStatus.state === "submitting" ? (
            <LoaderCircle className="h-4 w-4 animate-spin" />
          ) : (
            <Play className="h-4 w-4" />
          )}
          Run Simulation
        </button>

        {displayedSimulationStageAuthority ? (
          <div className="rounded-[0.95rem] border border-border bg-background px-4 py-4">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <p className="text-xs uppercase tracking-[0.16em] text-muted-foreground">
                  {displayedSimulationStageAuthority.taskId === displayedSimulationTaskDetail?.taskId
                    ? "Attached Simulation Run"
                    : "Latest Simulation Run"}
                </p>
                <p className="mt-2 text-sm font-semibold text-foreground">
                  Task #{displayedSimulationStageAuthority.taskId}
                </p>
                <p className="mt-2 text-sm text-muted-foreground">
                  {displayedSimulationTaskDetail?.progress.summary ??
                    displayedSimulationStageAuthority.summary}
                </p>
              </div>
              <SurfaceTag tone={taskStatusTone(displayedSimulationStageAuthority.status)}>
                {formatSimulationTaskStatusLabel(displayedSimulationStageAuthority.status)}
              </SurfaceTag>
            </div>
            <div className="mt-4 grid gap-3 md:grid-cols-3">
              <SummaryCard
                label="Submitted"
                value={displayedSimulationStageAuthority.submittedAt ?? "Pending"}
              />
              <SummaryCard
                label="Result"
                value={simulationResultReady ? "Ready" : "Pending"}
                detail={
                  displayedSimulationTaskDetail?.resultHandoff?.availability
                    ? `Persisted result handoff: ${displayedSimulationTaskDetail.resultHandoff.availability}`
                    : displayedSimulationStageAuthority.resultAvailability
                      ? `Backend result availability: ${displayedSimulationStageAuthority.resultAvailability}`
                      : "Result status is inferred from persisted task detail."
                }
              />
              <SummaryCard
                label="Progress"
                value={
                  displayedSimulationTaskDetail
                    ? `${Math.round(displayedSimulationTaskDetail.progress.percentComplete)}%`
                    : formatSimulationTaskStatusLabel(displayedSimulationStageAuthority.status)
                }
              />
            </div>
            <div className="mt-4">
              <StageTaskActions
                task={displayedSimulationStageAuthority}
                resolvedTaskId={resolvedTaskId}
                onViewTask={attachTask}
              />
            </div>
          </div>
        ) : null}
      </WorkflowStageSection>

      <SavedSetupDialogs
        activeSavedSetup={activeSavedSetup}
        isManageDialogOpen={isManageDialogOpen}
        isSaveDialogOpen={isSaveDialogOpen}
        openSaveAsNewFromManage={openSaveAsNewFromManage}
        resolvedDefinitionId={resolvedDefinitionId}
        saveDialogMode={saveDialogMode}
        saveDialogOverwriteTargetId={saveDialogOverwriteTargetId}
        saveSetupNameDraft={saveSetupNameDraft}
        selectedDefinitionDisplay={selectedDefinitionDisplay}
        setIsManageDialogOpen={setIsManageDialogOpen}
        setIsSaveDialogOpen={setIsSaveDialogOpen}
        setSaveSetupNameDraft={setSaveSetupNameDraft}
        submitSaveDialog={submitSaveDialog}
        visibleSavedSetups={visibleSavedSetups}
        applySavedSetup={applySavedSetup}
        deleteSavedSetup={deleteSavedSetup}
      />
    </>
  );
}
