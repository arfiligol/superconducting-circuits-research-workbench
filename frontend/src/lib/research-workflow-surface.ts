import type { TaskEventHistorySummary } from "@/lib/task-event-history";
import type {
  TaskConnectionState,
  TaskLifecycleSummary,
  TaskResultSurfaceSummary,
} from "@/lib/task-surface";

type SurfaceTone = "default" | "primary" | "success" | "warning";

export type ResearchWorkflowHierarchyCard = Readonly<{
  id: "attachment" | "dispatch" | "events" | "results";
  label: string;
  value: string;
  detail: string;
  tone: SurfaceTone;
}>;

export type ResearchWorkflowSurfaceSummary = Readonly<{
  statusLabel: string;
  statusTone: SurfaceTone;
  persistenceLabel: string;
  cards: readonly ResearchWorkflowHierarchyCard[];
  warningEventCount: number;
  errorEventCount: number;
  materializedHandleCount: number;
  pendingHandleCount: number;
  hasTracePayload: boolean;
}>;

function summarizeAttachmentState(
  connectionState: TaskConnectionState,
): ResearchWorkflowHierarchyCard {
  if (
    connectionState.selectedTaskId === null &&
    connectionState.attachedTaskId === null &&
    connectionState.latestTaskId === null
  ) {
    return {
      id: "attachment",
      label: "Attachment",
      value: "Awaiting task",
      detail: "Submit or attach a persisted task to anchor the workflow surface.",
      tone: "default",
    };
  }

  if (
    connectionState.isStaleSnapshot &&
    connectionState.attachedTaskId !== null &&
    connectionState.selectedTaskId !== null
  ) {
    return {
      id: "attachment",
      label: "Attachment",
      value: `Holding #${connectionState.attachedTaskId}`,
      detail: `Task #${connectionState.selectedTaskId} is reattaching while the current persisted snapshot stays visible.`,
      tone: "warning",
    };
  }

  if (connectionState.isFollowingLatest && connectionState.selectedTaskId !== null) {
    return {
      id: "attachment",
      label: "Attachment",
      value: `Latest #${connectionState.selectedTaskId}`,
      detail: "The surface follows the newest persisted task until a URL-pinned task overrides it.",
      tone: "success",
    };
  }

  if (connectionState.mode === "explicit" && connectionState.selectedTaskId !== null) {
    return {
      id: "attachment",
      label: "Attachment",
      value: `Pinned #${connectionState.selectedTaskId}`,
      detail: connectionState.isAttached
        ? "A URL-selected persisted task is actively attached."
        : "The selected persisted task is still attaching into the workflow surface.",
      tone: connectionState.isAttached ? "primary" : "warning",
    };
  }

  if (connectionState.selectedTaskId !== null) {
    return {
      id: "attachment",
      label: "Attachment",
      value: `Task #${connectionState.selectedTaskId}`,
      detail: "Resolved from the latest persisted queue activity for this workflow lane.",
      tone: "primary",
    };
  }

  return {
    id: "attachment",
    label: "Attachment",
    value: "Task pending",
    detail: "Persisted task selection is still resolving.",
    tone: "default",
  };
}

function summarizeDispatchState(
  lifecycleSummary: TaskLifecycleSummary,
): ResearchWorkflowHierarchyCard {
  return {
    id: "dispatch",
    label: "Dispatch",
    value: lifecycleSummary.statusLabel,
    detail: lifecycleSummary.summary,
    tone: lifecycleSummary.tone,
  };
}

function summarizeEventState(
  eventHistorySummary: TaskEventHistorySummary,
): ResearchWorkflowHierarchyCard {
  const detail =
    eventHistorySummary.total > 0
      ? `${eventHistorySummary.total} persisted events · ${eventHistorySummary.progressLabel ?? "no progress label yet"}`
      : "No persisted event records are attached to the current task yet.";
  const tone =
    eventHistorySummary.errorCount > 0
      ? "warning"
      : eventHistorySummary.warningCount > 0
        ? "warning"
        : eventHistorySummary.total > 0
          ? "primary"
          : "default";

  return {
    id: "events",
    label: "Events",
    value: eventHistorySummary.latestEventLabel ?? eventHistorySummary.terminalStateLabel,
    detail,
    tone,
  };
}

function summarizeResultState(
  resultSummary: TaskResultSurfaceSummary,
): ResearchWorkflowHierarchyCard {
  if (resultSummary.materializedHandleCount > 0) {
    return {
      id: "results",
      label: "Results",
      value: `${resultSummary.materializedHandleCount} materialized`,
      detail: `${resultSummary.pendingHandleCount} pending handles remain${resultSummary.hasTracePayload ? " and a trace payload is attached." : "."}`,
      tone: "success",
    };
  }

  if (resultSummary.pendingHandleCount > 0) {
    return {
      id: "results",
      label: "Results",
      value: `${resultSummary.pendingHandleCount} pending`,
      detail: resultSummary.hasTracePayload
        ? "Trace payload authority is attached while result handles are still pending."
        : "Result handles are registered but not materialized yet.",
      tone: "primary",
    };
  }

  return {
    id: "results",
    label: "Results",
    value: "Awaiting outputs",
    detail: resultSummary.hasTracePayload
      ? "Trace payload authority is present, but no result handles are materialized yet."
      : "No persisted trace payload or result handles are attached yet.",
    tone: "default",
  };
}

export function summarizeResearchWorkflowSurface(input: Readonly<{
  connectionState: TaskConnectionState;
  lifecycleSummary: TaskLifecycleSummary;
  eventHistorySummary: TaskEventHistorySummary;
  resultSummary: TaskResultSurfaceSummary;
}>): ResearchWorkflowSurfaceSummary {
  const attachmentCard = summarizeAttachmentState(input.connectionState);
  const dispatchCard = summarizeDispatchState(input.lifecycleSummary);
  const eventCard = summarizeEventState(input.eventHistorySummary);
  const resultCard = summarizeResultState(input.resultSummary);
  const persistenceLabel =
    input.connectionState.attachedTaskId !== null
      ? input.connectionState.isStaleSnapshot
        ? `Persisted snapshot #${input.connectionState.attachedTaskId} retained during reattach`
        : `Persisted task #${input.connectionState.attachedTaskId} attached`
      : "No persisted task attached";

  return {
    statusLabel: input.lifecycleSummary.statusLabel,
    statusTone: input.lifecycleSummary.tone,
    persistenceLabel,
    cards: [attachmentCard, dispatchCard, eventCard, resultCard],
    warningEventCount: input.eventHistorySummary.warningCount,
    errorEventCount: input.eventHistorySummary.errorCount,
    materializedHandleCount: input.resultSummary.materializedHandleCount,
    pendingHandleCount: input.resultSummary.pendingHandleCount,
    hasTracePayload: input.resultSummary.hasTracePayload,
  };
}
