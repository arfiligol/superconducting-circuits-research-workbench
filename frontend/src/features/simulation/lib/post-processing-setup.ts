"use client";

import type { PostProcessingSetup } from "@/lib/api/tasks";
import {
  normalizePostProcessingBasisLabel,
  parsePostProcessingPortNumber,
  type PostProcessingStepDraft,
} from "@/features/simulation/lib/post-processing-basis";

function buildPostProcessingOperationDraft(step: PostProcessingStepDraft) {
  if (step.type === "kron_reduction") {
    const keepLabels = Array.from(
      new Set(step.keepLabels.map(normalizePostProcessingBasisLabel)),
    );
    if (keepLabels.length === 0) {
      throw new Error("Kron Reduction requires at least one kept port.");
    }

    return {
      operation: "kron_reduction" as const,
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
    operation: "coordinate_transform" as const,
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

export function buildPostProcessingSetupDraft(
  steps: readonly PostProcessingStepDraft[],
) {
  return {
    operations: steps.map(buildPostProcessingOperationDraft),
  };
}

export function hydratePostProcessingSteps(
  setup: PostProcessingSetup,
  availablePortValues: readonly string[],
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
          : availablePortValues[0] ?? "port_1";
      const rawPortB =
        typeof operation.config.port_b === "number"
          ? `port_${operation.config.port_b}`
          : availablePortValues[1] ?? rawPortA;
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
