import {
  createDefaultSimulationParameterSweepAxis,
  defaultSimulationSetupFormValues,
  type SimulationSetupFormValues,
} from "@/features/simulation/lib/setup-form";

export const JOSEPHSON_EXAMPLE_PREFIX = "JosephsonCircuits Examples: ";

type JosephsonOfficialExampleSource = Readonly<{
  pumpFreqGhz: number;
  port: number;
  currentAmp: number;
  mode: readonly number[];
}>;

type JosephsonOfficialExampleSeed = Readonly<{
  startGhz: number;
  stopGhz: number;
  pointCount: number;
  nModulationHarmonics: number;
  nPumpHarmonics: number;
  sources: readonly JosephsonOfficialExampleSource[];
  maxIterations?: number;
  convergenceTolerance?: number;
}>;

export type OfficialSimulationExamplePreset = Readonly<{
  id: string;
  name: "Official Example";
  definitionName: string;
  exampleName: string;
  values: SimulationSetupFormValues;
}>;

const JOSEPHSON_OFFICIAL_EXAMPLE_SEEDS: Readonly<Record<string, JosephsonOfficialExampleSeed>> = {
  "Josephson Parametric Amplifier (JPA)": {
    startGhz: 4.5,
    stopGhz: 5.0,
    pointCount: 501,
    nModulationHarmonics: 8,
    nPumpHarmonics: 16,
    sources: [
      {
        pumpFreqGhz: 4.75001,
        port: 1,
        currentAmp: 0.00565e-6,
        mode: [1],
      },
    ],
  },
  "Double-pumped Josephson Parametric Amplifier (JPA)": {
    startGhz: 4.5,
    stopGhz: 5.0,
    pointCount: 501,
    nModulationHarmonics: 8,
    nPumpHarmonics: 8,
    sources: [
      {
        pumpFreqGhz: 4.65001,
        port: 1,
        currentAmp: 0.00565e-6 * 1.7,
        mode: [1, 0],
      },
      {
        pumpFreqGhz: 4.85001,
        port: 1,
        currentAmp: 0.00565e-6 * 1.7,
        mode: [0, 1],
      },
    ],
  },
  "Flux-pumped Josephson Parametric Amplifier (JPA)": {
    startGhz: 9.7,
    stopGhz: 9.8,
    pointCount: 1001,
    nModulationHarmonics: 8,
    nPumpHarmonics: 16,
    sources: [
      {
        pumpFreqGhz: 19.5,
        port: 2,
        currentAmp: 140.3e-6,
        mode: [0],
      },
      {
        pumpFreqGhz: 19.5,
        port: 2,
        currentAmp: 0.7e-6,
        mode: [1],
      },
    ],
  },
  "SNAIL Parametric Amplifier": {
    startGhz: 7.8,
    stopGhz: 8.2,
    pointCount: 401,
    nModulationHarmonics: 8,
    nPumpHarmonics: 16,
    sources: [
      {
        pumpFreqGhz: 16.0,
        port: 2,
        currentAmp: 0.000159,
        mode: [0],
      },
      {
        pumpFreqGhz: 16.0,
        port: 2,
        currentAmp: 4.4e-6,
        mode: [1],
      },
    ],
  },
  "Josephson Traveling Wave Parametric Amplifier (JTWPA)": {
    startGhz: 1.0,
    stopGhz: 14.0,
    pointCount: 131,
    nModulationHarmonics: 10,
    nPumpHarmonics: 20,
    sources: [
      {
        pumpFreqGhz: 7.12,
        port: 1,
        currentAmp: 1.85e-6,
        mode: [1],
      },
    ],
  },
  "Floquet JTWPA": {
    startGhz: 1.0,
    stopGhz: 14.0,
    pointCount: 131,
    nModulationHarmonics: 10,
    nPumpHarmonics: 20,
    sources: [
      {
        pumpFreqGhz: 7.9,
        port: 1,
        currentAmp: 1.1e-6,
        mode: [1],
      },
    ],
  },
  "Floquet JTWPA with Dissipation": {
    startGhz: 1.0,
    stopGhz: 14.0,
    pointCount: 131,
    nModulationHarmonics: 10,
    nPumpHarmonics: 20,
    sources: [
      {
        pumpFreqGhz: 7.9,
        port: 1,
        currentAmp: 1.1e-6 * (1 + 125e-6),
        mode: [1],
      },
    ],
  },
  "Flux-Driven Josephson Traveling-Wave Parametric Amplifier (JTWPA)": {
    startGhz: 5.0,
    stopGhz: 25.0,
    pointCount: 500,
    nModulationHarmonics: 4,
    nPumpHarmonics: 8,
    sources: [
      {
        pumpFreqGhz: 20.0,
        port: 3,
        currentAmp: 0.00019921960989995077,
        mode: [0],
      },
      {
        pumpFreqGhz: 20.0,
        port: 3,
        currentAmp: 1.1953176593997045e-05,
        mode: [1],
      },
    ],
    maxIterations: 200,
  },
  "Impedance-engineered JPA": {
    startGhz: 4.0,
    stopGhz: 5.8,
    pointCount: 181,
    nModulationHarmonics: 4,
    nPumpHarmonics: 8,
    sources: [
      {
        pumpFreqGhz: 9.8001,
        port: 2,
        currentAmp: 0.686e-3,
        mode: [0],
      },
      {
        pumpFreqGhz: 9.8001,
        port: 2,
        currentAmp: 0.247e-3,
        mode: [1],
      },
    ],
    maxIterations: 200,
  },
};

function buildOfficialExampleId(exampleName: string) {
  return `official-example:${exampleName
    .toLowerCase()
    .replaceAll(" ", "-")
    .replaceAll("(", "")
    .replaceAll(")", "")
    .replaceAll(",", "")}`;
}

function formatSourceMode(mode: readonly number[]) {
  if (mode.length === 0) {
    return "";
  }

  return mode.join(", ");
}

function resolveJosephsonExampleName(definitionName: string | null | undefined) {
  const normalizedDefinitionName = definitionName?.trim();
  if (!normalizedDefinitionName) {
    return null;
  }

  if (normalizedDefinitionName.startsWith(JOSEPHSON_EXAMPLE_PREFIX)) {
    return normalizedDefinitionName.slice(JOSEPHSON_EXAMPLE_PREFIX.length).trim();
  }

  return JOSEPHSON_OFFICIAL_EXAMPLE_SEEDS[normalizedDefinitionName]
    ? normalizedDefinitionName
    : null;
}

function buildPresetValues(seed: JosephsonOfficialExampleSeed): SimulationSetupFormValues {
  return {
    ...defaultSimulationSetupFormValues,
    simulationStartGhz: seed.startGhz,
    simulationStopGhz: seed.stopGhz,
    simulationPointCount: seed.pointCount,
    simulationSpacing: "linear",
    simulationParameterSweepEnabled: false,
    simulationParameterSweepAxes: [createDefaultSimulationParameterSweepAxis()],
    simulationMaxIterations:
      seed.maxIterations ?? defaultSimulationSetupFormValues.simulationMaxIterations,
    simulationConvergenceTolerance:
      seed.convergenceTolerance ??
      defaultSimulationSetupFormValues.simulationConvergenceTolerance,
    simulationHarmonicBalanceEnabled: true,
    simulationHarmonicCount: seed.nModulationHarmonics,
    simulationOversampleFactor: seed.nPumpHarmonics,
    simulationSources: seed.sources.map((source, index) => ({
      sourceId: `official_src_${index + 1}`,
      port: `port_${source.port}`,
      currentAmp: source.currentAmp,
      pumpFreqGhz: source.pumpFreqGhz,
      sourceMode: formatSourceMode(source.mode),
    })),
    simulationPtcEnabled: false,
    simulationPtcMode: defaultSimulationSetupFormValues.simulationPtcMode,
    simulationPtcCompensatePorts: "",
    simulationPtcManualNotes: "",
    simulationAdvancedDampingStrategy:
      defaultSimulationSetupFormValues.simulationAdvancedDampingStrategy,
    simulationAdvancedLineSearchEnabled:
      defaultSimulationSetupFormValues.simulationAdvancedLineSearchEnabled,
    simulationAdvancedResidualClamp:
      defaultSimulationSetupFormValues.simulationAdvancedResidualClamp,
    simulationAdvancedNewtonRelaxation:
      defaultSimulationSetupFormValues.simulationAdvancedNewtonRelaxation,
    simulationAdvancedNotes: defaultSimulationSetupFormValues.simulationAdvancedNotes,
  };
}

export function resolveOfficialSimulationExamplePreset(
  definitionName: string | null | undefined,
): OfficialSimulationExamplePreset | null {
  const exampleName = resolveJosephsonExampleName(definitionName);
  if (!exampleName) {
    return null;
  }

  const seed = JOSEPHSON_OFFICIAL_EXAMPLE_SEEDS[exampleName];
  if (!seed) {
    return null;
  }

  return {
    id: buildOfficialExampleId(exampleName),
    name: "Official Example",
    definitionName: definitionName?.trim() ?? exampleName,
    exampleName,
    values: buildPresetValues(seed),
  };
}
