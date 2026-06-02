---
title: "Task Management"
aliases:
  - "Frontend Task Management"
  - "Task Execution Management"
  - "Task Attachment"
tags:
  - diataxis/reference
  - audience/team
  - sot/true
  - topic/ui
status: stable
owner: docs-team
audience: team
scope: frontend task monitor, attachment, progress, and result handoff behavior
version: v1.0.0
last_updated: 2026-05-28
updated_by: codex
---

# Task Management

Task Management means task execution visibility, task attachment, recovery, and result handoff. It does not mean a separate queue-service UI or standalone runtime wall.

The frontend monitors persisted tasks. It does not execute simulation or analysis.

## Surface Boundary

| Surface | Owns |
|---|---|
| Header task trigger | compact task visibility and quick task status |
| Task / Execution Center | extended task browse, detail, progress, errors, result handoff |
| Simulation Workbench | product simulation request-building, task submission, stage-local simulation result context |
| Analysis Workbench | product analysis/fitting/post-processing request-building, task submission, stage-local analysis result context |

Simulation Workbench and Analysis Workbench are active first-class Application surfaces.

They may reuse shared task/result components, but they must not reimplement task lifecycle, Runner runtime, Backend publication, or TraceStore authority.

## Task Row Contract

| Field | Meaning |
|---|---|
| `task_id` | attach/recover key |
| `task_kind` | runner dispatch kind |
| `status` | lifecycle echo from backend |
| `summary` | human-readable label |
| `dataset_id`, `design_id` | output target context when available |
| `updated_at` | sort and activity signal |
| `result_availability` | discovery hint only; detail remains authority |

## Result Handoff

The app may open result views only after backend publication has completed. A runner manifest by itself is not a published result.

Runner completion does not equal product result availability. Result handoff belongs to the Backend-owned ResultView API after publication.

## UI Rules

| Rule | Meaning |
|---|---|
| task detail wins over row summary | page detail must refetch by `task_id` |
| no large arrays in task payloads | trace previews must use backend trace APIs |
| no duplicate execution runtime inside workbenches | workbenches may submit tasks and render results, but they must not recreate a separate task lifecycle, Runner runtime surface, or compute runtime |
| no standalone runtime wall | show Runner runtime status compactly as execution context, not as the product metaphor |

## Related

* [Tasks](../workspace/tasks.md)
* [Backend / Tasks & Execution](../../backend/tasks-execution.md)
* [TraceStore Zarr](../../../architecture/trace-store-zarr.md)
