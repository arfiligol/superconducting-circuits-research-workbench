---
title: "Circuit Simulation Workbench"
aliases:
  - "Circuit Simulation UI"
tags:
  - diataxis/reference
  - audience/team
  - sot/true
  - topic/app-reference
status: stable
owner: docs-team
audience: team
scope: productized Application Simulation Workbench contract
version: v1.3.0
last_updated: 2026-05-28
updated_by: codex
---

# Circuit Simulation Workbench

Circuit Simulation Workbench is the productized application surface for simulation requests. It does not run heavy compute in the frontend or Backend request thread.

## Execution Contract

```text
Application Simulation Workbench
    -> Python Backend SimulationRequestV1
    -> persisted Task
    -> Julia Runner
    -> local Zarr staging
    -> Backend publication
    -> TraceStore / Result View
```

The workbench builds product-grade simulation requests, submits them to the Backend, monitors task state, and renders published results through the shared task/result surfaces.

See [Product Async Contracts](../../../architecture/product-async-contracts.md) for the product request, `SimulationRequestV1` minimum shape, Runner envelope, manifest, and result-view contract.

## Boundary

- Direct Julia experimentation belongs in Pluto notebooks.
- Python notebooks may directly inspect data files and use Backend contracts when platform metadata, task submission, or result registration is needed.
- Application code must submit async tasks and render published data.
- Large numeric arrays must stay in local filesystem Zarr stores.

## Responsibilities

Simulation Workbench owns:

- simulation request form
- dataset/design target selection
- circuit/design source selection
- solver/request configuration
- output request selection
- submit
- task attachment and recovery
- stage-local progress context
- ResultView bootstrap
- result rendering

It must not own:

- heavy compute
- Backend task lifecycle
- Runner runtime
- TraceStore publication
- direct full Zarr reading

## Authoring Sections

| Section | Purpose |
| --- | --- |
| Dataset / Design target | select existing `dataset_id + design_id` or create-new target intent |
| Circuit / Design source selection | choose source document, schema, or saved design asset |
| Frequency sweep setup | define start/stop/count/spacing and units |
| Optional parameter sweep setup | define sweep axes and value domains without embedding dense result arrays |
| Output request setup | choose requested traces, summaries, and default ResultView |
| Solver / engine settings | configure small control values for the Backend request |
| Submit / validation summary | show request readiness and Backend validation errors |
| Attached task status | show waiting/running/publishing state through shared task components |
| ResultView panel | bootstrap and render published results |
| Error / recovery panel | expose retry, attach, cancellation, and publication failure recovery |

## UI States

| State | Meaning |
| --- | --- |
| `empty` | no dataset/design/source context selected |
| `draft` | user is editing request fields |
| `validating` | Backend or local schema validation is running |
| `ready_to_submit` | SimulationRequestV1 can be submitted |
| `submitting` | submit mutation is in flight |
| `attached_task_waiting` | task exists but is waiting/preparing |
| `attached_task_running` | Julia Runner is executing the task |
| `publishing` | Backend is validating/publishing Runner output |
| `completed` | ResultView bootstrap is available |
| `failed` | task or publication failed |
| `cancelled` | task was cancelled |
| `result_unavailable` | task exists but no published ResultView is available |

## Request Behavior

- Workbench sends `SimulationRequestV1`, not `RunnerTaskEnvelopeV1`.
- The canonical minimum request shape is defined in [SimulationRequestV1 Minimum Shape](../../../architecture/product-async-contracts.md#simulationrequestv1-minimum-shape).
- Workbench receives `task_id` from the Backend and uses the Task / Execution Center or a stage-local panel for status.
- Workbench opens ResultView only after Backend publication.
- Workbench may reuse shared task/result components.
- Workbench must not duplicate task lifecycle authority.
- Workbench must not read canonical Zarr directly; product rendering goes through ResultView API.

## Related

* [Application Interface](../../application-interface.md)
* [Simulation Interface Boundaries](../../../architecture/simulation-interface-boundaries.md)
* [Product Async Contracts](../../../architecture/product-async-contracts.md)
* [ResultView API](../../backend/result-view-api.md)
* [Julia Runner Compute Plane](../../../architecture/julia-runner-compute-plane.md)
* [TraceStore Zarr](../../../architecture/trace-store-zarr.md)
