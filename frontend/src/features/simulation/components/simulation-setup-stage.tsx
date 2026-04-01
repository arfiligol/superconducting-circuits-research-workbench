"use client";

import { LoaderCircle, Play, RefreshCcw, Save, Settings2, WandSparkles } from "lucide-react";
import type { UseFieldArrayReturn, UseFormReturn } from "react-hook-form";

import type { OfficialSimulationExamplePreset } from "@/features/simulation/lib/official-example";
import type { CircuitDefinitionId } from "@/features/circuit-definition-editor/lib/schema-identity";
import type { SimulationRequestValues } from "@/features/simulation/lib/request-form";
import {
  StageTaskActions,
  SummaryCard,
  WorkflowStageSection,
} from "@/features/simulation/components/simulation-workbench-stage-kit";
import { SimulationAdvancedHbsolveSection } from "@/features/simulation/components/simulation-advanced-hbsolve-section";
import { SimulationFrequencySweepSection } from "@/features/simulation/components/simulation-frequency-sweep-section";
import { SimulationHbSolvingSection } from "@/features/simulation/components/simulation-hb-solving-section";
import { SimulationParameterSweepSection } from "@/features/simulation/components/simulation-parameter-sweep-section";
import { SimulationPtcSection } from "@/features/simulation/components/simulation-ptc-section";
import { SimulationSavedSetupDialogs } from "@/features/simulation/components/simulation-saved-setup-dialogs";
import { SimulationSourcesSection } from "@/features/simulation/components/simulation-sources-section";
import type { WorkflowStageState } from "@/features/simulation/lib/stage-state";
import { formatSimulationTaskStatusLabel } from "@/features/simulation/lib/workflow";
import { taskStatusTone } from "@/features/simulation/lib/stage-state";
import type {
  AppSelectOption,
} from "@/features/shared/components/app-select";
import { SurfaceTag } from "@/features/shared/components/surface-kit";
import type { SimulationTaskMutationStatus } from "@/features/simulation/hooks/use-simulation-task-submit-mutation";
import type {
  CircuitDefinitionSummary,
} from "@/features/circuit-definition-editor/lib/contracts";
import type {
  TaskDetail,
  TaskSummary,
} from "@/lib/api/tasks";
import type { SavedSimulationSetupRecord } from "@/features/simulation/lib/saved-setups";

type SimulationSetupAuthorityPresentation = Readonly<{
  primaryTag: Readonly<{ label: string; tone: "default" | "primary" | "success" | "warning" | "error" }>;
  secondaryTag?: Readonly<{ label: string; tone: "default" | "primary" | "success" | "warning" | "error" }> | null;
  message: string;
  restoreLabel: string | null;
}>;

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

        <SimulationFrequencySweepSection form={form} />
        <SimulationParameterSweepSection
          form={form}
          onAddAxis={onAddAxis}
          parameterSweepEnabled={parameterSweepEnabled}
          parameterSweepFieldArray={parameterSweepFieldArray}
          sweepTargetOptions={sweepTargetOptions}
          sweepTargetOptionsByValue={sweepTargetOptionsByValue}
          sweepTargetSelectOptions={sweepTargetSelectOptions}
        />
        <SimulationHbSolvingSection
          form={form}
          harmonicBalanceEnabled={harmonicBalanceEnabled}
        />
        <SimulationSourcesSection
          form={form}
          onAddSource={onAddSource}
          ptcPortOptions={ptcPortOptions}
          sourceFieldArray={sourceFieldArray}
          sourcePortSelectOptions={sourcePortSelectOptions}
        />
        <SimulationPtcSection
          form={form}
          ptcEnabled={ptcEnabled}
          ptcPortOptions={ptcPortOptions}
          selectedPtcPorts={selectedPtcPorts}
        />
        <SimulationAdvancedHbsolveSection
          form={form}
          harmonicBalanceEnabled={harmonicBalanceEnabled}
          isAdvancedHbsolveExpanded={isAdvancedHbsolveExpanded}
          setIsAdvancedHbsolveExpanded={setIsAdvancedHbsolveExpanded}
        />

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
          disabled={
            taskMutationStatus.state === "submitting" || simulationSetupBlockedReason !== null
          }
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

      <SimulationSavedSetupDialogs
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
