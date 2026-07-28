---
aliases:
 - Circuit Authoring & Reuse
 - Circuit Workbench Manual
 - Circuit writing and reuse
tags:
 - diataxis/how-to
 - audience/user
 - topic/circuit-authoring
status: stable
owner: docs-team
audience: user
scope: Build reusable circuit topology, complete research plans, export-backed diagrams, and Pluto evidence through one Julia Core authoring path.
version: v1.2.0
last_updated: 2026-07-28
updated_by: codex
title: Circuit Workbench Manual
sidebar:
 label: Overview
 order: 10
---

# Circuit Workbench Manual

Use this manual to turn a research circuit idea into one reusable, inspectable
authoring path. Human researchers and Agents follow the same sequence: decide
what is reusable, build the electrical topology in Julia, validate and compile
the same `CircuitPlan`, export its drawing intent, render SVG documentation,
and use the same builder from Pluto.

```text
Research intent
  -> reusable component or project Plan Builder
  -> CircuitPlan
  -> EngineeringGraph + SchematicLayoutIntent
  -> validation + JosephsonCircuits netlist
  -> schematic_export.json
  -> Schemdraw light/dark SVG
  -> Pluto simulation and research evidence
```

The accepted
[Intrinsic Interferometric Purcell Components](../../reference/julia-core/intrinsic-interferometric-purcell-components.md)
are the current end-to-end example. Use that page for the topology contract;
this manual explains how to create and operate the workflow without copying
that component family into every notebook or diagram script.

## Choose The Authoring Unit

Start from the circuit's role in a larger topology, not from how large its
schematic looks.

| Question | Authoring unit | Owner |
| --- | --- | --- |
| Is this a stable local topology already used as a component inside a larger circuit? | Reusable Component: a typed result plus an `add_...!` builder that inserts its owned topology into a supplied plan | Eligible for the Julia Core reusable catalog; it may remain in an external Component Library when that is the better owner |
| Does this select and connect the complete research circuit, including feedlines, ports, drives, or observables? | Plan Builder returning one concrete `CircuitPlan` | The owning project or Component Library, outside the Julia Core reusable catalog |
| Is the construction still a one-off research probe? | Notebook-local code | Pluto until the reuse boundary is clear |
| Is the repeated work fitting, matrix analysis, or result transformation rather than circuit topology? | Analysis helper | Python Analysis Core or the owning scientific package |

A Reusable Component is not a miniature standalone simulation. It owns a
local topology, public electrical endpoints, parameters, validation, and an
inspectable component record. The enclosing topology supplies everything the
component explicitly excludes.

A Plan Builder owns the complete system choice. It creates a `CircuitPlan`,
instantiates Reusable Components, adds the enclosing connections and ports,
and declares simulation intent. A built `CircuitPlan` is one concrete design
point; it is not the reusable catalog entry.

Use these checks before adding anything to Julia Core:

1. Name the larger topology that already consumes the candidate component.
2. State the component's public endpoints and the topology it owns.
3. State what the enclosing circuit must add.
4. Keep a complete project circuit expressed as a Plan Builder outside the
   Julia Core reusable catalog.

## Follow The Current Lifecycle

Treat each new component, Plan Builder contract, or cross-language export flow
as its own semantic scope.

### While CONVERGING

1. Write the smallest contract that states topology, endpoints, parameters,
   ownership, failure behavior, exclusions, and drawing expectations.
2. Choose the owner and existing file structure.
3. Add a real candidate implementation; do not add placeholder success paths.
4. Inspect the plan, graph, compiled netlist, export, and rendered SVG.
5. Run non-test validation and existing tests only as diagnostic evidence.
6. Present the named candidate and validation evidence for explicit Human
   acceptance.

Do not add, rewrite, or remove durable tests to freeze unsettled semantics.

### After Explicit Acceptance

1. Record the accepted scope in its contract page.
2. Add or update tests derived from that accepted contract.
3. Regenerate committed exports and SVG assets.
4. Run the relevant full validation.
5. Mark the scope stabilized only when documentation, implementation, tests,
   exports, and validation agree.

If a stabilization test exposes a new topology, endpoint, ownership, or
failure decision, return only that affected scope to `CONVERGING`.

## Build The Smallest Complete File Set

Reuse the nearest existing owner. Do not create a new abstraction or folder
when an established component family already owns the behavior.

| Concern | Current repository path |
| --- | --- |
| Reusable topology and typed component result | `core/julia/SuperconductingCircuitsCore/src/components/reusable_components.jl` |
| Public Julia exports | `core/julia/SuperconductingCircuitsCore/src/SuperconductingCircuitsCore.jl` |
| Exportable Core examples and their schematic intent | `core/julia/SuperconductingCircuitsCore/src/examples/pluto_examples.jl` |
| Julia export fixture registry | `scripts/build/export_pluto_schematic_exports.jl` |
| Renderer mapping from exported component type | `core/python/circuit_libraries/schemdraw_circuit_library/rendering/from_schematic_export.py` |
| Reusable Schemdraw visual primitives | `core/python/circuit_libraries/schemdraw_circuit_library/components/` |
| Diagram source, manifest, export, and SVG outputs | `docs/assets/circuit_draw/<topic>/<diagram_id>/` |
| Diagram registry | `docs/assets/circuit_draw/registry.yml` |
| Stable component-family contract | `docs/reference/julia-core/<component-family>.md` |
| Research execution and evidence | `notebooks/pluto/<research-route>/` |

A new Core Reusable Component normally needs:

1. a contract page or an update to the owning component-family contract;
2. a typed component result and one `add_...!` builder;
3. a public export when downstream code must call it;
4. an exportable example only when docs or a reusable drawing needs one;
5. a renderer mapping and reusable visual class only when no existing visual
   projection represents it;
6. stabilization tests only after acceptance.

A project Plan Builder stays in its project or Component Library. It may use
Julia Core components, relations, validation, compilation, and schematic
export, but it should not be added to
`SuperconductingCircuitsCore/src/examples/pluto_examples.jl` merely to make a
project circuit globally visible.

## Implement Electrical Semantics First

For a Reusable Component, follow the established
`add_interdigitated_capacitor!` and
`add_intrinsic_interferometric_purcell_filter!` pattern:

1. accept a supplied `CircuitPlan`;
2. validate IDs, endpoint identity, units, ranges, and ownership before
   stamping topology;
3. create relations through Julia Core helpers such as
   `couple_capacitive!`, `shunt_capacitor!`, `series_inductor!`,
   `transmission_line!`, or `couple_transmission_window!`;
4. call `record_engineering_component!` once for the public component
   identity and its parameters and pins;
5. return a typed value that exposes only the endpoints and child objects an
   enclosing topology needs.

The component must not silently add a feedline, port, solver intent, or
project-specific default unless its contract says those are owned topology.
Do not hand-author JosephsonCircuits rows: the compiler owns that lowering.

A Plan Builder then composes the system:

```julia
function build_research_plan(params)
    plan = CircuitPlan("research-design")

    # Add reusable components to `plan`.
    # Connect their public endpoints and add project-owned ports or intent.

    return plan
end
```

The function name is project-owned. The important contract is that every
consumer receives the same inspectable `CircuitPlan` rather than rebuilding
the topology independently.

## Inspect Before Rendering Or Simulating

Use the plan as the electrical source of truth:

```julia
plan = build_research_plan(params)

authoring_report = validate_authoring(plan)
inspect_plan(plan)
inspect_parameters(plan)
inspect_endpoints(plan)

graph = engineering_graph(plan)
compiled = compile_to_josephson(plan)
inspect_topology_key(compiled)
compiled.netlist
```

Review these boundaries in order:

1. public endpoints match the component contract;
2. `EngineeringGraph` contains the intended component and relation roles;
3. the compiled netlist contains the expected electrical branches;
4. drawing layout does not create or remove electrical connectivity.

Fix a topology mismatch in the Julia builder. Do not patch the JSON or SVG to
make a wrong plan look correct.

## Add Drawing Intent And Export JSON

`EngineeringGraph` answers what the circuit is.
`SchematicLayoutIntent` answers how it should be arranged. Layout intent may
select tracks, coupled spans, terminals, labels, and anchors, but it must not
create electrical relations.

Use the public `schematic!` and layout-recording APIs described in
[Schematic Layout Intent](../../reference/julia-core/schematic-layout-intent.md).
For a Core Reusable Component's export-backed documentation example, keep the
builder and layout intent together in `pluto_examples.jl`. A project Plan
Builder remains in its project owner and supplies its own explicit export
producer. Workbench-owned Core examples and Pluto fixtures register their
builder-to-fixture mapping in
`scripts/build/export_pluto_schematic_exports.jl`.

Generate the Workbench-owned committed JSON fixtures from Julia Core:

```bash
julia --project=core/julia/SuperconductingCircuitsCore \
  scripts/build/export_pluto_schematic_exports.jl
```

Check that committed exports still match their builders:

```bash
julia --project=core/julia/SuperconductingCircuitsCore \
  scripts/build/export_pluto_schematic_exports.jl --check
```

The exported JSON is the cross-language handoff. `draw.py` loads it through
`load_schematic_export()` and calls `add_schematic_export_to_drawing()`. It
must not reconstruct the topology in Python.

## Render The Circuit Diagram

Each export-backed documentation diagram owns:

```text
draw.py
diagram.yml
schematic_export.json
diagram.light.svg
diagram.dark.svg
```

The four legacy direct-Python teaching figures have no
`schematic_export.json`; do not use them as the template for new diagrams.

Add the manifest to `docs/assets/circuit_draw/registry.yml`, then render one
diagram by its manifest `diagram_id`:

```bash
uv run python scripts/build/render_circuit_drawings.py \
  --diagram reusable.intrinsic_interferometric_purcell_filter
```

Verify the full corpus after the targeted preview is correct:

```bash
uv run python scripts/test/check_circuit_drawings.py
uv run python scripts/build/render_circuit_drawings.py --check
```

Use [Contributing Circuit Diagrams](../../contribute/contributing/circuit-diagrams.mdx)
for the manifest, registry, renderer, and SVG review contract. The accepted
Intrinsic Purcell reference shows the bus, public-terminal, physical-node,
marker, and label behavior expected from a reusable visual composition.

## Use The Same Builder In Pluto

Install the local Julia development packages once:

```bash
npm run julia:dev-install
```

Activate the same default environment from Pluto and load Julia Core:

```julia
import Pkg
Pkg.activate(joinpath(first(DEPOT_PATH), "environments", "v1.12"); io=devnull)

using Revise
using SuperconductingCircuitsCore
```

The current reusable Intrinsic Purcell example is directly inspectable:

```julia
example = build_intrinsic_interferometric_purcell_filter_example()
plan = example.plan

validate_authoring(plan)
inspect_plan(plan)
inspect_endpoints(plan)

compiled = compile_to_josephson(plan)
compiled.netlist
schematic_export_data(plan)
```

That example intentionally contains no feedline or external port. A research
notebook that needs a complete simulation should call its project Plan Builder,
which adds the enclosing feedline, ports, runtime parameters, and simulation
intent while reusing the same component.

Keep the notebook thin:

1. load the reusable component library or project Plan Builder;
2. bind one explicit parameter set;
3. build and inspect one plan;
4. compile and inspect the netlist;
5. run the real solver path;
6. plot real returned traces;
7. record inputs, assumptions, diagnostics, artifact paths, and the Human
   decision the evidence is meant to support.

Do not copy component construction into a notebook cell just to make it
editable. Use parameters to vary accepted behavior; return to the owning
builder when topology semantics change.

## Human And Agent Stop Conditions

Stop and surface the decision when:

- it is unclear whether a topology is a reusable local component or a complete
  project circuit;
- public endpoints, units, ownership, failure behavior, or physical meaning
  are unresolved;
- a proposed Core component has no identified larger topology that reuses it;
- the drawing would need Python or Schemdraw to infer electrical connectivity;
- the JSON, rendered topology, and compiled netlist disagree;
- a change requires a new public API, dependency, or cross-repository owner;
- a durable test would need to choose behavior that the Human has not accepted.

Agents may make reversible placement, naming, and file-organization decisions
inside an established contract. Only the Human accepts new topology,
ownership, public-interface, and failure semantics.

## Continue With Focused References

| Need | Reference |
| --- | --- |
| Understand plan ownership and runnable-system boundaries | [Circuit Plan](../../reference/julia-core/circuit-plan.md) |
| Define component composition and public endpoints | [Components And Composition](../../reference/julia-core/components-and-composition.mdx) |
| Define drawing tracks, terminals, labels, and exports | [Schematic Layout Intent](../../reference/julia-core/schematic-layout-intent.md) |
| Inspect the accepted worked component family | [Intrinsic Interferometric Purcell Components](../../reference/julia-core/intrinsic-interferometric-purcell-components.md) |
| Build and inspect a plan interactively | [Pluto Authoring Workflow](pluto-authoring-workflow.mdx) |
| Run a solver-facing response path | [JosephsonCircuits Response Path](josephsoncircuits-simulation.md) |
| Promote repeated notebook work under the lifecycle | [Promote Pluto Prototype To Reusable Core](promote-pluto-prototype-to-reusable-core.md) |

## Semantic Status

- Scope: Circuit Workbench Manual, including Reusable Component versus
  project Plan Builder ownership, export-backed diagrams, and Pluto reuse.
- Prior state: `CONVERGING`.
- Current state: `STABILIZED` V1.
- State changed: 2026-07-28.
- Human acceptance: explicitly accepted the named
  “Circuit Workbench Reusable Component Ownership, Manual, and export-backed
  Schemdraw Guide V1” scope.
- Contract references: this Manual, Component Libraries, Components and
  Composition, and Contributing Circuit Diagrams.
- Validation evidence: docs language and route checks, 232-page Astro build,
  Python Sphinx warning-as-error build, targeted Schemdraw checks, and diff
  checks.
- Test policy: `stabilization_tests_authorized`; existing docs validators cover
  this documentation-only scope.
- Excluded: project circuit topology, automatic plan-wide schematic layout,
  and new public APIs.
- Unresolved decisions: none.
