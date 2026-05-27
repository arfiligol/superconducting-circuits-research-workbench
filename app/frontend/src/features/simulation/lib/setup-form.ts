import { z } from "zod";

import { parseCircuitNetlistSource } from "@/features/circuit-definition-editor/lib/netlist";
import type { SimulationSetup, SimulationSetupDraft } from "@/lib/api/tasks";

export const simulationParameterSweepAxisModeSchema = z.enum(["range", "explicit"]);
export type SimulationParameterSweepAxisMode = z.infer<
  typeof simulationParameterSweepAxisModeSchema
>;

export const simulationParameterSweepAxisSchema = z.object({
  parameter: z.string().trim(),
  mode: simulationParameterSweepAxisModeSchema,
  start: z.number(),
  stop: z.number(),
  pointCount: z.number().int().min(1, "Point count must be at least 1."),
  explicitValues: z.string().trim(),
  unit: z.string().trim(),
});

export const simulationSourceFormSchema = z.object({
  sourceId: z.string().trim(),
  port: z.string().trim().min(1, "Source port is required."),
  currentAmp: z.number(),
  pumpFreqGhz: z.number().positive("Pump frequency must be greater than 0."),
  sourceMode: z.string().trim().min(1, "Source mode is required."),
});

export const simulationSetupFormSchema = z
  .object({
    simulationStartGhz: z.number().positive("Start GHz must be greater than 0."),
    simulationStopGhz: z.number().positive("Stop GHz must be greater than 0."),
    simulationPointCount: z.number().int().min(1, "Point count must be at least 1."),
    simulationSpacing: z.enum(["linear", "log"]),
    simulationParameterSweepEnabled: z.boolean(),
    simulationParameterSweepAxes: z.array(simulationParameterSweepAxisSchema),
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
    simulationSources: z.array(simulationSourceFormSchema),
    simulationPtcEnabled: z.boolean(),
    simulationPtcMode: z.enum(["auto", "manual"]),
    simulationPtcCompensatePorts: z.string().trim(),
    simulationPtcManualNotes: z.string().trim(),
    simulationAdvancedDampingStrategy: z.string().trim(),
    simulationAdvancedLineSearchEnabled: z.boolean(),
    simulationAdvancedResidualClamp: z.string().trim(),
    simulationAdvancedNewtonRelaxation: z.string().trim(),
    simulationAdvancedNotes: z.string().trim(),
  })
  .superRefine((values, context) => {
    if (values.simulationStopGhz <= values.simulationStartGhz) {
      context.addIssue({
        code: z.ZodIssueCode.custom,
        path: ["simulationStopGhz"],
        message: "Stop GHz must be greater than Start GHz.",
      });
    }

    if (!values.simulationParameterSweepEnabled) {
      return;
    }

    if (values.simulationParameterSweepAxes.length === 0) {
      context.addIssue({
        code: z.ZodIssueCode.custom,
        path: ["simulationParameterSweepAxes"],
        message: "Add at least one sweep axis or disable parameter sweeps.",
      });
      return;
    }

    values.simulationParameterSweepAxes.forEach((axis, index) => {
      if (axis.parameter.trim().length === 0) {
        context.addIssue({
          code: z.ZodIssueCode.custom,
          path: ["simulationParameterSweepAxes", index, "parameter"],
          message: "Parameter target is required.",
        });
      }

      if (axis.mode === "explicit") {
        let explicitValues: readonly number[] = [];
        try {
          explicitValues = parseCommaSeparatedNumericValues(axis.explicitValues);
        } catch (error) {
          context.addIssue({
            code: z.ZodIssueCode.custom,
            path: ["simulationParameterSweepAxes", index, "explicitValues"],
            message: error instanceof Error ? error.message : "Provide numeric sweep values.",
          });
          return;
        }

        if (explicitValues.length === 0) {
          context.addIssue({
            code: z.ZodIssueCode.custom,
            path: ["simulationParameterSweepAxes", index, "explicitValues"],
            message: "Provide at least one numeric value.",
          });
        }
      }
    });
  });

export type SimulationSetupFormValues = z.infer<typeof simulationSetupFormSchema>;
export type SimulationParameterSweepAxisForm = SimulationSetupFormValues["simulationParameterSweepAxes"][number];
export type SimulationSourceForm = SimulationSetupFormValues["simulationSources"][number];
export type SimulationSweepTargetOption = Readonly<{
  value: string;
  label: string;
  unit: string | null;
  source: "schema" | "source";
}>;
export type SimulationPtcPortOption = Readonly<{
  value: string;
  label: string;
  sourceElement: string;
}>;

export function cloneSimulationSetupFormValues(
  values: Readonly<SimulationSetupFormValues>,
): SimulationSetupFormValues {
  return {
    simulationStartGhz: values.simulationStartGhz,
    simulationStopGhz: values.simulationStopGhz,
    simulationPointCount: values.simulationPointCount,
    simulationSpacing: values.simulationSpacing,
    simulationParameterSweepEnabled: values.simulationParameterSweepEnabled,
    simulationParameterSweepAxes: values.simulationParameterSweepAxes.map((axis) => ({
      parameter: axis.parameter,
      mode: axis.mode,
      start: axis.start,
      stop: axis.stop,
      pointCount: axis.pointCount,
      explicitValues: axis.explicitValues,
      unit: axis.unit,
    })),
    simulationSolverFamily: values.simulationSolverFamily,
    simulationMaxIterations: values.simulationMaxIterations,
    simulationConvergenceTolerance: values.simulationConvergenceTolerance,
    simulationHarmonicBalanceEnabled: values.simulationHarmonicBalanceEnabled,
    simulationHarmonicCount: values.simulationHarmonicCount,
    simulationOversampleFactor: values.simulationOversampleFactor,
    simulationSources: values.simulationSources.map((source) => ({
      sourceId: source.sourceId,
      port: source.port,
      currentAmp: source.currentAmp,
      pumpFreqGhz: source.pumpFreqGhz,
      sourceMode: source.sourceMode,
    })),
    simulationPtcEnabled: values.simulationPtcEnabled,
    simulationPtcMode: values.simulationPtcMode,
    simulationPtcCompensatePorts: values.simulationPtcCompensatePorts,
    simulationPtcManualNotes: values.simulationPtcManualNotes,
    simulationAdvancedDampingStrategy: values.simulationAdvancedDampingStrategy,
    simulationAdvancedLineSearchEnabled: values.simulationAdvancedLineSearchEnabled,
    simulationAdvancedResidualClamp: values.simulationAdvancedResidualClamp,
    simulationAdvancedNewtonRelaxation: values.simulationAdvancedNewtonRelaxation,
    simulationAdvancedNotes: values.simulationAdvancedNotes,
  };
}

export function serializeSimulationSetupFormValues(
  values: Readonly<SimulationSetupFormValues>,
) {
  const normalized = cloneSimulationSetupFormValues(values);
  if (!normalized.simulationParameterSweepEnabled) {
    normalized.simulationParameterSweepAxes = [];
  }
  return JSON.stringify(normalized);
}

export function createDefaultSimulationParameterSweepAxis(
  input?: Readonly<{ parameter?: string; unit?: string | null }>,
): SimulationParameterSweepAxisForm {
  return {
    parameter: input?.parameter?.trim() ?? "",
    mode: "range",
    start: 0,
    stop: 1,
    pointCount: 5,
    explicitValues: "",
    unit: input?.unit?.trim() ?? "",
  };
}

export function createDefaultSimulationSource(): SimulationSourceForm {
  return {
    sourceId: "src_pump_1",
    port: "port_1",
    currentAmp: 0,
    pumpFreqGhz: 5,
    sourceMode: "1",
  };
}

export const defaultSimulationSetupFormValues: SimulationSetupFormValues = {
  simulationStartGhz: 1,
  simulationStopGhz: 8,
  simulationPointCount: 401,
  simulationSpacing: "linear",
  simulationParameterSweepEnabled: false,
  simulationParameterSweepAxes: [createDefaultSimulationParameterSweepAxis()],
  simulationSolverFamily: "harmonic_balance",
  simulationMaxIterations: 80,
  simulationConvergenceTolerance: 0.000001,
  simulationHarmonicBalanceEnabled: true,
  simulationHarmonicCount: 3,
  simulationOversampleFactor: 2,
  simulationSources: [createDefaultSimulationSource()],
  simulationPtcEnabled: false,
  simulationPtcMode: "auto",
  simulationPtcCompensatePorts: "",
  simulationPtcManualNotes: "",
  simulationAdvancedDampingStrategy: "",
  simulationAdvancedLineSearchEnabled: false,
  simulationAdvancedResidualClamp: "",
  simulationAdvancedNewtonRelaxation: "",
  simulationAdvancedNotes: "",
};

export function parseCommaSeparatedStringValues(value: string) {
  return value
    .split(",")
    .map((entry) => entry.trim())
    .filter((entry) => entry.length > 0);
}

export function parseCommaSeparatedNumericValues(value: string) {
  const segments = parseCommaSeparatedStringValues(value);
  return segments.map((segment) => {
    const parsed = Number(segment);
    if (!Number.isFinite(parsed)) {
      throw new Error(`"${segment}" is not a valid numeric value.`);
    }
    return parsed;
  });
}

function buildSourceSweepTargetLabel(
  source: Readonly<SimulationSourceForm>,
  sourceIndex: number,
  fieldLabel: string,
  unit: string | null,
) {
  const sourceName = source.port.trim()
    ? source.port
        .trim()
        .replace(/^port_(\d+)$/i, "Port $1")
    : `Source ${sourceIndex + 1}`;
  return unit
    ? `${sourceName} · ${fieldLabel} (${unit})`
    : `${sourceName} · ${fieldLabel}`;
}

export function deriveSimulationSweepTargetOptions(
  definitionSourceText: string | null | undefined,
  sources: readonly SimulationSourceForm[],
): readonly SimulationSweepTargetOption[] {
  const options: SimulationSweepTargetOption[] = [];
  const seen = new Set<string>();
  const parsed = definitionSourceText
    ? parseCircuitNetlistSource(definitionSourceText).document
    : null;

  const parameterMap = new Map(
    (parsed?.parameters ?? []).map((parameter) => [parameter.name, parameter] as const),
  );
  const schemaSweepTargets = new Set(
    parsed?.components.flatMap((component) =>
      component.value_ref?.trim() ? [component.value_ref.trim()] : [],
    ) ?? [],
  );

  for (const parameterName of schemaSweepTargets) {
    const parameter = parameterMap.get(parameterName);
    if (!parameter || seen.has(parameter.name)) {
      continue;
    }
    seen.add(parameter.name);
    options.push({
      value: parameter.name,
      label: `${parameter.name} (${parameter.unit})`,
      unit: parameter.unit,
      source: "schema",
    });
  }

  sources.forEach((source, sourceIndex) => {
    const optionSpecs = [
      {
        value: `sources[${sourceIndex + 1}].current_amp`,
        label: buildSourceSweepTargetLabel(source, sourceIndex, "Source current", "A"),
        unit: "A",
      },
      {
        value: `sources[${sourceIndex + 1}].pump_freq_ghz`,
        label: buildSourceSweepTargetLabel(source, sourceIndex, "Pump freq", "GHz"),
        unit: "GHz",
      },
    ] as const;

    optionSpecs.forEach((spec) => {
      if (seen.has(spec.value)) {
        return;
      }
      seen.add(spec.value);
      options.push({
        value: spec.value,
        label: spec.label,
        unit: spec.unit,
        source: "source",
      });
    });
  });

  return options;
}

export function deriveSimulationPtcPortOptions(
  definitionSourceText: string | null | undefined,
): readonly SimulationPtcPortOption[] {
  const parsed = definitionSourceText
    ? parseCircuitNetlistSource(definitionSourceText).document
    : null;
  if (!parsed) {
    return [];
  }

  const options = new Map<number, SimulationPtcPortOption>();
  parsed.topology.forEach(([elementName, , , componentRef]) => {
    if (!elementName.toUpperCase().startsWith("P") || typeof componentRef !== "number") {
      return;
    }

    options.set(componentRef, {
      value: `port_${componentRef}`,
      label: `Port ${componentRef}`,
      sourceElement: elementName,
    });
  });

  return [...options.entries()]
    .sort(([left], [right]) => left - right)
    .map(([, option]) => option);
}

function buildLinearSweepValues(start: number, stop: number, pointCount: number) {
  if (pointCount <= 1) {
    return [Number(start.toPrecision(12))];
  }

  const step = (stop - start) / (pointCount - 1);
  return Array.from({ length: pointCount }, (_, index) =>
    Number((start + step * index).toPrecision(12)),
  );
}

function buildParameterSweepValues(axis: SimulationParameterSweepAxisForm) {
  if (axis.mode === "explicit") {
    const values = parseCommaSeparatedNumericValues(axis.explicitValues);
    if (values.length === 0) {
      throw new Error(`Provide at least one numeric value for ${axis.parameter || "the sweep axis"}.`);
    }
    return values;
  }

  return buildLinearSweepValues(axis.start, axis.stop, axis.pointCount);
}

export function buildSimulationSetupDraft(
  values: SimulationSetupFormValues,
): SimulationSetupDraft {
  const parameterSweeps = values.simulationParameterSweepEnabled
    ? values.simulationParameterSweepAxes.map((axis) => {
        const parameter = axis.parameter.trim();
        if (!parameter) {
          throw new Error("Each enabled sweep axis requires a parameter target.");
        }

        return {
          parameter,
          values: buildParameterSweepValues(axis),
          unit: axis.unit.trim() || null,
        };
      })
    : [];

  return {
    frequency_sweep: {
      start_ghz: values.simulationStartGhz,
      stop_ghz: values.simulationStopGhz,
      point_count: values.simulationPointCount,
      spacing: values.simulationSpacing,
    },
    parameter_sweeps: parameterSweeps,
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
    sources: values.simulationSources.map((source) => ({
      source_id: source.sourceId.trim() || `src_pump_${source.port.trim() || "1"}`,
      kind: "pump",
      target: source.port.trim(),
      amplitude: source.currentAmp,
      frequency_ghz: source.pumpFreqGhz,
      phase_deg: null,
    })),
    ptc: {
      enabled: values.simulationPtcEnabled,
      mode: values.simulationPtcMode,
      compensate_ports: parseCommaSeparatedStringValues(values.simulationPtcCompensatePorts),
    },
  };
}

export function buildSimulationSetupFormValuesFromPersistedSetup<
  T extends SimulationSetupFormValues,
>(
  currentValues: T,
  setup: SimulationSetup | null | undefined,
): T {
  if (!setup) {
    return currentValues;
  }

  return {
    ...currentValues,
    simulationStartGhz: setup.frequencySweep.startGhz,
    simulationStopGhz: setup.frequencySweep.stopGhz,
    simulationPointCount: setup.frequencySweep.pointCount,
    simulationSpacing: setup.frequencySweep.spacing,
    simulationParameterSweepEnabled: setup.parameterSweeps.length > 0,
    simulationParameterSweepAxes:
      setup.parameterSweeps.length > 0
        ? setup.parameterSweeps.map((sweep) => ({
            parameter: sweep.parameter,
            mode: "explicit" as const,
            start: sweep.values[0] ?? 0,
            stop: sweep.values[sweep.values.length - 1] ?? sweep.values[0] ?? 0,
            pointCount: sweep.values.length > 0 ? sweep.values.length : 1,
            explicitValues: sweep.values.join(", "),
            unit: sweep.unit ?? "",
          }))
        : [createDefaultSimulationParameterSweepAxis()],
    simulationSolverFamily: setup.solver.solverFamily,
    simulationMaxIterations: setup.solver.maxIterations,
    simulationConvergenceTolerance: setup.solver.convergenceTolerance,
    simulationHarmonicBalanceEnabled: setup.solver.harmonicBalance?.enabled ?? false,
    simulationHarmonicCount:
      setup.solver.harmonicBalance?.harmonicCount ??
      defaultSimulationSetupFormValues.simulationHarmonicCount,
    simulationOversampleFactor:
      setup.solver.harmonicBalance?.oversampleFactor ??
      defaultSimulationSetupFormValues.simulationOversampleFactor,
    simulationSources:
      setup.sources.length > 0
        ? setup.sources.map((source) => ({
            sourceId: source.sourceId,
            port: source.target,
            currentAmp: source.amplitude,
            pumpFreqGhz: source.frequencyGhz ?? 0,
            sourceMode: currentValues.simulationSources[0]?.sourceMode ?? "1",
          }))
        : [createDefaultSimulationSource()],
    simulationPtcEnabled: setup.ptc?.enabled ?? false,
    simulationPtcMode:
      setup.ptc?.mode === "manual" ? "manual" : defaultSimulationSetupFormValues.simulationPtcMode,
    simulationPtcCompensatePorts: setup.ptc?.compensatePorts.join(", ") ?? "",
  };
}
