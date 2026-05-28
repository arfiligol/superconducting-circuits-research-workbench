---
title: "Analysis Workbench"
aliases:
  - "Application Analysis Workbench"
  - "Fitting Workbench"
tags:
  - diataxis/reference
  - audience/team
  - sot/true
  - topic/app-reference
status: stable
owner: docs-team
audience: team
scope: productized Application Analysis Workbench contract
version: v1.0.0
last_updated: 2026-05-28
updated_by: codex
---

# Analysis Workbench

Analysis Workbench is the productized application surface for fitting, post-processing, comparison, trace summary, and derived-parameter extraction.

It does not run heavy compute in the frontend, Electron main process, or Backend request thread.

## Execution Contract

```text
Application Analysis Workbench
    -> Python Backend AnalysisRequestV1
    -> persisted Task
    -> Julia Runner
    -> local Zarr staging
    -> Backend publication
    -> TraceStore / ResultView
```

The workbench builds product-grade analysis requests, submits them to the Backend, monitors task state, and renders published results through the shared task/result surfaces.

See [Product Async Contracts](../../../architecture/product-async-contracts.md) for the product request, Runner envelope, manifest, and ResultView contract.

## Responsibilities

Analysis Workbench owns:

- analysis / fitting / post-processing request form
- trace/result selection
- dataset/design context confirmation
- task submission
- task attachment and recovery
- stage-local progress context
- ResultView bootstrap and result rendering

It must not own:

- direct full-array mutation
- invisible TraceStore writes
- Backend task lifecycle
- Runner runtime
- TraceStore publication
- heavy compute

## Related

* [Application Interface](../../application-interface.md)
* [Frontend Reference](../index.md)
* [Task Management](../shared-workflow/task-management.md)
* [Datasets & Results](../../backend/datasets-results.md)
* [Product Async Contracts](../../../architecture/product-async-contracts.md)
* [Simulation Interface Boundaries](../../../architecture/simulation-interface-boundaries.md)
