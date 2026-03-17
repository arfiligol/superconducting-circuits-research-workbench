"use client";

import { useEffect, useMemo, useState, useTransition } from "react";
import { zodResolver } from "@hookform/resolvers/zod";
import { EditorState } from "@codemirror/state";
import { json } from "@codemirror/lang-json";
import { EditorView } from "@codemirror/view";
import {
  ArrowUpRight,
  ChevronDown,
  ChevronRight,
  FileCode2,
  LoaderCircle,
  Play,
  Plus,
  RefreshCcw,
  Trash2,
  WandSparkles,
  Workflow,
} from "lucide-react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import CodeMirror from "@uiw/react-codemirror";
import { useFieldArray, useForm } from "react-hook-form";
import { z } from "zod";

import { useSimulationWorkflowData } from "@/features/simulation/hooks/use-simulation-workflow-data";
import { parseSimulationDefinitionIdParam } from "@/features/simulation/lib/definition-id";
import {
  buildSimulationSetupDraft,
  buildSimulationSetupFormValuesFromPersistedSetup,
  createDefaultSimulationParameterSweepAxis,
  createDefaultSimulationSource,
  defaultSimulationSetupFormValues,
  parseCommaSeparatedStringValues,
  simulationSetupFormSchema,
} from "@/features/simulation/lib/setup-form";
import {
  buildSimulationRequestSummary,
  formatSimulationTaskStatusLabel,
  hasSimulationTaskResult,
  resolvePostProcessingUpstreamTaskId,
  resolveSimulationSelectionRecovery,
  summarizeSimulationTaskResults,
} from "@/features/simulation/lib/workflow";
import { AppSelectField } from "@/features/shared/components/app-select";
import {
  SurfaceHeader,
  SurfacePanel,
  SurfaceTag,
  cx,
  resolveSurfaceInsetToneClass,
} from "@/features/shared/components/surface-kit";
import {
  requestOpenGlobalContext,
  resolveShellTaskHref,
} from "@/components/layout/workspace-shell-contract";
import { ApiError } from "@/lib/api/client";
import type { TaskDetail, TaskExecutionStatus, TaskSummary } from "@/lib/api/tasks";
import {
  resolveTaskConnectionState,
  resolveTaskRecoveryNotice,
  summarizeTaskContextBinding,
} from "@/lib/task-surface";
import { vsCodeDarkEditorTheme } from "@/lib/codemirror-theme";

const simulationRequestSchema = simulationSetupFormSchema.extend({
  simulationNote: z.string().trim().max(180, "Keep the request note within 180 characters."),
  postProcessingNote: z
    .string()
    .trim()
    .max(180, "Keep the request note within 180 characters."),
  postOutputView: z.string().trim().min(1, "Output view is required."),
  postSelectionTraceFamily: z.string().trim().min(1, "Trace family is required."),
  postSelectionRepresentation: z.string().trim().min(1, "Representation is required."),
  postSelectionDesignId: z.string().trim(),
  postSelectionTraceIds: z.string().trim(),
  postOperationName: z.string().trim().min(1, "Operation name is required."),
  postOperationEnabled: z.boolean(),
  postOperationConfigJson: z.string().trim().min(1, "Operation config JSON is required."),
});

type SimulationRequestValues = z.infer<typeof simulationRequestSchema>;

const defaultRequestValues: SimulationRequestValues = {
  ...defaultSimulationSetupFormValues,
  simulationNote: "",
  postProcessingNote: "",
  postOutputView: "table",
  postSelectionTraceFamily: "y_matrix",
  postSelectionRepresentation: "imaginary",
  postSelectionDesignId: "",
  postSelectionTraceIds: "",
  postOperationName: "normalize",
  postOperationEnabled: true,
  postOperationConfigJson: "{}",
};

type StageTone = "default" | "primary" | "success" | "warning" | "error";

type WorkflowStageState = Readonly<{
  label: string;
  tone: StageTone;
  message: string;
}>;

const simulationStageFieldNames = [
  "simulationNote",
  "simulationStartGhz",
  "simulationStopGhz",
  "simulationPointCount",
  "simulationSpacing",
  "simulationParameterSweepEnabled",
  "simulationParameterSweepAxes",
  "simulationSolverFamily",
  "simulationMaxIterations",
  "simulationConvergenceTolerance",
  "simulationHarmonicBalanceEnabled",
  "simulationHarmonicCount",
  "simulationOversampleFactor",
  "simulationSources",
] as const;

function buildSimulationSearchHref(
  pathname: string,
  searchParamsValue: string,
  updates: Readonly<Record<string, string | null>>,
) {
  const params = new URLSearchParams(searchParamsValue);

  for (const [key, value] of Object.entries(updates)) {
    if (value === null) {
      params.delete(key);
    } else {
      params.set(key, value);
    }
  }

  const nextSearch = params.toString();
  return nextSearch ? `${pathname}?${nextSearch}` : pathname;
}

function parseTaskIdParam(value: string | null): number | null {
  if (!value) {
    return null;
  }

  const parsedValue = Number.parseInt(value, 10);
  return Number.isFinite(parsedValue) ? parsedValue : null;
}

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

function taskStatusTone(status: TaskExecutionStatus): StageTone {
  if (status === "completed") {
    return "success";
  }

  if (
    status === "queued" ||
    status === "dispatching" ||
    status === "running" ||
    status === "cancellation_requested" ||
    status === "cancelling" ||
    status === "termination_requested"
  ) {
    return "primary";
  }

  if (status === "failed" || status === "cancelled" || status === "terminated") {
    return "warning";
  }

  return "default";
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

function buildPostProcessingSetupDraft(values: SimulationRequestValues) {
  let config: Record<string, unknown> = {};
  try {
    const parsed = JSON.parse(values.postOperationConfigJson);
    if (parsed && typeof parsed === "object" && !Array.isArray(parsed)) {
      config = parsed as Record<string, unknown>;
    } else {
      throw new Error("Operation config must be a JSON object.");
    }
  } catch {
    throw new Error("Operation config must be valid JSON object text.");
  }

  return {
    output_view: values.postOutputView.trim(),
    selections: [
      {
        trace_family: values.postSelectionTraceFamily.trim(),
        representation: values.postSelectionRepresentation.trim(),
        design_id: values.postSelectionDesignId.trim() || null,
        trace_ids: parseCommaSeparatedStringValues(values.postSelectionTraceIds),
      },
    ],
    operations: [
      {
        operation: values.postOperationName.trim(),
        enabled: values.postOperationEnabled,
        config,
      },
    ],
  };
}

function resolveSetupStageState(input: Readonly<{
  stageLabel: string;
  blockedReason: string | null;
  latestTask: TaskSummary | undefined;
}>): WorkflowStageState {
  if (input.blockedReason) {
    return {
      label: "Blocked",
      tone: "warning",
      message: input.blockedReason,
    };
  }

  if (!input.latestTask) {
    return {
      label: "Not started",
      tone: "default",
      message: `${input.stageLabel} has not been submitted yet.`,
    };
  }

  if (input.latestTask.status === "completed") {
    return {
      label: "Completed",
      tone: "success",
      message: `Latest ${input.stageLabel.toLowerCase()} run completed successfully. You can review the result or launch another run.`,
    };
  }

  const statusLabel = formatSimulationTaskStatusLabel(input.latestTask.status);
  return {
    label: statusLabel,
    tone: taskStatusTone(input.latestTask.status),
    message: `Latest ${input.stageLabel.toLowerCase()} task #${input.latestTask.taskId} is ${statusLabel.toLowerCase()}.`,
  };
}

function resolveResultStageState(input: Readonly<{
  stageLabel: string;
  blockedReason?: string | null;
  latestTask: TaskSummary | undefined;
  detail: TaskDetail | undefined;
  hasResult: boolean;
}>): WorkflowStageState {
  if (input.blockedReason) {
    return {
      label: "Blocked",
      tone: "warning",
      message: input.blockedReason,
    };
  }

  if (!input.latestTask) {
    return {
      label: "Not started",
      tone: "default",
      message: `${input.stageLabel} is still waiting for its first run.`,
    };
  }

  if (input.latestTask.status === "completed") {
    if (input.hasResult) {
      return {
        label: "Completed",
        tone: "success",
        message: `Latest ${input.stageLabel.toLowerCase()} output is ready to inspect.`,
      };
    }

    return {
      label: "Completed",
      tone: "warning",
      message: `Latest ${input.stageLabel.toLowerCase()} task completed, but persisted outputs are not available yet.`,
    };
  }

  const statusLabel = formatSimulationTaskStatusLabel(input.latestTask.status);
  const progressSummary =
    input.detail?.progress.summary ?? input.detail?.dispatch?.status ?? input.latestTask.summary;

  return {
    label: statusLabel,
    tone: taskStatusTone(input.latestTask.status),
    message: `Latest ${input.stageLabel.toLowerCase()} task #${input.latestTask.taskId} is ${statusLabel.toLowerCase()}. ${progressSummary}`,
  };
}

function SummaryCard({
  label,
  value,
  detail,
}: Readonly<{
  label: string;
  value: string;
  detail?: string;
}>) {
  return (
    <div className="rounded-[0.9rem] border border-border bg-surface px-4 py-3">
      <p className="text-[11px] uppercase tracking-[0.16em] text-muted-foreground">{label}</p>
      <p className="mt-2 text-sm font-semibold text-foreground">{value}</p>
      {detail ? <p className="mt-2 text-xs leading-5 text-muted-foreground">{detail}</p> : null}
    </div>
  );
}

function StageNotice({
  tone,
  title,
  message,
  actions,
}: Readonly<{
  tone: StageTone;
  title: string;
  message: string;
  actions?: React.ReactNode;
}>) {
  const toneClass =
    tone === "error"
      ? resolveSurfaceInsetToneClass("error")
      : tone === "warning"
        ? resolveSurfaceInsetToneClass("warning")
        : tone === "success"
          ? resolveSurfaceInsetToneClass("success")
          : tone === "primary"
            ? resolveSurfaceInsetToneClass("primary")
            : "border-border bg-surface text-foreground";

  return (
    <div className={cx("rounded-[0.95rem] border px-4 py-4 text-sm", toneClass)}>
      <p className="font-medium text-foreground">{title}</p>
      <p className="mt-2 leading-6">{message}</p>
      {actions ? <div className="mt-4 flex flex-wrap gap-2">{actions}</div> : null}
    </div>
  );
}

function ReadOnlyCodeSurface({
  label,
  detail,
  value,
  height,
}: Readonly<{
  label: string;
  detail: string;
  value: string;
  height: string;
}>) {
  const extensions = useMemo(
    () => [json(), EditorState.readOnly.of(true), EditorView.editable.of(false), vsCodeDarkEditorTheme],
    [],
  );

  return (
    <div className="overflow-hidden rounded-[0.95rem] border border-border bg-background shadow-[0_8px_24px_rgba(15,23,42,0.08)]">
      <div className="flex items-center justify-between border-b border-border bg-surface px-4 py-3">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.16em] text-muted-foreground">
            {label}
          </p>
          <p className="mt-1 text-xs text-muted-foreground">{detail}</p>
        </div>
        <FileCode2 className="h-4 w-4 text-muted-foreground" />
      </div>
      <CodeMirror
        value={value}
        height={height}
        theme="dark"
        editable={false}
        extensions={extensions}
        className="text-sm leading-6"
      />
    </div>
  );
}

function WorkflowStageSection({
  step,
  title,
  description,
  status,
  actions,
  children,
}: Readonly<{
  step: number;
  title: string;
  description: string;
  status: WorkflowStageState;
  actions?: React.ReactNode;
  children: React.ReactNode;
}>) {
  return (
    <section className="rounded-[1.15rem] border border-border bg-card px-5 py-5 shadow-[0_12px_30px_rgba(0,0,0,0.08)]">
      <div className="grid gap-5 lg:grid-cols-[56px_minmax(0,1fr)]">
        <div className="flex lg:justify-center">
          <span className="inline-flex h-11 w-11 items-center justify-center rounded-full border border-primary/20 bg-primary/10 text-sm font-semibold text-primary">
            {step}
          </span>
        </div>
        <div className="min-w-0">
          <div className="flex flex-col gap-3 border-b border-border/80 pb-4 md:flex-row md:items-start md:justify-between">
            <div className="min-w-0">
              <h2 className="text-base font-semibold text-foreground">{title}</h2>
              <p className="mt-2 max-w-3xl text-sm leading-6 text-muted-foreground">
                {description}
              </p>
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <SurfaceTag tone={status.tone}>{status.label}</SurfaceTag>
              {actions}
            </div>
          </div>
          <div className="mt-4 space-y-4">{children}</div>
        </div>
      </div>
    </section>
  );
}

function SetupSection({
  title,
  description,
  status,
  actions,
  children,
}: Readonly<{
  title: string;
  description: string;
  status?: React.ReactNode;
  actions?: React.ReactNode;
  children: React.ReactNode;
}>) {
  return (
    <section className="rounded-[1rem] border border-border bg-surface px-4 py-4 shadow-[0_10px_24px_rgba(15,23,42,0.06)]">
      <div className="flex flex-col gap-3 border-b border-border/80 pb-4 md:flex-row md:items-start md:justify-between">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <h3 className="text-sm font-semibold text-foreground">{title}</h3>
            {status}
          </div>
          <p className="mt-2 max-w-3xl text-sm leading-6 text-muted-foreground">{description}</p>
        </div>
        {actions ? <div className="flex flex-wrap gap-2">{actions}</div> : null}
      </div>
      <div className="mt-4 space-y-4">{children}</div>
    </section>
  );
}

function SetupInputField({
  label,
  detail,
  children,
  error,
}: Readonly<{
  label: string;
  detail?: string;
  children: React.ReactNode;
  error?: string;
}>) {
  return (
    <label className="block rounded-[0.95rem] border border-border bg-background px-4 py-3 shadow-[0_1px_0_rgba(255,255,255,0.04)]">
      <span className="text-xs font-semibold uppercase tracking-[0.16em] text-muted-foreground">
        {label}
      </span>
      {detail ? <span className="mt-1 block text-xs leading-5 text-muted-foreground">{detail}</span> : null}
      <div className="mt-3">{children}</div>
      {error ? <p className="mt-2 text-xs text-rose-700 dark:text-rose-300">{error}</p> : null}
    </label>
  );
}

function SetupTextInput(props: Readonly<React.InputHTMLAttributes<HTMLInputElement>>) {
  return (
    <input
      {...props}
      className={cx(
        "w-full rounded-[0.8rem] border border-border bg-surface px-3 py-2.5 text-sm text-foreground outline-none transition placeholder:text-muted-foreground focus:border-primary/45 focus:ring-2 focus:ring-primary/15",
        props.className,
      )}
    />
  );
}

function SetupNumberInput(props: Readonly<React.InputHTMLAttributes<HTMLInputElement>>) {
  return (
    <input
      {...props}
      type="number"
      className={cx(
        "w-full rounded-[0.8rem] border border-border bg-surface px-3 py-2.5 text-sm text-foreground outline-none transition placeholder:text-muted-foreground focus:border-primary/45 focus:ring-2 focus:ring-primary/15 disabled:opacity-60",
        props.className,
      )}
    />
  );
}

function SetupSelect(props: Readonly<React.SelectHTMLAttributes<HTMLSelectElement>>) {
  return (
    <select
      {...props}
      className={cx(
        "w-full rounded-[0.8rem] border border-border bg-surface px-3 py-2.5 text-sm text-foreground outline-none transition focus:border-primary/45 focus:ring-2 focus:ring-primary/15 disabled:opacity-60",
        props.className,
      )}
    />
  );
}

function LocalDraftBadge() {
  return <SurfaceTag tone="warning">Local draft only</SurfaceTag>;
}

function StageTaskActions({
  task,
  resolvedTaskId,
  onViewTask,
  onOpenGlobalContext,
}: Readonly<{
  task: TaskSummary | undefined;
  resolvedTaskId: number | null;
  onViewTask: (taskId: number) => void;
  onOpenGlobalContext: (taskId: number) => void;
}>) {
  if (!task) {
    return null;
  }

  const isAttached = resolvedTaskId === task.taskId;

  return (
    <div className="flex flex-wrap gap-2">
      <button
        type="button"
        onClick={() => {
          onViewTask(task.taskId);
        }}
        className="inline-flex cursor-pointer items-center gap-2 rounded-full border border-border bg-background px-3 py-2 text-xs font-medium text-foreground transition hover:border-primary/35 hover:bg-primary/10"
      >
        View Task
      </button>
      {!isAttached ? (
        <button
          type="button"
          onClick={() => {
            onViewTask(task.taskId);
          }}
          className="inline-flex cursor-pointer items-center gap-2 rounded-full border border-border bg-background px-3 py-2 text-xs font-medium text-foreground transition hover:border-primary/35 hover:bg-primary/10"
        >
          Resume Latest Run
        </button>
      ) : null}
      <button
        type="button"
        onClick={() => {
          onOpenGlobalContext(task.taskId);
        }}
        className="inline-flex cursor-pointer items-center gap-2 rounded-full border border-border bg-background px-3 py-2 text-xs font-medium text-foreground transition hover:border-primary/35 hover:bg-primary/10"
      >
        Open in Global Context
      </button>
    </div>
  );
}

export function SimulationWorkbenchShell() {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const [, startTransition] = useTransition();
  const [isRefreshingWorkflow, setIsRefreshingWorkflow] = useState(false);
  const [isAdvancedHbsolveExpanded, setIsAdvancedHbsolveExpanded] = useState(false);
  const [simulationSetupBuildError, setSimulationSetupBuildError] = useState<string | null>(null);

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
  const [hydratedSimulationTaskId, setHydratedSimulationTaskId] = useState<number | null>(null);
  const [hydratedPostTaskId, setHydratedPostTaskId] = useState<number | null>(null);
  const parameterSweepEnabled = form.watch("simulationParameterSweepEnabled");
  const harmonicBalanceEnabled = form.watch("simulationHarmonicBalanceEnabled");
  const ptcEnabled = form.watch("simulationPtcEnabled");
  const ptcMode = form.watch("simulationPtcMode");

  const requestedDefinitionId = searchParams.get("definitionId");
  const requestedTaskId = parseTaskIdParam(searchParams.get("taskId"));
  const rawDefinitionId = parseSimulationDefinitionIdParam(requestedDefinitionId);
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
    latestSimulationTaskError,
    latestPostProcessingTask,
    latestPostProcessingTaskDetail,
    latestPostProcessingTaskError,
    resolvedTaskId,
    activeTask,
    activeTaskError,
    taskMutationStatus,
    submitSimulationTask,
    clearTaskMutationStatus,
    refreshSimulationWorkflow,
  } = useSimulationWorkflowData(rawDefinitionId, requestedTaskId);

  const definitionRecovery = resolveSimulationSelectionRecovery(
    requestedDefinitionId,
    resolvedDefinitionId,
    definitions,
  );
  const taskConnectionState = resolveTaskConnectionState({
    requestedTaskId,
    resolvedTaskId,
    latestTaskId: latestSimulationTask?.taskId ?? null,
    activeTask,
  });
  const taskRecovery = resolveTaskRecoveryNotice(
    requestedTaskId,
    latestSimulationTask?.taskId ?? null,
    activeTaskError,
  );
  const taskContextBinding = summarizeTaskContextBinding({
    task: activeTask,
    activeDatasetId: activeDatasetState.activeDataset?.datasetId ?? null,
    activeDefinitionId: resolvedDefinitionId,
  });
  const definitionsErrorMessage = describeApiError(definitionsError);
  const activeDefinitionErrorMessage = describeApiError(activeDefinitionError);
  const simulationStageErrorMessage = describeApiError(latestSimulationTaskError);
  const postProcessingStageErrorMessage = describeApiError(latestPostProcessingTaskError);
  const definitionOptions = useMemo(
    () =>
      (definitions ?? []).map((definition) => ({
        value: String(definition.definition_id),
        label: definition.name,
        description: `Definition #${definition.definition_id} · ${definition.preview_artifact_count} preview artifacts`,
      })),
    [definitions],
  );
  const formattedExpandedNetlist = useMemo(() => {
    const fallback = "pending_definition";
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
  const simulationRequestPreview = buildSimulationRequestSummary({
    kind: "simulation",
    definitionId: resolvedDefinitionId,
    definitionName: selectedDefinitionSummary?.name ?? null,
    datasetId: activeDatasetState.activeDataset?.datasetId ?? null,
    datasetName: activeDatasetState.activeDataset?.name ?? null,
    note: form.watch("simulationNote"),
  });
  const postProcessingRequestPreview = buildSimulationRequestSummary({
    kind: "post_processing",
    definitionId: resolvedDefinitionId,
    definitionName: selectedDefinitionSummary?.name ?? null,
    datasetId: activeDatasetState.activeDataset?.datasetId ?? null,
    datasetName: activeDatasetState.activeDataset?.name ?? null,
    note: form.watch("postProcessingNote"),
  });
  const simulationSetupBlockedReason =
    resolvedDefinitionId === null
      ? "Select a definition before submitting a simulation run."
      : !activeDatasetState.activeDataset
        ? "Attach an active dataset in the shell before submitting a simulation run."
        : !session?.canSubmitTasks
          ? "The current session does not allow submitting simulation tasks."
          : null;
  const simulationResultReady =
    latestSimulationStageTask?.resultAvailability === "ready" ||
    hasSimulationTaskResult(latestSimulationTaskDetail);
  const postProcessingSetupBlockedReason =
    simulationSetupBlockedReason ??
    (!simulationResultReady
      ? "Simulation result required before post-processing can start."
      : null);
  const simulationSetupState = resolveSetupStageState({
    stageLabel: "Simulation",
    blockedReason: simulationSetupBlockedReason,
    latestTask: latestSimulationStageTask,
  });
  const simulationResultState = resolveResultStageState({
    stageLabel: "Simulation Result",
    latestTask: latestSimulationStageTask,
    detail: latestSimulationTaskDetail,
    hasResult: simulationResultReady,
  });
  const postProcessingSetupState = resolveSetupStageState({
    stageLabel: "Post Processing",
    blockedReason: postProcessingSetupBlockedReason,
    latestTask: latestPostProcessingTask,
  });
  const postProcessingResultReady =
    latestPostProcessingTask?.resultAvailability === "ready" ||
    hasSimulationTaskResult(latestPostProcessingTaskDetail);
  const postProcessingResultState = resolveResultStageState({
    stageLabel: "Post Processing Result",
    blockedReason: !simulationResultReady
      ? "Post-processing result stays blocked until a simulation result is available."
      : null,
    latestTask: latestPostProcessingTask,
    detail: latestPostProcessingTaskDetail,
    hasResult: postProcessingResultReady,
  });
  const simulationResultSummary = summarizeSimulationTaskResults(latestSimulationTaskDetail);
  const postProcessingResultSummary = summarizeSimulationTaskResults(
    latestPostProcessingTaskDetail,
  );
  const explicitUpstreamSimulationTaskId = resolvePostProcessingUpstreamTaskId(
    latestPostProcessingTaskDetail,
  );

  useEffect(() => {
    if (
      !latestSimulationTaskDetail?.simulationSetup ||
      latestSimulationTaskDetail.taskId === hydratedSimulationTaskId
    ) {
      return;
    }

    form.reset(
      buildSimulationSetupFormValuesFromPersistedSetup(
        form.getValues(),
        latestSimulationTaskDetail.simulationSetup,
      ),
      { keepDefaultValues: true },
    );
    setSimulationSetupBuildError(null);
    setHydratedSimulationTaskId(latestSimulationTaskDetail.taskId);
  }, [form, hydratedSimulationTaskId, latestSimulationTaskDetail]);

  useEffect(() => {
    if (
      !latestPostProcessingTaskDetail?.postProcessingSetup ||
      latestPostProcessingTaskDetail.taskId === hydratedPostTaskId
    ) {
      return;
    }

    const setup = latestPostProcessingTaskDetail.postProcessingSetup;
    const firstSelection = setup.selections[0];
    const firstOperation = setup.operations[0];

    form.setValue("postOutputView", setup.outputView, { shouldDirty: false });
    form.setValue("postSelectionTraceFamily", firstSelection?.traceFamily ?? "", {
      shouldDirty: false,
    });
    form.setValue("postSelectionRepresentation", firstSelection?.representation ?? "", {
      shouldDirty: false,
    });
    form.setValue("postSelectionDesignId", firstSelection?.designId ?? "", {
      shouldDirty: false,
    });
    form.setValue("postSelectionTraceIds", firstSelection ? firstSelection.traceIds.join(", ") : "", {
      shouldDirty: false,
    });
    form.setValue("postOperationName", firstOperation?.operation ?? "", { shouldDirty: false });
    form.setValue("postOperationEnabled", firstOperation?.enabled ?? true, {
      shouldDirty: false,
    });
    form.setValue(
      "postOperationConfigJson",
      firstOperation ? JSON.stringify(firstOperation.config, null, 2) : "{}",
      { shouldDirty: false },
    );
    setHydratedPostTaskId(latestPostProcessingTaskDetail.taskId);
  }, [form, hydratedPostTaskId, latestPostProcessingTaskDetail]);

  function replaceSearchState(updates: Readonly<Record<string, string | null>>) {
    startTransition(() => {
      router.replace(buildSimulationSearchHref(pathname, searchParams.toString(), updates), {
        scroll: false,
      });
    });
  }

  useEffect(() => {
    if (resolvedDefinitionId === null || resolvedDefinitionId === rawDefinitionId) {
      return;
    }

    startTransition(() => {
      router.replace(
        buildSimulationSearchHref(pathname, searchParams.toString(), {
          definitionId: String(resolvedDefinitionId),
        }),
        { scroll: false },
      );
    });
  }, [pathname, rawDefinitionId, resolvedDefinitionId, router, searchParams]);

  async function handleRefreshWorkflow() {
    setIsRefreshingWorkflow(true);
    try {
      await refreshSimulationWorkflow();
    } finally {
      setIsRefreshingWorkflow(false);
    }
  }

  async function handleSubmit(kind: "simulation" | "post_processing") {
    const fieldNames =
      kind === "simulation" ? simulationStageFieldNames : ["postProcessingNote"] as const;
    const fieldName = kind === "simulation" ? "simulationNote" : "postProcessingNote";
    const isValid = await form.trigger(fieldNames);
    if (!isValid) {
      return;
    }

    setSimulationSetupBuildError(null);
    const values = form.getValues();
    let simulationSetup = null;
    let postProcessingSetup = null;
    try {
      simulationSetup = kind === "simulation" ? buildSimulationSetupDraft(values) : null;
      postProcessingSetup =
        kind === "post_processing" ? buildPostProcessingSetupDraft(values) : null;
    } catch (error) {
      const message =
        error instanceof Error ? error.message : "Unable to build and submit workflow setup.";
      if (kind === "simulation") {
        setSimulationSetupBuildError(message);
      } else {
        form.setError("postOperationConfigJson", { type: "manual", message });
      }
      return;
    }

    const task = await submitSimulationTask({
      kind,
      note: values[fieldName],
      simulationSetup,
      postProcessingSetup,
      upstreamTaskId: kind === "post_processing" ? (latestSimulationStageTask?.taskId ?? null) : null,
    });

    replaceSearchState({
      definitionId: resolvedDefinitionId !== null ? String(resolvedDefinitionId) : null,
      taskId: String(task.taskId),
    });
  }

  function attachTask(taskId: number) {
    replaceSearchState({
      definitionId: resolvedDefinitionId !== null ? String(resolvedDefinitionId) : null,
      taskId: String(taskId),
    });
  }

  function openTaskInGlobalContext(taskId: number) {
    attachTask(taskId);
    requestOpenGlobalContext("tasks");
  }

  return (
    <div className="space-y-6">
      <SurfaceHeader
        eyebrow="Research Workflow"
        title="Circuit Simulation"
        description="Run simulation and post-processing as a five-stage pipeline. Queue browse, worker health, cancel, terminate, retry, and deep diagnostics stay in Global Context."
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

      <div className="flex flex-wrap gap-2">
        <SurfaceTag tone="primary">
          {selectedDefinitionSummary?.name ?? "Definition pending"}
        </SurfaceTag>
        <SurfaceTag tone={activeDatasetState.activeDataset ? "success" : "warning"}>
          {activeDatasetState.activeDataset?.name ?? "Dataset not attached"}
        </SurfaceTag>
        {resolvedTaskId !== null ? (
          <SurfaceTag tone={taskConnectionState.isAttached ? "success" : "warning"}>
            Task #{resolvedTaskId}
          </SurfaceTag>
        ) : null}
      </div>

      {definitionsError ? (
        <StageNotice
          tone="error"
          title="Definition catalog unavailable"
          message={`Unable to load visible definitions. ${definitionsErrorMessage}`}
        />
      ) : null}

      {taskMutationStatus.message ? (
        <StageNotice
          tone={taskMutationStatus.state === "error" ? "error" : "success"}
          title={
            taskMutationStatus.state === "error"
              ? "Run submission failed"
              : "Run submission accepted"
          }
          message={taskMutationStatus.message}
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

      {!taskRecovery && taskContextBinding?.hasMismatch ? (
        <StageNotice
          tone="warning"
          title={taskContextBinding.title}
          message={taskContextBinding.message}
          actions={
            <>
              {latestSimulationTask && latestSimulationTask.taskId !== activeTask?.taskId ? (
                <button
                  type="button"
                  onClick={() => {
                    attachTask(latestSimulationTask.taskId);
                  }}
                  className="inline-flex cursor-pointer items-center gap-2 rounded-full border border-border bg-background px-3 py-2 text-xs font-medium text-foreground transition hover:border-primary/35 hover:bg-primary/10"
                >
                  Resume Latest Run
                </button>
              ) : null}
              <button
                type="button"
                onClick={() => {
                  requestOpenGlobalContext("tasks");
                }}
                className="inline-flex cursor-pointer items-center gap-2 rounded-full border border-border bg-background px-3 py-2 text-xs font-medium text-foreground transition hover:border-primary/35 hover:bg-primary/10"
              >
                Open in Global Context
              </button>
            </>
          }
        />
      ) : null}

      {!taskRecovery &&
      !taskContextBinding?.hasMismatch &&
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
          description="Confirm the selected definition and review the expanded netlist before launching a new run."
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
            <div className="grid gap-4 xl:grid-cols-[minmax(280px,0.6fr)_minmax(0,1.4fr)]">
              <AppSelectField
                label="Selected Definition"
                value={resolvedDefinitionId !== null ? String(resolvedDefinitionId) : ""}
                onChange={(value) => {
                  clearTaskMutationStatus();
                  replaceSearchState({ definitionId: value, taskId: null });
                }}
                options={definitionOptions}
                placeholder={
                  isDefinitionsLoading
                    ? "Loading definitions"
                    : definitions?.length
                      ? "Select a definition"
                      : "No definitions available"
                }
                disabled={isDefinitionsLoading || definitionOptions.length === 0}
              />

              <div className="rounded-[0.95rem] border border-border bg-surface px-4 py-3">
                <p className="text-xs uppercase tracking-[0.16em] text-muted-foreground">
                  Expanded Netlist
                </p>
                <p className="mt-2 text-sm text-muted-foreground">
                  Read-only normalized output used as the simulation-side netlist reference.
                </p>
              </div>
            </div>

            <ReadOnlyCodeSurface
              label="Expanded Netlist"
              detail="Scrollable read-only expanded netlist for simulation context."
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
          description="Author the runnable simulation setup in six focused sections. Persisted sections submit with the task; unsupported sections stay as local draft notes."
          status={simulationSetupState}
        >
          <StageNotice
            tone={simulationSetupState.tone}
            title={`Simulation Setup · ${simulationSetupState.label}`}
            message={simulationSetupState.message}
          />

          <div className="rounded-[0.95rem] border border-border bg-surface px-4 py-4">
            <div className="flex flex-wrap items-center gap-2">
              <SurfaceTag tone={activeDatasetState.activeDataset ? "success" : "warning"}>
                Dataset · {activeDatasetState.activeDataset?.name ?? "Attach in Global Context"}
              </SurfaceTag>
              <SurfaceTag tone={resolvedDefinitionId !== null ? "success" : "warning"}>
                Definition · {selectedDefinitionSummary?.name ?? "Selection required"}
              </SurfaceTag>
              <SurfaceTag tone={session?.canSubmitTasks ? "primary" : "warning"}>
                {session?.canSubmitTasks ? "Persisted task submit available" : "Persisted task submit blocked"}
              </SurfaceTag>
            </div>
            <p className="mt-3 text-sm leading-6 text-muted-foreground">
              Signal sweep, parameter sweeps, HB solving, and sources submit as persisted
              simulation setup. PTC and Advanced hbsolve Options stay browser-local until the
              backend contract exposes those fields.
            </p>
            {latestSimulationTaskDetail?.simulationSetup ? (
              <p className="mt-2 text-xs leading-5 text-muted-foreground">
                Persisted simulation setup was rehydrated from task #
                {latestSimulationTaskDetail.taskId}. Local-only draft sections were left unchanged.
              </p>
            ) : null}
          </div>

          <SetupSection
            title="Signal Frequency Sweep Range"
            description="Set the main frequency sweep window that defines the simulation sampling range."
            status={<SurfaceTag tone="primary">Persisted on task</SurfaceTag>}
          >
            <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
              <SetupInputField
                label="Start Freq (GHz)"
                error={form.formState.errors.simulationStartGhz?.message}
              >
                <SetupNumberInput
                  {...form.register("simulationStartGhz", { valueAsNumber: true })}
                  step="any"
                />
              </SetupInputField>
              <SetupInputField
                label="Stop Freq (GHz)"
                error={form.formState.errors.simulationStopGhz?.message}
              >
                <SetupNumberInput
                  {...form.register("simulationStopGhz", { valueAsNumber: true })}
                  step="any"
                />
              </SetupInputField>
              <SetupInputField
                label="Points"
                detail="Number of sample points across the sweep."
                error={form.formState.errors.simulationPointCount?.message}
              >
                <SetupNumberInput
                  {...form.register("simulationPointCount", { valueAsNumber: true })}
                  min={1}
                />
              </SetupInputField>
              <SetupInputField label="Spacing">
                <SetupSelect {...form.register("simulationSpacing")}>
                  <option value="linear">Linear</option>
                  <option value="log">Log</option>
                </SetupSelect>
              </SetupInputField>
            </div>
          </SetupSection>

          <SetupSection
            title="Parameter Sweep Setup"
            description="Add one or more sweep axes. Range mode expands start, stop, and points into the persisted values array."
            status={<SurfaceTag tone="primary">Persisted on task</SurfaceTag>}
            actions={
              parameterSweepEnabled ? (
                <button
                  type="button"
                  onClick={() => {
                    parameterSweepFieldArray.append(createDefaultSimulationParameterSweepAxis());
                    clearTaskMutationStatus();
                  }}
                  className="inline-flex cursor-pointer items-center gap-2 rounded-full border border-border bg-background px-3 py-2 text-xs font-medium text-foreground transition hover:border-primary/35 hover:bg-primary/10"
                >
                  <Plus className="h-3.5 w-3.5" />
                  Add Axis
                </button>
              ) : null
            }
          >
            <div className="flex flex-wrap items-center justify-between gap-3 rounded-[0.95rem] border border-border bg-background px-4 py-3">
              <div>
                <p className="text-sm font-medium text-foreground">Sweep authoring</p>
                <p className="mt-1 text-xs leading-5 text-muted-foreground">
                  Turn this on when the simulation needs one or more parameter axes beyond the main
                  frequency sweep.
                </p>
              </div>
              <label className="inline-flex cursor-pointer items-center gap-2 rounded-full border border-border bg-surface px-3 py-2 text-xs font-medium text-foreground">
                <input
                  type="checkbox"
                  checked={parameterSweepEnabled}
                  onChange={(event) => {
                    form.setValue("simulationParameterSweepEnabled", event.target.checked, {
                      shouldDirty: true,
                    });
                    if (event.target.checked && parameterSweepFieldArray.fields.length === 0) {
                      parameterSweepFieldArray.append(createDefaultSimulationParameterSweepAxis());
                    }
                  }}
                />
                Enable parameter sweeps
              </label>
            </div>

            {parameterSweepEnabled ? (
              <div className="space-y-3">
                {parameterSweepFieldArray.fields.map((field, index) => {
                  const axisErrors = form.formState.errors.simulationParameterSweepAxes?.[index];
                  const axisMode = form.watch(`simulationParameterSweepAxes.${index}.mode`);

                  return (
                    <div
                      key={field.id}
                      className="rounded-[0.95rem] border border-border bg-background px-4 py-4"
                    >
                      <div className="flex flex-wrap items-center justify-between gap-3">
                        <div>
                          <p className="text-sm font-semibold text-foreground">Axis {index + 1}</p>
                          <p className="mt-1 text-xs leading-5 text-muted-foreground">
                            Persisted as a parameter sweep values array on the simulation task.
                          </p>
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

                      <div className="mt-4 grid gap-3 md:grid-cols-2 xl:grid-cols-3">
                        <SetupInputField
                          label="Target / Parameter"
                          detail="Parameter path or target name for this sweep axis."
                          error={axisErrors?.parameter?.message}
                        >
                          <SetupTextInput
                            {...form.register(`simulationParameterSweepAxes.${index}.parameter`)}
                            placeholder="L_q"
                          />
                        </SetupInputField>
                        <SetupInputField label="Axis Mode">
                          <SetupSelect
                            {...form.register(`simulationParameterSweepAxes.${index}.mode`)}
                          >
                            <option value="range">Range builder</option>
                            <option value="explicit">Explicit values</option>
                          </SetupSelect>
                        </SetupInputField>
                        <SetupInputField
                          label="Unit"
                          detail="Optional engineering unit for this sweep axis."
                          error={axisErrors?.unit?.message}
                        >
                          <SetupTextInput
                            {...form.register(`simulationParameterSweepAxes.${index}.unit`)}
                            placeholder="nH"
                          />
                        </SetupInputField>
                        <SetupInputField
                          label="Start"
                          detail="Range builder start value."
                          error={axisErrors?.start?.message}
                        >
                          <SetupNumberInput
                            {...form.register(`simulationParameterSweepAxes.${index}.start`, {
                              valueAsNumber: true,
                            })}
                            step="any"
                          />
                        </SetupInputField>
                        <SetupInputField
                          label="Stop"
                          detail="Range builder stop value."
                          error={axisErrors?.stop?.message}
                        >
                          <SetupNumberInput
                            {...form.register(`simulationParameterSweepAxes.${index}.stop`, {
                              valueAsNumber: true,
                            })}
                            step="any"
                          />
                        </SetupInputField>
                        <SetupInputField
                          label="Points"
                          detail="Range builder sample count."
                          error={axisErrors?.pointCount?.message}
                        >
                          <SetupNumberInput
                            {...form.register(`simulationParameterSweepAxes.${index}.pointCount`, {
                              valueAsNumber: true,
                            })}
                            min={1}
                          />
                        </SetupInputField>
                      </div>

                      <SetupInputField
                        label="Explicit Values"
                        detail={
                          axisMode === "explicit"
                            ? "Comma-separated values submitted directly to the persisted values array."
                            : "Optional override. Range builder stays authoritative while Axis Mode is set to Range builder."
                        }
                        error={axisErrors?.explicitValues?.message}
                      >
                        <SetupTextInput
                          {...form.register(`simulationParameterSweepAxes.${index}.explicitValues`)}
                          placeholder="1.0, 1.1, 1.2"
                        />
                      </SetupInputField>
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
            description="Keep the solver family, convergence settings, and harmonic balance controls together as one solver authoring surface."
            status={<SurfaceTag tone="primary">Persisted on task</SurfaceTag>}
          >
            <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
              <SetupInputField
                label="Solver Family"
                error={form.formState.errors.simulationSolverFamily?.message}
              >
                <SetupTextInput
                  {...form.register("simulationSolverFamily")}
                  placeholder="harmonic_balance"
                />
              </SetupInputField>
              <SetupInputField
                label="Max Iterations"
                error={form.formState.errors.simulationMaxIterations?.message}
              >
                <SetupNumberInput
                  {...form.register("simulationMaxIterations", { valueAsNumber: true })}
                  min={1}
                />
              </SetupInputField>
              <SetupInputField
                label="Convergence Tolerance"
                error={form.formState.errors.simulationConvergenceTolerance?.message}
              >
                <SetupNumberInput
                  {...form.register("simulationConvergenceTolerance", {
                    valueAsNumber: true,
                  })}
                  step="any"
                />
              </SetupInputField>
            </div>

            <div className="rounded-[0.95rem] border border-border bg-background px-4 py-4">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div>
                  <p className="text-sm font-medium text-foreground">Harmonic balance</p>
                  <p className="mt-1 text-xs leading-5 text-muted-foreground">
                    Enable harmonic balance specific controls for this simulation request.
                  </p>
                </div>
                <label className="inline-flex cursor-pointer items-center gap-2 rounded-full border border-border bg-surface px-3 py-2 text-xs font-medium text-foreground">
                  <input type="checkbox" {...form.register("simulationHarmonicBalanceEnabled")} />
                  Enable harmonic balance
                </label>
              </div>

              <div className="mt-4 grid gap-3 md:grid-cols-2">
                <SetupInputField
                  label="Harmonic Count"
                  error={form.formState.errors.simulationHarmonicCount?.message}
                >
                  <SetupNumberInput
                    {...form.register("simulationHarmonicCount", { valueAsNumber: true })}
                    min={1}
                    disabled={!harmonicBalanceEnabled}
                  />
                </SetupInputField>
                <SetupInputField
                  label="Oversample Factor"
                  error={form.formState.errors.simulationOversampleFactor?.message}
                >
                  <SetupNumberInput
                    {...form.register("simulationOversampleFactor", { valueAsNumber: true })}
                    min={1}
                    disabled={!harmonicBalanceEnabled}
                  />
                </SetupInputField>
              </div>
            </div>
          </SetupSection>

          <SetupSection
            title="Sources"
            description="Build one or more simulation sources. Multiple source cards submit through the persisted sources[] contract."
            status={<SurfaceTag tone="primary">Persisted on task</SurfaceTag>}
            actions={
              <button
                type="button"
                onClick={() => {
                  sourceFieldArray.append(createDefaultSimulationSource());
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
                          <p className="text-sm font-semibold text-foreground">Source {index + 1}</p>
                          <p className="mt-1 text-xs leading-5 text-muted-foreground">
                            Drive source persisted with the simulation task.
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

                      <div className="mt-4 grid gap-3 md:grid-cols-2 xl:grid-cols-3">
                        <SetupInputField
                          label="Source Id"
                          error={sourceErrors?.sourceId?.message}
                        >
                          <SetupTextInput
                            {...form.register(`simulationSources.${index}.sourceId`)}
                            placeholder="src_drive_1"
                          />
                        </SetupInputField>
                        <SetupInputField label="Kind" error={sourceErrors?.kind?.message}>
                          <SetupTextInput
                            {...form.register(`simulationSources.${index}.kind`)}
                            placeholder="pump"
                          />
                        </SetupInputField>
                        <SetupInputField label="Target" error={sourceErrors?.target?.message}>
                          <SetupTextInput
                            {...form.register(`simulationSources.${index}.target`)}
                            placeholder="port_1"
                          />
                        </SetupInputField>
                        <SetupInputField
                          label="Amplitude"
                          error={sourceErrors?.amplitude?.message}
                        >
                          <SetupNumberInput
                            {...form.register(`simulationSources.${index}.amplitude`, {
                              valueAsNumber: true,
                            })}
                            step="any"
                          />
                        </SetupInputField>
                        <SetupInputField
                          label="Frequency (GHz)"
                          detail="Optional per-source frequency override."
                          error={sourceErrors?.frequencyGhz?.message}
                        >
                          <SetupTextInput
                            {...form.register(`simulationSources.${index}.frequencyGhz`)}
                            placeholder="optional"
                          />
                        </SetupInputField>
                        <SetupInputField
                          label="Phase (deg)"
                          detail="Optional per-source phase override."
                          error={sourceErrors?.phaseDeg?.message}
                        >
                          <SetupTextInput
                            {...form.register(`simulationSources.${index}.phaseDeg`)}
                            placeholder="optional"
                          />
                        </SetupInputField>
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
            description="Capture port tuning compensation intent without pretending the backend already persists it."
            status={<LocalDraftBadge />}
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
                Reset local draft
              </button>
            }
          >
            <div className="rounded-[0.95rem] border border-dashed border-amber-400/50 bg-amber-50/70 px-4 py-4 text-sm text-amber-950 dark:border-amber-400/30 dark:bg-amber-500/10 dark:text-amber-100">
              These fields stay local to the browser for now. They are visible during authoring but
              are not included in persisted simulation task submission or task rehydration.
            </div>

            <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
              <div className="rounded-[0.95rem] border border-border bg-background px-4 py-3">
                <label className="inline-flex cursor-pointer items-center gap-3 text-sm text-foreground">
                  <input type="checkbox" {...form.register("simulationPtcEnabled")} />
                  Enable PTC draft
                </label>
                <p className="mt-2 text-xs leading-5 text-muted-foreground">
                  Use this to track a local tuning draft without sending it to the backend.
                </p>
              </div>
              <SetupInputField label="Mode">
                <SetupSelect {...form.register("simulationPtcMode")} disabled={!ptcEnabled}>
                  <option value="auto">Auto compensate</option>
                  <option value="manual">Manual review</option>
                </SetupSelect>
              </SetupInputField>
              <SetupInputField
                label="Compensate Ports"
                detail="Comma-separated port ids or targets to include in this local PTC draft."
              >
                <SetupTextInput
                  {...form.register("simulationPtcCompensatePorts")}
                  disabled={!ptcEnabled}
                  placeholder="port_1, port_2"
                />
              </SetupInputField>
            </div>

            <SetupInputField
              label="Manual Affordance"
              detail={
                ptcMode === "manual"
                  ? "Record manual offsets, notes, or next-step instructions for this local draft."
                  : "Keep a short local note even when using auto compensate mode."
              }
            >
              <textarea
                {...form.register("simulationPtcManualNotes")}
                rows={4}
                disabled={!ptcEnabled}
                placeholder={
                  ptcMode === "manual"
                    ? "Describe manual port compensation steps."
                    : "Optional local note for the PTC draft."
                }
                className="w-full resize-none rounded-[0.8rem] border border-border bg-surface px-3 py-2.5 text-sm leading-6 text-foreground outline-none transition placeholder:text-muted-foreground focus:border-primary/45 focus:ring-2 focus:ring-primary/15 disabled:opacity-60"
              />
            </SetupInputField>
          </SetupSection>

          <SetupSection
            title="Advanced hbsolve Options"
            description="Keep advanced hbsolve draft settings out of the main flow until they are needed."
            status={<LocalDraftBadge />}
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
            <div className="rounded-[0.95rem] border border-dashed border-amber-400/50 bg-amber-50/70 px-4 py-4 text-sm text-amber-950 dark:border-amber-400/30 dark:bg-amber-500/10 dark:text-amber-100">
              Advanced hbsolve options are local draft only. They can guide authoring now, but the
              backend does not persist or rehydrate them yet.
            </div>

            {isAdvancedHbsolveExpanded ? (
              <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
                <SetupInputField label="Damping Strategy">
                  <SetupTextInput
                    {...form.register("simulationAdvancedDampingStrategy")}
                    placeholder="adaptive"
                  />
                </SetupInputField>
                <div className="rounded-[0.95rem] border border-border bg-background px-4 py-3">
                  <label className="inline-flex cursor-pointer items-center gap-3 text-sm text-foreground">
                    <input
                      type="checkbox"
                      {...form.register("simulationAdvancedLineSearchEnabled")}
                    />
                    Enable line search
                  </label>
                  <p className="mt-2 text-xs leading-5 text-muted-foreground">
                    Local-only toggle for advanced hbsolve experimentation notes.
                  </p>
                </div>
                <SetupInputField label="Residual Clamp">
                  <SetupTextInput
                    {...form.register("simulationAdvancedResidualClamp")}
                    placeholder="1e-6"
                  />
                </SetupInputField>
                <SetupInputField label="Newton Relaxation">
                  <SetupTextInput
                    {...form.register("simulationAdvancedNewtonRelaxation")}
                    placeholder="0.85"
                  />
                </SetupInputField>
                <SetupInputField
                  label="Advanced Notes"
                  detail="Keep any extra hbsolve options or reminders in local draft form."
                >
                  <textarea
                    {...form.register("simulationAdvancedNotes")}
                    rows={4}
                    placeholder="Optional advanced hbsolve notes."
                    className="w-full resize-none rounded-[0.8rem] border border-border bg-surface px-3 py-2.5 text-sm leading-6 text-foreground outline-none transition placeholder:text-muted-foreground focus:border-primary/45 focus:ring-2 focus:ring-primary/15"
                  />
                </SetupInputField>
              </div>
            ) : (
              <div className="rounded-[0.95rem] border border-dashed border-border bg-background px-4 py-4 text-sm text-muted-foreground">
                Advanced hbsolve options stay collapsed until you need them. Expanding this section
                will not change persisted task payloads.
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

          <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_auto]">
            <div className="rounded-[0.95rem] border border-border bg-surface px-4 py-4 text-sm text-muted-foreground">
              <p className="text-xs uppercase tracking-[0.16em] text-muted-foreground">
                Submission Preview
              </p>
              <p className="mt-2 text-foreground">{simulationRequestPreview}</p>
              <p className="mt-2 text-xs leading-5 text-muted-foreground">
                The first four sections submit with the simulation task. PTC and Advanced hbsolve
                Options remain local-only until backend persistence support lands.
              </p>
            </div>
            <button
              type="button"
              onClick={() => {
                void handleSubmit("simulation");
              }}
              disabled={taskMutationStatus.state === "submitting" || simulationSetupBlockedReason !== null}
              className="inline-flex min-h-11 cursor-pointer items-center justify-center gap-2 rounded-full bg-primary px-4 py-2.5 text-sm font-medium text-primary-foreground transition hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-60"
            >
              {taskMutationStatus.state === "submitting" ? (
                <LoaderCircle className="h-4 w-4 animate-spin" />
              ) : (
                <Play className="h-4 w-4" />
              )}
              Run Simulation
            </button>
          </div>

          {latestSimulationStageTask ? (
            <div className="rounded-[0.95rem] border border-border bg-background px-4 py-4">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div>
                  <p className="text-xs uppercase tracking-[0.16em] text-muted-foreground">
                    Latest Simulation Run
                  </p>
                  <p className="mt-2 text-sm font-semibold text-foreground">
                    Task #{latestSimulationStageTask.taskId}
                  </p>
                  <p className="mt-2 text-sm text-muted-foreground">
                    {latestSimulationTaskDetail?.progress.summary ??
                      latestSimulationStageTask.summary}
                  </p>
                </div>
                <SurfaceTag tone={taskStatusTone(latestSimulationStageTask.status)}>
                  {formatSimulationTaskStatusLabel(latestSimulationStageTask.status)}
                </SurfaceTag>
              </div>
              <div className="mt-4 grid gap-3 md:grid-cols-3">
                <SummaryCard
                  label="Submitted"
                  value={latestSimulationStageTask.submittedAt ?? "Pending"}
                />
                <SummaryCard
                  label="Result"
                  value={simulationResultReady ? "Ready" : "Pending"}
                  detail={
                    latestSimulationStageTask.resultAvailability
                      ? `Backend result availability: ${latestSimulationStageTask.resultAvailability}`
                      : "Result status is inferred from persisted task detail."
                  }
                />
                <SummaryCard
                  label="Progress"
                  value={
                    latestSimulationTaskDetail
                      ? `${Math.round(latestSimulationTaskDetail.progress.percentComplete)}%`
                      : formatSimulationTaskStatusLabel(latestSimulationStageTask.status)
                  }
                />
              </div>
              <div className="mt-4">
                <StageTaskActions
                  task={latestSimulationStageTask}
                  resolvedTaskId={resolvedTaskId}
                  onViewTask={attachTask}
                  onOpenGlobalContext={openTaskInGlobalContext}
                />
              </div>
            </div>
          ) : null}
        </WorkflowStageSection>

        <WorkflowStageSection
          step={3}
          title="Simulation Result"
          description="Inspect the latest simulation output without turning the page into a queue or worker dashboard."
          status={simulationResultState}
        >
          <StageNotice
            tone={simulationResultState.tone}
            title={`Simulation Result · ${simulationResultState.label}`}
            message={
              simulationStageErrorMessage
                ? `${simulationResultState.message} ${simulationStageErrorMessage}`
                : simulationResultState.message
            }
          />

          {latestSimulationStageTask ? (
            <>
              <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
                <SummaryCard
                  label="Latest Run"
                  value={`#${latestSimulationStageTask.taskId}`}
                  detail={latestSimulationStageTask.summary}
                />
                <SummaryCard
                  label="Trace Batch"
                  value={
                    simulationResultSummary.traceBatchId !== null
                      ? String(simulationResultSummary.traceBatchId)
                      : "Pending"
                  }
                />
                <SummaryCard
                  label="Result Handles"
                  value={String(simulationResultSummary.resultHandleCount)}
                  detail={`${simulationResultSummary.materializedHandleCount} materialized`}
                />
                <SummaryCard
                  label="Trace Payload"
                  value={simulationResultSummary.hasTracePayload ? "Attached" : "Pending"}
                  detail={`${simulationResultSummary.metadataRecordCount} metadata records`}
                />
              </div>

              <StageNotice
                tone={simulationResultReady ? "success" : simulationResultState.tone}
                title="Result handoff"
                message={
                  simulationResultReady
                    ? `Simulation result is ready for downstream work. Post Processing Setup can now use simulation task #${latestSimulationStageTask.taskId} as its upstream result source.`
                    : "Persisted simulation outputs are not ready yet. Post Processing Setup stays blocked until the simulation result becomes available."
                }
                actions={
                  <StageTaskActions
                    task={latestSimulationStageTask}
                    resolvedTaskId={resolvedTaskId}
                    onViewTask={attachTask}
                    onOpenGlobalContext={openTaskInGlobalContext}
                  />
                }
              />
            </>
          ) : null}
        </WorkflowStageSection>

        <WorkflowStageSection
          step={4}
          title="Post Processing Setup"
          description="Author output view, trace selection, and operation config, then submit a structured post-processing setup payload."
          status={postProcessingSetupState}
        >
          <StageNotice
            tone={postProcessingSetupState.tone}
            title={`Post Processing Setup · ${postProcessingSetupState.label}`}
            message={postProcessingSetupState.message}
          />

          <div className="grid gap-3 md:grid-cols-3">
            <SummaryCard
              label="Upstream Simulation"
              value={
                latestSimulationStageTask
                  ? `Task #${latestSimulationStageTask.taskId}`
                  : "Simulation required"
              }
              detail={
                simulationResultReady
                  ? "A persisted simulation result is available for downstream work."
                  : "Post-processing stays blocked until simulation publishes a persisted result."
              }
            />
            <SummaryCard
              label="Downstream Contract"
              value="Structured"
              detail="Post-processing setup persists output view, selection, operations, and upstream task linkage."
            />
            <SummaryCard
              label="Submit Authority"
              value={session?.canSubmitTasks ? "Available" : "Blocked"}
              detail="Post-processing still respects the same backend task authority as simulation."
            />
          </div>

          <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
            <label className="block rounded-[0.95rem] border border-border bg-surface px-4 py-3">
              <span className="text-xs uppercase tracking-[0.16em] text-muted-foreground">
                Output View
              </span>
              <input
                {...form.register("postOutputView")}
                className="mt-2 w-full bg-transparent text-sm text-foreground outline-none"
                placeholder="table"
              />
            </label>
            <label className="block rounded-[0.95rem] border border-border bg-surface px-4 py-3">
              <span className="text-xs uppercase tracking-[0.16em] text-muted-foreground">
                Trace Family
              </span>
              <input
                {...form.register("postSelectionTraceFamily")}
                className="mt-2 w-full bg-transparent text-sm text-foreground outline-none"
                placeholder="y_matrix"
              />
            </label>
            <label className="block rounded-[0.95rem] border border-border bg-surface px-4 py-3">
              <span className="text-xs uppercase tracking-[0.16em] text-muted-foreground">
                Representation
              </span>
              <input
                {...form.register("postSelectionRepresentation")}
                className="mt-2 w-full bg-transparent text-sm text-foreground outline-none"
                placeholder="imaginary"
              />
            </label>
            <label className="block rounded-[0.95rem] border border-border bg-surface px-4 py-3">
              <span className="text-xs uppercase tracking-[0.16em] text-muted-foreground">
                Selection Design Id (optional)
              </span>
              <input
                {...form.register("postSelectionDesignId")}
                className="mt-2 w-full bg-transparent text-sm text-foreground outline-none"
                placeholder="design_flux_scan_a"
              />
            </label>
          </div>

          <div className="grid gap-3 md:grid-cols-3">
            <label className="block rounded-[0.95rem] border border-border bg-surface px-4 py-3 md:col-span-2">
              <span className="text-xs uppercase tracking-[0.16em] text-muted-foreground">
                Trace Ids (comma separated)
              </span>
              <input
                {...form.register("postSelectionTraceIds")}
                className="mt-2 w-full bg-transparent text-sm text-foreground outline-none"
                placeholder="trace_001, trace_002"
              />
            </label>
            <label className="block rounded-[0.95rem] border border-border bg-surface px-4 py-3">
              <span className="text-xs uppercase tracking-[0.16em] text-muted-foreground">
                Operation Name
              </span>
              <input
                {...form.register("postOperationName")}
                className="mt-2 w-full bg-transparent text-sm text-foreground outline-none"
                placeholder="normalize"
              />
            </label>
          </div>

          <label className="flex items-center gap-3 rounded-[0.95rem] border border-border bg-surface px-4 py-3">
            <input type="checkbox" {...form.register("postOperationEnabled")} />
            <span className="text-sm text-foreground">Enable operation</span>
          </label>

          <label className="block rounded-[0.95rem] border border-border bg-surface px-4 py-3">
            <span className="mb-2 block text-xs uppercase tracking-[0.16em] text-muted-foreground">
              Operation Config JSON
            </span>
            <textarea
              {...form.register("postOperationConfigJson")}
              rows={4}
              placeholder='{"mode":"strict"}'
              className="w-full resize-none bg-transparent text-sm leading-6 text-foreground outline-none placeholder:text-muted-foreground"
            />
          </label>

          <label className="block rounded-[0.95rem] border border-border bg-surface px-4 py-3">
            <span className="mb-2 block text-xs uppercase tracking-[0.16em] text-muted-foreground">
              Post Processing Note
            </span>
            <textarea
              {...form.register("postProcessingNote")}
              rows={4}
              placeholder="Optional context for the downstream stage, for example export bundle or analysis handoff."
              className="w-full resize-none bg-transparent text-sm leading-6 text-foreground outline-none placeholder:text-muted-foreground"
            />
          </label>

          {form.formState.errors.postProcessingNote ? (
            <p className="text-sm text-rose-700 dark:text-rose-300">
              {form.formState.errors.postProcessingNote.message}
            </p>
          ) : null}
          {form.formState.errors.postOperationConfigJson ? (
            <p className="text-sm text-rose-700 dark:text-rose-300">
              {form.formState.errors.postOperationConfigJson.message}
            </p>
          ) : null}

          <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_auto]">
            <div className="rounded-[0.95rem] border border-border bg-surface px-4 py-4 text-sm text-muted-foreground">
              <p className="text-xs uppercase tracking-[0.16em] text-muted-foreground">
                Submission Preview
              </p>
              <p className="mt-2 text-foreground">{postProcessingRequestPreview}</p>
              {latestPostProcessingTaskDetail?.postProcessingSetup ? (
                <p className="mt-2 text-xs text-muted-foreground">
                  Latest post-processing setup was rehydrated from task #{latestPostProcessingTaskDetail.taskId}.
                </p>
              ) : null}
            </div>
            <button
              type="button"
              onClick={() => {
                void handleSubmit("post_processing");
              }}
              disabled={
                taskMutationStatus.state === "submitting" || postProcessingSetupBlockedReason !== null
              }
              className="inline-flex min-h-11 cursor-pointer items-center justify-center gap-2 rounded-full bg-primary px-4 py-2.5 text-sm font-medium text-primary-foreground transition hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-60"
            >
              {taskMutationStatus.state === "submitting" ? (
                <LoaderCircle className="h-4 w-4 animate-spin" />
              ) : (
                <WandSparkles className="h-4 w-4" />
              )}
              Run Post Processing
            </button>
          </div>

          {latestPostProcessingTask ? (
            <div className="rounded-[0.95rem] border border-border bg-background px-4 py-4">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div>
                  <p className="text-xs uppercase tracking-[0.16em] text-muted-foreground">
                    Latest Post Processing Run
                  </p>
                  <p className="mt-2 text-sm font-semibold text-foreground">
                    Task #{latestPostProcessingTask.taskId}
                  </p>
                  <p className="mt-2 text-sm text-muted-foreground">
                    {latestPostProcessingTaskDetail?.progress.summary ??
                      latestPostProcessingTask.summary}
                  </p>
                </div>
                <SurfaceTag tone={taskStatusTone(latestPostProcessingTask.status)}>
                  {formatSimulationTaskStatusLabel(latestPostProcessingTask.status)}
                </SurfaceTag>
              </div>
              <div className="mt-4 grid gap-3 md:grid-cols-3">
                <SummaryCard
                  label="Submitted"
                  value={latestPostProcessingTask.submittedAt ?? "Pending"}
                />
                <SummaryCard
                  label="Upstream"
                  value={
                    explicitUpstreamSimulationTaskId !== null
                      ? `Simulation #${explicitUpstreamSimulationTaskId}`
                      : latestSimulationStageTask
                        ? `Simulation #${latestSimulationStageTask.taskId}`
                        : "Pending"
                  }
                  detail={
                    explicitUpstreamSimulationTaskId !== null
                      ? "Recovered from persisted post-processing result provenance."
                      : latestSimulationStageTask
                        ? "Paired with the latest simulation result visible in the current page context."
                        : "Simulation result is still required."
                  }
                />
                <SummaryCard
                  label="Result"
                  value={postProcessingResultReady ? "Ready" : "Pending"}
                  detail={
                    latestPostProcessingTask.resultAvailability
                      ? `Backend result availability: ${latestPostProcessingTask.resultAvailability}`
                      : "Result status is inferred from persisted task detail."
                  }
                />
              </div>
              <div className="mt-4">
                <StageTaskActions
                  task={latestPostProcessingTask}
                  resolvedTaskId={resolvedTaskId}
                  onViewTask={attachTask}
                  onOpenGlobalContext={openTaskInGlobalContext}
                />
              </div>
            </div>
          ) : null}
        </WorkflowStageSection>

        <WorkflowStageSection
          step={5}
          title="Post Processing Result"
          description="Keep the downstream result tied to its post-processing stage and make the upstream simulation relation explicit."
          status={postProcessingResultState}
        >
          <StageNotice
            tone={postProcessingResultState.tone}
            title={`Post Processing Result · ${postProcessingResultState.label}`}
            message={
              postProcessingStageErrorMessage
                ? `${postProcessingResultState.message} ${postProcessingStageErrorMessage}`
                : postProcessingResultState.message
            }
          />

          {latestPostProcessingTask ? (
            <>
              <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
                <SummaryCard
                  label="Latest Run"
                  value={`#${latestPostProcessingTask.taskId}`}
                  detail={latestPostProcessingTask.summary}
                />
                <SummaryCard
                  label="Analysis Run"
                  value={
                    postProcessingResultSummary.analysisRunId !== null
                      ? String(postProcessingResultSummary.analysisRunId)
                      : "Pending"
                  }
                />
                <SummaryCard
                  label="Result Handles"
                  value={String(postProcessingResultSummary.resultHandleCount)}
                  detail={`${postProcessingResultSummary.materializedHandleCount} materialized`}
                />
                <SummaryCard
                  label="Trace Payload"
                  value={postProcessingResultSummary.hasTracePayload ? "Attached" : "Pending"}
                  detail={`${postProcessingResultSummary.metadataRecordCount} metadata records`}
                />
              </div>

              <StageNotice
                tone={postProcessingResultReady ? "success" : postProcessingResultState.tone}
                title="Downstream handoff"
                message={
                  explicitUpstreamSimulationTaskId !== null
                    ? `This downstream result is attached to post-processing task #${latestPostProcessingTask.taskId} and traces back to simulation task #${explicitUpstreamSimulationTaskId}.`
                    : latestSimulationStageTask
                      ? `This downstream result is attached to post-processing task #${latestPostProcessingTask.taskId}. The page can pair it with the latest simulation task #${latestSimulationStageTask.taskId}, but the backend payload does not expose a narrower upstream task id here.`
                      : `This downstream result is attached to post-processing task #${latestPostProcessingTask.taskId}. Upstream simulation context is not currently available in the page.`
                }
                actions={
                  <StageTaskActions
                    task={latestPostProcessingTask}
                    resolvedTaskId={resolvedTaskId}
                    onViewTask={attachTask}
                    onOpenGlobalContext={openTaskInGlobalContext}
                  />
                }
              />
            </>
          ) : null}
        </WorkflowStageSection>
      </div>

      <div className="rounded-[1rem] border border-border bg-surface px-4 py-4 text-sm text-muted-foreground">
        <div className="flex flex-wrap items-center gap-2">
          <Workflow className="h-4 w-4 text-primary" />
          <p className="font-medium text-foreground">Global Context owns the infrastructure.</p>
        </div>
        <p className="mt-2 leading-6">
          Queue browsing, worker lane health, attach / cancel / terminate / retry, and deeper task
          diagnostics stay in Global Context. This page only keeps the stage-local execution state
          needed to finish the simulation workflow.
        </p>
        {latestSimulationTask ? (
          <div className="mt-4">
            <button
              type="button"
              onClick={() => {
                openTaskInGlobalContext(latestSimulationTask.taskId);
              }}
              className="inline-flex cursor-pointer items-center gap-2 rounded-full border border-border bg-background px-3 py-2 text-xs font-medium text-foreground transition hover:border-primary/35 hover:bg-primary/10"
            >
              <ArrowUpRight className="h-3.5 w-3.5" />
              Open Latest Pipeline Task in Global Context
            </button>
          </div>
        ) : null}
      </div>
    </div>
  );
}
