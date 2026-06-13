---
aliases:
 - First Pluto Notebook
 - First Pluto Notebook
tags:
 - diataxis/how-to
 - status/stable
 - topic/getting-started
sidebar:
 label: First Pluto Notebook
 order: 30
---

# First Pluto Notebook

Confirm that the research portal is available with `notebooks/pluto/00_parallel_lc_resonator.jl`. This path calls Julia Core directly from Pluto without starting any production runtime first.

## Goal

Run through a grounded LC resonator notebook and verify that you can:

- Load local Julia Core packages from Pluto.
- Create inspectable `CircuitPlan` / `EngineeringGraph` / `HBProblemSpec`.
- Execute real JosephsonCircuits solver path.
- See actual S/Z/Y trace figures with Visualizer.

## Fresh Checkout Path

Complete [Installation](installation.md) first. Then start Julia from the repo root:

```bash
julia --startup-file=no --project=@v1.12
```

Start Pluto in the Julia REPL:

```julia
using Pluto
Pluto.run()
```

After Pluto opens the browser, select:

```text
notebooks/pluto/00_parallel_lc_resonator.jl
```

## Run The Notebook

When started for the first time, Pluto will parse the notebook environment and local packages. Please let all cells complete and then acknowledge these signals:

- package import cell successfully loaded `SuperconductingCircuitsCore` and `SuperconductingCircuitsVisualizer`.
- circuit diagram cell shows grounded LC resonator.
- `CircuitPlan`, `EngineeringGraph`, `HBIntent`, `HBProblemSpec` related cells can all produce named objects.
- solver cell complete, not placeholder output.
- S/Z/Y traces are displayed as Visualizer figures.

## What To Inspect

The first notebook should show the same research contract used by later examples:

```text
local teaching fixture or reusable builder
  -> CircuitPlan
  -> EngineeringGraph
  -> HBIntent / HBProblemSpec
  -> run_hb_problem
  -> real extracted output families
  -> Visualizer figures
```

The useful success signal is not only "the notebook opens". You should see real S11 / impedance-style traces produced from the solver path, not placeholder curves.

## Why This Comes First

Pluto is the direct research cockpit:

- It may call Julia Core directly.
- It may use the Visualizer for PlotlyJS figures.
- It keeps the first success path inside an explicit notebook research kernel.
- It shows the reusable circuit model before any product surface is involved.

## Next Step

- [Reusable Circuit Design](reusable-circuit-design.md) - understand how component libraries, plan builders, `CircuitPlan`, schematic intent, and simulation fit together.
- [Pluto Examples](../workflows/pluto/pluto-examples.mdx) - continue the numbered notebook learning path.
