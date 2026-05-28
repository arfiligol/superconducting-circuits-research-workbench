---
aliases:
  - Runner-Safe Julia Core API
  - Pluto Runner Shared API
tags:
  - diataxis/reference
  - audience/contributor
  - sot/true
  - topic/julia-core
status: stable
owner: docs-team
audience: contributor
scope: Runner-safe Julia Core API boundaries shared by Pluto direct research and Julia Runner execution.
version: v1.3.0
last_updated: 2026-05-28
updated_by: codex
---

# Runner-Safe API

Pluto and Julia Runner are two callers of the same Core API. The Core pipeline should be deterministic, framework-agnostic, and safe to run from an interactive notebook or a task runner process.

Pluto should not require a special compute path. Runner execution should call the same component builders, Circuit Plan validation, compiler, simulation helpers, and analysis helpers.

## Shared Pipeline

```text
                    Julia Core Pipeline
          Component -> Plan -> Compiler -> Simulation
                  ^                         ^
                  |                         |
          Pluto Notebook              Julia Runner
```

## Caller Roles

| Caller | Role |
| --- | --- |
| Pluto | interactive design, sliders, plots, local inspection |
| Julia Runner | task input, deterministic build, compile, simulate, staged output |

The caller may provide different inputs and output handling, but it should not redefine component construction or compiler semantics.

Runner execution calls Julia Core for deterministic task execution. It does not own a separate circuit construction model.

## Boundary Rules

| Boundary | Rule |
| --- | --- |
| Julia Core | owns circuit authoring, compiler concepts, simulation helpers, and analysis helpers |
| Pluto | direct Julia Core research surface |
| Julia Runner | calls Julia Core for deterministic task execution and writes staged numeric output |
| Python Backend | owns task lifecycle, metadata, publication, and TraceStore |
| Application / Electron | owns product UI and desktop process supervision |

Julia Core must not depend on FastAPI, Next.js, Electron, or Backend task state.

The Runner owns execution orchestration and staged output, not authoring semantics. Circuit construction, endpoint resolution, compiler semantics, and simulation result extraction belong to Julia Core.

Large numeric arrays should not move through HTTP JSON. Runner outputs should use staged local filesystem packages, with Backend publication handling canonical TraceStore records.

## Runner Component Library Dependencies

The Runner may execute tasks that depend on one or more component libraries.

Those component libraries are task/runtime dependencies, not Julia Core Kernel members.

The Runner must call Julia Core through the documented authoring path:

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

The Runner must not copy component-library logic into a separate Runner-only construction path.

## API Shape

A Runner-safe flow should be expressible with plain Julia calls:

```julia
plan = CircuitPlan(id = task_input.design_id)

lc = add_grounded_lc_resonator_component!(
    plan;
    id = "lc",
    capacitance = Capacitor(task_input.capacitance),
    inductive_element = LinearInductor(task_input.inductance),
)

validate_authoring(plan)

compiled = compile_to_josephson(plan)

result = run_frequency_sweep(compiled, task_input.frequency_range_hz)
```

The Runner adapter may map task payloads into this flow, but the mapping layer should stay outside the Core authoring model.

## Unsupported Shortcuts

Do not add a second circuit builder inside the Runner adapter.

Do not add Runner-only component construction.

Do not preserve old Core APIs as Runner fallback paths.

Do not bypass the Circuit Plan, Endpoint, Relation, Compiler, or `JosephsonCompiledCircuit` model in Runner code.

If a task needs a new circuit shape, add or update the reusable Julia Core component, endpoint, relation, or compiler path, then let both Pluto and Runner call it.
