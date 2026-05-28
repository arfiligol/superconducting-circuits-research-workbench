---
title: "Sidebar"
aliases:
  - "Frontend Sidebar"
  - "Unified Sidebar"
  - "App Sidebar"
tags:
  - diataxis/reference
  - audience/team
  - sot/true
  - topic/ui
status: stable
owner: docs-team
audience: team
scope: frontend shared sidebar navigation for retained application surfaces
version: v1.2.0
last_updated: 2026-05-28
updated_by: codex
---

# Sidebar

Sidebar is navigation only. It does not own task state, dataset state, Runner runtime status, or help copy.

## Group Contract

| Group | Contains | Must not contain |
|---|---|---|
| Workspace | Dashboard, Dataset, Simulation Workbench, Analysis Workbench, Task / Execution Center | data pipeline steps |
| Data | Data Ingestion, Raw Data | task runtime controls |
| Design Assets | Schemas | full simulation or diagram workflows |

## Navigation Contract

| Label | Route |
|---|---|
| Dashboard | `/dashboard` |
| Dataset | `/dataset` |
| Simulation Workbench | `/tasks?lane=simulation` |
| Analysis Workbench | `/tasks?lane=analysis` |
| Task / Execution Center | `/tasks` |
| Data Ingestion | `/data-ingestion` |
| Raw Data | `/raw-data` |
| Schemas | `/schemas` |

The sidebar may expose Simulation Workbench, Analysis Workbench, and Task / Execution Center as primary product surfaces. It must not expose old characterization or Schemdraw routes as standalone primary pages.

## Density Contract

| Element | Allowed |
|---|---|
| group label | yes |
| nav item title | yes |
| nav item icon | no |
| active state | yes |
| group description | no |
| item summary | no |
| shell identity | no |
| onboarding card | no |

## Related

* [Frontend Reference](../index.md)
* [Header](header.md)
