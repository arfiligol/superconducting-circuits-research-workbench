---
aliases:
 - "JosephsonCircuits Response Path"
 - "Simulation Guide"
tags:
 - diataxis/how-to
 - status/stable
 - topic/simulation
status: stable
owner: docs-team
audience: user
scope: "Solver-facing response path and direct Julia debugging workflow for Julia Core and JosephsonCircuits.jl."
version: v0.3.0
last_updated: 2026-06-14
updated_by: codex
sidebar:
 label: JosephsonCircuits Response Path
 order: 35
---

# JosephsonCircuits Response Path

Use this page when the notebook path already built a valid circuit and you need to inspect the solver-facing response path. The default workflow stays Pluto-first: build reusable Julia Core plans, compile them, run JosephsonCircuits.jl through Julia Core helpers, then inspect real response families.

## Normal Path

The preferred research route keeps reusable semantics above raw solver rows:

```text
Component library builder
  -> CircuitPlan
  -> validate_authoring
  -> compile_to_josephson
  -> HBProblemSpec
  -> run_hb_problem
  -> extracted S, Z, Y, QE, QEideal, or CM families
```

Use Pluto to keep the build, compile, solve, and plot cells visible. Package code should own reusable helpers, not notebook-only glue.

## Direct Julia Debugging

Use a native Julia REPL or script only when you need a small solver-facing check, a package-development debug loop, or a comparison against Julia Core compilation output.

```bash
cd superconducting-circuits-research-workbench
julia --project=core/julia/SuperconductingCircuitsCore
```

Load only the packages needed for the check:

```julia
using JosephsonCircuits
using JosephsonCircuits: @variables
```

Define units and symbolic parameters explicitly:

```julia
nH = 1e-9
pF = 1e-12
GHz = 1e9

@variables L C R50
```

Use raw JosephsonCircuits rows only for debugging or solver comparison, not as the primary teaching path:

```julia
circuit = [
  ("P1", "1", "0", 1),
  ("R50", "1", "0", R50),
  ("L", "1", "2", L),
  ("C", "2", "0", C),
]

circuitdefs = Dict(
  L => 10nH,
  C => 1pF,
  R50 => 50.0,
)
```

Run a small response solve:

```julia
frequencies = range(0.1GHz, 5GHz, length = 100)
ws = 2π .* frequencies
wp = (2π * 5GHz,)
sources = [(mode = (1,), port = 1, current = 0.0)]

sol = hbsolve(ws, wp, sources, (10,), (20,), circuit, circuitdefs)
```

Extract the response you are comparing:

```julia
S11 = sol.linearized.S(
  outputmode = (0,),
  outputport = 1,
  inputmode = (0,),
  inputport = 1,
  freqindex = :,
)

S11_mag = abs.(S11)
S11_phase = angle.(S11)
```

## When To Drop Below Julia Core

| Use direct JosephsonCircuits rows when | Stay in Julia Core when |
| --- | --- |
| checking whether a solver behavior is independent of Julia Core compilation | teaching reusable circuit authoring |
| comparing compiled rows against a minimal hand-written circuit | building component libraries or plan builders |
| debugging `hbsolve` controls, source slots, or extracted S/Z/Y fields | producing notebook examples or reusable package APIs |

## Related

- [Authoring Workflow](pluto-authoring-workflow.mdx)
- [Parameter Sweep Workflow](pluto-parameter-sweep-workflow.mdx)
- [Pluto Examples](pluto-examples.mdx)
- [Notebook Interface](../../reference/notebooks/index.md)
- [Core Reference](../../reference/core/index.md)
