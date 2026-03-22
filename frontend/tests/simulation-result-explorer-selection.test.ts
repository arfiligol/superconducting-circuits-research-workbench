import { describe, expect, it } from "vitest";

import {
  buildExplorerSelectionUpdateContext,
  deriveSimulationResultExplorerState,
  updateExplorerCompareAxisSelection,
  updateExplorerFamilySelection,
  updateExplorerInputPortSelection,
  updateExplorerOutputPortSelection,
  updateExplorerSweepValueSelection,
} from "../src/features/simulation/lib/simulation-result-explorer-selection";
import type { SimulationResultExplorerBootstrapPayload } from "../src/lib/api/tasks";

function buildBootstrapPayload(taskId: number): SimulationResultExplorerBootstrapPayload {
  return {
    taskId,
    taskStatus: "completed",
    runtimeMode: "local",
    bootstrap: {
      families: [
        {
          key: "s_matrix",
          label: "S Matrix",
          availableSources: [{ key: "raw", label: "Raw" }],
          availableMetrics: [{ key: "magnitude_db", label: "Magnitude (dB)", unit: "dB" }],
        },
        {
          key: "z_matrix",
          label: "Z Matrix",
          availableSources: [
            { key: "raw", label: "Raw" },
            { key: "ptc", label: "PTC" },
          ],
          availableMetrics: [{ key: "real", label: "Real", unit: "ohm" }],
        },
      ],
      traceSelector: {
        outputPorts: [
          { port: 1, label: "Port 1" },
          { port: 2, label: "Port 2" },
        ],
        inputPorts: [
          { port: 1, label: "Port 1" },
          { port: 2, label: "Port 2" },
        ],
        outputModes: [{ key: "mode_0", label: "Mode 0" }],
        inputModes: [{ key: "mode_0", label: "Mode 0" }],
      },
      parameterSweep: {
        active: true,
        pointCount: 4,
        compareAxisIndex: 0,
        axes: [
          {
            parameter: "L_jun",
            label: "L_jun",
            unit: "nH",
            values: [20, 22, 24, 26],
            selectedValueIndex: 2,
          },
        ],
      },
      defaultSelection: {
        family: "s_matrix",
        source: "raw",
        metric: "magnitude_db",
        sweepIndex: 2,
        compareAxisIndex: 0,
        traceKey: "raw:s_matrix:1:1:2",
        z0Ohm: 50,
        outputPort: 1,
        inputPort: 1,
        outputPortLabel: "Port 1",
        inputPortLabel: "Port 1",
        outputMode: "mode_0",
        inputMode: "mode_0",
      },
    },
    resultBasis: {
      tracePayloadAvailable: true,
      primaryResultHandleId: "handle-31",
      traceBatchId: 31,
    },
  };
}

describe("simulation result explorer selection helpers", () => {
  it("derives bootstrap selection, keys, and refresh state from the active task", () => {
    const bootstrapPayload = buildBootstrapPayload(31);
    const derived = deriveSimulationResultExplorerState({
      taskId: 31,
      bootstrapPayload,
      selection: null,
      activeViewKey: "31:family=s_matrix&source=raw&metric=magnitude_db&z0=50&output_port=1&input_port=1&sweep_index=2&compare_axis_index=0",
    });

    expect(derived.bootstrapSelection?.family).toBe("s_matrix");
    expect(derived.effectiveSelection?.traceKey).toBe("raw:s_matrix:1:1:2");
    expect(derived.bootstrapViewKey).toBe(
      "31:family=s_matrix&source=raw&metric=magnitude_db&z0=50&output_port=1&input_port=1&sweep_index=2&compare_axis_index=0",
    );
    expect(derived.requestedViewKey).toBe(derived.bootstrapViewKey);
    expect(derived.isRefreshingSelection).toBe(false);
  });

  it("updates family selection while keeping the compare-axis semantics intact", () => {
    const bootstrapPayload = buildBootstrapPayload(31);
    const context = buildExplorerSelectionUpdateContext(bootstrapPayload, {
      family: "s_matrix",
      source: "raw",
      metric: "magnitude_db",
      sweepIndex: 2,
      compareAxisIndex: 0,
      traceKey: "raw:s_matrix:1:1:2",
      z0: 50,
      outputPort: 1,
      inputPort: 1,
    });

    const updated = updateExplorerFamilySelection(
      {
        family: "s_matrix",
        source: "raw",
        metric: "magnitude_db",
        sweepIndex: 2,
        compareAxisIndex: 0,
        traceKey: "raw:s_matrix:1:1:2",
        z0: 50,
        outputPort: 1,
        inputPort: 1,
      },
      context!,
      "z_matrix",
    );

    expect(updated.family).toBe("z_matrix");
    expect(updated.source).toBe("raw");
    expect(updated.metric).toBe("real");
    expect(updated.compareAxisIndex).toBe(0);
  });

  it("updates sweep, compare-axis, and port selections through pure helpers", () => {
    const bootstrapPayload = buildBootstrapPayload(31);
    const context = buildExplorerSelectionUpdateContext(bootstrapPayload, null);
    const baseSelection = {
      family: "s_matrix",
      source: "raw",
      metric: "magnitude_db",
      sweepIndex: 2,
      compareAxisIndex: 0,
      traceKey: "raw:s_matrix:1:1:2",
      z0: 50,
      outputPort: 1,
      inputPort: 1,
    };

    expect(updateExplorerSweepValueSelection(baseSelection, context!, 0, 1).sweepIndex).toBe(1);
    expect(updateExplorerCompareAxisSelection(baseSelection, context!, 0).compareAxisIndex).toBe(
      0,
    );
    expect(updateExplorerOutputPortSelection(baseSelection, context!, 2).outputPort).toBe(2);
    expect(updateExplorerInputPortSelection(baseSelection, context!, 99).inputPort).toBe(1);
  });
});
