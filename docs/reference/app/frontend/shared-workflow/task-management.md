---
title: "Task Management"
aliases:
  - "Frontend Task Management"
  - "Task Queue"
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

The frontend monitors persisted tasks. It does not execute simulation or analysis.

## Surface Boundary

| Surface | Owns |
|---|---|
| Header task trigger | compact task visibility |
| `/tasks` | extended task browse, detail, progress, errors, result handoff |
| workflow pages | none; simulation/analysis workbenches are not active app surfaces |

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

## UI Rules

| Rule | Meaning |
|---|---|
| task detail wins over row summary | page detail must refetch by `task_id` |
| no large arrays in task payloads | trace previews must use backend trace APIs |
| no worker dashboard wall | show runner/task status compactly |
| no workbench reintroduction | task monitoring must not recreate removed simulation/analysis workbenches |

## Related

* [Tasks](../workspace/tasks.md)
* [Backend / Tasks & Execution](../../backend/tasks-execution.md)
* [TraceStore Zarr](../../../architecture/trace-store-zarr.md)
