---
aliases:
  - App Reference
  - UI Reference
  - 介面參考
  - Frontend Reference
tags:
  - diataxis/reference
  - audience/team
  - sot/true
  - topic/app-reference
status: stable
owner: docs-team
audience: team
scope: retained Electron/Next.js application surfaces for the data, simulation, and task workbench
version: v1.1.0
last_updated: 2026-05-28
updated_by: codex
---

# Frontend Reference

The frontend is the Electron application workbench. It is for datasets, traces, simulation requests, analysis requests, task execution, and result browsing.

It must not own heavy compute. Application simulation goes through persisted Backend tasks and Julia Runner execution; direct exploratory compute belongs in Pluto notebooks.

## Visible Navigation

| Group | Page | Route | Primary job |
|---|---|---|---|
| Workspace | Dashboard | `/dashboard` | current workspace and dataset overview |
| Workspace | Dataset | `/dataset` | choose and manage datasets |
| Workspace | Simulation Workbench | `/tasks?lane=simulation` | build or attach simulation requests and inspect simulation results |
| Workspace | Analysis Workbench | `/tasks?lane=analysis` | build or attach analysis, fitting, and post-processing requests |
| Workspace | Task / Execution Center | `/tasks` | monitor task execution, inspect progress, and open results |
| Data | Data Ingestion | `/data-ingestion` | import raw data |
| Data | Raw Data | `/raw-data` | browse traces and preview slices |
| Design Assets | Schemas | `/schemas` | browse source/design documents |

`/circuit-definition-editor` remains a focused editor reached from Design Assets. It is not a primary navigation item.

## Product Boundary

| Surface | Current rule |
|---|---|
| Simulation Workbench | first-class product surface; submits async Backend tasks and renders published results |
| Analysis Workbench | first-class product surface; submits fitting, comparison, post-processing, and derived-parameter tasks |
| Task / Execution Center | cross-workbench task visibility, actions, Runner runtime status summary, and result handoff |
| Schemdraw standalone workflow | Design Assets / Source Documents |

The canonical Simulation Workbench route is `/tasks?lane=simulation` unless a future source-of-truth explicitly changes the application information architecture. The route may share task/result UI components, but the product surface is Application Simulation Workbench.

The canonical Analysis Workbench route is `/tasks?lane=analysis` unless a future source-of-truth explicitly changes the application information architecture. The route may share task/result UI components, but the product surface is Application Analysis Workbench.

## Page Map

| Page | Core focus | Authority pair |
|---|---|---|
| [Header](shared-shell/header.mdx) | compact shell context | [Session & Workspace](../backend/session-workspace.mdx) |
| [Sidebar](shared-shell/sidebar.md) | navigation-only app IA | [Application Interface](../application-interface.md) |
| [Auth Entry](shared-shell/auth-entry.mdx) | online-mode auth entry | [Authentication & Authorization](../shared/authentication-and-authorization.mdx) |
| [Circuit Simulation Workbench](simulation-workbench/circuit-simulation.md) | productized simulation request/result workflow | [Simulation Interface Boundaries](../../reference/architecture/simulation-interface-boundaries.md) |
| [Analysis Workbench](analysis-workbench/analysis-workbench.md) | productized analysis/fitting/post-processing workflow | [Product Async Contracts](../../reference/architecture/product-async-contracts.md), [ResultView API](../backend/result-view-api.md) |
| [Task Management](shared-workflow/task-management.md) | shared task execution monitoring and attach/recover behavior | [Tasks & Execution](../backend/tasks-execution.md) |
| [Dashboard](workspace/dashboard.mdx) | workspace overview | [Datasets & Results](../backend/datasets-results.mdx) |
| [Dataset](workspace/dataset.mdx) | dataset selection and lifecycle | [Datasets & Results](../backend/datasets-results.mdx) |
| [Tasks](workspace/tasks.mdx) | Task / Execution Center | [Tasks & Execution](../backend/tasks-execution.md), [ResultView API](../backend/result-view-api.md) |
| [Data Ingestion](workspace/data-ingestion.mdx) | raw data intake | [Datasets & Results](../backend/datasets-results.mdx) |
| [Raw Data Browser](workspace/raw-data-browser.mdx) | trace browse and preview | [Datasets & Results](../backend/datasets-results.mdx), [ResultView API](../backend/result-view-api.md), [TraceStore Zarr](../../reference/architecture/trace-store-zarr.md) |
| [Schemas](definition/schemas.mdx) | design/source asset catalog | [Circuit Definitions](../backend/circuit-definitions.mdx) |
| [Schema Editor](definition/schema-editor.mdx) | edit one design/source asset | [Circuit Definitions](../backend/circuit-definitions.mdx) |

## UI Rule

The app should show product work surfaces, not architecture explanations. If a user needs to inspect compute details, expose task status, manifest summaries, Runner runtime status summaries, and trace previews. Simulation Workbench and Analysis Workbench must remain async task/result workflows, not in-frontend compute surfaces.

## Related

* [Application Interface](../application-interface.md)
* [Backend Reference](../backend/index.md)
* [Shared App Model](../shared/index.mdx)
* [Architecture Reference](../../reference/architecture/index.md)
