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
version: v1.8.0
last_updated: 2026-05-29
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

Runner receives a RunSpec and binds it to a compiled HB intent. Runner must not invent ports, source slots, pump axes, mode tuples, observable requests, or solver-output semantics.

Runner also must not invent EngineeringGraph semantics. Component identity, engineering roles, relation types, port roles, source slots, observable requests, groups, and schematic export hints come from CircuitPlan authoring and selected Component Libraries.

Large numeric arrays should not move through HTTP JSON. Runner outputs should use staged local filesystem packages, with Backend publication handling canonical TraceStore records.

## HB Simulation Boundary

HB solver inputs are not owned by the Runner.

The shared contract is:

```text
CircuitPlan
        |
        v
HBIntent: ports, pump axes, source slots, observables
        |
        v
compile_to_josephson
        |
        v
JosephsonCompiledCircuit with validated HB metadata
        |
        v
Runner binds runtime values and executes
```

`current = 0.0` is a valid runtime binding for an existing source slot. It means the source is intentionally off. It is not fake compute, a missing source, or dummy behavior.

The Runner may reject malformed runtime bindings, unknown solver controls, or unsupported observables. It must not repair them by creating new ports or source slots outside the compiled intent.

Runner must reject:

- unknown source slot ID;
- unknown pump axis ID;
- unknown observable ID;
- unknown `optional_hb_kwargs`;
- runtime values that do not satisfy compiled HB validation metadata.

Runner must not create a default S11 observable, create default ports, create source slots from task payloads, or convert ambiguous drive-magnitude fields into physical current.

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
EngineeringGraph
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

When Runner needs a report, preview, or schematic export, it should call Julia Core APIs such as:

```julia
graph = engineering_graph(plan)
spec = to_schemdraw_spec(graph)
```

Those APIs return renderer-neutral data. A Python Schemdraw renderer may consume the export later, but Julia Core and Runner should not depend on Schemdraw.

## Runner Sweep Execution

Runner sweep tasks should call the Julia Core sweep engine.

Runner sweep tasks use Julia Core sweep planning and execution.

Runner adapters may map Backend payloads into:

```text
Component Library plan builder
SweepSpec
CompilePolicy
Executor
AccelerationPolicy
```

But the Runner must not implement its own sweep classification, topology-key grouping, compile cache, or executor semantics.

The Runner may choose task-level scheduling, staging, cancellation checks, and result publication boundaries, but it must not implement its own parameter classification, topology grouping, compile-cache semantics, or sweep result schema.

The Runner should preserve the `SweepExecutionPlan` and `SweepResult` provenance generated by Julia Core.

## API Shape

A Runner-safe flow should be expressible with plain Julia calls.

The Runner task environment may load selected component libraries, but the authoring path still goes through Julia Core.

```julia
using SuperconductingCircuitsCore
using MyLabComponents

plan = build_plan(task_input.design_parameters)

validate_authoring(plan)

compiled = compile_to_josephson(plan)

result = run_frequency_sweep(compiled, task_input.frequency_range_hz)
```

For parameter sweeps:

```julia
sweep = build_sweep_spec(task_input.sweep)

preflight = preflight_sweep(build_plan, sweep)

result = run_parameter_sweep(build_plan, sweep)
```

The Runner adapter may map Backend payloads into component-library plan builders, `SweepSpec`, `CompilePolicy`, `Executor`, and `AccelerationPolicy`, but the mapping layer must stay outside the Core authoring model.

## Unsupported Shortcuts

Do not add a second circuit builder inside the Runner adapter.

Do not add Runner-only component construction.

Do not preserve old Core APIs as Runner alternate paths.

Do not bypass the Circuit Plan, Endpoint, Relation, Compiler, or `JosephsonCompiledCircuit` model in Runner code.

Do not reconstruct component-level schematic meaning from target netlist rows.

If a task needs a new circuit shape, add or update the reusable Julia Core component, endpoint, relation, or compiler path, then let both Pluto and Runner call it.
