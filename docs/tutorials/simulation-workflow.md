---
aliases:
  - Simulation Workflow
  - 模擬分析工作流
tags:
  - audience/team
status: stable
owner: docs-team
audience: team
scope: HFSS and Julia simulation workflows under the TraceStore architecture
version: v2.0.0
last_updated: 2026-05-28
updated_by: codex
---

# Simulation Workflow

Use notebooks for direct research execution.
Use the Application Interface for task submission, monitoring, and official result browsing.
Large arrays always move through local Zarr staging and backend publication, not HTTP JSON.

## Application Workflow

```mermaid
flowchart LR
    App["Electron App"] --> Backend["Python Backend"]
    Backend --> Task["TaskRecord"]
    Task --> Runner["Julia Runner"]
    Runner --> Staging["result.zarr + manifest"]
    Staging --> Publisher["Backend Publisher"]
    Publisher --> Store["TraceStore"]
```

## Notebook Workflow

Pluto notebooks may call Julia Core directly.
Use this route when you need direct experimentation, intermediate plots, or fast model iteration.

## Trace Validation

Before analysis, inspect the official trace through:

- `Raw Data`
- `Tasks / Result Browser`
- Python notebook backend API checks

The backend-published TraceStore batch is the numeric authority.

## Related

- [Notebook Interface](../reference/notebooks/index.md)
- [Application Interface](../reference/app/application-interface.md)
- [Julia Runner Compute Plane](../reference/architecture/julia-runner-compute-plane.md)
