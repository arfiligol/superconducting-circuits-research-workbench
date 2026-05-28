---
aliases:
  - HB Simulation Intent
  - Harmonic Balance Simulation Intent
tags:
  - diataxis/reference
  - audience/contributor
  - sot/true
  - topic/julia-core
status: stable
owner: docs-team
audience: contributor
scope: Defines how CircuitPlan declares HB ports, source slots, pump axes, observables, and solver-facing intent.
version: v1.1.0
last_updated: 2026-05-29
updated_by: codex
---

# HB Simulation Intent

HB simulation intent is the CircuitPlan-level contract for harmonic-balance simulation. It declares external ports, pump axes, source slots, observable requests, and solver-facing defaults before Runner execution sees runtime values.

The core rule is:

```text
CircuitPlan declares simulation intent.
Compiler validates simulation intent against the compiled circuit.
Runner binds runtime values and executes the validated HB problem.
```

## Conceptual Pipeline

```text
CircuitPlan
  -> ExternalPort declarations
  -> HBIntent declarations
  -> compile_to_josephson
  -> JosephsonCompiledCircuit
  -> HBProblemSpec
  -> run_hbsolve / run_frequency_sweep
```

CircuitPlan declares what is allowed. The compiler validates and maps that intent into the compiled circuit. The Runner binds task runtime values to the validated slots. JosephsonCircuits.jl receives normalized netlist rows, component values, sources, frequencies, harmonic counts, and whitelisted solver controls.

!!! warning "Runner does not own HB semantics"
    Runner task payloads may choose runtime values, but they must not invent ports, source slots, pump axes, mode tuples, or observable meanings after compilation.

## ExternalPort

`ExternalPort` is the plan-level declaration for a physical or logical external port that may lower to JosephsonCircuits port rows.

Conceptual shape:

```julia
ExternalPort(
    id,
    index,
    endpoint,
    resistance_ohm,
    role,
)
```

| Field | Meaning |
| --- | --- |
| `id` | stable logical port name, such as `:signal_port`, `:pump_port`, or `:readout_port` |
| `index` | JosephsonCircuits port index |
| `endpoint` | CircuitPlan endpoint that lowers to a netlist node |
| `resistance_ohm` | reference / port resistance used when emitting port rows |
| `role` | semantic role such as `:signal`, `:pump`, `:readout`, `:dc_bias`, or `:mixed` |

Rules:

- port IDs must be unique;
- port indices must be unique;
- port endpoints must resolve during compile;
- external ports must lower to compatible JosephsonCircuits port rows;
- one physical port may support multiple source modes.

## PumpAxis

`PumpAxis` declares one independent pump-frequency axis in the HB problem.

Single pump:

```julia
PumpAxis(
    id = :pump,
    frequency_parameter = :pump_frequency_hz,
)
```

Double pump:

```julia
PumpAxis(id = :pump_1, frequency_parameter = :pump_1_frequency_hz)
PumpAxis(id = :pump_2, frequency_parameter = :pump_2_frequency_hz)
```

Rules:

- the number of pump axes defines the HB mode tuple dimension;
- single-pump mode examples use tuples like `(1,)`;
- double-pump mode examples use tuples like `(1, 0)` and `(0, 1)`;
- DC mode `(0,)` must be explicitly allowed where relevant.

## HBSourceSlot

`HBSourceSlot` declares a source slot that can be bound at runtime. The slot is part of the plan intent; the current value is a runtime binding.

Modeled large-signal source:

```julia
HBSourceSlot(
    id = :large_signal_in,
    role = :signal,
    port = :signal_port,
    mode = (1,),
    current_parameter = :large_signal_current_a,
)
```

Pump source:

```julia
HBSourceSlot(
    id = :pump_in,
    role = :pump,
    port = :pump_port,
    mode = (1,),
    current_parameter = :pump_current_a,
)
```

Double-pump source:

```julia
HBSourceSlot(
    id = :pump_1_in,
    role = :pump,
    port = :pump_port,
    mode = (1, 0),
    current_parameter = :pump_1_current_a,
)

HBSourceSlot(
    id = :pump_2_in,
    role = :pump,
    port = :pump_port,
    mode = (0, 1),
    current_parameter = :pump_2_current_a,
)
```

DC source:

```julia
HBSourceSlot(
    id = :dc_bias,
    role = :dc_bias,
    port = :pump_port,
    mode = (0,),
    current_parameter = :dc_current_a,
)
```

Rules:

- source slot IDs must be unique;
- source slot ports must reference existing `ExternalPort` declarations;
- source modes must be compatible with the declared pump axes;
- `current = 0.0` is valid and means the source is intentionally off;
- source slot existence is not fake compute even if its current value is zero;
- source slot current value is a runtime binding.

## HBSourceSlot vs Linearized Probe

`HBSourceSlot` describes sources passed to JosephsonCircuits `sources`, such as pump drives, DC bias, or intentionally modeled large-signal drives.

Small-signal S-parameter probing is not automatically a source slot. It is normally declared through `HBObservableRequest` as an output/input mode-port extraction from the linearized solution.

A signal can be represented as an `HBSourceSlot` only when the circuit model intentionally treats it as a source in `sources`.

Source slot example:

```julia
HBSourceSlot(
    id = :pump_in,
    role = :pump,
    port = :pump_port,
    mode = (1,),
    current_parameter = :pump_current_a,
)
```

Linearized probe example:

```julia
SParameterRequest(
    id = :s11_signal,
    outputmode = (0,),
    outputport = :signal_port,
    inputmode = (0,),
    inputport = :signal_port,
)
```

!!! warning "Do not create probe sources"
    Do not create a source slot only because an S-parameter input port exists.

## HBObservableRequest

Observable requests declare what the caller may extract from solver output.

Signal reflection:

```julia
SParameterRequest(
    outputmode = (0,),
    outputport = :signal_port,
    inputmode = (0,),
    inputport = :signal_port,
)
```

Idler observable:

```julia
SParameterRequest(
    outputmode = (-1,),
    outputport = :signal_port,
    inputmode = (0,),
    inputport = :signal_port,
)
```

Optional future observable families include:

```julia
QERequest(...)
QEIdealRequest(...)
CMRequest(...)
ZParameterRequest(...)
```

Rules:

- observable ports must reference declared external ports;
- observable modes must be compatible with pump axes;
- unsupported observable families must fail clearly;
- Runner result extraction should follow declared observables, not hardcoded S11 forever.

## HBIntent

`HBIntent` is the CircuitPlan-level simulation intent for harmonic-balance execution.

Conceptual shape:

```julia
HBIntent(
    pump_axes = [...],
    source_slots = [...],
    observables = [...],
    default_solver_controls = HBSolverControls(...),
)
```

Rules:

- `HBIntent` is related to topology, but not identical to topology;
- changing source current values does not change `HBIntent`;
- changing pump-axis dimension changes `HBIntent`;
- changing the number of source slots changes `HBIntent`;
- changing observable requests changes output intent.

## Key Separation

Julia Core uses separate keys for topology, HB intent, HB problem shape, and concrete runtime values.

```text
topology_key
hb_intent_key
hb_problem_shape_key
run_value_key
```

### topology_key

`topology_key` includes:

- component hierarchy;
- component types;
- relations;
- endpoint topology;
- external ports that emit netlist rows;
- structural parameters affecting emitted rows;
- line taps / spans / distributed segmentation.

### hb_intent_key

`hb_intent_key` includes:

- pump-axis declarations;
- source slot declarations;
- source roles;
- mode tuple declarations;
- observable request declarations;
- solver-control families allowed by the intent.

### hb_problem_shape_key

`hb_problem_shape_key` includes:

- harmonic counts;
- `returnS` / `returnZ` / `returnQE` / `returnCM`;
- `keyedarrays`;
- `sorting` if it changes output shape or indexing assumptions;
- mode truncation controls;
- optional kwargs that change solver problem structure.

### run_value_key

`run_value_key` includes:

- concrete frequency arrays;
- concrete pump-frequency values;
- concrete source current values;
- `current = 0.0` source-off bindings;
- numeric solver tolerances that do not alter problem shape;
- output slicing / display preferences.

| Change | topology_key | hb_intent_key | hb_problem_shape_key | run_value_key |
| --- | ---: | ---: | ---: | ---: |
| pump current nonzero to `0.0` | unchanged | unchanged | unchanged | changed |
| pump frequency value changes | unchanged | unchanged | unchanged | changed |
| add second pump axis | unchanged unless circuit changes | changed | changed | changed |
| change harmonic count | unchanged | unchanged | changed | changed |
| toggle `returnQE` | unchanged | unchanged | changed | changed |
| add idler observable | unchanged | changed | may change | changed |
| add new physical port | changed | changed | changed | changed |
| change line-tap position | changed | may change | may change | changed |
| change frequency sweep range | unchanged | unchanged | unchanged | changed |

## Validation Boundary

HB validation is split across compile time and run time.

### Compile-Time Validation

`compile_to_josephson(plan)` validates:

- external port endpoints resolve;
- port indices are unique;
- source slots reference existing ports;
- source mode tuples match pump-axis dimension;
- DC mode usage is explicitly allowed;
- observable requests reference existing ports;
- observable modes are compatible;
- compiled output contains enough port metadata for HB problem construction.

### Run-Time Validation

`build_hb_problem(compiled, run_spec)` validates:

- frequency sweep values are positive;
- pump frequency values are positive;
- harmonic tuple lengths match pump axis count;
- source current values are present or have explicit defaults;
- `current = 0.0` is accepted;
- optional solver kwargs are whitelisted;
- requested observables can be extracted from solver output.

## Implementation Status

This page is stable as the target source of truth. It is not claiming that every concept is already implemented.

| Concept | Target contract | Current implementation | Status |
| --- | --- | --- | --- |
| `ExternalPort` | first-class CircuitPlan declaration | currently approximated by `metadata[:external_ports]` in MVP | target |
| `HBIntent` | first-class plan-level intent | not implemented as a struct yet | target |
| `HBSourceSlot` | first-class source slot declaration | not implemented yet | target |
| `HBObservableRequest` | first-class observable declaration | current Runner extraction still MVP / trace-specific | target |
| `HBSolverControls` | typed first-class controls | current Runner only partially maps controls | target |
| `optional_hb_kwargs` | whitelist only | not fully implemented | target |
| `current = 0.0` | valid source-off runtime binding | should be accepted | design-stable |

## Related

- [JosephsonCircuits hbsolve Controls](josephsoncircuits-hbsolve-controls.md)
- [Compiler](compiler.md)
- [Compiled Circuit](compiled-circuit.md)
- [Runner-Safe API](runner-safe-api.md)
