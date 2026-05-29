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
scope: Target macro authoring DSL contract for CircuitPlan, HBIntent, and EngineeringGraph capture.
version: v1.1.0
last_updated: 2026-05-29
updated_by: codex
---

# Macro Authoring DSL

The Macro Authoring DSL is the target human-facing syntax for Julia Core circuit authoring. It should make notebooks and component-library examples readable while still expanding into the canonical functional API.

The macro layer is not a separate construction path. It records authoring intent, source provenance, and engineering semantics, then calls the same `CircuitPlan`, endpoint, relation, validation, compiler, and HB intent APIs used by generated code and Runner-safe plan builders.

## Pipeline

```text
Macro DSL
    -> canonical functional API
    -> CircuitPlan
    -> EngineeringGraph
    -> Visualization / SchematicExportSpec
    -> Compiler netlist
```

The macro output must remain inspectable. A user should be able to look at the expanded calls and see `register_component!`, `external_port!`, `hb_intent!`, and EngineeringGraph recording calls rather than hidden simulator rows.

## Notebook Role

Pluto notebooks that exercise the Macro DSL should stay simple enough to serve as both tutorials and acceptance harnesses. Prefer Markdown, compact tables, and callouts that show the contract the user is testing. Avoid adding complex visualization dependencies unless the cell is explicitly validating a renderer boundary.

Tutorial notebooks may define small local reusable components when the goal is to demonstrate macro expansion, EngineeringGraph capture, or HB problem construction. Those local examples are notebook fixtures, not Julia Core Kernel component families.

## Macro DSL Captures Engineering Semantics

The macro layer does not only make code shorter. It preserves the user's structural intent so Julia Core can build an [`EngineeringGraph`](engineering-graph.md).

Macro DSL is the best place to capture:

- display names from variable binding;
- block hierarchy;
- user-facing groups;
- relation wording such as `couple`, `drive`, and `observe`;
- source code and notebook provenance;
- port, source-slot, and observable declarations before solver lowering.

This semantic capture is why the macro layer should feed the EngineeringGraph directly. Julia Core should not reconstruct human-facing circuit structure from JosephsonCircuits.jl rows after compilation.

## Circuit Example

Use macro syntax for the authoring surface, but keep each declaration reducible to ordinary Julia Core calls:

```julia
plan = @circuit "readout-chain-demo" begin
    feedline = component(
        CPWFeedline(length = feedline_length);
        role = :feedline,
    )

    resonator = component(
        QuarterWaveResonator(length = resonator_length);
        role = :readout_resonator,
    )

    qubit = component(
        FloatingTransmon(EJ = EJ, EC = EC);
        role = :qubit,
    )

    couple(
        feedline.output,
        resonator.input;
        through = CapacitiveCoupler(capacitance = Cc),
        role = :readout_coupling,
    )

    couple(
        resonator.end,
        qubit.xy;
        through = CapacitiveCoupler(capacitance = Cxy),
        role = :qubit_readout_coupling,
    )

    port(:readout_port) do
        index = 1
        endpoint = feedline.input
        resistance = 50
        role = :readout
    end
end
```

The DSL should record the component variable names `feedline`, `resonator`, and `qubit`, the reusable component types, relation verbs, coupling component, endpoint expressions, and source location.

The concrete component names in this example are component-library examples. Julia Core owns the authoring kernel and expansion contract; it does not ship lab-specific resonator, qubit, feedline, JPA, SNAIL, or filter catalogs.

## HB Intent Example

HB simulation intent can use the same authoring style:

```julia
@hbintent plan begin
    pump_axis(:pump; frequency_parameter = :pump_frequency)

    source_slot(:pump_in) do
        role = :pump
        port = :readout_port
        mode = (1,)
        current_parameter = :pump_current
    end

    sparameter(:s11_signal) do
        outputmode = (0,)
        outputport = :readout_port
        inputmode = (0,)
        inputport = :readout_port
    end
end
```

The macro should expand into the same `hb_intent!`, `PumpAxis`, `HBSourceSlot`, and observable request objects used by the functional API.

The runtime profiles are `:pump_off`, `:pumped`, and `:pumped_dc`. They should share the same declared pump axis and pump source slot; `:pump_off` binds `source_currents[:pump_in] = 0.0` and still requires a finite positive `pump_frequencies[:pump]` value.

DC bias uses the same source-slot mechanism:

```julia
source_slot(:dc_bias) do
    role = :dc_bias
    port = :readout_port
    mode = (0,)
    current_parameter = :dc_current
end
```

The runtime binding for this slot is `source_currents[:dc_bias]`. The corresponding controls must enable DC handling with `dc = true`.

Requested output families should be explicit in the expanded intent or associated controls. S/Z/QE/QEideal/CM extraction must be family-complete for requested families and must fail clearly when a requested solver family is absent.

## Expansion Contract

Macro expansion should call canonical functions like:

```julia
register_component!(...)
external_port!(...)
hb_intent!(...)
connect!(...) / couple_capacitive!(...) / shunt_capacitor!(...) / shunt_inductor!(...)
record_engineering_component!(...)
record_engineering_port!(...)
record_engineering_group!(...)
```

Physical relation calls populate the standard EngineeringGraph relations while they update the CircuitPlan. Macro expansion should call `record_engineering_relation!(...)` only for extra semantic annotations or overlays that are not already captured by `connect!`, `couple_capacitive!`, `shunt_capacitor!`, `shunt_inductor!`, `couple_inductive!`, or `couple_window!`.

The compiler still lowers the CircuitPlan into the target solver representation.

## Functional API Parity

The functional API must be able to record the same semantics for generated code, tests, and Runner-safe plan builders:

```julia
resonator = register_component!(
    plan,
    QuarterWaveResonator(length = resonator_length);
    display_name = :resonator,
    role = :readout_resonator,
)

couple_capacitive!(
    plan;
    id = "feedline_to_resonator",
    from = pin(feedline, :output),
    to = pin(resonator, :input),
    capacitance = Cc,
    role = :readout_coupling,
)
```

Macro syntax is preferred for human authoring, but it must not become the only way to produce a valid EngineeringGraph.
