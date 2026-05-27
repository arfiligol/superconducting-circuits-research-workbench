---
aliases:
  - Backend App Reference
tags:
  - diataxis/reference
  - audience/team
  - sot/true
  - topic/app-reference
status: stable
owner: docs-team
audience: team
scope: Python Backend control/data plane authority surfaces
version: v1.0.0
last_updated: 2026-05-28
updated_by: codex
---

# Backend Reference

The Python Backend owns the control plane and data plane. It does not own heavy simulation execution.

## Surface Map

| Surface | Primary consumers | Core focus |
|---|---|---|
| [Session & Workspace](session-workspace.md) | Header, app shell, notebooks | runtime mode, session, workspace, active dataset, capabilities |
| [Datasets & Results](datasets-results.md) | Dashboard, Dataset, Raw Data, Tasks, notebooks | dataset/design/trace metadata, trace preview, result handles |
| [Tasks & Execution](tasks-execution.md) | Tasks page, Header, Julia Runner | task lifecycle, runner API, completion publication |
| [Circuit Definitions](circuit-definitions.md) | Design Assets, Schema Editor, notebooks | source/design metadata |
| [Audit Logs](audit-logs.md) | governance and diagnostics | append-only audit query |

## Runtime Boundary

| Concern | Owner |
|---|---|
| task row creation and state transitions | Python Backend |
| runner claim/heartbeat/progress/complete/fail API | Python Backend |
| simulation, sweep, fitting, derived extraction | Julia Runner |
| Zarr staging package validation | Python Backend |
| canonical TraceStore publication | Python Backend |

## Not Backend Runtime

The backend must not run JosephsonCircuits through JuliaCall as an app execution path, start Redis/RQ workers, or own active CLI/NiceGUI surfaces.

## Related

* [Application Interface](../application-interface.md)
* [Frontend Reference](../frontend/index.md)
* [Julia Runner Compute Plane](../../architecture/julia-runner-compute-plane.md)
