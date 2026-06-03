---
aliases:
  - Julia Scientific Core
tags:
  - diataxis/reference
  - audience/team
  - sot/true
  - topic/core-reference
status: stable
owner: docs-team
audience: team
scope: Julia Core scientific API ownership for Pluto direct research and Julia Runner product execution.
version: v1.2.0
last_updated: 2026-05-28
updated_by: codex
---

# Julia Scientific Core

Julia Core is the canonical scientific library for the docs-defined authoring model, compiler concepts, JosephsonCircuits.jl simulation wrappers, parameter sweep interfaces, and analysis primitives.

Both execution tracks use the same Julia Core APIs:

- Pluto notebooks call Julia Core directly for research-grade exploration.
- Julia Runner calls Julia Core while executing persisted Backend tasks for product workflows.

The Python Backend, Electron Application, and Python notebooks do not reimplement circuit construction, lowering, sweep logic, or simulation analysis owned by Julia Core.

Python notebooks may analyze local Zarr, exported data, CSV/raw files, and canonical TraceStore files directly. That read-only analysis role does not make them Julia Core simulation owners or platform publication authorities.

## Canonical Package

| Item | Canonical surface |
|---|---|
| Julia package | `core/julia/SuperconductingCircuitsCore/` |
| Package entrypoint | `core/julia/SuperconductingCircuitsCore/src/SuperconductingCircuitsCore.jl` |
| Low-level line specs and tuple-netlist helpers | `src/components/` |
| Simulation and current sweep helpers | `src/simulation/` |
| Authoring architecture SoT | `docs/reference/julia-core/` |
| Pluto workflow docs | `docs/how-to/pluto/` |

Use from a user-written Pluto notebook after local dev installation:

```julia
import Pkg
Pkg.activate(joinpath(first(DEPOT_PATH), "environments", "v1.12"); io=devnull)

using Revise
using SuperconductingCircuitsCore
```

Run the local dev installation from the repository root when Pluto or REPL sessions should resolve this checkout through the Julia default environment:

```bash
npm run julia:dev-install
```

`SuperconductingCircuitsVisualizer` remains a separate package. Import it only for PlotlyJS figure construction:

```julia
using SuperconductingCircuitsVisualizer
```

For a Julia REPL session:

```bash
julia --startup-file=no --project=@v1.12
```

```julia
using Revise
using SuperconductingCircuitsCore
using SuperconductingCircuitsVisualizer
pathof(SuperconductingCircuitsCore)
pathof(SuperconductingCircuitsVisualizer)
```

Run tests:

```bash
julia --project=core/julia/SuperconductingCircuitsCore -e 'using Pkg; Pkg.test()'
julia --project=core/julia/SuperconductingCircuitsVisualizer -e 'using Pkg; Pkg.test()'
```

## Notebook Roles

Pluto is still the direct Julia Core research surface, but the old sandbox notebooks that demonstrated the retired draft/finalize flow have been removed. Use the Pluto how-to pages for the target authoring and sweep workflow:

- [Pluto Authoring Workflow](../../how-to/pluto/authoring-workflow.md)
- [Pluto Parameter Sweep Workflow](../../how-to/pluto/parameter-sweep-workflow.md)

## Research Direct Track

```text
Pluto Notebook
    -> direct Julia call
Julia Core
    -> Component Library plan builder / Circuit Plan
Compiler
    -> JosephsonCompiledCircuit
JosephsonCircuits.jl target
    -> simulation / sweep
Result object / table / plot-ready data
```

Pluto notebooks stay thin. They may define parameters, build designs through selected Component Libraries and the public Julia Core API, run a simulation or sweep, and inspect local research outputs. They must not duplicate reusable component definitions, compiler logic, coupled-window lowering logic, or result extraction core logic.

Pluto outputs are research-local by default. Official platform data must enter through an explicit import/publication workflow or through the Product Async Track.

## Product Async Track

```text
Application Simulation Workbench / Python Notebook
    -> Python Backend task
Julia Runner
    -> Julia Core
    -> local Zarr staging + manifest
Python Backend Publisher
    -> TraceStore + metadata records
```

Julia Runner is the product execution adapter around Julia Core. It receives Backend-owned task envelopes, executes the relevant Julia Core operations, writes staged result packages, and reports manifest locators.

Python Backend owns task lifecycle, publication, provenance, TraceStore registration, and result APIs. It does not run heavy scientific compute in request threads.

Python notebooks may submit Backend tasks through this product async path when the result should become platform state. They must not publish TraceStore records directly.

## Ownership Rules

| Rule | Meaning |
|---|---|
| Julia owns scientific construction contracts | Component interfaces, endpoints, Circuit Plan state, relation/coupling concepts, compiler concepts, simulation wrappers, sweeps, and analysis helpers live in Julia Core. |
| Delayed lowering stays required | Author a high-level Circuit Plan first; call the compiler only at the end. Do not patch already-flat JosephsonCircuits rows in place. |
| Pluto is direct research execution | Pluto may call Julia Core directly and inspect intermediate local data. Pluto is not a Backend task submitter. |
| Runner is product execution | Julia Runner calls Julia Core from Backend task envelopes and writes staging packages for Backend publication. |
| Python/backend does not own lowering | Python Backend validates requests and publishes results; it does not reimplement construction, lowering, sweep, fitting, or analysis logic. |
| Python Notebook is read/inspect only for files | Python notebooks may analyze data files directly, but do not own Julia Core simulation, lowering, fitting, platform publication, or metadata mutation authority. |

## JosephsonCircuits Validation

The wrapper keywords must follow the installed JosephsonCircuits.jl API. When changing wrapper keywords, check the official docs, docstrings, or source first.

Compatibility branches for older keyword sets are not part of the Julia Core contract unless a dedicated owner SoT defines them.

## Storage Boundary

Julia Core returns scientific results to its caller. Storage authority belongs outside Julia Core:

| Caller | Storage responsibility |
|---|---|
| Pluto Notebook | local research outputs, scratch plots, and notebook-owned analysis artifacts |
| Python Notebook | read-only local/exported/canonical data-file analysis; platform writes go through Backend contracts |
| Julia Runner | local staging Zarr package plus `manifest.json` |
| Python Backend | canonical TraceStore publication, metadata records, provenance, and result APIs |

## Related

- [Core Reference](index.md)
- [Julia Core Authoring](../julia-core/index.md)
- [Julia Core](julia-core.md)
- [Julia Wrapper](julia-wrapper.md)
- [Julia Runner Compute Plane](../architecture/julia-runner-compute-plane.md)
- [Simulation Interface Boundaries](../architecture/simulation-interface-boundaries.md)
