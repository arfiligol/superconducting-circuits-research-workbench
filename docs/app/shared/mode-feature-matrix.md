---
title: "Mode Feature Matrix"
aliases:
 - "Local Online Feature Matrix"
 - "Runtime Mode Feature Matrix"
tags:
 - diataxis/reference
 - audience/team
 - sot/true
 - topic/app-reference
status: stable
owner: docs-team
audience: team
scope: Local Mode / Online Mode support for retained application surfaces
version: v1.0.0
last_updated: 2026-05-28
updated_by: codex
---

# Mode Feature Matrix

The same application surfaces are used in local and online modes. Runtime ownership changes, but the app remains a data and task workbench.

## Shared Shell Matrix

| Concern | Local Mode | Online Mode | Notes |
|---|---|---|---|
| Header shell identity | `full` | `full` | same shell |
| Runtime mode switch | `full` | `full` | no implicit data migration |
| Account drawer | `reduced` | `full` | local uses local operator context |
| Active workspace | `reduced` | `full` | local fixed to local workspace |
| Active dataset | `full` | `full` | backed by mode-specific backend authority |
| Tasks | `full` | `full` | same task lifecycle vocabulary |

## Application Surface Matrix

| Surface | Local Mode | Online Mode | Notes |
|---|---|---|---|
| Dashboard | `full` | `full` | local data root vs hosted workspace data |
| Dataset | `full` | `full` | dataset metadata owned by backend |
| Simulation Workbench | `full` | `full` | submits persisted simulation tasks through Backend |
| Analysis Workbench | `full` | `full` | submits persisted analysis/fitting/post-processing tasks through Backend |
| Data Ingestion | `full` | `full` | explicit import/upload only |
| Raw Data | `full` | `full` | trace APIs read canonical store |
| Task / Execution Center | `full` | `full` | local uses local runner, online uses server-side compute plane |
| Design Assets | `full` | `full` | source/design metadata, not simulation cockpit |

## Compute Matrix

| Capability | Local Mode | Online Mode | Notes |
|---|---|---|---|
| App-triggered simulation | `full` | `full` | asynchronous Julia Runner task |
| App-triggered analysis | `full` | `full` | asynchronous Julia Runner task |
| Notebook direct execution | `full` | `reduced` | explicit research execution environment |
| User-facing command workflow | `removed` | `removed` | scripts are not product surface |

## Related

* [Runtime Modes](runtime-modes.mdx)
* [Task Runtime & Processors](task-runtime-and-processors.md)
* [Application Interface](../application-interface.md)
