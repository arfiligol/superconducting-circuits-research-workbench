---
aliases:
 - EngineeringGraph
 - Engineering Graph
tags:
 - diataxis/reference
 - audience/contributor
 - sot/true
 - topic/julia-core
status: stable
owner: docs-team
audience: contributor
scope: Human-facing engineering semantic graph contract for Julia Core authoring.
version: v1.2.0
last_updated: 2026-05-31
updated_by: codex
---

# Engineering Graph

`EngineeringGraph` is the human-facing semantic representation generated during `CircuitPlan` authoring. It captures what the circuit is: components, ports, relations, hierarchy, roles, HB overlays, and provenance.

It is not a solver netlist. It should not be reconstructed from JosephsonCircuits.jl rows.

It is also not the drawing layout. [`SchematicLayoutIntent`](schematic-layout-intent.md) answers how the circuit should be drawn.

## Purpose

EngineeringGraph answers questions that users and reviewers ask before they care about solver row details:

- Which reusable components are connected?
- What role does each component play?
- Which component couples to which component?
- Which port is signal, readout, pump, or DC bias?
- Which source slot enters which port?
- Which observable is being measured?
- Which relation is a point coupling, a distributed coupled window, a drive, or an observation?
- Which reusable component instance owns each public endpoint?

The JosephsonCircuits netlist answers a different question: which solver rows connect which solver nodes.

Schematic layout answers another question: which visual lane is above, which track is aligned with which other track, and where labels or terminals should appear. Keep these questions separate.

## Representation Pipeline

```text
@circuit / @hbintent
  -> canonical functional API
  -> CircuitPlan
  -> EngineeringGraph
  -> Josephson compiler
  -> JosephsonCircuits netlist
```

Schematic export uses the semantic graph plus drawing intent:

```text
EngineeringGraph
  + SchematicLayoutIntent
  -> SchematicExportSpec
  -> renderer
```

Notebook views should keep this layer easy to inspect. Use Markdown, compact tables, callouts, and renderer-neutral previews when the notebook is validating authoring semantics.

## EngineeringGraph Data Model

The model stays renderer-neutral and component-level.

### EngineeringComponent

```julia
EngineeringComponent(
  id,
  display_name,
  component_type,
  role,
  parameters,
  pins,
  source_location,
)
```

| Field | Meaning |
| --- | --- |
| `id` | stable component ID |
| `display_name` | user-facing label, often captured from macro variable name |
| `component_type` | reusable component type |
| `role` | semantic role, e.g. `:resonator`, `:qubit`, `:coupler`, `:feedline`, `:filter` |
| `parameters` | user-facing parameters with default units |
| `pins` | named electrical pins exposed by the component |
| `source_location` | macro provenance if available |

### EngineeringRelation

```julia
EngineeringRelation(
  id,
  relation_type,
  from,
  to,
  through,
  role,
  label,
  parameters,
  source_location,
)
```

Examples:

```text
feedline.signal -> resonator.feed through CapacitiveCoupler
resonator.end -> qubit.xy through CxyCoupler
pump_port -> SQUIDArray through PumpLine
readout_line sections 4:5 -> qwr sections 1:2 through MTL window
```

Relation types include:

```text
:connect
:couple
:drive
:observe
:contains
:feeds
:terminates
:coupled_window
:transmission_line_ladder
```

### EngineeringPort

```julia
EngineeringPort(
  id,
  component,
  endpoint,
  port_index,
  role,
  resistance,
  source_location,
)
```

Port roles include:

```text
:signal
:pump
:readout
:dc_bias
:mixed
:probe
:debug_probe
:reflection
```

Port roles are semantic metadata. A role such as `:probe` does not create a physical coupling element, remove a port termination, or apply post-processing. If the model needs a physical probe coupling, declare that coupling explicitly.

### EngineeringGroup

```julia
EngineeringGroup(
  id,
  label,
  role,
  members,
)
```

Examples:

```text
:readout_chain
:qubit_island
:pump_network
:coupling_network
```

### EngineeringHBIntentOverlay

HB simulation intent overlays solver-facing semantics onto the engineering graph:

```julia
EngineeringHBIntentOverlay(
  pump_axes,
  source_slots,
  observables,
)
```

The overlay should connect source slots and observables back to `EngineeringPort` and `EngineeringComponent` IDs.

## Boundary With Layout Intent

Engineering semantics and schematic layout intent are different layers.

EngineeringGraph answers:

```text
What is this circuit?
Which component couples to which component?
Which line is a readout line?
Which component is a QWR?
Which relation is a coupled window?
```

SchematicLayoutIntent answers:

```text
How should this circuit be drawn?
Which transmission line is on the top track?
Which line is on the bottom track?
Which segments are aligned?
Where should ports, grounds, opens, and labels appear?
```

Solver compilation uses electrical topology and parameters. It does not use drawing layout.

## Macro Capture Rules

Macro DSL should capture engineering semantics from user code.

```julia
plan = @circuit "readout-chain-demo" begin
  feedline = transmission_line!(
    id =:feedline,
    head = external_node("readout_in"),
    tail = external_node("readout_out"),
    spec = feedline_spec,
    head_termination =:external,
    tail_termination =:external,
    role =:feedline,
  )

  resonator = quarter_wave_resonator!(
    id =:resonator,
    grounded_head = ground(),
    open_tail = external_node("resonator_open"),
    spec = resonator_spec,
    role =:readout_resonator,
  )

  couple_capacitive!(
    id =:feedline_to_resonator,
    from = node_at_distance(feedline, coupling_position_m),
    to = resonator.line.nodes[end],
    capacitance = Cc,
    role =:readout_coupling,
  )

  port(:readout_port) do
    index = 1
    endpoint = feedline.head
    role =:readout
    resistance = 50
  end
end
```

The macro should record:

- component variable names such as `feedline` and `resonator`;
- component or generator types such as `transmission_line!` and `quarter_wave_resonator!`;
- relation type such as `couple`;
- through component type such as `CapacitiveCoupler`;
- port role such as `:readout`;
- endpoint expressions;
- notebook or source-code provenance.

The expansion should call canonical functions like:

```julia
register_component!(...)
external_port!(...)
record_engineering_component!(...)
record_engineering_relation!(...)
record_engineering_port!(...)
```

## Functional API Support

Macro DSL is preferred for human authoring, but the functional API must be able to record engineering semantics too.

```julia
register_component!(
  plan,
  QuarterWaveResonator(...);
  display_name =:resonator,
  role =:readout_resonator,
)
```

Standard physical operations record their EngineeringGraph relations as part of the same call. Users should normally call the physical operation, not duplicate it with a manual `record_engineering_relation!`.

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

The same rule applies to standard `connect!`, `couple_capacitive!`, `shunt_capacitor!`, `shunt_inductor!`, `couple_inductive!`, and `couple_window!` calls. Manual `record_engineering_relation!` is for extra semantic annotations, non-physical overlays, or metadata that is not already captured by the physical operation.

This lets Runner adapters, generated code, and tests build the same semantic representation without macro syntax while keeping the solver model and human-facing graph synchronized.

## Renderer-Neutral Export Boundary

`EngineeringGraph` supplies the semantic half of `SchematicExportSpec`. The layout half comes from `SchematicLayoutIntent`.

```text
SchematicExportSpec
  = EngineeringGraph
  + SchematicLayoutIntent
  + renderer-neutral hints
```

Renderers consume `SchematicExportSpec`. They do not define circuit semantics.

Schemdraw is one renderer for the export spec. Julia Core packages import no Python renderer packages and expose no Schemdraw-only circuit contract.

## Cross-Links

- [Macro Authoring DSL](macro-authoring-dsl.md) captures source semantics for EngineeringGraph.
- [Schematic Layout Intent](schematic-layout-intent.md) captures renderer-neutral drawing intent and defines `SchematicExportSpec`.
- [Compiled Circuit](compiled-circuit.md) is the solver-facing output and should preserve links back to engineering semantics.
- [HB Simulation Intent](hb-simulation-intent.mdx) overlays pump axes, source slots, and observables on ports and components.
- [Runner-Safe API](runner-safe-api.md) calls the same authoring path and must not invent EngineeringGraph semantics from task payloads.
