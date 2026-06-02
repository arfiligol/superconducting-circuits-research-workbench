import { describe, expect, it } from "vitest";

import { ApiError, getTaskEnqueueFailureDetails } from "../src/lib/api/client";

describe("api client enqueue failure parsing", () => {
  it("extracts persisted task and dispatch metadata from enqueue failures", () => {
    const error = new ApiError("Enqueue failed.", 503, {
      errorCode: "task_enqueue_failed",
      details: {
        task_id: 412,
        dispatch: {
          dispatch_key: "dispatch:412:simulation_run_task",
          queue_name: "simulation",
          runtime_job_id: "job-412",
          dispatch_attempt_count: 3,
          last_dispatch_outcome: "failed",
          last_dispatch_error_code: "runtime_unavailable",
        },
      },
    });

    expect(getTaskEnqueueFailureDetails(error)).toEqual({
      taskId: 412,
      dispatch: {
        dispatchKey: "dispatch:412:simulation_run_task",
        queueName: "simulation",
        runtimeJobId: "job-412",
        dispatchAttemptCount: 3,
        lastDispatchOutcome: "failed",
        lastDispatchErrorCode: "runtime_unavailable",
      },
    });
  });

  it("ignores non-enqueue API errors", () => {
    expect(getTaskEnqueueFailureDetails(new ApiError("Nope", 500, { errorCode: "other" }))).toBe(
      null,
    );
    expect(getTaskEnqueueFailureDetails(new Error("Nope"))).toBe(null);
  });
});
