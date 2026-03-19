import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

import { describe, expect, it } from "vitest";

import {
  buildTasksBrowseSearch,
  buildTasksListQueryFromBrowseState,
  buildWorkerLaneInspectionRows,
  parseTasksBrowseState,
  resolveSelectedTaskId,
  resolveTasksDefaultScope,
  summarizeTasksWorkspace,
} from "../src/features/tasks/lib/tasks-browse-state";

const tasksWorkspaceSource = readFileSync(
  fileURLToPath(
    new URL("../src/features/tasks/components/tasks-workspace.tsx", import.meta.url),
  ),
  "utf8",
);
const tasksPageSource = readFileSync(
  fileURLToPath(new URL("../src/app/(workspace)/tasks/page.tsx", import.meta.url)),
  "utf8",
);
const taskPanelsSource = readFileSync(
  fileURLToPath(
    new URL("../src/features/shared/components/task-workflow-panels.tsx", import.meta.url),
  ),
  "utf8",
);
const statusStripSource = readFileSync(
  fileURLToPath(
    new URL("../src/components/layout/workspace-status-strip.tsx", import.meta.url),
  ),
  "utf8",
);
const tasksApiSource = readFileSync(
  fileURLToPath(new URL("../src/lib/api/tasks.ts", import.meta.url)),
  "utf8",
);

describe("tasks browse helpers", () => {
  it("resolves scope defaults from runtime mode and session defaults", () => {
    expect(resolveTasksDefaultScope("local", "workspace")).toBe("local");
    expect(resolveTasksDefaultScope("online", "owned")).toBe("owned");
    expect(resolveTasksDefaultScope("online", null)).toBe("workspace");
  });

  it("parses and rebuilds URL-bound browse state", () => {
    expect(
      parseTasksBrowseState("?taskId=31&scope=owned&status=running&lane=simulation&q=flux", "workspace"),
    ).toEqual({
      taskId: 31,
      scope: "owned",
      status: "running",
      lane: "simulation",
      searchQuery: "flux",
    });

    expect(
      buildTasksBrowseSearch(
        "?taskId=31&scope=owned&status=running&lane=simulation&q=flux",
        {
          taskId: 55,
          scope: "workspace",
          status: "all",
          lane: "all",
          searchQuery: "",
        },
        "workspace",
      ),
    ).toBe("?taskId=55");
  });

  it("builds backend query input and resolves queue-backed selection", () => {
    const browseState = parseTasksBrowseState("?scope=owned&status=failed&q=retry", "workspace");

    expect(buildTasksListQueryFromBrowseState(browseState)).toEqual({
      scope: "owned",
      status: "failed",
      lane: undefined,
      searchQuery: "retry",
      limit: 50,
    });

    expect(
      resolveSelectedTaskId(null, {
        rows: [
          {
            taskId: 77,
            kind: "simulation",
            lane: "simulation",
            executionMode: "run",
            status: "running",
            submittedAt: "2026-03-19T00:00:00Z",
            ownerUserId: "user-1",
            ownerDisplayName: "Device Lab",
            workspaceId: "workspace-lab",
            workspaceSlug: "device-lab",
            visibilityScope: "workspace",
            datasetId: "fluxonium-2025-031",
            definitionId: 18,
            summary: "Simulation request",
            resultAvailability: "pending",
            controlState: "none",
            hasActionAuthority: true,
            allowedActions: {
              attach: true,
              cancel: true,
              terminate: true,
              retry: false,
              rejectionReason: null,
            },
          },
        ],
        workerSummary: [],
        generatedAt: null,
        totalCount: 1,
        nextCursor: null,
        prevCursor: null,
        hasMore: false,
      }),
    ).toBe(77);
  });

  it("summarizes queue state and binds lane inspection to backend rows", () => {
    const queue = {
      rows: [
        {
          taskId: 91,
          kind: "simulation",
          lane: "simulation",
          executionMode: "run",
          status: "running",
          submittedAt: "2026-03-19T00:00:00Z",
          ownerUserId: "user-1",
          ownerDisplayName: "Device Lab",
          workspaceId: "workspace-lab",
          workspaceSlug: "device-lab",
          visibilityScope: "workspace",
          datasetId: "fluxonium-2025-031",
          definitionId: 18,
          summary: "Simulation request",
          resultAvailability: "pending",
          controlState: "none",
          hasActionAuthority: true,
          allowedActions: {
            attach: true,
            cancel: true,
            terminate: true,
            retry: false,
            rejectionReason: null,
          },
        },
        {
          taskId: 92,
          kind: "characterization",
          lane: "characterization",
          executionMode: "run",
          status: "completed",
          submittedAt: "2026-03-19T00:05:00Z",
          ownerUserId: "user-2",
          ownerDisplayName: "Analysis Team",
          workspaceId: "workspace-lab",
          workspaceSlug: "device-lab",
          visibilityScope: "owned",
          datasetId: "fluxonium-2025-031",
          definitionId: null,
          summary: "Characterization request",
          resultAvailability: "ready",
          controlState: "none",
          hasActionAuthority: true,
          allowedActions: {
            attach: true,
            cancel: false,
            terminate: false,
            retry: true,
            rejectionReason: null,
          },
        },
      ],
      workerSummary: [
        {
          lane: "simulation",
          healthyProcessors: 1,
          busyProcessors: 1,
          degradedProcessors: 0,
          drainingProcessors: 0,
          offlineProcessors: 0,
        },
      ],
      generatedAt: "2026-03-19T00:10:00Z",
      totalCount: 2,
      nextCursor: null,
      prevCursor: null,
      hasMore: false,
    } as const;

    expect(summarizeTasksWorkspace(queue)).toEqual({
      visibleCount: 2,
      activeCount: 1,
      resultReadyCount: 1,
      failedCount: 0,
      workerLaneCount: 1,
    });

    expect(buildWorkerLaneInspectionRows(queue.workerSummary, queue.rows)).toEqual([
      {
        lane: "simulation",
        healthyProcessors: 1,
        busyProcessors: 1,
        degradedProcessors: 0,
        drainingProcessors: 0,
        offlineProcessors: 0,
        activeTaskIds: [91],
        latestTaskId: 91,
      },
    ]);
  });
});

describe("tasks workspace source contracts", () => {
  it("creates the standalone route and feature-owned workspace component", () => {
    expect(tasksPageSource).toContain("TasksWorkspace");
    expect(tasksPageSource).toContain("Loading tasks workspace");
  });

  it("keeps /tasks as a master-detail surface with filter bar, queue list, detail panel, and worker inspection", () => {
    expect(tasksWorkspaceSource).toContain('title="Browse Filters"');
    expect(tasksWorkspaceSource).toContain('title="Queue History"');
    expect(tasksWorkspaceSource).toContain('title="Task Detail"');
    expect(tasksWorkspaceSource).toContain('title="Worker / Lane Inspection"');
    expect(tasksWorkspaceSource).toContain("TaskLifecyclePanel");
    expect(tasksWorkspaceSource).toContain("TaskEventHistoryPanel");
    expect(tasksWorkspaceSource).toContain("TaskResultPanel");
    expect(tasksWorkspaceSource).not.toContain("Runtime Mode");
    expect(tasksWorkspaceSource).not.toContain("Active Dataset");
    expect(tasksWorkspaceSource).not.toContain("Active Workspace");
  });

  it("binds browse state to URL params and uses backend-owned queue/detail/event contracts", () => {
    expect(tasksWorkspaceSource).toContain("buildTasksBrowseSearch");
    expect(tasksWorkspaceSource).toContain("parseTasksBrowseState");
    expect(tasksWorkspaceSource).toContain("buildTasksListKey");
    expect(tasksWorkspaceSource).toContain("taskEventsKey");
    expect(tasksWorkspaceSource).toContain("listTasks(queueQueryInput)");
    expect(tasksWorkspaceSource).toContain("getTaskEvents(selectedTaskId");
    expect(tasksWorkspaceSource).toContain("cancelTask(selectedTaskId)");
    expect(tasksWorkspaceSource).toContain("terminateTask(selectedTaskId)");
    expect(tasksWorkspaceSource).toContain("retryTask(selectedTaskId)");
  });

  it("adds open-tasks-page entry points from shell queue and persisted task detail support", () => {
    expect(statusStripSource).toContain("Open Tasks Page");
    expect(statusStripSource).toContain("onOpenChange(false)");
    expect(statusStripSource).toContain("router.push(tasksPageHref)");
    expect(taskPanelsSource).toContain("showTasksPageLink");
    expect(taskPanelsSource).toContain('href={`/tasks?taskId=${task.taskId}`}');
  });

  it("extends the tasks API layer with list queries, event history, and control mutations", () => {
    expect(tasksApiSource).toContain("export type TaskListQuery");
    expect(tasksApiSource).toContain("export type TaskEventHistoryReadModel");
    expect(tasksApiSource).toContain("buildTasksListKey");
    expect(tasksApiSource).toContain("taskEventsKey");
    expect(tasksApiSource).toContain("getTaskEvents");
    expect(tasksApiSource).toContain("cancelTask");
    expect(tasksApiSource).toContain("terminateTask");
    expect(tasksApiSource).toContain("retryTask");
  });
});
