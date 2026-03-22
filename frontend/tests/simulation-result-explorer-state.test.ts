import { describe, expect, it } from "vitest";

import {
  buildEditableSelection,
  buildSimulationResultExplorerQuery,
  buildSimulationResultExplorerSelectionCacheKey,
  composeSimulationResultExplorerPayload,
  decodeSimulationExplorerSweepCoordinates,
  extractSimulationResultExplorerViewSlice,
  primeSimulationResultExplorerViewCache,
  resolveSimulationExplorerSweepAxes,
} from "../src/features/simulation/lib/simulation-result-explorer-state";
import type {
  SimulationResultExplorerBootstrapPayload,
  SimulationResultExplorerPayload,
  SimulationResultExplorerViewPayload,
} from "../src/lib/api/tasks";

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
      ],
      traceSelector: {
        outputPorts: [{ port: 1, label: "Port 1" }],
        inputPorts: [{ port: 1, label: "Port 1" }],
        outputModes: [{ key: "mode_0", label: "Mode 0" }],
        inputModes: [{ key: "mode_0", label: "Mode 0" }],
      },
      parameterSweep: {
        active: true,
        pointCount: 4,
        compareAxisIndex: 1,
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
        compareAxisIndex: 1,
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

function buildViewPayload(taskId: number): SimulationResultExplorerViewPayload {
  return {
    taskId,
    taskStatus: "completed",
    runtimeMode: "local",
    selection: {
      family: "s_matrix",
      source: "raw",
      metric: "magnitude_db",
      sweepIndex: 2,
      compareAxisIndex: 1,
      traceKey: "raw:s_matrix:1:1:2",
      z0Ohm: 50,
      outputPort: 1,
      inputPort: 1,
      outputPortLabel: "Port 1",
      inputPortLabel: "Port 1",
      outputMode: "mode_0",
      inputMode: "mode_0",
    },
    plot: {
      xAxis: {
        label: "Frequency",
        unit: "GHz",
        values: [5, 6, 7],
      },
      yAxis: {
        label: "Magnitude",
        unit: "dB",
        values: [],
      },
      series: [
        {
          seriesId: "raw:s_matrix:1:1:2",
          label: "S11",
          values: [-12, -10, -9],
          unit: "dB",
        },
      ],
      metadata: {
        family: "s_matrix",
        source: "raw",
        metric: "magnitude_db",
        sweepIndex: 2,
        compareAxisIndex: 1,
        traceKey: "raw:s_matrix:1:1:2",
        z0Ohm: 50,
        outputPort: 1,
        inputPort: 1,
        outputPortLabel: "Port 1",
        inputPortLabel: "Port 1",
        tracePayloadStoreKey: "trace-output-31",
      },
    },
  };
}

function buildExplorerPayload(taskId: number): SimulationResultExplorerPayload {
  return composeSimulationResultExplorerPayload(
    buildBootstrapPayload(taskId),
    extractSimulationResultExplorerViewSlice(buildViewPayload(taskId)),
  );
}

describe("simulation result explorer state helpers", () => {
  it("builds task-bound cache keys and view queries from normalized selection", () => {
    const selection = buildEditableSelection(buildExplorerPayload(31).selection);

    expect(buildSimulationResultExplorerSelectionCacheKey(31, selection)).toBe(
      "31:family=s_matrix&source=raw&metric=magnitude_db&z0=50&output_port=1&input_port=1&sweep_index=2&compare_axis_index=1",
    );
    expect(buildSimulationResultExplorerSelectionCacheKey(44, selection)).not.toBe(
      buildSimulationResultExplorerSelectionCacheKey(31, selection),
    );
    expect(buildSimulationResultExplorerQuery(selection)).toEqual({
      family: "s_matrix",
      source: "raw",
      metric: "magnitude_db",
      sweepIndex: 2,
      compareAxisIndex: 1,
      z0: 50,
      outputPort: 1,
      inputPort: 1,
    });
  });

  it("splits bootstrap payload from full-resolution current view slices", () => {
    const bootstrapPayload = buildBootstrapPayload(31);
    const viewSlice = extractSimulationResultExplorerViewSlice({
      ...buildViewPayload(31),
      selection: {
        ...buildViewPayload(31).selection,
        sweepIndex: 3,
        traceKey: "raw:s_matrix:1:1:3",
      },
      plot: {
        ...buildViewPayload(31).plot,
        series: [
          {
            seriesId: "raw:s_matrix:1:1:3",
            label: "S11",
            values: [-8, -7, -6],
            unit: "dB",
          },
        ],
        metadata: {
          ...buildViewPayload(31).plot.metadata,
          sweepIndex: 3,
          traceKey: "raw:s_matrix:1:1:3",
        },
      },
    });

    expect(composeSimulationResultExplorerPayload(bootstrapPayload, viewSlice)).toMatchObject({
      taskId: 31,
      bootstrap: bootstrapPayload.bootstrap,
      selection: {
        sweepIndex: 3,
        traceKey: "raw:s_matrix:1:1:3",
      },
      plot: {
        metadata: {
          sweepIndex: 3,
          traceKey: "raw:s_matrix:1:1:3",
        },
      },
    });
  });

  it("keeps a bounded cache and reuses the most recently primed selection slices", () => {
    const cache = new Map();

    primeSimulationResultExplorerViewCache(
      cache,
      "31:default",
      extractSimulationResultExplorerViewSlice(buildViewPayload(31)),
      2,
    );
    primeSimulationResultExplorerViewCache(
      cache,
      "31:alt",
      extractSimulationResultExplorerViewSlice(buildViewPayload(31)),
      2,
    );
    primeSimulationResultExplorerViewCache(
      cache,
      "31:newest",
      extractSimulationResultExplorerViewSlice(buildViewPayload(31)),
      2,
    );

    expect([...cache.keys()]).toEqual(["31:alt", "31:newest"]);
  });

  it("rebuilds current sweep selection from bootstrap axes without refetching bootstrap metadata", () => {
    const axes = buildExplorerPayload(31).bootstrap.parameterSweep.axes;

    expect(decodeSimulationExplorerSweepCoordinates(axes, 3)).toEqual([3]);
    expect(resolveSimulationExplorerSweepAxes(axes, 1)[0]?.selectedValueIndex).toBe(1);
  });
});
