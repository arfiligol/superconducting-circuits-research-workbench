---
aliases:
  - EngineeringGraph
  - Engineering Graph
  - SchematicExportSpec
tags:
  - diataxis/reference
  - audience/contributor
  - sot/true
  - topic/julia-core
status: stable
owner: docs-team
audience: contributor
scope: Human-facing engineering semantic graph, visualization, and schematic export contract for Julia Core authoring.
version: v1.0.0
last_updated: 2026-05-29
updated_by: codex
---

# Engineering Graph

`EngineeringGraph` is the human-facing semantic representation generated during `CircuitPlan` authoring. It is used for visualization, debugging, notebooks, reports, and schematic export.

It is not a solver netlist. It should not be reconstructed from JosephsonCircuits.jl rows.

## Purpose

EngineeringGraph answers questions that users and reviewers ask before they care about solver row details:

- Which reusable components are connected?
- What role does each component play?
- Which component couples to which component?
- Which port is signal, readout, pump, or DC bias?
- Which source slot enters which port?
- Which observable is being measured?

The JosephsonCircuits netlist answers a different question: which solver rows connect which solver nodes.

## Representation Pipeline

```text
@circuit / @hbintent
    -> canonical functional API
    -> CircuitPlan
    -> EngineeringGraph
    -> Josephson compiler
    -> JosephsonCircuits netlist
```

Visualization and export use the semantic graph, not the lowered netlist:

```text
EngineeringGraph
    -> Pluto engineering view
    -> SchematicExportSpec
    -> optional Schemdraw renderer
```

## EngineeringGraph Data Model

The first target model should stay renderer-neutral and component-level.

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
| `pins` | named pins / anchors |
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
```

Initial relation types:

```text
:connect
:couple
:drive
:observe
:contains
:feeds
:terminates
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
```

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

## Macro Capture Rules

Macro DSL should capture engineering semantics from user code.

```julia
plan = @circuit "readout-chain-demo" begin
    feedline = component(CPWFeedline(...); role = :feedline)
    resonator = component(QuarterWaveResonator(...); role = :readout_resonator)
    qubit = component(FloatingTransmon(...); role = :qubit)

    couple(
        feedline.output,
        resonator.input;
        through = CapacitiveCoupler(capacitance = Cc),
        role = :readout_coupling,
    )

    port(:readout_port) do
        endpoint = feedline.input
        role = :readout
        resistance = 50
    end
end
```

The macro should record:

- component variable names such as `feedline`, `resonator`, and `qubit`;
- component types such as `CPWFeedline`, `QuarterWaveResonator`, and `FloatingTransmon`;
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
    display_name = :resonator,
    role = :readout_resonator,
)
```

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

This lets Runner adapters, generated code, and tests build the same semantic representation without macro syntax.

## Visualization Backends

EngineeringGraph supports three visualization and export layers.

### Pluto Engineering View

Purpose:

```text
Fast interactive visualization in Pluto Notebook.
```

Initial implementation:

```text
- HTML / HypertextLiteral cards
- simple SVG / HTML graph
- DOT text preview
```

This view shows component-level structure and HB overlays before compilation.

### Graph Export

Purpose:

```text
General component graph export.
```

Target formats:

```text
- DOT
- JSON
- SVG if renderer is available
```

### Schemdraw Export

Purpose:

```text
Generate Python Schemdraw-compatible schematic data.
```

The exported data should include enough hints for Python to decide drawing order and element types.

Julia Core should not depend on Python Schemdraw. It should produce renderer-neutral data that a separate Python renderer can consume.

## SchematicExportSpec

`SchematicExportSpec` is the renderer-neutral schematic export shape:

```julia
SchematicExportSpec(
    components,
    relations,
    ports,
    groups,
    layout_hints,
    render_hints,
)
```

### Component Mapping

Each component entry should include:

```text
id
label
schematic_kind
parameters
pins
role
```

Example:

```json
{
  "id": "resonator",
  "label": "lambda/4 Resonator",
  "schematic_kind": "resonator",
  "role": "readout_resonator",
  "parameters": {
    "length": { "value": 0.0051, "unit": "m" }
  }
}
```

### Relation Mapping

Each relation entry should include:

```text
from
to
through
schematic_kind
label
direction_hint
```

Example:

```json
{
  "from": "feedline.output",
  "to": "resonator.input",
  "through": "Cc",
  "schematic_kind": "capacitive_coupling",
  "label": "Cc",
  "direction_hint": "right"
}
```

### Schemdraw Hints

The export may include:

```text
schemdraw_element
orientation
label
anchor
direction
length_hint
```

Example:

```json
{
  "schemdraw_element": "Capacitor",
  "label": "Cc",
  "direction": "right"
}
```

Do not hardcode every Schemdraw detail in Julia Core. Keep Schemdraw-specific data as hints.

## Cross-Links

- [Macro Authoring DSL](macro-authoring-dsl.md) captures source semantics for EngineeringGraph.
- [Compiled Circuit](compiled-circuit.md) is the solver-facing output and should preserve links back to engineering semantics.
- [HB Simulation Intent](hb-simulation-intent.md) overlays pump axes, source slots, and observables on ports and components.
- [Runner-Safe API](runner-safe-api.md) calls the same authoring path and must not invent EngineeringGraph semantics from task payloads.
