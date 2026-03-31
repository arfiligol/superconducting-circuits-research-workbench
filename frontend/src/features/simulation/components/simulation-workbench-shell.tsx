"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { zodResolver } from "@hookform/resolvers/zod";
import { EditorState } from "@codemirror/state";
import { json } from "@codemirror/lang-json";
import { EditorView } from "@codemirror/view";
import {
  ChevronDown,
  ChevronRight,
  LoaderCircle,
  Play,
  Plus,
  RefreshCcw,
  Save,
  Settings2,
  Trash2,
  WandSparkles,
} from "lucide-react";
import { useSearchParams } from "next/navigation";
import { useFieldArray, useForm } from "react-hook-form";

import { PostProcessingResultStage } from "@/features/simulation/components/post-processing-result-stage";
import { PostProcessingSetupStage } from "@/features/simulation/components/post-processing-setup-stage";
import { SimulationResultStage } from "@/features/simulation/components/simulation-result-stage";
import {
  CompactField,
  DraftOnlyBadge,
  OverlayDialog,
  ReadOnlyCodeSurface,
  SetupInputField,
  SetupSection,
  SetupSlideToggle,
  SetupTextInput,
  StageNotice,
  StageTaskActions,
  SummaryCard,
  WorkflowStageSection,
} from "@/features/simulation/components/simulation-workbench-stage-kit";
import { useSavedSimulationSetups } from "@/features/simulation/hooks/use-saved-simulation-setups";
import { useSimulationSubmission } from "@/features/simulation/hooks/use-simulation-submission";
import { useSimulationTaskAttachment } from "@/features/simulation/hooks/use-simulation-task-attachment";
import { useSimulationWorkflowData } from "@/features/simulation/hooks/use-simulation-workflow-data";
import { parseSimulationDefinitionIdParam } from "@/features/simulation/lib/definition-id";
import { resolveOfficialSimulationExamplePreset } from "@/features/simulation/lib/official-example";
import {
  buildSchemaIdentityDescription,
  formatSchemaIdLabel,
} from "@/features/circuit-definition-editor/lib/schema-identity";
import {
  createPostProcessingStep,
  derivePostProcessingStepContext,
  isPostProcessingStepTypeAvailable,
  normalizePostProcessingBasisLabel,
  parsePostProcessingPortNumber,
  sanitizePostProcessingStep,
  type PostProcessingStepDraft,
  type PostProcessingStepType,
} from "@/features/simulation/lib/post-processing-basis";
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
  taskStatusTone,
} from "@/features/simulation/lib/stage-state";
import {
  formatSimulationTaskStatusLabel,
  hasSimulationTaskResult,
  resolveAuthoritativeSimulationTaskSummary,
  resolvePostProcessingUpstreamTaskId,
  resolveSimulationSelectionRecovery,
  summarizeSimulationTaskResults,
  type SimulationStageKind,
} from "@/features/simulation/lib/workflow";
import {
  AppInlineSelect,
  AppSelectField,
  type AppSelectOption,
} from "@/features/shared/components/app-select";
import { AppNumberInput } from "@/features/shared/components/app-number-input";
import {
  SurfaceHeader,
  SurfacePanel,
  SurfaceTag,
  cx,
} from "@/features/shared/components/surface-kit";
import { ApiError } from "@/lib/api/client";
import { useAppToasts } from "@/lib/app-state";
import type {
  PostProcessingSetup,
  TaskDetail,
  TaskSummary,
} from "@/lib/api/tasks";

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

function formatCodeValue(value: string | null | undefined, fallback: string) {
  const trimmed = value?.trim();
  if (!trimmed) {
    return fallback;
  }

  try {
    return JSON.stringify(JSON.parse(trimmed), null, 2);
  } catch {
    return trimmed;
  }
}

function formatPostProcessingStepLabel(stepType: PostProcessingStepType) {
  return stepType === "coordinate_transform" ? "Coordinate Transformation" : "Kron Reduction";
}

function buildPostProcessingOperationDraft(step: PostProcessingStepDraft) {
  if (step.type === "kron_reduction") {
    const keepLabels = Array.from(
      new Set(step.keepLabels.map(normalizePostProcessingBasisLabel)),
    );
    if (keepLabels.length === 0) {
      throw new Error("Kron Reduction requires at least one kept port.");
    }

    return {
      operation: "kron_reduction",
      enabled: true,
      config: {
        keep_labels: keepLabels,
      },
    };
  }

  const portA = parsePostProcessingPortNumber(step.portA);
  const portB = parsePostProcessingPortNumber(step.portB);
  if (portA === null || portB === null) {
    throw new Error("Coordinate Transformation requires two valid ports.");
  }
  if (portA === portB) {
    throw new Error("Coordinate Transformation requires two different ports.");
  }

  return {
    operation: "coordinate_transform",
    enabled: true,
    config: {
      template: "cm_dm",
      weight_mode: "auto",
      alpha: 0.5,
      beta: 0.5,
      port_a: portA,
      port_b: portB,
    },
  };
}

function buildPostProcessingSetupDraft(
  steps: readonly PostProcessingStepDraft[],
) {
  const operations = steps.map(buildPostProcessingOperationDraft);

  return {
    operations,
  };
}

function hydratePostProcessingSteps(
  setup: PostProcessingSetup,
  portOptions: readonly AppSelectOption[],
): readonly PostProcessingStepDraft[] {
  const hydratedSteps: PostProcessingStepDraft[] = [];

  setup.operations.forEach((operation, index) => {
    if (operation.operation === "kron_reduction") {
      const keepLabels = Array.isArray(operation.config.keep_labels)
        ? operation.config.keep_labels
            .map((label) => normalizePostProcessingBasisLabel(String(label)))
        : [];
      hydratedSteps.push({
        id: `post-step:hydrated-kron-${index}`,
        type: "kron_reduction",
        keepLabels,
      });
      return;
    }

    if (operation.operation === "coordinate_transform") {
      const rawPortA =
        typeof operation.config.port_a === "number"
          ? `port_${operation.config.port_a}`
          : portOptions[0]?.value ?? "port_1";
      const rawPortB =
        typeof operation.config.port_b === "number"
          ? `port_${operation.config.port_b}`
          : portOptions[1]?.value ?? rawPortA;
      hydratedSteps.push({
        id: `post-step:hydrated-transform-${index}`,
        type: "coordinate_transform",
        portA: rawPortA,
        portB: rawPortB,
      });
    }
  });

  return hydratedSteps;
}

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
  const formattedExpandedNetlist = useMemo(() => {
    const fallback = "// Expanded netlist is loading for the selected definition.";
    const normalizedOutput = activeDefinition?.normalized_output?.trim();
    if (!normalizedOutput) {
      return fallback;
    }

    try {
      const parsed = JSON.parse(normalizedOutput) as Record<string, unknown>;
      const expanded = parsed?.expanded;

      if (typeof expanded === "string") {
        return expanded.trim() || fallback;
      }

      if (expanded && typeof expanded === "object") {
        return JSON.stringify(expanded, null, 2);
      }

      return formatCodeValue(normalizedOutput, fallback);
    } catch {
      return normalizedOutput;
    }
  }, [activeDefinition]);
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
    buildPostProcessingSetupDraft,
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
        sourcePortSelectOptions,
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
        <WorkflowStageSection
          step={1}
          title="Definition / Netlist Context"
          description="Select the definition and inspect the expanded netlist before launching a run."
          status={{
            label: activeDefinition ? "Ready" : isDefinitionsLoading ? "Loading" : "Blocked",
            tone: activeDefinition ? "success" : isDefinitionsLoading ? "primary" : "warning",
            message: activeDefinition
              ? "Definition context is ready."
              : "Select a visible definition first.",
          }}
        >
          {definitionRecovery ? (
            <StageNotice
              tone={definitionRecovery.tone === "warning" ? "warning" : "default"}
              title={definitionRecovery.title}
              message={definitionRecovery.message}
            />
          ) : null}

          {activeDefinitionError ? (
            <StageNotice
              tone="error"
              title="Definition detail unavailable"
              message={`Unable to load definition detail. ${activeDefinitionErrorMessage}`}
            />
          ) : null}

          <div className="space-y-4">
            <AppSelectField
              label="Selected Definition"
              value={resolvedDefinitionId !== null ? String(resolvedDefinitionId) : ""}
              onChange={(value) => {
                clearTaskMutationStatus();
                replaceSearchState({ definitionId: value, taskId: null });
              }}
              options={definitionOptions}
              placeholder={
                selectedDefinitionDisplay
                  ? selectedDefinitionDisplay.name
                  : isDefinitionsLoading
                    ? "Loading definitions"
                    : definitions?.length
                      ? "Select a definition"
                      : "No definitions available"
              }
              disabled={definitionOptions.length === 0}
            />

            <ReadOnlyCodeSurface
              label="Expanded Netlist"
              value={formattedExpandedNetlist}
              height="320px"
            />
          </div>

          {isDefinitionTransitioning ? (
            <div className="flex items-center gap-3 rounded-[0.95rem] border border-border bg-surface px-4 py-4 text-sm text-muted-foreground">
              <LoaderCircle className="h-4 w-4 animate-spin" />
              Refreshing definition context...
            </div>
          ) : null}
        </WorkflowStageSection>

        <WorkflowStageSection
          step={2}
          title="Simulation Setup"
          description="Configure the runnable simulation setup in six focused sections."
          status={simulationSetupState}
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
                onClick={() => {
                  openManageDialog();
                }}
                disabled={resolvedDefinitionId === null}
                className="inline-flex cursor-pointer items-center gap-2 rounded-full border border-border bg-background px-3 py-2 text-xs font-medium text-foreground transition hover:border-primary/35 hover:bg-primary/10 disabled:cursor-not-allowed disabled:opacity-60"
              >
                <Settings2 className="h-3.5 w-3.5" />
                Manage
              </button>
              <button
                type="button"
                onClick={openSaveDialog}
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
                    if (
                      nextChecked &&
                      parameterSweepFieldArray.fields.length === 0 &&
                      sweepTargetOptions.length > 0
                    ) {
                      const fallbackOption = sweepTargetOptions[0];
                      parameterSweepFieldArray.append(
                        createDefaultSimulationParameterSweepAxis({
                          parameter: fallbackOption?.value ?? "",
                          unit: fallbackOption?.unit ?? "",
                        }),
                      );
                    }
                  }}
                />
              </div>
              <div className="flex flex-wrap items-center gap-2">
                <button
                  type="button"
                  onClick={() => {
                    const fallbackOption = sweepTargetOptions[0];
                    parameterSweepFieldArray.append(
                      createDefaultSimulationParameterSweepAxis({
                        parameter: fallbackOption?.value ?? "",
                        unit: fallbackOption?.unit ?? "",
                      }),
                    );
                    clearTaskMutationStatus();
                  }}
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
                onClick={() => {
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
                }}
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
                  form.setValue("simulationPtcMode", defaultRequestValues.simulationPtcMode, {
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
                  <>
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
                  </>
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
            onClick={() => {
              void handleSubmit("simulation");
            }}
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
                    {attachedSimulationStageTask ? "Attached Simulation Run" : "Latest Simulation Run"}
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
              onClick={() => {
                openSaveAsNewFromManage();
              }}
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
    </div>
  );
}
