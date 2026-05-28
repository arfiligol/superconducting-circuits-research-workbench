---
title: "Circuit Simulation Workbench"
aliases:
  - "Circuit Simulation UI"
tags:
  - diataxis/reference
  - audience/team
  - sot/true
  - topic/app-reference
status: stable
owner: docs-team
audience: team
scope: productized Application Simulation Workbench contract
version: v1.1.0
last_updated: 2026-05-28
updated_by: codex
---

# Circuit Simulation Workbench

Circuit Simulation Workbench is the productized application surface for simulation requests. It does not run heavy compute in the frontend or Backend request thread.

## Execution Contract

```text
Application Simulation Workbench
    -> Python Backend SimulationRequest
    -> persisted Task
    -> Julia Runner
    -> local Zarr staging
    -> Backend publication
    -> TraceStore / Result View
```

The workbench builds product-grade simulation requests, submits them to the Backend, monitors task state, and renders published results through the shared task/result surfaces.

## Boundary

- Direct Julia experimentation belongs in Pluto notebooks.
- Python notebooks may act as programmable Backend clients.
- Application code must submit async tasks and render published data.
- Large numeric arrays must stay in local filesystem Zarr stores.

## Related

* [Application Interface](../../application-interface.md)
* [Simulation Interface Boundaries](../../../architecture/simulation-interface-boundaries.md)
* [Julia Runner Compute Plane](../../../architecture/julia-runner-compute-plane.md)
* [TraceStore Zarr](../../../architecture/trace-store-zarr.md)
