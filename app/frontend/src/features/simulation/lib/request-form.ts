"use client";

import { z } from "zod";

import {
  defaultSimulationSetupFormValues,
  simulationSetupFormSchema,
} from "@/features/simulation/lib/setup-form";

export const simulationRequestSchema = simulationSetupFormSchema.extend({
  simulationNote: z.string().trim().max(180, "Keep the request note within 180 characters."),
  postProcessingNote: z
    .string()
    .trim()
    .max(180, "Keep the request note within 180 characters."),
});

export type SimulationRequestValues = z.infer<typeof simulationRequestSchema>;

export const defaultRequestValues: SimulationRequestValues = {
  ...defaultSimulationSetupFormValues,
  simulationNote: "",
  postProcessingNote: "",
};

export const simulationStageFieldNames = [
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
  "simulationPtcEnabled",
  "simulationPtcMode",
  "simulationPtcCompensatePorts",
  "simulationPtcManualNotes",
  "simulationAdvancedDampingStrategy",
  "simulationAdvancedLineSearchEnabled",
  "simulationAdvancedResidualClamp",
  "simulationAdvancedNewtonRelaxation",
  "simulationAdvancedNotes",
] as const;
