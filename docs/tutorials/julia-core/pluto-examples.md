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
scope: Pluto example workflow for Julia Core HB simulation intent, S/Z/QE/CM extraction, pump-off semantics, and readout-line examples.
version: v0.2.0
last_updated: 2026-05-29
updated_by: codex
---

# Pluto Examples

Use these Pluto examples as the Julia Core learning path for harmonic-balance simulation intent, executable HB problem construction, and result-family inspection. The examples are notebook-first: Pluto calls Julia Core directly, while Backend task submission, persistence, publication, and display remain upper-layer responsibilities.

!!! info "Notebook status"
    The canonical learning-path notebooks are numbered `00` through `05` under `notebooks/pluto/`.
    Older unnumbered notebook files may remain in the repository during iteration, but this page documents the numbered suite as the official example path.

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

| Notebook | Goal | Main output | Status |
| --- | --- | --- | --- |
| `00_hb_simulation_intent_tutorial.jl` | Minimal end-to-end Julia Core tutorial for local component authoring, EngineeringGraph, HBIntent, compile, HBProblemSpec, and solve. | S11, phase(S11), Z11 | executable |
| `01_grounded_lc_reflection.jl` | Physics-focused one-port grounded LC reflection example with a resonance estimate. | S11 magnitude/phase, Z11 real/imag | executable |
| `02_pump_off_resonator.jl` | Pump-off semantics: pump axis exists, pump frequency exists, pump source exists, source current is `0.0`. | S11 magnitude | executable |
| `03_readout_line_hanging_qwr.jl` | Two-port readout line with a capacitively hanging ladder resonator. | S21/S11, Z11/Z21, derived Y21 | executable MVP |
| `04_coupling_sweep.jl` | Sweep coupling capacitance for the readout-line/hanging-resonator MVP. | S21 and S11 curve families | executable MVP |
| `05_output_families_s_z_qe_cm.jl` | Inspect full requested output families from Julia Core extraction. | S/Z/QE/QEideal/CM keys and representative traces | executable |

## Common Format

Each numbered notebook should include these seven elements:

| Requirement | Example surface |
| --- | --- |
| Understandable system code | Local component or local plan builder, not raw netlist rows only |
| Julia Core authoring path | `@circuit`, `CircuitPlan`, Core relations, `EngineeringGraph` |
| Compiled representation | `compiled.netlist`, `compiled.port_map`, `compiled.component_values` |
| HB problem representation | `hb_problem.frequencies_hz`, `wp`, `sources`, `Nmodulationharmonics`, `Npumpharmonics` |
| Real solver execution | `result = run_hb_problem(hb_problem)` or an equivalent helper that calls it |
| Real result visualization | Plots read from `result.traces` |
| Physics sanity check | A short "What should I expect?" section |

## Notebook Authoring Rules

Keep each example small enough that a reader can inspect every boundary.

1. Start with the current active Julia Core path, not legacy construction helpers.
2. Keep component-library examples local to the notebook unless a real reusable component library exists.
3. Show validation and compiler output before solver output.
4. Treat pump-off as a declared source slot with `current = 0.0`, not as a removed source.
5. Request output families explicitly and inspect extraction results after solving.
6. Do not replace a failing solver call with substitute curves or fabricated `NaN` values.

!!! tip "Acceptance gate"
    A notebook that claims to be executable should end with the real Julia Core solver/extraction path. For HB examples, the critical gate is `result = run_hb_problem(hb_problem)` followed by extraction of the requested output families.

## Related

- [HB Simulation Intent](../../reference/julia-core/hb-simulation-intent.md)
- [JosephsonCircuits hbsolve Controls](../../reference/julia-core/josephsoncircuits-hbsolve-controls.md)
- [Runner-Safe API](../../reference/julia-core/runner-safe-api.md)
- [Pluto Authoring Workflow](../../how-to/pluto/authoring-workflow.md)
