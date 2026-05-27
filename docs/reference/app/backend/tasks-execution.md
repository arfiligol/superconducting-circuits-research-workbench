---
aliases:
  - Backend Tasks Execution Reference
tags:
  - diataxis/reference
  - audience/team
  - sot/true
  - topic/app-reference
status: stable
owner: docs-team
audience: team
scope: Backend task lifecycle, runner API, staging result validation, and TraceStore publication
version: v1.0.0
last_updated: 2026-05-28
updated_by: codex
---

# Tasks & Execution

Python Backend owns task lifecycle. Julia Runner owns compute.

Application-triggered simulation and analysis are asynchronous. The app never sends large numeric arrays over HTTP/JSON.

## Task Statuses

```text
queued
claimed
running
staging_result
publishing
completed
failed
cancelled
```

## Minimum Task Fields

| Field | Meaning |
|---|---|
| `task_id` | public task identity |
| `task_kind` | runner dispatch kind |
| `status` | lifecycle authority |
| `input_payload_json` | small task control/input payload |
| `output_target_json` | dataset/design publication target |
| `staging_payload_json` | backend-prepared staging locators |
| `result_manifest_json` | published manifest summary |
| `error_summary` | stable failure summary |
| `runner_id` | claiming runner identity |
| `claimed_at`, `started_at`, `heartbeat_at`, `completed_at` | lifecycle timestamps |

## Initial Task Kinds

| Kind | Purpose |
|---|---|
| `julia_runner_smoke` | fake compute task for local contract and CI |
| `julia_simulation_parameter_sweep` | first real simulation/sweep task family |

The contract also allows future Julia analysis and post-processing task kinds, but unsupported kinds must fail clearly instead of falling back to legacy execution.

## Runner API

| Endpoint | Purpose |
|---|---|
| `POST /runner/v1/tasks/claim` | atomically claim one queued task |
| `POST /runner/v1/tasks/{task_id}/heartbeat` | refresh runner liveness |
| `POST /runner/v1/tasks/{task_id}/progress` | report small progress payload |
| `GET /runner/v1/tasks/{task_id}/cancellation` | let runner poll cancellation state |
| `POST /runner/v1/tasks/{task_id}/complete` | submit manifest locator and hash |
| `POST /runner/v1/tasks/{task_id}/fail` | report stable failure summary |

## Claim Response

```json
{
  "task": {
    "task_id": "task_001",
    "task_kind": "julia_runner_smoke",
    "input": {},
    "output_target": {
      "dataset_id": "ds_001",
      "design_id": "design_001"
    }
  },
  "staging": {
    "mode": "local_filesystem",
    "task_dir": "data/staging/tasks/task_001",
    "result_zarr": "data/staging/tasks/task_001/result.zarr",
    "manifest": "data/staging/tasks/task_001/manifest.json"
  }
}
```

## Completion Contract

Runner completion sends only manifest metadata:

```json
{
  "runner_id": "runner_local_001",
  "manifest_path": "data/staging/tasks/task_001/manifest.json",
  "manifest_sha256": "..."
}
```

The manifest path must be relative, under the staging task directory, and must not contain path traversal.

## Publication Steps

When the runner completes:

1. Backend marks the task `staging_result`.
2. Backend validates the manifest path and schema.
3. Backend opens staging `result.zarr`.
4. Backend verifies declared arrays, shape, chunk shape, dtype, and axis lengths.
5. Backend marks the task `publishing`.
6. Backend copies or moves the Zarr package into canonical TraceStore.
7. Backend creates TraceBatch/TraceRecord metadata.
8. Backend copies manifest/log artifacts into `data/artifacts/tasks/<task_id>/`.
9. Backend marks the task `completed`.

## Security Rules

| Rule | Meaning |
|---|---|
| no absolute manifest paths | runner cannot point outside staging |
| no `../` traversal | runner cannot escape the task directory |
| no trusted manifest claims | backend verifies every declared array |
| no large JSON arrays | numeric traces live in Zarr only |
| no complex dtype reliance | complex traces use real/imag arrays |

## Related

* [Julia Runner Compute Plane](../../architecture/julia-runner-compute-plane.md)
* [Runner Result Manifest](../../architecture/runner-result-manifest.md)
* [TraceStore Zarr](../../architecture/trace-store-zarr.md)
* [Task Management](../frontend/shared-workflow/task-management.md)
