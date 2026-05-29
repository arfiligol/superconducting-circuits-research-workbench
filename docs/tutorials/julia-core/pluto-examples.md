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
scope: Pluto example workflow for Julia Core HB simulation intent, S-parameter extraction, and full requested-output-family inspection.
version: v0.1.0
last_updated: 2026-05-29
updated_by: codex
---

# Pluto Examples

Use these Pluto examples as the Julia Core learning path for harmonic-balance simulation intent, executable HB problem construction, and result-family inspection. The examples are notebook-first: Pluto calls Julia Core directly, while Backend task submission, persistence, publication, and display remain upper-layer responsibilities.

!!! warning "Implementation status"
    This page lists the current and target notebook set. `notebooks/pluto/hb_simulation_intent_ux.jl`, `notebooks/pluto/01_grounded_lc_reflection.jl`, and `notebooks/pluto/02_pump_off_resonator_s11.jl` are present in this checkout as of 2026-05-29. The remaining notebook titles are target titles with no source notebook yet, and must not be described as working examples until their source notebooks exist.

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

## Target Notebook Set

| Notebook | Goal | Teaches | Inspect | Current implementation status |
| --- | --- | --- | --- | --- |
| 00 HB Simulation Intent Tutorial | Walk through the end-to-end HB intent path with a small local grounded-resonator component. | CircuitPlan authoring, EngineeringGraph inspection, HBIntent declarations, pump-off/pumped runtime bindings, HBProblemSpec normalization, and the executable `run_hb_problem` gate. | `graph.components`, `graph.ports`, `graph.relations`, `graph.hb_overlay`, `compiled.netlist`, `compiled.port_map`, `hb_report`, `hb_problem.sources`, `output_request_report`, and `result`. | Implemented as `notebooks/pluto/hb_simulation_intent_ux.jl`. Its title is currently `HB Simulation Intent Tutorial`; the numbered title is the target learning-path label. |
| 01 Grounded LC Reflection | Show the smallest grounded LC reflection problem before adding pump semantics. | One-port resonator authoring, external-port lowering, frequency-sweep setup, and baseline reflection interpretation. | `example.graph.components`, `example.graph.ports`, `example.graph.relations`, `example.compiled.netlist`, `keys(result.traces)`, `zero_mode_s(result, 1, 1)`, and `zero_mode_z(result, 1, 1)`. | Present as `notebooks/pluto/01_grounded_lc_reflection.jl`; it uses `notebooks/pluto/includes/hb_example_helpers.jl` and plots real `HBSolveResult` S/Z traces. |
| 02 Pump-Off Resonator S11 | Demonstrate a declared pump problem with the pump source intentionally off. | `pump_current = 0.0` as a valid source-off binding, finite positive pump-frequency binding, source-slot identity, and S11 extraction from solver output. | `PumpAxis`, `HBSourceSlot(:pump_in)`, `source_currents[:pump_in]`, `hb_problem.wp`, `hb_problem.sources`, output request validation, `keys(result.traces)`, and S11 traces. | Present as `notebooks/pluto/02_pump_off_resonator_s11.jl`; it requests the default output families and plots real `HBSolveResult` S11 data. |
| 03 Pumped JPA-style S11 | Move from pump-off to a pumped JPA-style S11 example without hiding mode, source, or control semantics. | Pumped source bindings, harmonic controls, three-wave/four-wave mixing flags where applicable, and interpreting gain from solver output. | Source modes, pump modes, `HBSolverControls`, optional HB kwargs, requested output families, and solver-returned S11 values. | Target notebook; no matching source notebook exists in `notebooks/pluto/` as of 2026-05-29. |
| 04 Two-Port S-Parameters | Extend the inspection path from one-port S11 to a two-port S-parameter matrix. | Multiple external ports, mode/port labels, matrix-shaped S/Z extraction, and port-index provenance. | `compiled.port_map`, observable requests for S11/S21/S12/S22, `traces[:s_parameter_mode]`, `traces[:z_parameter_mode]`, and mode-port labels. | Target notebook; no matching source notebook exists in `notebooks/pluto/` as of 2026-05-29. |
| 05 Output Families QE/CM | Make the full requested-output-family contract visible in Pluto. | S/Z/QE/QEideal/CM extraction, clear failure for missing requested families, allowed absence for unrequested families, and preservation of solver-returned `NaN`. | `traces[:s_parameter_mode]`, `traces[:z_parameter_mode]`, `traces[:qe_mode]`, `traces[:qeideal_mode]`, `traces[:cm_mode]`, missing-family errors, and `NaN` values. | Target notebook; Core extractor tests cover the policy, but no matching Pluto notebook exists in `notebooks/pluto/` as of 2026-05-29. |

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
