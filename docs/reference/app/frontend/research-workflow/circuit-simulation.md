---
title: "Circuit Simulation Workbench Removed"
aliases:
  - "Circuit Simulation UI"
tags:
  - diataxis/reference
  - audience/team
  - topic/removed-surface
status: archived
owner: docs-team
audience: team
scope: tombstone for the removed app simulation workbench
version: v1.0.0
last_updated: 2026-05-28
updated_by: codex
---

# Circuit Simulation Workbench Removed

The application no longer exposes a full Circuit Simulation Workbench.

Current path:

```text
App / Notebook -> Python Backend task -> Julia Runner -> staging Zarr -> Backend publish -> TraceStore
```

Use the Tasks / Result Browser for submitted work, Pluto for direct Julia research execution, and Design Assets for source/design documents.

## Related

* [Application Interface](../../application-interface.md)
* [Julia Runner Compute Plane](../../../architecture/julia-runner-compute-plane.md)
* [TraceStore Zarr](../../../architecture/trace-store-zarr.md)
