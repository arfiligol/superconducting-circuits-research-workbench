---
aliases:
 - Macro Authoring DSL
 - Julia Core Macro DSL
tags:
 - diataxis/reference
 - audience/contributor
 - sot/true
 - topic/julia-core
status: stable
owner: docs-team
audience: contributor
scope: Authoring macro contracts for reusable components, runnable CircuitPlan systems, and plan-bound HBIntent.
version: v2.0.0
last_updated: 2026-05-31
updated_by: codex
---

# Macro Authoring DSL

The Macro Authoring DSL is the schematic-like authoring surface for Julia Core. It lets a designer describe a superconducting circuit in code while the macro expansion still calls the canonical Core APIs for endpoints, relations, ports, validation, compilation, and harmonic-balance intent.

The macro layer has two authoring levels:

| Macro | Owns | Output |
| --- | --- | --- |
| `@circuit_component` | reusable component hierarchy / circuit template | component builder with an explicit public interface |
| `@circuit` | one complete runnable system-level design | `CircuitPlan` |

The macro layer is not a separate netlist language. It records source provenance, component hierarchy, engineering semantics, and schematic intent, then expands into the same Core objects used by functional builders.

## Authoring Pipeline

```text
@circuit_component / @circuit
 -> canonical Julia Core API
 -> CircuitPlan
 -> EngineeringGraph
 -> SchematicLayoutIntent
 -> SchematicExportSpec
 -> compiler netlist
```

`@circuit_component` and `@circuit` serve different purposes. A component macro defines a reusable template. A circuit macro instantiates one complete design point that can be validated, compiled, and simulated.

## Component Interfaces

`@circuit_component` must declare the interface that outside systems may use. Internal nodes are private by default.

| Interface concept | Meaning |
| --- | --- |
| `pin` | electrical endpoint intentionally exposed for normal external connection |
| `line` | exposed line-like interface that can be addressed by distance from head |
| `probe` | internal electrical endpoint intentionally exposed for measurement, debug, or coupling |
| `anchor` | non-electrical schematic, report, or layout reference point |

Only `pin`, line taps derived from `line`, and `probe` expose electrical endpoints. An `anchor` is not electrically connectable. If a reference point must accept a capacitor, port, transmission-window attachment, or other electrical relation, model it as a `pin`, line tap, or `probe`.

Line-like interfaces are declared with `line:main` or `line(:main)`. The `tap` accessor is not a declaration keyword; it retrieves an endpoint on a component line after an instance exists.

Component instances expose their public interface through stable accessors:

```julia
pin(instance,:name)
tap(instance, distance_from_head)
line_tap(instance; line =:main, at_m = distance_from_head)
probe(instance,:name)
anchor(instance,:name)
```

The shorthand `tap(instance, distance_from_head)` is valid only when the component exposes one unambiguous default line. Components with multiple exposed lines must use `line_tap(instance; line =:name, at_m = distance_from_head)`.

```julia
transmission_path! = @circuit_component "transmission_path" begin
  pin:head
  pin:tail
  line:main

  parameter(:length_m; unit = "m")
end
```

The instance keeps hierarchy available for `EngineeringGraph` and schematic export. The compiler may flatten the instance into solver rows after validation.

## Reusable LC Component

Use `@circuit_component` when a circuit fragment is meant to become reusable:

```julia
lc_resonator! = @circuit_component "lc_resonator" begin
  pin:signal

  parameter(:capacitance; unit = "F")
  parameter(:inductance; unit = "H")

  shunt_capacitor!(
    id =:Cres,
    at = pin(:signal),
    capacitance = capacitance,
    role =:resonator_capacitance,
    label = "Cres",
  )

  shunt_inductor!(
    id =:Lres,
    at = pin(:signal),
    inductance = inductance,
    role =:resonator_inductance,
    label = "Lres",
  )
end
```

The component declares one public electrical interface, `:signal`. The capacitor and inductor attach to that public endpoint, while any helper nodes inside the component body remain private.

## Runnable Circuit

Use `@circuit` for a complete system-level design:

```julia
plan = @circuit "one-port-lc" begin
  drive = external_node("drive")

  resonator = lc_resonator!(
    id =:res,
    signal = drive,
    capacitance = C,
    inductance = L,
  )

  port(:drive_port) do
    index = 1
    endpoint = pin(resonator,:signal)
    resistance = 50.0
    role =:reflection
  end
end
```

This block creates one runnable `CircuitPlan`. Reuse belongs in the `lc_resonator!` component definition; the plan owns the concrete design point, concrete endpoint bindings, and concrete port declaration.

## Primitive Relations

`@circuit` may contain primitive relations directly. Use this form when the circuit topology is clearer without an additional component boundary:

```julia
plan = @circuit "capacitive-probe" begin
  target = external_node("target")
  probe_node = external_node("probe")

  shunt_capacitor!(
    id =:Ctarget,
    at = target,
    capacitance = Ctarget,
    role =:node_capacitance,
  )

  couple_capacitive!(
    id =:Cprobe,
    from = probe_node,
    to = target,
    capacitance = Cprobe,
    role =:probe_coupling,
  )

  port(:probe_port) do
    index = 1
    endpoint = probe_node
    resistance = 50.0
    role =:probe
  end
end
```

Port `role` values are semantic metadata. A role does not create hidden components, hidden couplings, or analysis transforms. Physical coupling must be declared with a relation such as `couple_capacitive!`.

## Physical Generators

`@circuit` may call physical model generators next to primitive relations and component instances:

```julia
plan = @circuit "readout-qwr-mtl" begin
  input = external_node("input")
  output = external_node("output")
  qwr_open = external_node("qwr_open")

  readout = transmission_line!(
    id =:readout,
    head = input,
    tail = output,
    spec = readout_spec,
    head_termination =:external,
    tail_termination =:external,
    role =:readout_line,
  )

  qwr = quarter_wave_resonator!(
    id =:qwr,
    grounded_head = ground(),
    open_tail = qwr_open,
    spec = qwr_spec,
    role =:readout_resonator,
  )

  window = couple_transmission_window!(
    id =:readout_qwr_window,
    line1 = readout.line,
    line2 = qwr.line,
    start1 = 1.2e-3,
    start2 = 0.0,
    length = 500e-6,
    model = window_model,
    role =:distributed_readout_coupling,
  )

  port(:input_port) do
    index = 1
    endpoint = input
    resistance = 50.0
    role =:readout_input
  end

  port(:output_port) do
    index = 2
    endpoint = output
    resistance = 50.0
    role =:readout_output
  end
end
```

The line generators emit concrete ladder relations into the plan. The coupled-window generator records the distributed coupling relation and the schematic span needed by the engineering view.

## Hierarchical Component Usage

Reusable components, distributed models, and primitive relations may coexist in one circuit:

```julia
floating_lc! = @circuit_component "floating_lc" begin
  pin:island1
  pin:island2
  probe:differential_mode

  parameter(:capacitance; unit = "F")
  parameter(:inductance; unit = "H")

  couple_capacitive!(
    id =:Cq,
    from = pin(:island1),
    to = pin(:island2),
    capacitance = capacitance,
    role =:floating_capacitance,
  )

  series_inductor!(
    id =:Lq,
    from = pin(:island1),
    to = pin(:island2),
    inductance = inductance,
    role =:floating_inductance,
  )
end

plan = @circuit "floating-lc-xy" begin
  q = floating_lc!(
    id =:q,
    capacitance = Cq,
    inductance = Lq,
  )

  xy = transmission_line!(
    id =:xy,
    head = external_node("xy_input"),
    tail = external_node("xy_open"),
    spec = xy_spec,
    head_termination =:external,
    tail_termination =:open,
    role =:xy_line,
  )

  couple_capacitive!(
    id =:Cxy1,
    from = tap(xy, 1.0e-3),
    to = pin(q,:island1),
    capacitance = Cxy1,
    role =:xy_to_qubit_coupling,
  )

  couple_capacitive!(
    id =:Cxy2,
    from = tap(xy, 1.0e-3),
    to = pin(q,:island2),
    capacitance = Cxy2,
    role =:xy_to_qubit_coupling,
  )

  port(:xy_port) do
    index = 1
    endpoint = pin(xy,:head)
    resistance = 50.0
    role =:xy_drive
  end
end
```

The system-level circuit attaches only through exposed pins and taps. The component body remains responsible for its private implementation nodes.

## Termination Semantics

Transmission-line and resonator generators use explicit termination symbols:

| Termination | Contract |
| --- | --- |
| `:open` | terminal node exists; no ground connection is added; no outside connection is required |
| `:short` / `:grounded` | terminal node is connected to ground |
| `:external` | terminal node is exposed as an interface that must be connected by the enclosing circuit |

An unconnected `:external` terminal is a dangling interface endpoint and validation must report it. If the design intent is an open end, write `:open`.

## Plan-Bound HB Intent

`@hbintent` declares solver intent for an existing plan. Topology belongs in `@circuit`; harmonic-balance axes, source slots, observable requests, and defaults belong in `@hbintent`.

```julia
begin
  plan = @circuit "readout-qwr-mtl" begin
    input = external_node("input")
    output = external_node("output")

    readout = transmission_line!(
      id =:readout,
      head = input,
      tail = output,
      spec = readout_spec,
      head_termination =:external,
      tail_termination =:external,
      role =:readout_line,
    )

    port(:input_port) do
      index = 1
      endpoint = input
      resistance = 50.0
      role =:readout_input
    end

    port(:output_port) do
      index = 2
      endpoint = output
      resistance = 50.0
      role =:readout_output
    end
  end

  @hbintent plan begin
    pump_axis(:pump; frequency_parameter =:pump_frequency)

    source_slot(:pump_in) do
      role =:pump
      port =:input_port
      mode = (1,)
      current_parameter =:pump_current
    end

    sparameter(:s21) do
      outputmode = (0,)
      outputport =:output_port
      inputmode = (0,)
      inputport =:input_port
    end

    solver_controls() do
      n_pump_harmonics = 1
      n_modulation_harmonics = 1
      returnS = true
      returnZ = true
      returnQE = true
      returnCM = true
      keyedarrays = false
    end
  end

  plan
end
```

HB references are validated against the plan. A source slot or observable may reference only ports and mode dimensions declared by that plan's circuit and HB axes.

## Expansion Contract

Macro expansion must call canonical functions such as:

```julia
CircuitPlan(...)
external_node(...)
ground()
register_component!(...)
external_port!(...)
connect!(...)
couple_capacitive!(...)
couple_inductive!(...)
shunt_capacitor!(...)
shunt_inductor!(...)
series_inductor!(...)
series_resistor!(...)
transmission_line!(...)
quarter_wave_resonator!(...)
half_wave_resonator!(...)
couple_transmission_window!(...)
hb_intent!(...)
```

Physical relation calls populate the standard EngineeringGraph records while they update the plan. Extra graph annotations may be added only when they describe semantic overlays that are not already captured by a Core relation, port, component, or HB intent declaration.

The compiler lowers the validated plan to the solver representation. JosephsonCircuits.jl rows are the solver projection, not the authoring source of truth.
