---
aliases:
  - Julia Core Component Libraries
  - Component Library Boundary
tags:
  - diataxis/reference
  - audience/contributor
  - sot/true
  - topic/julia-core
status: stable
owner: docs-team
audience: contributor
scope: Defines the boundary between Julia Core Kernel and user/lab/project component libraries.
version: v1.1.0
last_updated: 2026-05-28
updated_by: codex
---

# Component Libraries

A Component Library is a user-space, lab-space, or project-space collection of reusable circuit components built on top of Julia Core.

Julia Core provides the authoring kernel. Component Libraries provide concrete components.

## Boundary

| Layer | Owns |
| --- | --- |
| Julia Core Kernel | `CircuitPlan`, `Endpoint`, Relation, Validation, Compiler, `JosephsonCompiledCircuit`, simulation / sweep interfaces |
| Component Library | concrete components, component-specific parameters, component-specific validation, reusable plan builders |
| Pluto Notebook | interactive use of Julia Core and selected component libraries |
| Julia Runner | deterministic execution of Julia Core and selected component libraries |

## Dependency Direction

```text
Component Library
        depends on
Julia Core Kernel
```

Component Library depends on Julia Core Kernel.

Julia Core must not depend on user/lab/project component libraries.

## Examples

A lab component library may define:

```text
GroundedLCResonatorComponent
FloatingLCResonatorComponent
QuarterWaveResonatorComponent
ReadoutLineComponent
CPWFluxLineComponent
SQUID
SNAIL
JPA
PurcellFilterComponent
```

These are not mandatory Julia Core members.

## Plan Builders

Component libraries may expose reusable plan builders:

```julia
build_grounded_lc_to_qwr_plan(params)

build_floating_lc_series_plan(params)

build_qwr_readout_with_shunt_plan(params)
```

These builders should return `CircuitPlan` objects and should use Julia Core endpoints, relations, validation, compiler, and simulation interfaces.

## Parameter Role Declarations

Component Libraries should declare default parameter roles for the parameters they introduce.

Examples:

| Component-library parameter | Default role |
| --- | --- |
| capacitance value | `NumericParameter` |
| inductance value | `NumericParameter` |
| line length | `StructuralParameter` if it changes line segmentation, node map, or emitted rows |
| section count | `StructuralParameter` |
| boundary choice | `StructuralParameter` |
| junction critical current | `NumericParameter` if junction topology is unchanged |
| SQUID external flux | `NumericParameter` or `DriveParameter` if topology is unchanged |

These declared roles are inputs to the sweep engine. The compiler / sweep engine still validates effective roles through topology-key consistency.

## Pluto Usage

Pluto notebooks may load one or more component libraries:

```julia
using SuperconductingCircuitsCore
using MyLabComponents

plan = build_grounded_lc_to_qwr_plan(params)

compiled = compile_to_josephson(plan)
result = run_frequency_sweep(compiled, freqs)
```

Pluto should not require component libraries to become part of Julia Core.

## Runner Usage

The Runner may execute tasks using selected component libraries, but those libraries remain dependencies of the Runner task environment, not part of Julia Core itself.

Runner adapters must not create a separate circuit construction model.
