---
aliases:
  - Julia Scientific Core
tags:
  - diataxis/reference
  - audience/team
  - sot/true
  - topic/core-reference
status: draft
owner: docs-team
audience: team
scope: Phase 1 Julia scientific core 與 Pluto Notebook research workflow。
version: v0.1.0
last_updated: 2026-05-28
updated_by: codex
---

# Julia Scientific Core

Phase 1 的核心方向是 Julia Core + Pluto Notebook 快速研究工作流。這不是 Application / Backend / Storage 大修。

## Julia Core Direction

The Julia Core is the canonical scientific execution surface for reusable superconducting-circuit construction and JosephsonCircuits.jl simulation.

Pluto Notebook may directly call the Julia Core for fast research iteration. This is the preferred Phase-1 workflow.

Application / Backend integration is deferred to a later phase. When implemented, the Application must call the same Julia Core instead of reimplementing circuit construction, lowering, or sweep logic in Python.

## Canonical Package

| Item | Current Canonical Surface |
|---|---|
| Julia package | `core/julia/SuperconductingCircuitsCore/` |
| Package entrypoint | `core/julia/SuperconductingCircuitsCore/src/SuperconductingCircuitsCore.jl` |
| Reusable components | `src/components/` |
| Circuit draft / lowering | `src/draft/` |
| Simulation and sweeps | `src/simulation/` |
| Plain Julia examples | `core/julia/SuperconductingCircuitsCore/examples/` |
| Pluto notebooks | `notebooks/pluto/` |

Use from Julia REPL or Pluto:

```julia
using Pkg
Pkg.activate("core/julia/SuperconductingCircuitsCore")

using SuperconductingCircuitsCore
```

Run tests:

```bash
julia --project=core/julia/SuperconductingCircuitsCore -e 'using Pkg; Pkg.test()'
```

Run a plain example:

```bash
julia --project=core/julia/SuperconductingCircuitsCore core/julia/SuperconductingCircuitsCore/examples/sweep_demo.jl
```

## Research Workflow

```text
Pluto Notebook
    -> direct Julia call
Julia Core
    -> reusable components / circuit draft
JosephsonCircuits.jl netlist
    -> simulation / sweep
Result object / table / plot-ready data
```

Pluto notebooks must stay thin. They may define parameters, build designs through the public Julia Core API, run a simulation or sweep, and inspect results. They must not duplicate reusable component definitions, lowering logic, coupled-window compiler logic, or result extraction core logic.

## Ownership Rules

| Rule | Meaning |
|---|---|
| Julia owns scientific construction | Components, symbolic pins, draft graph, coupled-window placement, distributed TL discretization, lowering, simulation wrappers, and sweeps live in Julia Core. |
| Delayed lowering stays required | Author high-level drafts first; call `finalize_to_josephson_netlist` only at the end. Do not patch already-flat JosephsonCircuits netlists in place. |
| Python/backend does not own lowering | Later productized workflows should call Julia Core instead of reimplementing construction or sweep logic in Python. |
| Application is deferred | Backend/frontend integration is not a Phase-1 implementation target. |

## Future Storage Direction

This is a planning note only; storage is not implemented in Phase 1.

| Mode | Metadata DB | TraceStore / ArtifactStore |
|---|---|---|
| Local Mode / Notebook / single-user research | SQLite | local filesystem or S3-compatible storage |
| Online Mode / multi-user / server | PostgreSQL | S3-compatible storage |

## Related

- [Core Reference](index.md)
- [Julia Core](julia-core.md)
- [Julia Wrapper](julia-wrapper.md)
