---
title: "Product Async Contracts"
description: "Defines the Application-to-Backend-to-Runner contracts for productized async simulation and result viewing."
icon: lucide/workflow
aliases:
  - Product Async Contract
  - SimulationRequestV1
  - AnalysisRequestV1
  - RunnerTaskEnvelopeV1
tags:
  - diataxis/reference
  - audience/team
  - sot/true
  - topic/architecture
status: stable
owner: docs-team
audience: team
scope: Application Simulation/Analysis Workbench requests, Backend task compilation, Runner envelope, Runner manifest, and ResultView API boundaries.
version: v1.4.0
last_updated: 2026-05-29
updated_by: codex
---

# Product Async Contracts

Product async contracts define how product simulation and analysis requests become persisted Backend tasks, Runner work, staged results, and published result views.

The Application and Python Notebook may submit product tasks through Backend contracts. They must not construct Runner staging paths, Runner filesystem payloads, or dense numeric arrays.

## Contract Vocabulary

| Contract | Owner | Purpose |
| --- | --- | --- |
| `SimulationRequestV1` | Python Backend API | product request submitted by Application Simulation Workbench or Python Notebook |
| `AnalysisRequestV1` | Python Backend API | product request submitted by Application Analysis Workbench or Python Notebook |
| `RunnerTaskEnvelopeV1` | Python Backend | Backend-compiled task envelope claimed by Julia Runner |
| `RunnerResultManifestV1` | Julia Runner writes; Python Backend validates | staged result declaration; see [Runner Result Manifest](runner-result-manifest.md) |
| `ResultView API` | Python Backend | status, metadata, published result handles, summary-safe previews, and trace/detail locators |

## SimulationRequestV1

`SimulationRequestV1` is the product-facing run request shape. It carries a runtime run request and references a design / circuit definition whose CircuitPlan owns the canonical simulation intent.

The request binds runtime values to compiled HB intent. It does not declare ports, source slots, pump axes, mode tuples, observable semantics, or JosephsonCircuits internals.

This page defines the target product contract. Current implementation may still be behind this contract and should be updated directly toward this shape without compatibility shims.

## SimulationRequestV1 Minimum Shape

```json
{
  "schema_version": "app.simulation_request.v1",
  "dataset_id": "ds_001",
  "design_id": "design_001",
  "source": {
    "kind": "design_asset",
    "asset_id": "design_asset_001"
  },
  "simulation_family": "frequency_sweep",
  "frequency_sweep": {
    "start_hz": 4000000000,
    "stop_hz": 6000000000,
    "point_count": 401,
    "spacing": "linear"
  },
  "runtime_bindings": {
    "pump_frequencies_hz": {
      "pump": 8000000000
    },
    "source_currents": {
      "pump_in": 0.0
    }
  },
  "observables": [
    {
      "observable_id": "s11_signal",
      "representation": "complex"
    }
  ],
  "solver": {
    "engine": "josephson_circuits",
    "hb_controls": {
      "n_pump_harmonics": {
        "pump": 16
      },
      "n_modulation_harmonics": 8,
      "dc": false,
      "threewavemixing": false,
      "fourwavemixing": true,
      "returnS": true,
      "returnZ": true,
      "returnQE": true,
      "returnCM": true,
      "sorting": "name",
      "keyedarrays": false
    },
    "optional_hb_kwargs": {}
  },
  "output_target": {
    "mode": "existing_design",
    "design_id": "design_001"
  }
}
```

### Simulation request field rules

| Field | Rule |
| --- | --- |
| `schema_version` | must be explicit |
| `dataset_id` | active dataset identity |
| `design_id` | active target `DesignScope` unless `output_target.mode = create_new_design` |
| `source` | product-level design / circuit definition reference, not a Julia internal object |
| `simulation_family` | Backend-recognized simulation family |
| `frequency_sweep` | required for `frequency_sweep` family |
| `runtime_bindings` | runtime pump-frequency and source-current bindings by compiled HB intent ID |
| `observables` | selected observable IDs allowed by compiled HB intent |
| `solver` | first-class solver controls and whitelisted optional HB kwargs |
| `output_target` | explicit publication target decision |

### Simulation request must not carry

- Runner staging directories
- `RunnerTaskEnvelopeV1`
- manifest paths
- TraceStore write paths
- dense S/Y/Z matrices or ND trace arrays
- Julia-internal execution objects
- new port declarations
- new source slot declarations
- new pump-axis declarations
- new observable semantics
- raw JosephsonCircuits internals not represented by the Core HB contract

## AnalysisRequestV1

`AnalysisRequestV1` is the product-facing request shape for fitting, post-processing, comparison, trace summaries, and derived-parameter extraction.

It carries:

- analysis intent and task family
- trace/result handle selection
- dataset/design context
- bounded analysis parameters and display preferences
- small control metadata

It must not carry:

- full trace payloads
- Runner staging directories
- manifest paths
- TraceStore write paths
- separate simulation request schemas

## Analysis Family Registry

The initial `analysis_family` registry is:

| `analysis_family` | Purpose | Inputs | Output expectation |
| --- | --- | --- | --- |
| `trace_summary` | compute summary statistics / metadata summaries from selected traces | trace IDs or result handles | summary table / result handle |
| `resonance_fit` | fit resonator-like response curves | one or more complex traces with frequency axis | fitted parameters, fit curve, residual summary |
| `sy_z_compare` | compare S/Y/Z representations | compatible S/Y/Z trace families | comparison metrics and aligned projections |
| `postprocess_coordinate_transform` | convert published trace coordinates or representations | trace/result selection and transform parameters | transformed trace/result artifact |
| `derived_parameter_extraction` | extract scalar/vector derived parameters | selected traces or prior results | derived parameter table / metadata artifact |

Registry rules:

1. Frontend code must not invent new `analysis_family` values.
2. Python Notebook helpers must use the same registry when submitting `AnalysisRequestV1`.
3. Backend validates `analysis_family` before creating task rows.
4. Julia Runner dispatch maps Backend-validated families to task kinds.
5. Unsupported `analysis_family` values must fail validation before Runner execution.

## RunnerTaskEnvelopeV1

`RunnerTaskEnvelopeV1` is created by the Backend after validating the product request and creating a persisted task row.

Only the Backend creates this envelope. Frontend code and Python notebooks submit `SimulationRequestV1` or `AnalysisRequestV1`; they do not build Runner envelopes directly.

The envelope includes:

- task identity and task kind
- small input payload
- Backend-owned output target
- Backend-prepared local staging locators
- cancellation, heartbeat, progress, complete, and fail protocol expectations

## RunnerResultManifestV1

Runner completion returns a manifest locator and hash. The manifest itself describes local filesystem Zarr arrays, axes, shapes, chunks, dtype, producer metadata, summaries, and logs.

The manifest is not trusted until the Backend validates it and publishes the result into the canonical TraceStore.

## ResultView API

ResultView is a Backend-owned read model for Application and Python Notebook consumers. It is the product-facing result availability and rendering contract after Backend publication.

The detailed Backend authoring contract lives in [ResultView API](../app/backend/result-view-api.md).

It provides:

- task state and publication state
- available result handles
- trace metadata
- summary-safe previews
- plot-ready projections
- slice/detail locators

It must not return large ND arrays as HTTP JSON.

### ResultView endpoint families

Endpoint names are product contract families. Exact route names may evolve only through the Backend owner docs and OpenAPI contract.

| Endpoint family | Purpose |
| --- | --- |
| `GET /tasks/{task_id}/results/bootstrap` | returns task result status, publication status, available result handles, available traces, and default views |
| `GET /tasks/{task_id}/results/view` | returns plot-ready projection for a selected result handle, trace, or view |
| `GET /traces/{trace_id}/preview` | returns summary-safe preview |
| `GET /traces/{trace_id}/slice` | returns selected slice/projection bounded by payload size rules |

### Baseline result views

| View | Meaning |
| --- | --- |
| `magnitude_db` | magnitude in decibels for complex trace families |
| `phase` | phase view for complex trace families |
| `real_imag` | paired real and imaginary components |
| `sweep_heatmap` | sweep-aware 2D projection of a selected trace/result |
| `selected_nd_slice` | bounded slice through an ND trace |

The Application receives only summary-safe or plot-ready data. It does not read full Zarr arrays directly. The Backend reads Zarr and returns bounded previews, projections, handles, or locators.

Runner completion does not equal product result availability. A Runner manifest is not a published result; Application and Python Notebook consumers open ResultView only after Backend publication completes.

### Status sync

Polling is the baseline status sync mechanism. SSE or WebSocket may be added as a transport optimization, but they must not replace Backend task lifecycle authority.

## Data Flow

```text
Simulation / Analysis Workbench or Python Notebook
    -> SimulationRequestV1 or AnalysisRequestV1
Python Backend
    -> validates request
    -> persisted task
    -> RunnerTaskEnvelopeV1
Julia Runner
    -> executes Julia Core / analysis logic
    -> local Zarr staging
    -> RunnerResultManifestV1
Python Backend Publisher
    -> validates manifest and Zarr
    -> TraceStore
    -> ResultView API
Application / Python Notebook
    -> polls task state
    -> opens ResultView after Backend publication
```

## Related

- [Simulation Interface Boundaries](simulation-interface-boundaries.md)
- [Tasks & Execution](../app/backend/tasks-execution.md)
- [ResultView API](../app/backend/result-view-api.md)
- [Julia Runner Compute Plane](julia-runner-compute-plane.md)
- [Runner Result Manifest](runner-result-manifest.md)
- [TraceStore Zarr](trace-store-zarr.md)
