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
scope: Julia Core scientific API ownership for Pluto direct research and Julia Runner package execution.
version: v1.2.0
last_updated: 2026-05-28
updated_by: codex
---

# Julia Scientific Core

Julia Core is the canonical scientific library for the docs-defined authoring model, compiler concepts, JosephsonCircuits.jl simulation wrappers, parameter sweep interfaces, and Julia-native trace extraction helpers.

Both execution tracks use the same Julia Core APIs:

- Pluto notebooks call Julia Core directly for research-grade exploration.
- Julia Runner calls Julia Core while executing persisted task envelopes for packaged workflows.

Infrastructure layers and Python notebooks do not reimplement circuit construction, lowering, sweep logic, or simulation analysis owned by Julia Core. Declared Python fitting algorithms, such as complex S21 notch/transmission fitting and S21 vector fitting, belong to `core/python/analysis/superconducting_circuits_analysis` and can be reached from Pluto through Julia Analysis Bridge.

Python notebooks may analyze local Zarr, exported data, and CSV/raw files directly. That read-only analysis role does not make them Julia Core simulation owners or publication authorities.

## Canonical Package

| Item | Canonical surface |
|---|---|
| Julia package | `core/julia/SuperconductingCircuitsCore/` |
| Package entrypoint | `core/julia/SuperconductingCircuitsCore/src/SuperconductingCircuitsCore.jl` |
| Low-level line specs and tuple-netlist helpers | `src/components/` |
| Simulation and current sweep helpers | `src/simulation/` |
| Authoring architecture SoT | `docs/reference/julia-core/` |
| Pluto workflow docs | `docs/workflows/reusable-circuit-authoring/` |

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

- [Pluto Authoring Workflow](../../workflows/reusable-circuit-authoring/pluto-authoring-workflow.mdx)
- [Pluto Parameter Sweep Workflow](../../workflows/reusable-circuit-authoring/pluto-parameter-sweep-workflow.mdx)

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

Pluto outputs are research-local by default. Durable publication belongs to the product documentation lane.

## Packaged Execution Track

```text
Julia Runner
  -> Julia Core
  -> local staging + manifest
```

Julia Runner is the packaged execution adapter around Julia Core. It receives task envelopes, executes the relevant Julia Core operations, writes staged result packages, and reports manifest locators.

The publication owner does not run heavy scientific compute in request threads.

## Ownership Rules

| Rule | Meaning |
|---|---|
| Julia owns scientific construction contracts | Component interfaces, endpoints, Circuit Plan state, relation/coupling concepts, compiler concepts, simulation wrappers, sweeps, and analysis helpers live in Julia Core. |
| Delayed lowering stays required | Author a high-level Circuit Plan first; call the compiler only at the end. Do not patch already-flat JosephsonCircuits rows in place. |
| Pluto is direct research execution | Pluto may call Julia Core directly and inspect intermediate local data. Pluto is not a persisted task submitter. |
| Runner is packaged execution | Julia Runner calls Julia Core from task envelopes and writes staging packages for later publication. |
| Infrastructure does not own lowering | request/publish layers validate envelopes and publish results; they do not reimplement construction, lowering, sweep, or Julia-owned simulation logic. |
| Python analysis owns declared fitting algorithms | `core/python/analysis/superconducting_circuits_analysis` owns reusable Python fitting algorithms such as complex S21 notch/transmission fitting and S21 vector fitting. |
| Python Notebook is read/inspect only for files | Python notebooks may analyze data files directly, but do not own Julia Core simulation, lowering, publication, or metadata mutation authority. |

## JosephsonCircuits Validation

The wrapper keywords must follow the installed JosephsonCircuits.jl API. When changing wrapper keywords, check the official docs, docstrings, or source first.

Compatibility branches for older keyword sets are not part of the Julia Core contract unless a dedicated owner SoT defines them.

## Storage Boundary

Julia Core returns scientific results to its caller. Storage authority belongs outside Julia Core:

| Caller | Storage responsibility |
|---|---|
| Pluto Notebook | local research outputs, scratch plots, and notebook-owned analysis artifacts |
| Python Notebook | read-only local/exported data-file analysis |
| Julia Runner | local staging Zarr package plus `manifest.json` |
| Publication layer | canonical publication, metadata records, provenance, and result APIs |

## Related

- [Core Reference](index.md)
- [Julia Core Authoring](../julia-core/index.mdx)
- [Julia Core](julia-core.mdx)
- [Julia Wrapper](julia-wrapper.md)
