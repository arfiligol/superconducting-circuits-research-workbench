---
title: "Analysis Workbench"
aliases:
  - "Application Analysis Workbench"
  - "Fitting Workbench"
tags:
  - diataxis/reference
  - audience/team
  - sot/true
  - topic/app-reference
status: stable
owner: docs-team
audience: team
scope: productized Application Analysis Workbench contract
version: v1.2.0
last_updated: 2026-05-28
updated_by: codex
---

# Analysis Workbench

Analysis Workbench is the productized application surface for fitting, post-processing, comparison, trace summary, and derived-parameter extraction.

It does not run heavy compute in the frontend, Electron main process, or Backend request thread.

## Execution Contract

```text
Application Analysis Workbench
    -> Python Backend AnalysisRequestV1
    -> persisted Task
    -> Julia Runner
    -> local Zarr staging
    -> Backend publication
    -> TraceStore / ResultView
```

The workbench builds product-grade analysis requests, submits them to the Backend, monitors task state, and renders published results through the shared task/result surfaces.

See [Product Async Contracts](../../../reference/architecture/product-async-contracts.md) for the product request, `Analysis Family Registry`, Runner envelope, manifest, and ResultView contract.

## Responsibilities

Analysis Workbench owns:

- analysis / fitting / post-processing request form
- trace/result selection
- dataset/design context confirmation
- task submission
- task attachment and recovery
- stage-local progress context
- ResultView bootstrap and result rendering

It must not own:

- direct full-array mutation
- invisible TraceStore writes
- Backend task lifecycle
- Runner runtime
- TraceStore publication
- heavy compute

## Analysis Selection Model

- User may explicitly select traces.
- Backend interprets selections through persisted trace structure.
- Analysis Workbench may consume analysis-facing trace projection from [Datasets & Results](../../backend/datasets-results.mdx).
- Raw checkbox list is not the final scientific collection model.
- `collection_projection` is a read model, not a persisted owner.
- Result handles may be selected as upstream inputs when the analysis depends on prior published results.

## AnalysisRequestV1 Minimum Shape

```json
{
  "schema_version": "app.analysis_request.v1",
  "dataset_id": "ds_001",
  "design_id": "design_001",
  "analysis_family": "resonance_fit",
  "selection": {
    "trace_ids": ["trace_001"],
    "result_handles": [],
    "collection_key": null
  },
  "parameters": {},
  "output_target": {
    "mode": "existing_design",
    "design_id": "design_001"
  }
}
```

`AnalysisRequestV1` is a product request. The workbench must not build `RunnerTaskEnvelopeV1`, manifest locators, or staging paths.
The canonical `analysis_family` values are defined in [Analysis Family Registry](../../../reference/architecture/product-async-contracts.md#analysis-family-registry).

## UI States

| State | Meaning |
| --- | --- |
| `empty` | no dataset/design context selected |
| `selecting_traces` | user is selecting traces, result handles, or collection projection |
| `selection_invalid` | Backend cannot derive a valid analysis collection from the selection |
| `ready_to_submit` | AnalysisRequestV1 can be submitted |
| `submitting` | submit mutation is in flight |
| `attached_task_waiting` | task exists but is waiting/preparing |
| `attached_task_running` | Julia Runner is executing the analysis |
| `publishing` | Backend is validating/publishing Runner output |
| `completed` | ResultView bootstrap is available |
| `failed` | task or publication failed |
| `cancelled` | task was cancelled |
| `result_unavailable` | task exists but no published ResultView is available |

## Request Behavior

- Workbench sends `AnalysisRequestV1`, not `RunnerTaskEnvelopeV1`.
- Workbench receives `task_id` from the Backend and uses the Task / Execution Center or a stage-local panel for status.
- Workbench opens ResultView only after Backend publication.
- Workbench may reuse shared task/result components.
- Workbench must not duplicate task lifecycle authority.
- Workbench must not directly mutate full arrays or publish TraceStore records.

## Related

* [Application Interface](../../application-interface.md)
* [Frontend Reference](../index.md)
* [Task Management](../shared-workflow/task-management.md)
* [Datasets & Results](../../backend/datasets-results.mdx)
* [Product Async Contracts](../../../reference/architecture/product-async-contracts.md)
* [ResultView API](../../backend/result-view-api.md)
* [Simulation Interface Boundaries](../../../reference/architecture/simulation-interface-boundaries.md)
