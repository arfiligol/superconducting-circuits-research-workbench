---
aliases:
  - Pluto Examples
  - Julia Core Pluto Examples
  - Pluto Example Workflow
tags:
  - diataxis/tutorial
  - audience/user
  - sot/true
  - topic/julia-core
  - topic/pluto
status: stable
owner: docs-team
audience: user
scope: Seven-notebook Pluto learning path for Julia Core authoring, visualizer figures, circuit diagrams, and real HBSolveResult inspection.
version: v0.4.0
last_updated: 2026-05-30
updated_by: codex
---

# Pluto Examples

Use these Pluto examples as the Julia Core learning path for circuit authoring, harmonic-balance simulation intent, executable HB problem construction, and result-family inspection. The notebooks are research-first: Pluto calls Julia Core directly, while Backend task submission, persistence, publication, and official TraceStore display remain upper-layer responsibilities.

!!! info "Learning path"
    The canonical learning path is exactly seven notebooks, numbered `00` through `06`.
    Each number has one notebook and one teaching responsibility.

## Workflow Contract

Each notebook keeps the same inspectable path:

```text
local teaching fixture or reusable component-library builder
    -> CircuitPlan
    -> EngineeringGraph
    -> HBIntent
    -> compile_to_josephson
    -> HBProblemSpec
    -> run_hb_problem
    -> extract requested output families
```

Pluto is the direct Julia research cockpit. It can build, inspect, solve, and plot local research results. It should not submit Backend tasks or become the publication layer for official TraceStore data.

## Learning Path

| Notebook | Circuit diagram | Teaching responsibility | Main inspection surface |
| --- | --- | --- | --- |
| `00` Parallel LC resonator | ![Parallel LC resonator](../../assets/pluto-00-parallel-lc-resonator.svg) | Ground the reader in a one-port resonator, declared pump-off source slots, `HBProblemSpec`, and reflection output. | S11 magnitude/phase, Z11/Y11 real/imag, extracted QE/QEideal/CM records when requested |
| `01` Reflective JPA, capacitively coupled LC | ![Reflective JPA capacitively coupled LC](../../assets/pluto-01-reflective-jpa-capacitive-coupled-lc.svg) | Show a reflective amplifier-style LC tank where the readout port couples through `C_c` and pump semantics stay explicit. | Port/source maps, pump-off versus pumped bindings, S/Z trace families |
| `02` Floating LC with XY line | ![Floating LC with XY line](../../assets/pluto-02-floating-lc-xy-line.svg) | Teach floating-node conventions, XY drive coupling, endpoint naming, and component pins before compilation. | EngineeringGraph components, public pins, source-slot overlays, S/Z traces |
| `03` Transmission-line circuit model | ![Transmission-line circuit model](../../assets/pluto-03-transmission-line-circuit-model.svg) | Introduce `RLGCSpec`, head/tail orientation, section indexing, generated ladder elements, and open/short terminations. | Ladder nodes, section values, compiled rows, S21/S11 and impedance traces |
| `04` Readout line with Purcell filter | ![Readout line with Purcell filter](../../assets/pluto-04-readout-line-purcell-filter.svg) | Model a readout path through a point-capacitively coupled half-wave Purcell filter. | Filter endpoints, coupling capacitors, S21/S11, impedance traces |
| `05` Readout line with hanging QWR MTL window | ![Readout line with hanging QWR MTL window](../../assets/pluto-05-readout-line-hanging-qwr-mtl.svg) | Replace point coupling with a finite distributed MTL coupled window between a readout line and a hanging quarter-wave resonator. | Coupled section ranges, C12/K12 rows, notch response, reflection |
| `06` Readout, Purcell filter, and hanging QWR MTL window | ![Readout, Purcell filter, and hanging QWR MTL window](../../assets/pluto-06-readout-purcell-hanging-qwr-mtl.svg) | Combine the readout filter and distributed hanging-QWR model so readers inspect composition without changing construction paths. | End-to-end plan graph, combined S21/S11 behavior, requested output-family extraction |

??? quote "Schemdraw Source Code"
    ```python
    # Source file: scripts/docs/generate_pluto_notebook_diagrams.py
    outputs = [
        ("pluto-00-parallel-lc-resonator.svg", draw_parallel_lc_resonator),
        (
            "pluto-01-reflective-jpa-capacitive-coupled-lc.svg",
            draw_reflective_jpa_capacitive_coupled_lc,
        ),
        ("pluto-02-floating-lc-xy-line.svg", draw_floating_lc_xy_line),
        ("pluto-03-transmission-line-circuit-model.svg", draw_transmission_line_circuit_model),
        ("pluto-04-readout-line-purcell-filter.svg", draw_readout_line_purcell_filter),
        ("pluto-05-readout-line-hanging-qwr-mtl.svg", draw_readout_line_hanging_qwr_mtl),
        (
            "pluto-06-readout-purcell-hanging-qwr-mtl.svg",
            draw_readout_purcell_hanging_qwr_mtl,
        ),
    ]
    ```

## PlotlyJS And WideCell

Pluto notebooks use `SuperconductingCircuitsVisualizer` to create `PlotlyJS.jl` static interactive figures. `Plots.jl` is outside the Pluto example plotting contract.

Plot construction belongs to `SuperconductingCircuitsVisualizer`. Julia Core and Julia Runner do not depend on PlotlyJS; Core owns circuit authoring, compilation, `HBProblemSpec`, solver execution, and trace extraction, while Runner owns async task execution and staged result packages.

Use `WideCell` for PlotlyJS figures, dense tables, and circuit previews that need horizontal room. `WideCell` is a Pluto presentation helper, not a computation contract; Julia Core, Julia Runner, and trace extraction APIs must stay independent of it.

## Schemdraw And LaTeX

Circuit diagrams for this learning path are Schemdraw-generated SVG files stored under `docs/assets/`. The diagrams are documentation assets and teaching aids; notebook acceptance depends on renderer-neutral `EngineeringGraph` and schematic-export data, not on a Python Schemdraw runtime inside Julia Core or Julia Runner.

Use LaTeX for equations, resonance estimates, coupling definitions, and axis labels where mathematical notation improves clarity. Define symbols near their first use, keep units explicit, and keep formulas searchable as text instead of replacing them with image-only equations.

## Real Trace Policy

Every PlotlyJS figure must read from real `HBSolveResult` traces produced by `run_hb_problem(hb_problem)` or an equivalent Julia Core execution path. Figures must fail clearly when a requested trace family, port label, or mode label is absent; they must not substitute analytic, sample, or fabricated curves.

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

## Common Format

Each numbered notebook includes these seven elements:

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

## Component-Builder Teaching Policy

Teach reusable circuit structure through component-library builders or explicitly local tutorial fixtures.

| Rule | Meaning |
| --- | --- |
| Julia Core is the kernel | Core owns `CircuitPlan`, endpoints, relations, validation, compiler concepts, simulation helpers, analysis helpers, and canonical reusable generators that express Core modeling conventions. |
| Component libraries own family variants | Lab-specific device families and process-specific variants are user-space, lab-space, or project-space components built on top of Core. |
| Tutorial fixtures stay local | A notebook may define a small local fixture when it makes the Core path readable, but that fixture is not evidence that Julia Core ships a lab catalog. |
| Builders return inspectable plans | A reusable builder exposes the plan, EngineeringGraph, compiler output, and HB problem needed for notebook inspection. The notebook owns the explicit `run_hb_problem(hb_problem)` call and trace extraction cells. |
| No raw-row teaching path | Do not teach users to hand-author JosephsonCircuits rows as the primary workflow when a component, relation, ladder, or coupled-window helper owns the convention. |

For transmission-line and coupled-window examples, use `RLGCSpec`, `build_lc_ladder_line!`, point coupling helpers, and `couple_transmission_window!` instead of copying ladder or MTL conventions into each notebook.

## Notebook Authoring Rules

Keep each example small enough that a reader can inspect every boundary.

1. Start with the canonical Julia Core path, not legacy construction helpers.
2. Keep tutorial fixtures local unless a real reusable component library owns the circuit family.
3. Show validation and compiler output before solver output.
4. Treat pump-off as a declared source slot with `current = 0.0`, not as a removed source.
5. Request output families explicitly and inspect extraction results after solving.
6. Do not replace a failing solver call with substitute curves or fabricated `NaN` values.
7. Teach physical conventions before code: ladder nodes, CPW head/tail, open/short terminations, coupling-window start distance, coupling length, and coupled-section parameters.
8. Use Julia Core APIs for transmission-line ladders and MTL coupled windows. Do not hand-code those conventions in each notebook.
9. Use `SuperconductingCircuitsVisualizer` for PlotlyJS figures. Do not reintroduce `Plots.jl` in Pluto examples.
10. Use `WideCell` for wide figures and dense previews; keep ordinary explanatory cells at normal Pluto width.

!!! tip "Acceptance gate"
    A notebook that claims to be executable should end with the real Julia Core solver/extraction path. For HB examples, the critical gate is `result = run_hb_problem(hb_problem)` followed by extraction of the requested output families.

## Related

- [HB Simulation Intent](../../reference/julia-core/hb-simulation-intent.md)
- [Circuit Plan](../../reference/julia-core/circuit-plan.md)
- [Component Libraries](../../reference/julia-core/component-libraries.md)
- [Engineering Graph](../../reference/julia-core/engineering-graph.md)
- [Transmission Line Ladder](../../reference/julia-core/transmission-line-ladder.md)
- [Coupling Models](../../reference/julia-core/coupling-models.md)
- [Julia Visualizer PlotlyJS Figures](../../reference/julia-visualizer/plotlyjs-figures.md)
- [JosephsonCircuits hbsolve Controls](../../reference/julia-core/josephsoncircuits-hbsolve-controls.md)
- [Runner-Safe API](../../reference/julia-core/runner-safe-api.md)
- [Pluto Authoring Workflow](../../how-to/pluto/authoring-workflow.md)
