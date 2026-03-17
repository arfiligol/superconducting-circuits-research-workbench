"use client";

import { useEffect, useMemo, useState, useTransition } from "react";
import { zodResolver } from "@hookform/resolvers/zod";
import { EditorState } from "@codemirror/state";
import { json } from "@codemirror/lang-json";
import { EditorView } from "@codemirror/view";
import {
  ArrowUpRight,
  Database,
  FileCode2,
  LoaderCircle,
  Play,
  RefreshCcw,
  Shapes,
  WandSparkles,
  Workflow,
} from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import CodeMirror from "@uiw/react-codemirror";
import { useForm } from "react-hook-form";
import { z } from "zod";

import {
  buildCircuitDefinitionCatalogHref,
  buildCircuitDefinitionEditorHref,
  buildCircuitSchemdrawHref,
} from "@/features/circuit-definition-editor/lib/routes";
import { formatCircuitNetlistSource } from "@/features/circuit-definition-editor/lib/netlist";
import { useSimulationWorkflowData } from "@/features/simulation/hooks/use-simulation-workflow-data";
import { parseSimulationDefinitionIdParam } from "@/features/simulation/lib/definition-id";
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

const simulationRequestSchema = z.object({
  simulationNote: z.string().trim().max(180, "Keep the request note within 180 characters."),
  simulationStartGhz: z.number().positive("Start GHz must be a positive number."),
  simulationStopGhz: z.number().positive("Stop GHz must be a positive number."),
  simulationPointCount: z.number().int().min(1, "Point count must be at least 1."),
  simulationSpacing: z.enum(["linear", "log"]),
  simulationSolverFamily: z.string().trim().min(1, "Solver family is required."),
  simulationMaxIterations: z.number().int().min(1, "Max iterations must be at least 1."),
  simulationConvergenceTolerance: z
    .number()
    .positive("Convergence tolerance must be a positive number."),
  simulationHarmonicBalanceEnabled: z.boolean(),
  simulationHarmonicCount: z.number().int().min(1, "Harmonic count must be at least 1."),
  simulationOversampleFactor: z
    .number()
    .int()
    .min(1, "Oversample factor must be at least 1."),
  simulationSourceId: z.string().trim().min(1, "Source id is required."),
  simulationSourceKind: z.string().trim().min(1, "Source kind is required."),
  simulationSourceTarget: z.string().trim().min(1, "Source target is required."),
  simulationSourceAmplitude: z.number(),
  simulationSourceFrequencyGhz: z.string().trim(),
  simulationSourcePhaseDeg: z.string().trim(),
  simulationSweepParameter: z.string().trim(),
  simulationSweepValues: z.string().trim(),
  simulationSweepUnit: z.string().trim(),
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
  simulationNote: "",
  simulationStartGhz: 1,
  simulationStopGhz: 8,
  simulationPointCount: 401,
  simulationSpacing: "linear",
  simulationSolverFamily: "harmonic_balance",
  simulationMaxIterations: 80,
  simulationConvergenceTolerance: 0.000001,
  simulationHarmonicBalanceEnabled: true,
  simulationHarmonicCount: 3,
  simulationOversampleFactor: 2,
  simulationSourceId: "src_drive_1",
  simulationSourceKind: "pump",
  simulationSourceTarget: "port_1",
  simulationSourceAmplitude: 1,
  simulationSourceFrequencyGhz: "5.0",
  simulationSourcePhaseDeg: "0",
  simulationSweepParameter: "",
  simulationSweepValues: "",
  simulationSweepUnit: "",
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

function lineCount(value: string) {
  return value.split("\n").length;
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

function parseOptionalNumberInput(value: string) {
  const normalized = value.trim();
  if (!normalized) {
    return null;
  }
  const parsed = Number(normalized);
  if (!Number.isFinite(parsed)) {
    throw new Error(`"${value}" is not a valid number.`);
  }
  return parsed;
}

function parseCommaSeparatedStrings(value: string) {
  return value
    .split(",")
    .map((entry) => entry.trim())
    .filter((entry) => entry.length > 0);
}

function parseCommaSeparatedNumbers(value: string) {
  const segments = parseCommaSeparatedStrings(value);
  return segments.map((segment) => {
    const parsed = Number(segment);
    if (!Number.isFinite(parsed)) {
      throw new Error(`"${segment}" is not a valid numeric sweep value.`);
    }
    return parsed;
  });
}

function buildSimulationSetupDraft(values: SimulationRequestValues) {
  const parameter = values.simulationSweepParameter.trim();
  const sweepValues = parseCommaSeparatedNumbers(values.simulationSweepValues);

  if (parameter.length > 0 && sweepValues.length === 0) {
    throw new Error("Provide at least one sweep value when a sweep parameter is set.");
  }

  return {
    frequency_sweep: {
      start_ghz: values.simulationStartGhz,
      stop_ghz: values.simulationStopGhz,
      point_count: values.simulationPointCount,
      spacing: values.simulationSpacing,
    },
    parameter_sweeps:
      parameter.length > 0
        ? [
            {
              parameter,
              values: sweepValues,
              unit: values.simulationSweepUnit.trim() || null,
            },
          ]
        : [],
    solver: {
      solver_family: values.simulationSolverFamily.trim(),
      max_iterations: values.simulationMaxIterations,
      convergence_tolerance: values.simulationConvergenceTolerance,
      harmonic_balance: {
        enabled: values.simulationHarmonicBalanceEnabled,
        harmonic_count: values.simulationHarmonicBalanceEnabled
          ? values.simulationHarmonicCount
          : null,
        oversample_factor: values.simulationHarmonicBalanceEnabled
          ? values.simulationOversampleFactor
          : null,
      },
    },
    sources: [
      {
        source_id: values.simulationSourceId.trim(),
        kind: values.simulationSourceKind.trim(),
        target: values.simulationSourceTarget.trim(),
        amplitude: values.simulationSourceAmplitude,
        frequency_ghz: parseOptionalNumberInput(values.simulationSourceFrequencyGhz),
        phase_deg: parseOptionalNumberInput(values.simulationSourcePhaseDeg),
      },
    ],
  };
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
        trace_ids: parseCommaSeparatedStrings(values.postSelectionTraceIds),
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

  const form = useForm<SimulationRequestValues>({
    resolver: zodResolver(simulationRequestSchema),
    defaultValues: defaultRequestValues,
  });
  const [hydratedSimulationTaskId, setHydratedSimulationTaskId] = useState<number | null>(null);
  const [hydratedPostTaskId, setHydratedPostTaskId] = useState<number | null>(null);

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
  const formattedSourceText = useMemo(() => {
    if (!activeDefinition?.source_text) {
      return "{\n  \"name\": \"pending_definition\"\n}";
    }

    return (
      formatCircuitNetlistSource(activeDefinition.source_text, {
        canonicalName: activeDefinition.name,
      }).formattedSource || activeDefinition.source_text
    );
  }, [activeDefinition]);
  const formattedNormalizedOutput = useMemo(
    () =>
      formatCodeValue(
        activeDefinition?.normalized_output,
        "{\n  \"expanded_netlist\": \"pending_definition\"\n}",
      ),
    [activeDefinition],
  );
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

    const setup = latestSimulationTaskDetail.simulationSetup;
    const firstSweep = setup.parameterSweeps[0];
    const firstSource = setup.sources[0];

    form.setValue("simulationStartGhz", setup.frequencySweep.startGhz, { shouldDirty: false });
    form.setValue("simulationStopGhz", setup.frequencySweep.stopGhz, { shouldDirty: false });
    form.setValue("simulationPointCount", setup.frequencySweep.pointCount, { shouldDirty: false });
    form.setValue("simulationSpacing", setup.frequencySweep.spacing, { shouldDirty: false });
    form.setValue("simulationSolverFamily", setup.solver.solverFamily, { shouldDirty: false });
    form.setValue("simulationMaxIterations", setup.solver.maxIterations, { shouldDirty: false });
    form.setValue(
      "simulationConvergenceTolerance",
      setup.solver.convergenceTolerance,
      { shouldDirty: false },
    );
    form.setValue(
      "simulationHarmonicBalanceEnabled",
      setup.solver.harmonicBalance?.enabled ?? false,
      { shouldDirty: false },
    );
    form.setValue(
      "simulationHarmonicCount",
      setup.solver.harmonicBalance?.harmonicCount ?? defaultRequestValues.simulationHarmonicCount,
      { shouldDirty: false },
    );
    form.setValue(
      "simulationOversampleFactor",
      setup.solver.harmonicBalance?.oversampleFactor ??
        defaultRequestValues.simulationOversampleFactor,
      { shouldDirty: false },
    );
    form.setValue("simulationSourceId", firstSource?.sourceId ?? "", { shouldDirty: false });
    form.setValue("simulationSourceKind", firstSource?.kind ?? "", { shouldDirty: false });
    form.setValue("simulationSourceTarget", firstSource?.target ?? "", { shouldDirty: false });
    form.setValue(
      "simulationSourceAmplitude",
      firstSource?.amplitude ?? defaultRequestValues.simulationSourceAmplitude,
      { shouldDirty: false },
    );
    form.setValue(
      "simulationSourceFrequencyGhz",
      firstSource?.frequencyGhz !== null && firstSource?.frequencyGhz !== undefined
        ? String(firstSource.frequencyGhz)
        : "",
      { shouldDirty: false },
    );
    form.setValue(
      "simulationSourcePhaseDeg",
      firstSource?.phaseDeg !== null && firstSource?.phaseDeg !== undefined
        ? String(firstSource.phaseDeg)
        : "",
      { shouldDirty: false },
    );
    form.setValue("simulationSweepParameter", firstSweep?.parameter ?? "", {
      shouldDirty: false,
    });
    form.setValue("simulationSweepValues", firstSweep ? firstSweep.values.join(", ") : "", {
      shouldDirty: false,
    });
    form.setValue("simulationSweepUnit", firstSweep?.unit ?? "", { shouldDirty: false });
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
    const fieldName = kind === "simulation" ? "simulationNote" : "postProcessingNote";
    const isValid = await form.trigger(fieldName);
    if (!isValid) {
      return;
    }

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
        form.setError("simulationSweepValues", { type: "manual", message });
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
          description="Read the persisted definition and its expanded netlist before changing setup or launching a new run."
          status={{
            label: activeDefinition ? "Ready" : isDefinitionsLoading ? "Loading" : "Blocked",
            tone: activeDefinition ? "success" : isDefinitionsLoading ? "primary" : "warning",
            message: activeDefinition
              ? "Definition context is ready."
              : "Select a visible definition first.",
          }}
          actions={
            <div className="flex flex-wrap gap-2">
              <Link
                href={buildCircuitDefinitionCatalogHref()}
                className="inline-flex min-h-10 items-center rounded-full border border-border bg-background px-3 py-2 text-xs font-medium uppercase tracking-[0.16em] text-foreground transition hover:border-primary/35 hover:bg-primary/10"
              >
                Open Schemas
              </Link>
              {resolvedDefinitionId !== null ? (
                <>
                  <Link
                    href={buildCircuitDefinitionEditorHref(resolvedDefinitionId)}
                    className="inline-flex min-h-10 items-center rounded-full border border-border bg-background px-3 py-2 text-xs font-medium uppercase tracking-[0.16em] text-foreground transition hover:border-primary/35 hover:bg-primary/10"
                  >
                    Open Schema Editor
                  </Link>
                  <Link
                    href={buildCircuitSchemdrawHref(resolvedDefinitionId)}
                    className="inline-flex min-h-10 items-center rounded-full border border-border bg-background px-3 py-2 text-xs font-medium uppercase tracking-[0.16em] text-foreground transition hover:border-primary/35 hover:bg-primary/10"
                  >
                    Open Schemdraw
                  </Link>
                </>
              ) : null}
            </div>
          }
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

          <div className="grid gap-4 xl:grid-cols-[minmax(0,0.78fr)_minmax(0,1.22fr)]">
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
                  isDefinitionsLoading
                    ? "Loading definitions"
                    : definitions?.length
                      ? "Select a definition"
                      : "No definitions available"
                }
                disabled={isDefinitionsLoading || definitionOptions.length === 0}
              />

              <div className="grid gap-3 sm:grid-cols-2">
                <SummaryCard
                  label="Definition"
                  value={activeDefinition?.name ?? "No definition selected"}
                  detail={
                    resolvedDefinitionId !== null
                      ? `Definition #${resolvedDefinitionId}`
                      : "Select a persisted definition from the visible catalog."
                  }
                />
                <SummaryCard
                  label="Validation"
                  value={activeDefinition?.validation_summary.status ?? "Pending"}
                  detail={
                    activeDefinition
                      ? `${activeDefinition.validation_summary.notice_count} persisted notices`
                      : "Validation summary arrives with definition detail."
                  }
                />
                <SummaryCard
                  label="Visibility"
                  value={activeDefinition?.visibility_scope ?? "Pending"}
                  detail={
                    activeDefinition?.workspace_id
                      ? `Workspace ${activeDefinition.workspace_id}`
                      : "Workspace detail is pending."
                  }
                />
                <SummaryCard
                  label="Source Snapshot"
                  value={activeDefinition ? `${lineCount(formattedSourceText)} lines` : "Pending"}
                  detail={
                    activeDefinition
                      ? `${lineCount(formattedNormalizedOutput)} expanded lines`
                      : "Source and expanded netlist appear after definition detail loads."
                  }
                />
              </div>

              <StageNotice
                tone="default"
                title="Workflow boundary"
                message="Definition context stays readable here. Queue browse, worker health, cancel, terminate, retry, and deep task diagnostics stay in Global Context."
              />
            </div>

            <div className="grid gap-4">
              <ReadOnlyCodeSurface
                label="Canonical Source"
                detail="Persisted definition source used as simulation authority."
                value={formattedSourceText}
                height="260px"
              />
              <ReadOnlyCodeSurface
                label="Expanded Netlist Snapshot"
                detail="Persisted normalized output snapshot used for readable netlist context."
                value={formattedNormalizedOutput}
                height="240px"
              />
            </div>
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
          description="Author frequency sweep, solver, source, and optional parameter sweep setup, then submit a real simulation setup payload."
          status={simulationSetupState}
        >
          <StageNotice
            tone={simulationSetupState.tone}
            title={`Simulation Setup · ${simulationSetupState.label}`}
            message={simulationSetupState.message}
          />

          <div className="grid gap-3 md:grid-cols-3">
            <SummaryCard
              label="Active Dataset"
              value={activeDatasetState.activeDataset?.name ?? "Dataset required"}
              detail={
                activeDatasetState.activeDataset?.datasetId ??
                "Attach a dataset from the shell before running simulation."
              }
            />
            <SummaryCard
              label="Definition Binding"
              value={selectedDefinitionSummary?.name ?? "Definition required"}
              detail={
                resolvedDefinitionId !== null
                  ? `Definition #${resolvedDefinitionId}`
                  : "Simulation submission requires a visible persisted definition."
              }
            />
            <SummaryCard
              label="Submit Authority"
              value={session?.canSubmitTasks ? "Available" : "Blocked"}
              detail="Simulation setup submit is backend-authoritative and persisted on the task."
            />
          </div>

          <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
            <label className="block rounded-[0.95rem] border border-border bg-surface px-4 py-3">
              <span className="text-xs uppercase tracking-[0.16em] text-muted-foreground">
                Start (GHz)
              </span>
              <input
                {...form.register("simulationStartGhz", { valueAsNumber: true })}
                type="number"
                step="any"
                className="mt-2 w-full bg-transparent text-sm text-foreground outline-none"
              />
            </label>
            <label className="block rounded-[0.95rem] border border-border bg-surface px-4 py-3">
              <span className="text-xs uppercase tracking-[0.16em] text-muted-foreground">
                Stop (GHz)
              </span>
              <input
                {...form.register("simulationStopGhz", { valueAsNumber: true })}
                type="number"
                step="any"
                className="mt-2 w-full bg-transparent text-sm text-foreground outline-none"
              />
            </label>
            <label className="block rounded-[0.95rem] border border-border bg-surface px-4 py-3">
              <span className="text-xs uppercase tracking-[0.16em] text-muted-foreground">
                Points
              </span>
              <input
                {...form.register("simulationPointCount", { valueAsNumber: true })}
                type="number"
                min={1}
                className="mt-2 w-full bg-transparent text-sm text-foreground outline-none"
              />
            </label>
            <label className="block rounded-[0.95rem] border border-border bg-surface px-4 py-3">
              <span className="text-xs uppercase tracking-[0.16em] text-muted-foreground">
                Spacing
              </span>
              <select
                {...form.register("simulationSpacing")}
                className="mt-2 w-full bg-transparent text-sm text-foreground outline-none"
              >
                <option value="linear">linear</option>
                <option value="log">log</option>
              </select>
            </label>
          </div>

          <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
            <label className="block rounded-[0.95rem] border border-border bg-surface px-4 py-3">
              <span className="text-xs uppercase tracking-[0.16em] text-muted-foreground">
                Solver Family
              </span>
              <input
                {...form.register("simulationSolverFamily")}
                className="mt-2 w-full bg-transparent text-sm text-foreground outline-none"
                placeholder="harmonic_balance"
              />
            </label>
            <label className="block rounded-[0.95rem] border border-border bg-surface px-4 py-3">
              <span className="text-xs uppercase tracking-[0.16em] text-muted-foreground">
                Max Iterations
              </span>
              <input
                {...form.register("simulationMaxIterations", { valueAsNumber: true })}
                type="number"
                min={1}
                className="mt-2 w-full bg-transparent text-sm text-foreground outline-none"
              />
            </label>
            <label className="block rounded-[0.95rem] border border-border bg-surface px-4 py-3">
              <span className="text-xs uppercase tracking-[0.16em] text-muted-foreground">
                Convergence Tolerance
              </span>
              <input
                {...form.register("simulationConvergenceTolerance", { valueAsNumber: true })}
                type="number"
                step="any"
                className="mt-2 w-full bg-transparent text-sm text-foreground outline-none"
              />
            </label>
            <label className="flex items-center gap-3 rounded-[0.95rem] border border-border bg-surface px-4 py-3">
              <input type="checkbox" {...form.register("simulationHarmonicBalanceEnabled")} />
              <span className="text-sm text-foreground">Enable Harmonic Balance</span>
            </label>
          </div>

          <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
            <label className="block rounded-[0.95rem] border border-border bg-surface px-4 py-3">
              <span className="text-xs uppercase tracking-[0.16em] text-muted-foreground">
                Harmonic Count
              </span>
              <input
                {...form.register("simulationHarmonicCount", { valueAsNumber: true })}
                type="number"
                min={1}
                disabled={!form.watch("simulationHarmonicBalanceEnabled")}
                className="mt-2 w-full bg-transparent text-sm text-foreground outline-none disabled:opacity-60"
              />
            </label>
            <label className="block rounded-[0.95rem] border border-border bg-surface px-4 py-3">
              <span className="text-xs uppercase tracking-[0.16em] text-muted-foreground">
                Oversample Factor
              </span>
              <input
                {...form.register("simulationOversampleFactor", { valueAsNumber: true })}
                type="number"
                min={1}
                disabled={!form.watch("simulationHarmonicBalanceEnabled")}
                className="mt-2 w-full bg-transparent text-sm text-foreground outline-none disabled:opacity-60"
              />
            </label>
            <label className="block rounded-[0.95rem] border border-border bg-surface px-4 py-3">
              <span className="text-xs uppercase tracking-[0.16em] text-muted-foreground">
                Source Id
              </span>
              <input
                {...form.register("simulationSourceId")}
                className="mt-2 w-full bg-transparent text-sm text-foreground outline-none"
                placeholder="src_drive_1"
              />
            </label>
            <label className="block rounded-[0.95rem] border border-border bg-surface px-4 py-3">
              <span className="text-xs uppercase tracking-[0.16em] text-muted-foreground">
                Source Kind
              </span>
              <input
                {...form.register("simulationSourceKind")}
                className="mt-2 w-full bg-transparent text-sm text-foreground outline-none"
                placeholder="pump"
              />
            </label>
          </div>

          <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
            <label className="block rounded-[0.95rem] border border-border bg-surface px-4 py-3">
              <span className="text-xs uppercase tracking-[0.16em] text-muted-foreground">
                Source Target
              </span>
              <input
                {...form.register("simulationSourceTarget")}
                className="mt-2 w-full bg-transparent text-sm text-foreground outline-none"
                placeholder="port_1"
              />
            </label>
            <label className="block rounded-[0.95rem] border border-border bg-surface px-4 py-3">
              <span className="text-xs uppercase tracking-[0.16em] text-muted-foreground">
                Source Amplitude
              </span>
              <input
                {...form.register("simulationSourceAmplitude", { valueAsNumber: true })}
                type="number"
                step="any"
                className="mt-2 w-full bg-transparent text-sm text-foreground outline-none"
              />
            </label>
            <label className="block rounded-[0.95rem] border border-border bg-surface px-4 py-3">
              <span className="text-xs uppercase tracking-[0.16em] text-muted-foreground">
                Source Frequency (GHz)
              </span>
              <input
                {...form.register("simulationSourceFrequencyGhz")}
                className="mt-2 w-full bg-transparent text-sm text-foreground outline-none"
                placeholder="optional"
              />
            </label>
            <label className="block rounded-[0.95rem] border border-border bg-surface px-4 py-3">
              <span className="text-xs uppercase tracking-[0.16em] text-muted-foreground">
                Source Phase (deg)
              </span>
              <input
                {...form.register("simulationSourcePhaseDeg")}
                className="mt-2 w-full bg-transparent text-sm text-foreground outline-none"
                placeholder="optional"
              />
            </label>
          </div>

          <div className="grid gap-3 md:grid-cols-3">
            <label className="block rounded-[0.95rem] border border-border bg-surface px-4 py-3">
              <span className="text-xs uppercase tracking-[0.16em] text-muted-foreground">
                Sweep Parameter (optional)
              </span>
              <input
                {...form.register("simulationSweepParameter")}
                className="mt-2 w-full bg-transparent text-sm text-foreground outline-none"
                placeholder="L_q"
              />
            </label>
            <label className="block rounded-[0.95rem] border border-border bg-surface px-4 py-3">
              <span className="text-xs uppercase tracking-[0.16em] text-muted-foreground">
                Sweep Values (comma separated)
              </span>
              <input
                {...form.register("simulationSweepValues")}
                className="mt-2 w-full bg-transparent text-sm text-foreground outline-none"
                placeholder="1.0, 1.1, 1.2"
              />
            </label>
            <label className="block rounded-[0.95rem] border border-border bg-surface px-4 py-3">
              <span className="text-xs uppercase tracking-[0.16em] text-muted-foreground">
                Sweep Unit
              </span>
              <input
                {...form.register("simulationSweepUnit")}
                className="mt-2 w-full bg-transparent text-sm text-foreground outline-none"
                placeholder="nH"
              />
            </label>
          </div>

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
          {form.formState.errors.simulationSweepValues ? (
            <p className="text-sm text-rose-700 dark:text-rose-300">
              {form.formState.errors.simulationSweepValues.message}
            </p>
          ) : null}

          <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_auto]">
            <div className="rounded-[0.95rem] border border-border bg-surface px-4 py-4 text-sm text-muted-foreground">
              <p className="text-xs uppercase tracking-[0.16em] text-muted-foreground">
                Submission Preview
              </p>
              <p className="mt-2 text-foreground">{simulationRequestPreview}</p>
              {latestSimulationTaskDetail?.simulationSetup ? (
                <p className="mt-2 text-xs text-muted-foreground">
                  Latest simulation setup was rehydrated from task #{latestSimulationTaskDetail.taskId}.
                </p>
              ) : null}
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
