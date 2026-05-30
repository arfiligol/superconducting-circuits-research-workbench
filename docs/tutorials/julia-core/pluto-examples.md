---
aliases:
  - Pluto Examples
  - Julia Core Pluto Examples
  - Pluto Example Workflow
tags:
  - diataxis/tutorial
  - audience/user
  - topic/julia-core
  - topic/pluto
status: incubating
owner: docs-team
audience: user
scope: Pluto example workflow for Julia Core HB simulation intent, transmission-line ladders, coupling models, and real HBSolveResult plotting.
version: v0.3.0
last_updated: 2026-05-30
updated_by: codex
---

# Pluto Examples

Use these Pluto examples as the Julia Core learning path for harmonic-balance simulation intent, executable HB problem construction, and result-family inspection. The examples are notebook-first: Pluto calls Julia Core directly, while Backend task submission, persistence, publication, and display remain upper-layer responsibilities.

!!! info "Learning path"
    The canonical learning-path notebooks for the coupling-model milestone are numbered `00` through `04` under `notebooks/pluto/`.
    Supplemental notebooks must be named by their modeling convention, especially when they use point capacitive coupling instead of a finite MTL coupled window.

## Workflow Contract

Each notebook should keep the same inspectable path:

```text
local component library or reusable plan builder
    -> CircuitPlan
    -> EngineeringGraph
    -> HBIntent
    -> compile_to_josephson
    -> HBProblemSpec
    -> run_hb_problem
    -> extract requested output families
```

Pluto is the direct Julia research cockpit. It can build, inspect, solve, and plot local research results. It should not submit Backend tasks or become the publication layer for official TraceStore data.

## Plotting Policy

Pluto notebooks use `SuperconductingCircuitsVisualizer` to create `PlotlyJS.jl` static interactive figures. `Plots.jl` is outside the Pluto example plotting contract.

Plot construction belongs to `SuperconductingCircuitsVisualizer`. Julia Core and Julia Runner do not depend on PlotlyJS; Core owns circuit authoring, compilation, `HBProblemSpec`, solver execution, and trace extraction, while Runner owns async task execution and staged result packages.

Every figure must read from real `HBSolveResult` traces produced by `run_hb_problem(hb_problem)` or an equivalent Julia Core execution path. Figures must fail clearly when a requested trace family or label is absent; they must not substitute analytic, sample, or fabricated curves.

## Output Extraction Policy

Julia Core owns full requested-output extraction. If a notebook requests S, Z, QE, QEideal, or CM, Julia Core should extract the full requested family from the solver result.

| Rule | Meaning |
| --- | --- |
| Full family extraction | Julia Core extracts the requested family, not only one displayed trace. |
| Upper-layer filtering | Apps, notebooks, and persistence layers choose which traces to filter, store, or display. |
| Missing requested family | The extractor fails clearly and names the missing family. |
| Missing unrequested family | The family remains absent. Julia Core does not fabricate placeholder data. |
| Solver-returned `NaN` | `NaN` values returned by the solver are preserved and surfaced as solver output. |
| Fabricated `NaN` | Julia Core must not create `NaN` placeholders for missing requested families. |

This keeps solver availability, extraction, persistence, and display as separate decisions.

Full extraction can grow large for multi-mode or multi-port simulations. Storage, artifact-writing, and reporting layers may choose not to persist every extracted trace, but that persistence policy sits outside Julia Core.

## Notebook Set

| Notebook | Goal | Main output |
| --- | --- | --- |
| `00_hb_simulation_intent_tutorial.jl` | Minimal grounded LC resonator / reflection workflow. | S11 magnitude/phase, Z11 real/imag |
| `01_cpw_lc_ladder.jl` | CPW / transmission line as an LC ladder with head/tail and section conventions. | S21/S11 magnitude/phase, Z11/Z21 when available |
| `02_readout_line_purcell_filter_point_coupled.jl` | Readout input/output capacitively coupled to a half-wave Purcell filter. | S21/S11 and impedance traces |
| `03_long_readout_line_baseline.jl` | Long CPW readout-line baseline before adding a hanging QWR. | S21 phase delay, S11 mismatch, Z behavior |
| `04_readout_line_hanging_qwr_mtl.jl` | Readout CPW + grounded quarter-wave resonator with a finite MTL coupled window. | S21 notch, S11 reflection, coupling-window inspection |

Supplemental notebooks may remain useful, but their scope must be named honestly. For example, `04_coupling_sweep.jl` is a point-coupled readout-resonator sweep, not a finite-length MTL coupled-window model.

## Common Format

Each numbered notebook should include these seven elements:

| Requirement | Example surface |
| --- | --- |
| Understandable system code | Local component or local plan builder, not raw netlist rows only |
| Julia Core authoring path | `@circuit`, `CircuitPlan`, Core relations, `EngineeringGraph` |
| Compiled representation | `compiled.netlist`, `compiled.port_map`, `compiled.component_values` |
| HB problem representation | `hb_problem.frequencies_hz`, `wp`, `sources`, `Nmodulationharmonics`, `Npumpharmonics` |
| Real solver execution | `result = run_hb_problem(hb_problem)` or an equivalent helper that calls it |
| Real result visualization | SuperconductingCircuitsVisualizer figures read from real `HBSolveResult` traces |
| Physics sanity check | A short "What should I expect?" section |

The coupling-model notebooks expand the seven elements into a complete tutorial contract:

```text
1. What is this system?
2. What physics should I expect?
3. What assumptions are used?
4. What parameters are used?
5. How does Julia Core describe this circuit?
6. What does the compiled solver representation look like?
7. What does the real solver output show?
```

## Notebook Authoring Rules

Keep each example small enough that a reader can inspect every boundary.

1. Start with the current active Julia Core path, not legacy construction helpers.
2. Keep component-library examples local to the notebook unless a real reusable component library exists.
3. Show validation and compiler output before solver output.
4. Treat pump-off as a declared source slot with `current = 0.0`, not as a removed source.
5. Request output families explicitly and inspect extraction results after solving.
6. Do not replace a failing solver call with substitute curves or fabricated `NaN` values.
7. Teach physical conventions before code: ladder nodes, CPW head/tail, open/short terminations, coupling-window start distance, coupling length, and coupled-section parameters.
8. Use Julia Core APIs for transmission-line ladders and MTL coupled windows. Do not hand-code those conventions in each notebook.
9. Use `SuperconductingCircuitsVisualizer` for PlotlyJS figures. Do not reintroduce `Plots.jl` in Pluto examples.

!!! tip "Acceptance gate"
    A notebook that claims to be executable should end with the real Julia Core solver/extraction path. For HB examples, the critical gate is `result = run_hb_problem(hb_problem)` followed by extraction of the requested output families.

## Related

- [HB Simulation Intent](../../reference/julia-core/hb-simulation-intent.md)
- [Transmission Line Ladder](../../reference/julia-core/transmission-line-ladder.md)
- [Coupling Models](../../reference/julia-core/coupling-models.md)
- [Julia Visualizer PlotlyJS Figures](../../reference/julia-visualizer/plotlyjs-figures.md)
- [JosephsonCircuits hbsolve Controls](../../reference/julia-core/josephsoncircuits-hbsolve-controls.md)
- [Runner-Safe API](../../reference/julia-core/runner-safe-api.md)
- [Pluto Authoring Workflow](../../how-to/pluto/authoring-workflow.md)
