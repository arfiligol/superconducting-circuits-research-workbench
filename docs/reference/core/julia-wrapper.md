---
aliases:
  - Julia Compute Reference
tags:
  - diataxis/reference
  - audience/team
  - sot/true
  - topic/core-reference
status: stable
owner: docs-team
audience: team
scope: Julia Core and Julia Runner compute boundary。
version: v0.5.3
last_updated: 2026-05-28
updated_by: codex
---

# Julia Compute Boundary

Julia compute now has two active packages:
Julia Core holds the docs-defined authoring model, Circuit Plan, compiler concepts, parameter sweep architecture, compile policies, executor interfaces, simulation helpers, sweep helpers, and analysis logic.
Julia Runner wraps that logic as asynchronous task execution and writes local staging artifacts.

Concrete component libraries are dependencies selected by the caller, notebook, or Runner task environment. They are not part of the Julia Core Kernel contract.

## Active Packages

| Package | Path | Responsibility |
|---|---|---|
| SuperconductingCircuitsCore | `core/julia/SuperconductingCircuitsCore/` | docs-defined authoring model, Circuit Plan, compiler concepts, parameter sweep architecture, compile policies, executor interfaces, simulation helpers, sweep engine, analysis helpers |
| SuperconductingCircuitsRunner | `core/julia/SuperconductingCircuitsRunner/` | backend polling, task dispatch, local Zarr staging writer, manifest generation, complete/fail reporting |

## Boundary

Python Backend does not run heavy simulation in-process.
It creates tasks, validates runner output, publishes official TraceStore data, and records provenance.

Julia Runner does not write formal metadata tables.
It writes:

```text
data/staging/tasks/<task_id>/
├── manifest.json
├── result.zarr/
└── logs/
```

## Output Contract

Runner result packages must use Zarr v2 and explicit real/imag arrays for complex traces:

```text
/traces/S11/real
/traces/S11/imag
```

The backend validates shape, chunk shape, dtype, axis lengths, manifest paths, and task identity before publishing.

## Related

- [Julia Runner Compute Plane](../architecture/julia-runner-compute-plane.md)
- [Runner Result Manifest](../architecture/runner-result-manifest.md)
- [TraceStore Zarr](../architecture/trace-store-zarr.md)
