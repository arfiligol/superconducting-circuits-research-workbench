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
version: v1.3.2
last_updated: 2026-05-29
updated_by: codex
---

# Component Libraries

A Component Library is a user-space, lab-space, or project-space collection of reusable circuit components built on top of Julia Core.

Julia Core provides the authoring kernel. Component Libraries provide concrete components.

## Boundary

| Layer | Owns |
| --- | --- |
| Julia Core Kernel | `CircuitPlan`, `Endpoint`, Relation, Validation, Compiler, `JosephsonCompiledCircuit`, simulation / sweep interfaces |
| Component Library | concrete components, component-specific parameters, engineering roles, schematic export hints, component-specific validation, reusable plan builders |
| Pluto Notebook | interactive use of Julia Core and selected component libraries |
| Julia Runner | deterministic execution of Julia Core and selected component libraries |

Julia Core does not ship lab-specific components. It defines the kernel contracts that let user, lab, and project libraries provide those components.

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

They also should not be added to Julia Core as convenience examples. Put concrete component families in a component library, a test fixture module, or a tutorial notebook cell with an explicit local-fixture label.

## Tutorial Notebook Fixtures

Tutorial notebooks may define small local reusable components when they need an executable acceptance harness for the Core API.

| Fixture scope | Allowed | Not allowed |
| --- | --- | --- |
| Notebook tutorial | minimal local component that exercises pins, ports, EngineeringGraph, or HB intent | lab catalog, production device library, or hidden alternate construction model |
| Julia Core tests | tiny deterministic fixture component | project-specific resonator or qubit family as a Core export |
| Component library | reusable lab/project components and plan builders | dependence from Julia Core back into the library |

The fixture should keep the notebook readable: Markdown, tables, and small callouts should carry the tutorial explanation; renderer or plotting dependencies should be optional unless the notebook is explicitly testing that renderer.

HB tutorial fixtures should use the product profiles `:pump_off`, `:pumped`, and `:pumped_dc`. Pump-off keeps the pump axis and pump source slot in the local fixture and binds `pump_current = 0.0`; it should not switch to a separate empty-pump construction path.

## Plan Builders

Component libraries may expose reusable plan builders:

```julia
build_grounded_lc_to_qwr_plan(params)

build_floating_lc_series_plan(params)

build_qwr_readout_with_shunt_plan(params)
```

These builders should return `CircuitPlan` objects and should use Julia Core endpoints, relations, validation, compiler, and simulation interfaces.

## EngineeringGraph Metadata

Component Libraries should provide the component-level information that Julia Core records into [`EngineeringGraph`](engineering-graph.md):

```text
- stable component ID;
- display name;
- reusable component type;
- engineering role;
- user-facing parameters with default units;
- named pins and anchors;
- schematic kind and optional render hints;
- source provenance when available.
```

These records are for human visualization, debugging, reports, and schematic export. They are not JosephsonCircuits.jl rows and should not be inferred from solver netlists.

Plan Builders should also record engineering relations when they connect reusable components:

```julia
record_engineering_relation!(
    plan;
    relation_type = :couple,
    from = pin(feedline, :output),
    to = pin(resonator, :input),
    through = CapacitiveCoupler(capacitance = Cc),
    role = :readout_coupling,
)
```

The same metadata should be available whether the plan was authored with the Macro DSL or ordinary functional calls.

## Plan Builder Parameter Metadata

Component Libraries may expose reusable Plan Builders.

Plan Builders should declare high-level user-facing knobs and preserve how those knobs map to component or relation parameters.

Example:

```julia
build_qwr_readout_plan(params)
```

A Plan Builder should declare metadata such as:

```text
- parameter name;
- default role;
- owner;
- mapped component / relation targets;
- sweep-facing name;
- valid domain;
- units;
- role assumptions;
- whether the parameter may change topology key.
```

This metadata is stored in the CircuitPlan and used by the sweep engine.

For HB-capable plan builders, the component library should also declare the HB intent needed by Runner-safe execution:

- pump-axis IDs and their frequency-parameter names;
- pump and DC source slots, including `HBSourceSlot(role = :dc_bias, mode = (0,))` where DC bias exists;
- observable requests for S/Z/QE/QEideal/CM extraction;
- default `HBSolverControls` suitable for the circuit family.

Runtime values still arrive through `HBRunSpec`. A component library should not hide pump-off behavior by emitting a different plan without the pump source slot.

## Parameter Role Declarations

Component Libraries should declare default parameter roles for component-owned parameters and for high-level Plan Builder knobs.

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
hb_problem = build_hb_problem(compiled, run_spec)
result = run_hb_problem(hb_problem)
```

Pluto should not require component libraries to become part of Julia Core.

## Runner Usage

The Runner may execute tasks using selected component libraries, but those libraries remain dependencies of the Runner task environment, not part of Julia Core itself.

Runner adapters must not create a separate circuit construction model.
