import { describe, expect, it } from "vitest";

import {
  createPostProcessingStep,
  derivePostProcessingStepContext,
  normalizePostProcessingBasisLabel,
  sanitizePostProcessingStep,
} from "../src/features/simulation/lib/post-processing-basis";

describe("post-processing basis label normalization", () => {
  it("normalizes transformed labels into the backend canonical CM/DM form", () => {
    expect(normalizePostProcessingBasisLabel("cm(1,2)")).toBe("CM(1,2)");
    expect(normalizePostProcessingBasisLabel(" dm(1,2) ")).toBe("DM(1,2)");
    expect(normalizePostProcessingBasisLabel("Port 3")).toBe("Port 3");
  });

  it("builds coordinate-transform preview context with canonical transformed labels", () => {
    const context = derivePostProcessingStepContext(
      [
        { value: "port_1", label: "Port 1" },
        { value: "port_2", label: "Port 2" },
        { value: "port_3", label: "Port 3" },
      ],
      [
        {
          id: "step-transform",
          type: "coordinate_transform",
          portA: "port_1",
          portB: "port_2",
        },
      ],
    );

    expect(context.basisLabels).toEqual(["CM(1,2)", "DM(1,2)", "3"]);
    expect(context.basisOptions.map((option) => option.value)).toEqual([
      "CM(1,2)",
      "DM(1,2)",
      "3",
    ]);
    expect(context.basisOptions.map((option) => option.label)).toEqual([
      "Port CM",
      "Port DM",
      "Port 3",
    ]);
  });

  it("sanitizes lowercase keep labels and seeds new kron steps with canonical values", () => {
    const context = derivePostProcessingStepContext(
      [
        { value: "port_1", label: "Port 1" },
        { value: "port_2", label: "Port 2" },
      ],
      [
        {
          id: "step-transform",
          type: "coordinate_transform",
          portA: "port_1",
          portB: "port_2",
        },
      ],
    );

    const sanitized = sanitizePostProcessingStep(
      {
        id: "step-kron",
        type: "kron_reduction",
        keepLabels: ["dm(1,2)", "CM(1,2)", "missing"],
      },
      context,
    );

    expect(sanitized).toEqual({
      id: "step-kron",
      type: "kron_reduction",
      keepLabels: ["DM(1,2)", "CM(1,2)"],
    });

    const created = createPostProcessingStep("kron_reduction", context, "step-new");

    expect(created).toEqual({
      id: "step-new",
      type: "kron_reduction",
      keepLabels: ["CM(1,2)", "DM(1,2)"],
    });
  });
});
