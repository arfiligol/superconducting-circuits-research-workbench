---
aliases:
  - Julia Visualizer
  - SuperconductingCircuitsVisualizer
tags:
  - diataxis/reference
  - audience/contributor
  - sot/true
  - topic/julia-visualizer
  - topic/julia-core
  - topic/pluto
status: stable
owner: docs-team
audience: contributor
scope: Julia visualization package boundary for Pluto-facing PlotlyJS figures built from Julia Core HBSolveResult traces.
version: v1.0.0
last_updated: 2026-05-30
updated_by: codex
---

# Julia Visualizer

`SuperconductingCircuitsVisualizer` owns Julia-side figure construction for Pluto research notebooks. It turns real `HBSolveResult` traces from Julia Core into static interactive `PlotlyJS.jl` figures while keeping solver execution, Runner staging, Backend publication, and app display contracts outside the plotting package.

## Page Map

<div class="grid cards" markdown>

- __[PlotlyJS Figures](plotlyjs-figures.md)__

    ---

    Define the PlotlyJS figure contract, trace input rules, dependency boundary, and notebook usage policy.

</div>

## Ownership

| Surface | Owns |
| --- | --- |
| `SuperconductingCircuitsVisualizer` | PlotlyJS figure configuration, trace-to-figure mapping, labels, axes, hover text, and Pluto-displayable figure objects |
| `SuperconductingCircuitsCore` | Circuit authoring, compilation, `HBProblemSpec`, JosephsonCircuits execution, trace extraction, and `HBSolveResult` |
| `SuperconductingCircuitsRunner` | Async task claiming, deterministic execution, local Zarr staging, manifest writing, and completion reporting |
| Pluto notebooks | Research narrative, parameter choices, solver invocation through Julia Core, and display of visualizer figures |
| Python Backend and Application | Persisted task lifecycle, official TraceStore publication, bounded result-view APIs, and product UI rendering |

## Boundary

`SuperconductingCircuitsVisualizer` may depend on `PlotlyJS.jl` and on Julia Core result types. Julia Core and Julia Runner must not depend on `PlotlyJS.jl` or on the visualizer package.

The visualizer does not submit Backend tasks, publish TraceStore data, mutate manifests, or call the solver. It receives result data from Julia Core and produces figures for local research inspection.

## Related

- [PlotlyJS Figures](plotlyjs-figures.md)
- [Julia Core](../julia-core/index.md)
- [Runner-Safe API](../julia-core/runner-safe-api.md)
- [Julia Runner Compute Plane](../architecture/julia-runner-compute-plane.md)
