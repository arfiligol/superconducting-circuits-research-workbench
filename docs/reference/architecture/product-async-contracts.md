---
title: "Product Async Contracts"
description: "Defines the Application-to-Backend-to-Runner contracts for productized async simulation and result viewing."
icon: lucide/workflow
aliases:
  - Product Async Contract
  - SimulationRequestV1
  - RunnerTaskEnvelopeV1
tags:
  - diataxis/reference
  - audience/team
  - sot/true
  - topic/architecture
status: stable
owner: docs-team
audience: team
scope: Application Simulation Workbench request, Backend task compilation, Runner envelope, Runner manifest, and ResultView API boundaries.
version: v1.0.0
last_updated: 2026-05-28
updated_by: codex
---

# Product Async Contracts

Product async contracts define how product simulation requests become persisted Backend tasks, Runner work, staged results, and published result views.

The Application and Python Notebook may submit product tasks through Backend contracts. They must not construct Runner staging paths, Runner filesystem payloads, or dense numeric arrays.

## Contract Vocabulary

| Contract | Owner | Purpose |
| --- | --- | --- |
| `SimulationRequestV1` | Python Backend API | product request submitted by Application Simulation Workbench or Python Notebook |
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

## RunnerTaskEnvelopeV1

`RunnerTaskEnvelopeV1` is created by the Backend after validating the product request and creating a persisted task row.

Only the Backend creates this envelope. Frontend code and Python notebooks submit `SimulationRequestV1`; they do not build Runner envelopes directly.

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

Result views are Backend-owned read models for the Application and Python Notebook.

They may return:

- task state and publication state
- dataset/design/trace/result metadata
- published result handles
- summary-safe previews
- slice or detail locators

They must not return large ND arrays as HTTP JSON.

## Data Flow

```text
Application Simulation Workbench / Python Notebook
    -> SimulationRequestV1
Python Backend
    -> persisted task
    -> RunnerTaskEnvelopeV1
Julia Runner
    -> local Zarr staging
    -> RunnerResultManifestV1
Python Backend Publisher
    -> TraceStore
    -> ResultView API
```

## Related

- [Simulation Interface Boundaries](simulation-interface-boundaries.md)
- [Tasks & Execution](../app/backend/tasks-execution.md)
- [Julia Runner Compute Plane](julia-runner-compute-plane.md)
- [Runner Result Manifest](runner-result-manifest.md)
- [TraceStore Zarr](trace-store-zarr.md)
