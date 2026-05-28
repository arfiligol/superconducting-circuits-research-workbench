---
aliases:
  - Simulation Interface Boundaries
  - Pluto vs Application Simulation
tags:
  - diataxis/reference
  - audience/contributor
  - sot/true
  - topic/architecture
status: stable
owner: docs-team
audience: contributor
scope: Defines the boundary between Pluto research simulation, Python Notebook data inspection, Application Simulation Workbench, Backend, and Julia Runner.
version: v1.1.0
last_updated: 2026-05-28
updated_by: codex
---

# Simulation Interface Boundaries

This page defines which interface owns each simulation-facing workflow, data-inspection path, and platform state change. Use it when you need to decide whether work belongs in Pluto, a Python notebook, the Electron application, the Python Backend, or Julia Runner.

The project has two simulation-facing execution tracks and one data-inspection track.

## Research Direct Track

```text
Pluto Notebook
    -> Julia Core
    -> direct JosephsonCircuits.jl / Julia analysis
    -> local research outputs
```

Pluto Notebook is the direct Julia Core research interface. It is used to prototype physics, component APIs, sweeps, and analysis logic.

It is not a Backend task submitter in the platform architecture.

Pluto outputs are research-local by default. They are not canonical TraceStore records. If a Pluto result should become official platform data, it must go through an explicit import/publication workflow defined separately.

## Product Async Track

```text
Electron Application / Python Notebook when submitting platform tasks
    -> Python Backend
    -> persisted Task
    -> Julia Runner
    -> local Zarr staging
    -> Backend publication
    -> TraceStore / Result View
```

Application Simulation Workbench is the productized simulation surface. It submits persisted simulation requests and renders published results.

Application Simulation Workbench is expected to submit real simulation requests. It must not rely on Runner fixture tasks as a substitute for compute implementation.

See [Product Async Contracts](product-async-contracts.md) for the product request, Backend-compiled Runner envelope, Runner manifest, and result-view boundary.

## Data / Platform Notebook Track

```text
Python Notebook
    -> direct local/exported/canonical data reads
    -> Backend APIs for platform state, task submission, metadata, publication, provenance
```

Python Notebook is a programmable data-analysis and inspection surface.

It may:

- call Backend APIs for dataset, task, trace, result metadata, and platform-aware queries;
- submit tasks through the same Backend contracts used by the Application;
- directly read local Zarr, exported data, CSV/raw files, and canonical TraceStore files for ad hoc analysis.

It must not:

- directly mutate the formal metadata DB;
- directly publish, overwrite, or register canonical TraceStore records;
- define a separate simulation request schema;
- use JuliaCall or Julia Core as the normal simulation compute path.

Python Notebook is useful for file inspection, debugging, migration checks, emergency analysis, and platform-aware API inspection. It is not the research-grade scientific compute cockpit; that role belongs to Pluto.

## Surface Responsibilities

| Surface | Responsibility |
| --- | --- |
| Pluto Notebook | Direct research computation through Julia Core |
| Python Notebook | Programmable data analysis, file inspection, Backend metadata/task/result API usage |
| Application Simulation Workbench | Productized simulation request builder, task monitor, result viewer |
| Python Backend | Task lifecycle, request validation, publication, TraceStore, result view APIs |
| Julia Runner | Async compute execution and local Zarr staging |
| Julia Core | Circuit construction, delayed lowering, simulation and analysis primitives |

## Non-Goals

- Pluto Notebook must not become an Application workflow client.
- Python Notebook must not become a Julia compute cockpit or direct platform publication path.
- Application frontend must not run heavy simulation.
- Python Backend must not run heavy simulation in request threads.
- Julia Runner must not own formal metadata DB records.
- Fixture outputs must not be treated as product simulation results.

## Promotion Path

```text
Prototype in Pluto
    -> stabilize Julia Core API
    -> implement Julia Runner task
    -> expose Backend request/result contract
    -> productize in Application Simulation Workbench
```

This path lets Julia Core, Pluto, and the Application develop together without duplicating compute ownership.
