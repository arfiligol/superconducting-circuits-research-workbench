import { describe, expect, it } from "vitest";

import {
  formatTaskControlStateLabel,
  formatTaskExecutionStatusLabel,
  formatTaskKindLabel,
  formatTaskLaneLabel,
  formatTaskResultAvailabilityLabel,
  formatTaskVisibilityScopeLabel,
  resolveTaskExecutionStatusTone,
  resolveTaskResultAvailabilityTone,
  summarizeTaskLifecycleCopy,
} from "../src/lib/task-presenters/presentation";

describe("task presenters", () => {
  it("normalizes shared task vocabulary in one place", () => {
    expect(formatTaskExecutionStatusLabel("termination_requested")).toBe("Terminate Requested");
    expect(formatTaskExecutionStatusLabel("staging_result")).toBe("Staging Result");
    expect(formatTaskKindLabel("post_processing")).toBe("Post Processing");
    expect(formatTaskLaneLabel("characterization")).toBe("Characterization");
    expect(formatTaskVisibilityScopeLabel("owned")).toBe("Mine");
    expect(formatTaskControlStateLabel("cancellation_requested")).toBe("Cancel requested");
    expect(formatTaskResultAvailabilityLabel("ready")).toBe("Ready");
  });

  it("keeps tones aligned with execution and result authority", () => {
    expect(resolveTaskExecutionStatusTone("completed")).toBe("success");
    expect(resolveTaskExecutionStatusTone("terminated")).toBe("warning");
    expect(resolveTaskResultAvailabilityTone("pending")).toBe("primary");
    expect(resolveTaskResultAvailabilityTone("none")).toBe("default");
  });

  it("builds lifecycle copy from task status authority", () => {
    expect(summarizeTaskLifecycleCopy("dispatching")).toEqual({
      stage: "running",
      statusLabel: "Dispatching",
      tone: "primary",
      summary:
        "Worker runtime is still active. Keep the attached task detail refreshed until the backend settles the request.",
      terminalStateLabel: "Execution active",
    });

    expect(summarizeTaskLifecycleCopy("cancelled")).toEqual({
      stage: "cancelled",
      statusLabel: "Cancelled",
      tone: "warning",
      summary:
        "Cancellation was acknowledged and persisted. The attached task remains the authority for follow-up review.",
      terminalStateLabel: "Cancellation persisted",
    });
  });
});
