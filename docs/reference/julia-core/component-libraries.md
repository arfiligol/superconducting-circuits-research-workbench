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
scope: Defines the candidate boundary between the Julia Core reusable component catalog and user/lab/project component libraries.
version: v1.5.0
last_updated: 2026-07-28
updated_by: codex
---

# Component Libraries

A Component Library is a user-space, lab-space, or project-space collection of
reusable circuit components and complete plan builders built on top of Julia
Core.

Julia Core provides both the authoring kernel and a bounded catalog of stable
reusable components. Being concrete does not by itself place a component
outside Core.

## Candidate Ownership Boundary

| Layer | Owns |
| --- | --- |
| Julia Core Kernel | `CircuitPlan`, `Endpoint`, Relation, Validation, Compiler, `JosephsonCompiledCircuit`, simulation / sweep interfaces |
| Julia Core Reusable Component Catalog | stable local topologies that are composed into larger circuit topologies, with public endpoints and parameters |
| Component Library | reusable components intentionally kept in user, lab, process, device-family, or project space, plus their local validation |
| Project Plan Builder | complete research circuits, external ports, measurement or simulation intent, study targets, and project-owned parameter policies |
| Pluto Notebook | interactive use of Julia Core and selected component libraries |
| Julia Runner | deterministic execution of Julia Core and selected component libraries |

A reusable component may enter the Julia Core catalog when all of the following
hold:

- it represents a local circuit topology that is used as a component by a
  larger topology;
- it exposes stable public endpoints and parameters while keeping internal
  nodes private;
- it does not own one study's complete circuit;
- it is implemented from Julia Core primitives without depending on a
  user/lab/project package.

This is an eligibility rule, not a requirement to move every qualifying
component into Core. Lab or process variants may remain in an external
Component Library.

A function that assembles a complete project circuit and returns its
`CircuitPlan` is a Project Plan Builder, not a Julia Core reusable component.
Its feedlines, ports, targets, sweep policy, and simulation intent remain owned
by the project.

| Candidate | Owner |
| --- | --- |
| endpoint, relation, compiler, or sweep contract | Julia Core Kernel |
| stable filter, resonator, coupler, qubit subcircuit, or other local topology embedded in a larger circuit | eligible for the Julia Core Reusable Component Catalog |
| process-calibrated or lab/device-family variant used inside a larger topology | eligible for the Julia Core catalog; may remain in its external Component Library |
| complete research circuit with ports, targets, and study policy | Project Plan Builder |
| exploratory one-off topology | Pluto notebook until its reusable boundary is clear |
| compiled netlist fragment | never a reusable component; compile the complete `CircuitPlan` |

`IntrinsicInterferometricPurcellFilter` is a Core-catalog example: it owns a
local filter topology and stable attachment endpoints, but it does not own the
enclosing feedline, external ports, or research circuit. A project composes it
into a larger `CircuitPlan`.

## Dependency Direction

```text
Component Library
    depends on
Julia Core Kernel
```

Component Library depends on Julia Core Kernel.

Julia Core, including its reusable component catalog, must not depend on
user/lab/project component libraries.

## Examples

A lab component library may define project- or process-specific variants such
as:

```text
FoundryXQuarterWaveResonator
LabYReadoutLine
DeviceFamilySQUIDArray
ProcessCalibratedSNAIL
StudySpecificPurcellFilter
```

Generic local topologies such as grounded or floating resonators, couplers,
quarter- or half-wave resonators, and intrinsic filter subcircuits may instead
qualify for the Core catalog. Do not add a component merely as a convenience
example; use the candidate ownership criteria above.

## Tutorial Notebook Fixtures

Tutorial notebooks may define small local reusable components when they need an executable acceptance harness for the Core API.

| Fixture scope | Allowed | Not allowed |
| --- | --- | --- |
| Notebook tutorial | minimal local component that exercises pins, ports, EngineeringGraph, or HB intent | lab catalog, production device library, or hidden alternate construction model |
| Julia Core tests | tiny deterministic fixture component | complete project circuit presented as a Core reusable component |
| Component library | reusable lab/project components and plan builders | dependence from Julia Core back into the library |

The fixture should keep the notebook readable: Markdown, tables, and small callouts should carry the tutorial explanation; renderer or plotting dependencies should be optional unless the notebook is explicitly testing that renderer.

HB tutorial fixtures should use the product profiles `:pump_off`, `:pumped`, and `:pumped_dc`. Pump-off keeps the pump axis and pump source slot in the local fixture and binds `pump_current = 0.0`; it should not switch to a separate empty-pump construction path.

## Plan Builders

Component libraries and projects may expose plan builders:

```julia
build_grounded_lc_to_qwr_plan(params)

build_floating_lc_series_plan(params)

build_qwr_readout_with_shunt_plan(params)
```

These builders should return `CircuitPlan` objects and should use Julia Core endpoints, relations, validation, compiler, and simulation interfaces.

Plan builders that own a complete research circuit remain outside the Julia
Core reusable component catalog. A Core reusable component instead adds its
local topology to a caller-owned plan through stable endpoints and parameters.

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

Plan Builders should use Julia Core physical relation helpers when they connect reusable components. Those helpers update the Circuit Plan and record the standard EngineeringGraph relation in the same operation:

```julia
couple_capacitive!(
  plan;
  id = "feedline_to_resonator",
  from = pin(feedline,:output),
  to = pin(resonator,:input),
  capacitance = Cc,
  role =:readout_coupling,
)
```

Do not duplicate standard `connect!`, `couple_capacitive!`, `shunt_capacitor!`, `shunt_inductor!`, `couple_inductive!`, or `couple_transmission_window!` calls with a manual `record_engineering_relation!`. Use manual recording only for extra semantic annotations or overlays that are not already captured by the physical operation.

The same metadata should be available whether the plan was authored with the Macro DSL or ordinary functional calls.

## Plan Builder Parameter Metadata

Component Libraries may expose project Plan Builders.

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
- pump and DC source slots, including `HBSourceSlot(role =:dc_bias, mode = (0,))` where DC bias exists;
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

## Semantic Status

- Scope: ownership boundary between the Julia Core reusable component catalog,
  external Component Libraries, and project-owned complete `CircuitPlan`
  builders.
- Prior evidence: the v1.4 page was marked stable and treated all concrete
  components as external-library assets, but this ownership scope has no
  separate explicit Human-acceptance record.
- Current state: `STABILIZED` V1.
- State changed: 2026-07-28.
- Human acceptance: explicitly accepted the named V1 ownership scope.
- Test policy: `stabilization_tests_authorized`; existing docs validation
  covers this documentation-only scope.
- Excluded: moving existing components, defining project-specific circuit
  ownership, and changing D3 artifacts.
- Unresolved decisions: none.
