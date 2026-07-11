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

Read the SCQ_Design [Ideal Parallel LC Resonator](https://github.com/arfiligol/SCQ_Design/blob/main/docs/knowledge/network-modeling/ideal-parallel-lc-resonator.qmd)
node before interpreting the traces. It separates the ideal component from the
compiled port network and its wave observable.

## Goal

Run through a grounded LC resonator notebook and verify that you can:

- Load local Julia Core packages from Pluto.
- Create inspectable `CircuitPlan` / `EngineeringGraph` / `HBProblemSpec`.
- Execute real JosephsonCircuits solver path.
- See actual S/Y trace figures and inspect the raw Z trace used to derive Y.

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
- circuit diagram cell shows the ideal grounded LC component view; the compiled
  summary separately exposes the port row and resistor.
- `CircuitPlan`, `EngineeringGraph`, `HBIntent`, `HBProblemSpec` related cells can all produce named objects.
- solver cell complete, not placeholder output.
- raw and verified-PTC Y traces plus S11 magnitude/phase are displayed as
  Visualizer figures.

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

The useful success signal is not only "the notebook opens". You should see real
S11 and admittance traces produced from the solver path, not placeholder
curves. The notebook's analytic arrays are acceptance checks and are not plotted
as substitute solver data.

## Why This Comes First

Pluto is the direct research cockpit:

- It may call Julia Core directly.
- It may use the Visualizer for PlotlyJS figures.
- It keeps the first success path inside an explicit notebook research kernel.
- It shows the reusable circuit model before any product surface is involved.

## Next Step

- [Reusable Circuit Design](reusable-circuit-design.md) - understand how component libraries, plan builders, `CircuitPlan`, schematic intent, and simulation fit together.
- [Pluto Examples](../workflows/reusable-circuit-authoring/pluto-examples.mdx) - continue the numbered notebook learning path.
- [SCQ_Design Port-Termination Compensation](https://github.com/arfiligol/SCQ_Design/blob/main/docs/knowledge/simulation/port-termination-compensation.qmd) - understand why this example may remove the proven `R_port` shunt for an intrinsic comparison.
