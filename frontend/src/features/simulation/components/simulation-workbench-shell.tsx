"use client";

import { useEffect, useMemo, useRef, useState, useTransition } from "react";
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
  Save,
  Settings2,
  Trash2,
  WandSparkles,
  Workflow,
  X,
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
  cloneSimulationSetupFormValues,
  createDefaultSimulationParameterSweepAxis,
  createDefaultSimulationSource,
  defaultSimulationSetupFormValues,
  deriveSimulationPtcPortOptions,
  deriveSimulationSweepTargetOptions,
  parseCommaSeparatedStringValues,
  simulationSetupFormSchema,
  type SimulationSetupFormValues,
} from "@/features/simulation/lib/setup-form";
import {
  createSavedSimulationSetupRecord,
  filterSavedSimulationSetupsByDefinition,
  readSavedSimulationSetupRecords,
  removeSavedSimulationSetupRecord,
  replaceSavedSimulationSetupRecord,
  SAVED_SIMULATION_SETUPS_STORAGE_KEY,
  serializeSavedSimulationSetupRecords,
  type SavedSimulationSetupRecord,
} from "@/features/simulation/lib/saved-setups";
import {
  buildSimulationRequestSummary,
  formatSimulationTaskStatusLabel,
  hasSimulationTaskResult,
  resolvePostProcessingUpstreamTaskId,
  resolveSimulationSelectionRecovery,
  summarizeSimulationTaskResults,
} from "@/features/simulation/lib/workflow";
import {
  AppInlineSelect,
  AppSelectField,
  type AppSelectOption,
} from "@/features/shared/components/app-select";
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

const FREQUENCY_WHEEL_STEP_GHZ = 0.001;

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
  detail?: string;
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
          {detail ? <p className="mt-1 text-xs text-muted-foreground">{detail}</p> : null}
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
          <p className="mt-1 text-sm leading-6 text-muted-foreground">{description}</p>
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

function CompactField({
  label,
  detail,
  headerAside,
  children,
  error,
  className,
}: Readonly<{
  label: string;
  detail?: string;
  headerAside?: React.ReactNode;
  children: React.ReactNode;
  error?: string;
  className?: string;
}>) {
  return (
    <label className={cx("block min-w-0", className)}>
      <span className="flex items-start justify-between gap-3">
        <span className="text-[11px] font-semibold uppercase tracking-[0.16em] text-muted-foreground">
          {label}
        </span>
        {headerAside ? (
          <span className="text-[11px] text-muted-foreground">{headerAside}</span>
        ) : null}
      </span>
      {detail ? <span className="mt-1 block text-xs leading-5 text-muted-foreground">{detail}</span> : null}
      <div className="mt-2">{children}</div>
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

function countDecimalPlaces(rawValue: string) {
  if (!rawValue) {
    return 0;
  }

  const normalized = rawValue.trim().toLowerCase();
  if (!normalized) {
    return 0;
  }

  const exponentIndex = normalized.indexOf("e");
  if (exponentIndex >= 0) {
    const mantissa = normalized.slice(0, exponentIndex);
    const exponent = Number(normalized.slice(exponentIndex + 1));
    const mantissaPlaces = mantissa.split(".")[1]?.length ?? 0;
    if (!Number.isFinite(exponent)) {
      return mantissaPlaces;
    }
    return Math.max(0, mantissaPlaces - exponent);
  }

  return normalized.split(".")[1]?.length ?? 0;
}

function resolveWheelStep(input: HTMLInputElement) {
  const stepAttribute = input.getAttribute("step");
  if (stepAttribute && stepAttribute !== "any") {
    const parsedStep = Number(stepAttribute);
    if (Number.isFinite(parsedStep) && parsedStep > 0) {
      return parsedStep;
    }
  }

  const precision = countDecimalPlaces(input.value);
  return precision > 0 ? 10 ** -precision : 1;
}

function SetupNumberInput(props: Readonly<React.InputHTMLAttributes<HTMLInputElement>>) {
  const inputRef = useRef<HTMLInputElement | null>(null);
  const lastWheelAdjustmentAtRef = useRef<number>(0);

  useEffect(() => {
    const input = inputRef.current;
    if (!input) {
      return undefined;
    }

    const handleWheel = (event: WheelEvent) => {
      const isTargetInput = event.target instanceof Node && input.contains(event.target);
      const isActiveInput = document.activeElement === input;
      const isHoveredInput = input.matches(":hover");
      if (!isTargetInput && !isActiveInput && !isHoveredInput) {
        return;
      }

      event.preventDefault();
      event.stopPropagation();

      if (event.timeStamp - lastWheelAdjustmentAtRef.current < 80) {
        return;
      }
      lastWheelAdjustmentAtRef.current = event.timeStamp;

      if (input.disabled || input.readOnly) {
        return;
      }
      const direction = event.deltaY < 0 ? 1 : -1;
      const originalStepAttribute = input.getAttribute("step");
      const temporaryStep =
        originalStepAttribute === null || originalStepAttribute === "any"
          ? String(resolveWheelStep(input))
          : null;

      if (temporaryStep) {
        input.setAttribute("step", temporaryStep);
      }

      const previousValue = input.value;
      try {
        if (direction > 0) {
          input.stepUp();
        } else {
          input.stepDown();
        }
      } finally {
        if (temporaryStep) {
          if (originalStepAttribute === null) {
            input.removeAttribute("step");
          } else {
            input.setAttribute("step", originalStepAttribute);
          }
        }
      }

      if (input.value === previousValue) {
        return;
      }

      input.dispatchEvent(new Event("input", { bubbles: true }));
      input.dispatchEvent(new Event("change", { bubbles: true }));
    };

    const listenerOptions = { passive: false, capture: true } as const;
    input.addEventListener("wheel", handleWheel, listenerOptions);
    return () => {
      input.removeEventListener("wheel", handleWheel, listenerOptions);
    };
  }, []);

  return (
    <input
      {...props}
      ref={inputRef}
      type="number"
      className={cx(
        "w-full rounded-[0.8rem] border border-border bg-surface px-3 py-2.5 text-sm text-foreground outline-none transition placeholder:text-muted-foreground focus:border-primary/45 focus:ring-2 focus:ring-primary/15 disabled:opacity-60",
        props.className,
      )}
    />
  );
}

function LocalDraftBadge() {
  return <SurfaceTag>Browser-local only</SurfaceTag>;
}

function SetupSlideToggle({
  checked,
  onCheckedChange,
  label,
  description,
  className,
  disabled = false,
}: Readonly<{
  checked: boolean;
  onCheckedChange: (nextChecked: boolean) => void;
  label: string;
  description?: string;
  className?: string;
  disabled?: boolean;
}>) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      disabled={disabled}
      onClick={() => {
        if (!disabled) {
          onCheckedChange(!checked);
        }
      }}
      className={cx(
        "flex w-full cursor-pointer items-center justify-between gap-4 rounded-[0.95rem] border px-4 py-3 text-left transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/25 disabled:cursor-not-allowed disabled:opacity-60",
        checked
          ? "border-primary/35 bg-primary/10"
          : "border-border bg-background hover:border-primary/25 hover:bg-primary/5",
        className,
      )}
    >
      <span className={cx("min-w-0", !disabled && "cursor-pointer")}>
        <span className={cx("block text-sm font-medium text-foreground", !disabled && "cursor-pointer")}>{label}</span>
        {description ? (
          <span
            className={cx(
              "mt-1 block text-xs leading-5 text-muted-foreground",
              !disabled && "cursor-pointer",
            )}
          >
            {description}
          </span>
        ) : null}
      </span>
      <span
        className={cx(
          "relative inline-flex h-7 w-12 shrink-0 items-center rounded-full border transition",
          checked
            ? "border-primary/30 bg-primary"
            : "border-border bg-muted/70",
          !disabled && "cursor-pointer",
        )}
      >
        <span
          className={cx(
            "inline-flex h-5 w-5 rounded-full bg-white shadow-[0_4px_12px_rgba(15,23,42,0.22)] transition-transform",
            checked ? "translate-x-6" : "translate-x-1",
            !disabled && "cursor-pointer",
          )}
        />
      </span>
    </button>
  );
}

function OverlayDialog({
  open,
  title,
  description,
  children,
  onClose,
}: Readonly<{
  open: boolean;
  title: string;
  description: string;
  children: React.ReactNode;
  onClose: () => void;
}>) {
  if (!open) {
    return null;
  }

  return (
    <div
      role="dialog"
      aria-modal="true"
      className="fixed inset-0 z-50 flex items-center justify-center bg-background/80 px-4 backdrop-blur-sm"
    >
      <div className="w-full max-w-3xl rounded-[1.1rem] border border-border bg-card shadow-[0_28px_90px_rgba(0,0,0,0.38)]">
        <div className="flex items-start justify-between gap-4 border-b border-border px-5 py-4">
          <div className="min-w-0">
            <h2 className="text-base font-semibold text-foreground">{title}</h2>
            <p className="mt-2 text-sm leading-6 text-muted-foreground">{description}</p>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="inline-flex h-10 w-10 cursor-pointer items-center justify-center rounded-full border border-border bg-background text-muted-foreground transition hover:border-primary/35 hover:bg-primary/10 hover:text-foreground"
          >
            <X className="h-4 w-4" />
          </button>
        </div>
        <div className="max-h-[70vh] overflow-y-auto px-5 py-5">{children}</div>
      </div>
    </div>
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
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const [, startTransition] = useTransition();
  const [isRefreshingWorkflow, setIsRefreshingWorkflow] = useState(false);
  const [isAdvancedHbsolveExpanded, setIsAdvancedHbsolveExpanded] = useState(false);
  const [simulationSetupBuildError, setSimulationSetupBuildError] = useState<string | null>(null);
  const [savedSimulationSetups, setSavedSimulationSetups] = useState<
    readonly SavedSimulationSetupRecord[]
  >([]);
  const [hasHydratedSavedSetups, setHasHydratedSavedSetups] = useState(false);
  const [selectedSavedSetupId, setSelectedSavedSetupId] = useState<string | null>(null);
  const [isSaveDialogOpen, setIsSaveDialogOpen] = useState(false);
  const [isManageDialogOpen, setIsManageDialogOpen] = useState(false);
  const [saveSetupNameDraft, setSaveSetupNameDraft] = useState("");
  const [savedSetupFeedback, setSavedSetupFeedback] = useState<string | null>(null);

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
  const watchedSimulationSources = form.watch("simulationSources");
  const selectedPtcPortsValue = form.watch("simulationPtcCompensatePorts");

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
  const selectedDefinitionDisplay =
    selectedDefinitionSummary ??
    (activeDefinition
      ? {
          definition_id: activeDefinition.definition_id,
          name: activeDefinition.name,
          preview_artifact_count: activeDefinition.preview_artifacts.length,
        }
      : null);
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
    () => {
      const options = (definitions ?? []).map((definition) => ({
        value: String(definition.definition_id),
        label: definition.name,
        description: `Definition #${definition.definition_id} · ${definition.preview_artifact_count} preview artifacts`,
      }));

      if (options.length > 0 || !activeDefinition) {
        return options;
      }

      return [
        {
          value: String(activeDefinition.definition_id),
          label: activeDefinition.name,
          description: `Definition #${activeDefinition.definition_id} · ${activeDefinition.preview_artifacts.length} preview artifacts`,
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
  const postProcessingRequestPreview = buildSimulationRequestSummary({
    kind: "post_processing",
    definitionId: resolvedDefinitionId,
    definitionName: selectedDefinitionDisplay?.name ?? null,
    datasetId: activeDatasetState.activeDataset?.datasetId ?? null,
    datasetName: activeDatasetState.activeDataset?.name ?? null,
    note: form.watch("postProcessingNote"),
  });
  const visibleSavedSetups = useMemo(
    () => filterSavedSimulationSetupsByDefinition(savedSimulationSetups, resolvedDefinitionId),
    [resolvedDefinitionId, savedSimulationSetups],
  );
  const activeSavedSetup =
    visibleSavedSetups.find((setup) => setup.id === selectedSavedSetupId) ?? null;
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
  const selectedPtcPorts = useMemo(
    () => new Set(parseCommaSeparatedStringValues(selectedPtcPortsValue)),
    [selectedPtcPortsValue],
  );
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

  useEffect(() => {
    if (typeof window === "undefined") {
      return;
    }

    setSavedSimulationSetups(
      readSavedSimulationSetupRecords(
        window.localStorage.getItem(SAVED_SIMULATION_SETUPS_STORAGE_KEY),
      ),
    );
    setHasHydratedSavedSetups(true);
  }, []);

  useEffect(() => {
    if (!hasHydratedSavedSetups || typeof window === "undefined") {
      return;
    }

    window.localStorage.setItem(
      SAVED_SIMULATION_SETUPS_STORAGE_KEY,
      serializeSavedSimulationSetupRecords(savedSimulationSetups),
    );
  }, [hasHydratedSavedSetups, savedSimulationSetups]);

  useEffect(() => {
    if (!selectedSavedSetupId) {
      return;
    }

    if (!visibleSavedSetups.some((setup) => setup.id === selectedSavedSetupId)) {
      setSelectedSavedSetupId(null);
    }
  }, [selectedSavedSetupId, visibleSavedSetups]);

  function snapshotCurrentSimulationSetup(): SimulationSetupFormValues {
    const values = form.getValues();
    return cloneSimulationSetupFormValues({
      simulationStartGhz: values.simulationStartGhz,
      simulationStopGhz: values.simulationStopGhz,
      simulationPointCount: values.simulationPointCount,
      simulationSpacing: values.simulationSpacing,
      simulationParameterSweepEnabled: values.simulationParameterSweepEnabled,
      simulationParameterSweepAxes: values.simulationParameterSweepAxes,
      simulationSolverFamily: values.simulationSolverFamily,
      simulationMaxIterations: values.simulationMaxIterations,
      simulationConvergenceTolerance: values.simulationConvergenceTolerance,
      simulationHarmonicBalanceEnabled: values.simulationHarmonicBalanceEnabled,
      simulationHarmonicCount: values.simulationHarmonicCount,
      simulationOversampleFactor: values.simulationOversampleFactor,
      simulationSources: values.simulationSources,
      simulationPtcEnabled: values.simulationPtcEnabled,
      simulationPtcMode: values.simulationPtcMode,
      simulationPtcCompensatePorts: values.simulationPtcCompensatePorts,
      simulationPtcManualNotes: values.simulationPtcManualNotes,
      simulationAdvancedDampingStrategy: values.simulationAdvancedDampingStrategy,
      simulationAdvancedLineSearchEnabled: values.simulationAdvancedLineSearchEnabled,
      simulationAdvancedResidualClamp: values.simulationAdvancedResidualClamp,
      simulationAdvancedNewtonRelaxation: values.simulationAdvancedNewtonRelaxation,
      simulationAdvancedNotes: values.simulationAdvancedNotes,
    });
  }

  function buildSavedSetupNameSuggestion() {
    const baseName = selectedDefinitionDisplay?.name ?? "Simulation Setup";
    const nextIndex = visibleSavedSetups.length + 1;
    return `${baseName} ${nextIndex}`;
  }

  function applySavedSetup(record: SavedSimulationSetupRecord) {
    form.reset(
      {
        ...form.getValues(),
        ...cloneSimulationSetupFormValues(record.values),
      },
      { keepDefaultValues: true },
    );
    setSelectedSavedSetupId(record.id);
    setSavedSetupFeedback(`Loaded saved setup “${record.name}”.`);
    setSimulationSetupBuildError(null);
    setIsSaveDialogOpen(false);
    setIsManageDialogOpen(false);
  }

  function persistSavedSetup(name: string, existingRecordId?: string | null) {
    if (resolvedDefinitionId === null) {
      setSavedSetupFeedback("Select a definition before saving a setup.");
      return;
    }

    const trimmedName = name.trim();
    if (!trimmedName) {
      setSavedSetupFeedback("Saved setup name is required.");
      return;
    }

    const existingRecord = existingRecordId
      ? visibleSavedSetups.find((record) => record.id === existingRecordId) ?? null
      : null;
    const nowIso = new Date().toISOString();
    const nextRecord = createSavedSimulationSetupRecord({
      id: existingRecord?.id ?? (typeof crypto !== "undefined" ? crypto.randomUUID() : `setup-${Date.now()}`),
      definitionId: resolvedDefinitionId,
      definitionName: selectedDefinitionDisplay?.name ?? null,
      name: trimmedName,
      createdAt: existingRecord?.createdAt ?? nowIso,
      updatedAt: nowIso,
      values: snapshotCurrentSimulationSetup(),
    });

    setSavedSimulationSetups((current) => replaceSavedSimulationSetupRecord(current, nextRecord));
    setSelectedSavedSetupId(nextRecord.id);
    setSavedSetupFeedback(
      existingRecord
        ? `Updated saved setup “${nextRecord.name}”.`
        : `Saved “${nextRecord.name}” in this browser.`,
    );
    setSaveSetupNameDraft(nextRecord.name);
    setIsSaveDialogOpen(false);
  }

  function handleSaveSetup() {
    if (activeSavedSetup) {
      persistSavedSetup(activeSavedSetup.name, activeSavedSetup.id);
      return;
    }

    setSaveSetupNameDraft(buildSavedSetupNameSuggestion());
    setIsSaveDialogOpen(true);
  }

  function deleteSavedSetup(recordId: string) {
    const record = savedSimulationSetups.find((entry) => entry.id === recordId);
    setSavedSimulationSetups((current) => removeSavedSimulationSetupRecord(current, recordId));
    if (selectedSavedSetupId === recordId) {
      setSelectedSavedSetupId(null);
    }
    setSavedSetupFeedback(
      record ? `Deleted saved setup “${record.name}”.` : "Deleted saved setup.",
    );
  }

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
      simulationSetup =
        kind === "simulation"
          ? buildSimulationSetupDraft(values)
          : null;
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
              <button
                type="button"
                onClick={() => {
                  setIsManageDialogOpen(true);
                }}
                disabled={resolvedDefinitionId === null}
                className="inline-flex cursor-pointer items-center gap-2 rounded-full border border-border bg-background px-3 py-2 text-xs font-medium text-foreground transition hover:border-primary/35 hover:bg-primary/10 disabled:cursor-not-allowed disabled:opacity-60"
              >
                <Settings2 className="h-3.5 w-3.5" />
                Manage
              </button>
              <button
                type="button"
                onClick={handleSaveSetup}
                disabled={resolvedDefinitionId === null}
                className="inline-flex cursor-pointer items-center gap-2 rounded-full border border-primary/30 bg-primary/10 px-3 py-2 text-xs font-medium text-foreground transition hover:border-primary/45 hover:bg-primary/15 disabled:cursor-not-allowed disabled:opacity-60"
              >
                <Save className="h-3.5 w-3.5" />
                Save
              </button>
            </div>
          }
        >
          {simulationSetupState.label !== "Not started" ? (
            <StageNotice
              tone={simulationSetupState.tone}
              title={`Simulation Setup · ${simulationSetupState.label}`}
              message={simulationSetupState.message}
            />
          ) : null}

          <div className="flex flex-wrap items-center gap-2 rounded-[0.95rem] border border-border bg-surface px-4 py-3 text-xs">
            {activeSavedSetup ? (
              <SurfaceTag tone="success">Saved · {activeSavedSetup.name}</SurfaceTag>
            ) : (
              <SurfaceTag tone="default">Unsaved draft</SurfaceTag>
            )}
            <span className="leading-5 text-muted-foreground">
              Browser-saved per selected definition.
            </span>
            {latestSimulationTaskDetail?.simulationSetup ? (
              <span className="leading-5 text-muted-foreground">
                Rehydrated from task #{latestSimulationTaskDetail.taskId}.
              </span>
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
                  <SetupNumberInput
                    {...form.register("simulationStartGhz", { valueAsNumber: true })}
                    step={String(FREQUENCY_WHEEL_STEP_GHZ)}
                    min={String(FREQUENCY_WHEEL_STEP_GHZ)}
                  />
                </CompactField>
                <CompactField
                  label="Stop Freq (GHz)"
                  error={form.formState.errors.simulationStopGhz?.message}
                >
                  <SetupNumberInput
                    {...form.register("simulationStopGhz", { valueAsNumber: true })}
                    step={String(FREQUENCY_WHEEL_STEP_GHZ)}
                    min={String(FREQUENCY_WHEEL_STEP_GHZ)}
                  />
                </CompactField>
                <CompactField
                  label="Points"
                  error={form.formState.errors.simulationPointCount?.message}
                >
                  <SetupNumberInput
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
                              <SetupNumberInput
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
                              <SetupNumberInput
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
                              <SetupNumberInput
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
                  <SetupNumberInput
                    {...form.register("simulationHarmonicCount", { valueAsNumber: true })}
                    min={1}
                    disabled={!harmonicBalanceEnabled}
                  />
                </CompactField>
                <CompactField
                  label="Npump Harmonics"
                  error={form.formState.errors.simulationOversampleFactor?.message}
                >
                  <SetupNumberInput
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
                          <SetupNumberInput
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
                          <SetupNumberInput
                            {...form.register(`simulationSources.${index}.currentAmp`, {
                              valueAsNumber: true,
                            })}
                            step="any"
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
            description="Choose the schema-defined ports for the browser-local PTC draft."
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
            <div className="rounded-[0.95rem] border border-border bg-background px-4 py-4">
              <p className="text-xs leading-5 text-muted-foreground">
                Browser-local only. PTC selections are not submitted with the task and do not
                rehydrate from persisted runs.
              </p>

              <div className="grid gap-4 lg:grid-cols-[minmax(260px,1fr)_220px]">
                <SetupSlideToggle
                  checked={ptcEnabled}
                  label="Enable PTC draft"
                  description={
                    ptcPortOptions.length > 0
                      ? "PTC stays browser-local for now and uses schema-derived ports."
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
                <LocalDraftBadge />
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
                      <SetupNumberInput
                        {...form.register("simulationMaxIterations", { valueAsNumber: true })}
                        min={1}
                      />
                    </CompactField>
                    <CompactField
                      label="Convergence Tolerance"
                      error={form.formState.errors.simulationConvergenceTolerance?.message}
                    >
                      <SetupNumberInput
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

          <SetupSlideToggle
            checked={form.watch("postOperationEnabled")}
            label="Enable operation"
            description="Controls whether this post-processing operation is included in the downstream payload."
            onCheckedChange={(nextChecked) => {
              form.setValue("postOperationEnabled", nextChecked, {
                shouldDirty: true,
              });
            }}
          />

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

      <OverlayDialog
        open={isSaveDialogOpen}
        title="Save Simulation Setup"
        description="Store the current Simulation Setup locally in this browser for the selected definition. This does not create a backend resource."
        onClose={() => {
          setIsSaveDialogOpen(false);
        }}
      >
        <div className="space-y-4">
          <SetupInputField label="Setup Name">
            <SetupTextInput
              value={saveSetupNameDraft}
              onChange={(event) => {
                setSaveSetupNameDraft(event.target.value);
              }}
              placeholder={buildSavedSetupNameSuggestion()}
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
            <button
              type="button"
              onClick={() => {
                persistSavedSetup(saveSetupNameDraft, activeSavedSetup?.id ?? null);
              }}
              className="inline-flex cursor-pointer items-center gap-2 rounded-md bg-primary px-3 py-2 text-sm font-medium text-primary-foreground transition hover:opacity-90"
            >
              <Save className="h-4 w-4" />
              Save Setup
            </button>
          </div>
        </div>
      </OverlayDialog>

      <OverlayDialog
        open={isManageDialogOpen}
        title="Manage Saved Setups"
        description="Review saved Simulation Setup drafts for the current definition, load one into Stage 2, or remove old drafts."
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
                setIsManageDialogOpen(false);
                setSaveSetupNameDraft(buildSavedSetupNameSuggestion());
                setIsSaveDialogOpen(true);
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
