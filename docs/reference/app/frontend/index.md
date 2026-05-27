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
scope: retained Electron/Next.js application surfaces for the data and task workbench
version: v1.0.0
last_updated: 2026-05-28
updated_by: codex
---

# Frontend Reference

The frontend is the Electron application workbench. It is for dataset, trace, task, and result browsing.

It is not the primary simulation or heavy-analysis cockpit. Compute goes through Julia Runner tasks or explicit notebook execution.

## Visible Navigation

| Group | Page | Route | Primary job |
|---|---|---|---|
| Workspace | Dashboard | `/dashboard` | current workspace and dataset overview |
| Workspace | Dataset | `/dataset` | choose and manage datasets |
| Workspace | Tasks | `/tasks` | monitor tasks and inspect results |
| Data | Data Ingestion | `/data-ingestion` | import raw data |
| Data | Raw Data | `/raw-data` | browse traces and preview slices |
| Design Assets | Schemas | `/schemas` | browse source/design documents |

`/circuit-definition-editor` remains a focused editor reached from Design Assets. It is not a primary navigation item.

## Removed From Primary Nav

| Removed surface | Current replacement |
|---|---|
| Circuit Simulation | task submission/result browsing + Pluto direct Julia cockpit |
| Characterization | Julia Runner analysis tasks + result browser |
| Schemdraw standalone workflow | Design Assets / Source Documents |

## Page Map

| Page | Core focus | Authority pair |
|---|---|---|
| [Header](shared-shell/header.md) | compact shell context | [Session & Workspace](../backend/session-workspace.md) |
| [Sidebar](shared-shell/sidebar.md) | navigation-only app IA | [Application Interface](../application-interface.md) |
| [Auth Entry](shared-shell/auth-entry.md) | online-mode auth entry | [Authentication & Authorization](../shared/authentication-and-authorization.md) |
| [Task Management](shared-workflow/task-management.md) | shared task monitoring and attach/recover behavior | [Tasks & Execution](../backend/tasks-execution.md) |
| [Dashboard](workspace/dashboard.md) | workspace overview | [Datasets & Results](../backend/datasets-results.md) |
| [Dataset](workspace/dataset.md) | dataset selection and lifecycle | [Datasets & Results](../backend/datasets-results.md) |
| [Tasks](workspace/tasks.md) | task/result browser | [Tasks & Execution](../backend/tasks-execution.md) |
| [Data Ingestion](workspace/data-ingestion.md) | raw data intake | [Datasets & Results](../backend/datasets-results.md) |
| [Raw Data Browser](workspace/raw-data-browser.md) | trace browse and preview | [Datasets & Results](../backend/datasets-results.md), [TraceStore Zarr](../../architecture/trace-store-zarr.md) |
| [Schemas](definition/schemas.md) | design/source asset catalog | [Circuit Definitions](../backend/circuit-definitions.md) |
| [Schema Editor](definition/schema-editor.md) | edit one design/source asset | [Circuit Definitions](../backend/circuit-definitions.md) |

## UI Rule

The app should show product work surfaces, not architecture explanations. If a user needs to inspect compute details, expose task status, manifest summaries, and trace previews. Do not reintroduce simulation or characterization workbenches as hidden page bodies.

## Related

* [Application Interface](../application-interface.md)
* [Backend Reference](../backend/index.md)
* [Shared App Model](../shared/index.md)
* [Architecture Reference](../../architecture/index.md)
