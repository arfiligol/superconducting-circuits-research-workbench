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
version: v1.1.0
last_updated: 2026-05-28
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

`SimulationRequestV1` is the product-facing request shape. It carries the simulation intent, dataset/design target, solver settings, sweep definitions, and small control metadata.

It must not carry:

- Runner staging directories
- manifest paths
- TraceStore write paths
- dense S/Y/Z matrices or ND trace arrays
- Julia-internal execution objects

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
- [Julia Runner Compute Plane](julia-runner-compute-plane.md)
- [Runner Result Manifest](runner-result-manifest.md)
- [TraceStore Zarr](trace-store-zarr.md)
