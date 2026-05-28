---
aliases:
  - Pluto Authoring Workflow
  - Pluto Julia Core Authoring
tags:
  - diataxis/how-to
  - status/stable
  - topic/julia-core
  - topic/pluto
status: stable
owner: docs-team
audience: user
scope: Pluto workflow for Julia Core CircuitPlan authoring, inspection, compilation, and single-point simulation.
version: v1.1.0
last_updated: 2026-05-28
updated_by: codex
---

# Pluto Authoring Workflow

Use this workflow when you want Pluto to act as a direct Julia Core research surface. The notebook should build one `CircuitPlan`, inspect it, compile it, and run a single simulation path before you move to an explicit batch sweep.

## Goal

Build and inspect a circuit through the Julia Core authoring model:

```text
Component Library plan builder
        |
        v
CircuitPlan
        |
        v
Validation
        |
        v
Compiler
        |
        v
JosephsonCompiledCircuit
        |
        v
Simulation / Analysis
```

Pluto should not use a separate construction path, and it should not submit Backend tasks as its normal authoring role.

## Cell Layout

Use a layout that makes each boundary inspectable:

1. Load Julia Core and selected Component Libraries.
2. Define units, frequencies, and single-point parameter values.
3. Define or import `build_plan(params)`.
4. Build one `CircuitPlan`.
5. Inspect components, endpoints, relations, and parameter metadata.
6. Validate authoring state.
7. Compile to `JosephsonCompiledCircuit`.
8. Inspect compiler maps, warnings, and topology key.
9. Run one frequency sweep.
10. Plot or summarize the result.

## Single-Point Workflow

Keep reactive cells small and bounded:

```julia
using SuperconductingCircuitsCore
using MyLabComponents

params = (
    qwr_length_mm = 5.0,
    coupling_fF = 3.0,
    flux_phi0 = 0.1,
)
```

Build one plan:

```julia
plan = build_plan(params)
validate_authoring(plan)
```

Inspect before compiling:

!!! note "Target inspection helpers"
    The helper names in this page describe the target Pluto-facing inspection API.
    If current implementation names differ, implementation work should align toward these helpers instead of preserving old names as compatibility aliases.

```julia
inspect_plan(plan)
inspect_parameters(plan)
inspect_endpoints(plan)
```

Compile and run one point:

```julia
compiled = compile_to_josephson(plan)
inspect_topology_key(compiled)

result = run_frequency_sweep(compiled, freqs)
```

## Debugging From Pluto

Use diagnostics when validation or compilation fails and you need structured fields instead of message text:

```julia
diagnose_plan(plan)
diagnose_compile(plan)
debug_bundle(plan; compiled = compiled)
```

`diagnose_plan` should point to authoring, endpoint, relation, and parameter metadata issues. `diagnose_compile` should report compile-readiness and topology-key context. `debug_bundle` collects plan summaries, diagnostics, topology explanation, and compiled output summaries in a Pluto-safe form.

## Before Batch Sweeps

Move from this page to [Pluto Parameter Sweep Workflow](parameter-sweep-workflow.md) when you need many parameter points.

Batch sweeps should be explicit. A Pluto slider update should rebuild and simulate one point, not launch a large hidden sweep.

## Related

- [Pluto Parameter Sweep Workflow](parameter-sweep-workflow.md)
- [Julia Core Authoring Model](../../reference/julia-core/authoring-model.md)
- [Circuit Plan](../../reference/julia-core/circuit-plan.md)
- [Debugging and Diagnostics](../../reference/julia-core/debugging-and-diagnostics.md)
