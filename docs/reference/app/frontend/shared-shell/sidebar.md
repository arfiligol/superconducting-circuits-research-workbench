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
version: v1.1.0
last_updated: 2026-05-28
updated_by: codex
---

# Sidebar

Sidebar is navigation only. It does not own task state, dataset state, worker status, or help copy.

## Group Contract

| Group | Contains | Must not contain |
|---|---|---|
| Workspace | Dashboard, Dataset, Simulation Workbench, Tasks | data pipeline steps |
| Data | Data Ingestion, Raw Data | task runtime controls |
| Design Assets | Schemas | full simulation or diagram workflows |

## Navigation Contract

| Label | Route |
|---|---|
| Dashboard | `/dashboard` |
| Dataset | `/dataset` |
| Simulation Workbench | `/tasks?lane=simulation` |
| Tasks | `/tasks` |
| Data Ingestion | `/data-ingestion` |
| Raw Data | `/raw-data` |
| Schemas | `/schemas` |

The sidebar may expose Simulation Workbench as a primary product surface. It must not expose Characterization or Schemdraw as standalone primary pages.

## Density Contract

| Element | Allowed |
|---|---|
| group label | yes |
| nav item title | yes |
| nav item icon | yes |
| active state | yes |
| group description | no |
| item summary | no |
| shell identity | no |
| onboarding card | no |

## Related

* [Frontend Reference](../index.md)
* [Header](header.md)
