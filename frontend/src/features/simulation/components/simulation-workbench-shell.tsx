"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { zodResolver } from "@hookform/resolvers/zod";
import { RefreshCcw } from "lucide-react";
import { useSearchParams } from "next/navigation";
import { useFieldArray, useForm } from "react-hook-form";

import { PostProcessingResultStage } from "@/features/simulation/components/post-processing-result-stage";
import { PostProcessingSetupStage } from "@/features/simulation/components/post-processing-setup-stage";
import { SimulationDefinitionContextStage } from "@/features/simulation/components/simulation-definition-context-stage";
import { SimulationResultStage } from "@/features/simulation/components/simulation-result-stage";
import { SimulationSetupStage } from "@/features/simulation/components/simulation-setup-stage";
import {
  StageNotice,
} from "@/features/simulation/components/simulation-workbench-stage-kit";
import { useSavedSimulationSetups } from "@/features/simulation/hooks/use-saved-simulation-setups";
import { useSimulationSubmission } from "@/features/simulation/hooks/use-simulation-submission";
import { useSimulationTaskAttachment } from "@/features/simulation/hooks/use-simulation-task-attachment";
import { useSimulationWorkflowData } from "@/features/simulation/hooks/use-simulation-workflow-data";
import { parseSimulationDefinitionIdParam } from "@/features/simulation/lib/definition-id";
import { resolveOfficialSimulationExamplePreset } from "@/features/simulation/lib/official-example";
import {
  buildSchemaIdentityDescription,
} from "@/features/circuit-definition-editor/lib/schema-identity";
import {
  createPostProcessingStep,
  derivePostProcessingStepContext,
  isPostProcessingStepTypeAvailable,
  sanitizePostProcessingStep,
  type PostProcessingStepDraft,
  type PostProcessingStepType,
} from "@/features/simulation/lib/post-processing-basis";
import { hydratePostProcessingSteps } from "@/features/simulation/lib/post-processing-setup";
import {
  createDefaultSimulationParameterSweepAxis,
  createDefaultSimulationSource,
  deriveSimulationPtcPortOptions,
  deriveSimulationSweepTargetOptions,
  parseCommaSeparatedStringValues,
} from "@/features/simulation/lib/setup-form";
import {
  defaultRequestValues,
  simulationRequestSchema,
  type SimulationRequestValues,
} from "@/features/simulation/lib/request-form";
import {
  resolveResultStageState,
  resolveSetupStageState,
} from "@/features/simulation/lib/stage-state";
import {
  hasSimulationTaskResult,
  resolveAuthoritativeSimulationTaskSummary,
  resolvePostProcessingUpstreamTaskId,
  resolveSimulationSelectionRecovery,
  summarizeSimulationTaskResults,
  type SimulationStageKind,
} from "@/features/simulation/lib/workflow";
import type { AppSelectOption } from "@/features/shared/components/app-select";
import {
  SurfaceHeader,
  cx,
} from "@/features/shared/components/surface-kit";
import { ApiError } from "@/lib/api/client";
import { useAppToasts } from "@/lib/app-state";

function describeApiError(error: Error | undefined) {
  if (!error) {
    return null;
  }

  if (error instanceof ApiError) {
    const retryHint = error.retryable === true ? " Retry is available." : "";
    const debugHint = error.debugRef ? ` Ref: ${error.debugRef}.` : "";
    return `${error.message}${retryHint}${debugHint}`;
  }

  return error.message;
}

export function SimulationWorkbenchShell() {
  const searchParams = useSearchParams();
  const { pushToast } = useAppToasts();
  const [isRefreshingWorkflow, setIsRefreshingWorkflow] = useState(false);
  const [isAdvancedHbsolveExpanded, setIsAdvancedHbsolveExpanded] = useState(false);
  const [postProcessingSteps, setPostProcessingSteps] = useState<readonly PostProcessingStepDraft[]>(
    [],
  );
  const [newPostProcessingStepType, setNewPostProcessingStepType] =
    useState<PostProcessingStepType>("coordinate_transform");
  const [hydratedPostTaskId, setHydratedPostTaskId] = useState<number | null>(null);
  const hasObservedSimulationTaskToastRef = useRef(false);
  const hasObservedPostProcessingTaskToastRef = useRef(false);
  const lastSimulationTaskToastKeyRef = useRef<string | null>(null);
  const lastPostProcessingTaskToastKeyRef = useRef<string | null>(null);
  const lastWorkflowContextResetKeyRef = useRef<string | null>(null);

  const form = useForm<SimulationRequestValues>({
    resolver: zodResolver(simulationRequestSchema),
    defaultValues: defaultRequestValues,
  });
  const parameterSweepFieldArray = useFieldArray({
    control: form.control,
    name: "simulationParameterSweepAxes",
  });
  const sourceFieldArray = useFieldArray({
    control: form.control,
    name: "simulationSources",
  });
  const parameterSweepEnabled = form.watch("simulationParameterSweepEnabled");
  const harmonicBalanceEnabled = form.watch("simulationHarmonicBalanceEnabled");
  const ptcEnabled = form.watch("simulationPtcEnabled");
  const watchedSimulationSources = form.watch("simulationSources");
  const selectedPtcPortsValue = form.watch("simulationPtcCompensatePorts");

  const requestedDefinitionIdParam = searchParams.get("definitionId");
  const requestedTaskIdValue = searchParams.get("taskId");
  const requestedTaskId = requestedTaskIdValue
    ? Number.parseInt(requestedTaskIdValue, 10) || null
    : null;
  const rawDefinitionId = parseSimulationDefinitionIdParam(requestedDefinitionIdParam);
  const {
    session,
    activeDatasetState,
    definitions,
    definitionsError,
    isDefinitionsLoading,
    resolvedDefinitionId,
    selectedDefinitionSummary,
    activeDefinition,
    activeDefinitionError,
    isDefinitionTransitioning,
    latestSimulationTask,
    latestSimulationStageTask,
    latestSimulationTaskDetail,
    attachedSimulationStageTask,
    attachedSimulationTaskDetail,
    latestSimulationTaskError,
    latestPostProcessingTask,
    latestPostProcessingTaskDetail,
    latestPostProcessingTaskError,
    resolvedTaskId,
    activeTask,
    activeTaskError,
    refreshSimulationWorkflow,
  } = useSimulationWorkflowData(rawDefinitionId, requestedTaskId);

  const activeDatasetId = activeDatasetState.activeDataset?.datasetId ?? null;
  const workflowContextResetKey = `${resolvedDefinitionId ?? "none"}:${activeDatasetId ?? "none"}`;
  const taskAttachment = useSimulationTaskAttachment({
    resolvedDefinitionId,
    resolvedTaskId,
    latestSimulationTask,
    activeTask,
    activeTaskError,
    pageContext: {
      definitionId: resolvedDefinitionId,
      datasetId: activeDatasetId,
    },
  });
  const {
    requestedDefinitionId,
    requestedTaskId: attachedRequestedTaskId,
    taskConnectionState,
    taskRecovery,
    replaceSearchState,
    attachTask,
    clearRequestedTask,
    resetAutoRestoreState,
  } = taskAttachment;

  const definitionRecovery = resolveSimulationSelectionRecovery(
    requestedDefinitionId,
    resolvedDefinitionId,
    definitions,
  );
  const selectedDefinitionDisplay =
    selectedDefinitionSummary ??
    (activeDefinition
      ? {
          definition_id: activeDefinition.definition_id,
          name: activeDefinition.name,
          preview_artifact_count: activeDefinition.preview_artifacts.length,
        }
      : null);
  const definitionsErrorMessage = describeApiError(definitionsError);
  const activeDefinitionErrorMessage = describeApiError(activeDefinitionError);
  const simulationStageErrorMessage = describeApiError(latestSimulationTaskError);
  const postProcessingStageErrorMessage = describeApiError(latestPostProcessingTaskError);
  const definitionOptions = useMemo(
    () => {
      const options = (definitions ?? []).map((definition) => ({
        value: String(definition.definition_id),
        label: definition.name,
        description: buildSchemaIdentityDescription({
          definitionId: definition.definition_id,
          createdAt: definition.created_at,
          extra: `${definition.preview_artifact_count} preview artifacts`,
        }),
      }));

      if (options.length > 0 || !activeDefinition) {
        return options;
      }

      return [
        {
          value: String(activeDefinition.definition_id),
          label: activeDefinition.name,
          description: buildSchemaIdentityDescription({
            definitionId: activeDefinition.definition_id,
            createdAt: activeDefinition.created_at,
            extra: `${activeDefinition.preview_artifacts.length} preview artifacts`,
          }),
        },
      ];
    },
    [activeDefinition, definitions],
  );
  const officialExamplePreset = useMemo(
    () =>
      resolveOfficialSimulationExamplePreset(
        activeDefinition?.name ?? selectedDefinitionDisplay?.name ?? null,
      ),
    [activeDefinition?.name, selectedDefinitionDisplay?.name],
  );
  const sweepTargetOptions = useMemo(
    () =>
      deriveSimulationSweepTargetOptions(
        activeDefinition?.source_text ?? null,
        watchedSimulationSources,
      ),
    [activeDefinition?.source_text, watchedSimulationSources],
  );
  const sweepTargetOptionsByValue = useMemo(
    () => new Map(sweepTargetOptions.map((option) => [option.value, option] as const)),
    [sweepTargetOptions],
  );
  const sweepTargetSelectOptions = useMemo<readonly AppSelectOption[]>(
    () =>
      sweepTargetOptions.map((option) => ({
        value: option.value,
        label: option.label,
        description: option.unit ? `Schema unit · ${option.unit}` : undefined,
        group: option.source === "schema" ? "Circuit Schema" : "Source Controls",
      })),
    [sweepTargetOptions],
  );
  const ptcPortOptions = useMemo(
    () => deriveSimulationPtcPortOptions(activeDefinition?.source_text ?? null),
    [activeDefinition?.source_text],
  );
  const sourcePortSelectOptions = useMemo<readonly AppSelectOption[]>(
    () =>
      ptcPortOptions.map((port) => ({
        value: port.value,
        label: port.label,
      })),
    [ptcPortOptions],
  );
  const initialPostProcessingStepContext = useMemo(
    () => derivePostProcessingStepContext(sourcePortSelectOptions, []),
    [sourcePortSelectOptions],
  );
  const postProcessingPipelineContext = useMemo(
    () => derivePostProcessingStepContext(sourcePortSelectOptions, postProcessingSteps),
    [postProcessingSteps, sourcePortSelectOptions],
  );
  const postProcessingStepContexts = useMemo(
    () =>
      new Map(
        postProcessingSteps.map((step) => [
          step.id,
          derivePostProcessingStepContext(sourcePortSelectOptions, postProcessingSteps, step.id),
        ]),
      ),
    [postProcessingSteps, sourcePortSelectOptions],
  );
  const postProcessingStepTypeOptions = useMemo<readonly AppSelectOption[]>(
    () => [
      {
        value: "coordinate_transform",
        label: "Coordinate Transformation",
        disabled: !isPostProcessingStepTypeAvailable(
          "coordinate_transform",
          postProcessingPipelineContext,
        ),
      },
      {
        value: "kron_reduction",
        label: "Kron Reduction",
        disabled: !isPostProcessingStepTypeAvailable(
          "kron_reduction",
          postProcessingPipelineContext,
        ),
      },
    ],
    [postProcessingPipelineContext],
  );
  const selectedPtcPorts = useMemo(
    () => new Set(parseCommaSeparatedStringValues(selectedPtcPortsValue)),
    [selectedPtcPortsValue],
  );
  const displayedSimulationStageTask = attachedSimulationStageTask ?? latestSimulationStageTask;
  const displayedSimulationTaskDetail =
    attachedSimulationTaskDetail ?? latestSimulationTaskDetail;
  const savedSetups = useSavedSimulationSetups({
    form,
    workflowContextResetKey,
    resolvedDefinitionId,
    selectedDefinitionName: selectedDefinitionDisplay?.name ?? null,
    displayedSimulationTaskDetail,
    officialExamplePreset,
  });
  const {
    activeSavedSetup,
    visibleSavedSetups,
    isSaveDialogOpen,
    isManageDialogOpen,
    saveDialogMode,
    saveDialogOverwriteTargetId,
    saveSetupNameDraft,
    savedSetupFeedback,
    simulationSetupAuthorityPresentation,
    restoreSimulationSetupFromCurrentSource,
    applySavedSetup,
    applyOfficialExamplePreset,
    deleteSavedSetup,
    openSaveDialog,
    openManageDialog,
    openSaveAsNewFromManage,
    submitSaveDialog,
    setSaveSetupNameDraft,
    setIsSaveDialogOpen,
    setIsManageDialogOpen,
    resetForWorkflowContext,
  } = savedSetups;
  const {
    taskMutationStatus,
    simulationSetupBuildError,
    postProcessingBuildError,
    clearTaskMutationStatus,
    clearBuildErrors,
    submit,
  } = useSimulationSubmission({
    form,
    postProcessingSteps,
    resolvedDefinitionId,
    selectedDefinitionName: selectedDefinitionSummary?.name ?? null,
    activeDefinitionName: activeDefinition?.name ?? null,
    displayedSimulationStageTaskId: displayedSimulationStageTask?.taskId ?? null,
    onTaskAttached: taskAttachment.attachTask,
  });
  const simulationSetupBlockedReason =
    resolvedDefinitionId === null
      ? "Select a definition before submitting a simulation run."
      : !activeDatasetState.activeDataset
        ? "Attach an active dataset in the shell before submitting a simulation run."
        : !session?.canSubmitTasks
          ? "The current session does not allow submitting simulation tasks."
          : null;
  const displayedSimulationStageAuthority = resolveAuthoritativeSimulationTaskSummary(
    displayedSimulationStageTask,
    displayedSimulationTaskDetail,
  );
  const latestPostProcessingStageAuthority = resolveAuthoritativeSimulationTaskSummary(
    latestPostProcessingTask,
    latestPostProcessingTaskDetail,
  );
  const simulationResultReady =
    displayedSimulationTaskDetail !== undefined
      ? hasSimulationTaskResult(displayedSimulationTaskDetail)
      : displayedSimulationStageAuthority?.resultAvailability === "ready";
  const postProcessingSetupBlockedReason =
    simulationSetupBlockedReason ??
    (!simulationResultReady ? "Simulation result required before post-processing can start." : null);
  const simulationSetupState = resolveSetupStageState({
    stageLabel: "Simulation",
    blockedReason: simulationSetupBlockedReason,
    latestTask: displayedSimulationStageAuthority,
  });
  const simulationResultState = resolveResultStageState({
    stageLabel: "Simulation Result",
    latestTask: displayedSimulationStageAuthority,
    detail: displayedSimulationTaskDetail,
    hasResult: simulationResultReady,
  });
  const postProcessingSetupState = resolveSetupStageState({
    stageLabel: "Post Processing",
    blockedReason: postProcessingSetupBlockedReason,
    latestTask: latestPostProcessingStageAuthority,
  });
  const postProcessingResultReady =
    latestPostProcessingTaskDetail !== undefined
      ? hasSimulationTaskResult(latestPostProcessingTaskDetail)
      : latestPostProcessingStageAuthority?.resultAvailability === "ready";
  const postProcessingResultState = resolveResultStageState({
    stageLabel: "Post Processing Result",
    blockedReason: !simulationResultReady
      ? "Post-processing result stays blocked until a simulation result is available."
      : null,
    latestTask: latestPostProcessingStageAuthority,
    detail: latestPostProcessingTaskDetail,
    hasResult: postProcessingResultReady,
  });
  const postProcessingResultSummary = summarizeSimulationTaskResults(
    latestPostProcessingTaskDetail,
  );
  const explicitUpstreamSimulationTaskId = resolvePostProcessingUpstreamTaskId(
    latestPostProcessingTaskDetail,
  );
  const postProcessingStepCount =
    latestPostProcessingTaskDetail?.postProcessingSetup?.operations.length ?? postProcessingSteps.length;

  function appendPostProcessingStep(stepType: PostProcessingStepType) {
    if (!isPostProcessingStepTypeAvailable(stepType, postProcessingPipelineContext)) {
      return;
    }

    clearBuildErrors();
    setPostProcessingSteps((current) => [
      ...current,
      createPostProcessingStep(stepType, postProcessingPipelineContext),
    ]);
  }

  function removePostProcessingStep(stepId: string) {
    clearBuildErrors();
    setPostProcessingSteps((current) => current.filter((step) => step.id !== stepId));
  }

  function updateCoordinateTransformStep(
    stepId: string,
    field: "portA" | "portB",
    value: string,
  ) {
    clearBuildErrors();
    setPostProcessingSteps((current) =>
      current.map((step) =>
        step.id === stepId && step.type === "coordinate_transform"
          ? { ...step, [field]: value }
          : step,
      ),
    );
  }

  function toggleKronReductionKeepLabel(stepId: string, label: string) {
    clearBuildErrors();
    setPostProcessingSteps((current) =>
      current.map((step) => {
        if (step.id !== stepId || step.type !== "kron_reduction") {
          return step;
        }

        const context =
          postProcessingStepContexts.get(stepId) ?? initialPostProcessingStepContext;
        const selected = new Set(step.keepLabels);
        if (selected.has(label)) {
          selected.delete(label);
        } else {
          selected.add(label);
        }

        return {
          ...step,
          keepLabels: context.basisOptions
            .map((option) => option.value)
            .filter((value) => selected.has(value)),
        };
      }),
    );
  }

  function updatePostProcessingStepType(stepId: string, nextType: PostProcessingStepType) {
    const context =
      postProcessingStepContexts.get(stepId) ?? initialPostProcessingStepContext;
    if (!isPostProcessingStepTypeAvailable(nextType, context)) {
      return;
    }

    clearBuildErrors();
    setPostProcessingSteps((current) =>
      current.map((step) =>
        step.id === stepId
          ? createPostProcessingStep(nextType, context, step.id)
          : step,
      ),
    );
  }

  useEffect(() => {
    if (sweepTargetOptions.length === 0) {
      if (parameterSweepEnabled) {
        form.setValue("simulationParameterSweepEnabled", false, { shouldDirty: true });
      }
      return;
    }

    const currentAxes = form.getValues("simulationParameterSweepAxes");
    currentAxes.forEach((axis, index) => {
      const matchedOption =
        sweepTargetOptionsByValue.get(axis.parameter) ?? sweepTargetOptions[0] ?? null;
      if (!matchedOption) {
        return;
      }

      if (axis.parameter !== matchedOption.value) {
        form.setValue(`simulationParameterSweepAxes.${index}.parameter`, matchedOption.value, {
          shouldDirty: false,
        });
      }
      if (axis.unit !== (matchedOption.unit ?? "")) {
        form.setValue(`simulationParameterSweepAxes.${index}.unit`, matchedOption.unit ?? "", {
          shouldDirty: false,
        });
      }
    });
  }, [
    form,
    parameterSweepEnabled,
    sweepTargetOptions,
    sweepTargetOptionsByValue,
  ]);

  useEffect(() => {
    if (ptcPortOptions.length === 0) {
      if (ptcEnabled) {
        form.setValue("simulationPtcEnabled", false, { shouldDirty: true });
      }
      if (selectedPtcPortsValue) {
        form.setValue("simulationPtcCompensatePorts", "", { shouldDirty: false });
      }
      return;
    }

    const allowedPorts = new Set(ptcPortOptions.map((option) => option.value));
    const filteredPorts = parseCommaSeparatedStringValues(selectedPtcPortsValue).filter((port) =>
      allowedPorts.has(port),
    );
    const normalizedSelection = filteredPorts.join(", ");
    if (normalizedSelection !== selectedPtcPortsValue) {
      form.setValue("simulationPtcCompensatePorts", normalizedSelection, { shouldDirty: false });
    }
  }, [form, ptcEnabled, ptcPortOptions, selectedPtcPortsValue]);

  useEffect(() => {
    if (
      !latestPostProcessingTaskDetail?.postProcessingSetup ||
      latestPostProcessingTaskDetail.taskId === hydratedPostTaskId
    ) {
      return;
    }

    setPostProcessingSteps(
      hydratePostProcessingSteps(
        latestPostProcessingTaskDetail.postProcessingSetup,
        sourcePortSelectOptions.map((option) => option.value),
      ),
    );
    setHydratedPostTaskId(latestPostProcessingTaskDetail.taskId);
  }, [form, hydratedPostTaskId, latestPostProcessingTaskDetail, sourcePortSelectOptions]);

  useEffect(() => {
    if (sourcePortSelectOptions.length === 0) {
      setPostProcessingSteps([]);
      return;
    }

    setPostProcessingSteps((current) =>
      current.map((step) =>
        sanitizePostProcessingStep(
          step,
          derivePostProcessingStepContext(sourcePortSelectOptions, current, step.id),
        ),
      ),
    );
  }, [sourcePortSelectOptions]);

  useEffect(() => {
    const preferredOption = postProcessingStepTypeOptions.find(
      (option) => option.value === newPostProcessingStepType,
    );
    if (preferredOption && !preferredOption.disabled) {
      return;
    }

    const firstAvailableOption = postProcessingStepTypeOptions.find((option) => !option.disabled);
    if (firstAvailableOption) {
      setNewPostProcessingStepType(firstAvailableOption.value as PostProcessingStepType);
    }
  }, [newPostProcessingStepType, postProcessingStepTypeOptions]);

  useEffect(() => {
    const previousContextKey = lastWorkflowContextResetKeyRef.current;
    lastWorkflowContextResetKeyRef.current = workflowContextResetKey;
    if (previousContextKey === null || previousContextKey === workflowContextResetKey) {
      return;
    }

    clearTaskMutationStatus();
    clearBuildErrors();
    resetForWorkflowContext();
    setIsAdvancedHbsolveExpanded(false);
    setPostProcessingSteps([]);
    setNewPostProcessingStepType("coordinate_transform");
    setHydratedPostTaskId(null);
    resetAutoRestoreState();
    hasObservedSimulationTaskToastRef.current = false;
    hasObservedPostProcessingTaskToastRef.current = false;
    lastSimulationTaskToastKeyRef.current = null;
    lastPostProcessingTaskToastKeyRef.current = null;

    if (attachedRequestedTaskId !== null) {
      clearRequestedTask();
    }
  }, [
    attachedRequestedTaskId,
    clearBuildErrors,
    clearRequestedTask,
    clearTaskMutationStatus,
    resetAutoRestoreState,
    resetForWorkflowContext,
    workflowContextResetKey,
  ]);

  useEffect(() => {
    if (!taskMutationStatus.message) {
      return;
    }

    if (taskMutationStatus.state !== "error" && taskMutationStatus.state !== "success") {
      return;
    }

    pushToast({
      tone: taskMutationStatus.state === "error" ? "error" : "success",
      title:
        taskMutationStatus.state === "error"
          ? "Run submission failed"
          : "Run submission accepted",
      message: taskMutationStatus.message,
    });
    clearTaskMutationStatus();
  }, [clearTaskMutationStatus, pushToast, taskMutationStatus]);

  useEffect(() => {
    const currentKey = latestSimulationTaskDetail
      ? `${latestSimulationTaskDetail.taskId}:${latestSimulationTaskDetail.status}`
      : null;
    if (!hasObservedSimulationTaskToastRef.current) {
      hasObservedSimulationTaskToastRef.current = true;
      lastSimulationTaskToastKeyRef.current = currentKey;
      return;
    }
    if (!currentKey || currentKey === lastSimulationTaskToastKeyRef.current) {
      return;
    }
    lastSimulationTaskToastKeyRef.current = currentKey;
    if (latestSimulationTaskDetail?.status === "completed") {
      pushToast({
        tone: "success",
        title: "Simulation completed",
        message:
          latestSimulationTaskDetail.progress.summary ??
          `Simulation task #${latestSimulationTaskDetail.taskId} completed.`,
      });
    } else if (latestSimulationTaskDetail?.status === "failed") {
      pushToast({
        tone: "error",
        title: "Simulation failed",
        message:
          latestSimulationTaskDetail.progress.summary ??
          `Simulation task #${latestSimulationTaskDetail.taskId} failed.`,
      });
    }
  }, [latestSimulationTaskDetail, pushToast]);

  useEffect(() => {
    const currentKey = latestPostProcessingTaskDetail
      ? `${latestPostProcessingTaskDetail.taskId}:${latestPostProcessingTaskDetail.status}`
      : null;
    if (!hasObservedPostProcessingTaskToastRef.current) {
      hasObservedPostProcessingTaskToastRef.current = true;
      lastPostProcessingTaskToastKeyRef.current = currentKey;
      return;
    }
    if (!currentKey || currentKey === lastPostProcessingTaskToastKeyRef.current) {
      return;
    }
    lastPostProcessingTaskToastKeyRef.current = currentKey;
    if (latestPostProcessingTaskDetail?.status === "completed") {
      pushToast({
        tone: "success",
        title: "Post-processing completed",
        message:
          latestPostProcessingTaskDetail.progress.summary ??
          `Post-processing task #${latestPostProcessingTaskDetail.taskId} completed.`,
      });
    } else if (latestPostProcessingTaskDetail?.status === "failed") {
      pushToast({
        tone: "error",
        title: "Post-processing failed",
        message:
          latestPostProcessingTaskDetail.progress.summary ??
          `Post-processing task #${latestPostProcessingTaskDetail.taskId} failed.`,
      });
    }
  }, [latestPostProcessingTaskDetail, pushToast]);

  async function handleRefreshWorkflow() {
    setIsRefreshingWorkflow(true);
    try {
      await refreshSimulationWorkflow();
    } finally {
      setIsRefreshingWorkflow(false);
    }
  }

  async function handleSubmit(kind: SimulationStageKind) {
    await submit(kind);
  }

  function handleDefinitionSelectionChange(value: string) {
    clearTaskMutationStatus();
    replaceSearchState({ definitionId: value, taskId: null });
  }

  function handleAddParameterSweepAxis() {
    const fallbackOption = sweepTargetOptions[0];
    parameterSweepFieldArray.append(
      createDefaultSimulationParameterSweepAxis({
        parameter: fallbackOption?.value ?? "",
        unit: fallbackOption?.unit ?? "",
      }),
    );
    clearTaskMutationStatus();
  }

  function handleAddSource() {
    const nextIndex = sourceFieldArray.fields.length + 1;
    sourceFieldArray.append({
      ...createDefaultSimulationSource(),
      sourceId: `src_pump_${nextIndex}`,
      port:
        ptcPortOptions[nextIndex - 1]?.value ??
        ptcPortOptions[0]?.value ??
        `port_${nextIndex}`,
    });
    clearTaskMutationStatus();
  }

  return (
    <div className="space-y-6">
      <SurfaceHeader
        eyebrow="Research Workflow"
        title="Circuit Simulation"
        description="Set up the run, inspect the result, and carry useful outputs forward into post processing."
        actions={
          <button
            type="button"
            onClick={() => {
              void handleRefreshWorkflow();
            }}
            disabled={isRefreshingWorkflow}
            className="inline-flex cursor-pointer items-center gap-2 rounded-full border border-border bg-background px-3.5 py-2 text-xs font-medium uppercase tracking-[0.16em] text-foreground transition hover:border-primary/35 hover:bg-primary/10 disabled:cursor-not-allowed disabled:opacity-60"
          >
            <RefreshCcw className={cx("h-3.5 w-3.5", isRefreshingWorkflow && "animate-spin")} />
            Refresh Workflow
          </button>
        }
      />

      {definitionsError ? (
        <StageNotice
          tone="error"
          title="Definition catalog unavailable"
          message={`Unable to load visible definitions. ${definitionsErrorMessage}`}
        />
      ) : null}

      {taskRecovery ? (
        <StageNotice
          tone="warning"
          title={taskRecovery.title}
          message={taskRecovery.message}
          actions={
            latestSimulationTask ? (
              <button
                type="button"
                onClick={() => {
                  attachTask(latestSimulationTask.taskId);
                }}
                className="inline-flex cursor-pointer items-center gap-2 rounded-full border border-border bg-background px-3 py-2 text-xs font-medium text-foreground transition hover:border-primary/35 hover:bg-primary/10"
              >
                Resume Latest Run
              </button>
            ) : null
          }
        />
      ) : null}

      {!taskRecovery &&
      taskConnectionState.hasNewerLatestTask &&
      latestSimulationTask ? (
        <StageNotice
          tone="primary"
          title="Latest task available"
          message={`You are inspecting task #${taskConnectionState.selectedTaskId}, while newer pipeline activity exists on task #${latestSimulationTask.taskId}.`}
          actions={
            <button
              type="button"
              onClick={() => {
                attachTask(latestSimulationTask.taskId);
              }}
              className="inline-flex cursor-pointer items-center gap-2 rounded-full border border-border bg-background px-3 py-2 text-xs font-medium text-foreground transition hover:border-primary/35 hover:bg-primary/10"
            >
              Resume Latest Run
            </button>
          }
        />
      ) : null}

      <div className="space-y-5">
        <SimulationDefinitionContextStage
          activeDefinition={activeDefinition}
          activeDefinitionErrorMessage={activeDefinitionErrorMessage}
          definitionOptions={definitionOptions}
          definitionRecovery={
            definitionRecovery
              ? {
                  tone: definitionRecovery.tone === "warning" ? "warning" : "default",
                  title: definitionRecovery.title,
                  message: definitionRecovery.message,
                }
              : null
          }
          isDefinitionTransitioning={isDefinitionTransitioning}
          isDefinitionsLoading={isDefinitionsLoading}
          resolvedDefinitionId={resolvedDefinitionId}
          selectedDefinitionDisplay={selectedDefinitionDisplay}
          onDefinitionChange={handleDefinitionSelectionChange}
        />

        <SimulationSetupStage
          activeSavedSetup={activeSavedSetup}
          applyOfficialExamplePreset={applyOfficialExamplePreset}
          applySavedSetup={applySavedSetup}
          deleteSavedSetup={deleteSavedSetup}
          displayedSimulationStageAuthority={displayedSimulationStageAuthority}
          displayedSimulationTaskDetail={displayedSimulationTaskDetail}
          form={form}
          harmonicBalanceEnabled={harmonicBalanceEnabled}
          isAdvancedHbsolveExpanded={isAdvancedHbsolveExpanded}
          isManageDialogOpen={isManageDialogOpen}
          isSaveDialogOpen={isSaveDialogOpen}
          officialExamplePreset={officialExamplePreset}
          onAddAxis={handleAddParameterSweepAxis}
          onAddSource={handleAddSource}
          onOpenManageDialog={openManageDialog}
          onOpenSaveDialog={openSaveDialog}
          onSubmit={() => {
            void handleSubmit("simulation");
          }}
          openSaveAsNewFromManage={openSaveAsNewFromManage}
          parameterSweepEnabled={parameterSweepEnabled}
          parameterSweepFieldArray={parameterSweepFieldArray}
          ptcEnabled={ptcEnabled}
          ptcPortOptions={sourcePortSelectOptions}
          resolvedDefinitionId={resolvedDefinitionId}
          resolvedTaskId={resolvedTaskId}
          restoreSimulationSetupFromCurrentSource={restoreSimulationSetupFromCurrentSource}
          saveDialogMode={saveDialogMode}
          saveDialogOverwriteTargetId={saveDialogOverwriteTargetId}
          saveSetupNameDraft={saveSetupNameDraft}
          savedSetupFeedback={savedSetupFeedback}
          selectedDefinitionDisplay={selectedDefinitionDisplay}
          selectedPtcPorts={selectedPtcPorts}
          setIsAdvancedHbsolveExpanded={setIsAdvancedHbsolveExpanded}
          setIsManageDialogOpen={setIsManageDialogOpen}
          setIsSaveDialogOpen={setIsSaveDialogOpen}
          setSaveSetupNameDraft={setSaveSetupNameDraft}
          simulationResultReady={simulationResultReady}
          simulationSetupAuthorityPresentation={simulationSetupAuthorityPresentation}
          simulationSetupBlockedReason={simulationSetupBlockedReason}
          simulationSetupBuildError={simulationSetupBuildError}
          sourceFieldArray={sourceFieldArray}
          sourcePortSelectOptions={sourcePortSelectOptions}
          state={simulationSetupState}
          submitSaveDialog={submitSaveDialog}
          sweepTargetOptions={sweepTargetOptions}
          sweepTargetOptionsByValue={sweepTargetOptionsByValue}
          sweepTargetSelectOptions={sweepTargetSelectOptions}
          taskMutationStatus={taskMutationStatus}
          attachTask={attachTask}
          visibleSavedSetups={visibleSavedSetups}
        />

        <SimulationResultStage
          state={simulationResultState}
          errorMessage={simulationStageErrorMessage}
          displayedSimulationStageAuthority={displayedSimulationStageAuthority}
          displayedSimulationTaskDetail={displayedSimulationTaskDetail}
          attachedSimulationStageTask={attachedSimulationStageTask}
          simulationResultReady={simulationResultReady}
          activeDatasetId={activeDatasetState.activeDataset?.datasetId ?? null}
          resolvedTaskId={resolvedTaskId}
          attachTask={attachTask}
        />

        <PostProcessingSetupStage
          state={postProcessingSetupState}
          blockedReason={postProcessingSetupBlockedReason}
          displayedSimulationStageAuthority={displayedSimulationStageAuthority}
          latestPostProcessingStageAuthority={latestPostProcessingStageAuthority}
          latestPostProcessingTaskDetail={latestPostProcessingTaskDetail}
          postProcessingResultReady={postProcessingResultReady}
          postProcessingSteps={postProcessingSteps}
          postProcessingPipelineContext={postProcessingPipelineContext}
          postProcessingStepContexts={postProcessingStepContexts}
          initialPostProcessingStepContext={initialPostProcessingStepContext}
          newPostProcessingStepType={newPostProcessingStepType}
          setNewPostProcessingStepType={setNewPostProcessingStepType}
          postProcessingStepTypeOptions={postProcessingStepTypeOptions}
          appendPostProcessingStep={appendPostProcessingStep}
          removePostProcessingStep={removePostProcessingStep}
          updateCoordinateTransformStep={updateCoordinateTransformStep}
          toggleKronReductionKeepLabel={toggleKronReductionKeepLabel}
          updatePostProcessingStepType={updatePostProcessingStepType}
          postProcessingBuildError={postProcessingBuildError}
          taskMutationState={taskMutationStatus.state}
          form={form}
          onSubmit={() => {
            void handleSubmit("post_processing");
          }}
          attachTask={attachTask}
          resolvedTaskId={resolvedTaskId}
        />

        <PostProcessingResultStage
          state={postProcessingResultState}
          errorMessage={postProcessingStageErrorMessage}
          latestPostProcessingStageAuthority={latestPostProcessingStageAuthority}
          latestPostProcessingTaskDetail={latestPostProcessingTaskDetail}
          postProcessingResultReady={postProcessingResultReady}
          activeDatasetId={activeDatasetState.activeDataset?.datasetId ?? null}
          explicitUpstreamSimulationTaskId={explicitUpstreamSimulationTaskId}
          displayedSimulationStageAuthority={displayedSimulationStageAuthority}
          postProcessingStepCount={postProcessingStepCount}
          postProcessingResultSummary={postProcessingResultSummary}
          resolvedTaskId={resolvedTaskId}
          attachTask={attachTask}
        />
      </div>
    </div>
  );
}
