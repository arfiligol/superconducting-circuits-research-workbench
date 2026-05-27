"use client";

import type { AppSelectOption } from "@/features/shared/components/app-select";

export type PostProcessingStepType = "coordinate_transform" | "kron_reduction";

export type CoordinateTransformStepDraft = Readonly<{
  id: string;
  type: "coordinate_transform";
  portA: string;
  portB: string;
}>;

export type KronReductionStepDraft = Readonly<{
  id: string;
  type: "kron_reduction";
  keepLabels: readonly string[];
}>;

export type PostProcessingStepDraft =
  | CoordinateTransformStepDraft
  | KronReductionStepDraft;

export type PostProcessingStepContext = Readonly<{
  basisLabels: readonly string[];
  basisOptions: readonly AppSelectOption[];
  coordinatePortOptions: readonly AppSelectOption[];
}>;

function isNumericBasisLabel(label: string) {
  return /^\d+$/.test(label.trim());
}

export function normalizePostProcessingBasisLabel(label: string) {
  const trimmed = label.trim();
  const transformedMatch = /^(cm|dm)\(\s*(\d+)\s*,\s*(\d+)\s*\)$/iu.exec(trimmed);
  if (transformedMatch) {
    const family = (transformedMatch[1] ?? "").toUpperCase();
    const portA = transformedMatch[2] ?? "";
    const portB = transformedMatch[3] ?? "";
    return `${family}(${portA},${portB})`;
  }
  return trimmed;
}

export function parsePostProcessingPortNumber(portValue: string) {
  const matchedPort = /port_(\d+)/i.exec(portValue.trim());
  if (!matchedPort) {
    return null;
  }

  const parsedPort = Number.parseInt(matchedPort[1] ?? "", 10);
  return Number.isFinite(parsedPort) ? parsedPort : null;
}

export function formatPostProcessingBasisLabel(label: string) {
  const trimmed = normalizePostProcessingBasisLabel(label);
  if (isNumericBasisLabel(trimmed)) {
    return `Port ${trimmed}`;
  }
  if (/^cm\(/i.test(trimmed)) {
    return "Port CM";
  }
  if (/^dm\(/i.test(trimmed)) {
    return "Port DM";
  }
  return `Port ${trimmed}`;
}

export function listPostProcessingBasisLabels(
  portOptions: readonly AppSelectOption[],
) {
  return portOptions
    .map((option) => {
      const portNumber = parsePostProcessingPortNumber(option.value);
      return portNumber !== null ? String(portNumber) : null;
    })
    .filter((value): value is string => value !== null);
}

function previewCoordinateTransformLabels(
  basisLabels: readonly string[],
  step: CoordinateTransformStepDraft,
) {
  const portA = parsePostProcessingPortNumber(step.portA);
  const portB = parsePostProcessingPortNumber(step.portB);
  if (portA === null || portB === null || portA === portB) {
    return [...basisLabels];
  }

  const portALabel = String(portA);
  const portBLabel = String(portB);
  const nextLabels = [...basisLabels];
  const portAIndex = nextLabels.findIndex((label) => label === portALabel);
  const portBIndex = nextLabels.findIndex((label) => label === portBLabel);
  if (portAIndex === -1 || portBIndex === -1) {
    return [...basisLabels];
  }

  nextLabels[portAIndex] = normalizePostProcessingBasisLabel(`CM(${portA},${portB})`);
  nextLabels[portBIndex] = normalizePostProcessingBasisLabel(`DM(${portA},${portB})`);
  return nextLabels;
}

function previewKronReductionLabels(
  basisLabels: readonly string[],
  step: KronReductionStepDraft,
) {
  const keepLabelSet = new Set(step.keepLabels.map(normalizePostProcessingBasisLabel));
  return basisLabels.filter((label) =>
    keepLabelSet.has(normalizePostProcessingBasisLabel(label)),
  );
}

export function previewPostProcessingBasisLabels(
  initialBasisLabels: readonly string[],
  steps: readonly PostProcessingStepDraft[],
  stopBeforeStepId?: string,
) {
  let basisLabels = [...initialBasisLabels];
  for (const step of steps) {
    if (stopBeforeStepId && step.id === stopBeforeStepId) {
      break;
    }
    basisLabels =
      step.type === "coordinate_transform"
        ? previewCoordinateTransformLabels(basisLabels, step)
        : previewKronReductionLabels(basisLabels, step);
  }
  return basisLabels;
}

export function derivePostProcessingStepContext(
  sourcePortOptions: readonly AppSelectOption[],
  steps: readonly PostProcessingStepDraft[],
  stopBeforeStepId?: string,
): PostProcessingStepContext {
  const initialBasisLabels = listPostProcessingBasisLabels(sourcePortOptions);
  const basisLabels = previewPostProcessingBasisLabels(
    initialBasisLabels,
    steps,
    stopBeforeStepId,
  );
  const basisOptions = basisLabels.map((label) => ({
    value: label,
    label: formatPostProcessingBasisLabel(label),
  }));
  const coordinatePortOptions = basisLabels
    .filter((label) => isNumericBasisLabel(label))
    .map((label) => ({
      value: `port_${label}`,
      label: `Port ${label}`,
    }));

  return {
    basisLabels,
    basisOptions,
    coordinatePortOptions,
  };
}

export function isPostProcessingStepTypeAvailable(
  stepType: PostProcessingStepType,
  context: PostProcessingStepContext,
) {
  if (stepType === "coordinate_transform") {
    return context.coordinatePortOptions.length >= 2;
  }

  return context.basisOptions.length > 0;
}

export function createPostProcessingStep(
  stepType: PostProcessingStepType,
  context: PostProcessingStepContext,
  stepId = `post-step:${crypto.randomUUID()}`,
): PostProcessingStepDraft {
  if (stepType === "coordinate_transform") {
    const firstPort = context.coordinatePortOptions[0]?.value ?? "port_1";
    const secondPort = context.coordinatePortOptions[1]?.value ?? firstPort;
    return {
      id: stepId,
      type: "coordinate_transform",
      portA: firstPort,
      portB: secondPort,
    };
  }

  return {
    id: stepId,
    type: "kron_reduction",
    keepLabels: context.basisOptions.map((option) =>
      normalizePostProcessingBasisLabel(option.value),
    ),
  };
}

export function sanitizePostProcessingStep(
  step: PostProcessingStepDraft,
  context: PostProcessingStepContext,
): PostProcessingStepDraft {
  if (step.type === "coordinate_transform") {
    const availablePortTokens = new Set(context.coordinatePortOptions.map((option) => option.value));
    const fallbackPort = context.coordinatePortOptions[0]?.value ?? "port_1";
    return {
      ...step,
      portA: availablePortTokens.has(step.portA) ? step.portA : fallbackPort,
      portB: availablePortTokens.has(step.portB)
        ? step.portB
        : context.coordinatePortOptions[1]?.value ?? fallbackPort,
    };
  }

  const availableBasisLabels = new Set(
    context.basisOptions.map((option) => normalizePostProcessingBasisLabel(option.value)),
  );
  return {
    ...step,
    keepLabels: step.keepLabels
      .map(normalizePostProcessingBasisLabel)
      .filter((label) => availableBasisLabels.has(label)),
  };
}
