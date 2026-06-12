---
title: "Application Authoring Map"
aliases:
  - App Authoring Map
  - Application Build Order
tags:
  - diataxis/reference
  - audience/contributor
  - sot/true
  - topic/app-reference
status: stable
owner: docs-team
audience: contributor
scope: Required reading order, build order, and ownership map for Application implementation work.
version: v1.1.0
last_updated: 2026-05-28
updated_by: codex
---

# Application Authoring Map

Use this map before implementing Application or Python Notebook product surfaces. It points implementation agents to the source-of-truth documents in the order that prevents inventing product contracts.

## Required Reading Order

1. `README.md`
2. [Folder Structure](../reference/guardrails/project-basics/folder-structure.mdx)
3. [Tech Stack](../reference/guardrails/project-basics/tech-stack.mdx)
4. [Simulation Interface Boundaries](../reference/architecture/simulation-interface-boundaries.md)
5. [Product Async Contracts](../reference/architecture/product-async-contracts.md)
6. [Application Interface](application-interface.md)
7. [Frontend Reference](frontend/index.md)
8. [Backend Reference](backend/index.md)
9. [Tasks & Execution](backend/tasks-execution.md)
10. [Datasets & Results](backend/datasets-results.mdx)
11. [ResultView API](backend/result-view-api.md)
12. [Python Notebook Authoring](../reference/notebooks/python-authoring.md)
13. Surface-specific frontend docs:
    - [Circuit Simulation Workbench](frontend/simulation-workbench/circuit-simulation.md)
    - [Analysis Workbench](frontend/analysis-workbench/analysis-workbench.md)
    - [Tasks](frontend/workspace/tasks.mdx)
    - [Raw Data Browser](frontend/workspace/raw-data-browser.mdx)
    - [Dataset](frontend/workspace/dataset.mdx)

## Build Order

1. Runtime/session shell
2. Dataset selection and Dataset Catalog
3. Design Assets and Target DesignScope selector
4. Task / Execution Center
5. ResultView API and Raw Data Browser preview path
6. Simulation Workbench
7. Analysis Workbench
8. Python Notebook helpers
9. Online mode extensions

This order keeps platform authority in place before product workbenches start composing requests and rendering results.

## Surface Ownership

| Surface | Owns | Must not own |
| --- | --- | --- |
| Frontend | UI state, request composition, task attachment, ResultView rendering | heavy compute, Backend task lifecycle, TraceStore publication |
| Python Backend | task lifecycle, metadata, publication, ResultView, authorization, TraceStore APIs | heavy simulation or analysis in request threads |
| Julia Runner | compute execution, progress, local Zarr staging, manifest writing | formal metadata DB records or publication authority |
| TraceStore | dense numeric data after Backend publication | task lifecycle or request validation |
| Python Notebook | read-only data analysis, Backend API inspection, product task submission through Backend contracts | metadata DB writes, direct TraceStore publication, JuliaCall simulation compute, Runner envelope construction |

## Implementation Rule

When a feature crosses multiple surfaces, implement it as a vertical slice through the accepted contracts:

```text
Application / Python Notebook
    -> Backend product request
    -> persisted Task
    -> Julia Runner
    -> local Zarr staging
    -> Backend publication
    -> ResultView / TraceStore
```

Do not bypass the slice by making the frontend, Electron main process, Python Backend request thread, or Python Notebook own compute or publication authority.

## Related

* [Application Interface](application-interface.md)
* [Product Async Contracts](../reference/architecture/product-async-contracts.md)
* [ResultView API](backend/result-view-api.md)
* [Notebook Interface](../reference/notebooks/index.md)
