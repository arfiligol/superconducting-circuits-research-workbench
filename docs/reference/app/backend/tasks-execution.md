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
version: v1.1.0
last_updated: 2026-05-28
updated_by: codex
---

# Tasks & Execution

Python Backend owns task lifecycle. Julia Runner owns compute.

Application-triggered simulation and analysis are asynchronous. The app never sends large numeric arrays over HTTP/JSON.

Product request, Runner envelope, manifest, and result-view boundaries are defined in [Product Async Contracts](../../architecture/product-async-contracts.md). Frontend code and Python notebooks submit product requests; only the Backend compiles Runner task envelopes.

## Task Execution Pipeline

```text
Simulation / Analysis Workbench
    -> SimulationRequestV1 or AnalysisRequestV1
Python Backend
    -> validates request
    -> creates persisted Task
    -> prepares staging directory
Julia Runner
    -> claims task
    -> executes Julia Core / analysis logic
    -> writes result.zarr + manifest.json
    -> reports complete/fail/progress
Python Backend Publisher
    -> validates manifest and Zarr
    -> publishes canonical TraceStore
    -> records TraceBatch / TraceRecord / Result handles
Application
    -> polls or subscribes to task state
    -> opens ResultView after Backend publication
```

The product metaphor is Task Execution Pipeline, Runner Runtime, Task / Execution Center, and ResultView. It is not a separate queue-service UI or standalone runtime wall.

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

## Product Status Labels

| Backend State | Product UI Label |
| --- | --- |
| `queued` | Waiting |
| `claimed` | Preparing |
| `running` | Running |
| `staging_result` | Saving result |
| `publishing` | Publishing |
| `completed` | Completed |
| `failed` | Failed |
| `cancelled` | Cancelled |

Backend state remains the lifecycle authority. Product labels are UI vocabulary.

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

## Runner Task Families

| Kind | Purpose |
|---|---|
| `julia_simulation_frequency_sweep` | frequency-sweep simulation through Julia Runner; currently implemented for the MVP supported design adapter |
| `julia_simulation_parameter_sweep` | parameterized simulation/sweep task family; fails clearly until real sweep execution is implemented |
| `julia_analysis_trace_summary` | analysis task family for published trace summaries |
| `julia_postprocess_coordinate_transform` | post-processing task family for explicit transform jobs |

Unknown or unsupported task kinds fail clearly. Runner execution must not fall back to fixture output.

The first code-backed Runner compute path is `julia_simulation_frequency_sweep` for the MVP supported design path, including the Local Space resonator seed definition. It calls Julia Core to build and compile a `CircuitPlan`, runs JosephsonCircuits through Julia Core simulation helpers, and stages real S-parameter traces.

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
    "task_kind": "julia_simulation_frequency_sweep",
    "input": {
      "simulation_setup": {
        "frequency_sweep": {
          "start_ghz": 4.0,
          "stop_ghz": 6.0,
          "point_count": 401,
          "spacing": "linear"
        },
        "parameter_sweeps": [],
        "solver": {
          "solver_family": "josephson_circuits",
          "max_iterations": 100,
          "convergence_tolerance": 1e-6
        },
        "sources": []
      }
    },
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

Runner completion does not equal product result availability. The Application may open result views only after Backend publication has completed. A Runner manifest is not a published result.

## Application Status Sync

Polling is the baseline status sync mechanism. SSE or WebSocket may be added as a transport optimization, but they must not replace Backend task lifecycle authority.

## Security Rules

| Rule | Meaning |
|---|---|
| no absolute manifest paths | runner cannot point outside staging |
| no `../` traversal | runner cannot escape the task directory |
| no trusted manifest claims | backend verifies every declared array |
| no large JSON arrays | numeric traces live in Zarr only |
| no complex dtype reliance | complex traces use real/imag arrays |

## Execution Rules

- Runner task execution must never silently replace real compute with fixture output.
- Test fixtures may write small staged Zarr packages, but fixture writers are not product task kinds.
- Unsupported task dispatch must report failure rather than complete with fake traces.

## Related

* [Julia Runner Compute Plane](../../architecture/julia-runner-compute-plane.md)
* [Product Async Contracts](../../architecture/product-async-contracts.md)
* [ResultView API](result-view-api.md)
* [Runner Result Manifest](../../architecture/runner-result-manifest.md)
* [TraceStore Zarr](../../architecture/trace-store-zarr.md)
* [Task Management](../frontend/shared-workflow/task-management.md)
